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

==========================  ===========  =======================================================
key                         default      meaning
==========================  ===========  =======================================================
enabled                     false        the in-git half of the two-key arming; a dispatch needs only this
cadence                     (required)   raw 5-field cron, == provenance.yml's ``- cron: '…'``
settle_hours                6            closed → due
max_defer_hours             24           deferred → forced freeze with incomplete[]
deploy_wait_hours           2            wait for a terminal Production deployment
scheduled_max_requests      400          request cap of one scheduled run
rate_floor                  500          X-RateLimit-Remaining floor (stop / sleep)
dispatch_max_minutes        330          a dispatch's CAPTURE stops at job start + this − the reserve
derive_reserve_minutes      30           kept for derive + publish after capture; replaced by 2× the
                                         measured derive time of the integration dry run
backfill_since              2026-07-31   earliest ``--since`` accepted, and the PR/brief cursor floor
ambiguity_window_minutes    15           serving code-basis ambiguity window
edit_grace_seconds          60           comment edit → claimed
receipt_lookback_hours      48           receipts re-list window (re-run attempts)
continuity_horizon_days     90           how far back the checkpoint scan reads (= artifact retention)
watched_workflows           (required)   comma list of ``*.yml`` names, unique
snapshot_id                 pr843        ``pr<N>``: the evidence subtree and receipts' ``source``
snapshot_dir                (required)   the snapshot's directory IN THE MAIN CHECKOUT
snapshot_commit             (required)   40-hex: the main commit that merged it (recorded in state)
snapshot_manifest_sha256    (required)   64-hex: sha256 of its MANIFEST.sha256 — the authenticity pin
==========================  ===========  =======================================================

There is no ref or branch key for the snapshot and no dispatch input can
name one (critique item 2): the ingest reads only the default-branch
checkout, and :func:`ingest.verify_manifest` refuses a directory whose
manifest does not hash to the pin.

Reeve's ``provenance-lag`` threshold is Reeve's own key (``provenance_lag_hours`` in
``.github/reeve.conf``, default 3) — one owner per policy value.

``scripts/cadence-sync-check.sh`` reads ``cadence`` with its own house
reader; nothing else reads this file but :func:`load` (there is no
``config --get`` subcommand — critique item 31).

Owner: H6. Pure (``parse`` takes text; ``load`` reads one file).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

DEFAULT_PATH = ".github/provenance.conf"

KEYS = (
    "enabled", "cadence", "settle_hours", "max_defer_hours", "deploy_wait_hours",
    "scheduled_max_requests", "rate_floor", "dispatch_max_minutes", "derive_reserve_minutes",
    "backfill_since", "ambiguity_window_minutes", "edit_grace_seconds", "receipt_lookback_hours",
    "continuity_horizon_days", "watched_workflows", "snapshot_id", "snapshot_dir",
    "snapshot_commit", "snapshot_manifest_sha256",
)

#: Keys with no default: a conf missing one is refused (``path: missing required key``).
REQUIRED = ("cadence", "watched_workflows", "snapshot_dir", "snapshot_commit",
            "snapshot_manifest_sha256")

#: Integer keys and the smallest value each accepts (owner decision 9 defaults below).
INT_MIN = {
    "settle_hours": 1, "max_defer_hours": 1, "deploy_wait_hours": 0,
    "scheduled_max_requests": 1, "rate_floor": 0, "dispatch_max_minutes": 1,
    "derive_reserve_minutes": 0, "ambiguity_window_minutes": 0, "edit_grace_seconds": 0,
    "receipt_lookback_hours": 0, "continuity_horizon_days": 1,
}

DEFAULTS = {
    "enabled": False, "settle_hours": 6, "max_defer_hours": 24, "deploy_wait_hours": 2,
    "scheduled_max_requests": 400, "rate_floor": 500, "dispatch_max_minutes": 330,
    "derive_reserve_minutes": 30, "backfill_since": "2026-07-31", "ambiguity_window_minutes": 15,
    "edit_grace_seconds": 60, "receipt_lookback_hours": 48, "continuity_horizon_days": 90,
    "snapshot_id": "pr843",
}

_INT_RE = re.compile(r"[0-9]{1,9}")
#: One cron field: digits, ``*``, ``,``, ``-``, ``/`` (a raw 5-field literal; no presets here).
_CRON_FIELD_RE = re.compile(r"[0-9*,/-]+")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)?")
#: The contract's receipts-cursor key pattern (``state@1.cursors.receipts``).
_WORKFLOW_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\.yml")
_SNAPSHOT_ID_RE = re.compile(r"pr[0-9]{1,7}")
_PATH_PART_RE = re.compile(r"[A-Za-z0-9._-]{1,128}")
_SHA40_RE = re.compile(r"[0-9a-f]{40}")
_HEX64_RE = re.compile(r"[0-9a-f]{64}")


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
    derive_reserve_minutes: int
    backfill_since: str
    ambiguity_window_minutes: int
    edit_grace_seconds: int
    receipt_lookback_hours: int
    continuity_horizon_days: int
    watched_workflows: tuple[str, ...]
    snapshot_id: str
    snapshot_dir: str
    snapshot_commit: str
    snapshot_manifest_sha256: str


