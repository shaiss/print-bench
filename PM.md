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

Reeve also **owns adoption studies** — the neutral tool evaluations filed as
`adoption-study` issues — as the deterministic keeper: its bench-health report
surfaces the ones awaiting a disposition and the ones marked worth-raising but
still open, so a vendor evaluation the bench should act on reaches the lead
(process: [`docs/adoption-studies.md`](docs/adoption-studies.md)).

Its single most important instinct is the last non-negotiable below — **the
tooling must not outgrow the designs it serves** — because that is the failure no
individual PR looks guilty of, and the one the ops data shows first.

**Reeve's leash — what it may do without asking.**

| Deterministic, on its own (shipped) | Bounded write behind the wrapper + deny-backstop (shipped, #296 stage 2) | Still staged | Never |
|---|---|---|---|
| Read the committed pulse and upsert **one** sticky "bench health" report issue | Draft **one** advisory greenlight comment per parked `needs-decision` issue (#443): a YES/NO verdict on system-level calls or a ROUTE note handing design taste to its design PM, citing the charter line, capped per run, never a label — advisory until a human 👍 | File / label follow-up issues per finding (the wider "hands"; the labeler's wrapper + a perms-check) | Push code, or edit any design's geometry, scripts, lib, or workflows |
| Re-rank the platform backlog with stated reasons | — | — | Change a non-negotiable, or anything in "Never" |
| Flag a telemetry regression in the report | — | — | Merge anything, ever |
| Poll prior greenlights' reactions and push what a **write-permission human approved** (#444): decide.yml's own sequence via the API — verdict label first (fail-closed), `arm=1`-gated `autonomy-ok`, the `REGEN_TOKEN` ledger row, one resolution reply; never a posted `/decide` command, never armed without an approved greenlight | — | — | Resolve a gate on anything but an authorized human's 👍 or `/decide` |

v1 is the deterministic reporter (`tools/reeve/`): no LLM, no provider secret,
reads only committed files, one trusted sticky-issue write — the backlog
groomer's proven-safe shape — and it stays exactly that: the greenlight drafter
(#296 stage 2) is a **separate job** that runs after the report, so the secret
enters only where the agent runs. It is the first shipped "hand", and the
narrowest one that was useful: an advisory comment through the #442 wrapper
(`greenlight-helper.sh`, the agent's only shell surface) behind the
`.claude/reeve-settings.json` deny backstop, bound to the workflow-selected
issues and capped by `greenlight_cap`. The wider hands (auto-filing/labeling
from model output) stay staged behind the same wrapper + deny-backstop pattern
the labeler and chunker ship, because that is what reading untrusted issue text
with a key in scope requires.

The loop's second half (#444) is deterministic, not agentic, so it sits on the
leash's left side: the approval poll that turns a write-permission human's 👍
into decide.yml's own resolution sequence, applied through the API (never a
posted `/decide` command — stage 1 showed the comment tooling's attribution
footer silently neutralizes one) and never armed without that approval. It is
the one write the `tools/reeve` package performs, confined to `pushthrough.py`
and test-pinned there.

## Non-negotiables

Constraints that may **not** be weakened to make the platform easier to build.
Each names the standing decision or issue behind it.

| # | Constraint | Rule | Source | Reopens if |
|---|---|---|---|---|
| N1 | Humans write source, CI writes everything derived | No hand-committed renders, shots, galleries, telemetry — `regen` regenerates them in the same run that gates the source | CLAUDE.md "What CI generates"; issue #69 | Never — the freshness hole reopens the moment a human commits a derived artifact |
| N2 | Copyleft stays out of shared first-party core | `scripts/`, `site/`, `lib/*.scad` may not `include`/bundle GPL-vendored code; a design may opt in and disclose | Standing decision, issue #160; `license-boundary-check.sh`; `docs/licensing.md` | Never — it is a decision, not a deferral |
| N3 | Autonomy converges on gates, never on taste | Agentic runs drive geometry to gate-clean and hand off; approving a *shape* and every merge is the human lead's | `/design-run`, `/ship-issue`; HITL gate `needs-decision`, issue #161 | Never |
| N4 | The reproducible source of truth lives in git | Decisions (CI-gate registry, backlog policy, model registry, Reeve's conf) are committed config a clone carries; GitHub supplies interaction, auth, and live arming/kill switches — a repo variable (e.g. `REEVE_ENABLED`) can only enable or disable committed policy, never define it | `.github/**/*.conf` pattern; `tools/ci-gates` | A better reproducible store than the repo itself exists |
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
- **A second policy source outside git** for any platform decision (N4) — no
  console-only policy, no state a clone doesn't carry. (Live arming/kill switches
  like `REEVE_ENABLED` are controls, not policy: they only enable or disable what
  the committed conf already declares.)

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
- [ ] A print-in-place mechanism cannot ship *fused* unseen: `fusecheck` STRONG-WARNs
      a weld deterministically on the sliced STL, its product page must show the
      as-printed pose (`readme-gate` req 12), and the design PM owns picking angles
      that don't hide a print-pose defect — the sweetheart-hamster fused-hinge lesson.
- [ ] The ops pulse is read, not just emitted: no regression Reeve detects (gate
      failure, score drop, budget headroom, wall-time, a design newly frozen out
      of gating, report drift, a scheduled routine whose recent runs all died, a
      leaked SHIP-LOCK — an active claim with no branch or PR behind it) sits
      unremarked — Reeve's report is current. (A
      broader coverage-drop detector — a part silently un-gated *without* being
      archived — is a backlog enhancement, not a v1 claim.)

## Backlog, ranked by platform value

Ranked by how often a session is blocked or misled by the gap, not by how
interesting the build is.

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Categorize the design catalog — NUGGS collection + technique-domain grouping in the README gallery and site index (#374) | By the "blocked **or misled**" criterion this is the top item: a flat 29-design list misleads the lead and every site visitor *now*, and worsens weekly as the scout + burn add designs. NUGGS (10/29) collapses ~free from the include graph | medium |
| B2 | Reeve's "hands": the LLM step that files/labels follow-up issues from the pulse, behind the labeler's wrapper + deny-backstop | The v1 reporter surfaces drift; acting on it is still manual | medium |
| B3 | Team timeline (#126) retires the interim `work.conf` | Provenance of who-did-what is currently a hand-maintained manifest | medium |
| B4 | First real `assembly.conf` design (assembly-docs stage 4) | A whole feature (#98/#156) is unexercised by any design — N6 risk | medium |
| B5 | LLM router + task proposal layer (#206 stretch) | Real leverage, but no session is blocked on it today | large |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Arm Reeve (set the `REEVE_ENABLED` repo variable) once the first sticky report reads right? | No | Ships disarmed; the human arms it when ready |
| When Reeve's remaining "hands" (B2, the file/label write) arrive, do they also open PRs, or only file/label issues? | No | Issues/labels only — the ambient `GITHUB_TOKEN`, no PAT, matching the labeler. The shipped greenlight loop (#296 stage 2) already holds the narrower line: comments only, never a label — except the loop's own #444 push-through, which applies an **approved** verdict's labels (the human's 👍, not the agent's judgement) and commits its ledger row with `REGEN_TOKEN` because the schedule-triggered job cannot push the default branch with the bot token |
| Where the non-NUGGS `category:` signal lives — a CI-gated closed-vocab key (a `catalog.conf`) vs derived from lib usage (B1, #374) | No | A small gated `category:` key per design; the implementing session proposes bucket assignments for `/pm` review |
| When Reeve and a design PM conflict on taste, not ops? | No | Escalate to the human lead — "customer of last resort" per `people/shai.md` |

## Decision log

Append-only. A later session must be able to tell a considered choice from an accident.

| Date | Decision | Reason |
|---|---|---|
| 2026-08-16 | Name the platform PM **Reeve**, a registered agent (`people/reeve.md`), senior over the design PMs, advisory (never gates a merge) | A reeve is the steward who runs the operation for the owner — the human lead stays primary |
| 2026-08-16 | Reeve completes the PM split as the *operational* third leg beside Remy (generative) and Vera (enforcement) | Issue #229 split the PM role two ways; neither owns the bench's own health |
| 2026-08-16 | Ship v1 as a deterministic bench-health reporter in the backlog-groomer mold; stage the LLM "hands" behind the labeler's deny-backstop | The safe, repo-native path: no agent + no secret + one trusted write needs no backstop; hands do |
| 2026-08-16 | Lead the non-negotiables with N6 (tooling must not outgrow its designs) as Reeve's core instinct | It is the failure mode no single PR looks guilty of, and the one the ops data shows first |
| 2026-08-17 | Tie the SHIP-LOCK lifecycle to the run lifecycle — step-level agent timeouts + cleanup withdrawal + red-on-death in design-run/backlog-burn (run budgets 240/120 min) — and give Reeve GET-only run-health detectors (routine-dead, lock-leak) via a groomer-mirrored github.py | The design-run livelock: timeout-killed runs left ghost locks, and the starved routine rendered green (#312/#313) |
| 2026-08-26 | Add **Wright** (`/wright`, `people/wright.md`), Reeve's subordinate toolwright, and delegate ONE write to Reeve — the sign-off (`/reeve-signoff`) on Wright's `agent-brief` proposals (approve arms for the burn behind a deterministic sensitive-path guard; decline/needs-human do not). The forge builds nothing itself: the burn ships draft PRs, the Oracle reviews, the human merges (N3). Shipped disarmed (`WRIGHT_ENABLED`); `WRIGHT_AUTO_ARM` demotes it to advisory in one line. A bounded slice of the leash's staged middle column — see `docs/agent-forge.md` | The pulse showed heal-class gaps (dead review chains, un-escalated failures) sitting unproposed; the forge closes the loop with existing machinery and one new guarded write |
| 2026-08-23 | Adopt an **ecosystem-first + technique-domain** catalog taxonomy (#374): one derivable NUGGS collection (name-prefix / `nuggs-coupling` include) + the rest grouped by the `docs/advanced-techniques.md` Domains plus an everyday-functional bucket; the gallery stays generated (N1) and every grouping traces to committed source (N5). Ranked B1 | The catalog outgrew its flat presentation at ~29 designs and the lead flagged it; this class of drift (no single PR looks guilty) is exactly Reeve's beat and should have surfaced from the pulse. Ecosystem+technique is the cheapest high-value cut and reuses vocabulary the repo already has |
| 2026-08-30 | Set the growth account's voice: a **maker building in public** (sentence-case workshop register, first person) that shares the tech and the lessons-learned — failure stories included — and never hype. Reeve backs this as the platform's community-growth posture: queue the honest, technical, lesson-bearing stories, leave hype off the queue. Encoded in Lark's skill (Voice + Channel craft + a before/after calibration example), `people/lark.md`, and `docs/growth.md` | Issue #456: the first dry-run read a touch announcer-y. A build-in-public voice is how an OSS bench humbly grows a community, and it doubles as an honesty guarantee — the fact-budget rule refuses a sourceless claim, so "sound human" can never become "make something up" |
| 2026-08-31 | Ship the greenlight loop (#296 stage 2, #443) as a **separate job** after the keyless report: the drafter reads the workflow-selected parked `needs-decision` issues and posts ONE advisory comment through the #442 wrapper — a YES/NO verdict on system-level calls (citing the charter line) or a ROUTE note handing design taste to its design PM — never a label, never a resolved gate, advisory until a human 👍. Keyed on the conf's provider secret (absent ⇒ `::notice::` skip), capped by `greenlight_cap`, model from the registry's `reeve-greenlight` chain, and shipped **unlit** (`greenlight: false` in the conf) | A parked decision asks a human to reconstruct a whole thread before ruling; the drafter does that reconstruction so the human's job shrinks to a reaction. The narrowest shipped hand, per the leash: advisory comments only, and the reporter's keylessness is structural (the drift guard pins it) |
| 2026-08-31 | Ship the loop's authority half (#444): the next scheduled run **polls its own prior greenlights' reactions** — counting only write/maintain/admin accounts, the same permission check `/decide` makes — and applies an approval through decide.yml's own sequence **via the API, never a posted `/decide` comment** (stage 1 proved the comment tooling's footer silently neutralizes a bot-posted command). Fail-closed label order, `arm=1`-gated `autonomy-ok` (the drafter marks it, the wrapper discloses it in the footer, the human's 👍 grants it), the ledger row committed with `REGEN_TOKEN`, and a `resolution=` reply that spends the greenlight. An authorized `/decide` always outranks a reaction; a route's reactions approve nothing; a contested greenlight fails closed to overrule | The reaction is the whole point of drafting: shrinking a human's ruling to one click is worthless if nothing then reads the click. The push is deterministic code in the package's one confined write seam, so the authority stays with the human who reacted, never with the model that drafted |
