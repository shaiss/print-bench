"""``state.json`` — the evidence branch's one mutable file: cursors, pending units, versions.

Shape (contract ``state@1``)::

    {"format": "state@1",
     "versions": {"harvester": "provenance 0.1.0", "digest": "body-digest@1",
                  "step_grammar": 1, "contract": 1},
     "cursors": {"receipts": {"<workflow>": "<ts>"}, "prs_updated": ts|null,
                 "briefs_updated": ts|null, "releases_published": ts|null},
     "pending": {"pr": {"<n>": {"closed_at", "due_at", "defer_until", "reasons": []}},
                 "brief": {"<n>": {...}}},
     "frozen": {"pr": {"<n>": <highest revision>}, "brief": {...}, "release": {"<tag>": 1}},
     "skipped": {"pr": [<closed PRs that touch no designs/ file>]},
     "ingested": {"pr843": {"manifest_sha256", "receipts", "statuses", "runs_listings"}}}

Rules:

* **No wall-clock stamp.** Every time in it is derived from GitHub data
  (``due_at = closed_at + settle_hours``; ``defer_until = closed_at +
  max_defer_hours``) or is a cursor copied from a payload, so a run with
  nothing new writes byte-identical state and pushes nothing.
* **The only M.** ``gitstore.guard_diff`` allows a modification of this
  path and no other.
* **Readers outside the package.** Reeve's ``provenance-lag`` detector reads
  ``pending`` (oldest ``due_at``) through its own GET-only seam; keep the
  field names stable (contract version bump otherwise).

Every function here is pure (``now`` is a parameter). Owner: H1.
"""

from __future__ import annotations

from typing import Any, Optional

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


def set_frozen(state: dict[str, Any], kind: str, key: str, revision: int) -> None:
    """Record a frozen unit (removes it from ``pending``)."""
    raise NotImplementedError("builder H1")


def next_revision(state: dict[str, Any], kind: str, key: str) -> int:
    """1 for a never-frozen unit, else the recorded revision + 1."""
    raise NotImplementedError("builder H1")


def oldest_overdue(state: dict[str, Any], now: str, grace_hours: int) -> Optional[dict[str, Any]]:
    """The pending unit whose ``due_at + grace_hours`` is furthest past ``now`` (Reeve mirrors this)."""
    raise NotImplementedError("builder H1")
