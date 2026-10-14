"""bundle + derived tree + Python↔Node parity (P1d).

Owner: H5. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e, the critique round's items 5, 6,
27); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_fixture_bundle_regenerates_byte_for_byte():
    """Rebuilding site/test/fixtures/provenance-bundle.json IN MEMORY from the synthetic records in tests/fixtures/records/ (main_sha 521d0928…, evidence_sha '0'*40, producer_run 1) is byte-identical across two runs and against the committed file; the file is written only when PROVENANCE_UPDATE_FIXTURES=1 (critique 27). Decorate with @needs(episodes.episodes_of, views.build_view): it runs, and the committed file is regenerated, at integration."""


@pytest.mark.skip(reason="builder: implement")
def test_python_and_node_validators_accept_and_reject():
    """Both validators accept the fixture bundle and both reject it with one extra field."""


@pytest.mark.skip(reason="builder: implement")
def test_same_content_reads_the_tip_not_its_digest():
    """Critique 5: same_content(tip, files) is True for a tip that differs only in main_sha / evidence_sha / producer_run, and False for a forged tip whose bundle keeps the real content_sha256 field but alters one view (or one records/ blob, or one file mode)."""


@pytest.mark.skip(reason="builder: implement")
def test_main_commit_outside_designs_changes_nothing():
    """Critique 6: derive over the same evidence against main M and against M' = M + one commit touching only scripts/ gives the same tree except the bundle's main_sha, same_content True, content_sha256 equal — so no derived push."""


@pytest.mark.skip(reason="builder: implement")
def test_derived_tree_layout():
    """derived_tree_files has exactly the contract 'trees.provenance-site' layout, the guard files byte-equal .github/data-branch-guard/* (main's CURRENT bytes), FORMAT 'print-bench-provenance-site 1\n'."""


@pytest.mark.skip(reason="builder: implement")
def test_rerun_with_unchanged_inputs_pushes_nothing():
    """A second derive over the same evidence + main gives an identical tree (P1d)."""


@pytest.mark.skip(reason="builder: implement")
def test_derive_order():
    """Critique 14: with monkeypatched extract/serving/episodes/views recording calls, derive calls extract_* → run_claims → annotate_record(claims=…) → receipt_events → place → build_views, in that order, and stores no unplaced event."""
