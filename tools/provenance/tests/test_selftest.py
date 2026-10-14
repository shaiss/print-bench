"""selftest — the suite scripts/provenance.sh --selftest runs.

Owner: H6 (the aggregator; the cases belong to gitstore, membership and trust,
so the end-to-end runs wait for them with ``@needs``). The aggregator's own
rules — one line per case, a False / raising / non-bool case fails the run, a
module that cannot supply its cases is a FAIL and never a skip — are tested
here on planted cases, live.
"""

from __future__ import annotations

import io
import subprocess

import pytest

from conftest import REPO, needs
from provenance import gitstore, membership, selftest, trust

SCRIPT = REPO / "scripts" / "provenance.sh"


def _run_with(monkeypatch, planted):
    monkeypatch.setattr(selftest, "cases", lambda: planted)
    buf = io.StringIO()
    return selftest.run(buf), buf.getvalue().splitlines()


@needs(gitstore.selftest_cases, membership.selftest_cases, trust.selftest_cases)
def test_suite_passes():
    """selftest.run() returns 0 and prints one 'selftest ok' line per case."""
    suite = selftest.cases()
    buf = io.StringIO()
    assert selftest.run(buf) == 0, buf.getvalue()
    lines = buf.getvalue().splitlines()
    assert [ln for ln in lines if ln.startswith("selftest ok ")] == [
        f"selftest ok {label}" for label, _ in suite]
    assert not [ln for ln in lines if ln.startswith("selftest FAIL")]
    # Every module contributes (a module returning nothing would itself be a FAIL line).
    assert {label.split(":", 1)[0] for label, _ in suite} == set(selftest.MODULES)


def test_suite_fails_when_a_case_fails(monkeypatch):
    """Negative: a case returning False makes run() return 1."""
    code, lines = _run_with(monkeypatch, [("a: holds", lambda: True), ("b: broken", lambda: False)])
    assert code == 1
    assert lines[:2] == ["selftest ok a: holds", "selftest FAIL b: broken"]
    assert lines[-1] == "provenance selftest: 1 held, 1 failed"


@pytest.mark.parametrize("bad", [lambda: None, lambda: 1, lambda: "yes", lambda: 1 / 0])
def test_a_non_true_or_raising_case_fails(monkeypatch, bad):
    code, lines = _run_with(monkeypatch, [("a: ok", lambda: True), ("b: odd", bad)])
    assert code == 1 and lines[1].startswith("selftest FAIL b: odd")


def test_all_true_passes_and_an_empty_suite_does_not(monkeypatch):
    code, lines = _run_with(monkeypatch, [("a: x", lambda: True), ("b: y", lambda: True)])
    assert code == 0 and lines == ["selftest ok a: x", "selftest ok b: y",
                                   "provenance selftest: 2 held, 0 failed"]
    assert _run_with(monkeypatch, [])[0] == 1        # a suite of nothing proves nothing


def test_a_module_that_cannot_supply_cases_is_a_fail(monkeypatch):
    """The collector: a stub (NotImplementedError), an empty list, a malformed case — all FAIL."""
    def stub():
        raise NotImplementedError("builder H2")

    monkeypatch.setattr(gitstore, "selftest_cases", lambda: [("guard D", lambda: True)])
    monkeypatch.setattr(membership, "selftest_cases", stub)
    monkeypatch.setattr(trust, "selftest_cases", lambda: [("bad", "not callable")])
    suite = selftest.cases()
    labels = [label for label, _ in suite]
    assert labels[0] == "gitstore: guard D"
    assert labels[1].startswith("membership: cases unavailable (NotImplementedError: builder H2")
    assert labels[2].startswith("trust: malformed case")
    assert [fn() for _, fn in suite] == [True, False, False]
    buf = io.StringIO()
    assert selftest.run(buf) == 1
    monkeypatch.setattr(trust, "selftest_cases", lambda: [])
    assert any(label == "trust: selftest_cases() returned no case" for label, _ in selftest.cases())


def test_labels_stay_one_line(monkeypatch):
    monkeypatch.setattr(gitstore, "selftest_cases", lambda: [("two\nlines", lambda: True)])
    monkeypatch.setattr(membership, "selftest_cases", lambda: [("m", lambda: True)])
    monkeypatch.setattr(trust, "selftest_cases", lambda: [("t", lambda: True)])
    buf = io.StringIO()
    assert selftest.run(buf) == 0
    assert "selftest ok gitstore: two lines" in buf.getvalue().splitlines()


def test_script_wrapper_refuses_an_unknown_flag():
    """scripts/provenance.sh with an unknown flag exits 2 (live half of test_script_wrapper)."""
    res = subprocess.run(["bash", str(SCRIPT), "--no-such-flag"], capture_output=True, text=True)
    assert res.returncode == 2 and "unknown option" in res.stderr
    assert "scaffold" not in SCRIPT.read_text(encoding="utf-8").lower()
    assert "exec python3 -m provenance selftest" in SCRIPT.read_text(encoding="utf-8")


@needs(gitstore.selftest_cases, membership.selftest_cases, trust.selftest_cases)
def test_script_wrapper():
    """scripts/provenance.sh --selftest exits 0; with an unknown flag exits 2."""
    res = subprocess.run(["bash", str(SCRIPT), "--selftest"], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "selftest ok" in res.stdout and "selftest FAIL" not in res.stdout
    bad = subprocess.run(["bash", str(SCRIPT), "--bogus"], capture_output=True, text=True)
    assert bad.returncode == 2


def test_check_sh_runs_the_selftest():
    text = (REPO / "scripts" / "check.sh").read_text(encoding="utf-8")
    assert "./scripts/provenance.sh --selftest" in text
