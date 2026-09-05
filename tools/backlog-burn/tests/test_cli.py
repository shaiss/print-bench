"""CLI tests for the backlog-burn entry point.

Focus: the job-summary heading is caller-supplied so the three routines that
share this selector (backlog burn, design run, chunker) each get a correctly
titled block. The default must stay "Backlog burn" (no regression for the
routine the tool is named after); an explicit --summary-title overrides it.
"""

from __future__ import annotations

import json

from backlog_burn.cli import main


def _snapshot():
    """A minimal snapshot with one eligible issue (autonomy-ok, unclaimed)."""
    return {
        "issues": [
            {
                "number": 42,
                "title": "issue 42",
                "createdAt": "2026-08-01T00:00:00Z",
                "labels": ["autonomy-ok"],
                "comments": [],
            }
        ],
        "openPRs": [],
        "branches": [],
    }


def _run_select(tmp_path, extra_args):
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(_snapshot()), encoding="utf-8")
    summary = tmp_path / "summary.md"
    rc = main(["select", "--input", str(snap), "--summary", str(summary), *extra_args])
    assert rc == 0
    return summary.read_text(encoding="utf-8")


def test_summary_title_defaults_to_backlog_burn(tmp_path):
    out = _run_select(tmp_path, [])
    assert out.startswith("## Backlog burn\n")


def test_summary_title_override(tmp_path):
    out = _run_select(tmp_path, ["--summary-title", "Chunker"])
    assert out.startswith("## Chunker\n")
    assert "## Backlog burn" not in out


def test_summary_title_override_design_run(tmp_path):
    out = _run_select(tmp_path, ["--summary-title", "Design run"])
    assert out.startswith("## Design run\n")
