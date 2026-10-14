"""The agent-step grammar — which Actions job steps ran an LLM agent, in every naming era.

A workflow's step names are the only durable record of *which chain link* an
agent run used (docs/provenance.md §Receipts, §Serving-model join). The names
changed shape four times, so the grammar is a closed, versioned list of
anchored regexes, one per era, each pinned by a fixture
(tests/test_steps.py):

====  ======================  ===========================================================
era   dates (first seen)      shape (examples)
====  ======================  ===========================================================
E0    2026-08-12 (#200)       ``Run /jane-review (unattended)`` — no provider, no model
E1    2026-08-08 → 08-21      ``Run via Anthropic (Claude)`` / ``Ship via Z.AI (GLM)`` —
                              provider only; the model is the step's inline ``--model``
                              pin in the workflow at the run's code basis (pre-#326)
E2    2026-08-12 → 08-20      ``/jane-review via Z.AI GLM 5.2`` /
                              ``/pm triage via Anthropic Opus 4.8`` — provider + a model
                              label; the model is still read from the inline pin
E3    2026-08-21 →            ``Run via Z.AI (GLM, chain link 3)``,
                              ``/drik-review via Anthropic (chain link 4)``,
                              ``Oracle via Z.AI GLM (chain link 1)``,
                              ``Ship via OpenRouter (OSS, chain link 6)``,
                              ``Propose via ...`` / ``Sign off via ...`` (wright.yml) —
                              the link number; the model is chain[link] from
                              ``registry.conf`` at the code basis
====  ======================  ===========================================================

Every pattern is anchored at both ends: a step such as ``Restore the coach
posting surface from the base branch (before chain link 1)`` contains the
words "chain link 1" but is not an agent step and must never parse as one.

**Fail-safe.** A step whose name carries LLM vocabulary (Claude, GLM, Z.AI,
Anthropic, OpenRouter, Opus, Sonnet, Haiku, "chain link") but matches no era
and none of :data:`NON_AGENT_PATTERNS` is *suspicious*: the receipt writer
keeps that run's complete jobs response (never a stub) and counts the name
as ``unknown.step`` in the job summary, so a fifth naming era cannot silently
turn into stubs. Adding an era is a :data:`STEP_GRAMMAR_VERSION` bump plus a
fixture.

This module is pure: no I/O, no clock. It is implemented in full by the
scaffold because both the receipt writer (H1) and the serving join (H4)
consume it; H4 owns it from here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

#: Bumped whenever an era is added or a pattern changes. Recorded in
#: ``state.json`` ``versions.step_grammar`` and in every receipt.
STEP_GRAMMAR_VERSION = 1

#: Conclusions that mean "the step did not run". A skipped link never served.
NOT_RUN_CONCLUSIONS = frozenset({"skipped"})

_LEAD = r"(?P<lead>Run|Ship|Oracle|Propose|Sign off|/jane-review|/drik-review|/design-coach|/pm triage)"

#: E3 — the chain-link era (issue #326 onward; reviewer chains since #206).
E3_RE = re.compile(
    "^" + _LEAD
    + r" via (?P<prov>Z\.AI|Anthropic|OpenRouter)(?: GLM)? \((?:(?:GLM|Claude|OSS), )?"
    r"chain link (?P<link>[1-9][0-9]?)\)$"
)
#: E2 — reviewer steps that named the model in the step name (2026-08-12 → 08-20).
E2_RE = re.compile(
    r"^(?P<lead>/jane-review|/drik-review|/design-coach|/pm triage) via "
    r"(?P<prov>Z\.AI GLM|Anthropic) "
    r"(?P<label>(?:Opus|Sonnet|Haiku) [0-9]+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)$"
)
#: E1 — routine provider steps before chains (pre-#326).
E1_RE = re.compile(
    r"^(?P<lead>Run|Ship) via (?:(?P<anthropic>Anthropic) \(Claude\)|(?P<zai>Z\.AI) \(GLM\))$"
)
#: E0 — the first unattended reviewer steps (2026-08-12, PR #200).
E0_RE = re.compile(r"^Run (?P<lead>/jane-review|/drik-review|/design-coach) \(unattended\)$")

#: LLM vocabulary that makes an unparsed step name suspicious.
SUSPICIOUS_RE = re.compile(
    r"(?i)(claude|\bglm\b|z\.ai|anthropic|openrouter|\bopus\b|\bsonnet\b|\bhaiku\b|chain link)"
)

#: Step names that carry LLM vocabulary but are known NOT to run an agent.
#: Anchored; extend with a fixture when a workflow adds such a step.
NON_AGENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^Post "),                                   # action post-steps
    re.compile(r"^Resolve the .*chain"),                      # model_registry resolve
    re.compile(r"^Restore the coach posting surface from the base branch"),
    re.compile(r"^No chain link delivered the review$"),
    re.compile(r"^Artifact check after link [0-9]+ "),
    re.compile(r"^Diagnose the exhausted "),
    re.compile(r"^Explain "),
    re.compile(r"^Run actions/"),
)

_PROVIDER = {"Z.AI": "zai", "Z.AI GLM": "zai", "Anthropic": "anthropic", "OpenRouter": "openrouter"}

#: The role a step's lead names. ``Run``/``Ship`` are routine leads whose
#: role is the workflow's (:data:`ROUTINE_ROLE_BY_WORKFLOW`).
ROLE_BY_LEAD = {
    "/jane-review": "jane",
    "/drik-review": "drik",
    "/design-coach": "coach",
    "/pm triage": "pm",
    "Oracle": "oracle",
    "Propose": "wright",
    "Sign off": "reeve-signoff",
}

#: Routine workflows whose ``Run``/``Ship`` lead takes the workflow's role.
ROUTINE_ROLE_BY_WORKFLOW = {
    "design-run.yml": "design-run",
    "backlog-burn.yml": "backlog-burn",
    "product-scout.yml": "product-scout",
    "spike-converter.yml": "spike-converter",
    "chunker.yml": "chunker",
    "labeler.yml": "labeler",
}

#: The closed role vocabulary (contract enum ``role``).
ROLES = (
    "jane", "drik", "pm", "coach", "oracle", "wright", "reeve-signoff",
    "design-run", "backlog-burn", "product-scout", "spike-converter", "chunker", "labeler",
)


@dataclass(frozen=True)
class AgentStep:
    """One parsed agent step name.

    ``era`` is ``"E0"``..``"E3"``; ``provider`` is ``zai``/``anthropic``/
    ``openrouter`` or ``None`` (E0); ``link`` is the 1-based chain link (E3
    only); ``label`` is the E2 model label (``"5.2"``, ``"Opus 4.8"``) — a
    cross-check only, never the model of record.
    """

    era: str
    lead: str
    provider: Optional[str]
    link: Optional[int]
    label: Optional[str]

    def role(self, workflow: str) -> Optional[str]:
        """The role this step served in ``workflow`` (``None`` if unknown)."""
        if self.lead in ROLE_BY_LEAD:
            return ROLE_BY_LEAD[self.lead]
        return ROUTINE_ROLE_BY_WORKFLOW.get(workflow)


def parse_step_name(name: str) -> Optional[AgentStep]:
    """Parse ``name`` against the four eras; ``None`` when it is not an agent step."""
    if not isinstance(name, str):
        return None
    m = E3_RE.match(name)
    if m:
        return AgentStep("E3", m.group("lead"), _PROVIDER[m.group("prov")], int(m.group("link")), None)
    m = E2_RE.match(name)
    if m:
        return AgentStep("E2", m.group("lead"), _PROVIDER[m.group("prov")], None, m.group("label"))
    m = E1_RE.match(name)
    if m:
        provider = "anthropic" if m.group("anthropic") else "zai"
        return AgentStep("E1", m.group("lead"), provider, None, None)
    m = E0_RE.match(name)
    if m:
        return AgentStep("E0", m.group("lead"), None, None, None)
    return None


def is_suspicious(name: str) -> bool:
    """True when ``name`` carries LLM vocabulary, parses as no era and is not a known non-agent step."""
    if not isinstance(name, str) or parse_step_name(name) is not None:
        return False
    if not SUSPICIOUS_RE.search(name):
        return False
    return not any(p.search(name) for p in NON_AGENT_PATTERNS)


def step_ran(step: dict[str, Any]) -> bool:
    """A step ran when its conclusion is not ``skipped`` (``continue-on-error``
    makes a failed link read ``success``, so a non-skipped link is *tried*, not *served*)."""
    return step.get("conclusion") not in NOT_RUN_CONCLUSIONS


def agent_steps(job: dict[str, Any]) -> list[tuple[dict[str, Any], AgentStep]]:
    """The job's agent steps, in step order, each with its parse."""
    out = []
    for step in job.get("steps") or []:
        parsed = parse_step_name(step.get("name", ""))
        if parsed is not None:
            out.append((step, parsed))
    return out


def last_run_link(job: dict[str, Any]) -> Optional[tuple[dict[str, Any], AgentStep]]:
    """The last agent step of ``job`` that ran (not skipped), or ``None``.

    This is the job-level serving rule (docs/provenance.md §Serving-model
    join): because ``continue-on-error`` masks step conclusions, the link
    that served a job is the LAST non-skipped agent step, never the first
    "success". Artifact-level attribution uses step-window containment
    instead (``serving.py``).
    """
    ran = [(s, p) for s, p in agent_steps(job) if step_ran(s)]
    return ran[-1] if ran else None


def jobs_have_agent_step(jobs: Iterable[dict[str, Any]]) -> bool:
    """True when any job has an agent step that ran — the full-receipt test."""
    return any(step_ran(s) for job in jobs for s, _ in agent_steps(job))


def suspicious_step_names(jobs: Iterable[dict[str, Any]]) -> list[str]:
    """Sorted, de-duplicated suspicious step names across ``jobs`` (fail-safe input)."""
    names = {
        step.get("name", "")
        for job in jobs
        for step in job.get("steps") or []
        if is_suspicious(step.get("name", ""))
    }
    return sorted(names)
