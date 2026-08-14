// support-free-bracket — a wall bracket authored in its optimal print
// orientation so it needs zero support material. Reference design for
// docs/advanced-techniques.md Domain 2 (designing around supports) and the
// cross-cutting move CC1 (orientation is the master variable).
//
// The whole part is a demonstration of "reshape geometry so the process
// stops mattering":
//   - vertical mounting holes through the back plate  → support-free because
//     they run along the build axis (Z);
//   - the horizontal dowel/rod bore                    → a TEARDROP, so its
//     roof self-supports where a plain round bore would droop;
//   - the arm-to-plate junction                       → a 45-degree GUSSET
//     chamfer, never a bottom fillet (a bottom fillet starts horizontal and
//     curls into an overhang).
//
// Print orientation = as authored: back plate flat on the bed (z = 0), the arm
// standing up in +Z. In USE you rotate it 90 deg so the back plate is against
// the wall and the dowel bore is horizontal. All dimensions in millimeters.

use <printability.scad>

/* [Back plate] */
// Plate width, X (mm)
plate_w = 46;
// Plate depth up the wall, Y (mm)
plate_d = 40;
// Plate thickness, Z / build direction (mm)
plate_t = 5;
// Mounting-screw size
screw = "M4"; // [M3, M4, M5]
// Screw hole inset from the plate edges (mm)
screw_inset = 9;

/* [Arm] */
// Arm (post) thickness, Y (mm) — must exceed bore_d so the horizontal bore
// keeps a real wall on each side (keep arm_t >= bore_d + 2*1.2)
arm_t = 16;
// Arm height above the plate, Z (mm)
arm_h = 34;
// How far the arm's foot chamfer runs out onto the plate (mm) — the 45-deg
// gusset that replaces a bottom fillet at the arm/plate junction
gusset = 10;
// Dowel/rod bore diameter (mm) — teardrop, so it prints roofless
bore_d = 10;

/* [Fit & print] */
// 45-deg chamfer on bed-contact edges (mm)
bottom_chamfer = 0.8;
// Corner rounding radius on the plate (mm)
plate_r = 4;

/* [Quality] */
// Iterating: 48. Production: 96+.
$fn = 64;

// ---- derived -----------------------------------------------------------
arm_y0 = plate_d - arm_t - gusset;   // arm foot sits toward the wall edge
// bore centre: high enough to hang a rod, low enough that the teardrop apex
// (~bore_d above centre) keeps a solid cap of blade above it — no severing.
bore_z = plate_t + arm_h * 0.52;

module back_plate() {
    difference() {
        rounded_box([plate_w, plate_d, plate_t], r = plate_r,
                    bottom_chamfer = bottom_chamfer);
        // Two countersunk mounting holes, axis +Z (support-free): the
        // countersink cone opens upward and self-supports.
        for (x = [screw_inset, plate_w - screw_inset])
            translate([x, plate_d - screw_inset, 0])
                screw_hole(size = screw, l = plate_t, head = "countersunk");
    }
}

// The arm: a vertical blade with a 45-degree gusset foot (self-supporting),
// carrying a teardrop dowel bore near the top.
module arm() {
    x0 = (plate_w - arm_t) / 2;   // not used for width; arm spans plate_w-inset
    arm_w = plate_w - 2 * plate_r; // blade width in X
    difference() {
        union() {
            // upright blade
            translate([(plate_w - arm_w)/2, arm_y0, plate_t - 0.01])
                cube([arm_w, arm_t, arm_h + 0.01]);
            // 45-degree gusset running from the blade front face out onto the
            // plate — a chamfer, so its sloped face self-supports
            translate([(plate_w - arm_w)/2, arm_y0, plate_t - 0.01])
                rotate([0, 0, 0])
                gusset_wedge(arm_w, gusset, gusset);
        }
        // horizontal dowel bore, axis along X, teardrop point +Z
        translate([plate_w/2, arm_y0 + arm_t/2, bore_z])
            rotate([0, 0, 90])
                teardrop_hole(d = bore_d, l = arm_w + 2);
    }
}

// A right-triangle wedge in the YZ plane, extruded along X — the gusset.
// Grows from the blade front face (y local 0) out by `run` in +... actually -Y
// (toward the plate front) and up by `rise` in Z.
module gusset_wedge(w, run, rise) {
    translate([0, 0, 0])
        rotate([90, 0, 90])
            linear_extrude(w)
                polygon([[0, 0], [-run, 0], [0, rise]]);
}

module main() {
    // A horizontal bore only self-supports as a teardrop if it also fits the
    // wall it passes through — guard the wall the render can't complain about.
    assert(arm_t >= bore_d + 2 * 1.2,
           "arm_t too thin for bore_d — the teardrop would breach the side walls");
    assert(bore_z + bore_d <= plate_t + arm_h - 3,
           "bore sits too high — the teardrop apex would sever the arm cap");
    back_plate();
    arm();
}

main();
