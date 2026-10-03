"""The package's shape, held by AST scans of every module:

* stdlib only — scripts/concept-preview.sh runs it from src/ with no install,
  so a third-party import would work on a dev box and break everywhere else;
* nothing network-capable — the tool, like the sheets it writes, reaches
  nothing outside the checkout;
* one filesystem writer — cli.py. The primitives, parser, emitter and
  checker are pure functions, which is what lets a test run any of them on
  any input without a sandbox.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import concept_preview

PKG = pathlib.Path(concept_preview.__file__).parent
MODULES = sorted(PKG.glob("*.py"))
NETWORK = {"urllib", "socket", "http", "ftplib", "smtplib", "asyncio", "ssl", "subprocess", "requests"}
# (Path.replace is a filesystem rename too, but the name collides with
# str.replace, which the emitter uses for escaping — so it is not scanned.)
WRITE_ATTRS = {"write", "writelines", "write_text", "write_bytes", "mkdir", "makedirs",
               "rmdir", "touch", "remove", "unlink", "rename", "rmtree"}
WRITER = "cli.py"


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


def test_modules_exist():
    assert {"palette.py", "primitives.py", "spec.py", "emit.py", "check.py", "cli.py"} <= {m.name for m in MODULES}


def test_stdlib_only_and_nothing_network_capable():
    for path in MODULES:
        for mod in _imports(ast.parse(path.read_text(encoding="utf-8"))):
            assert mod in sys.stdlib_module_names, f"{path.name} imports non-stdlib {mod!r}"
            assert mod not in NETWORK, f"{path.name} imports network-capable {mod!r}"


def test_only_the_cli_writes_to_the_filesystem():
    for path in MODULES:
        if path.name == WRITER:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in WRITE_ATTRS:
                raise AssertionError(f"{path.name}:{node.lineno} calls .{node.attr} — only {WRITER} writes")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
                raise AssertionError(f"{path.name}:{node.lineno} calls open() — only {WRITER} touches files")


def test_the_scan_would_catch_a_smuggled_writer():
    # Negative control for the scan itself: a module body that writes is
    # flagged by the same walk the test above runs.
    tree = ast.parse("from pathlib import Path\nPath('x').write_text('y')\n")
    assert any(isinstance(n, ast.Attribute) and n.attr in WRITE_ATTRS for n in ast.walk(tree))
    tree = ast.parse("import urllib.request\n")
    assert set(_imports(tree)) & NETWORK
