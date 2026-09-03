"""Thin live read of the routines' run health — Reeve's second, GET-only seam.

Reeve's primary pulse stays committed files (``signals.py``); this module adds
the run-health reads behind the ``routine-dead`` and ``lock-leak`` detectors
(issue #313): the scheduled routines' completed workflow runs, the open issues
carrying an active 🚢 SHIP-LOCK claim, and the open PRs/branches that would
corroborate one. It also serves the greenlight loop's selection (issue #443):
``gather_greenlight_queue`` lists the open ``needs-decision`` issues and reads
each thread to see which already carry a greenlight marker — the trusted
workflow's Select step consumes it, so the agent is handed only issues that
are genuinely parkable-for-a-verdict. Everything here is a **GET** — no HTTP
write verb appears in this module or anywhere else in the reeve package
outside the one confined seam (``tests/test_detectors.py`` scans for them;
``pushthrough.py`` is the deliberate, test-confined exception), and the
workflow's other writes (the sticky-issue upsert, the wrapper-mediated
greenlight comments) stay outside this package entirely.

``_get`` is the single network seam, so the tests monkeypatch it and no
request ever leaves the process — the same discipline
``tools/backlog-groomer/src/backlog_groomer/github.py`` documents.
Pagination follows the ``Link: rel="next"`` header with a hard page cap that
raises rather than silently truncating: a partial snapshot would make the
report lie about coverage.

The greenlight loop's approval poll (issue #444) reads through this same
seam and stays GET-only: the parked threads **with their comment ids**
(``gather_greenlight_poll``), one comment's reactions (``list_reactions``),
and each reactor's real repository permission (``permission_of``). The
writes that follow an approved reaction — the label flip, the ledger
commit, the resolution reply — live in ``pushthrough.py``, never here.
"""

from __future__ import annotations

import json
import re
import urllib.parse
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

# The claim marker /ship-issue posts and tools/backlog-burn's selector honours.
# Mirrored from tools/backlog-burn/src/backlog_burn/select.py, not imported —
# the two tools must stay independently installable (the groomer's precedent).
SHIP_LOCK_MARKER = "🚢 SHIP-LOCK"

# The label an adoption-study submission carries. Collected from the same
# open-issues listing the lock scan reads (no extra request), so Reeve can
# surface studies awaiting a disposition — or flagged worth-raising — to the
# platform lead. The disposition itself is read from the issue's own labels.
ADOPTION_STUDY_LABEL = "adoption-study"

# The label that parks an issue at the HITL decision gate (docs/decision-gate
# .md, issue #161) — the queue the greenlight loop drafts advisory verdicts on.
NEEDS_DECISION_LABEL = "needs-decision"

# The marker comment prefix the greenlight wrapper writes (mirrored from
# .claude/skills/reeve-greenlight/greenlight-helper.sh, not imported — the
# tool must stay installable without the wrapper). Matched as a prefix so any
# marker version and any verdict (yes/no/route) counts as "already
# greenlighted", exactly the wrapper's own live idempotency check.
GREENLIGHT_MARKER = "<!-- reeve-greenlight v"

# The marker `.github/actions/provider-triage` writes into the body of the
# needs-decision issue it files when a chain is exhausted (one per registry
# chain, so every converted walk can raise one — issue #544). That issue is an
# account/key ask with a fixed remedy — fund the account, raise the cap,
# rotate the key — not a decision a charter verdict can rule on, so the
# greenlight Select skips it rather than hand the drafter a yes/no it cannot
# give. Mirrored, not imported (the action is JavaScript); matched anywhere
# in the body, where the action writes it as the first line.
PROVIDER_ESCALATION_MARKER = "<!-- provider-escalation:"

# The scheduled routines whose death Reeve watches (the #312 incident class:
# a run killed by its own timeout leaves conclusion "cancelled"/"failure" and
# a ghost lock behind). growth-twitter is here because docs/growth.md names
# this detector as the "routine silently stops" handler for the growth desk.
ROUTINE_WORKFLOWS = ("design-run.yml", "backlog-burn.yml", "chunker.yml", "labeler.yml",
                     "growth-twitter.yml")

