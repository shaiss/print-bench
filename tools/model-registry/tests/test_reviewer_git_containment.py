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
  - Jane's, Drik's and pm-triage's jobs check out ``pull_request.base.ref`` (the
    posting MCP / settings / skills are never the PR's copy) at
    ``fetch-depth: 0``, then a TRUSTED step fetches the PR head SHA
    (Oracle extraheader auth) and overlays the changed design directories
    before any agent step;
    - the coach's checkout is full history (it no longer fetches) of the
    PR, not base.ref — it still git-pushes. A trusted step then overlays
    the posting surface from ``pull_request.base.sha`` immediately before
    each ship step so the MCP the action spawns is never the PR's copy
    (including after a failed earlier Write/Edit/Bash link). Coach ship
    steps must not set ``show_full_output`` (Jane/Drik keep the SDK log
    hidden).

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
# The jobs whose reviewer has no git and reviews the PR head's geometry
# from a base-branch checkout plus a trusted overlay (the posting MCP must
# not be the PR's copy).
STAGED_JOBS = ("jane-review", "drik-review", "pm-triage")
STAGE_MARKER = 'git checkout "$HEAD_SHA" -- "designs/${d}"'
HEAD_FETCH = 'fetch --no-tags origin "$HEAD_SHA"'
BASE_REF = "${{ github.event.pull_request.base.ref }}"
BASE_SHA = "${{ github.event.pull_request.base.sha }}"
COACH_RESTORE_MARKER = 'git checkout "$BASE_SHA" --'
COACH_POST_BLOB = '${BASE_SHA}:.claude/reviewer-post/reviewer_mcp.py'
COACH_RESTORE_PATHS = (
    ".claude/reviewer-post",
    ".claude/design-coach-settings.json",
    ".claude/skills/design-coach",
    "scripts/coach-lock-check.sh",
)
COACH_LOCK_CHECK_BLOB = "${BASE_SHA}:scripts/coach-lock-check.sh"
COACH_LOCK_CHECK_SHOW = (
    '/usr/bin/git show "${BASE_SHA}:scripts/coach-lock-check.sh"'
)


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
    assert _checkout_ref(block) != BASE_REF, (
        "auto-review.yml [design-coach] checks out base.ref — the coach "
        "must keep the PR branch local for git push; overlay the posting "
        "surface from base.sha instead")


def _assert_one_restore_step(restore: str, *, at: str) -> None:
    assert "uses:" not in restore.split("run:", 1)[0], (
        f"{at} is not a run step")
    env = _env_map(restore, 8)
    assert env.get("BASE_SHA") == BASE_SHA, (
        f"{at} does not take the PR base sha")
    for key in ("LD_PRELOAD", "BASH_ENV", "ENV"):
        assert env.get(key) == "", (
            f"{at} YAML env does not pin {key} to empty — GITHUB_ENV from "
            "a Bash-capable coach is applied at process start, before the "
            "in-script unset, so LD_PRELOAD maps at exec and BASH_ENV is "
            "sourced as bash starts")
    run = restore.split("run:", 1)[1]
    assert "${{" not in run, (
        f"{at} interpolates an expression into its script — PR-controlled "
        "values must arrive through env")
    assert "/usr/bin/git checkout" in run, (
        f"{at} does not invoke /usr/bin/git — a GITHUB_PATH write from an "
        "earlier Write/Edit/Bash link would run a stub git")
    assert 'export PATH="/usr/bin:/bin:/usr/local/bin"' in run, (
        f"{at} does not reset PATH — a GITHUB_PATH write would run a stub git")
    assert "unset PYTHONPATH" in run, (
        f"{at} does not drop PYTHONPATH — a GITHUB_ENV write would inject "
        "sitecustomize into a later python, and LD_PRELOAD would hijack git")
    assert "GIT_ALLOW_PROTOCOL=https" in run, (
        f"{at} does not re-assert the git protocol lock after GITHUB_ENV")
    for path in COACH_RESTORE_PATHS:
        assert path in run, (
            f"{at} no longer overlays {path} from base.sha")


