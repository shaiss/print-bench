"""The ONLY network module: GET-only REST, one read-only GraphQL query, ETag cache, pacing.

Every GitHub read the harvester makes goes through :class:`Client`
(tests/test_purity.py holds that no other module imports anything
network-capable, and that the only non-GET request in the package is the one
GraphQL call in :meth:`Client._graphql`, whose document — :data:`GRAPHQL_QUERY`
— is a constant containing no ``mutation``).

Rules (docs/provenance.md §API budget):

* **Base** — ``API_ROOT`` + ``/repos/{owner}/{repo}`` + path. ``Link:
  rel="next"`` is followed only when it stays on ``api.github.com``;
  ``/repositories/<id>/`` next-links are rewritten to ``/repos/{owner}/{repo}/``
  (GitHub accepts both; some proxies refuse the numeric form). A page cap
  (``max_pages``) raises :class:`Truncated` rather than return a silently
  short list — the caller records ``incomplete`` (e.g. ``commits-truncated``).
* **ETag** — every GET sends ``If-None-Match`` from the cache directory
  (``<out-dir>/etag-cache/``: ``<sha256(url)>.json`` = ``{etag, body}``);
  a ``304`` returns the cached body and does not count toward the request
  cap (GitHub does not charge it).
* **Cap** — :class:`Budget.max_requests` counts every non-304 response; the
  request that would exceed it raises :class:`BudgetExhausted` BEFORE it is
  sent. Scheduled runs use ``scheduled_max_requests`` (400).
* **Floor** — after each response, when ``X-RateLimit-Remaining`` <
  ``Budget.floor`` (``rate_floor``, 500): a scheduled run raises
  :class:`BudgetExhausted`; a self-paced dispatch (``Budget.pace``) sleeps
  until ``X-RateLimit-Reset`` + 5 s, unless that would pass
  ``Budget.deadline_epoch`` (the CAPTURE deadline: job start +
  ``dispatch_max_minutes`` − ``derive_reserve_minutes``), in which case
  it raises :class:`BudgetExhausted`. The floor is checked BEFORE the next
  request (the response that crossed it is still returned) and reads the REST
  ``core`` pool only — a GraphQL response (``X-RateLimit-Resource: graphql``,
  its own pool) never moves it. A primary-limit 403/429 (remaining 0) stops a
  schedule and makes a dispatch wait for the reset.
* **Retries** — a 5xx, a 403/429 carrying ``Retry-After`` or a secondary
  rate-limit message, or a socket timeout is retried up to 3 times with
  2/4/8 s backoff; 401/404/410/422 are not retried. A 404/410 on an object
  endpoint returns :data:`GONE` (the caller decides; e.g. a deleted run).
* **Headers** — ``Accept: application/vnd.github+json``,
  ``X-GitHub-Api-Version: 2022-11-28``, ``User-Agent: print-bench-provenance``,
  ``Authorization: Bearer $GH_TOKEN`` when a token is set.
* **Filtered lists cap at 1,000** — GitHub returns at most 1,000 results for
  a runs list filtered by ``created``/``branch``/``event``/``status``/
  ``actor``/``head_sha``/``check_suite_id``. The client exposes
  ``total_count`` per page (:meth:`Client.iter_pages`) so ``receipts.list_runs``
  can window by day and halve a capped window; nothing else in the package
  sends those filters (the gate's runs list is unfiltered, the artifact scan
  uses the repo-wide ``/actions/artifacts``).
* **Secrets in errors** — :class:`APIError` and :class:`Truncated` carry
  status, method and path only; the ``Authorization`` value never reaches an
  exception, a log line or the ETag cache (cache files hold ``{etag, body}``).
* **GraphQL** — one query document (:data:`GRAPHQL_QUERY`), variables only;
  used for review-thread resolution counts and ``lastEditedAt``. A 403 or
  ``errors`` payload raises :class:`GraphQLUnavailable`; the freezer then
  records ``incomplete: graphql-unavailable`` (the sandbox the scaffold was
  built in returns 403 for every GraphQL call — the fixtures carry
  ``threads.source: "ccr-fixture"`` instead; the production parser is
  therefore tested on canned GraphQL responses, paging included, in
  tests/test_github.py — critique item 27).

The package's modules use only the :class:`provenance.protocols.GitHubAPI`
surface (``get``, ``get_paged``, ``iter_pages`` and the two GraphQL calls) and
build their own paths, so ``tests/fakes.FakeGitHub`` stands in for every one
of them; this client carries no endpoint wrappers.

Owner: H1. Implements :class:`provenance.protocols.GitHubAPI`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional

API_ROOT = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
USER_AGENT = "print-bench-provenance"
API_VERSION = "2022-11-28"
TIMEOUT_S = 30
RETRIES = 3
GRAPHQL_MAX_PAGES = 50

#: Sentinel returned for a 404/410 on an object endpoint.
GONE = object()

#: The ONE read-only GraphQL document. ``$number`` is a PR or an issue
#: (``issueOrPullRequest``). No mutation, ever (a test pins the absence).
GRAPHQL_QUERY = """\
query ProvenanceThreads($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    issueOrPullRequest(number: $number) {
      ... on Issue { lastEditedAt }
      ... on PullRequest {
        lastEditedAt
        reviewThreads(first: 100, after: $after) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes { isResolved isOutdated comments(first: 1) { nodes { databaseId } } }
        }
      }
    }
  }
}
"""


class BudgetExhausted(Exception):
    """The request cap, the rate-limit floor or the dispatch deadline stopped the run (clean stop)."""


class GraphQLUnavailable(Exception):
    """The GraphQL endpoint refused (403), errored, or returned ``errors``."""


class Truncated(Exception):
    """A list endpoint had more pages than ``max_pages`` allows."""


class APIError(Exception):
    """A non-retryable, non-404 error status (message carries status and path, never the token).

    ``status`` is the HTTP status (``None`` for a transport failure after retries) so a
    caller can tell a 404 on a list endpoint (e.g. a run deleted between listing and its
    jobs GET) from any other failure.
    """

    def __init__(self, message: str, status: Optional[int] = None) -> None:
        super().__init__(message)
        self.status = status


#: transport(method, url, headers, body) -> (status, headers, body bytes). The
#: production transport wraps urllib; tests inject a canned one.
Transport = Callable[[str, str, dict[str, str], Optional[bytes]], tuple[int, dict[str, str], bytes]]


@dataclass
class Budget:
    """Request accounting for one run.

    ``max_requests`` — ``None`` = unlimited (a dispatch without ``max_requests``);
    ``floor`` — the ``X-RateLimit-Remaining`` floor; ``pace`` — sleep instead of
    stopping at the floor (dispatch); ``deadline_epoch`` — the capture deadline:
    no request is sent past it and no pacing sleep may cross it.
    ``used`` counts non-304 responses; ``not_modified`` counts 304s.
    """

    max_requests: Optional[int]
    floor: int
    pace: bool
    deadline_epoch: Optional[float] = None
    used: int = 0
    not_modified: int = 0
    last_remaining: Optional[int] = None
    stopped: Optional[str] = None
    last_reset: Optional[int] = None


#: Backoff before retry 1, 2, 3 (seconds).
BACKOFF_S = (2, 4, 8)
#: Statuses never retried (404/410 become GONE on an object endpoint).
NO_RETRY = frozenset({401, 404, 410, 422})
_LINK_RE = re.compile(r'<([^>]+)>\s*;\s*rel="([^"]+)"')
_REPOSITORIES_RE = re.compile(r"^/repositories/[0-9]+(?=/|$)")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect: urllib would replay the Authorization header to the new host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401 - urllib hook
        return None


def urllib_transport(method: str, url: str, headers: dict[str, str],
                     body: Optional[bytes]) -> tuple[int, dict[str, str], bytes]:
    """The production transport (urllib; honours HTTPS_PROXY via the default opener). H1.

    Every HTTP status — 3xx and 4xx/5xx included — is RETURNED, never raised
    (redirects are not followed: urllib's redirect handler would forward the
    ``Authorization`` header to whatever host the ``Location`` names); a
    socket-level failure raises ``OSError`` (``URLError``, ``TimeoutError``,
    ``ConnectionError``) for the client's retry loop.
    """
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with opener.open(req, timeout=TIMEOUT_S) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()
    except urllib.error.HTTPError as exc:
        try:
            data = exc.read()
        except Exception:  # an error body that cannot be read is an empty body
            data = b""
        return exc.code, dict(exc.headers.items()) if exc.headers else {}, data
    except OSError:
        raise
    except Exception as exc:  # http.client.IncompleteRead & co. (this module may not import http)
        raise ConnectionError(f"transport: {type(exc).__name__}") from None


@dataclass
class Client:
    """GET-only GitHub client for one repository. Implements ``protocols.GitHubAPI``."""

    repo: str
    token: str
    budget: Budget
    cache_dir: Optional[str] = None
    transport: Transport = field(default=urllib_transport)
    sleep: Callable[[float], None] = field(default=time.sleep)
    clock: Callable[[], float] = field(default=time.time)

    # -- plumbing -------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION,
             "User-Agent": USER_AGENT}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _url(self, path: str, params: Optional[dict[str, str]]) -> str:
        if not path.startswith("/") or "?" in path or "#" in path:
            raise ValueError(f"path must be a bare /-rooted path: {path!r}")
        query = urllib.parse.urlencode(sorted((k, str(v)) for k, v in (params or {}).items()))
        return f"{API_ROOT}/repos/{self.repo}{path}" + (f"?{query}" if query else "")

    def _stop(self, reason: str) -> None:
        self.budget.stopped = reason
        raise BudgetExhausted(reason)

    def _presend(self) -> None:
        """Deadline, rate-limit floor and request cap — checked BEFORE every send."""
        b = self.budget
        if b.stopped:
            raise BudgetExhausted(b.stopped)
        if b.deadline_epoch is not None and self.clock() >= b.deadline_epoch:
            self._stop("capture deadline reached")
        if b.last_remaining is not None and b.last_remaining < b.floor:
            if not b.pace:
                self._stop(f"X-RateLimit-Remaining {b.last_remaining} < floor {b.floor}")
            wait = (b.last_reset or 0) - self.clock() + 5
            if wait > 0:
                if b.deadline_epoch is not None and self.clock() + wait > b.deadline_epoch:
                    self._stop("rate-limit reset falls after the capture deadline")
                self.sleep(wait)
            b.last_remaining = None
        if b.max_requests is not None and b.used >= b.max_requests:
            self._stop(f"request cap {b.max_requests} reached")

    def _send(self, method: str, url: str, headers: dict[str, str], body: Optional[bytes],
              label: str) -> tuple[int, dict[str, str], bytes]:
        """One logical request with the retry policy; returns the final response.
        ``label`` (the path, never the query or a header) is all an error message names."""
        attempt = 0
        while True:
            self._presend()
            try:
                status, raw_headers, data = self.transport(method, url, headers, body)
            except OSError as exc:  # URLError, TimeoutError, ConnectionError
                if attempt < RETRIES:
                    self.sleep(BACKOFF_S[attempt])
                    attempt += 1
                    continue
                raise APIError(f"{method} {label}: transport failure ({type(exc).__name__}) "
                               f"after {RETRIES} retries") from None
            hdrs = {k.lower(): v for k, v in (raw_headers or {}).items()}
            if status == 304:
                self.budget.not_modified += 1
            else:
                self.budget.used += 1
            # The floor guards the REST ("core") pool the sibling workflows share; GraphQL has its
            # own pool (X-RateLimit-Resource: graphql) and its exhaustion is GraphQLUnavailable.
            if hdrs.get("x-ratelimit-resource", "core") == "core":
                remaining, reset = hdrs.get("x-ratelimit-remaining"), hdrs.get("x-ratelimit-reset")
                if remaining is not None and str(remaining).isdigit():
                    self.budget.last_remaining = int(remaining)
                if reset is not None and str(reset).isdigit():
                    self.budget.last_reset = int(reset)
            if attempt < RETRIES and status not in NO_RETRY:
                delay = self._retry_delay(status, hdrs, data, attempt)
                if delay is not None:
                    if delay:
                        if (self.budget.deadline_epoch is not None
                                and self.clock() + delay > self.budget.deadline_epoch):
                            self._stop("retry backoff falls after the capture deadline")
                        self.sleep(delay)
                    attempt += 1
                    continue
            if status in (403, 429) and self.budget.last_remaining == 0:
                self._stop(f"{method} {label}: primary rate limit exhausted (HTTP {status})")
            return status, hdrs, data

    def _retry_delay(self, status: int, hdrs: dict[str, str], data: bytes,
                     attempt: int) -> Optional[float]:
        """Seconds to wait before retrying, ``0`` for "retry after the floor wait", or ``None``."""
        if status >= 500:
            return BACKOFF_S[attempt]
        if status in (403, 429):
            ra = hdrs.get("retry-after")
            secondary = b"secondary rate limit" in (data or b"").lower()
            if ra is not None or secondary:
                extra = int(ra) if (ra is not None and str(ra).isdigit()) else 0
                return max(BACKOFF_S[attempt], extra)
            if self.budget.last_remaining == 0 and self.budget.pace:
                return 0  # primary limit: _presend sleeps until X-RateLimit-Reset + 5 s
        return None

    def _cache_path(self, url: str) -> Optional[str]:
        if not self.cache_dir:
            return None
        return os.path.join(self.cache_dir, hashlib.sha256(url.encode("utf-8")).hexdigest() + ".json")

    def _fetch(self, url: str, label: str) -> tuple[Optional[bytes], Optional[str]]:
        """``(body, Link header)`` of one GET; ``(None, None)`` on 404/410; :class:`APIError`
        on any other non-2xx/304 status. ETag-conditional when the cache holds the URL."""
        cache_file = self._cache_path(url)
        cached: Optional[dict[str, Any]] = None
        if cache_file and os.path.isfile(cache_file):
            try:
                with open(cache_file, encoding="utf-8") as fh:
                    cached = json.load(fh)
            except (OSError, ValueError):
                cached = None
        headers = self._headers()
        if cached and cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        status, hdrs, data = self._send("GET", url, headers, None, label)
        if status == 304 and cached is not None:
            return cached["body"].encode("utf-8"), cached.get("link")
        if status in (404, 410):
            return None, None
        if not 200 <= status < 300:
            raise APIError(f"HTTP {status} GET {label}", status=status)
        etag = hdrs.get("etag")
        if cache_file and etag:
            os.makedirs(self.cache_dir, exist_ok=True)
            tmp = cache_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"body": data.decode("utf-8"), "etag": etag, "link": hdrs.get("link")}, fh)
            os.replace(tmp, cache_file)
        return data, hdrs.get("link")

    def _next_url(self, link: Optional[str], label: str) -> Optional[str]:
        """The ``rel="next"`` URL, kept on ``api.github.com`` and this repository."""
        if not link:
            return None
        nxt = next((u for u, rel in _LINK_RE.findall(link) if rel == "next"), None)
        if nxt is None:
            return None
        parts = urllib.parse.urlsplit(nxt)
        if parts.scheme != "https" or parts.netloc != "api.github.com":
            raise APIError(f"GET {label}: refusing a next link off api.github.com")
        path = _REPOSITORIES_RE.sub(f"/repos/{self.repo}", parts.path)
        prefix = f"/repos/{self.repo}/".lower()
        if not (path.lower() + "/").startswith(prefix):
            raise APIError(f"GET {label}: refusing a next link outside /repos/{self.repo}")
        return urllib.parse.urlunsplit(("https", "api.github.com", path, parts.query, ""))

    # -- protocols.GitHubAPI ---------------------------------------------------
    def get(self, path: str, params: Optional[dict[str, str]] = None) -> Any:
        """One GET of ``/repos/{repo}{path}``; ETag-cached; :data:`GONE` on 404/410."""
        body, _ = self._fetch(self._url(path, params), path)
        if body is None:
            return GONE
        return json.loads(body.decode("utf-8"))

    def get_paged(self, path: str, params: Optional[dict[str, str]] = None,
                  key: Optional[str] = None, max_pages: int = 50) -> list[Any]:
        """All pages (``per_page=100``) concatenated; ``key`` unwraps ``{key: [...]}``; raises :class:`Truncated`.

        A 404/410 raises :class:`APIError` with ``status`` set (a list has no
        :data:`GONE` form; the caller decides, e.g. receipts skips a deleted run)."""
        out: list[Any] = []
        for items, _ in self.iter_pages(path, params, key=key, max_pages=max_pages):
            out.extend(items)
        return out

    def iter_pages(self, path: str, params: Optional[dict[str, str]] = None,
                   key: Optional[str] = None,
                   max_pages: int = 50) -> Iterator[tuple[list[Any], Optional[int]]]:
        """Lazy pages ``(items, total_count)`` in API order (``protocols.GitHubAPI.iter_pages``)."""
        query = dict(params or {})
        query.setdefault("per_page", "100")
        url: Optional[str] = self._url(path, query)
        pages = 0
        while url is not None:
            if pages >= max_pages:
                raise Truncated(f"GET {path}: more than {max_pages} pages")
            body, link = self._fetch(url, path)
            if body is None:
                raise APIError(f"HTTP 404 GET {path}", status=404)
            data = json.loads(body.decode("utf-8"))
            pages += 1
            items = (data.get(key) or []) if (key and isinstance(data, dict)) else data
            if not isinstance(items, list):
                raise APIError(f"GET {path}: page is not a JSON list (key={key!r})")
            total = data.get("total_count") if isinstance(data, dict) else None
            yield items, (total if isinstance(total, int) and not isinstance(total, bool) else None)
            url = self._next_url(link, path)

    def graphql_pr_threads(self, number: int) -> dict[str, Any]:
        """``{"nodes": [{first_comment_id, resolved, outdated}], "last_edited_at": ts|None}``
        (paging ``reviewThreads`` with ``$after``); :class:`GraphQLUnavailable` on refusal."""
        owner, name = self.repo.split("/", 1)
        nodes: list[dict[str, Any]] = []
        after: Optional[str] = None
        last_edited: Optional[str] = None
        for _ in range(GRAPHQL_MAX_PAGES):
            data = self._graphql({"owner": owner, "name": name, "number": int(number), "after": after})
            obj = (data.get("repository") or {}).get("issueOrPullRequest")
            if not isinstance(obj, dict):
                raise GraphQLUnavailable(f"graphql: #{number} not found")
            last_edited = obj.get("lastEditedAt")
            threads = obj.get("reviewThreads")
            if not isinstance(threads, dict):
                break  # an issue: no review threads
            for n in threads.get("nodes") or []:
                comments = (n.get("comments") or {}).get("nodes") or []
                nodes.append({"first_comment_id": comments[0].get("databaseId") if comments else None,
                              "outdated": bool(n.get("isOutdated")),
                              "resolved": bool(n.get("isResolved"))})
            info = threads.get("pageInfo") or {}
            if not info.get("hasNextPage"):
                break
            after = info.get("endCursor")
            if not after:
                raise GraphQLUnavailable("graphql: hasNextPage without endCursor")
        else:
            raise Truncated(f"graphql #{number}: more than {GRAPHQL_MAX_PAGES} reviewThreads pages")
        return {"last_edited_at": last_edited, "nodes": nodes}

    def graphql_issue_edited(self, number: int) -> Optional[str]:
        """``lastEditedAt`` of an issue via :data:`GRAPHQL_QUERY`."""
        owner, name = self.repo.split("/", 1)
        data = self._graphql({"owner": owner, "name": name, "number": int(number), "after": None})
        obj = (data.get("repository") or {}).get("issueOrPullRequest")
        if not isinstance(obj, dict):
            raise GraphQLUnavailable(f"graphql: #{number} not found")
        return obj.get("lastEditedAt")

    def _graphql(self, variables: dict[str, Any]) -> dict[str, Any]:
        """The single non-GET request in the package: the GraphQL query, read-only. H1.

        Counted against the same budget as REST; never ETag-cached. A 403, any
        other non-200, a transport failure, a non-JSON body or an ``errors``
        payload raises :class:`GraphQLUnavailable`."""
        body = json.dumps({"query": GRAPHQL_QUERY, "variables": variables}, sort_keys=True).encode("utf-8")
        headers = self._headers()
        headers["Content-Type"] = "application/json"
        try:
            status, _, data = self._send("POST", GRAPHQL_URL, headers, body, "graphql")
        except APIError as exc:
            raise GraphQLUnavailable(str(exc)) from None
        if status != 200:
            raise GraphQLUnavailable(f"graphql: HTTP {status}")
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise GraphQLUnavailable("graphql: body is not JSON") from None
        if not isinstance(payload, dict) or payload.get("errors") or not isinstance(payload.get("data"), dict):
            raise GraphQLUnavailable("graphql: errors payload")
        return payload["data"]
