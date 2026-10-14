"""freeze — settle/defer/re-capture/refreeze (P1e).

Owner: H6. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e, the critique round's items 10,
11, 24); replace the skip with the test.
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
def test_refreeze_after_retention_keeps_rounds():
    """Critique 10: a refreeze whose live /actions/workflows/ci.yml/runs, /commits/{sha}/statuses and /deployments all answer empty (GitHub deleted them) carries r1's ci_runs, statuses and deployments into r2 by id, so episodes.rounds(r2) == episodes.rounds(r1); a live row with an r1 id wins."""


@pytest.mark.skip(reason="builder: implement")
def test_changed_terminal_state_is_recaptured():
    """Critique 11: a PR frozen closed-unmerged (r1 pull.merged_at null) that the closed listing now shows merged goes back through settle and freezes r2 once due; a frozen PR whose listing differs only in updated_at (a late comment) is NOT recaptured; a skipped PR with a new closed_at is re-evaluated; a brief frozen with brief-open that is now closed gets r2 after settle."""


@pytest.mark.skip(reason="builder: implement")
def test_linked_issue_becomes_a_brief_only_with_the_label():
    """Critique 24: a PR linking #N (closes #N) where #N never carried design-brief captures no raw/brief/N (capture_brief returns None); with a timeline 'labeled design-brief' event (label since removed) it does."""


@pytest.mark.skip(reason="builder: implement")
def test_capture_unions_snapshot_rows():
    """capture_pr unions snapshot ci runs and statuses by id, live winning on a collision."""


@pytest.mark.skip(reason="builder: implement")
def test_capture_fetches_statuses_for_every_commit():
    """Statuses are fetched for every PR commit and ci head (/commits/{sha}/statuses), not the combined /status."""


@pytest.mark.skip(reason="builder: implement")
def test_no_design_files_is_skipped():
    """A closed PR touching no designs/ path is recorded in state.skipped.pr with its closed_at and never captured."""


@pytest.mark.skip(reason="builder: implement")
def test_no_op_harvest_writes_nothing():
    """A harvest with nothing new plans no file and an unchanged state.json."""
