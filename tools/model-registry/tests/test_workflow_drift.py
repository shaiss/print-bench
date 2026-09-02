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
# no-literal rule and the triage wiring. What stays explicit here is what
# the generic pins do NOT say: the converter's ONE write is not its own MCP
# server but the scout's REUSED filing tool (#439), so EVERY walk step —
# the tail included, which runs only on the fall-through path where nobody
# is watching — must carry the converter's own deny backstop, the scout's
# mcp-config and an allow-list naming exactly mcp__scout__file_design_brief
# (the workflow half of the coupling scripts/spike-converter-perms-check.sh
# holds over the files); issue #440's two frozen acceptance criteria — the
# conf declares the chain's head provider, and the two-key arming gates the
# job on every link; and the #440 degraded path, a ::notice:: skip that now
# fires only when NO provider in the chain has a key.

# The converter's own deny backstop, the scout's filing server it reuses, and
# the exact allow-list — the tool, its own read wrapper (both spellings) and
# the read-only file tools.
_SPIKE_BACKSTOP = ".claude/spike-converter-settings.json"
_SPIKE_MCP_CONFIG = ".claude/skills/product-scout/scout-mcp.json"
_SPIKE_ALLOWED = (
    "mcp__scout__file_design_brief,"
    "Bash(.claude/skills/spike-converter/converter-helper.sh:*),"
    "Bash(./.claude/skills/spike-converter/converter-helper.sh:*),"
    "Read,Grep,Glob")


def _spike_walk_steps(text: str) -> list[dict]:
    """The converter walk's ship steps (every link, via the generic parser),
    each with the surface fields the reuse pin reads parsed off its chunk."""
    row = ROUTINES["spike-converter"]
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    assert steps, (
        f"no claude-code-action ship step found in {row.workflow}'s `{row.job}` job")
    for step in steps:
        chunk = step["chunk"]
        settings = re.search(r"--settings (\S+)", chunk)
        mcp = re.search(r"--mcp-config (\S+)", chunk)
        allowed = re.search(r'--allowedTools "([^"]*)"', chunk)
        step["settings"] = settings.group(1) if settings else None
        step["mcp_config"] = mcp.group(1) if mcp else None
        step["allowed_tools"] = allowed.group(1) if allowed else ""
    return steps


def test_spike_converter_chain_exists_and_resolves():
    # The chain issue #440 names. A registry edit that dropped it would fail
    # the workflow's resolve step at run time — on the converter's weekly
    # cadence, where nobody is watching. Catch it here instead.
    row = ROUTINES["spike-converter"]
    links = Registry.load(str(REGISTRY)).resolve(row.chain)
    assert links, f"the `{row.chain}` chain resolved to zero links"


def _assert_spike_walk_carries_the_reused_surface(text: str) -> None:
    """Every walk step — head and tail alike — carries the #439/#440 reuse:
    the converter's own backstop, the SCOUT's mcp-config, the exact
    allow-list and dontAsk. A step that drops any of these either widens the
    unattended run's surface or — for the mcp-config / allow-list — silently
    revokes its only write, so the armed routine files nothing and fails
    without an error. Factored out so the negative control can run it
    against tampered text."""
    for step in _spike_walk_steps(text):
        where = f"spike-converter link-{step['link']} ship step"
        assert step["settings"] == _SPIKE_BACKSTOP, (
            f"{where}: --settings is {step['settings']!r}, not the converter's "
            f"own deny backstop {_SPIKE_BACKSTOP}")
        assert step["mcp_config"] == _SPIKE_MCP_CONFIG, (
            f"{where}: --mcp-config is {step['mcp_config']!r}, not the reused "
            f"scout filing server {_SPIKE_MCP_CONFIG} — filing a brief any "
            "other way breaks #439's one-filing-surface rule")
        assert step["allowed_tools"] == _SPIKE_ALLOWED, (
            f"{where}: allow-list is {step['allowed_tools']!r}, expected "
            f"exactly {_SPIKE_ALLOWED!r}")
        assert "--permission-mode dontAsk" in step["chunk"], (
            f"{where}: the dontAsk mode is gone — without it the allow-list "
            "stops being exclusive and a prompt-injected run gets "
            "prompted-for tools")


