// pip-piano-hinge — a multi-knuckle print-in-place hinge that comes off the
// plate assembled and swinging. Reference design for
// docs/advanced-techniques.md Domain 3 (print-in-place kinematics → hinges) and
// CC4 (grow the bore by a true offset(), not a scaled teardrop).
//
// It is built ON the repo library `lib/print-in-place.scad` — its teardrop
// profile, its clearance derivations, its barrel radius formula — which
// already encodes the one subtlety that makes a print-in-place hinge work: the
// bore must be the pin's own 2D profile grown by `offset(r=clear)`, NOT a
// scaled-up teardrop. Scaling leaves the 45° flank planes coincident with the
// pin's and welds the print (a bug only Manifold export catches); the offset
// restores real clearance on every surface. This design tiles that into a
// real hinge and adds three piano-hinge-specific moves:
//
// THE ROUND PIN (the articulation finding). The library's matching
// `pip_hinge_pin` is a TEARDROP — the right pin when the joint never rotates
// far, but wrong here: a teardrop pin only clears a teardrop bore while the
// two point the same way, because both carry material/air wedges beyond the
// circular zone (the pin's tip reaches 0.8·pin_d at 45°–135°). Fold the leaf
// 90° and the pin's tip is under barrel material — the hinge is a still render
// that cannot fold. A real rotating hinge needs a rotationally symmetric pin
// inside the bore's circular zone, with the teardrop kept where it earns its
// keep: on the BORE, whose roof must bridge supportless. The `fold90`
// fitcheck renders the folded leaf against everything else and must come back
// EMPTY — articulation is measured, not promised by a pose.
//
// XY ≠ Z CLEARANCE (the doc's clearance theory). One tunable radial
// tolerance, `clear_xy` (spread-limited), from which the sag-limited Z gap is
// DERIVED whole-layer: `clear_z = ceil(max(clear_xy, layer_h)/layer_h)·layer_h`.
// The bore is the lib's offset(clear_xy) profile UNIONED with the same offset
// profile shifted ±(clear_z − clear_xy) along the bore's point axis — sides
// stay at the spread-limited clear_xy, the roof AND the pin's under-side gap
// (both horizontal gaps a sagging layer must cross) open to clear_z. Both
// copies are true offsets of the same profile; nothing is scaled (CC4 intact).
//
// TOLERANCE STACKING (the Domain-3 hinge failure). A long run of knuckles
// binds if axial lengths add up wrong. Each knuckle gets its OWN axial
// clearance c_k = axial_gap + (2k+1)·axial_err — the gap between knuckles k
// and k+1 must absorb the worst-case accumulated slot error of a run (see
// NOTES.md for the arithmetic) — plus `leaf_gap` between each leaf's plate
// edge and the other leaf's barrels so a swinging leaf clears the opposing
// knuckles. Leaves interdigitate: even knuckles tie to leaf A, odd to leaf B,
// one free pin through all of them. Prints flat, axis horizontal, teardrop
// roofs up → no supports. All dimensions in millimeters.

use <print-in-place.scad>   // _pip_teardrop2d (the gated teardrop profile, CC4)

/* [Hinge] */
// Overall hinge length along the axis, Y (mm)
hinge_len = 60;
// Number of knuckles (alternating leaf A / leaf B). >= 3 for a real hinge.
knuckles = 5;
// Pin diameter (mm) — round, so it clears the bore at every fold angle
pin_d = 4;
// Knuckle wall around the bore (mm) — pip_hinge guards >= 1.2
knuckle_wall = 2.0;

/* [Leaves] */
// Leaf plate width out from the hinge line, X (mm)
leaf_w = 20;
// Leaf plate thickness, Z (mm)
leaf_t = 4;

/* [Clearances — the print-in-place fits] */
// THE tunable: radial pin clearance in XY (mm), spread-limited (doc: 0.15–0.25;
// pip_hinge's weld floor is 0.25). Tune this on the coupon; clear_z follows.
clear_xy = 0.25;
// Print layer height (mm) — only used to snap the Z clearances to whole layers
layer_h = 0.2;
// Sag-limited Z gap, DERIVED whole-layer from clear_xy (doc's formula). Do not
// hand-edit: ceil(max(0.25, 0.2)/0.2)·0.2 = 0.4 = two whole layers.
clear_z = ceil(max(clear_xy, layer_h) / layer_h) * layer_h;
// Base axial gap between consecutive knuckles (mm): 2× bead-spread (0.10/face,
// doc) + one extrusion width (0.4) — under that a draped bead welds the gap.
axial_gap = 0.6;
// Worst-case axial error of ONE slot (mm) used in the stacking derivation: a
// slot is two end faces whose systematic spread error mostly cancels in the
// length, leaving ~one face's floor error. Sets how fast c_k grows along the
// run; 0 recovers a shared nominal.
axial_err = 0.05;
// Gap between a leaf plate edge and the opposing leaf's barrels (mm)
leaf_gap = 0.4;

