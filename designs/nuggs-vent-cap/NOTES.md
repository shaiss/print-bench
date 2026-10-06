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
| Cap length | ≈ 40 mm port face → dome tip | **assumed** — the build comes out at 41.2 (dome tip 41.0 + the crown disc's 0.2 lift); the dome's rise knob is the trade |
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

- **Underside**: `r + z = ri + z_top + seat_clear` (53.1). It clears the
  bore's top edge outward by `seat_clear` = 0.1 mm, so the dome never narrows
  the throat — and never lands ON the neck's bore edge (see "One watertight
  body" below).
- **Outer face**: the same line pushed out by the perpendicular shell
  thickness, `r + z = 53.1 + strand_w·√2` (54.797).
- **Seating** `z_spring = c_out − ro = 12.397`: where the outer line meets the
  wall OD (the profile's foot is pulled `seat_clear` inside it, below). It lands **below** `z_top`, so the dome's seating ring
  (`r ∈ [40.70, 42.4]`) buries inside the wall band and fuses to the tube
  instead of kissing its top face — the same discipline as the y-splitter's
  buried caps. An assert pins `wall > strand_w·√2`: a strand thicker than the
  wall would seat the dome on an edge, not in a band.
- **Cells**: on a 45° face, a horizontal band of thickness `strand_w` has an
  on-slope opening of `strand_w·√2`, so the vertical band pitch is
  `aperture_max/√2 + strand_w` (5.44) and the tangential rib pitch is
  `aperture_max + strand_w` (7.2) — both measured so the **on-surface opening**
  is ≤ `aperture_max` in both grid directions, calipered as a cell *side*
  (hardware-cloth convention, not a diagonal). `n_rib = 38` ribs counted at the
  widest radius the grid reaches — the tube OD `ro` at the spring rim, the
  worst case for any `wall` — and an assert holds the built chord there
  (`rib_gap_max` = 5.80 mm) under `aperture_max`;
  `n_web = 15` crown spokes from the chord bound at the rim. Ribs and crown
  spokes are **half-length radial slabs** (axis → rim), one ray per iteration:
  a full-diameter slab doubles the count whenever `n_rib`/`n_web` is odd
  (dwarf settings `aperture_max=5`/`strand_w=1.6` hit `n_rib=41` and would
  shrink spring-rim openings to ~1.65 mm while the open-area assert still
  read the intended single-ray pitch).
- **Open area**: the on-slope cell fraction is
  `(aperture/ (aperture+strand))² = 0.694` — well over the 30 % floor, and
  asserted so a knob pairing that chokes the vent fails loudly.

### One watertight body (the manifold render's 51/100)

CI's manifold render scored the first lattice 51/100 — non-watertight, edges
shared by more than two triangles, duplicate/degenerate faces, 10 bodies (the
solid variant too). Cause: dome surfaces landing exactly ON neck surfaces. The
library pins its own `$fa`/`$fs`, the dome uses `$fn`, so two circles of one
radius cross instead of coinciding and leave sub-micron slivers that weld into
garbage once exported. Fix, no contact anywhere: the underside clears the bore
edge by `seat_clear`; the outer profile's foot steps in to `ro − seat_clear`
so the seating ring is buried in the wall band, never on its OD; the shell's
cutter overshoots the shell's bottom and top planes by 1 mm; latitude band 0
straddles the shell's bottom plane instead of sharing it; and the crown disc
stops `seat_clear` inside the shell's top outer edge and sits `crown_lift` =
0.2 mm proud of its top plane (it still overlaps the rib tops ~0.5 mm on its
first layer, the original anchoring).

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
the axis as a **hollow shell** closed only near the tip: the outer solid is
differenced against the underside 45° cavity (`r + z = dome_c_in`), leaving a
tip plug of thickness `strand_w·√2` along the axis — the same shell thickness
as the lattice. A filled cone would put a flat disk at `z_spring` across the
bore, an unsupported ceiling the lattice never has; the hollow form is
support-free like the lattice shell (never past 45°), more blocked, no crown
bridge — and it **cannot** respect the 40 mm length budget, because closing
40 mm of radius continuously needs 40 mm of rise. It ends where the geometry
puts it (tip at `z_spring + ro` = 54.7 mm), not where the lattice cap does.
It ships because the brief called it "cheap either way", and it is: one
boolean, no second geometry path to maintain. Owners who want maximum light
block-out (darkness for nesting) over airflow take the taller cap. The
`bore-clean-solid` fitcheck proves the hollow solid still leaves the throat
clear (same probe as the lattice).

Printcheck on the filled cone used to put a number on what the lattice buys:
the lattice's unbridgeable downward-facing surface is **1 %** of the part
(its 45° strands are all sub-5 mm bridges), while the filled solid's flat
disk at `z_spring` plus its smooth 45° face sat at **17 %**. Hollowing the
solid (this tip) drops that ceiling — sticky printcheck on the hollow solid
is **100/100** with no findings, while the lattice stays **84/100** (its
bridged crown still carries the 1 % overhang caveat). The lattice remains
the airflow option; the hollow solid is now the cleaner print.

## Print orientation

Port-axis vertical, **standing on the sector tips** — the family bed-contact
idiom. The dome's 45° slope rises from the wall rim; the lattice strands'
undersides are all sub-5 mm bridges; the crown disc bridges its ~10 mm spokes.
No supports, no brim. PLA or PETG; PETG for gnaw durability.

- **Care (family N7, `designs/nuggs/PM.md`):** hand wash only, ≤ 50 °C; never
  a dishwasher. PLA Tg ~57–70 °C and PETG ~80–85 °C sit at or below a
  dishwasher dry cycle (70 °C+); a warped port is a narrowed bore, so the
  material failure is the injury failure. The README condensation note
  (weekly pull-and-dry in humid rooms) is husbandry on top of that, not a
  substitute for the wash ceiling.

## Print this first

The coupon (`build/nuggs-vent-cap-coupon.stl`, `part="coupon"` in
`nuggs-vent-cap-coupon.scad`) is **two pieces on one plate**: the production
port stub (`nuggs_neck` at `z_top + 8`) and **one** flat cell printed on the
bed at the dome's on-slope pitch (`slope_pitch = aperture_max + strand_w`) —
not a multi-cell puck. Both come from the production modules; nothing is
copied. Owners who already dialed `port_tol` on another NUGGS module can skip
the stub and print only the cell: `part="coupon-cell"` (same production
`lattice_gauge()`, no copied geometry).

1. **Tune `port_tol`.** Print the stub, offer it to the module it must mate
   with (or another NUGGS port you have). Clicks in with a firm quarter-turn
   and no rock → done. Too tight: +0.05 on `port_tol`, reprint. Loose enough
   to rattle: −0.05. The 0.30 default is the standard's, **unmeasured on any
   printer** — the library's own header warns not to trust it blind.
2. **Caliper the one cell.** Strands should measure ~1.2 mm (under ~1.0 means
   your printer is under-extruding — raise `strand_w` to 1.6, not the flow).
   The opening should measure ≤ 6.0 mm; if it measures over, the welfare
   ceiling is breached — shrink `aperture_max` by the overshoot. Measure the
   opening at the top face, not the base: first-layer squish narrows the
   opening at its base, and the dome's openings are printed well above the
   first layer, so a base reading can look small and hide a dome that's
   over 6.0 mm.
3. Only then print the cap. The dome's print behaviour itself is gated by
   printcheck and the test-slice; what only your printer can tell you is in
   the coupon.

The coupon **intentionally has no product-page photo** until a proving print
exists (Drik, PR #636). Hero / contact-sheet / lattice-top / cutaway stay the
showroom; do not "fix" the missing coupon face with a studio render of the
plate. A real print photo is the artifact that belongs there.

## Decisions log

- 2026-09-12: Design opened from the brief (issue #592). Dome architecture
  settled by the length-budget derivation above; fitchecks and coupon idiom
  borrowed verbatim from `lib/nuggs-coupling-mates.conf` and the archived
  `designs/nuggs` coupon. All open questions from the brief were
  non-blocking; the assumed rows above carry the stated defaults.
- 2026-10-05: Coupon stays off the product page until a proving print exists
  — no render-of-the-plate as a stand-in (PR #636 Drik nit). No `PM.md` on
  this design; the hold lives here.
- 2026-10-05: Coupon slimmed to port stub + one production-pitch cell
  (Nadia/Keel eng step on PR #636). Multi-cell puck dropped — charter
  coverage is `port_tol` dial + caliper of `strand_w` / opening only.
- 2026-10-05: Docs-only fold of Drik R4 nits (PR #636): coupon slice cost
  on the Parts line, when the stub can be skipped, "flat cell on the bed
  at the dome's on-slope pitch", and caliper the opening at the top face
  not the base. Stub height and empty field-test log left alone.
- 2026-10-05: CodeRabbit on 25f41e8 — three findings verified and fixed:
  (1) solid cone hollowed (open underside + tip plug) so the support-free
  claim holds; `bore-clean-solid` fitcheck added; (2) rib/web slabs made
  half-length so odd counts (dwarf 5/1.6 → n_rib=41) no longer double the
  rays; (3) `part="coupon-cell"` exposes the cell-only print the README
  already described.
- 2026-10-06: Docs-only fold of Drik R7 nits (PR #636): Solid variant
  section — opaque dark filament advice for the 1.2 mm shell, and
  hollowing cut from ~57 g → ~35 g (~40 % less), not "roughly in half".
  Empty field-test log left alone.

## Field test log
