"""ingest — the #843 snapshot (tests use fixtures/snapshot-mini, same formats).

Owner: H1. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_manifest_mismatch_refuses():
    """One flipped byte in runs.tar → IngestError, nothing planned."""


@pytest.mark.skip(reason="builder: implement")
def test_mapping_writes_receipts_runs_and_statuses():
    """snapshot-mini plans receipts for its watched runs (31364447108 full, 34661448637 full, the skipped row none), raw/snapshot/pr843/runs/ci.yml.json.gz and raw/snapshot/pr843/statuses/<sha>.json.gz for each sha with statuses; prcommits/pulls/workflows are not ingested."""


@pytest.mark.skip(reason="builder: implement")
def test_snapshot_receipt_equals_live_shape():
    """A receipt built from a snapshot row validates against receipt@1 and differs from a live one only in 'source'."""


@pytest.mark.skip(reason="builder: implement")
def test_ingest_is_idempotent():
    """A second ingest over an evidence tree that already holds the first plans zero files; a path present with different bytes is counted as a conflict and never modified."""


@pytest.mark.skip(reason="builder: implement")
def test_check_runs_are_dropped_and_counted():
    """raw-snapshot-statuses@1 carries check_runs_dropped = the member's check-run count; no check-run output reaches a stored byte."""
