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
    }

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
from typing import Any

_WS_RE = re.compile(r"\s+")


def _flat(text: str) -> str:
    """Collapse whitespace so a telemetry string renders on one line."""
    return _WS_RE.sub(" ", str(text)).strip()


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
