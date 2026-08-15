"""Thin live read of the repo's open issues and PRs — the tool's only I/O.

Everything here is a **GET**: the groomer is advisory-only, and this module
is written so that property is checkable — ``tests/test_detectors.py``
asserts the pure core imports nothing network-capable, and that no HTTP
write verb appears anywhere in the package (the workflow's upsert step is
the sole write surface).

``_get`` is the single network seam, so the tests monkeypatch it and no
request ever leaves the process — the same discipline
``tools/backlog-burn/src/backlog_burn/github.py`` documents.  Pagination
follows the ``Link: rel="next"`` header with a hard page cap that raises
rather than silently truncating: a partial snapshot would make the report
lie about coverage.
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

API_ROOT = "https://api.github.com"

# Fail-loud bound: at per_page=100 this is 10k items per listing, far above
# anything this repo will see.  Hitting it means something is wrong, and a
# wrong snapshot must not quietly become a confident report.
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
            "User-Agent": "print-bench-backlog-groomer",
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
                "a silently-truncated snapshot"
            )
        body, link = _get(next_url, token)
        if not isinstance(body, list):
            # An error payload is an object, not a list; extending with one
            # would iterate its keys and fail confusingly far downstream.
            raise RuntimeError(
                f"unexpected non-list response from {next_url} "
                f"(got {type(body).__name__}) — refusing to build a snapshot from it"
            )
        items.extend(body)
        match = _LINK_NEXT_RE.search(link)
        next_url = match.group(1) if match else None
    return items


def gather_snapshot(
    repo: str, token: str, now: Optional[datetime] = None
) -> dict[str, Any]:
    """The snapshot ``detectors.evaluate`` consumes, from the live repo.

    ``generatedAt`` is stamped here — the I/O layer — so the pure layers
    stay deterministic: the same snapshot file always renders the same
    report bytes.
    """
    raw_issues = _paged(
        f"{API_ROOT}/repos/{repo}/issues?state=open&per_page=100", token
    )
    issues = []
    for item in raw_issues:
        if "pull_request" in item:
            continue  # the issues endpoint interleaves PRs; drop them
        issue: dict[str, Any] = {
            "number": item["number"],
            "title": item["title"],
            "labels": [lb["name"] for lb in item.get("labels", [])],
            "createdAt": item["created_at"],
            "updatedAt": item["updated_at"],
        }
        sub = item.get("sub_issues_summary")
        if sub is not None:
            issue["subIssues"] = {
                "total": sub.get("total", 0),
                "completed": sub.get("completed", 0),
            }
        issues.append(issue)

    open_prs = [
        {"number": pr["number"], "body": pr.get("body") or ""}
        for pr in _paged(f"{API_ROOT}/repos/{repo}/pulls?state=open&per_page=100", token)
    ]

    stamp = (now or datetime.now(timezone.utc)).isoformat()
    return {"generatedAt": stamp, "issues": issues, "openPRs": open_prs}
