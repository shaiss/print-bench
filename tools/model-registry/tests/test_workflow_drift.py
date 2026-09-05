"""Drift guard: the committed registry and its consumer workflows cannot silently diverge.

auto-review.yml only runs on design PRs, so this PR's CI does not live-exercise the
migrated review pipeline. This test is the standing proof that the registry drives
the workflow and stays consistent with it. product-scout.yml (issue #243) is the
second consumer — since #544 Part B a row of the ROUTINES table below, guarded
by the routine pins like every other chain-walking scheduled routine.

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

import functools
import pathlib
import re
from typing import NamedTuple

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


# ── The product scout (issue #243; #544 Part B) ───────────────────────────────
#
# The scout was the registry's second consumer (#243), pinned here as a
# single-link chain with one ship step per provider, the conf's `provider:`
# picking which one ran. Since #544 Part B it walks the cross-provider chain
# like the four Part A routines — the GLM head, then the Anthropic tail —
# and is the "scout" row of the ROUTINES table below, covered by every generic
# pin: the chain fits the walk (head on the conf provider, one step per link
# wired to its link's provider, the row's layout), the walk order, the
# per-provider key gates, the any-provider skip notice, the outcome
# simulation, the exhaustion gates (the red step and provider-triage), the job
# budget, the no-literal rule and the triage wiring. The two #243 properties
# that survive the walk unchanged stay explicit here: the chain resolves
# in-workflow, and the degraded path stays a ::notice:: skip — now firing only
# when NO provider in the chain has a key, never on the head's key alone.

SCOUT_CHAIN = "scout"


def _scout_text() -> str:
    return SCOUT_WORKFLOW.read_text(encoding="utf-8")


def test_scout_chain_exists_and_resolves():
    # The chain #243 named. A registry edit that dropped it would fail the
    # workflow's resolve step at run time — on the scout's weekly cadence, where
    # nobody is watching. Catch it here instead.
    links = Registry.load(str(REGISTRY)).resolve(SCOUT_CHAIN)
    assert links, f"the `{SCOUT_CHAIN}` chain resolved to zero links"


def test_scout_resolves_its_chain_in_workflow():
    # The resolve step must target the `scout` chain, or every ship step's
    # `link<N>_model` reference reads an empty output and the action errors.
    text = _scout_text()
    assert f"model_registry resolve {SCOUT_CHAIN}" in text, (
        "product-scout.yml no longer resolves the `scout` chain")


def test_scout_degraded_path_skips_with_a_notice_only_when_no_key_is_present():
    """The secret-absent path stays a `::notice::` skip, not a hard fail —
    the #243 property — reworded by #544 Part B: it fires only when NO
    provider in the chain has a key (the pre-#544 "the configured provider
    has no key" notice would announce a skip while the Anthropic tail ran,
    or skip the whole run on a keyless head). The generic rule proves the
    gate; this pins that the old single-provider wording is gone with it.
    """
    row = ROUTINES["scout"]
    text = _scout_text()
    _assert_routine_skip_notice_fires_only_without_any_key(row, text)
    assert "::notice::the configured provider" not in text, (
        "product-scout.yml still carries the single-provider secret-absent "
        "notice — under the cross-provider walk a keyless head is a fall-"
        "through, not a skip")


# ── The spike converter (#245 child C, issue #440; #544 Part B) ───────────────
#
# The scheduled spike-to-brief converter is the scout's shape exactly, and
# since #544 Part B it walks the scout's chain shape too — the GLM head, then
# the Anthropic tail — as the "spike-converter" row of the ROUTINES table
# below, covered by every generic pin: the chain fits the walk (head on the
# conf provider, one step per link wired to its link's provider, the row's
# layout), the walk order, the per-provider key gates, the any-provider skip
# notice, the outcome simulation, the exhaustion gates, the job budget, the
# no-literal rule, the triage wiring — and, since the review round, the
# agent SURFACE on every walk step: the converter's ONE write is not its own
# MCP server but the scout's REUSED filing tool (#439), so its row declares
# the converter's own deny backstop, the SCOUT's mcp-config and an allow-list
# naming exactly mcp__scout__file_design_brief, and the generic surface pin
# holds every step — the tail included, which runs only on the fall-through
# path where nobody is watching — to them (the workflow half of the coupling
# scripts/spike-converter-perms-check.sh holds over the files). What stays
# explicit here: issue #440's two frozen acceptance criteria — the conf
# declares the chain's head provider, and the two-key arming gates the job
# on every link; and the #440 degraded path, a ::notice:: skip that now fires
# only when NO provider in the chain has a key.


def _spike_walk_steps(text: str) -> list[dict]:
    """The converter walk's ship steps (every link, via the generic parser)."""
    row = ROUTINES["spike-converter"]
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    assert steps, (
        f"no claude-code-action ship step found in {row.workflow}'s `{row.job}` job")
    return steps


def test_spike_converter_row_reuses_the_scouts_filing_server():
    # #439's one-filing-surface rule as a table fact: the converter's row
    # names the SCOUT's mcp-config and the scout's filing tool, with its OWN
    # backstop — the generic surface pin then holds every walk step to it.
    spike, scout = ROUTINES["spike-converter"], ROUTINES["scout"]
    assert spike.mcp_config == scout.mcp_config, (
        "the converter row no longer reuses the scout's filing server — "
        "filing a brief any other way breaks #439's one-filing-surface rule")
    assert spike.allowed.startswith("mcp__scout__file_design_brief,"), (
        "the converter row's allow-list no longer leads with the scout's filing tool")
    assert spike.backstop != scout.backstop, (
        "the converter row wears the scout's backstop — it must carry its own")


def test_spike_converter_chain_exists_and_resolves():
    # The chain issue #440 names. A registry edit that dropped it would fail
    # the workflow's resolve step at run time — on the converter's weekly
    # cadence, where nobody is watching. Catch it here instead.
    row = ROUTINES["spike-converter"]
    links = Registry.load(str(REGISTRY)).resolve(row.chain)
    assert links, f"the `{row.chain}` chain resolved to zero links"


def test_spike_converter_conf_declares_the_chains_head_provider():
    # Issue #440's pinned acceptance criterion, held by name: .github/
    # spike-converter.conf must keep declaring the provider the chain's HEAD
    # link resolves to, or every armed run dies at the resolve step's shape
    # check before a key is spent. The generic chain-fits-walk pin applies
    # this same head rule to every ROUTINES row (with its negative control,
    # test_routine_shape_guard_rejects_a_head_off_the_conf_provider); this
    # keeps the issue's criterion legible where the issue put it.
    row = ROUTINES["spike-converter"]
    head = Registry.load(str(REGISTRY)).resolve(row.chain)[0]
    conf_provider = _routine_provider(row.conf)
    assert conf_provider == head.provider, (
        f"{row.conf} declares provider {conf_provider!r} but the "
        f"`{row.chain}` chain's head link ({head.model}) is on "
        f"{head.provider!r} — the resolve step's shape check will fail every "
        "armed run")


def test_spike_converter_degraded_path_skips_with_a_notice_only_when_no_key_is_present():
    """The secret-absent path stays a `::notice::` skip, not a hard fail —
    the #440 property — reworded by #544 Part B: it fires only when NO
    provider in the chain has a key (the pre-#544 "the configured provider
    has no key" notice would announce a skip while the Anthropic tail ran,
    or skip the whole run on a keyless head). The generic rule proves the
    gate; this pins that the old single-provider wording is gone with it.
    """
    row = ROUTINES["spike-converter"]
    text = _routine_text(row.workflow)
    _assert_routine_skip_notice_fires_only_without_any_key(row, text)
    assert "::notice::the configured provider" not in text, (
        "spike-converter.yml still carries the single-provider secret-absent "
        "notice — under the cross-provider walk a keyless head is a fall-"
        "through, not a skip")


def _assert_spike_two_key_arming_gates_the_job(text: str) -> None:
    """Issue #440's disarm acceptance, pinned structurally: the job-level
    `if:` must read the LIVE repo variable (key 1 — unset by default, so a
    clone/fork cannot silently arm an issue-filing cron) AND every walk step
    must gate on the committed conf's `enabled` (key 2 — `steps.policy
    .outputs.enabled`, read from .github/spike-converter.conf by the policy
    step). Dropping either key from its condition re-arms the routine
    one-sidedly — and a TAIL step that dropped key 2 would file with the
    conf paused in git, on the fall-through path alone. Factored out so the
    negative control can run it against tampered text."""
    row = ROUTINES["spike-converter"]
    convert_block = _routine_job_text(text, row)
    job_if = re.search(
        r"if: >-\n\s+vars\.SPIKE_CONVERTER_ENABLED == 'true'", convert_block)
    assert job_if, (
        "the convert job's `if:` no longer reads "
        "vars.SPIKE_CONVERTER_ENABLED == 'true' — key 1 of the two-key arming "
        "is gone, and a clone that sets only the conf would run")
    assert "enabled=\"$(backlog-burn config --get enabled --path \"$conf\")\"" \
        in convert_block, (
        "the policy step no longer reads `enabled` out of the conf — the "
        "key-2 output the walk steps gate on would be unfilled")
    for step in _spike_walk_steps(text):
        assert re.search(
            r"steps\.policy\.outputs\.enabled == 'true'", step["chunk"]), (
            f"spike-converter link-{step['link']} ship step no longer gates on "
            "the committed conf's `enabled` (steps.policy.outputs.enabled) — "
            "key 2 of the two-key arming is gone for that link, and a one-line "
            "conf edit would disarm nothing on its path")


def test_spike_converter_two_key_arming_gates_the_job():
    row = ROUTINES["spike-converter"]
    _assert_spike_two_key_arming_gates_the_job(_routine_text(row.workflow))


def test_spike_two_key_guard_rejects_a_tail_step_without_the_conf_key():
    # NEGATIVE CONTROL: strip the `enabled` leg from the terminal tail step's
    # `if:` (the leg is read off the live step, never hand-copied) — the job
    # still reads the live variable and the head still gates on the conf, so
    # only a per-link rule can see the tail re-armed one-sidedly.
    row = ROUTINES["spike-converter"]
    text = _routine_text(row.workflow)
    chunk = max(_spike_walk_steps(text), key=lambda s: s["link"])["chunk"]
    m = re.search(
        r"^([ \t]*)steps\.policy\.outputs\.enabled == 'true'\n[ \t]*&& ",
        chunk, re.MULTILINE)
    assert m, "tamper target not found — the tail step's `enabled` leg moved shape"
    tampered = text.replace(chunk, chunk.replace(m.group(0), m.group(1), 1), 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="key 2 of the two-key arming"):
        _assert_spike_two_key_arming_gates_the_job(tampered)


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


# ── The scheduled routines (issues #326, #327, #544) ─────────────────────────
#
# The burn, the design run, the chunker and the labeler are the registry's
# third consumer group, migrated in #326; #544 Part B brings the formerly
# single-link routines onto the same shape, one ROUTINES row each. The shape
# is a per-routine chain resolved in the job that consumes it
# (steps.<resolve id>.outputs) with one walk-specific addition: a ship step
# per LINK, walked in FILE ORDER ACROSS PROVIDERS (#544) — the Z.AI GLM
# step(s), then the Anthropic tail — so the chain can deepen (#327) and cross
# providers (#544) without the Actions literal-secret constraint changing
# shape: the workflow's step order IS the provider layout, and the registry
# fills each slot with a model.
#
# What the guard below proves, derived from the registry — never restated:
#
# * each routine's chain exists, its HEAD (link 1) sits on the provider its
#   .github/<routine>.conf declares, and the whole chain FITS the workflow's
#   walk — link N on the provider ship step N is wired for, one step per link
#   — by the SAME pure rule the workflow's resolve step runs at run time
#   (`walk_shape_errors`, via `model-registry shape --layout …`), so the two
#   cannot drift; the `--layout` literal in the resolve step must equal the
#   layout derived from the ship steps' real wiring, and both must equal the
#   layout the ROUTINES row declares;
# * every claude-code-action step in the routine's job takes --model from
#   steps.<resolve id>.outputs.link<N>_model for a real link N of that chain
#   — a hardcoded literal, or a reference to a link the chain doesn't have,
#   fails — and is named `<prefix>_<provider>_<N>` so every routine's walk
#   reads the same way;
# * each step's literal secret and endpoint are THAT LINK's provider's
#   (position-derived, the review guard's rule — with design-run's documented
#   CLAUDE_KEY alias marker), so a tail step wired to the other provider's
#   auth is caught, not just a step wired to *some* provider's;
# * the walk is real: each link-N step is gated on EVERY earlier link, across
#   providers, NOT having succeeded, so the Anthropic tail runs only after
#   the GLM links failed or were skipped, never unconditionally;
# * each step gates on ITS OWN provider's key (`<provider>_key_present`), so
#   a missing key skips that provider's links and never spends an empty
#   credential — and the secret-absent path stays a ::notice:: skip (#326)
#   that fires only when NO provider in the chain has a key (the policy
#   step's `key_present` is the either-key derivation);
# * the walk's OUTCOME is read off every link (#327, #544): the AGENT_OUTCOME
#   / RUN / SHIP expressions and every exhaustion gate the row names (the
#   red step and the provider-triage step) must treat any link's success as
#   the walk's success, simulated over the full outcome cartesian — an
#   expression still reading only one provider's links after the tail
#   crossed would send a healthy tail run red and (via
#   routine-lock-cleanup) withdraw a live run's SHIP-LOCK.
#
# Every pin has a negative control below (a tampered copy the pin must
# reject) — the repo's standing rule that a check which cannot fail proves
# nothing. The ROUTINES table drives everything; converting another routine
# is a row here plus its chain in the registry — and for a workflow with
# several jobs (wright.yml, reeve.yml) the row names the job the pins read.


class Routine(NamedTuple):
    """One ROUTINES row — everything the generic pins need to read a routine
    workflow, so converting another routine is a row here (plus its chain in
    the registry), never a new test.

    workflow    the workflow file under .github/workflows/ (two rows may
                share one file — wright.yml carries a walk per job)
    chain       the registry chain id the workflow resolves and walks
    conf        the routine's conf, whose `provider:` names the walk's HEAD
    job         the job whose steps, outcome expressions and job-level
                `timeout-minutes` the pins read (wright.yml and reeve.yml
                carry several jobs — the pins scope to this one)
    resolve_id  the id of the resolve step whose outputs the ship steps read
                (`--model ${{ steps.<resolve_id>.outputs.link<N>_model }}`)
    prefix      the ship-step id prefix: the walk's ids are
                `<prefix>_<provider>_<N>`, N the link position
    layout      the expected provider per link, in file order — what the
                ship steps' real wiring must carry AND what the resolve
                step's `--layout` literal must say
    gates       the exhaustion gates: every step whose `if:` must fire
                exactly when NO link succeeded (the routine's red step and
                its provider-triage step), by step name
    ship_lock   True for the SHIP-LOCK routines (the burn, the design run):
                AGENT_OUTCOME is then assigned twice — the lock cleanup and
                the red-on-death gate — and both copies must agree
    permission_mode, backstop, mcp_config, allowed
                the agent SURFACE every ship step must carry verbatim on its
                `claude_args:` line — read off the routine's head link when
                the row was enrolled: the `--permission-mode` (None where the
                step sets none), the `--settings` deny backstop, the
                `--mcp-config` server (None for a routine whose write is a
                shell wrapper, or none) and the exact `--allowedTools` list
                (None for the SHIP-LOCK routines, which run the whole skill
                under bypassPermissions). The tail runs only on the
                fall-through path where nobody is watching, so a tail step
                that shed its backstop or widened its allow-list is exactly
                the drift these fields pin — the same surface every
                `scripts/*-perms-check.sh` holds over the FILES, none of
                which reads a workflow.
    """
    workflow: str
    chain: str
    conf: str
    job: str
    resolve_id: str
    prefix: str
    layout: tuple[str, ...]
    gates: tuple[str, ...]
    ship_lock: bool
    permission_mode: str | None
    backstop: str | None
    mcp_config: str | None
    allowed: str | None


# The provider-triage step every routine carries (#347): its `if:` is an
# exhaustion gate — a stale one would run a live classify probe after every
# healthy tail run and, with escalate on, could file a needs-decision on a
# chain that just succeeded.
TRIAGE_STEP = "Diagnose the exhausted chain (billing / tokens / technical)"
# The red step the routines without a SHIP-LOCK lifecycle carry (#544): a walk
# exhausted with the tail SKIPPED has no failed non-coe step to fail the job.
EXHAUSTED_RED_STEP = "Turn an exhausted walk red"

