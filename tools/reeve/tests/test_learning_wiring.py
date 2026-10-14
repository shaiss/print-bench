"""Workflow-wiring drift tests for the greenlight loop's learning half (issue #445).

The pure layers live in ``test_greenlights.py``; these pin the WIRING the
learning half depends on, the way ``test_config.py`` pins the conf↔cron
cadence pair — because each is a load-bearing duplication that a silent edit
could break with every test still green:

- **the context channel** — reeve.yml's greenlight job assembles the precedent
  digest into ``.reeve-context/precedent.md`` with trusted workflow code, and
  the ship steps still invoke the committed skill (``prompt: /reeve-greenlight``),
  so the digest reaches the drafter through a file the SKILL reads, never
  through an inline prompt the agent could widen;
- **the two branch builders** — reeve.yml's ``observe`` job and ci.yml's
  telemetry roll-up BOTH rebuild the ``telemetry`` data branch with git
  plumbing, and each must build the identical five-path tree: the three
  telemetry files (a builder that drops ``reeve-greenlights.ndjson`` silently
  deletes every precedent record the other one pushed — the roll-up amendment
  #445 shipped) plus the data-branch Vercel guard, hashed from the committed
  ``.github/data-branch-guard/`` files (without it, the project's Ignored Build
  Step finds no ``scripts/vercel-ignore-build.sh`` in the pushed tree, exits
  127, and Vercel builds a preview for every data push);
- **the seed reads** — no ``git show <tip>:<path> > <path>`` redirect may
  remain: the shell truncates ``<path>`` before git looks it up, which is how
  a tip without the precedent log pushed it as a 0-byte file. Every read is
  guarded by ``git cat-file -e`` and lands through a temp file and ``mv``, and
  both builders then run ``reeve greenlights-merge`` to put back any seed record
  the tip lost;
- **least privilege** — the observer holds no provider secret and pushes with
  ``github.token``; the secret-bearing agent job stays ``contents: read``.
"""

import json
import pathlib
import re
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
REEVE_YML = REPO_ROOT / ".github" / "workflows" / "reeve.yml"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
GUARD_DIR = REPO_ROOT / ".github" / "data-branch-guard"

# The two branch builders and the two read-only overlays, as (workflow, step).
ROLL_UP = (CI_YML, "Roll the record into the telemetry data branch")
OBSERVE = (REEVE_YML, "Derive and push records for newly-resolved rounds")
BUILDERS = (ROLL_UP, OBSERVE)
OVERLAYS = (
    (REEVE_YML, "Overlay live telemetry from the data branch"),
    (REEVE_YML, "Overlay the live precedent log from the data branch"),
)

# The three files the telemetry/ subtree carries.
DATA_BRANCH_FILES = ("log.ndjson", "REPORT.md", "reeve-greenlights.ndjson")

# The data branch's whole tree: each of its five paths -> the mktree entry
# (as the printf format literally reads in the workflow) that puts it there.
# The modes are part of the pin — the stub script must land executable.
DATA_BRANCH_TREE = {
    "telemetry/log.ndjson": "100644 blob %s\\tlog.ndjson\\n",
    "telemetry/REPORT.md": "100644 blob %s\\tREPORT.md\\n",
    "telemetry/reeve-greenlights.ndjson": "100644 blob %s\\treeve-greenlights.ndjson\\n",
    "vercel.json": "100644 blob %s\\tvercel.json\\n",
    "scripts/vercel-ignore-build.sh": "100755 blob %s\\tvercel-ignore-build.sh\\n",
}
# The two subtrees the root names beside vercel.json.
DATA_BRANCH_SUBTREES = {
    "scripts/": "040000 tree %s\\tscripts\\n",
    "telemetry/": "040000 tree %s\\ttelemetry\\n",
}
# Where each guard path's blob must come from: the committed file, hashed —
# never an inline copy a later edit could let drift from what is reviewed.
GUARD_SOURCES = {
    "vercel.json": "git hash-object -w .github/data-branch-guard/vercel.json",
    "scripts/vercel-ignore-build.sh":
        "git hash-object -w .github/data-branch-guard/vercel-ignore-build.sh",
}
# The committed vercel.json, exactly: git deployments of the data commit off,
# and an ignoreCommand that skips should a deployment still be attempted.
GUARD_CONFIG = {"git": {"deploymentEnabled": False}, "ignoreCommand": "exit 0"}

