"""Post-time jitter: the per-date chosen slot, and the ≤1/day invariant.

A positive case and a negative control per rule, plus the two properties the
whole feature rests on: the choice is deterministic per UTC date, and exactly
one candidate hour is the post slot on any given day (so a multi-slot cadence
still posts at most once a day).
"""

from datetime import datetime

import pytest

from growth import postslot


# ---- candidate_hours: the cron hour field, expanded --------------------------

def test_candidate_hours_expands_the_stepped_window():
    assert postslot.candidate_hours("19 13-21/2 * * *") == [13, 15, 17, 19, 21]


def test_candidate_hours_single_hour_is_a_singleton():
    assert postslot.candidate_hours("19 13 * * *") == [13]


def test_candidate_hours_comma_list_sorted():
    assert postslot.candidate_hours("0 9,14,18 * * *") == [9, 14, 18]


# ---- chosen_hour: deterministic per date, walks the window -------------------

def test_chosen_hour_is_deterministic_per_date():
    hours = [13, 15, 17, 19, 21]
    a = postslot.chosen_hour("2026-08-30", hours)
    b = postslot.chosen_hour("2026-08-30", hours)
    assert a == b
    assert a in hours


def test_chosen_hour_varies_across_dates():
    hours = [13, 15, 17, 19, 21]
    picks = {postslot.chosen_hour(f"2026-09-{d:02d}", hours) for d in range(1, 31)}
    # Over a month the choice must actually move around the window, not stick
    # to one hour — the whole point of the jitter.
    assert len(picks) >= 3


def test_chosen_hour_is_roughly_uniform_over_the_window():
    hours = [13, 15, 17, 19, 21]
    counts = {h: 0 for h in hours}
    # A year of dates; a fair pick lands each hour ~73 times. Assert every
    # candidate hour is used and none dominates absurdly — a coarse fairness
    # check, not a statistical test.
    for m in range(1, 13):
        for d in range(1, 29):
            counts[postslot.chosen_hour(f"2026-{m:02d}-{d:02d}", hours)] += 1
    assert all(c > 0 for c in counts.values())
    assert max(counts.values()) < 3 * min(counts.values())


def test_chosen_hour_single_candidate_is_that_hour():
    assert postslot.chosen_hour("2026-08-30", [13]) == 13
    assert postslot.chosen_hour("2199-01-01", [13]) == 13


def test_chosen_hour_empty_candidates_raises():
    with pytest.raises(ValueError, match="no candidate hours"):
        postslot.chosen_hour("2026-08-30", [])


# ---- is_post_slot: the gate the workflow reads ------------------------------

def test_is_post_slot_true_only_at_the_chosen_hour():
    cadence = "19 13-21/2 * * *"
    date = datetime(2026, 8, 30)
    chosen = postslot.chosen_hour("2026-08-30", [13, 15, 17, 19, 21])
    for h in [13, 15, 17, 19, 21]:
        now = date.replace(hour=h, minute=19)
        assert postslot.is_post_slot(now, cadence) is (h == chosen)


def test_is_post_slot_false_for_an_off_schedule_hour():
    # An hour that is not a candidate at all (clock skew, or a hand-run at an
    # off-schedule time) never acts, even if it happens to be a candidate on
    # some other cadence.
    assert postslot.is_post_slot(datetime(2026, 8, 30, 14, 19), "19 13-21/2 * * *") is False
    assert postslot.is_post_slot(datetime(2026, 8, 30, 8, 0), "19 13-21/2 * * *") is False


def test_is_post_slot_single_candidate_always_fires_at_its_hour():
    # The shape every other routine uses, and Lark's own before this feature:
    # is_post_slot is inert — the one hour is always the chosen one.
    for m in range(1, 13):
        assert postslot.is_post_slot(datetime(2026, m, 15, 13), "19 13 * * *") is True


def test_exactly_one_candidate_hour_posts_per_day():
    # The invariant the ≤1/day cap rests on: across a day's candidate firings,
    # exactly one is the post slot — so a multi-slot cadence still posts once.
    cadence = "19 13-21/2 * * *"
    for d in range(1, 31):
        hits = [h for h in [13, 15, 17, 19, 21]
                if postslot.is_post_slot(datetime(2026, 9, d, h, 19), cadence)]
        assert len(hits) == 1
