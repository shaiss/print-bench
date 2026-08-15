# calibration-cube

## Goal
Simple dimensional-accuracy test print; also serves as the repo's starter
design demonstrating the parameter conventions.

## Key dimensions
- 20 mm cube (parametric via `size`)
- 0.6 mm 45° chamfer on bottom edges
- Top face engraved with the edge length (0.4 mm deep)

## Decisions
- Chamfer via `hull()` of a thin base slab and the upper body — keeps the
  model a single convex solid, no BOSL2 needed.
- Size marker is subtracted 0.4 mm below the top surface so it survives
  slicing at 0.2 mm layers.

## Print orientation
As modeled: flat face down, no supports. Print at 100% infill if using it
to check dimensional accuracy under load.

## Product-shot provenance

The committed `previews/lifestyle-bench-calipers.png` and `lifestyle-turntable.gif`
were generated **blind (text-to-image)**, before the pipeline gained image-to-image
seeding. The `seed=product-hero` field now in `lifestyle.conf` pins the shape to the
real mesh only from the **next re-roll** onward — it does not retroactively describe
the currently committed image.
