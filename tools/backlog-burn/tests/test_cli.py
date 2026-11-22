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


def test_triage_classify_all_failed_prints_infra(capsys, tmp_path):
    """CLI behavioral: synthetic all-failure outcomes → infra, not servable."""
    gh_out = tmp_path / "out"
    rc = main([
        "triage-classify",
        "--outcomes", "failure,failure,failure,failure,failure",
        "--provider-class", "servable",
        "--provider-reason", "served",
        "--chain", "backlog-burn",
        "--gh-output", str(gh_out),
    ])
    assert rc == 0
    printed = capsys.readouterr().out
    assert "CLASS backlog-burn: infra" in printed
    assert "REASON backlog-burn: no-link-served" in printed
    assert "servable" not in printed
    body = gh_out.read_text(encoding="utf-8")
    assert "class=infra\n" in body
    assert "reason=no-link-served\n" in body


def test_triage_classify_one_served_keeps_servable(capsys, tmp_path):
    gh_out = tmp_path / "out"
    rc = main([
        "triage-classify",
        "--outcomes", "failure,success,skipped,skipped,skipped",
        "--provider-class", "servable",
        "--provider-reason", "served",
        "--gh-output", str(gh_out),
    ])
    assert rc == 0
    printed = capsys.readouterr().out
    assert "CLASS backlog-burn: servable" in printed
    assert "REASON backlog-burn: served" in printed
    assert "class=servable\n" in gh_out.read_text(encoding="utf-8")


def test_triage_classify_deferred_disposition_keeps_servable(capsys):
    """#981: deferred disposition must not demote a served walk to infra."""
    rc = main([
        "triage-classify",
        "--outcomes", "success,skipped,skipped,skipped,skipped",
        "--provider-class", "servable",
        "--provider-reason", "served",
        "--disposition", "deferred",
    ])
    assert rc == 0
    printed = capsys.readouterr().out
    assert "CLASS backlog-burn: servable" in printed
    assert "infra" not in printed


def test_triage_classify_empty_outcomes_is_identity(capsys):
    """No ship-outcomes feed → provider signal unchanged (other routines)."""
    rc = main([
        "triage-classify",
        "--outcomes", "",
        "--provider-class", "servable",
        "--provider-reason", "served",
    ])
    assert rc == 0
    printed = capsys.readouterr().out
    assert "CLASS backlog-burn: servable" in printed
