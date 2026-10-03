"""Rule 4 — immutable, append-only episodes (#429 AC: no destructive edit).

#426 rejected reconsolidation: a memory is never rewritten; new learning is a
new note *linked* to the old one. The store enforces it three ways, each
with its negative control here:

* the write path is create-only — re-recording the same episode is an
  idempotent no-op, and a write that would change committed bytes refuses;
* the package has no update or delete surface at all;
* ``check`` re-derives every note from its own inputs, so an edit made
  outside the write path (by hand, by a script) is caught on the next run.
"""

from __future__ import annotations

import json

import pytest

import agent_memory
from agent_memory import (ImmutableNoteError, NoteError, check, content_id, encode, load,
                          record)
from agent_memory.store import note_path
from conftest import make_event


def test_record_creates_one_file_named_by_its_content_hash(store):
    rec = record(store, make_event())
    assert rec.created
    assert rec.path == store / "design-run" / f"{rec.note['id']}.json"
    assert rec.note["id"] == content_id(rec.note)
    assert [p.name for p in (store / "design-run").iterdir()] == [rec.path.name]


def test_re_recording_the_same_episode_is_an_idempotent_no_op(store):
    first = record(store, make_event())
    before = first.path.read_bytes()
    again = record(store, make_event())
    assert not again.created
    assert again.path == first.path
    assert first.path.read_bytes() == before
    assert len(list((store / "design-run").iterdir())) == 1


def test_negative_control_an_overwrite_with_different_bytes_is_refused(store):
    rec = record(store, make_event())
    tampered = rec.path.read_bytes().replace(b"gate green", b"gate red")
    rec.path.write_bytes(tampered)
    with pytest.raises(ImmutableNoteError, match="immutable"):
        record(store, make_event())
    assert rec.path.read_bytes() == tampered  # the refusal touched nothing


def test_a_correction_is_a_new_linked_note_and_the_original_is_untouched(store):
    original = record(store, make_event())
    before = original.path.read_bytes()
    fix = record(store, make_event(run_id="17000000002", outcome="re-run: gate red after all",
                                   status="failed", links=[original.note["id"]]))
    assert fix.created and fix.path != original.path
    assert fix.note["links"] == [original.note["id"]]
    assert original.path.read_bytes() == before
    assert {n["id"] for n in load(store, "design-run")} == {original.note["id"], fix.note["id"]}


def test_negative_control_a_link_must_name_an_existing_note_of_the_same_agent(store):
    other = record(store, make_event(agent="chunker"))
    with pytest.raises(NoteError, match="resolves to no note"):
        record(store, make_event(links=["0" * 64]))
    with pytest.raises(NoteError, match="resolves to no note in design-run"):
        record(store, make_event(links=[other.note["id"]]))  # memory is per-agent


def test_the_package_exposes_no_update_or_delete_surface():
    words = ("update", "delete", "remove", "edit", "rewrite", "overwrite", "unlink")
    surface = [n for n in dir(agent_memory) if not n.startswith("_")]
    surface += [n for n in dir(agent_memory.store) if not n.startswith("_")]
    assert not [n for n in surface if any(w in n.lower() for w in words)]


# --- check catches edits made outside the write path ---------------------------


def _rewrite(path, mutate):
    obj = json.loads(path.read_bytes())
    mutate(obj)
    path.write_bytes((json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode())


def test_check_passes_a_clean_store(store):
    record(store, make_event())
    record(store, make_event(run_id="2", status="failed"))
    assert check(store) == ([], 2)


@pytest.mark.parametrize(
    "mutate, match",
    [
        (lambda o: o.update(outcome="gate red"), "not the content hash"),
        (lambda o: o["salience"].update(status="failed"), "importance"),
        (lambda o: o.update(tags=["rewritten"]), "not the content hash"),
        (lambda o: o.update(retrieval_strength=0.5), "retrieval_strength"),
        (lambda o: o.update(schema=2), "unknown note shape"),
        (lambda o: o.update(extra="field"), "extra"),
    ],
)
def test_negative_control_check_flags_a_hand_edit(store, mutate, match):
    rec = record(store, make_event())
    _rewrite(rec.path, mutate)
    problems, count = check(store)
    assert count == 0
    assert len(problems) == 1 and match in problems[0], problems


def test_negative_control_check_flags_a_reformatted_note(store):
    rec = record(store, make_event())
    obj = json.loads(rec.path.read_bytes())
    rec.path.write_bytes(json.dumps(obj, sort_keys=True).encode())  # minified, no newline
    problems, _ = check(store)
    assert any("canonical serialization" in p for p in problems)


def test_negative_control_check_flags_a_renamed_or_misfiled_note(store):
    rec = record(store, make_event())
    renamed = rec.path.with_name("f" * 64 + ".json")
    rec.path.rename(renamed)
    assert any("file name does not match" in p for p in check(store)[0])
    misfiled = store / "chunker" / renamed.name
    misfiled.parent.mkdir()
    renamed.rename(misfiled)
    assert any("belongs to agent 'design-run'" in p for p in check(store)[0])


def test_negative_control_check_flags_stray_files(store):
    record(store, make_event())
    (store / "design-run" / "notes.txt").write_text("scratch")
    (store / "README").write_text("not an agent dir")
    (store / "Bad_Agent").mkdir()
    problems, count = check(store)
    assert count == 1
    assert any("notes.txt" in p for p in problems)
    assert any("README" in p for p in problems)
    assert any("Bad_Agent" in p for p in problems)
    with pytest.raises(NoteError, match="not a note file name"):
        load(store, "design-run")


def test_negative_control_check_and_load_flag_a_dangling_link(store):
    # Deleting a note another links to is the destructive edit a link exposes.
    rec = record(store, make_event())
    fix = record(store, make_event(run_id="2", links=[rec.note["id"]]))
    rec.path.unlink()
    assert any(f"link {rec.note['id']}" in p for p in check(store)[0])
    with pytest.raises(NoteError, match="resolves to no note"):
        load(store, "design-run")
    assert fix.path.exists()


def test_note_path_is_confined_to_the_agent_directory(store):
    with pytest.raises(NoteError, match="agent"):
        encode(make_event(agent="../escape"))
    with pytest.raises(NoteError, match="agent"):
        load(store, "../escape")
    assert note_path(store, "design-run", "a" * 64).parent == store / "design-run"