def _assert_coach_restores_posting_surface_from_base(text: str) -> None:
    """The coach cannot checkout base wholesale (it git-pushes the PR).
    The posting MCP / settings / skill are overlaid from base.sha by a
    trusted step immediately before EACH ship step (a failed first link
    with Write/Edit/Bash must not leave a rewritten MCP for the next
    spawn), and ship steps are gated on that surface existing on the
    base (Jane's first-landing skip)."""
    block = _without_comments(_job_blocks(text)["design-coach"])
    steps = _steps(block)
    ship_at = [i for i, c in enumerate(steps)
               if "uses: anthropics/claude-code-action" in c]
    restore_at = [i for i, c in enumerate(steps) if COACH_RESTORE_MARKER in c]
    assert restore_at, (
        "auto-review.yml [design-coach] has no trusted step restoring the "
        "posting surface from base.sha — the MCP would be the PR's copy")
    assert ship_at, "auto-review.yml [design-coach]: no ship step found"
    for n, idx in enumerate(ship_at, 1):
        assert idx > 0 and COACH_RESTORE_MARKER in steps[idx - 1], (
            f"auto-review.yml [design-coach] ship step {n} is not preceded "
            "by a trusted overlay of the posting surface from base.sha — "
            "a failed earlier link could rewrite the MCP the next spawn loads")
        _assert_one_restore_step(
            steps[idx - 1], at=f"auto-review.yml [design-coach] restore before ship {n}")
    ready_at = [i for i, c in enumerate(steps) if COACH_POST_BLOB in c]
    assert ready_at, (
        "auto-review.yml [design-coach] ready step no longer probes the "
        "posting MCP blob on base.sha — a working-tree check would accept "
        "the PR's copy")
    assert ready_at[0] < restore_at[0], (
        "auto-review.yml [design-coach] probes the base posting surface "
        "after restoring it")
    ready = steps[ready_at[0]]
    ready_env = _env_map(ready, 8)
    assert ready_env.get("BASE_SHA") == BASE_SHA, (
        "auto-review.yml [design-coach] ready step does not take the PR "
        "base sha")
    assert ready_env.get("GH_TOKEN") == "${{ github.token }}", (
        "auto-review.yml [design-coach] ready step has no job token for "
        "the authenticated base fetch (a private-repo anonymous fetch 403s)")
    ready_run = ready.split("run:", 1)[1]
    assert "${{" not in ready_run, (
        "auto-review.yml [design-coach] ready step interpolates an "
        "expression into its script")
    assert 'echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$GITHUB_OUTPUT"' in ready_run, (
        "auto-review.yml [design-coach] ready step does not record "
        "started_at — the lock-check cannot bound the pin to this run")
    assert 'fetch --no-tags origin "$BASE_SHA"' in ready_run, (
        "auto-review.yml [design-coach] ready step does not fetch the base "
        "SHA when it is not already local")
    assert COACH_LOCK_CHECK_BLOB in ready_run, (
        "auto-review.yml [design-coach] ready step no longer probes "
        "scripts/coach-lock-check.sh on base.sha — a missing-on-base first "
        "landing would spawn the agent then fail closed on git show, or a "
        "PR-committed stub would be the pin")
    for n, chunk in enumerate(_ship_chunks(block), 1):
        assert "steps.ready.outputs.ready" in chunk, (
            f"auto-review.yml [design-coach] ship step {n} is not gated on "
            "the base posting surface being present — a first landing "
            "would run the PR's copy")
        assert "show_full_output" not in chunk, (
            f"auto-review.yml [design-coach] ship step {n} sets "
            "show_full_output — Jane/Drik keep the SDK log hidden; full "
            "action logs are a live channel for transformed secrets")


def test_every_reviewer_ship_step_runs_under_the_git_lock():
    _assert_every_ship_step_is_git_locked(_workflow_text())


def test_jane_and_drik_get_the_head_staged_by_a_trusted_step():
    _assert_head_is_staged_before_the_agent(_workflow_text())


def test_coach_checks_out_full_history():
    _assert_coach_checks_out_full_history(_workflow_text())


def test_coach_restores_posting_surface_from_base():
    _assert_coach_restores_posting_surface_from_base(_workflow_text())


