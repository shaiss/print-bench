"""conf — the strict parser; .github/provenance.conf parses.

Owner: H6. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_committed_conf_parses_with_decision_9_values():
    """The committed conf parses: settle 6, max defer 24, cap 400, floor 500, 330 min, since 2026-07-31, :29 hourly, 15 min, the nine watched workflows."""


@pytest.mark.skip(reason="builder: implement")
def test_unknown_duplicate_colonless_and_float_fail():
    """Each malformed line raises ConfError with path:lineno (one negative control per rule)."""


@pytest.mark.skip(reason="builder: implement")
def test_armed_two_key():
    """armed(True,'true') only; every other combination False."""


@pytest.mark.skip(reason="builder: implement")
def test_watched_workflows_exist():
    """Every watched workflow file exists under .github/workflows/."""
