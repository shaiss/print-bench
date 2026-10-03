"""The committed store: one content-hashed JSON file per note, per agent.

Layout (the Slice 0 decision, #428)::

    tools/agent-memory/store/<agent>/<id>.json

``<id>`` is the note's content hash, so the path *is* the content: two routines
recording two different episodes in overlapping windows write two different
paths (git merges added files with no shared line to collide on), and the same
episode recorded twice lands on the same path with the same bytes (an
idempotent write, not a duplicate and not a conflict).

Append-only by construction. There is no update and no delete here — only
``record`` (create-if-absent), ``load`` and ``check``. A write that finds
different bytes already at its path refuses rather than overwrite: with
content-addressed ids that can only mean the file was edited after it was
written, which is exactly what immutable episodes forbid. A correction is a new
note whose ``links`` point at the one it corrects.

The publish is atomic as well as create-only: the bytes are written and fsynced
to a private temp file beside the note, then hard-linked to the note's path —
``os.link`` fails if that path exists, so the existence test and the publish are
still one syscall. A concurrent reader or recorder therefore sees no note or the
whole note, never a partial one, and a crash mid-write can leave at most a stray
temp file (which ``check`` names), never a corrupt note every retry refuses.

This is the only module that reads or writes the store, and it writes only
beneath the store root it is handed. (Two other modules touch the filesystem,
neither of them the store: ``cli`` reads the event file, and ``selftest``
writes inside a throwaway temporary directory. The purity tests hold that
split: only ``store`` and ``selftest`` may write.)
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .note import AGENT_RE, NoteError, canonical_bytes, encode, parse_note

NOTE_FILE_RE = re.compile(r"^([0-9a-f]{64})\.json$")


class ImmutableNoteError(NoteError):
    """A write that would change bytes already committed at a note's path."""


@dataclass(frozen=True)
class Recorded:
    note: dict
    path: Path
    created: bool  # False: the identical note was already there (idempotent)


def note_path(store: Path, agent: str, note_id: str) -> Path:
    return Path(store) / agent / f"{note_id}.json"


def record(store: Path, event: Mapping[str, Any]) -> Recorded:
    """Encode an event and write its note if absent; never overwrite.

    Every link must name a note already in the same agent's store: memory is
    per-agent (#426), and since an id is a content hash a note can only ever
    link *backwards* to something that exists.
    """
    note = encode(event)
    agent = note["agent"]
    for link in note["links"]:
        if not note_path(store, agent, link).is_file():
            raise NoteError(
                f"link {link} resolves to no note in {agent}'s store — "
                "a link points at an existing note of the same agent"
            )
    path = note_path(store, agent, note["id"])
    data = canonical_bytes(note)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write the whole note privately first; only a complete, fsynced file is
    # ever published. (The temp name is random, but it never reaches the
    # store: the note's bytes and path are still pure functions of the event.)
    fd, tmp = tempfile.mkstemp(prefix=f".{note['id']}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            # Create-only publish: link() refuses an existing path, so the
            # existence test and the publish are one syscall and a concurrent
            # writer of the same id cannot be clobbered.
            os.link(tmp, path)
        except FileExistsError:
            if path.read_bytes() == data:
                return Recorded(note=note, path=path, created=False)
            raise ImmutableNoteError(
                f"refusing to overwrite {path}: a note with this id is already committed with "
                "different bytes. Notes are immutable — record a correction as a new note that "
                "links to this one, and run `check` to find the edited file."
            ) from None
    finally:
        os.unlink(tmp)  # the temp only; a published note keeps its own link
    return Recorded(note=note, path=path, created=True)


def _read_note(path: Path, agent: str) -> dict:
    m = NOTE_FILE_RE.match(path.name)
    if not m or not path.is_file():
        raise NoteError(f"{path}: not a note file name (<64-hex id>.json)")
    data = path.read_bytes()
    try:
        obj = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise NoteError(f"{path}: not valid UTF-8 JSON ({e})") from None
    try:
        note = parse_note(obj)
    except NoteError as e:
        raise NoteError(f"{path}: {e}") from None
    if note["agent"] != agent:
        raise NoteError(f"{path}: note belongs to agent {note['agent']!r}, filed under {agent!r}")
    if note["id"] != m.group(1):
        raise NoteError(f"{path}: file name does not match the note id {note['id']}")
    if canonical_bytes(note) != data:
        raise NoteError(
            f"{path}: bytes are not the canonical serialization (sorted keys, two-space "
            "indent, trailing newline) — a reformatted note is an edited note"
        )
    return note


def load(store: Path, agent: str) -> list[dict]:
    """Read one agent's notes cold, oldest first; fail loud on any bad file.

    No index, no cache, nothing to warm: a glob and a strict parse of each
    file. Recall (Slice 1b) must never run on a store it cannot trust, so this
    raises rather than skip a file.
    """
    if not isinstance(agent, str) or not AGENT_RE.match(agent):
        raise NoteError(f"agent {agent!r} does not match {AGENT_RE.pattern}")
    root = Path(store) / agent
    if not root.is_dir():
        return []
    notes = [_read_note(p, agent) for p in sorted(root.iterdir())]
    ids = {n["id"] for n in notes}
    for n in notes:
        for link in n["links"]:
            if link not in ids:
                raise NoteError(f"{note_path(store, agent, n['id'])}: link {link} resolves to no note")
    return sorted(notes, key=lambda n: (n["ts"], n["id"]))


def check(store: Path) -> tuple[list[str], int]:
    """Validate every committed note; return ``(problems, note_count)``.

    Collects every problem rather than stopping at the first, so one run names
    them all. A missing store is an empty store, not an error.
    """
    store = Path(store)
    problems: list[str] = []
    count = 0
    if not store.exists():
        return problems, count
    if not store.is_dir():
        return [f"{store}: the store root is not a directory"], count
    for entry in sorted(store.iterdir()):
        if not entry.is_dir() or not AGENT_RE.match(entry.name):
            problems.append(f"{entry}: the store holds only <agent>/ directories")
            continue
        ids: set[str] = set()
        links: list[tuple[Path, str]] = []
        for path in sorted(entry.iterdir()):
            try:
                note = _read_note(path, entry.name)
            except NoteError as e:
                problems.append(str(e))
                continue
            count += 1
            ids.add(note["id"])
            links.extend((path, link) for link in note["links"])
        for path, link in links:
            if link not in ids:
                problems.append(f"{path}: link {link} resolves to no note in {entry.name}'s store")
    return problems, count