def _assert_coach_lock_check_runs_base_copy(text: str) -> None:
    """The completeness pin must not execute the workspace script.

    The coach has Write/Edit/Bash, so a prompt-injected turn (or a design
    PR that commits a stub) can rewrite ``scripts/coach-lock-check.sh``
    after the overlay. The check step extracts the blob from base.sha
    AFTER every ship step and runs that copy under a reset PATH.
    """
    block = _without_comments(_job_blocks(text)["design-coach"])
    steps = _steps(block)
    last_ship = max(i for i, c in enumerate(steps)
                    if "uses: anthropics/claude-code-action" in c)
    show_at = [i for i, c in enumerate(steps) if COACH_LOCK_CHECK_SHOW in c]
    assert show_at, (
        "auto-review.yml [design-coach] does not extract "
        "coach-lock-check.sh from base.sha — a workspace copy the agent "
        "can rewrite would stamp the round complete (issue #806)")
    assert show_at[0] > last_ship, (
        "auto-review.yml [design-coach] extracts coach-lock-check.sh "
        "BEFORE a ship step — the agent could rewrite the temp copy")
    check = steps[show_at[0]]
    assert "uses:" not in check.split("run:", 1)[0], (
        "lock-check step is not a run step")
    env = _env_map(check, 8)
    assert env.get("BASE_SHA") == BASE_SHA, (
        "auto-review.yml [design-coach] lock-check step does not take "
        "the PR base sha")
    assert env.get("PR") == "${{ github.event.pull_request.number }}", (
        "auto-review.yml [design-coach] lock-check step does not take "
        "the PR number through env")
    assert env.get("COACH_LOCK_SINCE") == (
        "${{ steps.ready.outputs.started_at }}"), (
        "auto-review.yml [design-coach] lock-check step does not take "
        "the ready step's started_at — a COACH-LOCK from an earlier coach "
        "run would stamp a denial-only reopened/ready_for_review turn")
    for key in ("LD_PRELOAD", "BASH_ENV", "ENV"):
        assert env.get(key) == "", (
            f"auto-review.yml [design-coach] lock-check YAML env does not "
            f"pin {key} to empty — GITHUB_ENV from a Bash-capable coach is "
            "applied at process start, before the in-script unset, so "
            "LD_PRELOAD maps at exec and BASH_ENV is sourced as bash starts")
    run = check.split("run:", 1)[1]
    assert "${{" not in run, (
        "auto-review.yml [design-coach] lock-check step interpolates an "
        "expression into its script")
    assert "./scripts/coach-lock-check.sh" not in run, (
        "auto-review.yml [design-coach] lock-check still executes the "
        "workspace script — the completeness pin would be PR-controlled")
    assert 'export PATH="/usr/bin:/bin:/usr/local/bin"' in run, (
        "auto-review.yml [design-coach] lock-check does not reset PATH — "
        "a GITHUB_PATH write from the Bash-capable coach would run a "
        "stub python3/gh")
    assert "unset PYTHONPATH" in run, (
        "auto-review.yml [design-coach] lock-check does not drop "
        "PYTHONPATH — a GITHUB_ENV write would inject sitecustomize "
        "into the completeness pin")
    assert "GIT_ALLOW_PROTOCOL=https" in run, (
        "auto-review.yml [design-coach] lock-check does not re-assert "
        "the git protocol lock after GITHUB_ENV")
    assert "/usr/bin/bash" in run, (
        "auto-review.yml [design-coach] lock-check does not invoke the "
        "extracted script with /usr/bin/bash")
    assert '--since "$COACH_LOCK_SINCE"' in run, (
        "auto-review.yml [design-coach] lock-check does not pass "
        "--since \"$COACH_LOCK_SINCE\" — a lock from an earlier coach run "
        "would stamp this round complete")
    assert 'if [ -z "${COACH_LOCK_SINCE:-}" ]' in run, (
        "auto-review.yml [design-coach] lock-check does not refuse an "
        "empty COACH_LOCK_SINCE — the this-run bound would silently drop")


def test_coach_lock_check_runs_the_base_copy_after_the_agent():
    _assert_coach_lock_check_runs_base_copy(_workflow_text())


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
    # NEGATIVE CONTROL: the terminal Anthropic coach link (fall-through only)
    # overrides the job-level config count from its own env block.
    tampered = _step_replace(
        _workflow_text(), "design-coach", -1,
        "          REVIEWER_POST_STATE: ${{ runner.temp }}/reviewer-posts\n",
        "          REVIEWER_POST_STATE: ${{ runner.temp }}/reviewer-posts\n"
        "          GIT_CONFIG_COUNT: \"0\"\n")
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


def test_coach_guard_rejects_a_base_ref_checkout():
    tampered = _job_replace(
        _workflow_text(), "design-coach",
        "          persist-credentials: false\n",
        "          persist-credentials: false\n"
        "          ref: ${{ github.event.pull_request.base.ref }}\n")
    with pytest.raises(AssertionError, match="base.ref"):
        _assert_coach_checks_out_full_history(tampered)


