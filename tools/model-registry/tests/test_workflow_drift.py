"""Drift guard: the committed registry and the workflows that consume it cannot
silently diverge.

auto-review.yml only runs on design PRs, and the four #297 routines are scheduled
jobs that never run in a PR's own CI — so nothing live-exercises the migrated
pipelines there. This test is the standing proof that the registry drives each
workflow and stays consistent with it.

The load-bearing check parses each workflow's ordered claude-code-action steps and
asserts, **position for position, derived from `Registry.resolve(<chain>)`**:

* the step at slot k sources `--model … <model-ref for slot k>` — the slot→model
  binding, so a scrambled reference (slot 1 pulling `model4`) is caught, not just
  the count;
* the step's literal `anthropic_api_key: secrets.<X>` is the registry link's secret
  at that position — so slots 1–3 wire `ZAI_KEY`, slot 4 `ANTHROPIC_API_KEY`, and
  swapping one is caught;
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

Two shapes are guarded, matching the two workflow structures:

* **per-link steps** (auto-review.yml): one ship step per chain link, the model
  ref an output of a *needs*-dependency job (`needs.design-changes.outputs.model{k}`).
* **walk-steps** (the four #297 routines: design-run, backlog-burn, chunker,
  labeler): one continue-on-error step per chain link inside the SAME job, the
  model ref a *step* output (`steps.chain.outputs.link{k}_model`), each gated on
  the earlier links having failed — the chain walk itself. For these the test also
  proves the walk (AC2 of #297) and the whole-chain-failure gate.
"""

from __future__ import annotations

import pathlib
import re

from model_registry.registry import Registry

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
REGISTRY = REPO_ROOT / ".github" / "models" / "registry.conf"

# The three reviewer jobs that carry the fallback chain. Each has one ship step
# per registry link, in chain order.
REVIEWER_JOBS = ("jane-review", "drik-review", "design-coach")

# The #297 walk-step workflows: (workflow file, chain id, the job that carries the
# walk, the step id of the resolve step). Each has one continue-on-error step per
# chain link plus a whole-chain-failure gate.
WALK_WORKFLOWS = [
    ("design-run.yml", "design-run", "run", "chain"),
    ("backlog-burn.yml", "ship", "burn", "chain"),
    ("chunker.yml", "ship", "chunk", "chain"),
    ("labeler.yml", "labeler", "label", "chain"),
]

# A top-level job header: a 2-space-indented `name:` with no inline value. Only
# valid inside the `jobs:` section (elsewhere — e.g. `on:` → `pull_request:` — a
# 2-space bare key is not a job), so callers slice from `jobs:` first.
_JOB_HEADER = re.compile(r"^  ([a-z][a-z0-9-]*):[ \t]*$", re.MULTILINE)


def _workflow_text() -> str:
    return (WORKFLOWS / "auto-review.yml").read_text(encoding="utf-8")


def _job_blocks(text: str) -> dict[str, str]:
    """Map each job name to its text block (header to the next job / EOF)."""
    jobs_at = re.search(r"^jobs:[ \t]*$", text, re.MULTILINE)
    assert jobs_at, "the workflow has no `jobs:` section"
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
    endpoint in any of the three jobs fails, and nothing is restated as a constant.
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
    # prefixes an allow-list would know about. Covers auto-review.yml AND the
    # four #297 walk-step workflows.
    for fname in ["auto-review.yml"] + [w[0] for w in WALK_WORKFLOWS]:
        text = (WORKFLOWS / fname).read_text(encoding="utf-8")
        literals = [tok for tok in re.findall(r"--model\s+(\S+)", text)
                    if not tok.startswith("${{")]
        assert not literals, f"hardcoded --model literal(s) in {fname}: {literals}"


# ── The #297 walk-step workflows ─────────────────────────────────────────────
#
# These differ from auto-review.yml in structure: the chain links are
# continue-on-error steps INSIDE one job, each reading the resolve step's
# linkN_model output directly, each gated on the earlier links having failed.
# The guard therefore also proves the WALK (AC2) and the secret-absent skip
# (AC3), which the per-link shape gets for free from its job-level `if:`.


def _walk_text(fname: str) -> str:
    return (WORKFLOWS / fname).read_text(encoding="utf-8")


