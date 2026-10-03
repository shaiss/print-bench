# calibration-cube

## Goal
Simple dimensional-accuracy test print; also serves as the repo's starter
design demonstrating the parameter conventions.

## Key dimensions
- 20 mm cube (parametric via `size`; `part = "cube"`)
- Multi-size strip: 5 / 10 / 20 / 30 mm fixed cubes (`part = "cube5"` …)
- 0.6 mm 45° chamfer on bottom edges
- Top face engraved with the edge length (0.4 mm deep)

## Decisions
- Chamfer via `hull()` of a thin base slab and the upper body — keeps the
  model a single convex solid, no BOSL2 needed.
- Size marker is subtracted 0.4 mm below the top surface so it survives
  slicing at 0.2 mm layers. On cubes under 8 mm the glyph outline is
  grown (`offset(delta=0.40)`) so letter strokes clear the 0.8 mm
  nozzle-safe wall floor; at the default 20 mm the grow is zero and the
  engraved look matches the committed product shots.
- Multi-size strip (charter B1) is four **separate** cubes on one plate,
  not a fused bar: each cube stays an independent dimensional sample, and
  a warp on one cannot pull its neighbours (same air-gap idea as
  `render.sh --sweep`). Deliverable is `ci.plate` →
  `build/calibration-cube-plate.3mf` via `plate.sh`; `part = "sweep"` is
  only a layout preview (STL cannot carry object separation).

## Print orientation
As modeled: flat face down, no supports. Print at 100% infill if using it
to check dimensional accuracy under load.

## Product-shot provenance

The committed `previews/lifestyle-bench-calipers.png` and `lifestyle-turntable.gif`
were generated **blind (text-to-image)**, before the pipeline gained image-to-image
seeding. The `seed=product-hero` field now in `lifestyle.conf` pins the shape to the
real mesh only from the **next re-roll** onward — it does not retroactively describe
the currently committed image.
