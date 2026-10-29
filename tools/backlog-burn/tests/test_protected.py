"""Parity + unit tests for the deliverer's protected-path policy port.

The bash ``is_protected_path`` in ``scripts/design-run-deliver.sh`` is the
source of truth. This suite (a) pins the Python port's own behaviour and
(b) extracts the bash functions and compares them on a fixture list so the
two cannot drift silently.
"""

from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

import pytest

from backlog_burn import protected as prot

REPO_ROOT = Path(__file__).resolve().parents[3]
DELIVER_SH = REPO_ROOT / "scripts" / "design-run-deliver.sh"

# Paths the deliverer must refuse / accept. Keep in sync with the case arms
# in is_protected_path (issues #869 / #879).
PROTECTED_FIXTURES = [
    ".github/workflows/ci.yml",
    ".github",
    "scripts/design-run-deliver.sh",
    "scripts",
    "tools/backlog-burn/src/backlog_burn/select.py",
    "tools",
    ".claude/skills/ship-issue/SKILL.md",
    "docs/.claude/hooks/evil.sh",
    "CLAUDE.md",
    "docs/CLAUDE.md",
    "CLAUDE.local.md",
    "AGENTS.md",
    "site/AGENTS.md",
    ".mcp.json",
    "designs/foo/.mcp.json",
    ".cursorrules",
    ".cursor/rules/x.md",
    "docs/.cursor/foo",
    "../escape",
    "/etc/passwd",
]

SAFE_FIXTURES = [
    "designs/phone-stand/phone-stand.scad",
    "docs/licensing.md",
    "docs/contributing/autonomy.md",
    "lib/printability.scad",
    "people/reeve.md",
    "styles/ovodyo/style.scad",
    "templates/README.md",
    "PM.md",
    "LICENSE",
    "README.md",
    "printer.conf",
    "site/index.html",
]


def test_python_marks_protected_fixtures():
    for path in PROTECTED_FIXTURES:
        assert prot.is_protected_path(path), f"expected protected: {path!r}"


def test_python_keeps_safe_fixtures():
    for path in SAFE_FIXTURES:
        assert not prot.is_protected_path(path), f"expected safe: {path!r}"


def _extract_bash_functions() -> str:
    text = DELIVER_SH.read_text(encoding="utf-8")
    chunks = []
    for name in ("normalize_repo_path", "is_protected_path"):
        m = re.search(
            rf"^{name}\(\)\s*\{{.*?\n\}}\n",
            text,
            re.MULTILINE | re.DOTALL,
        )
        assert m, f"{name} missing from {DELIVER_SH}"
        chunks.append(m.group(0))
    return "\n".join(chunks)


def test_python_matches_bash_deliverer():
    """Parity against the live bash functions (single source of truth)."""
    fns = _extract_bash_functions()
    script = textwrap.dedent(
        """\
        set -euo pipefail
        %s
        path="$1"
        if is_protected_path "$path"; then
          echo protected
        else
          echo safe
        fi
        """
    ) % fns
    for path in PROTECTED_FIXTURES + SAFE_FIXTURES:
        proc = subprocess.run(
            ["bash", "-c", script, "_", path],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, (
            f"bash is_protected_path failed for {path!r}: {proc.stderr}"
        )
        bash_verdict = proc.stdout.strip()
        py_verdict = "protected" if prot.is_protected_path(path) else "safe"
        assert py_verdict == bash_verdict, (
            f"drift on {path!r}: python={py_verdict} bash={bash_verdict}"
        )


def test_extract_scope_paths_from_touches():
    paths = prot.extract_scope_paths(
        "thicken the brim",
        "Touches: designs/phone-stand/phone-stand.scad\n",
    )
    assert paths == {"designs/phone-stand/phone-stand.scad"}


def test_extract_scope_paths_none_when_empty():
    assert prot.extract_scope_paths("improve something", "no paths here") is None


def test_extract_scope_paths_none_on_glob():
    assert prot.extract_scope_paths("x", "Touches: docs/**\n") is None


def test_bare_top_dir_word_is_not_a_free_text_path():
    # Prose "scripts" / "tools" must not extract; a real path still does.
    assert prot.extract_scope_paths(
        "improve the scripts", "we need better tools for this"
    ) is None
    assert prot.extract_scope_paths(
        "fix", "edit scripts/design-run-deliver.sh please"
    ) == {"scripts/design-run-deliver.sh"}


def test_touches_bare_scripts_still_counts():
    # An explicit Touches line may name a bare top-dir; that IS a path.
    assert prot.extract_scope_paths("x", "Touches: scripts\n") == {"scripts"}



def test_protected_scope_reason_safe():
    assert (
        prot.protected_scope_reason(
            "docs fix", "Touches: docs/licensing.md\n"
        )
        is None
    )


def test_protected_scope_reason_protected():
    reason = prot.protected_scope_reason(
        "CLAUDE.md: restore newline", ""
    )
    assert reason is not None
    assert "protected path" in reason


def test_protected_scope_reason_unknown():
    reason = prot.protected_scope_reason("mystery", "no paths")
    assert reason is not None
    assert "could not be determined" in reason