# Completed runs fetched per workflow — one page, newest-first as the API
# returns them. config.py caps `routine_dead_runs` at this value, since a
# window wider than the fetch could never fill.
_RUNS_FETCHED = 10


def _first_line(text: str) -> str:
    """The first non-blank line of ``text``, stripped (``""`` if none)."""
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _get(url: str, token: str) -> tuple[Any, str]:
    """One GET; returns ``(parsed JSON body, Link header or "")``."""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "print-bench-reeve",
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


def gather_run_health(
    repo: str, token: str, now: Optional[datetime] = None
) -> dict[str, Any]:
    """The ``runHealth`` block ``detectors.evaluate`` consumes, from the live repo.

    ``gatheredAt`` is stamped here — the I/O layer — so the pure layers stay
    deterministic: the same snapshot file always renders the same report bytes.
    A missing workflow file 404s and the uncaught HTTPError fails the run loud:
    a routine renamed away must be a red run, not a silently-unwatched routine.
    """
    workflows: list[dict[str, Any]] = []
    for wf in ROUTINE_WORKFLOWS:
        # The runs endpoint returns an OBJECT keyed `workflow_runs`, not a
        # list — one plain _get and unwrap, never _paged (its non-list guard
        # would raise). One page of the newest completed runs is the window.
        body, _ = _get(
            f"{API_ROOT}/repos/{repo}/actions/workflows/{wf}/runs"
            f"?status=completed&per_page={_RUNS_FETCHED}&exclude_pull_requests=true",
            token,
        )
        runs = body.get("workflow_runs") if isinstance(body, dict) else None
        if not isinstance(runs, list):
            raise RuntimeError(
                f"unexpected runs payload for {wf} (no workflow_runs list) — "
                "refusing to build a snapshot from it"
            )
        workflows.append(
            {
                "file": wf,
                "runs": [
                    {
                        "conclusion": r.get("conclusion"),
                        "createdAt": r.get("created_at"),
                        "url": r.get("html_url"),
                    }
                    for r in runs
                ],
            }
        )

    issues: list[dict[str, Any]] = []
    adoption_studies: list[dict[str, Any]] = []
    for item in _paged(f"{API_ROOT}/repos/{repo}/issues?state=open&per_page=100", token):
        if "pull_request" in item:
            continue  # the issues endpoint interleaves PRs; drop them
        label_names = [lbl.get("name", "") for lbl in item.get("labels", [])]
        if ADOPTION_STUDY_LABEL in label_names:
            # Collected before the comments skip below: a study is flagged by its
            # labels alone, so it must be gathered even with zero comments (the
            # skip only guards the per-issue lock-comments GET).
            adoption_studies.append(
                {
                    "number": item["number"],
                    "title": item["title"],
                    "labels": label_names,
                    "createdAt": item.get("created_at", ""),
                    "updatedAt": item.get("updated_at", ""),
                    "url": item.get("html_url", ""),
                }
            )
        if not item.get("comments"):
            continue  # no comments, no lock — skip the per-issue comments GET
        comments = _paged(
            f"{API_ROOT}/repos/{repo}/issues/{item['number']}/comments?per_page=100",
            token,
        )
        lock_comments = [
            c for c in comments
            if _first_line(c.get("body", "")).startswith(SHIP_LOCK_MARKER)
        ]
        if not lock_comments:
            continue
        # A claim is a state, not a flag (the selector's §0.3 reading): only
        # the newest lock comment counts, and a WITHDRAWN one releases it.
        # created_at is ISO-8601 UTC, which sorts lexicographically.
        latest = max(lock_comments, key=lambda c: c.get("created_at", ""))
        if "WITHDRAWN" in _first_line(latest.get("body", "")).upper():
            continue
        issues.append(
            {
                "number": item["number"],
                "title": item["title"],
                "lockCreatedAt": latest.get("created_at", ""),
            }
        )

    open_prs = [
        {
            "number": pr["number"],
            "headRefName": (pr.get("head") or {}).get("ref", ""),
            "body": pr.get("body") or "",
        }
        for pr in _paged(f"{API_ROOT}/repos/{repo}/pulls?state=open&per_page=100", token)
    ]

    branches = [
        b["name"]
        for b in _paged(f"{API_ROOT}/repos/{repo}/branches?per_page=100", token)
    ]

    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "gatheredAt": stamp,
        "workflows": workflows,
        "issues": issues,
        "adoptionStudies": adoption_studies,
        "openPRs": open_prs,
        "branches": branches,
    }


