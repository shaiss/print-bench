"""Extraction — raw@1 evidence → record@1 (pr, brief, release, direct commit) with event@1 events.

``record = extract(raw, extractor_version)`` is pure (no clock, no network;
git only through ``protocols.GitReader`` for main's history). The serving
join (``serving.annotate_record``) runs AFTER extraction and fills
``runtime`` and the ``window`` tier; extraction fills everything that is a
function of the raw document alone (docs/provenance.md §Records). Every
event leaves here PLACED (``episodes.assign`` over ``episodes.rounds``), so a
record is contract-valid before the join.

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
``issue_comments[]`` with PM_TRIAGE     triage.verdict           ``issuecomment:<id>``       same (sha = the PM_TRIAGE sha)
``issue_comments[]`` COACH_LOCK marker  coach.lock               ``issuecomment:<id>``       same (sha = COACH_DONE sha or null)
or lead ``coach_lock``
``issue_comments[]`` lead coach_round   coach.round              ``issuecomment:<id>``       same, sha null
``issue_comments[]`` ORACLE_REVIEW      oracle.review            ``issuecomment:<id>``       same, sha null
``reviews[]`` (a PR review body) by     the same kinds as an     ``review:<id>``             submitted_at / the same sha /
the same selection as an issue comment  issue comment                                        ``pull/<n>#pullrequestreview-<id>``
``statuses[sha]`` context               status.reviewer_signoff  ``status:<id>``             created_at / sha / ``pull/<n>/commits/<sha>``
``reviewer-signoff`` (except "no design
changes" → noise)
``ci_runs[]`` (one per run)             ci.gate                  ``run:<id>``                created_at / head_sha / ``actions/runs/<id>``
``deployments[]`` environment           deploy.production        ``deployment:<id>``         created_at / sha / ``commit/<sha>``
Production
=====================================  =======================  ==========================  =====================================

(``job.reviewer`` events come from receipts in ``serving.receipt_events``.)
A deployment's ``ts`` is the deployment's own ``created_at`` (the golden's
NVC-11, 22:57:47Z; its first status follows a second later), its
``fields.state`` the state of its first terminal status (``success``,
``failure``, ``error``, ``inactive``) in id order, else of its last status,
else null.

Which comment yields which event: the marker the event is built from is
``digest.suffix_markers[-1]`` when it is a valid sign-off/completion marker
(``JANE_SIGNOFF``, ``DRIK_SIGNOFF``, ``PM_TRIAGE_DONE``, ``COACH_DONE``),
else the LAST valid line of ``digest.marker_lines`` of an event family
(those four, ``PM_TRIAGE``, ``COACH_LOCK``, ``ORACLE_REVIEW``); a marker
that fails its parser (``markers.parse_signoff`` …) is not valid. Its family
picks the kind: a sign-off → ``review.signoff``; ``PM_TRIAGE``/
``PM_TRIAGE_DONE`` → ``triage.verdict`` (built from the last valid
``PM_TRIAGE`` line); ``COACH_LOCK``/``COACH_DONE`` → ``coach.lock``;
``ORACLE_REVIEW`` → ``oracle.review``. With no event marker, lead
``coach_lock`` → ``coach.lock`` and lead ``coach_round`` → ``coach.round``.
One comment yields at most one event; any author's post can (a marker quoted
by another author is an event the trust tier demotes). ``review.signoff``
fields: ``family``, ``verdict``, ``fuse``, ``edited``; ``triage.verdict``:
``designs`` (all PM_TRIAGE ``design=`` values), counts from
``digest.table_verdicts`` (a row counts toward every token it carries —
"decline the claim, act-now the kernel" is one act-now and one decline),
``rows``, ``completion_marker`` (a ``PM_TRIAGE_DONE`` line is present),
``edited``. ``edited`` = ``updated_at − created_at >= edit_grace_seconds``.

A PR review body (``reviews[]``) is selected EXACTLY like an issue comment —
"one attribute grammar parses all five" eras, and the M3 era (08-23/24) posted
Jane's sign-offs with ``gh pr review``: on #371 + #397 fifteen of the
sbc-case design's 31 sign-offs (every Jane sign-off on #397, one on #371)
exist only as review bodies (the audit golden's ``#pullrequestreview-`` rows,
pinned by tests/test_acceptance.py). Its id is ``review:<id>``, its ``ts``
``submitted_at`` (a pending review has none and yields nothing), its ``app``
null and it is never ``edited`` (the REST review has no ``updated_at``).

**Trust** at extraction: marker events take ``trust.comment_tier`` (H2's
port of reviewer-posted.sh / coach-lock-check.sh) — for a REVIEW body capped
at ``claimed``/``marker:no-suffix`` (:data:`REVIEW_TIER_CAP`): reviewer-posted.sh
reads ONLY issue comments, the reviewer MCP's sole write target ("review
bodies and line comments are out of scope; a planted marker there cannot
satisfy the walk/stamp"), so a review can never be the MCP-suffixed artifact
the verified rule names, even when its digest ends with that suffix (one #397
review does); serving may still lift it to ``window``. ``status.reviewer_signoff``
takes ``trust.status_tier`` with ``ctx.auto_review_run_ids`` (the run ids of
the evidence's ``auto-review.yml`` receipts — ``bundle.derive`` passes them)
and ``owner_login=ctx.owner_login`` (H2's signature: it names the owner's own
statuses ``marker:owner-token``),
and its runtime join (``run_id`` + ``workflow: auto-review.yml``, the
target_url's run) is made only when that tier is
``verified``/``actions-status+receipt`` — the rule's own conclusion, so an
owner-token status pointing at an auto-review run gets no runtime;
``ci.gate`` is ``verified``/``receipt`` (the run object is the Actions
record itself); a commit with an agent trailer (``Co-Authored-By: Claude…``
/ ``Cursor…``, ``Claude-Session``) is ``claimed``/``trailer``; an edited
lead-only comment (SHIP-LOCK, coach round …) is ``claimed``/``marker:edited``;
everything else with a known author login is ``login``, without one
``none``. ``serving.annotate_record`` upgrades ``login``/``claimed`` to
``window`` where exactly one compatible window holds the artifact.

**Commit kinds** (:func:`commit_kind`, first rule wins): regen identity →
``commit.regen``; ≥ 2 parents → ``commit.merge_main``; the PR's first
non-regen, non-merge commit (``first_builder_commit`` — the caller knows the
position) when it is authored by a builder bot (author login or commit
author name ``github-actions[bot]``/``claude[bot]``) → ``commit.design``;
author login == the repo owner and no agent trailer → ``commit.human``;
otherwise ``commit.fix``.

**Platform** (``runtime.platform``, D; first rule wins): regen commits,
commits authored by a builder bot (author login or commit author name
``github-actions[bot]``/``claude[bot]``), and every other event whose login is
the Actions bot (``github-actions[bot]``/``github-actions``) or ``claude[bot]``
→ ``github-actions``. ``claude[bot]`` is claude-code-action's identity (the
Claude app's installation token inside an Actions job — the same identity the
builder-commit rule already places on ``github-actions``), so its comments
and reviews are Actions-hosted too; the GitHub app ``claude`` on a comment by
a non-bot login (a user-token post via the app) is what the app rule below
maps to ``claude-code``. Then: author login ``claude`` or a ``Claude-Session`` trailer →
``claude-code``; ``cursoragent`` / ``cursor[bot]`` / a ``Cursor`` co-author →
``cursor``; ``Copilot`` / ``copilot-*`` → ``copilot``; ``coderabbitai[bot]``
→ ``coderabbit``; ``vercel[bot]`` → ``vercel``; committer ``web-flow`` →
``github-web``; then the comment's GitHub app (``github-actions``,
``claude`` → ``claude-code``, ``cursor``, ``copilot*``, ``coderabbitai``,
``vercel``); else ``unknown``. ``runtime.harness`` (D): ``claude-code`` for
the ``claude-code`` platform, ``claude-code-action`` for a commit (author
name) or a comment/review (login) authored by ``claude[bot]``,
``cursor-agent`` for a Cursor commit, else null.

**Noise** — never events, counted into ``noise_counts`` by the closed keys
(contract ``enums.noise_key``; zero counts omitted): a comment that is no
event is, first match, lead ``bugbot_limit``/``qodo_paused``/
``decision_needed``/``clear_prs`` → ``comment.<lead>``; a sticky marker
(``markers.STICKY_FAMILIES``) → ``sticky.*``; a third-party bot author (a
``Bot`` / ``…[bot]`` login other than ``github-actions[bot]``/``claude[bot]``)
→ ``comment.bot.<coderabbit|cursor|qodo|vercel|entelligence|copilot|other>``
(by login, then app); else ``comment.unclassified``. Reviews that are no
event → an empty body ``review.empty_wrapper``, a bot ``review.bot``, else
``review.human``; review
comments → ``review_comment.bot|human``; statuses other than
reviewer-signoff → ``status.coderabbit`` / ``status.vercel`` (by context or
creator) / ``status.other``, and the reviewer-signoff "no design changes"
form → ``status.reviewer_signoff.no_design_changes``; timeline ``deployed``
(preview deployments) → ``timeline.deployed``, every other timeline item but
``ready_for_review`` → ``timeline.other``; ``markers.unknown_families`` over
the PR body, every issue comment and every review → ``marker.unknown`` (one
per family occurrence) and ``record.unknown.markers``. Counted over
harvested sources only (NVC-12 is re-baselined on these keys —
tests/fixtures/acceptance.json).

**Brief events** (:func:`extract_brief`): ``issue:<n>:filed`` (brief.filed,
``fields.design_name`` null — the SHIP-LOCK carries the name),
comment leads ``ship_lock``→brief.claimed, ``shipped``→brief.shipped,
``declined``/``deferred``/``ship_lock_withdrawn``→brief.declined/deferred/
withdrawn (each with its own ``lead_fields.design_name``), timeline
``closed`` → brief.closed (``closed_by_pr`` when a PR in ``ctx.merge_shas``
closed it: the closed event's ``commit_id`` is that PR's merge sha, or a
``referenced`` timeline event whose ``commit_id`` is a frozen PR's merge sha
lies within the 60 s before the close — GitHub records the merge commit's
reference, not the commit, on the close itself; its ``state_reason`` is the
event's, else for the last close of a closed issue the issue's).
``record.design_name`` = the design_name of the last SHIP-LOCK that carries
one (validated slug), else the slug of a ``Design brief: <slug>`` title
prefix — null otherwise. ``record.prs`` = every ``shipped_pr`` and
``closed_by_pr``. Brief trust: ``brief.filed`` by the Actions bot is
``login`` until serving finds a unique scout window; an issue body with
``last_edited_at`` set is ``claimed``/``marker:edited``.

**Releases** (:func:`extract_release`): one ``release`` event (episode
``D:<publication day>``); ``designs`` = for every asset, the LONGEST design
name on main that prefixes it (``<d>-…``/``<d>.…``), so ``nuggs-vent-cap-…``
is not also credited to ``nuggs``.

**Direct-to-main commits** (:func:`extract_direct_commits`; critique item 7).
A first-parent main commit touching ``designs/`` is a DIRECT commit only when
all three hold: (1) its subject carries no PR reference — no squash ``(#N)``
suffix and no ``Merge pull request #N`` (``digest.message_digest``'s
``subject_pr`` rule); (2) its committer is not GitHub (``committer_email !=
noreply@github.com``) — GitHub commits a rebase merge's rewritten commits
(and web edits), which belong to a PR whose own commit list never holds
those new shas; (3) it is in no frozen PR's commit list. A ``(#N)`` commit
whose PR is not frozen yet (inside its settle window, or before the P2
backfill reaches it) therefore yields NO record — the site's checkout-derived
"settling" state covers it — instead of a ``C:`` record that would vanish
when the PR freezes (false history plus churn). Measured on main since
2026-07-31: 366 of 372 first-parent commits carry ``(#N)``; of the other six,
five are the owner-committed 07-31/08-01 bootstrap commits (real direct
commits) and one is ``43030db9`` "Merge PR #196: …" — committed by GitHub with
a subject neither PR pattern matches, which rule (2) keeps from becoming a
false direct record.
Membership by ``membership.classify_pr`` over ``changed_paths`` (title = the
subject, merged). ``GitReader`` exposes no author or message, so the one
event is ``commit.merge_main`` for ≥ 2 parents, else ``commit.human`` (a
non-GitHub committer pushed it to main), with empty signals, trust
``none`` and ``signature_verified`` false (not checked) — honest, not
guessed.

**Linked issues vs briefs** (critique item 24). ``record.linked_issues`` =
``raw.linked_issues``; ``record.briefs`` = those with a ``raw/brief/<n>``
document in the evidence (``ctx.brief_numbers``) — only design briefs are
captured, so a backlog-burn PR's ``autonomy-ok`` issue stays a number.

Records carry ``extractor`` = :data:`EXTRACTOR_VERSION` and are sorted by
``canonical.event_sort_key``. Owner: H3.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from . import canonical, episodes, markers, membership, trust
from .protocols import GitReader

EXTRACTOR_VERSION = "provenance-extract 1"
RECORD_FORMAT = "record@1"
BUILDER_BOTS = frozenset({"github-actions[bot]", "claude[bot]"})
#: The Actions bot's REST and GraphQL spellings plus claude-code-action's ``claude[bot]``: the
#: logins the platform rule puts on ``github-actions`` and the noise rule never calls third-party.
OUR_BOTS = frozenset({"github-actions[bot]", "github-actions", "claude[bot]"})
CLAUDE_APP_BOT = "claude[bot]"


@dataclass(frozen=True)
class ExtractContext:
    """Everything extraction needs besides the raw document.

    ``owner``/``repo`` — URL construction; ``owner_login`` — the repo owner
    (owner-token detection); ``git`` — main's history (merge method, main
    subject, blame); ``main_sha`` — the harvest's main; ``design_names`` —
    ``designs/*/`` on main; ``merge_shas`` — ``{merge sha: pr}`` of frozen
    PRs (brief close attribution); ``brief_numbers`` — issues with a
    ``raw/brief/`` document (``record.briefs``); ``edit_grace_seconds`` — conf;
    ``auto_review_run_ids`` — run ids of the evidence's ``auto-review.yml``
    receipts (``trust.status_tier``'s receipt half; empty = no status is
    receipt-verified).
    ``main_sha`` is used for READING main (design names, rows, merge method),
    never stored in a record or view (critique item 6).
    """

    owner: str
    repo: str
    owner_login: str
    git: GitReader
    main_sha: str
    design_names: frozenset[str]
    merge_shas: dict[str, int] = field(default_factory=dict)
    brief_numbers: frozenset[int] = frozenset()
    edit_grace_seconds: int = 60
    auto_review_run_ids: frozenset[int] = frozenset()


# ---------------------------------------------------------------------------
# Validation helpers (every stored value must satisfy the closed contract).

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_TS_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_LOGIN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}(\[bot\])?")
_APP_RE = re.compile(r"[a-z0-9-]{1,64}")
_DESIGN_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_TAG_RE = re.compile(r"[A-Za-z0-9._-]{1,100}")
_OWNER_RE = re.compile(r"[A-Za-z0-9-]+")
_REPO_RE = re.compile(r"[A-Za-z0-9._-]+")
_SESSION_RE = re.compile(r"https://claude\.ai/code/session_[A-Za-z0-9]{8,64}")
#: The contract's ``types.url.re`` WITH H3's requested delta (the ``#pullrequestreview-<id>``
#: anchor of a review-sourced event); tests/test_extract.py pins it to the delta-applied contract.
_URL_RE = re.compile(
    r"https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+/(issues/[0-9]+(#issuecomment-[0-9]+)?"
    r"|pull/[0-9]+(/commits/[0-9a-f]{40}|#issuecomment-[0-9]+|#pullrequestreview-[0-9]+)?|commit/[0-9a-f]{40}"
    r"|actions/runs/[0-9]+(/job/[0-9]+)?|releases/tag/[A-Za-z0-9._-]+"
    r"|blob/[0-9a-f]{40}/designs/[a-z0-9-]+/(PM|NOTES)\.md#L[0-9]+)")
_TITLE_SLUG_RE = re.compile(r"Design brief: ([a-z0-9][a-z0-9-]{0,63})(?=$|\s)")
_CLAIM_BRANCH_RE = re.compile(r"claude/issue-([0-9]{1,7})-")
_WORKFLOW_PATH_RE = re.compile(r"\.github/workflows/([a-z0-9][a-z0-9-]{0,63}\.yml)")

PLATFORMS = ("github-actions", "claude-code", "cursor", "copilot", "coderabbit", "vercel",
             "github-web", "unknown")
LOGIN_TYPES = ("User", "Bot", "Organization", "Mannequin")
CONCLUSIONS = frozenset({"success", "failure", "cancelled", "skipped", "neutral", "timed_out",
                         "action_required", "stale", "startup_failure"})
STATUS_STATES = frozenset({"success", "failure", "pending", "error"})
DEPLOY_STATES = frozenset({"success", "failure", "error", "inactive", "pending", "in_progress",
                           "queued"})
DEPLOY_TERMINAL = frozenset({"success", "failure", "error", "inactive"})
STATE_REASONS = frozenset({"completed", "not_planned", "duplicate", "reopened"})

SIGNOFF_FAMILIES = frozenset(markers.SIGNOFF_FAMILIES)
COMPLETION_FAMILIES = SIGNOFF_FAMILIES | {"PM_TRIAGE_DONE", "COACH_DONE"}
EVENT_FAMILIES = COMPLETION_FAMILIES | {"PM_TRIAGE", "COACH_LOCK", "ORACLE_REVIEW"}
NOISE_LEADS = frozenset({"bugbot_limit", "qodo_paused", "decision_needed", "clear_prs"})
BRIEF_LEAD_KINDS = {"ship_lock": "brief.claimed", "shipped": "brief.shipped",
                    "declined": "brief.declined", "deferred": "brief.deferred",
                    "ship_lock_withdrawn": "brief.withdrawn"}
CLOSE_REFERENCE_SECONDS = 60
#: ``trust.status_tier``'s verified result — the only status tier that carries a runtime join.
STATUS_RECEIPT_TIER = ("verified", "actions-status+receipt")
#: A review body's ceiling: reviewer-posted.sh reads ONLY issue comments ("a planted marker
#: there cannot satisfy the walk/stamp"), so a review is never the MCP-suffixed artifact.
REVIEW_TIER_CAP = ("claimed", "marker:no-suffix")


def _login(obj: Any) -> Optional[str]:
    value = obj.get("login") if isinstance(obj, dict) else obj
    return value if isinstance(value, str) and _LOGIN_RE.fullmatch(value) else None


def _login_type(obj: Any) -> Optional[str]:
    if isinstance(obj, dict):
        value = obj.get("type")
        return value if value in LOGIN_TYPES else None
    login = _login(obj)
    return "Bot" if login and login.endswith("[bot]") else None


def _app(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and _APP_RE.fullmatch(value) else None


def _sha(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and _SHA_RE.fullmatch(value) else None


def _ts(value: Any) -> Optional[str]:
    """An RFC3339 UTC second-precision timestamp, normalising an offset or a fraction."""
    if not isinstance(value, str):
        return None
    if _TS_RE.fullmatch(value):
        return value
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch(ts: str) -> int:
    return calendar.timegm((int(ts[0:4]), int(ts[5:7]), int(ts[8:10]),
                            int(ts[11:13]), int(ts[14:16]), int(ts[17:19]), 0, 0, 0))


def _ts_of_epoch(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cap(value: Any, limit: int) -> Optional[str]:
    """A string kept only when it fits the contract's ``max`` (never truncated)."""
    return value if isinstance(value, str) and len(value) <= limit else None


def _edited(created_at: Optional[str], updated_at: Optional[str], grace: int) -> bool:
    created, updated = _ts(created_at), _ts(updated_at)
    return bool(created and updated) and _epoch(updated) - _epoch(created) >= grace


# ---------------------------------------------------------------------------
# URLs, runtime, signals.

def build_url(owner: str, repo: str, kind: str, **ids: Any) -> str:
    """The permalink of :func:`url_for` from a bare owner/repo (``episodes.decision_rows`` uses it)."""
    if not _OWNER_RE.fullmatch(owner or "") or not _REPO_RE.fullmatch(repo or ""):
        raise ValueError(f"url: bad owner/repo {owner!r}/{repo!r}")

    def num(name: str) -> int:
        value = ids.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"url {kind}: {name}={value!r} is not a positive integer")
        return value

    def sha(name: str) -> str:
        value = ids.get(name)
        if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
            raise ValueError(f"url {kind}: {name}={value!r} is not a 40-hex sha")
        return value

    shapes = {"issue": {"number"}, "issuecomment": {"number", "comment"}, "pull": {"number"},
              "review": {"number", "review"},
              "pr_commit": {"number", "sha"}, "commit": {"sha"}, "run": {"run"},
              "job": {"run", "job"}, "release": {"tag"}, "blob": {"sha", "design", "file", "line"}}
    if kind not in shapes:
        raise ValueError(f"url: unknown kind {kind!r}")
    given = set(ids)
    allowed = shapes[kind] | ({"comment"} if kind == "pull" else set())
    if not shapes[kind] <= given or not given <= allowed:
        raise ValueError(f"url {kind}: ids {sorted(given)} (want {sorted(shapes[kind])})")
    if kind == "issue":
        tail = f"issues/{num('number')}"
    elif kind == "issuecomment":
        tail = f"issues/{num('number')}#issuecomment-{num('comment')}"
    elif kind == "pull":
        tail = f"pull/{num('number')}"
        if ids.get("comment") is not None:
            tail += f"#issuecomment-{num('comment')}"
    elif kind == "review":
        tail = f"pull/{num('number')}#pullrequestreview-{num('review')}"
    elif kind == "pr_commit":
        tail = f"pull/{num('number')}/commits/{sha('sha')}"
    elif kind == "commit":
        tail = f"commit/{sha('sha')}"
    elif kind == "run":
        tail = f"actions/runs/{num('run')}"
    elif kind == "job":
        tail = f"actions/runs/{num('run')}/job/{num('job')}"
    elif kind == "release":
        tag = ids.get("tag")
        if not isinstance(tag, str) or not _TAG_RE.fullmatch(tag):
            raise ValueError(f"url release: tag={tag!r}")
        tail = f"releases/tag/{tag}"
    else:
        design, name = ids.get("design"), ids.get("file")
        if not isinstance(design, str) or not _DESIGN_RE.fullmatch(design):
            raise ValueError(f"url blob: design={design!r}")
        if name not in ("PM.md", "NOTES.md"):
            raise ValueError(f"url blob: file={name!r}")
        tail = f"blob/{sha('sha')}/designs/{design}/{name}#L{num('line')}"
    url = f"https://github.com/{owner}/{repo}/{tail}"
    if len(url) > 300 or not _URL_RE.fullmatch(url):
        raise ValueError(f"url: {url!r} fails the contract pattern")
    return url


def url_for(ctx: ExtractContext, kind: str, **ids: Any) -> str:
    """Construct a permalink (kinds: issue, issuecomment, pull, review, pr_commit, commit, run, job,
    release, blob). Every id is validated numeric / 40-hex / slug; anything else raises ValueError.
    ``blob`` is ``blob/<added_in_sha>/designs/<d>/<file>#L<original line>`` — the commit that
    added the row and its line THERE, so the URL never changes with main (critique item 6).

    Ids by kind: ``issue(number)``, ``issuecomment(number, comment)`` (an issue thread),
    ``pull(number[, comment])`` (a PR, or a comment on its thread), ``review(number, review)``
    (``pull/<n>#pullrequestreview-<id>``, a PR review body), ``pr_commit(number, sha)``,
    ``commit(sha)``, ``run(run)``, ``job(run, job)``, ``release(tag)``,
    ``blob(sha, design, file, line)``; a missing or extra id raises ValueError."""
    return build_url(ctx.owner, ctx.repo, kind, **ids)


def empty_runtime(platform: str = "unknown") -> dict[str, Any]:
    """The runtime object before serving runs: all join fields null, ``model_basis`` ``none``."""
    if platform not in PLATFORMS:
        raise ValueError(f"runtime: unknown platform {platform!r}")
    return {"attempt": None, "chain": None, "chain_link": None, "harness": None, "job": None,
            "job_id": None, "links_not_served": None, "model": None, "model_basis": "none",
            "platform": platform, "provider": None, "role": None, "run_id": None,
            "workflow": None}


def empty_signals() -> dict[str, Any]:
    """The signals object with every identity fact absent."""
    return {"app": None, "commit_author_email": None, "commit_author_name": None,
            "committer_login": None, "login": None, "login_type": None, "marker": None,
            "regen_identity": False, "status_context": None, "trailer_coauthors": [],
            "trailer_session": None}


def _signals(**values: Any) -> dict[str, Any]:
    out = empty_signals()
    out.update(values)
    return out


def _platform(*, login: Optional[str] = None, app: Optional[str] = None,
              committer_login: Optional[str] = None, trailers: tuple[dict[str, str], ...] = (),
              regen: bool = False, author_name: Optional[str] = None) -> str:
    who = (login or "").lower()
    if regen or who in OUR_BOTS or (author_name or "") in BUILDER_BOTS:
        return "github-actions"
    if who == "claude" or any(t["key"] == "Claude-Session" for t in trailers):
        return "claude-code"
    if (who in ("cursoragent", "cursor[bot]")
            or any(t["key"] == "Co-Authored-By" and t["value"].startswith("Cursor") for t in trailers)):
        return "cursor"
    if who == "copilot" or who.startswith("copilot-"):
        return "copilot"
    if who == "coderabbitai[bot]":
        return "coderabbit"
    if who == "vercel[bot]":
        return "vercel"
    if (committer_login or "") == "web-flow":
        return "github-web"
    slug = (app or "").lower()
    if slug == "github-actions":
        return "github-actions"
    if slug == "claude":
        return "claude-code"
    if slug == "cursor":
        return "cursor"
    if slug.startswith("copilot"):
        return "copilot"
    if slug == "coderabbitai":
        return "coderabbit"
    if slug == "vercel":
        return "vercel"
    return "unknown"


def _runtime(platform: str, *, harness: Optional[str] = None, login: Optional[str] = None,
             **joined: Any) -> dict[str, Any]:
    """The pre-serving runtime; ``login`` — the event's author login, for the ``claude[bot]``
    harness rule of the module docstring."""
    out = empty_runtime(platform)
    if harness is None and platform == "claude-code":
        harness = "claude-code"
    if harness is None and (login or "").lower() == CLAUDE_APP_BOT:
        harness = "claude-code-action"
    out["harness"] = harness
    out.update(joined)
    return out


def _login_trust(login: Optional[str]) -> tuple[str, str]:
    return ("login", "login") if login else ("none", "none")


def _agent_trailer(trailers: list[dict[str, str]]) -> bool:
    return any((t["key"] == "Co-Authored-By" and t["value"].startswith(("Claude", "Cursor")))
               or t["key"] == "Claude-Session" for t in trailers)


def _event(*, ident: str, ts: str, kind: str, url: str, signals: dict[str, Any],
           tier: tuple[str, str], runtime: dict[str, Any], fields: dict[str, Any],
           pr: Optional[int] = None, issue: Optional[int] = None,
           sha: Optional[str] = None) -> dict[str, Any]:
    """One event@1, UNPLACED (``episode`` None) — callers place it."""
    return {"after_merge": False, "edges": {"verifies": []}, "episode": None, "fields": fields,
            "head_sha": None, "id": ident, "issue": issue, "kind": kind, "pr": pr,
            "runtime": runtime, "sha": sha, "signals": signals, "stale_sha": False,
            "trust": tier[0], "trust_basis": tier[1], "ts": ts, "ts_precision": "second",
            "tz": "UTC", "url": url}


def _evidence(prefix: str, key: str, raw: dict[str, Any]) -> dict[str, Any]:
    revision = raw.get("revision") or 1
    name = f"{key}.json.gz" if revision == 1 else f"{key}.r{revision}.json.gz"
    return {"raw": f"raw/{prefix}/{name}", "raw_sha256": canonical.content_sha256(raw),
            "receipts": [], "revision": revision, "source": "evidence"}


def _bump(counts: dict[str, int], key: str, by: int = 1) -> None:
    if by:
        counts[key] = counts.get(key, 0) + by


# ---------------------------------------------------------------------------
# Commits.

def _is_builder(commit: dict[str, Any]) -> bool:
    author = ((commit.get("commit") or {}).get("author") or {}).get("name")
    return _login(commit.get("author")) in BUILDER_BOTS or author in BUILDER_BOTS


def _trailers(commit: dict[str, Any]) -> list[dict[str, str]]:
    return list((((commit.get("commit") or {}).get("message") or {}).get("trailers")) or [])


def commit_kind(commit: dict[str, Any], *, first_builder_commit: bool, owner_login: str) -> str:
    """``commit.regen|merge_main|design|human|fix`` for one raw-pr@1 commit.

    ``first_builder_commit`` — this is the PR's first non-regen, non-merge commit; it is the
    ``commit.design`` only when a builder bot authored it (module docstring)."""
    if episodes.is_regen_commit(commit):
        return "commit.regen"
    if len(commit.get("parents") or []) >= 2:
        return "commit.merge_main"
    if first_builder_commit and _is_builder(commit):
        return "commit.design"
    author = _login(commit.get("author"))
    if author and author.lower() == owner_login.lower() and not _agent_trailer(_trailers(commit)):
        return "commit.human"
    return "commit.fix"


def _preview_diff(trailers: list[dict[str, str]]) -> str:
    values = [t["value"] for t in trailers if t["key"] == episodes.REGEN_TRAILER]
    if not values:
        return "absent"
    return values[0] if len(values) == 1 else "multiple"


def _commit_event(commit: dict[str, Any], kind: str, pr: int, ctx: ExtractContext) -> Optional[dict[str, Any]]:
    inner = commit.get("commit") or {}
    author, committer = inner.get("author") or {}, inner.get("committer") or {}
    sha = _sha(commit.get("sha"))
    ts = _ts(author.get("date")) or _ts(committer.get("date"))
    if sha is None or ts is None:
        return None
    trailers = _trailers(commit)
    login, committer_login = _login(commit.get("author")), _login(commit.get("committer"))
    regen = kind == "commit.regen"
    platform = _platform(login=login, committer_login=committer_login, trailers=tuple(trailers),
                         regen=regen, author_name=author.get("name"))
    harness = None
    if author.get("name") == "claude[bot]":
        harness = "claude-code-action"
    elif platform == "cursor":
        harness = "cursor-agent"
    coauthors = [t["value"] for t in trailers if t["key"] == "Co-Authored-By"][:8]
    session = next((t["value"] for t in trailers if t["key"] == "Claude-Session"
                    and _SESSION_RE.fullmatch(t["value"])), None)
    signals = _signals(commit_author_email=_cap(author.get("email"), 200),
                       commit_author_name=_cap(author.get("name"), 120),
                       committer_login=committer_login, login=login,
                       login_type=_login_type(commit.get("author")), regen_identity=regen,
                       trailer_coauthors=coauthors, trailer_session=session)
    parents = len(commit.get("parents") or [])
    if kind == "commit.regen":
        fields: dict[str, Any] = {"preview_diff": _preview_diff(trailers)}
    elif kind == "commit.merge_main":
        fields = {"parents": parents}
    else:
        fields = {"parents": parents, "signature_verified": bool(inner.get("verified"))}
    tier = ("claimed", "trailer") if _agent_trailer(trailers) else _login_trust(login)
    return _event(ident=f"commit:{sha}", ts=ts, kind=kind, url=url_for(ctx, "pr_commit", number=pr, sha=sha),
                  signals=signals, tier=tier, runtime=_runtime(platform, harness=harness),
                  fields=fields, pr=pr, sha=sha)


def merge_method(git: GitReader, merge_sha: Optional[str], pr: int) -> Optional[str]:
    """``merge`` (2 parents) | ``squash`` (1 parent, subject ends ``(#pr)``) | ``rebase`` | ``None``."""
    if not _sha(merge_sha) or not git.has_commit(merge_sha):
        return None
    if len(git.parents(merge_sha)) >= 2:
        return "merge"
    subject = (git.subject(merge_sha) or "").strip()
    return "squash" if subject.endswith(f"(#{pr})") else "rebase"


# ---------------------------------------------------------------------------
# Comments.

def _marker_valid(m: markers.Marker) -> bool:
    if m.family in SIGNOFF_FAMILIES:
        return markers.parse_signoff(m) is not None
    if m.family == "PM_TRIAGE":
        return markers.parse_pm_triage(m) is not None
    if m.family in ("PM_TRIAGE_DONE", "COACH_DONE"):
        return markers.completion_sha(m) is not None
    return m.family in EVENT_FAMILIES


def _parsed(lines: list[str]) -> list[markers.Marker]:
    return [m for m in (markers.parse_marker(line) for line in lines) if m is not None]


def _select_marker(dg: dict[str, Any]) -> Optional[markers.Marker]:
    """The marker a comment's event is built from (module docstring)."""
    suffix = _parsed(dg.get("suffix_markers") or [])
    if suffix and suffix[-1].family in COMPLETION_FAMILIES and _marker_valid(suffix[-1]):
        return suffix[-1]
    for m in reversed(_parsed(dg.get("marker_lines") or [])):
        if m.family in EVENT_FAMILIES and _marker_valid(m):
            return m
    return None


def _counts(table_verdicts: list[str]) -> dict[str, int]:
    tally = {"act-now": 0, "decline": 0, "no-action": 0, "queue": 0}
    for row in table_verdicts:
        for token in row.split("+"):
            if token in tally:
                tally[token] += 1
    return {"act_now": tally["act-now"], "decline": tally["decline"],
            "no_action": tally["no-action"], "queue": tally["queue"], "rows": len(table_verdicts)}


def _bot_noise_key(login: str, app: Optional[str]) -> str:
    who, slug = login.lower(), (app or "").lower()
    for needle, key in (("coderabbit", "coderabbit"), ("cursor", "cursor"), ("qodo", "qodo"),
                        ("vercel", "vercel"), ("entelligence", "entelligence"), ("copilot", "copilot")):
        if needle in who or needle in slug:
            return f"comment.bot.{key}"
    return "comment.bot.other"


def _is_bot(user: Any) -> bool:
    login = _login(user) or ""
    kind = user.get("type") if isinstance(user, dict) else None
    return kind == "Bot" or login.endswith("[bot]")


def _comment_noise(comment: dict[str, Any]) -> str:
    dg = comment["body"]
    if dg.get("lead") in NOISE_LEADS:
        return f"comment.{dg['lead']}"
    for m in _parsed(dg.get("marker_lines") or []):
        if m.family in markers.STICKY_FAMILIES:
            return markers.STICKY_FAMILIES[m.family]
    user = comment.get("user")
    login = _login(user)
    if login and login not in OUR_BOTS and _is_bot(user):
        return _bot_noise_key(login, comment.get("app"))
    return "comment.unclassified"


def _count_unknown(counts: dict[str, int], unknown: dict[str, int], author: Optional[str],
                   owner_login: str, lines: list[str]) -> None:
    for family in markers.unknown_families(author, owner_login, list(lines)):
        _bump(counts, "marker.unknown")
        _bump(unknown, family)


def _comment_event(comment: dict[str, Any], pr: int, ctx: ExtractContext) -> Optional[dict[str, Any]]:
    """review.signoff | triage.verdict | coach.lock | coach.round | oracle.review from an issue
    comment, or None."""
    return _marker_event(comment, pr, ctx, source="issuecomment")


def _review_event(review: dict[str, Any], pr: int, ctx: ExtractContext) -> Optional[dict[str, Any]]:
    """The same kinds from a PR review body (``review:<id>``, ts ``submitted_at``; a pending review
    with no ``submitted_at`` yields nothing), trust capped at :data:`REVIEW_TIER_CAP`."""
    return _marker_event(review, pr, ctx, source="review")


def _marker_event(item: dict[str, Any], pr: int, ctx: ExtractContext, *,
                  source: str) -> Optional[dict[str, Any]]:
    """One event from a body that carries an event marker or an event lead (module docstring);
    ``source`` is ``issuecomment`` (an issue comment) or ``review`` (a PR review body: no ``app``,
    no ``updated_at`` — a review is never edited — and never ``verified``)."""
    dg = item["body"]
    if source == "review":
        created_raw, updated_raw, app = item.get("submitted_at"), None, None
    else:
        created_raw, updated_raw, app = item.get("created_at"), item.get("updated_at"), _app(item.get("app"))
    ident, created = item.get("id"), _ts(created_raw)
    if not isinstance(ident, int) or isinstance(ident, bool) or ident < 1 or created is None:
        return None
    user = item.get("user")
    login = _login(user)
    edited = _edited(created_raw, updated_raw, ctx.edit_grace_seconds)
    marker = _select_marker(dg)
    all_lines = _parsed(list(dg.get("marker_lines") or []) + list(dg.get("suffix_markers") or []))
    sha: Optional[str] = None
    family: Optional[str] = None
    if marker is not None and marker.family in SIGNOFF_FAMILIES:
        so = markers.parse_signoff(marker)
        kind, sha, family = "review.signoff", so["sha"], so["family"]
        fields: dict[str, Any] = {"edited": edited, "family": so["family"], "fuse": so["fuse"],
                                  "verdict": so["verdict"]}
    elif marker is not None and marker.family in ("PM_TRIAGE", "PM_TRIAGE_DONE"):
        triage = next((markers.parse_pm_triage(m) for m in reversed(_parsed(dg.get("marker_lines") or []))
                       if m.family == "PM_TRIAGE" and markers.parse_pm_triage(m)), None)
        done = any(m.family == "PM_TRIAGE_DONE" and markers.completion_sha(m) for m in all_lines)
        kind = "triage.verdict"
        sha = triage["sha"] if triage else markers.completion_sha(marker)
        family = "PM_TRIAGE" if triage else "PM_TRIAGE_DONE"
        fields = dict(_counts(list(dg.get("table_verdicts") or [])), completion_marker=done,
                      designs=triage["designs"] if triage else [], edited=edited)
    elif (marker is not None and marker.family in ("COACH_LOCK", "COACH_DONE")) or (
            marker is None and dg.get("lead") == "coach_lock"):
        completion = next((markers.completion_sha(m) for m in reversed(all_lines)
                           if m.family == "COACH_DONE" and markers.completion_sha(m)), None)
        kind, sha = "coach.lock", completion
        family = None if marker is None else (
            "COACH_LOCK" if any(m.family == "COACH_LOCK" for m in all_lines) else "COACH_DONE")
        fields = {"completion_sha": completion, "edited": edited}
    elif marker is not None and marker.family == "ORACLE_REVIEW":
        kind, family = "oracle.review", "ORACLE_REVIEW"
        fields = {"edited": edited}
    elif marker is None and dg.get("lead") == "coach_round":
        lead_fields = dg.get("lead_fields") or {}
        kind = "coach.round"
        fields = {"round": lead_fields.get("round"), "sub": lead_fields.get("round_sub")}
    else:
        return None
    if family is not None:
        tier = trust.comment_tier(kind=kind, login=login, owner_login=ctx.owner_login, digest=dg,
                                  created_at=created_raw, updated_at=updated_raw,
                                  edit_grace_seconds=ctx.edit_grace_seconds, marker_sha=sha)
        if source == "review" and tier[0] == "verified":
            tier = REVIEW_TIER_CAP
    else:
        tier = ("claimed", "marker:edited") if edited and login else _login_trust(login)
    signals = _signals(app=app, login=login, login_type=_login_type(user), marker=family)
    if source == "review":
        url = url_for(ctx, "review", number=pr, review=ident)
    else:
        url = url_for(ctx, "pull", number=pr, comment=ident)
    return _event(ident=f"{source}:{ident}", ts=created, kind=kind, url=url, signals=signals, tier=tier,
                  runtime=_runtime(_platform(login=login, app=app), login=login), fields=fields,
                  pr=pr, sha=sha)


# ---------------------------------------------------------------------------
# Statuses, runs, deployments.

_REASONS = (("fuse warn", "fuse-acknowledged"), ("signed off on this design", "signed-off"),
            ("overridden", "overridden"), ("has not signed off", "not-signed"),
            ("is stale", "stale"), ("blocked (verdict", "blocked"),
            ("has not acknowledged", "fuse-unacknowledged"))


def signoff_reason(description: Optional[str]) -> str:
    """The ``status.reviewer_signoff`` reason for a status description (scripts/reviewer-signoff.sh
    ``decide`` sentences, PASS/BLOCK stripped; a multi-reviewer BLOCK reads its first clause)."""
    first = (description or "").split(";", 1)[0].strip().lower()
    if first.startswith("jane and drik signed off and acknowledged"):
        return "fuse-acknowledged"
    for needle, reason in _REASONS:
        if needle in first:
            return reason
    return "other"


def _status_verdict(state: str) -> str:
    return {"success": "PASS", "pending": "PENDING"}.get(state, "BLOCK")


def _run_id_of(target_url: Any, ctx: ExtractContext) -> Optional[int]:
    if not isinstance(target_url, str):
        return None
    m = re.fullmatch(rf"https://github\.com/{re.escape(ctx.owner)}/{re.escape(ctx.repo)}/actions/runs/([0-9]{{1,20}})(/.*)?",
                     target_url)
    return int(m.group(1)) if m else None


def _status_noise(status: dict[str, Any]) -> str:
    context, creator = (status.get("context") or ""), (status.get("creator") or "")
    if context == "CodeRabbit" or creator == "coderabbitai[bot]":
        return "status.coderabbit"
    if context.startswith("Vercel") or creator == "vercel[bot]":
        return "status.vercel"
    return "status.other"


def _status_event(status: dict[str, Any], sha: str, pr: int, ctx: ExtractContext) -> Optional[dict[str, Any]]:
    ident, ts, state = status.get("id"), _ts(status.get("created_at")), status.get("state")
    if not isinstance(ident, int) or ident < 1 or ts is None or state not in STATUS_STATES or not _sha(sha):
        return None
    creator = _login(status.get("creator"))
    tier = trust.status_tier(status, set(ctx.auto_review_run_ids), owner_login=ctx.owner_login)
    joined: dict[str, Any] = {}
    run_id = _run_id_of(status.get("target_url"), ctx)
    # The runtime join is the trust rule's own conclusion: only a status the rule verified as an
    # Actions-bot status on an auto-review receipt run names that run. An owner-token (or any
    # other writer's) status pointing at the same run gets no runtime, so trust and runtime
    # can never disagree.
    if tier == STATUS_RECEIPT_TIER and run_id is not None and run_id in ctx.auto_review_run_ids:
        joined = {"run_id": run_id, "workflow": "auto-review.yml"}
    return _event(ident=f"status:{ident}", ts=ts, kind="status.reviewer_signoff",
                  url=url_for(ctx, "pr_commit", number=pr, sha=sha),
                  signals=_signals(login=creator, login_type=_login_type(creator),
                                   status_context="reviewer-signoff"),
                  tier=tier, runtime=_runtime(_platform(login=creator), **joined),
                  fields={"reason": signoff_reason(status.get("description")), "state": state,
                          "verdict": _status_verdict(state)},
                  pr=pr, sha=sha)


def _ci_event(run: dict[str, Any], pr: int, ctx: ExtractContext) -> Optional[dict[str, Any]]:
    ident, ts = run.get("id"), _ts(run.get("created_at"))
    if not isinstance(ident, int) or ident < 1 or ts is None:
        return None
    actor = _login(run.get("actor"))
    workflow_match = _WORKFLOW_PATH_RE.fullmatch(run.get("path") or "")
    attempt = run.get("run_attempt")
    joined = {"attempt": attempt if isinstance(attempt, int) and attempt >= 1 else None,
              "run_id": ident, "workflow": workflow_match.group(1) if workflow_match else None}
    conclusion = run.get("conclusion")
    return _event(ident=f"run:{ident}", ts=ts, kind="ci.gate", url=url_for(ctx, "run", run=ident),
                  signals=_signals(login=actor, login_type=_login_type(actor)),
                  tier=("verified", "receipt"), runtime=_runtime("github-actions", **joined),
                  fields={"conclusion": conclusion if conclusion in CONCLUSIONS else None,
                          "event": _cap(run.get("event"), 40) or "unknown"},
                  pr=pr, sha=_sha(run.get("head_sha")))


def _deploy_state(statuses: list[dict[str, Any]]) -> Optional[str]:
    ordered = sorted(statuses, key=lambda s: s.get("id") or 0)
    terminal = next((s["state"] for s in ordered if s.get("state") in DEPLOY_TERMINAL), None)
    state = terminal or (ordered[-1].get("state") if ordered else None)
    return state if state in DEPLOY_STATES else None


def _deploy_event(dep: dict[str, Any], pr: int, ctx: ExtractContext) -> Optional[dict[str, Any]]:
    ident, ts, sha = dep.get("id"), _ts(dep.get("created_at")), _sha(dep.get("sha"))
    if not isinstance(ident, int) or ident < 1 or ts is None:
        return None
    creator = _login(dep.get("creator"))
    url = url_for(ctx, "commit", sha=sha) if sha else url_for(ctx, "pull", number=pr)
    return _event(ident=f"deployment:{ident}", ts=ts, kind="deploy.production", url=url,
                  signals=_signals(login=creator, login_type=_login_type(creator)),
                  tier=_login_trust(creator), runtime=_runtime(_platform(login=creator)),
                  fields={"deployment_id": ident, "state": _deploy_state(dep.get("statuses") or [])},
                  pr=pr, sha=sha)


# ---------------------------------------------------------------------------
# Records.

def _place(events: list[dict[str, Any]], rounds_: list[Any], *, pr: Optional[int],
           merged_at: Optional[str]) -> list[dict[str, Any]]:
    for event in events:
        episodes.apply_placement(event, episodes.assign(event, rounds_, pr=pr, merged_at=merged_at))
    return sorted(events, key=canonical.event_sort_key)


def _opened_as_draft(pull: dict[str, Any], timeline: list[dict[str, Any]]) -> bool:
    first = next((e["event"] for e in timeline if e.get("event") in ("ready_for_review", "convert_to_draft")), None)
    if first is not None:
        return first == "ready_for_review"
    return bool(pull.get("draft"))


def extract_pr(raw_pr: dict[str, Any], ctx: ExtractContext) -> dict[str, Any]:
    """record@1:pr (events placed by ``episodes``; runtime ``none`` until serving)."""
    n = raw_pr["pr"]
    pull = raw_pr.get("pull") or {}
    timeline = raw_pr.get("timeline") or []
    merged_at = _ts(pull.get("merged_at")) if pull.get("merged") or pull.get("merged_at") else None
    merge_sha = _sha(pull.get("merge_commit_sha")) if merged_at else None
    noise: dict[str, int] = {}
    unknown_markers: dict[str, int] = {}
    events: list[dict[str, Any]] = []
    author = _login(pull.get("user"))

    events.append(_event(ident=f"pr:{n}:opened", ts=_ts(pull.get("created_at")), kind="pr.opened",
                         url=url_for(ctx, "pull", number=n),
                         signals=_signals(login=author, login_type=_login_type(pull.get("user"))),
                         tier=_login_trust(author), runtime=_runtime(_platform(login=author)),
                         fields={"draft": _opened_as_draft(pull, timeline)}, pr=n))
    for item in timeline:
        kind = item.get("event")
        if kind == "ready_for_review" and isinstance(item.get("id"), int) and _ts(item.get("created_at")):
            actor = _login(item.get("actor"))
            events.append(_event(ident=f"timeline:{item['id']}", ts=_ts(item["created_at"]),
                                 kind="pr.ready_for_review", url=url_for(ctx, "pull", number=n),
                                 signals=_signals(app=_app(item.get("app")), login=actor,
                                                  login_type=_login_type(item.get("actor"))),
                                 tier=_login_trust(actor),
                                 runtime=_runtime(_platform(login=actor, app=_app(item.get("app")))),
                                 fields={}, pr=n))
        elif kind == "deployed":
            _bump(noise, "timeline.deployed")
        else:
            _bump(noise, "timeline.other")
    if merged_at:
        merger = _login(pull.get("merged_by"))
        subject = ctx.git.subject(merge_sha) if merge_sha else None
        events.append(_event(ident=f"pr:{n}:merged", ts=merged_at, kind="pr.merged",
                             url=url_for(ctx, "pull", number=n),
                             signals=_signals(login=merger, login_type=_login_type(pull.get("merged_by"))),
                             tier=_login_trust(merger), runtime=_runtime(_platform(login=merger)),
                             fields={"main_subject": _cap(subject, 300),
                                     "merge_method": merge_method(ctx.git, merge_sha, n),
                                     "merged_by_login": merger},
                             pr=n, sha=merge_sha))
    elif _ts(pull.get("closed_at")):
        closer_item = next((e for e in reversed(timeline) if e.get("event") == "closed"), None)
        closer = _login((closer_item or {}).get("actor"))
        events.append(_event(ident=f"pr:{n}:closed", ts=_ts(pull["closed_at"]), kind="pr.closed",
                             url=url_for(ctx, "pull", number=n),
                             signals=_signals(login=closer, login_type=_login_type((closer_item or {}).get("actor"))),
                             tier=_login_trust(closer), runtime=_runtime(_platform(login=closer)),
                             fields={}, pr=n))

    commits = raw_pr.get("commits") or []
    first = next((c for c in commits if not episodes.is_regen_commit(c) and len(c.get("parents") or []) < 2), None)
    for commit in commits:
        kind = commit_kind(commit, first_builder_commit=commit is first, owner_login=ctx.owner_login)
        event = _commit_event(commit, kind, n, ctx)
        if event is not None:
            events.append(event)

    _count_unknown(noise, unknown_markers, author, ctx.owner_login, (pull.get("body") or {}).get("marker_lines") or [])
    for comment in raw_pr.get("issue_comments") or []:
        _count_unknown(noise, unknown_markers, _login(comment.get("user")), ctx.owner_login,
                       comment["body"].get("marker_lines") or [])
        event = _comment_event(comment, n, ctx)
        if event is not None:
            events.append(event)
        else:
            _bump(noise, _comment_noise(comment))
    for review in raw_pr.get("reviews") or []:
        _count_unknown(noise, unknown_markers, _login(review.get("user")), ctx.owner_login,
                       review["body"].get("marker_lines") or [])
        event = _review_event(review, n, ctx)
        if event is not None:
            events.append(event)
        elif review["body"].get("length") == 0:
            _bump(noise, "review.empty_wrapper")
        elif _is_bot(review.get("user")):
            _bump(noise, "review.bot")
        else:
            _bump(noise, "review.human")
    for comment in raw_pr.get("review_comments") or []:
        _bump(noise, "review_comment.bot" if _is_bot(comment.get("user")) else "review_comment.human")
    for sha in sorted(raw_pr.get("statuses") or {}):
        for status in raw_pr["statuses"][sha]:
            if status.get("context") != "reviewer-signoff":
                _bump(noise, _status_noise(status))
            elif "no design changes" in (status.get("description") or "").lower():
                _bump(noise, "status.reviewer_signoff.no_design_changes")
            else:
                event = _status_event(status, sha, n, ctx)
                if event is not None:
                    events.append(event)
    for run in raw_pr.get("ci_runs") or []:
        event = _ci_event(run, n, ctx)
        if event is not None:
            events.append(event)
    if merged_at:
        for dep in raw_pr.get("deployments") or []:
            if dep.get("environment") == "Production":
                event = _deploy_event(dep, n, ctx)
                if event is not None:
                    events.append(event)

    rounds_ = episodes.rounds(raw_pr)
    events = _place(events, rounds_, pr=n, merged_at=merged_at)
    edges = episodes.verifies_edges(events, raw_pr)
    for event in events:
        if event["id"] in edges:
            event["edges"] = {"verifies": edges[event["id"]]}

    incomplete = set(raw_pr.get("incomplete") or [])
    if "commits-truncated" not in incomplete and any(not p.commits for p in episodes.pushes(raw_pr)):
        incomplete.add("force-pushed-heads")
    threads = raw_pr.get("threads") or {}
    thread_counts = None
    if threads and not incomplete & {"threads-unavailable", "graphql-unavailable"}:
        thread_counts = {"resolved": sum(1 for t in threads.get("nodes") or [] if t.get("resolved")),
                         "total": threads.get("total") or 0}
    paths = sorted({p for f in raw_pr.get("files") or []
                    for p in (f.get("filename"), f.get("previous_filename")) if p})
    linked = sorted(set(raw_pr.get("linked_issues") or []))
    head, base = pull.get("head") or {}, pull.get("base") or {}
    return {
        "base_ref": _cap(base.get("ref"), 255),
        "briefs": [b for b in linked if b in ctx.brief_numbers],
        "closed_at": _ts(pull.get("closed_at")),
        "created_at": _ts(pull.get("created_at")),
        "designs": membership.classify_pr(paths, title=pull.get("title") or "", merged=bool(merged_at)),
        "events": events,
        "evidence": _evidence("pr", str(n), raw_pr),
        "extractor": EXTRACTOR_VERSION,
        "format": RECORD_FORMAT,
        "head_ref": _cap(head.get("ref"), 255),
        "incomplete": sorted(incomplete),
        "key": str(n),
        "kind": "pr",
        "linked_issues": linked,
        "merge_commit_sha": merge_sha,
        "merge_method": merge_method(ctx.git, merge_sha, n) if merge_sha else None,
        "merged_at": merged_at,
        "noise_counts": {k: noise[k] for k in sorted(noise) if noise[k] > 0},
        "pr": n,
        "rounds": [episodes.round_dict(r) for r in rounds_],
        "state": "merged" if merged_at else "closed",
        "threads": thread_counts,
        "unknown": {"markers": dict(sorted(unknown_markers.items())), "steps": {}},
    }


def _closed_by_pr(closed: dict[str, Any], timeline: list[dict[str, Any]], merge_shas: dict[str, int]) -> Optional[int]:
    commit = closed.get("commit_id")
    if commit in merge_shas:
        return merge_shas[commit]
    at = _ts(closed.get("created_at"))
    if at is None:
        return None
    hit = None
    for item in timeline:
        ref_at = _ts(item.get("created_at"))
        if (item.get("event") == "referenced" and item.get("commit_id") in merge_shas and ref_at
                and 0 <= _epoch(at) - _epoch(ref_at) <= CLOSE_REFERENCE_SECONDS):
            hit = merge_shas[item["commit_id"]]
    return hit


def _slug(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and _DESIGN_RE.fullmatch(value) else None


def extract_brief(raw_brief: dict[str, Any], ctx: ExtractContext) -> dict[str, Any]:
    """record@1:brief."""
    n = raw_brief["number"]
    issue = raw_brief.get("issue") or {}
    comments = raw_brief.get("comments") or []
    timeline = raw_brief.get("timeline") or []
    claims = [c for c in comments if c["body"].get("lead") == "ship_lock"]
    design_name = next((_slug(c["body"]["lead_fields"].get("design_name")) for c in reversed(claims)
                        if _slug((c["body"].get("lead_fields") or {}).get("design_name"))), None)
    if design_name is None:
        m = _TITLE_SLUG_RE.match(issue.get("title") or "")
        design_name = m.group(1) if m else None
    events: list[dict[str, Any]] = []
    filer = _login(issue.get("user"))
    app = _app(issue.get("app"))
    tier = ("claimed", "marker:edited") if issue.get("last_edited_at") else _login_trust(filer)
    events.append(_event(ident=f"issue:{n}:filed", ts=_ts(issue.get("created_at")), kind="brief.filed",
                         url=url_for(ctx, "issue", number=n),
                         signals=_signals(app=app, login=filer, login_type=_login_type(issue.get("user"))),
                         tier=tier, runtime=_runtime(_platform(login=filer, app=app)),
                         fields={"design_name": None}, issue=n))
    prs: set[int] = set()
    for comment in comments:
        kind = BRIEF_LEAD_KINDS.get(comment["body"].get("lead"))
        ident, created = comment.get("id"), _ts(comment.get("created_at"))
        if kind is None or not isinstance(ident, int) or ident < 1 or created is None:
            continue
        lead_fields = comment["body"].get("lead_fields") or {}
        fields: dict[str, Any] = {"design_name": _slug(lead_fields.get("design_name"))}
        pr = None
        if kind == "brief.shipped":
            shipped = lead_fields.get("shipped_pr")
            pr = shipped if isinstance(shipped, int) and not isinstance(shipped, bool) and shipped >= 1 else None
            fields["shipped_pr"] = pr
            if pr:
                prs.add(pr)
        login, comment_app = _login(comment.get("user")), _app(comment.get("app"))
        edited = _edited(comment.get("created_at"), comment.get("updated_at"), ctx.edit_grace_seconds)
        events.append(_event(ident=f"issuecomment:{ident}", ts=created, kind=kind,
                             url=url_for(ctx, "issuecomment", number=n, comment=ident),
                             signals=_signals(app=comment_app, login=login,
                                              login_type=_login_type(comment.get("user"))),
                             tier=("claimed", "marker:edited") if edited and login else _login_trust(login),
                             runtime=_runtime(_platform(login=login, app=comment_app), login=login),
                             fields=fields, issue=n, pr=pr))
    closes = [e for e in timeline if e.get("event") == "closed" and isinstance(e.get("id"), int)
              and _ts(e.get("created_at"))]
    for i, item in enumerate(closes):
        closed_by = _closed_by_pr(item, timeline, ctx.merge_shas)
        if closed_by:
            prs.add(closed_by)
        reason = item.get("state_reason") if item.get("state_reason") in STATE_REASONS else None
        if reason is None and i == len(closes) - 1 and issue.get("state") == "closed":
            reason = issue.get("state_reason") if issue.get("state_reason") in STATE_REASONS else None
        actor = _login(item.get("actor"))
        events.append(_event(ident=f"timeline:{item['id']}", ts=_ts(item["created_at"]), kind="brief.closed",
                             url=url_for(ctx, "issue", number=n),
                             signals=_signals(app=_app(item.get("app")), login=actor,
                                              login_type=_login_type(item.get("actor"))),
                             tier=_login_trust(actor),
                             runtime=_runtime(_platform(login=actor, app=_app(item.get("app")))),
                             fields={"closed_by_pr": closed_by, "design_name": design_name,
                                     "state_reason": reason},
                             issue=n, pr=closed_by))
    state_reason = issue.get("state_reason")
    return {
        "closed_at": _ts(issue.get("closed_at")),
        "created_at": _ts(issue.get("created_at")),
        "design_name": design_name,
        "events": _place(events, [], pr=None, merged_at=None),
        "evidence": _evidence("brief", str(n), raw_brief),
        "extractor": EXTRACTOR_VERSION,
        "format": RECORD_FORMAT,
        "incomplete": sorted(set(raw_brief.get("incomplete") or [])),
        "issue": n,
        "key": str(n),
        "kind": "brief",
        "labels": sorted({lbl for lbl in issue.get("labels") or [] if isinstance(lbl, str) and len(lbl) <= 100}),
        "prs": sorted(prs),
        "state": "closed" if issue.get("state") == "closed" else "open",
        "state_reason": state_reason if state_reason in STATE_REASONS else None,
    }


def _release_designs(assets: list[dict[str, Any]], names: frozenset[str]) -> list[str]:
    found = set()
    for asset in assets:
        name = asset.get("name") or ""
        hits = [d for d in names if name.startswith(d + "-") or name.startswith(d + ".")]
        if hits:
            found.add(max(hits, key=len))
    return sorted(found)


def extract_release(raw_release: dict[str, Any], ctx: ExtractContext) -> dict[str, Any]:
    """record@1:release."""
    release = raw_release.get("release") or {}
    tag = raw_release["tag"]
    published = _ts(release.get("published_at"))
    ts = published or _ts(release.get("created_at"))
    assets = release.get("assets") or []
    author = _login(release.get("author"))
    events = []
    if isinstance(release.get("id"), int) and ts:
        events.append(_event(ident=f"release:{release['id']}", ts=ts, kind="release",
                             url=url_for(ctx, "release", tag=tag),
                             signals=_signals(login=author, login_type=_login_type(release.get("author"))),
                             tier=_login_trust(author), runtime=_runtime(_platform(login=author)),
                             fields={"assets": len(assets), "prerelease": bool(release.get("prerelease")),
                                     "tag": tag}))
    return {
        "designs": _release_designs(assets, ctx.design_names),
        "events": _place(events, [], pr=None, merged_at=None),
        "evidence": _evidence("release", tag, raw_release),
        "extractor": EXTRACTOR_VERSION,
        "format": RECORD_FORMAT,
        "incomplete": [],
        "key": tag,
        "kind": "release",
        "published_at": published,
        "tag": tag,
    }


#: The committer e-mail of every commit GitHub itself creates (squash/merge/rebase merges, web edits).
GITHUB_COMMITTER = "noreply@github.com"


def is_direct_commit(git: GitReader, sha: str, frozen_pr_commits: set[str]) -> bool:
    """The three-part rule of the module docstring (pure over ``git``); a commit the reader does
    not have is never direct."""
    if not git.has_commit(sha) or sha in frozen_pr_commits:
        return False
    if episodes.subject_pr(git.subject(sha)) is not None:
        return False
    return (git.committer_email(sha) or "").strip().lower() != GITHUB_COMMITTER


def extract_direct_commits(ctx: ExtractContext, frozen_pr_commits: set[str]) -> list[dict[str, Any]]:
    """record@1:commit for each first-parent main commit touching designs/ that
    :func:`is_direct_commit` accepts."""
    records = []
    for sha, epoch in ctx.git.first_parent_log(ctx.main_sha):
        if not is_direct_commit(ctx.git, sha, frozen_pr_commits):
            continue
        paths = ctx.git.changed_paths(sha)
        if not any(p.startswith("designs/") for p in paths):
            continue
        designs = membership.classify_pr(paths, title=ctx.git.subject(sha) or "", merged=True)
        if not designs:
            continue
        committed = ctx.git.committed_epoch(sha)
        ts = _ts_of_epoch(committed if committed is not None else epoch)
        parents = len(ctx.git.parents(sha))
        kind = "commit.merge_main" if parents >= 2 else "commit.human"
        fields: dict[str, Any] = {"parents": parents} if parents >= 2 else {
            "parents": parents, "signature_verified": False}
        event = _event(ident=f"commit:{sha}", ts=ts, kind=kind, url=url_for(ctx, "commit", sha=sha),
                       signals=empty_signals(), tier=("none", "none"), runtime=empty_runtime(),
                       fields=fields, sha=sha)
        records.append({
            "committed_at": ts,
            "designs": designs,
            "events": _place([event], [], pr=None, merged_at=None),
            "evidence": {"raw": None, "raw_sha256": None, "receipts": [], "revision": None,
                         "source": "git"},
            "extractor": EXTRACTOR_VERSION,
            "format": RECORD_FORMAT,
            "incomplete": [],
            "key": sha,
            "kind": "commit",
            "sha": sha,
        })
    return sorted(records, key=lambda r: (r["committed_at"], r["sha"]))
