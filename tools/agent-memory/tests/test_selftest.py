"""The selftest check.sh runs must be able to FAIL — break a rule, watch it."""

from __future__ import annotations

import pytest

from agent_memory import rules, selftest, store


def _run():
    lines = []
    rc = selftest.run(out=lines.append)
    return rc, lines


def test_selftest_passes_on_the_real_rules():
    rc, lines = _run()
    assert rc == 0, lines
    assert len([ln for ln in lines if ln.startswith("ok ")]) == len(selftest.CASES)


@pytest.mark.parametrize(
    "target, attr, broken, label",
    [
        # prediction error ignored: the surprising failure no longer outscores
        (rules, "PE_WEIGHT", 0, "prediction error"),
        # Zeigarnik flattened: unfinished no longer outranks completed-clean
        (rules, "ZEIGARNIK", dict.fromkeys(rules.ZEIGARNIK, 0), "Zeigarnik"),
        # depth decoupled from salience: everything rich
        (rules, "depth_for", lambda score: "rich", "depth"),
        # provenance self-certified: everything confirmed
        (rules, "verified_for", lambda sources: rules.VERIFIED_CONFIRMED, "provenance"),
    ],
)
def test_negative_control_a_broken_rule_fails_the_selftest(monkeypatch, target, attr, broken, label):
    monkeypatch.setattr(target, attr, broken)
    rc, lines = _run()
    assert rc == 1
    assert any(ln.startswith("FAIL") and label in ln for ln in lines), lines


def test_negative_control_an_overwriting_store_fails_the_selftest(monkeypatch):
    # A store that silently overwrites (the destructive edit) must be caught.
    real_open = open

    def clobbering_open(path, mode="r", *a, **kw):
        return real_open(path, mode.replace("x", "w"), *a, **kw)

    monkeypatch.setattr(store, "open", clobbering_open, raising=False)
    rc, lines = _run()
    assert rc == 1
    assert any(ln.startswith("FAIL") and "immutability" in ln for ln in lines), lines
