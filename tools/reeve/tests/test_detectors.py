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


def wf(file, conclusions):
    # Newest-first, as the API returns them; the newest run carries url .../0.
    return {"file": file, "runs": [
        {"conclusion": c, "createdAt": f"2026-08-{16 - i:02d}T05:23:00Z",
         "url": f"https://runs/{file}/{i}"}
        for i, c in enumerate(conclusions)
    ]}


def locked(number, title="Design brief: ghost", locked_at="2026-08-16T00:00:00Z"):
    return {"number": number, "title": title, "lockCreatedAt": locked_at}


def adoption(number, title="Adoption study: x", labels=("adoption-study",)):
    return {"number": number, "title": title, "labels": list(labels),
            "createdAt": "2026-08-12T05:00:00Z", "updatedAt": "2026-08-13T05:00:00Z",
            "url": f"https://github.com/o/r/issues/{number}"}


NOW = "2026-08-16T06:00:00Z"   # 6h after locked()'s default lockCreatedAt


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


# --- routine-dead ------------------------------------------------------------

def test_routine_dead_fires_on_successless_window_with_hard_failure():
    found = detectors.routine_dead(
        [wf("design-run.yml", ["cancelled", "failure", "cancelled"])], 3)
    assert found == [{"workflow": "design-run.yml", "window": 3,
                      "conclusions": ["cancelled", "failure", "cancelled"],
                      "url": "https://runs/design-run.yml/0"}]


def test_routine_dead_silent_with_success_in_window():    # negative control
    assert detectors.routine_dead(
        [wf("design-run.yml", ["failure", "success", "failure"])], 3) == []


def test_routine_dead_silent_with_too_few_runs():         # negative control
    # k-1 completed runs is too little history to call a routine dead.
    assert detectors.routine_dead([wf("design-run.yml", ["failure", "failure"])], 3) == []


def test_routine_dead_silent_on_pure_cancelled_streak():  # negative control
    # Queue supersession cancels runs without the routine ever failing.
    assert detectors.routine_dead(
        [wf("design-run.yml", ["cancelled", "cancelled", "cancelled"])], 3) == []


def test_routine_dead_only_judges_the_k_newest():
    # A success older than the window does not save a routine.
    found = detectors.routine_dead(
        [wf("design-run.yml", ["failure", "failure", "failure", "success"])], 3)
    assert [f["workflow"] for f in found] == ["design-run.yml"]


def test_routine_dead_sorted_by_workflow_name():
    found = detectors.routine_dead(
        [wf("labeler.yml", ["failure"] * 3), wf("chunker.yml", ["failure"] * 3)], 3)
    assert [f["workflow"] for f in found] == ["chunker.yml", "labeler.yml"]


# --- lock-leak ---------------------------------------------------------------

def test_lock_leak_fires_on_old_uncorroborated_lock():
    found = detectors.lock_leak([locked(281)], [], [], NOW, CFG.lock_leak_hours)
    assert found == [{"number": 281, "title": "Design brief: ghost",
                      "age_hours": 6.0, "lockCreatedAt": "2026-08-16T00:00:00Z"}]


def test_lock_leak_silent_with_corroborating_branch():    # negative control
    assert detectors.lock_leak(
        [locked(281)], [], ["claude/issue-281-ghost"], NOW, CFG.lock_leak_hours) == []


def test_lock_leak_silent_with_closing_pr_body():         # negative control
    prs = [{"number": 9, "headRefName": "other", "body": "Resolved: #281"}]
    assert detectors.lock_leak([locked(281)], prs, [], NOW, CFG.lock_leak_hours) == []


def test_lock_leak_silent_with_pr_head_branch():          # negative control
    prs = [{"number": 9, "headRefName": "claude/issue-281-fix", "body": ""}]
    assert detectors.lock_leak([locked(281)], prs, [], NOW, CFG.lock_leak_hours) == []


def test_lock_leak_silent_under_age_threshold():          # negative control
    fresh = locked(281, locked_at="2026-08-16T05:30:00Z")  # 0.5h < 2h
    assert detectors.lock_leak([fresh], [], [], NOW, CFG.lock_leak_hours) == []


