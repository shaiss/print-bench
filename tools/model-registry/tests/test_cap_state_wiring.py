"""Drift guard: every MCP write server's walk-spanning cap is wired on every step that launches it.

Every issue-writing MCP server the routines run (scout, wright, growth-queue,
reeve-signoff, adoption-assessor, growth-twitter, the Oracle) bounds its writes
per run, and a chain walk launches the server once PER LINK — each link is its
own claude-code-action step, so each gets a fresh server process. The cap
therefore lives in a state file every link step of the job shares, named by a
per-server env var the server declares as a module-level literal
(``CAP_STATE_ENV = "SCOUT_CAP_STATE"`` and siblings — the #549 class; the
Oracle's was the last in-process counter). The server fails CLOSED when that
env var is missing in an unattended run, which is the right runtime posture
and exactly why a wiring slip is quiet: a link step that forgets the env is not
a red run, it is a link that silently files nothing — and nothing caught it
before merge, because every check here passed on the YAML.

This guard closes that pre-merge. For every workflow step whose ``claude_args``
carries ``--mcp-config <json>`` it resolves the server script(s) that config
launches, reads the script's ``CAP_STATE_ENV`` literal (by AST, never a grep
that a comment could satisfy), and asserts:

* the step's own ``env:`` sets that variable — a commented-out line does not
  count;
* the value is a ``${{ runner.temp }}/…`` path — runner.temp is fresh per job,
  which is what makes the count run-scoped (a fixed path could outlive the
  job on a reused runner and pin the cap shut for every later run);
* every step in the same job that launches the same server uses the
  IDENTICAL value — two paths are two counters, and the walk is uncapped
  again across the split;
* every server a workflow launches declares a ``CAP_STATE_ENV`` at all, unless
  it is named in ``UNCAPPED_SERVERS`` with a reason (empty today: every write
  server here is capped) — so a server that regressed to an in-process
  counter cannot make this guard vacuous for itself.

Everything is derived from the live tree — the servers' own literals, the
workflows' own steps — never a hand-kept table of env names, so a new server or
a new link is covered the day it lands. Each rule has a negative control below
that tampers the live text and watches the rule fire.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re

import pytest

from test_workflow_drift import (
    REPO_ROOT,
    _all_workflow_texts,
    _job_blocks,
    _job_steps,
    _without_comments,
)

# Servers launched via --mcp-config that legitimately carry no walk-spanning
# cap, keyed by the script path relative to the repo root, each with the
# reason. Empty today — every write server here is capped — and an entry is a
# reviewed decision, not a way to silence the guard.
UNCAPPED_SERVERS: dict[str, str] = {}

RUNNER_TEMP_PREFIX = "${{ runner.temp }}/"

_MCP_CONFIG = re.compile(r"--mcp-config[ =]+(\"[^\"]+\"|'[^']+'|\S+)")
_STEP_ENV = re.compile(r"^        env:[ \t]*$")
_ENV_ENTRY = re.compile(r"^          ([A-Za-z_][A-Za-z0-9_]*):[ \t]*(.*?)[ \t]*$")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _step_label(step: str) -> str:
    """The step's `id:` (stable) or, failing that, its `name:` — for messages."""
    sid = re.search(r"^        id:[ \t]*(\S+)", step, re.MULTILINE)
    if sid:
        return sid.group(1)
    name = re.match(r"name:[ \t]*(.+)", step)
    return name.group(1).strip() if name else "<unnamed step>"


def _step_env(step: str) -> dict[str, str]:
    """The step-level `env:` mapping (8-space key, 10-space entries) of a
    comment-stripped step chunk. Job- and workflow-level env are deliberately
    not read: the runner context a run-scoped path needs exists only at step
    level, so that is where the house pattern puts it."""
    env: dict[str, str] = {}
    lines = step.splitlines()
    for i, line in enumerate(lines):
        if not _STEP_ENV.match(line):
            continue
        for entry in lines[i + 1:]:
            if not entry.strip():
                continue
            indent = len(entry) - len(entry.lstrip(" "))
            if indent <= 8:
                break
            m = _ENV_ENTRY.match(entry)
            if m:
                # A plain scalar's trailing ` # …` is a YAML comment, not value.
                value = m.group(2)
                if value[:1] not in "\"'":
                    value = re.sub(r"[ \t]+#.*$", "", value)
                env[m.group(1)] = _unquote(value)
        break
    return env


