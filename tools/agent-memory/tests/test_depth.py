"""Rule 2 — salience-proportional encoding depth (#429 AC: depth-by-salience).

Salient (importance >= RICH_THRESHOLD) -> a **rich** note: full text, detail,
every tag. Routine -> a **gist** note: one line per field, no detail, at most
GIST_MAX_TAGS tags. Depth is derived, never supplied, and a stored note whose
depth disagrees with its salience is refused on read.
"""

from __future__ import annotations

import json

import pytest

from agent_memory import NoteError, canonical_bytes, check, encode, parse_note, record, rules
from conftest import make_event

LONG = "x" * (rules.GIST_LINE_MAX + 40)
TAGS = ["nuggs", "petg", "print-in-place", "threads"]


def test_salient_event_is_encoded_rich_and_keeps_everything():
    n = encode(make_event(status="failed", detail="what changed, why, and how it ended",
                          action="line one\nline two", tags=TAGS))
    assert n["depth"] == "rich"
    assert n["detail"] == "what changed, why, and how it ended"
    assert n["action"] == "line one\nline two"
    assert n["tags"] == sorted(TAGS)


def test_routine_event_is_encoded_as_a_thin_gist():
    n = encode(make_event(detail="the full story nobody needs for a green run",
                          action="line one\nline two", outcome=LONG, tags=TAGS))
    assert n["depth"] == "gist"
    assert n["detail"] is None                       # detail dropped
    assert n["action"] == "line one"                 # first line only
    assert len(n["outcome"]) == rules.GIST_LINE_MAX  # clipped ...
    assert n["outcome"].endswith(rules.GIST_ELLIPSIS)  # ... visibly
    assert len(n["tags"]) == rules.GIST_MAX_TAGS     # "a couple tags"


def test_negative_control_a_routine_event_is_never_rich():
    # Same text and tags as the rich case above, but completed-clean: the
    # detail and the extra tags must NOT survive.
    n = encode(make_event(detail="what changed, why, and how it ended", tags=TAGS))
    assert n["depth"] == "gist"
    assert n["detail"] is None
    assert len(n["tags"]) < len(TAGS)


def test_gist_keeps_links_and_sources():
    # Structure and trust are not detail: a gist correction keeps its link, a
    # gist note keeps the source that confirms it.
    target = encode(make_event(run_id="1"))["id"]
    n = encode(make_event(run_id="2", links=[target],
                          sources=[{"kind": "gate", "ref": "gate.sh czs-slider"}]))
    assert n["depth"] == "gist"
    assert n["links"] == [target]
    assert n["provenance"]["sources"] == [{"kind": "gate", "ref": "gate.sh czs-slider"}]


def test_threshold_boundary():
    # parked scores exactly RICH_THRESHOLD; one point of surprise below it is gist.
    assert rules.ZEIGARNIK["parked"] == rules.RICH_THRESHOLD
    assert encode(make_event(status="parked"))["depth"] == "rich"
    below = (rules.RICH_THRESHOLD - 1) / rules.PE_WEIGHT
    n = encode(make_event(expected=0.0, actual=below))
    assert n["importance"] == rules.RICH_THRESHOLD - 1
    assert n["depth"] == "gist"


def test_short_gist_text_is_left_alone():
    n = encode(make_event(action="short"))
    assert n["action"] == "short"


def test_gist_clipping_is_idempotent():
    once = rules.gist_line(LONG + "\nsecond")
    assert rules.gist_line(once) == once


def test_negative_control_a_caller_can_never_set_depth():
    with pytest.raises(NoteError, match="derived at write time"):
        encode(make_event(depth="rich"))


def _edited(note: dict, **fields) -> dict:
    obj = json.loads(canonical_bytes(note))
    obj.update(fields)
    return obj


def test_negative_control_a_gist_note_promoted_by_hand_is_refused():
    gist = encode(make_event(detail="kept?"))
    with pytest.raises(NoteError, match="depth 'rich' does not match"):
        parse_note(_edited(gist, depth="rich"))
    with pytest.raises(NoteError, match="gist note carries no detail"):
        parse_note(_edited(gist, detail="smuggled back in"))
    with pytest.raises(NoteError, match="importance 90 does not match"):
        parse_note(_edited(gist, importance=90, depth="rich"))


def test_check_flags_a_promoted_note_in_the_store(store):
    rec = record(store, make_event())
    obj = json.loads(rec.path.read_bytes())
    obj["depth"] = "rich"
    rec.path.write_bytes((json.dumps(obj, sort_keys=True, indent=2) + "\n").encode())
    problems, _ = check(store)
    assert any("depth" in p for p in problems)
