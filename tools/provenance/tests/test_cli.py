"""cli — argparse, input validation (scaffold-implemented), mode orchestration.

Owner: H1. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_harvest_dry_run_writes_plan_not_pushes():
    """harvest --dry-run over a temp repo + FakeGitHub writes plan.json, sets evidence_changed/site_changed false in --gh-output and calls no push."""


@pytest.mark.skip(reason="builder: implement")
def test_budget_stop_exits_zero():
    """A BudgetExhausted during harvest exits 0 with a ::notice:: and resumable cursors in the planned state.json."""


@pytest.mark.skip(reason="builder: implement")
def test_foreign_tip_exit_3():
    """A foreign evidence tip: exit 3, ::error::, nothing planned."""


@pytest.mark.skip(reason="builder: implement")
def test_publish_rechecks_remote_tip():
    """publish refuses (exit 5, ::warning::) when the remote tip moved since the plan."""


def test_validate_inputs_accepts_the_documented_shapes():
    from provenance.cli import validate_inputs
    v = validate_inputs(since="2026-07-31", until="2026-10-13T00:00:00Z", pr="636,371,636",
                        max_requests="400", confirm_sha="a" * 40, snapshot_ref="ccr-d0be94c3-o4sati-rescue",
                        snapshot_path="audits/provenance-2026-10/rescue", snapshot_id="pr843")
    assert v.prs == (371, 636) and v.max_requests == 400 and v.snapshot_id == "pr843"
    assert validate_inputs(since="", pr="").prs == ()


@pytest.mark.parametrize("kw", [
    {"since": "2026-07-31; rm -rf /"}, {"since": "2026-7-31"}, {"pr": "636,"}, {"pr": "6 36"},
    {"max_requests": "123456"}, {"confirm_sha": "A" * 40}, {"snapshot_ref": "../main"},
    {"snapshot_path": "a/../b"}, {"snapshot_id": "843"}, {"until": "2026-10-13T00:00:00"},
])
def test_validate_inputs_refuses(kw):
    from provenance.cli import InputError, validate_inputs
    with pytest.raises(InputError):
        validate_inputs(**kw)


def test_parser_knows_every_mode():
    from provenance.cli import COMMANDS, build_parser
    ap = build_parser()
    for cmd in COMMANDS:
        assert ap.parse_args([cmd] + {"ingest": ["--ref", "x"], "refreeze": ["--pr", "1"],
                                      "recover": ["--confirm-sha", "a" * 40], "check": ["--ref", "provenance"],
                                      "config": ["--get", "enabled"]}.get(cmd, [])).cmd == cmd
