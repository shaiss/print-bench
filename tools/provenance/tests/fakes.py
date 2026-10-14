"""Dict-backed test doubles for the protocols in ``provenance.protocols``.

Architect-owned and FROZEN for the parallel build: builders add helpers in
their own test modules (or ``tests/_<module>_helpers.py``), never here, so
six worktrees never conflict on this file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FakeCommit:
    sha: str
    parents: list[str] = field(default_factory=list)
    epoch: int = 0
    subject: str = ""
    files: dict[str, bytes] = field(default_factory=dict)   # full tree at this commit
    changed: list[str] = field(default_factory=list)
    blame: dict[str, list[str]] = field(default_factory=dict)  # path -> per-line commit sha


class FakeGitReader:
    """``protocols.GitReader`` over in-memory commits. ``refs`` maps ref names to shas.

    ``merges`` maps ``(ours, theirs)`` to ``(files dict, conflicted paths)``;
    an unlisted pair answers ``(None, False)`` for every path.
    """

    def __init__(self, commits: list[FakeCommit], refs: Optional[dict[str, str]] = None,
                 merges: Optional[dict[tuple[str, str], tuple[dict[str, bytes], set[str]]]] = None,
                 fetchable: Optional[set[str]] = None) -> None:
        self.commits = {c.sha: c for c in commits}
        self.refs = dict(refs or {})
        self.merges = dict(merges or {})
        self.fetchable = set(fetchable or ())

    def _c(self, rev: str) -> Optional[FakeCommit]:
        sha = self.refs.get(rev, rev)
        if sha in self.commits:
            return self.commits[sha]
        hits = [c for s, c in self.commits.items() if s.startswith(sha)] if len(sha) >= 4 else []
        return hits[0] if len(hits) == 1 else None

    def rev_parse(self, rev: str) -> Optional[str]:
        c = self._c(rev)
        return c.sha if c else None

    def has_commit(self, sha: str) -> bool:
        return sha in self.commits

    def ensure_commit(self, sha: str) -> bool:
        return sha in self.commits or sha in self.fetchable

    def show(self, rev: str, path: str) -> Optional[bytes]:
        c = self._c(rev)
        return c.files.get(path) if c else None

    def parents(self, sha: str) -> list[str]:
        c = self._c(sha)
        return list(c.parents) if c else []

    def subject(self, sha: str) -> Optional[str]:
        c = self._c(sha)
        return c.subject if c else None

    def committed_epoch(self, sha: str) -> Optional[int]:
        c = self._c(sha)
        return c.epoch if c else None

    def first_parent_log(self, ref: str, paths: tuple[str, ...] = ()) -> list[tuple[str, int]]:
        out, c = [], self._c(ref)
        while c is not None:
            if not paths or any(p in c.changed for p in paths):
                out.append((c.sha, c.epoch))
            c = self.commits.get(c.parents[0]) if c.parents else None
        return out

    def changed_paths(self, sha: str) -> list[str]:
        c = self._c(sha)
        return sorted(c.changed) if c else []

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        stack, seen = [descendant], set()
        while stack:
            s = stack.pop()
            if s == ancestor:
                return True
            if s in seen or s not in self.commits:
                continue
            seen.add(s)
            stack.extend(self.commits[s].parents)
        return False

    def merge_tree_read(self, ours: str, theirs: str, path: str) -> tuple[Optional[bytes], bool]:
        files, conflicted = self.merges.get((ours, theirs), ({}, set()))
        if path in conflicted:
            return None, True
        return files.get(path), False

    def blame_commits(self, rev: str, path: str) -> list[str]:
        c = self._c(rev)
        return list(c.blame.get(path, [])) if c else []

    def list_dir(self, rev: str, prefix: str) -> list[str]:
        c = self._c(rev)
        if c is None:
            return []
        pre = prefix.rstrip("/") + "/"
        return sorted({p[len(pre):].split("/", 1)[0] for p in c.files if p.startswith(pre)})


class FakeTreeReader:
    """``protocols.TreeReader`` over ``{path: bytes}``."""

    def __init__(self, files: Optional[dict[str, bytes]] = None) -> None:
        self.files = dict(files or {})

    def paths(self, prefix: str = "") -> list[str]:
        return sorted(p for p in self.files if p.startswith(prefix))

    def read(self, path: str) -> Optional[bytes]:
        return self.files.get(path)


class FakeGitHub:
    """``protocols.GitHubAPI`` over canned responses keyed by ``(path, frozenset(params))``.

    ``calls`` records every request; ``budget`` (when set) raises the
    exception given in ``exhausted_with`` after that many calls.
    """

    def __init__(self, responses: Optional[dict[tuple[str, frozenset], Any]] = None,
                 threads: Optional[dict[int, Any]] = None, edited: Optional[dict[int, Optional[str]]] = None,
                 budget: Optional[int] = None, exhausted_with: Optional[type] = None) -> None:
        self.responses = dict(responses or {})
        self.threads = dict(threads or {})
        self.edited = dict(edited or {})
        self.budget = budget
        self.exhausted_with = exhausted_with
        self.calls: list[tuple[str, dict]] = []

    def _tick(self, path: str, params: Optional[dict]) -> None:
        if self.budget is not None and len(self.calls) >= self.budget:
            raise (self.exhausted_with or RuntimeError)("budget")
        self.calls.append((path, dict(params or {})))

    def _key(self, path: str, params: Optional[dict]) -> tuple[str, frozenset]:
        return path, frozenset((params or {}).items())

    def get(self, path: str, params: Optional[dict[str, str]] = None) -> Any:
        self._tick(path, params)
        return json.loads(json.dumps(self.responses.get(self._key(path, params))))

    def get_paged(self, path: str, params: Optional[dict[str, str]] = None,
                  key: Optional[str] = None, max_pages: int = 50) -> list[Any]:
        self._tick(path, params)
        data = self.responses.get(self._key(path, params)) or []
        if key and isinstance(data, dict):
            data = data.get(key, [])
        return json.loads(json.dumps(data))

    def graphql_pr_threads(self, number: int) -> dict[str, Any]:
        self._tick("graphql", {"number": number})
        if number not in self.threads:
            from provenance.github import GraphQLUnavailable
            raise GraphQLUnavailable("fake: no threads")
        return self.threads[number]

    def graphql_issue_edited(self, number: int) -> Optional[str]:
        self._tick("graphql", {"number": number})
        return self.edited.get(number)


class FakeCodeBasis:
    """``protocols.CodeBasis`` from tables: ``bases[(workflow, event, head, created)] -> Basis``,
    ``files[(basis.kind, basis.head_sha, basis.main_sha, path)] -> bytes``,
    ``chains[(basis.kind, basis.head_sha, basis.main_sha, chain)] -> tuple``."""

    def __init__(self, bases=None, files=None, chains=None, default=None) -> None:
        self.bases = dict(bases or {})
        self.files = dict(files or {})
        self.chains = dict(chains or {})
        self.default = default

    def basis_for(self, workflow, event, run_head_sha, run_created_at):
        b = self.bases.get((workflow, event, run_head_sha, run_created_at), self.default)
        if b is None:
            from provenance.protocols import Basis
            return Basis("head", run_head_sha, None)
        return b

    def file_at(self, basis, path):
        return self.files.get((basis.kind, basis.head_sha, basis.main_sha, path))

    def chain_models(self, basis, chain):
        return self.chains.get((basis.kind, basis.head_sha, basis.main_sha, chain))
