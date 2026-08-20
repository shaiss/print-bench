"""Drift guard: the committed registry and its consumer workflows cannot silently diverge.

auto-review.yml only runs on design PRs, so this PR's CI does not live-exercise the
migrated review pipeline. This test is the standing proof that the registry drives
the workflow and stays consistent with it. product-scout.yml (issue #243) is the
second consumer, guarded the same way at the bottom of this file.

The load-bearing check parses each reviewer job's ordered ship steps and asserts,
**position for position, derived from `Registry.resolve("review")`**:

* the step at slot k sources `--model … outputs.model{k}` — the slot→model binding,
  so a scrambled reference (slot 1 pulling `model4`) is caught, not just the count;
* the step's literal `anthropic_api_key: secrets.<X>` is the registry link's secret
  at that position — so slots 1–3 wire `ZAI_KEY`, slots 4–6 `ANTHROPIC_API_KEY`
  (the #298 Anthropic tail), and swapping one is caught;
* the step's `ANTHROPIC_BASE_URL` matches the link's `base_url` exactly — present
  and equal for Z.AI (the Anthropic-compatible endpoint), absent for Anthropic —
  so pointing a slot at the wrong endpoint is caught.

Everything is *derived from the registry*, never restated as a hand-copied constant:
the test reads the YAML and compares it against what the registry resolves to. A
model routed to the wrong provider/secret/endpoint — the exact failure the migration
promised to make impossible — fails here.

It deliberately does NOT pin the specific model *ids* — reordering/swapping a model
*within a provider* is exactly the registry edit #206 exists to allow, and stays
green. Changing the slot→provider *shape*, scrambling a slot's model reference,
rewiring a secret, or reverting to a hardcoded literal is what fails, pointing you
at the YAML that must change with the registry.
"""

from __future__ import annotations

import pathlib
import re

from model_registry.registry import Registry

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "auto-review.yml"
SCOUT_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "product-scout.yml"
REGISTRY = REPO_ROOT / ".github" / "models" / "registry.conf"

# The reviewer-round jobs that carry the fallback chain — the two reviewer
# personas, the PM triage gate on their feedback, and the coach. Each has one
# ship step per registry link, in chain order.
REVIEWER_JOBS = ("jane-review", "drik-review", "pm-triage", "design-coach")

# A top-level job header: a 2-space-indented `name:` with no inline value. Only
# valid inside the `jobs:` section (elsewhere — e.g. `on:` → `pull_request:` — a
# 2-space bare key is not a job), so callers slice from `jobs:` first.
_JOB_HEADER = re.compile(r"^  ([a-z][a-z0-9-]*):[ \t]*$", re.MULTILINE)


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _job_blocks(text: str) -> dict[str, str]:
    """Map each job name to its text block (header to the next job / EOF)."""
    jobs_at = re.search(r"^jobs:[ \t]*$", text, re.MULTILINE)
    assert jobs_at, "workflow has no `jobs:` section"
    section = text[jobs_at.start():]
    heads = [(m.group(1), m.start()) for m in _JOB_HEADER.finditer(section)]
    blocks: dict[str, str] = {}
    for i, (name, start) in enumerate(heads):
        end = heads[i + 1][1] if i + 1 < len(heads) else len(section)
        blocks[name] = section[start:end]
    return blocks


def _ship_steps(job_text: str) -> list[dict]:
    """The job's claude-code-action ship steps, in order, as parsed wiring.

    Steps live at 6-space indent (`      - …`); a ship step is one that invokes
    the claude-code-action (the checkout and the notice/failure steps are not).
    """
    steps: list[dict] = []
    for chunk in re.split(r"\n      - ", job_text):
        if "uses: anthropics/claude-code-action" not in chunk:
            continue
        model = re.search(
            r"--model \$\{\{ needs\.design-changes\.outputs\.model(\d+) \}\}", chunk)
        secret = re.search(r"anthropic_api_key: \$\{\{ secrets\.(\w+) \}\}", chunk)
        base = re.search(r"ANTHROPIC_BASE_URL: (\S+)", chunk)
        steps.append({
            "model_slot": int(model.group(1)) if model else None,
            "secret": secret.group(1) if secret else None,
            "base_url": base.group(1) if base else "",
        })
    return steps


def test_committed_registry_is_valid():
    # A malformed committed registry would fail the resolve step at run time and
    # block every design PR's review — catch it here instead.
    Registry.load(str(REGISTRY))


