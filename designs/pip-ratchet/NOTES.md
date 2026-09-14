# pip-ratchet — engineering log

## Goal

A print-in-place ratchet demonstrator (brief #668): one captive wheel that
**freewheels with a click one way (CCW) and locks solid the other (CW)**,
printed as ONE piece — wheel, two compliant pawls and frame in a single
print, no supports, no assembly. The reference shape for a ratchet/freewheel
family: tune the coupon, print the wheel.

## Given / assumed measurements

| Dimension | Value | Status |
|---|---|---|
| Wheel diameter | Ø56 | assumed (brief) |
| Teeth | 24, 15° pitch | assumed (brief) |
| Tooth depth | 1.6 | assumed (brief) |
| Locking flank | **0° from radial** | **GIVEN** — self-locking (docs/advanced-techniques.md Domain 1) |
| Drive flank | ~60° from radial | assumed (brief, coupon-tunable) |
| Pawls | 2, diametrically opposed | assumed (brief) |
| Pawl cross-section t×L×w | 1.2 × **18** × 8 | t, w from brief; **L deviates — see key decisions** |
| Wheel↔frame radial clearance | 0.2 (web_clr), derived as tip-side gap | brief said 0.4 per "the PIP clearance derivation"; the derivation actually splits XY vs Z (CC3) — radial gaps are spread-limited `xy_tol = k_xy·line_w ≈ 0.207`, so 0.2 is the derived number and 0.4 is the *axial* (z_tol, 2 layers) value. Both appear, each in its own direction. |
| Click force | 1–2 N at rim | assumed feel target — **not a gate**; predicted ~3 N peak at t=1.2, the coupon sweep brings it down (K ∝ t³) |
| Frame footprint | ≤ 70 × 70 × 14 | given (brief); built 69 × 69 × 13.7 |
| Material | PETG preferred for the pawls | brief (pop-fidget-card field test: PLA cyclic flex cracked); PLA variant = thinner beams, deferred |

## Key decisions

1. **Pawl free length 18, not the brief's 10.** The pawl must ride up
   `ride_defl = engagement + tip_clr ≈ 1.05 mm` each click. Small-deflection
   cantilever stress `σ = 3E·t·δ / (2L²)`: at L = 10 the pawl root sees
   σ ≈ 40 MPa in PETG (E ≈ 2000 MPa) — at the yield band, no margin. The
   honest number is worse than the naive L: the frame block clamps the beam
   from u = 13, so the *effective* cantilever is ~13 even at L = 18. With
   L = 18 (effective 13): σ ≈ 22 MPa, SF ≈ 2 vs PETG yield ~48 MPa. t and w
   stay at the brief's values; the coupon sweeps t, which moves both K (t³)
   and σ (t) if a printer's PETG needs a different point on that curve.
2. **Beam outside the tips, hook only at the nose.** A beam whose inner face
   slopes from root to nose dips toward the tooth circle and a tooth meets it
   mid-span in bending (stress → ∞ as the slope shallows). Instead the beam
   is a constant-thickness band entirely outside the tooth tips (underside at
   `web_in = r_tip + 0.2`), and only a short, steep hook (~75° from radial)
   at the nose reaches inside the tips to engage. Ride-up load then lands on
   the hook face, near the neutral axis of the beam.
3. **Locking is face-to-face radial.** Nose face and tooth wall are both
   radial planes, gap `lock_gap = 0.5` measured at the tips (the wedge
   narrows inward). Lock load is axial along the beam into its root — no
   radial ejection component, which is what lock_flank = 0° buys; any
   positive lock flank would cam the pawl out under load.
4. **Break-free first motion is designed in (CC2).** The wheel's bottom layer
   prints `z_tol = 0.4` (2 whole layers) above the base, exactly the
   captive-spinner's proven construction: a weak fusion you shear on first
   spin. The cone cap over the bore is the spinner's narrow-bottom 45° cone —
   self-supporting, gap exactly z_tol over the bore edge.
5. **Fusecheck is a direct 2-body assert, not a flexure drop.** The pawls are
   frame material fused to the blocks by design; the only separable body is
   the wheel. A flexure-zone drop around the pawl roots would pass a pose
   where a pawl welds to the wheel; `assert pip-ratchet.stl 2` sees any
   wheel-to-anything weld. Same pattern as captive-spinner / pip-piano-hinge.
6. **Coupon unrolls the production profiles at the root circle.** Same
   `tooth_profile()` / `pawl_profile()`, linear mapping — nothing copied, so
   the coupon tunes what ships. The demonstrator's polar mapping and the
   coupon's linear mapping differ by the polar distortion of a 26.4 mm radius
   over one 15° pitch, sub-0.01 mm.
7. **Three geometry bugs found by the first full-mesh verification, each fixed
   and re-proven by measurement** (the fitcheck intersection came back 15 KB
   non-empty; an ASCII-STL radius/angle histogram of the interference located
   all three):
   - **Wheel phase was mirrored.** The locking wall sat CW of the nose face,
     burying each tooth's tip land inside the hook. The nose face points CCW,
     so the wall that stops it sits `lock_gap` **CCW** of the face
     (`wall_base = pawl_angle + lock_gap_deg`): a CW turn sweeps that wall down
     onto the face.
   - **Beam edges were chords, not arcs.** A polar-mapped polygon with sparse
     constant-radius runs sags inside the intended radius — sagitta
     r(1−cos Δ/2) ≈ 0.79 mm over a 27° chord at r = 28.2, straight through the
     tooth tips mid-span. Both long beam edges are now arc-sampled every ~2°
     (sagitta ~0.004 mm).
   - **Pawls were 90° apart, not diametric** (`i*180/pawls` with pawls = 2).
     Now `i*360/pawls`; the empty fitcheck could NOT discriminate (90° = exactly
     6 tooth pitches, phase-clean either way), so the proof is an angular
     histogram of the frame export: noses at 15.0° and 195.0°, 180.0° apart.
   - **Coupon fixture joints must be volumetric.** Face-tangent cube contacts
     left separate shells in the CGAL output (a third body); every fixture
     joint now overlaps ≥ 0.2 mm, including a bridge over the block's clamp
     zone (frame-to-frame, clear of the flexure) that ties the rails into the
     pawl/block body. Coupon = exactly 2 bodies: strip + fixture.

## Measured on the export (G4 — built mesh, not the typed parameter)

| Must fit / hold row | Brief | Measured on the export | How |
|---|---|---|---|
| Wheel diameter | Ø56 | **55.99** | bbox of `part="wheel"` STL |
| Teeth / pitch | 24 @ 15° | **24 clusters @ 15.00°** | angular histogram of tip-radius facets |
| Tooth depth | 1.6 | **1.60** (valley r 26.400 → tip r 28.000) | vertex radii, teeth zone |
| Locking flank | 0° from radial | **0° by construction** — the wall is the u=0 segment, one angle for both endpoints | `tooth_profile()` + `polar_pt()`; interference-free pose proven by empty fitcheck |
| Drive flank | ~60° | **60°** ramp (`drive_run = 1.6·tan 60°`), coupon-tunable | profile code; visible in contact-sheet |
| Pawls diametric | 2, opposed | **15.0° and 195.0° — 180.0° apart** | angular histogram of frame STL block/beam facets |
| Pawl thickness | 1.2 | **1.22** (band r 28.178..29.396) | facet-centroid radii outside block sectors |
| Pawl width | 8 | **8.00** (band z 2.80..10.80) | vertex z of beam facets |
| Pawl free length | 10 → **18** (documented deviation, decision 1) | **18.0** (beam spans ~36.7° at r≈28.8) | cluster angular span of frame STL |
| Nose engagement | 0.85 below tips | **hook tip r 27.15 = 28 − 0.85** | `r_nose_in` on the export; proven non-interfering by empty fitcheck |
| Radial clearance | derived xy_tol ≈ 0.207 | **bore D 18.414 = 2·(9 + 0.207)** | min vertex radius of wheel STL |
| Frame footprint | ≤ 70 × 70 × 14 | **69.0 × 69.0 × 13.70** | bbox of frame STL / printcheck |
| Coupon | rack + 1 pawl, 2 bodies | **74.0 × 11.1 × 8.0, 2 bodies, watertight** | printcheck on coupon STL |

## Print this first

1. Print the coupon sweep plate:
   `./scripts/render.sh pip-ratchet --sweep pawl_t=0.9:1.5:0.1`, slice the
   resulting `build/pip-ratchet-sweep-pawl_t.stl`, print in PETG.
2. Break the rack strip free in its channel (firm slide). It should click
   freely +x and lock dead −x at every t.
3. Pick t by feel against the brief's 1–2 N rim target: stiffness scales t³
   (t = 1.0 ≈ 1.9 N predicted vs t = 1.2 ≈ 3 N peak). If the strip welded
   into the channel, raise `k_xy` by 0.05 and reprint; if it rattles, lower it.
4. Set `pawl_t` in `pip-ratchet.scad` and print the demonstrator. First
   motion: shear the wheel free (firm twist CCW — the arrow direction), then
   verify it freewheels CCW with a click and cannot be turned CW by hand.

## Print settings (demonstrator)

- **Material:** PETG (pawls cycle every click — the fatigue ranking in
  docs/advanced-techniques.md puts PETG ≫ PLA for cyclic flex)
- **Layer height:** 0.2 (the axial gaps are quantized to it — keep it)
- **Perimeters/walls:** 3 at a 0.4 nozzle; the pawl beam is 1.2 mm
- **Infill:** 15%, any
- **Supports:** none — the only overhangs are the 45° cone (self-supporting)
  and the wheel's first layer over the base (the designed break-free gap)
- **Orientation:** exactly as rendered, base down

## Field test log

<!-- FIELD-TEST entries append below (templates/FIELD-TEST.md). -->
