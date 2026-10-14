"""provenance.yml pinned to the tool (the andon test_workflow precedent).

Owner: H6. Regex/substring pins over the raw text — no YAML library (the
model-registry drift guard's parsing model) — each with a tamper negative
where the pin's own reader is cheap to invert. Acceptance criteria are the
docstrings (docs/provenance.md §Workflow, the critique round's items 3, 5,
12, 13, 17, 20, 21).
"""

from __future__ import annotations

import re

import pytest

from conftest import REPO
from provenance import cli, conf

WORKFLOW = REPO / ".github" / "workflows" / "provenance.yml"
GATE_IF = "github.event_name == 'workflow_dispatch' || vars.PROVENANCE_ENABLED == 'true'"
DEFAULT_BRANCH_PIN = "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)"
HARVEST_STEPS = [
    "Check out the default branch (full history, no credentials)",
    "Plan",
    "Declare the evidence intent",
    "Declare the derived intent",
    "Publish",
    "Checkpoint the evidence tip",
    "Checkpoint the derived tip",
    "Verdict",
    "Summary",
]


@pytest.fixture(scope="module")
def text() -> str:
    assert WORKFLOW.is_file(), f"{WORKFLOW} is missing"
    return WORKFLOW.read_text(encoding="utf-8")


# --- a tiny reader for the shapes this file uses -----------------------------

def _jobs_section(text: str) -> str:
    m = re.search(r"^jobs:\n(.*)\Z", text, re.MULTILINE | re.DOTALL)
    assert m, "no jobs: section"
    return m.group(1)


def job_names(text: str) -> list[str]:
    return re.findall(r"^  ([a-z][a-z0-9-]*):[ \t]*$", _jobs_section(text), re.MULTILINE)


def job_block(text: str, job: str) -> str:
    m = re.search(rf"^  {re.escape(job)}:[ \t]*\n(.*?)(?=^  [a-z][a-z0-9-]*:[ \t]*$|\Z)",
                  _jobs_section(text), re.MULTILINE | re.DOTALL)
    assert m, f"job {job!r} not found"
    return m.group(1)


def job_key(block: str, key: str) -> str:
    m = re.search(rf"^    {re.escape(key)}: (.+?)$", block, re.MULTILINE)
    assert m, f"job has no `{key}:`"
    return m.group(1).strip()


def mapping(block: str, key: str, indent: int) -> dict[str, str]:
    pad = " " * indent
    m = re.search(rf"^{pad}{re.escape(key)}:\n((?:{pad}  \S.*\n)+)", block, re.MULTILINE)
    assert m, f"no `{key}:` mapping at indent {indent}"
    out = {}
    for ln in m.group(1).splitlines():
        k, _, v = ln.strip().partition(":")
        out[k.strip()] = v.split("#")[0].strip()
    return out


def steps(block: str) -> list[tuple[str, str]]:
    """``[(name, step text)]`` in order (every step of these jobs starts with ``- name:``)."""
    parts = re.split(r"^      - name: (.+)$", block, flags=re.MULTILINE)
    return [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2)]


def run_blocks(text: str) -> list[str]:
    """Every run: script body (block scalars and one-liners)."""
    out, lines = [], text.splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", ln)
        if not m:
            continue
        indent, rest = len(m.group(1)), m.group(2)
        if rest and rest[0] not in "|>":
            out.append(rest)
            continue
        body = []
        for nxt in lines[i + 1:]:
            if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                break
            body.append(nxt)
        out.append("\n".join(body))
    return out


def test_reader_sees_the_whole_file(text):
    assert job_names(text) == ["gate", "harvest"]
    assert [n for n, _ in steps(job_block(text, "harvest"))] == HARVEST_STEPS
    assert len(run_blocks(text)) == 5


# --- the pins ----------------------------------------------------------------

def test_keyless(text):
    """No 'secrets.' reference anywhere, no claude-code-action, no AI_ANDON_CORD gate leg (the harvester keeps recording while the cord is pulled)."""
    assert "secrets." not in text
    assert "claude-code-action" not in text and "anthropics/" not in text
    assert "AI_ANDON_CORD" not in text
    # Every token use is the workflow's own GITHUB_TOKEN, by expression.
    assert set(re.findall(r"\$\{\{\s*([^}]*?token[^}]*?)\s*\}\}", text)) == {"github.token"}
    # The only external actions are checkout and upload-artifact.
    assert set(re.findall(r"^\s+(?:- )?uses: (\S+)", text, re.MULTILINE)) == {
        "actions/checkout@v7", "actions/upload-artifact@v7"}
    # Tamper negatives: each pin would catch its violation.
    assert "secrets." in text.replace("github.token", "secrets.GITHUB_TOKEN", 1)
    assert "AI_ANDON_CORD" in text.replace(GATE_IF, GATE_IF + " && vars.AI_ANDON_CORD != 'pulled'")