def _restore_chunk(text: str) -> str:
    return next(c for c in _steps(_job_blocks(text)["design-coach"])
                if COACH_RESTORE_MARKER in c)


def test_coach_guard_rejects_a_job_without_the_restore_step():
    text = _workflow_text()
    block = _job_blocks(text)["design-coach"]
    tampered = text
    for restore in [c for c in _steps(block) if COACH_RESTORE_MARKER in c]:
        tampered = tampered.replace("\n      - " + restore, "", 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="no trusted step restoring"):
        _assert_coach_restores_posting_surface_from_base(tampered)


def test_coach_guard_rejects_restore_after_the_agent():
    text = _workflow_text()
    block = _job_blocks(text)["design-coach"]
    restore = _restore_chunk(text)
    first_ship = _ship_chunks(block)[0]
    moved = block.replace("\n      - " + restore, "", 1).replace(
        first_ship, first_ship + "\n      - " + restore, 1)
    tampered = text.replace(block, moved, 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="not preceded"):
        _assert_coach_restores_posting_surface_from_base(tampered)


def test_coach_guard_rejects_restore_only_before_the_first_link():
    # NEGATIVE CONTROL: overlay once before link 1, then a failed
    # Write/Edit/Bash turn rewrites the MCP the next spawn loads.
    text = _workflow_text()
    block = _job_blocks(text)["design-coach"]
    restores = [c for c in _steps(block) if COACH_RESTORE_MARKER in c]
    assert len(restores) >= 2, "fixture stale — expected a restore per link"
    tampered = text.replace("\n      - " + restores[1], "", 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="not preceded"):
        _assert_coach_restores_posting_surface_from_base(tampered)


def test_coach_guard_rejects_an_interpolated_restore_script():
    # Insert ${{ without removing the checkout marker — a replace that
    # ate the restore identification string used to miss this guard.
    tampered = _job_replace(
        _workflow_text(), "design-coach",
        '          set -euo pipefail\n'
        '          export PATH="/usr/bin:/bin:/usr/local/bin"\n',
        '          set -euo pipefail\n'
        '          : ${{ github.event.pull_request.number }}\n'
        '          export PATH="/usr/bin:/bin:/usr/local/bin"\n')
    with pytest.raises(AssertionError, match="interpolates an expression"):
        _assert_coach_restores_posting_surface_from_base(tampered)


def test_coach_guard_rejects_a_path_git_on_restore():
    tampered = _job_replace(
        _workflow_text(), "design-coach",
        '          /usr/bin/git checkout "$BASE_SHA" -- \\\n',
        '          git checkout "$BASE_SHA" -- \\\n')
    with pytest.raises(AssertionError, match="/usr/bin/git"):
        _assert_coach_restores_posting_surface_from_base(tampered)


def test_coach_guard_rejects_restore_inheriting_pythonpath():
    tampered = _job_replace(
        _workflow_text(), "design-coach",
        "unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE \\\n",
        "true PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE \\\n")
    with pytest.raises(AssertionError, match="PYTHONPATH"):
        _assert_coach_restores_posting_surface_from_base(tampered)


def test_coach_guard_rejects_restore_without_process_start_env_pins():
    # In-script unset is too late: GITHUB_ENV LD_PRELOAD is mapped at exec.
    tampered = _job_replace(
        _workflow_text(), "design-coach",
        '          LD_PRELOAD: ""\n'
        '          LD_LIBRARY_PATH: ""\n'
        '          LD_AUDIT: ""\n'
        '          BASH_ENV: ""\n'
        '          ENV: ""\n',
        '          LD_LIBRARY_PATH: ""\n'
        '          LD_AUDIT: ""\n'
        '          BASH_ENV: ""\n'
        '          ENV: ""\n')
    with pytest.raises(AssertionError, match="LD_PRELOAD"):
        _assert_coach_restores_posting_surface_from_base(tampered)


def test_coach_guard_rejects_show_full_output():
    tampered = _step_replace(
        _workflow_text(), "design-coach", 0,
        "          allowed_bots: cursor\n",
        "          allowed_bots: cursor\n"
        "          show_full_output: \"true\"\n")
    with pytest.raises(AssertionError, match="show_full_output"):
        _assert_coach_restores_posting_surface_from_base(tampered)


def test_coach_guard_rejects_a_working_tree_ready_check():
    tampered = _job_replace(
        _workflow_text(), "design-coach",
        'git cat-file -e "${BASE_SHA}:.claude/reviewer-post/reviewer_mcp.py"',
        'test -f .claude/reviewer-post/reviewer_mcp.py')
    with pytest.raises(AssertionError, match="posting MCP blob"):
        _assert_coach_restores_posting_surface_from_base(tampered)


