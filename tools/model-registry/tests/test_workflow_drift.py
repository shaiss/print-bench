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

import pytest

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


# ── The Oracle reviewer (issue #333) ──────────────────────────────────────────
#
# The Oracle is the registry's third consumer: the cross-vendor, reasoning-blind
# advisory reviewer on autonomy PRs. Its shape combines the other two — like the
# scout it resolves its chains in the same job that consumes them
# (`steps.<id>.outputs`), like the reviewer jobs it carries one ship step per
# chain link with first-success short-circuiting — with one twist: it resolves
# BOTH role chains (oracle-anthropic and oracle-glm) every run, and a runtime
# vendor-inversion step picks which chain's ship steps fire. The guard below
# pins each chain's ship steps to its registry links position-for-position, the
# same property the reviewer guard proves, plus the two Oracle-specific
# invariants: every ship step carries the deny backstop + dontAsk (punch-list
# item #6 — the workflow must not quietly shed it), and each role chain stays
# SINGLE-vendor with the two chains on DIFFERENT vendors (the independence bet:
# an "opposite vendor" chain that mixed vendors, or two chains on one vendor,
# would silently unmake the cross-vendor split).

ORACLE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "oracle.yml"
# chain id → the resolve step id whose outputs that chain's ship steps read.
ORACLE_CHAINS = {"oracle-anthropic": "anth", "oracle-glm": "glm"}


def _oracle_text() -> str:
    return ORACLE_WORKFLOW.read_text(encoding="utf-8")


def _oracle_ship_steps(text: str, step_id: str) -> list[dict]:
    """The ship steps sourcing their model from `steps.<step_id>.outputs`,
    in document order — i.e. one chain's steps, the other chain's excluded."""
    pat = re.compile(
        r"--model \$\{\{ steps\." + re.escape(step_id)
        + r"\.outputs\.link(\d+)_model \}\}")
    steps: list[dict] = []
    for chunk in re.split(r"\n      - ", text):
        if "uses: anthropics/claude-code-action" not in chunk:
            continue
        model = pat.search(chunk)
        if not model:
            continue  # the other chain's step (or a stray, caught by counts)
        secret = re.search(r"anthropic_api_key: \$\{\{ secrets\.(\w+) \}\}", chunk)
        base = re.search(r"ANTHROPIC_BASE_URL: (\S+)", chunk)
        steps.append({
            "model_slot": int(model.group(1)),
            "secret": secret.group(1) if secret else None,
            "base_url": base.group(1) if base else "",
            "chunk": chunk,
        })
    return steps


def _assert_oracle_chain_pinned(text: str, chain: str, step_id: str) -> None:
    """One chain's ship steps match its resolved links, position for position,
    each carrying the deny backstop. Factored out so the negative controls can
    run it against tampered workflow text."""
    links = Registry.load(str(REGISTRY)).resolve(chain)
    assert links, f"the `{chain}` chain resolved to zero links"
    steps = _oracle_ship_steps(text, step_id)
    assert len(steps) == len(links), (
        f"oracle: {len(steps)} ship steps read steps.{step_id}.outputs but the "
        f"`{chain}` chain has {len(links)} links — add/remove a ship step to match.")
    for link, step in zip(links, steps):
        assert step["model_slot"] == link.position, (
            f"oracle {chain} slot {link.position}: references "
            f"link{step['model_slot']}_model but must reference "
            f"link{link.position}_model (the chain's order).")
        assert step["secret"] == link.secret, (
            f"oracle {chain} slot {link.position}: wires secrets.{step['secret']} "
            f"but the registry routes this position to secrets.{link.secret}.")
        assert step["base_url"] == link.base_url, (
            f"oracle {chain} slot {link.position}: ANTHROPIC_BASE_URL is "
            f"{step['base_url']!r} but the registry endpoint is {link.base_url!r}.")
        # Punch-list item #6: the ship step must not shed its narrowed surface.
        assert "--permission-mode dontAsk" in step["chunk"], (
            f"oracle {chain} slot {link.position}: ship step no longer runs "
            f"under --permission-mode dontAsk.")
        assert "--settings .claude/oracle-settings.json" in step["chunk"], (
            f"oracle {chain} slot {link.position}: ship step no longer carries "
            f"the deny backstop (--settings .claude/oracle-settings.json).")


def _assert_oracle_chains_single_vendor(reg: Registry) -> None:
    """Both role chains resolve, each stays on ONE provider, and the two are
    on DIFFERENT providers — the property that makes "resolve the opposite
    vendor's chain" mean anything at all. Factored out so the negative control
    can run it against a tampered registry."""
    providers = {}
    for chain in ORACLE_CHAINS:
        links = reg.resolve(chain)
        assert links, f"the `{chain}` chain resolved to zero links"
        chain_providers = {link.provider for link in links}
        assert len(chain_providers) == 1, (
            f"the `{chain}` chain mixes providers {sorted(chain_providers)} — "
            f"a role chain must stay single-vendor or the blind review is not "
            f"cross-vendor.")
        providers[chain] = chain_providers.pop()
    assert providers["oracle-anthropic"] != providers["oracle-glm"], (
        "both oracle chains resolve to the same provider — the cross-vendor "
        "split is gone.")


def test_oracle_chains_exist_and_are_single_vendor():
    _assert_oracle_chains_single_vendor(Registry.load(str(REGISTRY)))


def test_oracle_drift_guard_catches_a_mixed_vendor_chain(tmp_path):
    # NEGATIVE CONTROL: the single-vendor guard must FAIL on a chain that
    # quietly gains the other vendor's model — the registry edit that would
    # unmake the cross-vendor split while every ship step stays green.
    text = REGISTRY.read_text(encoding="utf-8")
    tampered = text.replace(
        "models = glm-5.3, glm-5.2, glm-5.1, glm-4.6",
        "models = glm-5.3, glm-5.2, glm-5.1, claude-haiku-4-5", 1)
    assert tampered != text, "tamper target not found — the fixture is stale"
    bad = tmp_path / "registry.conf"
    bad.write_text(tampered, encoding="utf-8")
    with pytest.raises(AssertionError):
        _assert_oracle_chains_single_vendor(Registry.load(str(bad)))


def test_oracle_ship_steps_are_pinned_to_their_registry_links():
    text = _oracle_text()
    for chain, step_id in ORACLE_CHAINS.items():
        _assert_oracle_chain_pinned(text, chain, step_id)


def test_oracle_resolves_both_chains_in_workflow():
    # Both resolve steps must target their chains by name, or a ship step's
    # linkN_model reference reads an empty output and the action errors.
    text = _oracle_text()
    for chain in ORACLE_CHAINS:
        assert f"model_registry resolve {chain}" in text, (
            f"oracle.yml no longer resolves the `{chain}` chain")


def test_oracle_no_hardcoded_model_literal_survives():
    # The #333 acceptance criterion as a test: no `--model` literal of ANY
    # provider may appear in oracle.yml — every one must be a `${{ … }}`
    # expression sourced from a resolve step's outputs.
    text = _oracle_text()
    literals = [tok for tok in re.findall(r"--model\s+(\S+)", text)
                if not tok.startswith("${{")]
    assert not literals, f"hardcoded --model literal(s) in oracle.yml: {literals}"


def test_oracle_drift_guard_catches_a_scrambled_slot():
    # NEGATIVE CONTROL: the guard must FAIL on a positional scramble — slot 1
    # reading link3's model — or it proves nothing (the repo's standing rule:
    # a check that cannot fail is worthless).
    text = _oracle_text()
    tampered = text.replace(
        "steps.anth.outputs.link1_model", "steps.anth.outputs.link3_model", 1)
    assert tampered != text, "tamper target not found — the fixture is stale"
    with pytest.raises(AssertionError):
        _assert_oracle_chain_pinned(tampered, "oracle-anthropic", "anth")


