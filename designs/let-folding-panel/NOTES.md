# let-folding-panel — engineering notes

**Reference design for** `docs/advanced-techniques.md` **Domain 1 (compliant
mechanisms), the lamina-emergent (LET) family** — "the best FDM match" — and
**CC1** (orientation). Tier-2 "harder". Brief: issue #388.

## Goal

Two rigid panels joined by a Lamina-Emergent Torsional (LET) joint: fabricated
flat from one sheet, folds to 90°, zero clearance / zero assembly / no rattle.
The alternative to a pin hinge when you want a fold, not a full revolution.

## Given / assumed measurements (issue #388)

| Quantity | Value | Status |
|---|---|---|
| Fold angle | 90° | **given** |
| Min feature thickness | t ≥ 0.8 mm | **given** (repo floor, 2 extrusion widths) |
| Root fillet | r ≥ 0.5·t | **given** (doc stress rule) |
| Panels | 2 × 70 × 45 × 3 mm | **assumed** (brief left panel size open; stated default) |
| Cycle life | hundreds of folds | **assumed** → drives material choice + coupon |
| Material | PETG / PP | **assumed** (doc Domain 1 fatigue ranking; PLA unsuitable) |
| Style | none | **given** (brief) |

## Topology (how the model realises a LET)

Fold line along X at y = 0.

- A thin **torsion bar** (t × w cross-section) lies on the fold line, built
  half into each panel's group so both halves carry root fillets — symmetric
  in stress as well as shape.
- Each panel reaches the bar only through a row of **fingers**; the rows are
  **interdigitated** (A at even pitches, B at odd). `pitch = finger_w + L`, so
  the free torsion span is *exactly* the `L` you set — a realized dimension,
  not a nominal one.
- Fold about X: adjacent fingers pull the bar in opposite Z directions, so each
  bar segment *between* two fingers **twists** (torsion) while each finger root
  **bends**. Torsion dominates the compliance — the LET signature, and why ROM
  is high and root stress low vs a plain living hinge.
- The hinge zone (bar + fingers) prints **thin** (`t`) while the panels stay at
  `panel_t` — compliance is concentrated in the joint, not the panels.

Verified on the folded preview pose (`previews/folded-pose.png`, `demo_fold=95`):
panel B stands, its fingers reaching the flat bar, interdigitated with A's.

## Parameters (the doc's LET knobs)

| Knob | Default | Effect |
|---|---|---|
| `t` | 1.2 | **dominant** — bar stiffness ~ t³, so fold force rises steeply with t |
| `L` | 14 | free torsion span — longer bar twists at lower strain (tear fix) |
| `w` | 2.0 | bar width across the fold line |
| `r` | 0.8 | root fillet at every finger↔bar junction; doc rule `r ≥ 0.5·t` |
| `theta_max` | 90° | the angle the echoed predictions are quoted at |
| `fingers` | 4 | total interdigitated fingers; spans = fingers − 1, in **parallel** |
| `finger_w` | 3.5 | finger width along X |
| `finger_reach` | 6 | finger run across the fold line — sets the bending length |
| `hinge_w` / `panel_d` / `panel_t` | 70 / 45 / 3 | the panels |

Guards (asserts in `main()`): `t ≥ 0.8`, `r ≥ 0.5·t`, `w ≥ 1.2`, `L > 2r`,
`fingers ≥ 3`, `finger_reach > w/2 + 2`.

## Echoed predictions — calibration starting points, not guarantees

`main()` echoes, per the doc's governing relations at `theta_max = 90°`
(E = 2000 MPa assumed PETG, ν = 0.4):

- Rectangular-section torsion constant `J = w·t³/3 · (1 − 0.63·t/w + 0.052·(t/w)⁵)`
- **`K_joint = 110.4 N·mm/rad`** (3 spans × 36.8, spans in parallel)
- **`sigma_root = 377 MPa`** — the doc's bending upper bound *if one root took
  the full fold*; not reached in practice because torsion carries most of it
- **`tau_bar = 93.5 MPa`** — torsion surface shear `G·θ·r_c/L`, the **design
  stress** here (torsion dominates)

