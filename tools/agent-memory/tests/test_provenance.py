"""Rule 3 — provenance tagging (#429 AC: source-confirmed vs model-asserted).

A note is ``source-confirmed`` only when it cites a source of truth (a gate
result, a field test, a render, a CI run); otherwise it is ``model-asserted``.
The class is derived from the cited sources and never accepted from the
caller — the false-memory defense #426 names: untrusted text can seed an
asserted memory, never a verified one.
"""

from __future__ import annotations

import json

import pytest

from agent_memory import NoteError, canonical_bytes, check, encode, parse_note, record, rules
from conftest import DROP, make_event

GATE = {"kind": "gate", "ref": "gate.sh --slice czs-slider, run 17000000001"}


def test_a_cited_source_confirms_the_note():
    n = encode(make_event(sources=[GATE]))
    assert n["provenance"]["verified"] == rules.VERIFIED_CONFIRMED
    assert n["provenance"]["sources"] == [GATE]


@pytest.mark.parametrize("kind", rules.SOURCE_KINDS)
def test_every_source_kind_confirms(kind):
    n = encode(make_event(sources=[{"kind": kind, "ref": "evidence"}]))
    assert n["provenance"]["verified"] == rules.VERIFIED_CONFIRMED


def test_negative_control_no_source_means_model_asserted():
    assert encode(make_event())["provenance"]["verified"] == rules.VERIFIED_ASSERTED
    assert encode(make_event(sources=[]))["provenance"]["verified"] == rules.VERIFIED_ASSERTED


def test_negative_control_a_human_without_a_source_is_still_unconfirmed():
    # Authorship is recorded separately; confirmation needs a source either way.
    n = encode(make_event(author="human", model=DROP))
    assert n["provenance"] == {"author": "human", "model": None,
                               "verified": rules.VERIFIED_ASSERTED, "sources": []}


@pytest.mark.parametrize("field", ["verified", "provenance"])
def test_negative_control_a_caller_cannot_self_certify(field):
    value = rules.VERIFIED_CONFIRMED if field == "verified" else {"verified": rules.VERIFIED_CONFIRMED}
    with pytest.raises(NoteError, match="derived at write time"):
        encode(make_event(**{field: value}))


def test_agent_notes_name_their_model_and_human_notes_do_not():
    with pytest.raises(NoteError, match="names the model"):
        encode(make_event(model=DROP))
    with pytest.raises(NoteError, match="carries no model"):
        encode(make_event(author="human"))
    with pytest.raises(NoteError, match="author"):
        encode(make_event(author="bot"))


@pytest.mark.parametrize(
    "bad, match",
    [
        ({"kind": "issue-comment", "ref": "#440"}, "source kind"),   # untrusted text is no source
        ({"kind": "gate"}, "exactly"),
        ({"kind": "gate", "ref": "a\nb"}, "single line"),
        ({"kind": "gate", "ref": ""}, "empty"),
        ("gate.sh", "exactly"),
    ],
)
def test_malformed_sources_are_refused(bad, match):
    with pytest.raises(NoteError, match=match):
        encode(make_event(sources=[bad]))


def test_sources_are_sorted_and_deduplicated():
    ci = {"kind": "ci", "ref": "run 9"}
    n = encode(make_event(sources=[GATE, ci, GATE]))
    assert n["provenance"]["sources"] == [ci, GATE]


def test_negative_control_a_hand_flipped_verified_is_refused_on_read():
    n = encode(make_event())
    obj = json.loads(canonical_bytes(n))
    obj["provenance"]["verified"] = rules.VERIFIED_CONFIRMED
    with pytest.raises(NoteError, match="only a cited source confirms"):
        parse_note(obj)


def test_check_flags_a_self_certified_note_in_the_store(store):
    rec = record(store, make_event())
    obj = json.loads(rec.path.read_bytes())
    obj["provenance"]["verified"] = rules.VERIFIED_CONFIRMED
    rec.path.write_bytes((json.dumps(obj, sort_keys=True, indent=2) + "\n").encode())
    problems, _ = check(store)
    assert any("only a cited source confirms" in p for p in problems)
