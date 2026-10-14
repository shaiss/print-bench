"""The integration gate (critique item 27): after the six builders merge, no scaffold stub remains.

Architect-owned. ``INTEGRATED`` is flipped to ``True`` by the integrator in
the integration commit; from then on CI fails if any ``NotImplementedError(
"builder …")`` survives in ``src/provenance/`` (a stub that ``conftest.needs``
would otherwise keep silently skipping) or any ``@pytest.mark.skip(reason=
"builder: implement")`` placeholder survives in ``tests/``.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from conftest import TESTS, TOOL

INTEGRATED = False


def _stubs() -> list[str]:
    found = []
    for p in sorted((TOOL / "src" / "provenance").glob("*.py")):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "NotImplementedError"
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and str(node.args[0].value).startswith("builder")):
                found.append(f"{p.name}:{node.lineno}")
    return found


def _placeholders() -> list[str]:
    found = []
    for p in sorted(pathlib.Path(TESTS).glob("test_*.py")):
        text = p.read_text(encoding="utf-8")
        if 'reason="builder: implement"' in text and p.name != pathlib.Path(__file__).name:
            found.append(p.name)
    return found


def test_scanner_sees_the_scaffold():
    """Negative control while INTEGRATED is False: the scanners do find the scaffold's stubs."""
    if INTEGRATED:
        pytest.skip("integrated")
    assert _stubs() and _placeholders()


@pytest.mark.skipif(not INTEGRATED, reason="flipped to True by the integration commit")
def test_no_builder_stub_or_placeholder_remains():
    assert _stubs() == [] and _placeholders() == []
