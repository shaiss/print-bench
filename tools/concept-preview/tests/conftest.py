"""Import the package from src/ without installing it (the tool is
stdlib-only and scripts/concept-preview.sh runs it straight from src/; the
suite holds itself to the same bar), and share the fixture spec.

``BASE`` is the shipped ``fixtures/valid.conf`` — the same file the
``--selftest`` runs — so a rule tested here is tested against the spec the
selftest proves clean, and a negative test is that spec with one deliberate
defect: the defect is the only reason it fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1]
REPO = TOOL.parents[1]
FIXTURES = TOOL / "fixtures"
sys.path.insert(0, str(TOOL / "src"))

BASE = (FIXTURES / "valid.conf").read_text(encoding="utf-8")


def with_lines(*lines: str) -> str:
    """The base fixture plus extra rows appended at the end."""
    return BASE.rstrip("\n") + "\n" + "\n".join(lines) + "\n"


def without(prefix: str) -> str:
    """The base fixture minus every line starting with ``prefix``."""
    return "\n".join(ln for ln in BASE.splitlines() if not ln.startswith(prefix)) + "\n"


def replacing(old: str, new: str) -> str:
    assert old in BASE, f"fixture no longer contains {old!r}"
    return BASE.replace(old, new, 1)


@pytest.fixture()
def base_text() -> str:
    return BASE
