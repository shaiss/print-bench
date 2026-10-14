"""The serving-model join — which routine, run, chain link and model produced each artifact.

Pure over receipts (``receipt@1``), record@1 events and a
``protocols.CodeBasis``. Nothing is guessed: zero or several candidate
windows give ``model: null`` with basis ``ambiguous``/``none``
(docs/provenance.md §Serving-model join).

**1. Windows** (:class:`ReceiptIndex`). Every agent step that RAN
(``steps.step_ran``) in a full receipt is a :class:`StepWindow` —
``[started_at, completed_at]`` inclusive, second precision — carrying its
run (workflow, event, head_sha, created_at, attempt), job (id, name) and
``steps.AgentStep``. A step with a null timestamp is no window. Of several
receipts of one run (``.a<k>`` paths) the highest attempt is read — its jobs
list holds every attempt (``filter=all``); ``attempt`` is the JOB's
``run_attempt``.

**2. Containment** (:func:`containing_windows`). An artifact at ``ts``
(comment ``created_at``, commit author date, issue ``created_at``) is
contained by a window when ``started <= ts <= completed``, the window's role
is in :data:`KIND_ROLES` for the event (marker family → reviewer role;
brief/commit/PR events → routine roles) and the artifact's author login is
one of that role's posting identities (:data:`ROLE_IDENTITIES`; ``OWNER`` =
``ctx.owner_login``). Exactly one window → attributed; ``0`` → no window
(``none``); ``>= 2`` distinct runs → ``ambiguous`` (overlapping design-run
and backlog-burn windows). Two windows of the SAME job (a boundary second
shared by link k and k+1) resolve to the earlier link only when the artifact
ts is strictly inside it; on the exact boundary → ``ambiguous``. Windows of
two different jobs of one run are ``ambiguous`` too (nothing tells the jobs
apart).

**2b. The owner's token needs a correlating key** (critique item 15). The
ship routines post and open PRs with the OWNER's PAT, so an OWNER-authored
artifact inside a design-run/backlog-burn window may equally be the owner's
own attended work. Such an artifact is attributed only through the issue the
run CLAIMED: :func:`run_claims` maps each ship-routine run to the one issue
``N`` whose OWNER-authored ``brief.claimed`` (SHIP-LOCK) lies in that run's
windows — the selector claims one issue per run, so a run whose windows hold
SHIP-LOCKs on two or more DISTINCT issues claims nothing, while several
SHIP-LOCKs on the one issue are one claim (review round 2, issue 4: brief #281's
locks 5315682248 at 11:54:09Z and 5316408268 at 13:02:28Z both lie in
design-run run 32026482297, whose PR #316 open is then the run's). A ship routine's selector only
claims an issue carrying its opt-in label (:data:`SHIP_ROUTINE_LABELS` —
``.github/design-run.conf`` ``label: design-brief``,
``.github/backlog-burn.conf`` ``label: autonomy-ok``), so a brief's SHIP-LOCK
counts toward a run only when the brief record's ``labels`` hold that run's
routine label. This is what keeps NVC-4: run 34661448637's attempt-2 link 1
(00:34:31–00:38:50) and backlog-burn run 34654859877's attempt-2 link 1
(00:34:36–00:40:48) BOTH contain the #592 SHIP-LOCK at 00:35:31 (the owner
re-ran both at 00:34); #592 carries ``design-brief`` only, so only the
design run claims it and the backlog-burn window fails the key. Then:

* the ``brief.claimed`` itself is attributed iff it is that run's claim;
* an OWNER ``brief.shipped|declined|deferred|withdrawn`` on issue ``N`` iff
  the run claimed ``N``;
* an OWNER ``pr.opened`` / ``commit.*`` iff the PR's ``head_ref`` is
  ``claude/issue-<N>-…`` and the run claimed ``N``;
* otherwise the trust stays ``login`` (an owner PR on any other branch inside
  a design-run window, a run that declined without claiming).

The key filters the candidate windows BEFORE the one/none/ambiguous
decision, so a key that holds for exactly one of two overlapping runs
attributes to that run. Bot-authored artifacts (``github-actions[bot]``,
``claude[bot]``) keep the plain containment rule. #636's head is
``claude/issue-592-nuggs-vent-cap``, so NVC-3/NVC-4 hold under the key.
Claims come from brief records only, so the owner-PAT events of a
backlog-burn run on a non-brief issue stay ``login`` — honest, not guessed.

**2c. A reviewer window must be the record's PR's** (review round 2,
issue 1). Every reviewer session posts as the Actions bot, and auto-review
runs of different PRs overlap all the time (over the #843 snapshot a
window's last 3 s overlaps another PR's window of the same role for 640 of
1,822 Jane, 515 of 1,766 Drik, 275 of 637 PM, 71 of 785 Oracle and 33 of
135 coach windows), so time + role + identity alone would leave a large
share of real sign-offs ``ambiguous`` and — when a PR's own receipt is
missing — attribute one to ANOTHER PR's run. So a window whose role is in
:data:`REVIEWER_ROLES` is a candidate only for a ``pr`` record whose run
it is, by the same rule the job-level events use (§7, :func:`run_belongs`):
the run's ``pull_requests`` holds the PR, or its ``head_branch`` is the
record's ``head_ref`` and the run was created within the PR's
``[created_at, closed_at]``. #636's own auto-review runs carry an empty
``pull_requests`` and match by branch. On any other record kind a reviewer
window is never a candidate (nothing ties it to the record). The filter runs
before the one/none/ambiguous decision, like the §2b key; ship-role windows
keep the §2b key and no PR scope (their artifacts live on brief records).

**3. Code basis** (``CodeBasis.basis_for``): schedule / workflow_dispatch →
``head`` (run.head_sha, exact); auto-review.yml pull_request → ``merge``
(``git merge-tree --write-tree <main@created_at> <run.head_sha>`` — the
design-changes job resolves the chain on the merge ref); oracle.yml
pull_request → ``main`` at the ``actions/checkout`` step's ``started_at``
(the job checks out ``pull_request.base.ref`` BY NAME when that step runs,
which can be long after ``created_at`` on a busy queue — critique item 26;
the step comes from the same receipt job) for the registry, while the
workflow TEXT — the resolve literal, the step's ``--model`` — is the PR
merge commit's, read from ``git merge-tree <main@checkout> <run.head_sha>``
(review round 2, issue 5; codebasis.py, "The oracle's two halves").
``main@T`` = the last first-parent main commit with committer date
``<= T``. ``ambiguous`` when merge-tree conflicts on registry.conf or the
workflow file (merge) / the workflow file (main), or a main commit touching
either lies in ``(created_at − window, created_at]`` (merge) or in
``[started_at − window, completed_at + window]`` of the checkout step (main;
for the workflow file from ``created_at − window``).
A commit the basis needs that is not local after the job-start fetch (a
force-pushed-away head) → basis ``none`` and ``incomplete:
codebasis-unavailable:<sha8>`` — deterministic, never a fetch (critique item
9). Bases are memoized per ``(workflow, kind, main8, head8)``
(``codebasis.py`` says which part).

**4. Chain and model** (:func:`resolve`):

* E3 (chain link) step: the chain id is the workflow's
  ``model_registry resolve <chain>`` literal at the basis
  (:func:`chain_literals`, YAML comment lines skipped); when the workflow has
  several (``oracle.yml``: oracle-anthropic / oracle-glm; ``wright.yml``:
  wright / wright-signoff), :data:`CHAIN_DISCRIMINATORS` picks by
  (workflow, lead, provider) and the pick must be one of the literals, else
  ``ambiguous``. ``model = chain_models(basis, chain)[link - 1]``;
  ``chain_link = link``; ``links_not_served = link - 1`` (rendered "links
  1–(N−1) did not serve", never "failed": the walk keys on ``served`` and a
  link can exit 0 having posted nothing, #762); basis
  ``step-window+registry@head(<sha8>)`` / ``@merge(<main8>+<head8>)`` /
  ``@main(<sha8>)``. ``chain_link``/``links_not_served`` are facts of the step
  name and are kept even when the model cannot be read.
* E0/E1/E2 (pre-#326) step: the model is the step's inline ``--model``
  literal in the workflow text at the basis (:func:`inline_pin`: the step
  block named exactly like the step, inside the job named like the job;
  the first ``--model <id>`` that is not ``${{ … }}``, YAML comments
  skipped); ``chain`` and ``chain_link`` null; basis
  ``provider-step+inline-pin@<sha8>`` (the head for head/merge bases, main
  for a main basis).
* An E1/E2 step with no literal pin whose ``--model`` is a registry chain
  output (review round 2, issue 2 — every E2 auto-review run after the
  registry landed on 08-16, 139 of the 213 local E2 windows, and
  product-scout's E1 ``Run via Z.AI (GLM)``): :func:`registry_pin` traces
  ``${{ needs.<job>.outputs.<out> }}`` to that job's
  ``<out>: ${{ steps.<id>.outputs.link<N>_model }}`` (or reads
  ``${{ steps.<id>.outputs.link<N>_model }}`` in the same job) and the
  ``model_registry resolve <chain>`` literal of step ``<id>``; then exactly
  the E3 rule — ``model = chain[N − 1]``, ``chain_link = N``,
  ``links_not_served = N − 1`` (the E2 steps walk the outputs in order, each
  gated on the earlier ones not succeeding), basis
  ``step-window+registry@…`` / ``job-link+registry@…``.
* The E2 name label is never the model of record, only a cross-check
  (:func:`e2_label_model`): a label that spells a different id than the pin or
  registry output → model null, basis ``ambiguous``.
* A missing workflow file, or a registry that is missing / refused by the
  strict parser / lacks the chain → model null, basis ``none``, counted
  ``codebasis-unavailable:<sha8>`` in ``incomplete``. A failure to MATCH
  (no resolve literal, link beyond the chain, no pin in the step) is basis
  ``none`` without the count.
* A model id outside the contract's ``runtime.model`` pattern
  (:data:`MODEL_RE`, e.g. an OpenRouter ``vendor/model:free`` id) → model
  null, basis ``none`` — the record stays contract-valid.
* Job-level events (``job.reviewer``) use ``steps.last_run_link`` — the
  last non-skipped link — with basis prefix ``job-link+registry@…`` (inline
  pins keep ``provider-step+inline-pin@…``: the contract has no job-level
  form).

**5. Trailers** (:func:`trailer_runtime`): a commit with
``Co-Authored-By: Claude <Name> <noreply@anthropic.com>`` (Name non-empty)
gets ``model = Name`` (e.g. ``Claude Opus 5.5``), basis ``trailer``,
``harness: claude-code``, trust ``claimed``; ``Claude Code`` names the
harness, not a model → ``harness: claude-code``, model null, basis ``none``
(review round 2, issue 3); ``Cursor Agent`` → platform ``cursor``, model
null. A unique window outranks a trailer (a step-window
join is evidence, a trailer a claim); a trailer outranks ``ambiguous``
windows.

**6. Trust upgrade.** An event whose trust is ``login`` or ``claimed``
(not ``marker:owner-token``) whose artifact sits in exactly one compatible
window becomes ``window`` with basis ``window:run <id>`` (``runtime.workflow``/
``job``/``run_id``/``attempt`` W-tagged). ``verified`` events keep their tier
and gain the runtime join. A window-joined event ran inside an Actions job
through claude-code-action, so its ``platform``/``harness`` become
``github-actions``/``claude-code-action``. Ambiguous windows leave the trust
alone and set ``model_basis: ambiguous``.

**7. Receipt events** (:func:`receipt_events`): one ``job.reviewer`` per
reviewer/coach/oracle JOB in the receipts of the PR's head branch
(``run.head_branch == head_ref`` or the run's ``pull_requests`` holds the
PR; a branch-name match only counts for a run created within the PR's
``[created_at, closed_at]``, so a reused branch name cannot import another
PR's runs) whose job has an agent step that ran. ``fields.posted`` = the job
SERVED in ``scripts/reviewer-posted.sh``'s sense: some event of the record is
attributed to that job (``runtime.job_id``) and its ``sha`` is the run's head
sha (or the event carries no sha — coach rounds, the Oracle) — Drik's job in
run 38161046420 posted a sign-off naming the stale ``9a751b26`` (NVC-8)
inside its link-1 window, so it is attributed (NVC-5 counts it) but did not
serve, and links 2–6 ran: ``posted`` false, ``links_tried`` 6.
``links_tried`` = agent steps that ran. Trust ``verified`` / basis
``receipt``; ``signals`` all null (a job has no authoring login). They are
returned UNPLACED (``episode``/``head_sha`` ``None``,
``stale_sha``/``after_merge`` false): ``episodes.place`` assigns them (the
derive order in episodes.py). Acceptance: NVC-2 (remy, 34112970240,
glm-5.2), NVC-3 (9a751b26, glm-4.6, link 3), NVC-5 (12, [glm-5.3]).

**8. Record-level effects of** :func:`annotate_record`. Because
:func:`receipt_events` returns events only, annotate_record also accounts
for the PR's job-level joins: ``incomplete`` gains every
``codebasis-unavailable:<sha8>`` either kind of join met;
``evidence.receipts`` = the receipt paths of every run whose window
attributed an event, plus (PR records) every run that yields a
``job.reviewer`` event; ``unknown.steps`` (PR records) = each suspicious step
name of the PR's own receipts, counted once per receipt. All three are SET
from the inputs (never incremented), so annotating twice changes nothing.

Owner: H4.
"""

