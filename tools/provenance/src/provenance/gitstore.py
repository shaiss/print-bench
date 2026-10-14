"""The ONLY git module: read primitives, the add-only writer, the guard, pushes, tip continuity.

Nothing else in the package runs a subprocess (tests/test_purity.py). Every
git invocation goes through :meth:`Git.run` with ``GIT_TERMINAL_PROMPT=0``,
``GIT_CONFIG_NOSYSTEM=1``, ``GIT_ALLOW_PROTOCOL=https:file`` (``file`` only
for the tests' local bare remotes), ``core.hooksPath=/dev/null``,
``core.fsmonitor=false``, ``safe.bareRepository=explicit`` and a fixed bot
identity (``GIT_AUTHOR_NAME``/``GIT_COMMITTER_NAME`` = ``github-actions[bot]``,
email ``41898282+github-actions[bot]@users.noreply.github.com`` — the
telemetry roll-up's identity). No PR file is ever checked out into the working
tree: PR objects are read with ``show`` / ``merge-tree --write-tree`` only.

**Fetching** — once, token-less, at the start of the plan step
(:meth:`Git.fetch_all`): both data refs and ``+refs/pull/*/head:refs/remotes/
pull/*/head`` (the repository is public, so an anonymous fetch reads every
PR head; with ``persist-credentials: false`` no credential exists to send).
Nothing fetches after that — derive reads only what is local, so its answer
is a pure function of (evidence, main, the fetched PR-ref set) (critique
item 9). The bulk PR-head fetch is bounded by the repository's total object
size (268 MB on 2026-10-14, most of it already in the ``fetch-depth: 0``
checkout); P2 measures its real cost. If it FAILS the run still publishes
evidence but publishes no derived tree (fail closed: ``derive_skipped``).

**Credentials** (critique item 12). Only :func:`push_fast_forward` and
:func:`push_force_with_lease` send a token, and never in argv: the
``Authorization`` header goes through ``GIT_CONFIG_COUNT=1``,
``GIT_CONFIG_KEY_0=http.https://github.com/.extraheader``,
``GIT_CONFIG_VALUE_0=AUTHORIZATION: basic <b64(x-access-token:TOKEN)>`` in the
child's environment, and ``::add-mask::<b64>`` is printed once before the
first push (Actions masks the raw token but not its base64 form — the
oracle.yml precedent). :class:`GitError` messages are built from
:func:`redact` over the argv and stderr — never the environment — so neither
the token nor its base64 can reach a log (tests/test_gitstore.py pins it with
a failing push to a local remote).

**Read side** — :class:`Git` implements ``protocols.GitReader`` (``show``,
``first_parent_log``, ``merge_tree_read``, ``blame_lines``,
``committer_email`` …) and :class:`GitTreeReader` implements
``protocols.TreeReader`` over one commit of a data ref (``git ls-tree -r -z``
once, ``git cat-file --batch`` for blobs). ``DirTreeReader`` reads a directory
the same way (``check --dir``, tests).

**Write side** — the evidence writer (docs/provenance.md §Storage):

1. :class:`TreeBuilder` seeds a TEMPORARY ``GIT_INDEX_FILE`` with ``git
   read-tree <tip>`` (or empty, at bootstrap), adds only NEW blobs with
   ``git hash-object -w --stdin`` + ``git update-index --add --cacheinfo``,
   and replaces only paths in ``mutable`` (``state.json``). ``add()`` of a
   path that already exists compares CONTENT: for a ``*.json.gz`` path the
   decompressed bytes (gzip output differs across zlib builds — critique item
   19), otherwise the bytes; equal → no-op (the existing blob is kept), else
   :class:`GuardViolation` at once. No existing file ever round-trips through
   the working tree, so the ``> file || true`` truncation (the telemetry #D2
   defect) is structurally impossible.
2. :func:`commit_tree` — ``git write-tree`` then ``git commit-tree -p <tip>``
   (no parent at bootstrap; the derived ref is always parentless).
3. :func:`guard_diff` — ``git diff-tree -r --no-renames -z <old> <new>``
   must show: no ``D`` anywhere; no ``M`` except on ``state.json``; no blob
   becoming 0 bytes; no change to the guard files once present; ``A`` only.
   An identical tree means "push nothing" (the caller skips the push).
   :class:`GuardViolation` names the first offending path and rule.
   The guard files are written into the evidence tree ONCE, at bootstrap
   (critique item 18): later runs never re-add them, so an edit to
   ``.github/data-branch-guard/*`` on main cannot brick the writer; the drift
   is reported by :func:`guard_drift` as a ``::warning::`` (harvest summary and
   ``check --kind evidence``). The derived tree always carries main's
   current bytes.
4. :func:`push_fast_forward` — ``git push origin <new>:refs/heads/provenance``
   with no force. A transport failure is retried up to 3 times with the SAME
   commit, then :class:`GitError` (exit 1). ANY rejection raises
   :class:`ForeignTip` (exit 3): inside the ``provenance-writer`` concurrency
   group no other default-branch harvester can move the tip, so a moved tip is
   foreign by construction (critique item 21) — nothing is rebuilt on it.
5. :func:`push_force_with_lease` — the derived ref and ``recover`` only:
   ``--force-with-lease=refs/heads/<ref>:<expected_old>``; a lease failure is
   :class:`ForeignTip`.

**Tip continuity** (docs/provenance.md §Tip continuity; critique items 3–5).
Every harvest job uploads small artifacts named by :func:`mark_name`:
``intent-<ref>-<sha40>`` BEFORE it pushes ``sha`` (a declared-but-unpushed
sha is harmless), and ``tip-<ref>-<sha40>`` — the CHECKPOINT — after every
successful publish, including a no-op one, naming the verified current tip.
:func:`scan_marks` reads them from ``GET /actions/artifacts`` (repo-wide,
newest first; measured ~70 artifacts/day, so one page usually reaches the
newest checkpoint), keeping only marks whose run is verified as a
default-branch harvester run (``path == .github/workflows/provenance.yml``,
``event`` ∈ {schedule, workflow_dispatch}, ``head_branch == main``,
``head_sha`` on main's first-parent history), within
``continuity_horizon_days`` (90 — artifact retention). The decision itself
is the PURE :func:`continuity_verdict` (implemented here; Reeve's
``provenance-foreign-tip`` ports it, and both suites run the shared table
``tests/fixtures/continuity_cases.json`` so the two cannot drift):

* **ok** — the tip IS the newest checkpoint ``C``, or (evidence) its
  first-parent chain reaches ``C`` through shas that are each a declared
  intent uploaded AFTER ``C`` (a run that pushed and died before
  checkpointing), or (derived) it is such an intent. Counting checkpoints,
  not runs, is what keeps a quiet day — or a disarmed week — from expiring
  the evidence of the live tip (the old "last 20 runs" window did).
* **foreign** — present but not accepted: a forged commit, or a ROLLBACK to an
  older declared sha (monotonic: only the newest checkpoint anchors).
* **deleted** — absent while a checkpoint exists. **unanchored** — present
  with no checkpoint in the horizon. **bootstrap** — absent with no
  checkpoint: the evidence root is created only by a dispatch carrying
  ``bootstrap=true`` (never automatically); the derived ref is simply
  recreated.

Owner: H1 (the I/O); ``continuity_verdict`` and the name helpers are
architect-implemented and frozen.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from .protocols import GitHubAPI

EVIDENCE_REF = "provenance"
DERIVED_REF = "provenance-site"
REFS = (EVIDENCE_REF, DERIVED_REF)
GUARD_DIR = ".github/data-branch-guard"
WORKFLOW_PATH = ".github/workflows/provenance.yml"
MARK_EVENTS = frozenset({"schedule", "workflow_dispatch"})

#: Data-tree path -> (mode, source path in the main checkout). Both refs carry
#: these, hash-objected from the ONE committed source (Q1's guard files) — the
#: evidence ref at bootstrap only, the derived ref on every build.
GUARD_FILES = {
    "vercel.json": ("100644", f"{GUARD_DIR}/vercel.json"),
    "scripts/vercel-ignore-build.sh": ("100755", f"{GUARD_DIR}/vercel-ignore-build.sh"),
}

#: The only evidence paths a push may MODIFY.
MUTABLE_EVIDENCE_PATHS = frozenset({"state.json"})

#: Artifact name prefixes: ``intent-<ref>-<sha40>`` (declared before a push) and
#: ``tip-<ref>-<sha40>`` (the checkpoint: the verified tip after a publish).
INTENT_PREFIX = "intent-"
TIP_PREFIX = "tip-"
MARK_KINDS = {"intent": INTENT_PREFIX, "tip": TIP_PREFIX}

#: Bulk, token-less fetch refspecs of the plan step (critique item 9).
FETCH_REFSPECS = (
    f"+refs/heads/{EVIDENCE_REF}:refs/remotes/origin/{EVIDENCE_REF}",
    f"+refs/heads/{DERIVED_REF}:refs/remotes/origin/{DERIVED_REF}",
    "+refs/pull/*/head:refs/remotes/pull/*/head",
)

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
    """A git command failed. The message is ``redact``-ed argv + stderr's first line — never env."""


