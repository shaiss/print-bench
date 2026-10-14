"""conf — the strict parser; .github/provenance.conf parses.

Owner: H6. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e, the critique round's items);
replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_committed_conf_parses_with_decision_9_values():
    """The committed conf parses: settle 6, max defer 24, cap 400, floor 500, 330 min with a 30 min derive reserve, since 2026-07-31, :29 hourly, 15 min, 90-day continuity horizon, the nine watched workflows, snapshot pr843 at audits/provenance-2026-10/rescue pinned to commit 411a7565… and manifest c713379b…."""


@pytest.mark.skip(reason="builder: implement")
def test_unknown_duplicate_colonless_and_float_fail():
    """Each malformed line raises ConfError with path:lineno (one negative control per rule), including the retired keys intent_window_runs / snapshot_ref / snapshot_path (now unknown), a snapshot_dir with '..' or a leading '/', a 39-hex snapshot_commit and derive_reserve_minutes >= dispatch_max_minutes."""


@pytest.mark.skip(reason="builder: implement")
def test_armed_two_key():
    """armed(True, v) for v in 'true', 'True', 'TRUE' (casefold, matching the YAML leg's case-insensitive ==); every other combination False (critique 20)."""


@pytest.mark.skip(reason="builder: implement")
def test_watched_workflows_exist():
    """Every watched workflow file exists under .github/workflows/."""
