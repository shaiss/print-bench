"""Render the grooming report — deterministic markdown from one evaluation.

Render and post are split on purpose (the smart-ci comment's pattern): this
module is a pure, unit-testable function of ``detectors.evaluate``'s result,
and the workflow only reads the file it wrote and does the GitHub call.  The
marker is the first line of the body so the upsert step can find the one
report issue it owns with a ``startsWith`` match, the way every sticky
comment in ci.yml is found.
"""

from __future__ import annotations

import re
from typing import Any

# First line of the report issue's body; the workflow's upsert keys on it.
MARKER = "<!-- backlog-groomer-report -->"

# Section metadata: (finding key, heading, per-finding line renderer).
# Order here is the report's section order — stable, so diffs read clean.


def _clean_title(title: str) -> str:
    """One-line, length-capped, markdown-defused rendering of an issue title.

    Titles are the report's only untrusted text; they get newlines collapsed,
    markdown specials backslash-escaped, and an 80-char cap so one weird
    title can't reshape the report.  Deterministic by construction.
    """
    flat = re.sub(r"\s+", " ", title).strip()
    escaped = re.sub(r"([\\`*_\[\]|~<>])", r"\\\1", flat)
    return escaped[:80] + "…" if len(escaped) > 80 else escaped


def _line_stale(f: dict) -> str:
    return f"- #{f['number']} {_clean_title(f['title'])} — last update {f['updatedAt'][:10]} ({f['days']} days)"


def _line_armed_stuck(f: dict) -> str:
    return f"- #{f['number']} {_clean_title(f['title'])} — armed {f['days']} days, no open closing PR"


def _line_plain(f: dict) -> str:
    return f"- #{f['number']} {_clean_title(f['title'])}"


def _line_decision(f: dict) -> str:
    return f"- #{f['number']} {_clean_title(f['title'])} — `{f['verdict']}` landed, `needs-decision` still set"


def _line_oversized(f: dict) -> str:
    return f"- #{f['number']} {_clean_title(f['title'])} — quiet {f['days']} days with `declined-too-big`"


def _line_dup(f: dict) -> str:
    return (
        f"- #{f['a']} ↔ #{f['b']} ({f['score']:.2f}): "
        f"{_clean_title(f['title_a'])} / {_clean_title(f['title_b'])}"
    )


def _line_epic(f: dict) -> str:
    return f"- #{f['number']} {_clean_title(f['title'])} — all {f['total']} sub-issues closed"


def render(result: dict[str, Any], snapshot: dict[str, Any], cfg: Any) -> str:
    """The full report body, marker first, byte-deterministic."""
    findings = result["findings"]
    not_evaluated = result["not_evaluated"]
    generated = snapshot["generatedAt"]

    sections = [
        ("stale",
         f"Stale — no update in >{cfg.staleness_days} days", _line_stale),
        ("armed-stuck",
         f"Armed but stuck — `autonomy-ok` for >{cfg.armed_stuck_days} days with no open closing PR",
         _line_armed_stuck),
        ("unsized-armed",
         "Armed but unsized — `autonomy-ok` without a `points-<n>` label", _line_plain),
        ("decision-resolved-parked",
         "Decision resolved but parked — verdict landed, nobody resumed", _line_decision),
        ("unchunked-oversized",
         f"Oversized and unchunked — `declined-too-big` quiet for >{cfg.oversized_stuck_days} days",
         _line_oversized),
        ("dup-candidates",
         f"Possible duplicates — title similarity ≥ {cfg.dup_threshold}", _line_dup),
        ("epic-complete",
         "Epics ready to close — every sub-issue completed", _line_epic),
    ]

    out: list[str] = [
        MARKER,
        "# 🧹 Backlog grooming report",
        "",
        "Advisory only — this report is the groomer's sole output; nothing else was changed.",
        f"Snapshot: {result['issue_count']} open issues at {generated}.",
        f"Config: staleness_days={cfg.staleness_days}, armed_stuck_days={cfg.armed_stuck_days}, "
        f"oversized_stuck_days={cfg.oversized_stuck_days}, dup_threshold={cfg.dup_threshold}, "
        f"max_dup_pairs={cfg.max_dup_pairs}.",
        "",
        "## Summary",
        "",
        "| Detector | Findings |",
        "|---|---|",
    ]
    for key, _heading, _renderer in sections:
        shown = "not evaluated" if key in not_evaluated else str(len(findings[key]))
        if key == "dup-candidates" and key not in not_evaluated:
            shown = str(result["dup_total"])
        out.append(f"| {key} | {shown} |")
    out.append("")

    for key, heading, renderer in sections:
        out.append(f"## {heading}")
        out.append("")
        if key in not_evaluated:
            out.append(f"Not evaluated — {not_evaluated[key]}.")
        elif not findings[key]:
            out.append("None. ✅")
        else:
            out.extend(renderer(f) for f in findings[key])
            if key == "dup-candidates" and result["dup_total"] > len(findings[key]):
                # The no-silent-caps rule: a bounded list says so.
                out.append("")
                out.append(
                    f"_Showing the top {len(findings[key])} of {result['dup_total']} "
                    f"matching pairs (max_dup_pairs={cfg.max_dup_pairs})._"
                )
        out.append("")

    out.append("## Coverage")
    out.append("")
    if not_evaluated:
        for key in sorted(not_evaluated):
            out.append(f"- `{key}`: not evaluated — {not_evaluated[key]}.")
    else:
        out.append("All detectors evaluated over the full snapshot.")
    out.append("")

    out.append("---")
    out.append(
        "Thresholds: `.github/backlog-groomer.conf` · tool: `tools/backlog-groomer/` · issue #244"
    )
    out.append(f"_Automated report for the snapshot generated {generated}._")
    out.append("")
    out.append("_Generated by [Claude Code](https://claude.ai/code)_")
    out.append("")
    return "\n".join(out)
