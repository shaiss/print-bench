"""gitstore — add-only writer, diff-tree guard, pushes, tip continuity (P0 acceptance). Real temp repos (git init), no network.

Owner: H1. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_treebuilder_adds_new_blobs_without_touching_existing():
    """Seeded from a tip, add() of a new path writes it; add() of an existing path with identical bytes is a no-op (False); with different bytes raises GuardViolation; no existing blob ever passes through the working tree."""


@pytest.mark.skip(reason="builder: implement")
def test_guard_refuses_delete():
    """Negative: a new commit missing any old path → GuardViolation('D …')."""


@pytest.mark.skip(reason="builder: implement")
def test_guard_refuses_modify_outside_state_json():
    """Negative: M under receipts/ or raw/ → GuardViolation; M of state.json passes."""


@pytest.mark.skip(reason="builder: implement")
def test_guard_refuses_zero_byte_blob():
    """Negative: 'a raw file becomes 0 B' → GuardViolation (the telemetry #D2 class)."""


@pytest.mark.skip(reason="builder: implement")
def test_guard_refuses_guard_file_change():
    """Negative: changing vercel.json or scripts/vercel-ignore-build.sh after bootstrap → GuardViolation."""


@pytest.mark.skip(reason="builder: implement")
def test_identical_tree_pushes_nothing():
    """guard_diff returns [] for an identical tree and the orchestrator skips the push (a repeat dispatch pushes no commit)."""


@pytest.mark.skip(reason="builder: implement")
def test_tip_continuity_refuses_a_foreign_tip():
    """A fixture branch whose tip is no declared intent: check_tip_continuity raises ForeignTip; cmd_harvest emits ::error::, pushes nothing, exits 3."""


@pytest.mark.skip(reason="builder: implement")
def test_tip_continuity_bootstrap_and_deleted_ref():
    """Absent ref + no intent ever seen = bootstrap ok; absent ref + intents seen = ForeignTip (deletion)."""


@pytest.mark.skip(reason="builder: implement")
def test_declared_intents_filters_runs():
    """Only head_branch=main, event schedule/workflow_dispatch, head_sha on main's first-parent history count; a run on another branch declaring the tip does not."""


@pytest.mark.skip(reason="builder: implement")
def test_recover_refuses_undeclared_sha():
    """recover --confirm-sha with a sha that is not a declared intent exits non-zero and moves nothing (P0)."""


@pytest.mark.skip(reason="builder: implement")
def test_push_ff_retries_transport_not_rejections():
    """A transport failure retries the SAME commit up to 3x; a non-ff rejection re-fetches, never rebuilds: foreign new tip → ForeignTip, declared → PushResult(rejected=True)."""


@pytest.mark.skip(reason="builder: implement")
def test_derived_push_uses_force_with_lease():
    """provenance-site is pushed with --force-with-lease on the planned old tip; a planted foreign derived tip is replaced by the verified tree with ::error:: (P1d)."""


@pytest.mark.skip(reason="builder: implement")
def test_guard_blobs_come_from_data_branch_guard():
    """Both data trees' vercel.json and scripts/vercel-ignore-build.sh (mode 100755) equal .github/data-branch-guard/* byte-for-byte."""
