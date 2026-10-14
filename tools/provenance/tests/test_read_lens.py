"""#646: both refs are a READ LENS — no gate, selector or sign-off consumes them.

LIVE and architect-owned (critique item 23 pinned the rule before fan-out):
the two patterns below define what "reads a data ref" means, each form has a
negative control, and the allow-list names the only files that may read
``provenance`` / ``provenance-site``. A new reader anywhere else — a gate
script, a routine workflow, a skill — fails this test until it is
deliberately added to :data:`ALLOW` in a reviewed change.
"""

from __future__ import annotations

import re

import pytest

from conftest import REPO

#: A ref spelled as a ref: refs/heads/<r>, origin/<r>, ref=<r> / ref: <r> (YAML, API query strings).
REF_RE = re.compile(r"(?:refs/heads/|origin/|\bref[=:]\s*['\"]?)provenance(?:-site)?(?![\w-])")
#: A git read naming the ref as a bare word on the same line (``git fetch origin provenance``,
#: ``git show provenance:state.json``, ``git ls-remote origin provenance-site`` …).
GIT_RE = re.compile(
    r"\bgit\s+(?:fetch|pull|show|checkout|switch|ls-remote|archive|cat-file|rev-parse|log|ls-tree|"
    r"worktree|diff|branch|push)\b[^\n]*?(?<![\w./-])provenance(?:-site)?(?![\w./-])")
PATTERNS = (REF_RE, GIT_RE)

SCAN_ROOTS = ("scripts", "tools", ".github", ".claude", "site")
#: The only readers: the harvester itself and its workflow, Reeve's one detector module (and its
#: tests), the site's provenance modules (P3 adds its seam under this prefix) and site tests.
ALLOW = ("tools/provenance/", ".github/workflows/provenance.yml", "tools/reeve/src/reeve/provenance.py",
         "tools/reeve/tests/", "site/lib/provenance-", "site/test/")
SKIP_SUFFIXES = {".gz", ".png", ".gif", ".jpg", ".jpeg", ".tar", ".stl", ".3mf", ".zip", ".pyc",
                 ".woff", ".woff2", ".ttf", ".svg", ".ico", ".mp4", ".webp"}


def readers(files: dict[str, str]) -> list[tuple[str, int, str]]:
    """``[(path, line number, line)]`` for every non-allow-listed line that reads a data ref."""
    hits = []
    for path, text in sorted(files.items()):
        if path.startswith(ALLOW):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if any(rx.search(line) for rx in PATTERNS):
                hits.append((path, n, line.strip()))
    return hits


def _tree() -> dict[str, str]:
    out: dict[str, str] = {}
    for root in SCAN_ROOTS:
        for p in (REPO / root).rglob("*"):
            if not p.is_file() or "node_modules" in p.parts or p.suffix.lower() in SKIP_SUFFIXES:
                continue
            try:
                out[p.relative_to(REPO).as_posix()] = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
    return out


def test_only_allowed_readers_name_the_refs():
    assert readers(_tree()) == []


@pytest.mark.parametrize("line", [
    "git fetch origin refs/heads/provenance",
    "BASE=origin/provenance-site",
    "curl -s \"$API/repos/o/r/contents/state.json?ref=provenance\"",
    "        ref: provenance-site",
    "        ref: 'provenance'",
    "git fetch origin provenance",
    "git show provenance-site:site/bundle.json > b.json",
    "git checkout provenance",
    "git ls-remote origin provenance-site",
    "git cat-file -p provenance:state.json",
    "git rev-parse provenance",
])
def test_injected_reader_fails(line):
    """Negative controls, one per form: each line in a synthetic workflow is flagged."""
    assert readers({".github/workflows/evil.yml": f"steps:\n  - run: {line}\n"})


@pytest.mark.parametrize("line", [
    "needs: [provenance-tests]",
    "PYTHONPATH=tools/provenance/src python3 -m provenance harvest",
    "git diff --name-only origin/main -- tools/provenance/ docs/provenance.md",
    "git log -1 -- .github/provenance.conf",
    "BRANCH=origin/provenance-foo",
])
def test_non_readers_pass(line):
    """Positive controls: naming the tool, its job or its files is not reading a ref."""
    assert readers({".github/workflows/ci.yml": f"steps:\n  - run: {line}\n"}) == []


def test_allow_list_is_honoured():
    assert readers({".github/workflows/provenance.yml": "git fetch origin provenance\n",
                    "tools/reeve/src/reeve/provenance.py": "REF = 'refs/heads/provenance'\n"}) == []
    assert readers({"tools/reeve/src/reeve/detectors.py": "REF = 'refs/heads/provenance'\n"})
