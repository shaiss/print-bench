# snap-cantilever-clip — engineering notes

**Reference design for** `docs/advanced-techniques.md` **Domain 1 (compliant
mechanisms)** — the cantilever snap, the canonical snap-fit — and **CC1
(orientation)**. Tier 1 of the reference-design catalog (epic #204, brief #386).

> **Supersedes the v0 draft** that previously lived in this directory (a
> screw-down cable clip with two C-mouth lips): same catalog slot (item 2),
> different object. Brief #386 defines the part — a plate-edge snap,
> dimensioned from the doc's SLFP relations — so the cable-clip geometry, its
> `lifestyle.conf` and its AI scene are replaced wholesale. The v0 notes'
> one reusable lesson (author the flexure silhouette in the bed plane) carries
> straight over and is structural here too.

## Goal

A one-piece clip that snaps onto a plate edge and holds by cantilever
deflection. Push it onto 3 mm card / shelf stock, the finger cams open over
the plate, springs back, and the clip grips by spring preload — removal takes
~2× the insertion force via the steep retention shoulder.

## Given (brief #386)

| Quantity | Value | Status |
|---|---|---|
| Plate thickness to grip | 3.0 mm | assumed (shelf/card stock) |
| Plate seating depth | 20 mm | assumed |
| Insertion force | 4–8 N | assumed |
| Root fillet r | ≥ 0.5·t | **given** (doc fatigue rule, asserted) |
| Flexure thickness t | ≥ 0.8 mm | **given** (repo min feature, asserted) |
| Body footprint | ≤ 60 × 25 mm | assumed |
| Hook deflection at insertion | ~15° | assumed — see the trade below |
| Material | PETG, E ≈ 2000 MPa design datum | assumed (PLA unsuitable) |
| Printer | 0.4 nozzle, 0.2 layers, flat, flex axis ∥ layers (CC1) | given |

## Derivation — the doc's relations, not guesses

The SLFP relations (`docs/advanced-techniques.md`, Domain 1) are evaluated at
render time (echoed by `render.sh`; see the top of the `.scad`):

```
I  = w·t³/12          = 15·1³/12          = 1.25 mm⁴
K  = E·I/L            = 2000·1.25/12      = 208.3 N·mm/rad
δ  = grip_p − tol     = 1.4 − 0.2         = 1.2 mm
θ  = 1.5·δ/L          (tip-load shape)    = 8.59°
F  = 3EIδ/L³          = 5.21 N            ← in the 4–8 N band
σ  = E·t·θ/L          (tip-load bound)    = 25.0 MPa
σ_doc = E·t·θ/(2L)    (pure-moment ideal) = 12.5 MPa
```

σ_tip-load 25 MPa sits at ~half of PETG's ≈50 MPa yield (static SF ≈ 2 at the
bounding shape) and at the ~25 MPa cyclic comfort line. Insertion felt force:
the 30° lead-in ramp multiplies F by tan(30°+φ) ≈ 1.06 (μ ≈ 0.3) → ≈ 5.5 N.

### The "15° deflection" assumption, and why the default is 8.6°

The brief marks 15° *assumed*, and it is the one number the physics declines:
with the tip-load shape δ = (2/3)·L·θ and the given t ≥ 0.8 floor,

- θ = 15° at L = 12 needs δ = 4.19 mm — grip_p ≈ 4.4 mm, which is thicker
  than the 3.2 mm channel itself; or
- keeping δ bounded (σ ∝ θ) puts the root at σ = E·t·θ/L ≈ 44 MPa at t = 0.8 —
  inside 20% of yield, far over any cyclic comfort, for a part whose whole
  job is to flex repeatedly.

The design therefore targets **σ ≤ 25 MPa and F ∈ 4–8 N** and lets θ land
where the relations put it: 8.59°. θ is behaviour, not geometry — it is not
mesh-measurable; the coupon is where a user who wants a snappier 12° raises
`grip_p` and accepts the stress. Every mesh-measurable brief row (plate grip,
footprint, r ≥ 0.5·t, t ≥ 0.8) is met exactly.

## Key decisions

