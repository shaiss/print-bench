"""steps: the agent-step grammar, one fixture per naming era (scaffold-implemented; H4 owns)."""

from __future__ import annotations

import pytest

from conftest import contract, receipt, receipts
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


@pytest.mark.parametrize("name,lead,provider,link", [
    # The shapes the fixture receipts actually carry, beyond the table above.
    ("Run via Anthropic (Claude, chain link 4)", "Run", "anthropic", 4),
    ("/drik-review via Z.AI GLM (chain link 1)", "/drik-review", "zai", 1),
    ("/design-coach via Z.AI GLM (chain link 2)", "/design-coach", "zai", 2),
    ("Oracle via Anthropic (chain link 3)", "Oracle", "anthropic", 3),
    ("Propose via Z.AI (GLM, chain link 1)", "Propose", "zai", 1),
])
def test_e3_shapes_in_the_receipts(name, lead, provider, link):
    p = steps.parse_step_name(name)
    assert (p.era, p.lead, p.provider, p.link, p.label) == ("E3", lead, provider, link, None)


@pytest.mark.parametrize("name", [
    "Run via Z.AI (GLM, chain link 0)",           # links are 1-based
    "Run via Z.AI (GLM, chain link 100)",         # at most two digits (contract chain_link <= 99)
    "Run via Z.AI (GLM, chain link 3) again",     # anchored at the end
    "Please Run via Z.AI (GLM, chain link 3)",    # anchored at the start
    "Run via Gemini (chain link 1)",              # closed provider set
    "/jane-review via Z.AI GLM five",             # E2 label must be a version
    "Run /oracle (unattended)",                   # E0 is the three reviewer leads only
])
def test_near_misses_parse_as_nothing(name):
    assert steps.parse_step_name(name) is None


def test_e2_label_is_carried_but_never_a_link():
    p = steps.parse_step_name("/pm triage via Anthropic Opus 4.8")
    assert (p.era, p.label, p.link, p.provider) == ("E2", "Opus 4.8", None, "anthropic")
    assert steps.parse_step_name("/jane-review via Z.AI GLM 5.2").label == "5.2"


def test_every_fixture_receipt_agrees_with_the_grammar():
    """Docs §Receipts: every agent step of the watched workflows parses, none is suspicious, and a
    receipt is full exactly when an agent step ran (or a suspicious one exists)."""
    rs = receipts()
    assert len(rs) == 166
    for r in rs:
        assert r["step_grammar"] == steps.STEP_GRAMMAR_VERSION
        if r["kind"] == "full":
            assert steps.jobs_have_agent_step(r["jobs"]) or steps.suspicious_step_names(r["jobs"])
            assert r["suspicious_steps"] == steps.suspicious_step_names(r["jobs"]) == []
        else:
            assert r["jobs"] is None and r["stub"] is not None
    # Every routine/reviewer receipt that ran an agent resolves a role for each of its agent steps.
    for r in rs:
        for job in r["jobs"] or []:
            for _, p in steps.agent_steps(job):
                assert p.role(r["workflow"]) in steps.ROLES, (r["workflow"], p)


def test_roles_are_the_contract_enum_and_cover_both_tables():
    assert set(steps.ROLES) == set(contract()["enums"]["role"])
    assert set(steps.ROLE_BY_LEAD.values()) | set(steps.ROUTINE_ROLE_BY_WORKFLOW.values()) <= set(steps.ROLES)
    # A Run/Ship lead in an unknown workflow has no role (never guessed).
    assert steps.parse_step_name("Run via Z.AI (GLM, chain link 1)").role("mystery.yml") is None


def test_skipped_links_never_ran():
    assert steps.step_ran({"conclusion": "success"}) and steps.step_ran({"conclusion": "failure"})
    assert steps.step_ran({"conclusion": None})          # still in progress / unknown is not "skipped"
    assert not steps.step_ran({"conclusion": "skipped"})
    assert steps.last_run_link({"steps": [{"name": "Run via Z.AI (GLM, chain link 1)", "conclusion": "skipped"}]}) is None
