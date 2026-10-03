"""The purity rules, checkable on the AST (#426: no LLM in the write path).

* **No network anywhere** — no module imports anything network-capable, and
  there is no carve-out (unlike the groomer's narrative seam): recording a
  memory never calls out.
* **Deterministic write path** — ``rules``, ``note`` and ``store`` never read
  the clock or a random source, so the same event is the same bytes on every
  machine and every retry (the content id depends on it).
* **Pure rules** — ``rules`` and ``note`` import no I/O module at all.
* **One writer** — only ``store`` (the write path) and ``selftest`` (inside a
  temporary directory) touch the filesystem.

Each scanner has a negative control proving it fires on a planted violation.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import agent_memory

_PKG = pathlib.Path(agent_memory.__file__).parent
_MODULES = sorted(_PKG.glob("*.py"))

_NETWORK = {"urllib", "socket", "http", "subprocess", "requests", "ftplib", "smtplib", "asyncio", "ssl"}
_NONDETERMINISTIC = {"time", "random", "uuid", "secrets"}
_CLOCK_CALLS = {"now", "utcnow", "today", "time", "time_ns", "monotonic", "perf_counter"}
_IO = {"os", "pathlib", "io", "sys", "shutil", "tempfile", "glob"}
_WRITE_ATTRS = {"write", "writelines", "write_text", "write_bytes", "mkdir", "makedirs",
                "rmdir", "touch", "remove", "unlink", "rename", "replace", "rmtree"}
_WRITE_PATH = ("rules.py", "note.py", "store.py")
_PURE = ("rules.py", "note.py")
_WRITERS = {"store.py", "selftest.py"}


def _tree(name: str) -> ast.AST:
    return ast.parse((_PKG / name).read_text(encoding="utf-8"))


def _imports(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def _clock_calls(tree: ast.AST) -> list[str]:
    return [n.func.attr for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr in _CLOCK_CALLS]


def _writes(tree: ast.AST) -> list[str]:
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in _WRITE_ATTRS:
            hits.append(n.func.attr)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open":
            modes = [a.value for a in n.args[1:2] if isinstance(a, ast.Constant)]
            modes += [k.value.value for k in n.keywords if k.arg == "mode" and isinstance(k.value, ast.Constant)]
            if any(set("wax+") & set(m) for m in modes):
                hits.append(f"open({modes[0]!r})")
    return hits


def test_the_package_has_the_expected_modules():
    assert {p.name for p in _MODULES} == {"__init__.py", "__main__.py", "cli.py", "note.py",
                                         "rules.py", "selftest.py", "store.py"}


@pytest.mark.parametrize("path", _MODULES, ids=lambda p: p.name)
def test_no_module_imports_anything_network_capable(path):
    assert not _imports(_tree(path.name)) & _NETWORK


@pytest.mark.parametrize("name", _WRITE_PATH)
def test_the_write_path_never_reads_a_clock_or_a_random_source(name):
    tree = _tree(name)
    assert not _imports(tree) & _NONDETERMINISTIC
    assert not _clock_calls(tree)


@pytest.mark.parametrize("name", _PURE)
def test_rules_and_note_import_no_io_module(name):
    assert not _imports(_tree(name)) & _IO


@pytest.mark.parametrize("path", _MODULES, ids=lambda p: p.name)
def test_only_the_store_and_the_selftest_write(path):
    if path.name in _WRITERS:
        return
    assert not _writes(_tree(path.name)), f"{path.name} writes"


def test_the_store_writes_create_only():
    # The one write in the write path opens "xb" — create-if-absent — never
    # "w", and nothing renames, replaces or unlinks a committed note.
    assert sorted(_writes(_tree("store.py"))) == ["mkdir", "open('xb')", "write"]


# --- negative controls: each scanner fires on a planted violation ---------------


def test_negative_control_the_scanners_can_fail():
    planted = ast.parse(
        "import urllib.request\nimport time\nfrom pathlib import Path\n"
        "x = datetime.datetime.now()\nopen(p, 'w')\nPath(p).write_text('x')\n"
    )
    assert _imports(planted) & _NETWORK == {"urllib"}
    assert _imports(planted) & _NONDETERMINISTIC == {"time"}
    assert _imports(planted) & _IO == {"pathlib"}
    assert _clock_calls(planted) == ["now"]
    assert sorted(_writes(planted)) == ["open('w')", "write_text"]
