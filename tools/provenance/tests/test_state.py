"""state — state@1 model.

Owner: H1. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e, the critique round's items);
replace the skip with the test.
"""

from __future__ import annotations

import json

import pytest

from conftest import needs

from provenance import contract, state

VERSIONS = {"contract": 1, "digest": "body-digest@1", "harvester": "provenance 0.1.0", "step_grammar": 1}


def _populated():
    s = state.empty_state(VERSIONS)
    s["cursors"]["receipts"]["design-run.yml"] = "2026-10-13T06:13:35Z"
    s["cursors"]["prs_updated"] = "2026-10-12T00:00:00Z"
    state.set_pending(s, "pr", "636", closed_at="2026-10-12T00:00:00Z", due_at="2026-10-12T06:00:00Z",
                      defer_until="2026-10-13T00:00:00Z", reasons=["settle-deferred", "settle-deferred", "a"])
    state.set_pending(s, "brief", "592", closed_at=None, due_at="2026-10-12T06:00:00Z",
                      defer_until="2026-10-13T00:00:00Z", reasons=[])
    state.set_skipped(s, 700, "2026-10-11T00:00:00Z")
    s["ingested"]["pr843"] = {"commit": "4" * 40, "manifest_sha256": "c" * 64, "receipts": 3, "runs_listings": 1,
                              "snapshot_end": "2026-10-13T06:13:35Z", "statuses": 2, "version": 1}
    return s


def test_round_trip_is_byte_stable():
    """load_state(dump_state(s)) == s and dumping twice gives identical bytes; no wall-clock field exists; there is no 'frozen' key (critique 28)."""
    s = _populated()
    data = state.dump_state(s)
    assert state.load_state(data, VERSIONS) == s
    assert state.dump_state(state.load_state(data, VERSIONS)) == data == state.dump_state(s)
    assert "frozen" not in s and set(s) == {"format", "versions", "cursors", "pending", "skipped", "ingested"}
    assert state.load_state(None, VERSIONS) == state.empty_state(VERSIONS)
    # A new harvester version is recorded, never a reason to discard cursors.
    newer = dict(VERSIONS, harvester="provenance 0.2.0")
    reloaded = state.load_state(data, newer)
    assert reloaded["versions"] == newer and reloaded["cursors"] == s["cursors"]
    assert state.dump_state(reloaded) != data
    with pytest.raises(ValueError):
        state.load_state(json.dumps({"format": "state@2"}).encode(), VERSIONS)
    assert s["pending"]["pr"]["636"]["reasons"] == ["a", "settle-deferred"]  # sorted, unique (contract)


@needs(contract.validate)
def test_state_validates_against_the_contract():
    assert contract.validate("state@1", _populated()) == []
    assert contract.validate("state@1", state.empty_state(VERSIONS)) == []
    assert contract.validate("state@1", dict(_populated(), frozen={})) != []


def test_frozen_from_paths():
    """frozen_from_paths over raw/pr/636.json.gz, raw/pr/636.r2.json.gz, raw/brief/592.json.gz, raw/release/v2.0.json.gz → {'pr': {'636': 2}, 'brief': {'592': 1}, 'release': {'v2.0': 1}}; next_revision → 3 / 2 / 1 for an unseen key; receipts/ and raw/snapshot/ paths are ignored."""
    paths = ["raw/pr/636.json.gz", "raw/pr/636.r2.json.gz", "raw/brief/592.json.gz", "raw/release/v2.0.json.gz",
             "receipts/2026/10/12/1.a1.json.gz", "raw/snapshot/pr843/runs/ci.yml.json.gz",
             "raw/snapshot/pr843/statuses/" + "a" * 40 + ".json.gz", "raw/pr/x.json.gz", "raw/pr/7.r1.json.gz",
             "state.json"]
    frozen = state.frozen_from_paths(paths)
    assert frozen == {"pr": {"636": 2}, "brief": {"592": 1}, "release": {"v2.0": 1}}
    assert state.frozen_from_paths(reversed(paths)) == frozen               # order-free
    assert state.next_revision(frozen, "pr", "636") == 3
    assert state.next_revision(frozen, "brief", "592") == 2
    assert state.next_revision(frozen, "pr", "1") == 1
    assert state.next_revision(frozen, "release", "v2.1") == 1
    assert state.frozen_from_paths(["raw/pr/5.r12.json.gz", "raw/pr/5.r3.json.gz"]) == \
        {"pr": {"5": 12}, "brief": {}, "release": {}}


def test_pending_skipped_clear():
    """set_pending then clear_pending removes the entry; set_skipped records {closed_at} per PR."""
    s = state.empty_state(VERSIONS)
    state.set_pending(s, "pr", "636", closed_at="2026-10-12T00:00:00Z", due_at="2026-10-12T06:00:00Z",
                      defer_until="2026-10-13T00:00:00Z", reasons=["b", "a"])
    assert s["pending"]["pr"] == {"636": {"closed_at": "2026-10-12T00:00:00Z", "defer_until": "2026-10-13T00:00:00Z",
                                          "due_at": "2026-10-12T06:00:00Z", "reasons": ["a", "b"]}}
    state.clear_pending(s, "pr", "636")
    assert s["pending"]["pr"] == {}
    state.clear_pending(s, "pr", "636")  # idempotent
    state.set_skipped(s, 700, "2026-10-11T00:00:00Z")
    state.set_skipped(s, 700, "2026-10-11T05:00:00Z")  # a later close replaces it
    assert s["skipped"]["pr"] == {"700": {"closed_at": "2026-10-11T05:00:00Z"}}
    with pytest.raises(ValueError):
        state.set_pending(s, "release", "v1", closed_at=None, due_at="x", defer_until="y", reasons=[])


def test_oldest_overdue():
    """oldest_overdue picks the unit furthest past due_at + grace (Reeve's provenance-lag mirrors it)."""
    s = state.empty_state(VERSIONS)
    now = "2026-10-12T12:00:00Z"
    assert state.oldest_overdue(s, now, 3) is None
    for key, due in (("1", "2026-10-12T08:00:00Z"), ("2", "2026-10-12T02:00:00Z"), ("3", "2026-10-12T11:00:00Z")):
        state.set_pending(s, "pr", key, closed_at="2026-10-11T00:00:00Z", due_at=due,
                          defer_until="2026-10-13T00:00:00Z", reasons=[])
    state.set_pending(s, "brief", "9", closed_at=None, due_at="2026-10-12T05:00:00Z",
                      defer_until="2026-10-13T00:00:00Z", reasons=[])
    got = state.oldest_overdue(s, now, 3)
    assert (got["kind"], got["key"], got["overdue_seconds"]) == ("pr", "2", 7 * 3600)
    assert got["due_at"] == "2026-10-12T02:00:00Z"
    assert state.oldest_overdue(s, now, 10) is None       # nothing past due + 10 h
    # A tie breaks on kind order (pr before brief), then the smaller number.
    t = state.empty_state(VERSIONS)
    for kind, key in (("brief", "1"), ("pr", "9"), ("pr", "5")):
        state.set_pending(t, kind, key, closed_at=None, due_at="2026-10-12T00:00:00Z",
                          defer_until="2026-10-13T00:00:00Z", reasons=[])
    assert state.oldest_overdue(t, now, 0)["key"] == "5"