def _value(key: str, raw: str, where: str):
    """Validate one value; returns its typed form or raises :class:`ConfError` at ``where``."""
    if key == "enabled":
        low = raw.lower()
        if low not in ("true", "false"):
            raise ConfError(f"{where}: 'enabled' must be 'true' or 'false', got {raw!r}")
        return low == "true"
    if key in INT_MIN:
        if "." in raw:
            raise ConfError(f"{where}: {key!r} must be an integer (no decimal point), got {raw!r}")
        if not _INT_RE.fullmatch(raw):
            raise ConfError(f"{where}: {key!r} must be a non-negative integer, got {raw!r}")
        value = int(raw)
        if value < INT_MIN[key]:
            raise ConfError(f"{where}: {key!r} must be >= {INT_MIN[key]}, got {raw!r}")
        return value
    if key == "cadence":
        fields = raw.split()
        if len(fields) != 5 or not all(_CRON_FIELD_RE.fullmatch(f) for f in fields):
            raise ConfError(f"{where}: 'cadence' must be a raw 5-field cron literal, got {raw!r}")
        return " ".join(fields)
    if key == "backfill_since":
        fmt = "%Y-%m-%dT%H:%M:%SZ" if "T" in raw else "%Y-%m-%d"
        try:
            if not _DATE_RE.fullmatch(raw):
                raise ValueError(raw)
            datetime.strptime(raw, fmt)
        except ValueError:
            raise ConfError(f"{where}: 'backfill_since' must be YYYY-MM-DD[THH:MM:SSZ], got {raw!r}") from None
        return raw
    if key == "watched_workflows":
        items = [item.strip() for item in raw.split(",")]
        for item in items:
            if not _WORKFLOW_RE.fullmatch(item):
                raise ConfError(f"{where}: 'watched_workflows' item {item!r} is not a workflow file name")
        if len(set(items)) != len(items):
            raise ConfError(f"{where}: 'watched_workflows' names a workflow twice")
        return tuple(items)
    if key == "snapshot_id":
        if not _SNAPSHOT_ID_RE.fullmatch(raw):
            raise ConfError(f"{where}: 'snapshot_id' must be pr<N>, got {raw!r}")
        return raw
    if key == "snapshot_dir":
        parts = raw.split("/")
        if (raw.startswith("/") or "\\" in raw
                or not all(_PATH_PART_RE.fullmatch(p) and p not in (".", "..") for p in parts)):
            raise ConfError(f"{where}: 'snapshot_dir' must be a relative POSIX path in the main "
                            f"checkout (no leading '/', no '..'), got {raw!r}")
        return raw
    if key == "snapshot_commit":
        if not _SHA40_RE.fullmatch(raw):
            raise ConfError(f"{where}: 'snapshot_commit' must be 40 lower-case hex, got {raw!r}")
        return raw
    if key == "snapshot_manifest_sha256":
        if not _HEX64_RE.fullmatch(raw):
            raise ConfError(f"{where}: 'snapshot_manifest_sha256' must be 64 lower-case hex, got {raw!r}")
        return raw
    raise ConfError(f"{where}: unknown key {key!r}")  # pragma: no cover — KEYS is checked first


def parse(text: str, path: str = DEFAULT_PATH) -> Config:
    """Parse conf text (module docstring rules). ``snapshot_dir`` must be a relative POSIX path
    without ``..``; ``snapshot_commit`` 40-hex; ``snapshot_manifest_sha256`` 64-hex;
    ``derive_reserve_minutes`` < ``dispatch_max_minutes``; ``max_defer_hours`` >= ``settle_hours``
    (a unit is never forced before it is due); every integer key has a floor (:data:`INT_MIN`)."""
    values: dict[str, object] = dict(DEFAULTS)
    lines: dict[str, int] = {}
    for lineno, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        where = f"{path}:{lineno}"
        if ":" not in line:
            raise ConfError(f"{where}: expected 'key: value', got {raw_line.rstrip()!r}")
        key, _, raw = line.partition(":")
        key, raw = key.strip(), raw.strip()
        if key not in KEYS:
            raise ConfError(f"{where}: unknown key {key!r} (known: {', '.join(KEYS)})")
        if key in lines:
            raise ConfError(f"{where}: duplicate key {key!r} (first set on line {lines[key]})")
        if not raw:
            raise ConfError(f"{where}: {key!r} has an empty value")
        lines[key] = lineno
        values[key] = _value(key, raw, where)
    for key in REQUIRED:
        if key not in values:
            raise ConfError(f"{path}: missing required key {key!r}")
    if values["derive_reserve_minutes"] >= values["dispatch_max_minutes"]:  # type: ignore[operator]
        where = f"{path}:{lines.get('derive_reserve_minutes', lines.get('dispatch_max_minutes', 0))}"
        raise ConfError(f"{where}: 'derive_reserve_minutes' must be < 'dispatch_max_minutes' "
                        f"({values['derive_reserve_minutes']} >= {values['dispatch_max_minutes']})")
    if values["max_defer_hours"] < values["settle_hours"]:  # type: ignore[operator]
        where = f"{path}:{lines.get('max_defer_hours', lines.get('settle_hours', 0))}"
        raise ConfError(f"{where}: 'max_defer_hours' must be >= 'settle_hours' "
                        f"({values['max_defer_hours']} < {values['settle_hours']})")
    return Config(**values)  # type: ignore[arg-type]


def load(path: str = DEFAULT_PATH) -> Config:
    """Read and :func:`parse` one file."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise ConfError(f"{path}: cannot read ({exc.strerror or exc})") from None
    return parse(text, path)


def armed(conf_enabled: bool, variable: Optional[str]) -> bool:
    """The two-key schedule arming: conf ``enabled`` AND ``PROVENANCE_ENABLED`` casefolds to
    ``"true"`` (GitHub's expression ``==`` is case-insensitive, so ``True``/``TRUE`` arm the
    YAML leg too — the two legs must agree; critique item 20)."""
    # No strip: the YAML leg `vars.PROVENANCE_ENABLED == 'true'` casefolds but never trims, so
    # ' true' is disarmed there and must be disarmed here (the andon cord's reading).
    return conf_enabled is True and isinstance(variable, str) and variable.casefold() == "true"
