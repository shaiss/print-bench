# nuggs-vent-cap — engineering log

## Goal

The NUGGS **vent cap** (issue #592, the filter body the ecosystem names but
doesn't have): the standard genderless quarter-turn port face closed by a
**support-free lattice dome**. Air and light pass; bedding stays; the animal
cannot. Charter **N2** caps a continuously enclosed run at 2 × body length
between breaks, and today the only way to *end* a run is a solid cap — which
seals it dead (ammonia and CO2 build up in an enclosed system) — or leaving it
open, which is an exit. The vent cap is the third option: an enclosed end that
breathes. It does **not** break a run the way nuggs-open does (air passes, the
animal cannot), so under the run-length rule it is still an end.

## Given / assumed measurements

| Measurement | Value | Source |
|---|---|---|
| Bore / port standard | 80 mm bore, full `nuggs_cfg()` defaults | given — `lib/nuggs-coupling.scad` |
| `port_tol` | 0.30 mm | given — the standard's default; **unmeasured**, coupon-tuned |
| Port projection | 10 mm (`port_proj`) | given — `nuggs_cfg()` default |
| Lugs per port face | 3 (`n_lug`) | given — kinematically determinate |
| Lattice aperture | ≤ 6.0 mm | **assumed** — the 1/4″ hardware-cloth convention; one parameter (`aperture_max`, dwarf keepers: 5.0) |
| Lattice strand width | ≥ 1.2 mm | given — repo wall floor (3 perimeters at 0.4 mm) |
| Open area | ≥ 30 % of the cap face | **assumed** — flow target; asserted on the derived cell geometry |
| Cap length | ≈ 40 mm port face → dome tip | **assumed** — the build comes out at 41.0; the dome's rise knob is the trade |
| Filtration (dust) | out of scope | brief — this is a vent, not a filter |
| Condensation | README care line only | brief — no geometry, a husbandry note |
| Solid variant | same design, `lattice=false` | brief — "cheap either way"; costs one boolean and nothing else |
| Added hardware | none (no mesh, no screws) | brief |
| Printer | stock 250×210×220 class | printcheck default bed; the cap is Ø94.9 × 51.0 (measured off the export) |
| Style | none | given — the brief; functional shell language |

## Key decisions

### The dome is a 45° lattice cone, not a solid dome — the length budget says so

The design problem is closing an 80 mm bore with no slicer supports. The
support-free doctrine (`docs/advanced-techniques.md`, "Self-supporting
substitution") closes a ceiling at ≤ 45° from horizontal, and the rule behind
it is an integral one: every millimetre of radius the closure eats costs at
least a millimetre of rise. A **continuous** support-free closure of this bore
therefore needs ≥ 40 mm of rise — and the cap-length budget (~40 mm port face
to tip) already spends 13 of its millimetres on the port zone
(`z_top = port_proj + collar_t`). There is no room for a solid dome.

So the closure is the brief's stated alternative: *"a woven lattice whose
strands each bridge onto the previous ring"*. The dome is a **45° conical
shell** cut into a grid of 1.2 mm strands — meridian ribs that climb the cone
and latitude bands that tie them — running from the wall rim up to a **crown
disc** that bridges the last hole. Physics puts the crown hole there, not
taste: 28 mm of rise closes 28 mm of radius at 45°, leaving a hole of radius
12 mm (disc outer 13.7). Every strand is 1.2 mm wide, so every overhanging
underside is narrower than printcheck's 5 mm bridgeable bound by construction,
and the longest unsupported run in the whole part is a crown disc radial spoke
at ~10 mm — the same territory as the turnaround's accepted 12.2 mm web span.
An assert pins the crown radius at ≤ 13 mm so raising `dome_rise` (a shorter
cap) cannot quietly push the bridge past precedent.

### The dome's algebra (all of it, so the parameters can't drift from the shape)

Both dome surfaces are lines of constant `r + z` — 45° in the r–z plane:

- **Underside**: `r + z = ri + z_top` (53). It passes **exactly** through the
  bore's top edge, so the passage is exactly the bore at the lip — the dome
  never narrows the throat.
- **Outer face**: the same line pushed out by the perpendicular shell
  thickness, `r + z = 53 + strand_w·√2` (54.697).
- **Seating** `z_spring = c_out − ro = 12.297`: where the outer line meets the
  wall OD. It lands **below** `z_top`, so the dome's seating ring
  (`r ∈ [40.70, 42.4]`) buries inside the wall band and fuses to the tube
  instead of kissing its top face — the same discipline as the y-splitter's
  buried caps. An assert pins `wall > strand_w·√2`: a strand thicker than the
  wall would seat the dome on an edge, not in a band.
- **Cells**: on a 45° face, a horizontal band of thickness `strand_w` has an
  on-slope opening of `strand_w·√2`, so the vertical band pitch is
  `aperture_max/√2 + strand_w` (5.44) and the tangential rib pitch is
  `aperture_max + strand_w` (7.2) — both measured so the **on-surface opening**
  is ≤ `aperture_max` in both grid directions, calipered as a cell *side*
  (hardware-cloth convention, not a diagonal). `n_rib = 37` ribs from the
  widest circumference the grid crosses (the spring rim's outer face);
  `n_web = 15` crown spokes from the chord bound at the rim.
- **Open area**: the on-slope cell fraction is
  `(aperture/ (aperture+strand))² = 0.694` — well over the 30 % floor, and
  asserted so a knob pairing that chokes the vent fails loudly.

### Port — the library's neck at minimum length, standing on the sector tips

`nuggs_neck(cfg, z_top)` — one bore-clean unit (port + full-round shell + the
mandatory `nuggs_bore_cut()`), the minimum length the library allows, because
the dome springs straight off the full-round ring the port's inner sectors
fuse to. Every coupling number is the `nuggs_cfg()` default, so the cap clicks
into every existing module. Print pose is the family bed-contact idiom:
port-axis vertical, standing on the sector tips at z = −`port_proj`, exactly
like the straight and the turnaround. The dome rises from there; nothing prints
over void except the bridges named above. (The lib header's mirrored-port idiom
is for flange-mounted ports; this family prints every port tip-down.)

The `bore-clean` fitcheck runs the lib manifest's probe, **scoped to the
throat** — a cylinder inset 0.5 mm from `ri` spanning `z_tip .. z_top`, the
bore the coupling contract is about — because the failure mode the library
warns about (a caller that forgets `nuggs_bore_cut()`) ships a watertight,
sliceable, 100/100-scoring part with plastic standing in the bore. Above
`z_top` the dome fills the bore *by design*, so an unscoped whole-cap probe
would fail on the feature, not the defect.

### Fitchecks — the mated proof, borrowed from `lib/nuggs-coupling-mates.conf`

`mates empty`: the library's own neck, mirrored so its sectors face the cap's,
clocked by `nuggs_clockings(cfg)[0]` (never a hardcoded angle) and pulled
0.01 mm — the seat and the tube face are zero-clearance stops, and at pull = 0
the pair shares whole faces (the lib manifest measured 1466 zero-volume facets
of exactly that; 0.01 mm is a fortieth of a layer and separates coincident
planes and nothing else). `mates-ctrl interferes`: the same pair clocked at 0
instead of half a pitch — outer shell on outer shell, grossly interfering
(the lib manifest measured 9346 mm³ for the mis-clocking). If the control ever
renders empty, the positive check proves nothing.

### The solid variant costs one boolean — and it is taller by physics

`lattice=false` (`part="vent-cap-solid"`) runs the same 45° cone all the way to
the axis: support-free like the lattice shell (never past 45°), more blocked,
no crown bridge — and it **cannot** respect the 40 mm length budget, because
closing 40 mm of radius continuously needs 40 mm of rise. It ends where the
geometry puts it (tip at `z_spring + ro` = 54.7 mm), not where the lattice cap
does. It ships because the brief called it "cheap either way", and it is: one
boolean, no second geometry path to maintain. Owners who want maximum light
block-out (darkness for nesting) over airflow take the taller cap.

Printcheck puts a number on what the lattice buys: the lattice variant's
unbridgeable downward-facing surface is **1 %** of the part (its 45° strands
are all sub-5 mm bridges), while the solid variant's smooth 45° face — sitting
*exactly at* the doctrine's limit — is **17 %** (printcheck counts the limit
itself as overhang, stricter than the slicer rule-of-thumb). The lattice isn't
just the airflow option: it is the one with support margin.

## Print orientation

Port-axis vertical, **standing on the sector tips** — the family bed-contact
idiom. The dome's 45° slope rises from the wall rim; the lattice strands'
undersides are all sub-5 mm bridges; the crown disc bridges its ~10 mm spokes.
No supports, no brim. PLA or PETG; PETG for gnaw durability.

## Print this first

The coupon (`build/nuggs-vent-cap-coupon.stl`, `part="coupon"` in
`nuggs-vent-cap-coupon.scad`) is **two pieces on one plate**: the production
port stub (`nuggs_neck` at `z_top + 8`) and a flat gauge of the dome's own
cell at production pitch.

1. **Tune `port_tol`.** Print the stub, offer it to the module it must mate
   with (or another NUGGS port you have). Clicks in with a firm quarter-turn
   and no rock → done. Too tight: +0.05 on `port_tol`, reprint. Loose enough
   to rattle: −0.05. The 0.30 default is the standard's, **unmeasured on any
   printer** — the library's own header warns not to trust it blind.
2. **Caliper the gauge.** Strands should measure ~1.2 mm (under ~1.0 means
   your printer is under-extruding — raise `strand_w` to 1.6, not the flow).
   Openings should measure ≤ 6.0 mm; if they measure over, the welfare ceiling
   is breached — shrink `aperture_max` by the overshoot.
3. Only then print the cap. The dome's print behaviour itself is gated by
   printcheck and the test-slice; what only your printer can tell you is in
   the coupon.

## Decisions log

- 2026-09-12: Design opened from the brief (issue #592). Dome architecture
  settled by the length-budget derivation above; fitchecks and coupon idiom
  borrowed verbatim from `lib/nuggs-coupling-mates.conf` and the archived
  `designs/nuggs` coupon. All open questions from the brief were
  non-blocking; the assumed rows above carry the stated defaults.

## Field test log
