"""The groomer's detectors — pure functions of one snapshot, no I/O.

Every detector is a recomputable fact about timestamps, labels, and links:
given the same snapshot and config it returns the same findings, which is
what makes the report a gate-grade artifact rather than an opinion.  None
of them touch the network — the snapshot comes in as data (see
``github.py`` for the single seam that gathers it live).

Findings are plain dicts with stable ordering (primary sort key per
detector, ties broken by issue number) so the rendered report is
byte-deterministic — the golden test in ``tests/test_report.py`` holds it
to that.

A detector whose input data is absent from the snapshot reports itself
"not evaluated" with the reason, never silently empty: an empty section
must mean "checked, clean", not "couldn't look".
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

# The labels this repo's autonomy loop uses as machine state.
ARMED_LABEL = "autonomy-ok"                # backlog-burn opt-in (issue #95)
DECISION_PENDING_LABEL = "needs-decision"  # HITL decision gate (issue #161)
DECISION_VERDICT_LABELS = ("decision-approved", "decision-rejected")
OVERSIZED_LABEL = "declined-too-big"       # chunker input (/chunk-issue)
_POINTS_RE = re.compile(r"^points-\d+$")   # roadmap-board estimate (issue #148)

# The nine closing keywords GitHub honours in PR bodies (close/closes/closed,
# fix/fixes/fixed, resolve/resolves/resolved), case-insensitive, optional
# colon.  The number is captured and compared as an int rather than matched
# with a boundary regex, so `fixes #24` can never half-match issue #244.
_CLOSING_RE = re.compile(
    r"(?i)(?<![a-z])(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?):?\s+#(\d+)"
)

# Tiny fixed stopword list for title-similarity tokenisation.  Deliberately
# frozen and boring: growing it changes every similarity score, so any edit
# shows up in the golden report test.
_STOPWORDS = frozenset(
    "a an and are as at by for from in is it its of on or that the this to via with".split()
)


def parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, accepting the trailing ``Z`` GitHub emits.

    ``datetime.fromisoformat`` only learned ``Z`` in Python 3.11 and this
    package supports 3.10 (the system-Python contract every tools/ package
    here keeps), so normalise by hand.
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _days_since(now: datetime, then: str) -> int:
    """Whole days between ``then`` (ISO string) and ``now``, floored."""
    return int((now - parse_ts(then)).total_seconds() // 86400)


def _labels(issue: dict[str, Any]) -> set[str]:
    return set(issue.get("labels", []))


def _open_issues(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """The snapshot's open issues, PR entries dropped defensively."""
    return [i for i in snapshot.get("issues", []) if not i.get("isPull")]


# ---------------------------------------------------------------------------
# The detectors. Each returns a list of finding dicts in stable order.
# ---------------------------------------------------------------------------

def stale(issues: list[dict], now: datetime, staleness_days: int) -> list[dict]:
    """Open issues with no update in strictly more than ``staleness_days``."""
    found = [
        {
            "number": i["number"],
            "title": i["title"],
            "days": _days_since(now, i["updatedAt"]),
            "updatedAt": i["updatedAt"],
        }
        for i in issues
        if _days_since(now, i["updatedAt"]) > staleness_days
    ]
    return sorted(found, key=lambda f: (f["updatedAt"], f["number"]))


def has_open_closing_pr(number: int, open_prs: list[dict]) -> bool:
    """True when any open PR's body carries a closing keyword for ``number``."""
    for pr in open_prs:
        for match in _CLOSING_RE.finditer(pr.get("body") or ""):
            if int(match.group(1)) == number:
                return True
    return False


def armed_stuck(
    issues: list[dict], open_prs: list[dict], now: datetime, armed_stuck_days: int
) -> list[dict]:
    """``autonomy-ok`` issues quiet past the threshold with no open closing PR.

    The burn should have shipped these; their sitting here means the burn is
    disarmed, failing, or stuck on them.  ``updatedAt`` is the label-age
    proxy (same as :func:`unchunked_oversized` — labeling bumps it, and
    label-event timestamps aren't in the snapshot), so a month-old issue
    armed an hour ago reads as fresh, not as a month of stuckness.  Like its
    sibling it errs quiet: any activity resets the clock, so a burn that
    posts a decline comment each firing keeps the issue out of the report
    until it stops commenting — an accepted limitation of a snapshot without
    label events, stated here rather than implied.
    """
    found = [
        {
            "number": i["number"],
            "title": i["title"],
            "days": _days_since(now, i["updatedAt"]),
            "updatedAt": i["updatedAt"],
        }
        for i in issues
        if ARMED_LABEL in _labels(i)
        and _days_since(now, i["updatedAt"]) > armed_stuck_days
        and not has_open_closing_pr(i["number"], open_prs)
    ]
    return sorted(found, key=lambda f: (f["updatedAt"], f["number"]))


def unsized_armed(issues: list[dict]) -> list[dict]:
    """``autonomy-ok`` issues with no ``points-<n>`` estimate label.

    The roadmap board (issue #148) mirrors that label to its Story-points
    field; a hand-armed issue that skipped the chunker's estimating lands
    on the board unsized.
    """
    found = [
        {"number": i["number"], "title": i["title"]}
        for i in issues
        if ARMED_LABEL in _labels(i)
        and not any(_POINTS_RE.match(lb) for lb in _labels(i))
    ]
    return sorted(found, key=lambda f: f["number"])


