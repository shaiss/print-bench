"""Behavioral deny check for the backlog-burn agent Bash backstop (#1022).

Loads the real `.claude/backlog-burn-settings.json` the workflow passes to
claude-code-action and asserts — under Claude Code's Bash matcher, not a
grep — that issue comment/edit and label writes are refused while the
legitimate burn surface still passes.

The same contract is enforced by `scripts/backlog-burn-perms-check.sh`
(run by check.sh). This module keeps the package suite green on the same
invariants so a tools/backlog-burn-only test run cannot miss a settings
regression.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SETTINGS = REPO_ROOT / ".claude" / "backlog-burn-settings.json"


def _kwe(spec: str):
    m = re.match(r"^(.+):\*$", spec)
    return m.group(1) if m else None


def _v8r(spec: str) -> bool:
    if spec.endswith(":*"):
        return False
    for n, ch in enumerate(spec):
        if ch != "*":
            continue
        s = 0
        r = n - 1
        while r >= 0 and spec[r] == "\\":
            s += 1
            r -= 1
        if s % 2 == 0:
            return True
    return False


def _dollar8(pattern: str, command: str, case_insensitive=False, collapse_ws=False) -> bool:
    if "\x00" in pattern:
        return False
    i = pattern.strip()
    d = re.sub(r"[ \t]+", " ", i) if collapse_ws else i
    c = re.sub(r"[ \t]+", " ", command) if collapse_ws else command
    p_parts = []
    g = 0
    while g < len(d):
        P = d[g]
        if P == "\\" and g + 1 < len(d):
            j = d[g + 1]
            if j == "*":
                p_parts.append("\x00ESCAPED_STAR\x00")
                g += 2
                continue
            if j == "\\":
                p_parts.append("\x00ESCAPED_BACKSLASH\x00")
                g += 2
                continue
        p_parts.append(P)
        g += 1
    p = "".join(p_parts)
    escaped = re.sub(r"""[.+?^${}()|[\]\\'"]""", lambda m: "\\" + m.group(0), p)
    escaped = re.sub(r"/(?:\*\*/)+", "\x00GLOBSTAR\x00", escaped)
    escaped = escaped.replace("*", ".*")
    escaped = escaped.replace("\x00GLOBSTAR\x00", "/(?:.*/)?")
    escaped = escaped.replace("\x00ESCAPED_STAR\x00", r"\*")
    escaped = escaped.replace("\x00ESCAPED_BACKSLASH\x00", r"\\")
    star_count = p.count("*")
    if escaped.endswith(" .*") and star_count == 1:
        escaped = escaped[:-3] + "( .*)?"
    flags = re.DOTALL | (re.IGNORECASE if case_insensitive else 0)
    try:
        return re.match(r"^" + escaped + r"$", c, flags) is not None
    except re.error:
        return False


def _bash_denied(spec: str, command: str) -> bool:
    prefix = _kwe(spec)
    if prefix is not None:
        cl, pl = command.lower(), prefix.lower()
        return cl == pl or cl.startswith(pl + " ")
    if _v8r(spec):
        return _dollar8(spec, command, case_insensitive=True, collapse_ws=True)
    return spec.lower() == command.lower()


def _denies(deny_rules: list[str], command: str) -> bool:
    for rule in deny_rules:
        if not (rule.startswith("Bash(") and rule.endswith(")")):
            continue
        if _bash_denied(rule[len("Bash(") : -1], command):
            return True
    return False


@pytest.fixture(scope="module")
def deny_rules() -> list[str]:
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return list((data.get("permissions") or {}).get("deny") or [])


@pytest.fixture(scope="module")
def allow_rules() -> list[str]:
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return list((data.get("permissions") or {}).get("allow") or [])


@pytest.mark.parametrize(
    "command",
    [
        "gh issue comment 1022 --body x",
        "gh issue edit 1022 --add-label needs-decision",
        "gh issue edit 1022 --remove-label autonomy-ok",
        "gh label create foo",
        "gh api --method POST repos/o/r/issues/1/comments -f body=x",
        "gh api --method POST repos/o/r/issues/1/labels -f name=x",
        "gh api --method DELETE repos/o/r/issues/1/labels/foo",
        "gh api repos/o/r/issues/1/labels -f name=x",
        "curl -X POST https://api.github.com/repos/o/r/issues/1/comments -d body=x",
        "curl -X POST https://api.github.com/repos/o/r/issues/1/labels -d name=x",
        "gh issue close 5 --comment x",
        "gh issue reopen 5 -c x",
        "gh api graphql -f query='mutation{addComment(input:{subjectId:\"I_x\",body:\"y\"}){clientMutationId}}'",
        "gh api -X PATCH repos/o/r/issues/5 -f body=x",
        "gh api --method PATCH repos/o/r/issues/5 -f title=x",
        "gh api --method POST repos/o/r/issues/5 -f title=x",
        "python3 -c \"import urllib.request\"",
    ],
)
def test_issue_write_probes_denied(deny_rules, command):
    assert _denies(deny_rules, command), f"expected deny for: {command}"


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git checkout -b claude/issue-1022-foo",
        "git commit -m x",
        "gh issue view 1022",
        "gh api repos/o/r/issues/1",
        "gh api repos/o/r/issues/1/comments",
        "gh api repos/o/r/issues/1/labels",
        "gh api repos/o/r/labels",
    ],
)
def test_legitimate_probes_allowed(deny_rules, command):
    assert not _denies(deny_rules, command), f"expected allow for: {command}"


def test_allow_list_not_widened_to_issue_writes(allow_rules):
    forbidden = (
        "gh issue comment",
        "gh issue edit",
        "gh label",
        "git push",
        "gh pr create",
    )
    for rule in allow_rules:
        for bad in forbidden:
            assert bad not in rule, f"allow list widened: {rule}"


def test_settings_file_is_the_workflow_backstop():
    """Parity: workflow and deliver selftest both name this path."""
    assert SETTINGS.is_file()
    workflow = (REPO_ROOT / ".github" / "workflows" / "backlog-burn.yml").read_text(
        encoding="utf-8"
    )
    assert "--settings .claude/backlog-burn-settings.json" in workflow
