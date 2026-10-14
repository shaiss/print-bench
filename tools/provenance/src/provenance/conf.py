"""Strict parser for ``.github/provenance.conf`` — the house ``key: value`` contract.

Same format contract as tools/reeve/config.py and tools/backlog-groomer
(each tool keeps its OWN parser with a CLOSED key set, so no parser learns
another routine's keys): ``key: value``, one per line; ``#`` starts a
whole-line comment; blank lines ignored; a colonless line, an unknown key, a
duplicate key or a malformed value raises :class:`ConfError` with
``path:lineno``. Fail-safe defaults: an absent ``enabled`` reads false.
Integers only — a value with a decimal point is refused (canonical JSON
stores no floats, and policy values should not drift by float repr).

Keys (:data:`KEYS`; defaults are owner decision 9):

=========================  ==========  =======================================================
key                        default     meaning
=========================  ==========  =======================================================
enabled                    false       the in-git half of the two-key arming (schedule only)
cadence                    (required)  raw 5-field cron, == provenance.yml's ``- cron:``
settle_hours               6           closed → due
max_defer_hours            24          deferred → forced freeze with incomplete[]
deploy_wait_hours          2           wait for a terminal Production deployment
scheduled_max_requests     400         request cap of one scheduled run
rate_floor                 500         X-RateLimit-Remaining floor (stop / sleep)
dispatch_max_minutes       330         self-paced dispatch stop (5.5 h)
backfill_since             2026-07-31  earliest ``--since`` accepted (YYYY-MM-DD)
ambiguity_window_minutes   15          serving code-basis ambiguity window
edit_grace_seconds         60          comment edit → claimed
receipt_lookback_hours     48          receipts re-list window (re-run attempts)
intent_window_runs         20          tip-continuity search depth
watched_workflows          (required)  comma list of ``*.yml`` names, unique
snapshot_id                pr843       ``pr<N>``
snapshot_ref               (required)  branch holding the snapshot
snapshot_path              (required)  directory inside it
=========================  ==========  =======================================================

Reeve's ``provenance-lag`` threshold is Reeve's own key (``provenance_lag_hours`` in
``.github/reeve.conf``, default 3) — one owner per policy value.

``scripts/cadence-sync-check.sh`` reads ``cadence`` with its own house
reader; ``python3 -m provenance config --get <key>`` prints one parsed value.

Owner: H6. Pure (``parse`` takes text; ``load`` reads one file).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

DEFAULT_PATH = ".github/provenance.conf"

KEYS = (
    "enabled", "cadence", "settle_hours", "max_defer_hours", "deploy_wait_hours",
    "scheduled_max_requests", "rate_floor", "dispatch_max_minutes", "backfill_since",
    "ambiguity_window_minutes", "edit_grace_seconds", "receipt_lookback_hours",
    "intent_window_runs", "watched_workflows", "snapshot_id",
    "snapshot_ref", "snapshot_path",
)


class ConfError(ValueError):
    """A malformed conf (message carries ``path:lineno``)."""


@dataclass(frozen=True)
class Config:
    """The parsed policy."""

    enabled: bool
    cadence: str
    settle_hours: int
    max_defer_hours: int
    deploy_wait_hours: int
    scheduled_max_requests: int
    rate_floor: int
    dispatch_max_minutes: int
    backfill_since: str
    ambiguity_window_minutes: int
    edit_grace_seconds: int
    receipt_lookback_hours: int
    intent_window_runs: int
    watched_workflows: tuple[str, ...]
    snapshot_id: str
    snapshot_ref: str
    snapshot_path: str


def parse(text: str, path: str = DEFAULT_PATH) -> Config:
    """Parse conf text (module docstring rules)."""
    raise NotImplementedError("builder H6")


def load(path: str = DEFAULT_PATH) -> Config:
    """Read and :func:`parse` one file."""
    raise NotImplementedError("builder H6")


def get(config: Config, key: str) -> str:
    """One value rendered for ``config --get`` (lists comma-joined, bools ``true``/``false``)."""
    raise NotImplementedError("builder H6")


def armed(conf_enabled: bool, variable: Optional[str]) -> bool:
    """The two-key schedule arming: conf ``enabled`` AND ``PROVENANCE_ENABLED == "true"``."""
    raise NotImplementedError("builder H6")