ROUTINES = {
    # routine name → its row (the conf's `provider:` is the HEAD)
    "design-run": Routine(
        workflow="design-run.yml", chain="design-run",
        conf=".github/design-run.conf", job="run",
        resolve_id="chain", prefix="run",
        layout=("zai", "zai", "zai", "anthropic", "anthropic"),
        gates=("Turn a dead agentic run red", TRIAGE_STEP), ship_lock=True,
        # The SHIP-LOCK routines run the whole skill: no backstop, no
        # allow-list, bypassPermissions on every link.
        permission_mode="bypassPermissions", backstop=None, mcp_config=None,
        allowed=None),
    "backlog-burn": Routine(
        workflow="backlog-burn.yml", chain="backlog-burn",
        conf=".github/backlog-burn.conf", job="burn",
        resolve_id="chain", prefix="ship",
        layout=("zai", "zai", "zai", "anthropic", "anthropic"),
        gates=("Turn a dead agentic run red", TRIAGE_STEP), ship_lock=True,
        permission_mode="bypassPermissions", backstop=None, mcp_config=None,
        allowed=None),
    "chunker": Routine(
        workflow="chunker.yml", chain="chunker",
        conf=".github/chunker.conf", job="chunk",
        resolve_id="chain", prefix="run",
        layout=("zai", "zai", "zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False,
        # The chunker's steps set no --permission-mode (the live value when
        # the row was enrolled — adding dontAsk is a deliberate row edit).
        permission_mode=None, backstop=".claude/chunker-settings.json",
        mcp_config=None,
        allowed="Bash(.claude/skills/chunk-issue/chunk-helper.sh:*),Read,Grep,Glob"),
    "labeler": Routine(
        workflow="labeler.yml", chain="labeler",
        conf=".github/labeler.conf", job="label",
        resolve_id="chain", prefix="run",
        layout=("zai", "zai", "zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False,
        permission_mode="dontAsk", backstop=".claude/labeler-settings.json",
        mcp_config=None,
        allowed="Bash(.claude/skills/label-issues/label-helper.sh:*),Read,Grep,Glob"),
    # #544 Part B: the eight formerly single-link routines, one row each —
    # the GLM head (one link, or the sign-off's three), then the two-link
    # Anthropic tail. The scout was the template.
    "scout": Routine(
        workflow="product-scout.yml", chain="scout",
        conf=".github/product-scout.conf", job="scout",
        resolve_id="chain", prefix="run",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False,
        permission_mode="dontAsk", backstop=".claude/scout-settings.json",
        mcp_config=".claude/skills/product-scout/scout-mcp.json",
        allowed=("mcp__scout__file_design_brief,"
                 "Bash(.claude/skills/product-scout/scout-helper.sh:*),"
                 "Bash(./.claude/skills/product-scout/scout-helper.sh:*),"
                 "Read,Grep,Glob")),
    "spike-converter": Routine(
        workflow="spike-converter.yml", chain="spike-converter",
        conf=".github/spike-converter.conf", job="convert",
        resolve_id="chain", prefix="run",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False,
        # Its own backstop, the SCOUT's reused filing server (#439: one
        # filing surface), its own read wrapper.
        permission_mode="dontAsk", backstop=".claude/spike-converter-settings.json",
        mcp_config=".claude/skills/product-scout/scout-mcp.json",
        allowed=("mcp__scout__file_design_brief,"
                 "Bash(.claude/skills/spike-converter/converter-helper.sh:*),"
                 "Bash(./.claude/skills/spike-converter/converter-helper.sh:*),"
                 "Read,Grep,Glob")),
    "adoption-assessor": Routine(
        workflow="adoption-assessor.yml", chain="adoption-assessor",
        conf=".github/adoption-assessor.conf", job="assess",
        resolve_id="chain", prefix="run",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False,
        permission_mode="dontAsk", backstop=".claude/adoption-assessor-settings.json",
        mcp_config=".claude/skills/adoption-assessor/assessor-mcp.json",
        allowed=("mcp__assessor__post_adoption_disposition,"
                 "Bash(.claude/skills/adoption-assessor/assessor-helper.sh:*),"
                 "Bash(./.claude/skills/adoption-assessor/assessor-helper.sh:*),"
                 "Read,Grep,Glob")),
    "growth-twitter": Routine(
        workflow="growth-twitter.yml", chain="growth-twitter",
        conf=".github/growth-twitter.conf", job="drain",
        resolve_id="chain", prefix="run",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False,
        # Oracle-shaped: no wrapper, the posting tool plus the read-only
        # file tools and nothing else.
        permission_mode="dontAsk", backstop=".claude/growth-twitter-settings.json",
        mcp_config=".claude/skills/growth-twitter/growth-mcp.json",
        allowed="mcp__growth_twitter__post_tweet,Read,Grep,Glob"),
    "reeve-growth": Routine(
        workflow="reeve-growth.yml", chain="reeve-growth",
        conf=".github/reeve-growth.conf", job="reeve-growth",
        resolve_id="chain", prefix="run",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False,
        permission_mode="dontAsk", backstop=".claude/reeve-growth-settings.json",
        mcp_config=".claude/skills/growth-queue/queue-mcp.json",
        allowed="mcp__growth_queue__queue_growth_post,Read,Grep,Glob"),
    # wright.yml carries two walks, one per job, each on its own chain and
    # its own resolve step (the Oracle's two-chain pattern) — two rows. Each
    # half carries ITS OWN backstop and filing server, never the other's:
    # the proposer/judge separation the forge is built on.
    "wright-propose": Routine(
        workflow="wright.yml", chain="wright",
        conf=".github/wright.conf", job="propose",
        resolve_id="propose_chain", prefix="propose",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False,
        permission_mode="dontAsk", backstop=".claude/wright-settings.json",
        mcp_config=".claude/skills/wright/wright-mcp.json",
        allowed=("mcp__wright__file_agent_brief,"
                 "Bash(.claude/skills/wright/wright-helper.sh:*),"
                 "Bash(./.claude/skills/wright/wright-helper.sh:*),"
                 "Read,Grep,Glob")),
    "wright-signoff": Routine(
        workflow="wright.yml", chain="wright-signoff",
        conf=".github/wright.conf", job="signoff",
        resolve_id="signoff_chain", prefix="signoff",
        layout=("zai", "zai", "zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False,
        permission_mode="dontAsk", backstop=".claude/reeve-signoff-settings.json",
        mcp_config=".claude/skills/reeve-signoff/signoff-mcp.json",
        allowed=("mcp__reeve_signoff__post_reeve_signoff,"
                 "Bash(.claude/skills/wright/wright-helper.sh:*),"
                 "Bash(./.claude/skills/wright/wright-helper.sh:*),"
                 "Read,Grep,Glob")),
    # reeve.yml's one agentic job; the report and observe jobs stay keyless
    # (pinned separately below) and are never walked. The loop's write is
    # its wrapper (#442) — no MCP server exists to allow.
    "reeve-greenlight": Routine(
        workflow="reeve.yml", chain="reeve-greenlight",
        conf=".github/reeve.conf", job="greenlight",
        resolve_id="chain", prefix="run",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False,
        permission_mode="dontAsk", backstop=".claude/reeve-settings.json",
        mcp_config=None,
        allowed=("Bash(.claude/skills/reeve-greenlight/greenlight-helper.sh:*),"
                 "Bash(./.claude/skills/reeve-greenlight/greenlight-helper.sh:*),"
                 "Read,Grep,Glob")),
}

# The registry's consumers that are NOT scheduled-routine walks and so carry
# no ROUTINES row: the design-review chain (its ship steps live in the
# reviewer jobs, pinned by the review guard above) and the Oracle's two
# role chains (pinned by the Oracle guard). Every OTHER `model_registry
# resolve <chain>` in .github/workflows/ must be a row — the coverage pin
# below — so a walk cannot exist ungoverned by the generic pins.
NON_ROUTINE_CONSUMERS = {
    ("auto-review.yml", "review"),
    ("oracle.yml", "oracle-anthropic"),
    ("oracle.yml", "oracle-glm"),
}


_WORKFLOW_GLOBS = ("*.yml", "*.yaml")


def _workflow_paths(workflows_dir: pathlib.Path) -> list[pathlib.Path]:
    """Every workflow file GitHub would run: it accepts BOTH extensions, so
    the search space globs both — a `.yaml` file must never be invisible to
    the pins (the hygiene test below still refuses one in the live tree)."""
    return sorted(p for pattern in _WORKFLOW_GLOBS for p in workflows_dir.glob(pattern))


def _all_workflow_texts() -> dict[str, str]:
    """Every workflow file, by name — the coverage pin's whole search space."""
    return {p.name: p.read_text(encoding="utf-8")
            for p in _workflow_paths(REPO_ROOT / ".github" / "workflows")}


def _registry_consumers(texts: dict[str, str]) -> set[tuple[str, str]]:
    """Every (workflow, chain) a `model_registry resolve <chain>` line names."""
    found: set[tuple[str, str]] = set()
    for workflow, text in texts.items():
        for chain in re.findall(r"model_registry resolve (\S+)", text):
            found.add((workflow, chain))
    return found


def _assert_every_consumer_has_a_row(consumers: set[tuple[str, str]],
                                     rows: dict[str, "Routine"]) -> None:
    """The resolved set and the table (plus the named non-routine consumers)
    are the same set, both ways. Factored out so the negative controls can
    run it against a thinned table / a thinned consumer set."""
    expected = {(row.workflow, row.chain) for row in rows.values()} | NON_ROUTINE_CONSUMERS
    missing = consumers - expected
    assert not missing, (
        f"chain-walking workflow(s) with no ROUTINES row: {sorted(missing)} — "
        "every `model_registry resolve <chain>` consumer must be a row of the "
        "table (or a named NON_ROUTINE_CONSUMERS entry), or its walk runs "
        "ungoverned by every generic pin")
    stale = expected - consumers
    assert not stale, (
        f"ROUTINES row(s) / named consumer(s) no workflow resolves: "
        f"{sorted(stale)} — a row outlived its walk; drop it, or restore the "
        "resolve step")


def test_every_chain_walking_workflow_has_a_routines_row():
    # A row is what enrols a walk in every generic pin — so deleting a row
    # must not be a silent way out of them (deleting `growth-twitter`'s row
    # once passed the whole suite). Scan the workflows, not the table.
    _assert_every_consumer_has_a_row(_registry_consumers(_all_workflow_texts()), ROUTINES)


def test_row_coverage_guard_rejects_a_table_missing_a_row():
    # NEGATIVE CONTROL: the table without one live row must fail on that row.
    thinned = {name: row for name, row in ROUTINES.items() if name != "growth-twitter"}
    assert len(thinned) == len(ROUTINES) - 1
    with pytest.raises(AssertionError, match="no ROUTINES row.*growth-twitter"):
        _assert_every_consumer_has_a_row(_registry_consumers(_all_workflow_texts()), thinned)


def test_row_coverage_guard_rejects_a_row_no_workflow_resolves():
    # NEGATIVE CONTROL, the other direction: a workflow that stopped
    # resolving its chain leaves a row describing a walk that no longer
    # exists — derived by deleting the live resolve line, never a literal.
    texts = _all_workflow_texts()
    victim = ROUTINES["growth-twitter"]
    line = f"model_registry resolve {victim.chain}"
    assert line in texts[victim.workflow], "tamper target not found — the fixture is stale"
    texts[victim.workflow] = texts[victim.workflow].replace(line, "model_registry resolve-nothing", 1)
    with pytest.raises(AssertionError, match="outlived its walk"):
        _assert_every_consumer_has_a_row(_registry_consumers(texts), ROUTINES)


# ── AI andon cord coverage (docs/andon-cord.md) ──────────────────────────────
#
# ONE repo variable, AI_ANDON_CORD: set to 'pulled' it must bypass EVERY
# AI-consuming job in .github/workflows/ — grey/skipped, never red, no
# provider call, no escalation — with exactly one ::notice:: explaining the
# bypass, while every deterministic job keeps running. The pins below hold
# that property over the WORKFLOWS rather than over a hand-kept list: a job is
# AI-consuming iff its block spends a provider key or runs an agent action,
# so a future AI-consuming job is enrolled the moment it references a key, and
# cannot land uncorded (the same enumerate-the-tree discipline as the
# ROUTINES row-coverage pin above — a list would let a new job slip past).

# The job-level gate leg every AI-consuming job's `if:` must carry as a
# TOP-LEVEL CONJUNCT — the whole condition, or joined to the rest by a
# top-level `&&`, with no top-level `||` anywhere in the condition (`&&`
# binds tighter than `||` in GitHub expressions, so `leg && A || B` runs the
# job on B with the cord pulled). Position is NOT enforced: the arming
# variable stays the first line by convention, the leg usually last, but the
# pin reads the folded expression, not the line order. The explain leg is
# what the visible-no-op sibling / step keys on. The comparison is GitHub's:
# case-insensitive on the exact word `pulled`, never trimmed — a value of
# `pulled ` (trailing space) is the RELEASED state to every gate here, and
# the tools (tools/andon, tools/reeve) must read it identically.
ANDON_JOB_LEG = "vars.AI_ANDON_CORD != 'pulled'"
ANDON_EXPLAIN_LEG = "vars.AI_ANDON_CORD == 'pulled'"

# A provider-key SPEND: `anthropic_api_key: ${{ secrets.X }}`, `zai-key:
# ${{ secrets.X }}`, `ZAI_KEY: ${{ secrets.X }}`. The negative lookahead
# excludes the presence probes deterministic jobs carry (`HAS_ZAI: ${{
# secrets.ZAI_KEY != '' }}`) so they are not flagged. The alternation is
# DERIVED, not hand-kept: every `secret` a `[provider:…]` stanza of the
# committed registry declares, UNION the literal floor below, UNION every
# `registry-secret-alias: X=Y` marker a workflow carries (design-run's
# Anthropic tail wires CLAUDE_KEY, a historical alias — without it that tail
# would be invisible). So a NEW registry provider's secret enrols its
# spenders the moment the stanza lands, with no edit here.
_LITERAL_PROVIDER_SECRETS = frozenset({"ANTHROPIC_API_KEY", "ZAI_KEY", "CLAUDE_KEY"})
_ALIAS_MARKER_RE = re.compile(r"registry-secret-alias:\s*(\w+)=(\w+)")


def _registry_provider_secrets() -> set[str]:
    """Every provider secret name the committed registry declares."""
    return {p.secret for p in Registry.load(str(REGISTRY)).providers.values()}


def _alias_secret_names(texts: dict[str, str]) -> set[str]:
    """Both sides of every `registry-secret-alias: X=Y` marker in the
    workflows (the marker lives in a comment, so this reads the RAW text)."""
    names: set[str] = set()
    for text in texts.values():
        for alias, canonical in _ALIAS_MARKER_RE.findall(text):
            names.add(alias)
            names.add(canonical)
    return names


def _provider_secret_names(texts: dict[str, str] | None = None) -> frozenset[str]:
    """The full spend alternation: literal floor ∪ registry ∪ aliases."""
    if texts is None:
        texts = _all_workflow_texts()
    return frozenset(_LITERAL_PROVIDER_SECRETS | _registry_provider_secrets()
                     | _alias_secret_names(texts))


def _ai_spend_regex(names: frozenset[str] | set[str]) -> re.Pattern[str]:
    """The spend regex over a given secret-name set (the presence-probe
    lookahead kept), so the negative controls can build one for a provider
    the registry does not declare yet — exactly what a new stanza would do."""
    assert names, "an empty alternation would match nothing — no spend could ever be seen"
    alternation = "|".join(re.escape(n) for n in sorted(names))
    return re.compile(r"secrets\.(" + alternation + r")\b(?!\s*!=\s*'')")


@functools.lru_cache(maxsize=None)
def _ai_spend() -> re.Pattern[str]:
    """The live spend regex, derived once per session."""
    return _ai_spend_regex(_provider_secret_names())
# The agent action and the exhaustion-triage action: a job carrying either
# reaches a provider even when the key is wired through a composite input.
_AI_ACTIONS = ("anthropics/claude-code-action", "./.github/actions/provider-triage")

# Deterministic jobs with ONE AI step each: the job must keep running (CI's
# regen still renders previews; the groomer still writes its report) so the
# cord lives on the AI STEP's own `if:` instead of the job header. Every step
# in such a job that spends a key must carry the leg.
ANDON_STEP_GATED = {("ci.yml", "regen"), ("backlog-groomer.yml", "groom")}

# The roster the enumerator finds on the live tree, by hand — so a reader sees
# what the cord covers, and a silent shrink (a job whose key reference moved
# into a shape the regex no longer sees) or grow (a new AI-consuming job) is
# caught here and reconciled deliberately, not absorbed.
ANDON_AI_JOBS = {
    ("adoption-assessor.yml", "assess"),
    ("auto-review.yml", "jane-review"),
    ("auto-review.yml", "drik-review"),
    ("auto-review.yml", "pm-triage"),
    ("auto-review.yml", "design-coach"),
    ("backlog-burn.yml", "burn"),
    ("backlog-groomer.yml", "groom"),
    ("chunker.yml", "chunk"),
    ("ci.yml", "regen"),
    ("design-run.yml", "run"),
    ("growth-twitter.yml", "drain"),
    ("labeler.yml", "label"),
    ("lifestyle-clip.yml", "generate"),
    ("lifestyle-shot.yml", "generate"),
    ("model-smoke.yml", "smoke"),
    ("oracle.yml", "oracle"),
    ("product-scout.yml", "scout"),
    ("product-still.yml", "generate"),
    ("reeve-growth.yml", "reeve-growth"),
    ("reeve.yml", "greenlight"),
    ("spike-converter.yml", "convert"),
    ("wright.yml", "propose"),
    ("wright.yml", "signoff"),
}

# The consumers outside the ROUTINES table the enumerator must never lose:
# the four reviewers, the Oracle, the smoke probe and the three image/clip
# generators. With the table's rows, this is the floor the enumerated set
# must cover — so the regex can never quietly shrink below the known roster.
_ANDON_NON_ROUTINE_AI_JOBS = {
    ("auto-review.yml", "jane-review"),
    ("auto-review.yml", "drik-review"),
    ("auto-review.yml", "pm-triage"),
    ("auto-review.yml", "design-coach"),
    ("oracle.yml", "oracle"),
    ("model-smoke.yml", "smoke"),
    ("lifestyle-shot.yml", "generate"),
    ("product-still.yml", "generate"),
    ("lifestyle-clip.yml", "generate"),
}

_ANDON_JOB_IF = re.compile(r"^    if:", re.MULTILINE)


def _without_comments(block: str) -> str:
    """The block with its comment lines dropped: a comment quoting the leg or
    a secret must neither enrol a job nor satisfy a pin on its behalf."""
    return "\n".join(l for l in block.splitlines() if not l.lstrip().startswith("#"))


def _job_header(block: str) -> str:
    """The job's text above its first step — where the job-level `if:` lives
    (`_step_condition` folds it exactly as it folds a step's)."""
    return re.split(r"\n      - ", block)[0]


def _job_steps(block: str) -> list[str]:
    """The job's step chunks, in order (the 6-space `- ` list the workflows
    here all use)."""
    return re.split(r"\n      - ", block)[1:]


def _workflow_header(text: str) -> str:
    """The workflow text ABOVE `jobs:` — `name:`, `on:`, `permissions:`,
    `concurrency:` and a top-level `env:` — where a hoisted secret would
    live out of every job block's sight."""
    jobs_at = re.search(r"^jobs:[ \t]*$", text, re.MULTILINE)
    assert jobs_at, "workflow has no `jobs:` section"
    return text[:jobs_at.start()]


def _is_ai_consuming(block: str, spend: re.Pattern[str] | None = None) -> tuple[bool, str]:
    """Whether a job block reaches a provider, and the first reference that
    says so (for the failure message). `spend` defaults to the live derived
    regex; the negative controls pass one built for a not-yet-declared
    provider."""
    body = _without_comments(block)
    for action in _AI_ACTIONS:
        if action in body:
            return True, action
    m = (spend or _ai_spend()).search(body)
    if m:
        return True, m.group(0)
    return False, ""


def _ai_consuming_jobs(texts: dict[str, str],
                       spend: re.Pattern[str] | None = None) -> dict[tuple[str, str], str]:
    """Every (workflow, job) that reaches a provider, with its block. The
    block includes the job header, so a spend wired as a job-level `env:`
    key (no step ever names the secret) enrols the job too."""
    found: dict[tuple[str, str], str] = {}
    for workflow, text in texts.items():
        for job, block in _job_blocks(text).items():
            consuming, _why = _is_ai_consuming(block, spend)
            if consuming:
                found[(workflow, job)] = block
    return found


def _strip_paren_groups(cond: str) -> str:
    """The condition with every balanced parenthesised group removed,
    innermost first — what is left is the expression's TOP LEVEL."""
    prev = None
    while prev != cond:
        prev = cond
        cond = re.sub(r"\([^()]*\)", " ", cond)
    return cond


def _cord_is_top_level_conjunct(cond: str) -> bool:
    """True iff the gate leg governs the whole condition: after the balanced
    parenthesised groups are removed there is NO top-level `||`, and the leg
    is one bare `&&`-conjunct (or the whole condition). `&&` binds tighter
    than `||` in GitHub expressions, so `leg && A || B` still runs on B with
    the cord pulled — a substring test would bless it; this refuses it. A
    leg that only appears INSIDE a group (`(leg && A) || B`) is not the
    gate either."""
    top = _strip_paren_groups(cond)
    if "||" in top:
        return False
    conjuncts = [re.sub(r"\s+", " ", c).strip() for c in top.split("&&")]
    return ANDON_JOB_LEG in conjuncts


def _job_level_cord_gated(block: str) -> bool:
    """True when the job's own `if:` carries the gate leg as a top-level
    conjunct (the shape that actually skips the job)."""
    header = _without_comments(_job_header(block))
    if not _ANDON_JOB_IF.search(header):
        return False
    return _cord_is_top_level_conjunct(_step_condition(header))


_HOISTED_KEY_MSG = ("provider keys must be wired at job/step level so the cord "
                    "pin can see them")


def _assert_no_workflow_level_provider_env(texts: dict[str, str],
                                           spend: re.Pattern[str] | None = None) -> None:
    """A provider secret hoisted into a workflow's top-level `env:` reaches
    every job through inheritance while living in NO job block — the
    enumerator would see nothing to cord. Refused outright: wire keys at
    job/step level (the simplest rule, and the one the pin can check)."""
    for workflow, text in sorted(texts.items()):
        m = (spend or _ai_spend()).search(_without_comments(_workflow_header(text)))
        assert not m, (
            f"{workflow}: {m.group(0) if m else ''} is referenced in the workflow "
            f"header (above `jobs:`) — {_HOISTED_KEY_MSG}; every job would inherit "
            "the key and none of them would enumerate as AI-consuming")


def _assert_every_ai_job_gates_on_the_cord(texts: dict[str, str],
                                           spend: re.Pattern[str] | None = None) -> None:
    """Every AI-consuming job is gated on the cord — at the job level, or for
    the allow-listed deterministic jobs, on every key-spending step — and in
    both places the leg must be a TOP-LEVEL CONJUNCT of the `if:`."""
    _assert_no_workflow_level_provider_env(texts, spend)
    jobs = _ai_consuming_jobs(texts, spend)
    floor = {(row.workflow, row.job) for row in ROUTINES.values()} | _ANDON_NON_ROUTINE_AI_JOBS
    lost = floor - set(jobs)
    assert not lost, (
        f"known AI-consuming job(s) the enumerator no longer sees: {sorted(lost)} "
        "— the key/action reference moved into a shape the spend regex / "
        "_AI_ACTIONS do not match, so the cord pin would silently stop covering them")
    for (workflow, job), block in sorted(jobs.items()):
        _consuming, why = _is_ai_consuming(block, spend)
        if (workflow, job) in ANDON_STEP_GATED:
            header_spend, header_why = _is_ai_consuming(_job_header(block), spend)
            assert not header_spend, (
                f"{workflow} [{job}]: allow-listed as step-gated but its job "
                f"header references {header_why} (a job-level env key reaches "
                "every step, gated or not) — move the key onto the AI step")
            spending = [chunk for chunk in _job_steps(block)
                        if _is_ai_consuming(chunk, spend)[0]]
            assert spending, (
                f"{workflow} [{job}]: allow-listed as step-gated but no step "
                "references a provider — drop it from ANDON_STEP_GATED")
            for chunk in spending:
                name = re.search(r"^\s*name:\s*(.+)$", chunk, re.MULTILINE)
                step = name.group(1).strip() if name else chunk.splitlines()[0].strip()
                _consuming, why = _is_ai_consuming(chunk, spend)
                body = _without_comments(chunk)
                has_if = re.search(r"^\s*if:", body, re.MULTILINE)
                cond = _step_condition(body) if has_if else ""
                assert has_if and _cord_is_top_level_conjunct(cond), (
                    f"{workflow} [{job}]: step '{step}' references {why} but "
                    f"{ANDON_JOB_LEG} is not a top-level conjunct of its `if:` "
                    f"({cond!r}) — pulling the cord would not stop it (the job "
                    "is deterministic and stays running, so its AI step must "
                    "carry the leg itself, joined by top-level && only)")
            continue
        header = _without_comments(_job_header(block))
        has_if = _ANDON_JOB_IF.search(header)
        cond = _step_condition(header) if has_if else ""
        assert has_if and _cord_is_top_level_conjunct(cond), (
            f"{workflow} [{job}]: AI-consuming job (references {why}) — "
            f"{ANDON_JOB_LEG} is not a top-level conjunct of its `if:` "
            f"({cond!r}); pulling the cord would not stop it (a top-level || "
            "lets the other branch run, and a leg inside parentheses is not "
            "the gate)")


def _assert_every_corded_workflow_explains_the_pull(texts: dict[str, str]) -> None:
    """A skipped job is mute, so every workflow the cord gates must say why
    nothing ran: some job that is NOT itself job-level cord-gated keys a
    ::notice:: on the explain leg — a disarmed-notice / andon-notice /
    oracle-andon sibling, auto-review's review-stamp env + notice, ci.yml's
    regen notice step, the groomer's notice step."""
    jobs = _ai_consuming_jobs(texts)
    for workflow in sorted({workflow for workflow, _job in jobs}):
        explained = False
        for _job, block in _job_blocks(texts[workflow]).items():
            if _job_level_cord_gated(block):
                continue  # skipped with the cord — cannot be the explainer
            body = _without_comments(block)
            if ANDON_EXPLAIN_LEG in body and "::notice::" in body:
                explained = True
                break
        assert explained, (
            f"{workflow}: the cord gates its AI job(s) but no ungated job keys "
            f"a ::notice:: on {ANDON_EXPLAIN_LEG} — a pulled cord would leave "
            "the run mute (grey, with nothing saying why); add the "
            "disarmed-notice-style sibling, or a notice step in a job that "
            "keeps running")


def test_every_ai_consuming_job_gates_on_the_andon_cord():
    _assert_every_ai_job_gates_on_the_cord(_all_workflow_texts())


def test_every_corded_workflow_explains_the_pull():
    _assert_every_corded_workflow_explains_the_pull(_all_workflow_texts())


def test_andon_ai_job_roster_is_the_expected_set():
    # The roster pin: the enumerated set equals the hand-derived one, so a
    # shrink or a grow is reconciled on purpose (a new AI-consuming job joins
    # ANDON_AI_JOBS in the same PR that cords it).
    found = set(_ai_consuming_jobs(_all_workflow_texts()))
    assert found == ANDON_AI_JOBS, (
        f"AI-consuming roster drifted — new: {sorted(found - ANDON_AI_JOBS)}, "
        f"gone: {sorted(ANDON_AI_JOBS - found)}")


def test_andon_reconciler_itself_is_not_corded():
    # SANITY: andon.yml (the status-issue reconciler) reads the variable but
    # spends no key and runs no agent — so it is outside the AI set, and its
    # reconcile job must NOT gate on the cord: it has to run WHILE the cord is
    # pulled to open the status issue, and after release to close it.
    texts = _all_workflow_texts()
    assert "andon.yml" in texts, "andon.yml is missing from .github/workflows/"
    assert not any(workflow == "andon.yml" for workflow, _job in _ai_consuming_jobs(texts)), (
        "andon.yml enumerated as AI-consuming — it must spend no provider key")
    blocks = _job_blocks(texts["andon.yml"])
    assert "reconcile" in blocks, "andon.yml has no `reconcile` job"
    # Absence of the LEG ANYWHERE in the job header, stricter than "not
    # gated as a top-level conjunct": a leg buried in a || branch would
    # still be a mistake here.
    assert ANDON_JOB_LEG not in _without_comments(_job_header(blocks["reconcile"])), (
        "andon.yml [reconcile] carries the gate leg — it could never open or "
        "close the status issue")
    assert not _job_level_cord_gated(blocks["reconcile"])


def test_andon_guard_rejects_a_job_that_shed_its_leg():
    # NEGATIVE CONTROL A (in-memory): the labeler's `label` job without its
    # folded leg line must fail naming that job — derived from the live text.
    texts = _all_workflow_texts()
    victim = "labeler.yml"
    leg = f"\n      && {ANDON_JOB_LEG}"
    assert leg in texts[victim], "tamper target not found — the fixture is stale"
    texts[victim] = texts[victim].replace(leg, "", 1)
    with pytest.raises(AssertionError, match=r"labeler\.yml \[label\]"):
        _assert_every_ai_job_gates_on_the_cord(texts)


_ROGUE_JOB = """\
  rogue:
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@e8c2d7c16c018cf1e694711c1c07a5f5db2b5eb1
        with:
          anthropic_api_key: ${{ secrets.ZAI_KEY }}
"""


def test_andon_guard_rejects_a_future_uncorded_ai_job(tmp_path):
    # NEGATIVE CONTROL B (tmp_path): a NEW agent job with no `if:` at all,
    # appended to a copy of the tree, must fail naming it — the property the
    # pin exists for: a future AI-consuming job cannot land uncorded.
    import shutil
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    for path in _workflow_paths(REPO_ROOT / ".github" / "workflows"):
        shutil.copy(path, workflows_dir)
    victim = workflows_dir / "labeler.yml"
    text = victim.read_text(encoding="utf-8")
    assert "  rogue:" not in text, "tamper target collides — the fixture is stale"
    victim.write_text(text.rstrip("\n") + "\n\n" + _ROGUE_JOB, encoding="utf-8")
    texts = {p.name: p.read_text(encoding="utf-8")
             for p in _workflow_paths(workflows_dir)}
    assert ("labeler.yml", "rogue") in _ai_consuming_jobs(texts), (
        "the rogue job was not enumerated — the enumerator, not the gate, is broken")
    with pytest.raises(AssertionError, match=r"labeler\.yml \[rogue\]"):
        _assert_every_ai_job_gates_on_the_cord(texts)


# ── Hardening pins: conjunct shape, hoisted keys, derived secrets, globs ─────

_DESIGN_COACH_SHAPE = (
    "always() && needs.design-changes.outputs.designs_changed == 'true' "
    "&& needs.jane-review.result == 'success' "
    f"&& {ANDON_JOB_LEG} "
    "&& (github.event.action == 'opened' || github.event.action == 'reopened')")
_MODEL_SMOKE_SHAPE = (
    f"{ANDON_JOB_LEG} && (github.event_name == 'workflow_dispatch' || "
    "github.event.pull_request.head.repo.full_name == github.repository)")


@pytest.mark.parametrize("cond", [
    ANDON_JOB_LEG,                                   # the whole condition
    f"vars.X_ENABLED == 'true' && {ANDON_JOB_LEG}",  # last conjunct (the routines)
    f"{ANDON_JOB_LEG} && vars.X_ENABLED == 'true'",  # first conjunct — position is free
    f"always()   &&   {ANDON_JOB_LEG}",              # whitespace-insensitive join
    _DESIGN_COACH_SHAPE,                             # leg mid-way, || group AFTER it
    _MODEL_SMOKE_SHAPE,                              # leg && (A || B)
    "!contains(github.event.pull_request.labels.*.name, 'no-oracle-review') "
    f"&& {ANDON_JOB_LEG}",                           # a call's parens are not a group of ||
])
def test_cord_conjunct_helper_accepts_a_governing_leg(cond):
    assert _cord_is_top_level_conjunct(cond), cond


@pytest.mark.parametrize("cond", [
    "",                                              # no condition at all
    "vars.X_ENABLED == 'true'",                      # no leg
    ANDON_EXPLAIN_LEG,                               # the OTHER leg (== 'pulled')
    f"{ANDON_JOB_LEG} && github.event_name == 'workflow_dispatch' "
    "|| github.event.pull_request.head.repo.full_name == github.repository",  # leg && A || B
    f"vars.X_ENABLED == 'true' || {ANDON_JOB_LEG}",  # A || leg
    f"({ANDON_JOB_LEG} && vars.X_ENABLED == 'true') || always()",  # leg only inside a group
    f"!({ANDON_JOB_LEG})",                           # negated group
    "vars.AI_ANDON_CORD != \"pulled\"",              # not the exact leg text
    f"{ANDON_JOB_LEG}x",                             # the leg as a prefix of something else
])
def test_cord_conjunct_helper_rejects_a_non_governing_leg(cond):
    assert not _cord_is_top_level_conjunct(cond), cond


def test_andon_guard_rejects_a_leg_that_is_not_a_top_level_conjunct():
    # NEGATIVE CONTROL E (in-memory): model-smoke's `leg && (A || B)` with its
    # parentheses dropped reads `leg && A || B` — GitHub runs the job on B
    # with the cord pulled. A substring pin would bless it; the guard must
    # fail naming the job and the shape.
    texts = _all_workflow_texts()
    victim = "model-smoke.yml"
    folded = (
        f"      {ANDON_JOB_LEG} &&\n"
        "      (github.event_name == 'workflow_dispatch' ||\n"
        "       github.event.pull_request.head.repo.full_name == github.repository)\n")
    flat = (
        f"      {ANDON_JOB_LEG} &&\n"
        "      github.event_name == 'workflow_dispatch' ||\n"
        "      github.event.pull_request.head.repo.full_name == github.repository\n")
    assert texts[victim].count(folded) == 1, "tamper target not found — the fixture is stale"
    texts[victim] = texts[victim].replace(folded, flat, 1)
    with pytest.raises(AssertionError,
                       match=r"model-smoke\.yml \[smoke\].*not a top-level conjunct"):
        _assert_every_ai_job_gates_on_the_cord(texts)


def test_andon_guard_rejects_a_provider_key_hoisted_into_workflow_env():
    # NEGATIVE CONTROL F (in-memory): a provider secret in a workflow's
    # top-level `env:` reaches every job by inheritance while living in no
    # job block — the enumerator would see nothing to cord. The guard must
    # refuse the hoist outright, naming the workflow.
    texts = _all_workflow_texts()
    victim = "labeler.yml"
    hoist = "env:\n  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}\n\njobs:\n"
    assert texts[victim].count("\njobs:\n") == 1, "tamper target not found — the fixture is stale"
    texts[victim] = texts[victim].replace("\njobs:\n", "\n" + hoist, 1)
    assert _ai_spend().search(_workflow_header(texts[victim])), "the hoist did not land"
    with pytest.raises(AssertionError, match=r"labeler\.yml.*" + re.escape(_HOISTED_KEY_MSG)):
        _assert_every_ai_job_gates_on_the_cord(texts)
    # Positive control: the presence probe shape is NOT a hoisted spend.
    probe = texts[victim].replace("${{ secrets.ANTHROPIC_API_KEY }}",
                                  "${{ secrets.ANTHROPIC_API_KEY != '' }}", 1)
    _assert_no_workflow_level_provider_env({victim: probe})


def test_live_workflows_hoist_no_provider_key_into_workflow_env():
    _assert_no_workflow_level_provider_env(_all_workflow_texts())


_ENV_ONLY_ROGUE_JOB = """\
  rogue:
    runs-on: ubuntu-latest
    env:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    steps:
      - run: python3 -m some_agent --spend
"""


def test_andon_guard_rejects_a_job_whose_only_spend_is_a_job_level_env_key():
    # NEGATIVE CONTROL G (in-memory): a job that names the secret ONLY in its
    # job-level `env:` (no action, no step references it) must still be
    # enumerated — the block includes the header — and fail the gate.
    texts = _all_workflow_texts()
    victim = "labeler.yml"
    assert "  rogue:" not in texts[victim], "tamper target collides — the fixture is stale"
    texts[victim] = texts[victim].rstrip("\n") + "\n\n" + _ENV_ONLY_ROGUE_JOB
    jobs = _ai_consuming_jobs(texts)
    assert ("labeler.yml", "rogue") in jobs, (
        "a job-level env spend was not enumerated — the job header is out of the enumerator's sight")
    assert not any(_is_ai_consuming(c)[0] for c in _job_steps(jobs[("labeler.yml", "rogue")])), (
        "the control is wrong: a STEP references the key, so it is not env-only")
    with pytest.raises(AssertionError, match=r"labeler\.yml \[rogue\]"):
        _assert_every_ai_job_gates_on_the_cord(texts)


def test_andon_guard_rejects_a_step_gated_job_with_a_job_level_env_key():
    # NEGATIVE CONTROL H (in-memory): ci.yml's regen is step-gated, so a key
    # wired in its JOB header would reach every step, gated or not — the
    # per-step scan cannot see it. The guard must refuse the header spend.
    texts = _all_workflow_texts()
    victim = "ci.yml"
    block = _job_blocks(texts[victim])["regen"]
    header = _job_header(block)
    assert not _is_ai_consuming(header)[0], "the fixture is stale: regen's header already spends"
    runs_on = re.search(r"^    runs-on:.*$", header, re.MULTILINE)
    assert runs_on, "regen has no runs-on line to anchor the tamper on"
    tampered = header.replace(
        runs_on.group(0),
        runs_on.group(0) + "\n    env:\n      ZAI_KEY: ${{ secrets.ZAI_KEY }}", 1)
    texts[victim] = texts[victim].replace(block, block.replace(header, tampered, 1), 1)
    with pytest.raises(AssertionError, match=r"ci\.yml \[regen\].*job header references"):
        _assert_every_ai_job_gates_on_the_cord(texts)


def test_spend_alternation_covers_every_registry_provider_secret():
    # Positive pin for the derivation: every `secret` a registry provider
    # declares is matched as a spend (and its presence probe is not), plus
    # the literal floor and both sides of every alias marker.
    registry_secrets = _registry_provider_secrets()
    assert registry_secrets, "the registry declares no providers"
    aliases = _alias_secret_names(_all_workflow_texts())
    assert ("CLAUDE_KEY", "ANTHROPIC_API_KEY") in [
        tuple(m) for text in _all_workflow_texts().values()
        for m in _ALIAS_MARKER_RE.findall(text)], (
        "design-run's registry-secret-alias marker is gone — the fixture is stale")
    spend = _ai_spend()
    for name in sorted(registry_secrets | _LITERAL_PROVIDER_SECRETS | aliases):
        assert spend.search(f"key: ${{{{ secrets.{name} }}}}"), f"{name} is not a spend"
        assert not spend.search(f"HAS: ${{{{ secrets.{name} != '' }}}}"), (
            f"{name}'s presence probe is flagged as a spend")
    assert not spend.search("key: ${{ secrets.REGEN_TOKEN }}"), (
        "a non-provider secret is in the alternation")


_OPENAI_ROGUE_JOB = """\
  rogue:
    runs-on: ubuntu-latest
    steps:
      - run: python3 -m some_agent
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
"""


def test_andon_guard_enrols_a_new_registry_providers_spender():
    # NEGATIVE CONTROL I (in-memory): the alternation built the way a NEW
    # `[provider:openai]` stanza would build it (its secret added to the
    # set) must enumerate a rogue job spending that key and fail the gate —
    # while today's alternation, without the stanza, does not see it (which
    # is exactly why the set is derived from the registry, not hand-kept).
    texts = _all_workflow_texts()
    victim = "labeler.yml"
    assert "  rogue:" not in texts[victim], "tamper target collides — the fixture is stale"
    texts[victim] = texts[victim].rstrip("\n") + "\n\n" + _OPENAI_ROGUE_JOB
    assert ("labeler.yml", "rogue") not in _ai_consuming_jobs(texts), (
        "OPENAI_API_KEY is already in the live alternation — pick another name for the control")
    widened = _ai_spend_regex(_provider_secret_names(texts) | {"OPENAI_API_KEY"})
    assert ("labeler.yml", "rogue") in _ai_consuming_jobs(texts, widened), (
        "the widened alternation did not enumerate the rogue spender")
    with pytest.raises(AssertionError, match=r"labeler\.yml \[rogue\]"):
        _assert_every_ai_job_gates_on_the_cord(texts, widened)
    # The widening changes nothing about the live tree: every real job still
    # passes under it (a new provider must not fail existing workflows).
    _assert_every_ai_job_gates_on_the_cord(_all_workflow_texts(), widened)


def _assert_no_yaml_extension(workflows_dir: pathlib.Path) -> None:
    """GitHub runs `.yaml` workflows as readily as `.yml`; the enumerator
    globs both, but the house convention is one extension so every grep,
    roster and script in the repo sees the same set."""
    stray = sorted(p.name for p in workflows_dir.glob("*.yaml"))
    assert not stray, (
        f"workflow file(s) with a .yaml extension: {stray} — rename to .yml "
        "(GitHub runs both, and every other tool here globs *.yml)")


def test_workflows_dir_has_no_yaml_extension():
    _assert_no_yaml_extension(REPO_ROOT / ".github" / "workflows")


def test_yaml_extension_guard_fires_and_the_enumerator_still_globs_it(tmp_path):
    # NEGATIVE CONTROL J: a `.yaml` copy of an AI workflow must (1) trip the
    # hygiene pin with the rename message and (2) still be enumerated by the
    # glob, so a stray extension can never hide an AI job from the cord pin.
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    (workflows_dir / "stray.yaml").write_text(
        (REPO_ROOT / ".github" / "workflows" / "labeler.yml").read_text(encoding="utf-8"),
        encoding="utf-8")
    with pytest.raises(AssertionError, match=r"stray\.yaml.*rename to \.yml"):
        _assert_no_yaml_extension(workflows_dir)
    texts = {p.name: p.read_text(encoding="utf-8") for p in _workflow_paths(workflows_dir)}
    assert ("stray.yaml", "label") in _ai_consuming_jobs(texts), (
        "a .yaml workflow is invisible to the enumerator")


def test_andon_guard_rejects_a_workflow_that_stopped_explaining():
    # NEGATIVE CONTROL C (in-memory): lifestyle-shot.yml's andon-notice job
    # with its explain leg removed leaves the workflow mute — the explain
    # pin must fail naming the workflow.
    texts = _all_workflow_texts()
    victim = "lifestyle-shot.yml"
    block = _job_blocks(texts[victim])["andon-notice"]
    assert ANDON_EXPLAIN_LEG in block, "tamper target not found — the fixture is stale"
    muted = block.replace(ANDON_EXPLAIN_LEG, "false")
    texts[victim] = texts[victim].replace(block, muted, 1)
    _assert_every_ai_job_gates_on_the_cord(texts)  # the gate side is intact
    with pytest.raises(AssertionError, match=r"lifestyle-shot\.yml"):
        _assert_every_corded_workflow_explains_the_pull(texts)


def test_andon_guard_rejects_a_step_gated_job_that_shed_its_leg():
    # NEGATIVE CONTROL D (in-memory): ci.yml's regen is a deterministic job
    # whose ONE AI step (product-page drafting) carries the cord — strip the
    # leg from that step's inline `if:` and the pin must fail naming the job.
    texts = _all_workflow_texts()
    victim = "ci.yml"
    leg = f" && {ANDON_JOB_LEG}"
    block = _job_blocks(texts[victim])["regen"]
    assert block.count(leg) == 1, "tamper target not found — the fixture is stale"
    texts[victim] = texts[victim].replace(block, block.replace(leg, "", 1), 1)
    with pytest.raises(AssertionError, match=r"ci\.yml \[regen\]"):
        _assert_every_ai_job_gates_on_the_cord(texts)



# An explicit in-workflow marker naming a step's secret as an alias for a
# registry provider's declared secret: `registry-secret-alias:
# <alias>=<registry-secret>` (design-run's anthropic link wires CLAUDE_KEY, a
# historical alias for the same credential as ANTHROPIC_API_KEY; both exist as
# repo secrets). Rewiring the secret would be a behavior change beyond #326's
# scope, so the marker is the accepted evidence instead — and the named
# registry secret is what identifies the provider (so the endpoint check still
# pins the step to a real provider's base_url).
_ALIAS_MARKER = "registry-secret-alias:"

# The any-provider secret-absent notice (#544): the wording every routine's
# skip step must carry, so a grep for it finds the degraded path.
_NO_KEY_NOTICE = "::notice::no key is set for ANY provider"


def _routine_text(workflow: str) -> str:
    return (REPO_ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")


def _routine_provider(conf: str) -> str:
    """The `provider:` value the routine's conf declares (last assignment wins)."""
    text = (REPO_ROOT / conf).read_text(encoding="utf-8")
    values = re.findall(r"^provider:\s*(\S+)\s*$", text, re.MULTILINE)
    assert values, f"{conf} declares no provider:"
    return values[-1]


def _routine_job_text(text: str, row: Routine) -> str:
    """The text of the job the row names — every pin reads THAT job's steps,
    never a sibling job's (wright.yml carries two walks, reeve.yml three
    jobs with only one agentic)."""
    blocks = _job_blocks(text)
    assert row.job in blocks, (
        f"{row.workflow}: no `{row.job}` job — the ROUTINES row names a job "
        f"the workflow does not carry (jobs: {sorted(blocks)})")
    return blocks[row.job]


def _arg_value(argline: str, flag: str) -> str | None:
    """The value after `<flag> ` on a claude_args line, or None if unset."""
    m = re.search(re.escape(flag) + r"[ \t]+(\S+)", argline)
    return m.group(1) if m else None


def _routine_ship_steps(job_text: str, resolve_id: str = "chain") -> list[dict]:
    """The routine job's claude-code-action steps, in order, as parsed wiring.

    `resolve_id` is the resolve step whose `link<N>_model` outputs the ship
    steps read (`chain` in every single-job routine; wright.yml's jobs read
    `propose_chain` / `signoff_chain`).
    """
    steps: list[dict] = []
    model_pat = re.compile(
        r"--model \$\{\{ steps\." + re.escape(resolve_id)
        + r"\.outputs\.link(\d+)_model \}\}")
    for chunk in re.split(r"\n      - ", job_text):
        if "uses: anthropics/claude-code-action" not in chunk:
            continue
        model = model_pat.search(chunk)
        secret = re.search(r"anthropic_api_key: \$\{\{ secrets\.(\w+) \}\}", chunk)
        base = re.search(r"ANTHROPIC_BASE_URL: (\S+)", chunk)
        step_id = re.search(r"^\s*id:\s*(\S+)", chunk, re.MULTILINE)
        # The agent surface, read off the `claude_args:` LINE only — a step's
        # comments may quote a flag (chunker's link 1 says "--settings
        # closes"), and a comment is not a surface.
        args = re.search(r"^[ \t]*claude_args:[ \t]*(.+)$", chunk, re.MULTILINE)
        argline = args.group(1) if args else ""
        allowed = re.search(r'--allowedTools "([^"]*)"', argline)
        steps.append({
            "id": step_id.group(1) if step_id else "",
            "link": int(model.group(1)) if model else None,
            "permission_mode": _arg_value(argline, "--permission-mode"),
            "backstop": _arg_value(argline, "--settings"),
            "mcp_config": _arg_value(argline, "--mcp-config"),
            "allowed": allowed.group(1) if allowed else None,
            "secret": secret.group(1) if secret else None,
            "base_url": base.group(1) if base else "",
            "alias": _ALIAS_MARKER in chunk,
            "gates_on_key": "key_present == '1'" in chunk,
            # The providers whose OWN key-presence output the step's `if:`
            # reads (`steps.policy.outputs.<provider>_key_present == '1'`,
            # #544) — the provider-derived key gate.
            "key_gate_providers": set(re.findall(
                r"steps\.policy\.outputs\.([a-z0-9]+)_key_present\s*==\s*'1'", chunk)),
            "chunk": chunk,
        })
    return steps


def _step_provider(reg: Registry, step: dict, where: str) -> str:
    """Which registry provider a ship step's literal wiring identifies.

    An alias marker names the registry secret (and so the provider)
    explicitly; a plain secret identifies it by uniqueness among declared
    providers. Either way the step's endpoint must be that provider's,
    exactly — a step wired for one provider's secret against another's
    endpoint is the wrong-endpoint spend this guard exists to prevent.
    """
    secrets_by_provider = {p.id: p.secret for p in reg.providers.values()}
    bases_by_provider = {p.id: p.base_url for p in reg.providers.values()}
    assert step["secret"] is not None, (
        f"{where}: a ship step wires no literal anthropic_api_key secret")
    named = _marker_registry_secret(step) if step["alias"] else step["secret"]
    providers = [pid for pid, s in secrets_by_provider.items() if s == named]
    assert len(providers) == 1, (
        f"{where}: a ship step's secret {named} matches no single registry "
        f"provider (matches: {providers})")
    provider = providers[0]
    assert step["base_url"] == bases_by_provider[provider], (
        f"{where}: a ship step for provider {provider!r} carries "
        f"ANTHROPIC_BASE_URL {step['base_url']!r} but the registry endpoint is "
        f"{bases_by_provider[provider]!r}")
    return provider


def _walk_layout(reg: Registry, steps: list[dict], where: str) -> list[str]:
    """The provider LAYOUT the workflow's ship steps actually carry, in link
    order — exactly one ship step per link position 1..N, each identified by
    its literal wiring. This is what the registry chain must fit."""
    by_link: dict[int, list[dict]] = {}
    for step in steps:
        assert step["link"] is not None, (
            f"{where}: a ship step's --model is not sourced from "
            "steps.<resolve id>.outputs.link<N>_model")
        by_link.setdefault(step["link"], []).append(step)
    positions = sorted(by_link)
    assert positions == list(range(1, len(positions) + 1)), (
        f"{where}: ship steps reference links {positions}, not a contiguous "
        "1..N — a link has no step, or a step references a link nobody walks")
    for n, group in by_link.items():
        assert len(group) == 1, (
            f"{where}: {len(group)} ship steps reference link{n}_model — "
            "exactly one ship step per link (a latent other-provider block "
            "reading the same link would spend its key on a model routed "
            "elsewhere)")
    return [_step_provider(reg, by_link[n][0], where) for n in positions]


def _walk_step_ids(steps: list[dict]) -> list[str]:
    """Step ids of the walk, in link order, across providers."""
    return [s["id"] for s in sorted(steps, key=lambda s: s["link"] or 0)]


def _resolve_layout_literal(job_text: str, chain_id: str, where: str) -> list[str]:
    """The `--layout` literal the workflow's resolve step hands to
    `model-registry shape <chain>` — the runtime half of the shape rule."""
    m = re.search(
        r"model_registry shape " + re.escape(chain_id)
        + r"[^\n]*?--layout\s+([a-z0-9,]+)", job_text)
    if not m:
        m = re.search(
            r"model_registry shape " + re.escape(chain_id)
            + r"(?:[^\n]*\\\n)*[^\n]*?--layout\s+([a-z0-9,]+)", job_text)
    assert m, (
        f"{where}: the resolve step no longer runs `model_registry shape "
        f"{chain_id} … --layout <providers>` — the runtime walk-shape check "
        "is gone, and a chain that does not fit the walk would spend a key "
        "against the wrong endpoint")
    return m.group(1).split(",")


def _marker_registry_secret(step: dict) -> str:
    """The registry secret a step's alias marker names it equivalent to."""
    m = re.search(re.escape(_ALIAS_MARKER) + r"\s*(\w+)=([A-Za-z0-9_]+)",
                  step["chunk"])
    assert m, (
        f"a step carries {_ALIAS_MARKER!r} but not in the "
        "'<alias>=<registry-secret>' form — the named registry secret is what "
        "pins the step's provider/endpoint")
    return m.group(2)


def _assert_routine_chain_fits_its_walk(reg: Registry, row: Routine,
                                        text: str) -> None:
    """The chain exists, its head is on the conf's provider, and it fits the
    workflow's walk slot for slot — by `walk_shape_errors`, the SAME pure rule
    the resolve step runs at run time — and that walk is the layout the
    ROUTINES row declares. Factored out so the negative controls can run it
    against a tampered registry / workflow."""
    workflow, chain_id = row.workflow, row.chain
    where = f"{row.workflow} [{row.job}]"
    assert chain_id in reg.chains, (
        f"the `{chain_id}` chain (consumed by {where}) is missing from "
        "the registry — the workflow's resolve step would fail at run time")
    links = reg.resolve(chain_id)
    conf_provider = _routine_provider(row.conf)
    assert links[0].provider == conf_provider, (
        f"{where}: link 1 of `{chain_id}` is on provider "
        f"{links[0].provider!r} but {row.conf} declares provider {conf_provider!r} "
        "as the walk's HEAD — the routine would start on the wrong endpoint")
    # Every link on a declared provider (a chain can only cross to providers
    # the registry knows).
    for link in links:
        assert link.provider in reg.providers, (
            f"{where}: link {link.position} of `{chain_id}` names provider "
            f"{link.provider!r}, which the registry does not declare")
    from model_registry.registry import walk_shape_errors
    job = _routine_job_text(text, row)
    steps = _routine_ship_steps(job, row.resolve_id)
    assert steps, f"no claude-code-action ship step found in {where}'s `{row.job}` job"
    layout = _walk_layout(reg, steps, where)
    errors = walk_shape_errors(links, conf_provider, layout)
    assert not errors, (
        f"{where}: the `{chain_id}` chain does not fit the walk the ship "
        f"steps carry ({','.join(layout)}): " + "; ".join(errors))
    # The runtime half must check the SAME layout the steps really carry —
    # a resolve step handing `shape` a stale literal would pass a chain the
    # steps cannot walk.
    literal = _resolve_layout_literal(job, chain_id, where)
    assert literal == layout, (
        f"{where}: the resolve step's --layout literal {','.join(literal)} "
        f"differs from the layout the ship steps actually carry "
        f"{','.join(layout)} — the runtime shape check and the workflow drifted")
    # And the table's expectation: the row says what walk this routine
    # carries, so a walk that quietly changed shape (a dropped tail step, a
    # fourth GLM link) fails against the declared layout even when chain,
    # steps and literal all moved together.
    assert layout == list(row.layout), (
        f"{where}: the ROUTINES row declares layout {','.join(row.layout)} "
        f"but the ship steps carry {','.join(layout)} — update the row with "
        "the walk, deliberately")


def test_routine_chains_exist_and_fit_their_walks():
    # Each routine's chain must exist, sit its HEAD on the provider its conf
    # declares, and fit the workflow's cross-provider walk slot for slot (the
    # run-time shape check's subject, caught pre-merge). A misfit would make
    # the workflow's resolve step fail before any key is spent, so a routine
    # would never run at all: fail here first.
    reg = Registry.load(str(REGISTRY))
    for row in ROUTINES.values():
        _assert_routine_chain_fits_its_walk(reg, row, _routine_text(row.workflow))


def test_routine_chains_are_mixed_provider_walks():
    # #544's acceptance: a MIXED chain is the accepted shape for every
    # chain-walking routine — each walks at least one link on a provider
    # other than its head. Pins the tail's existence so the cross-provider
    # fallback cannot be quietly reverted to a single-provider chain while
    # every other pin stays green (a single-provider chain still "fits" a
    # single-provider walk).
    reg = Registry.load(str(REGISTRY))
    for row in ROUTINES.values():
        where = f"{row.workflow} [{row.job}]"
        providers = [link.provider for link in reg.resolve(row.chain)]
        assert len(set(providers)) > 1, (
            f"{where}: the `{row.chain}` chain sits entirely on "
            f"{providers[0]!r} — the #544 cross-provider tail is gone")
        assert providers[0] == _routine_provider(row.conf)


def test_routine_shape_guard_rejects_a_head_off_the_conf_provider(tmp_path):
    # NEGATIVE CONTROL (i): a registry putting an Anthropic model at link 1 of
    # `labeler` while labeler.conf says zai must fail the head rule.
    text = REGISTRY.read_text(encoding="utf-8")
    tampered = text.replace(
        "[chain:labeler]\nmodels = glm-5.2, glm-5.1, glm-4.6, claude-sonnet-5, claude-haiku-4-5",
        "[chain:labeler]\nmodels = claude-sonnet-5, glm-5.1, glm-4.6, claude-sonnet-5, claude-haiku-4-5", 1)
    assert tampered != text, "tamper target not found — the fixture is stale"
    bad = tmp_path / "registry.conf"
    bad.write_text(tampered, encoding="utf-8")
    row = ROUTINES["labeler"]
    with pytest.raises(AssertionError, match="link 1 of `labeler`"):
        _assert_routine_chain_fits_its_walk(
            Registry.load(str(bad)), row, _routine_text(row.workflow))


def test_routine_shape_guard_rejects_a_zai_link_after_an_anthropic_one(tmp_path):
    # NEGATIVE CONTROL (vi): the monotone `zai* then anthropic*` shape — a
    # zai link after an anthropic one lands on an Anthropic-wired step, and
    # the same `walk_shape_errors` rule the resolve step runs must reject it.
    text = REGISTRY.read_text(encoding="utf-8")
    tampered = text.replace(
        "[chain:labeler]\nmodels = glm-5.2, glm-5.1, glm-4.6, claude-sonnet-5, claude-haiku-4-5",
        "[chain:labeler]\nmodels = glm-5.2, glm-5.1, claude-sonnet-5, glm-4.6, claude-haiku-4-5", 1)
    assert tampered != text, "tamper target not found — the fixture is stale"
    bad = tmp_path / "registry.conf"
    bad.write_text(tampered, encoding="utf-8")
    row = ROUTINES["labeler"]
    with pytest.raises(AssertionError, match="does not fit the walk"):
        _assert_routine_chain_fits_its_walk(
            Registry.load(str(bad)), row, _routine_text(row.workflow))


def test_routine_shape_guard_rejects_a_stale_layout_literal():
    # NEGATIVE CONTROL: the resolve step's --layout literal must equal the
    # layout the ship steps really carry, or the runtime check and the
    # workflow drift apart (the coupling the shared rule exists for).
    row = ROUTINES["labeler"]
    text = _routine_text(row.workflow)
    tampered = text.replace("--layout zai,zai,zai,anthropic,anthropic",
                            "--layout zai,zai,zai,zai,anthropic", 1)
    assert tampered != text, "tamper target not found — the fixture is stale"
    with pytest.raises(AssertionError, match="--layout literal"):
        _assert_routine_chain_fits_its_walk(Registry.load(str(REGISTRY)), row, tampered)


def test_routine_shape_guard_rejects_a_walk_off_the_rows_layout():
    # NEGATIVE CONTROL: the ROUTINES row's declared layout is a pin of its
    # own — a row claiming a different walk than the one chain, steps and
    # literal all carry must fail, so the table cannot silently describe a
    # walk the file no longer has (a phase adding a row must declare the
    # real one).
    row = ROUTINES["labeler"]
    wrong = row._replace(layout=("zai", "zai", "zai", "zai", "anthropic"))
    with pytest.raises(AssertionError, match="ROUTINES row declares layout"):
        _assert_routine_chain_fits_its_walk(
            Registry.load(str(REGISTRY)), wrong, _routine_text(row.workflow))


def _assert_routine_ship_steps_pinned(reg: Registry, row: Routine,
                                      text: str) -> None:
    """Every ship step is pinned to ITS link, position for position: --model
    from link<N>_model for a real link N, exactly one step per link, and the
    step's literal secret + endpoint are that link's provider's (the review
    guard's position-derived rule — not merely *some* provider's). Factored
    out so the negative controls can run it against tampered text."""
    workflow, chain_id = row.workflow, row.chain
    where = f"{row.workflow} [{row.job}]"
    links = reg.resolve(chain_id)
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    assert steps, f"no claude-code-action ship step found in {where}'s `{row.job}` job"
    link_positions = {link.position for link in links}
    for step in steps:
        assert step["link"] in link_positions, (
            f"{where}: a ship step references link{step['link']}_model, "
            f"but the `{chain_id}` chain has links {sorted(link_positions)} "
            "— add the registry link or fix the reference")
    # File order IS walk order: Actions runs steps top to bottom, so a
    # link-3 step listed above link 2's runs first — and, gated only on the
    # links before it, link 2 then runs as well: two tail spends for one
    # walk. Every other pin keys by link<N>, blind to the listing order.
    file_order = [step["link"] for step in steps]
    assert file_order == list(range(1, len(steps) + 1)), (
        f"{where}: the ship steps are listed in link order {file_order}, not "
        "1..N — file order is the order Actions runs them, so a tail step "
        "listed early runs before the link it should follow (and that link "
        "still runs after it)")
    # One ship step per link, in order — derived from the steps, compared to
    # the chain. A workflow still carrying only one provider's steps against
    # a mixed chain fails HERE (a link with no step), as does a latent block
    # reading a link another step already walks.
    layout = _walk_layout(reg, steps, where)
    assert len(layout) == len(links), (
        f"{where}: the ship steps walk {len(layout)} links but the "
        f"`{chain_id}` chain has {len(links)} — one ship step per link")
    for link, provider in zip(links, layout):
        assert provider == link.provider, (
            f"{where}: the link-{link.position} ship step is wired for "
            f"provider {provider!r} (its secret/endpoint) but the registry "
            f"routes link {link.position} ({link.model}) to "
            f"{link.provider!r} — the step would spend the wrong key against "
            "the wrong endpoint")


def test_every_routine_ship_step_is_pinned_to_its_chain():
    reg = Registry.load(str(REGISTRY))
    for row in ROUTINES.values():
        _assert_routine_ship_steps_pinned(reg, row, _routine_text(row.workflow))


def test_ship_step_pin_rejects_tail_steps_listed_out_of_link_order():
    # NEGATIVE CONTROL: the scout's two tail blocks swapped in the file —
    # every link still has exactly one correctly-wired step, so only the
    # file-order rule can see that link 3 would run before (and then with)
    # link 2. Derived by swapping the live chunks, never a literal.
    reg = Registry.load(str(REGISTRY))
    row = ROUTINES["scout"]
    text = _routine_text(row.workflow)
    two, three = _tail_step_chunk(text, row, 2), _tail_step_chunk(text, row, 3)
    tampered = text.replace(two, "\x00", 1).replace(three, two, 1).replace("\x00", three, 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="listed in link order"):
        _assert_routine_ship_steps_pinned(reg, row, tampered)


def _assert_routine_step_ids_follow_the_convention(
        reg: Registry, row: Routine, text: str) -> None:
    """Every ship step's id is `<prefix>_<provider>_<N>` — the row's prefix,
    the provider the registry routes link N to, and N. One naming for every
    routine's walk, so an outcome expression, a gate or a summary reads the
    same in any workflow and a step id says which link it is. Factored out
    so the negative control can run it against tampered text."""
    workflow = row.workflow
    where = f"{row.workflow} [{row.job}]"
    links = {link.position: link for link in reg.resolve(row.chain)}
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    assert steps, f"no claude-code-action ship step found in {where}'s `{row.job}` job"
    for step in steps:
        assert step["link"] in links, (
            f"{where}: a ship step references link{step['link']}_model, "
            f"which the `{row.chain}` chain does not have")
        want = f"{row.prefix}_{links[step['link']].provider}_{step['link']}"
        assert step["id"] == want, (
            f"{where}: the link-{step['link']} ship step is id "
            f"{step['id']!r}, expected {want!r} (`<prefix>_<provider>_<N>`, "
            f"the ROUTINES row's prefix {row.prefix!r})")


def test_every_routine_ship_step_id_follows_the_convention():
    reg = Registry.load(str(REGISTRY))
    for row in ROUTINES.values():
        _assert_routine_step_ids_follow_the_convention(
            reg, row, _routine_text(row.workflow))


def test_step_id_guard_rejects_an_off_convention_id():
    # NEGATIVE CONTROL: rename the labeler's terminal step off the
    # convention (the id is derived from the live step, not hand-copied).
    reg = Registry.load(str(REGISTRY))
    row = ROUTINES["labeler"]
    text = _routine_text(row.workflow)
    last = _walk_step_ids(_routine_ship_steps(_routine_job_text(text, row), row.resolve_id))[-1]
    tampered = text.replace(
        f"id: {last}\n", f"id: {row.prefix}_tail_{last.rsplit('_', 1)[1]}\n", 1)
    assert tampered != text, "tamper target not found — the fixture is stale"
    with pytest.raises(AssertionError, match="expected"):
        _assert_routine_step_ids_follow_the_convention(reg, row, tampered)


def _tail_step_chunk(text: str, row: Routine, link: int) -> str:
    """The raw text of the ship step reading link<N>_model."""
    for step in _routine_ship_steps(_routine_job_text(text, row), row.resolve_id):
        if step["link"] == link:
            return step["chunk"]
    raise AssertionError(f"no ship step reads link{link}_model — fixture stale")


def test_ship_step_pin_rejects_a_tail_step_rewired_to_the_other_provider():
    # NEGATIVE CONTROL (ii): a link-4 step (registry: anthropic) rewired to
    # ZAI_KEY + the Z.AI base_url identifies a real declared provider — the
    # pre-#544 pin accepted exactly this — and must now fail, since it is not
    # THAT link's provider.
    row = ROUTINES["labeler"]
    text = _routine_text(row.workflow)
    chunk = _tail_step_chunk(text, row, 4)
    assert "anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}" in chunk
    rewired = chunk.replace(
        "anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}",
        "anthropic_api_key: ${{ secrets.ZAI_KEY }}", 1)
    rewired = rewired.replace(
        "        uses: anthropics/claude-code-action",
        "        env:\n          ANTHROPIC_BASE_URL: https://api.z.ai/api/anthropic\n"
        "        uses: anthropics/claude-code-action", 1)
    tampered = text.replace(chunk, rewired, 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="link-4 ship step is wired"):
        _assert_routine_ship_steps_pinned(Registry.load(str(REGISTRY)), row, tampered)


def _without_anthropic_tail(text: str, row: Routine) -> str:
    """A copy of a routine workflow with its Anthropic tail steps deleted —
    a workflow that reads only ONE provider's steps against a mixed chain."""
    out = text
    for link in (4, 5):
        chunk = _tail_step_chunk(out, row, link)
        out = out.replace("\n      - " + chunk, "", 1)
    assert out != text
    return out


def test_ship_step_pin_rejects_a_workflow_carrying_one_providers_steps_only():
    # NEGATIVE CONTROL (iii): delete the Anthropic tail from a copy of
    # labeler.yml so it walks only the GLM steps against the mixed chain —
    # the one-step-per-link count must fail (links 4 and 5 have no step).
    row = ROUTINES["labeler"]
    tampered = _without_anthropic_tail(_routine_text(row.workflow), row)
    reg = Registry.load(str(REGISTRY))
    with pytest.raises(AssertionError, match="one ship step per link"):
        _assert_routine_ship_steps_pinned(reg, row, tampered)
    # And the shape rule rejects it too, from the other side: the chain does
    # not fit a three-slot walk.
    with pytest.raises(AssertionError, match="does not fit the walk"):
        _assert_routine_chain_fits_its_walk(reg, row, tampered)


def _assert_routine_walks_in_order(reg: Registry, row: Routine,
                                   text: str) -> None:
    """Every link-N step is gated on EVERY earlier link — across providers —
    NOT having succeeded, so the first success short-circuits the rest and
    the Anthropic tail runs only after the GLM links failed or were skipped.
    Factored out so the negative control can run it against tampered text."""
    workflow, chain_id = row.workflow, row.chain
    where = f"{row.workflow} [{row.job}]"
    links = reg.resolve(chain_id)
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    by_link = {step["link"]: step for step in steps}
    for n in range(1, len(links) + 1):
        assert n in by_link, (
            f"{where}: the `{chain_id}` chain has a link {n} but no ship "
            "step references it — a registry edit landed without its "
            "workflow half (the walk stops early)")
    for n in range(2, len(links) + 1):
        for earlier in range(1, n):
            needle = f"steps.{by_link[earlier]['id']}.outcome != 'success'"
            assert needle in by_link[n]["chunk"], (
                f"{where}: the link-{n} step is not gated on {needle} — "
                "the walk would run that link even after an earlier one "
                "succeeded, instead of stopping at the first success")


def test_routine_walks_its_chain_in_order():
    reg = Registry.load(str(REGISTRY))
    for row in ROUTINES.values():
        _assert_routine_walks_in_order(reg, row, _routine_text(row.workflow))


def test_walk_order_guard_rejects_a_tail_step_missing_an_earlier_gate():
    # NEGATIVE CONTROL (iv): strip the link-3 gate from the link-4 step's
    # `if:` — the tail would then run after a healthy link-3 success.
    row = ROUTINES["labeler"]
    text = _routine_text(row.workflow)
    chunk = _tail_step_chunk(text, row, 4)
    needle = "          && steps.run_zai_3.outcome != 'success'\n"
    assert needle in chunk, "tamper target not found — the fixture is stale"
    tampered = text.replace(chunk, chunk.replace(needle, "", 1), 1)
    with pytest.raises(AssertionError, match="link-4 step is not gated"):
        _assert_routine_walks_in_order(Registry.load(str(REGISTRY)), row, tampered)


def _assert_routine_steps_gate_on_their_providers_key(
        reg: Registry, row: Routine, text: str) -> None:
    """Each ship step gates on ITS OWN link provider's key-presence output
    (`steps.policy.outputs.<provider>_key_present == '1'`, #544) — never the
    other provider's, never none: a missing key must skip that provider's
    links (the #326 ::notice:: degraded path) rather than spend an empty
    credential, and the tail must not inherit the head's key gate. Factored
    out so the negative control can run it against tampered text."""
    workflow = row.workflow
    where = f"{row.workflow} [{row.job}]"
    links = reg.resolve(row.chain)
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    by_link = {step["link"]: step for step in steps}
    for link in links:
        step = by_link[link.position]
        assert step["gates_on_key"], (
            f"{where}: the link-{link.position} ship step does not gate on "
            "key_present == '1' — an absent provider key would not skip it")
        assert step["key_gate_providers"] == {link.provider}, (
            f"{where}: the link-{link.position} ship step gates on the key "
            f"of {sorted(step['key_gate_providers'])} but the registry routes "
            f"that link to {link.provider!r} — it must gate on "
            f"steps.policy.outputs.{link.provider}_key_present == '1' and "
            "nothing else")


def test_routine_run_steps_gate_on_their_providers_key_presence():
    reg = Registry.load(str(REGISTRY))
    for row in ROUTINES.values():
        where = f"{row.workflow} [{row.job}]"
        text = _routine_text(row.workflow)
        _assert_routine_steps_gate_on_their_providers_key(reg, row, text)
        # The secret-absent notice survives (the #326 skip, reworded for
        # #544: it fires only when NO provider in the chain has a key).
        assert _NO_KEY_NOTICE in _routine_job_text(text, row), (
            f"{where}: the no-key-for-any-provider ::notice:: is gone — "
            "the degraded path must stay a notice skip, never a hard fail")


def test_key_gate_guard_rejects_a_tail_step_without_its_key_gate():
    # NEGATIVE CONTROL (v): strip the anthropic key gate from the link-4 step
    # — it would run with an empty credential when only ZAI_KEY is set.
    row = ROUTINES["labeler"]
    text = _routine_text(row.workflow)
    chunk = _tail_step_chunk(text, row, 4)
    needle = "          && steps.policy.outputs.anthropic_key_present == '1'\n"
    assert needle in chunk, "tamper target not found — the fixture is stale"
    tampered = text.replace(chunk, chunk.replace(needle, "", 1), 1)
    with pytest.raises(AssertionError, match="link-4 ship step"):
        _assert_routine_steps_gate_on_their_providers_key(
            Registry.load(str(REGISTRY)), row, tampered)


# ── The agent surface on EVERY walk step (#544 Part B, review round) ─────────
#
# The deny backstop, the permission mode, the MCP server and the allow-list
# are the unattended run's containment — and the tail steps carry them only
# on the fall-through path, where a shed `--settings` or a widened allow-list
# is never seen in a green run. Every `scripts/*-perms-check.sh` holds the
# FILE half of that surface (the backstop denies what it must); none reads a
# workflow, so this is the only pin on the WORKFLOW half. The row declares
# the surface (read off the head link when the row was enrolled) and every
# ship step must carry it verbatim: exact allow-list equality, the mcp-config
# exact or absent per row, the backstop exact, the permission mode exact.


def _assert_routine_walk_steps_keep_their_surface(row: Routine, text: str) -> None:
    """Every ship step's claude_args surface equals the row's, field for
    field. Factored out so the negative controls can run it against
    tampered text."""
    where = f"{row.workflow} [{row.job}]"
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    assert steps, f"no claude-code-action ship step found in {where}"
    for step in steps:
        at = f"{where}: the link-{step['link']} ship step"
        assert step["permission_mode"] == row.permission_mode, (
            f"{at} runs under permission mode {step['permission_mode']!r}, "
            f"not the row's {row.permission_mode!r} — without dontAsk the "
            "allow-list stops being exclusive and a prompt-injected run gets "
            "prompted-for tools")
        assert step["backstop"] == row.backstop, (
            f"{at} carries deny backstop {step['backstop']!r}, not the row's "
            f"{row.backstop!r} — the settings.json allows it inherits are "
            "no longer neutralised (or it wears a sibling's backstop)")
        assert step["mcp_config"] == row.mcp_config, (
            f"{at} wires mcp-config {step['mcp_config']!r}, not the row's "
            f"{row.mcp_config!r} — its only write is silently revoked, or a "
            "server it must not hold is mounted")
        assert step["allowed"] == row.allowed, (
            f"{at} allow-list is {step['allowed']!r}, expected exactly "
            f"{row.allowed!r} — a widened list is a wider unattended surface, "
            "a narrowed one a silently revoked write")


def test_every_routine_walk_step_keeps_its_surface():
    for row in ROUTINES.values():
        _assert_routine_walk_steps_keep_their_surface(row, _routine_text(row.workflow))


def _terminal_step_chunk(row: Routine, text: str) -> str:
    """The raw chunk of the walk's TERMINAL ship step — the one that runs
    only after every earlier link failed, unwatched."""
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    return max(steps, key=lambda s: s["link"])["chunk"]


@pytest.mark.parametrize("name", [n for n, r in ROUTINES.items() if r.backstop])
def test_surface_guard_rejects_a_terminal_step_that_sheds_its_backstop(name):
    # NEGATIVE CONTROL, every row with a backstop: the terminal tail step
    # loses `--settings <backstop>` (and its dontAsk, where it has one) —
    # the exact hazard of a surface pinned on the head alone. Derived from
    # the live step, never a literal.
    row = ROUTINES[name]
    text = _routine_text(row.workflow)
    chunk = _terminal_step_chunk(row, text)
    shed = chunk.replace(f" --settings {row.backstop}", "", 1)
    if row.permission_mode:
        shed = shed.replace(f" --permission-mode {row.permission_mode}", "", 1)
    assert shed != chunk, "tamper target not found — the fixture is stale"
    tampered = text.replace(chunk, shed, 1)
    with pytest.raises(AssertionError, match="deny backstop|permission mode"):
        _assert_routine_walk_steps_keep_their_surface(row, tampered)


@pytest.mark.parametrize("name", [n for n, r in ROUTINES.items() if r.allowed])
def test_surface_guard_rejects_a_terminal_step_with_a_widened_allow_list(name):
    # NEGATIVE CONTROL, every row with an allow-list: the terminal tail
    # step's list widened to a general Bash and Write — the assessor's
    # `…,Read,Grep,Glob,Bash,Write` tamper that once passed the suite.
    row = ROUTINES[name]
    text = _routine_text(row.workflow)
    chunk = _terminal_step_chunk(row, text)
    needle = f'--allowedTools "{row.allowed}"'
    assert needle in chunk, "tamper target not found — the fixture is stale"
    tampered = text.replace(
        chunk, chunk.replace(needle, f'--allowedTools "{row.allowed},Bash,Write"', 1), 1)
    with pytest.raises(AssertionError, match="allow-list"):
        _assert_routine_walk_steps_keep_their_surface(row, tampered)


@pytest.mark.parametrize("name", [n for n, r in ROUTINES.items() if r.mcp_config])
def test_surface_guard_rejects_a_terminal_step_that_sheds_its_mcp_config(name):
    # NEGATIVE CONTROL, every row with an MCP write: the terminal tail step
    # without its mcp-config — its only write silently revoked on the one
    # path that runs unwatched (the converter's #439 reuse hazard, now for
    # every MCP-writing routine).
    row = ROUTINES[name]
    text = _routine_text(row.workflow)
    chunk = _terminal_step_chunk(row, text)
    needle = f"--mcp-config {row.mcp_config} "
    assert needle in chunk, "tamper target not found — the fixture is stale"
    tampered = text.replace(chunk, chunk.replace(needle, "", 1), 1)
    with pytest.raises(AssertionError, match="mcp-config"):
        _assert_routine_walk_steps_keep_their_surface(row, tampered)


def test_surface_guard_rejects_a_row_whose_surface_the_head_does_not_carry():
    # NEGATIVE CONTROL from the table's side: a row declaring a surface no
    # step carries (a stale row after a deliberate workflow change) fails
    # too — the pin is equality, not a subset.
    row = ROUTINES["scout"]._replace(backstop=".claude/oracle-settings.json")
    with pytest.raises(AssertionError, match="deny backstop"):
        _assert_routine_walk_steps_keep_their_surface(row, _routine_text(row.workflow))


def _step_condition(chunk: str) -> str:
    """A step chunk's `if:` body, one line — the folded `if: >-` form the
    routines use, or a one-line `if: <expr>`.

    Each continuation line is matched as indentation, then an optional
    non-blank remainder: a blank run of tabs has exactly one split, so a
    non-matching tail cannot make the engine backtrack exponentially (the
    `[ \t]+.*` shape CodeQL flagged as a ReDoS)."""
    m = re.search(
        r"^[ \t]*if: >-\n((?:[ \t]+(?:[^ \t\n][^\n]*)?\n)+?)(?=[ \t]*[a-z_-]+:)",
        chunk, re.MULTILINE)
    if m:
        return " ".join(l.strip() for l in m.group(1).splitlines())
    m = re.search(r"^[ \t]*if:[ \t]*(.+)$", chunk, re.MULTILINE)
    assert m, "the step carries no `if:`"
    return m.group(1).strip()


def _assert_routine_skip_notice_fires_only_without_any_key(
        row: Routine, text: str) -> None:
    """The degraded path (#326, reworded for #544): the policy step emits
    each provider's own `<provider>_key_present` plus `key_present` as the
    EITHER-key derivation, and the step carrying the secret-absent notice is
    gated on that any-key output — never on one provider's — so the notice
    fires only when NO provider in the chain has a key, and a keyless head
    falls through to the tail instead of skipping the run. Factored out so
    the negative controls can run it against tampered text."""
    workflow = row.workflow
    job = _routine_job_text(text, row)
    chunks = re.split(r"\n      - ", job)
    policy = [c for c in chunks if re.search(r"^\s*id:\s*policy\s*$", c, re.MULTILINE)]
    assert len(policy) == 1, (
        f"{workflow}: expected exactly one step with `id: policy` in the "
        f"`{row.job}` job, found {len(policy)}")
    for provider in sorted(set(row.layout)):
        assert f'echo "{provider}_key_present=' in policy[0], (
            f"{workflow}: the policy step no longer emits {provider}_key_present "
            "— that provider's ship steps would have no key gate to read")
    assert 'echo "key_present=$key"' in policy[0], (
        f"{workflow}: the policy step no longer emits key_present — the "
        "any-key gate the notice / triage / red steps read is unfilled")
    assert ('if [ "$zai_key" = 1 ] || [ "$anthropic_key" = 1 ]; then key=1; '
            'else key=0; fi') in policy[0], (
        f"{workflow}: the policy step's key_present is no longer the "
        "either-key derivation (zai OR anthropic) — a keyless head would "
        "skip the whole run instead of falling through to the tail")
    notice = [c for c in chunks if _NO_KEY_NOTICE in c]
    assert len(notice) == 1, (
        f"{workflow}: expected exactly one step carrying the no-key notice "
        f"{_NO_KEY_NOTICE!r} in the `{row.job}` job, found {len(notice)}")
    cond = _step_condition(notice[0])
    assert re.search(r"steps\.policy\.outputs\.key_present\s*!=\s*'1'", cond), (
        f"{workflow}: the no-key notice step is not gated on "
        f"steps.policy.outputs.key_present != '1' (the any-key output): {cond!r}")
    assert not re.search(r"steps\.policy\.outputs\.[a-z0-9]+_key_present", cond), (
        f"{workflow}: the no-key notice step gates on ONE provider's "
        f"key-presence — it would announce a skip while the other provider's "
        f"links run: {cond!r}")


def test_routine_skip_notice_fires_only_when_no_provider_has_a_key():
    for row in ROUTINES.values():
        _assert_routine_skip_notice_fires_only_without_any_key(
            row, _routine_text(row.workflow))


def test_skip_notice_guard_rejects_a_single_provider_notice_gate():
    # NEGATIVE CONTROL: the labeler's notice gated on the head provider's
    # key alone (the pre-#544 `key_present` meaning) must fail — it would
    # announce "skipping" while the Anthropic tail ran.
    row = ROUTINES["labeler"]
    text = _routine_text(row.workflow)
    job = _routine_job_text(text, row)
    notice = [c for c in re.split(r"\n      - ", job) if _NO_KEY_NOTICE in c][0]
    assert "steps.policy.outputs.key_present != '1'" in notice
    tampered = text.replace(
        notice, notice.replace("steps.policy.outputs.key_present != '1'",
                               "steps.policy.outputs.zai_key_present != '1'", 1), 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="any-key output|ONE provider"):
        _assert_routine_skip_notice_fires_only_without_any_key(row, tampered)


def test_skip_notice_guard_rejects_a_head_only_key_present_derivation():
    # NEGATIVE CONTROL: key_present derived from the head provider's key
    # alone — the whole run would skip on a keyless head, tail or no tail.
    row = ROUTINES["labeler"]
    text = _routine_text(row.workflow)
    either = 'if [ "$zai_key" = 1 ] || [ "$anthropic_key" = 1 ]; then key=1; else key=0; fi'
    assert either in text, "tamper target not found — the fixture is stale"
    tampered = text.replace(either, 'if [ "$zai_key" = 1 ]; then key=1; else key=0; fi', 1)
    with pytest.raises(AssertionError, match="either-key derivation"):
        _assert_routine_skip_notice_fires_only_without_any_key(row, tampered)


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
    the same subset the routine workflows' walk expressions use, so a
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

    The full 4^N cartesian set (1024 rows for the five-link cross-provider
    walk, #544 — still trivial), so the simulation is exhaustive rather than
    sampled: every state where any link succeeded must read success, every
    all-dead state must not — and must read as the LAST link that actually
    ran. 'skipped' matters as much as 'failure': a whole provider's links are
    skipped when its key is absent, and the walk must read through them to
    the other provider's links. 'cancelled' is what a step killed by its own
    timeout (or a job cancel) reports; the walk must pass it through like a
    failure, never mistake it for a skip.
    """
    from itertools import product
    values = ("success", "failure", "skipped", "cancelled")
    for combo in product(values, repeat=n_links):
        yield combo


def _routine_walk_ids(reg: Registry, row: Routine, job_text: str) -> list[str]:
    """The walk's step ids in link order across providers, checked against
    the chain's link count (the step tests above catch a mismatch first)."""
    where = f"{row.workflow} [{row.job}]"
    links = reg.resolve(row.chain)
    ids = _walk_step_ids(_routine_ship_steps(job_text, row.resolve_id))
    assert len(ids) == len(links), (
        f"{where}: the `{row.chain}` chain has {len(links)} links but "
        f"the walk carries {len(ids)} ship steps ({ids}) — the drift guard's "
        "step tests should have caught this first")
    return ids


def _assert_routine_walk_outcome_covers_every_link(
        reg: Registry, row: Routine, text: str) -> None:
    """The walk's outcome expressions must read EVERY link, across providers.

    Resolve the chain, take the walk's step ids in link order, and evaluate
    each AGENT_OUTCOME / RUN / SHIP expression under every outcome
    combination of those steps. Any state where a link succeeded must yield
    'success' — and the all-dead states must not. The all-dead states must
    further yield the outcome of the LAST LINK THAT ACTUALLY RAN (the last
    non-'skipped' link), and 'skipped' only when EVERY link was skipped:
    routine-lock-cleanup.sh reads 'skipped' as "the agent never ran, nothing
    to release", so a walk that reported 'skipped' after the GLM links FAILED
    and the keyless Anthropic tail was skipped left a dead run's SHIP-LOCK
    standing (the bare `|| steps.<link5>.outcome` tail did exactly that).
    Factored out so the negative controls can run it against tampered text.
    """
    global _PROVIDER_UNDER_TEST
    workflow = row.workflow
    where = f"{row.workflow} [{row.job}]"
    _PROVIDER_UNDER_TEST = _routine_provider(row.conf)
    job = _routine_job_text(text, row)
    walk_ids = _routine_walk_ids(reg, row, job)
    exprs = _outcome_expressions(job)
    assert exprs, (
        f"{where}: no AGENT_OUTCOME/RUN/SHIP expression found in the "
        f"`{row.job}` job — the walk-outcome wiring this test exists to pin "
        "is missing")
    for var, expr_list in exprs.items():
        for expr in expr_list:
            for state in _walk_states(len(walk_ids)):
                outcomes = dict(zip(walk_ids, state))
                got = _eval_github_expression(expr, outcomes)
                any_success = "success" in state
                if any_success:
                    assert got == "success", (
                        f"{where}: {var} evaluated to {got!r} with link "
                        f"outcomes {outcomes} — a link succeeded but the "
                        "walk's outcome is not success; the expression does "
                        "not cover every link of the walk")
                else:
                    assert got != "success", (
                        f"{where}: {var} read {got!r} with no link having "
                        f"succeeded ({state}) — the walk claims a success "
                        "nobody produced")
                    ran = [o for o in state if o != "skipped"]
                    want = ran[-1] if ran else "skipped"
                    assert got == want, (
                        f"{where}: {var} read {got!r} with link outcomes "
                        f"{outcomes} — expected {want!r}, the outcome of the "
                        "last link that actually ran ('skipped' only when "
                        "every link was skipped); a 'skipped' with a link that "
                        "ran tells routine-lock-cleanup the agent never ran "
                        "and leaves a dead run's SHIP-LOCK standing")


def test_routine_walk_outcome_covers_every_link():
    reg = Registry.load(str(REGISTRY))
    for row in ROUTINES.values():
        _assert_routine_walk_outcome_covers_every_link(
            reg, row, _routine_text(row.workflow))


def test_routine_agent_outcome_is_assigned_identically_everywhere():
    # AGENT_OUTCOME is assigned twice in the SHIP-LOCK workflows (the lock
    # cleanup's env and the red-on-death step's env) and those two MUST be
    # byte-identical — a divergence would have the cleanup release a lock
    # while the gate still calls the run dead, or vice versa. The simulation
    # above proves each occurrence correct; this pins that they agree.
    lock_rows = [r for r in ROUTINES.values() if r.ship_lock]
    assert lock_rows, "no SHIP-LOCK routine in the ROUTINES table"
    for row in lock_rows:
        exprs = _outcome_expressions(_routine_job_text(_routine_text(row.workflow), row))
        found = [e.strip() for e in exprs.get("AGENT_OUTCOME", [])]
        assert len(found) == 2, (
            f"{row.workflow}: expected AGENT_OUTCOME assigned exactly twice (lock "
            f"cleanup + red-on-death), found {len(found)}")
        assert found[0] == found[1], (
            f"{row.workflow}: the two AGENT_OUTCOME expressions differ — the lock "
            "cleanup and the red-on-death gate would disagree on whether the "
            "run died")


# The walk-exhaustion gates — every step whose `if:` must fire exactly when NO
# link succeeded, named per row (`Routine.gates`). The SHIP-LOCK routines carry
# the red-on-death step; the others carry the exhausted-walk red (#544 — a
# walk exhausted with the tail skipped has no failed non-coe step to fail the
# job); every routine carries the provider-triage gate (#347), which no test
# simulated before #544 — a stale single-provider gate there would run a live
# classify probe after every healthy tail run and, with escalate on, could
# file a needs-decision on a chain that just succeeded.


def _gate_condition(job_text: str, step_name: str, workflow: str) -> str:
    """The `if: >-` body of the named step, one line."""
    # Horizontal whitespace only (`[ \t]`, one explicit \n per repetition):
    # a `\s` class also matches `\n`, which lets a repetition span lines
    # and partition a run of blank/indented lines ambiguously — the
    # exponential-backtracking shape CodeQL flagged on the original. The
    # step's `id:` line (the triage step has one) may sit between the name
    # and the `if:`, alongside comments.
    m = re.search(
        r"name:[ \t]*" + re.escape(step_name) + r"(?:[ \t]*#.*)?\n"
        r"(?:[ \t]*(?:#.*|id:[ \t]*\w+)\n)*"
        r"[ \t]*if: >-\n((?:[ \t]+.*\n)+?)(?=[ \t]*\w+(?:-\w+)*:)",
        job_text)
    assert m, (
        f"{workflow}: the '{step_name}' step's if-condition was not found — "
        "the walk-exhaustion wiring changed shape")
    return " ".join(l.strip() for l in m.group(1).splitlines())


# The legs of an exhaustion gate the simulation fixes GREEN, leaving the
# walk clause: the leading always(), the policy outputs (enabled /
# key_present, plus reeve's armed / greenlight), a select output held
# non-empty or at a literal (`issues != ''`, `propose == 'yes'`), and the
# dry-run input in either spelling (`github.event.inputs.dry_run != 'true'`,
# `inputs.dry_run != true`). A gate is `always() && <these legs> &&
# (<walk>) != 'success'` — the shape every converted routine must keep.
_FIXED_GREEN_LEGS = (
    r"steps\.policy\.outputs\.(enabled|key_present|armed|greenlight)\s*==\s*'(true|1)'\s*&&\s*",
    r"steps\.select\.outputs\.\w+\s*(!=\s*''|==\s*'\w+')\s*&&\s*",
    r"(github\.event\.)?inputs\.dry_run\s*!=\s*(true|'true')\s*&&\s*",
)


def _strip_fixed_green_legs(cond: str) -> str:
    sim = re.sub(r"^always\(\)\s*&&\s*", "", cond)
    for leg in _FIXED_GREEN_LEGS:
        sim = re.sub(leg, "", sim)
    return sim


def _assert_gate_fires_on_whole_walk_failure(
        reg: Registry, row: Routine, text: str, step_name: str) -> None:
    """The named gate's `if` must fire exactly when NO link succeeded.

    Simulates the gate's condition under every outcome combination of the
    walk's steps across providers: green when any link succeeded, red when
    none did. A gate still reading only one provider's links would fire
    after a healthy tail run.
    """
    global _PROVIDER_UNDER_TEST
    workflow = row.workflow
    where = f"{row.workflow} [{row.job}]"
    _PROVIDER_UNDER_TEST = _routine_provider(row.conf)
    job = _routine_job_text(text, row)
    walk_ids = _routine_walk_ids(reg, row, job)
    cond = _gate_condition(job, step_name, where)
    # The legs the simulation fixes green must actually BE there: stripping
    # tolerates absence, so a gate that DROPPED its key_present leg passed —
    # and would turn the keyless degraded path (every link skipped, the
    # pinned ::notice:: skip) into a red run; one that dropped its arming
    # leg would fire with the routine paused in git. Require presence first.
    assert re.search(r"steps\.policy\.outputs\.key_present\s*==\s*'1'", cond), (
        f"{where}: the '{step_name}' gate carries no "
        "steps.policy.outputs.key_present == '1' leg — with no key set for any "
        "provider the walk is all-skipped, and this gate would turn the "
        "pinned ::notice:: skip into a red run (or a live triage probe)")
    assert re.search(r"steps\.policy\.outputs\.(enabled|armed)\s*==\s*'true'", cond), (
        f"{where}: the '{step_name}' gate carries no arming leg "
        "(steps.policy.outputs.enabled == 'true', or reeve's armed) — it "
        "would fire with the routine paused in git")
    # Drop the legs the simulation fixes green (policy/enabled/select/
    # key/dry_run) and the leading always(), leaving the outcome clause.
    sim_cond = _strip_fixed_green_legs(cond)
    # The surviving clause is `(walk-success test) != 'success'`.
    mm = re.match(r"^\((.+)\)\s*!=\s*'success'\s*$", sim_cond.strip())
    assert mm, (
        f"{where}: the '{step_name}' condition's outcome clause does not "
        f"match the expected `(walk) != 'success'` shape after stripping "
        f"the fixed-green legs: {sim_cond!r}")
    inner = mm.group(1)
    for state in _walk_states(len(walk_ids)):
        outcomes = dict(zip(walk_ids, state))
        walk = _eval_github_expression(inner, outcomes)
        # `inner` is the walk-OUTCOME expression (the same string form as
        # AGENT_OUTCOME): it yields the string 'success' when any link
        # succeeded, else a non-'success' string ('failure'/'skipped'/'').
        # The gate is `(inner) != 'success'`, a STRING comparison — it must
        # NOT reduce to a bool, because GitHub coerces `(bool) != 'success'`
        # to numbers (true→1, 'success'→NaN) so it is ALWAYS true: the
        # always-red bug this shape must avoid.
        assert isinstance(walk, str), (
            f"{where}: the '{step_name}' walk clause must reduce to a "
            f"string outcome, so `!= 'success'` is a string compare rather "
            f"than an always-true bool-vs-string: {inner!r} → {walk!r}")
        fired = walk != "success"
        any_success = "success" in state
        assert fired == (not any_success), (
            f"{where}: the '{step_name}' gate fired={fired} under link "
            f"outcomes {outcomes} — expected fired={not any_success}; the "
            "gate does not cover the whole chain")


def test_routine_exhaustion_gates_fire_on_whole_chain_failure():
    reg = Registry.load(str(REGISTRY))
    for row in ROUTINES.values():
        assert TRIAGE_STEP in row.gates, (
            f"{row.workflow}: the ROUTINES row does not name the provider-triage "
            "step among its exhaustion gates — its `if:` would go unsimulated")
        text = _routine_text(row.workflow)
        for step_name in row.gates:
            _assert_gate_fires_on_whole_walk_failure(reg, row, text, step_name)


def _gate_chunk(job_text: str, step_name: str) -> str:
    """The raw step chunk of the named gate (for tampering its `if:`)."""
    chunks = [c for c in re.split(r"\n      - ", job_text) if f"name: {step_name}" in c]
    assert len(chunks) == 1, f"expected one '{step_name}' step, found {len(chunks)}"
    return chunks[0]


def _gate_without_leg(row: Routine, step_name: str, leg: str) -> str:
    """A copy of the workflow with one `&& <leg>` line removed from the named
    gate's `if:` — the leg is read off the live gate, never hand-copied."""
    text = _routine_text(row.workflow)
    chunk = _gate_chunk(_routine_job_text(text, row), step_name)
    m = re.search(r"^[ \t]*&& " + leg + r"\n", chunk, re.MULTILINE)
    assert m, f"tamper target not found — the gate's `{leg}` leg moved shape"
    tampered = text.replace(chunk, chunk.replace(m.group(0), "", 1), 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    return tampered


def test_gate_guard_rejects_a_red_step_without_its_key_present_leg():
    # NEGATIVE CONTROL: the labeler's red step with its key_present leg
    # dropped — the walk clause still covers every link, so only the
    # presence rule can see that the keyless degraded path now goes red.
    reg = Registry.load(str(REGISTRY))
    row = ROUTINES["labeler"]
    tampered = _gate_without_leg(
        row, EXHAUSTED_RED_STEP, r"steps\.policy\.outputs\.key_present == '1'")
    with pytest.raises(AssertionError, match="no steps.policy.outputs.key_present"):
        _assert_gate_fires_on_whole_walk_failure(reg, row, tampered, EXHAUSTED_RED_STEP)


def test_gate_guard_rejects_a_red_step_without_its_arming_leg():
    # NEGATIVE CONTROL: the same gate with its `enabled` leg dropped — it
    # would fire with the routine paused in git.
    reg = Registry.load(str(REGISTRY))
    row = ROUTINES["labeler"]
    tampered = _gate_without_leg(
        row, EXHAUSTED_RED_STEP, r"steps\.policy\.outputs\.enabled == 'true'")
    with pytest.raises(AssertionError, match="no arming leg"):
        _assert_gate_fires_on_whole_walk_failure(reg, row, tampered, EXHAUSTED_RED_STEP)


def test_burn_checkless_pr_notice_fires_only_on_a_successful_walk():
    # The burn's "Note a checkless draft PR" notice reads the walk too — the
    # positive form `(walk) == 'success'`: it must fire for ANY link's
    # success (a PR was opened, by whichever provider) and never otherwise.
    reg = Registry.load(str(REGISTRY))
    row = ROUTINES["backlog-burn"]
    workflow = row.workflow
    job = _routine_job_text(_routine_text(workflow), row)
    global _PROVIDER_UNDER_TEST
    _PROVIDER_UNDER_TEST = _routine_provider(row.conf)
    walk_ids = _routine_walk_ids(reg, row, job)
    cond = _gate_condition(job, "Note a checkless draft PR (no CI-triggering PAT)", workflow)
    sim = _strip_fixed_green_legs(cond)
    sim = re.sub(r"env\.HAS_GH_TOKEN\s*!=\s*'true'\s*&&\s*", "", sim)
    mm = re.match(r"^\((.+)\)\s*==\s*'success'\s*$", sim.strip())
    assert mm, f"{workflow}: the checkless-PR notice clause changed shape: {sim!r}"
    for state in _walk_states(len(walk_ids)):
        walk = _eval_github_expression(mm.group(1), dict(zip(walk_ids, state)))
        assert isinstance(walk, str)
        assert (walk == "success") == ("success" in state), (
            f"{workflow}: the checkless-PR notice misreads walk state {state}")


def _live_walk_expression(job_text: str, workflow: str) -> str:
    """The workflow's live walk-outcome expression body, derived from its
    first AGENT_OUTCOME (SHIP-LOCK routines) or RUN assignment — so the
    negative controls mutate what the file actually says rather than a
    hand-copied literal that silently stops matching (or keeps matching a
    dead substring) when the expression grows."""
    exprs = _outcome_expressions(job_text)
    body = (exprs.get("AGENT_OUTCOME") or exprs.get("RUN") or exprs.get("SHIP"))
    assert body, f"{workflow}: no walk-outcome expression to derive the mutation from"
    return body[0].strip()


def _stale_link1_copy(row: Routine) -> str:
    """A copy of the workflow whose EVERY walk-outcome expression — the env
    assignments AND the gate `if:`s that quote the same string — is reverted
    to a link-1-only read (the pre-#327 form), the real regression shape."""
    workflow = row.workflow
    text = _routine_text(workflow)
    job = _routine_job_text(text, row)
    live = _live_walk_expression(job, workflow)
    first = _walk_step_ids(_routine_ship_steps(job, row.resolve_id))[0]
    # EVERY occurrence must go stale together: mutating only one would leave
    # a healthy copy for the extractor/simulation and the control would pass
    # vacuously. The expression appears at least twice in every routine (the
    # record step's RUN/SHIP plus each exhaustion gate).
    assert text.count(live) >= 2, (
        f"{workflow}: the live walk expression appears {text.count(live)} "
        "time(s) — the negative-control mutation would not represent the "
        "regression; update the derivation")
    return text.replace(live, f"steps.{first}.outcome")


def test_walk_outcome_guard_fires_on_a_stale_link1_expression():
    """Negative control: prove the walk-outcome guard can fail.

    The regression it exists for is a chain deepened (or crossed to another
    provider) while an outcome expression still reads only link 1. Derive
    that mutation from the live expression in design-run.yml and require the
    real simulation to FAIL: with a link-2 (or tail) success, the stale
    expression reports the walk as dead, which would withdraw a live run's
    SHIP-LOCK.
    """
    reg = Registry.load(str(REGISTRY))
    row = ROUTINES["design-run"]
    tampered = _stale_link1_copy(row)
    with pytest.raises(AssertionError, match="does not cover every link"):
        _assert_routine_walk_outcome_covers_every_link(reg, row, tampered)


def test_exhaustion_gate_guards_fire_on_a_stale_link1_gate():
    """Negative control for every exhaustion-gate simulation, every
    routine: a gate still pinned to link 1 would fire (fail the job, or run
    a live triage probe) after a healthy link-2 or tail run. Derive the
    mutation from each workflow's live expression and require each gate's
    simulation to fail."""
    reg = Registry.load(str(REGISTRY))
    for row in ROUTINES.values():
        tampered = _stale_link1_copy(row)
        for step_name in row.gates:
            with pytest.raises(AssertionError, match="does not cover the whole chain"):
                _assert_gate_fires_on_whole_walk_failure(reg, row, tampered, step_name)


def test_walk_outcome_guard_fires_on_a_single_provider_expression():
    """Negative control for #544 specifically: an expression that still reads
    only the HEAD provider's links (the pre-#544 zai-block form — correct for
    three links, blind to the Anthropic tail) must fail the simulation: a
    healthy link-4 run would read as dead."""
    reg = Registry.load(str(REGISTRY))
    row = ROUTINES["backlog-burn"]
    workflow = row.workflow
    text = _routine_text(workflow)
    job = _routine_job_text(text, row)
    live = _live_walk_expression(job, workflow)
    ids = _walk_step_ids(_routine_ship_steps(job, row.resolve_id))
    head_only = (f"steps.{ids[0]}.outcome == 'success' && 'success' || "
                 f"steps.{ids[1]}.outcome == 'success' && 'success' || "
                 f"steps.{ids[2]}.outcome")
    assert text.count(live) >= 2
    tampered = text.replace(live, head_only)
    with pytest.raises(AssertionError, match="does not cover every link"):
        _assert_routine_walk_outcome_covers_every_link(reg, row, tampered)
    with pytest.raises(AssertionError, match="does not cover the whole chain"):
        _assert_gate_fires_on_whole_walk_failure(reg, row, tampered, TRIAGE_STEP)


def _bare_tail_copy(row: Routine) -> str:
    """A copy of the workflow whose EVERY walk-outcome expression is reverted
    to the bare-last-link tail (`… || steps.<last link>.outcome`, the
    original #544 form): derived from the live expression by stripping the
    nested last-ran fallback, never from a hand-copied literal."""
    workflow = row.workflow
    text = _routine_text(workflow)
    live = _live_walk_expression(_routine_job_text(text, row), workflow)
    bare = re.sub(
        r" \|\| steps\.(\w+)\.outcome == 'success' && 'success' \|\| "
        r"\(steps\.\1\.outcome == 'skipped' && .*\)$",
        r" || steps.\1.outcome", live)
    assert bare != live, (
        f"{workflow}: the live walk expression carries no nested last-ran "
        "fallback to strip — the negative-control derivation is stale")
    assert text.count(live) >= 2
    return text.replace(live, bare)


def test_walk_outcome_guard_fires_on_a_bare_tail_expression():
    """Negative control for the last-ran rule: the bare-tail form reads
    'skipped' whenever the tail was skipped for want of its key — even after
    the head links FAILED — so routine-lock-cleanup would no-op on a dead run
    and leave its SHIP-LOCK standing. The simulation must reject it, for every
    routine, on exactly that rule (the any-success half still passes: the bare
    tail does cover every link's success)."""
    reg = Registry.load(str(REGISTRY))
    for row in ROUTINES.values():
        tampered = _bare_tail_copy(row)
        with pytest.raises(AssertionError, match="last link that actually ran"):
            _assert_routine_walk_outcome_covers_every_link(reg, row, tampered)


# ── The job budget vs GitHub's hosted-job cap ────────────────────────────────
#
# A hosted job is hard-capped at 360 minutes; a larger `timeout-minutes` is
# clamped, so a budget "2 × 220 + 20 = 460" budgeted nothing — a head link
# that stalled to its 220 would have the PLATFORM kill the fallback link
# mid-walk, and with it the lock cleanup (the #312 guillotine, one level up).
# The rule: job budget <= 360, and >= the longest HEAD step timeout + the
# longest TAIL step timeout + 5, so one stalled head plus one full fallback
# link always fits. The tail steps' timeout-minutes is therefore allowed to
# differ from their GLM siblings' on purpose (design-run: 220 head, 120 tail)
# — no pin here compares the step chunks byte for byte.

_PLATFORM_JOB_CAP_MINUTES = 360
_JOB_BUDGET_HEADROOM_MINUTES = 5


def _routine_job_timeout(job_text: str, workflow: str) -> int:
    """The routine JOB's timeout-minutes (4-space indent = job level; the
    ship steps' own timeouts sit deeper) — read from the row's job only, so
    a sibling job's budget (reeve.yml's report / observe) never stands in."""
    found = re.findall(r"^ {4}timeout-minutes: (\d+)$", job_text, re.MULTILINE)
    assert len(found) == 1, (
        f"{workflow}: expected exactly one job-level timeout-minutes in the "
        f"routine's job, found {found}")
    return int(found[0])


def _routine_step_timeouts(reg: Registry, row: Routine,
                           job_text: str) -> tuple[int, int]:
    """(longest head-provider ship-step timeout, longest tail-provider one).
    The head provider is the chain's link-1 provider; a walk with no tail
    reports 0 for it."""
    where = f"{row.workflow} [{row.job}]"
    links = {link.position: link for link in reg.resolve(row.chain)}
    head_provider = links[1].provider
    head, tail = 0, 0
    for step in _routine_ship_steps(job_text, row.resolve_id):
        m = re.search(r"^\s*timeout-minutes: (\d+)$", step["chunk"], re.MULTILINE)
        assert m, (
            f"{where}: the link-{step['link']} ship step carries no "
            "timeout-minutes")
        minutes = int(m.group(1))
        if links[step["link"]].provider == head_provider:
            head = max(head, minutes)
        else:
            tail = max(tail, minutes)
    return head, tail


def _assert_routine_job_budget_fits_the_platform_cap(
        reg: Registry, row: Routine, text: str) -> None:
    workflow = row.workflow
    where = f"{row.workflow} [{row.job}]"
    job_text = _routine_job_text(text, row)
    job = _routine_job_timeout(job_text, where)
    head, tail = _routine_step_timeouts(reg, row, job_text)
    assert job <= _PLATFORM_JOB_CAP_MINUTES, (
        f"{where}: job timeout-minutes {job} exceeds GitHub's "
        f"{_PLATFORM_JOB_CAP_MINUTES}-minute hosted-job cap — the platform clamps "
        "it, so the budget the comment claims is fiction and a stalled head "
        "link lets the platform kill the fallback link (and the lock cleanup) "
        "mid-walk")
    need = head + tail + _JOB_BUDGET_HEADROOM_MINUTES
    assert job >= need, (
        f"{where}: job timeout-minutes {job} does not budget one stalled head "
        f"link ({head}) plus one full tail link ({tail}) plus "
        f"{_JOB_BUDGET_HEADROOM_MINUTES} headroom = {need} — shorten a step "
        "timeout or raise the job budget (within the cap)")


def test_every_routine_job_budget_fits_the_platform_cap():
    reg = Registry.load(str(REGISTRY))
    for row in ROUTINES.values():
        _assert_routine_job_budget_fits_the_platform_cap(
            reg, row, _routine_text(row.workflow))


def test_job_budget_guard_rejects_a_budget_over_the_platform_cap():
    # NEGATIVE CONTROL: design-run's pre-fix 460 — a copy with the job budget
    # over the cap must fail on the cap rule.
    reg = Registry.load(str(REGISTRY))
    row = ROUTINES["design-run"]
    workflow = row.workflow
    text = _routine_text(workflow)
    live = _routine_job_timeout(_routine_job_text(text, row), workflow)
    tampered = text.replace(f"\n    timeout-minutes: {live}\n",
                            "\n    timeout-minutes: 460\n", 1)
    assert tampered != text, "tamper target not found — the fixture is stale"
    with pytest.raises(AssertionError, match="hosted-job cap"):
        _assert_routine_job_budget_fits_the_platform_cap(reg, row, tampered)


def test_job_budget_guard_rejects_a_tail_step_the_budget_cannot_carry():
    # NEGATIVE CONTROL: raise design-run's tail steps back to the head's 220
    # — 220 + 220 + 5 > 360, so one stalled head no longer leaves room for a
    # full fallback link. Derived from the live head timeout, no literals.
    reg = Registry.load(str(REGISTRY))
    row = ROUTINES["design-run"]
    text = _routine_text(row.workflow)
    head, tail = _routine_step_timeouts(reg, row, _routine_job_text(text, row))
    assert tail < head, "the fixture is stale — design-run's tail is no longer budgeted shorter"
    tampered = text
    for link in (4, 5):
        chunk = _tail_step_chunk(tampered, row, link)
        tampered = tampered.replace(
            chunk, chunk.replace(f"timeout-minutes: {tail}\n",
                                 f"timeout-minutes: {head}\n", 1), 1)
    assert tampered != text
    with pytest.raises(AssertionError, match="does not budget one stalled head"):
        _assert_routine_job_budget_fits_the_platform_cap(reg, row, tampered)


def _routine_workflows() -> list[str]:
    """Every workflow file the ROUTINES table names, once each."""
    return sorted({row.workflow for row in ROUTINES.values()})


def test_no_hardcoded_model_literal_in_any_routine():
    # The #326 acceptance criterion as a test: no --model literal of ANY
    # provider may appear in any routine workflow.
    for workflow in _routine_workflows():
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
    for workflow in _routine_workflows():
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
# The consumers are the review pipeline (file-level) plus every ROUTINES row
# (scoped to the row's job, so wright.yml's two walks each triage their own
# chain) — a routine joins the triage pin by joining the table.

TRIAGE_ACTION = REPO_ROOT / ".github" / "actions" / "provider-triage" / "action.yml"
TRIAGE_CONSUMERS = {"auto-review.yml": "review"}


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
    for row in ROUTINES.values():
        job = _routine_job_text(_routine_text(row.workflow), row)
        chains = _triage_chains(job)
        assert chains == [row.chain], (
            f"{row.workflow}: the `{row.job}` job wires provider-triage to "
            f"chain(s) {chains}, but it walks the {row.chain!r} chain — exactly "
            "one triage step, on the chain the job walks")
        assert f"model_registry resolve {row.chain}" in job, (
            f"{row.workflow}: the `{row.job}` job triages chain {row.chain!r} "
            "but does not resolve it — the walk and the diagnosis have drifted apart")


def test_provider_triage_action_declares_the_io_its_callers_use():
    # A rename or dropped input/output would break every caller at once;
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
# The forge is ONE workflow (wright.yml) carrying TWO walks — `wright` (the
# propose half) in the `propose` job and `wright-signoff` (the judging half)
# in the `signoff` job — each resolved by its own step id in its own job,
# the Oracle's two-chain pattern. Since #544 Part B each walk crosses
# providers (the propose half in the scout's three-link shape, the sign-off
# in the labeler's five-link one) and is its own row of the ROUTINES table
# above — "wright-propose" and "wright-signoff" — so every generic pin reads
# each job separately: the chain fits its walk (head on the conf provider,
# one step per link wired to its link's provider, the row's layout), the walk
# order, the per-provider key gates, the outcome simulation and the
# exhaustion gates per job, the job budget, the no-literal rule and the
# triage wiring on each job's OWN chain — and, since the review round, the
# agent surface on EVERY walk step of each half (the tail included, which
# runs only on the fall-through path): each row declares ITS OWN deny
# backstop, filing server and allow-list, and the generic surface pin holds
# every step to them verbatim. What stays explicit here is the forge's own
# invariant, which equality on one row cannot state alone: the two halves'
# surfaces DIFFER — a step carrying the other half's backstop would collapse
# the proposer/judge separation the forge is built on (the sign-off can
# apply `autonomy-ok`, so a shed or swapped backstop there is the worst
# drift in the family; scripts/wright-perms-check.sh holds the file side of
# that split). Plus the degraded path in its any-provider form.

# ROUTINES row → the half's OWN deny backstop, read from the table so the
# two can never disagree.
WRIGHT_BACKSTOPS = {name: ROUTINES[name].backstop
                    for name in ("wright-propose", "wright-signoff")}


def test_wright_halves_carry_different_surfaces():
    # The separation as a table fact: the two halves share a workflow and a
    # read wrapper but never a backstop or a filing server.
    propose, signoff = ROUTINES["wright-propose"], ROUTINES["wright-signoff"]
    assert propose.backstop != signoff.backstop, (
        "the forge's two halves declare the same deny backstop — the "
        "proposer/judge separation is gone from the table")
    assert propose.mcp_config != signoff.mcp_config, (
        "the forge's two halves declare the same filing server — the "
        "proposer could hold the arming tool")


def test_wright_backstop_guard_rejects_a_tail_step_on_the_other_halfs_backstop():
    # NEGATIVE CONTROL: the sign-off's terminal tail step rewired to the
    # PROPOSER's backstop — the cross-half drift, on the fall-through path —
    # must fail the generic surface pin (the sibling's backstop is a real
    # committed file, so only exact equality can see the swap). Derived from
    # the live step, not a hand-copied literal.
    row = ROUTINES["wright-signoff"]
    text = _routine_text(row.workflow)
    chunk = _terminal_step_chunk(row, text)
    own, other = WRIGHT_BACKSTOPS["wright-signoff"], WRIGHT_BACKSTOPS["wright-propose"]
    assert f"--settings {own}" in chunk, "tamper target not found — the fixture is stale"
    tampered = text.replace(
        chunk, chunk.replace(f"--settings {own}", f"--settings {other}", 1), 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="deny backstop"):
        _assert_routine_walk_steps_keep_their_surface(row, tampered)


def test_wright_degraded_path_skips_with_a_notice_only_when_no_key_is_present():
    # The #326 constraint on both halves, reworded for #544: each job's
    # secret-absent path is a ::notice:: skip that fires only when NO
    # provider in its chain has a key (the generic rule proves the gate per
    # row), and the pre-#544 single-provider wording is gone from the file.
    text = _routine_text("wright.yml")
    for name in WRIGHT_BACKSTOPS:
        _assert_routine_skip_notice_fires_only_without_any_key(ROUTINES[name], text)
    assert "::notice::the configured provider" not in text, (
        "wright.yml still carries the single-provider secret-absent notice — "
        "under the cross-provider walk a keyless head is a fall-through, not "
        "a skip")


# ── Reeve's greenlight drafter (issue #443, #296 stage 2; #544 Part B) ───────
#
# reeve.yml is an unusual consumer: ONE workflow whose jobs carry opposite
# security postures. The `report` job is the deterministic, keyless reporter
# — every finding a recomputable fact, no provider secret, no agent — and
# issue #443's contract is that it STAYS that way: the LLM greenlight
# drafter is a SEPARATE job that runs after it, so the secret enters only
# where the agent runs. Since #544 Part B the greenlight job walks its
# chain across providers (the scout's three-link shape) as the
# "reeve-greenlight" row of the ROUTINES table above, so every generic pin
# reads THAT job alone — the chain fits its walk, one step per link wired
# to its link's provider, the walk order, the per-provider key gates, the
# outcome simulation, the exhaustion gates, the job budget, the no-literal
# rule, the triage wiring — and, since the review round, the #442
# containment surface on EVERY walk step (dontAsk, the loop's own backstop,
# the exact wrapper-only allow-list, no mcp-config — the row's fields, held
# by the generic surface pin, the tail included) — and never the report or
# observe jobs. What stays explicit here, each with a negative control: the
# job split itself; the two containment facts equality on the row cannot
# say (no MCP server mentioned ANYWHERE on a step — the wrapper is both the
# read and the write surface — and the committed skill as the prompt, never
# an inline one that bypasses it); the #443 keyed-and-skippable degraded
# path in its any-provider form; and the report job's keylessness.

REEVE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "reeve.yml"
# The drafter's own deny backstop (#442) and its single shell surface.
REEVE_BACKSTOP = ".claude/reeve-settings.json"
REEVE_WRAPPER = ".claude/skills/reeve-greenlight/greenlight-helper.sh"


def _reeve_text() -> str:
    return REEVE_WORKFLOW.read_text(encoding="utf-8")


def _reeve_walk_steps(text: str) -> list[dict]:
    """The greenlight walk's ship steps, every link, via the generic parser."""
    row = ROUTINES["reeve-greenlight"]
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    assert steps, "reeve.yml's greenlight job has no claude-code-action ship step"
    return steps


def test_reeve_greenlight_is_a_separate_job_after_the_report():
    # The drafter must run in its OWN job that `needs:` the report — the report
    # job's keylessness is structural, not incidental, so an agent step cannot
    # creep into the reporter.
    row = ROUTINES["reeve-greenlight"]
    blocks = _job_blocks(_reeve_text())
    assert row.job in blocks, f"reeve.yml has no `{row.job}` job"
    assert re.search(r"^    needs: report\b", blocks[row.job], re.MULTILINE), (
        "reeve.yml's greenlight job does not `needs: report` — the drafter must "
        "run after (and only after a successful) deterministic report")
    # And it must be the workflow's resolve step that picks the model.
    assert f"model_registry resolve {row.chain}" in blocks[row.job], (
        f"the greenlight job no longer resolves the `{row.chain}` chain — "
        "its model would have to come from somewhere the registry does not own")


def test_reeve_greenlight_row_declares_the_wrapper_only_surface():
    # The #442 containment as a table fact, held on every step by the
    # generic surface pin: the loop's OWN backstop, the wrapper as the ONLY
    # Bash allow plus the read-only file tools, and no MCP server.
    row = ROUTINES["reeve-greenlight"]
    assert row.backstop == REEVE_BACKSTOP
    assert row.mcp_config is None, "the greenlight row mounts an MCP server — none exists to allow"
    assert f"Bash({REEVE_WRAPPER}:*)" in row.allowed and row.allowed.endswith("Read,Grep,Glob")
    assert not re.search(r"Bash\((?!\.?/?\.claude/skills/reeve-greenlight/)", row.allowed), (
        "the greenlight row allows a Bash beyond the wrapper")


def _assert_reeve_greenlight_walk_keeps_the_containment_surface(text: str) -> None:
    """The two containment facts the generic (per-flag equality) pin cannot
    say: no MCP server mentioned ANYWHERE on a step (not only on the
    claude_args line — the wrapper is both the read and the write surface),
    and the committed skill as the prompt — never an inline one that
    bypasses it. Factored out so the negative control can run it against
    tampered text."""
    for step in _reeve_walk_steps(text):
        where = f"reeve greenlight link-{step['link']} ship step"
        chunk = step["chunk"]
        assert "mcp__" not in chunk and "--mcp-config" not in chunk, (
            f"{where}: allows an MCP server — the loop's write surface is the "
            "wrapper, and no server exists to allow")
        assert "prompt: /reeve-greenlight" in chunk, (
            f"{where}: no longer invokes the committed /reeve-greenlight skill "
            "— an inline prompt would bypass it")


def test_reeve_greenlight_walk_steps_keep_the_containment_surface():
    _assert_reeve_greenlight_walk_keeps_the_containment_surface(_reeve_text())


def test_reeve_containment_guard_rejects_a_tail_step_with_an_inline_prompt():
    # NEGATIVE CONTROL: the terminal tail step's prompt swapped for an
    # inline one — the skill bypassed on the one path that runs unwatched.
    # Anchored inside the live step, never the file's first occurrence.
    text = _reeve_text()
    chunk = max(_reeve_walk_steps(text), key=lambda s: s["link"])["chunk"]
    needle = "prompt: /reeve-greenlight"
    assert needle in chunk, "tamper target not found — the fixture is stale"
    tampered = text.replace(
        chunk, chunk.replace(needle, "prompt: draft a greenlight on every parked issue", 1), 1)
    with pytest.raises(AssertionError, match="committed /reeve-greenlight skill"):
        _assert_reeve_greenlight_walk_keeps_the_containment_surface(tampered)


def test_reeve_greenlight_degraded_path_skips_with_a_notice_only_when_no_key_is_present():
    # The keyed-and-skippable requirement (#443's Done-when), reworded for
    # #544: every walk step gates on ITS provider's key (the generic
    # per-provider rule), the secret-absent path is a ::notice:: skip that
    # fires only when NO provider in the chain has a key — never a red run —
    # and the pre-#544 single-provider wording is gone with it.
    row = ROUTINES["reeve-greenlight"]
    text = _reeve_text()
    _assert_routine_skip_notice_fires_only_without_any_key(row, text)
    assert "::notice::the configured provider" not in text, (
        "reeve.yml still carries the single-provider secret-absent notice — "
        "under the cross-provider walk a keyless head is a fall-through, not "
        "a skip")


def test_reeve_key_gate_guard_fires_on_a_head_step_without_its_gate():
    # NEGATIVE CONTROL for #443's keyed-and-skippable Done-when, re-derived
    # for the walk: strip the HEAD step's own-provider key gate (the generic
    # control, test_key_gate_guard_rejects_a_tail_step_without_its_key_gate,
    # strips a TAIL step's on the labeler — this is the other end of the
    # walk) and require the per-provider key-gate rule to fail. The leg is
    # read off the live step, never hand-copied.
    reg = Registry.load(str(REGISTRY))
    row = ROUTINES["reeve-greenlight"]
    text = _reeve_text()
    head = min(_reeve_walk_steps(text), key=lambda s: s["link"])
    m = re.search(
        r"^[ \t]*&& steps\.policy\.outputs\.[a-z0-9]+_key_present == '1'\n",
        head["chunk"], re.MULTILINE)
    assert m, "tamper target not found — the head step's key gate moved shape"
    tampered = text.replace(
        head["chunk"], head["chunk"].replace(m.group(0), "", 1), 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="link-1 ship step"):
        _assert_routine_steps_gate_on_their_providers_key(reg, row, tampered)


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
