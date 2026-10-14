"""cli — argparse, input validation (scaffold-implemented), mode orchestration.

Owner: H1. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e, the critique round's items);
replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_harvest_dry_run_writes_plan_not_pushes():
    """harvest --dry-run over a temp repo + local bare origin + FakeGitHub writes plan.json, intent files and summary.md, sets evidence_changed/site_changed false in --gh-output and calls no push."""


@pytest.mark.skip(reason="builder: implement")
def test_budget_stop_exits_zero():
    """A BudgetExhausted during receipts or freeze exits 0 with a ::notice:: and resumable cursors in the planned state.json."""


@pytest.mark.skip(reason="builder: implement")
def test_capture_deadline_leaves_the_derive_reserve():
    """A dispatch's Budget.deadline_epoch is job start + dispatch_max_minutes − derive_reserve_minutes (critique 22): with a fake clock past it, capture stops cleanly and derive + plan still run."""


@pytest.mark.skip(reason="builder: implement")
def test_foreign_evidence_tip_derives_from_checkpoint():
    """Critique 5: both refs forged (evidence tip F on top of checkpoint C, derived tip a forged tree): plan exits 0 with foreign_tip=true, evidence_changed=false, receipts/freeze not run (no API GET beyond the scan), site_changed=true with the bundle's evidence_sha == C; publish pushes provenance-site only; the workflow's verdict step then fails."""


@pytest.mark.skip(reason="builder: implement")
def test_forged_derived_tip_is_replaced():
    """P1d + critique 5: a planted provenance-site tip that is not checkpointed — including one whose bundle copies the real content_sha256 but alters a view — is replaced by the verified tree with ::error:: (moved here from test_gitstore; critique 27)."""


@pytest.mark.skip(reason="builder: implement")
def test_bootstrap_needs_the_flag():
    """Critique 3: absent evidence ref + no checkpoint: without --bootstrap → ::error::, exit 3, nothing planned; with --bootstrap → a root commit carrying the guard files, README, FORMAT, state.json and the auto-ingest. --bootstrap with an existing ref or a checkpoint → exit 1/3."""


@pytest.mark.skip(reason="builder: implement")
def test_auto_ingest_runs_once():
    """Critique 17: the bootstrap harvest ingests --snapshot-dir fixtures/snapshot-mini (pin = its MANIFEST digest), records state.ingested.pr843 {manifest_sha256, commit, version, snapshot_end, …} and raises each watched receipts cursor to snapshot_end; the next harvest plans no ingest file."""


@pytest.mark.skip(reason="builder: implement")
def test_recover_refused_while_continuity_holds():
    """Critique 4: recover when the evidence tip passes continuity → exit 3, nothing planned."""


@pytest.mark.skip(reason="builder: implement")
def test_recover_needs_the_newest_checkpoint():
    """Critique 4: with a foreign tip, recover --confirm-sha <an older checkpoint or an intent> → exit 3; --confirm-sha <newest checkpoint> → a force-with-lease plan of that sha over the foreign tip."""


@pytest.mark.skip(reason="builder: implement")
def test_publish_order_and_rejection():
    """Critique 21: publish pushes provenance first and provenance-site only after it pushed or was unchanged (or the plan derived from the checkpoint); a rejected evidence push → exit 3 and provenance-site is NOT pushed; a moved remote tip since the plan → exit 3; checkpoints.json names only verified tips."""


@pytest.mark.skip(reason="builder: implement")
def test_gate_semantics():
    """Critique 20: a dispatch's go = conf enabled; a schedule's go needs conf.armed (casefold) AND no OTHER provenance.yml run in status queued / in_progress / pending / waiting / requested in ONE unfiltered runs-list GET (a pending dispatch → go=false)."""


@pytest.mark.skip(reason="builder: implement")
def test_guard_drift_warns_not_fails():
    """Critique 18: with .github/data-branch-guard/vercel.json changed by one byte on main, a harvest over an existing evidence ref exits 0, emits ::warning:: naming the path, and its evidence commit leaves the guard files untouched; the derived tree carries main's new bytes."""


def test_validate_inputs_accepts_the_documented_shapes():
    from provenance.cli import validate_inputs
    v = validate_inputs(since="2026-07-31", until="2026-10-13T00:00:00Z", pr="636,371,636",
                        max_requests="400", confirm_sha="a" * 40)
    assert v.prs == (371, 636) and v.max_requests == 400 and v.confirm_sha == "a" * 40
    assert validate_inputs(since="", pr="").prs == ()


@pytest.mark.parametrize("kw", [
    {"since": "2026-07-31; rm -rf /"}, {"since": "2026-7-31"}, {"pr": "636,"}, {"pr": "6 36"},
    {"max_requests": "123456"}, {"confirm_sha": "A" * 40}, {"until": "2026-10-13T00:00:00"},
])
def test_validate_inputs_refuses(kw):
    from provenance.cli import InputError, validate_inputs
    with pytest.raises(InputError):
        validate_inputs(**kw)


def test_no_snapshot_or_ref_inputs():
    """Critique 2/17: no input, option or subcommand can point the ingest at a ref or a path."""
    import inspect

    from provenance.cli import COMMANDS, build_parser, validate_inputs
    assert set(COMMANDS) == {"harvest", "refreeze", "publish", "recover", "gate", "check", "selftest"}
    assert not {"snapshot_ref", "snapshot_path", "snapshot_id"} & set(inspect.signature(validate_inputs).parameters)
    ap = build_parser()
    for bad in (["ingest", "--ref", "x"], ["harvest", "--ref", "x"], ["harvest", "--path", "x"],
                ["config", "--get", "enabled"], ["check", "--ref", "provenance"]):
        with pytest.raises(SystemExit):
            ap.parse_args(bad)


def test_parser_knows_every_mode():
    from provenance.cli import COMMANDS, build_parser
    ap = build_parser()
    for cmd in COMMANDS:
        assert ap.parse_args([cmd] + {"refreeze": ["--pr", "1"],
                                      "recover": ["--confirm-sha", "a" * 40],
                                      "check": ["--dir", ".", "--kind", "evidence"]}.get(cmd, [])).cmd == cmd
    assert ap.parse_args(["harvest", "--bootstrap", "--snapshot-dir", "d"]).bootstrap is True
