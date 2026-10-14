"""The seams between modules — typing Protocols every builder codes against.

The harvester is built by six builders in parallel (docs/provenance.md
§Build split). They meet only at these protocols: a module that needs git
history takes a :class:`GitReader`, one that needs the evidence tree takes a
:class:`TreeReader`, one that needs GitHub takes a :class:`GitHubAPI`, the
serving join takes a :class:`CodeBasis`. Production implementations live in
``gitstore.py`` (``Git``, ``GitTreeReader``), ``github.py`` (``Client``)
and ``codebasis.py`` (``GitCodeBasis``); the dict-backed test doubles live in
``tests/fakes.py``. Nothing here does I/O.

Architect-owned and frozen: changing a signature here is a cross-builder
change and must be agreed, not made unilaterally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional, Protocol, runtime_checkable


@runtime_checkable
class GitReader(Protocol):
    """Read-only local git. Every method is total: a missing object answers
    ``None``/``[]``/``False``, never raises — callers record the gap
    (``incomplete``/basis ``none``) instead of crashing a harvest."""

    def rev_parse(self, rev: str) -> Optional[str]:
        """Full 40-hex sha of ``rev`` (``refs/remotes/origin/main``, a sha prefix …) or ``None``."""

    def has_commit(self, sha: str) -> bool:
        """True when the commit object is present locally."""

    def ensure_commit(self, sha: str) -> bool:
        """Make ``sha`` present (``git fetch origin <sha>`` when missing); True on success."""

    def show(self, rev: str, path: str) -> Optional[bytes]:
        """Bytes of ``path`` at ``rev`` (``git show rev:path``), ``None`` when absent."""

    def parents(self, sha: str) -> list[str]:
        """Parent shas in order (first parent first); ``[]`` for a root or a missing commit."""

    def subject(self, sha: str) -> Optional[str]:
        """The commit's subject line (first line of the message), stripped."""

    def committed_epoch(self, sha: str) -> Optional[int]:
        """Committer date as a UTC epoch second."""

    def first_parent_log(self, ref: str, paths: tuple[str, ...] = ()) -> list[tuple[str, int]]:
        """``[(sha, committer epoch)]`` along ``ref``'s FIRST-PARENT chain, newest first.

        With ``paths``, only commits whose first-parent diff touches one of them.
        """

    def changed_paths(self, sha: str) -> list[str]:
        """Paths ``sha`` changes against its first parent (every path for a root commit), sorted."""

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        """``git merge-base --is-ancestor``."""

    def merge_tree_read(self, ours: str, theirs: str, path: str) -> tuple[Optional[bytes], bool]:
        """``git merge-tree --write-tree --name-only ours theirs``, then ``path`` from the result tree.

        Returns ``(content, path_conflicted)``: ``content`` is ``path``'s
        bytes in the merged tree (``None`` when absent or when either commit
        is missing), ``path_conflicted`` is True when the merge listed
        ``path`` among its conflicted files (the merged blob then carries
        conflict markers and must not be read as a registry). A conflict on
        some OTHER path does not taint ``path``. The serving join treats
        ``path_conflicted`` as basis ``ambiguous``.
        """

    def blame_commits(self, rev: str, path: str) -> list[str]:
        """``git blame --porcelain rev -- path`` reduced to one commit sha per line (index 0 = line 1)."""

    def list_dir(self, rev: str, prefix: str) -> list[str]:
        """Immediate child names of directory ``prefix`` at ``rev`` (``git ls-tree --name-only``), sorted."""


@runtime_checkable
class TreeReader(Protocol):
    """Read access to one tree of a data ref (evidence or derived), or a directory standing in for it."""

    def paths(self, prefix: str = "") -> list[str]:
        """Every blob path under ``prefix`` (``""`` = whole tree), sorted."""

    def read(self, path: str) -> Optional[bytes]:
        """Blob bytes at ``path`` or ``None``."""


@runtime_checkable
class GitHubAPI(Protocol):
    """The GET-only GitHub surface the capture modules use (``github.Client`` implements it).

    Every method raises ``github.BudgetExhausted`` when the request cap or the
    rate-limit floor stops the run; callers let it propagate to the
    orchestrator, which saves cursors and exits cleanly.
    """

    def get(self, path: str, params: Optional[dict[str, str]] = None) -> Any:
        """One GET of ``/repos/{owner}/{repo}{path}`` (one page), parsed JSON."""

    def get_paged(self, path: str, params: Optional[dict[str, str]] = None,
                  key: Optional[str] = None, max_pages: int = 50) -> list[Any]:
        """Every page of a list endpoint concatenated (``key`` unwraps ``{key: [...]}`` pages)."""

    def graphql_pr_threads(self, number: int) -> dict[str, Any]:
        """``{"nodes": [{first_comment_id, resolved, outdated}], "last_edited_at": ts|None}``
        via the ONE read-only GraphQL query; raises ``github.GraphQLUnavailable`` on 403/5xx."""

    def graphql_issue_edited(self, number: int) -> Optional[str]:
        """``lastEditedAt`` of an issue (same query document); raises ``GraphQLUnavailable``."""


@dataclass(frozen=True)
class Basis:
    """The code a run executed, for the serving join (docs/provenance.md §Serving-model join).

    ``kind`` — ``head`` (schedule/dispatch: ``run.head_sha``), ``merge``
    (auto-review pull_request: ``git merge-tree`` of ``main_sha`` with
    ``head_sha``) or ``main`` (oracle pull_request: ``main_sha``).
    ``ambiguous`` — True when the reconstruction cannot be trusted (merge
    conflict on the file, or a main commit touching registry/workflow within
    the ambiguity window before the run); ``reason`` says which.
    """

    kind: str
    head_sha: Optional[str]
    main_sha: Optional[str]
    ambiguous: bool = False
    reason: Optional[str] = None


@runtime_checkable
class CodeBasis(Protocol):
    """What the serving join needs from history (``codebasis.GitCodeBasis`` implements it)."""

    def basis_for(self, workflow: str, event: str, run_head_sha: Optional[str],
                  run_created_at: str) -> Basis:
        """The :class:`Basis` of one run."""

    def file_at(self, basis: Basis, path: str) -> Optional[bytes]:
        """``path`` as that run saw it (head tree, merge-tree result, or main), ``None`` when unknown."""

    def chain_models(self, basis: Basis, chain: str) -> Optional[tuple[str, ...]]:
        """The model ids of ``[chain:<chain>]`` in ``.github/models/registry.conf`` at ``basis``,
        parsed with tools/model-registry's own parser; ``None`` when absent/unparseable."""


def iter_sorted(items: Iterable[Any]) -> list[Any]:
    """``sorted(items)`` — a helper so protocol users never rely on set iteration order."""
    return sorted(items)
