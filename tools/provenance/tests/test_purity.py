"""The purity rules, checkable (docs/provenance.md §Determinism):

* network: only ``github.py`` imports anything network-capable;
* git: only ``gitstore.py`` imports ``subprocess``; no module shells out any other way;
* clock / randomness: only ``cli.py`` and ``github.py`` read the clock (``time``,
  ``datetime.now``/``utcnow``/``today``); nothing imports ``random``/``secrets``/``uuid`` —
  so ``extract``, ``episodes``, ``serving``, ``views``, ``bundle`` (and every other module)
  are pure functions of their inputs;
* writes: no HTTP write verb literal anywhere, except the single ``"POST"`` of the one
  read-only GraphQL query inside ``github.Client._graphql``; the query has no ``mutation``.

Each rule has a negative control proving the scanner can fail.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

import provenance
from provenance import github

PKG = pathlib.Path(provenance.__file__).parent
MODULES = sorted(p.name for p in PKG.glob("*.py"))
NETWORK = {"urllib", "http", "socket", "ssl", "requests", "ftplib", "smtplib", "telnetlib",
           "xmlrpc", "asyncio", "aiohttp", "httpx", "urllib3"}
SHELL_ATTRS = {("os", "system"), ("os", "popen"), ("os", "execv"), ("os", "execve"), ("os", "execvp"),
               ("os", "spawnv"), ("os", "spawnl"), ("os", "posix_spawn"), ("os", "fork")}
CLOCK_ATTRS = {"now", "utcnow", "today", "time", "monotonic", "perf_counter", "time_ns"}
CLOCK_MODULES = {"cli.py", "github.py"}
RANDOM = {"random", "secrets", "uuid"}
VERB_RE = re.compile(r"^(POST|PUT|PATCH|DELETE)$")


def _tree(name: str) -> ast.AST:
    return ast.parse((PKG / name).read_text(encoding="utf-8"), filename=name)


def imports_of(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def attr_pairs(tree: ast.AST) -> set[tuple[str, str]]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            out.add((node.value.id, node.attr))
    return out


def verb_literals(tree: ast.AST) -> list[tuple[str, str]]:
    """``[(enclosing function qualname or '<module>', literal)]`` for every HTTP-verb string constant."""
    found: list[tuple[str, str]] = []

    def visit(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit(child, f"{scope}.{child.name}" if scope != "<module>" else child.name)
            else:
                if isinstance(child, ast.Constant) and isinstance(child.value, str) and VERB_RE.match(child.value):
                    found.append((scope, child.value))
                visit(child, scope)

    visit(tree, "<module>")
    return found


def test_every_module_is_declared():
    declared = set(provenance.__all__) | {"__init__", "__main__"}
    assert {m[:-3] for m in MODULES} == declared


@pytest.mark.parametrize("module", MODULES)
def test_only_github_imports_network(module):
    found = imports_of(_tree(module)) & NETWORK
    if module == "github.py":
        assert found <= {"urllib"}
    else:
        assert not found, f"{module} imports {sorted(found)}"


@pytest.mark.parametrize("module", MODULES)
def test_only_gitstore_runs_subprocesses(module):
    tree = _tree(module)
    if module != "gitstore.py":
        assert "subprocess" not in imports_of(tree), module
        assert not ({"pty", "multiprocessing"} & imports_of(tree)), module
    assert not (attr_pairs(tree) & SHELL_ATTRS), module


@pytest.mark.parametrize("module", MODULES)
def test_clock_and_randomness(module):
    tree = _tree(module)
    imps = imports_of(tree)
    assert not (imps & RANDOM), f"{module} imports {sorted(imps & RANDOM)}"
    if module in CLOCK_MODULES:
        return
    assert "time" not in imps, f"{module} imports time"
    bad = {(a, b) for a, b in attr_pairs(tree)
           if a in {"datetime", "date", "time"} and b in CLOCK_ATTRS}
    assert not bad, f"{module} reads the clock via {sorted(bad)}"


@pytest.mark.parametrize("module", MODULES)
def test_no_http_write_verbs(module):
    found = verb_literals(_tree(module))
    if module == "github.py":
        assert all(scope == "Client._graphql" and lit == "POST" for scope, lit in found), found
    else:
        assert not found, f"{module}: {found}"


def test_graphql_query_is_read_only():
    assert "mutation" not in github.GRAPHQL_QUERY.lower()
    assert github.GRAPHQL_QUERY.lstrip().startswith("query ")


def test_scanners_can_fail():
    # Negative controls: each scanner flags a planted violation.
    planted = ast.parse(
        "import urllib.request, subprocess, random\n"
        "from datetime import datetime\n"
        "x = datetime.now()\n"
        "os.system('x')\n"
        "def f():\n    return 'PATCH'\n"
    )
    assert "urllib" in imports_of(planted) and "subprocess" in imports_of(planted)
    assert "random" in imports_of(planted)
    assert ("datetime", "now") in attr_pairs(planted)
    assert ("os", "system") in attr_pairs(planted)
    assert verb_literals(planted) == [("f", "PATCH")]
    assert imports_of(_tree("github.py")) & NETWORK == {"urllib"}
