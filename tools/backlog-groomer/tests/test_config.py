"""Config parser tests — every rejection path fails loudly, defaults fail safe.

Same conventions as ``tools/backlog-burn/tests/test_config.py``: tmp files,
``pytest.raises(ValueError, match=...)`` per rejection, and one test that
loads the REAL committed conf asserting only well-formedness (never pinning
values, so tuning a threshold in a reviewed PR stays green).
"""

from __future__ import annotations

import pathlib
import re

import pytest

from backlog_groomer import config


def write(tmp_path, content: str) -> str:
    path = tmp_path / "groomer.conf"
    path.write_text(content, encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# Defaults: fail-safe and exactly the documented numbers
# ---------------------------------------------------------------------------

def test_defaults_are_the_documented_ones(tmp_path):
    cfg = config.load(write(tmp_path, "# nothing set\n"))
    assert cfg.enabled is False  # absent enabled never reads as "on"
    assert cfg.cadence == ""
    assert cfg.staleness_days == 14
    assert cfg.armed_stuck_days == 7
    assert cfg.oversized_stuck_days == 7
    assert cfg.dup_threshold == 0.6
    assert cfg.max_dup_pairs == 10


def test_full_file_parses(tmp_path):
    cfg = config.load(write(tmp_path, (
        "enabled: true\n"
        "cadence: 41 5 * * *\n"
        "staleness_days: 21\n"
        "armed_stuck_days: 3\n"
        "oversized_stuck_days: 5\n"
        "dup_threshold: 0.8\n"
        "max_dup_pairs: 5\n"
    )))
    assert cfg.enabled is True
    assert cfg.cadence == "41 5 * * *"
    assert cfg.staleness_days == 21
    assert cfg.dup_threshold == 0.8
    assert cfg.max_dup_pairs == 5


def test_comments_and_blank_lines_ignored(tmp_path):
    cfg = config.load(write(tmp_path, "\n# comment\n  # indented comment\nenabled: true\n"))
    assert cfg.enabled is True


# ---------------------------------------------------------------------------
# get(): plain-string rendering for the workflow
# ---------------------------------------------------------------------------

def test_get_renders_bool_as_lowercase_word(tmp_path):
    path = write(tmp_path, "enabled: true\n")
    assert config.get("enabled", path=path) == "true"


def test_get_renders_numbers_bare(tmp_path):
    path = write(tmp_path, "enabled: false\n")
    assert config.get("staleness_days", path=path) == "14"
    assert config.get("dup_threshold", path=path) == "0.6"


def test_get_unknown_key_raises(tmp_path):
    with pytest.raises(KeyError, match="unknown config key"):
        config.get("provider", path=write(tmp_path, "enabled: true\n"))


# ---------------------------------------------------------------------------
# Fail-loud rejections, each with path:lineno context
# ---------------------------------------------------------------------------

def test_colonless_line_raises(tmp_path):
    with pytest.raises(ValueError, match=r"groomer\.conf:1: expected 'key: value'"):
        config.load(write(tmp_path, "enabled true\n"))


def test_unknown_key_raises(tmp_path):
    with pytest.raises(ValueError, match="unknown key 'provider'"):
        config.load(write(tmp_path, "provider: zai\n"))


def test_duplicate_key_raises(tmp_path):
    with pytest.raises(ValueError, match="duplicate key 'enabled'"):
        config.load(write(tmp_path, "enabled: true\nenabled: false\n"))


def test_bad_bool_raises(tmp_path):
    with pytest.raises(ValueError, match="'enabled' must be 'true' or 'false'"):
        config.load(write(tmp_path, "enabled: yes\n"))


@pytest.mark.parametrize("value", ["0", "-3", "x", "2.5"])
def test_bad_day_threshold_raises(tmp_path, value):
    with pytest.raises(ValueError, match="'staleness_days' must be a positive integer"):
        config.load(write(tmp_path, f"staleness_days: {value}\n"))


@pytest.mark.parametrize("value", ["0", "1.5", "-0.2", "x"])
def test_bad_dup_threshold_raises(tmp_path, value):
    with pytest.raises(ValueError, match="'dup_threshold' must be"):
        config.load(write(tmp_path, f"dup_threshold: {value}\n"))


def test_bad_max_dup_pairs_raises(tmp_path):
    with pytest.raises(ValueError, match="'max_dup_pairs' must be a positive integer"):
        config.load(write(tmp_path, "max_dup_pairs: 0\n"))


def test_bad_cadence_raises(tmp_path):
    with pytest.raises(ValueError, match="'cadence' must be a preset name"):
        config.load(write(tmp_path, "cadence: whenever\n"))


def test_cadence_accepts_preset_and_raw_cron(tmp_path):
    assert config.load(write(tmp_path, "cadence: daily\n")).cadence == "daily"
    assert config.load(write(tmp_path, "cadence: 41 5 * * *\n")).cadence == "41 5 * * *"


# ---------------------------------------------------------------------------
# armed(): the full 2x2 matrix (AC3), plus the strictness edges
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("variable,conf_enabled,expected", [
    ("true", "true", True),    # both keys agree → run
    ("true", "false", False),  # armed but disabled in git → inert
    ("false", "true", False),  # enabled in git but disarmed → inert
    ("false", "false", False), # both off → inert
])
def test_armed_matrix(variable, conf_enabled, expected):
    assert config.armed(variable, conf_enabled) is expected


@pytest.mark.parametrize("value", [None, "", "1", "yes", "TRUE?"])
def test_armed_only_the_word_true_arms(value):
    assert config.armed(value, "true") is False


def test_armed_tolerates_case_and_whitespace():
    assert config.armed(" TRUE ", "True") is True


# ---------------------------------------------------------------------------
# The real committed conf
# ---------------------------------------------------------------------------

def test_committed_conf_is_well_formed():
    # Deliberately does not pin values: flipping a threshold or `enabled` in
    # a reviewed PR must stay green. What may never regress silently is the
    # file parsing at all.
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    config.load(str(repo_root / config.DEFAULT_PATH))


def test_committed_cadence_matches_workflow_cron():
    # Actions cannot read a file for on.schedule, so the cadence lives twice
    # by necessity — the conf's `cadence:` key and the workflow's `- cron:`
    # literal. Both files say they must stay identical; this pins it so the
    # duplication cannot drift. Skipped only if the conf leaves cadence
    # unset (workflow literal authoritative by documented contract).
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    cadence = config.load(str(repo_root / config.DEFAULT_PATH)).cadence
    if not cadence:
        return
    workflow = (repo_root / ".github/workflows/backlog-groomer.yml").read_text(
        encoding="utf-8"
    )
    crons = re.findall(r"^\s*- cron:\s*'([^']*)'", workflow, re.MULTILINE)
    resolved = config.CADENCE_PRESETS.get(cadence, cadence)
    assert crons == [resolved]
