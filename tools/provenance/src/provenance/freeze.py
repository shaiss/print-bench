"""Freeze — the settle/defer policy and the GET sequences that capture one PR, brief or release.

Late ACTIVITY never mutates a frozen unit (docs/provenance.md §Freeze
units). A unit is captured ONCE, after it has settled, into
``raw/<kind>/<key>.json.gz`` (revision 1); a later revision
``raw/<kind>/<key>.r<K>.json.gz`` (K ≥ 2) is added only by ``refreeze`` or
when the unit's TERMINAL STATE changes; the extractor folds the highest K.
Which units are frozen, at which revision, is read from the evidence tree's
paths (``state.frozen_from_paths``), never from state.json.

**Settle** (:func:`settle_pr`, pure, ``now`` injected). A closed PR (merged
or closed unmerged) is due at ``closed_at + settle_hours``. At or after
due, it FREEZES when no watched run on its head branch is queued or in
progress and, if merged, the merge sha's Production deployment is terminal
or ``merged_at + deploy_wait_hours`` has passed; otherwise it is DEFERRED
(``pending`` with reasons) — until ``closed_at + max_defer_hours``, when it
freezes anyway with ``incomplete`` naming why (``settle-deferred``,
``deployment-not-terminal``). Before due it is PENDING. A PR whose files
touch no ``designs/`` path is recorded in ``state.skipped.pr[n] =
{closed_at}`` (never captured).

**Changed terminal state** (critique item 11). For every PR in the closed
listing that is already frozen, the highest revision's stored
``pull.closed_at`` / ``pull.merged_at`` are compared with the listing's; a
difference (closed-unmerged, reopened, then merged; or closed again) puts the
PR back through the settle rule and freezes the NEXT revision. A skipped PR
whose ``closed_at`` differs is re-evaluated (its files may now touch
``designs/``). Briefs likewise compare the stored ``issue.state`` /
``issue.closed_at`` with the listing's (a reopened brief that is re-shipped
gets its next revision once it closes and settles). Comment-only activity
after the freeze changes ``updated_at`` but neither field, so it never
re-captures.

**Briefs** (issues carrying, or having carried, ``design-brief``; critique
item 24): due at ``closed_at + settle_hours``. A frozen PR's linked issue
(``raw-pr.linked_issues``) is captured as a brief ONLY when its labels or its
timeline (``labeled`` ``design-brief``) show the label — a backlog-burn PR
closing an ``autonomy-ok`` issue links it but never makes a brief of it. An
OPEN brief that a frozen PR links is captured as revision 1 with
``incomplete: brief-open`` (and re-captured, by the changed-terminal-state
rule, once it closes and settles). Releases freeze on publish (non-draft).

**Refreeze** (:func:`refreeze`; critique item 10). Revision K+1 re-reads
everything live, then UNIONS the retention-bound sections — ``ci_runs``,
``statuses`` (per sha) and ``deployments`` — from revision K by id, live
winning on a collision, so a refreeze more than 90 days after close (when
GitHub has deleted the runs and statuses) keeps the pushed heads and
per-round statuses revision K froze. The same union applies to the
changed-terminal-state revision. Non-retention sections (comments, reviews,
timeline, commits, files) are taken live — a comment deleted since revision
K is absent from K+1 while K keeps it (add-only).

**PR capture** (:func:`capture_pr`, ~17–25 GETs; every body digested at
capture through ``rawdoc``):

1. ``/pulls/{n}``; 2. ``/pulls/{n}/files`` (all pages; > 3000 files →
``files-truncated``); 3. ``/pulls/{n}/commits`` (> 250 → ``commits-truncated``);
4. ``/issues/{n}/comments``; 5. ``/pulls/{n}/reviews``; 6. ``/pulls/{n}/comments``;
7. ``/issues/{n}/timeline``; 8. GraphQL threads (``GraphQLUnavailable`` →
``graphql-unavailable``, ``threads.total`` 0, source ``graphql``);
9. ``/actions/workflows/ci.yml/runs?branch=<head_ref>`` — rows kept when
``pull_requests`` holds ``n`` or ``head_sha`` is a PR commit — UNIONED with
the ingested snapshot listing (``raw/snapshot/<id>/runs/ci.yml.json.gz``,
same filter) by run id, live winning; 10. ``/commits/{sha}/statuses`` for
EVERY PR commit sha and every ci_runs head (a commit with any status is a
pushed head — episodes.py), each unioned with
``raw/snapshot/<id>/statuses/<sha>.json.gz`` by status id;
11. merged only: ``/deployments?sha=<merge>&environment=Production`` and
each deployment's ``/statuses``; 12. ``linked_issues`` = ``body.refs_closes``
∪ the ``claude/issue-<N>-*`` head-ref number (each checked for the brief label
as above: ``/issues/{N}`` + its timeline, then captured or left a number).

Per-SHA check runs are NOT read (54% of the audit's full profile, never
rendered). Statuses use the list endpoint (``/statuses``, every status with
its ``creator``) rather than the combined ``/status`` the plan first named:
the creator is what the ``reviewer-signoff`` trust rule needs, and the list
includes the superseded per-round statuses.

**Brief capture** (:func:`capture_brief`): ``/issues/{b}``, comments,
timeline, GraphQL ``lastEditedAt``. **Release capture**: the ``/releases``
list row itself (no extra GET).

**Selection** (:func:`plan_freezes`): ``/pulls?state=closed&sort=updated&
direction=desc`` paged until ``updated_at`` < the PR cursor minus the settle
window (a fresh cursor: ``backfill_since``), and ``/issues?labels=design-brief&
state=all&sort=updated&since=<cursor>``; with ``--pr`` only those PRs (settle
still applies unless ``refreeze``). Paths are built here over
``protocols.GitHubAPI`` (``get`` / ``get_paged``), so ``FakeGitHub`` serves
every capture test.

**What a pass decides, unit by unit.** A listed PR is, in this order: frozen
(compare the stored terminal state — unchanged → nothing, not one GET),
pending (re-evaluate), skipped (unchanged ``closed_at`` → nothing), or new
(``/pulls/{n}/files`` once: no ``designs/`` path → skipped). Every unit in
``state.pending`` that the listing did not reach is re-read by number
(``/pulls/{n}``, ``/issues/{n}``), so a cursor that moved past a long-deferred
unit never strands it; a pending PR found open again (reopened) leaves
``pending`` (``FreezePlan.cleared``). Due units need one ``/actions/runs?
branch=<head_ref>`` page (watched runs whose status is queued / in progress /
pending / waiting / requested) and, when merged, the merge sha's Production
deployment and its statuses (the newest deployment's newest status is one
of success / failure / error / inactive → terminal; a lookup GitHub refuses
counts as not terminal). A unit whose capture fails is ISOLATED: an API refusal
anywhere in it — the ``designs/`` files check, the capture itself (``CaptureError``:
its ``/pulls/{n}`` answered nothing), a linked brief's reads — or in the
re-read of a pending unit the listing did not reach leaves THAT unit pending
with the reason ``capture-failed`` and the pass goes on to the next one, so
one PR GitHub keeps refusing never blocks the PRs, briefs and releases after
it (a pending PR carrying ``capture-failed`` re-runs the ``designs/`` check,
since a failed one decided nothing). Every closed PR the pass has seen ends in
exactly one of frozen, pending or skipped (Reeve's ``provenance-lag`` stall
check counts on it); a unit that keeps failing is Reeve's ``overdue`` finding.
A failure of a LISTING itself (``/pulls``, ``/issues``, ``/releases``) still
ends the pass: nothing below it is knowable.

**Gone vs transient.** Only a 404 / 410 / 422 on a per-object listing
(``/commits/{sha}/statuses`` of a sha GitHub no longer knows, the statuses of a
deleted deployment) reads as "gone" — recorded as
``statuses-unavailable:<sha8>`` or an empty list. Any other refusal (a 5xx
after retries, a transport failure) fails the unit's capture, so it stays
pending and is retried next run instead of freezing a transient gap into
revision 1.

**Admission.** Every document is validated against the closed contract
(``contract.validate``: ``raw-pr@1`` / ``raw-brief@1`` / ``raw-release@1``)
BEFORE it is planned: the evidence ref is add-only, so a document that breaks
the contract could never be removed and every later ``check`` of the tree
would fail on it. A failing PR or brief stays pending with the reason
``contract-invalid`` (a PR's linked briefs with it — the unit is whole); a
failing release is not planned and the next full ``/releases`` listing retries
it; ``refreeze`` raises :class:`ContractInvalid`. ``linked_issues`` keeps only
issue numbers ≥ 1 whatever the body digest says (an untrusted body reading
"Closes #0" links nothing).

A PR and the briefs it links freeze as ONE unit: the PR's file is planned only
after its linked issues were each captured, left a number, or recorded
pending — so a budget stop between them cannot leave a frozen PR whose open
brief is never captured as ``brief-open``.

**The plan** (:class:`FreezePlan`) carries state UPDATES that ``cli`` applies
with ``state.py`` (this module never calls it): ``pending`` is the COMPLETE
new ``state.pending`` map (``{"pr": {...}, "brief": {...}}``, carried-over
entries included — so applying it is a replacement, and a budget-stopped pass
still loses nothing); ``frozen`` the ``(kind, key, revision)`` added this pass
(``state.clear_pending`` each — already absent from ``pending``);
``recaptured`` the subset that is a changed-terminal-state revision;
``cleared`` the ``(kind, key)`` that left ``pending`` without freezing;
``skipped_prs`` ``{pr: closed_at}`` to record; ``cursors`` the new
``state.cursors`` values (``prs_updated``, ``briefs_updated``,
``releases_published``) of each listing that COMPLETED — a budget stop leaves
the cursor of the interrupted listing (and the ones after it) out, so the
next run re-lists the same window; ``budget_stopped`` the clean stop. A pass
with nothing new plans no file and returns ``pending`` equal to the input
state's and ``cursors`` equal to its cursors (state.json byte-identical).

``plan_freezes`` and ``refreeze`` take two keyword arguments the cli supplies:
``run_id`` (``captured.run_id``; ``--run-id``) and, for ``plan_freezes``,
``since`` (a dispatch's ``since`` input: lowers both listing cursors for this
pass, never below ``backfill_since``).

``refreeze`` applies only to a PR that is already frozen (revision ≥ 1): it is
the operator's "capture this settled unit again", never a way around the
settle rule or the ``designs/`` filter — an unfrozen PR raises
:class:`RefreezeRefused` (a ``CaptureError``, so the cli exits 1) before any
request; ``harvest --pr N`` is the path for a PR that was never frozen.

Owner: H6.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Optional

from . import HARVESTER, canonical, contract, rawdoc
from .digest import DIGEST_VERSION
from .github import APIError, BudgetExhausted, GraphQLUnavailable, Truncated
from .protocols import GitHubAPI


@dataclass(frozen=True)
class Settle:
    """A settle decision: ``action`` ``freeze`` | ``pending`` | ``defer`` (pending past due);
    ``due_at``/``defer_until`` derived from close; ``incomplete`` reasons when forced."""

    action: str
    due_at: str
    defer_until: str
    reasons: tuple[str, ...] = ()
    incomplete: tuple[str, ...] = ()


#: raw-pr@1 sections a later revision carries from the previous one (retention-bound).
RETENTION_BOUND = ("ci_runs", "statuses", "deployments")


@dataclass
class FreezePlan:
    """Files to add (``{path: bytes}``) plus state updates and counts for the summary.

    ``frozen`` lists ``(kind, key, revision)`` added this pass (the tree is the
    record; this is for the summary and ``state.clear_pending``);
    ``skipped_prs`` maps PR → ``closed_at``. ``pending`` is the complete new
    ``state.pending`` map and ``cleared`` the units that left it without
    freezing (module docstring, "The plan").
    """

    files: dict[str, bytes] = field(default_factory=dict)
    frozen: list[tuple[str, str, int]] = field(default_factory=list)
    pending: dict[str, dict[str, Any]] = field(default_factory=dict)
    skipped_prs: dict[int, str] = field(default_factory=dict)
    recaptured: list[tuple[str, str, int]] = field(default_factory=list)
    cursors: dict[str, Optional[str]] = field(default_factory=dict)
    budget_stopped: bool = False
    cleared: list[tuple[str, str]] = field(default_factory=list)


class CaptureError(Exception):
    """A unit's primary object (``/pulls/{n}``) answered nothing usable; the unit stays pending."""


