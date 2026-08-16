"""Detector tests — a positive case and a negative control for each, plus the
advisory-only checks (the pure core imports nothing network-capable, and the
whole package performs no HTTP write verb). Delete a detector's condition and
one half of its pair fails.
"""

import ast
import copy
import pathlib

from reeve import detectors
from reeve.config import Config

CFG = Config()


def part(stl, score=95, criticals=0, slice_failed=False):
    return {"stl": stl, "score": score, "verdict": "x", "criticals": criticals,
            "warnings": 0, "slice_failed": slice_failed, "print_time": "1h", "filament_g": "1"}


def record(parts=None, seconds=None, archived=None, pre_fails=None,
           derivatives=None, ok=True, designs="ALL"):
    return {
        "schema": 1, "kind": "gate-run", "utc": "2026-08-15T05:00:00Z",
        "meta": {"designs": designs, "event": "push", "run_id": "1", "sha": "x"},
        "gate": {
            "parts": parts or [],
            "pre_fails": pre_fails or [],
            "derivatives": derivatives or [],
            "design_seconds": seconds or {},
            "archived_skips": archived or [],
            "fail_lines": 0 if ok else 1,
            "ok": ok,
        },
    }


def preview(file, headroom):
    return {"file": file, "bytes": 1, "budget": 100, "headroom_pct": headroom}


# --- budget-tightening -------------------------------------------------------

def test_budget_tightening_fires_under_threshold():
    found = detectors.budget_tightening([preview("a.gif", 4.6)], CFG.low_headroom_pct)
    assert [f["file"] for f in found] == ["a.gif"]
    assert found[0]["over"] is False


def test_budget_tightening_flags_over_budget():
    found = detectors.budget_tightening([preview("a.png", -1.7)], CFG.low_headroom_pct)
    assert found[0]["over"] is True


def test_budget_tightening_silent_with_headroom():        # negative control
    assert detectors.budget_tightening([preview("a.png", 68.2)], CFG.low_headroom_pct) == []


def test_budget_tightening_sorted_worst_first():
    found = detectors.budget_tightening(
        [preview("a.gif", 4.6), preview("b.png", -1.7)], CFG.low_headroom_pct)
    assert [f["file"] for f in found] == ["b.png", "a.gif"]


# --- gate-failing ------------------------------------------------------------

def test_gate_failing_lists_hard_failures():
    rec = record(
        parts=[part("build/g.stl", score=None, slice_failed=True), part("build/b.stl", criticals=1)],
        pre_fails=["delta: render failed"],
        derivatives=[{"ok": False, "design": "eps", "kind": "override",
                      "subject": "parent:lid", "detail": "no override took"}],
        ok=False,
    )
    kinds = sorted({f["kind"] for f in detectors.gate_failing(rec)})
    assert kinds == ["derivative", "part", "pre-fail"]


def test_gate_failing_silent_on_clean_run():              # negative control
    assert detectors.gate_failing(record(parts=[part("build/a.stl", score=95)])) == []


# --- score-regression --------------------------------------------------------

def test_score_regression_flags_below_floor():
    recs = [record(parts=[part("build/b.stl", score=72)])]
    found = detectors.score_regression(recs, CFG.score_drop, CFG.score_floor)
    assert any("below the floor" in f["reason"] for f in found)


def test_score_regression_flags_drop_vs_prior():
    recs = [record(parts=[part("build/a.stl", score=95)]),
            record(parts=[part("build/a.stl", score=85)])]
    found = detectors.score_regression(recs, CFG.score_drop, CFG.score_floor)
    assert any("dropped 95→85" in f["reason"] for f in found)


def test_score_regression_silent_when_stable_and_above_floor():   # negative control
    recs = [record(parts=[part("build/a.stl", score=95)]),
            record(parts=[part("build/a.stl", score=94)])]  # 1 < score_drop, above floor
    assert detectors.score_regression(recs, CFG.score_drop, CFG.score_floor) == []


def test_score_regression_boundary_drop_is_exclusive_below_threshold():
    # A 2-point drop with score_drop=3 does not fire; a 3-point drop does.
    recs2 = [record(parts=[part("x", score=95)]), record(parts=[part("x", score=93)])]
    assert detectors.score_regression(recs2, 3, 0) == []
    recs3 = [record(parts=[part("x", score=95)]), record(parts=[part("x", score=92)])]
    assert detectors.score_regression(recs3, 3, 0) != []


# --- walltime-regression -----------------------------------------------------