def test_no_inputs_in_run_scripts(text):
    """No '${{ inputs.' and no '${{ steps.' inside any run: block; inputs and step outputs reach run: steps only through env:."""
    for body in run_blocks(text):
        assert "${{" not in body, body
    # Every input reaches the plan step through env:.
    plan = dict(steps(job_block(text, "harvest")))["Plan"]
    env = mapping(plan, "env", 8)
    for name in ("mode", "since", "until", "pr", "receipts_only", "max_requests", "dry_run",
                 "bootstrap", "confirm_sha"):
        assert env[name.upper()] == f"${{{{ inputs.{name} }}}}", name
    # Tamper negative.
    tampered = text.replace('mode="${MODE:-harvest}"', 'mode="${{ inputs.mode }}"')
    assert tampered != text and any("${{" in b for b in run_blocks(tampered))


def test_permissions_job_level_only(text):
    """Workflow default contents: read; only the harvest job adds contents: write plus read on actions, pull-requests, issues, statuses, deployments — and NOT checks (nothing reads check runs; critique 13); the gate job holds contents: read + actions: read."""
    top = re.search(r"^permissions:\n((?:  \S.*\n)+)", text, re.MULTILINE)
    assert top and [ln.strip() for ln in top.group(1).splitlines()] == ["contents: read"]
    assert mapping(job_block(text, "gate"), "permissions", 4) == {"contents": "read", "actions": "read"}
    assert mapping(job_block(text, "harvest"), "permissions", 4) == {
        "contents": "write", "actions": "read", "pull-requests": "read", "issues": "read",
        "statuses": "read", "deployments": "read"}
    assert "checks:" not in text
    assert len(re.findall(r"^\s+contents: write", text, re.MULTILINE)) == 1


def test_token_reaches_steps_by_env_only(text):
    """GH_TOKEN (github.token) is set as env on the plan and publish steps only; no step writes it to a file, .git/config or argv; no step but publish could push (critique 12/13)."""
    harvest = steps(job_block(text, "harvest"))
    with_token = [n for n, body in harvest if "GH_TOKEN" in body]
    assert with_token == ["Plan", "Publish"]
    for name in ("Plan", "Publish"):
        assert mapping(dict(harvest)[name], "env", 8)["GH_TOKEN"] == "${{ github.token }}"
    # The gate job's one step reads the runs list with its own READ-ONLY token (contents +
    # actions read); it is a different job from the writer.
    gate = steps(job_block(text, "gate"))
    assert [n for n, body in gate if "GH_TOKEN" in body] == ["Gate"]
    # The token is never in argv, a file or git config; nothing but tools/provenance pushes.
    for body in run_blocks(text):
        assert "GH_TOKEN" not in body and "GITHUB_TOKEN" not in body
        assert not re.search(r"\bgit\b", body), body
        assert "extraheader" not in body and ".git/config" not in body
    pushers = [n for n, body in harvest if "provenance publish" in body]
    assert pushers == ["Publish"]
    assert text.count("persist-credentials: false") == 2 == text.count("uses: actions/checkout@v7")
    # Tamper negative: a token echoed into a run script is caught.
    tampered = text.replace("python3 -m provenance publish", 'echo "$GH_TOKEN" > t; python3 -m provenance publish')
    assert any("GH_TOKEN" in b for b in run_blocks(tampered))


