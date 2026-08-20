// Print this first. One pocket of the production train — the sun, one planet,
// and the ring segment they run in — at full production module, backlash and
// clearances, small enough to print in ~20 min and feel both meshes by hand
// before committing to the full Ø110 print. Nothing copied: the geometry is
// the entry design's own `part="coupon"` wedge (one pocket of the assembly),
// and the overrides below are pure values (OpenSCAD resolves top-level
// variables last-assignment-wins, so they sit after the include).
//
// What to tune here (see NOTES.md "Print this first"):
//   - backlash_gear  — half the mesh backlash. Fused/stiff mesh → +0.025;
//                      sloppy/rattling → −0.025.
//   - pin_diam_clear — planet bore ↔ carrier pin. Seized planet → +0.1;
//                      wobbly planet → −0.1.
include <pip-planetary.scad>

// one planet: enough to feel the sun mesh and the ring mesh at once
N_planets = 1;

// render one pocket of the train as a wedge
part = "coupon";
coupon_wedge_deg = 100;
