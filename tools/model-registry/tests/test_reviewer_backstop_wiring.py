"""Drift guard: every auto-review ship step runs under its reviewer deny backstop.

``scripts/reviewer-perms-check.sh`` holds the FILE half of the reviewers'
containment (issue #323): what ``.claude/reviewer-settings.json`` (Jane, Drik,
PM triage) and ``.claude/design-coach-settings.json`` (the coach) deny. It
never reads a workflow, so an edit that drops ``--settings`` from one fallback
step, hands a reviewer the coach's Write/Edit-allowing backstop, or reverts a
step to ``bypassPermissions`` (which ignores the step's own denies) would leave
it green while that reviewer ran with the whole ``.claude/settings.json`` allow
list — the render toolchain #323 exists to keep out of a review included. The
fall-through links are the risk: a run that the head link serves never shows a
tail step's surface.

This file is the WORKFLOW half: every claude-code-action step in the reviewer
jobs must carry exactly ``--permission-mode dontAsk --settings <its backstop>``,
no job in auto-review.yml may run a ship step outside the table, and the table's
backstops must be the files the perms check guards. Every pin has a tamper
negative control below, derived from the live workflow text, proving it can
fail. Kept out of test_workflow_drift.py (it reuses that file's job-block
parser) so the pin reads on its own.
"""

from __future__ import annotations

import json
import re

import pytest

from test_workflow_drift import (
    REPO_ROOT,
    REVIEWER_JOBS,
    _job_blocks,
    _without_comments,
    _workflow_text,
)

REVIEWER_BACKSTOP = ".claude/reviewer-settings.json"
COACH_BACKSTOP = ".claude/design-coach-settings.json"
# The posting surface (issues #764 / #772 / #806): Jane, Drik and pm-triage
# ship steps must carry the reviewer MCP server and pin its trusted env, or
# they relapse into having NO postable write (every round then ends with
# denials and an exit-0 job that posted nothing — the bug this closes). The
# coach uses the same server with a *different* tool and a wider
# --allowedTools so git push still works.
POST_CONFIG = ".claude/reviewer-post/reviewer-mcp.json"
# job → (REVIEWER_ID, allowed MCP tool)
POST_JOBS = {
    "jane-review": ("jane", "mcp__reviewer__post_review"),
    "drik-review": ("drik", "mcp__reviewer__post_review"),
    "pm-triage": ("pm", "mcp__reviewer__post_triage"),
}
COACH_POST_TOOL = "mcp__reviewer__post_coach"
COACH_LOCK_CHECK_SHOW = (
    '/usr/bin/git show "${BASE_SHA}:scripts/coach-lock-check.sh"'
)
COACH_POST_JOB = "design-coach"
COACH_ALLOWED_KEEP = ("Write", "Edit", "Bash")
POST_PR = "${{ github.event.pull_request.number }}"
POST_STATE = "${{ runner.temp }}/reviewer-posts"
# job → the deny backstop its ship steps pass. The coach's differs because it
# pushes iterations (Write/Edit stay allowed); the reviewers are read-only.
BACKSTOPS = {
    "jane-review": REVIEWER_BACKSTOP,
    "drik-review": REVIEWER_BACKSTOP,
    "pm-triage": REVIEWER_BACKSTOP,
    "design-coach": COACH_BACKSTOP,
}
PERMS_CHECK = REPO_ROOT / "scripts" / "reviewer-perms-check.sh"

_BLOCK_SCALAR = {">", ">-", ">+", "|", "|-", "|+"}


def _ship_chunks(job_text: str) -> list[str]:
    """The job's claude-code-action steps, in order (the 6-space `- ` list)."""
    return [c for c in re.split(r"\n      - ", job_text)
            if "uses: anthropics/claude-code-action" in c]


def _claude_args(chunk: str) -> list[str]:
    """Every `claude_args:` value in the step, a folded/literal block scalar
    joined onto one line — so reflowing the flags cannot hide them."""
    values = []
    lines = chunk.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s+)claude_args:[ \t]*(.*)$", line)
        if not m:
            continue
        indent, value = len(m.group(1)), m.group(2).strip()
        if value in _BLOCK_SCALAR:
            body = []
            for nxt in lines[i + 1:]:
                if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                    break
                body.append(nxt.strip())
            value = " ".join(b for b in body if b)
        values.append(value)
    return values


def _flag(args: str, flag: str) -> list[str]:
    """Every value passed to `flag` (space- or `=`-separated)."""
    return re.findall(r"(?:^|\s)" + re.escape(flag) + r"[ =](\S+)", args)


