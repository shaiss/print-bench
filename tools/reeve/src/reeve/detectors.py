"""The bench-health detectors — pure functions of one snapshot.

Every detector is a recomputable fact about the committed telemetry log, the
live preview sizes and the routine confs: given the same snapshot and config
it returns the same findings, in a deterministic order, so the rendered
report is byte-deterministic. No detector touches the network, the clock, or
global state.

The snapshot (built by ``signals.gather_snapshot``) is a plain dict::

    {
      "generatedAt": "2026-08-16T06:00:00Z",
      "records":   [ <gate-run record>, ... ],   # oldest-first
      "previews":  [ {"file","bytes","budget","headroom_pct"}, ... ],
      "reportPlaceholder": true/false,            # telemetry/REPORT.md still empty?
      "runHealth": { ... },                       # optional: github.gather_run_health
    }

The optional ``runHealth`` block (``github.gather_run_health``, issue #313)
carries ``gatheredAt``, per-routine ``workflows`` run conclusions, the open
``issues`` holding an active 🚢 SHIP-LOCK claim, and the ``openPRs`` /
``branches`` that would corroborate one. It is absent on an offline run
(no ``--repo``), and the two run-health detectors then read "not evaluated".

Gate-run records carry the telemetry schema (issue #93): ``meta.designs``
(``"ALL"`` for a full-catalog run, else a scoped list), ``gate.parts`` (per
printcheck'd STL: ``stl``, ``score`` int|null, ``criticals``, ``slice_failed``,
…), ``gate.design_seconds`` (per-design wall time), ``gate.archived_skips``,
``gate.derivatives`` and ``gate.pre_fails``.

The "not evaluated" honesty rule (from the groomer): a detector whose input
is *absent* is reported "not evaluated" with a reason by :func:`evaluate`,
never silently empty — an empty section must mean "checked, clean". Wall-time
and archived comparisons need two full-catalog runs; the committed log starts
empty, so those read "not evaluated" until history accrues.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

_WS_RE = re.compile(r"\s+")

# GitHub honours these nine keywords, case-insensitively, each optionally
# followed by a colon, to auto-close an issue from a PR body. Mirrored from
# tools/backlog-burn/src/backlog_burn/select.py, not imported — the tools stay
# independently installable, and select.py's own tests pin the semantics.
_CLOSING_KEYWORDS = (
    "close", "closes", "closed",
    "fix", "fixes", "fixed",
    "resolve", "resolves", "resolved",
)


def _flat(text: str) -> str:
    """Collapse whitespace so a telemetry string renders on one line."""
    return _WS_RE.sub(" ", str(text)).strip()


def _parse_iso(ts: str) -> Optional[datetime]:
    """Parse a GitHub ISO-8601 UTC timestamp; ``None`` if unparseable.

    ``datetime.fromisoformat`` only learned to accept a trailing ``Z`` in
    3.11, and the tool must run on 3.10, so normalise it by hand.
    """
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _issue_branch_re(number: int) -> re.Pattern[str]:
    """Matcher for a ``claude/issue-<number>-*`` branch (boundary-safe).

    ``number`` is escaped so a malformed snapshot value (e.g. the string
    ``".*"``) matches as a literal, never a pattern — select.py's own guard.
    """
    return re.compile(rf"^claude/issue-{re.escape(str(number))}-")


def _closes_issue(pr_body: str, number: int) -> bool:
    """True if ``pr_body`` closes issue ``number`` via any GitHub keyword."""
    num = re.escape(str(number))
    for kw in _CLOSING_KEYWORDS:
        # keyword, optional ':', whitespace, '#<number>', not glued to more
        # digits (so "#9" does not match issue 95).
        pattern = rf"(?i)\b{kw}:?\s+#{num}\b"
        if re.search(pattern, pr_body or ""):
            return True
    return False


def _all_records(records: list[dict]) -> list[dict]:
    """Full-catalog (designs=ALL) runs — the only ones comparable run-over-run."""
    return [r for r in records if r.get("meta", {}).get("designs") == "ALL"]


def _parts_by_stl(record: dict) -> dict[str, dict]:
    return {p["stl"]: p for p in record.get("gate", {}).get("parts", [])}


# --- the detectors -----------------------------------------------------------

def budget_tightening(previews: list[dict], low_headroom_pct: float) -> list[dict]:
    """Committed previews whose size headroom is under the threshold.

    Computed from the *live* committed preview sizes, so it works even with an
    empty telemetry log — the one always-available pulse. A negative headroom
    means the file is already over budget and failing ``readme-gate``.
    """
    findings = [
        {
            "file": pv["file"],
            "bytes": pv["bytes"],
            "budget": pv["budget"],
            "headroom_pct": pv["headroom_pct"],
            "over": pv["headroom_pct"] < 0,
        }
        for pv in previews
        if pv["headroom_pct"] < low_headroom_pct
    ]
    findings.sort(key=lambda f: (f["headroom_pct"], f["file"]))
    return findings


def gate_failing(record: dict) -> list[dict]:
    """Hard failures in the latest gate run — the interrupt-worthy signal.

    Pre-gate render failures, parts with no printcheck score / criticals / a
    failed test-slice, and derivative-override checks that flipped to failing.
    """
    gate = record.get("gate", {})
    findings: list[dict] = []
    for pf in gate.get("pre_fails", []):
        findings.append({"kind": "pre-fail", "detail": _flat(pf)})
    for p in gate.get("parts", []):
        reasons = []
        if p.get("score") is None:
            reasons.append("no printcheck score")
        if p.get("criticals", 0) > 0:
            reasons.append(f"{p['criticals']} critical(s)")
        if p.get("slice_failed"):
            reasons.append("test-slice failed")
        if reasons:
            findings.append({"kind": "part", "detail": f"{_flat(p['stl'])}: {', '.join(reasons)}"})
    for d in gate.get("derivatives", []):
        if not d.get("ok", True):
            subject = _flat(d.get("subject", ""))
            label = f"{d['kind']} {subject}".strip()
            findings.append(
                {"kind": "derivative", "detail": f"{_flat(d['design'])} ({label}): {_flat(d.get('detail', ''))}"}
            )
    findings.sort(key=lambda f: (f["kind"], f["detail"]))
    return findings


def routine_dead(workflows: list[dict], k: int) -> list[dict]:
    """Scheduled routines whose ``k`` newest completed runs hold no success.

    Fires only when at least one of those runs ended in a *hard* conclusion
    (``failure`` / ``timed_out`` / ``startup_failure``): a pure-cancelled
    streak is queue-supersession noise (concurrency groups cancel superseded
    runs), not a dead routine. Fewer than ``k`` completed runs is too little
    history to call a routine dead.
    """
    hard = {"failure", "timed_out", "startup_failure"}
    findings: list[dict] = []
    for wf in workflows:
        runs = wf.get("runs", [])[:k]  # newest-first, as the API returns them
        if len(runs) < k:
            continue
        conclusions = [r.get("conclusion") for r in runs]
        if "success" in conclusions:
            continue
        if not any(c in hard for c in conclusions):
            continue
        findings.append(
            {"workflow": wf["file"], "window": k, "conclusions": conclusions,
             "url": runs[0].get("url")}
        )
    findings.sort(key=lambda f: f["workflow"])
    return findings


def lock_leak(
    issues: list[dict],
    open_prs: list[dict],
    branches: list[str],
    generated_at: str,
    leak_hours: float,
) -> list[dict]:
    """Active 🚢 SHIP-LOCK claims that outlived any evidence of work.

    Mirrors the selector's corroboration order (``select.py``): a
    ``claude/issue-<N>-*`` branch, or an open PR whose head branch matches or
    whose body carries a closing keyword, corroborates the claim and clears
    the issue here. What remains is the #312 incident class — a run killed
    between posting its lock and pushing a branch — and it fires once the
    claim is older than ``leak_hours``. An unparseable ``lockCreatedAt`` is
    skipped: never report a leak on a claim that cannot be dated.
    """
    now = _parse_iso(generated_at)
    findings: list[dict] = []
    for issue in issues:
        number = issue["number"]
        rx = _issue_branch_re(number)
        if any(rx.match(b or "") for b in branches or []):
            continue
        if any(
            _closes_issue(pr.get("body", ""), number)
            or rx.match(pr.get("headRefName", "") or "")
            for pr in open_prs or []
        ):
            continue
        created = _parse_iso(issue.get("lockCreatedAt", ""))
        if created is None or now is None:
            continue
        age_hours = (now - created).total_seconds() / 3600.0
        if age_hours <= leak_hours:
            continue
        findings.append(
            {"number": number, "title": issue.get("title", ""),
             "age_hours": round(age_hours, 1),
             "lockCreatedAt": issue.get("lockCreatedAt", "")}
        )
    findings.sort(key=lambda f: f["number"])
    return findings


def adoption_study(studies: list[dict]) -> list[dict]:
    """Open ``adoption-study`` submissions needing the lead's attention.

    Each study carries its own ``labels`` (``github.gather_run_health`` only
    lists **open** issues, so a closed one never reaches here). The disposition
    is read from those labels:

    - no ``disposition:*`` label at all → ``awaiting-disposition`` (the queue
      reminder — a submission nobody has ruled on yet);
    - ``disposition:worth-raising`` → ``worth-raising`` (escalate to the lead);
    - any other ``disposition:*`` (e.g. ``disposition:declined``) → not flagged,
      the ruling has been made.

    ``worth-raising`` takes precedence over a co-present ``disposition:*`` so a
    flagged escalation is never silently dropped.
    """
    findings: list[dict] = []
    for study in studies:
        labels = study.get("labels", [])
        if "disposition:worth-raising" in labels:
            state = "worth-raising"
        elif any(lbl.startswith("disposition:") for lbl in labels):
            continue  # a disposition was recorded (declined/other) — not flagged
        else:
            state = "awaiting-disposition"
        findings.append(
            {"number": study["number"], "title": study.get("title", ""),
             "state": state, "url": study.get("url", "")}
        )
    findings.sort(key=lambda f: f["number"])
    return findings


def score_regression(records: list[dict], score_drop: int, score_floor: float) -> list[dict]:
    """Parts below the score floor, or down by ≥ ``score_drop`` vs the prior run.

    Only full-catalog runs are compared (a scoped run gates fewer parts). The
    floor check needs one full-catalog run; the drop check needs two.
    """
    all_with_parts = [r for r in _all_records(records) if r.get("gate", {}).get("parts")]
    latest = all_with_parts[-1]
    cur = _parts_by_stl(latest)
    findings: list[dict] = []
    for stl in sorted(cur):
        score = cur[stl].get("score")
        if score is not None and score < score_floor:
            findings.append(
                {"stl": stl, "prev": None, "cur": score,
                 "reason": f"score {score}/100 is below the floor of {score_floor:g}"}
            )
    if len(all_with_parts) >= 2:
        prev = _parts_by_stl(all_with_parts[-2])
        for stl in sorted(cur):
            cs = cur[stl].get("score")
            ps = prev.get(stl, {}).get("score")
            if cs is not None and ps is not None and ps - cs >= score_drop:
                findings.append(
                    {"stl": stl, "prev": ps, "cur": cs,
                     "reason": f"score dropped {ps}→{cs} ({ps - cs} points)"}
                )
    findings.sort(key=lambda f: (f["stl"], f["reason"]))
    return findings


def walltime_regression(records: list[dict], ratio: float, min_seconds: int) -> list[dict]:
    """Designs whose render+gate wall time rose ≥ ``ratio``× vs the prior run.

    Compares the two latest full-catalog runs; ``min_seconds`` filters out the
    noise of tiny designs. ``evaluate`` reports "not evaluated" with < 2 runs.
    """
    all_rec = _all_records(records)
    latest = all_rec[-1].get("gate", {}).get("design_seconds", {})
    prev = all_rec[-2].get("gate", {}).get("design_seconds", {})
    findings: list[dict] = []
    for design in sorted(latest):
        cur = latest[design]
        before = prev.get(design)
        if before is not None and before > 0 and cur >= min_seconds and cur >= before * ratio:
            findings.append({"design": design, "prev": before, "cur": cur})
    return findings


def archived_creep(records: list[dict]) -> list[dict]:
    """Designs newly frozen out of gating since the prior full-catalog run.

    A rising archived set is the "presence-only, never re-verified" hole CI
    guards against (issue #69) — more of the catalog dropping out of gating.
    """
    all_rec = _all_records(records)
    latest = set(all_rec[-1].get("gate", {}).get("archived_skips", []))
    prev = set(all_rec[-2].get("gate", {}).get("archived_skips", []))
    return [{"design": d} for d in sorted(latest - prev)]


def report_drift(records: list[dict], report_placeholder: bool) -> list[dict]:
    """The committed telemetry log has runs but REPORT.md never regenerated.

    An integrity meta-check: if the roll-up commits a log record but not the
    matching REPORT.md, the human-facing report is silently stale.
    """
    if records and report_placeholder:
        return [
            {"detail": f"telemetry/log.ndjson has {len(records)} gate-run record(s) but "
                       "telemetry/REPORT.md is still the empty placeholder — the roll-up "
                       "did not regenerate it"}
        ]
    return []


# --- the one entry point -----------------------------------------------------

def evaluate(snapshot: dict[str, Any], cfg: Any) -> dict[str, Any]:
    """Run every detector, honouring the "not evaluated" rule for absent inputs."""
    records = snapshot.get("records", [])
    previews = snapshot.get("previews", [])
    report_placeholder = snapshot.get("reportPlaceholder", True)

    findings: dict[str, list[dict]] = {}
    not_evaluated: dict[str, str] = {}

    # Always available — computed from the live committed previews.
    findings["budget-tightening"] = budget_tightening(previews, cfg.low_headroom_pct)

    if not records:
        not_evaluated["gate-failing"] = "no gate-run records in telemetry/log.ndjson yet"
    else:
        findings["gate-failing"] = gate_failing(records[-1])

    # Run health is opt-in (issue #313): absent means an offline run, and the
    # "not evaluated is never silently empty" rule applies to both detectors.
    run_health = snapshot.get("runHealth")
    if run_health is None:
        reason = "no GitHub run-health gathered (offline run — pass --repo to enable)"
        not_evaluated["routine-dead"] = reason
        not_evaluated["lock-leak"] = reason
        not_evaluated["adoption-study"] = reason
    else:
        rh_now = run_health.get("gatheredAt") or snapshot["generatedAt"]
        findings["routine-dead"] = routine_dead(
            run_health.get("workflows", []), cfg.routine_dead_runs
        )
        findings["lock-leak"] = lock_leak(
            run_health.get("issues", []), run_health.get("openPRs", []),
            run_health.get("branches", []), rh_now, cfg.lock_leak_hours,
        )
        findings["adoption-study"] = adoption_study(
            run_health.get("adoptionStudies", [])
        )

    all_with_parts = [r for r in _all_records(records) if r.get("gate", {}).get("parts")]
    if not all_with_parts:
        not_evaluated["score-regression"] = (
            "no full-catalog (designs=ALL) gate run with printcheck parts yet"
        )
    else:
        findings["score-regression"] = score_regression(records, cfg.score_drop, cfg.score_floor)

    all_rec = _all_records(records)
    if len(all_rec) < 2:
        reason = "need ≥ 2 full-catalog (designs=ALL) gate runs to compare"
        not_evaluated["walltime-regression"] = f"{reason} wall time"
        not_evaluated["archived-creep"] = f"{reason} archived skips"
    else:
        findings["walltime-regression"] = walltime_regression(
            records, cfg.walltime_ratio, cfg.walltime_min_seconds
        )
        findings["archived-creep"] = archived_creep(records)

    # Always evaluable: a bare consistency check between the log and the report.
    findings["report-drift"] = report_drift(records, report_placeholder)

    return {
        "findings": findings,
        "not_evaluated": not_evaluated,
        "record_count": len(records),
        "all_count": len(all_rec),
        "preview_count": len(previews),
    }
