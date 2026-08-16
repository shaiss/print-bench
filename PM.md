# print-bench — product charter

<!-- DRAFT for review (issue #272). The platform's own charter, one level up
     from the per-design PM.md files. This is what the BENCH is and who it is
     FOR; CLAUDE.md is how it works, README.md is what a visitor reads. Keep it
     under a page — if it grows past one, it has stopped being a charter.
     The art-direction / shots section from templates/PM.md is intentionally
     omitted: the platform has no product page of its own. -->

## The product, in one paragraph

print-bench is a **workshop where one person and an AI co-design a 3D-printable
part and ship it gate-proven** — parametric OpenSCAD in, a sliced-clean STL plus
an honest product page out. The customer is **Shai** (the founder, who brings the
idea and the measurements and prints on real hardware) and, right behind him, the
**design sessions — human or agent — that operate the bench**. The one thing it
must do well: let a single designer take an idea to a merge-ready, printable,
truthfully-documented design *without the bench's own machinery becoming the
project*. Everything else — the gates, the autonomy loop, the site, the styles
and lineage systems — exists only to serve that, and is overhead the moment it
doesn't.

## The PM's job (why this charter exists)

Shai owns every merge and is the customer of last resort. The platform PM is his
**co-founder for the bits he misses** — not an engineer and not a reviewer, but
the one who holds the platform's line while he's heads-down in a design: watching
for scope creep in the tooling, keeping the "never" list honest, and blocking on
the decisions only he can make. Its single most important instinct is the last
non-negotiable below — **the tooling must not outgrow the designs it serves** —
because that is the failure no individual PR looks guilty of.

## Non-negotiables

Constraints that may **not** be weakened to make the platform easier to build.
Each names the standing decision or issue behind it.

| # | Constraint | Rule | Source | Reopens if |
|---|---|---|---|---|
| N1 | Humans write source, CI writes everything derived | No hand-committed renders, shots, galleries, telemetry — `regen` regenerates them in the same run that gates the source | CLAUDE.md "What CI generates"; issue #69 | Never — the freshness hole reopens the moment a human commits a derived artifact |
| N2 | Copyleft stays out of shared first-party core | `scripts/`, `site/`, `lib/*.scad` may not `include`/bundle GPL-vendored code; a design may opt in and disclose | Standing decision, issue #160; `license-boundary-check.sh`; `docs/licensing.md` | Never — it is a decision, not a deferral |
| N3 | Autonomy converges on gates, never on taste | Agentic runs drive geometry to gate-clean and hand off; approving a *shape* and every merge is Shai's | `/design-run`, `/ship-issue`; HITL gate `needs-decision`, issue #161 | Never |
| N4 | The reproducible source of truth lives in git | Decisions (CI-gate registry, backlog policy, model registry) are committed conf a clone carries; GitHub supplies only interaction + auth | `.github/**/registry.conf` pattern; `tools/ci-gates` | A better reproducible store than the repo itself exists |
| N5 | The served site invents nothing and depends on nothing external | Every word/image traces to a provenanced committed file or first-party record; served bytes are vendored, no CDN; a broken local ref fails the build | `site/README.md` | Never |
| N6 | The tooling must not outgrow the designs it serves | New platform machinery must trace to a design need a real session hit; "interesting to build" is not a reason | This charter | The bench's purpose changes from co-designing parts to something else |

## Out of scope

**Deferred** — good ideas, not now (ranked in the backlog):

- The intelligent LLM router (flashx-as-router) and task proposal/assignment layer (issue #206 stretch).
- The team timeline as the history source (issue #126) that retires `people/work.conf`.
- Assembly-docs stage 4 — a real design shipping an `assembly.conf`.

**Never:**

- **A general CAD tool, a slicer, or a print-farm manager.** The bench co-designs
  parametric parts and proves them printable; it does not replace OpenSCAD,
  PrusaSlicer, or a fleet controller.
- **A marketplace / store / paywall.** Designs are open and gated for honesty, not
  merchandised.
- **Autonomy that merges its own design taste** (see N3), or a non-deterministic /
  CDN-dependent site (see N5), or copyleft in shared core (see N2). The "never"
  list is where the non-negotiables become refusals.
- **A second source of truth outside git** for any platform decision (see N4) —
  no console-only config, no state that a clone doesn't carry.

## What "working" looks like

Not a one-time definition of done — the health invariants a stranger can check:

- [ ] A design goes idea → merge-ready draft PR with the human reacting to a
      *shape*, never operating machinery.
- [ ] Every gate on a derived artifact is presence + freshness-by-construction
      (regenerated in the gating run), never a human's promise it's current.
- [ ] `check.sh` proves every claim the docs make about the tree (docs-drift,
      guard/mate negative controls, license boundary) — green means true.
- [ ] The autonomy loop has shippable work *and* a human gate: `/label-issues`
      arms, the burn ships, `needs-decision` parks what's Shai's.
- [ ] No platform feature is live that no design uses (N6) — or it's tracked to a
      design that will.

## Backlog, ranked by platform value

First-pass — ranked by how often a session is blocked or misled by the gap, not
by how interesting the build is. **To confirm with Shai.**

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Wire this charter in: `people/` co-founder entry + decide `/pm` reach (issue #272) | The PM has no mandate until it's registered and enforceable | small |
| B2 | Team timeline (#126) retires the interim `work.conf` | Provenance of who-did-what is currently a hand-maintained manifest | medium |
| B3 | First real `assembly.conf` design (assembly-docs stage 4) | A whole feature (#98/#156) is unexercised by any design — N6 risk | medium |
| B4 | LLM router + task proposal layer (#206 stretch) | Real leverage, but no session is blocked on it today | large |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| The co-founder is a new agent persona under Shai's merge authority — its name? | No | Placeholder until named; charter stands regardless |
| Charter lives at repo root (`PM.md`) mirroring per-design convention, vs `docs/` | No | Root, as drafted — closest to the pattern it extends |
| Does `/pm` get parameterized for the repo, or does the platform get its own thin enforcer? | Yes (B1) | Parameterize `/pm` to accept a repo-root charter; less machinery |
| When the platform PM and a design PM conflict, who arbitrates? | No | Shai — "customer of last resort" per `people/shai.md` |

## Decision log

Append-only. A later session must be able to tell a considered choice from an accident.

| Date | Decision | Reason |
|---|---|---|
| 2026-08-16 | Draft the platform charter as a co-founder mandate, not a founder self-charter | Shai asked for "someone to look after the bits I miss," not a restatement of his own authority (issue #272) |
| 2026-08-16 | Lead the non-negotiables with N6 (tooling must not outgrow its designs) as the PM's core instinct | It is the failure mode no single PR looks guilty of, which is exactly what a co-founder is for |
