# battery-caddy — engineering notes

## Goal

A one-piece wall-mounted AA/AAA cell caddy (brief: issue #704). Vertical
lanes store a gravity-fed column of cells; the bottom cell of each lane is
pinched by printed compliant spring blades and pulls out one-handed against a
tunable release force. 4 × AA + 4 × AAA on a spine, 2 × M4 wall screws.
Style: `workshop-utility`.

## Given / assumed measurements

Everything in the brief's *Must fit / hold* table is **assumed** — IEC
nominal envelopes, not the owner's calipered cells. Caliper before printing
the full body; every number below is a parameter.

| Quantity | Value | Status |
|---|---|---|
| AA cell | Ø 14.5 × 50.5 | assumed — IEC R6 nominal |
| AAA cell | Ø 10.5 × 44.5 | assumed — IEC R03 nominal |
| Lane bore over cell | +0.4 (`cell_clearance`) | assumed — repo fastener-hole convention |
| Retention | ~5–10 N one-handed withdraw | assumed feel target — `finger_t` + coupon |
| Mount | 2 × M4, Ø 4.5 clearance, 16 mm pitch | assumed — brief's rail vocabulary |
| Lanes | 4 AA + 4 AAA | assumed v1 default footprint |

## Key decisions

- **Retention = side pinch, not underhang.** Floor-rooted blades protrude
  `pinch` (0.35) into each bore from both x-walls over the bottom 13 mm
  (`finger_h_aa`; 9.5 for AAA) of the lane. Throat = bore − 2 × pinch
  (13.8 mm AA / 9.8 mm AAA) vs cell Ø 14.5/10.5. The bottom cell is dragged
  out along y between the blade flanks (sliding against the spring load);
  the cells above cannot escape sideways or forward (0.2 mm play per side).
- **Blades print as vertical fins** — constant cross-section standing on the
  lane floor, so the flexure bends **in the bed plane**, the correct fatigue
  orientation (docs/advanced-techniques.md, Domain 1), and needs no supports.
  Stiffness ∝ t³, which is why `finger_t` is *the* coupon knob, not the
  reach or the height.
- **Blade root and relief.** Each blade is embedded 0.8 mm (`foot_h`) into
  un-pocketed wall at its floor root, with a `foot_w` flare on the outboard
  (tension) face; above the root a `pocket_d`-deep relief pocket (1.65 mm)
  leaves the blade free to deflect. Divider web between two opposing
  pockets: 0.9 mm.
- **Loading path.** Funnel flares (`flare_w` 1.1 × `flare_h` 5) open each
  lane top; a dropped cell's nub passes the throat untouched and its Ø
  shoulder cams the blades open on their 45° tip lead-in (`tip_c` 0.8) —
  the brief's "press down, fingers ride the shoulder" gesture. `tip_c` must
  stay below `finger_t` or the blade polygon self-intersects (see traps).
- **Fitcheck interpretation** (documented deviation from the brief's literal
  spec): the brief's Ø 14.9/10.9 proxy sits *exactly* on the bore surface —
  a coincident-face boolean that reports phantom interference. The positive
  check uses `grow = 0.3` (Ø 14.8/10.8 — still over any realistic brand
  spread of the nominal cell) against the **fixed body only**; the negative
  uses `grow = 0.7`. Springs are excluded from rigid-proxy seating (a rigid
  proxy cannot seat past a preloaded spring by construction) and proven
  separately: `throat_grip` (blades ∩ nominal cell ≠ ∅ — the pinch is real)
  and `finger_relief` (blades rigidly offset by `pinch` clear the fixed
  body above the root and in front of the back plate — the relieved span
  can actually move).
- **Mount realized on the spine**: two Ø 4.5 M4 clearance holes 16 mm apart
  vertically through the back plate between the lane groups. Ø 4.5 is the
  `printability.scad` M4 clearance; the style's `style_hole_d = 3.4` is an
  M3-ish tap-drill advisory and is **intentionally not followed** — the
  brief names Ø 4.5 explicitly (a recorded style exception, printability
  wins).
- **Divider tops carry a bullnose** (r = `divider_t`/2 = 2.7 mm): the style
  pack's rounded utility lip. `divider_t` is 5.4 rather than the structural
  minimum 4.1 precisely so the bullnose radius lands inside the pack's
  corner-radius window (2.6–5.4 mm) — a lane grid of sharp-topped slabs
  measured off-family (the rounded-edge vocabulary split ~50/50 between a
  spurious sub-window mode and the back plate's r=4). The bullnose is drawn
  in (x, z) and extruded along y, so it prints as a constant vertical
  cross-section like the blades — no overhang — and it sits 190 mm above
  the blade/funnel fit zone, touching no gated geometry. The end walls
  (3.0 mm) stay square: too thin to carry an in-family radius.
- **Category**: `everyday-functional` (cell storage for the household
  shelf) — the compliant mechanism is the means, not the product.

### OpenSCAD 2021.01 traps hit (and fixed) here

- `$`-specials resolve **lexically to undef** on plain-assignment RHS inside
  a `children()`-style block (`b = bore_d($cd)` → "Ignoring unknown
  variable") but work in module arguments and `let()`. Every consumer of
  `each_lane()` uses `let (b = bore_d($cd), ...)`.
- A self-intersecting `polygon()` under `linear_extrude` exports clean as a
  lone top-level object (no CGAL validation) and only fails
  "not closed! … CGAL_Nef_Polyhedron" once unioned. Root cause of the
  original blade crashes: `tip_c` 1.5 > `finger_t` 1.3 crossed the outer
  face. Fixed `tip_c = 0.8`; the constraint is commented at both constants.
- Coincident boolean faces report as phantom interference: the relief
  fitcheck originally failed with 224 zero-volume facets, all within 0.01
  mm of the wall plane shared by the blade back face and the pocket cut.
  `above_root()` now scopes the check to the free span (above the root in
  z, in front of the back plate in y); the negative control still fires.
- The same coincidence breaks *unions*, not just checks: lane-floor cubes
  with side faces exactly coplanar with the (bullnose, rotated-extrusion)
  divider flanks left 7 non-manifold edges — printcheck 59, watertight
  false — even though floor-cube ∪ divider-cube alone is harmless. Rule:
  never let a cube face coincide with a rotate_extruded/extruded-union
  face; `lane_floors()` now overlaps 0.01 mm into each flanking wall
  (measured: 0 non-manifold edges, printcheck 100/100).
- Boolean kernels disagree about coincident faces, so a fitcheck green on
  one backend is not green on the other: `finger_relief`'s clip plane sat
  exactly on the pocket floor (both `floor_t + foot_h`) — CGAL 2021.01
  resolved the shared boundary to zero (local gate green), the Manifold
  nightly backend (CI's render gate) reported 32 phantom facets of
  interference. `above_root()` now clips 0.05 above the foot; the checked
  span is still the whole working finger, and the negative control still
  fires.

## Print orientation

Back plate flat on the bed; lanes run along the printer X. Footprint
206.5 × 164.4 × 18.1 mm (the 4-high AA column claims the long axis; fits a
250 × 210 × 220 volume). **No supports** — every overhang is either a bed
chamfer, a funnel wall at 45°, or a vertical fin. PETG preferred for the
springs (fatigue-tolerant); PLA workable with a coupon-thinned finger. A
brim helps if the bed adhesion is marginal — the 18.1 mm-tall walls are long
and thin. 0.2 mm layers, 3 perimeters.

## Print this first

`battery-caddy-coupon.scad` — one AA lane, two cells tall, production finger
geometry (~1 h 53 m, 22 g). Load it with two cells and pull the bottom one
out:

1. **Too hard to pull** (target is one-handed, firm but not a fight):
   reduce `finger_t` 1.3 → 1.2 in 0.1 steps — stiffness goes as t³, so 0.1
   is a big step; try the pull after each.
2. **Cells fall out on their own**: increase `finger_t`, or raise `pinch`
   0.35 → 0.45.
3. **PLA**: start at `finger_t = 1.2` — PLA prints stiffer than modeled
   (the pop-fidget-card field test's 1.5 → 1.3 finding).

Reprint the coupon per change; only print the full body once the pull feels
right. If your cells caliper over Ø 14.6, raise `cell_clearance` instead of
touching the springs.
