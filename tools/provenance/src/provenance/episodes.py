"""Episodes — review rounds keyed by author-push sha, folds, stale/after-merge flags, edges, decision rows.

**Push evidence** (:func:`pushes`). REST exposes no push time. A sha is a
*pushed head* when it is the PR's final head, or a ``ci_runs`` row names it
(any event), or ``statuses`` holds at least one status for it (Vercel and
CodeRabbit post one per pushed head even when ci.yml did not run — PR
#634's three one-second web commits are each a round only by this rule).
Its ``pushed_at`` is the earliest of those runs' ``created_at`` and those
statuses' ``created_at``. A final head with no run and no status (a degraded
capture: ``no-ci-runs`` plus ``statuses-unavailable:<sha8>``) falls back to
its commit's committer date (author date when absent) — a lower bound, since
a commit exists before it is pushed, and seconds early for an agent push
(#371's final head 69c14983: committed 23:41:38, first status 23:41:42) —
accepted only when it is later than every other pushed head's time (the
final head is the last push); otherwise, or when the final head is not in
``commits``, ``None``. Without the fallback the final round would never be
live, so sign-offs naming the live head would land in the previous round
flagged ``stale_sha``.
A pushed head missing from ``commits`` (force-pushed away) still forms a
push, with no commits, and the record gains ``incomplete:
force-pushed-heads`` (``extract.extract_pr``; not when ``commits-truncated``,
where the missing heads are the truncation's).

**Push groups.** Walk ``commits`` in API order; every commit joins the
current group; a commit that is a pushed head closes it (group head = that
commit). Commits left after the last pushed head (only possible past the
250-commit truncation) form one more group headed by the last listed commit,
``pushed_at`` ``None``. Pushed heads absent from ``commits`` become their own
groups, inserted before the first walked group whose ``pushed_at`` is later
than theirs (the walk order itself is never changed).

**Regen fold.** A group whose head commit is a regen commit-back — subject
``== REGEN_SUBJECT`` AND author email ``== REGEN_AUTHOR`` AND exactly one
parent (scripts/reviewer-signoff.sh's constants, drift-pinned by
tests/test_episodes.py) — folds into the preceding round, whatever its
``Preview-Diff`` trailer says (the trailer is recorded as
``commit.regen.fields.preview_diff``). A merge-of-main commit is just a
commit of its group; a group whose HEAD is a merge-of-main is an author push
and therefore a round (the golden's ``R:636:f4e36eb9``). A regen group with
no preceding round (the PR's first push) is a round of its own.

**Rounds** (:func:`rounds`). One round per author group:
``R:<pr>:<head sha8>``, ``heads`` = [author head] + folded regen heads,
``commits`` = every commit of those groups (group order), ``pushed_at`` =
the author head's push time, ``start`` = ``pushed_at``, ``end`` = the next
round's ``pushed_at`` (the last round: the PR's ``merged_at`` else
``closed_at``). Acceptance: NVC-1 = 15 (#636), SBC-1 = {371: 2, 397: 14},
CC-5 = 13 (#634).

**Episode of an event** (:func:`assign`), over :class:`protocols.Round`
objects only — so the extractor (which has the raw document) and
:func:`place` (which has only the stored record) place identically:

* ``brief.*`` → ``E0:brief:<issue>``, except ``brief.closed`` whose
  ``closed_by_pr`` is set → ``M:<pr>``;
* ``pr.merged``, ``pr.closed``, ``deploy.production`` → ``M:<pr>``;
* ``commit.*`` of a PR → the round whose ``commits`` hold it; a commit event
  with no PR (a direct-to-main commit record) → ``C:<sha8>``;
* committed rows (``decision.pm_log``, ``decision.notes_log``,
  ``field_test``, ``changelog``) and ``release`` → ``D:<YYYY-MM-DD>`` (the
  row's date / the publication day);
* ``job.reviewer`` and ``status.reviewer_signoff`` (:data:`HEAD_SHA_KINDS`:
  their ``sha`` is the head the reviewer job ran on / the status was posted
  to) → the round whose ``heads`` hold that sha, ``head_sha`` that round's
  head — a reviewer job or a ``reviewer-signoff`` status about head X that
  starts or posts after head Y was pushed judged X's round, not Y's (the
  audit golden places all 54 + 22 / 58 + 20 / 52 + 20 of them so; the ts
  rule misplaced 3 + 3 nuggs-vent-cap and 8 + 9 sbc-case ones a round late,
  unflagged). A sha in no round's ``heads`` (a force-pushed-away head) falls
  back to the ts rule below;
* every other PR event → the round whose ``pushed_at`` is the latest one
  ``<= ts`` (a folded regen push never starts a round, so it belongs to its
  round's span), or the FIRST round when ``ts`` precedes every push
  (``pr.opened`` can); a PR with no round at all → ``M:<pr>``.

**Flags.** ``head_sha`` = the head of the live round at ``ts`` — its author
push, the latest round ``pushed_at <= ts`` — and ``None`` when ``ts``
precedes every push; for a commit, the head of the push group that carried
it (read from the round: ``heads`` close their groups inside ``commits``).
The record keeps only the author head's push time, so a folded regen head is
never ``head_sha`` of a non-commit event (it IS one of the round's ``heads``,
which is what ``stale_sha`` reads). ``stale_sha`` = the event carries a
MARKER sha (``review.signoff``, ``triage.verdict``, ``coach.lock`` — the sha
the marker names) that is not among its round's ``heads`` (NVC-8: Drik's
sign-off naming ``9a751b26`` lands in ``R:636:f4e36eb9``); false for every
other event. ``after_merge`` = ``merged_at`` is set and ``ts > merged_at``
for an event kept in a live round (it stays there); never for an
``M:<pr>``-only kind (:data:`MERGE_KINDS` — a production deploy follows the
merge by definition, so the flag would only be noise on the very loose ends
it exists to surface).

**verifies** (:func:`verifies_edges`, ``review.signoff`` only): the
``commit.design``/``commit.fix``/``commit.human`` shas after the previous
sign-off of the SAME family (in event order; its marker sha's position in
``commits``) up to and including the marker sha, in commit order; ``[]``
when the marker sha is not a PR commit (that sign-off then does not move the
family's position) or when the previous sign-off named a later commit.

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
  ``decision.notes_log`` (new; nuggs-vent-cap's nine rows from L233). A
  decision TABLE under a NOTES.md heading is not a bullet and yields nothing
  here.

The ports reproduce JavaScript's semantics, not Python's: ``\\s``, ``.``,
``trim()`` and ``\\d`` are spelled out as JS defines them
(:data:`JS_WS`), and the real-calendar date check is the UTC round-trip
``isRealDate`` performs (proleptic Gregorian, year 0000 included).

Each carries ``fields`` ``{file, line, line_sha256 (sha256 of the line's
text — the raw line as ``text.split("\\n")`` yields it), added_in_sha,
added_in_pr}``: ``GitReader.blame_lines`` gives the sha that added the line
AND the line's number in that commit — ``line`` is that ORIGINAL line and
the ``url`` is ``blob/<added_in_sha>/designs/<d>/<file>#L<line>``, so neither
changes when main moves (critique item 6; ``added_in_sha`` is required —
blame over the full-history checkout always resolves, so a blame that does
not cover the file line for line, ``[]`` from a failed ``git blame``
included, raises :class:`BlameUnavailable` and derive aborts like a failed
bulk fetch: failing closed instead of publishing a view whose rows silently
vanished); ``added_in_pr`` is that sha's
PR — the first-parent main commit that contains it (the sha itself when it
is on the first-parent chain, else the oldest first-parent MERGE commit it
is an ancestor of), read from its subject ``(#N)`` (squash) or ``Merge pull
request #N`` (merge), else, for a rebase merge, the PR record whose commit
list holds the sha (``commit_to_pr``, tried for the sha, then for that main
commit). The id is ``row:<design>:<file>:<line_sha256[:16]>:<k>`` (``k`` =
the 0-based occurrence index of identical text among that file's rows), so a
row keeps its id when lines above it move; the site matches rows by
``line_sha256``, never by line number. No row text is stored (the site
renders committed text from its own checkout). Rows are unattributed:
trust ``none`` (the site reads them "added in PR #N", never "by").

**Parity with site/lib/timeline.mjs** (critique item 25). The three ports are
pinned to timeline.mjs by ``site/test/provenance-rows.test.mjs``: it runs
timeline.mjs AND this module (``python3`` with ``PYTHONPATH=tools/provenance/
src``) over every ``designs/*/PM.md`` / ``NOTES.md`` in the checkout and
asserts identical line selection. It lives in the site's suite, not in
``provenance-tests``, because timeline.mjs imports ``marked`` (through
markdown.mjs) and so needs ``site/node_modules``; the ``site-build`` job runs
``npm --prefix site test`` on EVERY PR (the site/lib/lineage.mjs ↔
tools/lineage precedent, python3 preinstalled), so a drift on either side
fails a required check. :func:`rows_json` is the entry point it calls (the
test hands it the file texts on stdin, so both stacks parse the same string).

**Placement after the join** (:func:`place`; critique item 14). The derive
order is fixed: ``extract_*`` (events placed from the raw document) →
``serving.annotate_record`` → ``serving.receipt_events`` (``job.reviewer``
events, returned UNPLACED: ``episode``/``head_sha`` ``None``) →
:func:`place` (assigns every unplaced event with :func:`assign` over
:func:`rounds_from_record`) → ``views``. Records are stored only after
:func:`place`, so every stored event has an episode.

**View episodes** (:func:`episodes_of`): one entry per distinct episode of
the given events — ``R:`` from its round (``head``, ``start``, ``end``),
``E0:``/``M:`` spanning their events' timestamps (``M:``'s ``head`` is the
merge sha when a ``pr.merged`` event is among them), ``C:`` the commit
(``start == end`` its ts), ``D:`` the day — each with its event ids in event
order; sorted by ``(start, id)`` with a ``None`` start first.

Owner: H3. Pure (git through ``protocols.GitReader``).
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from . import canonical
from .protocols import GitReader, Round

#: Byte-identical to scripts/reviewer-signoff.sh (drift-pinned).
REGEN_SUBJECT = "CI: regenerate previews and product pages"
REGEN_AUTHOR = "41898282+github-actions[bot]@users.noreply.github.com"
REGEN_TRAILER = "Preview-Diff"

#: Kinds whose ``sha`` is the sha a marker names (``stale_sha`` reads them).
MARKER_SHA_KINDS = frozenset({"review.signoff", "triage.verdict", "coach.lock"})
#: Kinds whose ``sha`` is the PR head they ran on / were posted to: placed in the round whose
#: ``heads`` hold it (module docstring), the ts rule only as the fallback.
HEAD_SHA_KINDS = frozenset({"job.reviewer", "status.reviewer_signoff"})
#: Kinds that live in the merge episode of their PR.
MERGE_KINDS = frozenset({"pr.merged", "pr.closed", "deploy.production"})
#: Committed-row kinds (day episodes) and the release (its publication day).
ROW_KINDS = frozenset({"decision.pm_log", "decision.notes_log", "field_test", "changelog"})
DAY_KINDS = ROW_KINDS | {"release"}
#: Commit kinds a sign-off's ``verifies`` edge can cover.
VERIFIABLE_COMMIT_KINDS = frozenset({"commit.design", "commit.fix", "commit.human"})
_TS_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


class BlameUnavailable(RuntimeError):
    """``GitReader.blame_lines`` does not cover a committed file that holds rows (a failed blame
    reads as ``[]``). Derive must abort — fail closed, like a failed bulk fetch — never publish a
    view with that file's rows silently missing."""


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
    inner = commit.get("commit") or {}
    message = inner.get("message") or {}
    author = inner.get("author") or {}
    return (message.get("subject_regen") is True
            and author.get("email") == REGEN_AUTHOR
            and len(commit.get("parents") or []) == 1)


