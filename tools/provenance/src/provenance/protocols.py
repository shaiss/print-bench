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
from typing import Any, Iterable, Iterator, Optional, Protocol, runtime_checkable


@runtime_checkable
class GitReader(Protocol):
    """Read-only local git. Every method is total: a missing object answers
    ``None``/``[]``/``False``, never raises — callers record the gap
    (``incomplete``/basis ``none``) instead of crashing a harvest.

    NO method fetches. Everything derive reads is fetched ONCE, token-less, at
    the start of the plan step (``gitstore.Git.fetch_all``: both data refs and
    ``+refs/pull/*/head``); a commit still missing after that is permanently
    missing (force-pushed away — 67 of 1,289 distinct auto-review run heads in
    the #843 snapshot are in no PR's commit list) and answers ``None``, which
    makes the derived answer deterministic for a given (evidence, main, PR-ref
    set) instead of flapping with a per-sha fetch (critique item 9)."""

    def rev_parse(self, rev: str) -> Optional[str]:
        """Full 40-hex sha of ``rev`` (``refs/remotes/origin/main``, a sha prefix …) or ``None``."""

    def has_commit(self, sha: str) -> bool:
        """True when the commit object is present locally."""

    def show(self, rev: str, path: str) -> Optional[bytes]:
        """Bytes of ``path`` at ``rev`` (``git show rev:path``), ``None`` when absent."""

    def parents(self, sha: str) -> list[str]:
        """Parent shas in order (first parent first); ``[]`` for a root or a missing commit."""

    def subject(self, sha: str) -> Optional[str]:
        """The commit's subject line (first line of the message), stripped."""

    def committer_email(self, sha: str) -> Optional[str]:
        """The committer e-mail (``%ce``). ``noreply@github.com`` marks a commit GitHub created
        (a rebase merge, a web edit) — extract.extract_direct_commits never makes one a direct record."""

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

    def blame_lines(self, rev: str, path: str) -> list[tuple[str, int]]:
        """``git blame --porcelain rev -- path``: one ``(commit sha, ORIGINAL line number in that
        commit)`` per line of the file at ``rev`` (index 0 = line 1). The original line, not the
        line at ``rev``, is what a committed row's ``fields.line`` and permalink carry, so a row
        does not change when lines above it move (critique item 6)."""

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

    def iter_pages(self, path: str, params: Optional[dict[str, str]] = None,
                   key: Optional[str] = None,
                   max_pages: int = 50) -> Iterator[tuple[list[Any], Optional[int]]]:
        """Lazily, one GET per page in API order: ``(items, total_count)`` per page —
        ``total_count`` is the response's own field (``None`` when it has none). The caller
        stops early by not iterating further (the artifact scan of tip continuity pages
        newest-first only until it has its checkpoints); past ``max_pages`` raises
        ``github.Truncated``."""

    def graphql_pr_threads(self, number: int) -> dict[str, Any]:
        """``{"nodes": [{first_comment_id, resolved, outdated}], "last_edited_at": ts|None}``
        via the ONE read-only GraphQL query; raises ``github.GraphQLUnavailable`` on 403/5xx."""

    def graphql_issue_edited(self, number: int) -> Optional[str]:
        """``lastEditedAt`` of an issue (same query document); raises ``GraphQLUnavailable``."""


@dataclass(frozen=True)
class Basis:
    """The code a run executed, for the serving join (docs/provenance.md §Serving-model join).

    ``kind`` — ``head`` (schedule/dispatch: ``run.head_sha``), ``merge``
    (auto-review pull_request: ``git merge-tree`` of ``main_sha`` =
    main@created_at with ``head_sha``) or ``main`` (oracle pull_request:
    ``main_sha`` = main at the checkout step's ``started_at``, which supplies
    the registry; ``head_sha`` = the run head, whose ``git merge-tree`` with
    ``main_sha`` supplies the workflow text, because GitHub runs a
    pull_request workflow's definition from the merge commit).
    ``ambiguous`` — True when the reconstruction cannot be trusted (merge
    conflict on the file; a main commit touching registry/workflow within
    the ambiguity window before ``created_at`` (merge) or within ± the window
    of the checkout step's interval (main; for the workflow file the interval
    starts the window before ``created_at``)); ``reason`` says which.
    ``unavailable`` — a commit the basis needs is not in the local object
    store after the job-start fetch (force-pushed away): the join answers
    basis ``none`` and the record gains ``codebasis-unavailable:<sha8>``.
    """

    kind: str
    head_sha: Optional[str]
    main_sha: Optional[str]
    ambiguous: bool = False
    reason: Optional[str] = None
    unavailable: Optional[str] = None


@runtime_checkable
class CodeBasis(Protocol):
    """What the serving join needs from history (``codebasis.GitCodeBasis`` implements it)."""

    def basis_for(self, workflow: str, event: str, run_head_sha: Optional[str],
                  run_created_at: str,
                  checkout: Optional[tuple[str, str]] = None) -> Basis:
        """The :class:`Basis` of one run. ``checkout`` is the ``(started_at, completed_at)`` of
        the ``actions/checkout`` step of the job that resolved the chain (from the same
        receipt): ``oracle.yml`` checks out ``pull_request.base.ref`` BY NAME when that step
        runs, so its basis is main at that instant, not at ``run_created_at`` (critique item 26)."""

    def file_at(self, basis: Basis, path: str) -> Optional[bytes]:
        """``path`` as that run saw it (head tree, merge-tree result, or main), ``None`` when unknown."""

    def chain_models(self, basis: Basis, chain: str) -> Optional[tuple[str, ...]]:
        """The model ids of ``[chain:<chain>]`` in ``.github/models/registry.conf`` at ``basis``,
        parsed with tools/model-registry's own parser; ``None`` when absent/unparseable."""


@dataclass(frozen=True)
class Round:
    """One review round — the in-memory form of the contract ``round`` type.

    Shared by extract/episodes (H3, who build them), serving (H4) and views (H5):
    records store rounds as contract dicts; ``episodes.rounds_from_record``
    converts back, ``episodes.round_dict`` forwards (critique item 14).
    """

    id: str
    head: str
    heads: tuple[str, ...]
    commits: tuple[str, ...]
    pushed_at: Optional[str]
    start: Optional[str]
    end: Optional[str]


def iter_sorted(items: Iterable[Any]) -> list[Any]:
    """``sorted(items)`` — a helper so protocol users never rely on set iteration order."""
    return sorted(items)
