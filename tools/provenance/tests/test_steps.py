"""steps: the agent-step grammar, one fixture per naming era (scaffold-implemented; H4 owns)."""

from __future__ import annotations

import pytest

from conftest import receipt
from provenance import steps


@pytest.mark.parametrize("name,era,lead,provider,link,role,workflow", [
    ("Run /jane-review (unattended)", "E0", "/jane-review", None, None, "jane", "auto-review.yml"),
    ("Run via Anthropic (Claude)", "E1", "Run", "anthropic", None, "design-run", "design-run.yml"),
    ("Ship via Z.AI (GLM)", "E1", "Ship", "zai", None, "backlog-burn", "backlog-burn.yml"),
    ("/jane-review via Z.AI GLM 5.2", "E2", "/jane-review", "zai", None, "jane", "auto-review.yml"),
    ("/pm triage via Anthropic Opus 5", "E2", "/pm triage", "anthropic", None, "pm", "auto-review.yml"),
    ("Run via Z.AI (GLM, chain link 3)", "E3", "Run", "zai", 3, "design-run", "design-run.yml"),
    ("Ship via OpenRouter (OSS, chain link 6)", "E3", "Ship", "openrouter", 6, "backlog-burn", "backlog-burn.yml"),
    ("/drik-review via Anthropic (chain link 4)", "E3", "/drik-review", "anthropic", 4, "drik", "auto-review.yml"),
    ("Oracle via Z.AI GLM (chain link 1)", "E3", "Oracle", "zai", 1, "oracle", "oracle.yml"),
    ("Sign off via Z.AI (GLM, chain link 2)", "E3", "Sign off", "zai", 2, "reeve-signoff", "wright.yml"),
])
def test_each_era_parses(name, era, lead, provider, link, role, workflow):
    p = steps.parse_step_name(name)
    assert (p.era, p.lead, p.provider, p.link, p.role(workflow)) == (era, lead, provider, link, role)


@pytest.mark.parametrize("name", [
    "Restore the coach posting surface from the base branch (before chain link 1)",
    "Artifact check after link 1 (did Jane's review land?)",
    "No chain link delivered the review",
    "Resolve the oracle-glm chain (issue #333)",
    "Post Run via Z.AI (GLM, chain link 1)",
    "Diagnose the exhausted chain (billing / tokens / technical)",
])
def test_lookalikes_are_not_agent_steps_and_not_suspicious(name):
    assert steps.parse_step_name(name) is None
    assert not steps.is_suspicious(name)


def test_fail_safe_flags_an_unknown_era():
    assert steps.is_suspicious("Run via Gemini (chain link 1)")
    assert steps.is_suspicious("Refresh the dedup context for chain link 2")


def test_last_run_link_masks_nothing_skipped():
    # Design run 34661448637 attempt 2: links 1-2 "success" but exited early, link 3 served.
    jobs = receipt(34661448637)["jobs"]
    job = [j for j in jobs if j["run_attempt"] == 2 and j["name"].startswith("Pick one")][0]
    step, parsed = steps.last_run_link(job)
    assert parsed.link == 3 and step["started_at"] == "2026-09-12T00:42:05Z"


def test_pre_326_run_is_full_and_disarmed_run_is_stub():
    pre = receipt(31364447108)
    assert pre["kind"] == "full"
    names = {s["name"] for j in pre["jobs"] for s in j["steps"]}
    assert {"Run via Anthropic (Claude)", "Run via Z.AI (GLM)"} <= names
