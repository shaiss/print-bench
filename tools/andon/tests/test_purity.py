"""The purity rule, checkable: the package never performs a GitHub or network
write (its only writes are local scratch files and $GITHUB_OUTPUT lines the
workflow consumes), and only the one I/O module may import anything
network-capable (the backlog-groomer's shape,
with ZERO exemptions — the andon package has no model call to carve out)."""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

from andon import policy

_PKG = pathlib.Path(policy.__file__).parent
_FORBIDDEN_IMPORTS = {"urllib", "socket", "http", "subprocess", "requests"}
_PURE_MODULES = ("policy.py", "cli.py", "__init__.py", "__main__.py")
_VERB_RE = re.compile(r"\b(POST|PATCH|PUT|DELETE)\b")


def _imports_of(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("module", _PURE_MODULES)
def test_pure_modules_import_nothing_network_capable(module):
    assert not _imports_of(_PKG / module) & _FORBIDDEN_IMPORTS


def test_policy_does_not_even_import_os():
    # policy.py is the byte-for-byte renderer; it must be I/O-free entirely.
    assert not _imports_of(_PKG / "policy.py") & {"os", "sys", "pathlib", "io"}


def test_github_module_imports_only_urllib_from_the_forbidden_set():
    assert _imports_of(_PKG / "github.py") & _FORBIDDEN_IMPORTS == {"urllib"}


def test_every_package_file_is_free_of_write_verbs():
    # Whole-file scan, comments and docstrings included, zero exemptions:
    # the one write lives in the workflow's github-script step, never here.
    files = sorted(_PKG.glob("*.py"))
    assert files, "no package files found"
    for path in files:
        match = _VERB_RE.search(path.read_text(encoding="utf-8"))
        assert match is None, f"{path.name} mentions {match.group(0) if match else ''}"


def test_the_verb_scan_can_fail():
    # Negative control: the regex is word-bounded and case-sensitive on
    # purpose, so `output` / `input` never trip it but a real verb does.
    assert _VERB_RE.search("gh-output and input") is None
    assert _VERB_RE.search("a PATCH call") is not None
