"""Freeze — the settle/defer policy and the GET sequences that capture one PR, brief or release.

Late activity never mutates a frozen unit (docs/provenance.md §Freeze
units). A unit is captured ONCE, after it has settled, into
``raw/<kind>/<key>.json.gz`` (revision 1) and only a ``refreeze`` adds
``raw/<kind>/<key>.r<K>.json.gz`` (K ≥ 2); the extractor folds the highest K.

**Settle** (:func:`settle_pr`, pure, ``now`` injected). A closed PR (merged
or closed unmerged) is due at ``closed_at + settle_hours``. At or after
due, it FREEZES when no watched run on its head branch is queued or in
progress and, if merged, the merge sha's Production deployment is terminal
or ``merged_at + deploy_wait_hours`` has passed; otherwise it is DEFERRED
(``pending`` with reasons) — until ``closed_at + max_defer_hours``, when it
freezes anyway with ``incomplete`` naming why (``settle-deferred``,
``deployment-not-terminal``). Before due it is PENDING. A PR whose files
touch no ``designs/`` path is recorded in ``state.skipped.pr`` (never
captured). Briefs (issues labelled ``design-brief``): due at ``closed_at +
settle_hours``; an OPEN brief that a frozen PR links (``briefs``) is
captured as revision 1 with ``incomplete: brief-open``, and re-captured as
the next revision when it later closes and settles. Releases freeze on
publish (non-draft).

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
each deployment's ``/statuses``; 12. briefs = ``body.refs_closes`` ∪ the
``claude/issue-<N>-*`` head-ref number.

Per-SHA check runs are NOT read (54% of the audit's full profile, never
rendered). Statuses use the list endpoint (``/statuses``, every status with
its ``creator``) rather than the combined ``/status`` the plan first named:
the creator is what the ``reviewer-signoff`` trust rule needs, and the list
includes the superseded per-round statuses.

**Brief capture** (:func:`capture_brief`): ``/issues/{b}``, comments,
timeline, GraphQL ``lastEditedAt``. **Release capture**: the ``/releases``
list row itself (no extra GET).

**Selection** (:func:`plan_freezes`): ``closed_pulls_updated_since(cursor -
settle window)`` and ``issues_updated_since("design-brief", cursor)``; with
``--pr`` only those PRs (settle still applies unless ``refreeze``).

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


@dataclass
class FreezePlan:
    """Files to add (``{path: bytes}``) plus state updates and counts for the summary."""

    files: dict[str, bytes] = field(default_factory=dict)
    frozen: list[tuple[str, str, int]] = field(default_factory=list)
    pending: dict[str, dict[str, Any]] = field(default_factory=dict)
    skipped_prs: list[int] = field(default_factory=list)
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
               snapshot_statuses: Callable[[str], Optional[list[dict[str, Any]]]]) -> dict[str, Any]:
    """raw-pr@1 for one PR (module docstring steps 1–12)."""
    raise NotImplementedError("builder H6")


def capture_brief(gh: GitHubAPI, number: int, *, revision: int, captured: dict[str, Any],
                  incomplete: tuple[str, ...] = ()) -> dict[str, Any]:
    """raw-brief@1 for one issue."""
    raise NotImplementedError("builder H6")


def capture_release(release: dict[str, Any], *, revision: int, captured: dict[str, Any]) -> dict[str, Any]:
    """raw-release@1 from a ``/releases`` row."""
    raise NotImplementedError("builder H6")


def plan_freezes(gh: GitHubAPI, *, state: dict[str, Any], conf: Any, now: str,
                 exists: Callable[[str], bool], read: Callable[[str], Optional[bytes]],
                 only_prs: tuple[int, ...] = ()) -> FreezePlan:
    """One freeze pass over PRs, briefs and releases (budget stop → partial plan)."""
    raise NotImplementedError("builder H6")


def refreeze(gh: GitHubAPI, number: int, *, state: dict[str, Any], conf: Any,
             read: Callable[[str], Optional[bytes]]) -> FreezePlan:
    """Capture PR ``number`` again as the next revision (no settle wait); modifies nothing."""
    raise NotImplementedError("builder H6")
