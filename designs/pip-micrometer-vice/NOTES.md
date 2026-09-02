# pip-micrometer-vice — NOTES

Engineering log. Product page: `README.md`. Scope contract: issue #516
(claimed 2026-09-02, SHIP-LOCK on the thread).

## Goal

A print-in-place bench vice whose entire drivetrain comes off the bed
assembled: one twist of the knob screws the moving jaw along a stationary
printed trapezoidal screw (rotary → linear, zero assembly, zero hardware in
the drivetrain). The gap the catalog had: the PIP shelf (sliders, hinges,
gears, snap bearings) had no screw joint printed in place, and the screw is
the one that turns rotation into travel — this design is the reference
consumer pairing `lib/threads-fdm.scad` with `docs/advanced-techniques.md`
Domain 3 (print-in-place kinematics).

## Given / assumed measurements

Per the brief (issue #516), all rows given unless marked:

| Row | Value | Status |
|---|---|---|
| Jaw opening (travel) | 0–30 mm | given (30 default of the 25/30/45 open question) |
| Jaw face width × height | 40 × 20 mm | given |
| Screw lead | 2.0 mm/turn, single-start | given (pitch = lead = 2.0) |
| Thread nominal (crest) Ø | 12 mm | given |
| Anti-rotation key clearance | 0.30 mm | given (coupon sweeps it) |
| Base mounting | two M5 through-holes, 40 mm grid | given (`screw_hole("M5")`, at (±20, 0) on x) |
| Base footprint | ≤ 80 × 60 mm | given (built at 80 × 58 — at the cap) |
| Style | `workshop-utility` | given |
| Print pose opening | 12 mm | assumed (non-blocking open question; every stop face stands off) |
| No 45° V-anvil | — | open question defaulted: plain faces |
| Coupling | plain faces (no magnetic/V) | assumed per brief default |

## Key decisions

1. **Bench-vice architecture, not tip-pusher.** The screw is axially FIXED:
   plain guide bore through the rear block, thrust collar (Ø16.4 × 2.5,
   0.5 radial / 0.75 axial play in a sealed chamber) takes the clamping
   reaction, thread spans the whole channel, and the MOVING JAW carries the
   nut. A tip-pusher (screw advancing into the jaw) would translate the
   screw 30 mm — impossible to keep supported or captive. The jaw's nut is
   cut by the screw's own world-space cutter (`screw_thread_cutter()`), so
   male and female cannot drift at any pose — the fit is exact by
   construction, and `ci.fitchecks` re-proves it on the mesh.

2. **Why the screw never dangles** (the core print-in-place problem — a
   horizontal cylinder's underside prints on nothing): every millimetre is
   supported by proximity. Guide bore 0.5 gap (the `pip_hinge` precedent),
   nut thread-interleaved at `thread_tol` (0.30), exposed span over the
   centre saddle with crest 0.4 above it (`saddle_gap`, ≥ the 0.35 weld
   floor, asserted). The knob is a Ø17 disc standing on the base top behind
   the rear block, 0.5 clear.

3. **Guideway = plain rail walls + saddle straddle + the screw itself** —
   a deliberate deviation from the brief's `slide_rail`/`slide_tab`
   vocabulary, and the reasoning is geometric: a 40 mm wide jaw FACE cannot
   travel between rails that carry castellated capture lips, because the
   lips occupy the exact y-band the face sweeps, and notching the clamping
   face to pass them would gut it. It is also unnecessary: the battleship's
   lips exist because a door is strung on nothing, and this jaw is strung
   on the screw — the nut bore wraps the thread, so lift is bounded by
   `thread_tol` at every pose. What the guideway must add is side keying:
   rail walls at `clr_h` (the brief's named key clearance, 0.30) + the
   saddle straddle (0.3/side) + the base-top floor ride (0.6). Measured
   consequence — the free-tip bound is clearance/lever from the screw axis
   to the key planes: ~2° ≈ 0.4 mm sway at the face top. Enough to develop
   clamping force (the thread seats the jaw against the workpiece); noted
   as the design's slop, not hidden.

4. **Thread depth 0.55** satisfies `lib/threads-fdm.scad`'s female
   `w_root < lead` guard at the coupon's worst station: tol 0.35 →
   w_root = 0.5 + 0.29 + 1.1 = 1.89 < 2.0. (At tol 0.30 production:
   1.85.) Never retype the flank split — `flank_add(tol)` derives it.

5. **Print pose = opening 12** so every stop face stands off — a zero-gap
   stop face prints as a seam that welds shut (the czs-slider lesson;
   iteration 1 of that design caught exactly this on its coupon sliders).

6. **Fixed jaw plate 8 mm thick** (not 5) so the workshop-utility r4 corner
   reads honestly (`rounded_box` r must be ≤ half the smallest plan
   dimension). Base grows to 80 × 58 — at the brief's cap, so the pad and
   the M5 holes coexist with the knob clearance.

7. **M5 vs the style's M3 hole vocabulary** — the one deliberate style
   deviation, required by the brief's given mounting row. The style's
   hole-vocabulary rule is advisory; recorded here per the style exception
   convention.

8. **Multi-body deliverable**: the default render is the printable
   assembly — one STL, three bodies (body / screw+knob / jaw). It is a
   print-in-place mechanism (prints together, must stay separable), so it
   is `ci.fusecheck`'s domain, NOT `ci.plate` — no plate manifest. The
   coupon adds 7 more (plate + 3 nuts + 3 sliders).

9. **Coupon station labels live on the parts they label** — digits cut
   into the nut front faces, letters into the slider tops — not on a plate
   strip between the rows. Measured reason: at any readable tilt the nut
   occludes a strip in front of it (at the coupon camera's 52° elevation,
   the sightline to a strip 3.9 mm in front of the nut crosses the nut at
   z 7 — mid-face). The digits were mesh-proven present on the first strip
   attempt (face-on edge-density A/B: 4.89/3.0/2.44% vs 1.78–2.33% blank
   controls) yet invisible in the 3/4 render — presence in the mesh is not
   visibility in the shot. Related traps, both hit: a `difference()` operand
   that misses the solid removes nothing and OpenSCAD does not warn, so a
   label cut must belong to the solid's own `difference()`; and face-on,
   flat-shading paints a recess floor the surface's own colour, so presence
   checks need the edge density, not the eye.

10. **`mirror([1,0,0])` on the nut-face digit is load-bearing.**
    `rotate([90,0,0])` stands the glyph upright but extrudes it −y — away
    from a +y-side reader — so the glyph is read from behind its own
    writing plane, which mirrors it (a `linear_extrude` glyph reads
    correctly from the side its extrusion points at; top-face letters with
    no rotate extrude +z and read correctly from above, consistent with
    this). Upright AND front-facing on a vertical face is a reflection,
    not a rotation — `rotate([-90,0,0])` would face the viewer but flip
    upside-down — hence the mirror. It flips about the `halign="center"`
    origin, so the glyph stays centred. Verified by the controlled
    mirror-compare (render | flop, side by side, 400% point-sampled): both
    chiral digits (2, 3) failed it pre-fix and pass it post-fix. Trust that
    test over open "is this mirrored?" questions — an open question
    produced a contradictory whole-row misread on the same pixels.

11. **`slot_hw = saddle_hw + clr_h`** — the saddle-straddle slot is
    derived from the key clearance, not typed alongside it, so coupon
    row 2 sweeps the straddle the vice actually ships. A hardcoded slot
    half-width would keep sweeping a stale value as `clr_h` moves.

12. **Three gate fixes from the iteration loop, one lesson.** (a) Rails
    extended to `x_base1`: they ended at the saddle, so the jaw reached
    the open end of its travel pinched between rails that had already
    stopped — a non-manifold crush at full open. (b) The coupon's
    nut-to-plate weld needed **two** fixes: lifting the nut 0.6 off the
    pad cured the bed-face weld, yet `fusecheck` still read 4 bodies —
    the surviving weld was *lateral*, the stud's Ø12 crest reaching
    x 13 against the nut's near face at x 12, a 1 mm solid overlap
    invisible to a vertical-separation check. Stub moved to x 5.4 (crest
    11.4, the same 0.6 the nut rides over the pad) → 7 bodies, `fusecheck`
    ok. (c) The M5 saddle through-cut capped at the saddle top, leaving
    an un-drilled ceiling over the screw — `screw_hole("M5",
    saddle_top + 1.15)` plus an assert that the cut clears the screw's
    lowest crest by ≥ 0.2. The lesson: a weld between two parts can have
    **more than one contact**, so after each fix re-run the check that
    failed — the first diagnosis being right does not make it complete.
13. **Digit visibility is proven by a difference mask, not an eye.**
    The frozen coupon camera shows the digits as *filled* glyphs (the
    recess floor shades a step darker at 52° — more readable than the
    thin-outline reading decision 9's face-on trap predicts). The proof:
    render the identical camera with the digit cut suppressed
    (`linear_extrude(0.001)` — sub-pixel at ~14 px/mm), `compare -metric
    AE -fuzz 4%` → 3110 px, and the difference mask's connected
    components are three glyph blobs at **exactly the cell pitch**
    (452 px), with area signature 864 / 1129 / 1117 px — "1" far smaller
    than "2"≈"3", the ordering the for-loop types. Two independent
    vision reads at downscaled resolution called the wrong digit on
    these same pixels (misreads 8–9); the controlled A/B is the ground
    truth, extending decision 9's edge-density method from face-on
    views to 3/4 views.

## Print settings

- Orientation: as rendered — base down, screw and jaw axes along x. No
  supports, ever: a support inside the thread welds the drivetrain, which
  is the exact failure `ci.fusecheck` exists to catch.
- Material: PLA or PETG; layer 0.2, ≥3 perimeters, 25% infill for the
  base/jaws.
- Bed: 80 × 58 × ~27 mm — fits any 220 mm printer.

## Print this first

The coupon (`pip-micrometer-vice-coupon.scad`, gated as
`build/pip-micrometer-vice-coupon.stl`) — tune in this order:

1. **Thread fit** (row 1, digits 1/2/3 = `thread_tol` 0.25/0.30/0.35):
   screw each nut onto its stub. Pick the one that turns smoothly through
   its full length without slop; production default is 2 (0.30). Tight →
   raise `thread_tol`; sloppy → lower it.
2. **Guide fit** (row 2, letters A/B/C = `clr_h` 0.25/0.30/0.35): push each
   slider along its channel. Pick the one that slides without rattling;
   production default is B (0.30).

Then set the two parameters in the entry `.scad` and render the vice. If a
real print later drags on the saddle or floor, `gap_z` (floor, 0.6) and the
straddle slot's 0.3 are the next dials — tune them together on a re-printed
coupon station B before touching the rails' `clr_h`.
