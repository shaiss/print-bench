"""Render the bench-health report — deterministic markdown from one evaluation.

Render and post are split on purpose (the groomer's / smart-ci's pattern):
this module is a pure, unit-testable function of ``detectors.evaluate``'s
result, and the workflow only reads the file it wrote and does the GitHub
call. The marker is the first line of the body so the upsert step can find
the one report issue it owns with a ``startsWith`` match.

Most of what Reeve renders — file paths, design names — comes from the tree
and the telemetry log, both controlled. The lock-leak findings (issue #313)
are the exception: their issue titles are untrusted GitHub text, so they go
through ``_clean_title`` — the groomer's defusal — before rendering.
"""

from __future__ import annotations

import re
from typing import Any

# First line of the report issue's body; the workflow's upsert keys on it.
MARKER = "<!-- reeve-bench-health -->"


def _clean_title(title: str) -> str:
    """One-line, length-capped, markdown-defused rendering of an issue title.

    Titles are the report's only untrusted text; they get newlines collapsed,
    markdown specials backslash-escaped, and an 80-char cap so one weird
    title can't reshape the report.  Deterministic by construction.
    """
    flat = re.sub(r"\s+", " ", title).strip()
    escaped = re.sub(r"([\\`*_\[\]|~<>])", r"\\\1", flat)
    return escaped[:80] + "…" if len(escaped) > 80 else escaped


def _line_gate_failing(f: dict) -> str:
    return f"- {f['kind']}: {f['detail']}"


def _line_routine_dead(f: dict) -> str:
    conclusions = ", ".join(str(c) for c in f["conclusions"])
    return f"- `{f['workflow']}` — {conclusions} — [latest run]({f['url']})"


def _line_lock_leak(f: dict) -> str:
    return (
        f"- #{f['number']} {_clean_title(f['title'])} — "
        f"locked {f['age_hours']}h ago, uncorroborated"
    )


def _line_adoption_study(f: dict) -> str:
    # The title is untrusted GitHub text, so it goes through _clean_title.
    return f"- #{f['number']} {_clean_title(f['title'])} — {f['state']}"


def _line_score(f: dict) -> str:
    return f"- `{f['stl']}` — {f['reason']}"


def _line_budget(f: dict) -> str:
    flag = " ❌ over budget" if f["over"] else " ⚠️"
    return (
        f"- `{f['file']}` — {f['headroom_pct']:.1f}% headroom "
        f"({f['bytes']}/{f['budget']} bytes){flag}"
    )


def _line_walltime(f: dict) -> str:
    return f"- `{f['design']}` — {f['prev']}s → {f['cur']}s"


def _line_archived(f: dict) -> str:
    return f"- `{f['design']}` — newly archived, dropped from gating"


def _line_drift(f: dict) -> str:
    return f"- {f['detail']}"


def render(result: dict[str, Any], snapshot: dict[str, Any], cfg: Any) -> str:
    """The full report body, marker first, byte-deterministic."""
    findings = result["findings"]
    not_evaluated = result["not_evaluated"]
    generated = snapshot["generatedAt"]

    # Order here is the report's section order — most severe first.
    sections = [
        ("gate-failing",
         "Gate failing — the latest run has hard failures", _line_gate_failing),
        ("routine-dead",
         f"Routine dead — no success in a routine's last {cfg.routine_dead_runs} completed runs",
         _line_routine_dead),
        ("lock-leak",
         f"Ship-lock leak — an uncorroborated 🚢 SHIP-LOCK older than {cfg.lock_leak_hours:g}h",
         _line_lock_leak),
        ("score-regression",
         f"Score regression — a part below {cfg.score_floor:g}/100 or down ≥{cfg.score_drop}",
         _line_score),
        ("budget-tightening",
         f"Preview budget tightening — headroom < {cfg.low_headroom_pct:g}%", _line_budget),
        ("walltime-regression",
         f"Gate wall-time regression — a design ≥ {cfg.walltime_ratio:g}× slower", _line_walltime),
        ("archived-creep",
         "Archived creep — a design newly frozen out of gating", _line_archived),
        ("adoption-study",
         "Adoption study submissions awaiting a disposition or worth raising",
         _line_adoption_study),
        ("report-drift",
         "Telemetry report drift — REPORT.md out of sync with the log", _line_drift),
    ]

    out: list[str] = [
        MARKER,
        "# 🩺 Bench health report",
        "",
        "Advisory only — this report is Reeve's sole output; nothing else was changed.",
        f"Pulse: {result['record_count']} gate-run record(s) "
        f"({result['all_count']} full-catalog), {result['preview_count']} committed previews, "
        f"at {generated}.",
        f"Thresholds: low_headroom_pct={cfg.low_headroom_pct:g}, score_drop={cfg.score_drop}, "
        f"score_floor={cfg.score_floor:g}, walltime_ratio={cfg.walltime_ratio:g}, "
        f"walltime_min_seconds={cfg.walltime_min_seconds}, "
        f"routine_dead_runs={cfg.routine_dead_runs}, lock_leak_hours={cfg.lock_leak_hours:g}.",
        "",
        "## Summary",
        "",
        "| Signal | Findings |",
        "|---|---|",
    ]
    for key, _heading, _renderer in sections:
        shown = "not evaluated" if key in not_evaluated else str(len(findings.get(key, [])))
        out.append(f"| {key} | {shown} |")
    out.append("")

    for key, heading, renderer in sections:
        out.append(f"## {heading}")
        out.append("")
        if key in not_evaluated:
            out.append(f"Not evaluated — {not_evaluated[key]}.")
        elif not findings.get(key):
            out.append("None. ✅")
        else:
            out.extend(renderer(f) for f in findings[key])
        out.append("")

    out.append("## Coverage")
    out.append("")
    if not_evaluated:
        for key in sorted(not_evaluated):
            out.append(f"- `{key}`: not evaluated — {not_evaluated[key]}.")
    else:
        out.append("All signals evaluated.")
    out.append("")

    out.append("---")
    out.append(
        "Thresholds: `.github/reeve.conf` · tool: `tools/reeve/` · charter: `PM.md` · issue #272"
    )
    out.append(f"_Automated bench-health report for the pulse taken {generated}._")
    out.append("")
    # Reeve is deterministic and holds no LLM — attributing the report to a model
    # would contradict its own contract (the __init__ docstring, the workflow).
    out.append("_Generated by Reeve — deterministic, no LLM (`tools/reeve/`)._")
    out.append("")
    return "\n".join(out)