from __future__ import annotations

import copy
import functools
import re
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from . import canonical, steps
from .protocols import Basis, CodeBasis
from .steps import AgentStep

#: ``OWNER`` stands for the repository owner's login (ctx.owner_login).
OWNER = "<owner>"

#: role -> logins that role's agent posts or commits as (window attribution
#: requires the artifact's author to be one of them). Reviewer sessions hold
#: only GITHUB_TOKEN (the reviewer MCP posts as the Actions bot); the ship
#: routines run with the owner PAT (SHIP-LOCK and PR open as the owner) and
#: commit through claude-code-action as a bot.
ROLE_IDENTITIES: dict[str, frozenset[str]] = {
    "jane": frozenset({"github-actions[bot]", "github-actions"}),
    "drik": frozenset({"github-actions[bot]", "github-actions"}),
    "pm": frozenset({"github-actions[bot]", "github-actions"}),
    "coach": frozenset({"github-actions[bot]", "github-actions"}),
    "oracle": frozenset({"github-actions[bot]", "github-actions"}),
    "wright": frozenset({"github-actions[bot]", "github-actions"}),
    "reeve-signoff": frozenset({"github-actions[bot]", "github-actions"}),
    "product-scout": frozenset({"github-actions[bot]", "github-actions"}),
    "spike-converter": frozenset({"github-actions[bot]", "github-actions"}),
    "design-run": frozenset({OWNER, "github-actions[bot]", "claude[bot]"}),
    "backlog-burn": frozenset({OWNER, "github-actions[bot]", "claude[bot]"}),
    "chunker": frozenset({OWNER, "github-actions[bot]"}),
    "labeler": frozenset({OWNER, "github-actions[bot]"}),
}