_MKTREE_ENTRY = re.compile(r"\d{6} (?:blob|tree) %s\\t[^\\'\"]+\\n")


def _jobs(path: pathlib.Path) -> dict[str, str]:
    """Split a workflow into top-level job blocks (name -> block text)."""
    jobs: dict[str, list[str]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        header = re.match(r"^  ([a-z][a-z0-9-]*):(?:\s.*)?$", line)
        if header:
            current = header.group(1)
            jobs[current] = []
        elif current is not None:
            if line and not line.startswith(" "):
                current = None  # back at a top-level key (name:/on:/jobs:)
            else:
                jobs[current].append(line)
    return {name: "\n".join(lines) for name, lines in jobs.items()}


def _step(path: pathlib.Path, name: str) -> str:
    """One step's block: its ``- name:`` line up to the next step or job."""
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        match = re.match(r"^(\s*)- name: (.*)$", line)
        if not match or match.group(2).strip() != name:
            continue
        indent = len(match.group(1))
        block = [line]
        for nxt in lines[i + 1:]:
            if nxt.strip():
                lead = len(nxt) - len(nxt.lstrip())
                if lead < indent or (lead == indent and nxt.lstrip().startswith("- ")):
                    break
            block.append(nxt)
        return "\n".join(block)
    raise AssertionError(f"{path.name} has no step named {name!r} — the pin moved")


def _code(block: str) -> str:
    """``block`` with full-line comments dropped and ``\\``-continuations joined,
    so a check reads the commands — not the prose that quotes the bad shape."""
    kept = [line for line in block.splitlines() if not line.lstrip().startswith("#")]
    return re.sub(r"[ \t]*\\\n\s*", " ", "\n".join(kept))


def _tree_problems(block: str) -> list[str]:
    """What the five-path tree a builder step builds is missing (``[]`` = whole).

    Structural, not a substring of the file: a path merely *mentioned* (a seed
    read, a comment) still vanishes from the branch when its mktree entry is
    dropped, and a guard blob hashed from anything but the committed file is an
    inline copy that can drift from what was reviewed.
    """
    code = _code(block)
    problems = [f"no mktree entry for {path}"
                for path, entry in DATA_BRANCH_TREE.items() if entry not in code]
    problems += [f"no mktree entry for the {path} subtree"
                 for path, entry in DATA_BRANCH_SUBTREES.items() if entry not in code]
    problems += [f"{path} is not hashed from .github/data-branch-guard/"
                 for path, source in GUARD_SOURCES.items() if source not in code]
    if "deploymentEnabled" in code or "hash-object -w --stdin" in code:
        problems.append("a guard file is inlined instead of hashed from the committed copy")
    return problems


def _assert_builds_the_five_path_tree(block: str, where: str) -> None:
    problems = _tree_problems(block)
    assert not problems, (
        f"{where} the data-branch tree is not the five-path tree: {problems} — a "
        "builder that drops a telemetry file silently deletes the other's records, "
        "and one that drops the guard costs a Vercel preview per data push")


# --- the context channel ------------------------------------------------------


def test_greenlight_job_assembles_the_precedent_context_with_trusted_code():
    job = _jobs(REEVE_YML)["greenlight"]
    assert "reeve greenlight-context" in job, (
        "reeve.yml's greenlight job no longer runs `reeve greenlight-context` — "
        "the drafter's precedent digest is assembled by trusted workflow code, "
        "never by the agent's own gather")
    assert ".reeve-context/precedent.md" in job, (
        "reeve.yml's context step no longer writes .reeve-context/precedent.md "
        "— the file the skill reads as its precedent evidence")
    # The overlay that feeds it: the live log comes from the data branch, not
    # the default-branch seed.
    assert "FETCH_HEAD:telemetry/reeve-greenlights.ndjson" in job


def test_ship_steps_still_invoke_the_committed_skill():
    # The digest must reach the drafter through the SKILL (which reads the
    # context file), not through an inline prompt — model-registry's drift
    # guard pins this line for containment reasons; here it pins the learning
    # half's channel: the prompt is unchanged by the context step.
    assert "prompt: /reeve-greenlight" in _jobs(REEVE_YML)["greenlight"]


# --- the observe job -----------------------------------------------------------


def test_observe_job_appends_after_the_drafter():
    jobs = _jobs(REEVE_YML)
    assert "observe" in jobs, "reeve.yml has no `observe` job — nothing records resolved rounds"
    job = jobs["observe"]
    assert "needs: greenlight" in job
    assert "reeve greenlight-append" in job
    # It re-reads the gates itself: a write-scope job must not inherit the
    # agent job's early-exit state.
    assert "reeve armed" in job


def test_observe_is_keyless_and_pushes_with_the_github_token():
    job = _jobs(REEVE_YML)["observe"]
    assert "secrets." not in job, (
        "reeve.yml's observe job references a provider secret — the observer "
        "is deterministic and keyless; a secret belongs in `greenlight` only")
    assert "PUSH_TOKEN: ${{ github.token }}" in job, (
        "the observe push no longer uses github.token — a GITHUB_TOKEN push "
        "triggers no workflow (the #481 property); a PAT would")


def test_observe_needs_write_only_contents_and_issues_read():
    job = _jobs(REEVE_YML)["observe"]
    assert "contents: write" in job  # the data-branch push
    assert "issues: write" not in job  # the observer comments nowhere


def test_the_agent_job_stays_contents_read():
    # Least privilege: the observer (not the agent) holds contents:write, so
    # the token the secret-bearing drafter step sees cannot push.
    job = _jobs(REEVE_YML)["greenlight"]
    assert "contents: read" in job
    assert "contents: write" not in job


# --- the two branch builders: the five-path tree -------------------------------


def test_both_builders_build_the_five_path_tree():
    for path, step in BUILDERS:
        _assert_builds_the_five_path_tree(_step(path, step), f"{path.name} ({step}):")


def test_both_builders_name_the_identical_tree():
    # Parity, path for path: the set of mktree entries each builder writes is
    # the same set, and it is exactly the five paths plus their two subtrees —
    # so neither builder can grow or lose a path the other does not.
    expected = set(DATA_BRANCH_TREE.values()) | set(DATA_BRANCH_SUBTREES.values())
    found = {f"{path.name} ({step})": set(_MKTREE_ENTRY.findall(_code(_step(path, step))))
             for path, step in BUILDERS}
    for where, entries in found.items():
        assert entries == expected, (
            f"{where} builds {sorted(entries)}; the data-branch tree is {sorted(expected)}")


def test_tree_guard_fires_on_each_dropped_path():
    # NEGATIVE CONTROL, one per path and builder (the standing rule: a check
    # that cannot fail is worthless): strip one mktree entry and require the
    # shared check to name exactly that loss — the regression it exists for.
    targets = dict(DATA_BRANCH_TREE)
    targets.update(DATA_BRANCH_SUBTREES)
    for path, step in BUILDERS:
        block = _step(path, step)
        assert not _tree_problems(block)
        for name, entry in targets.items():
            assert entry in block, (
                f"tamper target for {name} not found in {path.name} — the mktree "
                "entry moved shape; update the mutation")
            problems = _tree_problems(block.replace(entry, "", 1))
            assert problems and all(name in p for p in problems), (
                f"{path.name}: dropping the {name} entry was not caught ({problems})")


def test_guard_blobs_come_from_the_committed_files():
    for path, step in BUILDERS:
        block = _step(path, step)
        for name, source in GUARD_SOURCES.items():
            assert source in block, f"{path.name}: {name} not hashed from {source}"
            # NEGATIVE CONTROL: the same blob from an inline copy is refused.
            inline = block.replace(
                source, "printf '%s' \"$GUARD\" | git hash-object -w --stdin", 1)
            assert any("data-branch-guard" in p or "inlined" in p
                       for p in _tree_problems(inline)), (
                f"{path.name}: an inline {name} copy passed the tree check")


def _guard_config_problems(config: object) -> list[str]:
    """Why ``config`` is not the data-branch vercel.json (``[]`` = it is)."""
    if config != GUARD_CONFIG:
        return [f"vercel.json is {config!r}, not {GUARD_CONFIG!r}"]
    return []


def test_the_committed_guard_files_are_what_the_tree_needs():
    config = json.loads((GUARD_DIR / "vercel.json").read_text(encoding="utf-8"))
    assert not _guard_config_problems(config)
    # NEGATIVE CONTROLS: deployments left on, or the skip command dropped.
    assert _guard_config_problems({"git": {"deploymentEnabled": True},
                                   "ignoreCommand": "exit 0"})
    assert _guard_config_problems({"git": {"deploymentEnabled": False}})

    script = GUARD_DIR / "vercel-ignore-build.sh"
    assert script.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash\n")
    # Exit 0 is Vercel's "skip" — run it the way the Ignored Build Step does.
    assert subprocess.run(["bash", str(script)], check=False).returncode == 0
    # The COMMITTED mode, which is what a hashed blob's tree entry advertises
    # and a fresh checkout gets (docs-check.sh's shebang rule, issue #61).
    staged = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-s",
         ".github/data-branch-guard/vercel-ignore-build.sh"],
        capture_output=True, text=True, check=True).stdout
    assert staged.startswith("100755 "), (
        f"the guard script is not committed executable: {staged!r}")


