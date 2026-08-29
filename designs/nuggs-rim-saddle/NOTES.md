# nuggs-rim-saddle — the no-drill glass-enclosure entry port

Design brief: #395. Charter: `designs/nuggs/PM.md` (every module inherits
N1–N11; this is backlog item **B3** — "the only route for glass enclosures,
and no-drill lowers the entry cost more than any other item").

## Goal

A saddle that clamps over the top rim of a glass-tank enclosure — no drilling
(N9: tempered glass shatters), no adhesive — and carries one standard NUGGS
genderless quarter-turn port (`lib/nuggs-coupling.scad`, N10: the one
interlock), so a run starts from a glass cabinet the same way it starts from a
plywood bulkhead. Target enclosure: IKEA Detolf (the cabinet charter N9 itself
names), parametrically — every rim dimension is a parameter with the Detolf
value as the default, so another cabinet is a `-D` override.

## Given / assumed measurements

| Measurement | Value | Status | Source |
|---|---|---|---|
| Port face | one standard NUGGS port, 80 mm bore | given | `lib/nuggs-coupling.scad`; charter N1 (floor 70 mm), N10 (one standard) |
| Bore | 80 mm continuous smooth through the saddle body | given | charter N1 |
| Ramp incline | ≤ 15° from the port invert down into the tank | given | charter N4 (fall risk) — **asserted in geometry**, default exactly 15 |
| Ramp reach into tank | ~120 mm at ≤ 15° | assumed (brief) | brief open question, non-blocking; `ramp_len` parameter |
| Glass panel thickness | 4 mm | assumed | commonly documented Detolf figure; `glass_t` parameter, owner calipers |
| Clamp reach over rim | grip panel + frame lip, no seam pinch | assumed | brief; `skirt_h`, `lip_d`, `lip_h`, `seam_clear` parameters |
| Assembly | opens by hand, tool-free, one action | given | charter N5 (a wedged animal must be releasable) |
| Detolf overall | 43 × 39 × 163 cm | assumed | published IKEA dimensions — context only, not modelled |

