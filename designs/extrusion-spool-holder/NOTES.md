# extrusion-spool-holder — engineering log

## Goal

A filament-spool peg for standard 2020 T-slot extrusion: slide it into a
side slot from an open rail end and it cantilevers a horizontal axle stub
that a 1 kg spool (bore Ø52) drops onto and spins on its own bore — zero
hardware, zero bearings. Brief: issue #669. Style: `workshop-utility`.

## Given / assumed measurements

| Measurement | Value | Status / source |
|---|---|---|
| 2020 slot mouth | 6.0 mm | given — NopSCADlib E2020 (`lib/NopSCADlib/vitamins/extrusions.scad`), via extrusion-shelf-bracket |
| Slot cavity width / depth | 12.0 / 8.0 mm | given — E2020 `cwi` / `sq` |
| Slot lip thickness | 2.0 mm | given — E2020 `t` |
| Lug slide clearance | 0.15 mm/side | given — family coupon-tuned (extrusion-shelf-bracket); tune on the coupon |
| Standoff, rail face → spool | ≥25 mm | given — brief minimum; built 28 |
| Spool bore | Ø52 mm | assumed default (Prusament/Polymaker/eSUN 1 kg); 55 / 30 are `-D` overrides |
| Spool width between flanges | 66 mm | assumed (66–71 range; stub 68 covers it) |
| Spool OD | Ø200 mm | assumed (sets the moment; informational) |
| Bore diametral clearance | 0.6 mm | assumed default; coupon sweep 0.3–0.9 |
| Load | 10 N at ~64 mm | derived — 1 kg spool at its COM |

## Key decisions

1. **Print pose is a quarter turn from use pose.** Bed at the lug heads'
   outboard face (z=0), rail-face plane at z=3.5 = `head_depth`. The
   blade's T-lugs print as flat constant cross-sections (widest layer
   down, heads stack as identical layers); the plate bridges ≤9.15 mm onto
   the blade web (inside FDM bridge norms); the trunk flares ≤37.6° from
   vertical (self-supporting); the stub prints as a vertical hollow tube —
   a round bearing surface with no overhang at all, instead of a Ø51.4
   horizontal cylinder whose top dome can never print support-free. In use
   the stub's layers run perpendicular to its axis, so the cantilever's
   bending tension stays in-plane to the layers (the strong direction).
2. **Through-cut stub bore.** An enclosed 68 mm stub would leave a 41.4 mm
   internal ceiling over the bore — an unprintable sagging bridge. Cutting
   the bore through dropped printcheck's overhang warning 2240→896 mm²
   (what remains is the intentional plate bridges) and bodies 2→1.
3. **Ø58 seat shoulder is the inboard keeper.** Wider than the Ø52 bore,
   so the spool lands on the ring, not the trunk, and cannot walk past it
   (`assert shoulder_d > spool_bore + 0.5`).
4. **Two hammer-head fins on a continuous web** (pitch 24, span 34): the
   tipping couple is reacted as compression at one fin head and hook
   tension at the other, spread over two engagement zones. Lugs enter
   along the slot axis only — install by sliding on from an open rail end,
   never by pressing straight on.
5. **Hollow stub, 5 mm wall** (6 perimeters): a 1 kg spool without a
   150 g peg — the print is 61.6 g, ~4 h.
6. **Fits proven by boolean gates, not eyeballs** (`ci.fitchecks`): the
   lug-in-slot and bore-on-axle intersections must render zero facets, and
   each check carries a deliberately-interfering negative control that
   must render solid — proving the check can fail.

### Load case (1 kg spool) — and an honest margin

Weight 10 N at the spool COM ~64 mm from the rail face → 0.64 N·m tipping
couple; fin reactions ≈ ±18 N (compression at one head, hook tension at
the other). **Vertical-rail honesty:** sliding retention is couple-induced
friction ≈ 11 N against the 10 N weight — marginal by design. Prefer a
horizontal/top rail; if a vertical install creeps down, back the peg with
an M5 T-nut in the same slot just below the plate (no redesign needed).
Sustained clamp stress at the fin heads may also cold-flow and relax the
fit over weeks — that is the standing field-test question.

## Measured mesh (G4 evidence, off `build/extrusion-spool-holder.stl`)

| Brief number | Parameter | Measured on the export |
|---|---|---|
| neck through 6.0 mouth | `lug_neck_w = 5.7` | 5.7 (mouth − 2×0.15) |
| head hooks the lips | `lug_head_w = 10.4` | 10.4 (y ±5.2) |
| engagement depth | `head_depth = 3.5` | 3.5 (plate underside plane) |
| standoff ≥25 | `standoff = 28` | 28.0 (rail plane 3.5 → shoulder 31.5) |
| spool bore Ø52 | `axle_d = 51.4` | Ø51.4 (Ø41.4 through-bore) |
| stub past spool width | `axle_len = 68 ≥ spool_w 66` | 68.0 (z 34.5 → 102.5) |
| keeper shoulder | `shoulder_d = 58` | Ø58 (x −6…52) |
| overall | — | 58 × 58 × 102.5, 1 body, 1356 facets |

## Gate evidence (§4 iterations; telemetry in `build/design-run-telemetry.ndjson`)

- Iter 1 → 2: fitcheck FAILs 6 → 0 (manifest names must equal the literal
  `part == "…"` dispatch branches), overhang warning 2240 → 896 mm²,
  bodies 2 → 1, `gate_status` 1 → 0. Progress every iteration; no thrash;
  2 of the 8-iteration cap.
- `gate.sh --slice` green: peg 92/100 (the 896 mm² warning is the
  intentional plate bridges), coupon 100/100. Test slices: peg 4 h 05 m /
  61.6 g, coupon 2 h 03 m / 25.7 g; both flag tall-part first-layer
  stability → the brim note in Print settings.

## Print settings

- **Orientation:** as rendered — lug heads flat on the bed (the print pose
  above). No supports anywhere, by design.
- **Material:** PLA (stiff, creeps least) or PETG; skip PLA in a warm
  enclosure.
- **Layer height:** 0.2 mm. **Walls:** ≥3 perimeters (the stub's 5 mm wall
  resolves to 6). **Infill:** 15%.
- **Seam:** random or scarf — an aligned seam stacks a ridge up the stub OD,
  which is the bearing surface (the spool ticks once per revolution on it).
- **Brim:** 5–6 mm — the blade strip is a tall slim footprint and the
  test-slice flags first-layer stability without one; cool fully before
  popping it off.

## Print this first (coupon)

`extrusion-spool-holder-coupon.scad` (auto-gated, 100/100, ~2 h / 26 g):

1. Slide the lug strip into your real rail. Drags → `slot_fit_tol` +0.05;
   rocks → −0.05. Steps of 0.05.
2. Drop each embossed ring (0.3 / 0.6 / 0.9) into your real spool bore;
   pick the loosest that doesn't wobble and set `bore_clearance` to it.
3. Print the peg with those two values — nothing else changes.

## Field test log

(none yet — first entries wanted: does the loaded peg hold on a vertical
rail, and does the fin-head clamp relax after a few weeks?)
