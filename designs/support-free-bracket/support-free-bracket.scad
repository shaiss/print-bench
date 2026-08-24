// support-free-bracket — a wall shelf bracket authored in its optimal print
// orientation so it needs zero support material. Reference design for
// docs/advanced-techniques.md Domain 2 (designing around supports) and the
// cross-cutting move CC1 (orientation is the master variable).
//
// Every feature that would force supports in a naive orientation is reshaped
// here instead:
//   - the 2 x M5 wall-fastener bores run HORIZONTAL in the print frame →
//     TEARDROPS, so their roofs self-support where round bores would droop;
//   - the cavity under the shelf arm is closed by a diagonal brace whose
//     inner face is a VAULT at `vault_deg` from vertical — never a flat
//     ceiling, which would print as an unsupported bridge roof;
//   - every bed-contact edge carries a 45-degree CHAMFER, never a bottom
//     fillet (a bottom fillet starts horizontal and curls into an overhang).
//
// Print orientation = as authored: the shelf arm lies flat on the bed (z = 0,
// its shelf-bearing face down), the wall plate stands vertically at the back,
// and the vault brace rises between them. In USE the part is flipped 180 deg
// about X: the plate is still vertical against the wall, the arm is now at the
// TOP with the vault brace hanging beneath it, and the shelf board rests on
// the arm's smooth first-layer face. All dimensions in millimeters.

use <printability.scad>

/* [Wall plate] */
// Plate width, across the wall (X) (mm)
plate_w = 80;
// Plate height up the wall in use; on the bed, front-to-back (mm)
plate_h = 50;
// Plate thickness (mm)
plate_t = 6;
// Wall-fastener size (bores are clearance holes)
screw = "M5"; // [M3, M4, M5, M6]
// Fastener bore inset from the plate ends, X (mm)
bore_inset_x = 20;
// Lower bore centre height on the bed (mm)
bore_z_lo = 10;
// Upper bore centre height on the bed (mm)
bore_z_hi = 28;

/* [Shelf arm] */
// Arm depth out from the wall in use; on the bed, length in +Y (mm)
arm_d = 60;
// Arm thickness (mm) — the shelf rests on this print-face-down surface
arm_t = 6;

/* [Vault brace] */
// Vault ceiling angle from vertical (deg) — must stay <= 45 to self-support
vault_deg = 42;
// Height on the bed where the brace springs off the plate (mm)
web_top_z = 44;
// Brace thickness measured down the plate face (mm)
web_band = 8;

/* [Fit & print] */
// 45-degree chamfer on bed-contact edges (mm)
bottom_chamfer = 0.8;
// Vertical-corner rounding, arm (mm)
arm_r = 4;
// Vertical-corner rounding, plate (mm) — keep < plate_t / 2
plate_r = 2;

/* [Quality] */
// Iterating: 48. Production: 96+.
$fn = 64;

// ---- derived -----------------------------------------------------------
arm_y0 = plate_t;                          // arm starts at the plate face
arm_y1 = arm_y0 + arm_d;                   // arm tip on the bed
bore_d = screw_clearance_d(screw);         // 5.5 for M5
// Outer (upper) face of the brace: springs from the plate at web_top_z and
// runs down to the arm surface. Both brace faces sit at vault_deg from
// vertical, so every layer of the vault rests on the one below it.
web_out_foot_y = plate_t + (web_top_z - arm_t) * tan(vault_deg);
// Inner (lower) face — the vault ceiling over the cavity — parallel to it.
web_in_z = web_top_z - web_band;
web_in_foot_y = plate_t + (web_in_z - arm_t) * tan(vault_deg);

module back_plate() {
    // The wall plate, standing on the bed at the back edge.
    rounded_box([plate_w, plate_t, plate_h], r = plate_r,
                bottom_chamfer = bottom_chamfer);
}

module shelf_arm() {
    // The shelf arm, lying flat on the bed: its top-in-use (shelf-bearing)
    // face prints face-down, so the shelf rests on a smooth first-layer face.
    translate([0, arm_y0, 0])
        rounded_box([plate_w, arm_d, arm_t], r = arm_r,
                    bottom_chamfer = bottom_chamfer);
}

// The diagonal brace closing the cavity under the arm. Its inner face is the
// vault: a plane at vault_deg from vertical spanning the bed-facing void,
// where a flat ceiling would print as an unsupported bridge roof.
module vault_brace() {
    rotate([90, 0, 90])   // polygon (Y,Z) profile, extruded along +X
        linear_extrude(plate_w)
            polygon([[plate_t, web_in_z],
                     [plate_t, web_top_z],
                     [web_out_foot_y, arm_t],
                     [web_in_foot_y, arm_t]]);
}

// 2 x M5 wall-fastener bores, axis along Y (horizontal in the print frame):
// teardrop profile with the point UP, so the bore roof self-supports. The
// extra 180-degree flip is load-bearing: teardrop_hole()'s point actually
// faces -Z (its docstring says +Z; measured on the export — see NOTES.md and
// issue #398), so unrotated it cuts a round roof with a downward
// void spike — the exact droop this design exists to avoid. Flipped here, the
// 45-degree hat is the roof.
module fastener_bores() {
    for (p = [[bore_inset_x, bore_z_lo],
              [plate_w - bore_inset_x, bore_z_hi]])
        translate([p[0], plate_t / 2, p[1]])
            rotate([180, 0, 0])
                teardrop_hole(d = bore_d, l = plate_t + 4);
}

module main() {
    // The vault is the design: a ceiling over a bed-facing void must stay
    // <= 45 deg from vertical or it stops self-supporting.
    assert(vault_deg > 0 && vault_deg <= 45,
           "vault_deg must be in (0, 45] — a steeper ceiling needs supports");
    assert(web_out_foot_y <= arm_y1 - 4,
           "vault brace foot runs off the arm");
    assert(bore_z_hi + bore_d * 0.8 <= web_in_z - 2,
           "upper bore teardrop apex would breach the vault springing");
    assert(bore_z_lo - bore_d / 2 >= 3,
           "lower bore too close to the bed");
    assert(bore_inset_x - bore_d / 2 >= 3,
           "bores too close to the plate ends for the screw head");
    assert(arm_t >= 4, "arm thinner than 3 perimeters plus infill");

    difference() {
        union() {
            back_plate();
            shelf_arm();
            vault_brace();
        }
        fastener_bores();
    }
}

main();
