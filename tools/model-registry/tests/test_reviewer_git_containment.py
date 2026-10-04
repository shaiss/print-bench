"""Drift guard: the reviewers' git containment in auto-review.yml (code-scanning
finding on #760).

A deny list cannot contain git — `git fetch origin --upload-pack=<cmd> .` runs
<cmd> over the local file transport whatever prefix rules say, a PR-committed
bare-repository layout carries its own exec keys, and gh spawns git. So the
containment is structural, in two halves:

* the FILE half (``scripts/reviewer-perms-check.sh``): Jane / Drik / PM triage
  deny ``Bash(git:*)`` outright; the coach keeps checkout/add/commit/push and
  denies everything else;
* the WORKFLOW half, pinned here:
  - every reviewer and coach ship step — every chain link, every provider —
    runs under the git ENVIRONMENT lock (``GIT_ALLOW_PROTOCOL=https`` plus
    command-scope ``safe.bareRepository=explicit``, ``core.fsmonitor=false``,
    ``core.hooksPath=/dev/null``, ``core.pager=cat`` via ``GIT_CONFIG_COUNT``),
    computed as the step's EFFECTIVE env (job env, then the step's own, the
    step winning) so a single link that overrides or sheds it fails;
  - Jane's, Drik's and the PM triage jobs check out ``pull_request.base.ref``
    (the posting MCP / settings / skills are never the PR's copy — pm-triage
    joined the posting surface in #772, so it joins this boundary) at
    ``fetch-depth: 0``, then a TRUSTED step fetches the PR head SHA
    (Oracle extraheader auth) and overlays the changed design directories
    before any agent step;
  - the coach's checkout is full history (it no longer fetches).

Every pin has a tamper negative control below, derived from the live
workflow text, proving it can fail.
"""

from __future__ import annotations

import re

import pytest

from test_reviewer_backstop_wiring import BACKSTOPS, _ship_chunks
from test_workflow_drift import _job_blocks, _without_comments, _workflow_text

# The lock every reviewer/coach ship step must run under.
PROTOCOL = "https"
CONFIG_LOCK = {
    "safe.bareRepository": "explicit",
    "core.fsmonitor": "false",
    "core.hooksPath": "/dev/null",
    "core.pager": "cat",
}
# The jobs whose reviewer has no git and reviews the PR head's geometry.
STAGED_JOBS = ("jane-review", "drik-review", "pm-triage")
STAGE_MARKER = 'git checkout "$HEAD_SHA" -- "designs/${d}"'
HEAD_FETCH = 'fetch --no-tags origin "$HEAD_SHA"'
BASE_REF = "${{ github.event.pull_request.base.ref }}"


def _steps(block: str) -> list[str]:
    """The job's step chunks, in order (the 6-space `- ` list)."""
    return re.split(r"\n      - ", block)[1:]


def _env_map(text: str, indent: int) -> dict[str, str]:
    """The `env:` mapping opened at exactly `indent` spaces in `text` (the
    first one), as {key: unquoted value}. Comment lines are skipped."""
    lines = text.splitlines()
    head = " " * indent + "env:"
    out: dict[str, str] = {}
    for i, line in enumerate(lines):
        if line.rstrip() != head:
            continue
        for nxt in lines[i + 1:]:
            if nxt.lstrip().startswith("#") or not nxt.strip():
                continue
            if len(nxt) - len(nxt.lstrip()) <= indent:
                break
            m = re.match(r"^\s+([A-Za-z_][A-Za-z0-9_]*):\s*(.*?)\s*$", nxt)
            if m:
                out[m.group(1)] = m.group(2).strip("'\"")
        break
    return out


def _effective_env(job_block: str, step_chunk: str) -> dict[str, str]:
    env = _env_map(re.split(r"\n      - ", job_block)[0], 4)
    env.update(_env_map(step_chunk, 8))
    return env


def _lock_errors(env: dict[str, str]) -> list[str]:
    errs = []
    if env.get("GIT_ALLOW_PROTOCOL") != PROTOCOL:
        errs.append(f"GIT_ALLOW_PROTOCOL is {env.get('GIT_ALLOW_PROTOCOL')!r}, "
                    f"not {PROTOCOL!r}")
    try:
        count = int(env.get("GIT_CONFIG_COUNT", ""))
    except ValueError:
        return errs + [f"GIT_CONFIG_COUNT is {env.get('GIT_CONFIG_COUNT')!r}"]
    pairs: dict[str, str] = {}
    for i in range(count):
        key, value = env.get(f"GIT_CONFIG_KEY_{i}"), env.get(f"GIT_CONFIG_VALUE_{i}")
        if key is None or value is None:
            errs.append(f"GIT_CONFIG_KEY_{i}/GIT_CONFIG_VALUE_{i} missing under "
                        f"GIT_CONFIG_COUNT={count}")
            continue
        pairs[key] = value  # later entries win, as in git
    for key, want in CONFIG_LOCK.items():
        if pairs.get(key) != want:
            errs.append(f"command-scope {key} is {pairs.get(key)!r}, not {want!r}")
    return errs


