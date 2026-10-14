"""bundle + derived tree + Python↔Node parity (P1d).

Owner: H5. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_fixture_bundle_regenerates_byte_for_byte():
    """Rebuilding site/test/fixtures/provenance-bundle.json from the synthetic records in tests/fixtures/records/ (main_sha 521d0928…, evidence_sha '0'*40, producer_run 1) is byte-identical across two runs and against the committed file."""


@pytest.mark.skip(reason="builder: implement")
def test_python_and_node_validators_accept_and_reject():
    """Both validators accept the fixture bundle and both reject it with one extra field."""


@pytest.mark.skip(reason="builder: implement")
def test_same_content_ignores_meta():
    """Changing only main_sha / evidence_sha / producer_run keeps content_sha256 equal → no push."""


@pytest.mark.skip(reason="builder: implement")
def test_derived_tree_layout():
    """derived_tree_files has exactly the contract 'trees.provenance-site' layout, the guard files byte-equal .github/data-branch-guard/*, FORMAT 'print-bench-provenance-site 1\n'."""


@pytest.mark.skip(reason="builder: implement")
def test_rerun_with_unchanged_inputs_pushes_nothing():
    """A second derive over the same evidence + main gives an identical tree (P1d)."""
