"""Committed policy config for the growth agents (docs/growth.md).

``.github/growth-twitter.conf`` is the git-tracked source of truth for the
Twitter/X growth agent's policy and its half of the two-key arming switch —
the same split every scheduled routine here uses: git holds the reviewed
policy, the ``GROWTH_TWITTER_ENABLED`` repo variable is the live human-only
arming/kill switch, and the run is inert unless **both** agree. (Going LIVE
on the channel is a third, separate key — ``GROWTH_TWITTER_LIVE`` plus the X
credentials — read by the posting tool, never by this parser.)

This is deliberately the growth desk's *own* parser rather than a reuse of a
sibling's (``tools/backlog-burn`` / ``tools/backlog-groomer`` / ``tools/reeve``
each keep their own for the same reason): each parser's key set is closed on
purpose (unknown keys fail loudly — a typo must never be silently ignored),
so it can never carry another routine's keys, and teaching one parser
per-tool key sets would couple the routines' policies. The *format contract*
is identical — ``key: value``, ``#`` comments, colonless/unknown/duplicate
keys and malformed values all raise with ``path:lineno`` context, and
defaults are fail-safe (an absent ``enabled`` reads as off, an absent
``require_approval`` reads as required).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_PATH = ".github/growth-twitter.conf"

# The only keys the file may carry. Anything else is a typo and must fail.
_KNOWN_KEYS = (
    "enabled",
    "provider",
    "cadence",
    "max_posts_per_run",
    "require_approval",
)

_DEFAULTS = {
    "enabled": False,
    "provider": "zai",
    "cadence": "",
    "max_posts_per_run": 1,
    "require_approval": True,
}

_BOOL_KEYS = ("enabled", "require_approval")
_INT_KEYS = ("max_posts_per_run",)

# A raw 5-field cron literal: five whitespace-separated fields, none quoted.
_CRON_RE = re.compile(r"^\S+(?:\s+\S+){4}$")

_LINE_RE = re.compile(r"^([a-z_]+):\s*(.*?)\s*$")


class ConfigError(ValueError):
    """A malformed growth conf. The message carries ``path:lineno`` context."""


@dataclass(frozen=True)
class GrowthConfig:
    enabled: bool
    provider: str
    cadence: str
    max_posts_per_run: int
    require_approval: bool


def _parse_bool(raw: str, path: str, lineno: int, key: str) -> bool:
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise ConfigError(f"{path}:{lineno}: {key} must be 'true' or 'false', got {raw!r}")


def _parse_int(raw: str, path: str, lineno: int, key: str) -> int:
    if not raw.isdigit() or int(raw) < 1:
        raise ConfigError(f"{path}:{lineno}: {key} must be a positive integer, got {raw!r}")
    return int(raw)


def parse(text: str, path: str = DEFAULT_PATH) -> GrowthConfig:
    """Parse a growth conf's text. Unknown, duplicate, and colonless keys all
    raise :class:`ConfigError` with the offending line — a typo'd policy must
    fail the run loudly, never run on defaults nobody reviewed."""
    values: dict[str, object] = dict(_DEFAULTS)
    seen: set[str] = set()
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        # A '#' only opens a comment at line start (house format: a cron value
        # may legitimately never carry '#', so only whole-line comments exist).
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = _LINE_RE.match(stripped)
        if not m:
            raise ConfigError(f"{path}:{lineno}: not a 'key: value' line: {stripped!r}")
        key, value = m.group(1), m.group(2)
        if key not in _KNOWN_KEYS:
            raise ConfigError(
                f"{path}:{lineno}: unknown key {key!r} (known: {', '.join(_KNOWN_KEYS)})"
            )
        if key in seen:
            raise ConfigError(f"{path}:{lineno}: duplicate key {key!r}")
        seen.add(key)
        if key in _BOOL_KEYS:
            values[key] = _parse_bool(value, path, lineno, key)
        elif key in _INT_KEYS:
            values[key] = _parse_int(value, path, lineno, key)
        elif key == "cadence":
            if not _CRON_RE.match(value):
                raise ConfigError(
                    f"{path}:{lineno}: cadence must be a raw 5-field cron literal, got {value!r}"
                )
            values[key] = value
        else:
            if not value:
                raise ConfigError(f"{path}:{lineno}: {key} must not be empty")
            values[key] = value
    return GrowthConfig(**values)  # type: ignore[arg-type]


def load(path: str = DEFAULT_PATH) -> GrowthConfig:
    with open(path, encoding="utf-8") as fh:
        return parse(fh.read(), path)


def get(key: str, path: str = DEFAULT_PATH) -> str:
    """One key's value as the string the workflow's policy step consumes
    (booleans as ``true``/``false``, ints as decimal)."""
    if key not in _KNOWN_KEYS:
        raise ConfigError(f"unknown key {key!r} (known: {', '.join(_KNOWN_KEYS)})")
    cfg = load(path)
    value = getattr(cfg, key)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
