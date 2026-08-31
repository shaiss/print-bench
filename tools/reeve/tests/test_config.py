"""Config parser tests — defaults, rejections, the 2x2 arming matrix, and the
committed conf. Conventions mirror tools/backlog-groomer/tests/test_config.py:
tmp files, one ``pytest.raises(..., match=...)`` per rejection path.
"""

import pathlib
import re

import pytest

from reeve import config


def _write(tmp_path, text):
    p = tmp_path / "reeve.conf"
    p.write_text(text, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# Defaults and a full parse
# ---------------------------------------------------------------------------

def test_defaults_are_fail_safe():
    cfg = config.Config()
    assert cfg.enabled is False        # an incomplete file never reads as "on"
    assert cfg.cadence == ""
    assert cfg.greenlight is False     # the loop ships disarmed (#441)
    assert cfg.greenlight_cap == 6
    assert cfg.provider == "zai"       # the greenlight step's provider (#443)
    assert cfg.low_headroom_pct == 15.0
    assert cfg.score_drop == 3
    assert cfg.score_floor == 80.0
    assert cfg.walltime_ratio == 1.5
    assert cfg.walltime_min_seconds == 30
    assert cfg.routine_dead_runs == 3
    assert cfg.lock_leak_hours == 2.0


def test_full_file_parses(tmp_path):
    cfg = config.load(_write(tmp_path, """
        # a comment
        enabled: true
        cadence: 53 5 * * *
        greenlight: true
        greenlight_cap: 3
        provider: anthropic
        low_headroom_pct: 20
        score_drop: 5
        score_floor: 75
        walltime_ratio: 2.0
        walltime_min_seconds: 60
        routine_dead_runs: 5
        lock_leak_hours: 4.5
    """.replace("        ", "")))
    assert cfg.enabled is True
    assert cfg.cadence == "53 5 * * *"
    assert cfg.greenlight is True
    assert cfg.greenlight_cap == 3
    assert cfg.provider == "anthropic"
    assert cfg.low_headroom_pct == 20.0
    assert cfg.score_drop == 5
    assert cfg.score_floor == 75.0
    assert cfg.walltime_ratio == 2.0
    assert cfg.walltime_min_seconds == 60
    assert cfg.routine_dead_runs == 5
    assert cfg.lock_leak_hours == 4.5


def test_comments_and_blank_lines_ignored(tmp_path):
    cfg = config.load(_write(tmp_path, "\n# only a comment\n\nenabled: false\n"))
    assert cfg.enabled is False


def test_cadence_preset_kept_as_written(tmp_path):
    # A preset validates but the original string is stored (the workflow
    # cron is authoritative; the conf just records intent).
    cfg = config.load(_write(tmp_path, "cadence: daily\n"))
    assert cfg.cadence == "daily"


# ---------------------------------------------------------------------------
# get(): string rendering for the workflow
# ---------------------------------------------------------------------------

def test_get_renders_bool_as_word_and_numbers_bare(tmp_path):
    path = _write(tmp_path, "enabled: true\nscore_drop: 4\nwalltime_ratio: 1.5\n")
    assert config.get("enabled", path) == "true"
    assert config.get("score_drop", path) == "4"
    assert config.get("walltime_ratio", path) == "1.5"


def test_get_unknown_key_raises(tmp_path):
    path = _write(tmp_path, "enabled: true\n")
    with pytest.raises(KeyError, match="unknown config key"):
        config.get("nope", path)


# ---------------------------------------------------------------------------
# Rejections — one per path, fail-loud with path:lineno context
# ---------------------------------------------------------------------------

def test_colonless_line_raises(tmp_path):
    with pytest.raises(ValueError, match="expected 'key: value'"):
        config.load(_write(tmp_path, "enabled true\n"))


def test_unknown_key_raises(tmp_path):
    with pytest.raises(ValueError, match="unknown key 'stale_days'"):
        config.load(_write(tmp_path, "stale_days: 5\n"))


def test_duplicate_key_raises(tmp_path):
    with pytest.raises(ValueError, match="duplicate key 'enabled'"):
        config.load(_write(tmp_path, "enabled: true\nenabled: false\n"))


def test_bad_bool_raises(tmp_path):
    with pytest.raises(ValueError, match="'enabled' must be 'true' or 'false'"):
        config.load(_write(tmp_path, "enabled: yes\n"))


# ---------------------------------------------------------------------------
# The greenlight loop keys (#296 stage 2, vocabulary landed in #441) —
# optional with built-in defaults, fail-loud on every failure mode
# ---------------------------------------------------------------------------

def test_greenlight_keys_default_when_absent(tmp_path):
    # The low_headroom_pct pattern: a conf without the keys parses and the
    # built-in defaults apply, so the reporter behaves identically (the loop
    # ships disarmed even for a clone that never carries the keys).
    cfg = config.load(_write(tmp_path, "enabled: true\n"))
    assert cfg.greenlight is False
    assert cfg.greenlight_cap == 6


def test_greenlight_keys_parse_when_present(tmp_path):
    cfg = config.load(_write(tmp_path, "greenlight: true\ngreenlight_cap: 3\n"))
    assert cfg.greenlight is True
    assert cfg.greenlight_cap == 3


def test_get_renders_greenlight_keys(tmp_path):
    path = _write(tmp_path, "greenlight: false\ngreenlight_cap: 6\n")
    assert config.get("greenlight", path) == "false"
    assert config.get("greenlight_cap", path) == "6"


def test_greenlight_typo_is_an_unknown_key(tmp_path):
    # The keys joined the closed set, so only their exact names parse — a
    # look-alike must still fail loudly rather than read as a synonym.
    with pytest.raises(ValueError, match="unknown key 'greenlight_enabled'"):
        config.load(_write(tmp_path, "greenlight_enabled: true\n"))


def test_bad_greenlight_bool_raises(tmp_path):
    with pytest.raises(ValueError, match="'greenlight' must be 'true' or 'false'"):
        config.load(_write(tmp_path, "greenlight: maybe\n"))


@pytest.mark.parametrize("bad", ["0", "-3", "x", "2.5"])
def test_bad_greenlight_cap_raises(tmp_path, bad):
    with pytest.raises(ValueError, match="'greenlight_cap' must be a positive integer"):
        config.load(_write(tmp_path, f"greenlight_cap: {bad}\n"))


def test_duplicate_greenlight_raises(tmp_path):
    with pytest.raises(ValueError, match="duplicate key 'greenlight'"):
        config.load(_write(tmp_path, "greenlight: false\ngreenlight: true\n"))


def test_duplicate_greenlight_cap_raises(tmp_path):
    with pytest.raises(ValueError, match="duplicate key 'greenlight_cap'"):
        config.load(_write(tmp_path, "greenlight_cap: 6\ngreenlight_cap: 3\n"))


# The greenlight step's provider key (#443) — picks the ship step in reeve.yml;
# closed set, fail-safe default, fail-loud on every failure mode.

def test_provider_defaults_when_absent(tmp_path):
    # A conf without the key parses and the servable default applies, so the
    # greenlight job can never fall through to a silently-wrong endpoint.
    cfg = config.load(_write(tmp_path, "enabled: true\n"))
    assert cfg.provider == "zai"


def test_provider_parses_each_known_value(tmp_path):
    assert config.load(_write(tmp_path, "provider: zai\n")).provider == "zai"
    assert config.load(_write(tmp_path, "provider: anthropic\n")).provider == "anthropic"


def test_get_renders_provider_as_a_plain_string(tmp_path):
    assert config.get("provider", _write(tmp_path, "provider: zai\n")) == "zai"


@pytest.mark.parametrize("bad", ["GLM", "z.ai", "claude", ""])
def test_unknown_provider_raises(tmp_path, bad):
    # A typo'd provider would select no ship step at all — it must fail here.
    with pytest.raises(ValueError, match="'provider' must be one of"):
        config.load(_write(tmp_path, f"provider: {bad}\n"))


def test_duplicate_provider_raises(tmp_path):
    with pytest.raises(ValueError, match="duplicate key 'provider'"):
        config.load(_write(tmp_path, "provider: zai\nprovider: anthropic\n"))


@pytest.mark.parametrize("bad", ["0", "-3", "x", "2.5"])
def test_bad_positive_int_raises(tmp_path, bad):
    with pytest.raises(ValueError, match="must be a positive integer"):
        config.load(_write(tmp_path, f"score_drop: {bad}\n"))


@pytest.mark.parametrize("bad", ["-1", "101", "x"])
def test_bad_pct_raises(tmp_path, bad):
    with pytest.raises(ValueError, match=r"\[0, 100\]"):
        config.load(_write(tmp_path, f"low_headroom_pct: {bad}\n"))


@pytest.mark.parametrize("bad", ["1", "0.5", "-2", "x", "nan", "inf", "1e999"])
def test_bad_ratio_raises(tmp_path, bad):
    # nan/inf/1e999 must be rejected too — a bare `<= 1` guard would let them
    # through (`nan <= 1` and `inf <= 1` are both False) and silently disable
    # the wall-time detector.
    with pytest.raises(ValueError, match="'walltime_ratio' must be"):
        config.load(_write(tmp_path, f"walltime_ratio: {bad}\n"))


def test_bad_cadence_raises(tmp_path):
    with pytest.raises(ValueError, match="'cadence' must be"):
        config.load(_write(tmp_path, "cadence: not a cron\n"))


@pytest.mark.parametrize("bad", ["0", "-1", "x", "2.5"])
def test_bad_routine_dead_runs_raises(tmp_path, bad):
    with pytest.raises(ValueError, match="'routine_dead_runs' must be a positive integer"):
        config.load(_write(tmp_path, f"routine_dead_runs: {bad}\n"))


def test_routine_dead_runs_capped_at_the_fetch_window(tmp_path):
    # github.py fetches only 10 completed runs per workflow; a wider window
    # could never fill and the detector would silently stop firing.
    cfg = config.load(_write(tmp_path, "routine_dead_runs: 10\n"))
    assert cfg.routine_dead_runs == 10
    with pytest.raises(ValueError, match="'routine_dead_runs' must be ≤ 10"):
        config.load(_write(tmp_path, "routine_dead_runs: 11\n"))


@pytest.mark.parametrize("bad", ["0", "-2", "x", "nan", "inf", "1e999"])
def test_bad_lock_leak_hours_raises(tmp_path, bad):
    # nan/inf/1e999 must be rejected too — every age comparison against nan is
    # False, so a non-finite threshold would silently disable the detector.
    with pytest.raises(ValueError, match="'lock_leak_hours' must be"):
        config.load(_write(tmp_path, f"lock_leak_hours: {bad}\n"))


def test_lock_leak_hours_accepts_a_fraction(tmp_path):
    assert config.load(_write(tmp_path, "lock_leak_hours: 0.5\n")).lock_leak_hours == 0.5


# ---------------------------------------------------------------------------
# The two-key arming decision — the full 2x2 plus strictness edges
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("variable,conf_enabled,expected", [
    ("true", "true", True),
    ("true", "false", False),
    ("false", "true", False),
    ("false", "false", False),
])
def test_armed_matrix(variable, conf_enabled, expected):
    assert config.armed(variable, conf_enabled) is expected


@pytest.mark.parametrize("value", [None, "", "1", "yes", "TRUE?"])
def test_armed_only_the_word_true(value):
    # A non-"true" value never arms a key — a typo can't arm the routine.
    assert config.armed(value, "true") is False
    assert config.armed("true", value) is False


@pytest.mark.parametrize("value", [" TRUE ", "True", "true"])
def test_armed_true_is_case_and_space_insensitive(value):
    assert config.armed(value, value) is True


# ---------------------------------------------------------------------------
# The real committed conf
# ---------------------------------------------------------------------------

def test_committed_conf_is_well_formed():
    # Deliberately does not pin values: flipping a threshold or `enabled` in a
    # reviewed PR must stay green. What may never regress silently is the file
    # parsing at all.
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    config.load(str(repo_root / config.DEFAULT_PATH))


def test_committed_cadence_matches_workflow_cron():
    # Actions cannot read a file for on.schedule, so the cadence lives twice by
    # necessity — the conf's `cadence:` key and the workflow's `- cron:`
    # literal. This pins them identical so the duplication cannot drift.
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    cadence = config.load(str(repo_root / config.DEFAULT_PATH)).cadence
    if not cadence:
        return
    workflow = (repo_root / ".github/workflows/reeve.yml").read_text(encoding="utf-8")
    crons = re.findall(r"^\s*- cron:\s*'([^']*)'", workflow, re.MULTILINE)
    resolved = config.CADENCE_PRESETS.get(cadence, cadence)
    assert crons == [resolved]
