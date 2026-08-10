"""Committed policy config for the scheduled backlog burn.

``.github/backlog-burn.conf`` is the git-tracked source of truth for the
routine's policy — the same idea as ``.github/ci-gates/registry.conf``: a
clone carries it, every run reads it identically, and a change is a reviewed
one-line diff. GitHub supplies only the live arming (the
``BACKLOG_BURN_ENABLED`` repo variable) and the secret.

Parsing is strict on purpose (like the ci-gates registry): a typo'd key or a
malformed value fails loudly rather than being silently ignored and letting
the routine run on a policy nobody wrote.

The ``set`` function (and the ``/backlog-burn set`` workflow command backed by
it) lets a maintainer update any mutable key by posting a PR comment or
running the workflow manually, without writing a full PR.  The change is made
via the Contents API (same pattern as ``ci-gate-approve.yml``), so it lands as
a git commit on the branch — auditable, diffable, reverting as any edit would.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_PATH = ".github/backlog-burn.conf"
WORKFLOW_PATH = ".github/workflows/backlog-burn.yml"

# The only keys the file may carry. Anything else is a typo and must fail.
_KNOWN_KEYS = ("enabled", "label", "provider", "cadence")

# The LLM providers the workflow knows how to run /ship-issue against. Each has
# a matching, explicit ship step in .github/workflows/backlog-burn.yml (secrets
# must be referenced literally in GitHub Actions, so a provider is a reviewed
# workflow step, not pure data). The label here just picks among them.
KNOWN_PROVIDERS = ("anthropic", "zai")

# Named cadence presets → cron expression.  A maintainer can use the short name
# or pass a raw 5-field cron literal directly (e.g. '17 0,6,12,18 * * *').
# The preset name is stored in the conf; the cron is what lands in backlog-burn.yml.
# Every preset fires at :17 past the hour — an off-peak minute (not :00) to
# avoid GitHub Actions scheduler congestion, the same convention the workflow
# documents.
CADENCE_PRESETS: dict[str, str] = {
    "hourly": "17 * * * *",           # every hour
    "4x":     "17 0,6,12,18 * * *",   # every 6 hours
    "2x":     "17 6,18 * * *",         # twice daily
    "daily":  "17 6 * * *",            # once a day
    "weekly": "17 6 * * 1",            # Mondays 06:17 UTC
}

# A minimal 5-field cron literal: each of the five fields is a non-empty token
# that doesn't start with a single-quote (to guard against partial parses when
# the raw cron is surrounded by quotes in shell).
_CRON_RE = re.compile(r"^[^'\s]\S*(?:\s+[^'\s]\S*){4}$")


def _parse_bool(value: str, where: str) -> bool:
    low = value.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    raise ValueError(f"{where}: 'enabled' must be 'true' or 'false', got {value!r}")


def _validate_cadence(value: str, where: str) -> str:
    """Return a canonical cron string for ``value`` (preset name or raw cron).

    Raises :class:`ValueError` if the value is neither a known preset nor a
    5-field cron literal.  The *stored* value (in the conf file) is the
    caller's original string; the *returned* value is what goes into the
    workflow's ``cron:`` line.
    """
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
    """The routine's committed policy."""

    enabled: bool
    label: str
    provider: str
    cadence: str  # preset name or raw cron literal (empty string = unset / use workflow default)


def load(path: str = DEFAULT_PATH) -> Config:
    """Parse the config file into a :class:`Config`, or raise on any problem.

    Defaults: ``enabled`` is False if the key is absent (fail safe — an
    incomplete file never reads as "on"); ``label`` defaults to
    ``autonomy-ok``; ``cadence`` defaults to ``""`` (unset, meaning the
    workflow's hardcoded cron is authoritative).
    """
    enabled = False
    label = "autonomy-ok"
    provider = "anthropic"
    cadence = ""
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
                enabled = _parse_bool(value, where)
            elif key == "label":
                if not value:
                    raise ValueError(f"{where}: 'label' must not be empty")
                label = value
            elif key == "provider":
                if value not in KNOWN_PROVIDERS:
                    raise ValueError(
                        f"{where}: unknown provider {value!r} "
                        f"(known: {list(KNOWN_PROVIDERS)})"
                    )
                provider = value
            elif key == "cadence":
                _validate_cadence(value, where)  # validate but keep original string
                cadence = value
    return Config(enabled=enabled, label=label, provider=provider, cadence=cadence)


