// extrusion-shelf-bracket — a shelf corner bracket that locks into the side
// slot of standard 2020 T-slot aluminum extrusion. Hammer-head lugs on the
// back of the plate slide along the slot, so shelving attaches anywhere
// along a rail with no T-nuts and no frame teardown; the horizontal arm
// carries the shelf board between the gussets and a front stop lip.
//
// Print orientation = use orientation (nothing rotates): the arm is a
// 120 x 40 slab flat on the bed, the back plate and stop lip stand up from
// its ends, two 45-degree gussets brace plate to arm, and the lug fins are
// constant-cross-section extrusions standing against the plate's inner face
// — the hammer heads stack as identical layers, so nothing needs supports
// except the top fin's 3.5 mm head bridge (deliberate, see NOTES.md).
//
// Slot ground truth: NopSCADlib E2020 (lib/NopSCADlib/vitamins/extrusions.scad)
// — mouth 6.0, cavity 12.0 wide / 8.0 deep, lips 2.0. Lugs slide in along
// the slot axis only: install by sliding the bracket on from an open rail
// end (a rack post's top), not by pressing straight on.
//
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.

use <printability.scad>       // repo FDM helpers (OPENSCADPATH="$PWD/lib:$PWD")
include <styles/workshop-utility/style.scad>  // tokens: r=4, chamfer=0.6, fn=64

/* [Extrusion slot] */
// 2020 T-slot mouth width (mm) — the narrow slit on the extrusion face.
// 6.0 is the common European square-slot value; 6.2 variants exist.
slot_mouth = 6.0;
// Undercut cavity width behind the lips (mm) — NopSCADlib E2020 "cwi"
slot_cavity_w = 12.0;
// Cavity depth behind the face (mm) — NopSCADlib E2020 "sq"
slot_depth = 8.0;
// Slot lip thickness (mm) — how deep the overhang runs — E2020 "t"
slot_lip_t = 2.0;

/* [Lug fit] */
// Slide clearance per side in the slot mouth (mm) — the brief's 5.7 neck is
// slot_mouth - 2*0.15. TUNE ON THE COUPON in 0.05 steps.
slot_fit_tol = 0.15;
// How far the head hooks under each lip (mm); head = mouth + 2*hook.
// Real M5 hammer T-nuts for the 6-series hook about 2.2.
lug_hook = 2.2;
// Head thickness under the lip (mm) — the brief's engagement depth
lug_engage = 1.5;
// Fin length along the slot (mm)
lug_len = 10;
// Slide clearance per side of the head inside the cavity (mm)
cavity_tol = 0.3;

/* [Bracket] */
// Overall reach: extrusion face to bracket front edge (mm)
reach = 120;
// Width across the part / along the extrusion face (mm)
bracket_w = 40;
// Back plate height above the arm, vertical (mm)
plate_h = 40;
// Wall thickness: back plate, arm and lip (mm) — 3+ perimeters at 0.4 nozzle
t = 6;
// Shelf board thickness (mm) — sets the stop lip height
shelf_t = 16;

/* [Gussets] */
// 45-degree gusset run from the arm out against the plate (mm)
gusset_run = 18;
// Gusset wall thickness (mm)
gusset_t = 4;

/* [Fit & print] */
// 45-deg chamfer on bed-contact edges (mm) — style_edge_chamfer
bottom_chamfer = 0.6;
// Corner rounding radius (mm) — style_corner_r; clamped to t/2 on 6 mm parts
corner_r = 4;

/* [Quality] */
// Iterating: 48. Production: 96+.
$fn = style_fn;

/* [Hidden] */
part = "bracket"; // [bracket, coupon]

// ---- derived -----------------------------------------------------------
// Neck passes the mouth: brief's 5.7 = 6.0 - 2*0.15.
lug_neck_w = slot_mouth - 2 * slot_fit_tol;
// Head hooks behind the lips: wider than the mouth, free in the cavity.
lug_head_w = slot_mouth + 2 * lug_hook;
// Stop lip rises this far above the arm — engages most of the board edge.
lip_h = min(shelf_t - 4, 10);
// Usable shelf span between the gusset foot and the stop lip.
shelf_span = reach - gusset_run - t;
// Rounding that fits a 6 mm-thick standing part (rounded_box's hull
// overshoots the size when 2*r exceeds the smallest footprint dimension).
r_t = min(corner_r, t / 2);
// Fins: first starts on the bed, second one lug_pitch above it.
lug_z0 = [0, lug_len + 10];
// Fin z extent, centred on the slot line (y = slot_y).
slot_y = bracket_w - 10;

