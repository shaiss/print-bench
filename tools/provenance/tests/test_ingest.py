"""ingest — the #843 snapshot (tests use fixtures/snapshot-mini, same formats; the real one is on main).

Owner: H1 (the placeholders). Each placeholder's docstring is its
acceptance criterion (docs/provenance.md §INGEST, the critique round's items
1, 2, 8, 17, 19); replace the skip with the test. The pin test below is live.
"""

from __future__ import annotations

import hashlib
import re

import pytest

from conftest import REPO


def _conf_value(key: str) -> str:
    text = (REPO / ".github" / "provenance.conf").read_text(encoding="utf-8")
    m = re.search(rf"^{key}: (\S+)$", text, re.M)
    assert m, key
    return m.group(1)


def test_conf_pins_the_snapshot_on_main():
    """Critique 1: the committed snapshot directory's MANIFEST.sha256 hashes to the conf's pin (a
    textual read — conf.py is H6's). If this fails, someone changed the snapshot or the pin."""
    d = REPO / _conf_value("snapshot_dir")
    assert hashlib.sha256((d / "MANIFEST.sha256").read_bytes()).hexdigest() == _conf_value("snapshot_manifest_sha256")
    assert re.fullmatch(r"[0-9a-f]{40}", _conf_value("snapshot_commit"))
    for name in ("runs.tar", "jobs.tar", "sha.tar"):
        assert (d / name).is_file(), name


@pytest.mark.skip(reason="builder: implement")
def test_manifest_mismatch_refuses():
    """One flipped byte in runs.tar → IngestError, nothing planned."""


@pytest.mark.skip(reason="builder: implement")
def test_consistent_but_unpinned_snapshot_refuses():
    """Critique 2: a copy of snapshot-mini with a modified runs.tar AND a recomputed, internally consistent MANIFEST.sha256 → IngestError (its manifest digest is not the pin)."""


@pytest.mark.skip(reason="builder: implement")
def test_tar_members_are_regular_and_named():
    """Critique 2: a tar holding a symlink, a directory, '../x.json.gz', 'a/b.json.gz' or 'x.json' → IngestError; members are read with extractfile only (no extract/extractall call in ingest.py — an AST check)."""


@pytest.mark.skip(reason="builder: implement")
def test_mapping_writes_receipts_runs_and_statuses():
    """snapshot-mini plans receipts for its watched runs (31364447108 full, 34661448637 full, the skipped row none), raw/snapshot/pr843/runs/ci.yml.json.gz and raw/snapshot/pr843/statuses/<sha>.json.gz for each sha with statuses; prcommits/pulls/workflows are not ingested."""


@pytest.mark.skip(reason="builder: implement")
def test_snapshot_receipt_equals_live_shape():
    """A receipt built from a snapshot row validates against receipt@1 and differs from a live one only in 'source'."""


@pytest.mark.skip(reason="builder: implement")
def test_cursors_rise_to_snapshot_end():
    """Critique 8: plan_ingest raises every watched workflow's receipts cursor to snapshot_end (the latest row created_at — 2026-10-13T06:13:35Z for the real snapshot) and never lowers a later one."""


@pytest.mark.skip(reason="builder: implement")
def test_ingest_is_idempotent_on_content():
    """A second ingest over an evidence tree that already holds the first plans zero files — including when the existing .gz blobs were written at another gzip level (identity is the decompressed bytes, critique 19); a path present with different CONTENT is counted as a conflict and never modified; needs_ingest is false for the recorded version and true for INGEST_VERSION + 1."""


@pytest.mark.skip(reason="builder: implement")
def test_check_runs_are_dropped_and_counted():
    """raw-snapshot-statuses@1 carries check_runs_dropped = the member's check-run count; no check-run output reaches a stored byte."""
