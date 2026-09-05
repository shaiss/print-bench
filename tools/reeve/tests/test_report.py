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
from reeve.report import ANDON_BANNER, MARKER, render

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


def test_andon_pulled_adds_exactly_one_banner_line_and_nothing_else():
    # The AI andon cord (docs/andon-cord.md): pulled inserts ANDON_BANNER and
    # its blank once, under the H1, MARKER still first — and NOTHING else
    # moves, so the pulled body minus that insertion is today's golden bytes.
    snapshot = _load_snapshot()
    cfg = Config()
    result = evaluate(snapshot, cfg)
    golden = (FIXTURES / "report.golden.md").read_text(encoding="utf-8")
    released = render(result, snapshot, cfg)
    pulled = render(result, snapshot, cfg, andon_pulled=True)
    assert released == golden
    assert pulled.splitlines()[0] == MARKER
    assert pulled.count(ANDON_BANNER) == 1
    assert ANDON_BANNER not in released
    assert pulled.replace(ANDON_BANNER + "\n\n", "", 1) == released
    # Byte-pin the wording itself: the golden pair.
    pulled_golden = (FIXTURES / "report.andon-pulled.golden.md").read_text(encoding="utf-8")
    assert pulled == pulled_golden


def test_andon_released_is_the_golden_bytes():
    # Negative control: an explicit andon_pulled=False renders the golden —
    # the released path never carries a banner (or a "released" line).
    snapshot = _load_snapshot()
    cfg = Config()
    golden = (FIXTURES / "report.golden.md").read_text(encoding="utf-8")
    assert render(evaluate(snapshot, cfg), snapshot, cfg, andon_pulled=False) == golden
    assert ANDON_BANNER not in golden


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
