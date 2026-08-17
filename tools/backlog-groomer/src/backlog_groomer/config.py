"""Committed policy config for the backlog groomer.

``.github/backlog-groomer.conf`` is the git-tracked source of truth for the
routine's thresholds and its half of the two-key arming switch — the same
split every scheduled routine here uses (``.github/backlog-burn.conf`` is
the pattern): git holds the reviewed policy, the ``BACKLOG_GROOMER_ENABLED``
repo variable is the live human-only arming/kill switch, and the run is
inert unless **both** agree.

This is deliberately the groomer's *own* parser rather than a reuse of
``tools/backlog-burn``'s: that parser's key set is closed on purpose
(unknown keys fail loudly — a typo must never be silently ignored), so it
can never carry the groomer's threshold keys, and teaching it per-tool key
sets would couple the two routines' policies.  The *format contract* is
identical — ``key: value``, ``#`` comments, colonless/unknown/duplicate
keys and malformed values all raise with ``path:lineno`` context, and
defaults are fail-safe (an absent ``enabled`` reads as off).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_PATH = ".github/backlog-groomer.conf"

# The only keys the file may carry. Anything else is a typo and must fail.
_KNOWN_KEYS = (
    "enabled",
    "cadence",
    "provider",
    "narrative",
    "staleness_days",
    "armed_stuck_days",
    "oversized_stuck_days",
    "dup_threshold",
    "max_dup_pairs",
)

# Providers with a narrative ship step in the workflow (the house
# per-provider pattern: a secret can only be referenced by its literal
# name, so each provider owns a reviewed step). Maps the committed
# `provider:` label to that provider's secret name — the same vocabulary
# backlog-burn's conf and the #206 registry use.
NARRATIVE_PROVIDERS: dict[str, str] = {
    "zai": "ZAI_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

# Named cadence presets → cron expression, same vocabulary as the burn's
# config so the two files read alike.  NOTE the presets all fire at :17 —
# the backlog burn's slot — so the committed groomer conf stores a *raw*
# cron instead (the chunker's precedent for exactly this reason).
CADENCE_PRESETS: dict[str, str] = {
    "hourly": "17 * * * *",
    "4x":     "17 0,6,12,18 * * *",
    "2x":     "17 6,18 * * *",
    "daily":  "17 6 * * *",
    "weekly": "17 6 * * 1",
}

# A minimal 5-field cron literal (same guard as the burn's parser).
_CRON_RE = re.compile(r"^[^'\s]\S*(?:\s+[^'\s]\S*){4}$")


def _parse_bool(value: str, where: str) -> bool:
    low = value.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    raise ValueError(f"{where}: 'enabled' must be 'true' or 'false', got {value!r}")


def _parse_provider(value: str, where: str) -> str:
    if value not in NARRATIVE_PROVIDERS:
        known = ", ".join(sorted(NARRATIVE_PROVIDERS))
        raise ValueError(
            f"{where}: 'provider' must be one of ({known}), got {value!r}"
        )
    return value


def _parse_narrative_bool(value: str, where: str) -> bool:
    low = value.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    raise ValueError(f"{where}: 'narrative' must be 'true' or 'false', got {value!r}")


def _parse_positive_int(value: str, key: str, where: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise ValueError(f"{where}: {key!r} must be a positive integer, got {value!r}") from None
    if parsed <= 0:
        raise ValueError(f"{where}: {key!r} must be a positive integer, got {value!r}")
    return parsed


def _parse_threshold(value: str, where: str) -> float:
    try:
        parsed = float(value)
    except ValueError:
        raise ValueError(
            f"{where}: 'dup_threshold' must be a number in (0, 1], got {value!r}"
        ) from None
    if not 0 < parsed <= 1:
        raise ValueError(f"{where}: 'dup_threshold' must be in (0, 1], got {value!r}")
    return parsed


def _validate_cadence(value: str, where: str) -> str:
    """Return the cron for ``value`` (preset name or raw 5-field cron)."""
    if value in CADENCE_PRESETS:
        return CADENCE_PRESETS[value]
    if _CRON_RE.match(value):
        return value
    presets = ", ".join(sorted(CADENCE_PRESETS))
    raise ValueError(
        f"{where}: 'cadence' must be a preset name ({presets}) "
        f"or a 5-field cron literal, got {value!r}"
    )


@dataclass
class Config:
    """The groomer's committed policy.

    Defaults are the documented ones from issue #244; ``enabled`` defaults
    to False so an incomplete file never reads as "on".
    """

    enabled: bool = False
    cadence: str = ""  # preset name or raw cron ("" = workflow's literal is authoritative)
    # The narrative layer (#248): which provider's key the optional step
    # uses, and whether the step runs at all. `narrative` defaults OFF —
    # the deterministic report is the committed behavior, the narrative is
    # an opt-in layer on top.
    provider: str = ""  # "" = unset; the workflow fails loudly if narrative needs one
    narrative: bool = False
    staleness_days: int = 14
    armed_stuck_days: int = 7
    oversized_stuck_days: int = 7
    dup_threshold: float = 0.6
    max_dup_pairs: int = 10


def load(path: str = DEFAULT_PATH) -> Config:
    """Parse the config file into a :class:`Config`, or raise on any problem."""
    cfg = Config()
    seen: set[str] = set()
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                raise ValueError(f"{path}:{lineno}: expected 'key: value', got {raw.rstrip()!r}")
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            where = f"{path}:{lineno}"
            if key not in _KNOWN_KEYS:
                raise ValueError(f"{where}: unknown key {key!r} (known: {list(_KNOWN_KEYS)})")
            if key in seen:
                raise ValueError(f"{where}: duplicate key {key!r}")
            seen.add(key)
            if key == "enabled":
                cfg.enabled = _parse_bool(value, where)
            elif key == "cadence":
                _validate_cadence(value, where)  # validate but keep original string
                cfg.cadence = value
            elif key == "provider":
                cfg.provider = _parse_provider(value, where)
            elif key == "narrative":
                cfg.narrative = _parse_narrative_bool(value, where)
            elif key == "dup_threshold":
                cfg.dup_threshold = _parse_threshold(value, where)
            elif key == "max_dup_pairs":
                cfg.max_dup_pairs = _parse_positive_int(value, key, where)
            else:  # the three *_days thresholds
                setattr(cfg, key, _parse_positive_int(value, key, where))
    if cfg.narrative and not cfg.provider:
        raise ValueError(
            f"{path}: 'narrative: true' requires a 'provider:' key — the "
            "narrative step needs to know whose key to use (known: "
            f"{sorted(NARRATIVE_PROVIDERS)})"
        )
    return cfg


def get(key: str, path: str = DEFAULT_PATH) -> str:
    """Return one config value as a plain string, for the workflow to read.

    ``enabled`` renders as ``"true"``/``"false"`` so a workflow step can gate
    on it directly; numbers render bare (``14``, ``0.6``).
    """
    if key not in _KNOWN_KEYS:
        raise KeyError(f"unknown config key: {key!r} (known: {list(_KNOWN_KEYS)})")
    cfg = load(path)
    value = getattr(cfg, key)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def armed(variable: str | None, conf_enabled: str | None) -> bool:
    """The two-key arming decision: run only when *both* keys agree.

    ``variable`` is the live repo variable (``BACKLOG_GROOMER_ENABLED``),
    ``conf_enabled`` the committed conf's ``enabled`` as a string.  Only the
    exact word ``true`` (case-insensitive, surrounding whitespace ignored)
    arms a key; anything else — ``false``, ``1``, ``yes``, empty, unset —
    reads as off, so a typo can never arm the routine.
    """

    def _on(value: str | None) -> bool:
        return (value or "").strip().lower() == "true"

    return _on(variable) and _on(conf_enabled)
