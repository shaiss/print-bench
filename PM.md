# print-bench — product charter

print-bench is a workshop where a person and an AI co-design a 3D-printable part
and ship it gate-proven — parametric OpenSCAD in, a sliced-clean STL plus an
honest product page out. Its customer is the design sessions — human or agent —
that operate the bench, and behind them the human lead who brings the ideas and
the measurements and prints on real hardware. The one thing it must do well: let
a designer take an idea to a merge-ready, printable, truthfully-documented design
*without the bench's own machinery becoming the project*. Everything else — the
gates, the autonomy loop, the site, the styles and lineage systems — exists only
to serve that, and is overhead the moment it doesn't.

This is the platform's own charter, one level up from the per-design `PM.md`
files. It is what the **bench** is and who it is for; `CLAUDE.md` is how it
works, and `README.md` is what a visitor reads. It stays under a page — if it
grows past one, it has stopped being a charter (issue #272).

## The PM — who owns the system

print-bench splits the PM role three ways, and this charter names the third leg.
Issue #229 established two: **Remy** (`/product-scout`) is the *generative* PM —
it proposes what designs should exist; **Vera** (`/pm` on a design) is the
*enforcement* PM — it holds one design's scope and non-negotiables. Neither owns
the bench itself. **Reeve owns the system** — the gates, the autonomy loop, the
site, the telemetry — as a running whole. The design PMs roll up to it; it speaks
for the platform when a design's needs meet the bench's.

Reeve's authority is **operational, not editorial**. The human lead stays primary
and owns every merge; Reeve **never gates a merge**. What it does is keep the
machine that carries work to that merge healthy and honest *between* merges, by
reading the ops pulse the repo already emits — `telemetry/REPORT.md` and
`log.ndjson` (gate scores, render and gate wall-times, preview-budget headroom,
what was skipped and why; issue #93), and the live committed previews and routine
confs. When a number drifts — scores sliding, budgets tightening, skips creeping —
that is Reeve's finding, surfaced before it compounds. It interrupts the human
only for blockers; everything else it records in the repo for reading when wanted.

Its single most important instinct is the last non-negotiable below — **the
tooling must not outgrow the designs it serves** — because that is the failure no
individual PR looks guilty of, and the one the ops data shows first.

**Reeve's leash — what it may do without asking.**

| v1 — on its own (shipped) | Staged behind a wrapper + deny-backstop | Never |
|---|---|---|
| Read the committed pulse and upsert **one** sticky "bench health" report issue | File / label follow-up issues per finding (an LLM step; needs the labeler's wrapper + `.claude/*-settings.json` deny backstop + a perms-check) | Push code, or edit any design's geometry, scripts, lib, or workflows |
| Re-rank the platform backlog with stated reasons | — | Change a non-negotiable, or anything in "Never" |
| Flag a telemetry regression in the report | — | Merge anything, ever |

v1 is the deterministic reporter (`tools/reeve/`): no LLM, no provider secret,
reads only committed files, one trusted sticky-issue write — the backlog
groomer's proven-safe shape. The "hands" (auto-filing/labeling from model output)
cross into agentic-writer territory and are staged as a follow-up carrying the
same wrapper + deny-backstop the labeler and chunker ship, because that is what
reading untrusted issue text with a key in scope requires.

## Non-negotiables

Constraints that may **not** be weakened to make the platform easier to build.
Each names the standing decision or issue behind it.

| # | Constraint | Rule | Source | Reopens if |
|---|---|---|---|---|
| N1 | Humans write source, CI writes everything derived | No hand-committed renders, shots, galleries, telemetry — `regen` regenerates them in the same run that gates the source | CLAUDE.md "What CI generates"; issue #69 | Never — the freshness hole reopens the moment a human commits a derived artifact |
| N2 | Copyleft stays out of shared first-party core | `scripts/`, `site/`, `lib/*.scad` may not `include`/bundle GPL-vendored code; a design may opt in and disclose | Standing decision, issue #160; `license-boundary-check.sh`; `docs/licensing.md` | Never — it is a decision, not a deferral |
| N3 | Autonomy converges on gates, never on taste | Agentic runs drive geometry to gate-clean and hand off; approving a *shape* and every merge is the human lead's | `/design-run`, `/ship-issue`; HITL gate `needs-decision`, issue #161 | Never |
| N4 | The reproducible source of truth lives in git | Decisions (CI-gate registry, backlog policy, model registry, Reeve's conf) are committed config a clone carries; GitHub supplies only interaction + auth | `.github/**/*.conf` pattern; `tools/ci-gates` | A better reproducible store than the repo itself exists |
| N5 | The served site invents nothing and depends on nothing external | Every word/image traces to a provenanced committed file or first-party record; served bytes are vendored, no CDN; a broken local ref fails the build | `site/README.md` | Never |
| N6 | The tooling must not outgrow the designs it serves | New platform machinery must trace to a design need a real session hit; "interesting to build" is not a reason | This charter | The bench's purpose changes from co-designing parts to something else |

## Out of scope

**Deferred** — good ideas, not now (ranked in the backlog):

- Reeve's "hands" — the LLM step that files/labels follow-up issues from the pulse (the leash's middle column), behind the labeler's wrapper + deny-backstop pattern.
- The intelligent LLM router (flashx-as-router) and task proposal/assignment layer (issue #206 stretch).
- The team timeline as the history source (issue #126) that retires `people/work.conf`.

**Never:**

- **A general CAD tool, a slicer, or a print-farm manager.** The bench co-designs
  parametric parts and proves them printable; it does not replace OpenSCAD,
  PrusaSlicer, or a fleet controller.
- **A marketplace / store / paywall.** Designs are open and gated for honesty, not
  merchandised.
- **Autonomy that merges its own taste** (N3), a non-deterministic / CDN-dependent
  site (N5), or copyleft in shared core (N2). The "never" list is where the
  non-negotiables become refusals.
- **A second source of truth outside git** for any platform decision (N4) — no
  console-only config, no state a clone doesn't carry.

## What "working" looks like

Not a one-time definition of done — the health invariants a stranger can check:

- [ ] A design goes idea → merge-ready draft PR with the human reacting to a
      *shape*, never operating machinery.
- [ ] Every gate on a derived artifact is presence + freshness-by-construction
      (regenerated in the gating run), never a human's promise it's current.
- [ ] `check.sh` proves every claim the docs make about the tree (docs-drift,
      guard/mate negative controls, license boundary) — green means true.
- [ ] The autonomy loop has shippable work *and* a human gate: `/label-issues`
      arms, the burn ships, `needs-decision` parks what's the human lead's.
- [ ] No platform feature is live that no design uses (N6) — or it's tracked to a
      design that will.
- [ ] The ops pulse is read, not just emitted: no telemetry regression (gate
      score, budget headroom, skip rate) sits unremarked — Reeve's report is
      current.

## Backlog, ranked by platform value

Ranked by how often a session is blocked or misled by the gap, not by how
interesting the build is.

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Reeve's "hands": the LLM step that files/labels follow-up issues from the pulse, behind the labeler's wrapper + deny-backstop | The v1 reporter surfaces drift; acting on it is still manual | medium |
| B2 | Team timeline (#126) retires the interim `work.conf` | Provenance of who-did-what is currently a hand-maintained manifest | medium |
| B3 | First real `assembly.conf` design (assembly-docs stage 4) | A whole feature (#98/#156) is unexercised by any design — N6 risk | medium |
| B4 | LLM router + task proposal layer (#206 stretch) | Real leverage, but no session is blocked on it today | large |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Arm Reeve (set the `REEVE_ENABLED` repo variable) once the first sticky report reads right? | No | Ships disarmed; the human arms it when ready |
| When Reeve gains its "hands" (B1), does it also open PRs, or only file/label issues? | No | Issues/labels only — the ambient `GITHUB_TOKEN`, no PAT, matching the labeler |
| When Reeve and a design PM conflict on taste, not ops? | No | Escalate to the human lead — "customer of last resort" per `people/shai.md` |

## Decision log

Append-only. A later session must be able to tell a considered choice from an accident.

| Date | Decision | Reason |
|---|---|---|
| 2026-08-16 | Name the platform PM **Reeve**, a registered agent (`people/reeve.md`), senior over the design PMs, advisory (never gates a merge) | A reeve is the steward who runs the operation for the owner — the human lead stays primary |
| 2026-08-16 | Reeve completes the PM split as the *operational* third leg beside Remy (generative) and Vera (enforcement) | Issue #229 split the PM role two ways; neither owns the bench's own health |
| 2026-08-16 | Ship v1 as a deterministic bench-health reporter in the backlog-groomer mold; stage the LLM "hands" behind the labeler's deny-backstop | The safe, repo-native path: no agent + no secret + one trusted write needs no backstop; hands do |
| 2026-08-16 | Lead the non-negotiables with N6 (tooling must not outgrow its designs) as Reeve's core instinct | It is the failure mode no single PR looks guilty of, and the one the ops data shows first |