def _assert_reviewer_steps_carry_their_backstop(text: str) -> None:
    """Each reviewer job's every ship step runs dontAsk under its own backstop,
    and no job outside the table runs a ship step. Factored out so the
    negative controls can run it against tampered workflow text."""
    blocks = _job_blocks(text)
    for job, block in blocks.items():
        block = _without_comments(block)
        chunks = _ship_chunks(block)
        if job not in BACKSTOPS:
            assert not chunks, (
                f"auto-review.yml [{job}] runs a claude-code-action step but is "
                f"not in this file's BACKSTOPS table — enrol it with its deny "
                f"backstop, or it inherits every settings.json allow unpinned")
            continue
        assert chunks, f"auto-review.yml [{job}]: no claude-code-action ship step found"
        for word in ("bypassPermissions", "dangerously-skip-permissions"):
            assert word not in block, (
                f"auto-review.yml [{job}] mentions {word} — a step under it "
                f"ignores its own deny backstop")
        for n, chunk in enumerate(chunks, 1):
            at = f"auto-review.yml [{job}] ship step {n}"
            args = _claude_args(chunk)
            assert len(args) == 1, f"{at}: expected one claude_args, found {len(args)}"
            modes = _flag(args[0], "--permission-mode")
            assert modes == ["dontAsk"], (
                f"{at} runs under permission mode {modes or 'default'}, not "
                f"exactly dontAsk — without it the deny backstop's denies are "
                f"not what bounds the session")
            settings = _flag(args[0], "--settings")
            assert settings == [BACKSTOPS[job]], (
                f"{at} passes deny backstop {settings or 'none'}, not exactly "
                f"[{BACKSTOPS[job]!r}] — the settings.json allows it inherits "
                f"are no longer neutralised (or it wears the other backstop)")
            # Cursor cloud agents initiate the workflow as cursor[bot]. The
            # action's default allowed_bots is empty and refuses that actor
            # before any review runs. Pin the slug the error names (`cursor`,
            # not `cursor[bot]` and not `*`). Check `*` first so a widen
            # fails on that pin rather than the missing-cursor assertion.
            assert not re.search(
                r"(?m)^\s+allowed_bots:\s+['\"]?\*['\"]?\s*$", chunk
            ), (
                f"{at} sets allowed_bots to '*' — that lets any GitHub App "
                f"trigger the action on a public repo")
            assert re.search(r"(?m)^\s+allowed_bots:\s+cursor\s*$", chunk), (
                f"{at} omits `allowed_bots: cursor` — a Cursor-authored design "
                f"PR would fail at the human-actor check")


def test_every_reviewer_ship_step_carries_its_backstop():
    _assert_reviewer_steps_carry_their_backstop(_workflow_text())


def _step_env(chunk: str) -> dict[str, str]:
    """The step's `env:` scalar entries — the trusted inputs the posting
    server reads (REVIEWER_ID / REVIEWER_PR / REVIEWER_POST_STATE)."""
    env: dict[str, str] = {}
    for m in re.finditer(r"^ +([A-Z][A-Z0-9_]+): (.+)$", chunk, re.MULTILINE):
        env[m.group(1)] = m.group(2).strip()
    return env


def _assert_reviewer_steps_carry_their_post_surface(text: str) -> None:
    """Every Jane/Drik ship step wires the posting server AND pins its trusted
    env — the flags prove the tool is loaded and allowed, the env proves the
    server can know WHICH reviewer and WHICH PR it is posting for. Factored
    out for the tamper negative controls."""
    assert (REPO_ROOT / POST_CONFIG).is_file(), (
        f"{POST_CONFIG} is missing — the reviewers have no postable write")
    for job, (who, tool) in POST_JOBS.items():
        block = _without_comments(_job_blocks(text)[job])
        for n, chunk in enumerate(_ship_chunks(block), 1):
            at = f"auto-review.yml [{job}] ship step {n}"
            args = _claude_args(chunk)[0]
            configs = _flag(args, "--mcp-config")
            assert configs == [POST_CONFIG], (
                f"{at} passes --mcp-config {configs or 'none'}, not exactly "
                f"[{POST_CONFIG!r}] — the reviewer posts via that server or "
                f"not at all (issue #764/#772)")
            tools = _flag(args, "--allowedTools")
            allowed = tools[0].strip('"').split(",") if tools else []
            assert len(tools) == 1 and tool in allowed, (
                f"{at} does not allow {tool} — the session would be "
                f"denied on its only write surface")
            env = _step_env(chunk)
            assert env.get("REVIEWER_ID") == who, (
                f"{at} sets REVIEWER_ID={env.get('REVIEWER_ID')!r}, not "
                f"{who!r} — the env selects the marker family, so a wrong "
                f"value posts the wrong identity's marker")
            assert env.get("REVIEWER_PR") == POST_PR, (
                f"{at} sets REVIEWER_PR={env.get('REVIEWER_PR')!r}, not the "
                f"workflow's PR — the posting server pins its target to this "
                f"env; anything else lets the comment land elsewhere")
            assert env.get("REVIEWER_POST_STATE") == POST_STATE, (
                f"{at} sets REVIEWER_POST_STATE="
                f"{env.get('REVIEWER_POST_STATE')!r}, not the shared "
                f"{POST_STATE!r} — one path across the chain walk is what "
                f"makes the one-review cap span the links")


