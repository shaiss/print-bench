"""The note: event validation, encoding, canonical bytes and the content id.

A routine hands ``encode`` an **event** — what it did, chose and got, the
salience facts it already knows, who wrote it and what source it cites. Encoding
validates every field strictly (fail-loud: an unknown key, a missing key, a
malformed value all raise), derives everything derivable — importance, depth,
the provenance class, the id — and returns the **note**, the one shape that is
ever stored.

The derived fields are never accepted from the caller: importance, depth and
the provenance class are computed here, from inputs a reviewer can read in
the note itself, and ``parse_note`` recomputes them on every read so a hand
edit is caught too. That guarantees consistency, not truth. The inputs
(``status``, ``expected``/``actual``, ``signals``, ``sources``) are the
caller's assertion, and a source's ``ref`` is shape-checked, never resolved,
so a caller that controls the event can reach any importance and the
``source-confirmed`` class through them. Who fills those inputs is Slice
1d's decision (the README's "Open for later slices").

Pure: no I/O, no clock, no randomness — the purity tests hold it.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping

from . import rules
from .rules import RuleError

SCHEMA_VERSION = 1

#: A fresh note's retrieval strength (Bjork). Reserved for Slice 1c's
#: reinforcement loop; nothing in Slice 1a changes it, and ``parse_note``
#: refuses any other value until 1c owns the rule that may.
INITIAL_RETRIEVAL_STRENGTH = 1.0

#: Fields left out of the content id. ``id`` cannot hash itself;
#: ``retrieval_strength`` is the one *index* field (it governs recall, not what
#: happened), excluded so Slice 1c can evolve it without renaming the note.
ID_EXCLUDED = frozenset({"id", "retrieval_strength"})

NOTE_KEYS = frozenset({
    "schema", "id", "agent", "ts", "run_id", "issue", "design",
    "action", "choice", "outcome", "detail",
    "salience", "importance", "depth", "retrieval_strength",
    "provenance", "tags", "links",
})
SALIENCE_KEYS = frozenset({"status", "expected", "actual", "signals"})
PROVENANCE_KEYS = frozenset({"author", "model", "verified", "sources"})
SOURCE_KEYS = frozenset({"kind", "ref"})

EVENT_REQUIRED = frozenset({
    "agent", "ts", "run_id", "action", "choice", "outcome", "status", "author",
})
EVENT_OPTIONAL = frozenset({
    "issue", "design", "detail", "expected", "actual", "signals",
    "model", "sources", "tags", "links",
})
#: Keys a caller may never supply — each is computed at write time.
EVENT_DERIVED = frozenset({
    "schema", "id", "importance", "depth", "retrieval_strength",
    "provenance", "verified", "salience",
})

AGENT_RE = re.compile(r"^[a-z][a-z0-9-]{0,47}$")
DESIGN_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
TAG_RE = re.compile(r"^[a-z0-9][a-z0-9._:/-]{0,63}$")
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,99}$")
ID_RE = re.compile(r"^[0-9a-f]{64}$")
_NEWLINES = re.compile(r"\r\n?")

FIELD_MAX = 2000      # action / choice / outcome
DETAIL_MAX = 8000
REF_MAX = 300
MAX_TAGS = 16
MAX_LINKS = 32
MAX_SOURCES = 16


class NoteError(ValueError):
    """An event or stored note the schema refuses."""


# --- field validators -----------------------------------------------------------


def _text(name: str, value: object, limit: int) -> str:
    """Normalize free text: NFC, LF line endings, outer whitespace stripped.

    Normalizing before hashing is what makes the id clone-stable: the same
    words typed on a CRLF machine, or composed vs decomposed accents, land on
    the same id instead of a near-duplicate.
    """
    if not isinstance(value, str):
        raise NoteError(f"{name} must be a string, got {type(value).__name__}")
    text = _NEWLINES.sub("\n", unicodedata.normalize("NFC", value)).strip()
    if not text:
        raise NoteError(f"{name} must not be empty")
    for ch in text:
        if ch not in "\n\t" and unicodedata.category(ch) == "Cc":
            raise NoteError(f"{name} carries a control character {ch!r}")
    if len(text) > limit:
        raise NoteError(f"{name} is {len(text)} characters; the limit is {limit}")
    return text


def _single_line(name: str, value: object, limit: int) -> str:
    text = _text(name, value, limit)
    if "\n" in text:
        raise NoteError(f"{name} must be a single line")
    return text


def _slug(name: str, value: object, pattern: re.Pattern) -> str:
    if not isinstance(value, str) or not pattern.match(value):
        raise NoteError(f"{name} {value!r} does not match {pattern.pattern}")
    return value


def _ts(value: object) -> str:
    if not isinstance(value, str) or not TS_RE.match(value):
        raise NoteError(f"ts {value!r} must be UTC ISO-8601, YYYY-MM-DDTHH:MM:SSZ")
    try:
        _dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as e:
        raise NoteError(f"ts {value!r} is not a real instant: {e}") from None
    return value


def _issue(value: object):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise NoteError(f"issue must be a positive integer, got {value!r}")
    return value


def _list(name: str, value: object, limit: int) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise NoteError(f"{name} must be a list, got {type(value).__name__}")
    if len(value) > limit:
        raise NoteError(f"{name} has {len(value)} entries; the limit is {limit}")
    return value


def _tags(value: object) -> list[str]:
    out = set()
    for t in _list("tags", value, MAX_TAGS):
        if not isinstance(t, str):
            raise NoteError(f"tag {t!r} must be a string")
        norm = t.strip().lower()
        if not TAG_RE.match(norm):
            raise NoteError(f"tag {t!r} does not match {TAG_RE.pattern}")
        out.add(norm)
    return sorted(out)


def _links(value: object) -> list[str]:
    out = set()
    for link in _list("links", value, MAX_LINKS):
        if not isinstance(link, str) or not ID_RE.match(link):
            raise NoteError(f"link {link!r} is not a note id (64 lowercase hex)")
        out.add(link)
    return sorted(out)


def _sources(value: object) -> list[dict]:
    out = {}
    for src in _list("sources", value, MAX_SOURCES):
        if not isinstance(src, dict) or set(src) != SOURCE_KEYS:
            raise NoteError(f"source {src!r} must be an object with exactly {sorted(SOURCE_KEYS)}")
        kind = src["kind"]
        if kind not in rules.SOURCE_KINDS:
            raise NoteError(f"source kind {kind!r} — one of {', '.join(rules.SOURCE_KINDS)}")
        ref = _single_line("source ref", src["ref"], REF_MAX)
        out[(kind, ref)] = {"kind": kind, "ref": ref}
    return [out[k] for k in sorted(out)]


def _signals(value: object) -> list[str]:
    signals = _list("signals", value, len(rules.CONSEQUENCE))
    for s in signals:
        if not isinstance(s, str):
            raise NoteError(f"signal {s!r} must be a string")
    return signals


# --- encoding -------------------------------------------------------------------


def encode(event: Mapping[str, Any]) -> dict:
    """Validate an event and return the note it encodes to, id included."""
    if not isinstance(event, Mapping):
        raise NoteError(f"an event is a JSON object, got {type(event).__name__}")
    keys = set(event)
    derived = sorted(keys & EVENT_DERIVED)
    if derived:
        raise NoteError(
            f"{', '.join(derived)}: derived at write time from the event's own inputs — "
            "a caller never supplies it"
        )
    unknown = sorted(keys - EVENT_REQUIRED - EVENT_OPTIONAL)
    if unknown:
        raise NoteError(f"unknown event field(s): {', '.join(unknown)}")
    missing = sorted(EVENT_REQUIRED - keys)
    if missing:
        raise NoteError(f"missing event field(s): {', '.join(missing)}")

    agent = _slug("agent", event["agent"], AGENT_RE)
    issue = _issue(event.get("issue"))
    design = event.get("design")
    if design is not None:
        design = _slug("design", design, DESIGN_RE)
    if issue is None and design is None:
        raise NoteError("an episode is about an issue, a design, or both — supply at least one")

    action = _text("action", event["action"], FIELD_MAX)
    choice = _text("choice", event["choice"], FIELD_MAX)
    outcome = _text("outcome", event["outcome"], FIELD_MAX)
    detail = event.get("detail")
    if detail is not None:
        detail = _text("detail", detail, DETAIL_MAX)

    status = event["status"]
    if not isinstance(status, str):
        raise NoteError(f"status must be a string, got {status!r}")
    signals = _signals(event.get("signals"))
    try:
        score = rules.importance(status, event.get("expected"), event.get("actual"), signals)
    except RuleError as e:
        raise NoteError(str(e)) from None
    expected = event.get("expected")
    actual = event.get("actual")
    salience = {
        "status": status,
        "expected": None if expected is None else float(expected),
        "actual": None if actual is None else float(actual),
        "signals": sorted(signals),
    }

    author = event["author"]
    if author not in rules.AUTHORS:
        raise NoteError(f"author {author!r} — one of {', '.join(rules.AUTHORS)}")
    model = event.get("model")
    if author == "agent":
        if model is None:
            raise NoteError("an agent-authored note names the model that wrote it")
        model = _slug("model", model, MODEL_RE)
    elif model is not None:
        raise NoteError("a human-authored note carries no model")
    sources = _sources(event.get("sources"))

    tags = _tags(event.get("tags"))
    links = _links(event.get("links"))

    depth = rules.depth_for(score)
    if depth == "gist":
        # Selective encoding: a routine event is kept thin — one line per
        # field, no detail, a couple of tags. Links and sources survive: they
        # are structure and trust, not detail, and dropping a correction's link
        # or a confirmed note's source would corrupt the graph or the trust
        # class rather than thin the note.
        action, choice, outcome = (rules.gist_line(t) for t in (action, choice, outcome))
        detail = None
        tags = tags[: rules.GIST_MAX_TAGS]

    note = {
        "schema": SCHEMA_VERSION,
        "agent": agent,
        "ts": _ts(event["ts"]),
        "run_id": _slug("run_id", event["run_id"], RUN_ID_RE),
        "issue": issue,
        "design": design,
        "action": action,
        "choice": choice,
        "outcome": outcome,
        "detail": detail,
        "salience": salience,
        "importance": score,
        "depth": depth,
        "retrieval_strength": INITIAL_RETRIEVAL_STRENGTH,
        "provenance": {
            "author": author,
            "model": model,
            "verified": rules.verified_for(sources),
            "sources": sources,
        },
        "tags": tags,
        "links": links,
    }
    note["id"] = content_id(note)
    return note


def content_id(note: Mapping[str, Any]) -> str:
    """SHA-256 over the note's canonical content, ``ID_EXCLUDED`` left out.

    Compact, sorted-key, UTF-8 JSON — byte-identical on every machine for the
    same note, so the same episode recorded twice lands on the same path (an
    idempotent write) and two different episodes never share one.
    """
    body = {k: v for k, v in note.items() if k not in ID_EXCLUDED}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def canonical_bytes(note: Mapping[str, Any]) -> bytes:
    """The committed file's exact bytes: pretty, sorted keys, trailing newline.

    Pretty-printed so a review UI shows a new note as one readable file and
    any later edit as a per-field diff; sorted so the bytes never depend on
    dict insertion order.
    """
    return (json.dumps(note, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


# --- reading --------------------------------------------------------------------


def _exact(value: object) -> str:
    """A value's JSON text — equal only when value **and** JSON type agree."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _event_of(note: Mapping[str, Any]) -> dict:
    sal, prov = note["salience"], note["provenance"]
    return {
        "agent": note["agent"], "ts": note["ts"], "run_id": note["run_id"],
        "issue": note["issue"], "design": note["design"],
        "action": note["action"], "choice": note["choice"], "outcome": note["outcome"],
        "detail": note["detail"],
        "status": sal["status"], "expected": sal["expected"], "actual": sal["actual"],
        "signals": sal["signals"],
        "author": prov["author"], "model": prov["model"], "sources": prov["sources"],
        "tags": note["tags"], "links": note["links"],
    }