def _mcp_steps(texts: dict[str, str]) -> list[dict]:
    """Every step, in every job of every workflow, whose (comment-stripped)
    text passes `--mcp-config` — with the config path(s) and its env."""
    found: list[dict] = []
    for workflow, text in sorted(texts.items()):
        if not re.search(r"^jobs:[ \t]*$", text, re.MULTILINE):
            continue
        for job, block in _job_blocks(text).items():
            for step in _job_steps(_without_comments(block)):
                configs = [_unquote(c) for c in _MCP_CONFIG.findall(step)]
                if not configs:
                    continue
                found.append({
                    "workflow": workflow,
                    "job": job,
                    "step": _step_label(step),
                    "configs": configs,
                    "env": _step_env(step),
                })
    return found


def _server_scripts(config: str, root: pathlib.Path) -> list[pathlib.Path]:
    """The Python server script(s) an --mcp-config JSON launches, resolved
    against the checkout root (the workflow's cwd). A config that cannot be
    read, or launches no script this guard can inspect, raises — an
    unresolvable server must fail loudly, never be silently skipped."""
    path = root / config
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"cannot read --mcp-config {config}: {e}") from e
    servers = data.get("mcpServers") or {}
    if not servers:
        raise ValueError(f"--mcp-config {config} declares no mcpServers")
    scripts: list[pathlib.Path] = []
    for name, spec in servers.items():
        argv = [spec.get("command", "")] + list(spec.get("args") or [])
        py = [a for a in argv if isinstance(a, str) and a.endswith(".py")]
        if not py:
            raise ValueError(
                f"--mcp-config {config}: server {name!r} launches no .py script "
                "this guard can read its CAP_STATE_ENV from")
        scripts.extend(root / p for p in py)
    return scripts


def _cap_state_env(script: pathlib.Path) -> str | None:
    """The server's module-level `CAP_STATE_ENV = "<VAR>"` literal, or None.
    Read by AST, so only a real top-level assignment counts — a comment or a
    docstring that merely mentions the name does not."""
    try:
        tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
    except (OSError, SyntaxError) as e:
        raise ValueError(f"cannot parse MCP server {script}: {e}") from e
    for node in tree.body:
        targets: list[ast.expr] = []
        value = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        for t in targets:
            if (isinstance(t, ast.Name) and t.id == "CAP_STATE_ENV"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)):
                return value.value
    return None


def _cap_wiring_errors(texts: dict[str, str], root: pathlib.Path = REPO_ROOT,
                       uncapped: dict[str, str] | None = None) -> list[str]:
    """Every wiring defect across `texts` — empty when the tree is clean.
    Pure over its inputs so the negative controls can hand it tampered
    workflow text or a synthesized server tree."""
    uncapped = UNCAPPED_SERVERS if uncapped is None else uncapped
    errors: list[str] = []
    # (workflow, job, var) → {step label: value} for the same-path rule.
    groups: dict[tuple[str, str, str], dict[str, str]] = {}
    for step in _mcp_steps(texts):
        where = f"{step['workflow']} job `{step['job']}` step `{step['step']}`"
        for config in step["configs"]:
            try:
                scripts = _server_scripts(config, root)
            except ValueError as e:
                errors.append(f"{where}: {e}")
                continue
            for script in scripts:
                rel = script.relative_to(root).as_posix() if script.is_relative_to(root) else str(script)
                try:
                    var = _cap_state_env(script)
                except ValueError as e:
                    errors.append(f"{where}: {e}")
                    continue
                if var is None:
                    if rel not in uncapped:
                        errors.append(
                            f"{where}: launches {rel}, which declares no "
                            "module-level CAP_STATE_ENV — a write server's "
                            "per-run cap must count from a state file every "
                            "link step shares (the #549 mechanism), or the "
                            "server must be named in UNCAPPED_SERVERS with a "
                            "reason")
                    continue
                value = step["env"].get(var)
                if not value:
                    errors.append(
                        f"{where}: launches {rel}, whose cap counts from "
                        f"${var}, but the step's env does not set {var} — the "
                        "server fails closed unattended, so this link would "
                        "silently file nothing")
                    continue
                if not value.startswith(RUNNER_TEMP_PREFIX):
                    errors.append(
                        f"{where}: {var} is {value!r}, not a "
                        f"{RUNNER_TEMP_PREFIX}… path — runner.temp is fresh "
                        "per job, which is what keeps the count run-scoped")
                groups.setdefault((step["workflow"], step["job"], var), {})[step["step"]] = value
    for (workflow, job, var), by_step in sorted(groups.items()):
        if len(set(by_step.values())) > 1:
            errors.append(
                f"{workflow} job `{job}`: link steps set {var} to different "
                f"paths {by_step} — every link of one walk must count from the "
                "SAME state file, or the cap resets across the split")
    return errors