def test_every_ship_step_is_pinned_to_its_registry_link():
    """Each reviewer job's ship steps match the resolved chain, position for position.

    This is the guard's core: it reads the *workflow* and compares each slot's
    model reference, literal secret, and endpoint against what the *registry*
    resolves to — so a scrambled model reference, a rewired secret, or a wrong
    endpoint in any of the four jobs fails, and nothing is restated as a constant.
    """
    links = Registry.load(str(REGISTRY)).resolve("review")
    assert links, "the `review` chain resolved to zero links"

    blocks = _job_blocks(_workflow_text())
    checked = []
    for job in REVIEWER_JOBS:
        assert job in blocks, f"reviewer job {job!r} not found in auto-review.yml"
        steps = _ship_steps(blocks[job])
        checked.append(job)
        # One ship step per link, in chain order. A chain that grew/shrank without
        # the YAML gaining/losing a ship step fails right here.
        assert len(steps) == len(links), (
            f"{job}: {len(steps)} claude-code-action ship steps but the `review` "
            f"chain has {len(links)} links — add/remove a ship step to match.")
        for link, step in zip(links, steps):
            # Slot k must source `outputs.model{k}` (the slot→model binding), NOT
            # merely *some* modelN — this is what a positional scramble breaks.
            assert step["model_slot"] == link.position, (
                f"{job} slot {link.position}: references model{step['model_slot']} "
                f"but must reference model{link.position} (the chain's order).")
            # The step's literal secret must be the link's provider secret.
            assert step["secret"] == link.secret, (
                f"{job} slot {link.position}: wires secrets.{step['secret']} but the "
                f"registry routes this position to secrets.{link.secret}.")
            # The endpoint must match exactly: the Z.AI base_url for a Z.AI link,
            # absent (empty) for Anthropic's native endpoint.
            assert step["base_url"] == link.base_url, (
                f"{job} slot {link.position}: ANTHROPIC_BASE_URL is "
                f"{step['base_url']!r} but the registry endpoint is {link.base_url!r}.")
    assert checked == list(REVIEWER_JOBS)


def test_design_changes_exposes_one_model_output_per_link():
    # The design-changes job must publish model1..model{N} wired to the resolve
    # step's outputs, one per chain link, or a ship step references an empty output.
    links = Registry.load(str(REGISTRY)).resolve("review")
    text = _workflow_text()
    assert "model_registry resolve review" in text, (
        "the resolve step no longer targets the `review` chain")
    for n in range(1, len(links) + 1):
        assert f"model{n}: ${{{{ steps.chain.outputs.link{n}_model }}}}" in text, (
            f"design-changes does not expose model{n} wired to link{n}_model")


def test_no_hardcoded_model_literal_survives():
    # Every `--model` argument must be a `${{ … }}` expression sourced from the
    # resolve outputs. A hardcoded id of ANY provider (glm-*, claude-*, gpt-*, …)
    # is a regression back to per-job hardcoding and fails — not just the two id
    # prefixes an allow-list would know about.
    text = _workflow_text()
    literals = [tok for tok in re.findall(r"--model\s+(\S+)", text)
                if not tok.startswith("${{")]
    assert not literals, f"hardcoded --model literal(s) in auto-review.yml: {literals}"


# ── The product scout (issue #243) ────────────────────────────────────────────
#
# The scout is the registry's second consumer, migrated in #243. Its shape is
# the groomer-narrative one, not the review one: a SINGLE-link chain, and the
# workflow resolves it in the same job that consumes it (`steps.chain.outputs`,
# not a `needs.`-scoped job output). The guard below proves the same property
# the reviewer guard proves — the registry drives the model, the YAML carries
# only literal secrets — adapted to that shape: one ship step per provider,
# each sourcing `--model` from `steps.chain.outputs.link1_model`, each wiring
# the secret the registry says its link's provider uses, each endpoint matching
# the link's base_url.
#
# The degraded path is part of what's pinned: when the configured provider's
# secret is absent the run steps must be SKIPPED and the notice step must fire,
# never silently run (and never hard-fail) — that is the skip #243 requires to
# survive the migration verbatim.

SCOUT_CHAIN = "scout"


def _scout_text() -> str:
    return SCOUT_WORKFLOW.read_text(encoding="utf-8")


def _scout_ship_steps(text: str) -> list[dict]:
    """The scout job's claude-code-action ship steps, parsed for their wiring."""
    steps: list[dict] = []
    for chunk in re.split(r"\n      - ", text):
        if "uses: anthropics/claude-code-action" not in chunk:
            continue
        model = re.search(
            r"--model \$\{\{ steps\.chain\.outputs\.link(\d+)_model \}\}", chunk)
        secret = re.search(r"anthropic_api_key: \$\{\{ secrets\.(\w+) \}\}", chunk)
        base = re.search(r"ANTHROPIC_BASE_URL: (\S+)", chunk)
        steps.append({
            "model_slot": int(model.group(1)) if model else None,
            "secret": secret.group(1) if secret else None,
            "base_url": base.group(1) if base else "",
        })
    return steps


def test_scout_chain_exists_and_resolves():
    # The chain #243 named. A registry edit that dropped it would fail the
    # workflow's resolve step at run time — on the scout's weekly cadence, where
    # nobody is watching. Catch it here instead.
    links = Registry.load(str(REGISTRY)).resolve(SCOUT_CHAIN)
    assert links, f"the `{SCOUT_CHAIN}` chain resolved to zero links"


