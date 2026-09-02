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
  plumbing, and each must carry all three files: a builder that drops
  ``reeve-greenlights.ndjson`` from its tree silently deletes every precedent
  record the other one pushed (that is the roll-up amendment this issue
  shipped);
- **least privilege** — the observer holds no provider secret and pushes with
  ``github.token``; the secret-bearing agent job stays ``contents: read``.
"""

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
REEVE_YML = REPO_ROOT / ".github" / "workflows" / "reeve.yml"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# The three files the telemetry data branch carries.
DATA_BRANCH_FILES = ("log.ndjson", "REPORT.md", "reeve-greenlights.ndjson")


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


def _assert_builder_carries_all_three_files(text: str, where: str) -> None:
    """Both branch builders name all three files in the mktree they build —
    structural, not a substring: a file merely *mentioned* elsewhere (the seed
    fetch) still vanishes from the branch when its mktree entry is dropped."""
    for name in DATA_BRANCH_FILES:
        entry = f"blob %s\\t{name}\\n"
        assert entry in text, (
            f"{where} the data-branch tree no longer carries a mktree entry "
            f"for {name} — a builder that drops it silently deletes the "
            "other's records from the telemetry branch")


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


def test_observe_rebuilds_the_three_file_branch():
    _assert_builder_carries_all_three_files(
        _jobs(REEVE_YML)["observe"], "reeve.yml's observe job:")


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


# --- ci.yml's roll-up ----------------------------------------------------------


def test_ci_roll_up_preserves_the_precedent_log():
    text = CI_YML.read_text(encoding="utf-8")
    # Seeds the live file from the branch's tip (the append-only discipline),
    # then names all three files in the tree it rebuilds.
    assert "FETCH_HEAD:telemetry/reeve-greenlights.ndjson" in text, (
        "ci.yml's roll-up no longer re-seeds the precedent log from the data "
        "branch's tip — without it, the mktree below hashes the default-branch "
        "seed and reverts whatever the observer appended")
    _assert_builder_carries_all_three_files(text, "ci.yml's roll-up:")


def test_roll_up_guard_fires_when_the_third_file_is_dropped():
    # NEGATIVE CONTROL (the standing rule: a check that cannot fail is
    # worthless): strip the precedent-log entry from the roll-up's mktree and
    # require the shared assertion to fail — the exact regression the guard
    # exists to catch, since a two-file tree silently deletes the records.
    text = CI_YML.read_text(encoding="utf-8")
    tampered = text.replace(
        "100644 blob %s\\treeve-greenlights.ndjson\\n", "", 1)
    assert tampered != text, (
        "tamper target not found — the roll-up's mktree entry moved shape; "
        "update the mutation")
    try:
        _assert_builder_carries_all_three_files(tampered, "ci.yml's roll-up:")
    except AssertionError as exc:
        assert "reeve-greenlights.ndjson" in str(exc)
    else:
        raise AssertionError(
            "the roll-up guard did not react to a dropped precedent-log entry "
            "— it has been weakened into a restatement")
