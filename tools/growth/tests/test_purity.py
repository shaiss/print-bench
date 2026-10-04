"""The growth engine's network confinement, checkable (the tools/andon shape).

The package has exactly two network seams, each with one direction:

* ``poster.py`` — the X seam: the package's ONLY write, ``POST /2/tweets`` to
  X, behind the posting tool's approval policy;
* ``github.py`` — the GitHub seam: GET-only, the dedup context's read.

Every other module is pure. So: only those two may import anything
network-capable; only ``poster.py`` may name an HTTP write verb; and
``github.py`` may build no ``Request`` carrying a body (urllib silently sends
a body as a POST, so the verb scan alone could not see that write).
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

from growth import dedup

_PKG = pathlib.Path(dedup.__file__).parent
_FORBIDDEN_IMPORTS = {"urllib", "socket", "http", "subprocess", "requests"}
_NETWORK_SEAMS = {"poster.py", "github.py"}
_VERB_RE = re.compile(r"\b(POST|PATCH|PUT|DELETE)\b")


def _imports_of(source: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def _bodied_requests(source: str) -> list[int]:
    """Line numbers of ``Request(...)`` calls passing ``data`` (keyword, or the
    second positional argument) or a ``method``."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name != "Request":
            continue
        if len(node.args) > 1 or any(k.arg in ("data", "method") for k in node.keywords):
            lines.append(node.lineno)
    return lines


_MODULES = sorted(p.name for p in _PKG.glob("*.py"))


def test_the_package_has_the_modules_this_test_reasons_about():
    assert _NETWORK_SEAMS <= set(_MODULES)
    assert "dedup.py" in _MODULES and "cli.py" in _MODULES


@pytest.mark.parametrize("module", [m for m in _MODULES if m not in _NETWORK_SEAMS])
def test_pure_modules_import_nothing_network_capable(module):
    found = _imports_of((_PKG / module).read_text(encoding="utf-8")) & _FORBIDDEN_IMPORTS
    assert not found, f"{module} imports {sorted(found)} — only {sorted(_NETWORK_SEAMS)} may"


def test_the_github_seam_imports_only_urllib_from_the_forbidden_set():
    assert _imports_of((_PKG / "github.py").read_text(encoding="utf-8")) \
        & _FORBIDDEN_IMPORTS == {"urllib"}


@pytest.mark.parametrize("module", [m for m in _MODULES if m != "poster.py"])
def test_only_the_x_poster_names_a_write_verb(module):
    # Whole-file scan, docstrings and comments included: the GitHub seam and
    # every pure module stay verb-free, so a write would have to be spelled.
    match = _VERB_RE.search((_PKG / module).read_text(encoding="utf-8"))
    assert match is None, f"{module} mentions {match.group(0) if match else ''}"


def test_the_github_seam_builds_no_request_with_a_body():
    assert _bodied_requests((_PKG / "github.py").read_text(encoding="utf-8")) == []


# --- negative controls: each scan can fail ------------------------------------


def test_the_verb_scan_can_fail():
    assert _VERB_RE.search("gh-output, input, POSTED_MARKER") is None
    assert _VERB_RE.search("a PATCH call") is not None


def test_the_import_scan_sees_a_network_import():
    assert "urllib" in _imports_of("import urllib.request\n")
    assert "http" in _imports_of("from http import client\n")


def test_the_body_scan_sees_a_bodied_request():
    # The exact shape poster.py uses — proof the scan would catch it in github.py.
    assert _bodied_requests("urllib.request.Request(url, data=b, method='X')\n") == [1]
    assert _bodied_requests("Request(url, b'x')\n") == [1]
    assert _bodied_requests("Request(url, headers={})\n") == []
    assert _bodied_requests((_PKG / "poster.py").read_text(encoding="utf-8")) != []
