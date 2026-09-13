// spaceframe-demo.scad — exercises every public module/function of
// spaceframe.scad and all three topologies. Not a printable design —
// rendered (full CGAL) by scripts/check.sh, which is the library's
// regression test. The guards are exercised separately by
// lib/spaceframe-guards.conf: a firing assert aborts the render it lives
// in, so the cases that prove the guards REFUSE cannot live here.
// All dimensions in millimeters.

use <spaceframe.scad>

// 16 keeps the demo's CGAL render civil on the stable 2021.01 build CI
// also runs (six frames of ~50 members union slowly there; the nightly
// manifold backend is ~100x faster but check.sh must pass on both). The
// library does not pin quality — see TESSELLATION in its header.
$fn = 16;

L    = 110;  // span (mm)
W    = 40;   // bottom chord separation (mm)
D    = 18;   // midspan outer depth (mm)
BAYS = 5;    // panels
DE   = 3;    // needle-end outer depth (mm)
MULT = 3.5;  // strut section as a multiple of the 0.8 mm floor

// The part variants render smaller: they exist to exercise part = "core" /
// "web", and the full-size chords-vs-web contrast is visible at any span.
L2    = 90; BAYS2 = 4;

// 0. The derivations are functions, so the demo pins their endpoints.
//    These are ARITHMETIC pins on the taper curve, not measurements of the
//    built mesh — the realised envelope is measured on exports (stations
//    along the STL), which only a render outside this file can do.
echo(str("strut_section(", MULT, ") = ", strut_section(MULT),
         " mm (", MULT, " x ", strut_section(1), " mm floor)"));
assert(abs(frame_depth_at(0, L, D, DE) - DE) < 1e-9,
       "frame_depth_at(0) must equal end_depth");
assert(abs(frame_depth_at(L / 2, L, D, DE) - D) < 1e-9,
       "frame_depth_at(midspan) must equal depth");
assert(frame_depth_at(L / 4, L, D, DE) > DE &&
       frame_depth_at(L / 4, L, D, DE) < D,
       "frame_depth_at must taper monotonically between end and midspan");

// 1. Warren: alternating face diagonals, ribs only at the needle ends.
space_frame(L, W, D, BAYS,
            topology = "warren", end_depth = DE, strut_floor_mult = MULT);

// 2. Pratt: a rib at every panel point, face diagonals rising to midspan.
translate([L + 40, 0, 0])
    space_frame(L, W, D, BAYS,
                topology = "pratt", end_depth = DE, strut_floor_mult = MULT);

// 3. Vierendeel with the X at full depth: open panels, hub-and-spoke braces
//    spanning the whole panel height — at x_depth = 1 the spoke attachments
//    are the panel corners themselves.
translate([2 * (L + 40), 0, 0])
    space_frame(L2, W, D, BAYS2,
                topology = "vierendeel", end_depth = DE,
                strut_floor_mult = MULT, x_depth = 1);

// 4. Vierendeel plain: ribs and rungs only — the honest open-panel frame the
//    X exists to stiffen, and the x_depth = 0 default path.
translate([0, W + 40, 0])
    space_frame(L2, W, D, BAYS2,
                topology = "vierendeel", end_depth = DE, strut_floor_mult = MULT);

// 5. The red structural core (part = "core"): the chord network alone — what
//    a two-tone export prints red. Three chord chains; the web is what joins
//    them, so the chains meet the web, not each other.
translate([L + 40, W + 40, 0])
    space_frame(L2, W, D, BAYS2,
                topology = "warren", end_depth = DE,
                strut_floor_mult = MULT, part = "core");

// 6. The web (part = "web"): rungs, ribs and diagonals — everything the core
//    is not. Its members END at the core's node spheres, which is the
//    joint-fusion overlap the volume identity quantifies.
translate([2 * (L + 40), W + 40, 0])
    space_frame(L2, W, D, BAYS2,
                topology = "pratt", end_depth = DE,
                strut_floor_mult = MULT, part = "web");