def test_oracle_drift_guard_catches_a_dropped_backstop():
    # NEGATIVE CONTROL: stripping the deny backstop from a ship step must fail
    # the guard — that flag is punch-list item #6's whole enforcement. The
    # tamper is anchored inside the FIRST anth ship step (not the file's first
    # occurrence) so the control stays valid whichever chain's steps come
    # first in the workflow.
    text = _oracle_text()
    step = _oracle_ship_steps(text, "anth")[0]["chunk"]
    assert "--settings .claude/oracle-settings.json " in step, (
        "tamper target not found — the fixture is stale")
    tampered = text.replace(
        step, step.replace("--settings .claude/oracle-settings.json ", "", 1), 1)
    with pytest.raises(AssertionError):
        _assert_oracle_chain_pinned(tampered, "oracle-anthropic", "anth")


# ── The four scheduled routines (issue #326) ─────────────────────────────────
#
# The burn, the design run, the chunker and the labeler are the registry's
# third consumer group, migrated in #326. Their shape is the scout's
# (a per-routine chain resolved in the same job that consumes it,
# steps.chain.outputs) with one walk-specific addition: a ship step per LINK
# per provider, so the chain can deepen (#327) without the provider split
# (the Actions literal-secret constraint) changing shape.
#
# What the guard below proves, derived from the registry — never restated:
#
# * each routine's chain exists and every link's provider equals the provider
#   its .github/<routine>.conf declares (the run-time cross-check's subject —
#   caught here pre-merge so the workflow never spends a key against the
#   wrong endpoint);
# * every claude-code-action step in the workflow takes --model from
#   steps.chain.outputs.link<N>_model for a real link N of that chain — a
#   hardcoded literal, or a reference to a link the chain doesn't have, fails;
# * each step's literal secret matches its provider's registry secret (with
#   design-run's documented CLAUDE_KEY alias marker), and each Z.AI step
#   carries the registry's base_url — so a step can't be rewired to another
#   provider's auth silently;
# * the walk is real: each link-N step (N>1) must be gated on the earlier
#   links of its block NOT having succeeded, so a deepened chain actually
#   walks rather than running every link unconditionally;
# * the walk's OUTCOME is read off every link (#327): the AGENT_OUTCOME /
#   RUN / red-on-death expressions must treat any link's success as the
#   walk's success — an expression still reading only link 1 after the chain
#   deepened would send a healthy link-2 run red and (via
#   routine-lock-cleanup) withdraw a live run's SHIP-LOCK;
# * the run steps still gate on key_present (the #326 constraint that the
#   secret-absent path stays a ::notice:: skip, verbatim from before).
#
# The ROUTINES table drives everything; adding a fifth routine is a row here
# plus its chain in the registry.

ROUTINES = {
    # workflow file → (chain id, conf file, provider the conf declares)
    "design-run.yml":   ("design-run",   ".github/design-run.conf"),
    "backlog-burn.yml": ("backlog-burn", ".github/backlog-burn.conf"),
    "chunker.yml":      ("chunker",      ".github/chunker.conf"),
    "labeler.yml":      ("labeler",      ".github/labeler.conf"),
}

# An explicit in-workflow marker naming a step's secret as an alias for a
# registry provider's declared secret: `registry-secret-alias:
# <alias>=<registry-secret>` (design-run's anthropic link wires CLAUDE_KEY, a
# historical alias for the same credential as ANTHROPIC_API_KEY; both exist as
# repo secrets). Rewiring the secret would be a behavior change beyond #326's
# scope, so the marker is the accepted evidence instead — and the named
# registry secret is what identifies the provider (so the endpoint check still
# pins the step to a real provider's base_url).
_ALIAS_MARKER = "registry-secret-alias:"


