# calibration-cube

## Goal
Simple dimensional-accuracy test print; also serves as the repo's starter
design demonstrating the parameter conventions.

## Key dimensions
- 20 mm cube (parametric via `size`; `part = "cube"`)
- Multi-size strip: 5 / 10 / 20 / 30 mm fixed cubes (`part = "cube5"` …)
- 0.6 mm 45° chamfer on bottom edges (5 mm cube first-layer patch: 3.8 mm)
- Top face engraved with the edge length (0.4 mm deep); 5 mm top mark is
  a blob, not a readable size label
- Optional X/Y/Z side letters, default off (`face_letters`)

## Decisions
- Chamfer via `hull()` of a thin base slab and the upper body — keeps the
  model a single convex solid, no BOSL2 needed.
- Size marker is subtracted 0.4 mm below the top surface so it survives
  slicing at 0.2 mm layers. Marker stroke-grow ladder: under 8 mm → 0.40
  (the 5 mm "5" becomes a blob — identify `cube5` by plate position, not
  that mark); under 12 mm → 0.25 (the 10 mm cube, so grooves clear a 0.4 mm
  nozzle); else 0, so 20 / 30 match the committed product shots.
- Multi-size strip (charter B1) is four **separate** cubes on one plate,
  not a fused bar: each cube stays an independent dimensional sample, and
  a warp on one cannot pull its neighbours (same air-gap idea as
  `render.sh --sweep`). Deliverable is `ci.plate` →
  `build/calibration-cube-plate.3mf` via `plate.sh` (`cube5`/`cube10`/
  `cube20`/`cube30`); `part = "sweep"` is only a layout preview (STL
  cannot carry object separation). Keep the 4 mm air gap; do not add a
  brim. After the 0.6 mm chamfer the 5 mm cube's first layer is a 3.8 mm
  patch (`size − 2·chamfer`) — that is the sample, not something to pad.
- `size-sweep` studio framing is `20,32,0.60` (was `25,22,0.42`) so the
  5 mm cube occupies more of the frame; the top mark is still a blob.
- Optional X/Y/Z side letters (charter B2, Keel-approved) default **off**
  so the starter print stays a clean dimensional cube. When on, they are
  0.4 mm engraved pockets on the vertical faces (X on +X, Y on +Y, Z on
  −Y for height — the top already carries the size), not raised glyphs,
  so they add no overhang. Faces under 10 mm stay blank. A face-aligned
  slicer seam is a ridge a caliper will catch; park it on a rear corner
  in the slicer — the model does not force a face seam.

## Print orientation
As modeled: flat face down, no supports. Print at 100% infill if using it
to check dimensional accuracy under load.

## Product-shot provenance

The committed `previews/lifestyle-bench-calipers.png` and `lifestyle-turntable.gif`
were generated **blind (text-to-image)**, before the pipeline gained image-to-image
seeding. The `seed=product-hero` field now in `lifestyle.conf` pins the shape to the
real mesh only from the **next re-roll** onward — it does not retroactively describe
the currently committed image.
