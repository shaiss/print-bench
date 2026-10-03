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


def test_every_reviewer_ship_step_carries_its_backstop():
    _assert_reviewer_steps_carry_their_backstop(_workflow_text())


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
])
def test_wiring_guard_rejects_a_tampered_step(job, step, old, new, match):
    # NEGATIVE CONTROLS: each tamper must fail the pin, or it proves nothing.
    tampered = _tamper(_workflow_text(), job, step, old, new)
    with pytest.raises(AssertionError, match=match):
        _assert_reviewer_steps_carry_their_backstop(tampered)


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
