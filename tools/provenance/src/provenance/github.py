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
  ``Budget.deadline_epoch`` (start + ``dispatch_max_minutes``), in which case
  it raises :class:`BudgetExhausted`.
* **Retries** — a 5xx, a 403/429 carrying ``Retry-After`` or a secondary
  rate-limit message, or a socket timeout is retried up to 3 times with
  2/4/8 s backoff; 401/404/410/422 are not retried. A 404/410 on an object
  endpoint returns :data:`GONE` (the caller decides; e.g. a deleted run).
* **Headers** — ``Accept: application/vnd.github+json``,
  ``X-GitHub-Api-Version: 2022-11-28``, ``User-Agent: print-bench-provenance``,
  ``Authorization: Bearer $GH_TOKEN`` when a token is set.
* **GraphQL** — one query document (:data:`GRAPHQL_QUERY`), variables only;
  used for review-thread resolution counts and ``lastEditedAt``. A 403 or
  ``errors`` payload raises :class:`GraphQLUnavailable`; the freezer then
  records ``incomplete: graphql-unavailable`` (the sandbox the scaffold was
  built in returns 403 for every GraphQL call — the fixtures carry
  ``threads.source: "ccr-fixture"`` instead).

Owner: H1. Implements :class:`provenance.protocols.GitHubAPI`.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

API_ROOT = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
USER_AGENT = "print-bench-provenance"
API_VERSION = "2022-11-28"
TIMEOUT_S = 30
RETRIES = 3

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
    """A non-retryable, non-404 error status (message carries status and path, never the token)."""


#: transport(method, url, headers, body) -> (status, headers, body bytes). The
#: production transport wraps urllib; tests inject a canned one.
Transport = Callable[[str, str, dict[str, str], Optional[bytes]], tuple[int, dict[str, str], bytes]]


@dataclass
class Budget:
    """Request accounting for one run.

    ``max_requests`` — ``None`` = unlimited (a dispatch without ``max_requests``);
    ``floor`` — the ``X-RateLimit-Remaining`` floor; ``pace`` — sleep instead of
    stopping at the floor (dispatch); ``deadline_epoch`` — stop pacing past it.
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


def urllib_transport(method: str, url: str, headers: dict[str, str],
                     body: Optional[bytes]) -> tuple[int, dict[str, str], bytes]:
    """The production transport (urllib; honours HTTPS_PROXY via the default opener). H1."""
    raise NotImplementedError("builder H1: urllib transport")


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

    def get(self, path: str, params: Optional[dict[str, str]] = None) -> Any:
        """One GET of ``/repos/{repo}{path}``; ETag-cached; :data:`GONE` on 404/410."""
        raise NotImplementedError("builder H1")

    def get_paged(self, path: str, params: Optional[dict[str, str]] = None,
                  key: Optional[str] = None, max_pages: int = 50) -> list[Any]:
        """All pages (``per_page=100``) concatenated; ``key`` unwraps ``{key: [...]}``; raises :class:`Truncated`."""
        raise NotImplementedError("builder H1")

    def graphql_pr_threads(self, number: int) -> dict[str, Any]:
        """``{"nodes": [{first_comment_id, resolved, outdated}], "last_edited_at": ts|None}``
        (paging ``reviewThreads`` with ``$after``); :class:`GraphQLUnavailable` on refusal."""
        raise NotImplementedError("builder H1")

    def graphql_issue_edited(self, number: int) -> Optional[str]:
        """``lastEditedAt`` of an issue via :data:`GRAPHQL_QUERY`."""
        raise NotImplementedError("builder H1")

    def _graphql(self, variables: dict[str, Any]) -> dict[str, Any]:
        """The single non-GET request in the package: the GraphQL query, read-only. H1."""
        raise NotImplementedError("builder H1")

    # -- endpoint wrappers (each one GET or one paged GET) --------------------

    def list_workflow_runs(self, workflow: str, *, created: Optional[str] = None,
                           branch: Optional[str] = None, event: Optional[str] = None,
                           status: Optional[str] = None, max_pages: int = 50) -> list[dict[str, Any]]:
        """``/actions/workflows/{workflow}/runs`` (``created`` is GitHub's ``created=`` filter,
        e.g. ``>=2026-10-01T00:00:00Z``), all pages, ``workflow_runs`` unwrapped."""
        raise NotImplementedError("builder H1")

    def run_jobs(self, run_id: int) -> list[dict[str, Any]]:
        """``/actions/runs/{id}/jobs?filter=all`` — every attempt's jobs, complete objects."""
        raise NotImplementedError("builder H1")

    def run_artifacts(self, run_id: int) -> list[dict[str, Any]]:
        """``/actions/runs/{id}/artifacts`` (names only are used: intent artifacts)."""
        raise NotImplementedError("builder H1")

    def closed_pulls_updated_since(self, since: Optional[str]) -> list[dict[str, Any]]:
        """``/pulls?state=closed&sort=updated&direction=desc``, paged until ``updated_at < since``."""
        raise NotImplementedError("builder H1")

    def issues_updated_since(self, label: str, since: Optional[str]) -> list[dict[str, Any]]:
        """``/issues?labels=<label>&state=all&sort=updated&direction=desc&since=<since>`` (PRs filtered out)."""
        raise NotImplementedError("builder H1")