def test_every_reviewer_ship_step_carries_the_post_surface():
    _assert_reviewer_steps_carry_their_post_surface(_workflow_text())


def _assert_coach_steps_carry_their_post_surface(text: str) -> None:
    """Coach ship steps load post_coach AND keep Write/Edit/Bash.

    Copying Jane's read-only --allowedTools onto the coach is the #806
    containment trap: comments would post but iterations could not push.
    """
    assert (REPO_ROOT / POST_CONFIG).is_file()
    block = _without_comments(_job_blocks(text)[COACH_POST_JOB])
    chunks = _ship_chunks(block)
    assert chunks, "auto-review.yml [design-coach]: no ship step found"
    assert COACH_LOCK_CHECK_SHOW in block, (
        "auto-review.yml [design-coach] does not extract coach-lock-check.sh "
        "from base.sha — a workspace copy the agent can rewrite would stamp "
        "the round complete (issue #806)")
    assert "./scripts/coach-lock-check.sh" not in block, (
        "auto-review.yml [design-coach] still runs the workspace "
        "coach-lock-check.sh — the completeness pin would be PR-controlled")
    for n, chunk in enumerate(chunks, 1):
        at = f"auto-review.yml [design-coach] ship step {n}"
        args = _claude_args(chunk)[0]
        configs = _flag(args, "--mcp-config")
        assert configs == [POST_CONFIG], (
            f"{at} passes --mcp-config {configs or 'none'}, not exactly "
            f"[{POST_CONFIG!r}] — the coach posts via that server or not at all")
        tools = _flag(args, "--allowedTools")
        allowed = tools[0].strip('"').split(",") if tools else []
        assert len(tools) == 1 and COACH_POST_TOOL in allowed, (
            f"{at} does not allow {COACH_POST_TOOL} — the session would be "
            "denied on its comment write (issue #806)")
        assert POST_TOOL not in allowed, (
            f"{at} allows {POST_TOOL} — the coach must not hold the "
            "reviewers' sign-off tool")
        for keep in COACH_ALLOWED_KEEP:
            assert keep in allowed, (
                f"{at} dropped {keep} from --allowedTools — copying Jane's "
                "read-only list onto the coach would block git push")
        env = _step_env(chunk)
        assert env.get("REVIEWER_ID") == "coach", (
            f"{at} sets REVIEWER_ID={env.get('REVIEWER_ID')!r}, not 'coach'")
        assert env.get("REVIEWER_PR") == POST_PR, (
            f"{at} sets REVIEWER_PR={env.get('REVIEWER_PR')!r}, not the "
            "workflow's PR")
        assert env.get("REVIEWER_POST_STATE") == POST_STATE, (
            f"{at} sets REVIEWER_POST_STATE="
            f"{env.get('REVIEWER_POST_STATE')!r}, not {POST_STATE!r}")
        assert env.get("PYTHONPATH") == '""', (
            f"{at} does not clear PYTHONPATH — a GITHUB_ENV write from an "
            "earlier Bash link would inject sitecustomize into the posting "
            "server even under /usr/bin/python3")
        assert env.get("PYTHONNOUSERSITE") == '"1"', (
            f"{at} does not set PYTHONNOUSERSITE=1 — user-site sitecustomize "
            "would still load without isolated mode")


def test_every_coach_ship_step_carries_the_post_surface():
    _assert_coach_steps_carry_their_post_surface(_workflow_text())


MCP_PYTHON = "/usr/bin/python3"


