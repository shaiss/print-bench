"""``--selftest``: prove every write-path rule still fires, offline, in seconds.

What check.sh runs (no pytest in that environment). Each case is a positive
and its negative control in one: a rule that has never been seen refusing is
indistinguishable from one that cannot. The pytest suite is the thorough
version; this is the falsifiable floor, and ``tests/test_selftest.py`` proves
it can fail by breaking a rule underneath it.

Writes only inside a throwaway temporary directory.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from . import note as note_mod
from . import rules
from .note import NoteError
from .store import ImmutableNoteError, check, load, record

_BASE = {
    "agent": "design-run",
    "ts": "2026-08-30T16:00:00Z",
    "run_id": "17000000001",
    "design": "selftest-part",
    "action": "sliced the hinge",
    "choice": "kept the 0.3 mm gap",
    "outcome": "fusecheck passed",
    "status": "completed",
    "author": "agent",
    "model": "glm-5.2",
}


def _ev(**over):
    ev = dict(_BASE)
    ev.update(over)
    return ev


def _refuses(fn, exc=NoteError) -> bool:
    try:
        fn()
    except exc:
        return True
    return False


def _case_importance(_store: Path) -> str | None:
    # Same status, only the surprise differs — so this isolates prediction error.
    calm = note_mod.encode(_ev(expected=1.0, actual=1.0))["importance"]
    shock = note_mod.encode(_ev(expected=0.95, actual=0.0))["importance"]
    if calm != 0:
        return f"the 400th green run must score 0, scored {calm}"
    if not shock > calm:
        return f"a surprising outcome ({shock}) must outscore an expected one ({calm})"
    if not _refuses(lambda: note_mod.encode(_ev(importance=99))):
        return "a caller-supplied importance was accepted"
    return None


def _case_zeigarnik(_store: Path) -> str | None:
    clean = note_mod.encode(_ev())["importance"]
    for status in sorted(set(rules.ZEIGARNIK) - {"completed"}):
        if not note_mod.encode(_ev(status=status))["importance"] > clean:
            return f"unfinished status {status!r} did not outrank completed-clean"
    return None


def _case_depth(_store: Path) -> str | None:
    rich = note_mod.encode(_ev(status="failed", detail="the full story", tags=["a", "b", "c"]))
    gist = note_mod.encode(_ev(detail="the full story", tags=["a", "b", "c"],
                               action="line one\nline two"))
    if rich["depth"] != "rich" or rich["detail"] != "the full story" or len(rich["tags"]) != 3:
        return "a salient event was not encoded rich"
    if gist["depth"] != "gist" or gist["detail"] is not None or len(gist["tags"]) > rules.GIST_MAX_TAGS:
        return "a routine event was not encoded as a thin gist"
    if gist["action"] != "line one":
        return "a gist field kept more than its first line"
    if not _refuses(lambda: note_mod.encode(_ev(depth="rich"))):
        return "a caller-supplied depth was accepted"
    return None


def _case_provenance(_store: Path) -> str | None:
    asserted = note_mod.encode(_ev())["provenance"]["verified"]
    confirmed = note_mod.encode(_ev(sources=[{"kind": "gate", "ref": "gate.sh run 1"}]))
    if asserted != rules.VERIFIED_ASSERTED:
        return f"an unsourced note was {asserted!r}, not model-asserted"
    if confirmed["provenance"]["verified"] != rules.VERIFIED_CONFIRMED:
        return "a note citing a gate result was not source-confirmed"
    if not _refuses(lambda: note_mod.encode(_ev(verified="source-confirmed"))):
        return "a caller-supplied verified was accepted"
    return None


def _case_immutability(store: Path) -> str | None:
    first = record(store, _ev())
    again = record(store, _ev())
    if not first.created or again.created or first.path != again.path:
        return "re-recording the same episode was not an idempotent no-op"
    original = first.path.read_bytes()
    first.path.write_bytes(original.replace(b"fusecheck passed", b"fusecheck FAILED"))
    if not _refuses(lambda: record(store, _ev()), ImmutableNoteError):
        return "a write over different committed bytes was not refused"
    problems, _ = check(store)
    if not problems:
        return "check did not flag a note edited after it was written"
    first.path.write_bytes(original)
    if check(store)[0]:
        return "check flagged a clean store"
    fix = record(store, _ev(run_id="17000000002", outcome="fusecheck re-run passed",
                            links=[first.note["id"]]))
    if first.path.read_bytes() != original or fix.path == first.path:
        return "a correction touched the note it corrects"
    if sorted(n["id"] for n in load(store, "design-run")) != sorted([first.note["id"], fix.note["id"]]):
        return "a cold load did not read back both notes"
    return None


CASES = (
    ("importance: prediction error, derived-only", _case_importance),
    ("importance: Zeigarnik unfinished > completed-clean", _case_zeigarnik),
    ("depth: salient rich, routine gist, never caller-set", _case_depth),
    ("provenance: confirmed only by a cited source", _case_provenance),
    ("immutability: idempotent, refuses overwrite, check catches edits", _case_immutability),
)


def run(out=print) -> int:
    fails = 0
    for label, fn in CASES:
        with tempfile.TemporaryDirectory(prefix="agent-memory-selftest-") as tmp:
            try:
                why = fn(Path(tmp) / "store")
            except Exception as e:  # a crash is a failed control, never a pass
                why = f"raised {type(e).__name__}: {e}"
        if why is None:
            out(f"ok   [{label}]")
        else:
            out(f"FAIL [{label}]: {why}")
            fails += 1
    if fails:
        out(f"agent-memory selftest: {fails} case(s) failed")
        return 1
    out("agent-memory selftest: all cases passed")
    return 0
