"""Report renderer tests — the golden-file determinism gate, marker-first, and
the not-evaluated / over-budget rendering. The golden pins byte-exact
rendering of fixtures/snapshot.json under default Config(); any change to a
detector's semantics, a sort order, a heading or the marker shows up here and
must be a reviewed, regenerated golden.
"""

import json
import pathlib

from reeve.config import Config
from reeve.detectors import evaluate
from reeve.report import MARKER, render

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _load_snapshot():
    return json.loads((FIXTURES / "snapshot.json").read_text(encoding="utf-8"))


def _render_fixture():
    snapshot = _load_snapshot()
    cfg = Config()
    return render(evaluate(snapshot, cfg), snapshot, cfg)


def test_report_matches_golden():
    golden = (FIXTURES / "report.golden.md").read_text(encoding="utf-8")
    assert _render_fixture() == golden


def test_report_is_byte_deterministic():
    assert _render_fixture() == _render_fixture()


def test_marker_is_the_first_line():
    assert _render_fixture().splitlines()[0] == MARKER


def test_over_budget_preview_is_flagged():
    body = _render_fixture()
    assert "❌ over budget" in body


def test_lock_leak_title_is_sanitized():
    # Issue titles are the report's only untrusted text (they arrive from the
    # GitHub listing): markdown specials must come out escaped and newlines
    # collapsed, so one weird title cannot reshape the report.
    snapshot = {
        "generatedAt": "2026-08-16T06:00:00Z", "records": [], "previews": [],
        "reportPlaceholder": False,
        "runHealth": {
            "gatheredAt": "2026-08-16T06:00:00Z", "workflows": [],
            "issues": [{"number": 281, "title": "evil `code`\n# heading [x](y)",
                        "lockCreatedAt": "2026-08-16T00:00:00Z"}],
            "openPRs": [], "branches": [],
        },
    }
    cfg = Config()
    body = render(evaluate(snapshot, cfg), snapshot, cfg)
    line = next(ln for ln in body.splitlines() if ln.startswith("- #281"))
    assert "evil \\`code\\` # heading \\[x\\](y)" in line
    assert "\n# heading" not in line


def test_not_evaluated_never_silently_empty():
    # A snapshot with no telemetry still renders every section — the absent
    # ones say "Not evaluated", not a blank/clean line.
    snapshot = {"generatedAt": "2026-08-16T06:00:00Z", "records": [],
                "previews": [], "reportPlaceholder": True}
    cfg = Config()
    body = render(evaluate(snapshot, cfg), snapshot, cfg)
    assert "Not evaluated —" in body
    assert body.startswith(MARKER)