def _assert_mcp_command_is_absolute(raw: str) -> None:
    """PATH `python3` is GITHUB_PATH-poisonable after a Bash coach link.
    ``-I`` is isolated mode so PYTHONPATH/PYTHONHOME from GITHUB_ENV cannot
    inject sitecustomize into the posting server."""
    data = json.loads(raw)
    cmd = data["mcpServers"]["reviewer"]["command"]
    args = data["mcpServers"]["reviewer"]["args"]
    assert cmd == MCP_PYTHON, (
        f"{POST_CONFIG} command is {cmd!r}, not {MCP_PYTHON} — a PATH-relative "
        "python3 is GITHUB_PATH-poisonable after a failed Bash-capable coach "
        "link, and claude-code-action looks up the command before "
        "--allowedTools applies"
    )
    assert args and args[0] == "-I", (
        f"{POST_CONFIG} args are {args!r}, not starting with -I — "
        "/usr/bin/python3 still loads PYTHONPATH sitecustomize without "
        "isolated mode"
    )


def test_posting_mcp_uses_absolute_python():
    _assert_mcp_command_is_absolute(
        (REPO_ROOT / POST_CONFIG).read_text(encoding="utf-8"))


def test_posting_mcp_guard_rejects_path_python3():
    raw = (REPO_ROOT / POST_CONFIG).read_text(encoding="utf-8").replace(
        f'"{MCP_PYTHON}"', '"python3"')
    assert raw != (REPO_ROOT / POST_CONFIG).read_text(encoding="utf-8"), (
        "tamper did not land — the fixture is stale")
    with pytest.raises(AssertionError, match="PATH-relative"):
        _assert_mcp_command_is_absolute(raw)


def test_posting_mcp_guard_rejects_missing_isolated_mode():
    raw = (REPO_ROOT / POST_CONFIG).read_text(encoding="utf-8").replace(
        '"-I", ', "")
    assert raw != (REPO_ROOT / POST_CONFIG).read_text(encoding="utf-8"), (
        "tamper did not land — the fixture is stale")
    with pytest.raises(AssertionError, match="isolated mode"):
        _assert_mcp_command_is_absolute(raw)


def test_backstop_table_covers_every_reviewer_job():
    # The review-chain guard's job list and this table cannot drift: a reviewer
    # job enrolled there without a backstop here would ship unpinned.
    assert set(BACKSTOPS) == set(REVIEWER_JOBS), (
        f"BACKSTOPS {sorted(BACKSTOPS)} != REVIEWER_JOBS {sorted(REVIEWER_JOBS)}")


def _assert_perms_check_guards_the_backstops(script: str) -> None:
    """The workflow half and the file half name the same files, or the perms
    check guards a backstop no step passes (and the one a step passes goes
    unguarded). Factored out so the negative control can run it against a
    tampered script."""
    for backstop in sorted(set(BACKSTOPS.values())):
        assert (REPO_ROOT / backstop).is_file(), f"{backstop} is missing"
        assert f'"{backstop}"' in script, (
            f"scripts/reviewer-perms-check.sh does not guard {backstop}")


def test_backstops_are_the_files_the_perms_check_guards():
    _assert_perms_check_guards_the_backstops(PERMS_CHECK.read_text(encoding="utf-8"))


