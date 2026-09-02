# Sweetheart Hamster — product charter

## The product, in one paragraph

A palm-sized chibi-hamster jewelry box that **hoards a heart instead of seeds**,
for **the proposer** — someone with a ring hidden in a drawer and a date circled
on the calendar, printing this the week of. The one thing it must do well is
**the reveal**: hand over a closed hamster, watch them fold it open along the
spine so the ring lifts out of a heart-shaped scoop. It is a ceremony object,
not a daily fidget — a handful of folds in its whole life — so it optimizes for
that one moment and a long life on a shelf, not for hinge endurance.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Prints supportless, flat, one piece | body prints with no support; nest ceiling is the only optional-support zone | repo FDM defaults; NOTES | the massing changes so a face can't self-support |
| N2 | The fold axis clears the model top | `hinge_z*S` > max mesh z (ears, 60.13 mm) | v0.1 fused-hinge RCA; `ci.fusecheck` | never — below the top, material welds across the seam |
| N3 | The cut faces land on the bed (real first-layer contact) | intended-contact area at true z=0, not hovering | v0.2 bed-hover RCA (Jane) | never — a floating first layer doesn't adhere |
| N4 | Mechanism + preview honesty | the as-printed `contact-sheet` is shown, not only a posed hero | repo req 12; the design's own v0.1 lesson | never |
| N5 | Hinge material is disclosed | PETG/PP fold; PLA is a tear-line | README; field experience | never |

## Out of scope

**Deferred** — good ideas, ranked in the backlog below.

**Never:**
- **A many-cycle hinge** (e.g. the captive-pin `pip_hinge` variant). The usage
  math says ~5 folds ever; a durable hinge solves a cycle count this object does
  not have. Recorded so a later session does not re-litigate it.
- **A marketed "holds any ring" claim** without sizing guidance — the nest is a
  tuned pocket (`nest_w`), not a universal fit.

## v1 — definition of done

Separate from "the gate is green" (necessary, not sufficient):

- [ ] `gate.sh --slice` green (printcheck, fitcheck, fusecheck, test-slice).
- [ ] The as-printed pose is shown on the page (contact-sheet embedded).
- [ ] **One field test:** a real ring seated and the closed box carried around
      the block without opening — OR nest-on coupon evidence — logged as a
      FIELD-TEST entry. This is Drik's sign-off condition: "nestles a ring" is
      the claim the whole page rests on and it cannot be proven inside a PR.

## Product page & shots (art direction)

**Page promise.** *A hamster that hugs a heart — and hands one over.* The reveal
sells it; the closed hero leads, the open-heart shot proves the mechanism.

**Mechanism honesty.** The `contact-sheet` (as-printed flat pose) is embedded
and stays embedded. The closed hero omits the folded hinge tab — discharged for
now by a README line; the honest richer fix is a `fold=85` closed-pose shot
(backlog B3, a **new** frozen camera, never a reframe of the hero).

**Shot list — tier 1.** hero (closed 3/4), front (face-on), open-heart (fold=35
reveal), contact-sheet (as-printed). Frozen; add rows, never repurpose.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Closure / friction detent + ring retention | The hot path is cycle #2 (the handover); a box that flops open pre-spoils the surprise, and a loose ring rattles | v0.3 geometry |
| B2 | Nest-on coupon variant | The coupon insures the hinge but ships `nest_on=false`, so the payload fit is untested until the full print | new gated part |
| B3 | `fold=85` closed-pose hero + seam close-up (new cameras) | Shows the hinge tab the closed gift actually carries; the bed-level parting-gap close-up (a slice of each island in frame) is the visual anchor every flare-vs-gap round has lacked — the 0.5 mm seam is sub-pixel at whole-part scale | two new `cameras.conf` lines, one camera pass |
| B4 | Rattle / concealment revisit | A snug band (B1's `nest_w` guidance) barely rattles; confirm after the first field test | page + field test |
| B5 | Page tips: cold-PLA clause, two-color pause-and-swap belly heart, won't-part ladder consolidation | Cheap honesty + a nice gift trick; one canonical ladder telling in **First layer** with the `part_gap` cell and the Assembly paragraph pointing there — five homes is five chances to re-drift; ride the next page pass | page only |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Add a friction detent in v0.3, or keep it a carry-flat gift? | No | Carry-flat for now; detent is B1, the human's design call |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-23 | v0.2: raise `hinge_z` above the ear-top | v0.1 hinge printed fused; material above the fold axis welded across the seam |
| 2026-08-23 | v0.2: land the cut faces on the bed (`translate([0,0,-gg])` in `half_flat`) | halves hovered 0.25 mm; only the web touched the plate, so the first layer wouldn't adhere |
| 2026-08-23 | `pip_hinge` stays deferred | ~5 folds ever — a many-cycle hinge solves a problem this object doesn't have |
| 2026-08-29 | Round 4 (post-merge, PR #411): the NOTES supports straggler and the README tack-break flex direction ruled act-now as one copy-only follow-up commit on main (round 3's clause had merged unlanded); seam close-up camera routed to B3's camera pass, five-home ladder consolidation routed to B5 | The round-4 PM triage's ruling; the copy edits landed as #462 |
