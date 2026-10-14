"""state — state@1 model.

Owner: H1. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_round_trip_is_byte_stable():
    """load_state(dump_state(s)) == s and dumping twice gives identical bytes; no wall-clock field exists."""


@pytest.mark.skip(reason="builder: implement")
def test_pending_then_frozen():
    """set_pending then set_frozen removes the pending entry and records the revision; next_revision returns K+1."""


@pytest.mark.skip(reason="builder: implement")
def test_oldest_overdue():
    """oldest_overdue picks the unit furthest past due_at + grace (Reeve's provenance-lag mirrors it)."""
