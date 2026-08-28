"""AC5: the package performs zero HTTP calls and carries no write verbs.

The groomer/reeve pattern, one step stricter because this tool has no
network seam AT ALL (not even a GET): there is nothing this tool needs
beyond reading committed files and printing. Every check is on the AST of
every module in the package, so a smuggled import, a write-mode `open`, or
a filesystem-mutating method call anywhere fails the suite — docstring
prose never trips it, code always does.
"""

from __future__ import annotations

import ast
import pathlib

import brief_sources

_PKG = pathlib.Path(brief_sources.__file__).parent

_FORBIDDEN_IMPORTS = {"urllib", "socket", "http", "subprocess", "requests", "ftplib", "smtplib", "asyncio"}

# Attribute names that write — to files or to the filesystem. Reading
# (read_text, iterdir, glob) is the tool's whole job and is not listed.
_WRITE_ATTRS = {
    "write", "writelines", "write_text", "write_bytes",
    "mkdir", "makedirs", "rmdir", "touch",
    "remove", "unlink", "rename", "replace",
}

# HTTP write verbs as string constants — the groomer's rule: the value is
# where a smuggled verb lives, prose in a docstring does not count (it is
# not a Constant expression statement... but a string literal anywhere IS a
# Constant, so the scan covers f-strings' parts too).
_HTTP_WRITE_VERBS = {"POST", "PATCH", "PUT", "DELETE"}

_MODULES = sorted(_PKG.glob("*.py"))


def _imports_of(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_every_module_imports_nothing_network_capable():
    # No carve-out module exists here — unlike the groomer (whose
    # narrative.py is allowed urllib for its one model-API call), this
    # package has no permitted network exception at all.
    for path in _MODULES:
        assert not _imports_of(ast.parse(path.read_text(encoding="utf-8"))) & _FORBIDDEN_IMPORTS, (
            f"{path.name} imports a network-capable module"
        )


def test_no_open_call_ever_passes_a_write_mode():
    for path in _MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "open"):
                continue
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    assert not set("wax+") & set(kw.value.value), (
                        f"{path.name}:{node.lineno} opens a file in write mode {kw.value.value!r}"
                    )
            # positional mode: open(f, "w")
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                assert not set("wax+") & set(node.args[1].value), (
                    f"{path.name}:{node.lineno} opens a file in write mode {node.args[1].value!r}"
                )


def test_no_filesystem_write_method_is_called_anywhere():
    for path in _MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in _WRITE_ATTRS, (
                    f"{path.name}:{node.lineno} calls .{node.func.attr}() — the package writes nothing"
                )


def test_no_http_write_verb_appears_as_a_string_constant():
    for path in _MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value.strip().upper() not in _HTTP_WRITE_VERBS, (
                    f"{path.name}:{node.lineno} carries the HTTP verb {node.value!r}"
                )


def test_the_package_exports_no_write_surface():
    # Belt and braces on the public API: everything reachable from
    # `import brief_sources` is defined inside this package, not an
    # accidentally re-exported os/shutil helper.
    for name in brief_sources.__all__:
        obj = getattr(brief_sources, name)
        assert getattr(obj, "__module__", None) in ("brief_sources.markers", "brief_sources.select"), (
            f"brief_sources.{name} is re-exported from outside the package"
        )