class ContractInvalid(CaptureError):
    """A captured document failed the closed contract; it is never planned (module docstring,
    "Admission"). The message names the shape, the error count and the first error's JSON path
    only — never a value, which may be untrusted text."""


class RefreezeRefused(CaptureError):
    """``refreeze`` of a PR with no frozen revision (``harvest --pr N`` is that path)."""


KINDS = ("pr", "brief", "release")
BRIEF_LABEL = "design-brief"
DESIGNS_PREFIX = "designs/"
#: Run statuses that mean "still in flight" (cli.WAITING_STATUSES' set; a run blocked on a
#: concurrency group reports pending/waiting, not queued).
IN_FLIGHT_STATUSES = frozenset({"queued", "in_progress", "pending", "waiting", "requested"})
#: Deployment status states after which a Production deployment is over.
TERMINAL_DEPLOY_STATES = frozenset({"success", "failure", "error", "inactive"})
#: GitHub's own caps on the two PR listings (docs/provenance.md §raw@1 payloads).
MAX_PR_COMMITS = 250
MAX_PR_FILES = 3000
#: The reason a pending unit carries while its capture keeps failing.
CAPTURE_FAILED = "capture-failed"
#: The reason a pending unit carries while its captured document fails the contract.
CONTRACT_INVALID = "contract-invalid"
#: The contract shape each kind's document must satisfy before it is planned.
SHAPES = {"pr": "raw-pr@1", "brief": "raw-brief@1", "release": "raw-release@1"}
#: HTTP statuses a per-object listing answers for an object GitHub no longer has.
GONE_STATUSES = frozenset({404, 410, 422})
#: The failures that leave ONE unit pending instead of ending the pass.
UNIT_ERRORS = (CaptureError, APIError, Truncated)
#: Pending reasons of a deferred PR (state@1 ``pending.*.reasons``).
REASON_IN_FLIGHT = "in-flight-run"
REASON_DEPLOYMENT = "deployment-pending"