def push_times(raw_pr: dict[str, Any]) -> dict[str, Optional[str]]:
    """``{pushed head sha: pushed_at}`` — the push evidence of the module docstring."""
    times: dict[str, list[str]] = {}
    for run in raw_pr.get("ci_runs") or []:
        sha, ts = run.get("head_sha"), run.get("created_at")
        if sha:
            times.setdefault(sha, [])
            if ts:
                times[sha].append(ts)
    for sha, statuses in (raw_pr.get("statuses") or {}).items():
        if not statuses:
            continue
        times.setdefault(sha, [])
        times[sha].extend(s["created_at"] for s in statuses if s.get("created_at"))
    final = ((raw_pr.get("pull") or {}).get("head") or {}).get("sha")
    if final:
        times.setdefault(final, [])
    out = {sha: (min(ts) if ts else None) for sha, ts in times.items()}
    if final and out[final] is None:
        out[final] = _final_head_fallback(raw_pr, final, out)
    return out


def _final_head_fallback(raw_pr: dict[str, Any], final: str,
                         known: dict[str, Optional[str]]) -> Optional[str]:
    """The final head's committer (else author) date when later than every other push (docstring)."""
    commit = next((c for c in raw_pr.get("commits") or [] if c.get("sha") == final), None)
    if commit is None:
        return None
    inner = commit.get("commit") or {}
    stamp = (inner.get("committer") or {}).get("date") or (inner.get("author") or {}).get("date")
    if not isinstance(stamp, str) or not _TS_RE.fullmatch(stamp):
        return None
    if any(ts is not None and ts >= stamp for sha, ts in known.items() if sha != final):
        return None
    return stamp


