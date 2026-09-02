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
    r = simulate("0 9 * * *", 1, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 3, 1)
    assert [s["number"] for s in r["slots"]] == [11, 10, 12]
    assert r["slots"][0]["at"] == "2026-08-29T09:00:00Z"
    assert r["slots"][0]["thread"] == ["Because sound leaks state."]


def test_window_shorter_than_queue_leaves_items_queued():
    r = simulate("0 9 * * *", 1, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 2, 1)
    assert len(r["slots"]) == 2
    assert [u["number"] for u in r["unscheduled"]] == [12]


def test_max_posts_per_run_drains_faster():
    # A per-run cap of 2 drains two items in one firing — but the per-DAY cap
    # bounds the day's total, so raise it to 2 as well to exercise the per-run
    # cap alone (with a per-day cap of 1, only one would post).
    r = simulate("0 9 * * *", 2, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 1, 2)
    assert [s["number"] for s in r["slots"]] == [11, 10]
    assert {s["at"] for s in r["slots"]} == {"2026-08-29T09:00:00Z"}


def test_per_day_cap_bounds_a_high_per_run_cap():
    # The per-day cap is the outer bound: even a per-run cap of 5 posts only
    # `max_posts_per_day` in a day (the negative control for the test above).
    r = simulate("0 9 * * *", 5, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 1, 1)
    assert [s["number"] for s in r["slots"]] == [11]  # one firing, capped at 1/day


def test_uncomposed_item_is_skipped_and_reported_never_invented():
    posts = _posts()
    del posts["12"]
    r = simulate("0 9 * * *", 1, _snapshot(), posts, "2026-08-29T00:00:00Z", 5, 1)
    assert [s["number"] for s in r["slots"]] == [11, 10]
    assert r["skipped"] == [{"number": 12, "title": "Growth post: orrery",
                             "reason": "no composed post"}]


def test_over_limit_copy_fails_the_simulation_loudly():
    posts = _posts()
    posts["10"] = {"text": "x" * 281}
    with pytest.raises(SimulationError, match="over the weighted"):
        simulate("0 9 * * *", 1, _snapshot(), posts, "2026-08-29T00:00:00Z", 3, 1)


def test_over_limit_thread_part_also_fails():
    posts = _posts()
    posts["11"] = {"text": "ok", "thread": ["y" * 281]}
    with pytest.raises(SimulationError, match="over the weighted"):
        simulate("0 9 * * *", 1, _snapshot(), posts, "2026-08-29T00:00:00Z", 3, 1)


def test_bad_start_fails():
    with pytest.raises(SimulationError, match="--start"):
        simulate("0 9 * * *", 1, [], {}, "yesterday-ish", 3, 1)


def test_markdown_carries_every_slot_and_the_leftovers():
    r = simulate("0 9 * * *", 1, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 2, 1)
    md = render_markdown(r, "0 9 * * *", 1, "2026-08-29T00:00:00Z", 2)
    assert "queue item #11" in md and "queue item #10" in md
    assert "Still queued after the window" in md and "#12" in md
    assert "2/**" in md  # the thread part renders numbered


def test_ndjson_one_line_per_slot():
    r = simulate("0 9 * * *", 1, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 3, 1)
    lines = render_ndjson(r).strip().splitlines()
    assert len(lines) == 3
    assert all('"mode": "dry-run"' in line for line in lines)


def test_multi_slot_cadence_posts_once_per_utc_day():
    # A multi-slot cadence fires several times a day (delivery redundancy), but
    # the live drain holds once the day's cap is met (the per-day guard). With
    # a cap of 1 that is one post/day, at each day's FIRST firing — the dry-run
    # timeline shows the real cadence, not a post at every firing.
    cadence = "19 13-21/2 * * *"
    r = simulate(cadence, 1, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 3, 1)  # per-day cap = 1
    assert [s["number"] for s in r["slots"]] == [11, 10, 12]
    days = [s["at"][:10] for s in r["slots"]]
    assert days == ["2026-08-29", "2026-08-30", "2026-08-31"]  # one post each day
    # Each day's post lands on that day's FIRST firing (13:19), deterministically.
    assert all(s["at"][11:16] == "13:19" for s in r["slots"])


def test_daily_cap_of_two_places_two_posts_on_a_day():
    # With max_posts_per_day=2 (the shipped default), two of a day's firings
    # post — the first two nominal slots (13:19, 15:19) — mirroring daycap
    # holding at the cap rather than after the first post.
    cadence = "19 13-21/2 * * *"
    r = simulate(cadence, 1, _snapshot(), _posts(), "2026-08-29T00:00:00Z", 3, 2)
    assert [s["number"] for s in r["slots"]] == [11, 10, 12]
    times = [(s["at"][:10], s["at"][11:16]) for s in r["slots"]]
    assert times == [("2026-08-29", "13:19"), ("2026-08-29", "15:19"),
                     ("2026-08-30", "13:19")]  # 2 on day one, the third on day two
