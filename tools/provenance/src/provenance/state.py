"""``state.json`` — the evidence branch's one mutable file: cursors, pending units, skips, versions.

Shape (contract ``state@1``)::

    {"format": "state@1",
     "versions": {"harvester": "provenance 0.1.0", "digest": "body-digest@2",
                  "step_grammar": 1, "contract": 1},
     "cursors": {"receipts": {"<workflow>": "<ts>"}, "prs_updated": ts|null,
                 "briefs_updated": ts|null, "releases_published": ts|null},
     "pending": {"pr": {"<n>": {"closed_at", "due_at", "defer_until", "reasons": []}},
                 "brief": {"<n>": {...}}},
     "skipped": {"pr": {"<n>": {"closed_at": ts}}},
     "ingested": {"pr843": {"manifest_sha256", "commit", "version", "snapshot_end",
                            "receipts", "statuses", "runs_listings"}}}

**Frozen units are NOT here** (critique items 11, 28): which PR / brief /
release is frozen, and at which revision, is read from the evidence tree's
``raw/`` paths by :func:`frozen_from_paths` — one source of truth, so state
and tree cannot drift, and state.json stays small (it no longer grows by one
entry per frozen unit). The terminal state a unit was frozen with
(``closed_at``/``merged_at``, a brief's ``state``) is read from the stored raw
document itself when the closed listing shows a change (freeze.py).
``skipped.pr`` keeps each skipped PR's ``closed_at`` so a PR that is
reopened, gains design files and closes again is re-evaluated.

Rules:

* **No wall-clock stamp.** Every time in it is derived from GitHub data
  (``due_at = closed_at + settle_hours``; ``defer_until = closed_at +
  max_defer_hours``) or is a cursor copied from a payload, so a run with
  nothing new writes byte-identical state and pushes nothing.
* **The only M.** ``gitstore.guard_diff`` allows a modification of this
  path and no other.
* **Size.** ~1 KB of cursors plus ``pending`` (a handful of entries) plus
  ``skipped.pr`` (~35 B per non-design PR, ≈ 40 KB/year at the measured
  rate); each evidence commit rewrites it and git stores successive versions
  as deltas (docs/provenance.md §Sizes).
* **Readers outside the package.** Reeve's ``provenance-lag`` detector reads
  ``pending`` and ``skipped`` (plus the ``raw/pr`` tree listing) through its own
  GET-only seam; keep the field names stable (contract version bump otherwise).

Every function here is pure (``now`` is a parameter). Owner: H1.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from . import canonical

STATE_PATH = "state.json"
STATE_FORMAT = "state@1"

#: Pending kinds and the freeze cursors (``receipts`` is the per-workflow map).
PENDING_KINDS = ("pr", "brief")
FREEZE_CURSORS = ("prs_updated", "briefs_updated", "releases_published")

#: ``raw/<kind>/<key>[.r<K>].json.gz`` — a frozen unit's path (revision 1 is the bare path,
#: K >= 2 the ``.r<K>`` form). ``raw/snapshot/…`` and ``receipts/…`` never match.
_RAW_PATH_RE = re.compile(
    r"raw/(?:(?P<kind>pr|brief)/(?P<num>[0-9]+)|release/(?P<tag>[A-Za-z0-9._-]+?))"
    r"(?:\.r(?P<rev>[2-9]|[1-9][0-9]+))?\.json\.gz"
)


def _empty_cursors() -> dict[str, Any]:
    return {"receipts": {}, "prs_updated": None, "briefs_updated": None, "releases_published": None}


def empty_state(versions: dict[str, Any]) -> dict[str, Any]:
    """A fresh state@1 (bootstrap)."""
    return {
        "format": STATE_FORMAT,
        "versions": dict(versions),
        "cursors": _empty_cursors(),
        "pending": {"pr": {}, "brief": {}},
        "skipped": {"pr": {}},
        "ingested": {},
    }


def load_state(data: Optional[bytes], versions: dict[str, Any]) -> dict[str, Any]:
    """Parse ``state.json`` bytes (``None`` → :func:`empty_state`); a different
    ``versions`` is recorded, never a reason to discard cursors.

    Every section is re-assembled onto a fresh :func:`empty_state`, so a state
    written by an older harvester that lacks a section reads with its default
    rather than failing; an unknown top-level key is dropped (``check`` would
    refuse it). A document that is not ``state@1`` raises ``ValueError``.
    """
    if data is None:
        return empty_state(versions)
    raw = json.loads(data.decode("utf-8"))
    if not isinstance(raw, dict) or raw.get("format") != STATE_FORMAT:
        raise ValueError(f"{STATE_PATH}: not a {STATE_FORMAT} document")
    state = empty_state(versions)
    cursors = raw.get("cursors") or {}
    state["cursors"]["receipts"] = {str(k): v for k, v in (cursors.get("receipts") or {}).items()}
    for key in FREEZE_CURSORS:
        state["cursors"][key] = cursors.get(key)
    pending = raw.get("pending") or {}
    for kind in PENDING_KINDS:
        state["pending"][kind] = {str(k): dict(v) for k, v in (pending.get(kind) or {}).items()}
    skipped = (raw.get("skipped") or {}).get("pr") or {}
    state["skipped"]["pr"] = {str(k): dict(v) for k, v in skipped.items()}
    state["ingested"] = {str(k): dict(v) for k, v in (raw.get("ingested") or {}).items()}
    return state


def dump_state(state: dict[str, Any]) -> bytes:
    """Canonical JSON bytes (``canonical.dumps_bytes``). Shape validation is ``check``'s job."""
    return canonical.dumps_bytes(state)