def pushes(raw_pr: dict[str, Any]) -> list[Push]:
    """Push groups in push order (module docstring)."""
    commits = raw_pr.get("commits") or []
    pushed = push_times(raw_pr)
    groups: list[Push] = []
    current: list[str] = []
    for commit in commits:
        current.append(commit["sha"])
        if commit["sha"] in pushed:
            groups.append(Push(commit["sha"], pushed[commit["sha"]], tuple(current),
                               is_regen_commit(commit)))
            current = []
    if current:
        last = commits[-1]
        groups.append(Push(last["sha"], None, tuple(current), is_regen_commit(last)))
    listed = {c["sha"] for c in commits}
    orphans = sorted((sha for sha in pushed if sha not in listed),
                     key=lambda sha: (pushed[sha] or "", sha))
    for sha in orphans:
        at = pushed[sha]
        index = len(groups)
        if at is not None:
            index = next((i for i, g in enumerate(groups)
                          if g.pushed_at is not None and g.pushed_at > at), len(groups))
        groups.insert(index, Push(sha, at, (), False))
    return groups


def _unique(items: list[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return tuple(seen)


def rounds(raw_pr: dict[str, Any]) -> list[Round]:
    """Rounds with regen pushes folded (module docstring)."""
    pr = raw_pr["pr"]
    pull = raw_pr.get("pull") or {}
    building: list[dict[str, Any]] = []
    for push in pushes(raw_pr):
        if push.regen and building:
            building[-1]["heads"].append(push.head)
            building[-1]["commits"].extend(push.commits)
        else:
            building.append({"head": push.head, "heads": [push.head],
                             "commits": list(push.commits), "pushed_at": push.pushed_at})
    last_end = pull.get("merged_at") or pull.get("closed_at")
    out = []
    for i, r in enumerate(building):
        end = building[i + 1]["pushed_at"] if i + 1 < len(building) else last_end
        out.append(Round(id=f"R:{pr}:{r['head'][:8]}", head=r["head"], heads=_unique(r["heads"]),
                         commits=_unique(r["commits"]), pushed_at=r["pushed_at"],
                         start=r["pushed_at"], end=end))
    return out


def _live_round(rounds_: list[Round], ts: str) -> Optional[Round]:
    """The round whose ``pushed_at`` is the latest one ``<= ts`` (ties: the later round)."""
    best: Optional[Round] = None
    for r in rounds_:
        if r.pushed_at is not None and r.pushed_at <= ts and (best is None or r.pushed_at >= best.pushed_at):
            best = r
    return best


def _group_head(r: Round, sha: str) -> str:
    """The head of the push group inside ``r`` that carried commit ``sha``."""
    position = r.commits.index(sha)
    heads = set(r.heads)
    for later in r.commits[position:]:
        if later in heads:
            return later
    return r.head


def assign(event: dict[str, Any], rounds_: list[Round], *, pr: Optional[int],
           merged_at: Optional[str]) -> Placement:
    """The episode placement of one event (module docstring)."""
    kind, ts = event["kind"], event["ts"]
    after_merge = merged_at is not None and ts > merged_at
    if kind.startswith("brief."):
        closed_by = (event.get("fields") or {}).get("closed_by_pr") if kind == "brief.closed" else None
        episode = f"M:{closed_by}" if closed_by else f"E0:brief:{event['issue']}"
        return Placement(episode, None, False, after_merge)
    if kind in DAY_KINDS:
        return Placement(f"D:{ts[:10]}", None, False, False)
    if kind.startswith("commit.") and pr is None:
        return Placement(f"C:{event['sha'][:8]}", None, False, False)
    if kind.startswith("commit."):
        holder = next((r for r in rounds_ if event.get("sha") in r.commits), None)
        if holder is not None:
            return Placement(holder.id, _group_head(holder, event["sha"]), False, after_merge)
    if kind in HEAD_SHA_KINDS and event.get("sha"):
        holder = next((r for r in rounds_ if event["sha"] in r.heads), None)
        if holder is not None:
            return Placement(holder.id, holder.head, False, after_merge)
    live = _live_round(rounds_, ts)
    if kind in MERGE_KINDS or not rounds_:
        return Placement(f"M:{pr}", live.head if live else None, False,
                         after_merge and kind not in MERGE_KINDS)
    target = live if live is not None else rounds_[0]
    sha = event.get("sha")
    stale = kind in MARKER_SHA_KINDS and sha is not None and sha not in target.heads
    return Placement(target.id, live.head if live else None, stale, after_merge)


def round_dict(r: Round) -> dict[str, Any]:
    """A :class:`protocols.Round` as the contract ``round`` object (lists, not tuples)."""
    return {"commits": list(r.commits), "end": r.end, "head": r.head, "heads": list(r.heads),
            "id": r.id, "pushed_at": r.pushed_at, "start": r.start}


def rounds_from_record(record: dict[str, Any]) -> list[Round]:
    """The record's stored ``rounds`` back as :class:`protocols.Round` objects (inverse of
    :func:`round_dict`; ``[]`` for a non-PR record)."""
    return [Round(id=d["id"], head=d["head"], heads=tuple(d["heads"]), commits=tuple(d["commits"]),
                  pushed_at=d.get("pushed_at"), start=d.get("start"), end=d.get("end"))
            for d in record.get("rounds") or []]


def apply_placement(event: dict[str, Any], placement: Placement) -> None:
    """Write a :class:`Placement` into ``event`` (in place)."""
    event["episode"] = placement.episode
    event["head_sha"] = placement.head_sha
    event["stale_sha"] = placement.stale_sha
    event["after_merge"] = placement.after_merge


def place(record: dict[str, Any]) -> dict[str, Any]:
    """A NEW record whose every event with ``episode is None`` is placed by :func:`assign` over
    :func:`rounds_from_record` (``head_sha``, ``stale_sha``, ``after_merge`` set); already-placed
    events are untouched; events re-sorted by ``canonical.event_sort_key``."""
    out = copy.deepcopy(record)
    rounds_ = rounds_from_record(out)
    for event in out.get("events") or []:
        if event.get("episode") is None:
            apply_placement(event, assign(event, rounds_, pr=out.get("pr"),
                                          merged_at=out.get("merged_at")))
    out["events"] = sorted(out.get("events") or [], key=canonical.event_sort_key)
    return out


def verifies_edges(events: list[dict[str, Any]], raw_pr: dict[str, Any]) -> dict[str, list[str]]:
    """``{event id: [verified commit shas]}`` for the record's ``review.signoff`` events."""
    order = [c["sha"] for c in raw_pr.get("commits") or []]
    index = {sha: i for i, sha in enumerate(order)}
    kinds = {e["sha"]: e["kind"] for e in events if e["kind"].startswith("commit.") and e.get("sha")}
    previous: dict[str, int] = {}
    out: dict[str, list[str]] = {}
    for event in sorted((e for e in events if e["kind"] == "review.signoff"), key=canonical.event_sort_key):
        family, sha = event["fields"]["family"], event.get("sha")
        if sha not in index:
            out[event["id"]] = []
            continue
        low, high = previous.get(family, -1), index[sha]
        out[event["id"]] = [order[i] for i in range(low + 1, high + 1)
                            if kinds.get(order[i]) in VERIFIABLE_COMMIT_KINDS]
        previous[family] = high
    return out


# ---------------------------------------------------------------------------
# Committed rows — line-for-line ports of site/lib/timeline.mjs.

#: JavaScript's WhiteSpace + LineTerminator set (what JS ``\s`` and ``trim()`` mean).
JS_WS = ("\t\n\v\f\r            "
         "      　﻿")
_S = "[" + re.escape(JS_WS) + "]"
_NS = "[^" + re.escape(JS_WS) + "]"
#: JavaScript ``.`` (no ``s`` flag): anything but a line terminator.
_DOT = "[^\n\r  ]"

_HEADING_RE = re.compile(f"(#{{1,6}}){_S}+({_DOT}*?){_S}*\\Z")
_SECTION_END_RE = re.compile(f"#{{1,2}}{_S}+")
_H3_RE = re.compile(f"###{_S}+({_DOT}*{_NS}){_S}*\\Z")
_FIELD_SEP_RE = re.compile(f"({_NS}+){_S}*(?:—|-){_S}*({_DOT}*)\\Z")
_CHANGELOG_RE = re.compile(f"({_DOT}+?){_S}+—{_S}+({_NS}+){_S}+—{_S}+({_NS}(?:{_DOT}*{_NS})?){_S}*\\Z")
_SEP_CELL_RE = re.compile(":?-+:?\\Z")
_DATE_RE = re.compile("([0-9]{4})-([0-9]{2})-([0-9]{2})\\Z")
_NOTES_BULLET_RE = re.compile("- (?:([0-9]{4}-[0-9]{2}-[0-9]{2}):|\\*\\*([0-9]{4}-[0-9]{2}-[0-9]{2})\\*\\*)")


def _js_trim(text: str) -> str:
    return text.strip(JS_WS)


def is_real_date(date: str) -> bool:
    """timeline.mjs ``isRealDate``: ``YYYY-MM-DD`` that survives a UTC round trip."""
    m = _DATE_RE.match(date)
    if m is None:
        return False
    year, month, day = (int(g) for g in m.groups())
    if not 1 <= month <= 12 or day < 1:
        return False
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]
    return day <= days


def _table_cells(row: str) -> list[str]:
    """timeline.mjs ``tableCells``: ``\\|`` is literal, outer empty cells dropped."""
    cells, cur, i = [], "", 0
    while i < len(row):
        ch = row[i]
        if ch == "\\" and i + 1 < len(row) and row[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if ch == "|":
            cells.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    cells.append(cur)
    trimmed = [_js_trim(c) for c in cells]
    if trimmed and trimmed[0] == "":
        trimmed.pop(0)
    if trimmed and trimmed[-1] == "":
        trimmed.pop()
    return trimmed


def _is_separator_row(row: str) -> bool:
    cells = _table_cells(row)
    return bool(cells) and all(_SEP_CELL_RE.match(c) for c in cells)


def _section_lines(text: str, title: str) -> Optional[list[tuple[str, int]]]:
    """timeline.mjs ``sectionLines``: ``[(line, 1-based number)]`` of the first ``## title``."""
    lines = text.split("\n")
    want = _js_trim(title).lower()
    start = -1
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        if m and len(m.group(1)) == 2 and _js_trim(m.group(2)).lower() == want:
            start = i + 1
            break
    if start == -1:
        return None
    out = []
    for i in range(start, len(lines)):
        if _SECTION_END_RE.match(lines[i]):
            break
        out.append((lines[i], i + 1))
    return out


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
    section = _section_lines(text, "Decision log")
    if section is None:
        return []
    header_at = next((i for i, (line, _) in enumerate(section)
                      if _js_trim(line) and _js_trim(line).startswith("|")), -1)
    if header_at == -1:
        return []
    header = [c.lower() for c in _table_cells(section[header_at][0])]
    if header != ["date", "decision", "reason"]:
        return []
    if header_at + 1 >= len(section):
        return []
    separator = section[header_at + 1][0]
    if not _is_separator_row(separator) or len(_table_cells(separator)) != 3:
        return []
    rows = []
    for raw, lineno in section[header_at + 2:]:
        stripped = _js_trim(raw)
        if not stripped or "|" not in stripped:
            break
        cells = _table_cells(raw)
        if len(cells) != 3:
            continue
        date, decision, reason = cells
        if not is_real_date(date) or not decision or not reason:
            continue
        rows.append(Row("decision.pm_log", "PM.md", lineno, date, raw))
    return rows


def parse_field_test_log(text: str) -> list[Row]:
    """Port of timeline.mjs ``parseFieldTestLog``."""
    section = _section_lines(text, "Field test log")
    if section is None:
        return []
    rows = []
    for raw, lineno in section:
        m = _H3_RE.match(raw)
        if not m:
            continue
        heading = _js_trim(m.group(1))
        sep = _FIELD_SEP_RE.match(heading)
        date = sep.group(1) if sep else heading
        if not is_real_date(date):
            continue
        rows.append(Row("field_test", "NOTES.md", lineno, date, raw))
    return rows


def parse_changelog(text: str) -> list[Row]:
    """Port of timeline.mjs ``parseChangelog``."""
    section = _section_lines(text, "Changelog")
    if section is None:
        return []
    rows = []
    for raw, lineno in section:
        m = _H3_RE.match(raw)
        if not m:
            continue
        parts = _CHANGELOG_RE.match(_js_trim(m.group(1)))
        if not parts or not is_real_date(parts.group(2)):
            continue
        rows.append(Row("changelog", "NOTES.md", lineno, parts.group(2), raw))
    return rows


def parse_notes_decisions(text: str) -> list[Row]:
    """NOTES.md ``## Decisions log``/``## Decision log`` dated top-level bullets."""
    rows: dict[int, Row] = {}
    for title in ("Decisions log", "Decision log"):
        for raw, lineno in _section_lines(text, title) or []:
            m = _NOTES_BULLET_RE.match(raw)
            if not m:
                continue
            date = m.group(1) or m.group(2)
            if is_real_date(date):
                rows.setdefault(lineno, Row("decision.notes_log", "NOTES.md", lineno, date, raw))
    return [rows[k] for k in sorted(rows)]


#: Which parsers run over which committed file.
ROW_FILES: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("PM.md", (parse_pm_decision_log,)),
    ("NOTES.md", (parse_field_test_log, parse_changelog, parse_notes_decisions)),
)

_SUBJECT_PR_RE = re.compile(r"\(#([0-9]{1,7})\)$|^Merge pull request #([0-9]{1,7})\b")


def subject_pr(subject: Optional[str]) -> Optional[int]:
    """The PR a main commit subject names: a squash ``(#N)`` suffix or ``Merge pull request #N``."""
    m = _SUBJECT_PR_RE.search((subject or "").strip())
    return int(m.group(1) or m.group(2)) if m else None


class _AddedIn:
    """Memoized ``sha → added_in_pr`` over one main sha (module docstring)."""

    def __init__(self, git: GitReader, main_sha: str, commit_to_pr: dict[str, int]) -> None:
        self.git, self.main_sha, self.commit_to_pr = git, main_sha, commit_to_pr
        self._first_parent: Optional[list[str]] = None
        self._on_first_parent: frozenset[str] = frozenset()
        self._merges: Optional[list[str]] = None
        self._memo: dict[str, Optional[int]] = {}

    def _main_commit(self, sha: str) -> Optional[str]:
        if self._first_parent is None:
            self._first_parent = [s for s, _ in self.git.first_parent_log(self.main_sha)]
            self._on_first_parent = frozenset(self._first_parent)
        if sha in self._on_first_parent:
            return sha
        if self._merges is None:
            self._merges = [s for s in reversed(self._first_parent) if len(self.git.parents(s)) >= 2]
        return next((m for m in self._merges if self.git.is_ancestor(sha, m)), None)

    def pr(self, sha: str) -> Optional[int]:
        if sha not in self._memo:
            main_commit = self._main_commit(sha)
            number = subject_pr(self.git.subject(main_commit)) if main_commit else None
            if number is None:
                number = self.commit_to_pr.get(sha)
            if number is None and main_commit:
                number = self.commit_to_pr.get(main_commit)
            self._memo[sha] = number
        return self._memo[sha]


def git_line_count(data: bytes) -> int:
    """The number of lines ``git blame`` reports for a blob: one per ``\\n``, plus a final line
    without one."""
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def decision_rows(git: GitReader, main_sha: str, design: str, *, owner: str, repo: str,
                  commit_to_pr: dict[str, int]) -> list[dict[str, Any]]:
    """event@1 rows for one design at ``main_sha`` (module docstring): ``GitReader.blame_lines``
    → (added_in_sha, original line) → PR; nothing of ``main_sha`` is stored in a row. Raises
    :class:`BlameUnavailable` when a file that holds rows has a blame whose length is not its line
    count (``[]`` included) — fail closed, never a row silently dropped."""
    from . import extract  # lazy: extract imports this module

    added_in = _AddedIn(git, main_sha, commit_to_pr)
    out: list[dict[str, Any]] = []
    for name, parsers in ROW_FILES:
        path = f"designs/{design}/{name}"
        data = git.show(main_sha, path)
        if data is None:
            continue
        text = data.decode("utf-8", errors="replace")
        found = sorted((row for parser in parsers for row in parser(text)), key=lambda r: r.line)
        if not found:
            continue
        blame = git.blame_lines(main_sha, path)
        lines = git_line_count(data)
        if len(blame) != lines:
            raise BlameUnavailable(f"decision rows: blame of {path} at {main_sha[:8]} has "
                                   f"{len(blame)} entries for {lines} lines ({len(found)} rows)")
        occurrences: dict[str, int] = {}
        for row in found:
            added_sha, original_line = blame[row.line - 1]
            line_sha = hashlib.sha256(row.text.encode("utf-8")).hexdigest()
            k = occurrences.get(line_sha, 0)
            occurrences[line_sha] = k + 1
            out.append({
                "after_merge": False,
                "edges": {"verifies": []},
                "episode": f"D:{row.date}",
                "fields": {"added_in_pr": added_in.pr(added_sha), "added_in_sha": added_sha,
                           "file": name, "line": original_line, "line_sha256": line_sha},
                "head_sha": None,
                "id": f"row:{design}:{name}:{line_sha[:16]}:{k}",
                "issue": None,
                "kind": row.kind,
                "pr": None,
                "runtime": extract.empty_runtime(),
                "sha": None,
                "signals": extract.empty_signals(),
                "stale_sha": False,
                "trust": "none",
                "trust_basis": "none",
                "ts": f"{row.date}T00:00:00Z",
                "ts_precision": "day",
                "tz": "UTC",
                "url": extract.build_url(owner, repo, "blob", sha=added_sha, design=design,
                                         file=name, line=original_line),
            })
    return sorted(out, key=canonical.event_sort_key)


def rows_json(texts: dict[str, str]) -> str:
    """``{path: [{kind, line, date}]}`` for ``{path: file text}`` (PM.md / NOTES.md chosen by
    basename; rows in line order) as compact JSON — the Python half of
    site/test/provenance-rows.test.mjs, which hands over the very strings it parsed itself."""
    parsers = dict(ROW_FILES)
    out = {}
    for path in sorted(texts):
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        found = [r for parser in parsers.get(name, ()) for r in parser(texts[path])]
        out[path] = [{"date": r.date, "kind": r.kind, "line": r.line}
                     for r in sorted(found, key=lambda r: r.line)]
    return json.dumps(out, sort_keys=True, separators=(",", ":"))


@dataclass
class EpisodeIndex:
    """Per-record episode list for views: ``[{id, kind, pr, issue, head, start, end, events}]``."""

    episodes: list[dict[str, Any]] = field(default_factory=list)


_EPISODE_KINDS = {"E0": "brief", "R": "round", "M": "merge", "C": "commit", "D": "day"}


def episodes_of(events: list[dict[str, Any]], rounds_: list[Round]) -> list[dict[str, Any]]:
    """The view@1 ``episodes`` list for a set of placed events (sorted by start, then id)."""
    by_round = {r.id: r for r in rounds_}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in sorted(events, key=canonical.event_sort_key):
        grouped.setdefault(event["episode"], []).append(event)
    out = []
    for episode, members in grouped.items():
        prefix, _, rest = episode.partition(":")
        entry: dict[str, Any] = {"end": None, "events": list(_unique([e["id"] for e in members])),
                                 "head": None, "id": episode, "issue": None,
                                 "kind": _EPISODE_KINDS[prefix], "pr": None, "start": None}
        stamps = [e["ts"] for e in members]
        if prefix == "R":
            entry["pr"] = int(rest.split(":", 1)[0])
            r = by_round.get(episode)
            if r is not None:
                entry.update(head=r.head, start=r.start, end=r.end)
            else:
                entry.update(start=min(stamps), end=max(stamps))
        elif prefix == "E0":
            entry.update(issue=int(rest.rsplit(":", 1)[1]), start=min(stamps), end=max(stamps))
        elif prefix == "M":
            merged = next((e["sha"] for e in members if e["kind"] == "pr.merged"), None)
            entry.update(pr=int(rest), head=merged, start=min(stamps), end=max(stamps))
        elif prefix == "C":
            entry.update(head=next((e["sha"] for e in members if e.get("sha")), None),
                         start=min(stamps), end=max(stamps))
        else:
            day = f"{rest}T00:00:00Z"
            entry.update(start=day, end=day)
        out.append(entry)
    return sorted(out, key=lambda e: (e["start"] or "", e["id"]))
