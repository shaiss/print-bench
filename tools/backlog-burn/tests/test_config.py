"""Tests for the committed policy parser.

Strict parsing is the point: a typo'd key or a bad value must fail loudly, so
the routine never runs on a policy nobody wrote. Each guard has a
negative-control assertion.
"""

from __future__ import annotations

import pytest

from backlog_burn import config as cfg


def write(tmp_path, text):
    p = tmp_path / "backlog-burn.conf"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_parses_enabled_and_label(tmp_path):
    path = write(tmp_path, "enabled: true\nlabel: autonomy-ok\n")
    c = cfg.load(path)
    assert c.enabled is True
    assert c.label == "autonomy-ok"


def test_provider_defaults_to_anthropic(tmp_path):
    path = write(tmp_path, "enabled: true\n")
    assert cfg.load(path).provider == "anthropic"


def test_provider_zai(tmp_path):
    path = write(tmp_path, "enabled: true\nprovider: zai\n")
    assert cfg.load(path).provider == "zai"
    assert cfg.get("provider", path) == "zai"


def test_unknown_provider_fails_loudly(tmp_path):
    path = write(tmp_path, "provider: openai\n")
    with pytest.raises(ValueError, match="unknown provider 'openai'"):
        cfg.load(path)


def test_enabled_false(tmp_path):
    path = write(tmp_path, "enabled: false\nlabel: autonomy-ok\n")
    assert cfg.load(path).enabled is False


def test_comments_and_blank_lines_ignored(tmp_path):
    path = write(tmp_path, "# a comment\n\n  # indented comment\nenabled: true\n\nlabel: ship-me\n")
    c = cfg.load(path)
    assert c.enabled is True and c.label == "ship-me"


def test_missing_enabled_defaults_off(tmp_path):
    # Fail-safe: an incomplete file never reads as "on".
    path = write(tmp_path, "label: autonomy-ok\n")
    assert cfg.load(path).enabled is False


def test_unknown_key_fails_loudly(tmp_path):
    path = write(tmp_path, "enabled: true\nenabledd: true\n")
    with pytest.raises(ValueError, match="unknown key 'enabledd'"):
        cfg.load(path)


def test_duplicate_key_fails(tmp_path):
    path = write(tmp_path, "enabled: true\nenabled: false\n")
    with pytest.raises(ValueError, match="duplicate key 'enabled'"):
        cfg.load(path)


def test_bad_bool_fails(tmp_path):
    path = write(tmp_path, "enabled: yes\n")
    with pytest.raises(ValueError, match="must be 'true' or 'false'"):
        cfg.load(path)


def test_empty_label_fails(tmp_path):
    path = write(tmp_path, "enabled: true\nlabel:\n")
    with pytest.raises(ValueError, match="'label' must not be empty"):
        cfg.load(path)


def test_missing_colon_fails(tmp_path):
    path = write(tmp_path, "enabled true\n")
    with pytest.raises(ValueError, match="expected 'key: value'"):
        cfg.load(path)


def test_get_renders_strings(tmp_path):
    path = write(tmp_path, "enabled: true\nlabel: autonomy-ok\n")
    assert cfg.get("enabled", path) == "true"
    assert cfg.get("label", path) == "autonomy-ok"
    assert cfg.get("enabled", write(tmp_path, "enabled: false\n")) == "false"


def test_get_unknown_key_raises(tmp_path):
    path = write(tmp_path, "enabled: true\n")
    with pytest.raises(KeyError):
        cfg.get("notakey", path)


def test_committed_repo_config_is_wellformed():
    # The real committed file must parse and be well-formed — but deliberately
    # do NOT pin its values: flipping `enabled` or renaming `label` in a
    # reviewed PR is the intended toggle and must stay green, while a malformed
    # file still fails loudly (the guards above).
    c = cfg.load(".github/backlog-burn.conf")
    assert isinstance(c.enabled, bool)
    assert isinstance(c.label, str) and c.label.strip()
    assert c.provider in cfg.KNOWN_PROVIDERS
    # cadence may be absent (empty string) or a known preset or a cron literal
    assert isinstance(c.cadence, str)


# ---------------------------------------------------------------------------
# cadence key
# ---------------------------------------------------------------------------

def test_cadence_preset_accepted(tmp_path):
    for preset in cfg.CADENCE_PRESETS:
        path = write(tmp_path, f"cadence: {preset}\n")
        c = cfg.load(path)
        assert c.cadence == preset


def test_cadence_raw_cron_accepted(tmp_path):
    path = write(tmp_path, "cadence: 17 0,6,12,18 * * *\n")
    c = cfg.load(path)
    assert c.cadence == "17 0,6,12,18 * * *"


