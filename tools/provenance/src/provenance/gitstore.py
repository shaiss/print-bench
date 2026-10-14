"""The ONLY git module: read primitives, the add-only writer, the guard, pushes, tip continuity.

Nothing else in the package runs a subprocess (tests/test_purity.py). Every
git invocation goes through :meth:`Git.run` with ``GIT_TERMINAL_PROMPT=0``,
``GIT_CONFIG_NOSYSTEM=1``, ``core.hooksPath=/dev/null`` and a fixed bot
identity (``GIT_AUTHOR_NAME``/``GIT_COMMITTER_NAME`` = ``github-actions[bot]``,
email ``41898282+github-actions[bot]@users.noreply.github.com`` — the
telemetry roll-up's identity).

**Read side** — :class:`Git` implements ``protocols.GitReader`` (``show``,
``first_parent_log``, ``merge_tree_read``, ``blame_commits`` …) and
:class:`GitTreeReader` implements ``protocols.TreeReader`` over one commit
of a data ref (``git ls-tree -r -z`` once, ``git cat-file --batch`` for
blobs). ``DirTreeReader`` reads a directory the same way (``check --dir``,
ingest dry-runs, tests).

**Write side** — the evidence writer (docs/provenance.md §Storage):

1. :class:`TreeBuilder` seeds a TEMPORARY ``GIT_INDEX_FILE`` with ``git
   read-tree <tip>`` (or empty, at bootstrap), adds only NEW blobs with
   ``git hash-object -w --stdin`` + ``git update-index --add --cacheinfo``,
   and replaces only paths in ``mutable`` (``state.json``); adding a path
   that already exists with different bytes raises :class:`GuardViolation`
   immediately. No existing file ever round-trips through the working tree,
   so the ``> file || true`` truncation (the telemetry #D2 defect) is
   structurally impossible.
2. :func:`commit_tree` — ``git write-tree`` then ``git commit-tree -p <tip>``
   (no parent at bootstrap; the derived ref is always parentless).
3. :func:`guard_diff` — ``git diff-tree -r --no-renames -z <old> <new>``
   must show: no ``D`` anywhere; no ``M`` except on ``state.json``; no blob
   becoming 0 bytes; no change to the guard files once present; ``A`` only.
   An identical tree means "push nothing" (the caller skips the push).
   :class:`GuardViolation` names the first offending path and rule.
4. :func:`push_fast_forward` — ``git push origin <new>:refs/heads/provenance``
   with no force. A transport failure is retried up to 3 times with the SAME
   commit; a non-fast-forward rejection is NOT rebuilt on the new remote
   tip: it re-fetches, runs tip continuity on the new tip (foreign →
   :class:`ForeignTip`; declared → ``PushResult(rejected=True)`` and a
   ``::warning::``; the cursors redo the work next run).
5. :func:`push_force_with_lease` — the derived ref and ``recover`` only:
   ``--force-with-lease=refs/heads/<ref>:<expected_old>``.

**Tip continuity** (§Tip continuity) — :func:`declared_intents` lists the
last ``intent_window_runs`` provenance.yml runs with ``head_branch == main``
and ``event in {schedule, workflow_dispatch}`` whose ``head_sha`` is on
main's first-parent history, newest first, and reads their artifact names
(``intent-<ref>-<sha40>``), stopping early once the tip is found (usually
2 GETs). :func:`check_tip_continuity` refuses a tip that is not among them.
Bootstrap: an absent ref with no intent EVER declared in the window is
allowed (first run); an absent ref when intents exist is a deletion and
refused like a foreign tip.

Owner: H1.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .protocols import GitHubAPI

EVIDENCE_REF = "provenance"
DERIVED_REF = "provenance-site"
GUARD_DIR = ".github/data-branch-guard"

#: Data-tree path -> (mode, source path in the main checkout). Both refs carry
#: these, hash-objected from the ONE committed source (Q1's guard files).
GUARD_FILES = {
    "vercel.json": ("100644", f"{GUARD_DIR}/vercel.json"),
    "scripts/vercel-ignore-build.sh": ("100755", f"{GUARD_DIR}/vercel-ignore-build.sh"),
}

#: The only evidence paths a push may MODIFY.
MUTABLE_EVIDENCE_PATHS = frozenset({"state.json"})

#: Intent artifact names: ``intent-provenance-<sha40>`` / ``intent-provenance-site-<sha40>``.
INTENT_PREFIX = "intent-"

#: The evidence ref's README.md, written once at bootstrap and never changed.
EVIDENCE_README = """# provenance — evidence data branch

