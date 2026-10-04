"""Rule 1 — deterministic importance (#429 AC: the importance formula).

``importance = round(PE_WEIGHT * |expected - actual|) + ZEIGARNIK[status] +
sum(CONSEQUENCE[signal])``, clamped to 100. Each term gets a positive case
and a negative control, and a golden table pins the constants so a retune is
a deliberate diff, never an accident.
"""

from __future__ import annotations

import pytest

from agent_memory import NoteError, RuleError, encode, rules
from conftest import make_event


def score(**over) -> int:
    return encode(make_event(**over))["importance"]


# --- prediction error ---------------------------------------------------------


def test_surprise_outscores_an_expected_outcome():
    # A gate expected to pass (0.95) that fails is the anchor event; a gate
    # expected to fail (0.05) that fails is not news.
    assert score(expected=0.95, actual=0.0) > score(expected=0.05, actual=0.0)


def test_prediction_error_is_proportional_and_symmetric():
    assert score(expected=0.5, actual=1.0) == 30
    assert score(expected=0.0, actual=1.0) == rules.PE_WEIGHT
    # an unexpected success is as surprising as an unexpected failure
    assert score(expected=0.1, actual=0.9) == score(expected=0.9, actual=0.1)


def test_negative_control_the_400th_green_run_scores_zero():
    assert score(expected=1.0, actual=1.0) == 0
    assert score() == 0  # unmeasured expectation contributes nothing


def test_expected_and_actual_come_as_a_pair():
    with pytest.raises(NoteError, match="pair"):
        encode(make_event(expected=0.9))
    with pytest.raises(NoteError, match="pair"):
        encode(make_event(actual=0.0))


@pytest.mark.parametrize(
    "bad",
    # 10**1000 is a valid JSON integer that float() cannot hold (OverflowError,
    # not ValueError), so it must be refused as a RuleError, never escape.
    [-0.1, 1.5, True, "0.5", float("nan"), float("inf"), float("-inf"),
     pytest.param(10**1000, id="10**1000"), pytest.param(-(10**1000), id="-10**1000")],
)
def test_prediction_inputs_must_be_unit_interval_numbers(bad):
    with pytest.raises(NoteError, match=r"\[0, 1\]"):
        encode(make_event(expected=bad, actual=0.0))
    with pytest.raises(RuleError, match=r"\[0, 1\]"):
        rules.prediction_error(0.0, bad)


def test_integer_and_float_inputs_encode_identically():
    # 1 and 1.0 are the same prior; storing them differently would give the
    # same episode two ids.
    assert encode(make_event(expected=1, actual=0)) == encode(make_event(expected=1.0, actual=0.0))


# --- Zeigarnik ----------------------------------------------------------------


@pytest.mark.parametrize("status", sorted(set(rules.ZEIGARNIK) - {"completed"}))
def test_unfinished_business_outranks_completed_clean(status):
    assert score(status=status) > score(status="completed")


@pytest.mark.parametrize("status", sorted(set(rules.ZEIGARNIK) - {"completed"}))
def test_unfinished_outranks_even_a_mildly_surprising_clean_finish(status):
    # Zeigarnik alone beats a completed run with a moderate surprise.
    assert score(status=status) > score(status="completed", expected=0.6, actual=1.0)


def test_negative_control_completed_clean_adds_nothing():
    assert rules.ZEIGARNIK["completed"] == 0
    assert score(status="completed", signals=["escalation"]) == rules.CONSEQUENCE["escalation"]


def test_unknown_status_is_refused():
    with pytest.raises(NoteError, match="unknown status"):
        encode(make_event(status="done"))
    with pytest.raises(NoteError, match="status must be a string"):
        encode(make_event(status=["failed"]))


# --- consequence signals ------------------------------------------------------


@pytest.mark.parametrize("signal", sorted(rules.CONSEQUENCE))
def test_each_consequence_signal_adds_its_weight(signal):
    assert score(signals=[signal]) == rules.CONSEQUENCE[signal]


def test_negative_control_unknown_or_duplicated_signals_are_refused():
    with pytest.raises(NoteError, match="unknown consequence signal"):
        encode(make_event(signals=["reprinted"]))
    with pytest.raises(NoteError, match="duplicate"):
        encode(make_event(signals=["escalation", "escalation"]))


def test_signal_order_does_not_change_the_note():
    a = encode(make_event(signals=["escalation", "fuse-strong-warn"]))
    b = encode(make_event(signals=["fuse-strong-warn", "escalation"]))
    assert a == b


# --- the whole formula --------------------------------------------------------


def test_score_is_clamped_to_the_maximum():
    s = score(status="failed", expected=1.0, actual=0.0, signals=sorted(rules.CONSEQUENCE))
    assert s == rules.IMPORTANCE_MAX


# Golden pins: the initial tuning. Changing a constant must change one of
# these lines in the same diff.
@pytest.mark.parametrize(
    "over, expected",
    [
        ({}, 0),
        ({"expected": 0.9, "actual": 0.0}, 54),
        ({"status": "failed"}, 40),
        ({"status": "parked"}, 35),
        ({"status": "withdrawn", "signals": ["escalation"]}, 50),
        ({"signals": ["field-test-failure", "resolved-after-retries"]}, 35),
        ({"status": "incomplete", "expected": 0.75, "actual": 0.0}, 85),
        ({"status": "failed", "expected": 0.9, "actual": 0.0, "signals": ["fuse-strong-warn"]}, 100),
    ],
)
def test_golden_scores(over, expected):
    assert score(**over) == expected


def test_rounding_is_half_up_never_bankers():
    # 60 * 0.375 = 22.5 exactly (0.375 is a binary fraction): half-up gives
    # 23 where Python's round() — banker's — gives 22.
    assert round(rules.PE_WEIGHT * 0.375) == 22  # the trap, demonstrated
    assert rules.importance("completed", 0.0, 0.375, []) == 23


def test_rules_module_refuses_directly_too():
    with pytest.raises(RuleError):
        rules.importance("completed", None, 0.5, [])


def test_negative_control_a_caller_can_never_supply_importance():
    with pytest.raises(NoteError, match="derived at write time"):
        encode(make_event(importance=99))
