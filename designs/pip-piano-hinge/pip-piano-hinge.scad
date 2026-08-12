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

/* [CI fit-check — not a print parameter] */
// "" = the hinge. "fitcheck" = the boolean interference between the three
// print-in-place bodies (must render EMPTY — they clear). "fitcheck_neg" = the
// same with an oversized pin (must render NON-EMPTY — proves the check can
// fail). Wired by designs/pip-piano-hinge/ci.fitchecks.
part = "";

/* [Quality] */
// A captive teardrop bore is $fn-sensitive — keep high.
$fn = 96;

// ---- derived -----------------------------------------------------------
R          = 0.8 * pin_d + clear + knuckle_wall;   // pip_hinge outer radius
slot       = hinge_len / knuckles;                 // Y span per knuckle
barrel_len = slot - axial_gap;                     // actual barrel length
plate_edge = R + leaf_gap;                          // plate stops leaf_gap out
function y_c(k) = (k + 0.5) * slot;

// Print seating: leaves lie ON the bed (z = 0..leaf_t); barrels sit on top with
// their axis at z = R, so the barrel bottoms rest on the bed too. Nothing floats
// — the leaves' big flat undersides are bed contact, not overhang.
barrel_z = R;
// web reach INTO the barrel from its outer edge — must stay OUTSIDE the bore
// (bore reaches x ≈ pin_d/2 + clear from centre) or the web grips the pin and
// LOCKS the hinge. This is the bug the first version had.
web_reach = 2;

// One leaf: a plate on the bed + its knuckles + a side web fusing each knuckle
// to the plate at the barrel's OUTER wall only. `sx` = +1 leaf B (+X), −1 leaf A.
module leaf(sx, parity) {
    px = sx < 0 ? -(plate_edge + leaf_w) : plate_edge;
    translate([px, 0, 0]) cube([leaf_w, hinge_len, leaf_t]);
    for (k = [0 : knuckles - 1])
        if (k % 2 == parity) {
            translate([0, y_c(k), barrel_z]) pip_hinge(pin_d, clear, knuckle_wall, barrel_len);
            // side web: plate → barrel outer wall, never into the bore
            wx = sx < 0 ? -(plate_edge) - 0.01 : plate_edge - leaf_gap - web_reach;
            translate([wx, y_c(k) - barrel_len/2, 0])
                cube([leaf_gap + web_reach + 0.01, barrel_len, barrel_z]);
        }
}

module leaf_A() { leaf(-1, 0); }
module leaf_B() { leaf(1, 1); }               // unfolded (printed position)
module pin_body(d = pin_d) {
    translate([0, hinge_len/2, barrel_z]) pip_hinge_pin(d, hinge_len - 0.6);
}

module main() {
    assert(knuckles >= 3, "a piano hinge needs >= 3 knuckles");
    assert(leaf_gap >= 0.3, "leaf_gap too small — a swinging leaf would rub the opposing barrels");
    assert(axial_gap >= 0.4, "axial_gap under one extrusion width — adjacent knuckles weld");
    assert(web_reach < R - (pin_d/2 + clear),
           "web reaches into the bore — it would grip the pin and lock the hinge");

    if (part == "fitcheck") {
        // every pairwise overlap of the three bodies must be empty — if the pin
        // is gripped (the locked-hinge bug) or a leaf rubs the other, facets appear
        intersection() { pin_body(); leaf_A(); }
        intersection() { pin_body(); leaf_B(); }
        intersection() { leaf_A(); leaf_B(); }
    } else if (part == "fitcheck_neg") {
        // oversized pin MUST overlap the bores — proves the check can fail
        intersection() { pin_body(pin_d + 2*clear + 1); union() { leaf_A(); leaf_B(); } }
    } else {
        leaf_A();
        // leaf B folds about the pin (z = R) for the preview only
        translate([0, 0, barrel_z]) rotate([demo_fold, 0, 0]) translate([0, 0, -barrel_z])
            leaf(1, 1);
        pin_body();   // one FREE pin through all knuckles
    }
}

main();