def _cap_groups(texts: dict[str, str]) -> dict[tuple[str, str, str], list[str]]:
    """(workflow, job, var) → the step labels that set it — the live wiring's
    shape, for the coverage pins and to derive the negative controls."""
    out: dict[tuple[str, str, str], list[str]] = {}
    for step in _mcp_steps(texts):
        for config in step["configs"]:
            for script in _server_scripts(config, REPO_ROOT):
                var = _cap_state_env(script)
                if var:
                    out.setdefault((step["workflow"], step["job"], var), []).append(step["step"])
    return out


def _replace_in_step(text: str, job: str, step_label: str, old: str, new: str) -> str:
    """`text` with `old` replaced by `new` inside ONE step's chunk only —
    how a single link is tampered without touching its siblings."""
    block = _job_blocks(text)[job]
    for chunk in re.split(r"\n      - ", block):
        if _step_label(_without_comments(chunk)) == step_label and old in chunk:
            tampered = block.replace(chunk, chunk.replace(old, new, 1), 1)
            return text.replace(block, tampered, 1)
    raise AssertionError(f"tamper target {old!r} not found in {job}/{step_label} — "
                         "the fixture is stale")


# --- positive cases ---------------------------------------------------------


def test_every_mcp_step_wires_its_servers_cap_state():
    errors = _cap_wiring_errors(_all_workflow_texts())
    assert not errors, "cap-state wiring defects:\n  " + "\n  ".join(errors)


def test_guard_inspects_every_mcp_config_step():
    # The guard must not pass by not looking: the steps it parsed are exactly
    # the steps whose live (comment-stripped) text names --mcp-config.
    texts = _all_workflow_texts()
    expected = sum(len(_MCP_CONFIG.findall(_without_comments(t))) for t in texts.values())
    seen = sum(len(s["configs"]) for s in _mcp_steps(texts))
    assert expected > 0, "no workflow launches an MCP server — the guard is vacuous"
    assert seen == expected, (
        f"parsed {seen} --mcp-config use(s) but the workflows carry {expected} — "
        "a step the parser cannot see is a step the guard cannot check")


def test_every_launched_server_declares_its_cap_state_env():
    # Every server script any workflow launches is capped — none relies on
    # the UNCAPPED_SERVERS exemption today.
    scripts = {script
               for step in _mcp_steps(_all_workflow_texts())
               for config in step["configs"]
               for script in _server_scripts(config, REPO_ROOT)}
    assert scripts, "no MCP server scripts found"
    bare = sorted(str(s.relative_to(REPO_ROOT)) for s in scripts if _cap_state_env(s) is None)
    assert not bare, f"server(s) with no CAP_STATE_ENV: {bare}"


def test_oracle_walk_is_inside_the_guard():
    # The Oracle's one-review cap was the last in-process counter; every one
    # of its seven link steps (3 Anthropic + 4 GLM) now names the same file.
    assert _cap_state_env(REPO_ROOT / ".claude/skills/oracle-review/oracle_mcp.py") == "ORACLE_CAP_STATE"
    texts = _all_workflow_texts()
    links = _cap_groups(texts).get(("oracle.yml", "oracle", "ORACLE_CAP_STATE"))
    assert links == ["a1", "a2", "a3", "g1", "g2", "g3", "g4"], links
    wired = {s["step"]: s["env"].get("ORACLE_CAP_STATE")
             for s in _mcp_steps({"oracle.yml": texts["oracle.yml"]})}
    assert set(wired.values()) == {"${{ runner.temp }}/oracle-posts"}, wired


