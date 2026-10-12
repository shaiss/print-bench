# spring-rate-ladder — engineering notes

**Domain 1 (compliant mechanisms) showcase.** The positive-rate coil spring
the catalog's compliant shelf didn't have, built as a *rate ladder*: three
springs differing only in active-coil count, predicted k embossed beside
each, and a coupon that measures what the owner's filament actually does.

Brief: issue #734. Every number below traces to that brief unless marked
otherwise.

## Goal

Give anyone designing a compliant mechanism a **measured spring constant to
design against**. The field-test record says the gap bites: the
pop-fidget-card 2026-08-22 print found PLA flexures printing stiffer than
modeled (snap beam thinned 1.5 → 1.3 mm), and pip-ratchet deferred a whole
PLA pawl variant (#675). A printed spring whose rate is *derived from first
principles and then measured* turns that surprise into a number: measure k
on the coupon, back out effective G for the filament, and log it as a
FIELD-TEST entry (`templates/FIELD-TEST.md`). `printer.conf` write-back of
G is planned (PM backlog B3) — the profile has no G field yet.

## Given / assumed measurements (from the brief)

| Dimension | Value | Status |
|---|---|---|
| Wire Ø d | 1.6 mm (4 extrusion widths) | assumed — above the 1.2 wall floor with margin |
| Coil mean Ø D | 16 mm (index D/d = 10, mid-band 6–12) | assumed |
| Helix lead angle | ≤ 45° at the wire | **given** — support-free convention (`lib/threads-fdm.scad`) |
| Free length | ~40 mm | assumed |
| Active coils N | 4 / 6 / 8 (k ∝ 1/N) | assumed |
| Spring rate | k = G·d⁴/(8·N·D³); G ≈ 3.5 GPa PLA, 1.9–2 GPa PETG | assumed, literature — the coupon measures real G |
| Compress to solid | no yield / permanent set on the *coupon measurement range* (≤ 20 mm) | **scoped** — full-solid on N=4 PLA sits past shear yield (~61 MPa) and will likely take set; README discloses that. FIELD-TEST B1 verifies the measurement range, not N=4 pressed flat. |

All are parametric in `spring-rate-ladder.scad`.

## Key decisions

- **One polyhedron per spring**, not a union of segment primitives: a
  circular wire section swept along the helix is frame-invariant (any
  orthonormal frame ⊥ tangent sweeps the same surface), so the radial/
  tangential frame needs no parallel transport. Rings of `wire_sides` = 20
  vertices at `steps_per_turn` = 48 steps/turn; side quads + two endcap fans,
  wound outward (U × V = T fixes the triangle order). Resolution is tied to
  the wire, not to `$fn`, so a caller's quality preset cannot coarsen the
  coil — the nuggs-coupling lesson applied at design scale.
- **Closed ends at pitch d + end_gap (1.8 mm), end_gap = 0.2**: real closed
  ends have touching dead coils, but a self-tangent polyhedron is
  non-manifold, so the model keeps a 0.2 mm gap — under one extrusion width,
  so the dead coils weld in print exactly as a real closed end behaves.
  Solid height is (N + 2)·d accordingly.
- **Support-free by lead angle, not by round-wire promise**: at the defaults
  the active lead is atan(p/πD) ≈ 10° for N = 4 (9.1 mm pitch) down to 4.6°
  for N = 8, well inside the ≤ 45° assert (N2). Each wrap rests
  *approximately* on the one below — expect a slightly flattened wire
  underside (a free coil is not a screw-thread flank on a solid core); the
  coupon measures the as-printed section. Field-test kill criterion for N2
  is unchanged: sagging wraps reopen the constraint.
- **`ring()` tangent z-term is `slope/(2π)`** (2026-10-11): with the
  unscaled xy frame `[-r·sin(a), r·cos(a)]` the matching z derivative is
  `slope/(2π)`, matching the lead assert's `atan(p/(π·D))`. The previous
  `slope/360` under-tilted the wire ring by π/180 (~3 % elliptical section
  at N=4). Re-emboss is automatic (N4).
- **No d-varying fourth station** (the brief's non-blocking question, left
  to the session on plate space): declined — the ladder's identity is
  "differ only in N" so k ∝ 1/N reads directly; a d-station breaks the
  one-variable comparison *and* changes the wire the coupon tunes. Named
  follow-up, not scope.
- **Cap prints disc-down** (`cap_print()` flips the working pose): then it
  is a cup — bearing face a first-layer surface, skirt walls vertical, post
  hole through the floor. Nothing bridges. Ladder and coupon print
  plate/pad-down as modelled.
- **`ci.plate` for coupon + cap**: the measurement instrument's two
  separately-printed parts ship as `build/spring-rate-ladder-plate.3mf`
  (N distinct objects). The ladder is a standalone single-object deliverable
  and stays off the plate.
- **Stress honesty (predictions, echoed by the render)**: at full solid the
  Wahl-corrected torsional stress is ≈ 61 / 36 / 24 MPa (PLA) and ≈ 34 / 20 /
  13 MPa (PETG) for N = 4/6/8. PLA's shear yield is ~35–45 MPa literature —
  the N = 4 station compressed fully to solid in PLA sits well past it and
  will likely take set; lower G is *protective* (force at solid scales with
  k). This is not gated — it is the material reality the coupon measures, and
  the README says so.
- **Cap seats on the wire's top *surface*, not its centerline** (the iter-1
  fitcheck FAIL: seating the disc at `coupon_spring_top()` — the top wire
  centerline — put it 0.8 mm inside the wire, 484 interference facets).
  `coupon_cap_seat()` = centerline + wire radius + `cap_seat_gap` (0.2 mm,
  one layer) — the resting pose the fitcheck gates; exact tangency would
  hand CGAL a zero-volume contact to classify.