class GuardViolation(Exception):
    """An add-only rule would be broken; nothing is pushed (exit 4)."""


class ForeignTip(Exception):
    """A data ref's tip failed continuity, or a push was rejected (exit 3, ``::error::``)."""


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
    """Outcome of one push: ``pushed`` (False = identical tip, nothing sent) and ``attempts``."""

    pushed: bool
    attempts: int = 1
    remote_tip: Optional[str] = None


@dataclass(frozen=True)
class Mark:
    """One verified continuity artifact.

    ``seq`` — the artifact id (monotonic in upload time; ordering uses it, not
    the run id, so a late re-run attempt of an old run orders by when it
    actually uploaded). ``kind`` ``intent`` | ``tip``; ``run_id`` for the summary.
    """

    seq: int
    kind: str
    ref: str
    sha: str
    run_id: int


@dataclass(frozen=True)
class Continuity:
    """The verdict for one ref (see the module docstring)."""

    ref: str
    verdict: str
    tip: Optional[str]
    checkpoint: Optional[str]
    chain: tuple[str, ...] = ()
    reason: str = ""

    @property
    def accepted(self) -> bool:
        return self.verdict == "ok"


VERDICTS = ("ok", "foreign", "deleted", "unanchored", "bootstrap")


def _is_sha(s: str) -> bool:
    return len(s) == 40 and all(c in "0123456789abcdef" for c in s)


