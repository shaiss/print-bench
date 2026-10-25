# tslot-cable-clip — product charter

## The product, in one paragraph

A snap-in cable-clip family for standard 2020 T-slot aluminum extrusion:
one hammer-head lug slides into the rail's side slot and a closed snap loop
routes a common cable along the rail — no zip ties, no adhesive,
repositionable by sliding. For anyone building with 2020 extrusion
(printers, enclosures, workbenches) who wants cables managed on the frame
itself. The one thing it must do well: **hold a vertical cable run without
the cable falling out and without the clip leaving the rail.**

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Slot geometry is the E2020 table, never hand-measured | mouth 6.0, cavity 12.0, depth 8.0, lip 2.0 mm | NopSCADlib E2020 via `extrusion-shelf-bracket` NOTES | A measured rail disagrees — then the *table* is wrong, fix the table |
| N2 | Body height above the rail face | ≤ 14 mm | brief #836 (clear of adjacent T-nuts/brackets) | A real adjacent bracket is shown taller |
| N3 | Prints as-modeled, no supports, vertical walls only | 0 support faces > 45° | repo design convention; the flex tabs must not bridge | — |
| N4 | Tab flex bends in the layer plane (CC1) | plan-profile extrusion, never a folded print | `snap-cantilever-clip` rule, CLAUDE.md | — |
| N5 | Tuned fit ships with a print-this-first coupon | `slot_fit_tol` + `cable_fit` ladders | repo convention | — |

## Out of scope

**Deferred** — backlog below.

**Never** — adhesive-backed variants, non-2020 slot families (3030 etc.:
that is a *new design* parameterised the same way, not this one), zip-tie
loops (the point is to replace them).

## v1 — definition of done

- [x] Three stations (Ø4 / Ø6.2 / Ø8) gate green: printcheck + test-slice
- [x] Lug proven against the E2020 slot negative (`ci.fitchecks`, with a
      deliberately oversize negative control)
- [x] Standoff ≤ 14 mm measured on the export
- [x] Coupon ships the two tuning ladders (`slot_fit_tol`, `cable_fit`)
- [x] Product page passes `readme-gate.sh`; plate (3MF, separate objects)
      is the stated deliverable
- [ ] One real rail + real cable field test recorded in NOTES (post-merge;
      the coupon exists to make it cheap)

## Backlog (ranked)

1. **Field test + tolerance report** — print the coupon on the owner's
   rail, record a FIELD-TEST entry; tune `slot_fit_tol` default if 0.15
   proves tight on common rails.
2. **6.2-slot preset** — a documented parameter pair (`slot_mouth=6.2`,
   `slot_fit_tol=0.20`) rather than a new design.
3. **Two-lug comb** — longer body, two lugs, for stiff bundles; brief
   names it as a follow-up. Needs its own standoff check.
4. **Station Øs re-picked per field feedback** (brief allows a session to
   re-pick; keep three).

## Open decisions

- **Snap loop vs drop-in** (brief left open "on coupon evidence"): decided
  **snap loop** on geometry — a vertical rail run falls out of an open
  loop, the exact failure the clip exists to prevent (NOTES decision 1).
  The coupon still prices the feel. *Recorded 2026-10-16; the human's
  merge review is the approval this waits on.*

## Product page & shots (art direction)

The page must show: the clip **on a rail** (the installed pose — what the
buyer recognizes from their own frame), the **mouth detail** (funnel +
throat + tabs — the mechanism that differentiates it from a zip tie), and
the **coupon** (the honest "print this first" step). Tier-1 frozen
previews carry all three (`previews/cameras.conf`: installed / mouth /
fin / coupon / family / contact-sheet); no AI tiers in v1 — the mechanism
is the product, and geometry-true renders are the whole sales pitch. A
`shots.conf` studio hero can land post-merge via CI regen.

## Decision log

- 2026-10-16 — charter written from brief #836 at pre-ship PM checkpoint;
  snap-vs-drop-in recorded as the one open decision (decided, awaiting
  merge review).
