# NUGGS Sand Bath — NOTES

Engineering log. The product page a stranger reads is `README.md`; the brief is
issue #667; the run was `/design-run 667` (claim comment on the issue thread).
Everything below is what a later session needs to resume cold.

## Goal

The grooming module the NUGGS ecosystem was missing: an **open-topped sand-bath
trough** a run dead-ends into. The animal walks the standard 80 mm bore, crosses
a containment lip down a ≤45° beach, and stands on a flat sand floor wider than
the bore; sand goes in from the open mouth, the animal can be lifted out the
same way. One `nuggs_cfg()` consumer like every NUGGS module — the port is the
shared interlock, nothing about it is restated here.

## Given / assumed

From the brief's *Must fit / hold* table (issue #667):

| Row | Value | Given / assumed | Realised as |
|---|---|---|---|
| NUGGS bore diameter | 80.0 mm | given (lib default) | `bore_d` → lib cfg |
| Port tolerance | 0.30 mm, tunable | given — coupon mandatory | `port_tol`, coupon ships |
| Port projection | 10.0 mm | given (lib default) | `port_proj` → `z_tip = −10` |
| Lugs per face | 3 | given (lib default) | `n_lug` |
| Bathing sand depth | ≥ 15 mm | assumed (welfare practice cites 2–3 cm) | `sand_depth = 18` |
| Dish inside width | ≈ 110 mm | assumed | `dish_w = 110` (taken exactly) |
| Sand capacity | ≈ 250 mL | assumed | measured 245.5 mL (−1.8%) |
| Containment lip | ≈ 20 mm, ≤45° ramps | assumed (rim-saddle bore-invert precedent) | `lip_h = 20`; beach 42.27°, far ramp 44.16° |
| Wall above sand line | ≥ 15 mm | assumed | `freeboard = 15` |

Printer/material: repo FDM defaults, PLA or PETG, **no slicer supports**.

## Reading the print-pose line

The brief's "port-axis vertical standing on the sector tips, dish mouth up" is
**both poses in one sentence**, and the design reads it that way:

- **Print pose** (what's modelled): port axis vertical, standing on the sector
  tips, the dish growing up out of the tube. The mouth faces *sideways* here —
  which is the point: in this frame every dish wall is a z-extrusion (nz = 0 on
  any extrusion flank), so nothing outside the coupling's own tier needs
  support.
- **Use pose**: the module lies on its flat floor strip, port horizontal in the
  run wall, mouth up.

They cannot be one pose: a mouth-up *print* would put the dish floor and the
far wall over the trough as flat ceilings, and a port-vertical *use* would point
the port at the sky. `part = "hero"` is the use-pose preview (`rotate([-90,0,0])`
of the same solid); `part = "body"` is the printable print-pose part.

## Run-break ruling (brief open question 1)

**Treated as a run break.** The NUGGS length rule counts three breaks: an open
end, a ≥180° open module, a turnaround node. This dish's mouth is the entire
top side of the trough section — the same "the animal is in open air" condition
the 180° `nuggs_window()` module rests on (`lib/nuggs-coupling-mates.conf`,
`open-module-to-round-*`), applied along the dish instead of along a tube. The
brief asked for the ruling to be *recorded, not assumed*, so: recorded here,
flagged for the owner's confirmation at the PR, and the README's layout guidance
states it ("a destination, not mid-run passage"). Geometry is unaffected either
way — this only changes layout advice.

## Headroom at dish centre (brief open question 3)

**No crown, no stolen depth.** The brief worried a ≤45° dome floor over the bore
would recess the sand floor at dish centre. This design has no dome: the
self-supporting substitution is the **raked rim** — the mouth's rim plane
descends from the tube crown to the low rim, and that rake is the vault over
the entry, outboard of the bore. Nowhere does a flat ceiling cross the bore, and
the sand floor is one flat plane: measured at y = −60.00 mm across the whole
flat run, i.e. a uniform 18.00 mm of sand below the fill line everywhere on the
floor. The only geometry above the floor before the rim is the beach itself.

## Sand depth 15 vs 20 (brief open question 2)

The parameter carries it. 18 was chosen, not 15, for two reasons that close
together: the welfare source behind the brief's floor says 2–3 cm (15 is the
floor, not the target), and 18 is what closes the ~250 mL capacity row under
the 199 mm print ceiling while keeping `lip_h − sand_depth ≥ 2` (asserted; at
18 it sits at exactly 2 — sand line 2 mm below the port invert, so a quarter-turn
shake does not feed the run). `-D sand_depth=20` is a valid override for an
owner who wants the full 2 cm; the assert will refuse anything past 18 with the
default lip.

