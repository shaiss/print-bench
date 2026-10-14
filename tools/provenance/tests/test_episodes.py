"""episodes — rounds, folds, flags, edges, decision rows.

Owner: H3. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_rounds_nvc1_sbc1_cc5():
    """rounds(): #636 → 15 (NVC-1); #371 → 2, #397 → 14 (SBC-1); #634 → 13 (CC-5)."""


@pytest.mark.skip(reason="builder: implement")
def test_regen_constants_drift_pin():
    """REGEN_SUBJECT / REGEN_AUTHOR / REGEN_TRAILER equal scripts/reviewer-signoff.sh's literals."""


@pytest.mark.skip(reason="builder: implement")
def test_stale_signoff_nvc8():
    """NVC-8: the sign-off at issuecomment-6111973609 (sha 9a751b26) lands in R:636:f4e36eb9 with stale_sha true."""


@pytest.mark.skip(reason="builder: implement")
def test_after_merge_flag():
    """An event after merged_at has after_merge true and stays in the live round."""


@pytest.mark.skip(reason="builder: implement")
def test_verifies_edges():
    """A re-sign-off's verifies lists the fix commits since that family's previous sign-off (fix→re-sign-off 100% at SHA level)."""


@pytest.mark.skip(reason="builder: implement")
def test_decision_rows_select_the_documented_lines():
    """parse_pm_decision_log / parse_field_test_log / parse_changelog / parse_notes_decisions over synthetic texts: header + separator + rows until a blank or pipe-less line, a real YYYY-MM-DD first cell, ### headings by date, dated top-level bullets only. The cross-stack parity proof is site/test/provenance-rows.test.mjs (H3), run by the site-build job on every PR (critique 25)."""


@pytest.mark.skip(reason="builder: implement")
def test_rows_use_the_original_line_and_adding_commit():
    """Critique 6: a row whose blame is (sha S, original line 12) carries fields.line 12, added_in_sha S and url blob/S/designs/<d>/PM.md#L12; inserting lines above it on a later main commit changes neither (same row event bytes)."""


@pytest.mark.skip(reason="builder: implement")
def test_place_assigns_unplaced_events():
    """Critique 14: place() gives a job.reviewer event (episode None, ts inside round 3) episode R:<pr>:<round3 head8>, head_sha, after_merge per merged_at; already-placed events are unchanged; rounds_from_record(round_dict(r)) == r for every round of #636."""


@pytest.mark.skip(reason="builder: implement")
def test_notes_decisions_nuggs_vent_cap():
    """decision.notes_log rows for nuggs-vent-cap at L233, 238, 241, 244, 248, 254, 258, 265, 271 (golden)."""


@pytest.mark.skip(reason="builder: implement")
def test_blame_fallbacks():
    """added_in_pr from '(#N)' (squash), 'Merge pull request #N' (merge), and commit_to_pr for a rebase-merged sha."""
