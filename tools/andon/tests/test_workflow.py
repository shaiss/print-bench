"""Pins on .github/workflows/andon.yml — the tool and its workflow must agree.

Regex/substring pins over the raw text (the model-registry drift guard's
parsing model; no YAML library), each with a tamper negative where the
pin's own regex is cheap to invert.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from andon import policy

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "andon.yml"

DEFAULT_BRANCH_PIN = "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)"
CORD_GATE_LEG = "AI_ANDON_CORD != 'pulled'"
CRON_LINE_RE = re.compile(r"^\s*- cron: '43 \* \* \* \*'\s*$", re.MULTILINE)


@pytest.fixture(scope="module")
def text() -> str:
    assert WORKFLOW.is_file(), f"{WORKFLOW} is missing"
    return WORKFLOW.read_text(encoding="utf-8")


def _job_block(text: str, job: str) -> str:
    m = re.search(rf"^  {re.escape(job)}:[ \t]*\n(.*?)(?=^  [a-z][a-z0-9-]*:[ \t]*$|\Z)",
                  text, re.MULTILINE | re.DOTALL)
    assert m, f"job {job!r} not found"
    return m.group(1)


def _job_if(block: str) -> str:
    m = re.search(r"^    if: (.+?)$", block, re.MULTILINE)
    assert m, "job has no `if:`"
    return m.group(1)


# (i) the reconcile job runs on the default branch AND while the cord is pulled

def test_reconcile_job_pins_the_default_branch(text):
    assert DEFAULT_BRANCH_PIN in _job_if(_job_block(text, "reconcile"))


def test_reconcile_job_is_never_gated_on_the_cord(text):
    # The reconciler must run WHILE pulled (to open) and while released (to
    # close); a cord leg here would make the issue impossible to open.
    assert CORD_GATE_LEG not in _job_block(text, "reconcile")
    assert "vars.AI_ANDON_CORD ==" not in _job_if(_job_block(text, "reconcile"))


def test_cord_gate_pin_would_catch_a_gated_reconciler(text):
    tampered = text.replace(
        f"    if: {DEFAULT_BRANCH_PIN}",
        f"    if: {DEFAULT_BRANCH_PIN} && vars.{CORD_GATE_LEG}", 1)
    assert tampered != text
    assert CORD_GATE_LEG in _job_block(tampered, "reconcile")


# (ii) permissions: workflow-level contents: read only; the job adds issues: write

def test_workflow_level_permissions_are_contents_read_only(text):
    m = re.search(r"^permissions:\n((?:  \S.*\n)+)", text, re.MULTILINE)
    assert m, "no top-level permissions block"
    keys = [ln.split(":")[0].strip() for ln in m.group(1).splitlines()]
    values = [ln.split("#")[0].strip() for ln in m.group(1).splitlines()]
    assert keys == ["contents"]
    assert values == ["contents: read"]


def test_reconcile_job_declares_issues_write(text):
    block = _job_block(text, "reconcile")
    m = re.search(r"^    permissions:\n((?:      \S.*\n)+)", block, re.MULTILINE)
    assert m, "reconcile job has no permissions block"
    perms = {ln.split(":")[0].strip(): ln.split(":", 1)[1].split("#")[0].strip()
             for ln in m.group(1).splitlines()}
    assert perms == {"contents": "read", "issues": "write"}


# (iii) exactly one cron literal, hourly at :43

def test_exactly_one_cron_literal_at_43_past(text):
    assert len(CRON_LINE_RE.findall(text)) == 1
    assert len(re.findall(r"^\s*- cron:", text, re.MULTILINE)) == 1


def test_cron_pin_would_catch_a_moved_minute(text):
    tampered = text.replace("- cron: '43 * * * *'", "- cron: '17 * * * *'")
    assert tampered != text
    assert len(CRON_LINE_RE.findall(tampered)) == 0


# (iv) the github-script literals equal policy's constants

def _script_const(text: str, name: str) -> str:
    m = re.search(rf"const {name} = '([^']*)';", text)
    assert m, f"const {name} not found in the workflow script"
    return m.group(1)


@pytest.mark.parametrize("name, expected", [
    ("MARKER", policy.MARKER),
    ("LABEL", policy.LABEL),
    ("NOTICE_LABEL", policy.NOTICE_LABEL),
    ("TITLE", policy.TITLE),
])
def test_script_literals_match_policy_constants(text, name, expected):
    assert _script_const(text, name) == expected


def test_literal_pin_would_catch_a_renamed_marker(text):
    tampered = text.replace("const MARKER = '<!-- andon-cord -->'", "const MARKER = '<!-- andon -->'")
    assert tampered != text
    assert _script_const(tampered, "MARKER") != policy.MARKER


def test_issue_is_created_with_exactly_the_two_labels(text):
    assert "labels: [LABEL, NOTICE_LABEL]" in text
    assert "needs-decision" not in text.split("script: |", 1)[1]


# (v) keyless: no secrets anywhere

def test_no_secrets_reference_anywhere(text):
    assert "secrets." not in text


def test_no_agent_or_model_anywhere(text):
    assert "claude-code-action" not in text
    assert re.search(r"--model\s", text) is None


# (vi) the decide step invokes the tool the way the tests exercise it

def test_decide_step_invocation(text):
    block = _job_block(text, "reconcile")
    assert "python3 -m andon decide" in block
    assert '--gh-output "$GITHUB_OUTPUT"' in block
    assert '--cord "$CORD"' in block
    assert '--repo "$GITHUB_REPOSITORY"' in block
    # The variable is env-indirected, never interpolated into a run: block.
    assert re.search(r"CORD: \$\{\{ vars\.AI_ANDON_CORD \}\}", block)
    run_blocks = re.findall(r"run: \|\n((?:          .*\n)+)", block)
    assert run_blocks and all("${{" not in rb for rb in run_blocks)


def test_write_step_is_skipped_on_none_and_on_dry_run(text):
    assert "if: steps.decide.outputs.action != 'none' && inputs.dry_run != true" in text
    assert "if: steps.decide.outputs.action == 'none' || inputs.dry_run == true" in text


def test_concurrency_group_serialises_the_reconciler(text):
    assert re.search(r"^concurrency:\n(?:  #.*\n)*  group: andon\n  cancel-in-progress: false", text, re.MULTILINE)


def test_notice_wording_avoids_the_drift_guard_pinned_phrases(text):
    # Whole-file pins the model-registry drift guard applies to routine
    # workflows; this one is not a routine, but keep its notices in the
    # same family so a future enumerator never trips on it.
    assert "::notice::the configured provider" not in text
    assert "::notice::no key is set for ANY provider" not in text
