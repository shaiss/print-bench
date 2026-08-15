# sushi-battleship-tracker — product charter

## The product, in one paragraph

A shot-tracker refit of the archived [sushi-battleship](../sushi-battleship/)
(frozen at v0.1): every print-in-place shutter door gains a shallow spherical
seat that parks a small round marker — a dried soybean, a 6 mm BB, a
peppercorn — on any cell that has been called. The customer is the same two
players eating battleship off the original board, whose actual failure mode
is "wait, did we already call B3?": the original tracks hits (the door is
open and the sushi is gone) but leaves misses to memory. One thing it must
do well: mark a called cell without leaking any hidden information or
touching the tuned sliding fit.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Fit surfaces inherited byte-for-byte: door body/tab dims, rails, lips, clearances untouched | tab/lip/clearance params all inherited, door() restates them verbatim | parent NOTES.md + lib/print-in-place.scad acoustic-property note: clearances are tuned; a refit that re-tunes them re-opens the whole coupon cycle | the parent is un-frozen and its fit derivation changes |
| N2 | Fog of war intact: the seat encodes nothing about cell contents; markers are public state only | seat identical on all 16 doors | /drik-review information-leak rule; hidden-information game | the game itself changes to open information |
| N3 | Door floor under the seat stays printable | ≥ 1.2 mm (assert in .scad) | FDM min-feature rule (CLAUDE.md); door_t = 2.4 | door_t grows |
| N4 | Nothing new above rail height — the lid must stack/store as before | grip bar unchanged at 2.4 mm; seat is a cut, adds 0 height | parent geometry: rails clear the grip by 0.3 mm | rail_h derivation changes |

## Out of scope

**Deferred** — printed marker pegs as a fourth part (the parent's frozen
part-selection else-branch draws the assembled preview for any unknown
`part` value, so a clean `-D part=peg` render needs machinery this refit
doesn't want to invent; household markers work today). Ranked B2.

**Never** — transparent or windowed doors, and any per-cell geometry that
varies with contents: both are wallhacks in a hidden-information game
(N2). Also never: re-tuning rail/tab clearances "while we're here" (N1).

## v1 — definition of done

- [ ] `gate.sh --slice` green: bottom, top, door, coupon all watertight, sliceable
- [ ] Derivative gate proves `replaces: top, door` by mesh comparison (and `bottom` is deliberately unclaimed)
- [ ] Seat holds an 8 mm marker on a flat table without rolling (field-test on the coupon)
- [ ] Product page documents the delta only and links the parent for everything else

## Product page & shots (art direction)

**Page promise.** "The board you already printed, but nobody re-calls a
cell": a reader who knows the parent should instantly see the one new
feature — the marker seat — and understand nothing else moved.

**Shot list — tier 1 (real studio renders).** Ranked; the first is the hero.

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the full assembled board, one shutter open — same promise as the parent, new colorway so the pages don't blur together | three-quarter | crimson / satin | `part="assembled"` |
| seat-detail | the delta itself: door tops with the dished seats, close enough to read the coordinate engraving | detail | crimson / satin | `part="top"` |

**AI product stills — tier 1.5 (AI, bare product, disclosed).** The bare part,
no scene, image-to-image seeded from a tier-1 render — the angle is whichever
tier-1 shot each still seeds. Shown on the page beside the studio render; a
lifestyle scene may later seed from one of these.

| Still | Seeds from (tier-1 shot) | Prompt/notes |
|---|---|---|
| hero | product-hero | the full assembled board, bare on a seamless studio sweep — the clean "here's the object" shot |
| seat | seat-detail | close on the dished marker seats and shutters, bare, raking light for the FDM texture |

**Lifestyle scenes — tier 2 (AI, cosmetic, disclosed).** Optional. `Seed` names
the render each scene starts from (a tier-1 shot or a tier-1.5 product still).

| Shot | Seed | Scene |
|---|---|---|
| product-hero | product-hero | the board mid-game on a dinner table, soybeans parked on a few closed shutters, sushi and soy dishes around it |

**Motion clips — tier 2 (AI, cosmetic, disclosed).** Optional; only motion
the print really performs — shutters slide along their rails, markers settle
into seats. Nothing that would leak hidden information (N2).

| Shot | Seed | Scene/Motion |
|---|---|---|
| product-hero | product-hero | mid-game on the dinner table: one shutter slides open along its rail, a soybean settles into a closed shutter's seat |

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Field-test the seat depth against real dried soybeans (size varies 7–9 mm) | it's the whole feature; the coupon makes it a 40-min print | one coupon print |
| B2 | Printed marker pegs as a separate part | household markers already work; needs part-selection machinery (see Out of scope) | new part + CI wiring |
| B3 | A second seat per door for hit/miss two-marker play | speculative; one marker per called cell covers the base game | geometry + re-review |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Default marker: soybean (8 mm) vs BB (6 mm)? | No | 8 mm default; `marker_d` is a parameter and the coupon is the tuning loop |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-08 | Contribute as a derivative, not an in-place edit | the parent is ARCHIVED at v0.1; the marker itself names the derivative route as the revival path |
| 2026-08-08 | Claim only `top` and `door` in `replaces:` | the tray is inherited unchanged; claiming an unchanged part is exactly the failure the gate reads as a typo'd override |
| 2026-08-08 | Seat is a cut, not a raised feature | adds zero height (N4), no new overhangs, and can't affect the sliding envelope (N1) |