def _routine_text(workflow: str) -> str:
    return (REPO_ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")


def _routine_provider(conf: str) -> str:
    """The `provider:` value the routine's conf declares (last assignment wins)."""
    text = (REPO_ROOT / conf).read_text(encoding="utf-8")
    values = re.findall(r"^provider:\s*(\S+)\s*$", text, re.MULTILINE)
    assert values, f"{conf} declares no provider:"
    return values[-1]


def _routine_ship_steps(text: str) -> list[dict]:
    """The routine job's claude-code-action steps, in order, as parsed wiring."""
    steps: list[dict] = []
    for chunk in re.split(r"\n      - ", text):
        if "uses: anthropics/claude-code-action" not in chunk:
            continue
        model = re.search(
            r"--model \$\{\{ steps\.chain\.outputs\.link(\d+)_model \}\}", chunk)
        secret = re.search(r"anthropic_api_key: \$\{\{ secrets\.(\w+) \}\}", chunk)
        base = re.search(r"ANTHROPIC_BASE_URL: (\S+)", chunk)
        steps.append({
            "link": int(model.group(1)) if model else None,
            "secret": secret.group(1) if secret else None,
            "base_url": base.group(1) if base else "",
            "alias": _ALIAS_MARKER in chunk,
            "gates_on_key": "key_present == '1'" in chunk,
            "chunk": chunk,
        })
    return steps


def _marker_registry_secret(step: dict) -> str:
    """The registry secret a step's alias marker names it equivalent to."""
    m = re.search(re.escape(_ALIAS_MARKER) + r"\s*(\w+)=([A-Za-z0-9_]+)",
                  step["chunk"])
    assert m, (
        f"a step carries {_ALIAS_MARKER!r} but not in the "
        "'<alias>=<registry-secret>' form — the named registry secret is what "
        "pins the step's provider/endpoint")
    return m.group(2)


def test_routine_chains_exist_and_match_their_confs():
    # Each routine's chain must exist AND sit on the provider its conf
    # declares — the run-time cross-check's subject, caught pre-merge. A chain
    # on another provider would make the workflow's resolve step fail before
    # any key is spent, so a routine would never run at all: fail here first.
    reg = Registry.load(str(REGISTRY))
    for workflow, (chain_id, conf) in ROUTINES.items():
        assert chain_id in reg.chains, (
            f"the `{chain_id}` chain (consumed by {workflow}) is missing from "
            "the registry — the workflow's resolve step would fail at run time")
        conf_provider = _routine_provider(conf)
        for link in reg.resolve(chain_id):
            assert link.provider == conf_provider, (
                f"{workflow}: link {link.position} of `{chain_id}` is on provider "
                f"{link.provider!r} but {conf} declares provider {conf_provider!r} — "
                "the walk would spend that link's key against the wrong endpoint")


def test_every_routine_ship_step_is_pinned_to_its_chain():
    """Every ship step sources --model from a real link of its routine's chain,
    and the step that can actually run is pinned to the conf's provider exactly.

    Two tiers, the scout guard's split: the conf's `provider:` label picks
    which BLOCK runs, so the block on that provider must match the chain's
    wiring exactly (secret + endpoint). The OTHER provider's block is latent —
    it runs only after someone flips the conf AND the registry chain together
    (the resolve step's cross-check refuses anything else) — so it is checked
    structurally: its model must still be a real chain link, and its
    secret/endpoint must identify exactly one declared registry provider, so
    the latent step cannot rot while nobody runs it.
    """
    reg = Registry.load(str(REGISTRY))
    for workflow, (chain_id, conf) in ROUTINES.items():
        links = reg.resolve(chain_id)
        link_positions = {link.position for link in links}
        conf_provider = _routine_provider(conf)
        secrets_by_provider = {p.id: p.secret for p in reg.providers.values()}
        bases_by_provider = {p.id: p.base_url for p in reg.providers.values()}
        steps = _routine_ship_steps(_routine_text(workflow))
        assert steps, f"no claude-code-action ship step found in {workflow}"
        matched_current = False
        for step in steps:
            assert step["link"] in link_positions, (
                f"{workflow}: a ship step references link{step['link']}_model, "
                f"but the `{chain_id}` chain has links {sorted(link_positions)} "
                "— add the registry link or fix the reference")
            assert step["secret"] is not None, (
                f"{workflow}: a ship step wires no literal anthropic_api_key secret")
            # Which provider does this step's wiring identify? An alias marker
            # names the registry secret (and so the provider) explicitly; a
            # plain secret identifies it by uniqueness among declared providers.
            if step["alias"]:
                named = _marker_registry_secret(step)
                named_providers = [pid for pid, s in secrets_by_provider.items()
                                   if s == named]
                assert len(named_providers) == 1, (
                    f"{workflow}: a step's {_ALIAS_MARKER} names {named}, which "
                    f"matches no single registry provider ({named_providers})")
                step_provider = named_providers[0]
            else:
                providers_with_secret = [pid for pid, s in secrets_by_provider.items()
                                         if s == step["secret"]]
                assert len(providers_with_secret) == 1, (
                    f"{workflow}: a ship step wires secrets.{step['secret']}, which "
                    f"matches no single registry provider (matches: "
                    f"{providers_with_secret})")
                step_provider = providers_with_secret[0]
            # Either way the endpoint must be that provider's, exactly — a
            # step wired for one provider's secret against another's endpoint
            # is the wrong-endpoint spend this guard exists to prevent.
            assert step["base_url"] == bases_by_provider[step_provider], (
                f"{workflow}: a ship step for provider {step_provider!r} carries "
                f"ANTHROPIC_BASE_URL {step['base_url']!r} but the registry "
                f"endpoint is {bases_by_provider[step_provider]!r}")
            if step_provider == conf_provider:
                # The step that will actually run (the resolve step's
                # cross-check already proved every chain link is on this
                # provider) must exist — a missing one would leave the
                # routine with no runnable step.
                matched_current = True
        assert matched_current, (
            f"{workflow}: no ship step is wired for provider {conf_provider!r} "
            f"(the provider {conf} declares) — the routine would have no step "
            "to run, or would run one wired for another provider's endpoint")



def test_routine_walks_its_chain_in_order():
    # A deepened chain (#327) must actually WALK: every link-N step with N>1
    # is gated on the earlier links of its block not having succeeded, so the
    # first success short-circuits the rest. Single-link chains (today's
    # #326 state) trivially pass — there is no second link to gate.
    reg = Registry.load(str(REGISTRY))
    for workflow, (chain_id, _conf) in ROUTINES.items():
        links = reg.resolve(chain_id)
        steps = _routine_ship_steps(_routine_text(workflow))
        by_link: dict[int, list[dict]] = {}
        for step in steps:
            by_link.setdefault(step["link"], []).append(step)
        for n in range(2, len(links) + 1):
            assert n in by_link, (
                f"{workflow}: the `{chain_id}` chain has a link {n} but no ship "
                "step references it — a registry edit landed without its "
                "workflow half (the walk stops at link 1)")
            for step in by_link[n]:
                for earlier in range(1, n):
                    block = _step_block_id(steps, earlier, step)
                    assert block is not None, (
                        f"{workflow}: link {n} has no same-block link {earlier} "
                        "step to gate on")
                    assert f"steps.{block}.outcome != 'success'" in step["chunk"], (
                        f"{workflow}: the link-{n} step is not gated on "
                        f"steps.{block}.outcome != 'success' — the walk would run "
                        "every link unconditionally instead of stopping at the "
                        "first success")


def _step_block_id(steps: list[dict], link: int, sibling: dict) -> str | None:
    """The step id of the link-`link` step in `sibling`'s provider block."""
    m = re.search(r"^\s*id:\s*(\S+)", sibling["chunk"], re.MULTILINE)
    own_id = m.group(1) if m else ""
    for step in steps:
        if step["link"] != link:
            continue
        s = re.search(r"^\s*id:\s*(\S+)", step["chunk"], re.MULTILINE)
        other = s.group(1) if s else ""
        # Same block ⇔ the ids share their provider suffix family (e.g.
        # ship_zai_1 / ship_zai_2). Match on the longest common prefix ending
        # at the link digit.
        base_own = re.sub(r"_\d+$", "", own_id)
        base_other = re.sub(r"_\d+$", "", other)
        if base_own == base_other:
            return other
    return None


def test_routine_run_steps_gate_on_key_presence():
    # #326 requires the degraded path preserved verbatim: the run steps gate
    # on key_present (an absent key skips them with a ::notice::, never a hard
    # fail), exactly as before the migration.
    for workflow in ROUTINES:
        steps = _routine_ship_steps(_routine_text(workflow))
        assert steps, f"no ship steps in {workflow}"
        for step in steps:
            assert step["gates_on_key"], (
                f"{workflow}: a ship step does not gate on key_present == '1' — "
                "an absent provider key would not skip it")


# ── The walk's OUTCOME wiring (#327) ─────────────────────────────────────────
#
# Deepening a chain is a same-PR pair with a THIRD half the step-graph tests
# above cannot see: every expression that reads the walk's result —
# AGENT_OUTCOME (which feeds routine-lock-cleanup's --agent-outcome), the
# red-on-death gate's `if`, and the summary's RUN/SHIP — must treat ANY
# link's success as the walk's success. An expression still reading only
# link 1 after the chain grew sends a healthy link-2 run red AND withdraws
# its SHIP-LOCK (the cleanup reads AGENT_OUTCOME), the exact regression the
# design-run comment warned "#327 deepens it and this expression grows a
# link2/link3 disjunct then" about.
#
# The strong form of the check is simulation: pull each `${{ … }}` outcome
# expression out of the workflow, substitute step outcomes for every walk
# state, and evaluate the GitHub-expression semantics the workflow will use
# (&&/|| short-circuit, non-empty strings truthy, comparisons string-wise).
# Structural text-matching alone would pass an expression that mentions
# link2 in a dead branch.


def _outcome_expressions(text: str) -> dict[str, list[str]]:
    """Map each outcome variable name to EVERY `${{ … }}` expression assigned it.

    AGENT_OUTCOME is assigned twice in the SHIP-LOCK workflows (the lock
    cleanup's env and the red-on-death step's env) and those two MUST agree —
    a divergence would have the cleanup release a lock while the gate still
    calls the run dead, or vice versa. So the mapping is name → list, and the
    simulation checks every occurrence.
    """
    exprs: dict[str, list[str]] = {}
    # Horizontal-whitespace-only classes: `\s` also matches `\n`, which would
    # let a repetition span lines and partition a whitespace run ambiguously
    # (the CodeQL ReDoS finding on the original pattern) — one `\n` per line,
    # matched explicitly, keeps each repetition deterministic.
    for m in re.finditer(
            r"^([ \t]+)(AGENT_OUTCOME|RUN|SHIP):[ \t]*\$\{\{(.+?)\}\}[ \t]*$",
            text, re.MULTILINE | re.DOTALL):
        exprs.setdefault(m.group(2), []).append(m.group(3))
    return exprs


def _eval_github_expression(expr: str, outcomes: dict[str, str]) -> str:
    """Evaluate one `${{ … }}` body under GitHub's operator semantics.

    Implemented as recursive descent over the &&/||/== grammar with
    `steps.<id>.outcome` context lookups and quoted string literals —
    the same subset the four workflows' walk expressions use, so a
    change to an expression the evaluator cannot parse raises (better a
    red test than an silently unexercised expression).
    """
    pos = 0

    def skip_ws():
        nonlocal pos
        while pos < len(expr) and expr[pos] in " \t\n":
            pos += 1

    def peek(tok: str) -> bool:
        skip_ws()
        return expr.startswith(tok, pos)

    def eat(tok: str) -> bool:
        nonlocal pos
        skip_ws()
        if expr.startswith(tok, pos):
            pos += len(tok)
            return True
        return False

    def parse_operand():
        nonlocal pos
        skip_ws()
        if eat("("):
            node = parse_or()
            assert eat(")"), f"unbalanced parens in walk expression: {expr!r}"
            return node
        m = re.match(r"'([^']*)'", expr[pos:])
        if m:
            pos += m.end()
            return ("lit", m.group(1))
        m = re.match(r"steps\.([A-Za-z0-9_]+)\.outcome", expr[pos:])
        if m:
            pos += m.end()
            return ("ref", m.group(1))
        # steps.policy.outputs.<key> — a plain string output; the simulation
        # fixes it to the conf's provider (the branch selector).
        m = re.match(r"steps\.policy\.outputs\.provider", expr[pos:])
        if m:
            pos += m.end()
            return ("lit", _PROVIDER_UNDER_TEST)
        m = re.match(r"always\(\)", expr[pos:])
        if m:
            pos += m.end()
            return ("lit", "always")
        m = re.match(r"env\.([A-Z_]+)", expr[pos:])
        if m:
            pos += m.end()
            return ("env", m.group(1))
        raise AssertionError(
            f"walk-outcome expression uses syntax the test evaluator cannot "
            f"parse (at offset {pos}): {expr!r}")

    def parse_eq():
        node = parse_operand()
        while peek("=="):
            eat("==")
            node = ("==", node, parse_operand())
        return node

    def parse_and():
        node = parse_eq()
        while eat("&&"):
            node = ("&&", node, parse_eq())
        return node

    def parse_or():
        node = parse_and()
        while eat("||"):
            node = ("||", node, parse_and())
        return node

    ast = parse_or()
    skip_ws()
    assert pos == len(expr), f"trailing tokens in walk expression: {expr!r}"

    def ev(node):
        """Yield GitHub's three value kinds: bool, string, or '' (null).

        Truthiness follows GitHub: booleans by their own value, strings (and
        the null '') by non-emptiness — a comparison yields a REAL boolean,
        never the string 'false', so `false && x` is falsy. Conflating the
        two (returning 'true'/'false' strings) silently inverts every
        negative comparison, which is exactly the bug this evaluator must
        not have: it would read an all-dead walk as success.
        """
        kind = node[0]
        if kind == "lit":
            return node[1]
        if kind == "ref":
            return outcomes.get(node[1], "")
        if kind == "env":
            return outcomes.get(node[1], "")
        if kind == "==":
            return ev(node[1]) == ev(node[2])
        if kind == "&&":
            left = ev(node[1])
            return ev(node[2]) if _gh_truthy(left) else left
        if kind == "||":
            left = ev(node[1])
            return left if _gh_truthy(left) else ev(node[2])
        raise AssertionError(f"unhandled AST node {node!r}")

    def _gh_truthy(val) -> bool:
        if isinstance(val, bool):
            return val
        return val != ""

    return ev(ast)


def _truthy(val: str) -> bool:
    # GitHub: a string is truthy when non-empty (after its coercion rules;
    # the expressions here only produce 'success'/'failure'/'skipped'/''/
    # 'true'/'false', all of which follow the non-empty rule — and 'false'
    # the STRING is truthy in GitHub expressions, a known quirk these
    # workflows avoid by never branching on a bare boolean literal).
    return val != ""


# The provider the simulation fixes `steps.policy.outputs.provider` to — the
# conf's declared provider, i.e. the block that actually runs. Set per
# workflow by the tests before evaluating.
_PROVIDER_UNDER_TEST = "zai"


def _walk_states(n_links: int):
    """Every combination of link outcomes worth distinguishing, labeled.

    n_links ≤ 3 keeps this at ≤ 27 rows — the full cartesian set, so the
    simulation is exhaustive rather than sampled: every state where any link
    succeeded must read success, every all-dead state must not.
    """
    from itertools import product
    values = ("success", "failure", "skipped")
    for combo in product(values, repeat=n_links):
        yield combo


def _provider_block_ids(text: str, provider: str) -> list[str]:
    """Step ids of the walk steps in `provider`'s block, link order."""
    ids = re.findall(r"id:\s*((?:run|ship)_%s_\d+)" % provider, text)
    return sorted(set(ids), key=lambda i: int(i.rsplit("_", 1)[1]))


def test_routine_walk_outcome_covers_every_link():
    """The walk's outcome expressions must read EVERY link of the active block.

    For each routine: resolve its chain, take the provider its conf declares,
    and evaluate the AGENT_OUTCOME / RUN / SHIP expression under every
    outcome combination of that block's walk steps. Any state where a link
    succeeded must yield 'success' — and the all-dead states must not.
    """
    reg = Registry.load(str(REGISTRY))
    for workflow, (chain_id, conf) in ROUTINES.items():
        links = reg.resolve(chain_id)
        provider = _routine_provider(conf)
        text = _routine_text(workflow)
        block_ids = _provider_block_ids(text, provider)
        assert len(block_ids) == len(links), (
            f"{workflow}: the `{chain_id}` chain has {len(links)} links but the "
            f"{provider} block carries {len(block_ids)} walk steps "
            f"({block_ids}) — the drift guard's step tests should have caught "
            "this first")
        exprs = _outcome_expressions(text)
        assert exprs, (
            f"{workflow}: no AGENT_OUTCOME/RUN/SHIP expression found — the "
            "walk-outcome wiring this test exists to pin is missing")
        global _PROVIDER_UNDER_TEST
        _PROVIDER_UNDER_TEST = provider
        for var, expr_list in exprs.items():
            for expr in expr_list:
                for state in _walk_states(len(links)):
                    outcomes = dict(zip(block_ids, state))
                    got = _eval_github_expression(expr, outcomes)
                    any_success = "success" in state
                    if any_success:
                        assert got == "success", (
                            f"{workflow}: {var} evaluated to {got!r} with link "
                            f"outcomes {dict(zip(block_ids, state))} — a link "
                            "succeeded but the walk's outcome is not success; "
                            "the expression does not cover every link of the "
                            "walk")
                    else:
                        assert got != "success", (
                            f"{workflow}: {var} read {got!r} with no link "
                            f"having succeeded ({state}) — the walk claims a "
                            "success nobody produced")


def test_routine_red_on_death_gates_on_whole_chain_failure():
    """The red-on-death `if` must fire exactly when NO link succeeded.

    Simulates the gate's condition under every outcome combination: green
    when any link succeeded, red when none did. A gate still pinned to link 1
    alone would fire (fail the job) after a healthy link-2 run.
    """
    reg = Registry.load(str(REGISTRY))
    for workflow, (chain_id, conf) in ROUTINES.items():
        if workflow not in ("design-run.yml", "backlog-burn.yml"):
            continue  # only these two carry the SHIP-LOCK red-on-death step
        links = reg.resolve(chain_id)
        provider = _routine_provider(conf)
        text = _routine_text(workflow)
        block_ids = _provider_block_ids(text, provider)
        # Horizontal whitespace only (`[ \t]`, one explicit \n per repetition):
        # a `\s` class also matches `\n`, which lets a repetition span lines
        # and partition a run of blank/indented lines ambiguously — the
        # exponential-backtracking shape CodeQL flagged on the original.
        m = re.search(
            r"name:[ \t]*Turn a dead agentic run red(?:[ \t]*#.*)?\n"
            r"(?:[ \t]*#.*\n)*"
            r"[ \t]*if: >-\n((?:[ \t]+.*\n)+?)(?=[ \t]*\w+:)",
            text)
        assert m, (
            f"{workflow}: the 'Turn a dead agentic run red' step's if-condition "
            "was not found — the SHIP-LOCK lifecycle wiring changed shape")
        cond = " ".join(l.strip() for l in m.group(1).splitlines())
        # Drop the legs the simulation fixes green (policy/enabled/select/
        # key/dry_run) and the leading always(), leaving the outcome clause.
        sim_cond = cond
        sim_cond = re.sub(r"^always\(\)\s*&&\s*", "", sim_cond)
        sim_cond = re.sub(
            r"steps\.policy\.outputs\.(enabled|key_present)\s*==\s*'(true|1)'\s*&&\s*",
            "", sim_cond)
        sim_cond = re.sub(r"steps\.select\.outputs\.\w+\s*!=\s*''\s*&&\s*", "", sim_cond)
        sim_cond = re.sub(r"github\.event\.inputs\.dry_run\s*!=\s*'true'\s*&&\s*", "", sim_cond)
        # The surviving clause is `(walk-success test) != 'success'`.
        mm = re.match(r"^\((.+)\)\s*!=\s*'success'\s*$", sim_cond.strip())
        assert mm, (
            f"{workflow}: the red-on-death condition's outcome clause does not "
            f"match the expected `(walk) != 'success'` shape after stripping "
            f"the fixed-green legs: {sim_cond!r}")
        inner = mm.group(1)
        for state in _walk_states(len(links)):
            outcomes = dict(zip(block_ids, state))
            walk = _eval_github_expression(inner, outcomes)
            # `inner` is the walk-OUTCOME expression (the same string form as
            # AGENT_OUTCOME): it yields the string 'success' when any link
            # succeeded, else a non-'success' string ('failure'/'skipped'/'').
            # The gate is `(inner) != 'success'`, a STRING comparison — it must
            # NOT reduce to a bool, because GitHub coerces `(bool) != 'success'`
            # to numbers (true→1, 'success'→NaN) so it is ALWAYS true: the
            # always-red bug this shape must avoid, and did not before this fix.
            assert isinstance(walk, str), (
                f"{workflow}: the red-on-death walk clause must reduce to a "
                f"string outcome, so `!= 'success'` is a string compare rather "
                f"than an always-true bool-vs-string: {inner!r} → {walk!r}")
            fired = walk != "success"
            any_success = "success" in state
            assert fired == (not any_success), (
                f"{workflow}: the red-on-death gate fired={fired} under link "
                f"outcomes {dict(zip(block_ids, state))} — expected "
                f"fired={not any_success}; the gate does not cover the whole "
                "chain")


def test_walk_outcome_guard_fires_on_a_stale_link1_expression(tmp_path, monkeypatch):
    """Negative control: prove the walk-outcome guard can fail.

    The regression it exists for is a chain deepened while an outcome
    expression still reads only link 1 — the exact drift the design-run
    comment warned about. Reintroduce it in a copy of design-run.yml (revert
    AGENT_OUTCOME to the pre-#327 link-1-only form) and re-run the real
    assertions against the mutated tree, which must FAIL: with a link-2
    success, the stale expression reports the walk as dead, which would
    withdraw a live run's SHIP-LOCK.
    """
    import shutil
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    for workflow in ROUTINES:
        shutil.copy(REPO_ROOT / ".github" / "workflows" / workflow, workflows_dir)
    victim = workflows_dir / "design-run.yml"
    text = victim.read_text(encoding="utf-8")
    stale = ("steps.run_zai_1.outcome == 'success' && 'success' || "
             "steps.run_zai_2.outcome == 'success' && 'success' || "
             "steps.run_zai_3.outcome")
    # EVERY occurrence — AGENT_OUTCOME is assigned twice (lock cleanup env,
    # red-on-death env) and both must go stale together for this mutation to
    # represent the real regression; mutating only the first leaves the
    # extractor's second occurrence healthy and the control passes vacuously.
    assert text.count(stale) >= 2, (
        "the live AGENT_OUTCOME expression changed shape — update the mutation")
    victim.write_text(text.replace(stale, "steps.run_zai_1.outcome"),
                      encoding="utf-8")

    original = _routine_text

    def _mutated(workflow: str) -> str:
        mutated = workflows_dir / workflow
        if mutated.exists():
            return mutated.read_text(encoding="utf-8")
        return original(workflow)

    monkeypatch.setitem(globals(), "_routine_text", _mutated)
    try:
        test_routine_walk_outcome_covers_every_link()
    except AssertionError:
        return  # the guard fired — the control passes
    raise AssertionError(
        "the walk-outcome guard passed on an AGENT_OUTCOME expression that "
        "still reads only link 1 after the chain deepened — it has been "
        "weakened into a restatement")


def test_red_on_death_guard_fires_on_a_stale_link1_gate(tmp_path, monkeypatch):
    """Negative control for the red-on-death gate simulation.

    Same mutation class, different surface: the gate's `if` still pinned to
    link 1 would fire (fail the job) after a healthy link-2 run. Reintroduce
    that in a copy of backlog-burn.yml and require the simulation to fail.
    """
    import shutil
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    for workflow in ROUTINES:
        shutil.copy(REPO_ROOT / ".github" / "workflows" / workflow, workflows_dir)
    victim = workflows_dir / "backlog-burn.yml"
    text = victim.read_text(encoding="utf-8")
    stale = ("(steps.ship_zai_1.outcome == 'success' && 'success' || "
             "steps.ship_zai_2.outcome == 'success' && 'success' || "
             "steps.ship_zai_3.outcome)")
    # EVERY occurrence — the string-form walk-outcome expression is quoted by
    # the red-on-death gate's `if:` AND both AGENT_OUTCOME envs (the lock
    # cleanup and the red-on-death step); a stale gate means all its copies are
    # stale, and mutating only one would leave the gate the simulation reads
    # untouched (the control would pass vacuously).
    assert text.count(stale) >= 2, (
        "the live walk-test expression changed shape — update the mutation")
    victim.write_text(text.replace(stale, "(steps.ship_zai_1.outcome)"),
                      encoding="utf-8")

    original = _routine_text

    def _mutated(workflow: str) -> str:
        mutated = workflows_dir / workflow
        if mutated.exists():
            return mutated.read_text(encoding="utf-8")
        return original(workflow)

    monkeypatch.setitem(globals(), "_routine_text", _mutated)
    try:
        test_routine_red_on_death_gates_on_whole_chain_failure()
    except AssertionError:
        return  # the guard fired — the control passes
    raise AssertionError(
        "the red-on-death simulation passed on a gate still pinned to link 1 "
        "after the chain deepened — it has been weakened into a restatement")


def test_no_hardcoded_model_literal_in_any_routine():
    # The #326 acceptance criterion as a test: no --model literal of ANY
    # provider may appear in any of the four routine workflows.
    for workflow in ROUTINES:
        text = _routine_text(workflow)
        literals = [tok for tok in re.findall(r"--model\s+(\S+)", text)
                    if not tok.startswith("${{")]
        assert not literals, (
            f"hardcoded --model literal(s) in {workflow}: {literals}")


def test_routine_guards_fire_on_a_reintroduced_literal(tmp_path, monkeypatch):
    """The negative control AC6 asks for: prove the guard can fail, not just pass.

    Reintroduces a hardcoded --model literal into a copy of the routine
    workflows and re-runs the real assertions against the mutated tree,
    which must FAIL — so the guard cannot be weakened into an always-green
    restatement without this test going red with it.
    """
    import shutil
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    for workflow in ROUTINES:
        shutil.copy(REPO_ROOT / ".github" / "workflows" / workflow, workflows_dir)
    victim = workflows_dir / "labeler.yml"
    text = victim.read_text(encoding="utf-8")
    assert "--model ${{ steps.chain.outputs.link1_model }}" in text
    victim.write_text(text.replace(
        "--model ${{ steps.chain.outputs.link1_model }}",
        "--model glm-5.2", 1), encoding="utf-8")

    # Point the guard's own path helper at the mutated tree, then re-run the
    # real assertions: with a literal present, at least one must fail.
    original = _routine_text

    def _mutated(workflow: str) -> str:
        mutated = workflows_dir / workflow
        if mutated.exists():
            return mutated.read_text(encoding="utf-8")
        return original(workflow)

    monkeypatch.setitem(globals(), "_routine_text", _mutated)
    try:
        test_no_hardcoded_model_literal_in_any_routine()
    except AssertionError:
        return  # the guard fired — the control passes
    raise AssertionError(
        "the no-literal guard passed on a workflow carrying a hardcoded "
        "--model glm-5.2 — it has been weakened into a restatement")


# ── Provider-failure triage wiring (smarter chain-exhaustion routing) ─────────
#
# Every chain-walking consumer must, when its chain fails on EVERY link, invoke
# the shared provider-triage composite action with ITS OWN chain — so the cause
# (billing / out-of-tokens / bad key / dead id / transient) is recovered and the
# human-fixable ones escalate through the decision gate, instead of a silent
# scheduled red. The action is the one tested home for that logic (the classify
# core has its own suite in test_smoke.py); the guard below pins that each
# consumer stays wired to it AND triages the same chain it walks — a mis-named
# chain would diagnose a DIFFERENT registry chain than the one that just failed.

TRIAGE_ACTION = REPO_ROOT / ".github" / "actions" / "provider-triage" / "action.yml"
TRIAGE_CONSUMERS = {
    "auto-review.yml": "review",
    "backlog-burn.yml": "backlog-burn",
    "design-run.yml": "design-run",
    "chunker.yml": "chunker",
    "labeler.yml": "labeler",
}


def _triage_chains(text: str) -> list[str]:
    """The `chain:` input of every provider-triage invocation in a workflow."""
    chains: list[str] = []
    for chunk in re.split(r"\n      - ", text):
        if "uses: ./.github/actions/provider-triage" not in chunk:
            continue
        m = re.search(r"^[ \t]*chain:[ \t]*(\S+)", chunk, re.MULTILINE)
        chains.append(m.group(1) if m else None)
    return chains


def test_every_consumer_wires_provider_triage_to_its_own_chain():
    for workflow, chain in TRIAGE_CONSUMERS.items():
        text = (REPO_ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
        chains = _triage_chains(text)
        assert chains, (
            f"{workflow} no longer invokes ./.github/actions/provider-triage on "
            "chain exhaustion — the smarter billing/tokens/technical routing is gone")
        assert all(c == chain for c in chains), (
            f"{workflow}: provider-triage is wired to chain(s) {chains}, but this "
            f"workflow walks the {chain!r} chain — it would diagnose the wrong one")
        # It must triage the SAME chain it resolves/walks.
        assert f"model_registry resolve {chain}" in text, (
            f"{workflow} triages chain {chain!r} but does not resolve it — the "
            "walk and the diagnosis have drifted apart")


def test_provider_triage_action_declares_the_io_its_callers_use():
    # A rename or dropped input/output would break all five callers at once;
    # actionlint catches an unknown `with:` key, and this pins the contract the
    # callers depend on (the classify chain input, both provider keys, the token,
    # the escalate switch, and the class/reason outputs the callers read).
    action = TRIAGE_ACTION.read_text(encoding="utf-8")
    for decl in ("chain:", "zai-key:", "anthropic-key:", "github-token:",
                 "context:", "escalate:"):
        assert decl in action, f"provider-triage no longer declares input {decl!r}"
    assert re.search(r"^outputs:", action, re.MULTILINE), "provider-triage lost its outputs block"
    for out in ("class:", "reason:"):
        assert out in action, f"provider-triage no longer declares output {out!r}"
    # The action must actually run the classifier that produces class+reason.
    assert "model_registry classify" in action, (
        "provider-triage no longer runs `model_registry classify` — its class/reason "
        "outputs would be empty and every caller's branch would misfire")


def test_triage_wiring_guard_discriminates_a_wrong_chain():
    # NEGATIVE CONTROL: the same rule, run against a workflow whose triage chain
    # was swapped to another consumer's, must NOT pass — or the guard proves
    # nothing (a check that cannot fail is worthless, the repo's standing rule).
    text = (REPO_ROOT / ".github" / "workflows" / "labeler.yml").read_text(encoding="utf-8")
    tampered = text.replace("chain: labeler", "chain: review", 1)
    assert tampered != text, "tamper target not found — the fixture is stale"
    chains = _triage_chains(tampered)
    assert not all(c == "labeler" for c in chains), (
        "the triage-chain check did not react to a swapped chain — it has been "
        "weakened into a restatement")


# ── The agent forge (Wright + Reeve's sign-off, docs/agent-forge.md) ─────────
#
# The forge is the registry's next consumer: ONE workflow (wright.yml), TWO
# chains — `wright` (the propose half, single-link, the scout's shape) and
# `wright-signoff` (the judging half, a walking tail, the labeler's shape) —
# each resolved by its own step id in its own job, the Oracle's two-chain
# pattern. The guard pins each chain's ship steps to its registry links, the
# conf/chain provider agreement, the per-half deny backstop + dontAsk on
# every ship step (the sign-off can apply `autonomy-ok`, so a quietly-shed
# backstop there is the worst drift in the family), the sign-off walk's
# gating, and — by simulation — that the sign-off RUN expression reads every
# link, with a negative control proving the simulation can fail.

WRIGHT_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "wright.yml"
WRIGHT_CONF = ".github/wright.conf"
# chain id → (the resolve step id whose outputs that chain's ship steps read,
#             the half's OWN deny backstop the ship steps must carry)
WRIGHT_CHAINS = {
    "wright": ("propose_chain", ".claude/wright-settings.json"),
    "wright-signoff": ("signoff_chain", ".claude/reeve-signoff-settings.json"),
}
# The sign-off walk's step ids in the conf provider's block, link order.
WRIGHT_SIGNOFF_BLOCK = ("signoff_zai_1", "signoff_zai_2", "signoff_zai_3")


def _wright_text() -> str:
    return WRIGHT_WORKFLOW.read_text(encoding="utf-8")


def test_wright_chains_exist_and_match_conf():
    # Both chains must exist AND every link must sit on the provider
    # .github/wright.conf declares — the workflow resolve steps' run-time
    # cross-check, caught pre-merge (a mismatched link would spend a key
    # against the wrong endpoint mid-walk).
    reg = Registry.load(str(REGISTRY))
    conf_provider = _routine_provider(WRIGHT_CONF)
    for chain in WRIGHT_CHAINS:
        links = reg.resolve(chain)
        assert links, f"the `{chain}` chain resolved to zero links"
        for link in links:
            assert link.provider == conf_provider, (
                f"wright: link {link.position} of `{chain}` is on provider "
                f"{link.provider!r} but {WRIGHT_CONF} declares "
                f"{conf_provider!r} — the walk would spend that link's key "
                "against the wrong endpoint")


def test_wright_ship_steps_are_pinned_to_their_registry_links():
    """Every forge ship step sources --model from a real link of its half's
    chain and carries that half's deny backstop + dontAsk; the steps on the
    conf's provider match the chain exactly (count, order, secret, endpoint),
    the latent other-provider block is checked structurally — the scout/
    routine guards' two-tier split."""
    reg = Registry.load(str(REGISTRY))
    conf_provider = _routine_provider(WRIGHT_CONF)
    secrets_by_provider = {p.id: p.secret for p in reg.providers.values()}
    bases_by_provider = {p.id: p.base_url for p in reg.providers.values()}
    text = _wright_text()
    for chain, (step_id, backstop) in WRIGHT_CHAINS.items():
        links = reg.resolve(chain)
        link_positions = {link.position for link in links}
        steps = _oracle_ship_steps(text, step_id)
        assert steps, f"no ship step reads steps.{step_id}.outputs in wright.yml"
        current = []
        for step in steps:
            assert step["model_slot"] in link_positions, (
                f"wright {chain}: a ship step references "
                f"link{step['model_slot']}_model but the chain has links "
                f"{sorted(link_positions)}")
            providers_with_secret = [pid for pid, s in secrets_by_provider.items()
                                     if s == step["secret"]]
            assert len(providers_with_secret) == 1, (
                f"wright {chain}: a ship step wires secrets.{step['secret']}, "
                f"which matches no single registry provider "
                f"({providers_with_secret})")
            step_provider = providers_with_secret[0]
            assert step["base_url"] == bases_by_provider[step_provider], (
                f"wright {chain}: a step for provider {step_provider!r} carries "
                f"ANTHROPIC_BASE_URL {step['base_url']!r} but the registry "
                f"endpoint is {bases_by_provider[step_provider]!r}")
            # Punch-list discipline (the Oracle's): the narrowed surface must
            # not be quietly shed — and each half must carry ITS OWN backstop,
            # never the other's (the proposer/judge separation lives there).
            assert "--permission-mode dontAsk" in step["chunk"], (
                f"wright {chain}: a ship step no longer runs under "
                "--permission-mode dontAsk")
            assert f"--settings {backstop}" in step["chunk"], (
                f"wright {chain}: a ship step no longer carries its half's "
                f"deny backstop (--settings {backstop})")
            if step_provider == conf_provider:
                current.append(step)
        assert [s["model_slot"] for s in current] == [l.position for l in links], (
            f"wright {chain}: the {conf_provider} block's steps reference links "
            f"{[s['model_slot'] for s in current]} but the chain has "
            f"{[l.position for l in links]} — one ship step per link, in order")


def test_wright_signoff_walk_gates_on_earlier_links():
    # The sign-off walk must actually WALK: each link-N step (N>1) is gated on
    # every earlier same-block link NOT having succeeded, so the first success
    # short-circuits the rest (#327's rule, the labeler's shape).
    text = _wright_text()
    steps = _oracle_ship_steps(text, "signoff_chain")
    by_link = {}
    for step in steps:
        m = re.search(r"^\s*id:\s*(\S+)", step["chunk"], re.MULTILINE)
        if m and m.group(1).startswith("signoff_zai_"):
            by_link[step["model_slot"]] = step
    assert set(by_link) == {1, 2, 3}, (
        f"wright signoff: expected zai walk steps for links 1-3, found "
        f"{sorted(by_link)}")
    for n in (2, 3):
        for earlier in range(1, n):
            needle = f"steps.signoff_zai_{earlier}.outcome != 'success'"
            assert needle in by_link[n]["chunk"], (
                f"wright signoff: the link-{n} step is not gated on {needle} — "
                "the walk would run every link unconditionally")


def test_wright_run_steps_gate_on_key_presence():
    # The degraded path stays a ::notice:: skip (the #326 constraint): every
    # ship step gates on key_present, and the skip notice survives.
    text = _wright_text()
    for chain, (step_id, _backstop) in WRIGHT_CHAINS.items():
        for step in _oracle_ship_steps(text, step_id):
            assert "key_present == '1'" in step["chunk"], (
                f"wright {chain}: a ship step does not gate on "
                "key_present == '1' — an absent provider key would not skip it")
    assert "::notice::the configured provider" in text, (
        "wright.yml's secret-absent notice is gone — the degraded path must "
        "stay a ::notice:: skip")


def test_wright_no_hardcoded_model_literal_survives():
    text = _wright_text()
    literals = [tok for tok in re.findall(r"--model\s+(\S+)", text)
                if not tok.startswith("${{")]
    assert not literals, f"hardcoded --model literal(s) in wright.yml: {literals}"


def _assert_wright_signoff_outcome_covers_every_link(text: str) -> None:
    """The sign-off job's RUN expression must treat ANY walk link's success as
    the walk's success, and no-success as not-success — simulated over the
    full outcome cartesian, the #327 walk-outcome discipline. Factored out so
    the negative control can run it against tampered text."""
    global _PROVIDER_UNDER_TEST
    blocks = _job_blocks(text)
    assert "signoff" in blocks, "wright.yml has no `signoff` job"
    exprs = _outcome_expressions(blocks["signoff"])
    assert exprs.get("RUN"), (
        "wright.yml's signoff job has no RUN outcome expression to pin")
    _PROVIDER_UNDER_TEST = _routine_provider(WRIGHT_CONF)
    links = Registry.load(str(REGISTRY)).resolve("wright-signoff")
    assert len(WRIGHT_SIGNOFF_BLOCK) == len(links), (
        f"the `wright-signoff` chain has {len(links)} links but the pinned "
        f"walk block has {len(WRIGHT_SIGNOFF_BLOCK)} step ids — update "
        "WRIGHT_SIGNOFF_BLOCK with the chain")
    for expr in exprs["RUN"]:
        for state in _walk_states(len(links)):
            outcomes = dict(zip(WRIGHT_SIGNOFF_BLOCK, state))
            got = _eval_github_expression(expr, outcomes)
            any_success = "success" in state
            if any_success:
                assert got == "success", (
                    f"wright signoff RUN evaluated to {got!r} under "
                    f"{outcomes} — a link succeeded but the walk's outcome "
                    "is not success")
            else:
                assert got != "success", (
                    f"wright signoff RUN read {got!r} with no link having "
                    f"succeeded ({state})")


def test_wright_signoff_walk_outcome_covers_every_link():
    _assert_wright_signoff_outcome_covers_every_link(_wright_text())


def test_wright_walk_outcome_guard_fires_on_a_stale_link1_expression():
    # NEGATIVE CONTROL: revert the sign-off RUN expression to a link-1-only
    # read and require the simulation to FAIL — otherwise the guard is a
    # restatement (the repo's standing rule).
    text = _wright_text()
    stale = ("(steps.signoff_zai_1.outcome == 'success' && 'success' || "
             "steps.signoff_zai_2.outcome == 'success' && 'success' || "
             "steps.signoff_zai_3.outcome)")
    assert stale in text, (
        "the live signoff RUN expression changed shape — update the mutation")
    tampered = text.replace(stale, "(steps.signoff_zai_1.outcome)")
    with pytest.raises(AssertionError):
        _assert_wright_signoff_outcome_covers_every_link(tampered)


# ── Reeve's greenlight drafter (issue #443, #296 stage 2) ────────────────────
#
# reeve.yml is the registry's next consumer, and an unusual one: ONE workflow,
# TWO jobs with opposite security postures. The `report` job is the
# deterministic, keyless reporter — every finding a recomputable fact, no
# provider secret, no agent — and issue #443's contract is that it STAYS that
# way: the LLM greenlight drafter is a SEPARATE job that runs after it, so the
# secret enters only where the agent runs. The guard therefore pins both
# directions: the greenlight job's wiring to the `reeve-greenlight` chain (the
# routine guards' two-tier split — provider agreement, literal secret,
# endpoint, link-per-step, the #442 containment surface), and the report job's
# keylessness (no `secrets.` reference, no agent step), each with a negative
# control proving the check can fail.

REEVE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "reeve.yml"
REEVE_CONF = ".github/reeve.conf"
REEVE_CHAIN = "reeve-greenlight"
# The drafter's own deny backstop (#442) and its single shell surface.
REEVE_BACKSTOP = ".claude/reeve-settings.json"
REEVE_WRAPPER = ".claude/skills/reeve-greenlight/greenlight-helper.sh"


def _reeve_text() -> str:
    return REEVE_WORKFLOW.read_text(encoding="utf-8")


def test_reeve_greenlight_chain_exists_and_matches_conf():
    # The chain must exist AND sit on the provider .github/reeve.conf declares —
    # the greenlight resolve step's run-time cross-check, caught pre-merge (a
    # mismatched link would spend its key against the wrong endpoint).
    reg = Registry.load(str(REGISTRY))
    assert REEVE_CHAIN in reg.chains, (
        f"the `{REEVE_CHAIN}` chain is missing from the registry — reeve.yml's "
        "greenlight resolve step would fail at run time, before any key is spent")
    conf_provider = _routine_provider(REEVE_CONF)
    for link in reg.resolve(REEVE_CHAIN):
        assert link.provider == conf_provider, (
            f"reeve: link {link.position} of `{REEVE_CHAIN}` is on provider "
            f"{link.provider!r} but {REEVE_CONF} declares {conf_provider!r} — "
            "the drafter would run its model against the wrong endpoint")


def test_reeve_greenlight_is_a_separate_job_after_the_report():
    # The drafter must run in its OWN job that `needs:` the report — the report
    # job's keylessness is structural, not incidental, so an agent step cannot
    # creep into the reporter.
    blocks = _job_blocks(_reeve_text())
    assert "greenlight" in blocks, "reeve.yml has no `greenlight` job"
    assert re.search(r"^    needs: report\b", blocks["greenlight"], re.MULTILINE), (
        "reeve.yml's greenlight job does not `needs: report` — the drafter must "
        "run after (and only after a successful) deterministic report")
    # And it must be the workflow's resolve step that picks the model.
    assert "model_registry resolve reeve-greenlight" in blocks["greenlight"], (
        "the greenlight job no longer resolves the `reeve-greenlight` chain — "
        "its model would have to come from somewhere the registry does not own")


def test_reeve_greenlight_ship_steps_are_pinned_to_the_chain():
    """Every greenlight ship step sources --model from a real chain link, wires
    the link's provider's literal secret + endpoint, keeps the #442 containment
    surface (dontAsk, its OWN backstop, the wrapper as the only Bash allow, no
    MCP server, the committed skill as the prompt), and the steps on the conf's
    provider match the chain exactly — one ship step per link, in order, so the
    single-link chain cannot quietly grow a fallback the workflow never walks."""
    reg = Registry.load(str(REGISTRY))
    conf_provider = _routine_provider(REEVE_CONF)
    secrets_by_provider = {p.id: p.secret for p in reg.providers.values()}
    bases_by_provider = {p.id: p.base_url for p in reg.providers.values()}
    links = reg.resolve(REEVE_CHAIN)
    link_positions = {link.position for link in links}
    steps = _routine_ship_steps(_job_blocks(_reeve_text())["greenlight"])
    assert steps, "reeve.yml's greenlight job has no claude-code-action ship step"
    current = []
    for step in steps:
        assert step["link"] in link_positions, (
            f"reeve: a greenlight ship step references link{step['link']}_model "
            f"but the `{REEVE_CHAIN}` chain has links {sorted(link_positions)}")
        assert step["secret"] is not None, (
            "reeve: a greenlight ship step wires no literal anthropic_api_key secret")
        providers_with_secret = [pid for pid, s in secrets_by_provider.items()
                                 if s == step["secret"]]
        assert len(providers_with_secret) == 1, (
            f"reeve: a ship step wires secrets.{step['secret']}, which matches "
            f"no single registry provider ({providers_with_secret})")
        step_provider = providers_with_secret[0]
        assert step["base_url"] == bases_by_provider[step_provider], (
            f"reeve: the {step_provider!r} step carries ANTHROPIC_BASE_URL "
            f"{step['base_url']!r} but the registry endpoint is "
            f"{bases_by_provider[step_provider]!r}")
        # The #442 containment surface, which must not be quietly shed: dontAsk,
        # the loop's OWN deny backstop (never a sibling's), the wrapper as the
        # ONLY Bash allow plus the read-only file tools, no MCP server (the
        # wrapper is both the read and the write surface), and the committed
        # skill as the prompt — never an inline one that bypasses it.
        assert "--permission-mode dontAsk" in step["chunk"], (
            "reeve: a greenlight ship step no longer runs under "
            "--permission-mode dontAsk")
        assert f"--settings {REEVE_BACKSTOP}" in step["chunk"], (
            f"reeve: a greenlight ship step no longer carries the deny backstop "
            f"(--settings {REEVE_BACKSTOP})")
        assert f"Bash({REEVE_WRAPPER}:*)" in step["chunk"], (
            "reeve: a greenlight ship step no longer allows the greenlight "
            "wrapper — the agent's only shell surface")
        assert "Read,Grep,Glob" in step["chunk"], (
            "reeve: a greenlight ship step dropped the read-only file tools the "
            "charter grounding (repo-root PM.md) depends on")
        assert "mcp__" not in step["chunk"] and "--mcp-config" not in step["chunk"], (
            "reeve: a greenlight ship step allows an MCP server — the loop's "
            "write surface is the wrapper, and no server exists to allow")
        assert "prompt: /reeve-greenlight" in step["chunk"], (
            "reeve: a greenlight ship step no longer invokes the committed "
            "/reeve-greenlight skill — an inline prompt would bypass it")
        if step_provider == conf_provider:
            current.append(step)
    assert [s["link"] for s in current] == [l.position for l in links], (
        f"reeve: the {conf_provider} block's steps reference links "
        f"{[s['link'] for s in current]} but the chain has "
        f"{[l.position for l in links]} — one ship step per link in order, so "
        "deepening the chain means wiring (and gating) its walk, not just "
        "editing the registry")


def test_reeve_greenlight_run_steps_gate_on_key_presence():
    # The keyed-and-skippable requirement (#443's Done-when): every ship step
    # gates on key_present, so an absent provider secret is a ::notice:: skip,
    # never a red run — and the notice survives.
    text = _reeve_text()
    for step in _routine_ship_steps(_job_blocks(text)["greenlight"]):
        assert step["gates_on_key"], (
            "reeve: a greenlight ship step does not gate on key_present == '1' "
            "— an absent provider key would fail the run red instead of skipping")
    assert "::notice::the configured provider" in text, (
        "reeve.yml's secret-absent notice is gone — the degraded path must stay "
        "a ::notice:: skip")


def test_reeve_key_gate_guard_fires_without_the_gate():
    # NEGATIVE CONTROL: strip the key gate from a ship step and require the
    # guard to FAIL — otherwise it proves nothing (a check that cannot fail is
    # worthless, the repo's standing rule).
    text = _reeve_text()
    tampered = text.replace("          && steps.policy.outputs.key_present == '1'\n", "", 1)
    assert tampered != text, (
        "tamper target not found — the greenlight ship-step key gate moved "
        "shape; update the mutation")
    stripped = [s for s in _routine_ship_steps(_job_blocks(tampered)["greenlight"])
                if not s["gates_on_key"]]
    assert stripped, (
        "the key-presence check did not react to a stripped gate — it has been "
        "weakened into a restatement")


def test_reeve_no_hardcoded_model_literal_survives():
    text = _reeve_text()
    literals = [tok for tok in re.findall(r"--model\s+(\S+)", text)
                if not tok.startswith("${{")]
    assert not literals, f"hardcoded --model literal(s) in reeve.yml: {literals}"


def _assert_reeve_report_job_is_keyless(text: str) -> None:
    """The deterministic reporter holds no secret and runs no agent (issue
    #443's contract that it keeps running keyless and unchanged). Factored out
    so the negative control can run it against tampered text."""
    blocks = _job_blocks(text)
    assert "report" in blocks, "reeve.yml has no `report` job"
    assert "secrets." not in blocks["report"], (
        "reeve.yml's report job references a secret — the deterministic "
        "reporter is keyless by design; a secret-bearing step belongs in the "
        "separate `greenlight` job")
    assert "claude-code-action" not in blocks["report"], (
        "reeve.yml's report job runs an agent step — the reporter is "
        "deterministic by design; the LLM half lives in `greenlight`")


def test_reeve_reporter_stays_keyless_and_agent_free():
    _assert_reeve_report_job_is_keyless(_reeve_text())


def test_reeve_reporter_keyless_guard_fires_on_a_secret_reference():
    # NEGATIVE CONTROL: wire a secret into the report job and require the
    # keylessness guard to FAIL — the reporter's keylessness is a security
    # property, so its guard must be able to fail.
    text = _reeve_text()
    tampered = text.replace("GH_TOKEN: ${{ github.token }}",
                            "GH_TOKEN: ${{ secrets.ZAI_KEY }}", 1)
    assert tampered != text, "tamper target not found — the fixture is stale"
    assert "secrets.ZAI_KEY" in _job_blocks(tampered)["report"], (
        "the tamper landed outside the report job — the fixture is stale")
    with pytest.raises(AssertionError):
        _assert_reeve_report_job_is_keyless(tampered)