/* [Preview only] */
// Fold leaf B up about the pin for the preview pose (deg). PRINT AT 0.
demo_fold = 0; // [0:5:180]

/* [CI fit/fuse checks — not print parameters] */
// "" = the hinge. "fitcheck" = boolean interference between the three
// print-in-place bodies (must render EMPTY — they clear). "fitcheck_neg" =
// the same with an oversized pin (must render NON-EMPTY — proves the check
// can fail). "fold90" = leaf B folded 90° against everything else (must be
// EMPTY — articulation measured, not posed). "fused" = the oversized-pin
// weld for ci.fusecheck's known-fused control. Wired by ci.fitchecks /
// ci.fusecheck.
part = "";

/* [Quality] */
// A captive teardrop bore is $fn-sensitive — keep high.
$fn = 96;

// ---- derived -----------------------------------------------------------
R    = 0.8 * pin_d + clear_xy + knuckle_wall;   // pip_hinge outer radius
slot = hinge_len / knuckles;                    // Y span per knuckle
dz   = clear_z - clear_xy;                      // whole-layer lift at roof+floor
plate_edge = R + leaf_gap;                       // plate stops leaf_gap out

// Per-knuckle axial clearance: the gap following knuckle k (mm). Grows along
// the run because a series accumulates axial error — see NOTES.md.
function c_k(k) = axial_gap + (2*k + 1) * axial_err;
// Boundary values at the run's ends mirror the adjacent gap.
function c_prev(k) = c_k(max(k - 1, 0));
function c_next(k) = c_k(min(k, knuckles - 2));
// Knuckle k's faces on the slot grid, so every realized gap is exactly c_k.
function y_lo(k) = k * slot + c_prev(k) / 2;
function y_hi(k) = (k + 1) * slot - c_next(k) / 2;
function bl_k(k) = y_hi(k) - y_lo(k);
function y_c(k)  = (y_lo(k) + y_hi(k)) / 2;

// Print seating: leaves lie ON the bed (z = 0..leaf_t); barrels sit on top with
// their axis at z = R, so the barrel bottoms rest on the bed too. Nothing floats
// — the leaves' big flat undersides are bed contact, not overhang.
//
// ORIENTATION IS A CLEARANCE DECISION (doc CC1): axis horizontal, roofs up.
// Vertical axis would make every bore a perfect vertical ring (no roof to
// bridge) but stand the leaf plates on edge — unusable bed contact. Horizontal
// costs a sag-limited bore roof, paid for with the teardrop profile + the
// whole-layer clear_z; that trade IS this design's xy≠z split. See NOTES.md.
barrel_z = R;
// web reach INTO the barrel from its outer edge — must stay OUTSIDE the bore
// (bore reaches pin_d/2 + clear_xy from centre) or the web grips the pin and
// LOCKS the hinge. This is the bug the first version had.
web_reach = 2;
// free pin length: hinge_len minus one c_0 of end clearance (half each end)
pin_len = hinge_len - c_k(0);

// One knuckle: barrel + bore, built on the lib's gated teardrop PROFILE
// (_pip_teardrop2d) and its radius formula — but constructed here, not via
// pip_hinge. Historical note: this design surfaced the lib finding that the
// teardrop_hole/pip_hinge rotate sign pointed the teardrop -Z (down) while
// the docs say +Z (measured; NOTES.md D5, issue #407) — FIXED upstream by
// PR #424 (closing #398), which flipped teardrop_hole and pip_hinge's bore
// in lockstep. The in-design construction below already used the correct
// +90 rotation (the point IS the roof) and is unchanged; it stays in-design
// because pip_hinge has no xy≠z whole-layer split or per-knuckle clearance.
// CC4 intact: the bore is the profile grown by a true offset(clear_xy) —
// never scaled — and the ±dz copies open the sag-limited roof AND floor to
// the whole-layer clear_z while the spread-limited sides stay at clear_xy.
module knuckle(k) {
    l = bl_k(k);
    translate([0, y_c(k), barrel_z])
        difference() {
            rotate([-90, 0, 0]) cylinder(r = R, h = l, center = true);
            rotate([90, 0, 0])    // +90: the teardrop point becomes the +Z roof
                linear_extrude(l + 0.02, center = true)
                    union() {
                        offset(r = clear_xy) _pip_teardrop2d(pin_d);
                        translate([0,  dz]) offset(r = clear_xy) _pip_teardrop2d(pin_d);
                        translate([0, -dz]) offset(r = clear_xy) _pip_teardrop2d(pin_d);
                    }
        }
}