def test_gate_job_and_concurrency(text):
    """A gate job with no concurrency group whose job-level if: is `github.event_name == 'workflow_dispatch' || vars.PROVENANCE_ENABLED == 'true'` (so a disarmed schedule's run is all-skipped and uploads nothing) feeds harvest's if: needs.gate.outputs.go == 'true'; harvest has job-level concurrency provenance-writer, cancel-in-progress false, timeout-minutes 350."""
    gate, harvest = job_block(text, "gate"), job_block(text, "harvest")
    assert job_key(gate, "if") == GATE_IF
    assert not re.search(r"^\s+concurrency:", gate, re.MULTILINE)
    assert re.search(r"^\s+concurrency:", harvest, re.MULTILINE)          # the reader can see one
    assert mapping(gate, "outputs", 4) == {"go": "${{ steps.gate.outputs.go }}"}
    assert job_key(harvest, "needs") == "gate"
    assert job_key(harvest, "if").startswith("needs.gate.outputs.go == 'true' && ")
    assert mapping(harvest, "concurrency", 4) == {"group": "provenance-writer",
                                                  "cancel-in-progress": "false"}
    assert job_key(harvest, "timeout-minutes") == "350"
    assert not re.search(r"^concurrency:", text, re.MULTILINE)   # never workflow-level
    # Only two triggers: data-ref pushes and PRs start nothing here.
    on = re.search(r"^on:\n(.*?)^\S", text, re.MULTILINE | re.DOTALL).group(1)
    assert re.findall(r"^  ([a-z_]+):", on, re.MULTILINE) == ["schedule", "workflow_dispatch"]


def test_default_branch_pin_and_checkout(text):
    """checkout ref = default branch, fetch-depth 0, persist-credentials false; the job if: pins github.ref_name to the default branch."""
    harvest = job_block(text, "harvest")
    # The pin is github.ref against refs/heads/<default>: stricter than the bare ref_name, which
    # a TAG named like the default branch would also match (the andon.yml precedent).
    assert job_key(harvest, "if").endswith(DEFAULT_BRANCH_PIN)
    checkout = dict(steps(harvest))[HARVEST_STEPS[0]]
    w = mapping(checkout, "with", 8)
    assert w == {"ref": "${{ github.event.repository.default_branch }}", "fetch-depth": "0",
                 "persist-credentials": "false"}
    gate_checkout = steps(job_block(text, "gate"))[0][1]
    assert mapping(gate_checkout, "with", 8) == {
        "ref": "${{ github.event.repository.default_branch }}", "persist-credentials": "false"}


def test_schedule_matches_conf(text):
    """Exactly one `- cron: '…'` literal (single-quoted — cadence-sync-check.sh's regex requires it), equal to the conf's cadence."""
    crons = re.findall(r"^\s*-\s*cron:\s*'([^']*)'\s*$", text, re.MULTILINE)
    assert crons == [conf.load(str(REPO / ".github" / "provenance.conf")).cadence] == ["29 * * * *"]
    assert len(re.findall(r"cron:", text)) == 1
    double = text.replace("- cron: '29 * * * *'", '- cron: "29 * * * *"')
    assert re.findall(r"^\s*-\s*cron:\s*'([^']*)'\s*$", double, re.MULTILINE) == []   # tamper


def test_step_order_intents_publish_checkpoints_verdict(text):
    """Steps in order: plan → upload intent-provenance-<sha> / intent-provenance-site-<sha> (each if: its *_changed output, retention-days 90) → publish → upload tip-provenance-<sha> / tip-provenance-site-<sha> checkpoints (each if: publish's *_tip output is non-empty, retention-days 90) → a verdict step that exits 3 when foreign_tip is true → summary (if: always()). Artifact names come from validated 40-hex outputs."""
    s = dict(steps(job_block(text, "harvest")))
    assert list(s) == HARVEST_STEPS
    uploads = {
        "Declare the evidence intent": ("steps.plan.outputs.evidence_changed == 'true'",
                                        "intent-provenance-${{ steps.plan.outputs.evidence_sha }}",
                                        ".provenance/intent-provenance.json"),
        "Declare the derived intent": ("steps.plan.outputs.site_changed == 'true'",
                                       "intent-provenance-site-${{ steps.plan.outputs.site_sha }}",
                                       ".provenance/intent-provenance-site.json"),
        "Checkpoint the evidence tip": ("steps.publish.outputs.evidence_tip != ''",
                                        "tip-provenance-${{ steps.publish.outputs.evidence_tip }}",
                                        ".provenance/checkpoint-provenance.json"),
        "Checkpoint the derived tip": ("steps.publish.outputs.site_tip != ''",
                                       "tip-provenance-site-${{ steps.publish.outputs.site_tip }}",
                                       ".provenance/checkpoint-provenance-site.json"),
    }
    for name, (cond, artifact, path) in uploads.items():
        body = s[name]
        assert re.search(rf"^        if: {re.escape(cond)}$", body, re.MULTILINE), name
        assert "uses: actions/upload-artifact@v7" in body
        assert mapping(body, "with", 8) == {"name": artifact, "path": path, "retention-days": "90",
                                            "if-no-files-found": "error"}, name
    # The artifact names are exactly gitstore's mark names over a 40-hex sha.
    from provenance.gitstore import intent_name, tip_name
    sha = "ab" * 20
    assert intent_name("provenance-site", sha) == f"intent-provenance-site-{sha}"
    assert tip_name("provenance", sha) == f"tip-provenance-{sha}"
    assert re.search(r"^        id: plan$", s["Plan"], re.MULTILINE)
    assert re.search(r"^        id: publish$", s["Publish"], re.MULTILINE)
    assert "if: steps.plan.outputs.dry_run != 'true'" in s["Publish"]
    verdict = s["Verdict"]
    assert ("if: steps.plan.outputs.foreign_tip == 'true' || "
            "steps.publish.outputs.foreign_tip == 'true'") in verdict
    assert re.search(r"^\s+exit 3$", verdict, re.MULTILINE) and "::error::" in verdict
    assert "if: always()" in s["Summary"] and "GITHUB_STEP_SUMMARY" in s["Summary"]
    assert ".provenance/summary.md" in s["Summary"]


