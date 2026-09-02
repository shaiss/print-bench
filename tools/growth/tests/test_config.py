"""The strict conf parser: a positive case and a negative control per rule."""

import pytest

from growth import config

GOOD = """\
# comment
enabled: true
provider: zai
cadence: 19 7 * * *
max_posts_per_run: 1
max_posts_per_day: 2
require_approval: true
"""


def test_good_conf_parses():
    cfg = config.parse(GOOD, "test.conf")
    assert cfg.enabled is True
    assert cfg.provider == "zai"
    assert cfg.cadence == "19 7 * * *"
    assert cfg.max_posts_per_run == 1
    assert cfg.max_posts_per_day == 2
    assert cfg.require_approval is True


def test_defaults_are_fail_safe():
    cfg = config.parse("", "empty.conf")
    assert cfg.enabled is False, "an absent 'enabled' must read as off"
    assert cfg.require_approval is True, "an absent approval rule must read as required"
    assert cfg.max_posts_per_run == 1
    assert cfg.max_posts_per_day == 2, "the per-day cap defaults to 2"


def test_unknown_key_fails_loudly():
    with pytest.raises(config.ConfigError, match="unknown key"):
        config.parse("enabbled: true\n", "t.conf")


def test_duplicate_key_fails():
    with pytest.raises(config.ConfigError, match="duplicate"):
        config.parse("enabled: true\nenabled: false\n", "t.conf")


def test_colonless_line_fails():
    with pytest.raises(config.ConfigError, match="key: value"):
        config.parse("enabled true\n", "t.conf")


def test_bad_bool_fails():
    with pytest.raises(config.ConfigError, match="'true' or 'false'"):
        config.parse("enabled: yes\n", "t.conf")


def test_bad_int_fails():
    with pytest.raises(config.ConfigError, match="positive integer"):
        config.parse("max_posts_per_run: 0\n", "t.conf")


def test_bad_cadence_fails():
    with pytest.raises(config.ConfigError, match="5-field cron"):
        config.parse("cadence: daily\n", "t.conf")


def test_get_renders_workflow_strings(tmp_path):
    p = tmp_path / "g.conf"
    p.write_text(GOOD)
    assert config.get("enabled", str(p)) == "true"
    assert config.get("provider", str(p)) == "zai"
    assert config.get("max_posts_per_run", str(p)) == "1"
    assert config.get("max_posts_per_day", str(p)) == "2"
    with pytest.raises(config.ConfigError, match="unknown key"):
        config.get("nope", str(p))
