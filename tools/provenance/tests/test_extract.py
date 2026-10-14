"""extract — raw@1 → record@1 (validated by contract.check).

Owner: H3. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_pr_records_validate():
    """extract_pr over every fixture raw PR yields a record that contract.check('record@1:pr') accepts."""


@pytest.mark.skip(reason="builder: implement")
def test_every_event_has_a_constructed_url():
    """NVC-14: every event has a url matching the contract pattern, built from ids (no payload html_url copied)."""


@pytest.mark.skip(reason="builder: implement")
def test_noise_never_becomes_an_event():
    """NVC-12b: no event of a noise class (bugbot limit, qodo paused, preview deploys, CodeRabbit statuses) is stored."""


@pytest.mark.skip(reason="builder: implement")
def test_commit_kinds_636():
    """#636: 9a751b26 commit.design; 8 commit.regen; 3 commit.merge_main (4862566b, f4e36eb9, d7bfd77c); the Cursor commits commit.fix."""


@pytest.mark.skip(reason="builder: implement")
def test_human_commits_634():
    """#634: 856831c4, 0443cba6, cb7e8903 are commit.human (owner, no agent trailer)."""


@pytest.mark.skip(reason="builder: implement")
def test_merge_method_fixtures():
    """squash, merge-commit and rebase fixtures (synthetic FakeGitReader main with blame_lines) each give the right merge_method and map a blamed PM.md line to the right PR."""


@pytest.mark.skip(reason="builder: implement")
def test_brief_records():
    """#592: brief.filed (github-actions[bot]), brief.claimed (design_name nuggs-vent-cap), brief.shipped (shipped_pr 636), brief.closed closed_by_pr 636; record.design_name nuggs-vent-cap."""


@pytest.mark.skip(reason="builder: implement")
def test_extractor_has_no_clock():
    """Covered by test_purity; this asserts two extractions of the same raw are byte-identical."""


@pytest.mark.skip(reason="builder: implement")
def test_direct_commit_rule():
    """Critique 7, over a synthetic FakeGitReader main: an owner-committed commit touching designs/ with no PR subject → one commit record (C:<sha8>); a '(#N)' squash commit whose PR is NOT frozen → no record; a 'Merge pull request #N' commit → no record; a GitHub-committed (noreply@github.com) rebase-merge commit with an ordinary subject → no record; a commit in a frozen PR's commit list → no record; the real 43030db9 shape ('Merge PR #196: …', committed by GitHub) → no record."""


@pytest.mark.skip(reason="builder: implement")
def test_linked_issues_vs_briefs():
    """Critique 24: record.linked_issues = raw.linked_issues; record.briefs = those in ctx.brief_numbers (#636 → linked [592], briefs [592]; with brief_numbers empty → briefs [])."""


@pytest.mark.skip(reason="builder: implement")
def test_records_carry_no_main_sha():
    """Critique 6: extracting the same raw PR against two different ctx.main_sha values (the second a main commit touching no designs/ file) yields byte-identical records."""