def test_modes_and_input_validation(text):
    """workflow_dispatch input mode is a choice of exactly harvest | refreeze | recover (owner decision 12 — no ingest mode, critique 17); booleans receipts_only, dry_run, bootstrap; free-text since, until, pr, max_requests, confirm_sha passed as CLI arguments from env and validated by cli.validate_inputs; no snapshot_ref / snapshot_path input exists."""
    inputs = re.search(r"^    inputs:\n(.*?)^\S", text, re.MULTILINE | re.DOTALL).group(1)
    names = re.findall(r"^      ([a-z_]+):$", inputs, re.MULTILINE)
    assert names == ["mode", "since", "until", "pr", "receipts_only", "max_requests", "dry_run",
                     "bootstrap", "confirm_sha"]
    blocks = dict(zip(names, re.split(r"^      [a-z_]+:$", inputs, flags=re.MULTILINE)[1:]))
    assert "type: choice" in blocks["mode"]
    assert "options: [harvest, refreeze, recover]" in blocks["mode"]
    for b in ("receipts_only", "dry_run", "bootstrap"):
        assert "type: boolean" in blocks[b] and "default: false" in blocks[b], b
    for s in ("since", "until", "pr", "max_requests", "confirm_sha"):
        assert "type: string" in blocks[s], s
    assert not {"ingest", "snapshot_ref", "snapshot_path", "snapshot_dir", "ref", "path"} & set(names)
    assert "ingest" not in re.search(r"options: \[(.*)\]", blocks["mode"]).group(1)
    # Every flag the run scripts pass is one the cli parses (argparse would exit 2 otherwise) …
    ap = cli.build_parser()
    ap.parse_args(["gate", "--gh-output", "o", "--armed-var=", "--scheduled"])
    ap.parse_args(["harvest", "--out-dir", ".provenance", "--gh-output", "o", "--since=", "--until=",
                   "--pr=", "--max-requests=", "--scheduled", "--receipts-only", "--dry-run",
                   "--bootstrap"])
    ap.parse_args(["refreeze", "--out-dir", ".provenance", "--gh-output", "o", "--pr=636", "--dry-run"])
    ap.parse_args(["recover", "--out-dir", ".provenance", "--gh-output", "o", "--confirm-sha=" + "a" * 40])
    ap.parse_args(["publish", "--out-dir", ".provenance", "--gh-output", "o"])
    plan = dict(steps(job_block(text, "harvest")))["Plan"]
    for flag in ('--since="$SINCE"', '--until="$UNTIL"', '--pr="$PR"', '--max-requests="$MAX_REQUESTS"',
                 '--confirm-sha="$CONFIRM_SHA"', "--receipts-only", "--dry-run", "--bootstrap",
                 "--scheduled"):
        assert flag in plan, flag
    # … and the free text the dispatcher types is regex-checked there before use.
    assert cli.validate_inputs(since="2026-07-31", pr="636,371", max_requests="400",
                               confirm_sha="a" * 40).prs == (371, 636)
    for bad in ({"since": "2026-07-31; rm -rf /"}, {"pr": "636 && curl"}, {"max_requests": "-1"},
                {"confirm_sha": "A" * 40}, {"until": "$(id)"}):
        with pytest.raises(cli.InputError):
            cli.validate_inputs(**bad)
    # The schedule always runs mode harvest, whatever the (absent) input says.
    assert 'if [ "$EVENT" = "schedule" ]; then\n            mode=harvest' in plan
