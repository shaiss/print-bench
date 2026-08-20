# perspective-coin — engineering notes

## Goal

John Cena carries a watch engraved on two sides: *"comparison is the thief of
joy"* on the back (for when he doesn't feel enough) and *"memento mori"* on the
other (for when his head gets too big) — "a keeper of perspective, not time"
(as he tells it in an [interview clip shared on
Reddit](https://www.reddit.com/r/MotivationalThoughts/s/q9BbhOayrd)).
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
the disc firmly to shear the break-in fusion. Two *different* clearances tune
two *different* symptoms — this is the whole reason the coupon exists:

1. **Fused solid / won't break free** → raise `pivot_clear` by 0.05 and
   reprint. Ceiling is **0.40** (above it the socket bowl breaks through the
   ring underside — the assert says so); if your printer needs more, raise
   `coin_t` to 5.5 and everything re-derives.
2. **Rattles ACROSS the axis** (radial click, coin wobbles in its plane) →
   lower `pivot_clear` by 0.05.
3. **Slides ALONG the axis** (end-play, coin shifts side to side on the pivot)
   → lower `socket_end_clear` by 0.05. `pivot_clear` cannot fix this — it is
   the radial annulus only. (v0.2 already halved the default float to 0.8 mm.)
4. Sweet spot: flips freely with a faint click, no slop you can feel.

Carry the tuned `pivot_clear` (and `socket_end_clear` if you touched it) into
the full-size flipper. The bare coin has no fit to tune.

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

- **v0.2** — field-driven refinement of the shipped v0.1, in place (not a
  derivative). See `## Changelog` and `## Field test log` below.
- Geometry renders clean (CGAL), both faces reviewed in preview, cutaway
  verified: teardrop apex up, clearance ring visible all around the axle.
- Fitchecks wired (`ci.fitchecks`): rest-pose `fitcheck` + negative control,
  **plus the v0.2 swept-flip `fitcheck_flip`** (the rotor swept across the
  flip must clear the bore *and* the loop tab at every tilt) + its control.
- `gate.sh --slice`: **flipper 100/100, coupon 100/100, bare coin 92/100**
  (with the bridge-aware overhang check — see below). The flipper and coupon
  are clean; the coin's one remaining warning is the *reeded edge* sampling as
  thin wall (the ridge tips), which is cosmetic and removable via `reed_n=0`
  if a perfect score is wanted over the reeding.
- **Why the scores rose from v0.1's 84/92/92:** printcheck's overhang check
  became bridge-aware in this change — a downward region narrower than the
  bridge span (a debossed letter's ceiling, the thin bore-relief chamfer, the
  print-in-place socket roof) is self-supporting and no longer scored as an
  overhang, while a genuinely wide flat shelf still is. The geometry did not
  change; the metric got honest. (Decomposition: the bare coin blank always
  scored 100; every prior deduction was a deliberate feature or a printcheck
  artifact — the analysis is in the PR.)
- The pivot is **field-validated at `pivot_clear = 0.35`** (v0.1 print 1 freed
  first flip). v0.2 targets the field findings, not the pivot recipe.

## Changelog

Design version history, newest first. A version is cut as a release
(`scripts/release-bundle.sh`, defaulting v0.1); this section is the human-read
"what changed and why" beside it. Each entry cites the field prints that drove
it (see `## Field test log`).

### v0.2 — 2026-08-20 — field-driven refinement

Driven by the first two field prints (print 1 + 2 below) and a Jane/Drik
review pass. Geometry:

- **Loop tab no longer intrudes into the bore or the flip path.** The tab's
  inner disc is now *derived* (`tab_inner_y = bore_r + tab_r + tab_bore_margin`)
  so its bulge sits a fixed 0.2 mm *outside* the bore at every `coin_d` and
  every `loop_hole_d` — the old hardcoded offset put it 0.45 mm inside the
  full-size bore and **0.05 mm from the coupon coin (the coupon fused and
  jammed at 12 o'clock)**. New asserts guard `tab_reach`, and a new swept-flip
  fitcheck proves the coin clears the tab across the whole flip.
- **Axial float halved:** `socket_end_clear` 0.7 → 0.4 (float 1.4 → 0.8 mm —
  print 1 had perceptible end-play). Docs now name the *right* knob:
  along-axis rattle is `socket_end_clear`, across-axis is `pivot_clear`.
- **Hourglass redesigned** so it reads as an hourglass, not a rune: a bolder
  bowtie silhouette (side rails apex-to-apex), one settled sand pile + a
  falling grain, no overlapping voids.
- **"IS THE" raised 2.6 → 3.2 mm** — at 2.6 the stroke was one extrusion wide
  and the closing sealed the S.
- **Loop threads a split ring:** a top-side 45° counterbore thins the hole
  region to `loop_thick = 3 mm` (was the full 6 mm ring height).
- **Moat tightened** `rim_gap` 1.5 → 1.2 and bore inset 0.5 → 0.3 (v0.1 read
  ~2.8 mm apparent moat; the coin now fills its ring). Every guard margin held.
- **Randomness is the feature:** the coin has no detent, so the face at
  retrieval is whatever the last jostle left — "the coin picks your reminder."
  Documented deliberately so a future round doesn't "fix" it.
- README gains the print-settings the field asked for (plate, seam, ironing,
  layer-height quantization) and a **two-color-swap recipe** — the engraving is
  exactly 3 × 0.2 layers, so a filament swap at z=0.6 and z=4.4 gives both
  faces contrasting text on any single-extruder printer.

### v0.1 — 2026-08-18 — first shipped version

Two-sided coin + print-in-place flipper. The pivot recipe (teardrop socket +
45° diamond axle + `pivot_clear = 0.35`), coin-flip text alignment, glyph
morphological closing, sub-45° chamfers, reed-skip axle-root protection.
Field-validated: print 1 freed on the first flip.

## Field test log

_Real prints of this design, newest at the bottom. See templates/FIELD-TEST.md
and docs/print-feedback.md for the convention._

### 2026-08-19 — Prusa-style textured PEI (orange PLA)
- **Printed from:** v0.1 (flipper, as shipped)
- **Part(s):** flipper (MEMENTO face on the bed, COMPARISON face up)
- **Slicer settings:** 0.2 mm layer · 0.4 mm nozzle · PLA · textured PEI plate
- **Result:** **pivot freed on the first firm flip** — both diamond axle stubs
  intact, coin rotates freely, photographed at multiple angles. COMPARISON arc
  text crisp; "IS THE" (2.6 mm) marginal; some fuzz/scarring around OF JOY.
  MEMENTO bed face legible but soft on the textured sheet; the hourglass read
  as a bordered rune. Perceptible **axial play** along the pivot. Moat looked
  wide; a divot/seam scar sat at the loop junction.
- **Measured deviations:** `pivot_clear = 0.35` → free (no change); axial
  float ~1.4 mm (perceptible); "IS THE" and the hourglass below legibility.
- **Carry forward:** `pivot_clear = 0.35` confirmed for textured-PEI PLA — no
  `printer.conf` change. All other items drove v0.2 (see Changelog).

### 2026-08-19 — smooth plate, multi-color (translucent + cream PLA)
- **Printed from:** v0.1 (flipper) — captured mid-print, top-down
- **Part(s):** flipper, two-color experiment
- **Slicer settings:** 0.2 mm layer · 0.4 mm nozzle · PLA · smooth plate · purge tower
- **Result:** mid-print top-down view — the bed-face (MEMENTO) engraving reads
  crisp and **high-contrast** at layer ~3 (plate showing through the voids),
  confirming the finished textured-plate softness is a *plate/finish* issue,
  not geometry. The top-down mid-print looks mirrored because face B is built
  to read upright *from below* — expected, not a slicer mirror (the model's
  180° flip is a rigid rotation, det = +1, and cannot mirror).
- **Measured deviations:** none (cosmetic experiment).
- **Carry forward:** motivates the v0.2 two-color-swap recipe (both faces get
  contrasting text with two filament changes, no geometry change).