def _tamper(text: str, job: str, step: int, old: str, new: str) -> str:
    """Rewrite `old` → `new` inside ONE ship step of one job, anchored on the
    live step text (never a file-wide first occurrence)."""
    chunk = _ship_chunks(_job_blocks(text)[job])[step]
    assert old in chunk, "tamper target not found — the fixture is stale"
    tampered = text.replace(chunk, chunk.replace(old, new, 1), 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    return tampered


@pytest.mark.parametrize("job,step,old,new,match", [
    # The terminal tail step sheds its backstop — seen only on full fall-through.
    ("jane-review", -1, " --settings .claude/reviewer-settings.json", "",
     "deny backstop"),
    # A reviewer step wears the coach's backstop, which allows Write/Edit.
    ("drik-review", 1, "--settings .claude/reviewer-settings.json",
     "--settings .claude/design-coach-settings.json", "deny backstop"),
    # The coach wears the reviewers' — it could no longer push its rounds.
    ("design-coach", -1, "--settings .claude/design-coach-settings.json",
     "--settings .claude/reviewer-settings.json", "deny backstop"),
    # A second --settings layered on top: the backstop is no longer the one file.
    ("design-coach", 0, " --model", " --settings .claude/settings.json --model",
     "deny backstop"),
    # Reverted to bypassPermissions, which ignores the step's own denies.
    ("drik-review", 0, "--permission-mode dontAsk",
     "--permission-mode bypassPermissions", "bypassPermissions"),
    # dontAsk dropped: the default mode is not what bounds the session.
    ("pm-triage", 2, "--permission-mode dontAsk ", "", "permission mode"),
    # The skip-all-permissions flag appended.
    ("jane-review", 3, " --model", " --dangerously-skip-permissions --model",
     "dangerously-skip-permissions"),
    # Cursor allowlist dropped: Jane/Drik fail on cursor[bot] PRs before review.
    ("jane-review", 0, "          allowed_bots: cursor\n", "",
     "allowed_bots: cursor"),
    # Widened to every bot — public-repo Apps could trigger the action.
    ("drik-review", 0, "          allowed_bots: cursor\n",
     "          allowed_bots: '*'\n", "allowed_bots to '*'"),
])
def test_wiring_guard_rejects_a_tampered_step(job, step, old, new, match):
    # NEGATIVE CONTROLS: each tamper must fail the pin, or it proves nothing.
    tampered = _tamper(_workflow_text(), job, step, old, new)
    with pytest.raises(AssertionError, match=match):
        _assert_reviewer_steps_carry_their_backstop(tampered)


@pytest.mark.parametrize("job,step,old,new,match", [
    # The posting server dropped: back to denials and an exit-0 nothing.
    ("jane-review", 0, " --mcp-config .claude/reviewer-post/reviewer-mcp.json",
     "", "--mcp-config"),
    # The tool dropped from --allowedTools: loaded but never permitted.
    ("drik-review", 2,
     '--allowedTools "mcp__reviewer__post_review,Read,Grep,Glob"',
     '--allowedTools "Read,Grep,Glob"', "only write surface"),
    # REVIEWER_ID crossed: a Jane step posting DRIK's sign-off family.
    ("jane-review", 4, "REVIEWER_ID: jane", "REVIEWER_ID: drik",
     "REVIEWER_ID"),
    # REVIEWER_PR unpinned: the server would refuse (or post elsewhere).
    ("drik-review", 5,
     "REVIEWER_PR: ${{ github.event.pull_request.number }}",
     "REVIEWER_PR: 1", "REVIEWER_PR"),
    # The state path off runner.temp / per-link: the cap stops spanning the walk.
    ("jane-review", 1,
     "REVIEWER_POST_STATE: ${{ runner.temp }}/reviewer-posts",
     "REVIEWER_POST_STATE: reviewer-posts", "REVIEWER_POST_STATE"),
    # The state env dropped entirely.
    ("drik-review", -1, "          REVIEWER_POST_STATE: ${{ runner.temp }}"
     "/reviewer-posts\n", "", "REVIEWER_POST_STATE"),
    # pm-triage: dropping the posting server is the #772 silent-no-post again.
    ("pm-triage", 0, " --mcp-config .claude/reviewer-post/reviewer-mcp.json",
     "", "--mcp-config"),
    ("pm-triage", 2,
     '--allowedTools "mcp__reviewer__post_triage,Read,Grep,Glob"',
     '--allowedTools "Read,Grep,Glob"', "only write surface"),
    ("pm-triage", 4, "REVIEWER_ID: pm", "REVIEWER_ID: jane",
     "REVIEWER_ID"),
])
def test_post_surface_guard_rejects_a_tampered_step(job, step, old, new, match):
    # NEGATIVE CONTROLS for the posting-surface pin, same discipline.
    tampered = _tamper(_workflow_text(), job, step, old, new)
    with pytest.raises(AssertionError, match=match):
        _assert_reviewer_steps_carry_their_post_surface(tampered)


@pytest.mark.parametrize("step,old,new,match", [
    (0, " --mcp-config .claude/reviewer-post/reviewer-mcp.json",
     "", "--mcp-config"),
    (1,
     '--allowedTools "mcp__reviewer__post_coach,Read,Grep,Glob,Write,Edit,Bash"',
     '--allowedTools "mcp__reviewer__post_review,Read,Grep,Glob"',
     "post_coach"),
    (2,
     '--allowedTools "mcp__reviewer__post_coach,Read,Grep,Glob,Write,Edit,Bash"',
     '--allowedTools "mcp__reviewer__post_coach,Read,Grep,Glob"',
     "Write"),
    (3, "REVIEWER_ID: coach", "REVIEWER_ID: jane",
     "REVIEWER_ID"),
    (4,
     "REVIEWER_PR: ${{ github.event.pull_request.number }}",
     "REVIEWER_PR: 1", "REVIEWER_PR"),
    (5,
     "REVIEWER_POST_STATE: ${{ runner.temp }}/reviewer-posts",
     "REVIEWER_POST_STATE: reviewer-posts", "REVIEWER_POST_STATE"),
    (0, '          PYTHONPATH: ""\n', "", "PYTHONPATH"),
])
def test_coach_post_surface_guard_rejects_a_tampered_step(step, old, new, match):
    tampered = _tamper(_workflow_text(), "design-coach", step, old, new)
    with pytest.raises(AssertionError, match=match):
        _assert_coach_steps_carry_their_post_surface(tampered)


def test_coach_lock_check_step_cannot_be_dropped():
    text = _workflow_text()
    dropped = text.replace(COACH_LOCK_CHECK_SHOW, "true", 1)
    assert dropped != text, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="coach-lock-check"):
        _assert_coach_steps_carry_their_post_surface(dropped)


