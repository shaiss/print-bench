"""views — fold (P1d).

Owner: H5. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_one_view_per_design_including_zero_pr():
    """build_views yields one view per designs/<name>/<name>.scad on main, including a design with no PR (empty events, counts all 0)."""


@pytest.mark.skip(reason="builder: implement")
def test_member_vs_maintenance():
    """A regen-only or sweep PR becomes a maintenance row, never events."""


@pytest.mark.skip(reason="builder: implement")
def test_brief_aliases():
    """A brief linked via a member PR's briefs and a different design_name slug lands in aliases."""


@pytest.mark.skip(reason="builder: implement")
def test_events_deduped_and_sorted():
    """Events are unique by id and sorted by canonical.event_sort_key."""


@pytest.mark.skip(reason="builder: implement")
def test_counts():
    """counts.signoffs by tier and jobs_posted_nothing match the events."""
