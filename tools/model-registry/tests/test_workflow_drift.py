"""Drift guard: the committed registry and auto-review.yml cannot silently diverge.

auto-review.yml only runs on design PRs, so this PR's CI does not live-exercise the
migrated review pipeline. This test is the standing proof that the registry drives
the workflow and stays consistent with it:

* the real registry loads and the `review` chain resolves to the 4 links the
  workflow has slots for;
* each slot's *provider* (which secret it wires literally) matches the registry
  chain's provider at that position — slots 1–3 are Z.AI (ZAI_KEY), slot 4 is
  Anthropic (ANTHROPIC_API_KEY);
* every reviewer ship step sources its model from the resolve outputs, with no
  hardcoded model literal left behind.

It deliberately does NOT pin the specific model ids — reordering/swapping a model
*within a provider* is exactly the registry edit #206 exists to allow, and stays
green here. Changing the slot→provider *shape* (or reverting to a hardcoded model)
is what fails, pointing you at the YAML that must change with it.
"""

from __future__ import annotations

import pathlib
import re

from model_registry.registry import Registry

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "auto-review.yml"
REGISTRY = REPO_ROOT / ".github" / "models" / "registry.conf"

# The workflow's fixed slot→provider wiring: slots p1..p3 reference secrets.ZAI_KEY
# (via the Anthropic-compatible endpoint), slot p4 references secrets.ANTHROPIC_API_KEY.
# The registry's `review` chain must line up with this, position for position.
EXPECTED_SLOT_PROVIDERS = ["zai", "zai", "zai", "anthropic"]


def test_committed_registry_is_valid():
    # A malformed committed registry would fail the resolve step at run time and
    # block every design PR's review — catch it here instead.
    Registry.load(str(REGISTRY))


def test_review_chain_matches_the_workflow_slot_shape():
    links = Registry.load(str(REGISTRY)).resolve("review")
    assert [l.provider for l in links] == EXPECTED_SLOT_PROVIDERS, (
        "the `review` chain's per-position providers no longer match auto-review.yml's "
        "slot→secret wiring (slots 1-3 Z.AI, slot 4 Anthropic). Changing the shape means "
        "editing the ship steps' literal secret refs too, then this expectation."
    )


def test_workflow_sources_every_model_from_the_registry():
    text = WORKFLOW.read_text(encoding="utf-8")
    # No hardcoded model id may remain in a claude_args line — all must be sourced.
    leftover = re.findall(r"--model\s+(glm-[\w.]+|claude-[\w.-]+)\b", text)
    assert not leftover, f"hardcoded model literal(s) still in auto-review.yml: {leftover}"
    # The resolve step targets the `review` chain specifically.
    assert "model_registry resolve review" in text
    # design-changes exposes model1..model4 wired to the resolve step's outputs.
    for n in range(1, 5):
        assert f"model{n}: ${{{{ steps.chain.outputs.link{n}_model }}}}" in text
    # Each of the three reviewer jobs sources all four links (4 × 3 = 12 refs).
    sourced = re.findall(r"--model \$\{\{ needs\.design-changes\.outputs\.model[1-4] \}\}", text)
    assert len(sourced) == 12, f"expected 12 sourced --model refs, found {len(sourced)}"


def test_link_count_matches_workflow_slots():
    # The workflow has exactly 4 ship-step slots per job; the chain must fill them.
    links = Registry.load(str(REGISTRY)).resolve("review")
    assert len(links) == len(EXPECTED_SLOT_PROVIDERS) == 4