def test_coach_guard_rejects_a_ship_step_not_gated_on_ready():
    tampered = _step_replace(
        _workflow_text(), "design-coach", 0,
        "        if: steps.ready.outputs.ready == 'true' && env.HAS_ZAI == 'true'\n",
        "        if: env.HAS_ZAI == 'true'\n")
    with pytest.raises(AssertionError, match="not gated on"):
        _assert_coach_restores_posting_surface_from_base(tampered)


def test_coach_lock_guard_rejects_running_the_workspace_script():
    tampered = _job_replace(
        _workflow_text(), "design-coach",
        '          /usr/bin/bash "$CHECK" "$PR" --since "$COACH_LOCK_SINCE"\n',
        '          ./scripts/coach-lock-check.sh "$PR"\n')
    with pytest.raises(AssertionError, match="workspace script"):
        _assert_coach_lock_check_runs_base_copy(tampered)


def test_coach_lock_guard_rejects_dropping_this_run_since():
    tampered = _job_replace(
        _workflow_text(), "design-coach",
        '          /usr/bin/bash "$CHECK" "$PR" --since "$COACH_LOCK_SINCE"\n',
        '          /usr/bin/bash "$CHECK" "$PR"\n')
    with pytest.raises(AssertionError, match="--since"):
        _assert_coach_lock_check_runs_base_copy(tampered)


def test_coach_lock_guard_rejects_inheriting_pythonpath():
    # Unique to the lock-check step (restore has no PYTHONNOUSERSITE).
    tampered = _job_replace(
        _workflow_text(), "design-coach",
        "unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE \\\n"
        "                PYTHONEXECUTABLE LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT \\\n"
        "                DYLD_INSERT_LIBRARIES BASH_ENV ENV || true\n"
        "          export PYTHONNOUSERSITE=1\n",
        "export PYTHONNOUSERSITE=1\n")
    with pytest.raises(AssertionError, match="PYTHONPATH"):
        _assert_coach_lock_check_runs_base_copy(tampered)


def test_coach_lock_guard_rejects_unpinned_process_start_env():
    # Unique to lock-check (PR: is not on restore env). Keep the this-run
    # since binding — this tamper only drops the process-start pins.
    tampered = _job_replace(
        _workflow_text(), "design-coach",
        '          COACH_LOCK_SINCE: ${{ steps.ready.outputs.started_at }}\n'
        '          # Process-start pins: GITHUB_ENV from a prior Bash coach link\n'
        '          # is applied before this script body, so in-script unset is too\n'
        '          # late for LD_PRELOAD (mapped at exec) and BASH_ENV/ENV (sourced\n'
        '          # as bash starts). Empty BASH_ENV/`ENV` is skipped (`[ -n ]`).\n'
        '          PYTHONPATH: ""\n'
        '          PYTHONHOME: ""\n'
        '          PYTHONSTARTUP: ""\n'
        '          PYTHONNOUSERSITE: "1"\n'
        '          LD_PRELOAD: ""\n'
        '          LD_LIBRARY_PATH: ""\n'
        '          LD_AUDIT: ""\n'
        '          BASH_ENV: ""\n'
        '          ENV: ""\n',
        '          COACH_LOCK_SINCE: ${{ steps.ready.outputs.started_at }}\n')
    with pytest.raises(AssertionError, match="LD_PRELOAD"):
        _assert_coach_lock_check_runs_base_copy(tampered)


def test_coach_lock_guard_rejects_extracting_before_the_agent():
    text = _workflow_text()
    block = _job_blocks(text)["design-coach"]
    steps = _steps(block)
    check = next(c for c in steps if COACH_LOCK_CHECK_SHOW in c)
    first_ship = _ship_chunks(block)[0]
    moved = block.replace("\n      - " + check, "", 1).replace(
        first_ship, check + "\n      - " + first_ship, 1)
    tampered = text.replace(block, moved, 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="BEFORE a ship step"):
        _assert_coach_lock_check_runs_base_copy(tampered)


def test_coach_lock_guard_rejects_dropping_the_base_extract():
    tampered = _job_replace(
        _workflow_text(), "design-coach",
        COACH_LOCK_CHECK_SHOW, "true")
    with pytest.raises(AssertionError, match="does not extract"):
        _assert_coach_lock_check_runs_base_copy(tampered)