#: event kind (or ``review.signoff:<FAMILY>``) -> roles whose windows may contain it.
KIND_ROLES: dict[str, frozenset[str]] = {
    "review.signoff:JANE_SIGNOFF": frozenset({"jane"}),
    "review.signoff:DRIK_SIGNOFF": frozenset({"drik"}),
    "triage.verdict": frozenset({"pm"}),
    "coach.lock": frozenset({"coach"}),
    "coach.round": frozenset({"coach"}),
    "oracle.review": frozenset({"oracle"}),
    "brief.filed": frozenset({"product-scout", "spike-converter"}),
    "brief.claimed": frozenset({"design-run", "backlog-burn"}),
    "brief.shipped": frozenset({"design-run", "backlog-burn"}),
    "brief.declined": frozenset({"design-run", "backlog-burn"}),
    "brief.deferred": frozenset({"design-run", "backlog-burn"}),
    "brief.withdrawn": frozenset({"design-run", "backlog-burn"}),
    "pr.opened": frozenset({"design-run", "backlog-burn"}),
    "commit.design": frozenset({"design-run", "backlog-burn"}),
    "commit.fix": frozenset({"design-run", "backlog-burn"}),
}

#: (workflow, step lead, provider) -> chain id, for workflows with several resolve literals.
CHAIN_DISCRIMINATORS: dict[tuple[str, str, Optional[str]], str] = {
    ("oracle.yml", "Oracle", "anthropic"): "oracle-anthropic",
    ("oracle.yml", "Oracle", "zai"): "oracle-glm",
    ("wright.yml", "Propose", "zai"): "wright",
    ("wright.yml", "Propose", "anthropic"): "wright",
    ("wright.yml", "Sign off", "zai"): "wright-signoff",
    ("wright.yml", "Sign off", "anthropic"): "wright-signoff",
}

CHAIN_LITERAL_RE = re.compile(r"model_registry resolve ([a-z0-9][a-z0-9-]{0,63})\b")
INLINE_PIN_RE = re.compile(r"--model[ =]([A-Za-z0-9][A-Za-z0-9._-]{0,63})(?![A-Za-z0-9._{-])")

#: The contract's ``runtime.model`` pattern (drift-pinned by tests/test_serving.py).
MODEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}")
SHA40_RE = re.compile(r"[0-9a-f]{40}")
_SLUG_RE = re.compile(r"[A-Za-z0-9-]+")
_REPO_RE = re.compile(r"[A-Za-z0-9._-]+")

#: Roles whose jobs yield ``job.reviewer`` events (§7).
REVIEWER_ROLES = frozenset({"jane", "drik", "pm", "coach", "oracle"})

#: The closed ``fields.conclusion`` vocabulary of ``job.reviewer`` (contract enum).
CONCLUSIONS = frozenset({"success", "failure", "cancelled", "skipped", "neutral", "timed_out",
                         "action_required", "stale", "startup_failure"})

WORKFLOW_DIR = ".github/workflows/"


# ---------------------------------------------------------------------------
# Timestamps.

def ts_epoch(ts: Optional[str]) -> Optional[int]:
    """UTC epoch second of an RFC3339 timestamp (``Z`` or an offset; fractional seconds
    truncated), ``None`` for anything else."""
    if not isinstance(ts, str) or not ts:
        return None
    s = ts.strip()
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() // 1)