def carries_greenlight(comments: list[Any]) -> bool:
    """Whether any comment in ``comments`` opens with a greenlight marker.

    Pure, so the selection rule is testable without the seam: the wrapper
    writes the marker as the comment's first line, and its live idempotency
    check greps that same line — this is the read-side mirror, prefix-matched
    so any marker version or verdict (yes/no/route) counts.
    """
    return any(
        _first_line(c.get("body", "")).startswith(GREENLIGHT_MARKER)
        for c in comments
    )


def is_provider_escalation(body: str | None) -> bool:
    """Whether an issue body carries provider-triage's escalation marker."""
    return PROVIDER_ESCALATION_MARKER in (body or "")


def gather_greenlight_queue(repo: str, token: str) -> dict[str, Any]:
    """The greenlight loop's work-list, from the live repo (issue #443).

    Every OPEN issue parked at the decision gate (``needs-decision``), plus
    which of them already carry a greenlight marker comment — the trusted
    workflow's Select step reads this and hands the agent only the rest, so
    the drafter never even sees an issue it cannot post on (the wrapper
    re-checks live at write time; this is the selection, not the enforcement).
    A parked issue that is a provider-triage escalation (its body carries
    ``PROVIDER_ESCALATION_MARKER``) stays in ``parked`` — it IS at the gate —
    but never enters ``queue``, and its thread is not even read.
    Still GET-only: two listings per issue and nothing else.
    """
    parked: list[dict[str, Any]] = []
    for item in _paged(
        f"{API_ROOT}/repos/{repo}/issues"
        f"?state=open&labels={NEEDS_DECISION_LABEL}&per_page=100",
        token,
    ):
        if "pull_request" in item:
            continue  # the issues endpoint interleaves PRs; drop them
        parked.append(
            {
                "number": item["number"],
                "title": item["title"],
                "url": item.get("html_url", ""),
                "providerEscalation": is_provider_escalation(item.get("body", "")),
            }
        )

    queue: list[dict[str, Any]] = []
    for issue in parked:
        if issue["providerEscalation"]:
            continue  # an account/key ask with a fixed remedy, not a charter call
        comments = _paged(
            f"{API_ROOT}/repos/{repo}/issues/{issue['number']}/comments?per_page=100",
            token,
        )
        if not carries_greenlight(comments):
            queue.append(issue)

    # Oldest first (the sibling routines' bias — a decision parked longest
    # gets its verdict first), by number as the wrapper's list-parked sorts.
    queue.sort(key=lambda i: i["number"])
    return {"parked": parked, "queue": queue}


def permission_of(repo: str, token: str, username: str) -> str:
    """One user's real repository permission, e.g. ``"write"``/``"read"``.

    ``GET /repos/{repo}/collaborators/{username}/permission`` — the same
    authorization check ``decide.yml`` makes before honouring a ``/decide``
    (``getCollaboratorPermissionLevel`` in the JS client), because a
    reaction may resolve a gate only when its author could have typed the
    command. Never ``author_association``: that field describes prior
    participation (``CONTRIBUTOR`` for one merged PR, ``NONE`` for a
    first-timer), not current access, so it both over- and under-counts
    exactly the people this check exists to bound. The poll counts a
    reaction only for ``admin``/``maintain``/``write`` — the mapping lives
    beside the aggregation in ``greenlight.AUTHORIZED_PERMISSIONS``.
    """
    body, _ = _get(f"{API_ROOT}/repos/{repo}/collaborators/{username}/permission", token)
    if not isinstance(body, dict) or "permission" not in body:
        raise RuntimeError(
            f"unexpected permission payload for {username} on {repo} — "
            "refusing to authorize a reaction from it"
        )
    return body["permission"]


