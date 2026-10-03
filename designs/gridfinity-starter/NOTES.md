# gridfinity-starter — NOTES

## Goal

A first-party Gridfinity starter set (issue #733): one screw-down baseplate
(3×3 default) plus the open bins that drop into it — 1×1×3U, 2×1×3U and a
1×1×1U low tray. The product is **interoperability**: every bin printed from
this design must drop into any community Gridfinity baseplate, and every
community bin must drop into this baseplate. Wrong-by-0.5 mm breaks that, so
the spec numbers below were pinned before any modeling.

## Spec numbers (pinned before modeling — every value sourced)

Gridfinity's own spec page (gridfinity.xyz/specification) is work-in-progress
prose with no dimensioned values. The reproducible number source is the
MIT-licensed reference implementation **kennetek/gridfinity-rebuilt-openscad**
(`main`, read 2026-09-29 via the GitHub API) — read as *numbers only, no code
copied*, per the license boundary (issue #160; the active alternatives,
e.g. ostat/gridfinity_extended_openscad, are GPL-3 and stay out — see
`docs/oss-libraries-research.md`).

| Quantity | Value | Source file |
|---|---|---|
| Grid pitch | 42 × 42 mm | `src/core/standard.scad` `GRID_DIMENSIONS_MM` |
| Bin top per cell | 41.5 × 41.5 (= 42 − 0.5 gap/unit side) | `BASE_TOP_DIMENSIONS`, `BASE_GAP_MM` |
| Bin top corner radius | 3.75 | `BASE_TOP_RADIUS = 7.5/2` |
| Multi-cell bin footprint | n×42 − 0.5 (gap at perimeter only) | `src/core/base.scad` `grid_size_mm` |
| Boss profile | 0.8 out / 1.8 up / 2.15 out (45°/vert/45°), height 4.75 | `BASE_PROFILE` |
| Boss bottom | 35.6 × 35.6, corner r 0.8 | derived: top − 2×2.95; r 3.75−2.95 |
| Base block height (1U) | 7 (= 4.75 profile + 2.25 bridge) | `BASE_HEIGHT`; `docs/bins.md`: "gridz is the height in # of 7mm increments (Zack)" |
| Bin wall (community default) | 0.95 (`d_wall`) — this design uses 1.2, see decisions | `standard.scad` |
| Plate socket profile | 0.7 / 1.8 / 2.15, height 4.65 = bin boss − 0.1 per step | `src/core/gridfinity-baseplate.scad` `_BASEPLATE_PROFILE` |
| Socket clearances | wall +0.25/side, floor edge +0.35/side | derived from both profiles (verified: 36.3/37.2/37.7/42.0 vs 35.6/37.2/41.5) |
| Plate socket depth | 5 (4.65 + 0.35 seating clearance) | `BASEPLATE_HEIGHT` |
| Plate outer corner radius | 4 | `BASEPLATE_OUTER_DIAMETER = 8` |
| Stacking lip line | 0.7 out / 1.8 up / 1.9 out → 2.6 deep × 4.4 tall | `STACKING_LIP_LINE`, `STACKING_LIP_SIZE` |
| Lip tip fillet | r 0.6 (approximated here by a chamfer — non-contacting edge, 0.35 clearance to the next bin's boss) | `STACKING_LIP_FILLET_RADIUS` |
| Lip support | 1.2 vertical + 45° under the inward overhang | `STACKING_LIP_SUPPORT_HEIGHT` |

**Out of scope (per the brief):** magnet pockets, weighted/skeletonized
baseplate styles, baseplate interconnect — follow-up work, not parameters
here.

## Given / assumed measurements

Given (brief, sourced to the spec above): pitch 42; clearance +0.5 per unit
side; 3×3 default plate; bins 1×1×3U, 2×1×3U, 1×1 low tray; print
orientations baseplate grid-down / bins opening-down; style
workshop-utility.

Assumed (brief, stated defaults):

- **4× M4 socket-head corner mounts** in the plate margin (brief's
  assumption, repo fastener vocabulary via `screw_hole("M4")`). The
  workshop-utility style pack's `style_hole_d = 3.4` describes an **M3**
  vocabulary — the brief's M4 wins (it is the frozen contract); recorded as
  a style exception here per CLAUDE.md. The plate corner radius *is* taken
  from the style (`style_corner_r = 4`), which coincidentally equals the
  spec's plate corner diameter 8/2.
- **Margin 14 mm** around the grid (brief: "~126×126 + margins, parameter")
  so the M4 counterbores (⌀7.5 head) keep ≥ 2.75 mm rim to the plate edge
  and ≥ 3.25 mm web to the first socket.
- **Plate floor 2.0 mm** under the sockets (solid, carries nothing critical
  — bins seat on the socket floor).
- **Bin wall 1.2 mm** (repo FDM floor) instead of the community 0.95 —
  every mating surface is outside the wall, so this only shrinks the
  interior. This is also a style/printability call, not a spec one.

## Key decisions

- **Clean-room first-party implementation.** All geometry built from the
  spec constants above with plain OpenSCAD (`hull` lofts of rounded
  squares); no Gridfinity library included, MIT reference used for numbers
  only. Keeps the design out of GPL entirely (`docs/licensing.md`).
- **Boss/socket construction:** stacked hulls between rounded squares whose
  corner radii are concentric (`r = top_r − inset`). At every height the
  loft's corner radius equals its inset, which reproduces the reference's
  `sweep_rounded` conical corners exactly and makes the mating clearances
  (0.25/0.35 per side) fall out of the two profiles rather than being
  hand-tuned.
- **Seating model (verified, not assumed):** a bin seats with its boss
  *bottom face* on the socket floor (36.3 opening vs 35.6 boss → 0.35/side);
  the bridge underside never contacts the socket (0.25/side at the lip
  band). Stacked bins seat boss-bottom on the lip's V floor the same way.
- **Lip top:** the spec's knife edge at inset 0 is capped at a 0.3 mm flat
  rim (cut ends at foot − 0.6) for printability; envelope deviation 0.3 mm,
  inside the 0.5 cell gap, stacking unaffected (the next boss never reaches
  inset < 2.15).
- **Label plate:** the front lip slope is locally capped by a flat plate at
  dy 3.2 spanning inset 0…1.3. Chosen so the stacking envelope is untouched
  (a stacked bin's boss needs inset ≥ 1.55 at that height — 0.25 clearance);
  outward-protruding tabs and deeper shelves both collide with neighbours /
  stacking. Text (if any) is raised 0.31 mm on the plate's outer face and
  stays within the 0.5 cell gap (0.19 to spare).
- **1U tray recess:** 36.3 opening drafted ~11° down to a 1.2 floor, so the
  thin lower walls of a straight recess (0.45 mm at the boss waist) become
  ≥ 1.58 mm measured. Prints support-free; the lip's support chamfer forms
  the recess mouth. **The recess is a cutter, differenced from the base
  block in `gf_bin`** — see the defect note in the iteration-5 gate
  evidence for why that sentence is load-bearing.
- **Bin solids are single sweeps** (`gf_sweep`, PR #738 CI fix). The
  render gate runs OpenSCAD nightly with `--backend=manifold`, and there
  every bin part failed printcheck at 51/100: edges shared by more than
  two triangles plus 48–80 zero-area triangles. The cause was solids that
  only *touched* face-to-face: the wall stacked on the bridge at z = 7, and
  the lip cutters meeting on zero-volume waists (support chamfer on the V
  chamfer at the ridge, V band on the top slope at 2.5). CGAL unions those
  cleanly. Manifold does not. Every rounded-rectangle surface here shares
  one corner centre (r = gf_top_r − inset), so each profile is now one
  closed polyhedron lofted through `[inset, z]` rings. That covers the
  boss's three stages, the body (bridge + wall + lip outer face) and the
  cavity (wall interior or the tray's drafted recess, support chamfer and
  lip V). The bin is bosses ∪ body − cavity, and each boss runs 0.1 mm into
  the body with bit-identical outer rings. Reproduced and verified offline
  by re-evaluating the exported CSG tree with manifold3d booleans. The old
  geometry reproduced CI exactly: tray 51/100, 80 zero-area. The new
  geometry is watertight with no degenerate faces on all four bins and the
  coupon. The mesh moves by under 3 mm³ (sub-0.01 mm plate-step drift).
- **Parts are exported print-oriented** (bins opening-down, plate
  grid-down, per the brief) — the STL is what CI slices.
- **`ci.plate`** ships the four production parts as one multi-object 3MF
  (the multi-part-fuse lesson: an assembled STL prints as one welded lump).
  The assembled render stays a preview only. The gated `bin-2x1-div`
  variant is deliberately **not** a plate part: it is the proof of the
  divider option, not a starter part.
- **Optional dividers** (`dividers_x` / `dividers_y`, default 0 = open):
  wall-thick (1.2) slabs evenly spaced across the bin interior, floor to
  bin top (flush with the wall tops). Even spacing puts the first divider
  of a multi-cell bin exactly on the cell boundary — pitch-aligned with
  community bins; higher counts subdivide cells (asserts refuse a
  fractional or negative count, and any compartment under 8 mm *clear* —
  the span minus the dividers' own thickness, not the centre spacing). Interior = inside the side walls for bins, the
  recess **mouth** (36.3) for the 1U tray, whose drafted walls a
  wall-based span would poke through. Divider ends and floor are buried
  0.3/0.4 mm into the neighbouring solid — a slab that merely *touches*
  face-to-face unions along coplanar faces and exports zero-area triangles
  (8 of them, caught by printcheck in iteration 4). The loops are guarded
  because `[1:0]` is a *descending* range in OpenSCAD 2021.01 (iterates
  1, 0 — the confusion its deprecation warning names), not an empty one:
  the ungated loop silently added two stray slabs against the Y walls.
- **Baseplate drawn at 4× style_fn** (`$fn = 4 * style_fn` at the top of
  `gf_plate`, so slab + mounts + sockets all draw at fn 256). Adjacent
  socket mouths (42.0 at 42 pitch) leave zero web, the neighbouring cutters
  touch along a line, and CGAL's boolean emits coarse 45° crease strips
  between the funnels. At the style's own fn 64 — and still at 128 on a 3×3
  — those strips out-share the drawn arcs and stylelift's curve-smoothness
  reads the plate's dominant band as fn 8, below the style's floor of 44.
  Measured matrix (dominant implied_fn by grid × $fn): 1×1 tracks $fn
  exactly (64.0 / 127.8 / 256.2), so the drawn arcs were never the problem;
  3×3 reads 8 at both 64 and 128 and only passes at 256 (256.2), where the
  *whole part* is fine enough for the arcs to dominate. Hence the bump sits
  in `gf_plate`, not `gf_socket` — a socket-local bump leaves the slab and
  mounts coarse (both earlier attempts failed exactly that way). Sampling
  only: every dimension is unchanged, proven by identical printcheck scores
  across the change (92/84/84/76/92) and re-measured G4 numbers on the new
  exports. Cost: baseplate CGAL render ~54 s (from ~20 s) — acceptable for
  a gated part.

## Print settings

- **Material:** PLA or PETG
- **Layer height:** 0.2 mm (all spec heights are 0.1 multiples)
- **Infill:** 15 % grid — walls and floors carry the structure
- **Supports:** none — every taper is the spec's own 45°; the flat socket
  ceilings (plate, grid-down) and bin floors (opening-down) are ~36 mm
  bridges, sliced clean on stock bridging in the gate's test-slice
- **Orientation:** as exported (bins opening-down, plate grid-down) — do not
  reorient
- **Brim:** recommended on the bins — the stacking lip ends in the spec's
  0.3 mm flat rim, a knife-edge first layer (48 mm² bed contact on bin-1x1
  per printcheck). The plate's margin frame is a wide, stable contact ring.

## Gate evidence (iteration 1, 2026-09-29)

`gate.sh --slice gridfinity-starter` exit 0 on the first iteration. All five
renders CGAL-simple and watertight; plate 3MF built as 4 separate objects.

| Part | Score | Printcheck warnings (all WARN tier, no criticals) |
|---|---|---|
| baseplate | 92/100 | 23% of surface flagged support-needed — the grid-down socket ceilings (13 061 mm² of flat 36.3 mm bridges) |
| bin-1x1 | 84/100 | 15% support-flagged (1 523 mm² = the bin-floor bridge, 36.3 × 41.5); 48 mm² bed contact (lip rim) |
| bin-2x1 | 84/100 | 18% (3 165 mm² = same floor bridge, 2 cells); 73 mm² bed contact |
| tray-1x1 | 76/100 | 25% (1 318 mm² — **misattributed at the time**: this was the lip under-rim chamfer ceiling; the tray of iterations 1–2 shipped with a *solid* top because the recess cutter was never differenced — see iteration 5); 0.00 mm thin-wall sample = the lip knife edge (spec geometry); 48 mm² bed contact |
| coupon | 92/100 | 19%; 2 bodies (socket coupon + tray coupon, intentional) |

**How the support warnings were adjudicated:** printcheck's heuristic wants
every wide flat bridge supported and its auto-oracle suggests flipping the
plate (0 mm² unsupported socket-up). The brief explicitly mandates grid-down
("Baseplate prints grid-down flat; bins print opening-down … label tab at the
bed"), and PrusaSlicer's test-slice produced a valid no-support toolpath for
every part — so the orientation stands per the contract and the bridge claim
is documented honestly above instead. The M4 counterbores opening at the bed
face in grid-down is also why that face carries them.

## Gate evidence (iteration 2, 2026-09-29 — shipped geometry)

Re-ran the full gate after the tessellation change above (the only `.scad`
change between iterations). `gate.sh --slice` exit 0; all five parts score
**identically** to iteration 1 — baseplate 92, bin-1x1 84, bin-2x1 84,
tray-1x1 76, coupon 92 — which is the independent proof the change moved
sampling, not dimensions. Bboxes re-confirmed off the exports: plate
154.0 × 154.0 × 7.0, bin-1x1 41.5 × 41.5 × 25.4, bin-2x1 83.5 × 41.5 × 25.4,
tray 41.5 × 41.5 × 11.4; 3MF 4 objects; gate wall time 106 s.

`style-check.sh gridfinity-starter` now **passes**: baseplate
curve-smoothness 256.2 ≥ 44, corner-radius 4.00 (was 3.16), soft-edges ok;
remaining warnings are the two documented advisories (soft-family share on a
big plate; M4 mounts overriding the style's M3 hole vocabulary per the
brief). Bins/tray: IN STYLE (tray with the same soft-family advisory).

G4 dimensions re-measured on the new exports (scanline sections of the
rendered STLs): pitch voids −42.000 / 0.000 / +42.000; socket slope 40.700
at z = 1.0; bin boss lower-chamfer width 35.700 at 0.05 up the 45° (35.6 +
2×0.05); bin lip outer 41.50; M4 counterbore ⌀7.500 and through-exit
⌀4.500 exact (chord
math on offset scanlines — a line through the exact centre drops
tangential edges).

## Gate evidence (iteration 5, 2026-09-29 — shipped geometry)

Iterations 3–5 came out of the pre-ship brief audit (§6 Pass B), which
caught two things every gate was blind to:

1. **The tray shipped as a solid cap.** `gf_tray_recess()` was *called
   additively* in `gf_bin` — the "cutter" buried inside the base block and
   changed nothing. A solid cap is watertight, sliceable and scores 76/100,
   so no gate complained; the audit found it by reading `gf_bin` and
   proving it on the mesh (design z=5.0 section solid at 41.5, z=3.0 solid
   at 38.0 = the boss chamfer exactly). Fix: `difference()` in the 1U
   branch. Measured on the gated STL: mouth void 36.284 (36.3 − rim),
   draft mid 34.715 (computed exact), floor void 34.040, remaining walls
   1.58–3.0 (2.995 at design z=5). The printcheck support-flag for the
   tray moved 1318 → 1156 mm² ≈ the recess floor (34.04² = 1158 mm²) — the
   genuine cavity-floor bridge, same class as the bins' floor bridges —
   confirming the earlier 1318 attribution (lip under-rim chamfer) wrong.
2. **The contract's "optional dividers" were never implemented.** Added
   `dividers_x`/`dividers_y` + `gf_dividers()` (semantics above), with a
   gated proof variant `bin-2x1-div` in `ci.parts`.

`gate.sh --slice` exit 0; all renders CGAL-simple, no deprecation
warnings, no degenerate faces; plate 3MF still 4 objects (the div variant
is not a plate part); gate wall time 109 s.

| Part | Score | Notes |
|---|---|---|
| baseplate | 92/100 | unchanged (23% support-flag = socket ceilings, adjudicated below) |
| bin-1x1 | 84/100 | unchanged |
| bin-2x1 | 84/100 | unchanged |
| bin-2x1-div | 84/100 | new: divider 1.200 thick on the cell boundary, compartments 39.950; no degenerate faces after burial |
| tray-1x1 | 76/100 | recess now real: cavity 36.284 → 34.040 drafted, walls ≥ 1.58; 1156 mm² floor bridge |
| coupon | 92/100 | 2 bodies intentional; tray half carries the real recess |

`style-check.sh` exit 0 on the same STLs: baseplate IN STYLE (2 advisories
— soft-family share, M4-vs-M3 hole vocabulary), bin-1x1 / bin-2x1 IN STYLE
clean, bin-2x1-div and tray IN STYLE (1 advisory each — the grammar-rounded
share, which falls as a part grows at fixed radius). A top-down projection
of the gated STLs was also checked by connected-components: exactly one
centred dark region (tray cavity) and exactly two equal compartments
(div bin) — the deterministic stand-in for a visual pass.

## Print this first

`gridfinity-starter-coupon.scad` — one plate socket + one 1×1×1U tray at
the production `fit = 0.1`, both on one bed. Print it before any full part:

1. The tray must drop into the socket and sit flat with a faint click, no
   rock.
2. Too tight / melted ridges → raise `fit` by 0.02–0.05 and re-print the
   coupon.
3. Sloppy / rattly → lower `fit` the same step. Do not go below 0.05: the
   community clearance is what makes *other* bins fit this plate.

Tuning `fit` only affects the socket (plate side). The bin boss is spec
geometry and never moves — a bin that fits community plates is guaranteed by
construction.

## Field test log
