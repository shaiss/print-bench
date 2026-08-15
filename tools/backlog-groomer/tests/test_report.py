"""Report renderer tests — the golden file is the determinism gate (AC1).

The golden pins the byte-exact rendering of the fixture snapshot under the
documented default config: any change to a detector's semantics, a sort
order, a heading, or the marker shows up as a golden diff and has to be a
reviewed, regenerated file — never silent drift.  Detector *semantics* are
independently pinned by ``test_detectors.py``; this file owns the bytes.
"""

from __future__ import annotations

import json
import pathlib

from backlog_groomer.config import Config
from backlog_groomer.detectors import evaluate
from backlog_groomer.report import MARKER, render

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _load_snapshot():
    with open(FIXTURES / "snapshot.json", encoding="utf-8") as fh:
        return json.load(fh)


def _render_fixture() -> str:
    snapshot = _load_snapshot()
    cfg = Config()
    return render(evaluate(snapshot, cfg), snapshot, cfg)


def test_report_matches_golden():
    golden = (FIXTURES / "report.golden.md").read_text(encoding="utf-8")
    assert _render_fixture() == golden


def test_report_is_byte_deterministic():
    # Fresh loads both times: same snapshot in, same bytes out, twice.
    assert _render_fixture() == _render_fixture()


def test_marker_is_the_first_line():
    # The workflow's upsert finds the report issue by startsWith(MARKER).
    assert _render_fixture().splitlines()[0] == MARKER


def test_cap_disclosure_present_when_capped():
    report = _render_fixture()
    # 16 = C(6,2) widget-bracket pairs + the epic-all/half-done pair the
    # fixture happens to score at exactly 0.60 — both disclosed, capped at 10.
    assert "Showing the top 10 of 16 matching pairs" in report


def _mini_snapshot(issues):
    return {"generatedAt": "2026-08-15T06:00:00+00:00", "issues": issues, "openPRs": []}


def test_cap_disclosure_absent_when_not_capped():
    snapshot = _mini_snapshot([
        {"number": 60, "title": "Widget mount bracket one", "labels": [],
         "createdAt": "2026-08-14T06:00:00+00:00", "updatedAt": "2026-08-14T06:00:00+00:00"},
        {"number": 61, "title": "Widget mount bracket two", "labels": [],
         "createdAt": "2026-08-14T06:00:00+00:00", "updatedAt": "2026-08-14T06:00:00+00:00"},
    ])
    cfg = Config()
    report = render(evaluate(snapshot, cfg), snapshot, cfg)
    assert "Showing the top" not in report


def test_not_evaluated_rendered_never_silently_empty():
    snapshot = _mini_snapshot([
        {"number": 20, "title": "Armed task", "labels": ["autonomy-ok", "points-1"],
         "createdAt": "2026-08-01T06:00:00+00:00", "updatedAt": "2026-08-01T06:00:00+00:00"},
    ])
    del snapshot["openPRs"]
    cfg = Config()
    report = render(evaluate(snapshot, cfg), snapshot, cfg)
    assert "Not evaluated — snapshot carries no open-PR data" in report
    assert "| armed-stuck | not evaluated |" in report


def test_titles_are_defused_and_capped():
    nasty = "A `weird` [title] | with *markdown*\nand a newline " + "x" * 100
    snapshot = _mini_snapshot([
        {"number": 10, "title": nasty, "labels": [],
         "createdAt": "2026-07-01T06:00:00+00:00", "updatedAt": "2026-07-01T06:00:00+00:00"},
    ])
    cfg = Config()
    report = render(evaluate(snapshot, cfg), snapshot, cfg)
    line = next(l for l in report.splitlines() if l.startswith("- #10"))
    assert "\\`weird\\`" in line and "\\|" in line  # markdown defused
    assert "\n" not in line[1:]                     # newline collapsed
    assert "…" in line                              # length-capped