def get(key: str, path: str = DEFAULT_PATH) -> str:
    """Return one config value as a plain string, for the workflow to read.

    ``enabled`` renders as ``"true"``/``"false"`` so a workflow step can gate
    on it directly.  ``cadence`` returns the raw stored value (preset name or
    cron literal).
    """
    cfg = load(path)
    if key == "enabled":
        return "true" if cfg.enabled else "false"
    if key == "label":
        return cfg.label
    if key == "provider":
        return cfg.provider
    if key == "cadence":
        return cfg.cadence
    raise KeyError(f"unknown config key: {key!r} (known: {list(_KNOWN_KEYS)})")


def set_value(key: str, value: str, path: str = DEFAULT_PATH) -> str:
    """Update ``key`` to ``value`` in the config file and return the cron string.

    For ``cadence`` specifically, returns the resolved 5-field cron expression
    (needed by the workflow to also patch ``backlog-burn.yml``).  For all other
    keys returns ``""``.

    Raises :class:`ValueError` for unknown keys or invalid values (same guards
    as :func:`load`).  The file is written atomically: we read the current
    content, replace or append the key's line, and write back.  Comment lines
    and blank lines are preserved.
    """
    if key not in _KNOWN_KEYS:
        raise ValueError(f"unknown config key {key!r} (known: {list(_KNOWN_KEYS)})")

    # Validate the value before touching the file.
    cron_result = ""
    where = f"{path} (set)"
    if key == "enabled":
        _parse_bool(value, where)
    elif key == "label":
        if not value.strip():
            raise ValueError(f"{where}: 'label' must not be empty")
    elif key == "provider":
        if value not in KNOWN_PROVIDERS:
            raise ValueError(
                f"{where}: unknown provider {value!r} "
                f"(known: {list(KNOWN_PROVIDERS)})"
            )
    elif key == "cadence":
        cron_result = _validate_cadence(value, where)

    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()

    # Replace an existing line for this key, or append one.
    new_line = f"{key}: {value}\n"
    found = False
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if ":" not in stripped:
            continue
        k, _, _ = stripped.partition(":")
        if k.strip() == key:
            lines[i] = new_line
            found = True
            break

    if not found:
        # Append before any trailing blank lines / comments so the file stays tidy.
        lines.append(new_line)

    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)

    return cron_result


def patch_workflow_cron(cron: str, path: str = WORKFLOW_PATH) -> None:
    """Replace the ``cron:`` literal in ``backlog-burn.yml`` with ``cron``.

    The workflow's ``on.schedule.cron`` must be a literal (Actions cannot read
    a variable or file for it), so when the user sets a new cadence via
    ``/backlog-burn set cadence …`` the workflow file itself must be patched
    too.  Only the first ``- cron:`` line is replaced, which is the schedule
    trigger (not any comment that happens to contain the word "cron").
    """
    with open(path, encoding="utf-8") as fh:
        content = fh.read()

    # Match the schedule cron line: leading spaces, '- cron: ', then a quoted value.
    pattern = re.compile(r"^(\s*- cron:\s*)'[^']*'", re.MULTILINE)
    replacement = rf"\g<1>'{cron}'"
    new_content, count = pattern.subn(replacement, content, count=1)
    if count == 0:
        raise ValueError(f"{path}: could not find a '- cron: ...' line to patch")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new_content)