The coupon arbitrates; these numbers exist so a measured fold force has
something to be compared against. E is the biggest unknown — a real PETG may
be 1800–2500 MPa, swinging K proportionally.

## Key decisions

- **Holding the 90° fold is out of scope for v1.** The joint is elastic: it
  folds to 90° and springs back unless held (that is what a torsional flexure
  *is*). A detent/over-center lock would be a second mechanism — brief left it
  open, so v1 is the joint itself and the fold-hold question is backlog (see
  PM.md). Recorded per the brief's instruction to note this in NOTES.
- **`t = 1.2` (not the 0.8 floor)** — headroom for the t³ stiffness budget and
  above the 2-extrusion-width minimum with margin; the sweep tunes it.
- **Panels assumed 70 × 45 × 3** — brief gave no size; 3 mm is ≈10 perimeters,
  rigid next to a 1.2 mm bar, so the compliance stays in the joint.
- **Both bar halves carry root fillets** (each built by its own morphological
  closing) — symmetric stress, no single worst-side root.

## `lib/` candidates (issue #202) — NOTES only, deliberately not in this PR

The LET parameterization (`t/L/w/r/theta_max` + the J/K/τ relations above) and
the morphological-closing root fillet (`offset(-r) offset(r)` on a hinge
silhouette) are candidates for `lib/compliant.scad` once a second design needs
them. This PR keeps them in the design file so the reference lands first; no
`lib/` changes ship here.

## Measured off the export (G4 evidence)

From `build/let-folding-panel.stl` (ASCII facet parse), not the parameters:

| Brief row | Measured |
|---|---|
| Panel width 70 | X bbox = **70.000 mm** |
| Panel depth 45 × 2 | panel A y ∈ [−51, −6] = **45.000**; panel B y ∈ [6, 51] = **45.000** |
| Panel thickness 3 | Z bbox = **3.000 mm** |
| t ≥ 0.8 | pure torsion-bar band (|y| ≤ 1) top Z = **1.200 mm**; facet top-Z histogram 400 @ 1.2, 28 @ 3.0, 144 @ 0.0 |
| r ≥ 0.5·t | assert in `main()` fires during the render (export cannot exist with it violated) + visible fillets in preview |
| Fold 90° | `theta_max = 90` parameter + `previews/folded-pose.png` (`demo_fold=95`) |

Coupon: 52.50 × 42.00 × 3.00 mm bbox.

## Print settings

Flat, no supports — it is a flat sheet (70 × 102 × 3 mm as printed, hinge zone
1.2 mm). `demo_fold` is a **preview-only** pose; the printed model is always
`demo_fold = 0`. Material matters for a live flexure: PETG/PP/nylon/TPU fold
for hundreds of cycles, **PLA cracks** (doc Domain 1 fatigue ranking).
0.2 mm layers, 100% infill or high perimeters.

## Print this first (coupon)

`let-folding-panel-coupon.scad` — the production LET joint at hand scale
(3 fingers → 2 real torsion spans, straight from the production modules).
Print it, fold it to 90°, cycle ~50 times. It should fold smooth and not tear.

- **Too stiff / too soft?** Stiffness is **t³** — sweep it:
  `./scripts/render.sh let-folding-panel --sweep t=0.8:1.6:0.2`
  (r = 0.8 default keeps every swept t clear of the `r ≥ 0.5·t` assert).
- **Tearing at a root?** Tearing is **strain** (θ·r/L), not stiffness — fix it
  by lengthening L (drop a finger) or narrowing w, **not** by thickening t.

## Status

- Renders clean; `gate.sh --slice` green (main 100/100, coupon 100/100);
  telemetry captured (iteration 1, gate.ok = true).
- Frozen previews committed: `contact-sheet` (as-printed) + `folded-pose`
  (`demo_fold=95`). `hero.png` is a `shots.conf` bpy shot — CI regen re-renders
  it from the moved `.scad` (issue #69 rule: committed previews must not be
  older than the source beside them).
- Backlog: fold-hold mechanism (detent/over-center), `animations.conf` fold
  animation, `lib/compliant.scad` extraction (#202).
