# nuggs-orrery — product charter

## Customer

A NUGGS builder with a dual-nozzle printer who wants the showpiece module
of the run — the one that demonstrates what the printer can do — without
compromising one millimetre of the welfare standard the system is built on.

## Non-negotiables

- **N1 — the bore is the standard's bore.** `nuggs_cfg()` defaults,
  bore-clean end to end, no interior features. Enforced by the library's
  own asserts plus the mandatory `nuggs_bore_cut()` (source:
  `lib/nuggs-coupling.scad`, designs/nuggs PM N1).
- **N2 — per-run length limit.** `tube_len ≤ 2 × body_len_mm`, asserted;
  couplings do not reset a run; engraved on the wall. (DTSchB
  *Tierschutzwidriges Zubehör*, one limb of a conjunctive test; the
  reversing derivation is judgement — designs/nuggs round 5.)
- **N3 — animal-contact material is the body material only.** The second
  material exists strictly outside the hamster envelope; nothing proud,
  nothing engraved on an animal-reachable face (N6 chew-edge rule).
- **N4 — captivity is guaranteed by geometry, not clearance.** The ring
  hole must underlap the fin cage by ≥ 1.5 mm (asserted). A ring that can
  come off is a swallowable part near an animal enclosure.
- **N5 — both material STLs gate individually and never intersect.**
  `ci.parts` gates each; `ci.fitchecks` makes CI render `part="fitcheck"`
  (must be empty) and the `fitcheck_neg` negative control (must interfere)
  on every gate run.

## Out of scope — never

- Any in-enclosure placement or accessory (designs/nuggs charter, sourced).
- Lubricants on the races.
- A version whose kinetic parts are load-bearing for the coupling.

## Ranked backlog

1. Print the coupon on a real H2-class machine; measure `race_gap`.
2. Print the full co-print; measure sprue snap force and ring spin.
3. A `$t`-driven ring-spin animation (`anim` parameter, new manifest entry).
4. Sound: if ring rattle annoys owners, a felt-washer note or a damped
   ring variant — only after a real print says it matters.

## Open decisions

- None blocking. `race_gap`'s default moves to the measured value after
  backlog item 1.

## Decision log

- 2026-08-11 — Design created; dual-material orbit-ring concept chosen over
  interpenetrating lattice (unverifiable) and over dissimilar-material
  break-away brims (rejected by designs/nuggs round 3 precedent). Sprue
  frame added for slicer layer-continuity, not print necessity.

## Product page & shots (art direction)

**Page promise:** "the module that can only exist printed."
Tier-1 shots: `product-hero` — the kinetic state, three-quarter view, rings
catching light against a dark body; `orbit-rings` — the orbit STL alone with
its sprue frame, contrasting color, so the page shows the second material as
its own object. Turntable GIF of the kinetic state. No tier-2 lifestyle
scene until a real print exists to be honest against.