def test_lock_leak_branch_match_is_boundary_safe():
    # issue 28's branch must not corroborate issue 281's lock.
    found = detectors.lock_leak(
        [locked(281)], [], ["claude/issue-28-other"], NOW, CFG.lock_leak_hours)
    assert [f["number"] for f in found] == [281]


def test_lock_leak_skips_unparseable_lock_date():
    # A claim that cannot be dated is skipped, never reported as leaked.
    assert detectors.lock_leak(
        [locked(281, locked_at="not-a-date")], [], [], NOW, CFG.lock_leak_hours) == []


def test_lock_leak_sorted_by_number():
    found = detectors.lock_leak(
        [locked(285), locked(281)], [], [], NOW, CFG.lock_leak_hours)
    assert [f["number"] for f in found] == [281, 285]


# --- adoption-study ----------------------------------------------------------

def test_adoption_study_flags_awaiting_and_worth_raising():
    found = detectors.adoption_study([
        adoption(305, labels=["adoption-study"]),
        adoption(306, labels=["adoption-study", "disposition:worth-raising"]),
    ])
    assert {f["number"]: f["state"] for f in found} == {
        305: "awaiting-disposition", 306: "worth-raising"}
    assert found[0]["url"] == "https://github.com/o/r/issues/305"


def test_adoption_study_silent_on_declined():            # negative control
    # A recorded disposition (not worth-raising) means the ruling is made.
    assert detectors.adoption_study(
        [adoption(307, labels=["adoption-study", "disposition:declined"])]) == []


def test_adoption_study_worth_raising_wins_over_co_present_disposition():
    # A flagged escalation is never dropped by a co-present disposition label.
    found = detectors.adoption_study(
        [adoption(308, labels=["adoption-study", "disposition:declined",
                               "disposition:worth-raising"])])
    assert [f["state"] for f in found] == ["worth-raising"]


def test_adoption_study_sorted_by_number():
    found = detectors.adoption_study([
        adoption(306, labels=["adoption-study"]),
        adoption(305, labels=["adoption-study"]),
    ])
    assert [f["number"] for f in found] == [305, 306]


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


def test_evaluate_marks_absent_run_health_not_evaluated():
    # The offline invariant: no runHealth key -> both run-health detectors are
    # "not evaluated" with the pass-`--repo` reason, never silently empty.
    result = detectors.evaluate({"records": [], "previews": [], "reportPlaceholder": True}, CFG)
    ne = result["not_evaluated"]
    assert "offline run" in ne["routine-dead"]
    assert "offline run" in ne["lock-leak"]
    assert "offline run" in ne["adoption-study"]
    assert "routine-dead" not in result["findings"]
    assert "lock-leak" not in result["findings"]
    assert "adoption-study" not in result["findings"]


def test_evaluate_run_health_present_evaluates_both():
    snap = {"records": [], "previews": [], "reportPlaceholder": True,
            "generatedAt": "2026-08-01T00:00:00Z",
            "runHealth": {"gatheredAt": NOW,
                          "workflows": [wf("design-run.yml", ["failure"] * 3)],
                          "issues": [locked(281)], "openPRs": [], "branches": [],
                          "adoptionStudies": [adoption(305, labels=["adoption-study"])]}}
    result = detectors.evaluate(snap, CFG)
    assert "routine-dead" not in result["not_evaluated"]
    assert "lock-leak" not in result["not_evaluated"]
    assert "adoption-study" not in result["not_evaluated"]
    assert [f["workflow"] for f in result["findings"]["routine-dead"]] == ["design-run.yml"]
    # Ages are computed from runHealth's own gatheredAt, not generatedAt.
    assert result["findings"]["lock-leak"][0]["age_hours"] == 6.0
    assert [f["state"] for f in result["findings"]["adoption-study"]] == ["awaiting-disposition"]


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
# The package's ONE write-bearing module (issue #444): pushthrough.py applies
# an approved greenlight through decide.yml's own sequence — the confined-seam
# exemption the parent issue names. The purity tests below hold every OTHER
# module to read-only and pin that this one is real, so the exemption cannot
# rot into "everything is exempt".
WRITE_SEAM = "pushthrough.py"
# Includes signals.py — the committed-files seam, which reads only os/glob/json.
# The excluded modules are github.py — the opt-in GET-only live-read seam
# (issue #313's run health, and issue #443's greenlight queue — the open
# needs-decision issues plus their comment threads): it genuinely uses urllib,
# exactly like the groomer's, and test_github.py holds it to GET-only — and
# pushthrough.py, the write seam above (test_pushthrough.py holds it to the
# fail-closed order and the no-/decide-comment rule). The wrapper-mediated
# greenlight comments live outside this package entirely, in
# .claude/skills/reeve-greenlight/. cli.py stays in this list because it
# imports github.py and pushthrough.py lazily, inside the --repo /
# greenlight-select / greenlight-poll paths only.
_PURE_MODULES = ("detectors.py", "report.py", "config.py", "cli.py", "signals.py")


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