_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
_NUMBER_RE = re.compile(r"[1-9][0-9]{0,6}")
_TAG_RE = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]{0,99}")
_SHA40_RE = re.compile(r"[0-9a-f]{40}")
_HEAD_ISSUE_RE = re.compile(r"claude/issue-([0-9]{1,7})-")
_ERROR_PATH_RE = re.compile(r"[^A-Za-z0-9_.$\[\]@-]")


# --- small pure helpers ------------------------------------------------------

def _ts(value: str) -> datetime:
    """An RFC3339 UTC timestamp (``…Z`` or ``…+00:00``; a bare date is its midnight)."""
    text = value if "T" in value else value + "T00:00:00Z"
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fmt(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime(_TS_FMT)


def _plus_hours(ts: str, hours: int) -> str:
    return _fmt(_ts(ts) + timedelta(hours=hours))


def _key(kind: str, key: Any) -> str:
    text = str(key)
    if kind in ("pr", "brief"):
        if not _NUMBER_RE.fullmatch(text):
            raise ValueError(f"bad {kind} number {key!r}")
    elif kind == "release":
        if not _TAG_RE.fullmatch(text) or ".." in text:
            raise ValueError(f"bad release tag {key!r}")
    else:
        raise ValueError(f"unknown unit kind {kind!r}")
    return text


def raw_path(kind: str, key: str, revision: int) -> str:
    """``raw/<kind>/<key>.json.gz`` (revision 1) or ``raw/<kind>/<key>.r<K>.json.gz``."""
    text = _key(kind, key)
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ValueError(f"bad revision {revision!r}")
    suffix = "" if revision == 1 else f".r{revision}"
    return f"raw/{kind}/{text}{suffix}.json.gz"


def _captured(run_id: int) -> dict[str, Any]:
    return {"digest": DIGEST_VERSION, "harvester": HARVESTER, "run_id": int(run_id)}


def _items(value: Any, key: Optional[str] = None) -> Optional[list[Any]]:
    """A list response (``key`` unwraps ``{key: [...]}``), or ``None`` when the API gave none."""
    if key and isinstance(value, dict):
        value = value.get(key)
    return value if isinstance(value, list) else None


def _optional_list(gh: GitHubAPI, path: str, params: Optional[dict[str, str]] = None) -> Optional[list[Any]]:
    """A per-object listing whose object may be gone (a sha GitHub no longer knows, a deleted
    deployment): ``None`` on a :data:`GONE_STATUSES` refusal only. Any other ``APIError`` (a 5xx
    after retries; a transport failure, ``status`` None) propagates and fails the unit's capture,
    so it is retried next run rather than frozen with a transient gap. Budget stops propagate."""
    try:
        return _items(gh.get_paged(path, params))
    except APIError as exc:
        if getattr(exc, "status", None) in GONE_STATUSES:
            return None
        raise


def _admit(kind: str, doc: dict[str, Any]) -> bytes:
    """The document's ``*.json.gz`` bytes — only when it satisfies ``SHAPES[kind]``."""
    errors = contract.validate(SHAPES[kind], doc)
    if errors:
        where = _ERROR_PATH_RE.sub("?", str(errors[0]).split(": ", 1)[0])[:120]
        raise ContractInvalid(f"{SHAPES[kind]}: {len(errors)} contract error(s), first at {where}")
    return canonical.dumps_gz(doc)


def _union(live: Iterable[dict[str, Any]], *older: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """``live`` plus every older row whose ``id`` live lacks (live wins on a collision)."""
    out = list(live)
    seen = {row.get("id") for row in out}
    for rows in older:
        for row in rows or ():
            if row.get("id") not in seen:
                seen.add(row.get("id"))
                out.append(row)
    return out


def _by_time(rows: list[dict[str, Any]], ts: str) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (r.get(ts) or "", r.get("id") or 0))


def _touches_designs(files: Iterable[dict[str, Any]]) -> bool:
    return any(str(f.get(k) or "").startswith(DESIGNS_PREFIX)
               for f in files for k in ("filename", "previous_filename"))


def _label_names(labels: Any) -> list[str]:
    out = []
    for lbl in labels or ():
        name = lbl.get("name") if isinstance(lbl, dict) else lbl
        if isinstance(name, str):
            out.append(name)
    return out


def _pr_numbers(prs: Any) -> set[int]:
    out = set()
    for p in prs or ():
        n = p if isinstance(p, int) else (p.get("number") if isinstance(p, dict) else None)
        if isinstance(n, int):
            out.add(n)
    return out


def _issue_number(n: Any) -> bool:
    return isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= 9_999_999


def _linked_issues(body_digest: dict[str, Any], head_ref: Optional[str]) -> list[int]:
    """``body.refs_closes`` ∪ the ``claude/issue-<N>-`` head-ref number, issue numbers ≥ 1 only:
    an untrusted body reading "Closes #0" must never put a 0 into ``linked_issues``."""
    linked = {n for n in body_digest.get("refs_closes") or () if _issue_number(n)}
    m = _HEAD_ISSUE_RE.match(head_ref or "")
    if m and _issue_number(int(m.group(1))):
        linked.add(int(m.group(1)))
    return sorted(linked)


def _read_doc(read: Callable[[str], Optional[bytes]], path: str) -> Optional[dict[str, Any]]:
    data = read(path)
    if data is None:
        return None
    doc = canonical.loads_gz(data)
    return doc if isinstance(doc, dict) else None


class _Snapshot:
    """The ingested snapshot's two consumable listings, read from the evidence tree once."""

    def __init__(self, read: Callable[[str], Optional[bytes]], snapshot_id: str) -> None:
        self.read = read
        self.sid = snapshot_id
        self._runs: Optional[list[dict[str, Any]]] = None

    def runs(self) -> list[dict[str, Any]]:
        if self._runs is None:
            doc = _read_doc(self.read, f"raw/snapshot/{self.sid}/runs/ci.yml.json.gz")
            self._runs = list((doc or {}).get("runs") or [])
        return self._runs

    def statuses(self, sha: str) -> Optional[list[dict[str, Any]]]:
        if not _SHA40_RE.fullmatch(sha or ""):
            return None
        doc = _read_doc(self.read, f"raw/snapshot/{self.sid}/statuses/{sha}.json.gz")
        return None if doc is None else list(doc.get("statuses") or [])


# --- settle ------------------------------------------------------------------

def settle_pr(*, closed_at: str, merged_at: Optional[str], in_flight_runs: int,
              deployment_terminal: Optional[bool], now: str, settle_hours: int,
              max_defer_hours: int, deploy_wait_hours: int) -> Settle:
    """The settle decision for one closed PR (module docstring)."""
    due_at = _plus_hours(closed_at, settle_hours)
    defer_until = _plus_hours(closed_at, max_defer_hours)
    t = _ts(now)
    if t < _ts(due_at):
        return Settle("pending", due_at, defer_until)
    blockers: set[str] = set()
    forced: set[str] = set()
    if in_flight_runs > 0:
        blockers.add(REASON_IN_FLIGHT)
        forced.add("settle-deferred")
    if merged_at is not None and deployment_terminal is not True:
        if t < _ts(merged_at) + timedelta(hours=deploy_wait_hours):
            blockers.add(REASON_DEPLOYMENT)
        forced.add("deployment-not-terminal")  # waited out (or forced): it never went terminal
    if not blockers:
        return Settle("freeze", due_at, defer_until, (), tuple(sorted(forced)))
    if t < _ts(defer_until):
        return Settle("defer", due_at, defer_until, tuple(sorted(blockers)))
    return Settle("freeze", due_at, defer_until, tuple(sorted(blockers)), tuple(sorted(forced)))


def settle_brief(*, state: str, closed_at: Optional[str], linked_by_frozen_pr: bool, now: str,
                 settle_hours: int, max_defer_hours: int) -> Settle:
    """The settle decision for one design-brief issue.

    Closed: pending until ``closed_at + settle_hours``, then freeze. Open and linked by a
    frozen PR: freeze now with ``incomplete: brief-open`` (``due_at`` = ``defer_until`` =
    ``now``). Open and not linked: ``pending`` with empty times and the reason ``brief-open``
    — the caller does NOT record it (it has no due time until it closes)."""
    if state == "closed" and closed_at:
        due_at = _plus_hours(closed_at, settle_hours)
        defer_until = _plus_hours(closed_at, max_defer_hours)
        if _ts(now) < _ts(due_at):
            return Settle("pending", due_at, defer_until)
        return Settle("freeze", due_at, defer_until)
    if linked_by_frozen_pr:
        return Settle("freeze", now, now, (), ("brief-open",))
    return Settle("pending", "", "", ("brief-open",))


# --- capture -----------------------------------------------------------------

def _capture_pr(gh: GitHubAPI, number: int, *, revision: int, captured: dict[str, Any],
                snapshot_runs: Callable[[], list[dict[str, Any]]],
                snapshot_statuses: Callable[[str], Optional[list[dict[str, Any]]]],
                previous: Optional[dict[str, Any]] = None,
                files_raw: Optional[list[Any]] = None) -> dict[str, Any]:
    # ``files_raw``: the /files listing when the pass already read it for the designs/ check
    # (one GET saved); the /pulls/{n} object itself is always re-read — the closed LISTING's
    # rows lack merged / commits / changed_files / merged_by.
    incomplete: set[str] = set()
    pull_raw = gh.get(f"/pulls/{number}")
    if not isinstance(pull_raw, dict):
        raise CaptureError(f"PR #{number}: /pulls/{number} answered nothing")
    pull = rawdoc.project_pull(pull_raw)
    head_ref = pull["head"]["ref"]

    if files_raw is None:
        files_raw = _items(gh.get_paged(f"/pulls/{number}/files")) or []
    files = rawdoc.project_files(files_raw)
    if len(files) >= MAX_PR_FILES or (pull["changed_files"] or 0) > len(files):
        incomplete.add("files-truncated")

    commits = rawdoc.project_commits(_items(gh.get_paged(f"/pulls/{number}/commits")) or [])
    if len(commits) >= MAX_PR_COMMITS or (pull["commits"] or 0) > len(commits):
        incomplete.add("commits-truncated")
    commit_shas = {c["sha"] for c in commits if c.get("sha")}

    issue_comments = rawdoc.project_issue_comments(
        _items(gh.get_paged(f"/issues/{number}/comments")) or [])
    reviews = rawdoc.project_reviews(_items(gh.get_paged(f"/pulls/{number}/reviews")) or [])
    review_comments = rawdoc.project_review_comments(
        _items(gh.get_paged(f"/pulls/{number}/comments")) or [])
    timeline = rawdoc.project_timeline(_items(gh.get_paged(f"/issues/{number}/timeline")) or [])

    try:
        gql = gh.graphql_pr_threads(number)
        threads = rawdoc.project_threads((gql or {}).get("nodes") or [], "graphql",
                                         (gql or {}).get("last_edited_at"))
    except GraphQLUnavailable:
        incomplete.add("graphql-unavailable")
        threads = rawdoc.project_threads([], "graphql", None)

    def _ours(row: dict[str, Any]) -> bool:
        return number in _pr_numbers(row.get("pull_requests")) or row.get("head_sha") in commit_shas

    live_runs: list[dict[str, Any]] = []
    if head_ref:
        listed = _items(gh.get_paged("/actions/workflows/ci.yml/runs", {"branch": head_ref},
                                     key="workflow_runs"), "workflow_runs") or []
        live_runs = rawdoc.project_runs(r for r in listed if isinstance(r, dict) and _ours(r))
    snap_runs = [r for r in snapshot_runs() or ()
                 if r.get("head_branch") == head_ref and _ours(r)]
    prev_runs = (previous or {}).get("ci_runs") or []
    ci_runs = _by_time(_union(live_runs, prev_runs, snap_runs), "created_at")

    prev_statuses: dict[str, list[dict[str, Any]]] = (previous or {}).get("statuses") or {}
    heads = {r.get("head_sha") for r in ci_runs} | commit_shas | {pull["head"]["sha"]}
    shas = sorted(s for s in heads if isinstance(s, str) and _SHA40_RE.fullmatch(s))
    statuses: dict[str, list[dict[str, Any]]] = {}
    for sha in sorted(set(shas) | set(prev_statuses)):
        live = None
        if sha in shas:
            live = _optional_list(gh, f"/commits/{sha}/statuses")
        snap = snapshot_statuses(sha) if sha in shas else None
        prev = prev_statuses.get(sha)
        if live is None and snap is None and prev is None:
            incomplete.add(f"statuses-unavailable:{sha[:8]}")
            continue
        rows = _union(rawdoc.project_statuses(live or []), prev or [],
                      rawdoc.project_statuses(snap or []))
        if rows:
            statuses[sha] = _by_time(rows, "created_at")

    live_deps: list[dict[str, Any]] = []
    merge = pull["merge_commit_sha"]
    if pull["merged_at"] and merge:
        for d in _items(gh.get_paged("/deployments", {"sha": merge, "environment": "Production"})) or []:
            if not isinstance(d, dict) or d.get("id") is None:
                continue
            st = _optional_list(gh, f"/deployments/{d['id']}/statuses") or []
            live_deps.append(rawdoc.project_deployment(d, st))
    deployments = sorted(_union(live_deps, (previous or {}).get("deployments") or []),
                         key=lambda d: d.get("id") or 0)

    return rawdoc.raw_pr_doc(
        number=number, revision=revision, captured=captured, incomplete=sorted(incomplete),
        pull=pull, files=files, commits=commits, reviews=reviews,
        review_comments=review_comments, issue_comments=issue_comments, timeline=timeline,
        threads=threads, ci_runs=ci_runs, statuses=statuses, deployments=deployments,
        linked_issues=_linked_issues(pull["body"], head_ref),
    )


def capture_pr(gh: GitHubAPI, number: int, *, revision: int, captured: dict[str, Any],
               snapshot_runs: Callable[[], list[dict[str, Any]]],
               snapshot_statuses: Callable[[str], Optional[list[dict[str, Any]]]],
               previous: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """raw-pr@1 for one PR (module docstring steps 1–12). ``previous`` = revision K's document
    (revision ≥ 2): its :data:`RETENTION_BOUND` sections are unioned in by id, live winning."""
    return _capture_pr(gh, number, revision=revision, captured=captured,
                       snapshot_runs=snapshot_runs, snapshot_statuses=snapshot_statuses,
                       previous=previous)


def is_design_brief(issue: dict[str, Any], timeline: list[dict[str, Any]]) -> bool:
    """The issue carries ``design-brief`` now, or its timeline shows it ``labeled`` so (projected
    shapes: ``rawdoc.project_issue`` / ``project_timeline``)."""
    if BRIEF_LABEL in _label_names((issue or {}).get("labels")):
        return True
    for event in timeline or ():
        label = event.get("label")
        if isinstance(label, dict):
            label = label.get("name")
        if event.get("event") == "labeled" and label == BRIEF_LABEL:
            return True
    return False


def _capture_brief_from(gh: GitHubAPI, number: int, issue_raw: dict[str, Any],
                        timeline_raw: list[Any], *, revision: int, captured: dict[str, Any],
                        incomplete: tuple[str, ...] = ()) -> Optional[dict[str, Any]]:
    timeline = rawdoc.project_timeline(timeline_raw)
    if not is_design_brief(rawdoc.project_issue(issue_raw, None), timeline):
        return None
    reasons = set(incomplete)
    try:
        edited = gh.graphql_issue_edited(number)
    except GraphQLUnavailable:
        edited = None
        reasons.add("graphql-unavailable")
    issue = rawdoc.project_issue(issue_raw, edited)
    if issue["state"] != "closed":
        reasons.add("brief-open")
    comments = rawdoc.project_issue_comments(_items(gh.get_paged(f"/issues/{number}/comments")) or [])
    return rawdoc.raw_brief_doc(number=number, revision=revision, captured=captured,
                                incomplete=sorted(reasons), issue=issue, comments=comments,
                                timeline=timeline)


def _issue(gh: GitHubAPI, number: int) -> Optional[dict[str, Any]]:
    """``/issues/{n}`` when it is an issue (not a PR), else ``None``."""
    raw = gh.get(f"/issues/{number}")
    if not isinstance(raw, dict) or raw.get("pull_request"):
        return None
    return raw


def capture_brief(gh: GitHubAPI, number: int, *, revision: int, captured: dict[str, Any],
                  incomplete: tuple[str, ...] = ()) -> Optional[dict[str, Any]]:
    """raw-brief@1 for one issue, or ``None`` when :func:`is_design_brief` is false."""
    issue_raw = _issue(gh, number)
    if issue_raw is None:
        return None
    timeline_raw = _items(gh.get_paged(f"/issues/{number}/timeline")) or []
    return _capture_brief_from(gh, number, issue_raw, timeline_raw, revision=revision,
                               captured=captured, incomplete=incomplete)


def capture_release(release: dict[str, Any], *, revision: int, captured: dict[str, Any]) -> dict[str, Any]:
    """raw-release@1 from a ``/releases`` row."""
    tag = _key("release", release.get("tag_name"))
    return rawdoc.raw_release_doc(tag=tag, revision=revision, captured=captured,
                                  release=rawdoc.project_release(release))


# --- the pass ----------------------------------------------------------------

def _copy_pending(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    pending = (state or {}).get("pending") or {}
    return {kind: {str(k): dict(v) for k, v in (pending.get(kind) or {}).items()}
            for kind in ("pr", "brief")}


def _entry(closed_at: Optional[str], s: Settle) -> dict[str, Any]:
    return {"closed_at": closed_at, "due_at": s.due_at, "defer_until": s.defer_until,
            "reasons": sorted(set(s.reasons))}


class _Pass:
    """One freeze pass: the shared inputs and the plan being built."""

    def __init__(self, gh: GitHubAPI, *, state: dict[str, Any], frozen: dict[str, dict[str, int]],
                 conf: Any, now: str, read: Callable[[str], Optional[bytes]], run_id: int) -> None:
        self.gh = gh
        self.state = state or {}
        self.frozen = {k: dict(v) for k, v in (frozen or {}).items()}
        self.conf = conf
        self.now = now
        self.read = read
        self.captured = _captured(run_id)
        self.snap = _Snapshot(read, conf.snapshot_id)
        self.skipped = {str(k): v for k, v in
                        (((self.state.get("skipped") or {}).get("pr")) or {}).items()}
        self.plan = FreezePlan(pending=_copy_pending(self.state))

    # -- helpers --
    def revision_of(self, kind: str, key: str) -> int:
        return int(self.frozen.get(kind, {}).get(key, 0))

    def pending(self, kind: str) -> dict[str, Any]:
        return self.plan.pending[kind]

    def hold(self, kind: str, key: str, closed_at: Optional[str], s: Settle, reason: str) -> None:
        """Keep ONE unit pending with ``reason`` added (its capture failed); the pass goes on."""
        self.pending(kind)[key] = _entry(closed_at, Settle(
            "defer", s.due_at, s.defer_until, tuple(sorted(set(s.reasons) | {reason}))))

    def hold_existing(self, kind: str, key: str) -> None:
        """A pending unit whose re-read GitHub refused: its entry stays, marked ``capture-failed``."""
        entry = dict(self.pending(kind).get(key) or {})
        if entry:
            entry["reasons"] = sorted(set(entry.get("reasons") or ()) | {CAPTURE_FAILED})
            self.pending(kind)[key] = entry

    def commit_unit(self, files: dict[str, bytes], units: list[tuple[str, str, int, bool]]) -> None:
        self.plan.files.update(files)
        for kind, key, revision, recapture in units:
            self.plan.frozen.append((kind, key, revision))
            if recapture:
                self.plan.recaptured.append((kind, key, revision))
            self.frozen.setdefault(kind, {})[key] = revision
            self.plan.pending.get(kind, {}).pop(key, None)

    # -- PRs --
    def in_flight(self, head_ref: Optional[str]) -> int:
        if not head_ref:
            return 0
        try:
            page = self.gh.get("/actions/runs", {"branch": head_ref, "per_page": "100"})
        except APIError:
            return 1  # unknown counts as in flight: defer, and force-freeze at max_defer_hours
        watched = set(self.conf.watched_workflows)
        return sum(1 for r in _items(page, "workflow_runs") or []
                   if isinstance(r, dict) and r.get("status") in IN_FLIGHT_STATUSES
                   and str(r.get("path") or "").rsplit("/", 1)[-1] in watched)

    def deployment_terminal(self, merge_sha: Optional[str]) -> bool:
        """Is the merge sha's newest Production deployment over? Unknown (no deployment, or a
        lookup GitHub refuses) is ``False``: wait, and freeze with ``deployment-not-terminal``
        once ``deploy_wait_hours`` has passed — never read a refusal as terminal."""
        if not merge_sha:
            return False
        try:
            deps = [d for d in _optional_list(
                self.gh, "/deployments", {"sha": merge_sha, "environment": "Production"}) or []
                if isinstance(d, dict) and d.get("id") is not None]
            if not deps:
                return False
            newest = max(deps, key=lambda d: d["id"])
            statuses = [s for s in _optional_list(self.gh, f"/deployments/{newest['id']}/statuses")
                        or [] if isinstance(s, dict)]
        except (APIError, Truncated):
            return False
        if not statuses:
            return False
        latest = max(statuses, key=lambda s: s.get("id") or 0)
        return latest.get("state") in TERMINAL_DEPLOY_STATES

    def consider_pr(self, number: int, row: dict[str, Any]) -> None:
        key = str(number)
        closed_at = row.get("closed_at")
        merged_at = row.get("merged_at")
        if row.get("state") not in (None, "closed") or not closed_at:
            if self.pending("pr").pop(key, None) is not None:
                self.plan.cleared.append(("pr", key))
            return
        k = self.revision_of("pr", key)
        previous = None
        if k:
            previous = _read_doc(self.read, raw_path("pr", key, k))
            stored = (previous or {}).get("pull") or {}
            if previous is None or (stored.get("closed_at") == closed_at
                                    and stored.get("merged_at") == merged_at):
                if self.pending("pr").pop(key, None) is not None:
                    self.plan.cleared.append(("pr", key))
                return
        cfg = self.conf
        due_at = _plus_hours(closed_at, cfg.settle_hours)
        defer_until = _plus_hours(closed_at, cfg.max_defer_hours)
        files_raw = None
        held = self.pending("pr").get(key)
        # The designs/ check runs for a NEW PR, and again for a pending one whose earlier pass
        # failed (a capture-failed entry may never have read its files).
        if not k and (held is None or CAPTURE_FAILED in (held.get("reasons") or ())):
            if held is None and key in self.skipped \
                    and (self.skipped[key] or {}).get("closed_at") == closed_at:
                return
            try:
                files_raw = _items(self.gh.get_paged(f"/pulls/{number}/files")) or []
            except (APIError, Truncated):
                self.hold("pr", key, closed_at, Settle("defer", due_at, defer_until), CAPTURE_FAILED)
                return
            if not _touches_designs(files_raw):
                self.pending("pr").pop(key, None)
                self.plan.skipped_prs[number] = closed_at
                return
        if _ts(self.now) < _ts(due_at):
            s = Settle("pending", due_at, defer_until)
        else:
            head_ref = (row.get("head") or {}).get("ref")
            s = settle_pr(closed_at=closed_at, merged_at=merged_at,
                          in_flight_runs=self.in_flight(head_ref),
                          deployment_terminal=(self.deployment_terminal(row.get("merge_commit_sha"))
                                               if merged_at else None),
                          now=self.now, settle_hours=cfg.settle_hours,
                          max_defer_hours=cfg.max_defer_hours,
                          deploy_wait_hours=cfg.deploy_wait_hours)
        if s.action != "freeze":
            self.pending("pr")[key] = _entry(closed_at, s)
            return
        revision = k + 1
        brief_pending: dict[str, dict[str, Any]] = {}
        try:
            doc = _capture_pr(self.gh, number, revision=revision, captured=self.captured,
                              snapshot_runs=self.snap.runs, snapshot_statuses=self.snap.statuses,
                              previous=previous, files_raw=files_raw)
            if s.incomplete:
                doc["incomplete"] = sorted(set(doc["incomplete"]) | set(s.incomplete))
            unit_files = {raw_path("pr", key, revision): _admit("pr", doc)}
            units = [("pr", key, revision, bool(k))]
            for issue in doc["linked_issues"]:
                self.linked_brief(issue, unit_files, units, brief_pending)
        except ContractInvalid:
            # A document the add-only ref could never shed: none of the unit is planned.
            self.hold("pr", key, closed_at, s, CONTRACT_INVALID)
            return
        except UNIT_ERRORS:
            # The PR and its briefs are one unit: a refusal anywhere in it leaves the PR
            # pending (retried next pass) and plans none of it.
            self.hold("pr", key, closed_at, s, CAPTURE_FAILED)
            return
        self.pending("brief").update(brief_pending)
        self.commit_unit(unit_files, units)

    def linked_brief(self, number: int, unit_files: dict[str, bytes],
                     units: list[tuple[str, str, int, bool]],
                     brief_pending: dict[str, dict[str, Any]]) -> None:
        key = str(number)
        if self.revision_of("brief", key) or any(u[0] == "brief" and u[1] == key for u in units):
            return
        issue_raw = _issue(self.gh, number)
        if issue_raw is None:
            return
        timeline_raw = _items(self.gh.get_paged(f"/issues/{number}/timeline")) or []
        if not is_design_brief(rawdoc.project_issue(issue_raw, None),
                               rawdoc.project_timeline(timeline_raw)):
            return  # stays a number (critique item 24)
        s = settle_brief(state=issue_raw.get("state") or "", closed_at=issue_raw.get("closed_at"),
                         linked_by_frozen_pr=True, now=self.now,
                         settle_hours=self.conf.settle_hours,
                         max_defer_hours=self.conf.max_defer_hours)
        if s.action != "freeze":
            brief_pending[key] = _entry(issue_raw.get("closed_at"), s)   # recorded with the unit
            return
        doc = _capture_brief_from(self.gh, number, issue_raw, timeline_raw, revision=1,
                                  captured=self.captured, incomplete=s.incomplete)
        if doc is not None:
            unit_files[raw_path("brief", key, 1)] = _admit("brief", doc)
            units.append(("brief", key, 1, False))

    def cutoff(self, cursor_key: str, since: Optional[str], hours: int) -> str:
        floor = _ts(self.conf.backfill_since)
        cursor = ((self.state.get("cursors") or {}).get(cursor_key))
        start = _ts(cursor) if cursor else floor
        if since:
            start = min(start, _ts(since))
        start = max(start, floor)
        return _fmt(start - timedelta(hours=hours))

    def prs(self, since: Optional[str]) -> None:
        cursor = (self.state.get("cursors") or {}).get("prs_updated")
        cutoff = _ts(self.cutoff("prs_updated", since, self.conf.settle_hours))
        newest = cursor
        seen: set[str] = set()
        done = False
        params = {"state": "closed", "sort": "updated", "direction": "desc"}
        for page, _total in self.gh.iter_pages("/pulls", params):
            for row in page:
                if not isinstance(row, dict) or not isinstance(row.get("number"), int):
                    continue
                updated = row.get("updated_at")
                if not updated or _ts(updated) < cutoff:
                    done = True
                    break
                if newest is None or _ts(updated) > _ts(newest):
                    newest = updated
                seen.add(str(row["number"]))
                self.consider_pr(row["number"], row)
            if done:
                break
        for key in sorted(self.pending("pr"), key=int):
            if key in seen:
                continue
            try:
                row = self.gh.get(f"/pulls/{key}")
            except (APIError, Truncated):
                self.hold_existing("pr", key)
                continue
            if isinstance(row, dict):
                self.consider_pr(int(key), row)
        self.plan.cursors["prs_updated"] = newest

    def briefs(self, since: Optional[str]) -> None:
        cursor = (self.state.get("cursors") or {}).get("briefs_updated")
        start = self.cutoff("briefs_updated", since, 0)
        newest = cursor
        seen: set[str] = set()
        items = _items(self.gh.get_paged("/issues", {"labels": BRIEF_LABEL, "state": "all",
                                                       "sort": "updated", "since": start})) or []
        for item in items:
            if not isinstance(item, dict) or item.get("pull_request") \
                    or not isinstance(item.get("number"), int):
                continue
            updated = item.get("updated_at")
            if updated and (newest is None or _ts(updated) > _ts(newest)):
                newest = updated
            seen.add(str(item["number"]))
            self.consider_brief(item["number"], item)
        for key in sorted(self.pending("brief"), key=int):
            if key in seen:
                continue
            try:
                issue_raw = _issue(self.gh, int(key))
            except (APIError, Truncated):
                self.hold_existing("brief", key)
                continue
            if issue_raw is not None:
                self.consider_brief(int(key), issue_raw)
        self.plan.cursors["briefs_updated"] = newest

    def consider_brief(self, number: int, item: dict[str, Any]) -> None:
        key = str(number)
        k = self.revision_of("brief", key)
        state, closed_at = item.get("state"), item.get("closed_at")
        if k:
            stored = ((_read_doc(self.read, raw_path("brief", key, k)) or {}).get("issue")) or {}
            if not stored or (stored.get("state") == state and stored.get("closed_at") == closed_at):
                return
        if state != "closed" or not closed_at:
            # Open (never frozen, or reopened): nothing is due until it closes; a linked open
            # brief is captured with its PR (brief-open), never from this listing.
            if self.pending("brief").pop(key, None) is not None:
                self.plan.cleared.append(("brief", key))
            return
        s = settle_brief(state=state, closed_at=closed_at, linked_by_frozen_pr=False, now=self.now,
                         settle_hours=self.conf.settle_hours,
                         max_defer_hours=self.conf.max_defer_hours)
        if s.action != "freeze":
            self.pending("brief")[key] = _entry(closed_at, s)
            return
        try:
            doc = capture_brief(self.gh, number, revision=k + 1, captured=self.captured)
            data = None if doc is None else _admit("brief", doc)
        except ContractInvalid:
            self.hold("brief", key, closed_at, s, CONTRACT_INVALID)
            return
        except UNIT_ERRORS:
            self.hold("brief", key, closed_at, s, CAPTURE_FAILED)
            return
        if data is None:
            if self.pending("brief").pop(key, None) is not None:
                self.plan.cleared.append(("brief", key))
            return
        self.commit_unit({raw_path("brief", key, k + 1): data}, [("brief", key, k + 1, bool(k))])

    def releases(self) -> None:
        newest = (self.state.get("cursors") or {}).get("releases_published")
        for rel in _items(self.gh.get_paged("/releases")) or []:
            if not isinstance(rel, dict) or rel.get("draft") or not rel.get("published_at"):
                continue
            try:
                tag = _key("release", rel.get("tag_name"))
            except ValueError:
                continue  # not a path-safe tag: never written (contract tag pattern)
            if newest is None or _ts(rel["published_at"]) > _ts(newest):
                newest = rel["published_at"]
            if self.revision_of("release", tag):
                continue
            try:
                data = _admit("release", capture_release(rel, revision=1, captured=self.captured))
            except ContractInvalid:
                continue  # never planned; the next full /releases listing retries it
            self.commit_unit({raw_path("release", tag, 1): data}, [("release", tag, 1, False)])
        self.plan.cursors["releases_published"] = newest


def plan_freezes(gh: GitHubAPI, *, state: dict[str, Any], frozen: dict[str, dict[str, int]],
                 conf: Any, now: str, read: Callable[[str], Optional[bytes]],
                 only_prs: tuple[int, ...] = (), run_id: int = 0,
                 since: Optional[str] = None) -> FreezePlan:
    """One freeze pass over PRs, briefs and releases (budget stop → partial plan). ``frozen`` is
    ``state.frozen_from_paths(evidence paths)``; ``read(path)`` reads the evidence tree (the
    previous revision for a terminal-state comparison or the retention union)."""
    p = _Pass(gh, state=state, frozen=frozen, conf=conf, now=now, read=read, run_id=run_id)
    try:
        if only_prs:
            for number in sorted(set(only_prs)):
                row = gh.get(f"/pulls/{number}")
                if isinstance(row, dict):
                    p.consider_pr(int(number), row)
        else:
            p.prs(since)
            p.briefs(since)
            p.releases()
    except BudgetExhausted:
        p.plan.budget_stopped = True
    return p.plan


def refreeze(gh: GitHubAPI, number: int, *, state: dict[str, Any], frozen: dict[str, dict[str, int]],
             conf: Any, read: Callable[[str], Optional[bytes]], run_id: int = 0) -> FreezePlan:
    """Capture FROZEN PR ``number`` again as revision K+1 (no settle wait, retention union from
    revision K); adds exactly one path and modifies nothing. A PR with no frozen revision raises
    :class:`RefreezeRefused` before any request — refreeze never bypasses settle or the
    ``designs/`` filter (``harvest --pr N`` is that path)."""
    p = _Pass(gh, state=state, frozen=frozen, conf=conf, now="", read=read, run_id=run_id)
    key = _key("pr", number)
    k = p.revision_of("pr", key)
    if k < 1:
        raise RefreezeRefused(f"refreeze needs a frozen PR: #{key} has no raw/pr revision "
                              "(use harvest --pr for a PR that was never frozen)")
    previous = _read_doc(read, raw_path("pr", key, k))
    try:
        doc = _capture_pr(gh, int(number), revision=k + 1, captured=p.captured,
                          snapshot_runs=p.snap.runs, snapshot_statuses=p.snap.statuses,
                          previous=previous)
    except BudgetExhausted:
        p.plan.budget_stopped = True
        return p.plan
    # Not a changed terminal state, so not in ``recaptured``. A CaptureError (the operator named
    # a PR GitHub cannot serve) and a ContractInvalid propagate — cli exits 1, nothing planned.
    p.commit_unit({raw_path("pr", key, k + 1): _admit("pr", doc)}, [("pr", key, k + 1, False)])
    return p.plan
