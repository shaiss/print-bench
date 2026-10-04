"""Live GitHub read: assemble the snapshot :mod:`backlog_burn.select` consumes.

Deliberately stdlib-only (``urllib``), like ``tools/lineage``: the routine
runs in CI where the only guaranteed interpreter is the system Python, and a
selection tool that pulled in ``requests`` would need a pip step in front of
the step that decides what to ship. This module is thin I/O — it does no
policy — so the interesting logic all sits behind unit tests in ``select``.
Even *which* branches are worth a compare request is asked of ``select``
(:func:`backlog_burn.select.branches_needing_compare`), not decided here.
"""

from __future__ import annotations

import http.client
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Optional

from .select import DEFAULT_REQUIRED_LABEL, branches_needing_compare

_API = "https://api.github.com"

# What a single best-effort request may raise: HTTP errors and transport
# failures (``urllib.error.URLError`` is an ``OSError``; so are timeouts and
# connection resets), a malformed status line, or a body that is not JSON.
# Anything else — an ``AssertionError`` from a test double included — still
# propagates, so a programming error is never mistaken for "compare failed".
_REQUEST_ERRORS = (OSError, ValueError, http.client.HTTPException)


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


def _warn(message: str) -> None:
    """One diagnostic line on stderr (an Actions ``::warning::`` in CI)."""
    sys.stderr.write(f"::warning::backlog-burn: {message}\n")


def _ahead_by(repo: str, token: str, base: str, branch: str) -> Optional[int]:
    """How many commits ``branch`` holds that ``base`` does not, or ``None``.

    ``GET /repos/{repo}/compare/{base}...{branch}``'s ``ahead_by``. ``None``
    whenever the answer is not a clean integer — the request failed, the
    branch vanished between the listing and the compare, the payload has no
    ``ahead_by`` — and the policy reads ``None`` as "may carry work", so a
    failed compare can only keep a claim, never release one. Ref names are
    percent-encoded with ``/`` kept literal (a ``claude/issue-<N>-*`` name is
    path-shaped by design); anything else URL-special is escaped.
    """
    basehead = (
        f"{urllib.parse.quote(base, safe='/')}..."
        f"{urllib.parse.quote(branch, safe='/')}"
    )
    try:
        body, _ = _get(f"{_API}/repos/{repo}/compare/{basehead}", token)
    except _REQUEST_ERRORS as exc:
        _warn(f"compare {base}...{branch} failed ({exc}) — keeping the branch as a claim")
        return None
    ahead = body.get("ahead_by") if isinstance(body, dict) else None
    if type(ahead) is not int:
        _warn(f"compare {base}...{branch} returned no integer ahead_by — keeping the branch as a claim")
        return None
    return ahead


def _branch_ahead_by(
    repo: str, token: str, wanted: list[str]
) -> dict[str, int]:
    """``{branch: ahead_by}`` for each wanted branch whose compare succeeded.

    One ``GET /repos/{repo}`` for the default branch (only when there is
    something to compare), then one compare per branch. A branch whose
    compare failed is simply absent from the map — absence is the policy's
    "unknown", which claims. If the default branch itself cannot be read,
    nothing can be compared and the map is empty: every branch claims.
    """
    if not wanted:
        return {}
    try:
        meta, _ = _get(f"{_API}/repos/{repo}", token)
    except _REQUEST_ERRORS as exc:
        _warn(f"could not read the default branch ({exc}) — every claude/issue-* branch stays a claim")
        return {}
    base = meta.get("default_branch") if isinstance(meta, dict) else None
    if not isinstance(base, str) or not base:
        _warn("the repo payload named no default branch — every claude/issue-* branch stays a claim")
        return {}
    out: dict[str, int] = {}
    for branch in wanted:
        ahead = _ahead_by(repo, token, base, branch)
        if ahead is not None:
            out[branch] = ahead
    return out


def gather_snapshot(
    repo: str,
    token: str,
    required_label: str = DEFAULT_REQUIRED_LABEL,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Build the snapshot for ``repo`` (``owner/name``) via the REST API.

    An issue's comment thread is fetched only when the list payload reports it
    has any comments (``comments > 0``); the thread is kept whole (see
    :func:`_issue_comments`). So a commented-but-unlocked issue still costs
    one extra request — while a fresh, comment-free issue is read from the
    list call alone.

    ``branchAheadBy`` carries the compare result for exactly the branches
    :func:`backlog_burn.select.branches_needing_compare` names — those of
    issues that are eligible but for their branch, under ``required_label``
    and ``now`` (pass the same values the selection will use). Which branches
    are worth a request is policy, so this layer asks rather than decides.
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

    snapshot: dict[str, Any] = {
        "issues": issues, "openPRs": open_prs, "branches": branches,
    }
    wanted = branches_needing_compare(snapshot, required_label, now)
    snapshot["branchAheadBy"] = _branch_ahead_by(repo, token, wanted)
    return snapshot