## The height ceiling

The CI test-slice runs PrusaSlicer's **factory-default profile**, measured here
with calibration boxes: a 200 mm-tall box slices, a 201 mm box fails "exceeds
the maximum build volume height". `scripts/gate.sh`'s `slice_one()` passes
process flags only — no printer profile, no per-design override — so 199 mm is
the hard ceiling this design asserts against (`z_far_out − z_tip ≤ 199`).

That ceiling drove the geometry, in three telemetry-recorded iterations
(`build/design-run-telemetry.ndjson`, iters 1–3; scores 76 → 84 → 84, fail
lines 0 → 1 → 0):

1. **Single-hull widening** (tube → dish section, one hull): the rounded-rect
   corners sit farthest out and drove the skirt to **59.6°** — the facet census
   measured 7484 mm² of >45° unbridgeable overhang (printcheck's "7% needs
   support", score 76). The far wall was also a flat 110 × 31 mm ceiling.
2. **Lengthening the flare** to pull the corners under 45° pushed the print
   height to 227.4 mm — and the slice failed, which is how the 200 mm ceiling
   was discovered and measured.
3. **Staged widening** (what shipped): two hulls. Hull 1 grows the tube into a
   **stage-1 circle** spanning the dish's full depth — a circle is the cheapest
   widening target there is, growth = `lip_h` regardless of dish width — over
   `flare_run = lip_h + 2 = 22`. Hull 2 grows the circle into the dish section
   over `widen_run ≈ 22.2` (corner-boundary travel + 2 margin, asserted). The
   far wall became a 44.16° ramp (asserted `ramp_run ≥ ramp_rise`), and the
   height budget the single hull spent on flare went to **floor run** instead.

The capacity trade that lands under the ceiling: `dish_w = 110` (brief-exact) ×
`sand_depth = 18` × `floor_run = 96` → print height **197.155 mm**, measured
capacity 245.5 mL. **The escape hatch on a taller printer is `-D floor_run=…`,
never `dish_w`**: width is brief-pinned and buys less capacity per millimetre
than run does; run is pure length. `-D floor_run=140` fits a 250 mm-tall volume.

A note for the platform, not this design: `printcheck.args` says
`--build-volume 256x256x256` (family-consistent with the other NUGGS modules)
while the slicer test tops out at 200 mm — a printcheck/slicer mismatch worth a
follow-up issue on the harness, mentioned in the PR.

## Overhang census

G1 evidence is a **facet census of the exported body STL** (ASCII STL parsed to
facets; per-facet normal / area / centroid; bands: bed contact `nz < −0.5` near
`z_min`, overhang `nz < −0.7071` (>45°), bridge `nz < −0.995`). A visual check
of `build/nuggs-sand-bath.png` was also run (image analysis of the contact
sheet) and its flags reconcile with the census — the "severe taper" it saw is
the staged skirts in iso foreshortening, and the collar's flat ceiling is the
coupling's own known tier. Numbers, final geometry:

| Band | Area | Where |
|---|---|---|
| >45° overhang, non-bridge | **0.0 mm²** | — |
| 30–45° moderate | 6179 mm² | the two staged skirts (max 42.27°), the far ramp, the raked rim |
| Bridges | port tier + 53.9 mm² | port tier = every NUGGS module's known coupling tier; the 53.9 mm² is the hull→extrusion handover ledge |
| Bed contact | 527 mm² | the three sector tips → brim advisory |

The **handover ledge**: the trough's vertical extrusion starts 1 mm below the
stage-2 hull's top section, leaving a ≤1 mm-wide downward annular ring at
z = 56.16. Slicer-bridgeable (well under the 110 × 31 mm flat-ceiling class the
redesign eliminated), and the same class as the pre-redesign documented ledge.
The census history worth keeping: the first revision's single-hull corners
measured **59.6°** — that number, not a hunch, is what forced the staged
widening.

## Capacity

The audited number is **measured off the exported mesh**, never read from the
echo: `part = "sandbody"` exports the sand fill as a solid (the cavity's void
primitives clipped at the fill surface and cut by the far ramp); its volume by
divergence theorem after BFS orientation repair (ASCII STL export has
inconsistent facet winding; vertices rounded to 1e-4 for shared-edge matching)
is **245.5 mL** against the ~250 mL brief row (−1.8%).

The `.scad`'s analytic `cap_est_ml = 242.583` is a *pre-flight* assert (±5% of
250), derived from the real cross-section shapes:

