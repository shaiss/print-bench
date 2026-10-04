"""The growth desk's GitHub read seam — GET-only, the dedup context's one I/O.

``python3 -m growth dedup-context --repo <owner/name>`` needs every issue that
carries ANY ``channel:*`` label: open ones whatever their age, closed ones
inside the window. The REST issues endpoint filters by exact label names, so
this lists the repository's labels once, keeps the ``channel:*`` ones, and per
channel makes two strongly-consistent listings (never the eventually-
consistent Search API — a tail link refreshing the context must see the
items the head link filed seconds earlier):

* ``state=open`` — every open item, however old;
* ``state=closed&since=<cutoff>`` — ``since`` filters on ``updated_at``, a
  superset of "closed inside the window" (closing an issue updates it), so
  the pure layer (:func:`growth.dedup.build`) applies the exact
  ``closed_at`` cutoff.

Everything here is a GET, and that is checkable: ``tests/test_purity.py``
holds this module to urllib-only imports, no HTTP write verb anywhere in the
file, and no request body on any ``Request`` it builds. The package's only
other network module is :mod:`growth.poster` (the X seam), so the growth
engine can READ GitHub but never write to it.

``_get`` is the single network seam, so tests monkeypatch it and no request
leaves the process — the tools/andon discipline, copied with its bounded
retry on transient failures (5xx, 429, GitHub's secondary-rate-limit 403, a
socket timeout) and its hard page cap that raises rather than silently
truncating: a partial listing would be a dedup list with holes in it.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

from .dedup import CHANNEL_PREFIX

API_ROOT = "https://api.github.com"

# Fail-loud bound: at per_page=100 this is 5k items per listing, far above
# anything one channel will see. Hitting it means something is wrong, and a
# wrong listing must not quietly become a confident dedup list.
_MAX_PAGES = 50

# Per-request timeout: a stalled socket should fail in seconds, not eat the
# step's budget ahead of the agent run it feeds.
_TIMEOUT_S = 30

# Retry policy for TRANSIENT failures only: three attempts, sleeps summing to
# 6 s. Tests monkeypatch ``time.sleep`` (via this module's ``time``).
_RETRY_DELAYS = (2.0, 4.0)

# The HTTP statuses that mean "try again", not "you are wrong". Anything else
# (401 bad token, 404 no such repo, 422 bad query) surfaces on attempt one.
_RETRY_STATUSES = frozenset({403, 429, 500, 502, 503, 504})

_LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')


def _get(url: str, token: str) -> tuple[Any, str]:
    """One GET; returns ``(parsed JSON body, Link header or "")``. Built with
    no request body, so urllib can only ever send a GET."""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "print-bench-growth",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
        return json.load(resp), resp.headers.get("Link", "")


def _is_transient(exc: BaseException) -> bool:
    """Could a second attempt clear this? ``HTTPError`` subclasses
    ``URLError``, so it is tested first: only the statuses in
    :data:`_RETRY_STATUSES` retry; a bare ``URLError`` or a timeout always
    does."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in _RETRY_STATUSES
    return isinstance(exc, (urllib.error.URLError, TimeoutError))


def _get_with_retry(url: str, token: str) -> tuple[Any, str]:
    """``_get`` with bounded retries on transient failures only; the last
    transient error is re-raised once the delays are spent."""
    for attempt, delay in enumerate(_RETRY_DELAYS + (None,)):
        try:
            return _get(url, token)
        except Exception as exc:  # noqa: BLE001 — classified right below
            if not _is_transient(exc) or delay is None:
                raise
            print(
                f"warning: transient GitHub API failure on attempt {attempt + 1} "
                f"({exc}); retrying in {delay:g}s",
                file=sys.stderr,
            )
            time.sleep(delay)
    raise AssertionError("unreachable: the retry loop always returns or raises")


def _paged(url: str, token: str) -> list[Any]:
    """Every item from ``url``, following Link rel="next" up to the cap."""
    items: list[Any] = []
    pages = 0
    next_url: Optional[str] = url
    while next_url:
        pages += 1
        if pages > _MAX_PAGES:
            raise RuntimeError(
                f"more than {_MAX_PAGES} pages from {url} — refusing to build "
                "a silently-truncated dedup list"
            )
        body, link = _get_with_retry(next_url, token)
        if not isinstance(body, list):
            # An error payload is an object, not a list; extending with one
            # would iterate its keys and fail confusingly far downstream.
            raise RuntimeError(
                f"unexpected non-list response from {next_url} "
                f"(got {type(body).__name__}) — refusing to build a dedup list from it"
            )
        items.extend(body)
        match = _LINK_NEXT_RE.search(link)
        next_url = match.group(1) if match else None
    return items


def channel_labels(repo: str, token: str) -> list[str]:
    """The repository's ``channel:*`` label names, sorted."""
    raw = _paged(f"{API_ROOT}/repos/{repo}/labels?per_page=100", token)
    return sorted(
        str(lbl.get("name", "")) for lbl in raw
        if isinstance(lbl, dict) and str(lbl.get("name", "")).startswith(CHANNEL_PREFIX)
    )


def channel_issues(repo: str, token: str, cutoff: datetime) -> list[dict]:
    """Every issue carrying a ``channel:*`` label that is open, or closed and
    updated since ``cutoff`` — the raw REST dicts, de-duplicated by number
    (an item carrying two channel labels is listed once). Pull requests are
    left in for :func:`growth.dedup.build` to drop with the rest of its
    filtering, so the policy has one home."""
    since = cutoff.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    found: dict[int, dict] = {}
    for label in channel_labels(repo, token):
        for params in (
            {"state": "open", "labels": label, "per_page": 100},
            {"state": "closed", "labels": label, "since": since, "per_page": 100},
        ):
            query = urllib.parse.urlencode(params)
            for item in _paged(f"{API_ROOT}/repos/{repo}/issues?{query}", token):
                if isinstance(item, dict) and isinstance(item.get("number"), int):
                    found.setdefault(item["number"], item)
    return [found[n] for n in sorted(found)]