# --- negative controls ------------------------------------------------------


def test_guard_rejects_a_link_that_forgot_the_env_in_every_walk():
    # NEGATIVE CONTROL, derived from the live tree: in EVERY (workflow, job)
    # walk, dropping the cap env from its last link must fail on that link —
    # the shape of a new provider's tail step pasted in without it.
    texts = _all_workflow_texts()
    groups = _cap_groups(texts)
    assert groups, "no cap-state groups found — the fixture is stale"
    for (workflow, job, var), steps in sorted(groups.items()):
        tampered = dict(texts)
        env_line = re.search(rf"^          {var}:.*$", texts[workflow], re.MULTILINE).group(0)
        tampered[workflow] = _replace_in_step(texts[workflow], job, steps[-1],
                                              env_line + "\n", "")
        errors = _cap_wiring_errors(tampered)
        assert any(f"step `{steps[-1]}`" in e and f"does not set {var}" in e
                   for e in errors), (workflow, job, errors)


def test_guard_rejects_a_commented_out_env_line():
    # NEGATIVE CONTROL: a comment that quotes the env line wires nothing.
    texts = _all_workflow_texts()
    line = "          ORACLE_CAP_STATE: ${{ runner.temp }}/oracle-posts"
    texts["oracle.yml"] = _replace_in_step(texts["oracle.yml"], "oracle", "g2",
                                           line, "          # ORACLE_CAP_STATE: ${{ runner.temp }}/oracle-posts")
    errors = _cap_wiring_errors(texts)
    assert any("step `g2`" in e and "does not set ORACLE_CAP_STATE" in e for e in errors), errors


def test_guard_rejects_a_link_on_a_different_path():
    # NEGATIVE CONTROL: two paths are two counters — the walk is uncapped
    # across the split even though every link "has" the env.
    texts = _all_workflow_texts()
    texts["oracle.yml"] = _replace_in_step(
        texts["oracle.yml"], "oracle", "g3",
        "${{ runner.temp }}/oracle-posts", "${{ runner.temp }}/oracle-posts-2")
    errors = _cap_wiring_errors(texts)
    assert any("different paths" in e and "ORACLE_CAP_STATE" in e for e in errors), errors


def test_guard_rejects_a_path_outside_runner_temp():
    # NEGATIVE CONTROL: identical on every link, but not run-scoped.
    texts = _all_workflow_texts()
    texts["oracle.yml"] = texts["oracle.yml"].replace(
        "${{ runner.temp }}/oracle-posts", "/tmp/oracle-posts")
    errors = _cap_wiring_errors(texts)
    assert sum("not a ${{ runner.temp }}/" in e for e in errors) == 7, errors


def _synth_tree(tmp_path: pathlib.Path, server_src: str) -> tuple[pathlib.Path, dict[str, str]]:
    """A minimal checkout: one config, one server, one one-link workflow."""
    skill = tmp_path / ".claude" / "skills" / "rogue"
    skill.mkdir(parents=True)
    (skill / "rogue_mcp.py").write_text(server_src, encoding="utf-8")
    (skill / "rogue-mcp.json").write_text(json.dumps({"mcpServers": {"rogue": {
        "command": "python3", "args": [".claude/skills/rogue/rogue_mcp.py"]}}}),
        encoding="utf-8")
    workflow = (
        "name: rogue\n"
        "jobs:\n"
        "  rogue:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: Rogue (chain link 1)\n"
        "        id: r1\n"
        "        env:\n"
        "          GITHUB_TOKEN: ${{ github.token }}\n"
        "        uses: anthropics/claude-code-action@v1\n"
        "        with:\n"
        "          claude_args: --mcp-config .claude/skills/rogue/rogue-mcp.json --allowedTools \"mcp__rogue__x\"\n"
    )
    return tmp_path, {"rogue.yml": workflow}


