"""codebasis — GitCodeBasis over a FakeGitReader built from fixtures/codebasis + fixtures/main_history.

Owner: H4. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e, the critique round's items 9 and
26); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_head_basis_for_schedule():
    """schedule/workflow_dispatch → Basis('head', run.head_sha)."""


@pytest.mark.skip(reason="builder: implement")
def test_merge_basis_for_auto_review():
    """auto-review pull_request → Basis('merge', head, main@created_at)."""


@pytest.mark.skip(reason="builder: implement")
def test_main_basis_for_oracle_uses_checkout():
    """oracle pull_request with checkout=(started, completed) → Basis('main', None, main@started); without a checkout interval → main@created_at, ambiguous (reason 'no-checkout-step')."""


@pytest.mark.skip(reason="builder: implement")
def test_conflict_on_registry_is_ambiguous():
    """merge_tree_read reports registry.conf conflicted → ambiguous."""


@pytest.mark.skip(reason="builder: implement")
def test_missing_head_is_unavailable():
    """A head sha the GitReader does not have → Basis.unavailable == that sha (never a fetch); memoized per (workflow, kind, main8, head8)."""


@pytest.mark.skip(reason="builder: implement")
def test_registry_parsed_with_model_registry():
    """chain_models reads the fixture registry@a720a6bd: design-run = (glm-5.2, glm-5.1, glm-4.6, claude-sonnet-5, claude-haiku-4-5)."""


@pytest.mark.skip(reason="builder: implement")
def test_unparseable_registry_is_none():
    """A registry the strict parser refuses → None (never a lenient re-parse)."""
