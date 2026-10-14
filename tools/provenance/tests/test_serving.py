"""serving — the join (P1c). Receipts and code bases from the committed fixtures; synthetic FakeCodeBasis/FakeGitReader for the edge cases.

Owner: H4. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e, the critique round's items 9, 14,
15, 26); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_nvc2_scout_window():
    """NVC-2: brief #592 filed 10:49:36Z by github-actions[bot] sits in exactly one product-scout window (run 34112970240, link 1 10:44:13–10:51:20) → role product-scout, model glm-5.2 (registry@a720a6bd chain scout), trust window."""


@pytest.mark.skip(reason="builder: implement")
def test_nvc3_design_run_link3():
    """NVC-3: commit 9a751b26 at 02:06:03Z → design-run run 34661448637 attempt 2, link 3, glm-4.6, links_not_served 2, basis step-window+registry@head(a720a6bd) (bot-authored: plain containment)."""


@pytest.mark.skip(reason="builder: implement")
def test_nvc4_ship_lock_link1():
    """The SHIP-LOCK at 00:35:31Z (owner PAT) → link 1, glm-5.2, trust window — it is the only OWNER brief.claimed in run 34661448637's windows, so run_claims gives {34661448637: 592}."""


@pytest.mark.skip(reason="builder: implement")
def test_owner_artifacts_need_the_claimed_issue():
    """Critique 15 (negatives): inside a design-run window that claimed #592, an OWNER pr.opened on a non-claude branch stays login; an OWNER pr.opened on claude/issue-700-x stays login; an OWNER brief.declined on #700 stays login; a window holding two OWNER SHIP-LOCKs claims nothing (both stay login); the OWNER pr.opened of #636 (claude/issue-592-…) becomes window."""


@pytest.mark.skip(reason="builder: implement")
def test_nvc5_reviewers_glm53():
    """NVC-5: the 12 verified sign-offs on #636 resolve to glm-5.3 via chain review link 1 at the merge-tree basis."""


@pytest.mark.skip(reason="builder: implement")
def test_merge_tree_basis_when_head_registry_differs():
    """A fixture PR whose head registry differs from main's at created_at resolves to the merge tree's model, basis step-window+registry@merge(<main8>+<head8>)."""


@pytest.mark.skip(reason="builder: implement")
def test_registry_change_within_15_minutes_is_ambiguous():
    """A main registry change 5 minutes before created_at → model null, basis ambiguous."""


@pytest.mark.skip(reason="builder: implement")
def test_oracle_resolves_against_main_at_checkout():
    """Critique 26: an oracle pull_request run created at T whose checkout step started at T+40 min resolves against main@(T+40 min) — a registry change landing between T and T+40 min is the one it read; a registry change within 15 min either side of the checkout step → ambiguous; its two resolve literals are discriminated by the step provider group."""


@pytest.mark.skip(reason="builder: implement")
def test_pre_326_inline_pin():
    """Run 31364447108 → step 'Run via Anthropic (Claude)' → inline pin claude-opus-4-8 from design-run.yml@dae83d67, chain_link null, basis provider-step+inline-pin@dae83d67."""


@pytest.mark.skip(reason="builder: implement")
def test_overlapping_windows_are_ambiguous():
    """Overlapping design-run and backlog-burn windows → model null, basis ambiguous, trust not upgraded."""


@pytest.mark.skip(reason="builder: implement")
def test_missing_commit_is_none_not_a_fetch():
    """Critique 9: a run whose head sha is absent from the FakeGitReader (force-pushed away) → model null, basis none, the record gains codebasis-unavailable:<sha8>; the same input twice gives identical output (GitReader has no fetch method to call)."""


@pytest.mark.skip(reason="builder: implement")
def test_non_null_model_has_basis():
    """Every event with a non-null model carries a basis other than none."""


@pytest.mark.skip(reason="builder: implement")
def test_owner_token_signoff_never_window():
    """A DRIK_SIGNOFF by the owner inside a Drik job window stays claimed (ROLE_IDENTITIES: reviewers post as the Actions bot)."""


@pytest.mark.skip(reason="builder: implement")
def test_job_reviewer_posted_nothing():
    """Drik job 38161046420 (all six links tried, nothing posted) → job.reviewer posted false, links_tried 6; receipt_events returns it unplaced (episode None) for episodes.place."""


@pytest.mark.skip(reason="builder: implement")
def test_trailer_claimed_model():
    """7c25f888's 'Co-Authored-By: Claude Opus 5.5' → model 'Claude Opus 5.5', basis trailer, harness claude-code."""
