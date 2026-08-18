# perspective-coin — engineering notes

## Goal

John Cena carries a watch engraved on two sides: *"comparison is the thief of
joy"* on the back (for when he doesn't feel enough) and *"memento mori"* on the
other (for when his head gets too big) — "a keeper of perspective, not time"
([interview](https://www.reddit.com/r/MotivationalThoughts/s/q9BbhOayrd)).
This design turns those two engravings into a two-sided pocket coin, plus a
print-in-place **flipper charm**: the coin captured in a keyring gimbal so you
physically flip it to the reminder you need. Tier reference:
`docs/advanced-techniques.md` Domain 3 (print-in-place kinematics).

## Given / assumed measurements

All assumed (no fit to an external object):

- Coin Ø40 × 5 mm — pocket-coin heft; thickness also sets the pivot height.
- Ring: bore = coin + 2×1.5 mm moat, 6 mm radial width, 6 mm tall.
- Keyring hole Ø4.5 mm — fits a standard 25 mm split ring.

## Key decisions

- **Both faces engraved (debossed), never embossed.** Authentic to a watch
  engraving, and the bed-side face stays printable: engraved text on the
  first layers reads fine; raised text against the bed would not. Depth
  0.6 mm = 3 layers at 0.2.
- **Coin-flip text alignment.** The bottom face's artwork is the top-face
  cutter turned 180° about the pivot (X) axis (`bottom_face_cut()`), so
  flipping the charm end over end presents the back face upright. The small
  engraved diamonds at 3 and 9 o'clock mark the pivot axis on both faces.
- **Pivot = diamond axle in a teardrop socket.** The axle cross-section is a
  45° diamond (self-supporting overhang, four-line contact = low friction
  and low break-free torque). The socket is a teardrop bore (round bowl,
  45° roof) so the pocket roof never bridges — the repo's support-free
  horizontal-hole primitive, cut as a blind pocket in the ring bore.
- **One tuned clearance, horizontal.** `pivot_clear = 0.35` between axle
  vertex and socket wall. This is a horizontal-bore fit — sag-limited on the
  roof side — so it wants more than a vertical-wall 0.2 (the
  captive-spinner anisotropy lesson applied to a horizontal axis). Tune on
  the coupon.
- **The moat does the rest.** Coin edge ↔ ring bore = 1.5 mm; coin and ring
  both sit on the bed, so the only fusable interface is the axle/socket
  annulus. First flip shears the micro-fusion (break-free motion, expected).
- **The flip actually clears.** The coin's edge corner sweeps
  `sqrt(coin_r² + (coin_t/2)²)` = 20.16 mm about the pivot; the bore is
  21.5 mm. Guarded by an assert (`bore_r ≥ flip_sweep_r + 0.8`), so a
  parameter change can't silently make the charm decorative.
- **Socket stays inside the ring.** Bowl bottom leaves ≥ 0.6 mm above the
  ring underside and the teardrop apex ≥ 0.6 mm below the ring top —
  both asserted; that is what forces `ring_t = 6` over the coin's 5.
- **Reeds skip the axle roots** (±14°) so the reeded edge never thins the
  axle attachment.
- Multi-part choice: one `.scad` with a `part` parameter (`coin`,
  `flipper`/default, `cutaway` QA view, plus the two fitchecks) — recorded
  here per convention.
- Legends are absolute-size artwork tuned to Ø40, so the coupon sets
  `engrave = false` rather than shrinking unreadable text.
- **Glyph closing (`engrave_relief = 0.25`).** Bold letterforms carry acute
  material wedges (the crotch of N, M, V) that taper to literal zero width —
  printcheck sampled 0.008 mm walls in the first cut. A morphological
  closing (offset +0.25 then −0.25) on every face cutter truncates each
  wedge at ~0.5 mm and rounds convex corners the way die-stamped text is;
  measured thinnest wall went 0.008 → 0.50 mm.
- **Arc spacing.** Fanned per-char arcs graze on wide glyphs when the slot
  arc at the baseline drops under ~3.5 mm (the original 17-char top arc left
  0.01 mm between O and M). Face A therefore splits into three zones —
  arc COMPARISON / straight IS THE / arc THIEF OF JOY — instead of two
  packed arcs.
- **Emblems are strokes, not fills.** On the bed face every engraved void's
  roof is a bridge, so all filled art stays under ~2.5 mm across (annular
  sun, outlined hourglass bulbs); the first filled bulbs drew a PrusaSlicer
  "long bridging extrusions" stability warning, the stroked ones slice
  silently. Overlap art that nearly touches (bulb base into end bar): a
  0.05 mm land between voids is a printcheck sliver.
- **Sub-45° chamfers (`chamfer_rise = 1.2`).** A 45.0° cone tessellates to
  facets fractionally past 45° and lights up the overhang check; every rim
  chamfer runs its height at 1.2× the radial bite (~40°) instead.
- **Reeds clamped to the straight edge band** with 0.6 mm land to the
  chamfer cones (the chamfer meets the edge at z = chamfer height, so a
  smaller margin leaves a sub-nozzle shelf), and 64 grooves so the lands
  between V-mouths stay over 1 mm.

## Print this first

`perspective-coin-coupon.scad` — the production ring, sockets and axles at a
24 mm disc (include + override, no copied geometry). Print it flat, then flip
the disc firmly to shear the break-in fusion:

1. Fused solid → raise `pivot_clear` by 0.05 and reprint.
2. Spins but rattles along/across the axis → lower `pivot_clear` by 0.05.
3. Sweet spot: flips freely with a faint click, no slop you can feel.

Carry the tuned value into the full-size flipper. The bare coin has no fit
to tune.

## Print settings

- Orientation: as modeled — flat on the bed (both parts; the flipper prints
  in place, coin inside ring).
- Supports: none. The socket roof is a teardrop, the axle is a 45° diamond,
  face engravings are shallow.
- Material: any rigid filament; PLA at 0.2 mm layers is the reference.
  Silk/metallic golds suit it.
- Perimeters before infill on the first layers helps the bed-face legend
  edges stay crisp.

## Status

- Geometry renders clean (CGAL), both faces reviewed in preview, cutaway
  verified: teardrop apex up, clearance ring visible all around the axle.
- Fitchecks wired (`ci.fitchecks`): rotor ∩ ring empty + negative control.
- `gate.sh --slice`: flipper 92/100, coupon 92/100, bare coin 84/100 — the
  coin's residual warnings are structural to a two-sided engraved coin (the
  bed-face engraving roofs count as overhang area — all spans ≤ ~2.5 mm and
  PrusaSlicer slices without a stability warning — and glyph lands between
  0.5–0.8 mm sample as thin). No score-affecting slivers remain.
- Field-tuning pending a real print (pivot_clear 0.35 is the paper value).
