"""Thin live read of the repo's open status issues — the tool's only I/O.

Everything here is a **GET**: the reconciler's package is advisory-only, and
this module is written so that property is checkable — ``tests/test_purity.py``
asserts the pure modules import nothing network-capable, and that no HTTP
write verb appears anywhere in the package (the workflow's github-script
step is the sole write surface).

``_get`` is the single network seam, so the tests monkeypatch it and no
request ever leaves the process — the same discipline
``tools/backlog-groomer/src/backlog_groomer/github.py`` documents.
Pagination follows the ``Link: rel="next"`` header with a hard page cap that
raises rather than silently truncating: a partial listing could miss the
open status issue and open a duplicate beside it.
"""

from __future__ import annotations

import json
import re
import sys
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
        body, link = _get(next_url, token)
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
