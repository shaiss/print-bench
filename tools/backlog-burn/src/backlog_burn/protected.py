"""Protected delivery paths — must stay in sync with design-run-deliver.sh.

``scripts/design-run-deliver.sh``'s ``is_protected_path`` / ``normalize_repo_path``
are the source of truth for what backlog-burn (and design-run) refuse to push.
This module mirrors that policy so the selector can skip issues whose scope
resolves only to those paths (or cannot be determined) before an agent burns
a firing on work the deliverer would never ship.

Parity is pinned by ``tests/test_protected.py``, which extracts the bash
functions from the deliverer and compares them against this port on a fixture
list. Prefer editing the deliverer first, then updating this port + fixtures.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional


def normalize_repo_path(raw: str) -> Optional[str]:
    """Normalize a repo-relative path the way the deliverer does.

    Lowercase, strip empty/``.`` segments, resolve ``..``. Returns ``None``
    when the path is not a safe repo-relative name (absolute, backslash,
    NUL/newline, or a ``..`` that escapes the root) — callers fail closed.
    """
    if not raw or "\n" in raw or "\r" in raw or "\\" in raw:
        return None
    if raw.startswith("/") or (len(raw) >= 2 and raw[1] == ":"):
        return None
    parts = raw.lower().split("/")
    out: list[str] = []
    for part in parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not out:
                return None
            out.pop()
            continue
        out.append(part)
    return "/".join(out)


def is_protected_path(path: str) -> bool:
    """True when ``path`` is a protected delivery path after normalization.

    Mirrors ``is_protected_path`` in ``scripts/design-run-deliver.sh``:

    * prefixes: ``scripts``, ``tools`` (repo-root)
    * ``**/.github/**`` and ``**/.claude/**`` at any depth (leading ``./``
      normalized away)
    * agent-instruction files at any depth: ``CLAUDE.md``, ``CLAUDE.local.md``,
      ``AGENTS.md``, ``.mcp.json``, ``.cursorrules``, ``.cursor/**``

    Fail closed: an unnormalizable path counts as protected.
    """
    norm = normalize_repo_path(path)
    if norm is None:
        return True
    # Repo-root prefixes (scripts/tools) plus any-depth .github / .claude
    # (leading ``./`` is already stripped by normalize_repo_path; a nested
    # ``sub/.github/x`` is as dangerous as the root tree — Security on #953).
    if (
        norm == ".github"
        or norm.startswith(".github/")
        or "/.github/" in f"/{norm}/"
    ):
        return True
    if norm == "scripts" or norm.startswith("scripts/"):
        return True
    if norm == "tools" or norm.startswith("tools/"):
        return True
    # any-depth .claude
    if norm == ".claude" or norm.startswith(".claude/") or "/.claude/" in f"/{norm}/":
        return True
    if norm == "claude.md" or norm.endswith("/claude.md"):
        return True
    if norm == "claude.local.md" or norm.endswith("/claude.local.md"):
        return True
    if norm == "agents.md" or norm.endswith("/agents.md"):
        return True
    if norm == ".mcp.json" or norm.endswith("/.mcp.json"):
        return True
    if norm == ".cursorrules" or norm.endswith("/.cursorrules"):
        return True
    if norm == ".cursor" or norm.startswith(".cursor/") or "/.cursor/" in f"/{norm}/":
        return True
    return False


# Path-like tokens the selector can recognize in an issue title/body.
# Leading top-level dirs the deliverer (or a design PR) commonly names, plus
# the agent-instruction filenames the deliverer refuses at any depth.
_TOP_DIRS = (
    ".github",
    ".claude",
    ".cursor",
    "scripts",
    "tools",
    "designs",
    "docs",
    "lib",
    "people",
    "styles",
    "templates",
    "site",
    "telemetry",
    "build",
)
_ROOT_FILES = (
    "CLAUDE.md",
    "CLAUDE.local.md",
    "AGENTS.md",
    ".mcp.json",
    ".cursorrules",
    "PM.md",
    "LICENSE",
    "README.md",
    "printer.conf",
)

# A path token in free text: a top-dir WITH at least one slash segment, or a
# known root file. Bare words like ``scripts`` / ``tools`` in prose must NOT
# match — that starved design-briefs that mentioned those words (Bugbot on
# #953). An explicit ``Touches:`` line still accepts bare tokens (below).
# Globs (*, ?, **) are kept so we can refuse them as undetermined.
_PATH_TOKEN = re.compile(
    r"(?i)(?<![A-Za-z0-9_./-])("
    + r"(?:(?:"
    + "|".join(re.escape(d) for d in _TOP_DIRS)
    + r")/[^\s`\"')\],:;|]+"
    + r"|"
    + "|".join(re.escape(f) for f in _ROOT_FILES)
    + r")"
    + r")(?![A-Za-z0-9_./-])"
)

_TOUCHES_LINE = re.compile(
    r"(?im)^\s*\*?\*?Touches\*?\*?\s*:\s*(.+?)\s*$"
)


def _clean_token(token: str) -> str:
    return token.strip().strip("`\"'").rstrip(".,;")


def extract_scope_paths(title: str, body: str = "") -> Optional[set[str]]:
    """Return the path set an issue's scope names, or ``None`` if unknown.

    Looks at the title, an explicit ``Touches:`` line, and path-like tokens in
    the body. Returns ``None`` (caller must fail closed / skip) when:

    * no path tokens are found, or
    * a token still carries a glob metacharacter (``*``, ``?``, ``[``) so the
      concrete path set cannot be determined.
    """
    text_bits = [title or "", body or ""]
    found: set[str] = set()

    for text in text_bits:
        for m in _TOUCHES_LINE.finditer(text):
            for piece in re.split(r"[\s,]+", m.group(1)):
                tok = _clean_token(piece)
                if tok:
                    found.add(tok)
        for m in _PATH_TOKEN.finditer(text):
            tok = _clean_token(m.group(1))
            if tok:
                found.add(tok)

    if not found:
        return None
    for tok in found:
        if any(ch in tok for ch in "*?["):
            return None
    return found


def protected_scope_reason(title: str, body: str = "") -> Optional[str]:
    """Why this issue's scope is unsafe for backlog-burn, or ``None`` if ok.

    * unknown / unparseable path set → fail closed
    * any path the deliverer would refuse → skip, naming one such path
    """
    paths = extract_scope_paths(title, body)
    if paths is None:
        return (
            "scope paths could not be determined "
            "(fail closed — title/Touches/body name no concrete paths)"
        )
    for path in sorted(paths):
        if is_protected_path(path):
            return (
                f"touches protected path {path!r} "
                "(deliverer refuses .github/**, **/.claude/**, scripts/**, "
                "tools/**, and agent-instruction files)"
            )
    return None


def any_protected(paths: Iterable[str]) -> bool:
    """True if any path in ``paths`` is protected (or unnormalizable)."""
    return any(is_protected_path(p) for p in paths)
