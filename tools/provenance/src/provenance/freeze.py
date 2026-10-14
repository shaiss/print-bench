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

Owner: H6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

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
    ``skipped_prs`` maps PR → ``closed_at``.
    """

    files: dict[str, bytes] = field(default_factory=dict)
    frozen: list[tuple[str, str, int]] = field(default_factory=list)
    pending: dict[str, dict[str, Any]] = field(default_factory=dict)
    skipped_prs: dict[int, str] = field(default_factory=dict)
    recaptured: list[tuple[str, str, int]] = field(default_factory=list)
    cursors: dict[str, Optional[str]] = field(default_factory=dict)
    budget_stopped: bool = False


def raw_path(kind: str, key: str, revision: int) -> str:
    """``raw/<kind>/<key>.json.gz`` (revision 1) or ``raw/<kind>/<key>.r<K>.json.gz``."""
    raise NotImplementedError("builder H6")


def settle_pr(*, closed_at: str, merged_at: Optional[str], in_flight_runs: int,
              deployment_terminal: Optional[bool], now: str, settle_hours: int,
              max_defer_hours: int, deploy_wait_hours: int) -> Settle:
    """The settle decision for one closed PR (module docstring)."""
    raise NotImplementedError("builder H6")


def settle_brief(*, state: str, closed_at: Optional[str], linked_by_frozen_pr: bool, now: str,
                 settle_hours: int, max_defer_hours: int) -> Settle:
    """The settle decision for one design-brief issue."""
    raise NotImplementedError("builder H6")


def capture_pr(gh: GitHubAPI, number: int, *, revision: int, captured: dict[str, Any],
               snapshot_runs: Callable[[], list[dict[str, Any]]],
               snapshot_statuses: Callable[[str], Optional[list[dict[str, Any]]]],
               previous: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """raw-pr@1 for one PR (module docstring steps 1–12). ``previous`` = revision K's document
    (revision ≥ 2): its :data:`RETENTION_BOUND` sections are unioned in by id, live winning."""
    raise NotImplementedError("builder H6")


def is_design_brief(issue: dict[str, Any], timeline: list[dict[str, Any]]) -> bool:
    """The issue carries ``design-brief`` now, or its timeline shows it ``labeled`` so (projected
    shapes: ``rawdoc.project_issue`` / ``project_timeline``)."""
    raise NotImplementedError("builder H6")


def capture_brief(gh: GitHubAPI, number: int, *, revision: int, captured: dict[str, Any],
                  incomplete: tuple[str, ...] = ()) -> Optional[dict[str, Any]]:
    """raw-brief@1 for one issue, or ``None`` when :func:`is_design_brief` is false."""
    raise NotImplementedError("builder H6")


def capture_release(release: dict[str, Any], *, revision: int, captured: dict[str, Any]) -> dict[str, Any]:
    """raw-release@1 from a ``/releases`` row."""
    raise NotImplementedError("builder H6")


def plan_freezes(gh: GitHubAPI, *, state: dict[str, Any], frozen: dict[str, dict[str, int]],
                 conf: Any, now: str, read: Callable[[str], Optional[bytes]],
                 only_prs: tuple[int, ...] = ()) -> FreezePlan:
    """One freeze pass over PRs, briefs and releases (budget stop → partial plan). ``frozen`` is
    ``state.frozen_from_paths(evidence paths)``; ``read(path)`` reads the evidence tree (the
    previous revision for a terminal-state comparison or the retention union)."""
    raise NotImplementedError("builder H6")


def refreeze(gh: GitHubAPI, number: int, *, state: dict[str, Any], frozen: dict[str, dict[str, int]],
             conf: Any, read: Callable[[str], Optional[bytes]]) -> FreezePlan:
    """Capture PR ``number`` again as the next revision (no settle wait, retention union from
    revision K); adds exactly one path and modifies nothing."""
    raise NotImplementedError("builder H6")