def decision_resolved_parked(issues: list[dict]) -> list[dict]:
    """Parked decisions whose verdict landed but nobody resumed.

    ``needs-decision`` is the durable pause; ``decision-approved`` /
    ``decision-rejected`` is the human's answer (issue #161).  Both present
    means the gate did its job and the loop dropped the ball.
    """
    found = []
    for i in issues:
        labels = _labels(i)
        if DECISION_PENDING_LABEL not in labels:
            continue
        verdicts = sorted(labels.intersection(DECISION_VERDICT_LABELS))
        if verdicts:
            found.append(
                {"number": i["number"], "title": i["title"], "verdict": verdicts[-1]}
            )
    return sorted(found, key=lambda f: f["number"])


def unchunked_oversized(
    issues: list[dict], now: datetime, oversized_stuck_days: int
) -> list[dict]:
    """``declined-too-big`` issues quiet for longer than the threshold.

    The chunker removes that label on every path that handles an issue (its
    idempotency latch), so label-still-present plus no activity means the
    chunker is disarmed or failing.  ``updatedAt`` is the proxy for "since
    the label landed" — label-event timestamps aren't in the snapshot — and
    it errs quiet: an actively-discussed oversized issue stays out of the
    report until the thread goes cold.
    """
    found = [
        {
            "number": i["number"],
            "title": i["title"],
            "days": _days_since(now, i["updatedAt"]),
            "updatedAt": i["updatedAt"],
        }
        for i in issues
        if OVERSIZED_LABEL in _labels(i)
        and _days_since(now, i["updatedAt"]) > oversized_stuck_days
    ]
    return sorted(found, key=lambda f: (f["updatedAt"], f["number"]))


def _title_tokens(title: str) -> frozenset[str]:
    """Normalised token set for similarity: lowercase, alnum, stopword-free."""
    words = re.sub(r"[^a-z0-9]+", " ", title.lower()).split()
    return frozenset(w for w in words if w not in _STOPWORDS)


def dup_candidates(
    issues: list[dict], threshold: float, cap: int
) -> tuple[list[dict], int]:
    """Open-issue pairs whose title-token Jaccard similarity ≥ ``threshold``.

    Returns ``(top pairs, total matching pairs)`` — the total is what lets
    the report disclose the cap (showing N of M) instead of silently
    truncating.  Issues whose titles normalise to zero tokens are skipped
    (similarity is undefined on an empty set).
    """
    tokened = [
        (i["number"], i["title"], _title_tokens(i["title"])) for i in issues
    ]
    tokened = [(n, t, toks) for n, t, toks in tokened if toks]
    pairs = []
    for a in range(len(tokened)):
        for b in range(a + 1, len(tokened)):
            n1, t1, tok1 = tokened[a]
            n2, t2, tok2 = tokened[b]
            score = len(tok1 & tok2) / len(tok1 | tok2)
            if score >= threshold:
                lo, hi = sorted((n1, n2))
                pairs.append(
                    {
                        "a": lo,
                        "b": hi,
                        "title_a": t1 if lo == n1 else t2,
                        "title_b": t2 if hi == n2 else t1,
                        "score": score,
                    }
                )
    pairs.sort(key=lambda p: (-p["score"], p["a"], p["b"]))
    return pairs[:cap], len(pairs)


def epic_complete(issues: list[dict]) -> list[dict]:
    """Open issues whose native sub-issues are all closed — close candidates.

    Closing stays the human's call (a tracked epic may deliberately outlive
    its children); the groomer only surfaces that the checklist is done.
    """
    found = []
    for i in issues:
        sub = i.get("subIssues")
        if sub and sub.get("total", 0) > 0 and sub.get("completed") == sub["total"]:
            found.append(
                {"number": i["number"], "title": i["title"], "total": sub["total"]}
            )
    return sorted(found, key=lambda f: f["number"])


# ---------------------------------------------------------------------------
# The one entry point report.py consumes.
# ---------------------------------------------------------------------------

def evaluate(snapshot: dict[str, Any], cfg: Any, now: Optional[datetime] = None) -> dict:
    """Run every detector over ``snapshot`` under config ``cfg``.

    ``now`` defaults to the snapshot's own ``generatedAt`` so the result —
    and therefore the report — is a pure function of the snapshot: re-running
    over the same file reproduces the same bytes (the determinism AC).
    """
    issues = _open_issues(snapshot)
    if now is None:
        now = parse_ts(snapshot["generatedAt"])

    findings: dict[str, list[dict]] = {}
    not_evaluated: dict[str, str] = {}

    findings["stale"] = stale(issues, now, cfg.staleness_days)

    open_prs = snapshot.get("openPRs")
    if open_prs is None:
        # Absent (key missing) is "couldn't look"; an empty list is a real
        # answer (no open PRs) and evaluates normally.
        findings["armed-stuck"] = []
        not_evaluated["armed-stuck"] = "snapshot carries no open-PR data (openPRs missing)"
    else:
        findings["armed-stuck"] = armed_stuck(issues, open_prs, now, cfg.armed_stuck_days)

    findings["unsized-armed"] = unsized_armed(issues)
    findings["decision-resolved-parked"] = decision_resolved_parked(issues)
    findings["unchunked-oversized"] = unchunked_oversized(
        issues, now, cfg.oversized_stuck_days
    )

    dups, dup_total = dup_candidates(issues, cfg.dup_threshold, cfg.max_dup_pairs)
    findings["dup-candidates"] = dups

    if issues and not any("subIssues" in i for i in issues):
        findings["epic-complete"] = []
        not_evaluated["epic-complete"] = "snapshot carries no sub-issue data (subIssues missing)"
    else:
        findings["epic-complete"] = epic_complete(issues)

    return {
        "findings": findings,
        "not_evaluated": not_evaluated,
        "dup_total": dup_total,
        "issue_count": len(issues),
    }