def _walk_steps(job_text: str) -> list[dict]:
    """The job's claude-code-action steps in order, as parsed wiring.

    Mirrors _ship_steps but for the walk shape: the model ref is the resolve
    step's own output (`steps.chain.outputs.linkN_model`), and each step's
    full `if:` condition and id are captured so the walk itself can be
    asserted. A step may carry a `registry-secret-alias: <NAME>` comment
    marking an explicit in-file alias for the registry's provider secret
    (design-run.yml's CLAUDE_KEY for ANTHROPIC_API_KEY) — recorded as
    `secret_alias`, checked against the registry only when absent.
    """
    steps: list[dict] = []
    for chunk in re.split(r"\n      - ", job_text):
        if "uses: anthropics/claude-code-action" not in chunk:
            continue
        model = re.search(
            r"--model \$\{\{ steps\.chain\.outputs\.link(\d+)_model \}\}", chunk)
        secret = re.search(r"anthropic_api_key: \$\{\{ secrets\.(\w+) \}\}", chunk)
        alias = re.search(r"registry-secret-alias:.*", chunk)
        base = re.search(r"ANTHROPIC_BASE_URL: (\S+)", chunk)
        cont = re.search(r"continue-on-error:\s*true", chunk)
        cond = re.search(r"if: >-\n((?:          .+\n)+)", chunk)
        sid = re.search(r"\n        id: (\w+)\n", "\n" + chunk.split("\n", 1)[1] + "\n")
        steps.append({
            "id": sid.group(1) if sid else None,
            "link": int(model.group(1)) if model else None,
            "secret": secret.group(1) if secret else None,
            "secret_alias": bool(alias),
            "base_url": base.group(1) if base else "",
            "continue_on_error": bool(cont),
            "if_condition": cond.group(1) if cond else "",
        })
    return steps


def test_walk_workflows_pin_every_link_to_the_registry():
    """Each #297 routine's walk steps match its chain, position for position.

    The core guard, extended to the walk shape: the step running chain link k
    must reference link{k}_model, wire the link's provider secret literally,
    carry the link's endpoint, and be continue-on-error (or a link dying fails
    the job instead of walking — the exact #297 bug).
    """
    for fname, chain_id, job_name, _resolve_id in WALK_WORKFLOWS:
        links = Registry.load(str(REGISTRY)).resolve(chain_id)
        assert links, f"the `{chain_id}` chain resolved to zero links"
        text = _walk_text(fname)
        blocks = _job_blocks(text)
        assert job_name in blocks, f"{fname} has no job {job_name!r}"
        steps = _walk_steps(blocks[job_name])
        assert len(steps) == len(links), (
            f"{fname}: {len(steps)} claude-code-action steps but the `{chain_id}` "
            f"chain has {len(links)} links — add/remove a step to match.")
        for link, step in zip(links, steps):
            assert step["link"] == link.position, (
                f"{fname} link {link.position}: references link{step['link']} "
                f"but must reference link{link.position} (the chain's order).")
            if not step["secret_alias"]:
                assert step["secret"] == link.secret, (
                    f"{fname} link {link.position}: wires secrets.{step['secret']} "
                    f"but the registry routes this position to "
                    f"secrets.{link.secret}.")
            assert step["base_url"] == link.base_url, (
                f"{fname} link {link.position}: ANTHROPIC_BASE_URL is "
                f"{step['base_url']!r} but the registry endpoint is "
                f"{link.base_url!r}.")
            assert step["continue_on_error"], (
                f"{fname} link {link.position}: not continue-on-error — a dead "
                f"link would fail the job instead of walking to the next (#297).")


def test_walk_workflows_resolve_their_chain():
    # Each routine must run the resolve step against ITS chain id (not another
    # routine's) and emit the outputs its steps read, or every link ref is empty.
    for fname, chain_id, job_name, resolve_id in WALK_WORKFLOWS:
        text = _walk_text(fname)
        assert f"model_registry resolve {chain_id}" in text, (
            f"{fname}: the resolve step no longer targets the `{chain_id}` chain")
        blocks = _job_blocks(text)
        steps = _walk_steps(blocks[job_name])
        for n in range(1, len(steps) + 1):
            assert f"link{n}_model" in text, (
                f"{fname}: the resolve output link{n}_model is never consumed")