def _assert_every_ship_step_is_git_locked(text: str) -> None:
    blocks = _job_blocks(text)
    for job in BACKSTOPS:
        block = _without_comments(blocks[job])
        chunks = _ship_chunks(block)
        assert chunks, f"auto-review.yml [{job}]: no ship step found"
        for n, chunk in enumerate(chunks, 1):
            errs = _lock_errors(_effective_env(block, chunk))
            assert not errs, (
                f"auto-review.yml [{job}] ship step {n} runs without the git "
                f"environment lock — {'; '.join(errs)} — so a subcommand option "
                f"(--upload-pack) or a committed bare repo can run a command")


def _checkout_depth(block: str) -> int | None:
    first = _steps(block)[0]
    assert "uses: actions/checkout" in first, "first step is not the checkout"
    m = re.search(r"^\s+fetch-depth:\s*(\d+)", first, re.MULTILINE)
    return int(m.group(1)) if m else None


def _checkout_ref(block: str) -> str | None:
    first = _steps(block)[0]
    assert "uses: actions/checkout" in first, "first step is not the checkout"
    m = re.search(r"^\s+ref:\s*(.+)$", first, re.MULTILINE)
    return m.group(1).strip() if m else None


def _assert_head_is_staged_before_the_agent(text: str) -> None:
    blocks = _job_blocks(text)
    for job in STAGED_JOBS:
        block = _without_comments(blocks[job])
        steps = _steps(block)
        ship_at = next(i for i, c in enumerate(steps)
                       if "uses: anthropics/claude-code-action" in c)
        stage_at = [i for i, c in enumerate(steps) if STAGE_MARKER in c]
        assert stage_at, (
            f"auto-review.yml [{job}] has no trusted step staging the PR head's "
            f"design directories — the reviewer has no git to do it")
        assert stage_at[0] < ship_at, (
            f"auto-review.yml [{job}] stages the PR head AFTER an agent step — "
            f"the review would read the merge checkout, not the head")
        stage = steps[stage_at[0]]
        assert "uses:" not in stage.split("run:", 1)[0], "staging step is not a run step"
        env = _env_map(stage, 8)
        assert env.get("HEAD_SHA") == "${{ github.event.pull_request.head.sha }}", (
            f"auto-review.yml [{job}] staging step does not take the PR head sha")
        assert env.get("CHANGED_DESIGNS") == (
            "${{ needs.design-changes.outputs.changed_designs }}"), (
            f"auto-review.yml [{job}] staging step does not take the changed designs")
        assert env.get("GH_TOKEN") == "${{ github.token }}", (
            f"auto-review.yml [{job}] staging step has no job token for the "
            f"authenticated head fetch (a private-repo anonymous fetch 403s)")
        run = stage.split("run:", 1)[1]
        assert "${{" not in run, (
            f"auto-review.yml [{job}] staging step interpolates an expression into "
            f"its script — PR-controlled values must arrive through env")
        assert "set -f" in run and "[A-Za-z0-9._-]" in run, (
            f"auto-review.yml [{job}] staging step no longer refuses to glob or "
            f"validate the PR-controlled design names")
        assert HEAD_FETCH in run, (
            f"auto-review.yml [{job}] staging step does not fetch the PR head "
            f"SHA — the base checkout cannot already hold it")
        depth = _checkout_depth(block)
        assert depth == 0, (
            f"auto-review.yml [{job}] checks out at fetch-depth {depth}: the "
            f"base-branch checkout must be full history (Oracle's pattern)")
        assert _checkout_ref(block) == BASE_REF, (
            f"auto-review.yml [{job}] checkout ref is {_checkout_ref(block)!r}, "
            f"not base.ref — the posting MCP would be the PR's copy")


def _assert_coach_checks_out_full_history(text: str) -> None:
    block = _without_comments(_job_blocks(text)["design-coach"])
    assert _checkout_depth(block) == 0, (
        "auto-review.yml [design-coach] checkout is not full history — the "
        "coach's backstop denies git fetch, so the PR branch must be local")


def test_every_reviewer_ship_step_runs_under_the_git_lock():
    _assert_every_ship_step_is_git_locked(_workflow_text())


def test_jane_drik_and_pm_get_the_head_staged_by_a_trusted_step():
    _assert_head_is_staged_before_the_agent(_workflow_text())


def test_coach_checks_out_full_history():
    _assert_coach_checks_out_full_history(_workflow_text())


# ── negative controls ─────────────────────────────────────────────────────────