- **Orientation (CC1, structural):** the whole silhouette is authored in the
  XY (bed) plane and extruded up in Z to `w` = 15. The finger bends *in the
  layer plane* — bending stress runs across roads within a layer, never across
  the weak bond between layers. Printed upright, the finger delaminates on the
  first insertion (doc Domain 1, rule #1).
- **Mechanism geometry:** plate enters the mouth at y = 0 and seats against
  the strap face at y = 20. Channel gap = 3.2 (3.0 plate + 0.2 slide). The
  finger hangs from the strap on the plate's entry side, its lip protruding
  1.4 mm into the channel (throat 1.8). Insertion: the plate edge rides the
  30° ramp, camming the finger out by δ = 1.2; seated, the lip springs back
  onto the plate face and preloads it against the stiff jaw with F_snap —
  that preload **is** the grip. Removal re-cams the same finger on the 45°
  shoulder ≈ 1.85–2× insertion; `shoulder_deg = 90` is non-releasing.
- **Guard rail (hard stop):** the doc's motion-limiting rule. A rail stands at
  the finger's overtravel limit, δ + 0.3 mm beyond the snap deflection, so an
  over-hard push bottoms on plastic instead of folding the flexure to failure.
  It also ties the finger, strap and wall into one torsionally-stiff body.
- **Root fillet construction:** the fillet is the corner square
  [0, f] × [plate_depth−f, plate_depth] **minus** the disc (centred at the
  far corner) — material added into the channel at the concave root. The
  obvious alternative (the disc quadrant itself, via `intersection`) touches
  both walls at single tangent points and never welds into the union: 12 naked
  edges, printcheck 75/100, iteration 1. `difference` puts the fillet's
  straight edges exactly on the finger face and strap face, where the union
  welds them.
- **Fillet-vs-seat tradeoff, recorded honestly:** r = 0.6 ≥ 0.5·t intrudes to
  x = 0.6 at the strap face, while the seated plate's near face sits at
  x = 0.2 — so the plate's leading corner meets the fillet arc at y ≈ 19.85
  and seats ~0.15 mm shallow of nominal. That is inside the 0.2 mm clearance
  band and irrelevant to grip (grip is lip preload at y ≈ 8, not the seat).
  Fully clearing the plate would need r ≤ 0.2 < 0.5·t, which trades a
  fatigue rule (given) for 0.15 mm of seat — the wrong trade. Documented here
  for the reviewer.
- **Blunt lip apex:** the tooth tip is a 0.8 mm flat, not a knife edge — no
  first-layer pin, and the contact preload spreads over a real area.
- **Mouth funnel:** 45° × 1.2 chamfer on the stiff jaw's mouth corner lets a
  tilted plate self-align on entry.
- **$fn = 96:** only the root-fillet arc is curved, and it is the
  fatigue-critical surface, so it gets the smooth setting.
- **Parameters as customizer sections**, every brief row a named variable
  with its unit; guards assert r ≥ 0.5·t, t ≥ 0.8, throat ≥ 0.8, cam-angle
  ranges, and that the guard sits past the deflection.

## Print this first

The clip is already coupon-sized (~16 min, 2.6 g), so
`snap-cantilever-clip-coupon.scad` is the **production part unmodified** —
print it, snap it onto a 3 mm card edge, and *feel* the insertion before
committing to any retuning. Tune in this order:

1. **`t` first** (stiffness ∝ t³, stress ∝ t/L — the highest-leverage knob).
   Too hard to push → lower t; sloppy retention → raise t.
   Sweep: `./scripts/render.sh snap-cantilever-clip --sweep t=0.8:1.6:0.2`
2. **`root_fillet` second**, keeping r ≥ 0.5·t (asserted).
   Sweep: `./scripts/render.sh snap-cantilever-clip --sweep root_fillet=0.5:1.2:0.1`
3. `grip_p` only after t is settled (it sets both δ and the preload).

## Fatigue (qualification caveat)

Doc ranking for flexure fatigue: **TPU ≈ PP > Nylon > PETG ≫ PLA.** PETG is
the brief's assumed material and is acceptable, but the root stress bound
(25 MPa tip-load shape) is a design-datum calculation from E = 2000 MPa, not a
qualification — and the **cycle-count target is deliberately undecided**
(the brief defers it to review). Until a target is set, qualify on the coupon:
snap it 20×, inspect the root fillet; any whitening line or creep set there
means stop, raise `t` or `root_fillet`, and requalify. PLA is disqualified for
the flexure (it work-hardens and cracks); PP prints this same geometry far
past PETG's cycle life if the printer can run it.

## Deferred / out of scope (per brief and epic rulings)

- Sibling catalog designs (#385, #387–#393) — other briefs.
- Flexure-primitive library extraction (`lib/compliant.scad`, issue #202):
  epic #204's chunker ruling keeps **lib/ changes out of design PRs**. The
  candidates this design would contribute — the corner-square-minus-disc root
  fillet (weld-safe where the naive disc quadrant is not), and the
  cam-profile lip (ramp/shoulder angles from force targets) — are recorded
  here for the lib PR to harvest, not implemented in `lib/`.
- Cycle-count target → decided at review (above).

## Field test log

(no entries yet — append with `./scripts/field-test.sh` or the
"Log a print result" Action; format `templates/FIELD-TEST.md`)

## Status

- [x] `render.sh` clean; bottom-iso inspected: flat-extruded silhouette,
      every wall vertical, full-bed contact, zero overhangs
- [x] `gate.sh --slice` green (iteration 2): printcheck **100/100 both parts**,
      watertight, PrusaSlicer test-slice 15m37s / 2.56 g
      (iteration 1: 75/100, not watertight — the tangent-point fillet, fixed)
- [x] Coupon wrapper shipped and gated (`-coupon.scad`, production values)
- [x] Predicted K, θ, F, σ echoed at render and recorded above
- [x] Brief audit measured off the export, both directions (gap 3.201,
      throat 1.801, seat 20.000, t 0.997, r 0.600 on 48/48 arc vertices,
      ramp 30.0°, shoulder 45.0°, footprint 9.90 × 24 × 15 → F = 5.16 N,
      θ = 8.59°, σ = 24.9 MPa from measured geometry)
- [x] Product page (readme-gate green), PM charter, frozen camera set +
      hero shipped; v0 lifestyle artifacts deleted with the superseded
      cable-clip
- [ ] Human review of the shape (the merge decision)
