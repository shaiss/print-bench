// Print this first. The clip is already coupon-sized (~10x24x15 mm, well
// under an hour), so the coupon is the production part unmodified: snap it
// onto a 3 mm card edge and feel the insertion force before committing to
// anything bigger. Too hard to push -> lower t (or grip_p); cracks at the
// root after a few cycles -> raise t or root_fillet, and read NOTES.md
// "Fatigue" before trusting PLA. The t ladder comes from the sweep:
//   ./scripts/render.sh snap-cantilever-clip --sweep t=0.8:1.6:0.2
//   ./scripts/render.sh snap-cantilever-clip --sweep root_fillet=0.5:1.2:0.1
// (root_fillet must stay >= 0.5*t; the design asserts it.) No overrides sit
// below the include on purpose — the coupon tests true production values.
include <snap-cantilever-clip.scad>
