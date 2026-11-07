# auxetic-tile — engineering notes

**Metamaterial demonstrator** (docs/metamaterials-4d.md §1). The canonical
re-entrant honeycomb lattice the catalog did not have: a flat-printed tile
that gets *wider* when pulled (ν < 0) because inward-pointing ribs rotate
outward under tension (Lakes, *Science* 235, 1987). Sibling posture to
`spring-rate-ladder` — measurement demonstrator, no style pack, embossed
parameter callout, coupon, no mate.

Brief: issue #977. Every number below traces to that brief unless marked
otherwise.

## Goal

Prove on the reader's own filament that printed PLA lattices do what the
metamaterials literature says: negative Poisson response from **cell
geometry**, not a designed flexure joint. The compliant shelf already has
arches, clips, pivots and sliders; this is the missing cell-geometry
technique the advanced-technique mandate names.

## Given / assumed measurements (from the brief)

| Dimension | Value | Status |
|---|---|---|
| Re-entrant angle (rib from vertical) | default 30°, **max 45°** | **given** — `docs/metamaterials-4d.md` §1 printability note |
| Rib width | 1.2 mm (never below 0.8) | assumed — repo wall convention ≥ 1.2; doc floor is 1 line width |
| Tile footprint | 120 × 70 mm | assumed — one-bed print |
| Rib depth (out-of-plane) | 8 mm | assumed — grip + slender about the in-plane rotation axis |
| Cell edge (slanted rib) | 8 mm | assumed — ~collective behaviour, room for 1.2 mm ribs at 30° |
| Horizontal rib `cell_horiz` | 10 mm | **assumed (session)** — equal-edge at 30° pinches the neck to 0; 10 mm keeps neck ≈ 2 mm open through the 45° cap |
| Mating fit | none | **given** — coupon-based, no `ci.fitchecks` |

All are parametric in `auxetic-tile.scad`.

## Key decisions

- **Emboss wording is qualitative-by-construction** (brief assumption,
  locked in the SHIP-LOCK): the strip states the mechanism (`pull -> wider`,
  `nu < 0 (mech.)`) and the printability bound (`th max 45 deg`), plus the
  live parameter values (`th=…`, `edge … rib …`). It does **not** promise a
  numeric Poisson ratio — `docs/metamaterials-4d.md` §1 warns published ν
  are upper bounds and strain-dependent; FDM fillets push measured ν toward
  −0.4…−0.7. Same discipline as spring-rate-ladder N4: every embossed number
  is `str()`'d from the parameter that builds the mesh, and `echo()`'d for
  the gate log.
- **Conventional contrast strip included** (brief non-blocking open Q,
  locked yes): one column of the same cell with θ negated (outward necks →
  ν > 0) sits in a left-hand pocket so the physics reads on the bed without
  a second print. No brick shift on that column so it fits `contrast_w`.
- **No `lib/` harvest in this PR** (brief non-blocking open Q): if the cell
  generator proves out, promoting it to a first-party primitive is the doc's
  own roadmap row and a follow-up issue — not scope here.
- **Yang-style pitches**: `pitch_x = 2·cell_horiz − 2·cell_edge·sin(θ)`,
  `pitch_y = 2·cell_edge·cos(θ)`, θ from vertical. Positive θ indents the
  necks (auxetic); negative θ pushes them out (contrast).
- **Open pockets, not a solid backplate**: the tile is a framed window with
  ribs welded into the border — a solid plate under the lattice would lock
  the mechanism. Coupon likewise: grip tabs + open lattice window.
- **Hard asserts**: `reentrant_angle ∈ [0, 45]`, `rib_width ≥ 0.8`, neck
  width ≥ 0, cell pitch > rib width. The 45° cap is the brief's given
  printability bound; the 0.8 floor is the doc's absolute line-width floor
  (default stays at the repo's 1.2 mm wall convention).

## Print settings

- **Orientation:** flat on the bed as modelled — every rib is a vertical wall
  (horizontal ribs) or a ≤ 45° in-plane slant (the re-entrant ribs are
  *in-plane*, not Z-cantilevers; the angle bound is about the lattice
  geometry's printability as small per-layer overhangs along the slant).
- **Material:** PLA (the doc's assessment is PLA-specific).
- **Layer height:** 0.2 mm (embossing is exactly two layers).
- **Nozzle:** 0.4 mm.
- **Supports:** none — support-free by the angle bound.
- **Perimeters:** rib_width 1.2 = 3 × 0.4; do not thin the ribs.

## Print this first (the coupon)

1. Print `auxetic-tile-coupon.stl`.
2. Grip the solid end tabs and pull gently along the strip axis. The strip
   should get **wider** (auxetic). Compare by eye with the tile's left-hand
   conventional column, which narrows under the same kind of pull.
3. Log what you felt as a FIELD-TEST entry (`templates/FIELD-TEST.md`) —
   qualitative is enough for v1; a measured ν is backlog.

## Status

**Gate-green locally (2026-11-07).** `gate.sh --slice auxetic-tile` exits 0:
tile 92/100 (WARNING: Thin walls — embossed text strokes, same class as
spring-rate-ladder's plate text), coupon 100/100; both single-body
watertight; embossed-values `echo()` present in the gate log
(`th=30 … edge=8 … rib=1.2 … neck=2 … mechanism: nu<0 … no promised nu`).
Frozen `cameras.conf` previews regenerated and committed; `shots.conf`
product-hero awaits CI `regen` Cycles pass (no local `bpy` — OpenSCAD
iso staged as the README embed so `readme-gate` is green meantime).
Design-run from brief #977.