def list_reactions(repo: str, token: str, comment_id: int) -> list[dict[str, Any]]:
    """One issue comment's reactions as ``[{"user": {...}, "content": ...}]``.

    GitHub fires no webhook for reactions, which is why the *next* run
    polls: this is that read. Content values are ``+1`` (👍), ``-1`` (👎)
    and the decorative set — the aggregation in ``greenlight.poll_outcome``
    keeps only the first two.
    """
    return [
        {
            "user": r.get("user") or {},
            "content": r.get("content", ""),
        }
        for r in _paged(
            f"{API_ROOT}/repos/{repo}/issues/comments/{comment_id}/reactions?per_page=100",
            token,
        )
    ]


def gather_greenlight_poll(repo: str, token: str) -> list[dict[str, Any]]:
    """Every open parked decision's thread, ids intact (issue #444).

    The poll's own work-list: each open ``needs-decision`` issue with its
    body and its comments **including comment ids and authors** —
    ``gather_greenlight_queue`` drops both (the drafter's selection needs
    neither), while the poll must address a specific comment to read its
    reactions and must authorize ``/decide`` authors by login. Oldest first,
    the sibling bias. Still two GET-only listings per issue.
    """
    parked: list[dict[str, Any]] = []
    for item in _paged(
        f"{API_ROOT}/repos/{repo}/issues"
        f"?state=open&labels={NEEDS_DECISION_LABEL}&per_page=100",
        token,
    ):
        if "pull_request" in item:
            continue  # the issues endpoint interleaves PRs; drop them
        parked.append(
            {
                "number": item["number"],
                "title": item["title"],
                "url": item.get("html_url", ""),
                "body": item.get("body") or "",
            }
        )

    threads: list[dict[str, Any]] = []
    for issue in parked:
        comments = [
            {
                "id": c.get("id"),
                "user": c.get("user") or {},
                "created_at": c.get("created_at", ""),
                "body": c.get("body", ""),
            }
            for c in _paged(
                f"{API_ROOT}/repos/{repo}/issues/{issue['number']}/comments?per_page=100",
                token,
            )
        ]
        threads.append({**issue, "comments": comments})
    threads.sort(key=lambda t: t["number"])
    return threads


# The greenlight marker line's shape (the wrapper's own first line; mirrored,
# not imported). Captures the version, the issue the wrapper bound it to, and
# the verdict — the fields the observer reads back out of a thread. The
# resolution-execution comments (#201/#202's ``resolution=approved`` lines)
# use a different marker shape the ``verdict=`` capture rejects.
_GREENLIGHT_MARKER_RE = re.compile(
    r"^<!-- reeve-greenlight v(\d+) issue=(\d+) verdict=(\w+) -->$"
)

# The author associations that imply write-ish access — a filter for picking
# "owner replies" out of a thread AS CONTEXT (advisory evidence), never an
# authorization check. Whose reaction actually resolves a gate is #444's
# permission-level poll; this is the load half reading what the owner said.
_OWNER_ASSOCIATIONS = ("OWNER", "MEMBER", "COLLABORATOR")

# The search probe's phrase: the marker text as a quoted phrase. The search
# index also matches bodies that merely QUOTE the marker (issue #296's spec
# body does), so every candidate is verified against a real marker first line
# before it counts.
_SEARCH_PHRASE = '"reeve-greenlight v1"'


def _greenlight_of(comments: list[Any], number: int) -> Optional[dict[str, Any]]:
    """The thread's greenlight comment, or None — verified, not assumed.

    The FIRST comment whose first line is a well-formed marker naming THIS
    issue: the wrapper writes exactly one marker per greenlight, and a marker
    naming another issue (a quoted or copied comment) does not count.
    """
    for comment in comments:
        match = _GREENLIGHT_MARKER_RE.match(_first_line(comment.get("body", "")))
        if match and int(match.group(2)) == number:
            body = comment.get("body", "")
            reasoning = "\n".join(body.splitlines()[1:])
            return {
                "verdict": match.group(3),
                "reasoning": reasoning,
                "posted_at": comment.get("created_at", ""),
            }
    return None