def test_spike_converter_walk_steps_wire_the_reused_surface():
    row = ROUTINES["spike-converter"]
    _assert_spike_walk_carries_the_reused_surface(_routine_text(row.workflow))


def test_spike_reuse_guard_rejects_a_tail_step_that_sheds_the_mcp_config():
    # NEGATIVE CONTROL: the terminal tail step without the reused scout
    # mcp-config — its only write silently revoked, on the one path that
    # runs unwatched — must fail. The tamper is anchored inside the live
    # step, not the file's first occurrence, so it stays valid whichever
    # link's step the file lists first.
    row = ROUTINES["spike-converter"]
    text = _routine_text(row.workflow)
    chunk = max(_spike_walk_steps(text), key=lambda s: s["link"])["chunk"]
    needle = f"--mcp-config {_SPIKE_MCP_CONFIG} "
    assert needle in chunk, "tamper target not found — the fixture is stale"
    tampered = text.replace(chunk, chunk.replace(needle, "", 1), 1)
    with pytest.raises(AssertionError, match="mcp-config"):
        _assert_spike_walk_carries_the_reused_surface(tampered)


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
        gates=("Turn a dead agentic run red", TRIAGE_STEP), ship_lock=True),
    "backlog-burn": Routine(
        workflow="backlog-burn.yml", chain="backlog-burn",
        conf=".github/backlog-burn.conf", job="burn",
        resolve_id="chain", prefix="ship",
        layout=("zai", "zai", "zai", "anthropic", "anthropic"),
        gates=("Turn a dead agentic run red", TRIAGE_STEP), ship_lock=True),
    "chunker": Routine(
        workflow="chunker.yml", chain="chunker",
        conf=".github/chunker.conf", job="chunk",
        resolve_id="chain", prefix="run",
        layout=("zai", "zai", "zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False),
    "labeler": Routine(
        workflow="labeler.yml", chain="labeler",
        conf=".github/labeler.conf", job="label",
        resolve_id="chain", prefix="run",
        layout=("zai", "zai", "zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False),
    # #544 Part B: the eight formerly single-link routines, one row each —
    # the GLM head (one link, or the sign-off's three), then the two-link
    # Anthropic tail. The scout was the template.
    "scout": Routine(
        workflow="product-scout.yml", chain="scout",
        conf=".github/product-scout.conf", job="scout",
        resolve_id="chain", prefix="run",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False),
    "spike-converter": Routine(
        workflow="spike-converter.yml", chain="spike-converter",
        conf=".github/spike-converter.conf", job="convert",
        resolve_id="chain", prefix="run",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False),
    "adoption-assessor": Routine(
        workflow="adoption-assessor.yml", chain="adoption-assessor",
        conf=".github/adoption-assessor.conf", job="assess",
        resolve_id="chain", prefix="run",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False),
    "growth-twitter": Routine(
        workflow="growth-twitter.yml", chain="growth-twitter",
        conf=".github/growth-twitter.conf", job="drain",
        resolve_id="chain", prefix="run",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False),
    "reeve-growth": Routine(
        workflow="reeve-growth.yml", chain="reeve-growth",
        conf=".github/reeve-growth.conf", job="reeve-growth",
        resolve_id="chain", prefix="run",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False),
    # wright.yml carries two walks, one per job, each on its own chain and
    # its own resolve step (the Oracle's two-chain pattern) — two rows.
    "wright-propose": Routine(
        workflow="wright.yml", chain="wright",
        conf=".github/wright.conf", job="propose",
        resolve_id="propose_chain", prefix="propose",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False),
    "wright-signoff": Routine(
        workflow="wright.yml", chain="wright-signoff",
        conf=".github/wright.conf", job="signoff",
        resolve_id="signoff_chain", prefix="signoff",
        layout=("zai", "zai", "zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False),
    # reeve.yml's one agentic job; the report and observe jobs stay keyless
    # (pinned separately below) and are never walked.
    "reeve-greenlight": Routine(
        workflow="reeve.yml", chain="reeve-greenlight",
        conf=".github/reeve.conf", job="greenlight",
        resolve_id="chain", prefix="run",
        layout=("zai", "anthropic", "anthropic"),
        gates=(EXHAUSTED_RED_STEP, TRIAGE_STEP), ship_lock=False),
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
        steps.append({
            "id": step_id.group(1) if step_id else "",
            "link": int(model.group(1)) if model else None,
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
    assert chain_id in reg.chains, (
        f"the `{chain_id}` chain (consumed by {workflow}) is missing from "
        "the registry — the workflow's resolve step would fail at run time")
    links = reg.resolve(chain_id)
    conf_provider = _routine_provider(row.conf)
    assert links[0].provider == conf_provider, (
        f"{workflow}: link 1 of `{chain_id}` is on provider "
        f"{links[0].provider!r} but {row.conf} declares provider {conf_provider!r} "
        "as the walk's HEAD — the routine would start on the wrong endpoint")
    # Every link on a declared provider (a chain can only cross to providers
    # the registry knows).
    for link in links:
        assert link.provider in reg.providers, (
            f"{workflow}: link {link.position} of `{chain_id}` names provider "
            f"{link.provider!r}, which the registry does not declare")
    from model_registry.registry import walk_shape_errors
    job = _routine_job_text(text, row)
    steps = _routine_ship_steps(job, row.resolve_id)
    assert steps, f"no claude-code-action ship step found in {workflow}'s `{row.job}` job"
    layout = _walk_layout(reg, steps, workflow)
    errors = walk_shape_errors(links, conf_provider, layout)
    assert not errors, (
        f"{workflow}: the `{chain_id}` chain does not fit the walk the ship "
        f"steps carry ({','.join(layout)}): " + "; ".join(errors))
    # The runtime half must check the SAME layout the steps really carry —
    # a resolve step handing `shape` a stale literal would pass a chain the
    # steps cannot walk.
    literal = _resolve_layout_literal(job, chain_id, workflow)
    assert literal == layout, (
        f"{workflow}: the resolve step's --layout literal {','.join(literal)} "
        f"differs from the layout the ship steps actually carry "
        f"{','.join(layout)} — the runtime shape check and the workflow drifted")
    # And the table's expectation: the row says what walk this routine
    # carries, so a walk that quietly changed shape (a dropped tail step, a
    # fourth GLM link) fails against the declared layout even when chain,
    # steps and literal all moved together.
    assert layout == list(row.layout), (
        f"{workflow}: the ROUTINES row declares layout {','.join(row.layout)} "
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
        providers = [link.provider for link in reg.resolve(row.chain)]
        assert len(set(providers)) > 1, (
            f"{row.workflow}: the `{row.chain}` chain sits entirely on "
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
    links = reg.resolve(chain_id)
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    assert steps, f"no claude-code-action ship step found in {workflow}'s `{row.job}` job"
    link_positions = {link.position for link in links}
    for step in steps:
        assert step["link"] in link_positions, (
            f"{workflow}: a ship step references link{step['link']}_model, "
            f"but the `{chain_id}` chain has links {sorted(link_positions)} "
            "— add the registry link or fix the reference")
    # One ship step per link, in order — derived from the steps, compared to
    # the chain. A workflow still carrying only one provider's steps against
    # a mixed chain fails HERE (a link with no step), as does a latent block
    # reading a link another step already walks.
    layout = _walk_layout(reg, steps, workflow)
    assert len(layout) == len(links), (
        f"{workflow}: the ship steps walk {len(layout)} links but the "
        f"`{chain_id}` chain has {len(links)} — one ship step per link")
    for link, provider in zip(links, layout):
        assert provider == link.provider, (
            f"{workflow}: the link-{link.position} ship step is wired for "
            f"provider {provider!r} (its secret/endpoint) but the registry "
            f"routes link {link.position} ({link.model}) to "
            f"{link.provider!r} — the step would spend the wrong key against "
            "the wrong endpoint")


def test_every_routine_ship_step_is_pinned_to_its_chain():
    reg = Registry.load(str(REGISTRY))
    for row in ROUTINES.values():
        _assert_routine_ship_steps_pinned(reg, row, _routine_text(row.workflow))


def _assert_routine_step_ids_follow_the_convention(
        reg: Registry, row: Routine, text: str) -> None:
    """Every ship step's id is `<prefix>_<provider>_<N>` — the row's prefix,
    the provider the registry routes link N to, and N. One naming for every
    routine's walk, so an outcome expression, a gate or a summary reads the
    same in any workflow and a step id says which link it is. Factored out
    so the negative control can run it against tampered text."""
    workflow = row.workflow
    links = {link.position: link for link in reg.resolve(row.chain)}
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    assert steps, f"no claude-code-action ship step found in {workflow}'s `{row.job}` job"
    for step in steps:
        assert step["link"] in links, (
            f"{workflow}: a ship step references link{step['link']}_model, "
            f"which the `{row.chain}` chain does not have")
        want = f"{row.prefix}_{links[step['link']].provider}_{step['link']}"
        assert step["id"] == want, (
            f"{workflow}: the link-{step['link']} ship step is id "
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
    links = reg.resolve(chain_id)
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    by_link = {step["link"]: step for step in steps}
    for n in range(1, len(links) + 1):
        assert n in by_link, (
            f"{workflow}: the `{chain_id}` chain has a link {n} but no ship "
            "step references it — a registry edit landed without its "
            "workflow half (the walk stops early)")
    for n in range(2, len(links) + 1):
        for earlier in range(1, n):
            needle = f"steps.{by_link[earlier]['id']}.outcome != 'success'"
            assert needle in by_link[n]["chunk"], (
                f"{workflow}: the link-{n} step is not gated on {needle} — "
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
    links = reg.resolve(row.chain)
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    by_link = {step["link"]: step for step in steps}
    for link in links:
        step = by_link[link.position]
        assert step["gates_on_key"], (
            f"{workflow}: the link-{link.position} ship step does not gate on "
            "key_present == '1' — an absent provider key would not skip it")
        assert step["key_gate_providers"] == {link.provider}, (
            f"{workflow}: the link-{link.position} ship step gates on the key "
            f"of {sorted(step['key_gate_providers'])} but the registry routes "
            f"that link to {link.provider!r} — it must gate on "
            f"steps.policy.outputs.{link.provider}_key_present == '1' and "
            "nothing else")


def test_routine_run_steps_gate_on_their_providers_key_presence():
    reg = Registry.load(str(REGISTRY))
    for row in ROUTINES.values():
        text = _routine_text(row.workflow)
        _assert_routine_steps_gate_on_their_providers_key(reg, row, text)
        # The secret-absent notice survives (the #326 skip, reworded for
        # #544: it fires only when NO provider in the chain has a key).
        assert _NO_KEY_NOTICE in _routine_job_text(text, row), (
            f"{row.workflow}: the no-key-for-any-provider ::notice:: is gone — "
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


def _step_condition(chunk: str) -> str:
    """A step chunk's `if:` body, one line — the folded `if: >-` form the
    routines use, or a one-line `if: <expr>`."""
    m = re.search(
        r"^[ \t]*if: >-\n((?:[ \t]+.*\n)+?)(?=[ \t]*[a-z_-]+:)", chunk, re.MULTILINE)
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
    links = reg.resolve(row.chain)
    ids = _walk_step_ids(_routine_ship_steps(job_text, row.resolve_id))
    assert len(ids) == len(links), (
        f"{row.workflow}: the `{row.chain}` chain has {len(links)} links but "
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
    _PROVIDER_UNDER_TEST = _routine_provider(row.conf)
    job = _routine_job_text(text, row)
    walk_ids = _routine_walk_ids(reg, row, job)
    exprs = _outcome_expressions(job)
    assert exprs, (
        f"{workflow}: no AGENT_OUTCOME/RUN/SHIP expression found in the "
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
                        f"{workflow}: {var} evaluated to {got!r} with link "
                        f"outcomes {outcomes} — a link succeeded but the "
                        "walk's outcome is not success; the expression does "
                        "not cover every link of the walk")
                else:
                    assert got != "success", (
                        f"{workflow}: {var} read {got!r} with no link having "
                        f"succeeded ({state}) — the walk claims a success "
                        "nobody produced")
                    ran = [o for o in state if o != "skipped"]
                    want = ran[-1] if ran else "skipped"
                    assert got == want, (
                        f"{workflow}: {var} read {got!r} with link outcomes "
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
    _PROVIDER_UNDER_TEST = _routine_provider(row.conf)
    job = _routine_job_text(text, row)
    walk_ids = _routine_walk_ids(reg, row, job)
    cond = _gate_condition(job, step_name, workflow)
    # Drop the legs the simulation fixes green (policy/enabled/select/
    # key/dry_run) and the leading always(), leaving the outcome clause.
    sim_cond = _strip_fixed_green_legs(cond)
    # The surviving clause is `(walk-success test) != 'success'`.
    mm = re.match(r"^\((.+)\)\s*!=\s*'success'\s*$", sim_cond.strip())
    assert mm, (
        f"{workflow}: the '{step_name}' condition's outcome clause does not "
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
            f"{workflow}: the '{step_name}' walk clause must reduce to a "
            f"string outcome, so `!= 'success'` is a string compare rather "
            f"than an always-true bool-vs-string: {inner!r} → {walk!r}")
        fired = walk != "success"
        any_success = "success" in state
        assert fired == (not any_success), (
            f"{workflow}: the '{step_name}' gate fired={fired} under link "
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
    links = {link.position: link for link in reg.resolve(row.chain)}
    head_provider = links[1].provider
    head, tail = 0, 0
    for step in _routine_ship_steps(job_text, row.resolve_id):
        m = re.search(r"^\s*timeout-minutes: (\d+)$", step["chunk"], re.MULTILINE)
        assert m, (
            f"{row.workflow}: the link-{step['link']} ship step carries no "
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
    job_text = _routine_job_text(text, row)
    job = _routine_job_timeout(job_text, workflow)
    head, tail = _routine_step_timeouts(reg, row, job_text)
    assert job <= _PLATFORM_JOB_CAP_MINUTES, (
        f"{workflow}: job timeout-minutes {job} exceeds GitHub's "
        f"{_PLATFORM_JOB_CAP_MINUTES}-minute hosted-job cap — the platform clamps "
        "it, so the budget the comment claims is fiction and a stalled head "
        "link lets the platform kill the fallback link (and the lock cleanup) "
        "mid-walk")
    need = head + tail + _JOB_BUDGET_HEADROOM_MINUTES
    assert job >= need, (
        f"{workflow}: job timeout-minutes {job} does not budget one stalled head "
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
# triage wiring on each job's OWN chain. What stays explicit here is the
# forge's own invariant, which no generic pin states: EVERY walk step of
# each half — the tail included, which runs only on the fall-through path —
# carries ITS OWN deny backstop and dontAsk, never the other half's. The
# sign-off can apply `autonomy-ok`, so a quietly-shed backstop there is the
# worst drift in the family, and a step carrying the other half's backstop
# would collapse the proposer/judge separation the forge is built on
# (scripts/wright-perms-check.sh holds the file side of that split). Plus
# the degraded path in its any-provider form.

# ROUTINES row → the half's OWN deny backstop every walk step must carry.
WRIGHT_BACKSTOPS = {
    "wright-propose": ".claude/wright-settings.json",
    "wright-signoff": ".claude/reeve-signoff-settings.json",
}


def _assert_wright_half_carries_its_own_backstop(
        row: Routine, backstop: str, text: str) -> None:
    """Every walk step of one half runs under dontAsk with that half's own
    backstop — and NOT the other half's. Factored out so the negative
    control can run it against tampered text."""
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    assert steps, (
        f"no claude-code-action ship step found in {row.workflow}'s `{row.job}` job")
    others = [b for b in WRIGHT_BACKSTOPS.values() if b != backstop]
    for step in steps:
        where = f"wright {row.job} link-{step['link']} ship step"
        assert "--permission-mode dontAsk" in step["chunk"], (
            f"{where}: no longer runs under --permission-mode dontAsk")
        assert f"--settings {backstop}" in step["chunk"], (
            f"{where}: no longer carries its half's deny backstop "
            f"(--settings {backstop})")
        for other in others:
            assert f"--settings {other}" not in step["chunk"], (
                f"{where}: carries the OTHER half's deny backstop "
                f"(--settings {other}) — the proposer/judge separation is gone")


def test_wright_walk_steps_carry_their_halfs_backstop():
    for name, backstop in WRIGHT_BACKSTOPS.items():
        row = ROUTINES[name]
        _assert_wright_half_carries_its_own_backstop(
            row, backstop, _routine_text(row.workflow))


def test_wright_backstop_guard_rejects_a_tail_step_on_the_other_halfs_backstop():
    # NEGATIVE CONTROL: the sign-off's terminal tail step rewired to the
    # PROPOSER's backstop — the cross-half drift, on the fall-through path —
    # must fail. Derived from the live step, not a hand-copied literal.
    row = ROUTINES["wright-signoff"]
    text = _routine_text(row.workflow)
    steps = _routine_ship_steps(_routine_job_text(text, row), row.resolve_id)
    chunk = max(steps, key=lambda s: s["link"])["chunk"]
    own = WRIGHT_BACKSTOPS["wright-signoff"]
    other = WRIGHT_BACKSTOPS["wright-propose"]
    assert f"--settings {own}" in chunk, "tamper target not found — the fixture is stale"
    tampered = text.replace(
        chunk, chunk.replace(f"--settings {own}", f"--settings {other}", 1), 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="deny backstop"):
        _assert_wright_half_carries_its_own_backstop(row, own, tampered)


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
# rule, the triage wiring — and never the report or observe jobs. What
# stays explicit here, each with a negative control: the job split itself;
# the #442 containment surface on EVERY walk step (the tail included — a
# step that shed it would do so only on the fall-through path); the #443
# keyed-and-skippable degraded path in its any-provider form; and the
# report job's keylessness.

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


def _assert_reeve_greenlight_walk_keeps_the_containment_surface(text: str) -> None:
    """The #442 containment surface on every walk step, which must not be
    quietly shed: dontAsk, the loop's OWN deny backstop (never a sibling's),
    the wrapper as the ONLY Bash allow plus the read-only file tools, no MCP
    server (the wrapper is both the read and the write surface), and the
    committed skill as the prompt — never an inline one that bypasses it.
    Factored out so the negative control can run it against tampered text."""
    for step in _reeve_walk_steps(text):
        where = f"reeve greenlight link-{step['link']} ship step"
        chunk = step["chunk"]
        assert "--permission-mode dontAsk" in chunk, (
            f"{where}: no longer runs under --permission-mode dontAsk")
        assert f"--settings {REEVE_BACKSTOP}" in chunk, (
            f"{where}: no longer carries the deny backstop "
            f"(--settings {REEVE_BACKSTOP})")
        assert f"Bash({REEVE_WRAPPER}:*)" in chunk, (
            f"{where}: no longer allows the greenlight wrapper — the agent's "
            "only shell surface")
        assert "Read,Grep,Glob" in chunk, (
            f"{where}: dropped the read-only file tools the charter grounding "
            "(repo-root PM.md) depends on")
        assert "mcp__" not in chunk and "--mcp-config" not in chunk, (
            f"{where}: allows an MCP server — the loop's write surface is the "
            "wrapper, and no server exists to allow")
        assert "prompt: /reeve-greenlight" in chunk, (
            f"{where}: no longer invokes the committed /reeve-greenlight skill "
            "— an inline prompt would bypass it")


def test_reeve_greenlight_walk_steps_keep_the_containment_surface():
    _assert_reeve_greenlight_walk_keeps_the_containment_surface(_reeve_text())


def test_reeve_containment_guard_rejects_a_tail_step_that_sheds_the_backstop():
    # NEGATIVE CONTROL: strip the deny backstop from the terminal tail step
    # — the one that runs only after every earlier link failed, unwatched —
    # and require the containment pin to FAIL. Anchored inside the live step
    # (the Oracle control's pattern), never the file's first occurrence.
    text = _reeve_text()
    chunk = max(_reeve_walk_steps(text), key=lambda s: s["link"])["chunk"]
    needle = f"--settings {REEVE_BACKSTOP} "
    assert needle in chunk, "tamper target not found — the fixture is stale"
    tampered = text.replace(chunk, chunk.replace(needle, "", 1), 1)
    with pytest.raises(AssertionError, match="deny backstop"):
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