- Embossed values are **computed in the .scad from the same parameters that
  build the geometry** (`k_pred`, `fmt2`), so the plate can never state a
  number the mesh didn't produce.

## Print settings

- **Orientation:** as modelled — ladder plate down; coupon pad down; **cap
  disc down** (flipped in `cap_print()`). The disc-face post-hole mouth has
  a 0.4 mm 45° chamfer so first-layer squish cannot close N5's 0.3 mm radial.
- **Material:** PLA or PETG (measuring the difference is half the point);
  springs live or die by layer adhesion — print PETG slow-cooled / PLA with
  plenty of part-cooling. PETG: start `post_clearance` at 0.8.
- **Layer height:** 0.2 mm (the embossing is exactly two layers; the
  `end_gap` weld assumes ≤ 0.2).
- **Wall width:** 0.40 mm (4 × 0.40 = 1.60 solid wire — not stock 0.42).
- **Seam:** back or scarf.
- **Supports:** none anywhere; expect a slightly flattened wire underside.
- **Perimeters:** the wire is 1.6 mm = 4 × 0.40 — do not thin it; k ∝ d⁴.

## Print this first (the coupon)

1. Print `spring-rate-ladder-coupon.stl` **and**
   `spring-rate-ladder-cap.stl` in one slicer session.
2. Seat the cap: skirt over the spring, hole down the post. It should slide
   down the post and rest on the spring under its own weight. If the post
   hole binds, raise `post_clearance` (+0.2 steps; PETG start 0.8); if the
   skirt scrapes the coils, raise `cap_spring_clearance`.
3. Zero a kitchen scale (must resolve single grams — 1 g ⇒ ~0.01 N). Press
   the cap; convert **F [N] = g × 0.00981**. Read deflection as
   **post-tip-above-disc-top**: at rest the tip sits ~2 mm below the disc
   face; x = (tip-above-disc pressed) − (tip-above-disc at rest). Points at
   5/10/15/20 mm; stop at the 20 mm reading for routine G measurement.
   Pressing toward solid (~27 mm travel on N=6) risks permanent set and
   biases later readings — treat a solid-height check as a separate
   controlled test, not the measurement series. k = slope of F(x); N = 6
   defaults.
   Worked example: 122 g at 10 mm → F ≈ 1.20 N → k ≈ 0.12 N/mm →
   G ≈ 3600 MPa.
4. Back out effective G = 8·N·D³·k/d⁴ and log it as a FIELD-TEST entry
   (templates/FIELD-TEST.md). `printer.conf` write-back of G is planned
   (B3) — the profile has no G field yet.
5. Store the cap **off** the spring between sessions.

The wire-Ø / print-fidelity interaction is the whole experiment: if the
coupon's wire shows visible faceting that shifts k, step `d_wire` to 2.0 and
re-derive (k ∝ d⁴ — re-embossing is automatic).

## Status

**Gate-green; 2026-10-11 act-now round on the PM triage.** CI sticky at
`81e715b` (pre-round truth): ladder 92/100 (WARNING: Thin walls — 10% of
sampled surface under 0.8 mm, thinnest ≈ 0.03 mm — the embossed text
strokes), cap 100/100, coupon 92/100 (WARNING: Thin walls — 2% of sampled
surface under 0.8 mm, thinnest ≈ 0.10 mm; the coupon carries no embossed
text — this is the helical wire's sampled thin sections, not the ladder's
text warning); `ci.fitchecks` both verbs (empty ✓ / interferes ✓). After
this round's emboss bump (value lines 4.0 mm bold / footer 3.0 mm bold),
`ring()` tangent → `slope/(2π)`, and the 0.4 mm 45° disc-face post-hole
chamfer, a local re-gate still asserts clean and shows ladder 92/100
(thinnest ≈ 0.21 mm — improved) / cap 100 / coupon 100; CI will re-stamp
on push. Measured off earlier exports (G4): OD 17.60 / ID 14.40 / wire Ø
1.60 / mean Ø 16.00 / free length 40.00 c2c; +x coil crossings 5/7/9 = N+1
per station; station centres −36/0/+36; coupon post Ø 5.00; cap hole Ø
5.60, skirt ID 18.80.

Sessions so far, in order:

1. Scaffold + first render failed silently (see below) — the vanishing-
   springs debug arc.
2. Root cause found and fixed; clean render; gate iter=1 failed only the
   `fitcheck empty` verb (cap seated on the wire centerline, 0.8 mm inside
   the wire); iter=2 green after the `coupon_cap_seat()` fix.
3. Product page, PM charter, frozen previews, shots.conf; /pm + /preflight;
   draft PR.

### Lessons worth keeping (session resume context)

- **OpenSCAD trig takes DEGREES.** `a = TwoPi*u` collapses a helix to a
  37.7° strand with ~zero volume — and it still renders "watertight". The
  signed-volume test (divergence theorem over the polyhedron's own points/
  faces) is what caught it; `lineage.sh facet-count` misparses ASCII STL.
- **`rounded_box` is corner-anchored** ([0,size] in x/y): center it or the
  origin-centered stations float off the plate.
- **CGAL can exit 0 on a corrupt union** (`SNC_external_structure.h Line
  1078`) — capture full openscad output on any suspicious render; a silent
  exit is not success.
- **A single-segment cylinder's side walls have vertices only at their end
  rings** — vertex-position filters can't see vertical walls; ray-cast to
  measure bores/posts.