The rim cross-section open question is **blocking for the fit, not for the
scaffold** (the brief's wording): the model is parametric on the assumed
values and the coupon is the calibration path.

## Key decisions

- **One straight inclined bore, not a horizontal port plus a separate ramp.**
  The whole module is one tube whose axis is inclined exactly 15° (the N4 cap)
  descending into the tank. The internal ramp the brief asks for IS the bore's
  invert — a round tube at 15°, so the walking surface is the bore arc
  (charter N11's zero-step argument holds by construction: it is a tube, not a
  trough), and the animal climbs back out the same surface it descends.
- **The mouth discharges into the enclosure — that is the N2/N3 break.** The
  run this module contributes is its own enclosed length only (port face to
  mouth ≈ 145 mm axial); a port discharging into a ventilated enclosure is a
  break, so the run ends here. The product page says so (the family rule:
  document the break, don't imply one).
- **Clamp: two identical compliant snap arms, not mirrored halves.** The brief
  left the mechanism to the session ("compliant snap vs captive-knob screw…
  session's choice"; "two mirrored clamp halves" was its *likely* guess). Two
  *identical* translated arms beat a mirrored pair for the owner — one spare
  serves both sides — and they release with one two-finger spread (both
  outboard tabs pulled together = one action, N5). Each arm is a flat
  cantilever: a cap that clips captively over a rail on the bridge (no lost
  parts), a beam descending outside the glass, and a foot whose pad bears the
  frame lip while a hook latches under a bar at the outer skirt's foot.
- **The clamp bears on glass and frame only.** The inner skirt's bearing pad
  starts below the top-edge seam zone (`seam_clear`); nothing bears on the
  silicone bead. The bearing loop: arm pad → frame lip → panel → inner skirt
  pad → bridge → outer skirt → latch bar ← arm hook.
- **Three parts, printed separately; the 3MF plate is the deliverable**
  (`ci.plate`): body (port-down, the family orientation — sectors at the bed,
  tube vertical), arms ×2 (flat, profile horizontal — PETG, layers in the
  bending plane), coupon. Assembled renders are previews only.
- **PETG over PLA for the arms** (a clamp is a bending member; PLA creeps) —
  noted on the product page per the brief. Hand-wash ≤ 50 °C (N7).
- **$fa=3 / $fs=0.8** everywhere the tube meets the port, matching the
  library's pin exactly (the issue #99 / PR #200 shell-split lesson: the tube
  must be drawn at the port's own resolution).
- **Iteration 1 (gate run 1) caught two silent breakages the render never
  showed.** The inner bearing pad was drawn 2 mm INSIDE the glass panel (the
  `clamped` fitcheck's 24 interference facets) and floated as a disconnected
  island — the body STL shipped 3 shells. The inner skirt's only connection to
  the bridge was a coplanar z=0 face, which the bead-zone clearance cut sliced
  clean through, orphaning it too. Fixes: the pad became a leaf-plus-spine one
  piece bearing the panel face from inside the tank and overlapping the skirt
  1 mm; both skirts fuse 3 mm up into the bridge (a coplanar touch is not a
  fuse); the bead zone is cleared by x-standoff and a relief pocket under the
  bridge, not by cutting the wall. The fitcheck envelope also carries a 0.05 mm
  check margin so the *designed* exact-contact rest faces (pad leaf on panel,
  bridge on rim) read as clear instead of zero-volume slivers, and the
  negative control crushes the arms inboard with a rigid shift — growing
  `grip_gap` would relocate the latch wall (one-knob rule) and trip the arm's
  own guard instead of the glass.
- **Round 2 (Jane) caught the `bore_lead` branch-cross by hand-measuring the
  mesh.** The module's two `dir` branch expressions were crossed: at the
  in-tank mouth the lead cone was inverted (bore 40.000 at the exit face,
  41.000 one mm inside — a ~1 mm annular groove behind a ~1 mm proud lip, a
  toe-catch on the walking ramp, exactly the step N11 forbids and the
  module's own "only ever widens the bore" contract denies), and at the port
  face the cone spanned 99.9 % below its cutting plane, so that mouth shipped
  with effectively no lead. Postmortem: a wrong-direction cut renders
  watertight and scores printable — it is invisible to every gate in the
  repo; Jane found it by projecting the rendered mesh's bore-band vertices
  onto the axis and reading the radii. The fix (one translate/rotate swap so
  the wide end sits at each face) was verified the same way: 41.000 at each
  face tapering to 40.000 one mm inside, both mouths, no groove, no lip.
- **G4 measured off the export, not the parameter** (issue #37 discipline).
  A gauge cylinder placed from the *declared* axis/incline and intersected
  with the rendered body: **Ø 79.6 passes the full ~145 mm clean** (empty
  intersection — N1's ≥ 70 mm floor met with 9.6 mm to spare), Ø 80.4 scrapes
  the wall (the negative control fires), so the bore measures
  **Ø ∈ (79.6, 80.4)** and the mesh axis agrees with the declared 15° to
  ~0.08° (0.2 mm radial over 145 mm). **Nothing in the bore** (N6): 0 of the
  4970 STL facets lie inside r < 39. Measurement footnote: the gauge must be
  seam-rotated ~7° about the axis — coaxial with its `$fn` seam on the body's
  `rotate_extrude` seam ray it reports a phantom 76-facet "fin", a
  coincident-surface CGAL sliver (identical for every gauge diameter, absent
  from the STL), not material.
- **The body prints with supports.** Standing port-down (the family
  orientation — the coupling sectors must never face the bed), the shell grows
  out of the vertical tube and printcheck measures 11 % of the surface
  (12 611 mm²) as unbridgeable overhang; the gate's PrusaSlicer test-slice
  completes with auto supports (13 h 11 min, ~195 g). That is the honest
  print-settings line, not "supports: none".

## Print this first

`nuggs-rim-saddle-coupon.scad` — one ~6 h / ~79 g print, tests both tuned fits
(print it in the same PETG as the arms; a fit tuned in PLA reads ~0.05 mm
tight in PETG):

1. **Port fit** (`port_tol`, default 0.30 mm): two port stubs side by side.
   Snap together, twist either way. Too loose to retain → −0.05; needs
   force to seat → +0.05. This is the family knob — tuned on `designs/nuggs`'s
   coupon, same steps.
2. **Rim grip** (`grip_gap`, default 0.20 mm): the coupon carries the
   production latch flange on a bed-standing skirt-foot fixture, with the two
   production arms as separate flat bodies beside it. Snap an arm onto the
   flange, check it latches and releases with a finger lift. Sloppy → −0.05
   (tighter); will not seat over your panel → +0.05. Then measure your actual
   panel (`glass_t`) and frame lip (`lip_d`, `lip_h`) with calipers and
   re-render the saddle before committing to the full print.

## Print settings

- **Material:** PETG (arms mandatory; body PETG or PETG-HT). Never PLA for the
  arms — a clamp is a bending member and PLA creeps. Hand-wash ≤ 50 °C, never
  dishwashered (N7).
- **Orientation:** as rendered — body standing port-down on the sector tips;
  arms flat on their back; coupon flat.
- **Layer height:** 0.2 mm. **Seam:** scarf, not aligned — the bore invert is
  the walking surface; an aligned seam stacks a ridge down it. **Infill:**
  ≥ 15 %, 4 walls on the arms.
- **Supports:** body — tree supports under the shell where it grows out of
  the tube (11 % of its surface; ~12 600 mm²); arms and coupon — none.
  Deburr every glass/frame bearing face afterward (a support nick is a point
  load on tempered glass).
- **Brim:** body — mandatory (three sector tips = 527 mm² bed contact, under
  5 % of its footprint; 155 mm tall); arms and coupon no. Peel the brim and
  deburr the sector tips before testing any fit — the coupling datum is the
  bed face.
- **Bed:** every part fits a 256 × 256 mm bed (body 137.5 × 124.8 × 154.9 mm
  standing; arms flat 41.2 × 63 × 24 mm the pair; coupon 203.8 × 205.8 × 52
  mm — centered: it clips the front-left exclusion zone on X1/P1 beds).