// One leaf: a plate on the bed + its knuckles + a side web fusing each knuckle
// to the plate at the barrel's OUTER wall only. `sx` = +1 leaf B (+X), −1 leaf A.
module leaf(sx, parity) {
    px = sx < 0 ? -(plate_edge + leaf_w) : plate_edge;
    translate([px, 0, 0]) cube([leaf_w, hinge_len, leaf_t]);
    for (k = [0 : knuckles - 1])
        if (k % 2 == parity) {
            knuckle(k);
            // side web: plate → barrel outer wall, never into the bore
            wx = sx < 0 ? -(plate_edge) - 0.01 : plate_edge - leaf_gap - web_reach;
            translate([wx, y_lo(k), 0])
                cube([leaf_gap + web_reach + 0.01, bl_k(k), barrel_z]);
        }
}

module leaf_A() { leaf(-1, 0); }
module leaf_B() { leaf(1, 1); }               // unfolded (printed position)
// The free pin: ROUND, so it clears the bore's circular zone at every fold
// angle (see header) — a teardrop pin here would jam against the bore's
// flanks past a few degrees.
module pin_body(d = pin_d) {
    translate([0, hinge_len / 2, barrel_z])
        rotate([-90, 0, 0]) cylinder(d = d, h = pin_len, center = true);
}

// leaf B folded `a` degrees up about the pin axis (the axis runs along Y at
// x = 0, z = barrel_z). Negative demo_fold would fold DOWN through the bed.
module leaf_B_folded(a) {
    translate([0, 0, barrel_z]) rotate([0, -a, 0]) translate([0, 0, -barrel_z])
        leaf(1, 1);
}

module main() {
    assert(knuckles >= 3, "a piano hinge needs >= 3 knuckles");
    assert(clear_xy >= 0.25,
           "clear_xy under 0.25 mm welds at typical layer heights (pip_hinge's floor)");
    assert(clear_z >= clear_xy, "clear_z must not undercut clear_xy");
    assert(abs(clear_z / layer_h - round(clear_z / layer_h)) < 1e-9,
           "clear_z must land on whole layers — derive it, don't hand-edit it");
    assert(leaf_gap >= 0.3, "leaf_gap too small — a swinging leaf would rub the opposing barrels");
    assert(c_k(0) >= 0.4,
           "axial clearance under one extrusion width — adjacent knuckles weld");
    assert(axial_err >= 0, "axial_err is a worst-case magnitude — it cannot be negative");
    assert(web_reach < R - (pin_d/2 + clear_xy),
           "web reaches into the bore — it would grip the pin and lock the hinge");

    if (part == "fitcheck") {
        // every pairwise overlap of the three bodies must be empty — if the pin
        // is gripped (the locked-hinge bug) or a leaf rubs the other, facets appear
        intersection() { pin_body(); leaf_A(); }
        intersection() { pin_body(); leaf_B(); }
        intersection() { leaf_A(); leaf_B(); }
    } else if (part == "fitcheck_neg") {
        // oversized pin MUST overlap the bores — proves the check can fail
        intersection() { pin_body(pin_d + 2*clear_xy + 1); union() { leaf_A(); leaf_B(); } }
    } else if (part == "fold90") {
        // >= 90° articulation, measured: leaf B folded 90° must clear leaf A
        // AND the pin entirely. This is the check a teardrop pin fails.
        intersection() { leaf_B_folded(90); union() { leaf_A(); pin_body(); } }
    } else if (part == "fused") {
        // ci.fusecheck's known-fused control: the oversized pin welds through
        // every bore, so the whole assembly renders as ONE body
        leaf_A();
        leaf_B();
        pin_body(pin_d + 2*clear_xy + 1);
    } else {
        leaf_A();
        leaf_B_folded(demo_fold);
        pin_body();   // one FREE pin through all knuckles
    }
}

main();