def _owner_replies_after(comments: list[Any], posted_at: str) -> list[dict[str, Any]]:
    """Write-access replies posted after the greenlight, in thread order.

    Marker-led comments are the loop's own (the greenlight, the resolution
    execution) — never counted as owner replies. Bounded at three per thread:
    this feeds a digest, not an archive.
    """
    replies: list[dict[str, Any]] = []
    for comment in comments:
        if comment.get("created_at", "") <= posted_at:
            continue
        if _GREENLIGHT_MARKER_RE.match(_first_line(comment.get("body", ""))):
            continue
        if comment.get("author_association") not in _OWNER_ASSOCIATIONS:
            continue
        replies.append(
            {
                "author": (comment.get("author") or {}).get("login", ""),
                "text": (comment.get("body") or "")[:400],
            }
        )
        if len(replies) >= 3:
            break
    return replies


def _closing_pr(repo: str, token: str, number: int) -> Optional[int]:
    """The last PR that cross-referenced a closed thread, or None.

    A digest heuristic, honestly bounded: GitHub exposes no "closed by PR"
    field on the issue side, so the timeline's cross-references are the best
    available signal (the PR that closed it is virtually always the last one
    to reference it). One bounded GET, only for closed verified threads.
    """
    events, _ = _get(
        f"{API_ROOT}/repos/{repo}/issues/{number}/timeline?per_page=100", token
    )
    if not isinstance(events, list):
        raise RuntimeError(
            f"unexpected timeline payload for #{number} (not a list) — "
            "refusing to build a snapshot from it"
        )
    closing: Optional[int] = None
    for event in events:
        if event.get("event") != "cross-referenced":
            continue
        source = event.get("source") or {}
        issue = source.get("issue") or {}
        if "pull_request" in issue:
            closing = issue.get("number")
    return closing


def gather_greenlight_rounds(repo: str, token: str) -> dict[str, Any]:
    """Every greenlighted thread with its resolution state (issue #445).

    The observer's snapshot: discovery by a search probe over the marker phrase
    (it sees open AND closed threads — a resolved thread may be closed or
    label-flipped out of the parked listing, so the probe is the only listing
    that sees it whole), then per-candidate verification by reading the
    thread's comments for a real marker first line. Each verified thread
    carries what ``greenlights.derive_records`` reads: the greenlight's verdict
    and reasoning, the thread's state and labels, the inline owner replies
    after the greenlight, and (closed threads only) the closing PR.

    Search-index freshness is eventual: a thread greenlighted or resolved
    minutes ago may be missing until the index catches up — the next run
    records it. Still GET-only, like every seam here.
    """
    query = urllib.parse.quote(f"repo:{repo} {_SEARCH_PHRASE} type:issue", safe="")
    body, _ = _get(f"{API_ROOT}/search/issues?q={query}&per_page=100", token)
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        raise RuntimeError(
            "unexpected search payload (no items list) — refusing to build a "
            "snapshot from it"
        )
    if body.get("incomplete_results"):
        raise RuntimeError(
            "the greenlight search probe returned incomplete results — "
            "refusing to build a silently-truncated snapshot; retry next run"
        )
    if body.get("total_count", 0) > 100:
        raise RuntimeError(
            f"more than 100 issues match the greenlight probe ({body['total_count']}) — "
            "the one-page bound is wrong for this repo now; widen it deliberately"
        )

    threads: list[dict[str, Any]] = []
    for item in body["items"]:
        number = item.get("number")
        if not isinstance(number, int):
            continue
        comments = _paged(
            f"{API_ROOT}/repos/{repo}/issues/{number}/comments?per_page=100",
            token,
        )
        greenlight = _greenlight_of(comments, number)
        if greenlight is None:
            continue  # a body that quotes the marker, not a greenlight thread
        threads.append(
            {
                "number": number,
                "title": item.get("title", ""),
                "state": item.get("state", ""),
                "labels": [lbl.get("name", "") for lbl in item.get("labels", [])],
                "greenlight_verdict": greenlight["verdict"],
                "greenlight_reasoning": greenlight["reasoning"],
                "owner_replies": _owner_replies_after(comments, greenlight["posted_at"]),
                "closing_pr": (
                    _closing_pr(repo, token, number)
                    if item.get("state") == "closed" else None
                ),
            }
        )
    threads.sort(key=lambda t: t["number"])
    return {"threads": threads}