def test_walk_workflows_actually_walk():
    """AC2 — a failed link falls through to the next rather than failing the job.

    Two gates make the walk, and each step after the first must carry the right
    one for its role:

    * a SAME-PROVIDER later link (a zai fallback after a zai link) gates on the
      previous step's outcome being 'failure' — strictly, so a success
      short-circuits and a skip (provider mismatch) does NOT count as walked;
    * a CROSS-PROVIDER step (the anthropic tail) gates on the previous step's
      outcome != 'success' PLUS an entry condition (the conf's provider picking
      it, or — in the tail's case — its own key's presence), because it is both
      the walk-back target AND a provider-conf entry point, and 'skipped'
      upstream steps must not block it.

    A dropped gate would run every link unconditionally (four attempts, four
    draft PRs); a wrong step id would silence a link forever.
    """
    for fname, chain_id, job_name, _resolve_id in WALK_WORKFLOWS:
        links = Registry.load(str(REGISTRY)).resolve(chain_id)
        steps = _walk_steps(_job_blocks(_walk_text(fname))[job_name])
        prev = None
        for link, step in zip(links, steps):
            step["provider"] = link.provider
            if prev is not None:
                ref = f"steps.{prev['id']}.outcome"
                if link.provider == prev["provider"]:
                    assert f"{ref} == 'failure'" in step["if_condition"], (
                        f"{fname} step {step['id']} (link {link.position}): its "
                        f"if: does not gate on {ref} == 'failure' — the chain "
                        f"walk is broken (later links must not run after a "
                        f"success).")
                else:
                    # `!= 'success'` or the strictly-stronger `== 'failure'`
                    # (with an entry-point alternative) both walk correctly.
                    walks = (f"{ref} != 'success'" in step["if_condition"]
                             or f"{ref} == 'failure'" in step["if_condition"])
                    assert walks, (
                        f"{fname} step {step['id']} (link {link.position}): its "
                        f"if: gates on neither {ref} != 'success' nor "
                        f"{ref} == 'failure' — the cross-provider walk-back "
                        f"would not fire when the upstream provider's links all "
                        f"died.")
            prev = step


def test_walk_workflows_gate_on_whole_chain_failure():
    # AC2's other half: only the WHOLE chain dying fails the job. Each routine
    # carries a terminal step that errors iff every SHIP step's outcome !=
    # 'success' — so a link that was skipped-for-a-reason-the-job-knows (no key,
    # dry run) can't leave the run "succeeding" while doing nothing.
    for fname, chain_id, job_name, _resolve_id in WALK_WORKFLOWS:
        blocks = _job_blocks(_walk_text(fname))
        gate = re.search(
            r"- name: Fail when every chain link failed\n((?:        .+\n)+)",
            blocks[job_name])
        assert gate, f"{fname}: no 'Fail when every chain link failed' step"
        for step in _walk_steps(blocks[job_name]):
            assert f"steps.{step['id']}.outcome != 'success'" in gate.group(1), (
                f"{fname}: the whole-chain gate does not cover ship step "
                f"{step['id']!r} — a dead link there fails silently (the run "
                f"'succeeds' doing nothing), the under-delivery direction of "
                f"#297.")


def test_walk_workflows_preserve_the_secret_absent_notice():
    """AC3 — the provider-secret-absent `::notice::` skip is preserved.

    The pre-#297 behavior: with the conf's provider key unset, the routine
    # selects, logs the pick, emits a ::notice:: naming the provider and the
    # secret, and exits cleanly. The chain walk must not lose that legibility.
    """
    for fname, chain_id, job_name, _resolve_id in WALK_WORKFLOWS:
        text = _walk_text(fname)
        notice = re.search(
            r"- name: Explain a skipped agentic run\n((?:        .+\n)+)", text)
        assert notice, f"{fname}: the 'Explain a skipped agentic run' step is gone"
        body = notice.group(1)
        assert "::notice::" in body, (
            f"{fname}: the skipped-run notice no longer emits a ::notice::")
        assert "key_present" in body, (
            f"{fname}: the notice no longer keys on key_present — it would fire "
            f"on every run, masking the real skip condition")
        # And the run steps still gate on key_present, so a missing key cannot
        # reach an agent step (which would fail on an empty secret).
        steps = _walk_steps(_job_blocks(text)[job_name])
        for step in steps:
            assert "key_present == '1'" in step["if_condition"], (
                f"{fname} link {step['link']}: the step no longer gates on "
                f"key_present — the secret-absent skip is broken (AC3).")
