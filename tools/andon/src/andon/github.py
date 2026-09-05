"""Thin live read of the repo's open status issues — the tool's only I/O.

Everything here is a **GET**: the reconciler's package is advisory-only, and
this module is written so that property is checkable — ``tests/test_purity.py``
asserts the pure modules import nothing network-capable, and that no HTTP
write verb appears anywhere in the package (the workflow's github-script
step is the sole write surface).

``_get`` is the single network seam, so the tests monkeypatch it and no
request ever leaves the process — the same discipline
``tools/backlog-groomer/src/backlog_groomer/github.py`` documents.
``_get_with_retry`` wraps that seam so a transient API blip — a 5xx, a 429,
GitHub's secondary-rate-limit 403, a socket timeout — is retried a bounded
number of times with a short backoff instead of turning the hourly keyless
reconciler red on every hiccup; a real error (401, 404, 422 …) is re-raised
on the first attempt, and the transient error itself is re-raised after the
last. Pagination follows the ``Link: rel="next"`` header with a hard page
cap that raises rather than silently truncating: a partial listing could
miss the open status issue and open a duplicate beside it.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from .policy import LABEL, MARKER, OpenIssue, parse_iso

API_ROOT = "https://api.github.com"

# Fail-loud bound: at per_page=100 this is 10k items per listing, far above
# anything this repo will see.  Hitting it means something is wrong, and a
# wrong listing must not quietly become a confident decision.
_MAX_PAGES = 100

# Per-request timeout: the workflow bounds a hung *job* at 10 minutes, but a
# stalled socket should fail in seconds, not eat that whole budget.
_TIMEOUT_S = 30

# Retry policy for TRANSIENT failures only. One delay per retry, so the
# attempt count is len(_RETRY_DELAYS) + 1 = 3; the sleeps sum to 6 s, well
# inside the job's 10-minute bound even with three timed-out sockets. Tests
# monkeypatch ``time.sleep`` (via this module's ``time``) so no test waits.
_RETRY_DELAYS = (2.0, 4.0)

# The HTTP statuses that mean "try again", not "you are wrong": the 5xx
# family, 429 (rate limited) and 403 — GitHub's secondary rate limit answers
# 403, and an unauthenticated GET that hits the primary limit does too.
# Anything else (401 bad token, 404 no such repo, 422 bad query) is a real
# error and must surface on the first attempt.
_RETRY_STATUSES = frozenset({403, 429, 500, 502, 503, 504})

_LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')


def _get(url: str, token: str) -> tuple[Any, str]:
    """One GET; returns ``(parsed JSON body, Link header or "")``."""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "print-bench-andon",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
        return json.load(resp), resp.headers.get("Link", "")


def _is_transient(exc: BaseException) -> bool:
    """Is this failure one a second attempt could reasonably clear?

    ``HTTPError`` is a ``URLError`` subclass, so it is tested first: an HTTP
    answer is transient only when its status is in :data:`_RETRY_STATUSES`.
    A bare ``URLError`` (DNS, connection reset) or a ``TimeoutError`` (the
    socket timeout ``urlopen`` raises past ``_TIMEOUT_S``) is always
    transient.
    """
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in _RETRY_STATUSES
    return isinstance(exc, (urllib.error.URLError, TimeoutError))


def _get_with_retry(url: str, token: str) -> tuple[Any, str]:
    """``_get`` with bounded retries on transient failures only.

    Up to ``len(_RETRY_DELAYS) + 1`` attempts; a non-transient error is
    re-raised immediately (a 401/404/422 will not improve by waiting), and
    the last transient error is re-raised once the delays are spent so the
    step still fails loudly on a real outage.
    """
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
                "a silently-truncated listing"
            )
        body, link = _get_with_retry(next_url, token)
        if not isinstance(body, list):
            # An error payload is an object, not a list; extending with one
            # would iterate its keys and fail confusingly far downstream.
            raise RuntimeError(
                f"unexpected non-list response from {next_url} "
                f"(got {type(body).__name__}) — refusing to decide from it"
            )
        items.extend(body)
        match = _LINK_NEXT_RE.search(link)
        next_url = match.group(1) if match else None
    return items


def find_open_status_issue(repo: str, token: str) -> Optional[OpenIssue]:
    """The open andon status issue, or ``None`` when the cord has no record.

    Lists the OPEN issues carrying :data:`~andon.policy.LABEL`, drops the
    pull requests the issues endpoint interleaves, keeps only bodies that
    start with :data:`~andon.policy.MARKER` (belt-and-braces with the label —
    a human-applied label on an unrelated issue must not be mistaken for the
    status record), and picks the OLDEST by ``created_at`` so the episode's
    true start is what the closing comment reports. More than one candidate
    is a state the reconciler never creates itself, so it is logged to
    stderr rather than silently collapsed.
    """
    query = urllib.parse.urlencode({"state": "open", "labels": LABEL, "per_page": 100})
    raw = _paged(f"{API_ROOT}/repos/{repo}/issues?{query}", token)
    candidates: list[OpenIssue] = []
    for item in raw:
        if "pull_request" in item:
            continue  # the issues endpoint interleaves PRs; drop them
        body = item.get("body") or ""
        if not body.startswith(MARKER):
            continue
        candidates.append(OpenIssue(int(item["number"]), parse_iso(item["created_at"])))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (c.created_at, c.number))
    if len(candidates) > 1:
        numbers = ", ".join(f"#{c.number}" for c in candidates)
        print(
            f"warning: {len(candidates)} open andon status issues carry the marker "
            f"({numbers}); using the oldest, #{candidates[0].number} — the others "
            "were not opened by the reconciler and should be closed by hand",
            file=sys.stderr,
        )
    return candidates[0]
