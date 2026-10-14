"""Episodes — review rounds keyed by author-push sha, folds, stale/after-merge flags, edges, decision rows.

**Push evidence** (:func:`pushes`). REST exposes no push time. A sha is a
*pushed head* when it is the PR's final head, or a ``ci_runs`` row names it
(any event), or ``statuses`` holds at least one status for it (Vercel and
CodeRabbit post one per pushed head even when ci.yml did not run — PR
#634's three one-second web commits are each a round only by this rule).
Its ``pushed_at`` is the earliest of those runs' ``created_at`` and those
statuses' ``created_at``. A pushed head missing from ``commits`` (force-
pushed away) still forms a push, with no commits, and the record gains
``incomplete: force-pushed-heads``.

**Push groups.** Walk ``commits`` in API order; every commit joins the
current group; a commit that is a pushed head closes it (group head = that
commit). Pushed heads absent from ``commits`` become their own groups, placed
by ``pushed_at``.

**Regen fold.** A group whose head commit is a regen commit-back — subject
``== REGEN_SUBJECT`` AND author email ``== REGEN_AUTHOR`` AND exactly one
parent (scripts/reviewer-signoff.sh's constants, drift-pinned by
tests/test_episodes.py) — folds into the preceding round, whatever its
``Preview-Diff`` trailer says (the trailer is recorded as
``commit.regen.fields.preview_diff``). A merge-of-main commit is just a
commit of its group; a group whose HEAD is a merge-of-main is an author push
and therefore a round (the golden's ``R:636:f4e36eb9``).

**Rounds** (:func:`rounds`). One round per author group:
``R:<pr>:<head sha8>``, ``heads`` = [author head] + folded regen heads,
``commits`` = every commit of those groups, ``pushed_at`` = the author
head's push time, ``start`` = ``pushed_at``, ``end`` = the next round's
``pushed_at`` (the last round: the PR's ``merged_at``/``closed_at``).
Acceptance: NVC-1 = 15 (#636), SBC-1 = {371: 2, 397: 14}, CC-5 = 13 (#634).

**Episode of an event** (:func:`assign`):

* ``brief.*`` → ``E0:brief:<issue>``, except ``brief.closed`` whose
  ``closed_by_pr`` is set → ``M:<pr>``;
* ``pr.merged``, ``pr.closed``, ``deploy.production`` → ``M:<pr>``;
* ``commit.*`` → the round whose ``commits`` hold it;
* every other PR event → the round whose ``pushed_at`` is the latest one
  ``<= ts`` (folded regen heads count as their round's), or the FIRST round
  when ``ts`` precedes every push (``pr.opened``);
* direct-to-main commits → ``C:<sha8>``; committed rows → ``D:<date>``.

**Flags.** ``head_sha`` = the live pushed head at ``ts`` (the latest
``pushed_at <= ts``; for a commit, its group head). ``stale_sha`` = the
event's marker sha is not among its round's ``heads`` (NVC-8: Drik's
sign-off naming ``9a751b26`` lands in ``R:636:f4e36eb9``). ``after_merge``
= ``merged_at`` is set and ``ts > merged_at``.

**verifies** (:func:`verifies_edges`, ``review.signoff`` only): the
``commit.design``/``commit.fix``/``commit.human`` shas at or before the
marker sha in commit order and after the previous sign-off of the SAME
family's marker sha; ``[]`` when the marker sha is not a PR commit.

**Decision rows** (:func:`decision_rows`). Committed rows become day-precision
events from main at the harvest's main sha:

* ``designs/<d>/PM.md`` ``## Decision log`` table rows → ``decision.pm_log``
  (parse = a line-for-line port of site/lib/timeline.mjs
  ``parseDecisionLog``: header ``| Date | Decision | Reason |``, separator,
  rows until a blank or pipe-less line, a real ``YYYY-MM-DD`` first cell);
* ``designs/<d>/NOTES.md`` ``## Field test log`` ``### YYYY-MM-DD — …``
  headings → ``field_test`` (``parseFieldTestLog``);
* ``designs/<d>/NOTES.md`` ``## Changelog`` ``### <v> — YYYY-MM-DD — <t>``
  headings → ``changelog`` (``parseChangelog``);
* ``designs/<d>/NOTES.md`` ``## Decisions log`` / ``## Decision log``
  top-level bullets ``- YYYY-MM-DD:`` / ``- **YYYY-MM-DD**`` →
  ``decision.notes_log`` (new; nuggs-vent-cap's nine rows from L233).

Each carries ``fields`` ``{file, line, line_sha256 (sha256 of the line's
text), added_in_sha, added_in_pr}``: ``GitReader.blame_lines`` gives the sha
that added the line AND the line's number in that commit — ``line`` is that
ORIGINAL line and the ``url`` is ``blob/<added_in_sha>/designs/<d>/<file>#L<line>``,
so neither changes when main moves (critique item 6; ``added_in_sha`` is
required — blame over the full-history checkout always resolves); ``added_in_pr`` is that sha's PR — the first-parent main commit
that contains it, read from its subject ``(#N)`` (squash) or ``Merge pull
request #N`` (merge), else, for a rebase merge, the PR record whose commit
list holds the sha (``commit_to_pr``). The id is
``row:<design>:<file>:<line_sha256[:16]>:<k>`` (``k`` = occurrence index of
identical text), so a row keeps its id when lines above it move; the site
matches rows by ``line_sha256``, never by line number. No row text is
stored (the site renders committed text from its own checkout).

**Parity with site/lib/timeline.mjs** (critique item 25). The three ports are
pinned to timeline.mjs by ``site/test/provenance-rows.test.mjs``: it runs
timeline.mjs AND this module (``python3`` with ``PYTHONPATH=tools/provenance/
src``) over every ``designs/*/PM.md`` / ``NOTES.md`` in the checkout and
asserts identical line selection. It lives in the site's suite, not in
``provenance-tests``, because timeline.mjs imports ``marked`` (through
markdown.mjs) and so needs ``site/node_modules``; the ``site-build`` job runs
``npm --prefix site test`` on EVERY PR (the site/lib/lineage.mjs ↔
tools/lineage precedent, python3 preinstalled), so a drift on either side
fails a required check.

**Placement after the join** (:func:`place`; critique item 14). The derive
order is fixed: ``extract_*`` (events placed from the raw document) →
``serving.annotate_record`` → ``serving.receipt_events`` (``job.reviewer``
events, returned UNPLACED: ``episode``/``head_sha`` ``None``) →
:func:`place` (assigns every unplaced event with :func:`assign` over
:func:`rounds_from_record`) → ``views``. Records are stored only after
:func:`place`, so every stored event has an episode.

Owner: H3. Pure (git through ``protocols.GitReader``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .protocols import GitReader, Round

#: Byte-identical to scripts/reviewer-signoff.sh (drift-pinned).
REGEN_SUBJECT = "CI: regenerate previews and product pages"
REGEN_AUTHOR = "41898282+github-actions[bot]@users.noreply.github.com"
REGEN_TRAILER = "Preview-Diff"


@dataclass(frozen=True)
class Push:
    """One push group: ``head`` sha, ``pushed_at``, its ``commits`` (API order), ``regen``."""

    head: str
    pushed_at: Optional[str]
    commits: tuple[str, ...]
    regen: bool


@dataclass
class Placement:
    """Where an event lands: ``episode``, ``head_sha``, ``stale_sha``, ``after_merge``."""

    episode: str
    head_sha: Optional[str]
    stale_sha: bool
    after_merge: bool


def is_regen_commit(commit: dict[str, Any]) -> bool:
    """raw-pr@1 commit → regen commit-back identity (subject, author email, one parent)."""
    raise NotImplementedError("builder H3")


def pushes(raw_pr: dict[str, Any]) -> list[Push]:
    """Push groups in push order (module docstring)."""
    raise NotImplementedError("builder H3")


def rounds(raw_pr: dict[str, Any]) -> list[Round]:
    """Rounds with regen pushes folded (module docstring)."""
    raise NotImplementedError("builder H3")


def assign(event: dict[str, Any], rounds_: list[Round], *, pr: Optional[int],
           merged_at: Optional[str]) -> Placement:
    """The episode placement of one event (module docstring)."""
    raise NotImplementedError("builder H3")


def round_dict(r: Round) -> dict[str, Any]:
    """A :class:`protocols.Round` as the contract ``round`` object (lists, not tuples)."""
    raise NotImplementedError("builder H3")


def rounds_from_record(record: dict[str, Any]) -> list[Round]:
    """The record's stored ``rounds`` back as :class:`protocols.Round` objects (inverse of
    :func:`round_dict`; ``[]`` for a non-PR record)."""
    raise NotImplementedError("builder H3")


def place(record: dict[str, Any]) -> dict[str, Any]:
    """A NEW record whose every event with ``episode is None`` is placed by :func:`assign` over
    :func:`rounds_from_record` (``head_sha``, ``stale_sha``, ``after_merge`` set); already-placed
    events are untouched; events re-sorted by ``canonical.event_sort_key``."""
    raise NotImplementedError("builder H3")


def verifies_edges(events: list[dict[str, Any]], raw_pr: dict[str, Any]) -> dict[str, list[str]]:
    """``{event id: [verified commit shas]}`` for the record's ``review.signoff`` events."""
    raise NotImplementedError("builder H3")


