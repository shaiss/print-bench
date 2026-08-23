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

