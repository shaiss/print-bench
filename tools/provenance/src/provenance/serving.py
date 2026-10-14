"""The serving-model join — which routine, run, chain link and model produced each artifact.

Pure over receipts (``receipt@1``), record@1 events and a
``protocols.CodeBasis``. Nothing is guessed: zero or several candidate
windows give ``model: null`` with basis ``ambiguous``/``none``
(docs/provenance.md §Serving-model join).

**1. Windows** (:class:`ReceiptIndex`). Every agent step that RAN
(``steps.step_ran``) in a full receipt is a :class:`StepWindow` —
``[started_at, completed_at]`` inclusive, second precision — carrying its
run (workflow, event, head_sha, created_at, attempt), job (id, name) and
``steps.AgentStep``. A step with a null timestamp is no window.

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
ts is strictly inside it; on the exact boundary → ``ambiguous``.

**2b. The owner's token needs a correlating key** (critique item 15). The
ship routines post and open PRs with the OWNER's PAT, so an OWNER-authored
artifact inside a design-run/backlog-burn window may equally be the owner's
own attended work. Such an artifact is attributed only through the issue the
run CLAIMED: :func:`run_claims` maps each ship-routine run to the one issue
``N`` whose OWNER-authored ``brief.claimed`` (SHIP-LOCK) lies in that run's
windows — the selector claims one issue per run, so a run whose windows hold
two or more such SHIP-LOCKs claims nothing. Then:

* the ``brief.claimed`` itself is attributed iff it is that run's claim;
* an OWNER ``brief.shipped|declined|deferred|withdrawn`` on issue ``N`` iff
  the run claimed ``N``;
* an OWNER ``pr.opened`` / ``commit.*`` iff the PR's ``head_ref`` is
  ``claude/issue-<N>-…`` and the run claimed ``N``;
* otherwise the trust stays ``login`` (an owner PR on any other branch inside
  a design-run window, a run that declined without claiming).

Bot-authored artifacts (``github-actions[bot]``, ``claude[bot]``) keep the
plain containment rule. Run 34661448637 claimed #592 (SHIP-LOCK 00:35:31Z in
link 1) and #636's head is ``claude/issue-592-nuggs-vent-cap``, so NVC-3/NVC-4
hold under the key. Claims come from brief records only, so the owner-PAT
events of a backlog-burn run on a non-brief issue stay ``login`` — honest,
not guessed.

**3. Code basis** (``CodeBasis.basis_for``): schedule / workflow_dispatch →
``head`` (run.head_sha, exact); auto-review.yml pull_request → ``merge``
(``git merge-tree --write-tree <main@created_at> <run.head_sha>`` — the
design-changes job resolves the chain on the merge ref); oracle.yml
pull_request → ``main`` at the ``actions/checkout`` step's ``started_at``
(the job checks out ``pull_request.base.ref`` BY NAME when that step runs,
which can be long after ``created_at`` on a busy queue — critique item 26;
the step comes from the same receipt job). ``main@T`` = the last first-parent
main commit with committer date ``<= T``. ``ambiguous`` when merge-tree
conflicts on registry.conf or the workflow file, or a main commit touching
either lies in ``(created_at − window, created_at]`` (merge) or in
``[started_at − window, completed_at + window]`` of the checkout step (main).
A commit the basis needs that is not local after the job-start fetch (a
force-pushed-away head) → basis ``none`` and ``incomplete:
codebasis-unavailable:<sha8>`` — deterministic, never a fetch (critique item
9). Bases are memoized per ``(workflow, kind, main8, head8)``.

**4. Chain and model** (:func:`resolve`):

* E3 (chain link) step: the chain id is the workflow's
  ``model_registry resolve <chain>`` literal at the basis
  (:func:`chain_literals`); when the workflow has several
  (``oracle.yml``: oracle-anthropic / oracle-glm; ``wright.yml``: wright /
  wright-signoff), :data:`CHAIN_DISCRIMINATORS` picks by
  (workflow, lead, provider) and the pick must be one of the literals, else
  ``ambiguous``. ``model = chain_models(basis, chain)[link - 1]``;
  ``chain_link = link``; ``links_not_served = link - 1`` (rendered "links
  1–(N−1) did not serve", never "failed": the walk keys on ``served`` and a
  link can exit 0 having posted nothing, #762); basis
  ``step-window+registry@head(<sha8>)`` / ``@merge(<main8>+<head8>)`` /
  ``@main(<sha8>)``.
* E0/E1/E2 (pre-#326) step: the model is the step's inline ``--model``
  literal in the workflow text at the basis (:func:`inline_pin`: the step
  block named exactly like the step, inside the job named like the job;
  the first ``--model <id>`` that is not ``${{ … }}``); ``chain`` and
  ``chain_link`` null; basis ``provider-step+inline-pin@<sha8>``. The E2
  name label is never the model of record.
* An unparseable/missing registry or workflow → model null, basis ``none``
  (counted ``codebasis-unavailable:<sha8>`` in ``incomplete``).
* Job-level events (``job.reviewer``) use ``steps.last_run_link`` — the
  last non-skipped link — with basis prefix ``job-link+registry@…``.

**5. Trailers** (:func:`trailer_runtime`): a commit with
``Co-Authored-By: Claude <Name> <noreply@anthropic.com>`` (Name non-empty)
gets ``model = Name`` (e.g. ``Claude Opus 5.5``), basis ``trailer``,
``harness: claude-code``, trust ``claimed``; ``Cursor Agent`` → platform
``cursor``, model null.

**6. Trust upgrade.** An event whose trust is ``login`` or ``claimed``
(not ``marker:owner-token``) whose artifact sits in exactly one compatible
window becomes ``window`` with basis ``window:run <id>`` (``runtime.workflow``/
``job``/``run_id``/``attempt`` W-tagged). ``verified`` events keep their tier
and gain the runtime join.

**7. Receipt events** (:func:`receipt_events`): one ``job.reviewer`` per
reviewer/coach/oracle JOB in the receipts of the PR's head branch
(``run.head_branch == head_ref`` or the run's ``pull_requests`` holds the
PR) whose job has an agent step that ran; ``fields.posted`` = some event of
the record is attributed to that job; ``links_tried`` = agent steps that ran.
Trust ``verified`` / basis ``receipt``. They are returned UNPLACED
(``episode``/``head_sha`` ``None``, ``stale_sha``/``after_merge`` false):
``episodes.place`` assigns them (the derive order in episodes.py). Acceptance: NVC-2 (remy,
34112970240, glm-5.2), NVC-3 (9a751b26, glm-4.6, link 3), NVC-5 (12,
[glm-5.3]).

Owner: H4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

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
    """The runtime join for one event (the event's ``runtime`` fields it sets)."""

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


class ReceiptIndex:
    """Agent-step windows from a set of receipts, queryable by time and role."""

    def __init__(self, receipts: Iterable[dict[str, Any]]) -> None:
        raise NotImplementedError("builder H4")

    def windows(self) -> list[StepWindow]:
        """Every window, sorted (started, run_id, job_id, step name)."""
        raise NotImplementedError("builder H4")

    def jobs_for_pr(self, pr: int, head_ref: Optional[str]) -> list[dict[str, Any]]:
        """Reviewer/coach/oracle jobs (receipt run + job) belonging to one PR."""
        raise NotImplementedError("builder H4")


def containing_windows(index: ReceiptIndex, *, ts: str, roles: frozenset[str],
                       author_login: Optional[str], owner_login: str) -> list[StepWindow]:
    """Candidate windows for one artifact (module docstring §2)."""
    raise NotImplementedError("builder H4")


def chain_literals(workflow_text: str) -> list[str]:
    """Distinct ``model_registry resolve <chain>`` literals, in file order."""
    raise NotImplementedError("builder H4")


def inline_pin(workflow_text: str, job_name: str, step_name: str) -> Optional[str]:
    """The step's literal ``--model`` (pre-#326), found by a line scanner over the workflow
    text: the job whose ``name:`` equals ``job_name``, the step whose ``- name:`` equals
    ``step_name`` exactly once inside it; ``None`` otherwise. Not a YAML parser."""
    raise NotImplementedError("builder H4")


def resolve(window: StepWindow, codebasis: CodeBasis, *, job_level: bool = False) -> Join:
    """Chain/model for one window (module docstring §3–4)."""
    raise NotImplementedError("builder H4")


def trailer_runtime(signals: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Claimed runtime from commit trailers (module docstring §5), or ``None``."""
    raise NotImplementedError("builder H4")


#: The ship routines whose OWNER-authored artifacts need a claimed-issue key (§2b).
SHIP_ROLES = frozenset({"design-run", "backlog-burn"})
CLAIM_BRANCH_RE = re.compile(r"claude/issue-([0-9]{1,7})-")


def run_claims(brief_records: list[dict[str, Any]], index: ReceiptIndex, *,
               owner_login: str) -> dict[int, int]:
    """``{ship-routine run id: claimed issue}`` (§2b): the unique OWNER ``brief.claimed`` inside
    that run's windows; runs with zero or several are absent."""
    raise NotImplementedError("builder H4")


def annotate_record(record: dict[str, Any], index: ReceiptIndex, codebasis: CodeBasis, *,
                    owner_login: str, claims: dict[int, int]) -> dict[str, Any]:
    """A NEW record with every event's runtime joined and window trust applied (§2–6, the §2b
    key from ``claims``)."""
    raise NotImplementedError("builder H4")


def receipt_events(record: dict[str, Any], index: ReceiptIndex, codebasis: CodeBasis, *,
                   owner: str, repo: str) -> list[dict[str, Any]]:
    """``job.reviewer`` events for one PR record (§7)."""
    raise NotImplementedError("builder H4")


def basis_label(basis: Basis, *, job_level: bool) -> str:
    """The ``model_basis`` string for a basis (contract pattern)."""
    raise NotImplementedError("builder H4")