def test_scout_ship_steps_are_pinned_to_its_registry_link():
    """Every scout ship step reads its model from the resolved chain, sources it
    from the resolve step's output, and carries exactly one endpoint/secret pair
    per provider — the model id itself appears nowhere in the YAML.

    The chain's link pins the CURRENT provider's wiring (secret + endpoint
    must match the link's provider exactly); the other provider's step is
    checked structurally (a `${{ }}` model reference, and a secret/endpoint
    belonging to a declared registry provider) because the conf's `provider:`
    label — not the chain — picks which step runs. A conf/chain provider
    mismatch is caught at run time by the workflow's own cross-check and
    pre-merge by the test below this one.
    """
    reg = Registry.load(str(REGISTRY))
    link = reg.resolve(SCOUT_CHAIN)[0]
    text = _scout_text()
    steps = _scout_ship_steps(text)
    assert steps, "no claude-code-action ship step found in product-scout.yml"
    secrets_by_provider = {p.id: p.secret for p in reg.providers.values()}
    bases_by_provider = {p.id: p.base_url for p in reg.providers.values()}
    matched_current = False
    for step in steps:
        # Every step — whichever provider it belongs to — must take its model
        # from the resolve step's output at the link's position. A literal here
        # is the regression #243 exists to remove.
        assert step["model_slot"] == link.position, (
            f"scout ship step: references link{step['model_slot']}_model but the "
            f"`{SCOUT_CHAIN}` chain has its only model at position {link.position}.")
        # The step's secret must belong to a DECLARED provider, and together
        # with its endpoint must identify exactly one — a rewired or invented
        # secret is caught here.
        providers_with_secret = [pid for pid, s in secrets_by_provider.items()
                                 if s == step["secret"]]
        assert len(providers_with_secret) == 1, (
            f"scout ship step: wires secrets.{step['secret']}, which matches no "
            f"single registry provider (matches: {providers_with_secret}).")
        step_provider = providers_with_secret[0]
        assert step["base_url"] == bases_by_provider[step_provider], (
            f"scout ship step: wires secrets.{step['secret']} with "
            f"ANTHROPIC_BASE_URL {step['base_url']!r} but registry provider "
            f"{step_provider!r} uses {bases_by_provider[step_provider]!r}.")
        if step_provider == link.provider:
            # The step that will actually run (the conf label selects it when
            # it matches the chain's provider) must match the link exactly.
            matched_current = True
    assert matched_current, (
        f"no scout ship step carries the `{SCOUT_CHAIN}` chain's provider "
        f"{link.provider!r} (secret {link.secret}) — the configured provider "
        f"would have no step to run, or would run one wired for another "
        f"provider's endpoint.")


def test_scout_workflow_cross_checks_chain_and_conf_providers():
    # The workflow itself must refuse a conf/chain provider mismatch at resolve
    # time (before any key is spent), or the model would run against the wrong
    # provider's endpoint and fail mid-run. This pins that guard's presence so
    # it cannot be dropped as "unreachable" cleanup later.
    text = _scout_text()
    assert re.search(r"link1_provider", text), (
        "product-scout.yml no longer reads link1_provider — the conf/chain "
        "provider cross-check is gone")


def test_scout_resolves_its_chain_in_workflow():
    # The resolve step must target the `scout` chain, or every ship step's
    # `link1_model` reference reads an empty output and the action errors.
    text = _scout_text()
    assert f"model_registry resolve {SCOUT_CHAIN}" in text, (
        "product-scout.yml no longer resolves the `scout` chain")


def test_scout_degraded_path_skips_with_a_notice():
    """The secret-absent path stays a `::notice::` skip, not a hard fail.

    #243 requires the degraded path preserved verbatim: the run steps' `if:`
    must gate on `key_present` (so an absent key skips them), and the step that
    explains the skip must still emit a `::notice::` naming the provider and
    its key. Reverting either — running without a key, or failing loudly —
    changes what the issue pinned as unchanged.
    """
    text = _scout_text()
    assert re.search(
        r"steps\.policy\.outputs\.key_present\s*==\s*'1'", text), (
        "the scout run steps no longer gate on key_present — an absent key "
        "would not skip them")
    assert "::notice::the configured provider" in text, (
        "the secret-absent notice is gone — the degraded path must stay a "
        "::notice:: skip, per #243")


def test_scout_no_hardcoded_model_literal_survives():
    # The #243 acceptance criterion as a test: no `--model` literal of ANY
    # provider may appear in product-scout.yml — every one must be a `${{ … }}`
    # expression sourced from the resolve step's outputs.
    text = _scout_text()
    literals = [tok for tok in re.findall(r"--model\s+(\S+)", text)
                if not tok.startswith("${{")]
    assert not literals, f"hardcoded --model literal(s) in product-scout.yml: {literals}"
