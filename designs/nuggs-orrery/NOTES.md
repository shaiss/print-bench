# nuggs-orrery — engineering log

## Goal

An abstract, boundary-pushing NUGGS module that is *only manufacturable on a
dual-nozzle 3D printer* (Bambu H2-series class; AMS available for color):
the standard port at both ends, and outside the hamster-contact envelope a
kinetic sculpture — six twisted fins carrying three captive, free-spinning
orbit rings in a second material. Request: unique/abstract, dual materials
using both nozzles, bonus for built-in break-away supports and other
advanced techniques. NUGGS rules constrain the animal-contact surfaces; the
exterior is fair game (owner's brief, this session).

## The three claims, and what proves each

1. **Unassemblable — print-only.** Each ring's hole (`ring_r_in = 54.8`) is
   smaller than the fin cage (`fin_r = 57`). A rigid ring cannot pass over a
   larger rigid cage at any position or tilt; it got there by being printed
   there. Guarded by the `ORRERY CAPTIVITY` assert (≥ 1.5 mm overlap).
2. **Zero generated support.** Every downward face in both STLs is at
   `ramp_ang = 50°` (printcheck's threshold is a strict > 45°, and inscribed
   polygons sit ~0.01° past nominal — designs/nuggs round 3), is a designed
   micro-bridge (ring bottom land 0.8 mm, sprue tabs 0.7 mm), or rests on
   the other material: each ring's lower-outer face is *parallel to its
   race, `race_gap` above it*, so the second material prints directly on the
   first for the ring's whole circumference.
3. **Dual-nozzle-required.** Two reasons, one physical and one practical.
   Physical: the race is the print support **and** the bearing — that only
   works because PETG and PLA do not weld. One material printing a
   zero-support captive ring on its own race fuses to it (the coupon's
   same-material fallback needs `race_gap ≥ 0.20` and a cracking twist, and
   loses the zero-clearance seat). Practical: the rings change material
   every layer for their whole height; through one nozzle that is a purge
   festival with per-layer PETG↔PLA temperature cycling.

## Given / assumed measurements

- **NUGGS standard:** `nuggs_cfg()` defaults, untouched — bore 80,
  wall 2.4, `r_out` 48.4, `port_tol` 0.30. The port fit is the library's
  (proved by `lib/nuggs-coupling-mates.conf`); this design adds nothing to
  the coupling and tunes nothing on it.
- **Assumed:** `race_gap = 0.10` for PETG/PLA. **Nothing here has been
  printed.** 0.05–0.15 is the band reported for incompatible-material
  support interfaces; the coupon exists to measure it.
- **Assumed:** `body_len_mm = 180` (same Merck figure as designs/nuggs).

## Key decisions

- **Two STLs, one coordinate frame.** `part="body"` and `part="orbit"`
  export in the same frame; a slicer imports them as one object with two
  parts, one per nozzle. Both are gated individually by CI (`ci.parts`),
  and `part="fitcheck"` renders their intersection — **measured empty** at
  the print pose, and the check can fail: shifting the orbit down 1 mm
  yields 939.727 mm³ of interference (negative control, this session).
  The two-way-empty lesson from designs/nuggs round 6.1 is why the
  control exists: an empty boolean proves nothing until it is shown able
  to be non-empty. **CI-gated since review round 1** (Qodo finding):
  `ci.fitchecks` makes every gate run render `fitcheck` (must be empty)
  and `fitcheck_neg` (the −1 mm pose, must interfere) via the new
  fitcheck support in `scripts/gate.sh` — so an interference regression
  or a vacuous-check regression both fail CI, not just this session.
- **The race is the support, the bearing, and the lower travel stop.** A
  50° conical shell grown from inside the tube wall (`race_root_r = 41.5`,
  0.9 mm bite into the wall, never through it — the bore cut at `ri = 40`
  is untouched). Its top surface runs `race_gap` under the ring's
  lower-outer face, parallel, so ring layer 1 lands on it and every later
  layer is self-supported at 50°.
- **Ring cross-section:** flat 0.8 mm bottom land (first layers ≥ 2
  extrusion widths; also the plate-contact face printcheck measures on the
  lowest ring — a knife-edge vertex scored `Almost no bed contact`
  CRITICAL in a dry run of the check logic), then 50° lower faces both
  sides, vertical walls, flat top. 2.8 mm radial × 3.6 mm tall.
- **Grooves (fin cutbacks) make the airspace; fins make the cage.** Fins
  are cleared to `groove_floor_r = 53` from 1 mm below each seat to
  `groove_head = 6.5` above, with a 50° roof. Free lift ≈ 5.0 mm (echoed
  by the model), then the ring's inner band meets the roof: rattle by
  design, escape by geometry impossible.
- **Break-away sprue frame (the engineered break-away supports).** Three
  vertical spars outboard of everything (`sprue_r0 = 58.3`, ≥ 1 mm from
  the cage), tabbed to each ring's outer face: 9 tabs, each bridging
  0.7 mm and snapping at a ~1 × 3 mm neck. The frame exists for three
  reasons: **(a)** PrusaSlicer hard-fails an STL with empty layers, and
  three floating rings are mostly empty layers — the frame makes the orbit
  STL one continuous body (gate: 1 body, watertight); **(b)** it ships and
  handles as one rigid piece; **(c)** after the snap the spars are captive
  to nothing and fall away. This is the model owning what a slicer would
  otherwise improvise.
- **Fin lean is asserted, not eyeballed.** A twisted blade leans
  `atan(r · twist-rate)` from vertical — 32.2° at the defaults, asserted
  ≤ 40°. The envelope's lead-in/out cones and the groove roofs are all at
  50° from horizontal for the same printcheck-strict-inequality reason.
- **Wall engraving between twisting fins.** `NUGGS PORT R1` /
  `MAX RUN 360MM`, engraved (never proud — chew-edge rule N6), one
  character per tangent plane (designs/nuggs round 4), each line centered
  on the fin gap *at its own height* — the gap tracks the twist, so the
  center angle is a function of z. Verified empirically: the mark cutters
  ∩ fin cage renders empty (and OpenSCAD's `twist` sign convention was
  confirmed by that same test — a wrong sign would put the text 42.7° into
  a fin).
- **Mate envelope untouched.** The mate's geometry reaches at most
  `z_seat = 10` alongside our port (tips on our collar, `r ≤ 48.4`); our
  first sculpture element is the fin band at z = 16 and the lowest race
  roots at z ≈ 24. Closest approach ≥ 6 mm; the port itself is pure
  library geometry at default cfg, already proved by
  `lib/nuggs-coupling-mates.conf`. No new mate test needed — nothing in
  this design is within reach of a mate.
- **`printer-conf` not opted into, deliberately.** `race_gap` is a
  z-interface between dissimilar materials, not an XY clearance;
  pre-filling it from `printer_xy_tol` would be false precision. The
  coupon is the instrument.
- **This design is the `orrery` style's reference** (owner request,
  mid-session): the look was lifted into `styles/orrery/` with
  `style-lift.sh` from the `part="kinetic"` mesh, pruned by hand (the
  42 mm "corner radius" was the tube barrel — form, not edge treatment;
  the 80 mm "hole vocabulary" was the NUGGS welfare bore — a standard,
  not a style), and the design now declares it in `style.conf` and builds
  from the tokens (`style_ramp_deg`, `style_blade_th`, `style_ring_h`,
  `style_seat_gap`). The retrofit is **mesh-neutral, proven**: canonical
  triangle-set equality on the body STL before/after (25852 faces,
  162208.075928 mm³ both ways), so the gate table below still stands.
  Two rule-scoping findings from checking the reference's own parts:
  the smoothness rule is scoped to dominant rounding ≥ 10 mm (stylelift
  reads the ring's deliberately faceted cross-section as a coarse
  sub-3 mm circle), and `ramp-grammar` is the required rule, because it
  is the one signature every family part actually carries.