def mark_name(kind: str, ref: str, sha: str) -> str:
    """``intent-<ref>-<sha40>`` / ``tip-<ref>-<sha40>`` (architect-implemented)."""
    if kind not in MARK_KINDS or ref not in REFS or not _is_sha(sha):
        raise ValueError(f"bad mark ({kind!r}, {ref!r}, {sha!r})")
    return f"{MARK_KINDS[kind]}{ref}-{sha}"


def intent_name(ref: str, sha: str) -> str:
    """``intent-<ref>-<sha40>``."""
    return mark_name("intent", ref, sha)


def tip_name(ref: str, sha: str) -> str:
    """``tip-<ref>-<sha40>`` (the checkpoint)."""
    return mark_name("tip", ref, sha)


def parse_mark_name(name: str) -> Optional[tuple[str, str, str]]:
    """``(kind, ref, sha)`` from an artifact name, or ``None`` (architect-implemented)."""
    for kind, prefix in MARK_KINDS.items():
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix):]
        for ref in (DERIVED_REF, EVIDENCE_REF):  # longest first: provenance-site before provenance
            if rest.startswith(f"{ref}-") and _is_sha(rest[len(ref) + 1:]):
                return kind, ref, rest[len(ref) + 1:]
    return None


def parse_intent_name(name: str) -> Optional[tuple[str, str]]:
    """``(ref, sha)`` of an ``intent-…`` name, or ``None`` (kept for the scaffold's callers)."""
    m = parse_mark_name(name)
    return (m[1], m[2]) if m and m[0] == "intent" else None