def test_cadence_hourly_preset_maps_to_hourly_cron():
    # 'hourly' is a first-class preset, firing at :17 past every hour like the
    # other presets (an off-peak minute, not :00). It exists so a maintainer can
    # type `hourly` instead of hand-writing the raw cron.
    assert cfg.CADENCE_PRESETS["hourly"] == "17 * * * *"


def test_cadence_bad_value_fails(tmp_path):
    path = write(tmp_path, "cadence: everyhour\n")
    with pytest.raises(ValueError, match="'cadence' must be a preset"):
        cfg.load(path)


def test_cadence_defaults_to_empty(tmp_path):
    path = write(tmp_path, "enabled: true\n")
    assert cfg.load(path).cadence == ""


def test_get_cadence(tmp_path):
    path = write(tmp_path, "cadence: weekly\n")
    assert cfg.get("cadence", path) == "weekly"


# ---------------------------------------------------------------------------
# set_value — round-trip write
# ---------------------------------------------------------------------------

def test_set_value_updates_existing_key(tmp_path):
    path = write(tmp_path, "enabled: true\nlabel: autonomy-ok\n")
    cfg.set_value("enabled", "false", path=path)
    assert cfg.load(path).enabled is False
    # other key preserved
    assert cfg.load(path).label == "autonomy-ok"


def test_set_value_appends_missing_key(tmp_path):
    path = write(tmp_path, "enabled: true\n")
    cfg.set_value("label", "my-label", path=path)
    assert cfg.load(path).label == "my-label"


def test_set_value_unknown_key_rejected(tmp_path):
    path = write(tmp_path, "enabled: true\n")
    with pytest.raises(ValueError, match="unknown config key"):
        cfg.set_value("notakey", "x", path=path)


def test_set_value_bad_bool_rejected(tmp_path):
    path = write(tmp_path, "enabled: true\n")
    with pytest.raises(ValueError, match="must be 'true' or 'false'"):
        cfg.set_value("enabled", "yes", path=path)


def test_set_value_empty_label_rejected(tmp_path):
    path = write(tmp_path, "label: autonomy-ok\n")
    with pytest.raises(ValueError, match="'label' must not be empty"):
        cfg.set_value("label", "", path=path)


def test_set_value_cadence_preset_returns_cron(tmp_path):
    path = write(tmp_path, "cadence: daily\n")
    cron = cfg.set_value("cadence", "weekly", path=path)
    assert cron == cfg.CADENCE_PRESETS["weekly"]
    assert cfg.load(path).cadence == "weekly"


def test_set_value_cadence_raw_cron(tmp_path):
    path = write(tmp_path, "cadence: daily\n")
    raw = "5 */4 * * *"
    cron = cfg.set_value("cadence", raw, path=path)
    assert cron == raw
    assert cfg.load(path).cadence == raw


def test_set_value_cadence_hourly(tmp_path):
    path = write(tmp_path, "cadence: 4x\n")
    cron = cfg.set_value("cadence", "hourly", path=path)
    assert cron == "17 * * * *"
    assert cfg.load(path).cadence == "hourly"


def test_set_value_bad_cadence_rejected(tmp_path):
    path = write(tmp_path, "cadence: daily\n")
    # 'biweekly' is not a preset and not a 5-field cron — must be refused.
    with pytest.raises(ValueError, match="'cadence' must be a preset"):
        cfg.set_value("cadence", "biweekly", path=path)


def test_set_value_preserves_comments(tmp_path):
    path = write(tmp_path, "# header\nenabled: true\n# footer\n")
    cfg.set_value("enabled", "false", path=path)
    content = (tmp_path / "backlog-burn.conf").read_text()
    assert "# header" in content
    assert "# footer" in content


# ---------------------------------------------------------------------------
# patch_workflow_cron
# ---------------------------------------------------------------------------

def test_patch_workflow_cron(tmp_path):
    wf = tmp_path / "backlog-burn.yml"
    wf.write_text(
        "on:\n  schedule:\n    - cron: '17 6 * * 1'\njobs:\n  burn:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    cfg.patch_workflow_cron("17 0,6,12,18 * * *", path=str(wf))
    assert "- cron: '17 0,6,12,18 * * *'" in wf.read_text()


def test_patch_workflow_cron_no_cron_line_raises(tmp_path):
    wf = tmp_path / "backlog-burn.yml"
    wf.write_text("on:\n  push:\njobs:\n  burn:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
    with pytest.raises(ValueError, match="could not find"):
        cfg.patch_workflow_cron("17 6 * * 1", path=str(wf))