def set_pending(state: dict[str, Any], kind: str, key: str, *, closed_at: Optional[str],
                due_at: str, defer_until: str, reasons: list[str]) -> None:
    """Record/refresh a pending unit (``kind`` ``pr``/``brief``)."""
    if kind not in PENDING_KINDS:
        raise ValueError(f"pending kind {kind!r} (expected one of {PENDING_KINDS})")
    state["pending"].setdefault(kind, {})[str(key)] = {
        "closed_at": closed_at, "defer_until": defer_until, "due_at": due_at,
        "reasons": sorted(set(reasons)),
    }


def clear_pending(state: dict[str, Any], kind: str, key: str) -> None:
    """Drop a unit from ``pending`` (it froze this run)."""
    state["pending"].get(kind, {}).pop(str(key), None)


def set_skipped(state: dict[str, Any], pr: int, closed_at: str) -> None:
    """Record a closed PR that touches no ``designs/`` file (``skipped.pr[n] = {closed_at}``)."""
    state["skipped"].setdefault("pr", {})[str(int(pr))] = {"closed_at": closed_at}


def frozen_from_paths(paths: Iterable[str]) -> dict[str, dict[str, int]]:
    """``{"pr": {"636": 2}, "brief": {...}, "release": {...}}`` — the highest revision of every
    ``raw/<kind>/<key>[.r<K>].json.gz`` path (revision 1 = the bare path)."""
    out: dict[str, dict[str, int]] = {"pr": {}, "brief": {}, "release": {}}
    for path in paths:
        m = _RAW_PATH_RE.fullmatch(path)
        if m is None:
            continue
        kind = m.group("kind") or "release"
        key = m.group("num") if m.group("kind") else m.group("tag")
        rev = int(m.group("rev")) if m.group("rev") else 1
        if rev > out[kind].get(key, 0):
            out[kind][key] = rev
    return out


def next_revision(frozen: dict[str, dict[str, int]], kind: str, key: str) -> int:
    """1 for a never-frozen unit, else the highest revision + 1."""
    return frozen.get(kind, {}).get(str(key), 0) + 1


def _ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def oldest_overdue(state: dict[str, Any], now: str, grace_hours: int) -> Optional[dict[str, Any]]:
    """The pending unit whose ``due_at + grace_hours`` is furthest past ``now`` (Reeve mirrors this).

    Returns ``{"kind", "key", "overdue_seconds", **entry}``, or ``None`` when no
    pending unit is past ``due_at + grace_hours``. Ties break on kind order
    (``pr`` before ``brief``) then the smaller number, so the answer is
    deterministic.
    """
    t_now = _ts(now)
    best: Optional[tuple[tuple[int, int, int], str, str, dict[str, Any]]] = None
    for rank, kind in enumerate(PENDING_KINDS):
        for key, entry in (state.get("pending", {}).get(kind) or {}).items():
            due = entry.get("due_at")
            if not due:
                continue
            over = int((t_now - (_ts(due) + timedelta(hours=grace_hours))).total_seconds())
            if over <= 0:
                continue
            num = int(key) if str(key).isdigit() else 0
            order = (over, -rank, -num)
            if best is None or order > best[0]:
                best = (order, kind, str(key), entry)
    if best is None:
        return None
    (over, _, _), kind, key, entry = best
    return {"kind": kind, "key": key, "overdue_seconds": over, **entry}
