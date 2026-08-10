---
name: design-run
description: The idea→PR pipeline (issue #96, Stage 3) — take one well-formed design-brief issue through the whole co-design loop autonomously and land a gated draft PR the human only has to react to and merge. Composes /intake, /new-design, the co-design loop, /pm, the reviewer skills and /preflight; it never approves a shape on the human's behalf. Use when asked to run a design end-to-end from a brief, to turn a design-brief issue into a draft PR, or when invoked as /design-run [issue-number | idea].
---

# Design run — one brief in, one gated draft PR out

You take **exactly one** `design-brief` issue and land a draft PR that a human
only has to *react to and merge*. This is the flagship autonomy loop of the
repo (issue #96): idea in, gated draft PR out. The bet is **orchestration, not
capability** — you compose skills that already exist (`/intake`, `/new-design`,
the CLAUDE.md co-design loop, `/pm`, the reviewer skills, `/preflight`) rather
than inventing new machinery.

Read this boundary first, because everything below serves it:

> **You converge on gates, never on taste.** The one thing this skill must not
> do is approve a *shape* on the user's behalf — that is exactly what
> `/ship-issue` declines a design for. So you drive the brief to the point where
> the geometry is **gate-clean** (renders without CGAL errors, passes printcheck
> and a test-slice, has a product page that passes `readme-gate.sh`), attach the
> previews, and **hand off**. The human's approval *is* the merge. You never
> block mid-run waiting for someone to say "yes, that's the right shape"; you
> produce a gated artifact and stop.

This skill runs the same attended (a human invoked it) or unattended (the
scheduled `design-run.yml` workflow did). Section 8 says what tightens when
nobody is watching. It shares the one-claim lock protocol with `/ship-issue`,
so the two never collide on the same issue.

## 0. Claim exactly one brief

1. **A named issue is the only candidate.** If the invoker named one it is that
   issue or nothing: if it fails any check below, stop and report *that* issue.
   Never fall through to a different one. Only an unnamed invocation selects per
   §1. (An invocation with a raw idea and no issue is §1's "no brief yet" path.)
2. **Baseline** — clean worktree (`git status --porcelain` empty, untracked
   included) on a branch freshly based on the current default branch. The
   contract's timestamp only proves it predates the diff if there was no diff
   when you posted it.
3. **Lock check** — the issue is taken if any of these hold, and the protocol is
   byte-for-byte the one `/ship-issue` §0 uses so a burn and a hand-run cannot
   both claim it:
   - **an active claim marker** — read the *latest* `🚢 SHIP-LOCK` comment and
     act on that one. `🚢 SHIP-LOCK` is active and the issue is taken;
     `🚢 SHIP-LOCK WITHDRAWN` is released and blocks nothing. An active claim
     more than a few hours old with **no** `claude/issue-<N>-*` branch and **no**
     open PR closing the issue is *stale* — take it over, naming the one you
     superseded.
   - **an open PR closes it** — read the issue's linked-PR metadata (GitHub's
     nine closing keywords, case-insensitive), don't grep the body.
   - a remote branch `claude/issue-<N>-*` already exists.
4. **Claim it** by posting the §2 contract as a comment led by `🚢 SHIP-LOCK`,
   **before you scaffold a single part**. Keep **one active claim** per issue at
   a time — never delete a claim comment (the timestamps are the record),
   withdraw it instead. The timestamp is the proof the contract predates the
   diff.
5. **Re-read after claiming.** Check-then-post is not atomic. Re-read the
   comments; if another *active* claim predates yours, withdraw (edit your
   comment so its first line reads `🚢 SHIP-LOCK WITHDRAWN` — never delete it)
   and stop. Last writer yields.
6. **Release on a terminal stop.** If you stop for any reason *before* a
   `claude/issue-<N>-*` branch or an open closing PR exists — a §1 decline, a
   §4 non-convergence, any §8 stop — **withdraw your claim** the same way (edit
   the first line to `🚢 SHIP-LOCK WITHDRAWN`). A run that claimed then walked
   away must not leave the brief frozen until it ages into a stale takeover; the
   branch/PR is what carries the claim forward once real work exists.

If the issue is taken, say so and stop. Never work two.

## 1. Select — can this brief be run to a gated PR?

The input to this pipeline is a **well-formed `design-brief` issue** (the
`templates/design-brief.md` shape `/intake` and the issue form produce). Judge
the brief, not the idea:

**No brief yet** (invoked with a raw idea, or a bare idea-issue with no brief
body): this skill does not model from a one-liner. Run `/intake` to produce the
brief issue first, then either continue from that issue (attended) or stop and
let the scheduled run pick it up (unattended). Filing the brief is a legitimate
outcome; guessing the measurements is not.

**Take it** when the brief is well-formed by `/intake` §6's bar: every
*Must fit / hold* row is given-with-source or assumed-with-a-stated-default, the
*Style* line is a decision (a pack, `none`, or `new — lift …`), and *Open
questions* has **no blocking entry**. You can name the finished state — the
parts, their fits, the gates that must pass — from the brief text alone.

**Decline it** — comment saying why, don't half-do it:
- **A blocking open question.** The brief itself says modeling can't start until
  it's answered. Ask it on the issue and stop. Non-blocking questions are fine;
  proceed on the stated assumption and note it.
- **A bare number of unknown provenance**, or a *Must fit / hold* dimension
  marked neither given nor assumed. A fit you can't source is a shape you'd be
  guessing. Send it back to `/intake`.
- **`Style: new — lift from <ref>`** with no style pack yet. The lift is a
  human-taste step (`/style-spec`); it is not this skill's to run blind. Stop
  and say the lift must land first.
- **Bigger than one reviewable design PR** — several independent parts that are
  really separate designs. Propose the split (the briefs you'd file) and stop.

A brief nobody can run in one PR is a triage result, not a failure. Reporting it
is the deliverable.

## 2. Freeze the scope contract — before scaffolding

Written from the **brief thread only** (body plus comments; an owner comment
settling an open question is part of the spec — quote it). What must stay out is
the *geometry you're about to write*: decide the done-state from the brief, not
from the shape you already have in mind.

```markdown
🚢 SHIP-LOCK — running this design to a gated draft PR.

**Design name:** <kebab-case>
**Brief parts:** <the First-pass part breakdown, as the contract's part list>
**Style:** <the pack, or `none`>

**Gate contract** (done = every box passes a command, not a reading)
- [ ] G1 — `render.sh <name>` completes, no CGAL errors, bottom-iso inspected
- [ ] G2 — `gate.sh --slice <name>` exits 0 (printcheck + test-slice) for every
        printable part, including any tuned-fit coupon
- [ ] G3 — `readme-gate.sh <name>` passes (product page: title, pitch, preview,
        Print settings, Parameters)
- [ ] G4 — every *Must fit / hold* dimension is realised in a parameter with
        its unit, and the built mesh measures within tolerance of the brief's
        number (measure the export, not the variable)
- [ ] G5 — `/preflight` green

**Touches:** designs/<name>/** (and lib/ only if a fit genuinely belongs there)
**Explicitly not in scope:** <adjacent designs, look changes beyond the named
style, anything the brief left to Open questions — each with where it goes>
```

Every gate is a command or a measurement. "Looks right" is never a gate — that
is the human's merge decision, by construction.

## 3. Scaffold

Run `/new-design <name>` — entry `.scad` from `templates/design.scad`,
`NOTES.md` recording the brief's goal / given measurements / print orientation,
`README.md` from `templates/README.md`, and `ci.parts` / `printcheck.args` when
the design has distinct printable parts. If the brief names a style, wire it in
now (`designs/<name>/style.conf` + `include <styles/<style-name>/style.scad>`,
where `<style-name>` is the pack the brief named — independent of the design
name) —
retrofitting a look later means redoing the geometry (CLAUDE.md, co-design
step 1). Record the brief's given numbers as parametric variables with units.

## 4. Iterate to gates-green — the reactor is the gate, not a person

This is the CLAUDE.md co-design loop (step 3) run with the *gate* as the thing
you react to, because the human isn't in the loop yet:

Each iteration:
1. `render.sh <name>` → **look at the bottom-iso view yourself** for overhang /
   bed-contact problems, and check the shape against the brief's numbers. If
   `render.sh` itself *fails* (a CGAL/geometry error), that error **is** this
   iteration's finding: fix the `.scad` and re-render — don't run `gate.sh` or
   capture telemetry on a render that never produced a mesh to inspect.
2. `gate.sh --slice <name>` for the printable parts.
3. **Capture the iteration as telemetry** (this is the #93 consumer #96
   anticipated — it turns "is this converging?" from a vibe into a reading).
   Pick a fresh per-run log path once (`RUN_NDJSON=$(mktemp)`, reused every
   iteration so the records accumulate in order) and a per-iteration gate log,
   and **fail closed** — `pipefail` so a `gate.sh` failure isn't masked by the
   `tee`, and a capture failure stops the run rather than letting convergence
   read stale data:
   ```bash
   set -o pipefail
   ITER_LOG=$(mktemp)                       # one per iteration
   # RUN_NDJSON set once at the start of the run: RUN_NDJSON=$(mktemp)
   ./scripts/gate.sh --slice <name> 2>&1 | tee "$ITER_LOG"; gate_status=${PIPESTATUS[0]}
   ./scripts/telemetry.sh capture --gate-log "$ITER_LOG" \
     --out "$RUN_NDJSON" --meta event=design-run --meta iter=<n> --meta design=<name> \
     || { echo "telemetry capture failed — stop, don't trust the trend"; exit 1; }
   ```
   A non-zero `gate_status` is a failing gate (expected while iterating — it is
   the signal you're converging on), not an error to abort on; a failed
   *capture* is, because the convergence rule below would then read missing or
   stale telemetry. Read the trend across the accumulated records —
   `gate.parts[].score` rising and `criticals` / `fail_lines` falling is
   **progress**; the same failure reproduced with no score movement is
   **thrashing**.
4. Adjust the `.scad` and go again.

**Convergence — bounded so a bad run costs one stalled PR, not an infinite
loop:**
- **Progress → keep going.** Any iteration that clears a gate that was failing,
  or moves a printcheck score up while criticals fall, is progress.
- **Thrashing → stop.** If **3 consecutive** iterations produce no telemetry
  progress on the blocking gate (same criticals, no score gain), you are not
  converging. Stop; do **not** push a half-green PR. Comment the current state,
  the telemetry trend, and the specific gate you're stuck on (§8 governs the
  unattended stop).
- **Hard cap.** Never exceed **8** gate iterations regardless — the cap is the
  backstop for a trend that oscillates without repeating exactly. Hitting it is
  a stop-and-report, same as thrashing.

A design whose brief was well-formed but whose geometry won't come clean in the
bound is telling you the brief under-specified something. Report *that*, with the
telemetry, rather than forcing green.

## 5. Product page + PM / reviewer checkpoints

- **Product page.** Complete the README scaffolded in §3 so `readme-gate.sh`
  passes: the pitch, **Print settings**, **Parameters** worth tuning, and a
  preview. Declare the hero shot in `shots.conf` and the frozen previews in
  `previews/cameras.conf` — **CI renders and commits the images**; you own the
  manifest and the embed, not the pixels (CLAUDE.md: "what CI generates").
  - **The regen handoff (read this unattended) — a preview is a prerequisite,
    not a nice-to-have.** `readme-gate.sh` requires an embedded preview, and it
    runs inside `/preflight` (§6), which is a hard stop — so a design with no
    preview never reaches §7 anyway. Get the preview to exist *before* you ship,
    in this order:
    1. **Generate what you can locally.** Frozen `previews/cameras.conf` shots
       render with `render.sh <name> --previews` (plain OpenSCAD, no `bpy`) —
       commit those. Most designs can satisfy the gate this way with no CI at
       all. (Path-traced `shots.conf` product shots need `bpy`/CI; don't
       hand-fake them.)
    2. **If a required preview can only come from CI `regen`, it needs a PAT.**
       The scheduled `design-run.yml` runs the agent with the default
       `github.token`, and a push/PR authored by `github.token` **does not
       trigger `ci.yml`** (the same reason `regen` uses `REGEN_TOKEN` — see
       CLAUDE.md), so `regen` won't fire on your draft PR. With a PAT wired as
       `github_token`, CI regenerates and commits the shot as usual.
    3. **No PAT and the gate still needs a CI-only shot?** Then `/preflight` is
       red and §8's hard stop applies: **do not open an image-less draft PR**
       that fails its own gate — stop, withdraw the claim (§0.6), and report the
       credential-gated run on the issue so a maintainer can wire the PAT or run
       it attended. Never hand-commit product shots to fake the regen.
- **`/pm` checkpoint.** Run `/pm <name>` against the brief before you push:
  scope not crept past the brief's parts, the named non-negotiables honoured.
  Cheap, and it catches the design drifting off the brief.
- **Reviewer self-pass (optional, recommended).** `/jane-review` on the design
  directory catches the printability foot-guns (bed exclusion, seams, bridge
  angles) a gate score alone misses. Fold in what it finds; it is not a merge
  gate here.

## 6. Verify — two independent passes

**Pass A — would CI pass?** Run `/preflight`. It owns the check set and the
scoping; do not keep a competing list. Red is a stop.

**Pass B — brief audit, both directions.** Over every path this branch touches:

| direction | question | failure it catches |
|---|---|---|
| diff → brief | does every changed file serve a named part / gate in the contract? | creep — a second design, an unrelated lib edit |
| brief → diff | does every *Must fit / hold* row map to a parameter, and every gate pass with **measured** evidence? | under-delivery — a dimension silently dropped, a gate asserted not run |

Evidence means a re-derivation from the exported mesh (facet measurements,
printcheck output, slice result), never the parameter you just typed — issue
#37's lesson. Anything unmapped: revert it, or file it, before the PR exists.

## 7. Ship

Draft PR, base = default branch, title stating what the design *is* (not
"closes #96"). Body:

1. `Closes #<N>` on its own line.
2. The frozen contract with every gate box passing, **linking the claim
   comment** so a reader sees it predates the diff.
3. The §6 brief-audit table — file → part, and *Must fit / hold* row → the
   measured number off the export.
4. The preview images (once CI has committed them), the `/preflight` verdict,
   and anything deferred with its follow-up issue link.

Then `subscribe_pr_activity` and drive it to green per the PR-ownership rules —
a PR you opened is yours until it merges or closes. The human's job from here is
what #96 promised: react to the previews and merge.

## 8. Unattended mode (the scheduled workflow invoked this)

Same skill, three tightenings — nobody is there to catch a wrong guess:

- **Never guess past an ambiguity, and never approve a shape.** Attended, a
  judgement call can wait for the human; unattended, if the fork is a binary
  yes/no a human can settle, raise it through the HITL gate (§9) — a
  `🚦 DECISION NEEDED` that is machine-resumable — and stop; otherwise it is a
  `🚢 DECLINED — needs a decision` comment naming what's unresolved, and a
  clean stop. Taste — "is this the right shape?" — is *always* the human's, so
  unattended you ship only what the gates certify and stop; you never invent a
  design decision the brief didn't make.
- **Hard stop conditions:** a blocking open question (§1); the geometry not
  converging inside §4's bound; `/preflight` red after one honest fix attempt;
  the diff outgrowing `Touches` in a way that isn't a legitimate consequence of
  the brief; a `Style: new` brief whose lift never landed. Stop and comment —
  never push a design you'd have to apologise for.
- **The issue thread is the only log.** Assume nobody reads the run output.
  Claim, amendments, the telemetry trend at a stop, declines, and the final
  verdict all land as comments, each readable cold.

A stopped run costs nothing; a confidently wrong design PR costs a review and,
worse, teaches the human to distrust the pipeline. When unsure, decline.

## 9. Decisions that need a human (the HITL decision gate)

A design run hits forks the brief did not settle — a fit ambiguous between two
readings, a scope edge the charter is silent on, a choice between two ways to
realize a *Must fit / hold* row. Section 8's `🚢 DECLINED — needs a decision` is
the human-readable form of that stop; the repo's HITL gate
(`docs/decision-gate.md`, issue #161) gives its **binary** form a single
findable place and an authoritative answer, so a parked decision is
*machine-resumable* instead of a dead-end comment. Use it for a yes/no a human
can settle; **not** for taste — "is this the right shape?" is always the
human's merge decision, never a `/decide` — and not for anything with more than
two live answers (decline and ask, don't enumerate).

**Raise** — at the fork, before anything else:

1. Pick a stable **kebab-case id** unique on this thread
   (`[a-z0-9][a-z0-9-]*`, e.g. `bay-width-42-vs-44`). The id is the key the
   resuming run looks up.
2. **Ensure + add the `needs-decision` label** with the `ensure-label` idiom
   (enumerate with `gh api --paginate repos/<repo>/labels`, create only if
   absent — **not** `gh label list`, which caps at 30 and would fall through to
   a 422), then add it:
   ```bash
   .claude/skills/chunk-issue/chunk-helper.sh ensure-label needs-decision
   gh issue edit <N> --add-label needs-decision
   ```
   The label is unspoofable (write access to set) and is what the backlog-burn
   selector keys its durable pause on.
3. Post a **`🚦 DECISION NEEDED — \`<id>\``** comment with **exactly two**
   options — the yes and the no — each saying what ships if chosen, enough
   context (what the gates/telemetry say) to answer without scrolling, and the
   resolve line:
   ```markdown
   🚦 DECISION NEEDED — `bay-width-42-vs-44`

   **Question:** <the fork, phrased as a yes/no>

   **yes** → <what ships if yes>
   **no**  → <what ships if no>

   **Context:** <one or two lines — gates/telemetry, why this is a human call>

   Resolve with `/decide yes bay-width-42-vs-44` or `/decide no bay-width-42-vs-44`.
   ```
4. **Halt cleanly.** This is a terminal stop before a branch/PR exists, so
   **withdraw the claim** per §0.6 (edit the SHIP-LOCK's first line to
   `🚢 SHIP-LOCK WITHDRAWN`); the `needs-decision` label is the durable pause
   now. Then stop. Do not push a half-resolved design PR.

**Consume** — a later run that reclaims this brief resumes by reading the
verdict, not by re-asking:

1. Scan the thread for `🚦 DECISION NEEDED` comments; collect the ids.
2. For the id you are resuming at, read its verdict. The
   `decision-approved` / `decision-rejected` **label** is the authoritative,
   unforgeable verdict (`decide.yml` sets it); the **ledger**
   (`.github/decisions/ledger.conf` — `<id> | approved|rejected | #<issue> |
   <login> | <iso8601>`) is how you look up a *specific* id, since the label is
   per-thread and reflects only the latest:
   ```bash
   grep "^<id> |" .github/decisions/ledger.conf
   ```
   If label and ledger disagree, the **label wins** — flag it and take that
   branch.
3. **Take the chosen branch** and proceed. `rejected` picks the "no" branch
   (often "leave the default" or "file as backlog item N"), a real outcome the
   run continues from.
