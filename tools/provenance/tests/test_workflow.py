"""provenance.yml pinned to the tool (the andon test_workflow precedent).

Owner: H6. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md §Workflow, the critique round's items 3, 5, 12, 13, 17,
20, 21); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_keyless():
    """No 'secrets.' reference anywhere, no claude-code-action, no AI_ANDON_CORD gate leg (the harvester keeps recording while the cord is pulled)."""


@pytest.mark.skip(reason="builder: implement")
def test_no_inputs_in_run_scripts():
    """No '${{ inputs.' and no '${{ steps.' inside any run: block; inputs and step outputs reach run: steps only through env:."""


@pytest.mark.skip(reason="builder: implement")
def test_permissions_job_level_only():
    """Workflow default contents: read; only the harvest job adds contents: write plus read on actions, pull-requests, issues, statuses, deployments — and NOT checks (nothing reads check runs; critique 13); the gate job holds contents: read + actions: read."""


@pytest.mark.skip(reason="builder: implement")
def test_token_reaches_steps_by_env_only():
    """GH_TOKEN (github.token) is set as env on the plan and publish steps only; no step writes it to a file, .git/config or argv; no step but publish could push (critique 12/13)."""


@pytest.mark.skip(reason="builder: implement")
def test_gate_job_and_concurrency():
    """A gate job with no concurrency group whose job-level if: is `github.event_name == 'workflow_dispatch' || vars.PROVENANCE_ENABLED == 'true'` (so a disarmed schedule's run is all-skipped and uploads nothing) feeds harvest's if: needs.gate.outputs.go == 'true'; harvest has job-level concurrency provenance-writer, cancel-in-progress false, timeout-minutes 350."""


@pytest.mark.skip(reason="builder: implement")
def test_default_branch_pin_and_checkout():
    """checkout ref = default branch, fetch-depth 0, persist-credentials false; the job if: pins github.ref_name to the default branch."""


@pytest.mark.skip(reason="builder: implement")
def test_schedule_matches_conf():
    """Exactly one `- cron: '…'` literal (single-quoted — cadence-sync-check.sh's regex requires it), equal to the conf's cadence."""


@pytest.mark.skip(reason="builder: implement")
def test_step_order_intents_publish_checkpoints_verdict():
    """Steps in order: plan → upload intent-provenance-<sha> / intent-provenance-site-<sha> (each if: its *_changed output, retention-days 90) → publish → upload tip-provenance-<sha> / tip-provenance-site-<sha> checkpoints (each if: publish's *_tip output is non-empty, retention-days 90) → a verdict step that exits 3 when foreign_tip is true → summary (if: always()). Artifact names come from validated 40-hex outputs."""


@pytest.mark.skip(reason="builder: implement")
def test_modes_and_input_validation():
    """workflow_dispatch input mode is a choice of exactly harvest | refreeze | recover (owner decision 12 — no ingest mode, critique 17); booleans receipts_only, dry_run, bootstrap; free-text since, until, pr, max_requests, confirm_sha passed as CLI arguments from env and validated by cli.validate_inputs; no snapshot_ref / snapshot_path input exists."""
