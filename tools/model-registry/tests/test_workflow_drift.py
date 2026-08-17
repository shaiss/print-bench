"""Drift guard: the committed registry and auto-review.yml cannot silently diverge.

auto-review.yml only runs on design PRs, so this PR's CI does not live-exercise the
migrated review pipeline. This test is the standing proof that the registry drives
the workflow and stays consistent with it.

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
REGISTRY = REPO_ROOT / ".github" / "models" / "registry.conf"

# The three reviewer jobs that carry the fallback chain. Each has one ship step
# per registry link, in chain order.
REVIEWER_JOBS = ("jane-review", "drik-review", "design-coach")

# A top-level job header: a 2-space-indented `name:` with no inline value. Only
# valid inside the `jobs:` section (elsewhere — e.g. `on:` → `pull_request:` — a
# 2-space bare key is not a job), so callers slice from `jobs:` first.
_JOB_HEADER = re.compile(r"^  ([a-z][a-z0-9-]*):[ \t]*$", re.MULTILINE)


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _job_blocks(text: str) -> dict[str, str]:
    """Map each job name to its text block (header to the next job / EOF)."""
    jobs_at = re.search(r"^jobs:[ \t]*$", text, re.MULTILINE)
    assert jobs_at, "auto-review.yml has no `jobs:` section"
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
    # prefixes an allow-list would know about.
    text = _workflow_text()
    literals = [tok for tok in re.findall(r"--model\s+(\S+)", text)
                if not tok.startswith("${{")]
    assert not literals, f"hardcoded --model literal(s) in auto-review.yml: {literals}"