def _job_replace(text: str, job: str, old: str, new: str) -> str:
    block = _job_blocks(text)[job]
    assert old in block, "tamper target not found — the fixture is stale"
    tampered = text.replace(block, block.replace(old, new, 1), 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    return tampered


def _step_replace(text: str, job: str, step: int, old: str, new: str) -> str:
    chunk = _ship_chunks(_job_blocks(text)[job])[step]
    assert old in chunk, "tamper target not found — the fixture is stale"
    tampered = text.replace(chunk, chunk.replace(old, new, 1), 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    return tampered


@pytest.mark.parametrize("job,old,new", [
    # A job sheds the protocol lock: every one of its links can --upload-pack.
    ("pm-triage", "      GIT_ALLOW_PROTOCOL: https\n", ""),
    # The count shrinks and silently drops core.pager.
    ("design-coach", 'GIT_CONFIG_COUNT: "4"', 'GIT_CONFIG_COUNT: "3"'),
    # A value is weakened: hooks run again.
    ("jane-review", "GIT_CONFIG_VALUE_2: /dev/null", "GIT_CONFIG_VALUE_2: .githooks"),
    # Bare-repository discovery re-enabled.
    ("drik-review", "GIT_CONFIG_VALUE_0: explicit", "GIT_CONFIG_VALUE_0: all"),
])
def test_lock_guard_rejects_a_tampered_job_env(job, old, new):
    tampered = _job_replace(_workflow_text(), job, old, new)
    with pytest.raises(AssertionError, match="git environment lock"):
        _assert_every_ship_step_is_git_locked(tampered)


def test_lock_guard_rejects_one_link_overriding_the_protocol():
    # NEGATIVE CONTROL: a single Z.AI link (which has its own env block)
    # re-allows the file transport — the job env is intact, the step wins.
    tampered = _step_replace(
        _workflow_text(), "jane-review", 0,
        "          API_TIMEOUT_MS:", "          GIT_ALLOW_PROTOCOL: file:https\n"
        "          API_TIMEOUT_MS:")
    with pytest.raises(AssertionError, match="ship step 1 runs without"):
        _assert_every_ship_step_is_git_locked(tampered)


def test_lock_guard_rejects_the_tail_link_shedding_its_config():
    # NEGATIVE CONTROL: the terminal Anthropic link (no env block of its own,
    # seen only on full fall-through) gains one that zeroes the config count.
    tampered = _step_replace(
        _workflow_text(), "design-coach", -1,
        "        with:\n", '        env:\n          GIT_CONFIG_COUNT: "0"\n        with:\n')
    with pytest.raises(AssertionError, match="ship step 6 runs without"):
        _assert_every_ship_step_is_git_locked(tampered)


def _stage_chunk(text: str, job: str) -> str:
    return next(c for c in _steps(_job_blocks(text)[job]) if STAGE_MARKER in c)


def test_stage_guard_rejects_a_job_without_the_staging_step():
    text = _workflow_text()
    stage = _stage_chunk(text, "drik-review")
    tampered = text.replace("\n      - " + stage, "", 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="no trusted step staging"):
        _assert_head_is_staged_before_the_agent(tampered)


def test_stage_guard_rejects_staging_after_the_agent():
    text = _workflow_text()
    block = _job_blocks(text)["jane-review"]
    stage = _stage_chunk(text, "jane-review")
    first_ship = _ship_chunks(block)[0]
    moved = block.replace("\n      - " + stage, "", 1).replace(
        first_ship, first_ship + "\n      - " + stage, 1)
    tampered = text.replace(block, moved, 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="AFTER an agent step"):
        _assert_head_is_staged_before_the_agent(tampered)


def test_stage_guard_rejects_a_shallow_checkout():
    tampered = _job_replace(_workflow_text(), "jane-review",
                            "          fetch-depth: 0\n", "")
    with pytest.raises(AssertionError, match="fetch-depth"):
        _assert_head_is_staged_before_the_agent(tampered)


def test_stage_guard_rejects_a_merge_ref_checkout():
    tampered = _job_replace(_workflow_text(), "drik-review",
                            "          ref: ${{ github.event.pull_request.base.ref }}\n",
                            "")
    with pytest.raises(AssertionError, match="base.ref"):
        _assert_head_is_staged_before_the_agent(tampered)


def test_stage_guard_rejects_staging_without_fetching_head():
    tampered = _job_replace(
        _workflow_text(), "jane-review",
        '            fetch --no-tags origin "$HEAD_SHA"\n',
        "")
    with pytest.raises(AssertionError, match="does not fetch the PR head"):
        _assert_head_is_staged_before_the_agent(tampered)


def test_stage_guard_rejects_an_interpolated_script():
    tampered = _job_replace(
        _workflow_text(), "drik-review", "for d in $CHANGED_DESIGNS; do",
        "for d in ${{ needs.design-changes.outputs.changed_designs }}; do")
    with pytest.raises(AssertionError, match="interpolates an expression"):
        _assert_head_is_staged_before_the_agent(tampered)


def test_stage_guard_rejects_a_globbing_script():
    tampered = _job_replace(_workflow_text(), "jane-review", "          set -f", "")
    with pytest.raises(AssertionError, match="glob"):
        _assert_head_is_staged_before_the_agent(tampered)


def test_coach_guard_rejects_a_shallow_checkout():
    tampered = _job_replace(_workflow_text(), "design-coach",
                            "          fetch-depth: 0\n", "")
    with pytest.raises(AssertionError, match="full history"):
        _assert_coach_checks_out_full_history(tampered)
