<!-- The agent-brief format — the input contract of the agent forge
     (docs/agent-forge.md). This is the shape /wright files and the
     .github/ISSUE_TEMPLATE/agent-brief.yml issue form collects; the section
     headings here and that form's field labels must stay identical (the
     design-brief pair's discipline). The brief becomes the BODY of an issue
     titled "Agent brief: <name>" and labeled `agent-brief`; Reeve's sign-off
     (/reeve-signoff) rules on it, an approved brief is armed for the backlog
     burn, and /ship-issue freezes THIS text as its acceptance contract — so
     everything the build owes must be in here or in Open questions.
     One deliberate rule: name existing protection machinery GENERICALLY
     ("its own deny backstop", "the provider's registry secret") — a brief
     that names existing settings/perms-check files, secrets, or arming
     variables is deterministically downgraded to needs-decision by the
     sign-off tool's sensitive-path guard. Delete these comments. -->

## Gap

The observed failure or missing capability, with the **signal** that proves
it exists — a run link, a report section (Reeve's bench-health / the groomer
report), a telemetry record, or an issue. A gap with no checkable signal is a
hunch and will be declined.

## What to build

Kind: one of **probabilistic agent** / **deterministic tool** / **hybrid**
(say which half of a hybrid is which). One paragraph of what it does. For a
new agent, name the house pattern it clones: the scout for filers, the
assessor for commenters, the labeler for label-appliers, the groomer/Reeve
for deterministic reporters. Deterministic beats probabilistic when a pure
function of committed files closes the gap.

## Surfaces & bounds

What it reads, what it writes, and its caps. A new scheduled agent inherits
the full house pattern — list it generically: committed conf + two-key
arming (shipped disarmed), a registry model chain (no pinned ids), its own
deny backstop + perms-check run by check.sh, the read-wrapper/MCP-write
split, cadence-sync coverage, drift-guard coverage. A deterministic tool
lists its inputs (committed files only, or a GET-only seam) and its
`--selftest`.

## Acceptance criteria

Checkable and falsifiable, one per line — this becomes `/ship-issue`'s
frozen contract. Every guard/check claimed must include its negative control
(prove it can fail), the repo's standing rule.

## Size

`points-1`, `points-2` or `points-3` with one line of reasoning. An honest
5+ means split this brief before filing — or say explicitly that the chunker
is the expected path and why the whole is still worth arming.

## Assumptions & defaults

Everything defaulted above, restated in one list so Reeve (or a human
reading back) can challenge each without re-deriving which were guesses.

## Open questions

What must be answered before building starts, marked blocking or not. An
empty section is a claim: it says `/ship-issue` can start from this brief
alone.
