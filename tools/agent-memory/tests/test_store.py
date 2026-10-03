"""The store as a committed artifact (#429 AC: diffable records, runs read-cold).

Also the schema's strictness (fail-loud on unknown/missing/malformed fields)
and the determinism the content id rests on: the same episode must hash the
same on every machine, whatever the input's key order, line endings or
Unicode composition.
"""

from __future__ import annotations

import json
import unicodedata

import pytest

from agent_memory import NoteError, canonical_bytes, content_id, encode, load, parse_note, record
from agent_memory.note import EVENT_DERIVED, EVENT_REQUIRED
from conftest import BASE_EVENT, DROP, make_event

# --- diffable artifact ----------------------------------------------------------


def test_note_file_is_pretty_sorted_utf8_with_a_trailing_newline(store):
    rec = record(store, make_event(status="failed", detail="Flexure welded — the chamber was 0.2 mm short"))
    data = rec.path.read_bytes()
    assert data.endswith(b"}\n")
    text = data.decode("utf-8")
    assert "\n  \"action\": " in text           # one field per line: a per-field diff
    assert "welded — the" in text               # non-ASCII kept readable, not \u-escaped
    keys = [line.split('"')[1] for line in text.splitlines() if line.startswith('  "')]
    assert keys == sorted(keys)
    assert data == canonical_bytes(json.loads(data))


def test_two_agents_and_two_episodes_never_share_a_file(store):
    # The Slice 0 concurrency property: overlapping writers touch disjoint
    # paths, so git merges their commits with nothing to conflict on.
    a = record(store, make_event())
    b = record(store, make_event(run_id="2"))
    c = record(store, make_event(agent="chunker"))
    assert len({a.path, b.path, c.path}) == 3
    assert a.path.parent == b.path.parent == store / "design-run"
    assert c.path.parent == store / "chunker"


# --- read-cold --------------------------------------------------------------------


def test_load_reads_cold_oldest_first(store):
    late = record(store, make_event(run_id="2", ts="2026-09-01T00:00:00Z"))
    early = record(store, make_event(run_id="1", ts="2026-08-01T00:00:00Z"))
    notes = load(store, "design-run")
    assert [n["id"] for n in notes] == [early.note["id"], late.note["id"]]
    assert notes[0] == early.note


def test_load_of_an_absent_store_or_agent_is_empty(store):
    assert load(store, "design-run") == []
    record(store, make_event(agent="chunker"))
    assert load(store, "design-run") == []


def test_negative_control_load_fails_loud_on_a_corrupt_note(store):
    rec = record(store, make_event())
    rec.path.write_bytes(b"{ not json")
    with pytest.raises(NoteError, match="not valid UTF-8 JSON"):
        load(store, "design-run")


# --- determinism ------------------------------------------------------------------


def test_same_event_same_bytes_whatever_the_input_order():
    shuffled = dict(reversed(list(make_event(tags=["b", "a"]).items())))
    assert canonical_bytes(encode(shuffled)) == canonical_bytes(encode(make_event(tags=["a", "b"])))


def test_text_is_normalized_before_hashing():
    nfd = unicodedata.normalize("NFD", "café run")
    a = encode(make_event(status="failed", outcome="line one\r\nline two  ", action=nfd))
    b = encode(make_event(status="failed", outcome="line one\nline two", action="café run"))
    assert a["id"] == b["id"]


def test_tags_are_case_folded_deduplicated_and_sorted():
    n = encode(make_event(status="failed", tags=["PETG", "petg", " nuggs "]))
    assert n["tags"] == ["nuggs", "petg"]


def test_different_episodes_get_different_ids():
    ids = {encode(make_event(run_id=str(i)))["id"] for i in range(20)}
    assert len(ids) == 20


def test_retrieval_strength_is_outside_the_id_but_pinned_in_slice_1a():
    n = encode(make_event())
    assert n["retrieval_strength"] == 1.0
    assert content_id({**n, "retrieval_strength": 0.25}) == n["id"]  # 1c may evolve it ...
    with pytest.raises(NoteError, match="retrieval_strength"):           # ... 1a never does
        parse_note({**json.loads(canonical_bytes(n)), "retrieval_strength": 0.25})


def test_parse_note_accepts_what_encode_produces():
    for over in ({}, {"status": "failed", "detail": "d"}, {"author": "human", "model": DROP}):
        n = encode(make_event(**over))
        assert parse_note(json.loads(canonical_bytes(n))) == n


# --- strict, fail-loud schema -----------------------------------------------------


@pytest.mark.parametrize("field", sorted(EVENT_REQUIRED))
def test_every_required_field_is_required(field):
    with pytest.raises(NoteError, match="missing event field"):
        encode(make_event(**{field: DROP}))


@pytest.mark.parametrize("field", sorted(EVENT_DERIVED))
def test_every_derived_field_is_refused_from_the_caller(field):
    with pytest.raises(NoteError, match="derived at write time"):
        encode(make_event(**{field: 1}))


def test_unknown_fields_are_refused():
    with pytest.raises(NoteError, match="unknown event field"):
        encode(make_event(note="free text"))


def test_an_episode_names_an_issue_or_a_design():
    assert encode(make_event(design=DROP))["design"] is None
    assert encode(make_event(issue=DROP))["issue"] is None
    with pytest.raises(NoteError, match="at least one"):
        encode(make_event(issue=DROP, design=DROP))


@pytest.mark.parametrize(
    "over, match",
    [
        ({"agent": "Design Run"}, "agent"),
        ({"ts": "2026-08-30 16:00:00"}, "UTC ISO-8601"),
        ({"ts": "2026-02-30T16:00:00Z"}, "real instant"),
        ({"run_id": "run id"}, "run_id"),
        ({"issue": 0}, "positive integer"),
        ({"issue": True}, "positive integer"),
        ({"design": "Not_Kebab"}, "design"),
        ({"action": ""}, "empty"),
        ({"action": "   "}, "empty"),
        ({"outcome": 42}, "string"),
        ({"choice": "a\x00b"}, "control character"),
        ({"detail": "x" * 9000, "status": "failed"}, "limit"),
        ({"tags": ["has space"]}, "tag"),
        ({"tags": "nuggs"}, "list"),
        ({"links": ["not-an-id"]}, "note id"),
        ({"model": "glm 5"}, "model"),
    ],
)
def test_malformed_fields_are_refused(over, match):
    with pytest.raises(NoteError, match=match):
        encode(make_event(**over))


def test_an_event_must_be_an_object():
    with pytest.raises(NoteError, match="JSON object"):
        encode(["not", "an", "object"])


def test_base_event_fixture_is_valid():
    # Guards every test above: a broken fixture would make every refusal
    # test pass for the wrong reason.
    assert encode(dict(BASE_EVENT))["depth"] == "gist"
