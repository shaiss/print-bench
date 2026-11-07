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
| Horizontal rib `cell_horiz` | 10 mm | **assumed (session)** — equal-edge at 30° pinches the neck to 0; 10 mm keeps neck ≈ 2 mm open at the 30° default. The neck guard (not the 45° printability max) caps θ near ~33° at these defaults — raise `cell_horiz` to push the neck cap toward 45°. |
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
  a second print. No brick shift on that column so it fits `contrast_w`; it
  stacks at full `pitch_y` (shared horizontal ribs). Look-side-by-side only —
  the column is framed and is not a pull comparison.
- **No `lib/` harvest in this PR** (brief non-blocking open Q): if the cell
  generator proves out, promoting it to a first-party primitive is the doc's
  own roadmap row and a follow-up issue — not scope here.
- **Yang-style pitches**: `pitch_x = 2·cell_horiz − 2·cell_edge·sin(θ)`,
  `pitch_y = 2·cell_edge·cos(θ)`, θ from vertical. Positive θ indents the
  necks (auxetic); negative θ pushes them out (contrast).
- **Brick rows tessellate at half-height** (2026-11-07 Round 1): auxetic
  voids sit on `pitch_y/2` with a `pitch_x/2` brick shift so neighbouring
  cells share slanted edges and the leftover web is ~`rib_width`. Full-pitch
  brick packing left isolated bowtie holes in a solid plate (Drik block /
  Copilot / coach). Contrast column keeps full-pitch, unshifted.
- **Coupon is free-sided** (2026-11-07 Round 1): grip tabs attach to the
  lattice ±X ends only (with a small bury so the union is manifold); the
  lattice body is shortened in Y so outermost voids punch through top and
  bottom — no solid tab-to-tab rail. Tabs are rounded finger pads with
  shallow scallops; comfort rides the same rework, not a separate redesign.
- **Open framed tile, open coupon lattice**: the tile is a framed window with
  a tessellating rib network inside (frame = look-at demo); the coupon is the
  stretch demo — tabs load cells, not rails.
- **Hard asserts**: `reentrant_angle ∈ (0, 45]`, `rib_width ≥ 0.8`, neck
  width ≥ rib, cell pitch > 2×rib. θ = 0 is refused — it collapses the
  re-entrant indent to a rectangle while the emboss still claims auxetic.
  The 45° cap is the brief's given printability bound; the 0.8 floor is the
  doc's absolute line-width floor (default stays at the repo's 1.2 mm wall
  convention).

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
2. Grip the end tabs and pull gently along the strip axis. The strip should
   get **wider** (auxetic). Look at the tile's left-hand conventional column
   side-by-side for the visual opposite (outward necks) — that column is
   framed and cannot be pulled; it is not a stretch comparison. **B1
   observation:** if the strip does not widen along X, try Y and log which
   axis responded.
3. Log what you felt as a FIELD-TEST entry (`templates/FIELD-TEST.md`) —
   qualitative is enough for v1; a measured ν is backlog.

## Status

**Round 1 lattice rework (2026-11-07).** Tessellating half-height brick rows +
free-sided coupon via `lattice_network_2d` (offset cell-union minus voids —
no rectangular bypass rails); θ>0 guard; honesty fixes for the neck-cap vs
45° printability bound. Local `gate.sh --slice`: tile 92/100 (thin-wall WARN
on emboss text), coupon 100/100; both single-body watertight; readme-gate
ok. Frozen cameras unchanged (added `render` so CGAL depicts the ribs).
`shots.conf` product-hero awaits CI `regen` Cycles (no local `bpy`) —
OpenSCAD iso staged as the README embed meantime, labelled as such.
Design-run from brief #977.
