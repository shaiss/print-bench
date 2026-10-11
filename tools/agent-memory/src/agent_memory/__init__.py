"""agent-memory — per-agent episodic memory for the autonomy routines (Slice 1a).

The store and its deterministic **record** (write) path, the first build slice
of the agentic-memory design (#426, `docs/agentic-memory.md`; this slice is
issue #429). A routine hands ``record`` an event — what it did, chose and got,
plus the salience facts it already knows — and the package encodes it into an
immutable note: importance scored by prediction error, Zeigarnik and
consequence signals; depth set by salience (rich vs gist); provenance classed
``source-confirmed`` when a source is cited (cited, not resolved, in this
slice); everything derived at write time, **no LLM in the write path**. The
event's inputs are the caller's word; who supplies them is Slice 1d's call.

The backend is the Slice 0 decision (#428): one content-hashed JSON file per
note under ``tools/agent-memory/store/<agent>/<id>.json``. Recall (1b),
reinforcement and clustering (1c) and routine wiring (1d) are later slices and
deliberately absent: nothing here reads a note *for* a routine, and nothing
calls this package yet.

Stdlib-only, zero network; ``store.py`` is the one module that reads or
writes the store. ``cli`` also reads the event file, and ``selftest`` writes
only inside a temporary directory. The purity tests hold all of it.
"""

from .note import NoteError, canonical_bytes, content_id, encode, parse_note
from .rules import RuleError, depth_for, importance, verified_for
from .store import ImmutableNoteError, Recorded, check, load, record

__all__ = [
    "ImmutableNoteError",
    "NoteError",
    "Recorded",
    "RuleError",
    "canonical_bytes",
    "check",
    "content_id",
    "depth_for",
    "encode",
    "importance",
    "load",
    "parse_note",
    "record",
    "verified_for",
]
