"""Extraction — raw@1 evidence → record@1 (pr, brief, release, direct commit) with event@1 events.

``record = extract(raw, extractor_version)`` is pure (no clock, no network;
git only through ``protocols.GitReader`` for main's history). The serving
join (``serving.annotate_record``) runs AFTER extraction and fills
``runtime`` and the ``window`` tier; extraction fills everything that is a
function of the raw document alone (docs/provenance.md §Records).

**PR events** (:func:`extract_pr`) — every event's ``url`` is constructed
from validated numeric ids and ``ctx.owner``/``ctx.repo`` (never copied
from a payload ``html_url``):

=====================================  =======================  ==========================  =====================================
source (raw-pr@1)                       kind                     id                          ts / sha / url
=====================================  =======================  ==========================  =====================================
``pull``                                pr.opened                ``pr:<n>:opened``           created_at / – / ``pull/<n>``
``timeline`` ``ready_for_review``       pr.ready_for_review      ``timeline:<id>``           created_at / – / ``pull/<n>``
``pull`` merged                         pr.merged                ``pr:<n>:merged``           merged_at / merge sha / ``pull/<n>``
``pull`` closed, not merged             pr.closed                ``pr:<n>:closed``           closed_at / – / ``pull/<n>``
``commits[]``                           commit.* (below)         ``commit:<sha>``            author date / sha / ``pull/<n>/commits/<sha>``
``issue_comments[]`` with a             review.signoff           ``issuecomment:<id>``       created_at / marker sha /
JANE/DRIK_SIGNOFF marker                                                                     ``pull/<n>#issuecomment-<id>``
``issue_comments[]`` with PM_TRIAGE     triage.verdict           ``issuecomment:<id>``       same
``issue_comments[]`` COACH_LOCK marker  coach.lock               ``issuecomment:<id>``       same (sha = COACH_DONE sha or null)
or lead ``coach_lock``
``issue_comments[]`` lead coach_round   coach.round              ``issuecomment:<id>``       same, sha null
``issue_comments[]`` ORACLE_REVIEW head oracle.review            ``issuecomment:<id>``       same, sha null
``statuses[sha]`` context               status.reviewer_signoff  ``status:<id>``             created_at / sha / ``pull/<n>/commits/<sha>``
``reviewer-signoff`` (except "no design
changes" → noise)
``ci_runs[]`` (one per run)             ci.gate                  ``run:<id>``                created_at / head_sha / ``actions/runs/<id>``
``deployments[]`` environment           deploy.production        ``deployment:<id>``         first terminal status created_at
Production                                                                                   (else created_at) / sha / ``commit/<sha>``
=====================================  =======================  ==========================  =====================================

(``job.reviewer`` events come from receipts in ``serving.receipt_events``.)

Which comment yields which event: the marker the event is built from is
``digest.suffix_markers[-1]`` when it is a sign-off/completion marker, else
the LAST matching line of ``digest.marker_lines``. One comment yields at
most one event. ``review.signoff`` fields: ``family``, ``verdict``, ``fuse``,
``edited``; ``triage.verdict``: ``designs`` (all PM_TRIAGE ``design=``
values), counts from ``digest.table_verdicts`` (a row counts toward every
token it carries — "decline the claim, act-now the kernel" is one act-now
and one decline), ``rows``, ``completion_marker``, ``edited``.

**Commit kinds** (:func:`commit_kind`, first rule wins): regen identity →
``commit.regen``; ≥ 2 parents → ``commit.merge_main``; the first non-regen,
non-merge commit of the PR authored by a builder bot (``github-actions[bot]``
or ``claude[bot]``) → ``commit.design``; author login == the repo owner and
no agent trailer (``Co-Authored-By: Claude…``/``Cursor…``, ``Claude-Session``)
→ ``commit.human``; otherwise ``commit.fix``.

**Platform** (``runtime.platform``, D): regen/bot-authored commits and
Actions-bot comments/statuses → ``github-actions``; author login ``claude``
or a ``Claude-Session`` trailer → ``claude-code``; ``cursoragent`` /
``cursor[bot]`` / a Cursor co-author → ``cursor``; ``Copilot`` /
``copilot-*`` → ``copilot``; ``coderabbitai[bot]`` → ``coderabbit``;
``vercel[bot]`` → ``vercel``; committer ``web-flow`` → ``github-web``;
else ``unknown``.

**Noise** — never events, counted into ``noise_counts`` by the closed keys
(contract ``enums.noise_key``): third-party bot comments by app, lead
``bugbot_limit``/``qodo_paused``/``decision_needed``/``clear_prs``, reviews
(bot / empty wrapper / human), review comments, statuses other than
reviewer-signoff (and its "no design changes" form), the three sticky
families, timeline ``deployed`` (preview deployments) and other timeline
events, ``unknown.marker`` → ``record.unknown.markers``. Counted over
harvested sources only (NVC-12 is re-baselined on these keys).

**Brief events** (:func:`extract_brief`): ``issue:<n>:filed`` (brief.filed,
``fields.design_name`` null — the SHIP-LOCK carries the name),
comment leads ``ship_lock``→brief.claimed, ``shipped``→brief.shipped,
``declined``/``deferred``/``ship_lock_withdrawn``→brief.declined/deferred/
withdrawn, timeline ``closed`` → brief.closed (``closed_by_pr`` when a PR in
``ctx.merge_shas`` closed it: the timeline event's ``commit_id`` is that PR's
merge sha, or a frozen PR lists the brief in ``briefs`` and merged within
60 s before the close). ``record.design_name`` = the last SHIP-LOCK's
``design_name`` (validated slug), else the slug of a ``Design brief: <slug>``
title prefix — null otherwise. Brief trust: ``brief.filed`` by the Actions
bot is ``login`` until serving finds a unique scout window; an issue body
with ``last_edited_at`` set is ``claimed``.

**Releases** (:func:`extract_release`): one ``release`` event; ``designs``
= the designs on main whose name prefixes an asset name (``<d>-…``/``<d>.…``).

**Direct-to-main commits** (:func:`extract_direct_commits`): first-parent
main commits touching ``designs/`` that belong to no frozen PR (not a PR
merge commit, not in any PR's commit list); membership by
``membership.classify_pr`` over ``changed_paths``; trailer runtime as claimed.

Records carry ``extractor`` = :data:`EXTRACTOR_VERSION` and are sorted by
``canonical.event_sort_key``. Owner: H3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .protocols import GitReader

EXTRACTOR_VERSION = "provenance-extract 1"
BUILDER_BOTS = frozenset({"github-actions[bot]", "claude[bot]"})


@dataclass(frozen=True)
class ExtractContext:
    """Everything extraction needs besides the raw document.

    ``owner``/``repo`` — URL construction; ``owner_login`` — the repo owner
    (owner-token detection); ``git`` — main's history (merge method, main
    subject, blame); ``main_sha`` — the harvest's main; ``design_names`` —
    ``designs/*/`` on main; ``merge_shas`` — ``{merge sha: pr}`` of frozen
    PRs (brief close attribution); ``edit_grace_seconds`` — conf.
    """

    owner: str
    repo: str
    owner_login: str
    git: GitReader
    main_sha: str
    design_names: frozenset[str]
    merge_shas: dict[str, int] = field(default_factory=dict)
    edit_grace_seconds: int = 60


def commit_kind(commit: dict[str, Any], *, first_builder_commit: bool, owner_login: str) -> str:
    """``commit.regen|merge_main|design|human|fix`` for one raw-pr@1 commit."""
    raise NotImplementedError("builder H3")


def merge_method(git: GitReader, merge_sha: Optional[str], pr: int) -> Optional[str]:
    """``merge`` (2 parents) | ``squash`` (1 parent, subject ends ``(#pr)``) | ``rebase`` | ``None``."""
    raise NotImplementedError("builder H3")


def extract_pr(raw_pr: dict[str, Any], ctx: ExtractContext) -> dict[str, Any]:
    """record@1:pr (events placed by ``episodes``; runtime ``none`` until serving)."""
    raise NotImplementedError("builder H3")


def extract_brief(raw_brief: dict[str, Any], ctx: ExtractContext) -> dict[str, Any]:
    """record@1:brief."""
    raise NotImplementedError("builder H3")


def extract_release(raw_release: dict[str, Any], ctx: ExtractContext) -> dict[str, Any]:
    """record@1:release."""
    raise NotImplementedError("builder H3")


def extract_direct_commits(ctx: ExtractContext, pr_commit_shas: set[str]) -> list[dict[str, Any]]:
    """record@1:commit for each first-parent main commit touching designs/ outside any PR."""
    raise NotImplementedError("builder H3")


def empty_runtime(platform: str = "unknown") -> dict[str, Any]:
    """The runtime object before serving runs: all join fields null, ``model_basis`` ``none``."""
    raise NotImplementedError("builder H3")


def url_for(ctx: ExtractContext, kind: str, **ids: Any) -> str:
    """Construct a permalink (kinds: issue, issuecomment, pull, pr_commit, commit, run, job,
    release, blob). Every id is validated numeric / 40-hex / slug; anything else raises ValueError."""
    raise NotImplementedError("builder H3")
