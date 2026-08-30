"""The accelerated dry run: scheduling, refusal of unpostable copy, rendering."""

import pytest

from growth.simulate import SimulationError, render_markdown, render_ndjson, simulate


def _snapshot():
    return [
        {"number": 10, "title": "Growth post: threads", "labels": []},
        {"number": 11, "title": "Growth post: acoustic", "labels": [{"name": "priority:high"}]},
        {"number": 12, "title": "Growth post: orrery", "labels": []},
    ]


def _posts():
    return {
        "10": {"text": "45° flanks print supportless. https://example.com", "thread": []},
        "11": {"text": "A door that must not rattle.", "thread": ["Because sound leaks state."]},
        "12": {"text": "It can only be printed."},
    }


def test_priority_item_takes_the_first_slot():
    r = simulate("0 9 * * *", 1, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 3)
    assert [s["number"] for s in r["slots"]] == [11, 10, 12]
    assert r["slots"][0]["at"] == "2026-08-29T09:00:00Z"
    assert r["slots"][0]["thread"] == ["Because sound leaks state."]


def test_window_shorter_than_queue_leaves_items_queued():
    r = simulate("0 9 * * *", 1, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 2)
    assert len(r["slots"]) == 2
    assert [u["number"] for u in r["unscheduled"]] == [12]


def test_max_posts_per_run_drains_faster():
    r = simulate("0 9 * * *", 2, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 1)
    assert [s["number"] for s in r["slots"]] == [11, 10]
    assert {s["at"] for s in r["slots"]} == {"2026-08-29T09:00:00Z"}


def test_uncomposed_item_is_skipped_and_reported_never_invented():
    posts = _posts()
    del posts["12"]
    r = simulate("0 9 * * *", 1, _snapshot(), posts, "2026-08-29T00:00:00Z", 5)
    assert [s["number"] for s in r["slots"]] == [11, 10]
    assert r["skipped"] == [{"number": 12, "title": "Growth post: orrery",
                             "reason": "no composed post"}]


def test_over_limit_copy_fails_the_simulation_loudly():
    posts = _posts()
    posts["10"] = {"text": "x" * 281}
    with pytest.raises(SimulationError, match="over the weighted"):
        simulate("0 9 * * *", 1, _snapshot(), posts, "2026-08-29T00:00:00Z", 3)


def test_over_limit_thread_part_also_fails():
    posts = _posts()
    posts["11"] = {"text": "ok", "thread": ["y" * 281]}
    with pytest.raises(SimulationError, match="over the weighted"):
        simulate("0 9 * * *", 1, _snapshot(), posts, "2026-08-29T00:00:00Z", 3)


def test_bad_start_fails():
    with pytest.raises(SimulationError, match="--start"):
        simulate("0 9 * * *", 1, [], {}, "yesterday-ish", 3)


def test_markdown_carries_every_slot_and_the_leftovers():
    r = simulate("0 9 * * *", 1, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 2)
    md = render_markdown(r, "0 9 * * *", 1, "2026-08-29T00:00:00Z", 2)
    assert "queue item #11" in md and "queue item #10" in md
    assert "Still queued after the window" in md and "#12" in md
    assert "2/**" in md  # the thread part renders numbered


def test_ndjson_one_line_per_slot():
    r = simulate("0 9 * * *", 1, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 3)
    lines = render_ndjson(r).strip().splitlines()
    assert len(lines) == 3
    assert all('"mode": "dry-run"' in line for line in lines)


def test_multi_hour_cadence_posts_once_per_day_at_the_chosen_hour():
    # A jittered cadence fires at five candidate hours a day, but the simulator
    # slots exactly one post per day — at that date's chosen hour — so the
    # dry-run timeline shows the real ~1/day cadence at varied times, not a
    # post at every candidate firing.
    cadence = "19 13-21/2 * * *"
    r = simulate(cadence, 1, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 3)
    assert [s["number"] for s in r["slots"]] == [11, 10, 12]
    days = {s["at"][:10] for s in r["slots"]}
    assert days == {"2026-08-29", "2026-08-30", "2026-08-31"}  # one post each day
    hours = {s["at"][11:13] for s in r["slots"]}
    assert hours <= {"13", "15", "17", "19", "21"}  # only ever a candidate hour