// One hammer-head lug fin against the plate's inner face (x = 0), spanning
// z0..z0+lug_len along the slot axis. Constant cross-section extruded up, so
// every layer is the full T outline: neck through the mouth (buried 1 mm
// into the plate), head hooking behind the lips.
module lug_fin(z0) {
    hx0 = -(slot_lip_t + lug_engage);   // head outboard face (under the lip)
    hx1 = -slot_lip_t;                  // head inboard face (lip inner edge)
    ny1 = 1;                            // neck buried into the plate
    translate([0, 0, z0])
        linear_extrude(lug_len)
            polygon([
                [hx0, slot_y - lug_head_w / 2],
                [hx1, slot_y - lug_head_w / 2],
                [hx1, slot_y - lug_neck_w / 2],
                [ny1, slot_y - lug_neck_w / 2],
                [ny1, slot_y + lug_neck_w / 2],
                [hx1, slot_y + lug_neck_w / 2],
                [hx1, slot_y + lug_head_w / 2],
                [hx0, slot_y + lug_head_w / 2],
            ]);
}

// 45-degree lead-in under an elevated fin's head (the thread_neck move):
// without it the head's first layer cantilevers off the plate face; with it
// the head grows out of the plate at 45 degrees, self-supporting. The ramp
// is widest at the fin's bottom (the full head span) and tapers down to the
// plate face, overlapping 0.5 mm up into the fin so the union is solid.
module fin_ramp(z0) {
    h = slot_lip_t + lug_engage;
    hx0 = -(slot_lip_t + lug_engage);
    translate([0, slot_y + lug_head_w / 2, 0])
        rotate([90, 0, 0])
            linear_extrude(lug_head_w)
                polygon([[0.5, z0 - h], [0.5, z0 + 0.5], [hx0, z0 + 0.5]]);
}

// 45-degree gusset: triangle in the XZ plane (vertical face against the
// plate, foot on the arm, 45-degree hypotenuse facing the shelf), swept
// along Y. Sunk 0.5 mm into both plate and arm so the union is solid.
module gusset(y) {
    x0 = t - 0.5;
    z0 = t - 0.5;
    translate([0, y + gusset_t, 0])
        rotate([90, 0, 0])
            linear_extrude(gusset_t)
                polygon([[x0, z0], [t + gusset_run, z0], [x0, t + gusset_run]]);
}

module bracket() {
    // arm: the bed slab; its top face (z = t) carries the shelf
    rounded_box([reach, bracket_w, t], r = corner_r,
                bottom_chamfer = bottom_chamfer);
    // back plate standing at the rail end, on the bed
    rounded_box([t, bracket_w, t + plate_h], r = r_t,
                bottom_chamfer = bottom_chamfer);
    // stop lip standing at the front end, on the arm
    translate([reach - t, 0, t - 0.5])
        rounded_box([t, bracket_w, lip_h + 0.5], r = r_t);
    // two gussets along the sides
    for (y = [0, bracket_w - gusset_t])
        gusset(y);
    // lug fins: the first starts on the (coupon/plate) bed strip, the second
    // grows out of the plate at 45 degrees (fin_ramp), so neither cantilevers
    lug_fin(lug_z0[0]);
    fin_ramp(lug_z0[1]);
    lug_fin(lug_z0[1]);
}

// "Print this first" coupon: the two production lug fins on a narrow strip
// of the production plate, in the production orientation — slide it into
// your real extrusion rail and tune slot_fit_tol. See NOTES.md.
module coupon() {
    w = 20;
    translate([0, slot_y - w / 2, 0])
        rounded_box([t, w, lug_len * 2 + 10 + 2 * t], r = r_t,
                    bottom_chamfer = bottom_chamfer);
    lug_fin(lug_z0[0]);
    fin_ramp(lug_z0[1]);
    lug_fin(lug_z0[1]);
}

module main() {
    assert(lug_neck_w < slot_mouth - 0.2,
           "lug neck must slide through the slot mouth — lower slot_fit_tol");
    assert(lug_head_w > slot_mouth + 0.5,
           "lug head must be wider than the mouth to hook the lips");
    assert(lug_head_w < slot_cavity_w - 2 * cavity_tol,
           "lug head too wide — it will not slide inside the cavity");
    assert(slot_lip_t + lug_engage <= slot_depth - 0.5,
           "lug bottoms out in the cavity before the plate seats on the face");
    assert(t >= 1.2 * 3, "walls under 3 perimeters at 0.4 nozzle");
    assert(lip_h >= 4, "stop lip too short to engage the shelf edge");
    assert(shelf_span >= 40, "usable shelf span under 40 mm — shorten gusset");

    if (part == "coupon") coupon();
    else bracket();
}

main();