def test_walltime_regression_fires_on_slowdown():
    recs = [record(seconds={"a": 40}), record(seconds={"a": 100})]  # 2.5x, >= min
    found = detectors.walltime_regression(recs, CFG.walltime_ratio, CFG.walltime_min_seconds)
    assert [f["design"] for f in found] == ["a"]


def test_walltime_regression_silent_below_ratio():        # negative control
    recs = [record(seconds={"a": 100}), record(seconds={"a": 120})]  # 1.2x < 1.5x
    assert detectors.walltime_regression(recs, CFG.walltime_ratio, CFG.walltime_min_seconds) == []


def test_walltime_regression_ignores_tiny_designs():
    recs = [record(seconds={"a": 2}), record(seconds={"a": 20})]  # 10x but < min_seconds
    assert detectors.walltime_regression(recs, CFG.walltime_ratio, CFG.walltime_min_seconds) == []


# --- archived-creep ----------------------------------------------------------

def test_archived_creep_flags_new_skip():
    recs = [record(archived=["old"]), record(archived=["old", "new"])]
    assert [f["design"] for f in detectors.archived_creep(recs)] == ["new"]


def test_archived_creep_silent_when_unchanged():          # negative control
    recs = [record(archived=["old"]), record(archived=["old"])]
    assert detectors.archived_creep(recs) == []


# --- report-drift ------------------------------------------------------------

def test_report_drift_fires_when_log_has_runs_but_report_empty():
    assert detectors.report_drift([record()], report_placeholder=True) != []


def test_report_drift_silent_when_report_present():       # negative control
    assert detectors.report_drift([record()], report_placeholder=False) == []


def test_report_drift_silent_when_no_records():
    assert detectors.report_drift([], report_placeholder=True) == []


# --- evaluate(): the not-evaluated honesty rule ------------------------------

def test_evaluate_marks_absent_inputs_not_evaluated():
    result = detectors.evaluate({"records": [], "previews": [], "reportPlaceholder": True}, CFG)
    ne = result["not_evaluated"]
    assert "gate-failing" in ne          # no records
    assert "score-regression" in ne      # no ALL run with parts
    assert "walltime-regression" in ne   # < 2 ALL runs
    assert "archived-creep" in ne
    # budget-tightening is always evaluated (from live previews), clean here.
    assert result["findings"]["budget-tightening"] == []


def test_evaluate_scoped_runs_do_not_enable_comparisons():
    # Two runs, but both scoped (designs != ALL) — the comparisons still can't fire.
    recs = [record(parts=[part("x", 90)], designs="alpha"),
            record(parts=[part("x", 60)], designs="alpha")]
    result = detectors.evaluate({"records": recs, "previews": [], "reportPlaceholder": False}, CFG)
    assert "score-regression" in result["not_evaluated"]
    assert "walltime-regression" in result["not_evaluated"]


def test_evaluate_is_pure_and_repeatable():
    snap = {"records": [record(parts=[part("x", 90)])], "previews": [preview("a.png", 5.0)],
            "reportPlaceholder": True}
    first = detectors.evaluate(copy.deepcopy(snap), CFG)
    second = detectors.evaluate(copy.deepcopy(snap), CFG)
    assert first == second


# ---------------------------------------------------------------------------
# Advisory-only, checkable: the pure core imports nothing network-capable, and
# the whole package performs no write verb anywhere.
# ---------------------------------------------------------------------------

_PKG = pathlib.Path(detectors.__file__).parent
_FORBIDDEN_IMPORTS = {"urllib", "socket", "http", "subprocess", "requests"}
_PURE_MODULES = ("detectors.py", "report.py", "config.py", "cli.py")


def _imports_of(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_pure_modules_import_nothing_network_capable():
    for module in _PURE_MODULES:
        assert not _imports_of(_PKG / module) & _FORBIDDEN_IMPORTS, module


def test_package_contains_no_write_verbs():
    # GET/read-only by construction: no POST/PATCH/PUT/DELETE anywhere in the
    # package (word-bounded, so GITHUB_OUTPUT's "PUT" doesn't trip it). Reeve
    # reads only committed files; the workflow's upsert is the sole write.
    import re as _re

    verb_re = _re.compile(r"\b(POST|PATCH|PUT|DELETE)\b")
    for path in _PKG.glob("*.py"):
        match = verb_re.search(path.read_text(encoding="utf-8"))
        assert match is None, f"{path.name} mentions {match.group(0) if match else ''}"