- the widening zone is a **circular segment** below the fill line
  (`circ_seg_below`) in the stage-1 circle, averaging end-sections across the
  hulls (the mesh runs ~1.2% convex above analytic — the honest direction);
- the trough band is `dish_w × sand_depth` minus the four corner arcs
  `(1 − π/4)·rc²`, capped at the depth;
- OpenSCAD trig is **degree-based**: `acos()` returns degrees, hence the
  `* PI / 180` in `circ_seg_below` (without it the estimate reads 3029 mL and
  trips its own assert).

History, so the heuristic is never trusted again: the first analytic used
rectangle/diameter shortcuts and ran **~10% hot** — claimed 242.3 where the
mesh measured 221.3 at the same draft parameters. The wedges are circular
segments, not rectangles.

## Key decisions

1. **Open module, not a tube** — mouth open for pouring sand and lifting the
   animal out; the brief's "fully open-topped, no lid in v1".
2. **The beach starts exactly at `z_top`** (toe-stub rule): below `z_top` the
   bore floor is the `ri` arc, continuous with the mate's bore to 0.000 mm
   across the joint plane. A flat trough floor pulled down to the port face
   instead would stand the mate's tube proud 9.36 mm at the walk-band edge
   (`lib/nuggs-coupling-mates.conf`, the open-module case). The flat floor
   belongs wholly beyond the port zone.
3. **Staged widening** (tube → circle → dish) to fit the 199 mm ceiling — the
   census-driven decision, see above.
4. **Far wall as a ramp**, not a flat ceiling: the dish cannot end in a wall
   perpendicular to the run (a 110 × 31 mm bridge in the print pose); the ramp
   also *adds* a sand wedge instead of costing floor.
5. **Raked rim as the entry vault**: one plane from the tube crown down to the
   low rim; no flat ceiling ever crosses the bore (the brief's
   self-supporting-substitution requirement, satisfied by geometry).
6. **`sand_depth = 18`**, the depth-for-flat-run trade (see above).
7. **`printcheck.args` stays 256³** — family-consistent with every NUGGS
   module; the 200 mm slicer ceiling is handled by the design's own assert, and
   the harness mismatch is flagged for a follow-up, not worked around here
   (contract scope: `designs/nuggs-sand-bath/**` only).
8. **$fa/$fs match the library pin** (`3/0.8`): where this file's tube meets
   the port, mismatched presets split the shell into ~20 bodies under Manifold
   (issue #99, PR #200). Do not "improve" them.

## Print settings

- **Orientation:** as modelled — port down, standing on the three sector tips,
  dish growing up. No rotation needed or wanted.
- **Supports:** none — 0.0 mm² of >45° non-bridge overhang (census above).
  Leave slicer supports off.
- **Brim:** yes — 527 mm² of bed contact on the sector tips is under 5% of the
  footprint (printcheck's advisory; a 4–5 mm brim is enough).
- **Material:** PLA or PETG. PETG if the bath will be washed often.
- **Walls / layer:** 0.4 mm nozzle, ≥ 3 perimeters (`dish_wall = 2.4`), 0.2 mm
  layers.
- **Test-slice reference:** 8 h 55 m / 129.4 g (body, normal mode).
- **Expected slicer notices:** print-stability warning (the brim answers it);
  2 zero-area facets from the port tessellation — the pure-library coupon
  carries 4 of its own, i.e. they come from the coupling, not this junction.
- **Fill with bathing *sand* (0.1–0.5 mm grain), never chinchilla dust** —
  dust is a respiratory irritant for hamsters.

## Print this first

`nuggs-sand-bath-coupon.scad` — two bore-clean `nuggs_neck()` port stubs
(~60 g, 4.5 h). Mate them, or mate one to any NUGGS module you already own, and
tune `port_tol` in ±0.05 mm steps until the quarter-turn locks without rock.
The port tolerance is **untested on any printer** (the lib header's own
warning) — the coupon is mandatory before the full dish.