def continuity_verdict(*, ref: str, tip: Optional[str], marks: Iterable[Mark],
                       first_parent: Callable[[str], Optional[str]],
                       max_chain: int = 24) -> Continuity:
    """The tip-continuity rule (pure; architect-implemented, frozen; shared table in
    ``tests/fixtures/continuity_cases.json``). ``marks`` are VERIFIED marks within the horizon;
    ``first_parent(sha)`` answers from local git (harvester) or ``GET /git/commits`` (Reeve)."""
    if ref not in REFS:
        raise ValueError(f"unknown ref {ref!r}")
    mine = [m for m in marks if m.ref == ref]
    tips = sorted((m for m in mine if m.kind == "tip"), key=lambda m: m.seq, reverse=True)
    if not tips:
        if tip is None:
            return Continuity(ref, "bootstrap", None, None, reason="ref absent, no checkpoint in the horizon")
        return Continuity(ref, "unanchored", tip, None, reason="no checkpoint in the horizon")
    c = tips[0]
    if tip is None:
        return Continuity(ref, "deleted", None, c.sha, reason=f"ref absent; newest checkpoint {c.sha[:8]}")
    if tip == c.sha:
        return Continuity(ref, "ok", tip, c.sha, reason="tip is the newest checkpoint")
    newer = {m.sha for m in mine if m.kind == "intent" and m.seq > c.seq}
    if ref == DERIVED_REF:
        if tip in newer:
            return Continuity(ref, "ok", tip, c.sha, (tip,), reason="declared after the newest checkpoint")
        return Continuity(ref, "foreign", tip, c.sha,
                          reason=f"{tip[:8]} is neither checkpoint {c.sha[:8]} nor declared after it")
    chain: list[str] = []
    sha: Optional[str] = tip
    for _ in range(max_chain):
        if sha not in newer:
            return Continuity(ref, "foreign", tip, c.sha, tuple(chain),
                              reason=f"{sha[:8]} is not an intent declared after checkpoint {c.sha[:8]}")
        chain.append(sha)
        parent = first_parent(sha)
        if parent == c.sha:
            return Continuity(ref, "ok", tip, c.sha, tuple(chain),
                              reason=f"{len(chain)} declared commit(s) on checkpoint {c.sha[:8]}")
        if parent is None:
            break
        sha = parent
    return Continuity(ref, "foreign", tip, c.sha, tuple(chain),
                      reason=f"no declared chain from {tip[:8]} to checkpoint {c.sha[:8]}")


def redact(text: str, secrets: Iterable[str]) -> str:
    """``text`` with every non-empty secret (the token AND its base64 header form) replaced by ``***``."""
    raise NotImplementedError("builder H1")


@dataclass
class Git:
    """Subprocess git for one repository directory. Implements ``protocols.GitReader``.

    ``token`` is used by the two push functions only (through ``GIT_CONFIG_*``
    env, never argv); every other call — fetches included — runs token-less.
    """

    repo_dir: str
    env: dict[str, str] = field(default_factory=dict)
    token: str = ""

    def run(self, *args: str, input: Optional[bytes] = None, check: bool = True,
            env: Optional[dict[str, str]] = None) -> bytes:
        """Run ``git <args>`` and return stdout bytes; :class:`GitError` (redacted) on failure when ``check``."""
        raise NotImplementedError("builder H1")

    def fetch(self, refspec: str) -> bool:
        """Token-less ``git fetch --no-tags origin <refspec>``; False (not raise) when the remote lacks it.
        Used by ``fetch_all`` and by ``recover`` for the checkpoint sha; NEVER by derive."""
        raise NotImplementedError("builder H1")

    def fetch_all(self) -> dict[str, bool]:
        """The plan step's one bulk fetch (:data:`FETCH_REFSPECS`), ``{refspec: ok}``. An absent data
        ref is ok=True with no local ref; a failed ``refs/pull/*`` fetch is ok=False (derive skipped)."""
        raise NotImplementedError("builder H1")

    # -- protocols.GitReader --------------------------------------------------
    def rev_parse(self, rev: str) -> Optional[str]:
        raise NotImplementedError("builder H1")

    def has_commit(self, sha: str) -> bool:
        raise NotImplementedError("builder H1")

    def show(self, rev: str, path: str) -> Optional[bytes]:
        raise NotImplementedError("builder H1")

    def parents(self, sha: str) -> list[str]:
        raise NotImplementedError("builder H1")

    def subject(self, sha: str) -> Optional[str]:
        raise NotImplementedError("builder H1")

    def committer_email(self, sha: str) -> Optional[str]:
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

    def blame_lines(self, rev: str, path: str) -> list[tuple[str, int]]:
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
        """Add a NEW blob; True if added, False if ``path`` already holds the same CONTENT
        (decompressed for ``*.json.gz``; the existing blob is kept); :class:`GuardViolation`
        if it holds other content and is not mutable."""
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


