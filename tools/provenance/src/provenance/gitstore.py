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
Nothing else fetches after that — except, when the evidence tip failed
continuity, the newest checkpoint ``C`` by sha (``recover``, and a foreign
plan's derive base) — so derive's answer is a pure function of (evidence,
main, the fetched PR-ref set) (critique item 9). The bulk PR-head fetch is bounded by the repository's total object
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
listed in artifact-id order, newest first; measured ~70 artifacts/day, so one
page usually reaches the newest checkpoint), keeping only marks whose run is
verified as a default-branch harvester run (``path ==
.github/workflows/provenance.yml``, ``event`` ∈ {schedule,
workflow_dispatch}, ``head_branch == main``, ``head_sha`` on main's
first-parent history), within ``continuity_horizon_days`` (90 — artifact
retention).

**Order is upload time, not artifact id.** Artifact ids are NOT monotonic in
upload time: of 817 small artifacts measured GET-only (2026-08-31 →
2026-10-14), 45 were uploaded ≥ 30 min before some lower-id artifact and the
worst inversion was 3,843 s. Ordering by id let a genuine newer tip read
foreign and a rollback to an older, higher-id checkpoint read ok. Marks
therefore order by :func:`mark_order` = ``(created, seq)`` — the artifact's
``created_at`` (its upload time, 1 s resolution) first, the id only to break a
same-second tie — and the scan does not stop at the first tip in list order:
it pages on until every needed ref has a verified tip AND the oldest artifact
seen is more than :data:`MARK_ORDER_SLACK_SECONDS` (6 h, well above the
measured 64 min) older than the oldest of those newest tips, so no unread
(lower-id) artifact can be newer than them. For the evidence ref a clock-free
cross-check backs the clock: the ref is fast-forward-only, so the newest
checkpoint ``C`` must equal or descend from every other verified evidence
checkpoint read (:func:`checkpoint_conflicts`, ``is_ancestor`` = ``git
merge-base --is-ancestor``); one that it does not descend from makes the
verdict **foreign** with ``conflicts`` naming it.

The decision itself is the PURE :func:`continuity_verdict` (implemented here;
Reeve's ``provenance-foreign-tip`` ports it, and both suites run the shared
table ``tests/fixtures/continuity_cases.json`` so the two cannot drift):

* **ok** — the tip IS the newest checkpoint ``C``, or (evidence) its
  first-parent chain reaches ``C`` through shas that are each a declared
  intent uploaded AFTER ``C`` (a run that pushed and died before
  checkpointing), or (derived) it is such an intent; and (evidence, when
  ``is_ancestor`` is given) ``C`` has no checkpoint conflict. Counting
  checkpoints, not runs, is what keeps a quiet day — or a disarmed week — from
  expiring the evidence of the live tip (the old "last 20 runs" window did).
* **foreign** — present but not accepted: a forged commit, a ROLLBACK to an
  older declared sha (monotonic in upload time: only the newest checkpoint
  anchors), or (evidence) a checkpoint order conflict.
* **deleted** — absent while a checkpoint exists. **unanchored** — present
  with no checkpoint in the horizon. **bootstrap** — absent with no
  checkpoint: the evidence root is created only by a dispatch carrying
  ``bootstrap=true`` (never automatically); the derived ref is simply
  recreated.