- **Welfare surface unchanged.** The bore is `nuggs_bore_cut()` clean end
  to end, no window, no interior features; the run-length assert carries
  the round-5 language (DTSchB, conjunctive test, per-run, couplings don't
  reset, reversing derivation is judgement). PLA appears only outside the
  enclosure envelope. The rings will click against their stops when the
  module is bumped — noted as a (human) acoustic caveat, not a welfare
  one, since the module hangs outside the enclosures in the bin bridge.

## Gate results (this session, OpenSCAD 2021.01/CGAL)

`./scripts/gate.sh --slice nuggs-orrery` **exits 0**:

| part | printcheck | bodies | filament | slice | note |
|---|---|---|---|---|---|
| body | 76/100 | 1, watertight | 193.0 g | 14h40m | 2 % overhang (port sectors), bed-contact warning (six tips — brim mandatory, same as nuggs straight), 4 degenerate faces = the library's known B1b port artifact |
| orbit | 84/100 | **1**, watertight | 12.3 g | 1h02m | 4 % overhang = the ring lands + tab undersides, by design; the sprue frame is what makes it one body |
| coupon | 84/100 | 2, watertight | 47.8 g | 3h32m | 2 bodies intentional (stub + captive ring); thin-wall warning is the race shell edge |

`part="fitcheck"` empty at print pose; 939.727 mm³ at −1 mm (control).

## Print settings (intended, not yet validated)

- Body PETG, rings PLA (the pairing is functional — see README).
- 0.2 mm layers, tube axis vertical exactly as exported, shared origin.
- Brim `outer_and_inner` for the body, ≤ 5 mm.
- Never a dishwasher; ≤ 50 °C (PLA rings).

## Print this first: the coupon

`nuggs-orrery-coupon.scad` — one complete ring station (tube stub, fin
band, race, captive ring) at 30 mm tall, ~48 g. Tune **`race_gap`** in
±0.05 steps (asserted 0.04–0.40):

- ring welded to race → raise;
- ring released but audibly sloppy on its race → lower;
- PETG/PLA expect 0.05–0.15; same-material fallback expect 0.20–0.30.

It also proves the snap: the coupon's ring has no sprues, so it releases
on the race interface alone — if it doesn't, the full module's 9 tabs
won't save the print either.

## Open items — next round

- **Nothing has been printed.** `race_gap = 0.10` is a literature-shaped
  guess; the coupon settles it. Ring spin quality (does it spin, or just
  rotate grudgingly?) is unknowable from geometry.
- The four degenerate port facets (B1b) are inherited from
  `lib/nuggs-coupling.scad`, pre-existing, zero-area, tracked upstream.
- Sprue snap force is designed (~1 × 3 mm necks) but unmeasured; if a
  printed frame tears a ring's outer face instead of snapping at the neck,
  thin the tab z-height 1.0 → 0.8 before touching its radial bridge.
- The engraving's fin-gap margin is ~5° per side at `mark_size = 2.8`;
  anyone growing the text past 3.2 mm re-runs the mark-vs-fin
  intersection check (it is two lines in a scratch file; see Key
  decisions).
- No animation of the *rings actually spinning* — the turntable GIF spins
  the camera. A `$t`-driven ring-clocking anim would need an `anim`
  parameter; deferred until someone wants it (frozen-camera rule: new
  entry, not a reframe).
