"""receipts — runs-list selection, day windows, full vs stub, day-sharded paths (P0).

Owner: H1. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md §Receipts, the critique round's items 8 and 19);
replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_build_receipt_matches_every_committed_fixture():
    """For every fixture receipt, receipts.build_receipt(workflow, run, jobs, source) reproduces the committed DOCUMENT: its canonical JSON equals the fixture's decompressed bytes (gzip bytes are storage only and may differ across zlib builds — critique 19)."""


@pytest.mark.skip(reason="builder: implement")
def test_pre_326_run_is_stored_complete():
    """Design-run run 31364447108 (2026-08-10; steps 'Run via Anthropic (Claude)' and 'Run via Z.AI (GLM)') is stored with its complete jobs response (kind full)."""


@pytest.mark.skip(reason="builder: implement")
def test_disarmed_run_is_a_stub():
    """A run whose only job that ran is 'Explain a disarmed run' is kind stub with jobs null and the stub job list; jobs_sha256 still digests the jobs."""


@pytest.mark.skip(reason="builder: implement")
def test_selection_is_by_runs_list_not_step_name():
    """Every completed, non-skipped watched run without a receipt gets one jobs GET; skipped runs get none; in-progress runs are left for the next pass and hold the cursor back."""


@pytest.mark.skip(reason="builder: implement")
def test_receipt_path_is_day_sharded_with_attempt():
    """receipts/YYYY/MM/DD/<id>.a<attempt>.json.gz from run.created_at (UTC)."""


@pytest.mark.skip(reason="builder: implement")
def test_windows_halve_at_the_1000_cap():
    """Critique 8: a FakeGitHub responder that answers any created=A..B window holding more than 1,000 runs with total_count >= 1000 and only the first 1,000 rows: list_runs halves until every window is under the cap, returns all 2,500 runs exactly once, and only ever sends the created filter; a window whose rows != total_count is retried once then raises Truncated; a one-minute window still capped raises Truncated."""


@pytest.mark.skip(reason="builder: implement")
def test_run_windows_are_utc_days():
    """run_windows('2026-10-11T06:13:35Z', '2026-10-13T00:00:00Z') → three windows split at UTC midnight, contiguous, inclusive bounds, none past the end."""


@pytest.mark.skip(reason="builder: implement")
def test_budget_stop_resumes_from_cursor():
    """BudgetExhausted mid-pass returns budget_stopped=True and cursors that, on the next pass with a fresh budget, list exactly the runs not yet receipted."""


@pytest.mark.skip(reason="builder: implement")
def test_receipt_count_equals_non_skipped_runs():
    """Over a FakeGitHub runs list, the pass's full+stub count equals the non-skipped completed runs listed (the shape of the P2 live check, which compares snapshot rows ∪ the windowed live listing)."""
