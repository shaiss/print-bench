"""The deterministic write-time rules: importance, encoding depth, provenance.

Every function here is a pure function of a note's own inputs — no clock, no
randomness, no I/O, no model. That is the #426 line this slice exists to hold:
**no LLM in the write path**. Importance is computed once, at write time, from
facts the routine already has; relevance (recall time, task-relative, the
lite-LLM's job) is Slice 1b and never touches this module.

The constants are the initial tuning (#426's "Still open" item 3 names them as
build-time knobs). They live in this one module so a retune is a one-file diff
the golden tests in ``tests/test_importance.py`` make deliberate: change a
weight and a pinned score moves, so nobody retunes by accident.
"""

from __future__ import annotations

import math

# --- importance ---------------------------------------------------------------

#: Weight of a *total* surprise, ``|expected - actual| == 1``. The largest
#: single term on purpose: prediction error is "the engine of anchor events"
#: (#426) — a gate expected to pass that fails is high-surprise, the 400th green
#: run is ~zero.
PE_WEIGHT = 60

#: Zeigarnik: unfinished business is retained above completed-clean. Every
#: non-``completed`` status scores at least ``RICH_THRESHOLD`` on its own, so an
#: unfinished run is always encoded rich — its lesson is the reason to remember
#: it. ``completed`` contributes nothing: a clean finish is not, by itself,
#: worth remembering.
ZEIGARNIK = {
    "completed": 0,
    "withdrawn": 35,   # a run that withdrew its own claim (dead SHIP-LOCK)
    "parked": 35,      # a `needs-decision` park
    "incomplete": 40,  # interrupted / unconverged
    "failed": 40,
}

#: Baseline consequence signals (#426: "reprint/field-test failure,
#: fuse/STRONG-WARN, escalation, resolved-after-N"). A closed set: an unknown
#: signal is refused, never silently scored 0.
CONSEQUENCE = {
    "field-test-failure": 25,
    "fuse-strong-warn": 20,
    "escalation": 15,
    "resolved-after-retries": 10,
}

IMPORTANCE_MAX = 100

# --- encoding depth -----------------------------------------------------------

#: Salience-proportional depth: at or above this importance a note is encoded
#: **rich** (full text, detail, every tag); below it, **gist** (one line per
#: field, no detail, a couple of tags).
RICH_THRESHOLD = 35
DEPTHS = ("gist", "rich")

#: A gist field is its text's first line, at most this many characters.
GIST_LINE_MAX = 120
#: "A line + a couple tags" (#426).
GIST_MAX_TAGS = 2
GIST_ELLIPSIS = "…"

# --- provenance ---------------------------------------------------------------

VERIFIED_CONFIRMED = "source-confirmed"
VERIFIED_ASSERTED = "model-asserted"
#: The kinds of source a note may cite: sources of truth a routine can point
#: at. A closed set, but only the *kind* is checked; the ``ref`` is not
#: resolved in Slice 1a (see ``verified_for``).
SOURCE_KINDS = ("ci", "field-test", "gate", "render")
AUTHORS = ("agent", "human")


class RuleError(ValueError):
    """An input the deterministic rules refuse to score."""


def _unit(name: str, value: object) -> float:
    # bool is an int subclass in Python; True would otherwise score as 1.0.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuleError(f"{name} must be a number in [0, 1], got {value!r}")
    v = float(value)
    if math.isnan(v) or not 0.0 <= v <= 1.0:
        raise RuleError(f"{name} must be a number in [0, 1], got {value!r}")
    return v


def prediction_error(expected: object, actual: object) -> float:
    """``|expected - actual|`` on the unit interval, or 0.0 when unmeasured.

    ``expected`` is the routine's prior (e.g. the chance this gate passes, from
    telemetry); ``actual`` the realized outcome on the same scale. They come as
    a pair: half a measurement is a caller bug, not "no surprise".
    """
    if expected is None and actual is None:
        return 0.0
    if expected is None or actual is None:
        raise RuleError("expected and actual come as a pair — supply both or neither")
    return abs(_unit("expected", expected) - _unit("actual", actual))


def importance(status: str, expected: object, actual: object, signals) -> int:
    """The write-time importance score, an int in ``[0, IMPORTANCE_MAX]``.

    ``round(PE_WEIGHT * |expected - actual|) + ZEIGARNIK[status] +
    sum(CONSEQUENCE[signal])``, clamped. Additive on purpose: each term is
    visible in the note's stored ``salience`` block, so a reviewer (and
    ``check``) can recompute the number by hand.
    """
    if status not in ZEIGARNIK:
        raise RuleError(f"unknown status {status!r} — one of {', '.join(sorted(ZEIGARNIK))}")
    signals = list(signals)
    for s in signals:
        if s not in CONSEQUENCE:
            raise RuleError(
                f"unknown consequence signal {s!r} — one of {', '.join(sorted(CONSEQUENCE))}"
            )
    if len(set(signals)) != len(signals):
        raise RuleError(f"duplicate consequence signal in {signals!r} — each counts once")
    pe = prediction_error(expected, actual)
    # Round half up with integer output — never banker's rounding, never a float
    # score that could print differently on another machine.
    raw = math.floor(PE_WEIGHT * pe + 0.5) + ZEIGARNIK[status] + sum(CONSEQUENCE[s] for s in signals)
    return min(IMPORTANCE_MAX, raw)


def depth_for(score: int) -> str:
    """Salience-proportional encoding depth for an importance score."""
    return "rich" if score >= RICH_THRESHOLD else "gist"


def gist_line(text: str) -> str:
    """A gist field: the text's first line, clipped to ``GIST_LINE_MAX``.

    Idempotent — ``gist_line(gist_line(x)) == gist_line(x)`` — which is what
    lets ``check`` re-encode a stored gist note and get it back byte-for-byte.
    """
    first = text.split("\n", 1)[0].rstrip()
    if len(first) <= GIST_LINE_MAX:
        return first
    return first[: GIST_LINE_MAX - 1].rstrip() + GIST_ELLIPSIS


def verified_for(sources) -> str:
    """Provenance class: ``source-confirmed`` when at least one source is cited.

    A note with no source is ``model-asserted`` whoever wrote it — the class
    recall must re-ground before acting on. A caller cannot type the class
    directly; it can only cite a source. In Slice 1a that is all
    "confirmed" means: a source is *cited* (shape-checked by ``note``), not
    *resolved*. Nothing looks the ``ref`` up, so the class is only as
    trustworthy as whoever fills ``sources``, which is Slice 1d's decision.
    """
    return VERIFIED_CONFIRMED if sources else VERIFIED_ASSERTED