Generated and pushed by .github/workflows/provenance.yml (tools/provenance).
Never hand-edit: every push is fast-forward only, add-only (no deletes, no
modifications except state.json) and tip-continuity checked. The design of
record is docs/provenance.md on the default branch; the shapes are
site/lib/provenance-contract.json.
""".encode("utf-8")

BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"


class GitError(Exception):
    """A git command failed (message carries the command and stderr's first line)."""


class GuardViolation(Exception):
    """An add-only rule would be broken; nothing is pushed (exit 4)."""


class ForeignTip(Exception):
    """A data ref's tip is not a declared intent (exit 3, ``::error::``)."""


@dataclass(frozen=True)
class TreeChange:
    """One ``git diff-tree -r`` line."""

    status: str
    path: str
    old_mode: str
    new_mode: str
    old_blob: str
    new_blob: str


@dataclass(frozen=True)
class PushResult:
    """Outcome of one push: ``pushed``; ``rejected`` (non-ff, tip was declared); ``attempts``."""

    pushed: bool
    rejected: bool = False
    attempts: int = 1
    remote_tip: Optional[str] = None


def intent_name(ref: str, sha: str) -> str:
    """``intent-<ref>-<sha40>`` (implemented by the scaffold)."""
    return f"{INTENT_PREFIX}{ref}-{sha}"


def parse_intent_name(name: str) -> Optional[tuple[str, str]]:
    """``(ref, sha)`` from an artifact name, or ``None`` (implemented by the scaffold)."""
    for ref in (DERIVED_REF, EVIDENCE_REF):  # longest first: provenance-site before provenance
        prefix = f"{INTENT_PREFIX}{ref}-"
        if name.startswith(prefix):
            sha = name[len(prefix):]
            if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
                return ref, sha
    return None


@dataclass
class Git:
    """Subprocess git for one repository directory. Implements ``protocols.GitReader``."""

    repo_dir: str
    env: dict[str, str] = field(default_factory=dict)

    def run(self, *args: str, input: Optional[bytes] = None, check: bool = True,
            env: Optional[dict[str, str]] = None) -> bytes:
        """Run ``git <args>`` and return stdout bytes; :class:`GitError` on failure when ``check``."""
        raise NotImplementedError("builder H1")

    def fetch(self, refspec: str) -> bool:
        """``git fetch --no-tags origin <refspec>``; False (not raise) when the remote lacks it."""
        raise NotImplementedError("builder H1")

    # -- protocols.GitReader --------------------------------------------------
    def rev_parse(self, rev: str) -> Optional[str]:
        raise NotImplementedError("builder H1")

    def has_commit(self, sha: str) -> bool:
        raise NotImplementedError("builder H1")

    def ensure_commit(self, sha: str) -> bool:
        raise NotImplementedError("builder H1")

    def show(self, rev: str, path: str) -> Optional[bytes]:
        raise NotImplementedError("builder H1")

    def parents(self, sha: str) -> list[str]:
        raise NotImplementedError("builder H1")

    def subject(self, sha: str) -> Optional[str]:
        raise NotImplementedError("builder H1")

    def committed_epoch(self, sha: str) -> Optional[int]:
        raise NotImplementedError("builder H1")

    def first_parent_log(self, ref: str, paths: tuple[str, ...] = ()) -> list[tuple[str, int]]:
        raise NotImplementedError("builder H1")

    def changed_paths(self, sha: str) -> list[str]:
        raise NotImplementedError("builder H1")

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        raise NotImplementedError("builder H1")

    def merge_tree_read(self, ours: str, theirs: str, path: str) -> tuple[Optional[bytes], bool]:
        raise NotImplementedError("builder H1")

    def blame_commits(self, rev: str, path: str) -> list[str]:
        raise NotImplementedError("builder H1")

    def list_dir(self, rev: str, prefix: str) -> list[str]:
        raise NotImplementedError("builder H1")


@dataclass
class GitTreeReader:
    """``protocols.TreeReader`` over one commit (``ls-tree -r -z`` + ``cat-file --batch``)."""

    git: Git
    commit: Optional[str]

    def paths(self, prefix: str = "") -> list[str]:
        raise NotImplementedError("builder H1")

    def read(self, path: str) -> Optional[bytes]:
        raise NotImplementedError("builder H1")


@dataclass
class DirTreeReader:
    """``protocols.TreeReader`` over a directory (POSIX-relative paths, sorted)."""

    root: str

    def paths(self, prefix: str = "") -> list[str]:
        raise NotImplementedError("builder H1")

    def read(self, path: str) -> Optional[bytes]:
        raise NotImplementedError("builder H1")


class TreeBuilder:
    """Add-only tree assembly in a temporary index seeded from ``base_commit`` (or empty)."""

    def __init__(self, git: Git, base_commit: Optional[str],
                 mutable: frozenset[str] = MUTABLE_EVIDENCE_PATHS) -> None:
        raise NotImplementedError("builder H1")

    def add(self, path: str, data: bytes, mode: str = "100644") -> bool:
        """Add a NEW blob; True if added, False if the identical blob is already there;
        :class:`GuardViolation` if ``path`` exists with other bytes and is not mutable."""
        raise NotImplementedError("builder H1")

    def replace(self, path: str, data: bytes, mode: str = "100644") -> None:
        """Set a ``mutable`` path (``state.json``); :class:`GuardViolation` for any other path."""
        raise NotImplementedError("builder H1")

    def write_tree(self) -> str:
        """``git write-tree`` of the temp index; the temp index is removed afterwards."""
        raise NotImplementedError("builder H1")


class DerivedTreeBuilder:
    """A fresh (empty-index) tree for ``provenance-site``: every path set, nothing inherited."""

    def __init__(self, git: Git) -> None:
        raise NotImplementedError("builder H1")

    def set(self, path: str, data: bytes, mode: str = "100644") -> None:
        raise NotImplementedError("builder H1")

    def write_tree(self) -> str:
        raise NotImplementedError("builder H1")


def guard_blobs(git: Git, main_rev: str = "HEAD") -> dict[str, tuple[str, bytes]]:
    """``{data-tree path: (mode, bytes)}`` read from :data:`GUARD_FILES` sources at ``main_rev``.
    Raises :class:`GuardViolation` if a source is missing (both refs must carry the guard)."""
    raise NotImplementedError("builder H1")


def commit_tree(git: Git, tree: str, parent: Optional[str], message: str) -> str:
    """``git commit-tree`` with the bot identity; ``parent`` ``None`` = parentless."""
    raise NotImplementedError("builder H1")


def tree_of(git: Git, commit: Optional[str]) -> Optional[str]:
    """``<commit>^{tree}`` or ``None``."""
    raise NotImplementedError("builder H1")


def guard_diff(git: Git, old_commit: Optional[str], new_commit: str,
               mutable: frozenset[str] = MUTABLE_EVIDENCE_PATHS) -> list[TreeChange]:
    """The pre-push guard. Returns the change list (``[]`` = identical tree, push nothing);
    raises :class:`GuardViolation` on: any ``D``; ``M`` outside ``mutable``; a blob that becomes
    0 bytes; a guard-file change after bootstrap; any status other than ``A``/``M``."""
    raise NotImplementedError("builder H1")


def push_fast_forward(git: Git, gh: GitHubAPI, ref: str, new: str, expected_old: Optional[str],
                      *, declared: set[str], retries: int = 3) -> PushResult:
    """Fast-forward push of ``new`` to ``refs/heads/<ref>`` (see module docstring, step 4)."""
    raise NotImplementedError("builder H1")


def push_force_with_lease(git: Git, ref: str, new: str, expected_old: Optional[str]) -> PushResult:
    """``git push --force-with-lease=refs/heads/<ref>:<expected_old or empty>``."""
    raise NotImplementedError("builder H1")


def remote_tip(git: Git, ref: str) -> Optional[str]:
    """``git ls-remote origin refs/heads/<ref>`` sha, or ``None`` when the ref is absent."""
    raise NotImplementedError("builder H1")


def declared_intents(gh: GitHubAPI, git: Git, *, ref: str, window: int,
                     stop_at: Optional[str] = None,
                     workflow: str = "provenance.yml") -> tuple[set[str], bool]:
    """``(declared shas for ref, any_intent_seen)`` from recent default-branch runs' artifacts.

    Runs considered: ``head_branch == "main"``, ``event in {"schedule",
    "workflow_dispatch"}``, ``head_sha`` on main's first-parent history (local
    git). Stops listing artifacts once ``stop_at`` is found.
    """
    raise NotImplementedError("builder H1")


def check_tip_continuity(tip: Optional[str], declared: set[str], *, ref: str,
                         any_intent_seen: bool) -> None:
    """Raise :class:`ForeignTip` unless ``tip`` is declared, or the ref is absent at bootstrap.

    ``tip is None`` and ``not any_intent_seen`` → bootstrap (ok); ``tip is
    None`` and ``any_intent_seen`` → the ref was deleted → :class:`ForeignTip`.
    """
    raise NotImplementedError("builder H1")


def selftest_cases() -> list:
    """Offline negative controls for ``selftest.run`` (temp repo, no network): each guard rule
    (D, M outside state.json, 0-byte blob, guard-file change), an identical tree = no push,
    continuity foreign/deleted/bootstrap/declared, recover refusing an undeclared sha. H1."""
    raise NotImplementedError("builder H1")


def iter_changes(lines: Iterable[bytes]) -> list[TreeChange]:
    """Parse ``git diff-tree -r -z`` output records into :class:`TreeChange` (helper for guard_diff)."""
    raise NotImplementedError("builder H1")


_ = subprocess  # the one module allowed to import it (tests/test_purity.py)
