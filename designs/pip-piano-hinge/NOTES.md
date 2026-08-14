# pip-piano-hinge — engineering notes

**Reference design for** `docs/advanced-techniques.md` **Domain 3 (print-in-place
kinematics → hinges)** and **CC4 (grow the bore by a true `offset()`, not a
scaled teardrop)**. Tier-2 "harder". Built on `lib/print-in-place.scad`.

## Goal

A multi-knuckle hinge that comes off the plate assembled and swinging — the
Domain-3 pin-in-bore joint tiled into a real piano hinge, and the place to show
the library's `pip_hinge` primitive doing its job.

## What it reuses vs what it adds

- **Reuses (the hard part is already solved):** `pip_hinge` / `pip_hinge_pin`.
  Their bore is the pin's own 2D profile grown by `offset(r=clear)` — the CC4
  subtlety. A *scaled* teardrop leaves the 45° flank planes coincident with the
  pin's (a welded print that CGAL passes and only Manifold export catches); the
  offset gives real clearance on every surface. This design does not re-derive
  that; it trusts the gated library.
- **Adds (the piano-hinge-specific problem): tolerance stacking.** A long run of
  knuckles binds if lengths add up wrong. Defeated by two clearances:
  - `axial_gap` (0.6) between consecutive knuckles — leaves never rub end-to-end;
  - `leaf_gap` (0.4) between a leaf's plate edge and the *opposing* leaf's barrels
    — a swinging leaf clears the knuckles it isn't attached to.
  Both asserted.

## Construction

Leaves interdigitate: even knuckles → leaf A, odd → leaf B. Each leaf is a plate
+ its knuckles + a per-slot web that fuses plate to barrel *only at that leaf's
slots* (so the plate never touches the other leaf's barrels — the tangent-kiss
trap). One free pin runs through all knuckles. `plate_edge = R + leaf_gap` keeps
each plate edge off the opposing barrels.

Folded preview (`previews/folded-pose.png`, `demo_fold=110`) confirms leaf B
swings while leaf A and the pin hold; the offset bores show real clearance.

## Print

Flat, axis horizontal, teardrop roofs up → no supports. `pin $fn ≥ 64` (the bore
is $fn-sensitive; set to 96). `clear = 0.4` is an acoustic-class clearance — 0.25
is the weld floor (`pip_hinge` guards it), tuning far up buys a rattly hinge.

## Print this first

`pip-piano-hinge-coupon.scad` — a fast 3-knuckle stub (include + override, no
copied geometry). Print it and work the knuckles free; if any binds, raise
`clear` by 0.05 mm and reprint. Tune `clear` on the coupon before committing to a
full-length hinge. Gated like any part (printcheck + test-slice).

## Status

- Renders clean, folds correctly.
- Print-in-place fit → before ship: `ci.fitchecks` proving each leaf + pin render
  as separate bodies (0 interference facets) with a deliberately-interfering
  negative control (clear driven below the weld floor). TODO with gate.
- TODO: `gate.sh --slice`, README, product shot.
