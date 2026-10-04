// Calibration cube — starter design demonstrating repo conventions.
// A simple cube with chamfered bottom edges and an engraved size marker,
// useful for checking printer dimensional accuracy.
//
// Parts:
//   cube   — single parametric cube (default; edge length = `size`)
//   cube5 / cube10 / cube20 / cube30 — fixed-size cubes for the multi-size
//            plate deliverable (designs/calibration-cube/ci.plate)
//   sweep  — layout preview of the 5/10/20/30 strip (not a plate part;
//            the printable strip is the multi-object 3MF from plate.sh)
// All dimensions in millimeters.

/* [Part] */
// What to render: the single cube, a fixed plate size, or the strip layout
part = "cube"; // [cube, cube5, cube10, cube20, cube30, sweep]

/* [Size] */
// Edge length of the parametric `cube` part (mm); ignored by fixed-size parts
size = 20;

/* [Printing] */
// 45-degree chamfer on the bottom edges so the first layer releases cleanly (mm, 0 to disable)
bottom_chamfer = 0.6;
// Engrave X / Y / Z on the side faces (off: clean dimensional cube)
face_letters = false;

/* [Sweep] */
// Fixed edge lengths on the multi-size strip (mm); charter backlog B1
sweep_sizes = [5, 10, 20, 30];
// Air gap between cubes on the strip layout / plate (mm) — not fused, so a warp
// on one cube cannot pull its neighbours (same idea as render.sh --sweep).
sweep_gap = 4;

/* [Quality] */
// Iterating: 32. Production: 64+.
$fn = 64;

function sweep_x(i, sizes = sweep_sizes, gap = sweep_gap) =
    i <= 0 ? 0 : sweep_x(i - 1, sizes, gap) + sizes[i - 1] + gap;

// Size-marker glyph. Small cubes' default font strokes leave sub-nozzle
// walls that printcheck rejects; grow the outline just enough to clear the
// 0.8 mm floor. At the starter 20 mm size the grow is 0, so the engraved
// look stays the one the product shots already show. On the 5 mm cube the
// grown glyph is a blob — identify that cube by plate position / `cube5`,
// not by reading the top mark.
function marker_text_size(cube_size) = cube_size * 0.35;
function marker_stroke_grow(cube_size) =
    cube_size < 8 ? 0.40 : 0;

module size_marker(cube_size) {
    ts = marker_text_size(cube_size);
    grow = marker_stroke_grow(cube_size);
    if (grow > 0)
        offset(delta = grow)
            text(str(cube_size), size = ts,
                 halign = "center", valign = "center");
    else
        text(str(cube_size), size = ts,
             halign = "center", valign = "center");
}

// Optional axis labels (charter B2). Engraved 0.4 mm into the vertical
// faces — pockets, not raised letters — so they print supportless with
// the cube flat-face-down. X on +X, Y on +Y, Z on −Y (height; the top
// already carries the size marker). Faces under 10 mm have no room for a
// readable glyph and are left blank.
module axis_letters(cube_size) {
    if (cube_size >= 10) {
        ts = cube_size * 0.32;
        translate([cube_size - 0.4, cube_size / 2, cube_size / 2])
            rotate([90, 0, 90])
                linear_extrude(0.5)
                    text("X", size = ts, halign = "center", valign = "center");
        translate([cube_size / 2, cube_size - 0.4, cube_size / 2])
            rotate([90, 0, 180])
                linear_extrude(0.5)
                    text("Y", size = ts, halign = "center", valign = "center");
        translate([cube_size / 2, 0.4, cube_size / 2])
            rotate([90, 0, 0])
                linear_extrude(0.5)
                    text("Z", size = ts, halign = "center", valign = "center");
    }
}

module calibration_cube(cube_size = size, chamfer = bottom_chamfer,
                        letters = face_letters) {
    assert(cube_size > 0, "cube_size must be positive");
    assert(chamfer >= 0, "bottom_chamfer must be >= 0");
    // N2: when enabled, the release chamfer is at least 0.4 mm.
    assert(chamfer == 0 || chamfer >= 0.4,
           "bottom_chamfer must be 0 or >= 0.4 mm (N2)");
    assert(cube_size > 2 * chamfer,
           "cube_size must leave room for the bottom chamfer on both sides");
    difference() {
        // Cube with chamfered bottom edges
        hull() {
            translate([chamfer, chamfer, 0])
                cube([cube_size - 2 * chamfer, cube_size - 2 * chamfer, 0.01]);
            translate([0, 0, chamfer])
                cube([cube_size, cube_size, cube_size - chamfer]);
        }
        // Engraved size marker on the top face (0.4 mm deep — N3)
        translate([cube_size / 2, cube_size / 2, cube_size - 0.4])
            linear_extrude(0.5)
                size_marker(cube_size);
        if (letters)
            axis_letters(cube_size);
    }
}

// Layout preview of the 5/10/20/30 strip — separate cubes, air-gapped.
// The printable deliverable is the multi-object 3MF from ci.plate / plate.sh,
// not this single STL (STL cannot carry object separation).
module size_sweep(sizes = sweep_sizes, gap = sweep_gap) {
    for (i = [0 : len(sizes) - 1])
        translate([sweep_x(i, sizes, gap), 0, 0])
            calibration_cube(sizes[i]);
}

if (part == "cube") calibration_cube();
else if (part == "cube5") calibration_cube(5);
else if (part == "cube10") calibration_cube(10);
else if (part == "cube20") calibration_cube(20);
else if (part == "cube30") calibration_cube(30);
else if (part == "sweep") size_sweep();
else assert(false, str("calibration-cube: unknown part '", part, "'"));
