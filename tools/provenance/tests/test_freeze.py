"""freeze — settle/defer/refreeze (P1e).

Owner: H6. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_pr_merged_2h_ago_is_pending():
    """A PR merged 2 h ago lands in state.pending with due_at = closed_at + 6 h, not in raw/."""


@pytest.mark.skip(reason="builder: implement")
def test_pr_at_7h_freezes():
    """The same PR at 7 h freezes to raw/pr/<n>.json.gz."""


@pytest.mark.skip(reason="builder: implement")
def test_in_flight_run_defers_then_forces():
    """One with an in-flight watched run defers; at 24 h it freezes with incomplete ['settle-deferred']."""


@pytest.mark.skip(reason="builder: implement")
def test_deployment_wait():
    """A merged PR whose Production deployment is not terminal waits up to deploy_wait_hours, then freezes with incomplete deployment-not-terminal."""


@pytest.mark.skip(reason="builder: implement")
def test_refreeze_adds_r2_and_modifies_nothing():
    """refreeze adds raw/pr/<n>.r2.json.gz; the plan holds no other path."""


@pytest.mark.skip(reason="builder: implement")
def test_capture_unions_snapshot_rows():
    """capture_pr unions snapshot ci runs and statuses by id, live winning on a collision."""


@pytest.mark.skip(reason="builder: implement")
def test_capture_fetches_statuses_for_every_commit():
    """Statuses are fetched for every PR commit and ci head (/commits/{sha}/statuses), not the combined /status."""


@pytest.mark.skip(reason="builder: implement")
def test_no_design_files_is_skipped():
    """A closed PR touching no designs/ path is recorded in state.skipped.pr and never captured."""


@pytest.mark.skip(reason="builder: implement")
def test_no_op_harvest_writes_nothing():
    """A harvest with nothing new plans no file and an unchanged state.json."""
