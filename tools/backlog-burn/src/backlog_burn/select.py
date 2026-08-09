"""Selection policy for the scheduled backlog burn.

Pure functions: given a *snapshot* of the repository's open issues — plus the
open PRs and remote branches that reveal which issues are already claimed —
decide the single issue an unattended ``/ship-issue`` run should take next,
or none.

Every exclusion here mirrors the ``/ship-issue`` skill's own §0 lock check:

* an active ``🚢 SHIP-LOCK`` marker comment (a ``WITHDRAWN`` one releases it),
* an open PR that *closes* the issue — detected from its body's closing
  keywords or a ``claude/issue-<N>-*`` head branch. A keyword-free PR linked
  only through GitHub's Development sidebar is *not* detected here (that needs
  timeline/GraphQL metadata this stdlib snapshot deliberately does not fetch);
  the skill's own linked-PR-metadata check is the backstop, so the worst case
  is one wasted selection the skill then declines, never a wrong ship,
* an existing remote ``claude/issue-<N>-*`` branch.

One further exclusion does not come from the lock check: an issue carrying the
``needs-decision`` label is skipped because an agentic run parked it for a human
yes/no (the HITL decision gate, issue #161) and must not be re-selected until
the decision is recorded and the label is cleared. Unlike a SHIP-LOCK this block
is *durable* — it never goes stale, because a pending decision does not expire.

The skill re-verifies all of this before it touches a line of code, so this
module is a best-effort *pre-filter*. Its only jobs are to never hand the run
an issue that is plainly already taken, and — the hard cap — to never hand it
more than one. Keeping the policy pure (a function of the snapshot, with no
network) is what lets every guard below carry a negative-control test.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# The label a human must add for an issue to be eligible for unattended
# shipping. Nothing is eligible until someone opts it in, so the routine is
# safe on the day it lands: it selects nothing until the backlog is curated.
DEFAULT_REQUIRED_LABEL = "autonomy-ok"

SHIP_LOCK_MARKER = "🚢 SHIP-LOCK"

# An issue an agentic run parked for a human yes/no (the HITL decision gate,
# issue #161) carries this label until the decision is recorded and it is
# cleared. It excludes the issue from selection the same way a claim does, but is
# *durable*: unlike a SHIP-LOCK it never goes stale, because a pending decision
# does not expire. A fixed marker, not configurable — the /decide resolution
# flips it to decision-approved / decision-rejected.
DECISION_PENDING_LABEL = "needs-decision"

# A SHIP-LOCK this old, with no corroborating branch or closing PR, is a
# *stale* claim — a run that died between posting its lock and pushing a
# branch. The /ship-issue skill §0.3 takes such a claim over rather than
# letting it freeze the issue forever; this pre-filter must do the same, or a
# dead run's lock would permanently starve the issue from the burn (the skill
# only gets to run the takeover for an issue this selector actually hands it).
# "A few hours old" in the skill, made concrete.
STALE_LOCK_HOURS = 6

# GitHub honours these nine keywords, case-insensitively, each optionally
# followed by a colon, to auto-close an issue from a PR body. Grepping only
# for "Closes #N" misses "Resolved: #38" — so match the full set, exactly as
# the /ship-issue skill's §0 note spells out.
_CLOSING_KEYWORDS = (
    "close", "closes", "closed",
    "fix", "fixes", "fixed",
    "resolve", "resolves", "resolved",
)


def _first_line(text: str) -> str:
    """The first non-blank line of ``text``, stripped (``""`` if none)."""
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _parse_iso(ts: str) -> Optional[datetime]:
    """Parse a GitHub ISO-8601 UTC timestamp; ``None`` if unparseable.

    ``datetime.fromisoformat`` only learned to accept a trailing ``Z`` in
    3.11, and the tool must run on 3.10, so normalise it by hand.
    """
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ship_lock_state(
    comments: list[dict[str, Any]],
    now: Optional[datetime],
    stale_after_hours: float,
) -> str:
    """Classify the *latest* SHIP-LOCK comment: ``none`` / ``active`` / ``stale``.

    A claim is a state, not a flag (the skill's §0.3 rule): read the newest
    ``🚢 SHIP-LOCK`` comment and act on that one. ``🚢 SHIP-LOCK WITHDRAWN``
    releases the claim (``none``), which is why a withdrawal has to be able to
    *un*-exclude an issue here, not merely be ignored.

    An un-withdrawn claim older than ``stale_after_hours`` is ``stale`` — the
    caller only asks about the lock once it has already ruled out a
    corroborating branch or closing PR, so a stale verdict here means exactly
    the skill's takeover condition. With ``now`` unknown (``None``) staleness
    cannot be judged, so the safe reading is ``active``: never select over a
    claim we cannot date.
    """
    lock_comments = [
        c for c in (comments or [])
        if _first_line(c.get("body", "")).startswith(SHIP_LOCK_MARKER)
    ]
    if not lock_comments:
        return "none"
    # createdAt is ISO-8601 UTC ("2026-08-07T23:35:56Z"), which sorts
    # lexicographically in timestamp order — newest last.
    latest = max(lock_comments, key=lambda c: c.get("createdAt", ""))
    if "WITHDRAWN" in _first_line(latest.get("body", "")).upper():
        return "none"
    if now is None:
        return "active"
    created = _parse_iso(latest.get("createdAt", ""))
    if created is None:
        return "active"
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if now - created > timedelta(hours=stale_after_hours):
        return "stale"
    return "active"


def _closes_issue(pr_body: str, number: int) -> bool:
    """True if ``pr_body`` closes issue ``number`` via any GitHub keyword."""
    # re.escape so a malformed snapshot number (e.g. the string ".*") is
    # matched as a literal, never interpolated as a pattern — for a real
    # integer this is a no-op (digits escape to themselves).
    num = re.escape(str(number))
    for kw in _CLOSING_KEYWORDS:
        # keyword, optional ':', whitespace, '#<number>', not glued to more
        # digits (so "#9" does not match issue 95).
        pattern = rf"(?i)\b{kw}:?\s+#{num}\b"
        if re.search(pattern, pr_body or ""):
            return True
    return False


def _issue_branch_re(number: int) -> re.Pattern[str]:
    """Matcher for a ``claude/issue-<number>-*`` branch (boundary-safe).

    ``number`` is escaped for the same reason as in :func:`_closes_issue`: a
    malformed value must be a literal, not a pattern.
    """
    return re.compile(rf"^claude/issue-{re.escape(str(number))}-")


def _has_issue_branch(branches: list[str], number: int) -> bool:
    """True if any branch is this issue's ``claude/issue-<number>-*``."""
    rx = _issue_branch_re(number)
    return any(rx.match(b or "") for b in (branches or []))


def _open_pr_claims(open_prs: list[dict[str, Any]], number: int) -> bool:
    """True if an open PR closes this issue (by keyword or head branch)."""
    rx = _issue_branch_re(number)
    for pr in open_prs or []:
        if _closes_issue(pr.get("body", ""), number):
            return True
        if rx.match(pr.get("headRefName", "") or ""):
            return True
    return False


def exclusion_reason(
    issue: dict[str, Any],
    open_prs: list[dict[str, Any]],
    branches: list[str],
    required_label: str = DEFAULT_REQUIRED_LABEL,
    now: Optional[datetime] = None,
    stale_after_hours: float = STALE_LOCK_HOURS,
    decision_label: str = DECISION_PENDING_LABEL,
) -> Optional[str]:
    """Why this issue is *not* eligible, or ``None`` if it is.

    The branch and closing-PR guards are checked *before* the SHIP-LOCK guard
    on purpose: by the time we ask about the lock, a corroborating branch or
    PR has already been ruled out, so a ``stale`` lock verdict means precisely
    the skill's takeover condition — an old claim with nothing backing it —
    and the issue is left eligible rather than frozen forever.

    The ``needs-decision`` guard sits just after the opt-in label check, ahead
    of every claim guard: a parked decision is a *durable* block that must hold
    even after a pausing run's SHIP-LOCK goes stale, so it cannot be gated
    behind the staleness logic.
    """
    number = issue["number"]
    labels = issue.get("labels", []) or []
    if required_label not in labels:
        return f"not labelled {required_label!r}"
    if decision_label in labels:
        return f"awaiting a human decision ({decision_label})"
    if _has_issue_branch(branches, number):
        return f"a claude/issue-{number}-* branch already exists"
    if _open_pr_claims(open_prs, number):
        return f"an open PR already closes #{number}"
    if _ship_lock_state(issue.get("shipLockComments", []), now, stale_after_hours) == "active":
        return "an active 🚢 SHIP-LOCK claim"
    return None


def select_issue(
    snapshot: dict[str, Any],
    required_label: str = DEFAULT_REQUIRED_LABEL,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Pick at most one issue from a snapshot; return a structured record.

    The record is the outcome log the workflow surfaces (AC4): what was
    selected, how many were considered, and — for every issue that was not —
    the reason it was skipped, so a maintainer reading the run can see the
    routine's reasoning without re-deriving it.

    ``now`` (a timezone-aware datetime) dates SHIP-LOCK claims for staleness;
    the CLI passes the current UTC time. With ``now`` omitted, a claim is
    never treated as stale — the conservative reading.
    """
    issues = snapshot.get("issues", []) or []
    open_prs = snapshot.get("openPRs", []) or []
    branches = snapshot.get("branches", []) or []

    eligible: list[dict[str, Any]] = []
    excluded: dict[str, str] = {}
    for issue in issues:
        reason = exclusion_reason(
            issue, open_prs, branches, required_label, now=now
        )
        if reason is None:
            eligible.append(issue)
        else:
            excluded[str(issue["number"])] = reason

    # Oldest-first (the /ship-issue policy's default ordering), tie-broken by
    # issue number so the choice is deterministic across runs and machines.
    eligible.sort(key=lambda i: (i.get("createdAt", ""), i["number"]))

    # The hard cap: one issue per firing, so a bad night costs one PR, not
    # five. Everything past the first eligible issue is deferred to the next
    # firing, and reported as such.
    selected = eligible[0] if eligible else None
    deferred = [i["number"] for i in eligible[1:]]

    return {
        "selected": (selected["number"] if selected else None),
        "selected_title": (selected.get("title") if selected else None),
        "considered": len(issues),
        "eligible_count": len(eligible),
        "deferred": deferred,
        "excluded": excluded,
        "required_label": required_label,
    }


def render_summary(record: dict[str, Any]) -> str:
    """A short markdown block for the job summary / logs (AC4)."""
    lines = []
    if record["selected"] is not None:
        lines.append(
            f"**Selected #{record['selected']}** — "
            f"{record.get('selected_title') or ''}".rstrip(" —")
        )
    else:
        lines.append(
            f"**No issue selected** — nothing labelled "
            f"`{record['required_label']}` is currently unclaimed."
        )
    lines.append("")
    lines.append(
        f"- considered: {record['considered']} open issue(s); "
        f"eligible: {record['eligible_count']}"
    )
    if record["deferred"]:
        deferred = ", ".join(f"#{n}" for n in record["deferred"])
        lines.append(f"- deferred to a later firing (cap 1): {deferred}")
    if record["excluded"]:
        lines.append("- skipped:")
        for num, reason in sorted(record["excluded"].items(), key=lambda kv: int(kv[0])):
            lines.append(f"  - #{num}: {reason}")
    return "\n".join(lines)