def parse_note(obj: object) -> dict:
    """Validate a stored note strictly and return it.

    Re-derives every derived field from the note's own inputs and refuses any
    disagreement, so a hand edit — a promoted importance, a gist note given
    detail, a hand-flipped ``verified`` — fails here, by name.
    """
    if not isinstance(obj, dict):
        raise NoteError(f"a note is a JSON object, got {type(obj).__name__}")
    if obj.get("schema") != SCHEMA_VERSION:
        raise NoteError(f"schema {obj.get('schema')!r} is not {SCHEMA_VERSION} — refusing an unknown note shape")
    if set(obj) != NOTE_KEYS:
        extra, gone = sorted(set(obj) - NOTE_KEYS), sorted(NOTE_KEYS - set(obj))
        raise NoteError(f"note keys differ from schema {SCHEMA_VERSION}: extra {extra}, missing {gone}")
    for name, want in (("salience", SALIENCE_KEYS), ("provenance", PROVENANCE_KEYS)):
        if not isinstance(obj[name], dict) or set(obj[name]) != want:
            raise NoteError(f"{name} must be an object with exactly {sorted(want)}")
    for name in ("expected", "actual"):
        v = obj["salience"][name]
        if v is not None and not isinstance(v, float):
            raise NoteError(f"salience.{name} must be stored as a float, got {v!r}")
    if obj["retrieval_strength"] != INITIAL_RETRIEVAL_STRENGTH or not isinstance(obj["retrieval_strength"], float):
        raise NoteError(
            f"retrieval_strength {obj['retrieval_strength']!r} is not the initial "
            f"{INITIAL_RETRIEVAL_STRENGTH} — nothing in Slice 1a changes it"
        )
    if not isinstance(obj["id"], str) or not ID_RE.match(obj["id"]):
        raise NoteError(f"id {obj['id']!r} is not 64 lowercase hex")

    rebuilt = encode(_event_of(obj))

    if obj["importance"] != rebuilt["importance"]:
        raise NoteError(
            f"importance {obj['importance']!r} does not match its salience inputs "
            f"(they score {rebuilt['importance']}) — importance is derived, never edited"
        )
    if obj["depth"] != rebuilt["depth"]:
        raise NoteError(
            f"depth {obj['depth']!r} does not match importance {rebuilt['importance']} "
            f"(it encodes {rebuilt['depth']!r}) — depth is derived from salience"
        )
    if obj["provenance"]["verified"] != rebuilt["provenance"]["verified"]:
        raise NoteError(
            f"verified {obj['provenance']['verified']!r} does not follow from its sources "
            f"(they make it {rebuilt['provenance']['verified']!r}) — only a cited source confirms a note"
        )
    if obj["depth"] == "gist" and obj["detail"] is not None:
        raise NoteError("a gist note carries no detail — detail is kept only for rich notes")
    for key in sorted(NOTE_KEYS - {"id"}):
        # Compare the JSON text, not the Python values: ``40 == 40.0 == True``
        # in Python, so a ``!=`` here would let a type-only edit (an importance
        # stored as 40.0, a schema of 1.0 or true) through with the id still
        # matching. The JSON text tells them apart, and it is what is stored.
        if _exact(obj[key]) != _exact(rebuilt[key]):
            raise NoteError(
                f"{key} is not in its canonical encoded form — its value or its JSON "
                "type differs from what the note's own inputs encode to"
            )
    if obj["id"] != rebuilt["id"]:
        raise NoteError(
            f"id {obj['id']} is not the content hash {rebuilt['id']} — the note was edited "
            "after it was written (notes are immutable; a correction is a new linked note)"
        )
    return obj