def test_post_surface_guard_rejects_a_missing_server():
    # NEGATIVE CONTROL: the wiring can be perfect and still post nothing if
    # the server file the config launches is gone. Prove the pin sees the
    # file, without deleting it: point the constant at a missing path.
    text = _workflow_text()
    import test_reviewer_backstop_wiring as mod
    real = mod.POST_CONFIG
    try:
        mod.POST_CONFIG = ".claude/reviewer-post/gone-mcp.json"
        with pytest.raises(AssertionError, match="is missing"):
            _assert_reviewer_steps_carry_their_post_surface(text)
    finally:
        mod.POST_CONFIG = real


def test_wiring_guard_rejects_a_reflowed_step_that_shed_its_backstop():
    # NEGATIVE CONTROL: moving the flags into a folded block scalar must not
    # hide them — the reflow alone passes, the reflow minus --settings fails.
    text = _workflow_text()
    chunk = _ship_chunks(_job_blocks(text)["pm-triage"])[0]
    line = next(l for l in chunk.splitlines() if "claude_args:" in l)
    indent = line[:len(line) - len(line.lstrip())]
    args = line.split("claude_args:", 1)[1].strip()
    folded = f"{indent}claude_args: >-\n{indent}  " + args.replace(
        " --model", f"\n{indent}  --model", 1)
    reflowed = text.replace(chunk, chunk.replace(line, folded, 1), 1)
    assert reflowed != text, "tamper did not land — the fixture is stale"
    _assert_reviewer_steps_carry_their_backstop(reflowed)
    shed = reflowed.replace(
        folded, folded.replace(" --settings .claude/reviewer-settings.json", "", 1), 1)
    assert shed != reflowed, "tamper did not land — the fixture is stale"
    with pytest.raises(AssertionError, match="deny backstop"):
        _assert_reviewer_steps_carry_their_backstop(shed)


_ROGUE_JOB = """\
  rogue-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - name: /rogue-review
        uses: anthropics/claude-code-action@9171db3e57d6a3140a37ddc2ba92788584e0ead6  # v1
        with:
          claude_args: --model x
          prompt: /jane-review 1
"""


def test_wiring_guard_rejects_an_unenrolled_ship_job():
    # NEGATIVE CONTROL: a fifth job running a ship step outside the table
    # (here with no backstop at all) must fail, not slip past the pin.
    text = _workflow_text()
    assert "  rogue-review:" not in text, "tamper target collides — the fixture is stale"
    head = re.search(r"^jobs:[ \t]*\n", text, re.MULTILINE)
    assert head, "workflow has no `jobs:` section"
    tampered = text[:head.end()] + _ROGUE_JOB + text[head.end():]
    with pytest.raises(AssertionError, match="BACKSTOPS table"):
        _assert_reviewer_steps_carry_their_backstop(tampered)


def test_backstop_guard_rejects_a_perms_check_that_moved_off_the_file():
    # NEGATIVE CONTROL: the perms check pointed at a different file — the
    # workflow's backstop would go unguarded while both halves stay green.
    script = PERMS_CHECK.read_text(encoding="utf-8")
    moved = script.replace('".claude/design-coach-settings.json"',
                           '".claude/coach-settings.json"')
    assert moved != script, "tamper target not found — the fixture is stale"
    with pytest.raises(AssertionError, match="does not guard"):
        _assert_perms_check_guards_the_backstops(moved)
