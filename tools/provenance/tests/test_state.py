"""state — state@1 model.

Owner: H1. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e, the critique round's items);
replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_round_trip_is_byte_stable():
    """load_state(dump_state(s)) == s and dumping twice gives identical bytes; no wall-clock field exists; there is no 'frozen' key (critique 28)."""


@pytest.mark.skip(reason="builder: implement")
def test_frozen_from_paths():
    """frozen_from_paths over raw/pr/636.json.gz, raw/pr/636.r2.json.gz, raw/brief/592.json.gz, raw/release/v2.0.json.gz → {'pr': {'636': 2}, 'brief': {'592': 1}, 'release': {'v2.0': 1}}; next_revision → 3 / 2 / 1 for an unseen key; receipts/ and raw/snapshot/ paths are ignored."""


@pytest.mark.skip(reason="builder: implement")
def test_pending_skipped_clear():
    """set_pending then clear_pending removes the entry; set_skipped records {closed_at} per PR."""


@pytest.mark.skip(reason="builder: implement")
def test_oldest_overdue():
    """oldest_overdue picks the unit furthest past due_at + grace (Reeve's provenance-lag mirrors it)."""
