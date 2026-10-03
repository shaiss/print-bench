// Exercises every module in stencil-glyphs.scad — check.sh CGAL-renders this
// on every run, so it is the library's geometry regression test (the guards
// have their own negative suite in stencil-glyphs-guards.conf).
//
// THE PROOF THIS RENDER IS: a 2.2 mm plate (the ovodyo shell thickness) with
// all ten digits plus "12", "05", "10", "00" cut THROUGH it at the design's
// glyph height (14 mm) and bridge (1.2). Every counter — the holes in 0, 4,
// 6, 8, 9 — is an island of plate held only by the two bridge tethers, so
// the plate stays ONE body exactly when every tether is real. OpenSCAD's
// render summary reports that as `Volumes: 2` (one solid + the outer void);
// a loose island is an extra volume. Read the line:
//
//   xvfb-run -a openscad -o /tmp/x.stl lib/stencil-glyphs-demo.scad 2>&1 | grep Volumes
//
// check.sh only fails this render on ERROR/WARNING, never on that count, so
// the proof is ALSO enforced automatically, twice, each with a negative
// control (#618 review):
//   * tools/printcheck/tests/test_stencil_demo.py renders this file and
//     asserts fusecheck's body count is 1 — then renders it again with
//     -D 'demo_bridged=false' (the parameter below, which strips the bridge
//     bars from the through-cuts only) and asserts the count is > 1: every
//     counter freed, Volumes: 12. Run by the printcheck unit-tests CI job.
//   * lib/stencil-glyphs-mates.conf (mate-check.sh, inside check.sh on every
//     PR) intersects a probe box with a cut plate exactly where a "0" and an
//     "8" tether must stand, and the same probe against bridged = false must
//     measure nothing — pinning the tether geometry itself.
//
// The raised glyphs on the right half are the POSITIVE use (a linear_extrude
// of the same modules, fused to the plate), plus the ':' glyph, ' ' spacing
// and the unbroken bridged = false variant. They add no volume by
// construction (each overlaps the plate by an epsilon), so the count above
// is the through-cut zone's alone. The two-sided fusecheck (#612 part 2) is
// the gate that carries this proof onto a SLICED part.
//
// Layout: the cut zone's booleans happen in 2D (Clipper, fast) and the
// result is extruded once, so the only 3D boolean CGAL evaluates is the
// final union with the raised zone — keeps the demo well under a minute.
use <stencil-glyphs.scad>

$fn = 48;          // production-quality for 3 mm strokes; the family is $fn-agnostic

plate_t = 2.2;     // the ovodyo shell thickness
gh      = 14;      // the ovodyo glyph height
br      = 1.2;     // the ovodyo bridge
eps     = 0.01;
// The through-cuts' bridge bars. true is the design; false is the NEGATIVE
// CONTROL for the counter-tether proof (every counter becomes a freed island
// and the plate splits into eleven bodies) — test_stencil_demo.py renders
// both. The raised zone's own bridged = false glyph is the positive use and
// is not driven by this.
demo_bridged = true;

// Row layout: cut rows on the left, raised rows on the right.
cut_w    = stencil_text_width("0123456789", gh);      // 113.1 at gh = 14
rows     = 2;
row_p    = gh + 8;                                    // row pitch
plate_x0 = -cut_w / 2 - 6;
plate_w  = cut_w + 12;
plate_h  = rows * row_p + 6;

// The plate with its through-cuts, as one 2D polygon with holes.
module cut_plate_2d() {
    difference() {
        translate([plate_x0, -plate_h / 2]) square([plate_w, plate_h]);
        translate([0,  row_p / 2])
            stencil_text("0123456789", gh, bridge = br, bridged = demo_bridged);
        translate([0, -row_p / 2])
            stencil_text("12 05 10 00", gh, bridge = br, bridged = demo_bridged);
    }
}

// The raised zone: a strip of the same plate carrying positive glyphs.
strip_w = 74; strip_h = 2 * row_p + 6;
strip_x = plate_x0 + plate_w + 8;

module raised_zone() {
    translate([strip_x, -strip_h / 2, 0]) cube([strip_w, strip_h, plate_t]);
    translate([strip_x + strip_w / 2, 0, plate_t - eps]) linear_extrude(1.2 + eps) {
        // the clock's own shape: digits, ':' and the bridged stencil look
        translate([0,  row_p / 2]) stencil_text("12:05", gh, bridge = br);
        // stencil_digit direct, then an unbroken glyph (bridged = false),
        // then a raised bridge_min above the floor and a lighter stroke
        translate([-24, -row_p / 2]) stencil_digit(8, gh, bridge = br);
        translate([-8,  -row_p / 2]) stencil_digit(6, gh, bridged = false);
        translate([ 8,  -row_p / 2]) stencil_digit(4, gh, bridge = 1.4, bridge_min = 1.2);
        translate([24,  -row_p / 2]) stencil_digit(9, gh, stroke = 2.4, bridge = br);
    }
}

union() {
    linear_extrude(plate_t) cut_plate_2d();
    // a bridge of plate between the two zones so the demo is one body
    translate([plate_x0 + plate_w - eps, -6, 0]) cube([8 + 2 * eps, 12, plate_t]);
    raised_zone();
}

// The width function, checked against the layout it sizes: the ten-digit
// row is exactly ten advances plus nine spacings.
assert(abs(cut_w - (10 * stencil_glyph_width("0", gh) + 9 * 0.12 * gh)) < 1e-9,
       "stencil_text_width must equal the sum of advances and spacings");
assert(stencil_text_width("", gh) == 0, "an empty string has zero width");
assert(stencil_glyph_width(":", gh) < stencil_glyph_width("0", gh),
       "the colon is narrower than a digit");

// Every clock value lays out, and the digits are tabular: all sixty minute
// values "00".."59" and the two-digit hours share ONE width, so a changing
// display never shifts. The width function is the layout's own arithmetic
// (stencil_text places glyph i at the same _sg_x it sums), so this pins the
// full value range without cutting sixty more glyphs.
two_w = stencil_text_width("00", gh);
for (m = [0 : 59])
    assert(stencil_text_width(str(m < 10 ? "0" : "", m), gh) == two_w,
           str("minute value ", m, " must lay out at the tabular two-digit width"));
for (hr = [1 : 12])
    assert(stencil_text_width(str(hr), gh) == (hr < 10 ? stencil_glyph_width("0", gh) : two_w),
           str("hour value ", hr, " must lay out at its tabular width"));
