// pip-piano-hinge — a multi-knuckle print-in-place hinge that comes off the
// plate assembled and swinging. Reference design for
// docs/advanced-techniques.md Domain 3 (print-in-place kinematics → hinges) and
// CC4 (grow the bore by a true offset(), not a scaled teardrop).
//
// It is built ON the repo library `lib/print-in-place.scad`, whose `pip_hinge`
// already encodes the one subtlety that makes a print-in-place hinge work: the
// teardrop bore is the pin's own 2D profile grown by `offset(r=clear)`, NOT a
// scaled-up teardrop. Scaling leaves the 45° flank planes coincident with the
// pin's and welds the print (a bug only Manifold export catches); the offset
// restores real clearance on every surface. This design's job is to show that
// primitive tiled into a real hinge, and to add the piano-hinge-specific move:
//
// TOLERANCE STACKING (the Domain-3 hinge failure). A long run of knuckles binds
// if their axial lengths add up wrong. Two clearances defeat it, both here:
//   - `axial_gap` between consecutive knuckles (so leaves never rub end-to-end);
//   - `leaf_gap` between each leaf's plate edge and the other leaf's barrels (so
//     a swinging leaf clears the opposing knuckles).
// Leaves interdigitate: even knuckles tie to leaf A, odd to leaf B, one free pin
// through all of them. Prints flat, axis horizontal, teardrop roofs up → no
// supports. All dimensions in millimeters.

use <print-in-place.scad>   // pip_hinge, pip_hinge_pin (offset-teardrop bore)

/* [Hinge] */
// Overall hinge length along the axis, Y (mm)
hinge_len = 60;
// Number of knuckles (alternating leaf A / leaf B). >= 3 for a real hinge.
knuckles = 5;
// Pin diameter (mm)
pin_d = 4;
// Knuckle wall around the bore (mm) — pip_hinge guards >= 1.2
knuckle_wall = 2.0;

/* [Leaves] */
// Leaf plate width out from the hinge line, X (mm)
leaf_w = 20;
// Leaf plate thickness, Z (mm)
leaf_t = 4;

/* [Clearances — the print-in-place fits] */
// Radial pin clearance on every bore surface (mm) — pip_hinge guards >= 0.25
clear = 0.4;
// Axial gap between consecutive knuckles (mm) — beats tolerance stacking
axial_gap = 0.6;
// Gap between a leaf plate edge and the opposing leaf's barrels (mm)
leaf_gap = 0.4;

/* [Preview only] */
// Fold leaf B up about the pin for the preview pose (deg). PRINT AT 0.
demo_fold = 0; // [0:5:170]

/* [Quality] */
// A captive teardrop bore is $fn-sensitive — keep high.
$fn = 96;

// ---- derived -----------------------------------------------------------
R          = 0.8 * pin_d + clear + knuckle_wall;   // pip_hinge outer radius
slot       = hinge_len / knuckles;                 // Y span per knuckle
barrel_len = slot - axial_gap;                     // actual barrel length
plate_edge = R + leaf_gap;                          // plate stops leaf_gap out
function y_c(k) = (k + 0.5) * slot;

// One leaf: a plate on its X side + its knuckles + a web fusing each knuckle to
// the plate. `sx` = +1 for leaf B (plate at +X), -1 for leaf A (plate at -X).
// `parity` selects which knuckle slots this leaf owns.
module leaf(sx, parity) {
    // plate
    if (sx < 0)
        translate([-(plate_edge + leaf_w), 0, -leaf_t/2]) cube([leaf_w, hinge_len, leaf_t]);
    else
        translate([plate_edge, 0, -leaf_t/2]) cube([leaf_w, hinge_len, leaf_t]);
    for (k = [0 : knuckles - 1])
        if (k % 2 == parity) {
            // knuckle barrel (with the offset-teardrop bore)
            translate([0, y_c(k), 0]) pip_hinge(pin_d, clear, knuckle_wall, barrel_len);
            // web fusing plate → barrel, only at this leaf's slots
            if (sx < 0)
                translate([-(plate_edge) - 0.01, y_c(k) - barrel_len/2, -leaf_t/2])
                    cube([plate_edge + 0.11, barrel_len, leaf_t]);
            else
                translate([-0.1, y_c(k) - barrel_len/2, -leaf_t/2])
                    cube([plate_edge + 0.11, barrel_len, leaf_t]);
        }
}

module main() {
    assert(knuckles >= 3, "a piano hinge needs >= 3 knuckles");
    assert(leaf_gap >= 0.3, "leaf_gap too small — a swinging leaf would rub the opposing barrels");
    assert(axial_gap >= 0.4, "axial_gap under one extrusion width — adjacent knuckles weld");

    // leaf A (even knuckles), fixed
    leaf(-1, 0);
    // leaf B (odd knuckles), folds for the preview only
    rotate([demo_fold, 0, 0]) leaf(1, 1);
    // one free pin through all knuckles (teardrop solid, matches the offset bore)
    translate([0, hinge_len/2, 0]) pip_hinge_pin(pin_d, hinge_len - 0.6);
}

main();
