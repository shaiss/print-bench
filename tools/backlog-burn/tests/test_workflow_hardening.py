"""Structural gates for backlog-burn.yml (Cipher / SA on #953)."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WORKFLOW = REPO / ".github" / "workflows" / "backlog-burn.yml"

HARDENED_SHELL = "/usr/bin/bash --noprofile --norc -eo pipefail {0}"
HARDENED_ENV_KEYS = (
    "PATH: /usr/bin:/bin",
    'LD_PRELOAD: ""',
    'LD_LIBRARY_PATH: ""',
    'LD_AUDIT: ""',
    'BASH_ENV: ""',
    'ENV: ""',
)


def _step_block(text: str, name: str) -> str:
    """Return the YAML step block starting at ``- name: <name>`` until the next step."""
    pat = re.compile(
        rf"^      - name: {re.escape(name)}\n(.*?)(?=^      - name: |\Z)",
        re.M | re.S,
    )
    m = pat.search(text)
    assert m, f"step not found: {name}"
    return m.group(0)


def test_bundle_verify_is_hardened():
    text = WORKFLOW.read_text(encoding="utf-8")
    block = _step_block(text, "Recheck bundle digest before upload")
    assert "id: bundle_verify" in block
    assert f"shell: {HARDENED_SHELL}" in block
    for line in HARDENED_ENV_KEYS:
        assert line in block, line
    assert "match=true" in block
    assert "match=false" in block


def test_clear_execution_log_steps_are_hardened():
    text = WORKFLOW.read_text(encoding="utf-8")
    for n in range(1, 6):
        block = _step_block(text, f"Clear execution log before link {n}")
        assert f"shell: {HARDENED_SHELL}" in block
        for line in HARDENED_ENV_KEYS:
            assert line in block, f"link {n}: {line}"


def test_metadata_upload_steps_require_bundle_verify_match():
    text = WORKFLOW.read_text(encoding="utf-8")
    needle = "steps.bundle_verify.outputs.match == 'true'"
    for name in (
        "Upload the delivery metadata",
        "Note the delivery metadata upload",
    ):
        block = _step_block(text, name)
        assert needle in block, name
    assert "id: meta_upload" in _step_block(text, "Note the delivery metadata upload")


def test_bundle_digest_match_helper():
    from backlog_burn.bundle_digest import digest_match

    assert digest_match("abc", "abc") is True
    assert digest_match("abc", "abd") is False
    assert digest_match("", "abc") is False
    assert digest_match(None, "abc") is False
    assert digest_match("abc", None) is False