# --- the seed reads ---------------------------------------------------------------

# A `git show`/`git cat-file -p|blob` whose stdout is redirected (`>`, not
# `2>`/`>&`/`>>`) — the target is captured so the check can ask where it went.
_SHOW_REDIRECT = re.compile(
    r"git\s+(?:show|cat-file\s+(?:-p|blob))\b[^|;&\n]*?(?<![0-9&>])>(?![&>])\s*"
    r"(?P<target>\"[^\"]*\"|'[^']*'|[^\s;|&)]+)")


def _truncating_seed_reads(text: str) -> list[str]:
    """Every git read redirected anywhere but a temp file renamed into place.

    The defect shape: ``git show FETCH_HEAD:<path> > <path>`` — the shell
    truncates ``<path>`` before git looks the path up, so a tip without it
    leaves a 0-byte seed. The safe shape writes a temp file and ``mv``s it onto
    the destination, so the destination is touched only once the read
    succeeded; a redirect straight onto a data-branch path, or onto anything
    never renamed afterwards, is reported.
    """
    code = _code(text)
    bad = []
    for match in _SHOW_REDIRECT.finditer(code):
        target = match.group("target")
        bare = target.strip("\"'")
        renamed = re.search(r"\bmv\s+" + re.escape(target) + r"\s+\S", code[match.end():])
        if bare in DATA_BRANCH_TREE or not renamed:
            bad.append(match.group(0))
    return bad


