"""conf — the strict parser; .github/provenance.conf parses.

Owner: H6. One negative control per refusal rule (each names ``path:lineno``),
the committed conf's decision-9 values, the casefolded two-key arming, and the
watched workflows' existence on this tree.
"""

from __future__ import annotations

import re

import pytest

from conftest import REPO
from provenance import conf

CONF = REPO / ".github" / "provenance.conf"

BASE = """\
# a comment
enabled: true
cadence: 29 * * * *
watched_workflows: auto-review.yml, design-run.yml
snapshot_dir: audits/provenance-2026-10/rescue
snapshot_commit: 411a7565e1c6c8f2b96edf631286ceac798d7887
snapshot_manifest_sha256: c713379b96e22480ebf40d5046adcee63802de5f47b82e1b3fea5eb63f1151c7
"""


def _with(line: str, base: str = BASE) -> str:
    return base + line + "\n"


def _replace(key: str, value: str) -> str:
    out = [ln if not ln.startswith(f"{key}:") else f"{key}: {value}" for ln in BASE.splitlines()]
    return "\n".join(out) + "\n"


def test_committed_conf_parses_with_decision_9_values():
    """The committed conf parses: settle 6, max defer 24, cap 400, floor 500, 330 min with a 1 min derive reserve (2× the integration dry run's measured derive), since 2026-07-31, :29 hourly, 15 min, 90-day continuity horizon, the nine watched workflows, snapshot pr843 at audits/provenance-2026-10/rescue pinned to commit 411a7565… and manifest c713379b…."""
    c = conf.load(str(CONF))
    assert c.enabled is True
    assert (c.settle_hours, c.max_defer_hours, c.deploy_wait_hours) == (6, 24, 2)
    assert (c.scheduled_max_requests, c.rate_floor) == (400, 500)
    assert (c.dispatch_max_minutes, c.derive_reserve_minutes) == (330, 8)
    assert c.backfill_since == "2026-07-31"
    assert c.cadence == "29 * * * *"
    assert (c.ambiguity_window_minutes, c.edit_grace_seconds) == (15, 60)
    assert (c.receipt_lookback_hours, c.continuity_horizon_days) == (48, 90)
    assert c.watched_workflows == (
        "auto-review.yml", "backlog-burn.yml", "chunker.yml", "design-run.yml", "labeler.yml",
        "oracle.yml", "product-scout.yml", "spike-converter.yml", "wright.yml")
    assert c.snapshot_id == "pr843"
    assert c.snapshot_dir == "audits/provenance-2026-10/rescue"
    assert c.snapshot_commit == "411a7565e1c6c8f2b96edf631286ceac798d7887"
    assert c.snapshot_manifest_sha256 == (
        "c713379b96e22480ebf40d5046adcee63802de5f47b82e1b3fea5eb63f1151c7")
    # Every key of the closed set is a Config field, and the file sets every key explicitly
    # (the policy is reviewed in one place, never left to a default).
    assert set(conf.KEYS) == set(conf.Config.__dataclass_fields__)
    keys = [ln.split(":", 1)[0] for ln in CONF.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    assert sorted(keys) == sorted(conf.KEYS)


def test_minimal_conf_takes_the_documented_defaults():
    c = conf.parse(BASE, "t.conf")
    assert (c.settle_hours, c.max_defer_hours, c.deploy_wait_hours) == (6, 24, 2)
    assert (c.dispatch_max_minutes, c.derive_reserve_minutes, c.snapshot_id) == (330, 30, "pr843")
    assert conf.parse(BASE.replace("enabled: true\n", ""), "t.conf").enabled is False  # fail-safe


@pytest.mark.parametrize("text,lineno,pattern", [
    (_with("colonless line"), 8, "expected 'key: value'"),
    (_with("intent_window_runs: 20"), 8, "unknown key 'intent_window_runs'"),
    (_with("snapshot_ref: provenance-snapshot"), 8, "unknown key 'snapshot_ref'"),
    (_with("snapshot_path: audits/x"), 8, "unknown key 'snapshot_path'"),
    (_with("Enabled: true"), 8, "unknown key 'Enabled'"),
    (_with("enabled: false"), 8, "duplicate key 'enabled'"),
    (_with("settle_hours: 6.0"), 8, "no decimal point"),
    (_with("settle_hours: 1.5"), 8, "no decimal point"),
    (_with("settle_hours: -1"), 8, "non-negative integer"),
    (_with("settle_hours: six"), 8, "non-negative integer"),
    (_with("settle_hours: 0"), 8, "must be >= 1"),
    (_with("settle_hours:"), 8, "empty value"),
    (_with("enabled: yes", BASE.replace("enabled: true\n", "")), 7, "'enabled' must be"),
    (_replace("cadence", "hourly"), 3, "raw 5-field cron"),
    (_replace("cadence", "29 * * *"), 3, "raw 5-field cron"),
    (_replace("snapshot_dir", "../rescue"), 5, "relative POSIX path"),
    (_replace("snapshot_dir", "audits/../rescue"), 5, "relative POSIX path"),
    (_replace("snapshot_dir", "/audits/provenance-2026-10/rescue"), 5, "relative POSIX path"),
    (_replace("snapshot_dir", "audits\\rescue"), 5, "relative POSIX path"),
    (_replace("snapshot_commit", "411a7565e1c6c8f2b96edf631286ceac798d778"), 6, "40 lower-case hex"),
    (_replace("snapshot_commit", "411A7565E1C6C8F2B96EDF631286CEAC798D7887"), 6, "40 lower-case hex"),
    (_replace("snapshot_manifest_sha256", "c713379b"), 7, "64 lower-case hex"),
    (_replace("watched_workflows", "auto-review.yml, auto-review.yml"), 4, "twice"),
    (_replace("watched_workflows", "auto-review.yml, ../ci.yml"), 4, "not a workflow file name"),
    (_replace("watched_workflows", "auto-review.yaml"), 4, "not a workflow file name"),
    (_with("snapshot_id: 843"), 8, "pr<N>"),
    (_with("backfill_since: 2026-13-01"), 8, "backfill_since"),
    (_with("backfill_since: yesterday"), 8, "backfill_since"),
    (_with("derive_reserve_minutes: 330"), 8, "must be < 'dispatch_max_minutes'"),
    (_with("dispatch_max_minutes: 30"), 8, "must be < 'dispatch_max_minutes'"),
    (_with("max_defer_hours: 5"), 8, "must be >= 'settle_hours'"),
])
def test_unknown_duplicate_colonless_and_float_fail(text, lineno, pattern):
    """Each malformed line raises ConfError with path:lineno (one negative control per rule), including the retired keys intent_window_runs / snapshot_ref / snapshot_path (now unknown), a snapshot_dir with '..' or a leading '/', a 39-hex snapshot_commit and derive_reserve_minutes >= dispatch_max_minutes."""
    with pytest.raises(conf.ConfError) as exc:
        conf.parse(text, "t.conf")
    msg = str(exc.value)
    assert msg.startswith(f"t.conf:{lineno}: "), msg
    assert re.search(re.escape(pattern), msg), msg


@pytest.mark.parametrize("key", conf.REQUIRED)
def test_missing_required_key_fails(key):
    text = "\n".join(ln for ln in BASE.splitlines() if not ln.startswith(f"{key}:")) + "\n"
    with pytest.raises(conf.ConfError, match=f"t.conf: missing required key '{key}'"):
        conf.parse(text, "t.conf")


def test_the_base_fixture_itself_parses():
    """Positive control for the table above: every refusal is the injected line, not the base."""
    assert conf.parse(BASE, "t.conf").watched_workflows == ("auto-review.yml", "design-run.yml")
    assert conf.parse(_with("settle_hours: 07"), "t.conf").settle_hours == 7
    assert conf.parse(_with("backfill_since: 2026-08-01T06:00:00Z"), "t.conf").backfill_since == (
        "2026-08-01T06:00:00Z")


def test_load_reads_one_file_and_names_a_missing_one(tmp_path):
    p = tmp_path / "p.conf"
    p.write_text(BASE, encoding="utf-8")
    assert conf.load(str(p)).cadence == "29 * * * *"
    with pytest.raises(conf.ConfError, match="cannot read"):
        conf.load(str(tmp_path / "absent.conf"))


@pytest.mark.parametrize("enabled,variable,expected", [
    (True, "true", True), (True, "True", True), (True, "TRUE", True), (True, "tRuE", True),
    (False, "true", False), (False, "TRUE", False),
    (True, None, False), (True, "", False), (True, "false", False), (True, "1", False),
    (True, "yes", False), (True, " true", False), (True, "true ", False), (True, "truee", False),
    (False, None, False), (False, "", False),
])
def test_armed_two_key(enabled, variable, expected):
    """armed(True, v) for v in 'true', 'True', 'TRUE' (casefold, matching the YAML leg's case-insensitive ==); every other combination False (critique 20)."""
    assert conf.armed(enabled, variable) is expected


def test_watched_workflows_exist():
    """Every watched workflow file exists under .github/workflows/."""
    c = conf.load(str(CONF))
    missing = [w for w in c.watched_workflows if not (REPO / ".github" / "workflows" / w).is_file()]
    assert missing == []


def test_reeve_reads_backfill_since_with_the_same_grammar():
    """Round 2 (low): Reeve's provenance lens parses this conf's backfill_since itself (the tools stay
    independently installable). Its regex must be this parser's, or a valid YYYY-MM-DDTHH:MM:SSZ
    commit makes Reeve's armed gather fail daily — both detectors silently "not evaluated". Pinned
    from this side; scripts/ci-classify.sh re-runs this suite when Reeve's port changes."""
    import re

    from conftest import REPO
    from provenance import conf as conf_mod
    text = (REPO / "tools" / "reeve" / "src" / "reeve" / "provenance.py").read_text(encoding="utf-8")
    m = re.search(r'^_DATE_RE = re\.compile\(r"([^"]+)"\)$', text, re.MULTILINE)
    assert m, "tools/reeve/src/reeve/provenance.py lost _DATE_RE"
    assert m.group(1) == conf_mod._DATE_RE.pattern