def ts_str(epoch: int) -> str:
    """``YYYY-MM-DDTHH:MM:SSZ`` for a UTC epoch second (the contract ``ts`` form)."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def receipt_path_of(receipt: dict[str, Any]) -> Optional[str]:
    """``receipts/YYYY/MM/DD/<run_id>.a<attempt>.json.gz`` — the evidence path of a receipt
    (docs/provenance.md §Receipts: the UTC date of ``run.created_at``, the run's attempt)."""
    run = receipt.get("run") or {}
    rid, epoch = run.get("id"), ts_epoch(run.get("created_at"))
    if not isinstance(rid, int) or epoch is None:
        return None
    day = ts_str(epoch)[:10].split("-")
    return f"receipts/{day[0]}/{day[1]}/{day[2]}/{rid}.a{run.get('run_attempt') or 1}.json.gz"


# ---------------------------------------------------------------------------
# Windows.

@dataclass(frozen=True)
class StepWindow:
    """One agent step that ran, with its run/job context."""

    workflow: str
    run_id: int
    run_event: str
    run_head_sha: Optional[str]
    run_head_branch: Optional[str]
    run_created_at: str
    run_pull_requests: tuple[int, ...]
    attempt: int
    job_id: int
    job_name: str
    step_name: str
    step: AgentStep
    started: str
    completed: str
    #: ``(started_at, completed_at)`` of the job's first ``actions/checkout`` step (oracle basis), or None
    checkout: Optional[tuple[str, str]] = None

    @property
    def role(self) -> Optional[str]:
        return self.step.role(self.workflow)


@dataclass(frozen=True)
class Join:
    """The runtime join for one event (the event's ``runtime`` fields it sets).

    ``unavailable`` — the sha whose code basis could not be read (a commit
    missing after the job-start fetch, or a missing/unparseable registry or
    workflow at the basis); the caller records ``codebasis-unavailable:<sha8>``.
    """

    role: Optional[str]
    workflow: Optional[str]
    job: Optional[str]
    job_id: Optional[int]
    run_id: Optional[int]
    attempt: Optional[int]
    chain: Optional[str]
    chain_link: Optional[int]
    links_not_served: Optional[int]
    provider: Optional[str]
    model: Optional[str]
    model_basis: str
    unavailable: Optional[str] = None

    def runtime_fields(self) -> dict[str, Any]:
        """The ``runtime`` keys this join sets (everything but platform/harness)."""
        return {"role": self.role, "workflow": self.workflow, "job": self.job, "job_id": self.job_id,
                "run_id": self.run_id, "attempt": self.attempt, "chain": self.chain,
                "chain_link": self.chain_link, "links_not_served": self.links_not_served,
                "provider": self.provider, "model": self.model, "model_basis": self.model_basis}


def _checkout_interval(job: dict[str, Any]) -> Optional[tuple[str, str]]:
    for step in job.get("steps") or []:
        if str(step.get("name", "")).startswith("Run actions/checkout"):
            s0, s1 = ts_epoch(step.get("started_at")), ts_epoch(step.get("completed_at"))
            if s0 is None or s1 is None:
                return None
            return ts_str(s0), ts_str(s1)
    return None


def _window(workflow: str, run: dict[str, Any], job: dict[str, Any], step: dict[str, Any],
            parsed: AgentStep, *, require_times: bool = True) -> Optional[StepWindow]:
    s0, s1 = ts_epoch(step.get("started_at")), ts_epoch(step.get("completed_at"))
    if s0 is None or s1 is None or s1 < s0:
        if require_times:
            return None
        s0 = s1 = ts_epoch(job.get("started_at")) or ts_epoch(run.get("created_at")) or 0
    prs = run.get("pull_requests") or []
    return StepWindow(
        workflow=workflow,
        run_id=run["id"],
        run_event=str(run.get("event") or ""),
        run_head_sha=run.get("head_sha"),
        run_head_branch=run.get("head_branch"),
        run_created_at=str(run.get("created_at") or ""),
        run_pull_requests=tuple(sorted({p for p in prs if isinstance(p, int)})),
        attempt=int(job.get("run_attempt") or run.get("run_attempt") or 1),
        job_id=int(job["id"]),
        job_name=str(job.get("name") or ""),
        step_name=str(step.get("name") or ""),
        step=parsed,
        started=ts_str(s0),
        completed=ts_str(s1),
        checkout=_checkout_interval(job),
    )


def _window_key(w: StepWindow) -> tuple:
    return (ts_epoch(w.started), w.run_id, w.job_id, w.step_name)


class ReceiptIndex:
    """Agent-step windows from a set of receipts, queryable by time and role."""

    def __init__(self, receipts: Iterable[dict[str, Any]]) -> None:
        best: dict[int, dict[str, Any]] = {}
        for r in receipts:
            run = r.get("run") or {}
            rid = run.get("id")
            if not isinstance(rid, int):
                continue
            att = run.get("run_attempt") or 1
            cur = best.get(rid)
            if cur is None or att > ((cur.get("run") or {}).get("run_attempt") or 1):
                best[rid] = r
        self._receipts = best
        self._paths = {rid: receipt_path_of(r) for rid, r in best.items()}
        windows: list[StepWindow] = []
        jobs: list[dict[str, Any]] = []
        for rid in sorted(best):
            r = best[rid]
            if r.get("kind") != "full":
                continue
            run, workflow = r["run"], str(r.get("workflow") or "")
            for job in r.get("jobs") or []:
                if not isinstance(job.get("id"), int):
                    continue
                agent = steps.agent_steps(job)
                for step, parsed in agent:
                    if steps.step_ran(step):
                        w = _window(workflow, run, job, step, parsed)
                        if w is not None:
                            windows.append(w)
                if any(p.role(workflow) in REVIEWER_ROLES for _, p in agent):
                    jobs.append({"workflow": workflow, "run": run, "job": job, "path": self._paths[rid]})
        windows.sort(key=_window_key)
        self._windows = windows
        self._starts = [ts_epoch(w.started) for w in windows]
        self._ends = [ts_epoch(w.completed) for w in windows]
        self._max_span = max((e - s for s, e in zip(self._starts, self._ends)), default=0)
        self._jobs = sorted(jobs, key=lambda j: (ts_epoch(j["job"].get("started_at")) or 0,
                                                 j["run"]["id"], j["job"]["id"]))

    def windows(self) -> list[StepWindow]:
        """Every window, sorted (started, run_id, job_id, step name)."""
        return list(self._windows)

    def receipt(self, run_id: int) -> Optional[dict[str, Any]]:
        """The (highest-attempt) receipt of ``run_id``."""
        return self._receipts.get(run_id)

    def path_of(self, run_id: int) -> Optional[str]:
        """The evidence path of ``run_id``'s receipt."""
        return self._paths.get(run_id)

    def at(self, epoch: int) -> list[StepWindow]:
        """Windows with ``started <= epoch <= completed``, in :meth:`windows` order."""
        hi = bisect_right(self._starts, epoch)
        lo = bisect_right(self._starts, epoch - self._max_span - 1)
        return [self._windows[i] for i in range(lo, hi) if self._ends[i] >= epoch]

    def runs_for_pr(self, pr: int, head_ref: Optional[str]) -> list[dict[str, Any]]:
        """Every receipt (full or stub) whose run belongs to the PR, sorted by run id."""
        return [r for rid, r in sorted(self._receipts.items()) if _run_matches(r["run"], pr, head_ref)]

    def jobs_for_pr(self, pr: int, head_ref: Optional[str]) -> list[dict[str, Any]]:
        """Reviewer/coach/oracle jobs (receipt run + job) belonging to one PR.

        ``[{"workflow", "run", "job", "path"}]`` — jobs of full receipts with an
        agent step of a reviewer role (ran or not), whose run's ``head_branch`` is
        ``head_ref`` or whose ``pull_requests`` holds ``pr``; sorted by (job
        ``started_at``, run id, job id). The PR-window bound for branch-only
        matches is applied by the record-aware callers (module docstring §7)."""
        return [j for j in self._jobs if _run_matches(j["run"], pr, head_ref)]


def _run_matches(run: dict[str, Any], pr: int, head_ref: Optional[str]) -> bool:
    if pr in (run.get("pull_requests") or []):
        return True
    return bool(head_ref) and run.get("head_branch") == head_ref


def _in_pr_window(run: dict[str, Any], record: dict[str, Any]) -> bool:
    """A run reached through the PR number always counts; a branch-name-only match counts when
    the run was created within the PR's ``[created_at, closed_at]``."""
    if record.get("pr") in (run.get("pull_requests") or []):
        return True
    t = ts_epoch(run.get("created_at"))
    lo, hi = ts_epoch(record.get("created_at")), ts_epoch(record.get("closed_at"))
    if t is None:
        return False
    return (lo is None or t >= lo) and (hi is None or t <= hi)


def run_belongs(run: dict[str, Any], record: dict[str, Any]) -> bool:
    """The run is one of the ``pr`` record's (§2c, §7): :func:`_run_matches` and
    :func:`_in_pr_window`. ``False`` for any other record kind."""
    pr = record.get("pr")
    if record.get("kind") != "pr" or not isinstance(pr, int):
        return False
    return _run_matches(run, pr, record.get("head_ref")) and _in_pr_window(run, record)


def window_belongs(w: StepWindow, record: dict[str, Any]) -> bool:
    """§2c: a reviewer-role window is a candidate only for the record whose run it is; a window
    of any other role is not PR-scoped (``True``)."""
    if w.role not in REVIEWER_ROLES:
        return True
    return run_belongs({"pull_requests": list(w.run_pull_requests), "head_branch": w.run_head_branch,
                        "created_at": w.run_created_at}, record)


# ---------------------------------------------------------------------------
# Containment.

def _identity_ok(role: str, login: str, owner_login: str) -> bool:
    ident = ROLE_IDENTITIES.get(role, frozenset())
    return login in ident or (OWNER in ident and login == owner_login)


def containing_windows(index: ReceiptIndex, *, ts: str, roles: frozenset[str],
                       author_login: Optional[str], owner_login: str) -> list[StepWindow]:
    """Candidate windows for one artifact (module docstring §2)."""
    t = ts_epoch(ts)
    if t is None or not author_login:
        return []
    return [w for w in index.at(t)
            if w.role in roles and _identity_ok(w.role, author_login, owner_login)]


def pick_window(candidates: list[StepWindow], ts: str) -> tuple[str, Optional[StepWindow]]:
    """``("one", w)`` / ``("none", None)`` / ``("ambiguous", None)`` over :func:`containing_windows`."""
    if not candidates:
        return "none", None
    if len(candidates) == 1:
        return "one", candidates[0]
    if len({(w.run_id, w.job_id) for w in candidates}) == 1:
        t = ts_epoch(ts)
        earliest = min(candidates, key=lambda w: (ts_epoch(w.started), w.step.link or 0, w.step_name))
        if t is not None and ts_epoch(earliest.started) < t < ts_epoch(earliest.completed):
            return "one", earliest
    return "ambiguous", None


# ---------------------------------------------------------------------------
# Workflow text scanners (line scanners, not a YAML parser).

def _drop_comment(line: str) -> str:
    """The line without a YAML comment ('' for a whole-line comment; a trailing ``<space>#…``
    is cut, as YAML does for plain scalars)."""
    if line.lstrip().startswith("#"):
        return ""
    m = re.search(r"\s#", line)
    return line[:m.start()] if m else line


def chain_literals(workflow_text: str) -> list[str]:
    """Distinct ``model_registry resolve <chain>`` literals, in file order."""
    out: list[str] = []
    for line in workflow_text.split("\n"):
        for m in CHAIN_LITERAL_RE.finditer(_drop_comment(line)):
            if m.group(1) not in out:
                out.append(m.group(1))
    return out


_KEY_RE = re.compile(r"^(?P<ind> *)(?P<dash>-\s+)?(?P<key>[A-Za-z0-9_.$-][^:#]*?):(?:\s+(?P<val>.*))?\s*$")
_ITEM_RE = re.compile(r"^(?P<ind> *)-(?:\s+(?P<rest>.*))?$")
_BLOCK_RE = re.compile(r"^[|>][+-]?[0-9]?[+-]?$")


def _scalar(raw: Optional[str]) -> str:
    """A YAML scalar's value: quotes removed, or a plain scalar's trailing comment cut."""
    v = (raw or "").strip()
    if v[:1] in ("'", '"'):
        q = v[0]
        end = v.find(q, 1)
        while q == "'" and end != -1 and v[end + 1:end + 2] == "'":
            end = v.find(q, end + 2)
        inner = v[1:end] if end != -1 else v[1:]
        return inner.replace("''", "'") if q == "'" else inner
    return _drop_comment(v).strip()


def _structure(lines: list[str]) -> list[tuple[int, int, str]]:
    """``[(line index, indent, line)]`` of the structural lines: blank, comment and block-scalar
    content lines are dropped."""
    out, block_col = [], None
    for i, raw in enumerate(lines):
        if not raw.strip():
            continue
        ind = len(raw) - len(raw.lstrip(" "))
        if block_col is not None:
            if ind > block_col:
                continue
            block_col = None
        if raw.lstrip().startswith("#"):
            continue
        out.append((i, ind, raw))
        m = _KEY_RE.match(raw)
        if m and m.group("val") is not None and _BLOCK_RE.match(_drop_comment(m.group("val")).strip()):
            block_col = len(m.group("ind")) + len(m.group("dash") or "")
    return out


def _key(raw: str) -> Optional[tuple[str, Optional[str], bool, int]]:
    """``(key, value, is_item, key column)`` of a ``key: value`` / ``- key: value`` line."""
    m = _KEY_RE.match(raw)
    if not m:
        return None
    return m.group("key").strip(), m.group("val"), bool(m.group("dash")), len(m.group("ind")) + len(m.group("dash") or "")


def _span_end(struct: list[tuple[int, int, str]], k: int, limit: int) -> int:
    """The struct position where the node at ``k`` ends (the next line at its indent or shallower)."""
    ind = struct[k][1]
    return next((j for j in range(k + 1, limit) if struct[j][1] <= ind), limit)


def _children(struct: list[tuple[int, int, str]], k: int, end: int) -> list[int]:
    """Positions of the lines at the first indent below the node at ``k`` (its direct keys)."""
    if k + 1 >= end or struct[k + 1][1] <= struct[k][1]:
        return []
    child = struct[k + 1][1]
    return [j for j in range(k + 1, end) if struct[j][1] == child]


def _child_value(struct: list[tuple[int, int, str]], k: int, end: int, key: str) -> Optional[int]:
    """Position of the non-item child ``key:`` of the node at ``k``, or None."""
    for j in _children(struct, k, end):
        kv = _key(struct[j][2])
        if kv and not kv[2] and kv[0] == key:
            return j
    return None


def _seq_items(struct: list[tuple[int, int, str]], k: int, end: int) -> tuple[list[int], int]:
    """The item positions of the block sequence under the key at ``k`` and where it ends: the
    items sit at the first item's indent (which may equal the key's) until a shallower line or
    a non-item line at that indent."""
    items, s_ind, j = [], None, k + 1
    while j < end:
        ind, raw = struct[j][1], struct[j][2]
        is_item = _ITEM_RE.match(raw) is not None
        if s_ind is None:
            if not is_item or ind < struct[k][1]:
                break
            s_ind = ind
        if ind < s_ind or (ind == s_ind and not is_item):
            break
        if ind == s_ind:
            items.append(j)
        j += 1
    return items, j


def _item_key(struct: list[tuple[int, int, str]], i: int, nxt: int, key: str) -> Optional[str]:
    """The ``key:`` of the sequence item at ``i`` (``- key: X`` or at the item's mapping column)."""
    kv = _key(struct[i][2])
    if kv and kv[2]:
        if kv[0] == key:
            return _scalar(kv[1])
        col: Optional[int] = kv[3]
    else:
        col = struct[i + 1][1] if i + 1 < nxt else None
    for j in range(i + 1, nxt):
        if struct[j][1] != col:
            continue
        ckv = _key(struct[j][2])
        if ckv and not ckv[2] and ckv[0] == key:
            return _scalar(ckv[1])
    return None


def _item_name(struct: list[tuple[int, int, str]], i: int, nxt: int) -> Optional[str]:
    """The ``name:`` of the sequence item at ``i``."""
    return _item_key(struct, i, nxt, "name")


class _Workflow:
    """The structural lines of one workflow text, with the job/step lookups the pin scanners share."""

    def __init__(self, workflow_text: str) -> None:
        self.lines = workflow_text.split("\n")
        self.struct = _structure(self.lines)
        n = len(self.struct)
        jobs_k = next((k for k in range(n) if self.struct[k][1] == 0
                       and (_key(self.struct[k][2]) or ("",))[0] == "jobs"
                       and _key(self.struct[k][2])[1] is None), None)
        #: ``[(key, name or None, struct pos, span end)]`` of every job.
        self.jobs: list[tuple[str, Optional[str], int, int]] = []
        if jobs_k is None:
            return
        jobs_end = _span_end(self.struct, jobs_k, n)
        for k in _children(self.struct, jobs_k, jobs_end):
            kv = _key(self.struct[k][2])
            if not kv or kv[2]:
                continue
            end = _span_end(self.struct, k, jobs_end)
            name_k = _child_value(self.struct, k, end, "name")
            name = _scalar(_key(self.struct[name_k][2])[1]) if name_k is not None else None
            self.jobs.append((kv[0], name, k, end))

    def job_by_name(self, job_name: str) -> Optional[tuple[int, int]]:
        """The one job whose ``name:`` is ``job_name`` (else the one nameless job keyed so)."""
        by_name = [(k, e) for _key_, name, k, e in self.jobs if name == job_name]
        by_key = [(k, e) for key, name, k, e in self.jobs if name is None and key == job_name]
        hits = by_name or by_key
        return hits[0] if len(hits) == 1 else None

    def job_by_key(self, key: str) -> Optional[tuple[int, int]]:
        """The job whose key (its id — what ``needs.<id>`` names) is ``key``."""
        hits = [(k, e) for jkey, _name, k, e in self.jobs if jkey == key]
        return hits[0] if len(hits) == 1 else None

    def _steps(self, job: tuple[int, int]) -> list[tuple[int, int]]:
        """``[(item struct pos, next item struct pos)]`` of the job's ``steps:`` sequence."""
        jk, jend = job
        steps_k = _child_value(self.struct, jk, jend, "steps")
        if steps_k is None:
            return []
        items, seq_end = _seq_items(self.struct, steps_k, jend)
        return [(i, items[x + 1] if x + 1 < len(items) else seq_end) for x, i in enumerate(items)]

    def _line_span(self, i: int, nxt: int) -> tuple[int, int]:
        return self.struct[i][0], (self.struct[nxt][0] if nxt < len(self.struct) else len(self.lines))

    def step_lines(self, job: tuple[int, int], *, name: Optional[str] = None,
                   step_id: Optional[str] = None) -> Optional[list[str]]:
        """The comment-stripped lines of the one step of ``job`` named ``name`` (or whose
        ``id:`` is ``step_id``); ``None`` unless exactly one matches."""
        found = []
        for i, nxt in self._steps(job):
            if name is not None and _item_name(self.struct, i, nxt) == name:
                found.append((i, nxt))
            elif step_id is not None and _item_key(self.struct, i, nxt, "id") == step_id:
                found.append((i, nxt))
        if len(found) != 1:
            return None
        first, last = self._line_span(*found[0])
        return [_drop_comment(line) for line in self.lines[first:last]]

    def job_output(self, job: tuple[int, int], output: str) -> Optional[str]:
        """The scalar value of ``outputs.<output>`` of ``job``."""
        jk, jend = job
        outputs_k = _child_value(self.struct, jk, jend, "outputs")
        if outputs_k is None:
            return None
        out_end = _span_end(self.struct, outputs_k, jend)
        k = _child_value(self.struct, outputs_k, out_end, output)
        return _scalar(_key(self.struct[k][2])[1]) if k is not None else None


@functools.lru_cache(maxsize=64)
def _parse_workflow(workflow_text: str) -> _Workflow:
    """:class:`_Workflow` of one text, memoized (a run of windows reads the same few texts; the
    object is never mutated after construction)."""
    return _Workflow(workflow_text)


def inline_pin(workflow_text: str, job_name: str, step_name: str) -> Optional[str]:
    """The step's literal ``--model`` (pre-#326), found by a line scanner over the workflow
    text: the job whose ``name:`` equals ``job_name``, the step whose ``- name:`` equals
    ``step_name`` exactly once inside it; ``None`` otherwise. Not a YAML parser.

    A job without a ``name:`` is matched by its key (GitHub shows the key then). Comment lines
    and block-scalar contents never shape the structure; the pin is the first
    ``INLINE_PIN_RE`` match in the step block's comment-stripped lines (block scalars
    included — ``claude_args: |`` may carry it)."""
    wf = _parse_workflow(workflow_text)
    job = wf.job_by_name(job_name)
    lines = wf.step_lines(job, name=step_name) if job is not None else None
    for line in lines or []:
        m = INLINE_PIN_RE.search(line)
        if m:
            return m.group(1)
    return None


#: ``--model ${{ <expr> }}`` — a step's model read from an expression.
MODEL_EXPR_RE = re.compile(r"--model[ =]\$\{\{\s*(?P<expr>[^{}]*?)\s*\}\}")
#: ``needs.<job id>.outputs.<output>`` — a model output of another job.
NEEDS_OUTPUT_RE = re.compile(r"needs\.(?P<job>[A-Za-z0-9_-]+)\.outputs\.(?P<out>[A-Za-z0-9_-]+)")
#: ``steps.<id>.outputs.link<N>_model`` — what ``model_registry resolve --gh-output`` emits.
STEP_LINK_RE = re.compile(r"steps\.(?P<id>[A-Za-z0-9_-]+)\.outputs\.link(?P<n>[1-9][0-9]?)_model")


def registry_pin(workflow_text: str, job_name: str, step_name: str) -> Optional[tuple[str, int]]:
    """``(chain, link)`` when the step's ``--model`` is a registry chain output (review round 2,
    issue 2), else ``None``. Not a YAML parser — the same line scanner as :func:`inline_pin`.

    The first ``--model ${{ … }}`` of the step block (comment-stripped) must be either
    ``steps.<id>.outputs.link<N>_model`` (a resolve step of the same job — product-scout's E1
    ``Run via Z.AI (GLM)``) or ``needs.<job>.outputs.<out>`` whose job (by key) declares
    ``<out>: ${{ steps.<id>.outputs.link<N>_model }}`` (auto-review's E2
    ``model<N>`` outputs of ``design-changes``). The step with ``id: <id>`` in that job must
    carry exactly one ``model_registry resolve <chain>`` literal; the link is ``N``. Anything
    else (``vars.X``, an output that is not a link, a missing or duplicated step id, two
    literals) → ``None``."""
    wf = _parse_workflow(workflow_text)
    job = wf.job_by_name(job_name)
    lines = wf.step_lines(job, name=step_name) if job is not None else None
    expr = next((m.group("expr") for line in lines or [] for m in [MODEL_EXPR_RE.search(line)] if m), None)
    if expr is None:
        return None
    target, link_expr = job, expr
    m = NEEDS_OUTPUT_RE.fullmatch(expr)
    if m:
        target = wf.job_by_key(m.group("job"))
        value = wf.job_output(target, m.group("out")) if target is not None else None
        inner = re.fullmatch(r"\$\{\{\s*(?P<expr>[^{}]*?)\s*\}\}", value or "")
        link_expr = inner.group("expr") if inner else ""
    m = STEP_LINK_RE.fullmatch(link_expr)
    if m is None or target is None:
        return None
    resolve_lines = wf.step_lines(target, step_id=m.group("id"))
    if resolve_lines is None:
        return None
    literals = chain_literals("\n".join(resolve_lines))
    if len(literals) != 1:
        return None
    return literals[0], int(m.group("n"))


# ---------------------------------------------------------------------------
# Chain and model.

def _basis_sha(basis: Basis) -> Optional[str]:
    sha = basis.main_sha if basis.kind == "main" else basis.head_sha
    if basis.kind == "merge" and not basis.main_sha:
        return None
    return sha if isinstance(sha, str) and SHA40_RE.fullmatch(sha) else None


def basis_label(basis: Basis, *, job_level: bool) -> str:
    """The ``model_basis`` string for a basis (contract pattern)."""
    if basis.unavailable:
        return "none"
    if basis.ambiguous:
        return "ambiguous"
    prefix = "job-link+registry@" if job_level else "step-window+registry@"
    head = basis.head_sha if isinstance(basis.head_sha, str) and SHA40_RE.fullmatch(basis.head_sha) else None
    main = basis.main_sha if isinstance(basis.main_sha, str) and SHA40_RE.fullmatch(basis.main_sha) else None
    if basis.kind == "head" and head:
        return f"{prefix}head({head[:8]})"
    if basis.kind == "merge" and head and main:
        return f"{prefix}merge({main[:8]}+{head[:8]})"
    if basis.kind == "main" and main:
        return f"{prefix}main({main[:8]})"
    return "none"


def resolve(window: StepWindow, codebasis: CodeBasis, *, job_level: bool = False) -> Join:
    """Chain/model for one window (module docstring §3–4)."""
    step = window.step
    e3 = step.era == "E3" and step.link is not None
    base = {"role": window.role, "workflow": window.workflow, "job": window.job_name,
            "job_id": window.job_id, "run_id": window.run_id, "attempt": window.attempt,
            "provider": step.provider,
            "chain_link": step.link if e3 else None,
            "links_not_served": step.link - 1 if e3 else None}

    def out(chain: Optional[str] = None, model: Optional[str] = None, model_basis: str = "none",
            unavailable: Optional[str] = None) -> Join:
        # No model ⇒ basis ambiguous or none; a model outside the contract pattern is no model.
        if model is None or not MODEL_RE.fullmatch(model):
            model = None
            model_basis = "ambiguous" if model_basis == "ambiguous" else "none"
        return Join(chain=chain, model=model, model_basis=model_basis, unavailable=unavailable, **base)

    basis = codebasis.basis_for(window.workflow, window.run_event, window.run_head_sha,
                                window.run_created_at, checkout=window.checkout)
    if basis.unavailable:
        return out(unavailable=basis.unavailable)
    if basis.ambiguous:
        return out(model_basis="ambiguous")
    sha = _basis_sha(basis)
    if sha is None:
        return out()
    wf = codebasis.file_at(basis, WORKFLOW_DIR + window.workflow)
    if wf is None:
        return out(unavailable=sha)
    text = wf.decode("utf-8", errors="replace")
    if e3:
        literals = chain_literals(text)
        if not literals:
            return out()
        if len(literals) == 1:
            chain = literals[0]
        else:
            pick = CHAIN_DISCRIMINATORS.get((window.workflow, step.lead, step.provider))
            if pick not in literals:
                return out(model_basis="ambiguous")
            chain = pick
        models = codebasis.chain_models(basis, chain)
        if models is None:
            return out(chain=chain, unavailable=sha)
        if step.link > len(models):
            return out(chain=chain)
        return out(chain=chain, model=models[step.link - 1],
                   model_basis=basis_label(basis, job_level=job_level))
    label = e2_label_model(step)
    pin = inline_pin(text, window.job_name, window.step_name)
    if pin is not None:
        if label is not None and label != pin:
            return out(model_basis="ambiguous")
        return out(model=pin, model_basis=f"provider-step+inline-pin@{sha[:8]}")
    reg = registry_pin(text, window.job_name, window.step_name)
    if reg is None:
        return out()
    chain, link = reg
    # The walk's link is a fact of the workflow text now (the step reads chain output N).
    base["chain_link"], base["links_not_served"] = link, link - 1
    models = codebasis.chain_models(basis, chain)
    if models is None:
        return out(chain=chain, unavailable=sha)
    if link > len(models):
        return out(chain=chain)
    if label is not None and label != models[link - 1]:
        return out(chain=chain, model_basis="ambiguous")
    return out(chain=chain, model=models[link - 1], model_basis=basis_label(basis, job_level=job_level))


_E2_ANTHROPIC_LABEL_RE = re.compile(r"(?P<family>Opus|Sonnet|Haiku) (?P<ver>[0-9]+(?:\.[0-9]+)?)")
_E2_GLM_LABEL_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def e2_label_model(step: AgentStep) -> Optional[str]:
    """The model id an E2 step name spells — ``/jane-review via Z.AI GLM 5.2`` → ``glm-5.2``,
    ``/pm triage via Anthropic Opus 4.8`` → ``claude-opus-4-8`` — or ``None`` (not E2, or a label
    outside those two forms). A cross-check only (§4): the model of record is the step's pin or
    registry output, and a label that disagrees with it makes the join ``ambiguous`` (the
    reconstructed basis, or the name, is not what ran). Over the #843 snapshot all 213 E2
    windows whose workflow is local agree (74 inline pins, 139 registry outputs)."""
    if step.era != "E2" or not step.label:
        return None
    if step.provider == "zai" and _E2_GLM_LABEL_RE.fullmatch(step.label):
        return f"glm-{step.label}"
    m = _E2_ANTHROPIC_LABEL_RE.fullmatch(step.label)
    if step.provider == "anthropic" and m:
        return f"claude-{m.group('family').lower()}-{m.group('ver').replace('.', '-')}"
    return None


# ---------------------------------------------------------------------------
# Trailers.

_CLAUDE_COAUTHOR_RE = re.compile(r"Claude(?:\s+(?P<name>[^<>]*?))?\s*<noreply@anthropic\.com>")
_CURSOR_COAUTHOR_RE = re.compile(r"Cursor Agent\s*<[^<>]*>")


#: Co-author names that name the harness, not a model (``Claude Code <noreply@anthropic.com>``:
#: 31 commits, e.g. 0987cd1 on #738 and d9cfda0 on #643 — review round 2, issue 3).
HARNESS_NAMES = frozenset({"Code"})


def trailer_runtime(signals: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Claimed runtime from commit trailers (module docstring §5), or ``None``.

    Reads ``signals.trailer_coauthors`` (the ``Co-Authored-By`` values) and
    returns the ``runtime`` keys the claim sets: a named Claude co-author →
    ``{"harness": "claude-code", "model": "Claude <Name>", "model_basis":
    "trailer"}`` (two different names → model null, basis ``ambiguous``; a
    name outside the contract's model pattern → model null, basis ``none``);
    else ``Claude Code`` (a name in :data:`HARNESS_NAMES` names the harness and
    is never a model) → ``{"harness": "claude-code", "model": None,
    "model_basis": "none"}``; else a ``Cursor Agent`` co-author →
    ``{"platform": "cursor", "harness": "cursor-agent", "model": None,
    "model_basis": "none"}``; else ``None`` (an unnamed ``Claude
    <noreply@anthropic.com>`` names no model)."""
    names, harness, cursor = set(), False, False
    for value in signals.get("trailer_coauthors") or []:
        v = str(value).strip()
        m = _CLAUDE_COAUTHOR_RE.fullmatch(v)
        if m:
            name = (m.group("name") or "").strip()
            if name in HARNESS_NAMES:
                harness = True
            elif name:
                names.add(f"Claude {name}")
        elif _CURSOR_COAUTHOR_RE.fullmatch(v):
            cursor = True
    if names:
        if len(names) > 1:
            return {"harness": "claude-code", "model": None, "model_basis": "ambiguous"}
        model = next(iter(names))
        if not MODEL_RE.fullmatch(model):
            return {"harness": "claude-code", "model": None, "model_basis": "none"}
        return {"harness": "claude-code", "model": model, "model_basis": "trailer"}
    if harness:
        return {"harness": "claude-code", "model": None, "model_basis": "none"}
    if cursor:
        return {"platform": "cursor", "harness": "cursor-agent", "model": None, "model_basis": "none"}
    return None


# ---------------------------------------------------------------------------
# Claims (§2b).

#: The ship routines whose OWNER-authored artifacts need a claimed-issue key (§2b).
SHIP_ROLES = frozenset({"design-run", "backlog-burn"})
CLAIM_BRANCH_RE = re.compile(r"claude/issue-([0-9]{1,7})-")
#: Each ship routine's selector opt-in label (its committed conf's ``label:``).
SHIP_ROUTINE_LABELS = {"design-run": "design-brief", "backlog-burn": "autonomy-ok"}


def run_claims(brief_records: list[dict[str, Any]], index: ReceiptIndex, *,
               owner_login: str) -> dict[int, int]:
    """``{ship-routine run id: claimed issue}`` (§2b): the one issue whose OWNER ``brief.claimed``
    lies inside that run's windows; runs whose windows hold SHIP-LOCKs on zero or on two or more
    DISTINCT issues are absent. Several SHIP-LOCKs on one issue are one claim (review round 2,
    issue 4: design-run run 32026482297 holds #281's locks 5315682248 and 5316408268)."""
    per_run: dict[int, set[int]] = {}
    for rec in brief_records:
        if rec.get("kind") != "brief":
            continue
        labels = set(rec.get("labels") or [])
        for e in rec.get("events") or []:
            if e.get("kind") != "brief.claimed" or (e.get("signals") or {}).get("login") != owner_login:
                continue
            issue = e.get("issue") or rec.get("issue")
            if not isinstance(issue, int):
                continue
            for w in containing_windows(index, ts=e.get("ts"), roles=KIND_ROLES["brief.claimed"],
                                        author_login=owner_login, owner_login=owner_login):
                if SHIP_ROUTINE_LABELS.get(w.role) in labels:
                    per_run.setdefault(w.run_id, set()).add(issue)
    return {rid: next(iter(c)) for rid, c in sorted(per_run.items()) if len(c) == 1}


def _kind_key(event: dict[str, Any]) -> str:
    kind = event.get("kind", "")
    if kind == "review.signoff":
        return f"review.signoff:{(event.get('fields') or {}).get('family')}"
    return kind


def _owner_key_ok(event: dict[str, Any], w: StepWindow, record: dict[str, Any],
                  claims: dict[int, int], owner_login: str) -> bool:
    if w.role not in SHIP_ROLES or (event.get("signals") or {}).get("login") != owner_login:
        return True
    claimed = claims.get(w.run_id)
    if claimed is None:
        return False
    kind = event.get("kind", "")
    if kind.startswith("brief."):
        return (event.get("issue") or record.get("issue")) == claimed
    if kind == "pr.opened" or kind.startswith("commit."):
        m = CLAIM_BRANCH_RE.match(record.get("head_ref") or "")
        return bool(m) and int(m.group(1)) == claimed
    return False


# ---------------------------------------------------------------------------
# The record join.

def _window_runtime(runtime: dict[str, Any], join: Join) -> dict[str, Any]:
    out = dict(runtime)
    out.update(join.runtime_fields())
    out["platform"] = "github-actions"
    out["harness"] = "claude-code-action"
    return out


def _unavailable_tag(sha: Optional[str]) -> Optional[str]:
    if isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{8,40}", sha):
        return f"codebasis-unavailable:{sha[:8]}"
    return None


def _pr_jobs(record: dict[str, Any], index: ReceiptIndex) -> list[dict[str, Any]]:
    """The jobs that yield ``job.reviewer`` events for a PR record (§7)."""
    if record.get("kind") != "pr" or not isinstance(record.get("pr"), int):
        return []
    out = []
    for entry in index.jobs_for_pr(record["pr"], record.get("head_ref")):
        if not run_belongs(entry["run"], record):
            continue
        ran = [(s, p) for s, p in steps.agent_steps(entry["job"])
               if steps.step_ran(s) and p.role(entry["workflow"]) in REVIEWER_ROLES]
        if ran:
            out.append(entry)
    return out


def _job_join(entry: dict[str, Any], codebasis: CodeBasis) -> Optional[Join]:
    last = steps.last_run_link(entry["job"])
    if last is None:
        return None
    w = _window(entry["workflow"], entry["run"], entry["job"], last[0], last[1], require_times=False)
    return resolve(w, codebasis, job_level=True)


def annotate_record(record: dict[str, Any], index: ReceiptIndex, codebasis: CodeBasis, *,
                    owner_login: str, claims: dict[int, int]) -> dict[str, Any]:
    """A NEW record with every event's runtime joined and window trust applied (§2–6, the §2b
    key from ``claims``; the record-level effects of §8)."""
    rec = copy.deepcopy(record)
    incomplete = set(rec.get("incomplete") or [])
    used_runs: set[int] = set()
    for event in rec.get("events") or []:
        if event.get("kind") == "job.reviewer" or event.get("ts_precision") == "day":
            continue
        roles = KIND_ROLES.get(_kind_key(event))
        signals = event.get("signals") or {}
        verdict, w = "none", None
        if roles:
            cands = [c for c in containing_windows(index, ts=event.get("ts"), roles=roles,
                                                   author_login=signals.get("login"),
                                                   owner_login=owner_login)
                     if window_belongs(c, rec) and _owner_key_ok(event, c, rec, claims, owner_login)]
            verdict, w = pick_window(cands, event.get("ts"))
        runtime = dict(event.get("runtime") or {})
        if verdict == "one":
            join = resolve(w, codebasis)
            event["runtime"] = _window_runtime(runtime, join)
            used_runs.add(w.run_id)
            tag = _unavailable_tag(join.unavailable)
            if tag:
                incomplete.add(tag)
            if event.get("trust") in ("login", "claimed") and event.get("trust_basis") != "marker:owner-token":
                event["trust"] = "window"
                event["trust_basis"] = f"window:run {w.run_id}"
            continue
        claim = trailer_runtime(signals)
        if claim is not None:
            runtime.update(claim)
            event["runtime"] = runtime
            if event.get("trust") not in ("verified", "window"):
                event["trust"] = "claimed"
                event["trust_basis"] = "trailer"
            continue
        if verdict == "ambiguous":
            for k in ("role", "workflow", "job", "job_id", "run_id", "attempt", "chain", "chain_link",
                      "links_not_served", "provider", "model"):
                runtime[k] = None
            runtime["model_basis"] = "ambiguous"
            event["runtime"] = runtime
    receipts_used = {index.path_of(r) for r in used_runs}
    if rec.get("kind") == "pr":
        for entry in _pr_jobs(rec, index):
            receipts_used.add(entry["path"])
            join = _job_join(entry, codebasis)
            tag = _unavailable_tag(join.unavailable) if join else None
            if tag:
                incomplete.add(tag)
        if isinstance(rec.get("unknown"), dict) and isinstance(record.get("pr"), int):
            counts: dict[str, int] = {}
            for r in index.runs_for_pr(rec["pr"], rec.get("head_ref")):
                if run_belongs(r["run"], rec):
                    for name in sorted(set(r.get("suspicious_steps") or [])):
                        counts[name] = counts.get(name, 0) + 1
            step_counts = dict(rec["unknown"].get("steps") or {})
            step_counts.update(counts)
            rec["unknown"]["steps"] = {k: step_counts[k] for k in sorted(step_counts)}
    if "incomplete" in rec:
        rec["incomplete"] = sorted(incomplete)
    evidence = rec.get("evidence")
    if isinstance(evidence, dict):
        paths = set(evidence.get("receipts") or []) | {p for p in receipts_used if p}
        evidence["receipts"] = sorted(paths)
    return rec


_EMPTY_SIGNALS = {"login": None, "login_type": None, "app": None, "marker": None,
                  "commit_author_name": None, "commit_author_email": None, "committer_login": None,
                  "status_context": None, "regen_identity": False, "trailer_coauthors": [],
                  "trailer_session": None}


def receipt_events(record: dict[str, Any], index: ReceiptIndex, codebasis: CodeBasis, *,
                   owner: str, repo: str) -> list[dict[str, Any]]:
    """``job.reviewer`` events for one PR record (§7)."""
    if not (_SLUG_RE.fullmatch(owner or "") and _REPO_RE.fullmatch(repo or "")):
        raise ValueError(f"invalid owner/repo {owner!r}/{repo!r}")
    events = [e for e in record.get("events") or [] if e.get("kind") != "job.reviewer"]
    out = []
    for entry in _pr_jobs(record, index):
        run, job = entry["run"], entry["job"]
        head = run.get("head_sha") if isinstance(run.get("head_sha"), str) and SHA40_RE.fullmatch(run["head_sha"]) else None
        posted = any(((e.get("runtime") or {}).get("job_id") == job["id"])
                     and (e.get("sha") is None or e.get("sha") == head) for e in events)
        tried = sum(1 for s, _ in steps.agent_steps(job) if steps.step_ran(s))
        join = _job_join(entry, codebasis)
        runtime = {"platform": "github-actions", "harness": "claude-code-action", "role": None,
                   "workflow": entry["workflow"], "job": job.get("name"), "job_id": job["id"],
                   "run_id": run["id"], "attempt": job.get("run_attempt") or run.get("run_attempt") or 1,
                   "chain": None, "chain_link": None, "links_not_served": None, "provider": None,
                   "model": None, "model_basis": "none"}
        if join is not None:
            runtime.update(join.runtime_fields())
        started = (ts_epoch(job.get("started_at")) or ts_epoch(run.get("created_at")))
        conclusion = job.get("conclusion")
        out.append({
            "id": f"job:{job['id']}",
            "ts": ts_str(started),
            "ts_precision": "second",
            "tz": "UTC",
            "kind": "job.reviewer",
            "episode": None,
            "pr": record.get("pr"),
            "issue": None,
            "sha": head,
            "head_sha": None,
            "stale_sha": False,
            "after_merge": False,
            "url": f"https://github.com/{owner}/{repo}/actions/runs/{int(run['id'])}/job/{int(job['id'])}",
            "signals": dict(_EMPTY_SIGNALS, trailer_coauthors=[]),
            "trust": "verified",
            "trust_basis": "receipt",
            "runtime": runtime,
            "fields": {"conclusion": conclusion if conclusion in CONCLUSIONS else None,
                       "posted": posted, "links_tried": min(tried, 99)},
            "edges": {"verifies": []},
        })
    return sorted(out, key=canonical.event_sort_key)
