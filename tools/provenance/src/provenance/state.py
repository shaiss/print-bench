"""``state.json`` — the evidence branch's one mutable file: cursors, pending units, skips, versions.

Shape (contract ``state@1``)::

    {"format": "state@1",
     "versions": {"harvester": "provenance 0.1.0", "digest": "body-digest@1",
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

from typing import Any, Iterable, Optional

STATE_PATH = "state.json"
STATE_FORMAT = "state@1"


def empty_state(versions: dict[str, Any]) -> dict[str, Any]:
    """A fresh state@1 (bootstrap)."""
    raise NotImplementedError("builder H1")


def load_state(data: Optional[bytes], versions: dict[str, Any]) -> dict[str, Any]:
    """Parse ``state.json`` bytes (``None`` → :func:`empty_state`); a different
    ``versions`` is recorded, never a reason to discard cursors."""
    raise NotImplementedError("builder H1")


def dump_state(state: dict[str, Any]) -> bytes:
    """Canonical JSON bytes (``canonical.dumps_bytes``). Shape validation is ``check``'s job."""
    raise NotImplementedError("builder H1")


def set_pending(state: dict[str, Any], kind: str, key: str, *, closed_at: Optional[str],
                due_at: str, defer_until: str, reasons: list[str]) -> None:
    """Record/refresh a pending unit (``kind`` ``pr``/``brief``)."""
    raise NotImplementedError("builder H1")


def clear_pending(state: dict[str, Any], kind: str, key: str) -> None:
    """Drop a unit from ``pending`` (it froze this run)."""
    raise NotImplementedError("builder H1")


def set_skipped(state: dict[str, Any], pr: int, closed_at: str) -> None:
    """Record a closed PR that touches no ``designs/`` file (``skipped.pr[n] = {closed_at}``)."""
    raise NotImplementedError("builder H1")


def frozen_from_paths(paths: Iterable[str]) -> dict[str, dict[str, int]]:
    """``{"pr": {"636": 2}, "brief": {...}, "release": {...}}`` — the highest revision of every
    ``raw/<kind>/<key>[.r<K>].json.gz`` path (revision 1 = the bare path)."""
    raise NotImplementedError("builder H1")


def next_revision(frozen: dict[str, dict[str, int]], kind: str, key: str) -> int:
    """1 for a never-frozen unit, else the highest revision + 1."""
    raise NotImplementedError("builder H1")


def oldest_overdue(state: dict[str, Any], now: str, grace_hours: int) -> Optional[dict[str, Any]]:
    """The pending unit whose ``due_at + grace_hours`` is furthest past ``now`` (Reeve mirrors this)."""
    raise NotImplementedError("builder H1")