def test_no_truncating_seed_read_remains():
    for path in (CI_YML, REEVE_YML):
        bad = _truncating_seed_reads(path.read_text(encoding="utf-8"))
        assert not bad, (
            f"{path.name} still redirects a git read straight onto a file: {bad} — "
            "the shell truncates the committed seed before git looks the path up; "
            "guard with `git cat-file -e` and write through a temp file + mv")


def test_truncation_check_flags_the_shapes_it_replaced():
    # NEGATIVE CONTROLS: the three shapes the two workflows used to carry, each
    # of which emptied the checkout's seed on a tip without the path.
    replaced = (
        "git show FETCH_HEAD:telemetry/log.ndjson > telemetry/log.ndjson\n",
        "git show FETCH_HEAD:telemetry/REPORT.md  > telemetry/REPORT.md 2>/dev/null || true\n",
        "git show FETCH_HEAD:telemetry/reeve-greenlights.ndjson \\\n"
        "  > telemetry/reeve-greenlights.ndjson 2>/dev/null || true\n",
        "if git show FETCH_HEAD:telemetry/reeve-greenlights.ndjson \\\n"
        "    > telemetry/reeve-greenlights.ndjson 2>/dev/null; then\n",
        # A temp file that is never renamed is no better than a lost read.
        'git show "FETCH_HEAD:$f" > "$f.tip"\n',
    )
    for shape in replaced:
        assert _truncating_seed_reads(shape), f"not flagged: {shape!r}"
    # And the positive control: the guarded temp-file shapes now in use pass,
    # as does the prose that quotes the bad shape in a comment.
    for shape in (
        'git show "${src}:$1" > "$1.seed"\nmv "$1.seed" "$1"\n',
        'git show FETCH_HEAD:x \\\n  > x.tip\nmv x.tip x\n',
        "# a bare `git show FETCH_HEAD:<path> > <path>` truncates the seed\n",
        "git show --pretty=format: --name-only HEAD | while IFS= read -r f; do\n",
    ):
        assert not _truncating_seed_reads(shape), f"flagged: {shape!r}"