Owner: H1 (the I/O); ``continuity_verdict`` and the name helpers are
architect-implemented (the upload-time order and the checkpoint-conflict
cross-check are the integrator's round-2 delta, ported to Reeve with them).
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import re
import shutil
import subprocess
import tempfile
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
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

    ``created`` — the artifact's ``created_at`` as a UTC epoch (its upload time);
    ``seq`` — the artifact id. Marks order by :func:`mark_order` ``(created,
    seq)``: upload time first, because artifact ids are NOT monotonic in upload
    time (inversions over an hour were measured — module docstring), the id only
    breaking a same-second tie. Not the run id either, so a late re-run attempt of
    an old run orders by when it actually uploaded. ``kind`` ``intent`` | ``tip``;
    ``run_id`` for the summary.
    """

    seq: int
    kind: str
    ref: str
    sha: str
    run_id: int
    created: int


@dataclass(frozen=True)
class Continuity:
    """The verdict for one ref (see the module docstring)."""

    ref: str
    verdict: str
    tip: Optional[str]
    checkpoint: Optional[str]
    chain: tuple[str, ...] = ()
    reason: str = ""
    #: Verified evidence checkpoints ``checkpoint`` does not descend from (a mark-order
    #: conflict, :func:`checkpoint_conflicts`): the verdict is then ``foreign`` and the
    #: newest checkpoint is NOT trusted as a derive base or a ``recover`` target.
    conflicts: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.verdict == "ok"


VERDICTS = ("ok", "foreign", "deleted", "unanchored", "bootstrap")

#: The bound on how much older than a newer-id artifact a lower-id one may have been
#: uploaded (artifact ids are not monotonic in upload time; the worst inversion measured
#: on 2026-10-14 was 3,843 s). :func:`scan_marks` reads on until the oldest artifact seen
#: is this much older than every needed ref's newest tip.
MARK_ORDER_SLACK_SECONDS = 6 * 3600


def mark_order(m: "Mark") -> tuple[int, int]:
    """The order of marks: ``(created, seq)`` — upload time, then the artifact id for a tie."""
    return (m.created, m.seq)


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


def checkpoint_conflicts(*, ref: str, checkpoint: str, marks: Iterable[Mark],
                         is_ancestor: Callable[[str, str], Optional[bool]]) -> tuple[str, ...]:
    """The clock-free cross-check of the evidence ref (pure): the verified ``tip`` marks of
    ``ref`` whose sha ``checkpoint`` neither equals nor descends from, sorted. The evidence ref
    is fast-forward-only, so every genuine checkpoint is an ancestor of every later one; a
    conflict means the upload-time order picked the wrong newest checkpoint (or history was
    rewritten) and ``checkpoint`` must not be trusted. ``is_ancestor(a, d)`` — "is ``a`` an
    ancestor of ``d``" — answers from local git (``merge-base --is-ancestor``) or ``GET
    /compare/{a}...{d}`` (Reeve); anything but ``True`` is a conflict. The derived ref is
    parentless (never checked: ``()``)."""
    if ref != EVIDENCE_REF:
        return ()
    others = sorted({m.sha for m in marks if m.ref == ref and m.kind == "tip" and m.sha != checkpoint})
    return tuple(x for x in others if is_ancestor(x, checkpoint) is not True)


def continuity_verdict(*, ref: str, tip: Optional[str], marks: Iterable[Mark],
                       first_parent: Callable[[str], Optional[str]],
                       is_ancestor: Optional[Callable[[str, str], Optional[bool]]] = None,
                       max_chain: int = 24) -> Continuity:
    """The tip-continuity rule (pure; architect-implemented; shared table in
    ``tests/fixtures/continuity_cases.json``). ``marks`` are VERIFIED marks within the horizon,
    ordered by :func:`mark_order` (upload time, never the artifact id alone);
    ``first_parent(sha)`` answers from local git (harvester) or ``GET /git/commits`` (Reeve);
    ``is_ancestor`` (evidence only; ``None`` skips it) runs :func:`checkpoint_conflicts` on an
    otherwise-``ok`` verdict, which then reads ``foreign`` with ``conflicts`` set."""
    if ref not in REFS:
        raise ValueError(f"unknown ref {ref!r}")
    mine = [m for m in marks if m.ref == ref]
    tips = sorted((m for m in mine if m.kind == "tip"), key=mark_order, reverse=True)
    if not tips:
        if tip is None:
            return Continuity(ref, "bootstrap", None, None, reason="ref absent, no checkpoint in the horizon")
        return Continuity(ref, "unanchored", tip, None, reason="no checkpoint in the horizon")
    c = tips[0]

    def accept(chain: tuple[str, ...], reason: str) -> Continuity:
        bad = checkpoint_conflicts(ref=ref, checkpoint=c.sha, marks=mine,
                                   is_ancestor=is_ancestor) if is_ancestor is not None else ()
        if bad:
            return Continuity(ref, "foreign", tip, c.sha, chain, conflicts=bad,
                              reason=f"newest checkpoint {c.sha[:8]} does not descend from verified checkpoint "
                                     f"{bad[0][:8]}" + (f" (+{len(bad) - 1} more)" if len(bad) > 1 else "")
                                     + " — a mark-order conflict")
        return Continuity(ref, "ok", tip, c.sha, chain, reason=reason)

    if tip is None:
        return Continuity(ref, "deleted", None, c.sha, reason=f"ref absent; newest checkpoint {c.sha[:8]}")
    if tip == c.sha:
        return accept((), "tip is the newest checkpoint")
    newer = {m.sha for m in mine if m.kind == "intent" and mark_order(m) > mark_order(c)}
    if ref == DERIVED_REF:
        if tip in newer:
            return accept((tip,), "declared after the newest checkpoint")
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
            return accept(tuple(chain), f"{len(chain)} declared commit(s) on checkpoint {c.sha[:8]}")
        if parent is None:
            break
        sha = parent
    return Continuity(ref, "foreign", tip, c.sha, tuple(chain),
                      reason=f"no declared chain from {tip[:8]} to checkpoint {c.sha[:8]}")


def redact(text: str, secrets: Iterable[str]) -> str:
    """``text`` with every non-empty secret (the token AND its base64 header form) replaced by ``***``."""
    out = text
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        out = out.replace(secret, "***")
    return out


# Pattern-based scrub for public artifacts (backlog-burn agent diag, etc.).
# Exact known-secret redact() cannot see a token that never entered the env
# (or a fragment that straddles a truncation boundary). Always run these
# patterns AFTER exact redact and BEFORE any truncation.
_SECRET_PATTERN_SPECS: tuple[tuple[str, str], ...] = (
    # GitHub fine-grained / classic / app installation / user-to-server /
    # refresh tokens (ghp_/gho_/ghs_/ghu_/ghr_). Allow . and - — some
    # server-to-server forms are not pure [A-Za-z0-9_].
    (r"gh[pousr]_[A-Za-z0-9._\-]{20,}", "***"),
    (r"github_pat_[A-Za-z0-9._\-]{20,}", "***"),
    # Actions / OIDC JWTs (ACTIONS_RUNTIME_TOKEN and friends).
    (r"eyJ[A-Za-z0-9_\-]+=*\.eyJ[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-+/=]+", "***"),
    # OpenRouter / Anthropic API keys.
    (r"sk-or-[A-Za-z0-9_\-]{20,}", "***"),
    (r"sk-ant-[A-Za-z0-9_\-]{20,}", "***"),
    # Documented Z.AI API keys (32 hex + '.' + 16 alnum), including when
    # echoed as ANTHROPIC_AUTH_TOKEN=… from a ship-link env dump. Do NOT use
    # a blanket 48+ url-safe class — that redacts SHA-256 digests (64 hex).
    # Leading lookbehind is hex-only so a non-hex letter prefix still redacts;
    # trailing lookahead omits '.' so ``key.`` (key then a dot) still redacts.
    (r"(?i)(?:ANTHROPIC_AUTH_TOKEN|ZAI_KEY)\s*[=:]\s*[0-9a-f]{32}\.[A-Za-z0-9]{16}", "***"),
    (r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{32}\.[A-Za-z0-9]{16}(?![A-Za-z0-9])", "***"),
    # AWS secret access key sitting near an access-key id (40 chars of
    # base64-ish, within ~80 chars of AKIA/ASIA — catch both orders).
    # These MUST run before the standalone AKIA/ASIA patterns or the id
    # is replaced first and the nearby secret is left behind. No
    # lookbehind on [A-Za-z0-9/+=] — that class includes ``=``, which is
    # the usual ``secret=…`` separator and would skip the value.
    (
        r"(?:AKIA|ASIA)[0-9A-Z]{16}"
        r"(?:[\s\S]{0,80}?)"
        r"[A-Za-z0-9/+]{40}",
        "***",
    ),
    (
        r"[A-Za-z0-9/+]{40}"
        r"(?:[\s\S]{0,80}?)"
        r"(?:AKIA|ASIA)[0-9A-Z]{16}",
        "***",
    ),
    # AWS access key ids (after the nearby-secret pairs above).
    (r"(?:AKIA|ASIA)[0-9A-Z]{16}", "***"),
    # Authorization Bearer values (header form before bare Bearer).
    (r"(?i)Authorization\s*:\s*Bearer\s+\S+", "Authorization: Bearer ***"),
    (r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]{20,}", "Bearer ***"),
    # Credentials in URLs (user:pass@ before x-access-token form).
    (r"(?i)https?://[^\s/@:]+:[^\s/@]+@", "https://***:***@"),
    (r"(?i)x-access-token:[^\s/@]+@", "x-access-token:***@"),
    # Base64-encoded x-access-token basic-auth strings (Actions masks the
    # raw token but not this form — see credential_env / Git.secrets).
    (r"(?i)(?:AUTHORIZATION:\s*)?basic\s+[A-Za-z0-9+/]{20,}={0,2}", "basic ***"),
)

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pat), repl) for pat, repl in _SECRET_PATTERN_SPECS
)


def redact_patterns(text: str) -> str:
    """Replace well-known credential shapes with ``***`` (pattern-based)."""
    out = text or ""
    for pat, repl in _SECRET_PATTERNS:
        out = pat.sub(repl, out)
    return out


def scrub(text: str, secrets: Iterable[str] = ()) -> str:
    """Exact known-secret redact, then pattern redact. Call BEFORE truncating."""
    return redact_patterns(redact(text or "", secrets))


def scrub_then_truncate(
    text: str, limit: int, secrets: Iterable[str] = ()
) -> str:
    """``scrub`` the full text, then truncate — never the other way around."""
    if limit < 0:
        raise ValueError("limit must be >= 0")
    return scrub(text, secrets)[:limit]


# ---------------------------------------------------------------------------
# I/O (H1). Everything below runs git through Git.run / Git._popen only.

#: ``GIT_ALLOW_PROTOCOL`` of every invocation. Production is https only; the tests and the
#: selftest widen it to ``https:file`` for their local bare remotes (``Git.env`` overrides it).
ALLOW_PROTOCOL = "https"

#: Inherited variables that would redirect git (another repo, index or object store) or smuggle
#: config/credentials into a token-less call; scrubbed from every child environment.
_SCRUB_ENV = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_CONFIG",
    "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT", "GIT_ASKPASS", "SSH_ASKPASS",
    "GIT_SSH", "GIT_SSH_COMMAND", "GIT_PROXY_COMMAND", "GIT_EXTERNAL_DIFF",
})
_SCRUB_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_", "GIT_TRACE")

#: ``-c`` options on every invocation (docs/provenance.md §The add-only guard), plus: no
#: credential helper (a global helper must never hand a stored token to a "token-less" fetch),
#: no signing, no auto-gc, and no blame ignore-revs file (row blame must be the plain history).
HARDEN = (
    "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
    "-c", "safe.bareRepository=explicit", "-c", "credential.helper=",
    "-c", "commit.gpgSign=false", "-c", "gc.auto=0", "-c", "blame.ignoreRevsFile=",
)

#: The http.extraheader key the push credential is configured under (env only, never argv).
EXTRAHEADER_KEY = "http.https://github.com/.extraheader"

_HEX40_RE = re.compile(r"[0-9a-f]{40}")
_PORCELAIN_RE = re.compile(r"^([ +\-*!=])\t([^\t]*):([^\t]*)\t")
_PERSON_RE = re.compile(r"^(?P<name>.*) <(?P<email>[^>]*)> (?P<epoch>-?[0-9]+) [+-][0-9]{4}$")
_BLAME_HEADER_RE = re.compile(rb"^([0-9a-f]{40}) ([0-9]+) ([0-9]+)(?: [0-9]+)?$")
_REJECTED_MARKERS = ("[rejected]", "[remote rejected]", "stale info", "non-fast-forward", "fetch first")
_MISSING_REF_MARKERS = ("couldn't find remote ref", "not our ref", "unadvertised object",
                        "no such remote ref")

#: Printed ``::add-mask::`` values (once per process).
_MASKED: set[str] = set()


def _short(sha: Optional[str]) -> str:
    return sha[:8] if sha else "(absent)"


def credential_env(token: str) -> tuple[dict[str, str], str]:
    """``(GIT_CONFIG_* env, base64 form)`` carrying ``token`` as an ``http.extraheader``."""
    b64 = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
    return ({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": EXTRAHEADER_KEY,
             "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {b64}"}, b64)


def _mask_once(b64: str) -> None:
    if b64 and b64 not in _MASKED:
        _MASKED.add(b64)
        print(f"::add-mask::{b64}", flush=True)


def content_of(path: str, data: bytes) -> bytes:
    """Content identity of a blob (critique item 19): the decompressed bytes of a ``*.json.gz``
    path (gzip output differs across zlib builds), else the bytes themselves."""
    if path.endswith(".json.gz"):
        try:
            return gzip.decompress(data)
        except (OSError, EOFError, zlib.error):
            return data
    return data


def _check_tree_path(path: str) -> None:
    parts = path.split("/")
    if (not path or path.startswith("/") or any(p in ("", ".", "..") for p in parts)
            or ".git" in parts or "\0" in path or "\n" in path):
        raise GuardViolation(f"bad tree path {path!r}")


def _check_mode(mode: str) -> None:
    if mode not in ("100644", "100755"):
        raise GuardViolation(f"bad blob mode {mode!r}")


class _CatFile:
    """One long-lived ``git cat-file --batch`` (blob reads without a process per blob)."""

    def __init__(self, git: "Git") -> None:
        self.git = git
        self.proc: Optional[subprocess.Popen] = None

    def read(self, oid: str) -> Optional[bytes]:
        if not oid or "\n" in oid:
            return None
        if self.proc is None or self.proc.poll() is not None:
            self.proc = self.git._popen("cat-file", "--batch")
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(oid.encode("ascii") + b"\n")
        self.proc.stdin.flush()
        header = self.proc.stdout.readline()
        if not header or header.endswith(b" missing\n") or header.endswith(b" ambiguous\n"):
            return None
        fields = header.split()
        if len(fields) != 3:
            raise GitError(f"git cat-file --batch: unexpected header {header[:80]!r}")
        size = int(fields[2])
        data = self.proc.stdout.read(size)
        self.proc.stdout.read(1)  # the LF after the object
        return data if fields[1] == b"blob" else None

    def close(self) -> None:
        if self.proc is not None:
            try:
                if self.proc.stdin:
                    self.proc.stdin.close()
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
            self.proc = None


@dataclass
class Git:
    """Subprocess git for one repository directory. Implements ``protocols.GitReader``.

    ``token`` is used by the two push functions only (through ``GIT_CONFIG_*``
    env, never argv); every other call — fetches included — runs token-less.
    ``env`` is merged LAST into every child environment (the CLI pins
    ``GIT_AUTHOR_DATE``/``GIT_COMMITTER_DATE`` to the run's one clock read; the
    tests widen ``GIT_ALLOW_PROTOCOL``). Commit objects and first-parent logs are
    memoized (immutable). The ``GitReader`` methods never raise for a missing
    object (``None``/``[]``/``False``), as the protocol requires.
    """

    repo_dir: str
    env: dict[str, str] = field(default_factory=dict)
    token: str = field(default="", repr=False)
    _commits: dict = field(default_factory=dict, init=False, repr=False)
    _fplog: dict = field(default_factory=dict, init=False, repr=False)
    _catfile: Optional[_CatFile] = field(default=None, init=False, repr=False)

    # -- plumbing ---------------------------------------------------------------
    def secrets(self) -> list[str]:
        """The strings that must never reach a message: the token, its base64 header form."""
        if not self.token:
            return []
        cred, b64 = credential_env(self.token)
        return [self.token, b64, cred["GIT_CONFIG_VALUE_0"]]

    def _child_env(self, extra: Optional[dict[str, str]] = None) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items()
               if k not in _SCRUB_ENV and not k.startswith(_SCRUB_PREFIXES)}
        env.update({
            "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_ALLOW_PROTOCOL": ALLOW_PROTOCOL, "LC_ALL": "C", "LANGUAGE": "C",
            "GIT_AUTHOR_NAME": BOT_NAME, "GIT_AUTHOR_EMAIL": BOT_EMAIL,
            "GIT_COMMITTER_NAME": BOT_NAME, "GIT_COMMITTER_EMAIL": BOT_EMAIL,
        })
        env.update(self.env)
        if extra:
            env.update(extra)
        return env

    def _argv(self, args: tuple[str, ...]) -> list[str]:
        return ["git", "-C", self.repo_dir, *HARDEN, *args]

    def _error(self, args: tuple[str, ...], rc: int, stderr: bytes) -> GitError:
        line = next((ln for ln in stderr.decode("utf-8", "replace").splitlines() if ln.strip()), "")
        return GitError(redact(f"git {' '.join(args)} failed (exit {rc}): {line.strip()}", self.secrets()))

    def run_full(self, *args: str, input: Optional[bytes] = None,
                 env: Optional[dict[str, str]] = None) -> subprocess.CompletedProcess:
        """``git <args>`` with the hardened argv/env; the completed process, whatever its exit."""
        return subprocess.run(self._argv(args), input=input, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=self._child_env(env), check=False)

    def run(self, *args: str, input: Optional[bytes] = None, check: bool = True,
            env: Optional[dict[str, str]] = None) -> bytes:
        """Run ``git <args>`` and return stdout bytes; :class:`GitError` (redacted) on failure when ``check``."""
        proc = self.run_full(*args, input=input, env=env)
        if check and proc.returncode != 0:
            raise self._error(args, proc.returncode, proc.stderr)
        return proc.stdout

    def _popen(self, *args: str) -> subprocess.Popen:
        return subprocess.Popen(self._argv(args), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, env=self._child_env())

    def read_blob(self, oid: str) -> Optional[bytes]:
        """A blob's bytes by object id (one shared ``cat-file --batch``), ``None`` when absent."""
        if self._catfile is None:
            self._catfile = _CatFile(self)
        return self._catfile.read(oid)

    def close(self) -> None:
        if self._catfile is not None:
            self._catfile.close()
            self._catfile = None

    def __del__(self) -> None:  # pragma: no cover - interpreter teardown
        try:
            self.close()
        except Exception:
            pass

    # -- fetching (token-less) ----------------------------------------------------
    def fetch(self, refspec: str) -> bool:
        """Token-less ``git fetch --no-tags origin <refspec>``; False (not raise) when the remote lacks it.
        Used by ``fetch_all``, and for the newest evidence checkpoint's sha by ``recover`` and by a
        foreign-tip plan's derive (``cli._checkpoint_usable``) — the one fetch after the bulk one,
        and only of ``C``, a sha the harvester itself verified."""
        args = ("fetch", "--no-tags", "--no-write-fetch-head", "origin", refspec)
        proc = self.run_full(*args)
        if proc.returncode == 0:
            return True
        err = proc.stderr.decode("utf-8", "replace").lower()
        if any(m in err for m in _MISSING_REF_MARKERS):
            return False
        raise self._error(args, proc.returncode, proc.stderr)

    def fetch_all(self) -> dict[str, bool]:
        """The plan step's one bulk fetch (:data:`FETCH_REFSPECS`), ``{refspec: ok}``. An absent data
        ref is ok=True with no local ref; a failed ``refs/pull/*`` fetch is ok=False (derive skipped).

        One token-less ``ls-remote`` decides which data refs exist; a present one
        is fetched (force-updating ``refs/remotes/origin/<ref>``), an absent one
        has any stale local tracking ref deleted, so the local ref is exactly the
        remote's. A failure to list or fetch a DATA ref raises :class:`GitError`
        (tip continuity cannot be judged without it)."""
        out = self.fetch_data_refs()
        try:
            out[FETCH_REFSPECS[2]] = self.fetch(FETCH_REFSPECS[2])
        except GitError:
            out[FETCH_REFSPECS[2]] = False
        return out

    def fetch_data_refs(self) -> dict[str, bool]:
        """The data-ref half of :meth:`fetch_all` (``recover`` needs no PR heads)."""
        heads = self.remote_heads(REFS)
        out: dict[str, bool] = {}
        for ref, spec in zip(REFS, FETCH_REFSPECS[:2]):
            if ref in heads:
                if not self.fetch(spec):
                    raise GitError(f"git fetch {spec}: the remote listed refs/heads/{ref} but did not serve it")
            elif self.rev_parse(f"refs/remotes/origin/{ref}") is not None:
                self.run("update-ref", "-d", f"refs/remotes/origin/{ref}")
            out[spec] = True
        return out

    def remote_heads(self, refs: Iterable[str]) -> dict[str, str]:
        """``{ref: sha}`` for the named ``refs/heads/<ref>`` that exist on ``origin`` (token-less)."""
        names = [f"refs/heads/{r}" for r in refs]
        out = self.run("ls-remote", "origin", *names).decode("utf-8")
        found: dict[str, str] = {}
        for line in out.splitlines():
            sha, _, name = line.partition("\t")
            if name in names and _HEX40_RE.fullmatch(sha):
                found[name[len("refs/heads/"):]] = sha
        return found

    # -- protocols.GitReader --------------------------------------------------
    def rev_parse(self, rev: str) -> Optional[str]:
        if not rev or rev.startswith("-") or "\n" in rev:
            return None
        proc = self.run_full("rev-parse", "--verify", "--quiet", "--end-of-options", f"{rev}^{{commit}}")
        sha = proc.stdout.decode("ascii", "replace").strip()
        return sha if proc.returncode == 0 and _HEX40_RE.fullmatch(sha) else None

    def has_commit(self, sha: str) -> bool:
        if not sha or not _HEX40_RE.fullmatch(sha):
            return False
        return self._commit(sha) is not None

    def _commit(self, sha: str) -> Optional[dict]:
        if sha in self._commits:
            return self._commits[sha]
        if not _HEX40_RE.fullmatch(sha or ""):
            full = self.rev_parse(sha) if sha else None
            return self._commit(full) if full else None
        proc = self.run_full("cat-file", "commit", sha)
        if proc.returncode != 0:
            return None  # absent now; not memoized (a later fetch may bring it)
        raw = proc.stdout
        head, _, message = raw.partition(b"\n\n")
        info: dict = {"parents": [], "committer": None, "message": message.decode("utf-8", "replace")}
        for line in head.decode("utf-8", "replace").split("\n"):
            key, _, value = line.partition(" ")
            if key == "parent":
                info["parents"].append(value.strip())
            elif key == "committer":
                info["committer"] = value
            elif key == "tree":
                info["tree"] = value.strip()
        self._commits[sha] = info
        return info

    def show(self, rev: str, path: str) -> Optional[bytes]:
        sha = self.rev_parse(rev)
        if sha is None or not path or path.startswith("-"):
            return None
        proc = self.run_full("cat-file", "blob", f"{sha}:{path}")
        return proc.stdout if proc.returncode == 0 else None

    def parents(self, sha: str) -> list[str]:
        c = self._commit(sha) if sha else None
        return list(c["parents"]) if c else []

    def subject(self, sha: str) -> Optional[str]:
        c = self._commit(sha) if sha else None
        if c is None:
            return None
        return c["message"].split("\n", 1)[0].strip()

    def _person(self, sha: str) -> Optional[re.Match]:
        c = self._commit(sha) if sha else None
        if c is None or not c.get("committer"):
            return None
        return _PERSON_RE.match(c["committer"])

    def committer_email(self, sha: str) -> Optional[str]:
        m = self._person(sha)
        return m.group("email") if m else None

    def committed_epoch(self, sha: str) -> Optional[int]:
        m = self._person(sha)
        return int(m.group("epoch")) if m else None

    def first_parent_log(self, ref: str, paths: tuple[str, ...] = ()) -> list[tuple[str, int]]:
        sha = self.rev_parse(ref)
        if sha is None:
            return []
        key = (sha, tuple(paths))
        if key not in self._fplog:
            args = ["log", "--first-parent", "--format=%H %ct", sha]
            if paths:
                args += ["--", *paths]
            out = self.run(*args).decode("ascii", "replace")
            rows = []
            for line in out.splitlines():
                h, _, ct = line.partition(" ")
                if _HEX40_RE.fullmatch(h) and ct.strip().lstrip("-").isdigit():
                    rows.append((h, int(ct)))
            self._fplog[key] = rows
        return list(self._fplog[key])

    def changed_paths(self, sha: str) -> list[str]:
        c = self._commit(sha) if sha else None
        if c is None:
            return []
        full = self.rev_parse(sha)
        if c["parents"]:
            proc = self.run_full("diff-tree", "-r", "--no-renames", "--no-commit-id", "--name-only", "-z",
                                 c["parents"][0], full)
        else:
            proc = self.run_full("diff-tree", "-r", "--root", "--no-renames", "--no-commit-id",
                                 "--name-only", "-z", full)
        if proc.returncode != 0:
            return []
        return sorted(p.decode("utf-8", "replace") for p in proc.stdout.split(b"\0") if p)

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        a, d = self.rev_parse(ancestor), self.rev_parse(descendant)
        if a is None or d is None:
            return False
        return self.run_full("merge-base", "--is-ancestor", a, d).returncode == 0

    def merge_tree_read(self, ours: str, theirs: str, path: str) -> tuple[Optional[bytes], bool]:
        o, t = self.rev_parse(ours), self.rev_parse(theirs)
        if o is None or t is None:
            return None, False
        key = ("merge-tree", o, t)
        if key not in self._fplog:
            proc = self.run_full("merge-tree", "--write-tree", "--name-only", "-z", "--no-messages", o, t)
            if proc.returncode not in (0, 1):
                self._fplog[key] = None
            else:
                parts = [p.decode("utf-8", "replace") for p in proc.stdout.split(b"\0") if p]
                self._fplog[key] = (parts[0], frozenset(parts[1:])) if parts and _HEX40_RE.fullmatch(parts[0]) else None
        merged = self._fplog[key]
        if merged is None:
            return None, False
        tree, conflicted = merged
        proc = self.run_full("cat-file", "blob", f"{tree}:{path}")
        return (proc.stdout if proc.returncode == 0 else None), path in conflicted

    def blame_lines(self, rev: str, path: str) -> list[tuple[str, int]]:
        sha = self.rev_parse(rev)
        if sha is None or not path or path.startswith("-"):
            return []
        proc = self.run_full("blame", "--porcelain", sha, "--", path)
        if proc.returncode != 0:
            return []
        out: list[tuple[str, int]] = []
        current: Optional[tuple[str, int]] = None
        for line in proc.stdout.split(b"\n"):
            if line.startswith(b"\t"):
                if current is not None:
                    out.append(current)
                continue
            m = _BLAME_HEADER_RE.match(line)
            if m:
                current = (m.group(1).decode("ascii"), int(m.group(2)))
        return out

    def list_dir(self, rev: str, prefix: str) -> list[str]:
        sha = self.rev_parse(rev)
        if sha is None:
            return []
        pre = prefix.strip("/")
        proc = self.run_full("ls-tree", "--name-only", "-z", f"{sha}:{pre}" if pre else sha)
        if proc.returncode != 0:
            return []
        return sorted(p.decode("utf-8", "replace") for p in proc.stdout.split(b"\0") if p)

    # -- trees ------------------------------------------------------------------
    def tree_entries(self, commit: str) -> dict[str, tuple[str, str]]:
        """``{path: (mode, blob oid)}`` of every blob in ``commit``'s tree (``ls-tree -r -z``)."""
        out = self.run("ls-tree", "-r", "-z", "--full-tree", commit)
        entries: dict[str, tuple[str, str]] = {}
        for rec in out.split(b"\0"):
            if not rec:
                continue
            meta, _, path = rec.partition(b"\t")
            mode, kind, oid = meta.decode("ascii").split(" ")
            if kind == "blob":
                entries[path.decode("utf-8", "replace")] = (mode, oid)
        return entries

    def blob_sizes(self, oids: Iterable[str]) -> dict[str, int]:
        """``{oid: size}`` via one ``cat-file --batch-check`` (absent objects omitted)."""
        want = sorted(set(oids))
        if not want:
            return {}
        out = self.run("cat-file", "--batch-check", input=("\n".join(want) + "\n").encode("ascii"))
        sizes: dict[str, int] = {}
        for line in out.decode("ascii", "replace").splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[2].isdigit():
                sizes[parts[0]] = int(parts[2])
        return sizes

    def tree_size(self, commit: Optional[str]) -> tuple[int, int]:
        """``(files, bytes)`` of a commit's tree — the summary's size line (``ls-tree -r -l``)."""
        if not commit:
            return 0, 0
        out = self.run("ls-tree", "-r", "-l", "-z", "--full-tree", commit)
        files = total = 0
        for rec in out.split(b"\0"):
            meta = rec.partition(b"\t")[0].split()
            if len(meta) == 4 and meta[1] == b"blob" and meta[3].isdigit():
                files += 1
                total += int(meta[3])
        return files, total


@dataclass
class GitTreeReader:
    """``protocols.TreeReader`` over one commit (``ls-tree -r -z`` + ``cat-file --batch``)."""

    git: Git
    commit: Optional[str]
    _entries: Optional[dict] = field(default=None, init=False, repr=False)

    def entries(self) -> dict[str, tuple[str, str]]:
        if self._entries is None:
            self._entries = self.git.tree_entries(self.commit) if self.commit else {}
        return self._entries

    def paths(self, prefix: str = "") -> list[str]:
        return sorted(p for p in self.entries() if p.startswith(prefix))

    def read(self, path: str) -> Optional[bytes]:
        e = self.entries().get(path)
        return self.git.read_blob(e[1]) if e else None

    def mode(self, path: str) -> Optional[str]:
        e = self.entries().get(path)
        return e[0] if e else None


@dataclass
class DirTreeReader:
    """``protocols.TreeReader`` over a directory (POSIX-relative paths, sorted)."""

    root: str

    def _all(self) -> list[str]:
        out = []
        for base, dirs, files in os.walk(self.root):
            dirs[:] = sorted(d for d in dirs if d != ".git")
            for f in files:
                if f == ".git":
                    continue
                rel = os.path.relpath(os.path.join(base, f), self.root)
                out.append(rel.replace(os.sep, "/"))
        return sorted(out)

    def _resolve(self, path: str) -> Optional[str]:
        parts = path.split("/")
        if not path or path.startswith("/") or any(p in ("", ".", "..") for p in parts) or ".git" in parts:
            return None
        full = os.path.join(self.root, *parts)
        return full if os.path.isfile(full) else None

    def paths(self, prefix: str = "") -> list[str]:
        return [p for p in self._all() if p.startswith(prefix)]

    def read(self, path: str) -> Optional[bytes]:
        full = self._resolve(path)
        if full is None:
            return None
        with open(full, "rb") as fh:
            return fh.read()

    def mode(self, path: str) -> Optional[str]:
        full = self._resolve(path)
        if full is None:
            return None
        return "100755" if os.stat(full).st_mode & 0o111 else "100644"


class _IndexBuilder:
    """Shared temp-index assembly: blobs are batched into ONE ``hash-object --stdin-paths`` and
    ONE ``update-index -z --index-info`` at :meth:`write_tree`; nothing touches the work tree."""

    def __init__(self, git: Git, base_commit: Optional[str]) -> None:
        self.git = git
        self._tmp = tempfile.mkdtemp(prefix="provenance-index-")
        self._env = {"GIT_INDEX_FILE": os.path.join(self._tmp, "index")}
        if base_commit:
            git.run("read-tree", base_commit, env=self._env)
        else:
            git.run("read-tree", "--empty", env=self._env)
        self._existing: dict[str, tuple[str, str]] = {}
        out = git.run("ls-files", "-s", "-z", env=self._env)
        for rec in out.split(b"\0"):
            if not rec:
                continue
            meta, _, path = rec.partition(b"\t")
            mode, oid, _stage = meta.decode("ascii").split(" ")
            self._existing[path.decode("utf-8", "replace")] = (mode, oid)
        self._dirs = {d for p in self._existing for d in self._parents(p)}
        self._pending: dict[str, tuple[str, bytes]] = {}

    @staticmethod
    def _parents(path: str) -> list[str]:
        parts = path.split("/")
        return ["/".join(parts[:i]) for i in range(1, len(parts))]

    def _dir_conflict(self, path: str) -> bool:
        if path in self._dirs:
            return True  # a directory already lives at this path
        return any(d in self._existing or d in self._pending for d in self._parents(path))

    def _stage(self, path: str, data: bytes, mode: str) -> None:
        if path not in self._existing and path not in self._pending and self._dir_conflict(path):
            raise GuardViolation(f"D {path}: a file and a directory would collide (add-only)")
        self._pending[path] = (mode, data)
        self._dirs.update(self._parents(path))

    def _flush(self) -> None:
        if not self._pending:
            return
        items = sorted(self._pending.items())
        blob_dir = os.path.join(self._tmp, "blobs")
        os.makedirs(blob_dir, exist_ok=True)
        files = []
        for i, (_, (_, data)) in enumerate(items):
            fp = os.path.join(blob_dir, str(i))
            with open(fp, "wb") as fh:
                fh.write(data)
            files.append(fp)
        out = self.git.run("hash-object", "-w", "--no-filters", "--stdin-paths",
                           input=("\n".join(files) + "\n").encode("utf-8"))
        oids = out.decode("ascii").split()
        if len(oids) != len(items):
            raise GitError("git hash-object --stdin-paths returned the wrong number of objects")
        info = b"".join(f"{mode} {oid}\t{path}".encode("utf-8") + b"\0"
                        for (path, (mode, _)), oid in zip(items, oids))
        self.git.run("update-index", "-z", "--index-info", input=info, env=self._env)
        for (path, (mode, _)), oid in zip(items, oids):
            self._existing[path] = (mode, oid)
        self._pending.clear()

    def write_tree(self) -> str:
        """``git write-tree`` of the temp index; the temp index is removed afterwards."""
        try:
            self._flush()
            return self.git.run("write-tree", env=self._env).decode("ascii").strip()
        finally:
            shutil.rmtree(self._tmp, ignore_errors=True)


class TreeBuilder(_IndexBuilder):
    """Add-only tree assembly in a temporary index seeded from ``base_commit`` (or empty)."""

    def __init__(self, git: Git, base_commit: Optional[str],
                 mutable: frozenset[str] = MUTABLE_EVIDENCE_PATHS) -> None:
        super().__init__(git, base_commit)
        self.mutable = frozenset(mutable)
        self.added = 0
        self.identical = 0

    def _current(self, path: str) -> Optional[tuple[str, bytes]]:
        if path in self._pending:
            return self._pending[path]
        if path in self._existing:
            mode, oid = self._existing[path]
            data = self.git.read_blob(oid)
            return (mode, data) if data is not None else None
        return None

    def add(self, path: str, data: bytes, mode: str = "100644") -> bool:
        """Add a NEW blob; True if added, False if ``path`` already holds the same CONTENT
        (decompressed for ``*.json.gz``; the existing blob is kept); :class:`GuardViolation`
        if it holds other content and is not mutable."""
        _check_tree_path(path)
        _check_mode(mode)
        held = self._current(path)
        if held is None and (path in self._existing):
            raise GuardViolation(f"M {path}: the existing blob cannot be read")
        if held is not None:
            old_mode, old = held
            if old_mode == mode and content_of(path, old) == content_of(path, data):
                self.identical += 1
                return False
            if path not in self.mutable:
                raise GuardViolation(f"M {path}: add-only evidence already holds other content here")
        self._stage(path, data, mode)
        self.added += 1
        return True

    def replace(self, path: str, data: bytes, mode: str = "100644") -> None:
        """Set a ``mutable`` path (``state.json``); :class:`GuardViolation` for any other path."""
        _check_tree_path(path)
        _check_mode(mode)
        if path not in self.mutable:
            raise GuardViolation(f"M {path}: only {sorted(self.mutable)} may be replaced")
        self._stage(path, data, mode)


class DerivedTreeBuilder(_IndexBuilder):
    """A fresh (empty-index) tree for ``provenance-site``: every path set, nothing inherited."""

    def __init__(self, git: Git) -> None:
        super().__init__(git, None)

    def set(self, path: str, data: bytes, mode: str = "100644") -> None:
        _check_tree_path(path)
        _check_mode(mode)
        self._stage(path, data, mode)


def guard_blobs(repo_dir: str) -> dict[str, tuple[str, bytes]]:
    """``{data-tree path: (mode, bytes)}`` read from :data:`GUARD_FILES` sources in the main
    checkout. Raises :class:`GuardViolation` if a source is missing (both refs must carry the guard).
    Used at the evidence bootstrap and for every derived tree."""
    out: dict[str, tuple[str, bytes]] = {}
    for path, (mode, source) in sorted(GUARD_FILES.items()):
        full = os.path.join(repo_dir, *source.split("/"))
        if not os.path.isfile(full):
            raise GuardViolation(f"guard source {source} is missing from the checkout")
        with open(full, "rb") as fh:
            out[path] = (mode, fh.read())
    return out


def guard_drift(tree: "object", guard: dict[str, tuple[str, bytes]]) -> list[str]:
    """Guard paths whose bytes/mode in an evidence tree (a ``protocols.TreeReader``) differ from
    main's current ``guard`` — a ``::warning::`` each, never an error (critique item 18)."""
    drift = []
    mode_of = getattr(tree, "mode", None)
    for path, (mode, data) in sorted(guard.items()):
        held = tree.read(path)
        held_mode = mode_of(path) if callable(mode_of) else None
        if held != data or (held_mode is not None and held_mode != mode):
            drift.append(path)
    return drift


def commit_tree(git: Git, tree: str, parent: Optional[str], message: str) -> str:
    """``git commit-tree`` with the bot identity; ``parent`` ``None`` = parentless."""
    args = ["commit-tree", "--no-gpg-sign", tree]
    if parent:
        args += ["-p", parent]
    text = message if message.endswith("\n") else message + "\n"
    sha = git.run(*args, input=text.encode("utf-8")).decode("ascii").strip()
    if not _HEX40_RE.fullmatch(sha):
        raise GitError(f"git commit-tree returned {sha[:80]!r}")
    return sha


def tree_of(git: Git, commit: Optional[str]) -> Optional[str]:
    """``<commit>^{tree}`` or ``None``."""
    if not commit or commit.startswith("-"):
        return None
    proc = git.run_full("rev-parse", "--verify", "--quiet", "--end-of-options", f"{commit}^{{tree}}")
    sha = proc.stdout.decode("ascii", "replace").strip()
    return sha if proc.returncode == 0 and _HEX40_RE.fullmatch(sha) else None


def iter_changes(lines: Iterable[bytes]) -> list[TreeChange]:
    """Parse ``git diff-tree -r -z`` output records into :class:`TreeChange` (helper for guard_diff).

    ``lines`` are the NUL-separated tokens: a ``:<old mode> <new mode> <old> <new> <status>``
    token followed by its path token (``--no-renames``: one path per change)."""
    toks = [t for t in lines if t != b""]
    out: list[TreeChange] = []
    i = 0
    while i < len(toks):
        meta = toks[i].decode("ascii", "replace")
        if not meta.startswith(":") or i + 1 >= len(toks):
            raise GitError(f"git diff-tree: unexpected record {meta[:80]!r}")
        old_mode, new_mode, old_blob, new_blob, status = meta[1:].split(" ")
        out.append(TreeChange(status=status[:1], path=toks[i + 1].decode("utf-8", "replace"),
                              old_mode=old_mode, new_mode=new_mode, old_blob=old_blob, new_blob=new_blob))
        i += 2
    return out


def _empty_tree(git: Git) -> str:
    return git.run("mktree", input=b"").decode("ascii").strip()


#: The head of each guard rule's message (``guard_diff`` raises ``<head>`` + its detail); the
#: selftest matches a refusal on its rule's head, so a case cannot pass through another rule.
GUARD_RULE_HEADS = {
    "D": "D {path}: add-only evidence never deletes a path",
    "guard": "guard {path}: the guard files never change after bootstrap",
    "M": "M {path}: only ",
    "0B": "0B {path}: a blob may never be (or become) empty",
}


def guard_diff(git: Git, old_commit: Optional[str], new_commit: str,
               mutable: frozenset[str] = MUTABLE_EVIDENCE_PATHS) -> list[TreeChange]:
    """The pre-push guard. Returns the change list (``[]`` = identical tree, push nothing);
    raises :class:`GuardViolation` on: any ``D``; ``M`` outside ``mutable``; a blob that becomes
    0 bytes; a guard-file change after bootstrap; any status other than ``A``/``M``.

    ``old_commit`` ``None`` (bootstrap) diffs against the empty tree, so every path
    must be an ``A``. Rules are checked change by change in diff-tree (path) order,
    and the first violation is raised naming its path and rule."""
    old = old_commit or _empty_tree(git)
    out = git.run("diff-tree", "-r", "--no-renames", "--no-commit-id", "-z", old, new_commit)
    changes = iter_changes(out.split(b"\0"))
    zero = "0" * 40
    sizes = git.blob_sizes(c.new_blob for c in changes if c.status in ("A", "M") and c.new_blob != zero)
    for c in changes:
        if c.status == "D":
            raise GuardViolation(GUARD_RULE_HEADS["D"].format(path=c.path))
        if c.path in GUARD_FILES and old_commit is not None and c.status != "A":
            raise GuardViolation(GUARD_RULE_HEADS["guard"].format(path=c.path))
        if c.status in ("M", "T") and c.path not in mutable:
            raise GuardViolation(GUARD_RULE_HEADS["M"].format(path=c.path)
                                 + f"{', '.join(sorted(mutable))} may be modified")
        if c.status not in ("A", "M"):
            raise GuardViolation(f"{c.status} {c.path}: only additions (and the {', '.join(sorted(mutable))} "
                                 "modification) are allowed")
        if sizes.get(c.new_blob) == 0:
            raise GuardViolation(GUARD_RULE_HEADS["0B"].format(path=c.path))
    return changes


def _porcelain_flag(stdout: bytes, ref: str) -> Optional[str]:
    target = f"refs/heads/{ref}"
    for line in stdout.decode("utf-8", "replace").splitlines():
        m = _PORCELAIN_RE.match(line)
        if m and m.group(3) == target:
            return m.group(1)
    return None


def _push(git: Git, ref: str, args: list[str], *, retries: int) -> PushResult:
    """Shared push loop: credential through env, porcelain parsing, transport retries."""
    env: dict[str, str] = {}
    if git.token:
        env, b64 = credential_env(git.token)
        _mask_once(b64)
    last_err = b""
    rc = 0
    for attempt in range(1, retries + 2):
        argv = ("push", "--porcelain", "--no-verify", *args)
        proc = git.run_full(*argv, env=env)
        flag = _porcelain_flag(proc.stdout, ref)
        err = proc.stderr.decode("utf-8", "replace")
        if proc.returncode == 0 and flag in (" ", "*", "+", "="):
            return PushResult(pushed=True, attempts=attempt)
        if flag == "!" or any(m in err for m in _REJECTED_MARKERS):
            detail = next((ln for ln in (proc.stdout.decode("utf-8", "replace") + "\n" + err).splitlines()
                           if ln.startswith("!") or "rejected" in ln or "stale" in ln), "rejected")
            raise ForeignTip(redact(f"push to refs/heads/{ref} rejected: {detail.strip()}", git.secrets()))
        last_err, rc = proc.stderr, proc.returncode
    raise git._error(("push", "origin", f"refs/heads/{ref}", f"({retries + 1} attempts)"), rc, last_err)


def push_fast_forward(git: Git, ref: str, new: str, expected_old: Optional[str], *,
                      retries: int = 3) -> PushResult:
    """Fast-forward push of ``new`` to ``refs/heads/<ref>`` with ``git.token`` (module docstring,
    step 4): transport failures retried with the SAME commit then :class:`GitError`; any rejection
    → :class:`ForeignTip`.

    The remote tip is re-read first and must equal ``expected_old`` (``None`` =
    the ref must not exist): a fast-forward push alone would accept a remote that
    was ROLLED BACK to an ancestor of ``new``, silently re-anchoring the rollback."""
    if ref not in REFS or not _HEX40_RE.fullmatch(new or ""):
        raise ValueError(f"bad push ({ref!r}, {new!r})")
    remote = remote_tip(git, ref)
    if remote != expected_old:
        raise ForeignTip(f"{ref}: remote tip {_short(remote)} is not the planned {_short(expected_old)}")
    return _push(git, ref, ["origin", f"{new}:refs/heads/{ref}"], retries=retries)


def push_force_with_lease(git: Git, ref: str, new: str, expected_old: Optional[str]) -> PushResult:
    """``git push --force-with-lease=refs/heads/<ref>:<expected_old or empty>``; lease failure →
    :class:`ForeignTip`."""
    if ref not in REFS or not _HEX40_RE.fullmatch(new or ""):
        raise ValueError(f"bad push ({ref!r}, {new!r})")
    if expected_old is not None and not _HEX40_RE.fullmatch(expected_old):
        raise ValueError(f"bad lease {expected_old!r}")
    lease = f"--force-with-lease=refs/heads/{ref}:{expected_old or ''}"
    return _push(git, ref, [lease, "origin", f"{new}:refs/heads/{ref}"], retries=3)


def remote_tip(git: Git, ref: str) -> Optional[str]:
    """Token-less ``git ls-remote origin refs/heads/<ref>`` sha, or ``None`` when the ref is absent."""
    return git.remote_heads([ref]).get(ref)


def scan_marks(gh: GitHubAPI, git: Git, *, now_epoch: int, horizon_days: int,
               main_ref: str = "refs/remotes/origin/main",
               need: tuple[str, ...] = REFS) -> tuple[list[Mark], dict[str, int]]:
    """``(verified marks newest first by mark_order, counts)`` from ``GET /actions/artifacts``.

    Pages in the API's order (artifact id, descending — NOT upload order, module
    docstring) and stops after the page on which (a) every ref in ``need`` has a
    verified ``tip`` mark and the oldest artifact seen so far was uploaded more
    than :data:`MARK_ORDER_SLACK_SECONDS` before the OLDEST of those refs' newest
    tips (by :func:`mark_order`) — so no unread, lower-id artifact can be newer
    than any of them — or (b) the page's oldest artifact is older than the
    horizon, or (c) the list ends. Each candidate run is verified once: the
    artifact's ``workflow_run`` gives ``head_branch`` / ``head_sha`` (pre-filter:
    ``main``, on ``git.first_parent_log(main_ref)``), then ``GET
    /actions/runs/{id}`` confirms ``path == WORKFLOW_PATH`` and ``event in
    MARK_EVENTS``. ``counts`` = {pages, runs_checked, runs_verified,
    marks_rejected} for the summary. The cost is about one page per 1.4 days
    since the newest checkpoint plus, usually, nothing more (a page spans ~34 h,
    far more than the 6 h slack) — 6,519 artifacts on 2026-10-14; 100 cover ~34 h.

    The run object is checked too (``head_branch``, ``head_sha`` on main's first
    parents), not only the artifact's embedded ``workflow_run``. ``runs_verified``
    counts runs that passed; ``runs_checked`` every run GET.
    """
    branch = main_ref.rsplit("/", 1)[-1]
    on_main = {sha for sha, _ in git.first_parent_log(main_ref)}
    horizon = now_epoch - horizon_days * 86400
    counts = {"pages": 0, "runs_checked": 0, "runs_verified": 0, "marks_rejected": 0}
    verdicts: dict[int, bool] = {}
    marks: list[Mark] = []
    newest_tip: dict[str, Mark] = {}
    oldest_seen: Optional[int] = None

    def run_ok(run_id: int) -> bool:
        if run_id not in verdicts:
            counts["runs_checked"] += 1
            run = gh.get(f"/actions/runs/{run_id}")
            ok = (isinstance(run, dict) and run.get("path") == WORKFLOW_PATH
                  and run.get("event") in MARK_EVENTS and run.get("head_branch") == branch
                  and run.get("head_sha") in on_main)
            verdicts[run_id] = ok
            if ok:
                counts["runs_verified"] += 1
        return verdicts[run_id]

    for items, _ in gh.iter_pages("/actions/artifacts", None, key="artifacts", max_pages=1000):
        counts["pages"] += 1
        oldest_in_page: Optional[int] = None
        for art in items:
            created = _epoch(art.get("created_at"))
            if created is not None:
                oldest_in_page = created if oldest_in_page is None else min(oldest_in_page, created)
                oldest_seen = created if oldest_seen is None else min(oldest_seen, created)
            parsed = parse_mark_name(str(art.get("name") or ""))
            if parsed is None:
                continue
            kind, ref, sha = parsed
            if created is None or created < horizon:
                continue
            wr = art.get("workflow_run") or {}
            run_id = wr.get("id")
            seq = art.get("id")
            if (not isinstance(run_id, int) or not isinstance(seq, int) or wr.get("head_branch") != branch
                    or wr.get("head_sha") not in on_main or not run_ok(run_id)):
                counts["marks_rejected"] += 1
                continue
            m = Mark(seq=seq, kind=kind, ref=ref, sha=sha, run_id=run_id, created=created)
            marks.append(m)
            if kind == "tip" and (ref not in newest_tip or mark_order(m) > mark_order(newest_tip[ref])):
                newest_tip[ref] = m
        settled = (all(r in newest_tip for r in need) and oldest_seen is not None
                   and oldest_seen + MARK_ORDER_SLACK_SECONDS < min(newest_tip[r].created for r in need))
        if settled or (oldest_in_page is not None and oldest_in_page < horizon) or not items:
            break
    marks.sort(key=mark_order, reverse=True)
    return marks, counts


def _epoch(ts: Optional[str]) -> Optional[int]:
    if not isinstance(ts, str):
        return None
    try:
        return int(datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# selftest (scripts/provenance.sh --selftest via selftest.run)

_CONTINUITY_CASES = os.path.join(os.path.dirname(__file__), "..", "..", "tests", "fixtures",
                                 "continuity_cases.json")


class _Sandbox:
    """A throwaway work repo with a local bare ``origin`` (file protocol allowed for it only)."""

    def __init__(self, root: str) -> None:
        self.remote = os.path.join(root, "origin.git")
        self.work = os.path.join(root, "work")
        os.makedirs(self.work)
        env = {"GIT_ALLOW_PROTOCOL": "https:file"}
        Git(root, env=env).run("init", "-q", "--bare", self.remote)
        self.git = Git(self.work, env=env)
        self.git.run("init", "-q")
        self.git.run("remote", "add", "origin", self.remote)

    def commit(self, files: dict[str, bytes], parent: Optional[str], *, modes: Optional[dict] = None) -> str:
        b = DerivedTreeBuilder(self.git)
        for p, data in files.items():
            b.set(p, data, (modes or {}).get(p, "100644"))
        return commit_tree(self.git, b.write_tree(), parent, "selftest")


def _raises(exc: type, fn: Callable[[], object]) -> bool:
    try:
        fn()
    except exc:
        return True
    return False


def _guard_case(mutate: Callable[[dict], dict], expect: str) -> Callable[[], bool]:
    """True only when ``guard_diff`` refuses the mutation with a message STARTING ``expect`` — the
    rule's own head (``"<rule> <path>: <rule text>"``), so a case pins its rule: with that rule
    deleted a later rule may still refuse the same change (a D also fails "only A/M", a guard-file
    M also fails "M outside state.json"), and the case must then report False."""
    def run() -> bool:
        with tempfile.TemporaryDirectory() as root:
            sb = _Sandbox(root)
            base = {"vercel.json": b"{}\n", "scripts/vercel-ignore-build.sh": b"exit 0\n",
                    "state.json": b"{}\n", "receipts/2026/08/10/1.a1.json.gz": b"gz-1",
                    "raw/pr/1.json.gz": b"gz-2"}
            modes = {"scripts/vercel-ignore-build.sh": "100755"}
            old = sb.commit(base, None, modes=modes)
            new = sb.commit(mutate(dict(base)), old, modes=modes)
            try:
                guard_diff(sb.git, old, new)
            except GuardViolation as exc:
                return str(exc).startswith(expect)
            return False
    return run


def _guard_allows_state_and_adds() -> bool:
    with tempfile.TemporaryDirectory() as root:
        sb = _Sandbox(root)
        old = sb.commit({"state.json": b"{}\n", "raw/pr/1.json.gz": b"gz"}, None)
        new = sb.commit({"state.json": b'{"x": 1}\n', "raw/pr/1.json.gz": b"gz", "raw/pr/2.json.gz": b"g2"}, old)
        same = sb.commit({"state.json": b"{}\n", "raw/pr/1.json.gz": b"gz"}, old)
        return ({c.status for c in guard_diff(sb.git, old, new)} == {"A", "M"}
                and guard_diff(sb.git, old, same) == [])


def _rejected_push_is_foreign() -> bool:
    with tempfile.TemporaryDirectory() as root:
        sb = _Sandbox(root)
        a = sb.commit({"FORMAT": b"a\n"}, None)
        sb.git.run("push", "-q", "origin", f"{a}:refs/heads/{EVIDENCE_REF}")
        b = sb.commit({"FORMAT": b"b\n"}, a)
        c = sb.commit({"FORMAT": b"c\n"}, a)
        sb.git.run("push", "-q", "origin", f"{b}:refs/heads/{EVIDENCE_REF}")
        # remote moved under us: the pre-check refuses; with a stale expectation equal to the
        # remote, a non-fast-forward push is rejected by git itself.
        moved = _raises(ForeignTip, lambda: push_fast_forward(sb.git, EVIDENCE_REF, c, a))
        nonff = _raises(ForeignTip, lambda: push_fast_forward(sb.git, EVIDENCE_REF, c, b))
        return moved and nonff and remote_tip(sb.git, EVIDENCE_REF) == b


def _push_error_free_of_token() -> bool:
    # A token whose header base64 is path-safe (no "/", "+" or "=" padding), so BOTH secrets can sit
    # verbatim in the remote path and git's own stderr echoes them: without redact() they would
    # reach the message. The raw push below proves git does echo them (else the case is vacuous).
    token = "ghs_SELFTEST_TOKEN"
    cred, b64 = credential_env(token)
    if not re.fullmatch(r"[A-Za-z0-9]+", b64):
        return False
    with tempfile.TemporaryDirectory() as root:
        sb = _Sandbox(root)
        a = sb.commit({"FORMAT": b"a\n"}, None)
        git = Git(sb.work, env={"GIT_ALLOW_PROTOCOL": "https:file"}, token=token)
        git.run("remote", "set-url", "origin", os.path.join(root, f"x-{token}-{b64}", "missing.git"))
        spec = f"{a}:refs/heads/{EVIDENCE_REF}"
        raw = git.run_full("push", "--porcelain", "--no-verify", "origin", spec, env=cred)
        echoed = raw.stderr.decode("utf-8", "replace")
        if raw.returncode == 0 or token not in echoed or b64 not in echoed:
            return False
        try:
            _push(git, EVIDENCE_REF, ["origin", spec], retries=0)
        except GitError as exc:
            msg = str(exc)
            return token not in msg and b64 not in msg and "***" in msg
        return False


def selftest_cases() -> list:
    """Offline negative controls for ``selftest.run`` (temp repo, local bare remote, no network): each
    guard rule (D, M outside state.json, 0-byte blob, guard-file change), an identical tree = no push,
    every row of ``continuity_cases.json``, a rejected push = ForeignTip, a failing push's error carrying
    neither the token nor its base64. H1."""
    def drop(d: dict) -> dict:
        d.pop("raw/pr/1.json.gz")
        return d

    def modify(d: dict) -> dict:
        d["receipts/2026/08/10/1.a1.json.gz"] = b"other"
        return d

    def empty(d: dict) -> dict:
        d["state.json"] = b""
        return d

    def guard_change(d: dict) -> dict:
        d["vercel.json"] = b'{"x": 1}\n'
        return d

    cases: list = [
        ("gitstore guard refuses D", _guard_case(drop, GUARD_RULE_HEADS["D"].format(path="raw/pr/1.json.gz"))),
        ("gitstore guard refuses M outside state.json",
         _guard_case(modify, GUARD_RULE_HEADS["M"].format(path="receipts/2026/08/10/1.a1.json.gz"))),
        ("gitstore guard refuses a 0-byte blob", _guard_case(empty, GUARD_RULE_HEADS["0B"].format(path="state.json"))),
        ("gitstore guard refuses a guard-file change",
         _guard_case(guard_change, GUARD_RULE_HEADS["guard"].format(path="vercel.json"))),
        ("gitstore guard allows A + state.json M; identical tree = no push", _guard_allows_state_and_adds),
        ("gitstore rejected push raises ForeignTip", _rejected_push_is_foreign),
        ("gitstore failing push error carries neither token nor base64", _push_error_free_of_token),
    ]
    try:
        with open(_CONTINUITY_CASES, encoding="utf-8") as fh:
            table = json.load(fh)["cases"]
    except (OSError, ValueError, KeyError) as exc:
        def missing(exc: Exception = exc) -> bool:
            return False
        return cases + [(f"gitstore continuity table readable ({type(exc).__name__})", missing)]
    for case in table:
        def row(case: dict = case) -> bool:
            kw = {"max_chain": case["max_chain"]} if "max_chain" in case else {}
            v = continuity_verdict(ref=case["ref"], tip=case["tip"], marks=[Mark(**m) for m in case["marks"]],
                                   first_parent=lambda s: case["parents"].get(s),
                                   is_ancestor=parents_is_ancestor(case["parents"]), **kw)
            return (v.verdict == case["expect"] and ("chain" not in case or list(v.chain) == case["chain"])
                    and list(v.conflicts) == case.get("conflicts", []))
        cases.append((f"gitstore continuity {case['name']}", row))
    return cases


def parents_is_ancestor(parents: dict, limit: int = 64) -> Callable[[str, str], bool]:
    """``is_ancestor`` over a ``{sha: first parent}`` map (the shared continuity table's
    ``parents``): walk first parents from the descendant. The evidence ref is linear, so the
    first-parent walk IS its ancestry; Reeve's suite uses the same walk over the same map."""
    def is_ancestor(a: str, d: str) -> bool:
        sha: Optional[str] = d
        for _ in range(limit):
            if sha == a:
                return True
            sha = parents.get(sha)
            if sha is None:
                return False
        return False
    return is_ancestor


_ = subprocess  # the one module allowed to import it (tests/test_purity.py)