def guard_blobs(repo_dir: str) -> dict[str, tuple[str, bytes]]:
    """``{data-tree path: (mode, bytes)}`` read from :data:`GUARD_FILES` sources in the main
    checkout. Raises :class:`GuardViolation` if a source is missing (both refs must carry the guard).
    Used at the evidence bootstrap and for every derived tree."""
    raise NotImplementedError("builder H1")


def guard_drift(tree: "object", guard: dict[str, tuple[str, bytes]]) -> list[str]:
    """Guard paths whose bytes/mode in an evidence tree (a ``protocols.TreeReader``) differ from
    main's current ``guard`` — a ``::warning::`` each, never an error (critique item 18)."""
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


def push_fast_forward(git: Git, ref: str, new: str, expected_old: Optional[str], *,
                      retries: int = 3) -> PushResult:
    """Fast-forward push of ``new`` to ``refs/heads/<ref>`` with ``git.token`` (module docstring,
    step 4): transport failures retried with the SAME commit then :class:`GitError`; any rejection
    → :class:`ForeignTip`."""
    raise NotImplementedError("builder H1")


def push_force_with_lease(git: Git, ref: str, new: str, expected_old: Optional[str]) -> PushResult:
    """``git push --force-with-lease=refs/heads/<ref>:<expected_old or empty>``; lease failure →
    :class:`ForeignTip`."""
    raise NotImplementedError("builder H1")


def remote_tip(git: Git, ref: str) -> Optional[str]:
    """Token-less ``git ls-remote origin refs/heads/<ref>`` sha, or ``None`` when the ref is absent."""
    raise NotImplementedError("builder H1")


def scan_marks(gh: GitHubAPI, git: Git, *, now_epoch: int, horizon_days: int,
               main_ref: str = "refs/remotes/origin/main",
               need: tuple[str, ...] = REFS) -> tuple[list[Mark], dict[str, int]]:
    """``(verified marks newest first, counts)`` from ``GET /actions/artifacts`` (module docstring).

    Pages newest-first (``gh.iter_pages``) and stops once every ref in ``need``
    has a verified ``tip`` mark, or the page's oldest artifact is older than the
    horizon. Each candidate run is verified once: the artifact's
    ``workflow_run`` gives ``head_branch`` / ``head_sha`` (pre-filter:
    ``main``, on ``git.first_parent_log(main_ref)``), then ``GET
    /actions/runs/{id}`` confirms ``path == WORKFLOW_PATH`` and ``event in
    MARK_EVENTS``. ``counts`` = {pages, runs_verified, marks_rejected} for the
    summary. The cost is about one page per 1.4 days since the newest checkpoint
    (6,519 artifacts on 2026-10-14; 100 cover ~34 h).
    """
    raise NotImplementedError("builder H1")


def selftest_cases() -> list:
    """Offline negative controls for ``selftest.run`` (temp repo, local bare remote, no network): each
    guard rule (D, M outside state.json, 0-byte blob, guard-file change), an identical tree = no push,
    every row of ``continuity_cases.json``, a rejected push = ForeignTip, a failing push's error carrying
    neither the token nor its base64. H1."""
    raise NotImplementedError("builder H1")


def iter_changes(lines: Iterable[bytes]) -> list[TreeChange]:
    """Parse ``git diff-tree -r -z`` output records into :class:`TreeChange` (helper for guard_diff)."""
    raise NotImplementedError("builder H1")


_ = subprocess  # the one module allowed to import it (tests/test_purity.py)