def test_package_contains_no_write_verbs_outside_the_confined_seam():
    # GET/read-only by construction: no POST/PATCH/PUT/DELETE anywhere in the
    # package (word-bounded, so GITHUB_OUTPUT's "PUT" doesn't trip it) except
    # pushthrough.py — the ONE confined seam the greenlight loop's approval
    # push-through (issue #444) needed, the backlog groomer's github.py shape
    # the parent issue named: every write verb in the package lives there, and
    # a test (below) pins that the exemption is not vacuous. Everything else
    # still reads only committed files plus the GET-only live seams.
    import re as _re

    verb_re = _re.compile(r"\b(POST|PATCH|PUT|DELETE)\b")
    for path in _PKG.glob("*.py"):
        if path.name == WRITE_SEAM:
            continue
        match = verb_re.search(path.read_text(encoding="utf-8"))
        assert match is None, f"{path.name} mentions {match.group(0) if match else ''}"


def test_write_verbs_are_confined_to_the_seam_and_the_seam_is_real():
    # The other half of the confinement (issue #444's purity guard): the seam
    # module must actually exist and actually carry write verbs — an exemption
    # for a file that isn't there, or one that drifted read-only while some
    # sibling quietly grew the verbs instead, is a hole dressed as a rule. And
    # the seam must import no module outside {github, greenlight} + stdlib, so
    # a write verb can never travel back into a pure module through it.
    import re as _re

    seam = _PKG / WRITE_SEAM
    assert seam.is_file(), f"the write seam {WRITE_SEAM} is missing"
    verbs = _re.findall(r"\b(POST|PUT|DELETE|PATCH)\b", seam.read_text(encoding="utf-8"))
    assert set(verbs) >= {"POST", "PUT", "DELETE"}, (
        f"{WRITE_SEAM} no longer performs the pushes it exists for: {sorted(set(verbs))}"
    )
    # The read side it builds on stays the GET seam; the pure side stays pure.
    assert _imports_of(seam) & {"urllib"} == {"urllib"}
    local_imports = _relative_imports_of(seam.read_text(encoding="utf-8"))
    assert local_imports <= {"config", "detectors", "greenlight", "github", "report", "signals"}, (
        f"{WRITE_SEAM} imports outside the package's own modules: {sorted(local_imports)}"
    )


def _relative_imports_of(source: str) -> set[str]:
    """The top-level package modules a source's relative imports resolve to.

    `from . import github` names the module in the alias; `from .github
    import _get` names it in `node.module` — the alias there is a symbol
    (`_get`), not a module. Collecting only alias names let `from
    .unapproved_module import github` pass the seam's import guard, because
    the alias `github` sat in the allowed set while the module did not.
    """
    tree = ast.parse(source)
    return {
        (node.module or alias.name).split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 1
        for alias in node.names
    }


def test_seam_import_guard_reads_the_module_not_the_alias():
    # The guard's own negative control: a relative import that names an
    # unapproved MODULE while aliasing an approved NAME must be caught — the
    # shape the alias-only collector let through.
    allowed = {"config", "detectors", "greenlight", "github", "report", "signals"}
    assert _relative_imports_of("from . import greenlight, github") <= allowed
    assert _relative_imports_of("from .github import _get") <= allowed
    smuggled = _relative_imports_of("from .unapproved_module import github")
    assert not smuggled <= allowed, smuggled
    nested = _relative_imports_of("from .unapproved_pkg.sub import github")
    assert not nested <= allowed, nested