def test_guard_rejects_a_server_with_no_cap_state_env(tmp_path):
    # NEGATIVE CONTROL: a server that regressed to an in-process counter (no
    # CAP_STATE_ENV literal — a comment naming it does not count) must not
    # make the guard vacuous for itself.
    root, texts = _synth_tree(tmp_path, (
        "# CAP_STATE_ENV = \"ROGUE_CAP_STATE\"  (a comment, not a declaration)\n"
        "_posted_this_run = 0\n"))
    errors = _cap_wiring_errors(texts, root, uncapped={})
    assert any("declares no module-level CAP_STATE_ENV" in e for e in errors), errors
    # ...and the reviewed exemption is the one way out.
    assert _cap_wiring_errors(texts, root, uncapped={
        ".claude/skills/rogue/rogue_mcp.py": "selftest exemption"}) == []


def test_guard_reads_a_synthesized_servers_env_name(tmp_path):
    # The env name comes from the server, not a table: a new server declaring
    # ROGUE_CAP_STATE is enforced on its launching step the day it lands.
    root, texts = _synth_tree(tmp_path, 'CAP_STATE_ENV = "ROGUE_CAP_STATE"\n')
    errors = _cap_wiring_errors(texts, root, uncapped={})
    assert any("does not set ROGUE_CAP_STATE" in e for e in errors), errors
    wired = {name: text.replace(
        "          GITHUB_TOKEN: ${{ github.token }}\n",
        "          GITHUB_TOKEN: ${{ github.token }}\n"
        "          ROGUE_CAP_STATE: ${{ runner.temp }}/rogue\n")
        for name, text in texts.items()}
    assert _cap_wiring_errors(wired, root, uncapped={}) == []


def test_guard_rejects_an_unresolvable_config(tmp_path):
    # NEGATIVE CONTROL: a config the guard cannot read fails loudly — a
    # missing server must never be silently skipped as "uncapped".
    root, texts = _synth_tree(tmp_path, 'CAP_STATE_ENV = "ROGUE_CAP_STATE"\n')
    texts = {n: t.replace("rogue-mcp.json", "missing-mcp.json") for n, t in texts.items()}
    errors = _cap_wiring_errors(texts, root, uncapped={})
    assert any("cannot read --mcp-config" in e for e in errors), errors


def test_guard_ignores_an_mcp_config_quoted_in_a_comment(tmp_path):
    # NEGATIVE CONTROL for the comment stripping: the workflows explain their
    # tool surface in comments ("served by x_mcp.py via --mcp-config …"), and
    # a quoted or commented-out launch is not a launch — it must neither be
    # checked nor fail the guard on a config that no longer exists.
    root, texts = _synth_tree(tmp_path, 'CAP_STATE_ENV = "ROGUE_CAP_STATE"\n')
    texts = {n: t.replace(
        "          claude_args: --mcp-config .claude/skills/rogue/rogue-mcp.json",
        "          # claude_args: --mcp-config .claude/skills/gone/gone-mcp.json\n"
        "          claude_args: --allowedTools Read")
        for n, t in texts.items()}
    assert _mcp_steps(texts) == []
    assert _cap_wiring_errors(texts, root, uncapped={}) == []


@pytest.mark.parametrize("src", [
    'CAP_STATE_ENV = "X_CAP_STATE"\n',
    'CAP_STATE_ENV: str = "X_CAP_STATE"\n',
])
def test_cap_state_env_reader_accepts_a_module_level_literal(tmp_path, src):
    p = tmp_path / "s.py"
    p.write_text(src, encoding="utf-8")
    assert _cap_state_env(p) == "X_CAP_STATE"


@pytest.mark.parametrize("src", [
    '# CAP_STATE_ENV = "X_CAP_STATE"\n',
    '"""CAP_STATE_ENV = "X_CAP_STATE" in a docstring"""\n',
    'def f():\n    CAP_STATE_ENV = "X_CAP_STATE"\n',
    'CAP_STATE_ENV = os.environ["X"]\n',
])
def test_cap_state_env_reader_rejects_a_non_declaration(tmp_path, src):
    # NEGATIVE CONTROL: only a real top-level string assignment declares one.
    p = tmp_path / "s.py"
    p.write_text(src, encoding="utf-8")
    assert _cap_state_env(p) is None
