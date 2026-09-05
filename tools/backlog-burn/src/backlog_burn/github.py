"""Live GitHub read: assemble the snapshot :mod:`backlog_burn.select` consumes.

Deliberately stdlib-only (``urllib``), like ``tools/lineage``: the routine
runs in CI where the only guaranteed interpreter is the system Python, and a
selection tool that pulled in ``requests`` would need a pip step in front of
the step that decides what to ship. This module is thin I/O — it does no
policy — so the interesting logic all sits behind unit tests in ``select``.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

_API = "https://api.github.com"


def _get(url: str, token: str) -> tuple[Any, dict[str, str]]:
    """GET ``url`` and return ``(parsed_json, lowercased_headers)``."""
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "print-bench-backlog-burn")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed host)
        body = json.loads(resp.read().decode("utf-8"))
        headers = {k.lower(): v for k, v in resp.headers.items()}
    return body, headers


# A page cap so a pathological Link loop cannot spin forever; 100 pages is
# 10k items, far beyond any real backlog. Hitting it is treated as an error,
# not silently truncated — a partial snapshot could miss the true oldest
# eligible issue and select the wrong one, with no signal (the repo's "no
# silent caps" rule).
_MAX_PAGES = 100


def _paginate(path: str, token: str) -> list[dict[str, Any]]:
    """Follow ``Link: rel="next"`` until the collection is exhausted.

    Raises ``RuntimeError`` rather than returning a truncated list if the page
    cap is exceeded, so the selector never operates on a partial snapshot.
    """
    url = f"{_API}{path}"
    if "?" not in url:
        url += "?per_page=100"
    elif "per_page=" not in url:
        url += "&per_page=100"
    out: list[dict[str, Any]] = []
    seen = 0
    while url:
        if seen >= _MAX_PAGES:
            raise RuntimeError(
                f"pagination exceeded {_MAX_PAGES} pages for {path!r} — refusing "
                "to select on a truncated snapshot"
            )
        body, headers = _get(url, token)
        if isinstance(body, list):
            out.extend(body)
        seen += 1
        url = _next_link(headers.get("link", ""))
    return out


def _next_link(link_header: str) -> str:
    """The ``rel="next"`` URL from a ``Link`` header, or ``""``."""
    for part in link_header.split(","):
        section = part.split(";")
        if len(section) < 2:
            continue
        url = section[0].strip().lstrip("<").rstrip(">")
        for param in section[1:]:
            if param.strip() == 'rel="next"':
                return url
    return ""


def _issue_comments(repo: str, number: int, token: str) -> list[dict[str, str]]:
    """The whole comment thread, normalised to what the policy reads.

    No marker filtering here on purpose: which first-line prefixes mean a
    lock, a decline or a machine-posted comment is *policy*, and policy
    belongs in :mod:`backlog_burn.select` behind its negative-control tests.
    This layer only normalises — body, createdAt, and the author's GitHub
    type (``User``/``Bot``), the leg of the run-vs-owner test that does not
    depend on markers. A deleted author types as ``""``, which the policy
    reads as a human: the conservative direction, since treating an owner
    reply as machine noise would wrongly hold the cooldown.
    """
    comments = _paginate(f"/repos/{repo}/issues/{number}/comments", token)
    return [
        {
            "body": c.get("body", ""),
            "createdAt": c.get("created_at", ""),
            "authorType": (c.get("user") or {}).get("type", ""),
        }
        for c in comments
    ]


def gather_snapshot(repo: str, token: str) -> dict[str, Any]:
    """Build the snapshot for ``repo`` (``owner/name``) via the REST API.

    An issue's comment thread is fetched only when the list payload reports it
    has any comments (``comments > 0``); the thread is kept whole (see
    :func:`_issue_comments`). So a commented-but-unlocked issue still costs
    one extra request — while a fresh, comment-free issue is read from the
    list call alone.
    """
    raw_issues = _paginate(f"/repos/{repo}/issues?state=open", token)
    issues: list[dict[str, Any]] = []
    for it in raw_issues:
        # The issues endpoint returns PRs too; a PR carries a "pull_request"
        # key. Drop them — the backlog is issues only.
        if "pull_request" in it:
            continue
        number = it["number"]
        # `comments` is a count on the list payload; fetch the thread only
        # when there is one, keeping it whole for the policy to read.
        thread: list[dict[str, str]] = []
        if it.get("comments", 0):
            thread = _issue_comments(repo, number, token)
        issues.append({
            "number": number,
            "title": it.get("title", ""),
            "createdAt": it.get("created_at", ""),
            "labels": [lbl.get("name", "") for lbl in it.get("labels", [])],
            "comments": thread,
        })

    raw_prs = _paginate(f"/repos/{repo}/pulls?state=open", token)
    open_prs = [
        {
            "number": pr["number"],
            "headRefName": (pr.get("head") or {}).get("ref", ""),
            "body": pr.get("body") or "",
        }
        for pr in raw_prs
    ]

    raw_branches = _paginate(f"/repos/{repo}/branches", token)
    branches = [b.get("name", "") for b in raw_branches]

    return {"issues": issues, "openPRs": open_prs, "branches": branches}
