"""provenance.yml pinned to the tool (the andon test_workflow precedent).

Owner: H6. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_keyless():
    """No 'secrets.' reference anywhere, no claude-code-action, no AI_ANDON_CORD gate leg (the harvester keeps recording while the cord is pulled)."""


@pytest.mark.skip(reason="builder: implement")
def test_no_inputs_in_run_scripts():
    """No '${{ inputs.' inside any run: block; inputs reach steps only through env:."""


@pytest.mark.skip(reason="builder: implement")
def test_permissions_job_level_only():
    """Workflow default contents: read; only the harvest job adds contents: write (plus read on actions, pull-requests, issues, statuses, checks, deployments); the gate job is read-only."""


@pytest.mark.skip(reason="builder: implement")
def test_gate_job_and_concurrency():
    """A gate job with no concurrency group feeds harvest's if: needs.gate.outputs.go == 'true'; harvest has job-level concurrency provenance-writer, cancel-in-progress false."""


@pytest.mark.skip(reason="builder: implement")
def test_default_branch_pin_and_checkout():
    """checkout ref = default branch, fetch-depth 0, persist-credentials false; the job if: pins github.ref_name to the default branch."""


@pytest.mark.skip(reason="builder: implement")
def test_schedule_matches_conf():
    """Exactly one '- cron:' literal, equal to the conf's cadence; the schedule leg needs vars.PROVENANCE_ENABLED == 'true'."""


@pytest.mark.skip(reason="builder: implement")
def test_intents_uploaded_before_publish():
    """upload-artifact steps for intent-provenance-<sha> / intent-provenance-site-<sha> (retention-days 90) run after 'harvest' and before 'publish'."""


@pytest.mark.skip(reason="builder: implement")
def test_modes_and_input_validation():
    """workflow_dispatch modes harvest | ingest | refreeze | recover (choice input); every free-text input is passed as a CLI argument from env and validated by cli.validate_inputs."""