@dataclass(frozen=True)
class Row:
    """One committed row located in a file at main: ``kind``, ``file``, ``line``, ``date``, ``text``."""

    kind: str
    file: str
    line: int
    date: str
    text: str


def parse_pm_decision_log(text: str) -> list[Row]:
    """Port of timeline.mjs ``parseDecisionLog`` (rows only; problems are not this module's job)."""
    raise NotImplementedError("builder H3")


def parse_field_test_log(text: str) -> list[Row]:
    """Port of timeline.mjs ``parseFieldTestLog``."""
    raise NotImplementedError("builder H3")


def parse_changelog(text: str) -> list[Row]:
    """Port of timeline.mjs ``parseChangelog``."""
    raise NotImplementedError("builder H3")


def parse_notes_decisions(text: str) -> list[Row]:
    """NOTES.md ``## Decisions log``/``## Decision log`` dated top-level bullets."""
    raise NotImplementedError("builder H3")


def decision_rows(git: GitReader, main_sha: str, design: str, *, owner: str, repo: str,
                  commit_to_pr: dict[str, int]) -> list[dict[str, Any]]:
    """event@1 rows for one design at ``main_sha`` (module docstring): ``GitReader.blame_lines``
    → (added_in_sha, original line) → PR; nothing of ``main_sha`` is stored in a row."""
    raise NotImplementedError("builder H3")


@dataclass
class EpisodeIndex:
    """Per-record episode list for views: ``[{id, kind, pr, issue, head, start, end, events}]``."""

    episodes: list[dict[str, Any]] = field(default_factory=list)


def episodes_of(events: list[dict[str, Any]], rounds_: list[Round]) -> list[dict[str, Any]]:
    """The view@1 ``episodes`` list for a set of placed events (sorted by start, then id)."""
    raise NotImplementedError("builder H3")
