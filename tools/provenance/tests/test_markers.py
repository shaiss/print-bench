"""markers — one parser, five eras, unknown.marker counting.

Owner: H2. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_one_fixture_per_era():
    """M1..M5 each have a fixture comment (digest) from the committed raw PRs with the tier ERAS states: M1 no event, M2/M3 window at best, M4/M5 verified."""


@pytest.mark.skip(reason="builder: implement")
def test_pm_triage_designs_split_on_comma():
    """<!-- PM_TRIAGE design=a,b sha=… --> → designs [a, b]."""


@pytest.mark.skip(reason="builder: implement")
def test_verdict_fail_is_kept():
    """An M3 'verdict=fail' parses with verdict 'fail'."""


@pytest.mark.skip(reason="builder: implement")
def test_unknown_family_counted_only_for_our_identities():
    """An unknown family in an Actions-bot or owner body is counted; a CodeRabbit *_start marker is not."""