def _unguarded(block: str) -> bool:
    """Whether a step that fetches the data branch and reads files out of it
    does so without a ``git cat-file -e FETCH_HEAD:<path>`` guard — the
    builders read through ``git show "${src}:<path>"``, so the read itself need
    not spell FETCH_HEAD; fetching and showing is what makes it a tip read."""
    code = _code(block)
    reads_tip = re.search(r"git\s+fetch\b", code) and re.search(r"git\s+show\b", code)
    return bool(reads_tip) and not re.search(r'git cat-file -e "?FETCH_HEAD:', code)


def test_every_seed_read_is_guarded_by_cat_file():
    for path, step in BUILDERS + OVERLAYS:
        block = _step(path, step)
        assert re.search(r"git\s+fetch\b", block) and re.search(r"git\s+show\b", block), (
            f"{path.name} ({step}) no longer reads the tip — the pin moved")
        assert not _unguarded(block), (
            f"{path.name} ({step}) reads the tip without `git cat-file -e` — a "
            "missing path must keep the committed seed, never fail or truncate it")
        # NEGATIVE CONTROL: the same step with its guard stripped is caught.
        stripped = re.sub(r'git cat-file -e "?FETCH_HEAD:[^ ]*', "true", block)
        assert _unguarded(stripped), f"{path.name} ({step}): a dropped guard passed"


# --- the two branch builders: restoring the lost seed records ---------------------


def test_both_builders_restore_lost_seed_records_after_seeding():
    runs = {
        ROLL_UP: "PYTHONPATH=tools/reeve/src python3 -m reeve greenlights-merge",
        OBSERVE: "reeve greenlights-merge",
    }
    for (path, step), invocation in runs.items():
        code = _code(_step(path, step))
        where = f"{path.name} ({step})"
        assert "gl=telemetry/reeve-greenlights.ndjson" in code, where
        # The committed seed is set aside BEFORE any attempt overwrites it.
        aside = code.find('cp "$gl" "$gl_seed"')
        assert -1 < aside < code.find("for attempt"), (
            f"{where}: the seed is not set aside before the retry loop")
        merge = code.find(f'{invocation} --tip "$gl" --seed "$gl_seed" --out "$gl"')
        assert merge > -1, f"{where} no longer runs `{invocation}` over the seeded log"
        # After the tip is seeded, before the tree is built.
        assert code.find('seed_file "$gl"') < merge < code.find("git mktree"), (
            f"{where}: the merge does not sit between the seed and the tree")
        # A tip the strict parser rejects is warned about, never fatal on its
        # own and never overwritten (the CLI writes nothing on a parse error).
        assert re.search(r"if ! [^\n]*greenlights-merge[^\n]*; then\s+echo \"::warning::",
                         code), f"{where}: a failed merge is not a ::warning::"


def test_the_observer_pushes_a_repair_even_with_nothing_appended():
    # Without this, a tip that lost the seed records stays without them in
    # every observe run that resolves no new round.
    code = _code(_step(*OBSERVE))
    assert '[ "${appended:-0}" = "0" ] && [ "${restored:-0}" = "0" ]' in code
