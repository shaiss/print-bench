"""reeve-growth.yml must hand EVERY link of its chain walk a fresh dedup
context, assembled by this package's tested helper — not an inline listing.

Pins, read off the workflow text (stdlib only, like the drift guard's parser):

* each claude-code-action link step is immediately preceded by a step that
  runs ``python3 -m growth dedup-context`` (head assembly, tail refreshes);
* each link step names that context's JSON file in the env var the queue
  server reads (``queue_mcp.DEDUP_ENV``) — the backstop is fail-closed when
  unattended, so a link without it could file nothing at all;
* the invocation parses and runs under the real CLI, writing where the env
  var and the agent's markdown path say it does;
* no inline ``gh issue list`` assembly survives (the open-queue-only list that
  let declined #597 back in as #754).

Each pin has a negative control: a tampered copy of the workflow must fail.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shlex
from pathlib import Path

import pytest

from growth import dedup
from growth.cli import main

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "reeve-growth.yml"
SERVER = ROOT / ".claude" / "skills" / "growth-queue" / "queue_mcp.py"
JOB = "reeve-growth"

_JOB_HEADER = re.compile(r"^  ([a-z][a-z0-9-]*):[ \t]*$", re.MULTILINE)
_INVOKE_RE = re.compile(r"python3 -m growth dedup-context((?:[^\n]*\\\n)*[^\n]*)")


def _dedup_env() -> str:
    spec = importlib.util.spec_from_file_location("queue_mcp", SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DEDUP_ENV


def _job_text(text: str) -> str:
    section = text[re.search(r"^jobs:[ \t]*$", text, re.MULTILINE).start():]
    heads = [(m.group(1), m.start()) for m in _JOB_HEADER.finditer(section)]
    for i, (name, start) in enumerate(heads):
        if name == JOB:
            end = heads[i + 1][1] if i + 1 < len(heads) else len(section)
            return section[start:end]
    raise AssertionError(f"no `{JOB}` job in the workflow")


def _steps(job: str) -> list[str]:
    # Steps live at 6-space indent; the first chunk is the job header.
    return re.split(r"\n      - ", job)[1:]


def _invocation(step: str) -> list[str] | None:
    m = _INVOKE_RE.search(step)
    if not m:
        return None
    # The command ends at the first shell separator (`...; then`, `|| ...`).
    command = re.split(r";|&&|\|\|", m.group(1).replace("\\\n", " "), maxsplit=1)[0]
    return shlex.split(command)


def _flag(args: list[str], flag: str) -> str | None:
    return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else None


def wiring_errors(text: str, env_name: str) -> list[str]:
    errors: list[str] = []
    steps = _steps(_job_text(text))
    links = [i for i, s in enumerate(steps) if "uses: anthropics/claude-code-action" in s]
    if not links:
        return ["no claude-code-action link steps found"]
    if "gh issue list" in _job_text(text):
        errors.append("an inline `gh issue list` assembly survives — use `growth dedup-context`")
    for n, i in enumerate(links, start=1):
        before = steps[i - 1] if i > 0 else ""
        args = _invocation(before)
        if args is None:
            errors.append(f"link {n}: the step before it does not run `python3 -m growth dedup-context`")
            continue
        out_dir = _flag(args, "--out-dir")
        if not out_dir or "--repo" not in args:
            errors.append(f"link {n}: dedup-context must run live (--repo) into an --out-dir")
            continue
        if "PYTHONPATH: tools/growth/src" not in before:
            errors.append(f"link {n}: the dedup step does not put tools/growth/src on PYTHONPATH")
        want = f"{env_name}: ${{{{ github.workspace }}}}/{out_dir}/{dedup.JSON_NAME}"
        if want not in steps[i]:
            errors.append(f"link {n}: env does not carry `{want}`")
        if f"{out_dir}/{dedup.MD_NAME}" not in before:
            errors.append(f"link {n}: the dedup step does not surface {out_dir}/{dedup.MD_NAME}")
    return errors


def test_every_link_gets_a_fresh_tested_dedup_context():
    assert wiring_errors(WORKFLOW.read_text(encoding="utf-8"), _dedup_env()) == []


def test_the_workflow_invocation_parses_and_runs_under_the_real_cli(tmp_path):
    text = WORKFLOW.read_text(encoding="utf-8")
    invocations = [a for a in map(_invocation, _steps(_job_text(text))) if a]
    assert len(invocations) == 3, "expected the head assembly + two tail refreshes"
    assert all(a == invocations[0] for a in invocations), "the three copies diverged"
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps([{"number": 597, "title": "Growth post: declined",
                                 "state": "open",
                                 "labels": ["channel:twitter", "disposition:declined"]}]))
    args = list(invocations[0])
    args[args.index("--repo") : args.index("--repo") + 2] = ["--snapshot", str(snap)]
    out = tmp_path / _flag(args, "--out-dir")
    args[args.index("--out-dir") + 1] = str(out)
    assert main(["dedup-context", *args]) == 0
    assert json.loads((out / dedup.JSON_NAME).read_text())["covered"][0]["number"] == 597


# --- negative controls: each pin fails on a tampered workflow ---------------------


def _tamper(old: str, new: str, count: int = 1) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert old in text, f"tamper anchor not found: {old[:60]!r}"
    return text.replace(old, new, count)


def test_a_link_without_the_context_env_is_caught():
    env = _dedup_env()
    line = f"          {env}: ${{{{ github.workspace }}}}/.reeve-growth-context/{dedup.JSON_NAME}\n"
    text = WORKFLOW.read_text(encoding="utf-8")
    # Drop it from the LAST link only (the terminal link a future edit forgets).
    head, sep, tail = text.rpartition(line)
    assert sep, "env line not found"
    errors = wiring_errors(head + tail, env)
    assert any(e.startswith("link 3: env") for e in errors), errors


def test_a_tail_link_without_its_refresh_is_caught():
    # Splice the link-2 refresh step out, leaving an unrelated step in its
    # place — the stale-list shape the refresh steps exist to prevent.
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index("      - name: Refresh the dedup context for chain link 2\n")
    end = text.index("      - name: Run via Anthropic (Claude, chain link 2)\n")
    text = text[:start] + "      - name: Unrelated\n        run: echo hi\n\n" + text[end:]
    errors = wiring_errors(text, _dedup_env())
    assert any(e.startswith("link 2:") and "dedup-context" in e for e in errors), errors


def test_an_inline_gh_listing_is_caught():
    text = _tamper("          cat .reeve-growth-context/dedup.md || true\n",
                   "          gh issue list --label growth-queue > .reeve-growth-context/dedup.md\n")
    assert any("gh issue list" in e for e in wiring_errors(text, _dedup_env()))


def test_a_mismatched_out_dir_is_caught():
    text = _tamper("--out-dir .reeve-growth-context;", "--out-dir .elsewhere;", count=3)
    errors = wiring_errors(text, _dedup_env())
    assert len([e for e in errors if "env does not carry" in e]) == 3, errors


def test_a_renamed_server_env_var_is_caught():
    # If queue_mcp.py renamed its env var, every link would be unwired.
    errors = wiring_errors(WORKFLOW.read_text(encoding="utf-8"), "GROWTHQ_RENAMED")
    assert len(errors) == 3, errors


@pytest.mark.parametrize("missing", ["--repo", "--out-dir"])
def test_a_snapshot_or_dirless_invocation_is_caught(missing):
    text = WORKFLOW.read_text(encoding="utf-8")
    if missing == "--repo":
        text = text.replace('--repo "$GITHUB_REPOSITORY"', '--snapshot fixture.json')
    else:
        text = text.replace("--out-dir .reeve-growth-context", "")
    assert any("--repo" in e for e in wiring_errors(text, _dedup_env()))
