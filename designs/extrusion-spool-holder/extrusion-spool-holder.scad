// extrusion-spool-holder — a filament-spool peg that locks into the side
// slot of standard 2020 T-slot aluminum extrusion and cantilevers a
// horizontal axle stub the spool drops onto, so it spins on its own bore
// with zero hardware and zero bearings: slide the peg anywhere along an
// open rail, drop the spool on. The lug vocabulary is the measured one
// extrusion-shelf-bracket established (its slot ground truth is NopSCADlib
// E2020); what is new here is the load: a shelf board loads the lugs in
// shear, a hanging spool loads them in a tipping couple, so the peg
// carries the axle on a flaring trunk instead of a flat arm.
//
// Print pose (evidence in NOTES.md): the part prints rotated a quarter
// turn from its use pose — the blade's T-lugs lie flat on the bed
// (widest layer down, so the hammer heads stack as identical layers and
// nothing overhangs), the face plate bridges 6–9 mm onto the blade, the
// trunk flares outward at <=38 degrees from vertical, and the axle stub
// prints as a vertical hollow cylinder — a round bearing surface with no
// overhang at all, instead of a 51.4 mm horizontal cylinder whose top
// dome can never print support-free. In use the stub's layers run
// perpendicular to its axis, so the cantilever's bending tension stays
// in-plane to the layers (the strong direction).
//
// Slot ground truth: NopSCADlib E2020 (lib/NopSCADlib/vitamins/extrusions.scad)
// — mouth 6.0, cavity 12.0 wide / 8.0 deep, lips 2.0. Lugs slide in along
// the slot axis only: install by sliding the peg on from an open rail end,
// not by pressing straight on.
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
// Slide clearance per side in the slot mouth (mm) — the family's
// coupon-tuned value (extrusion-shelf-bracket). TUNE ON THE COUPON in
// 0.05 steps.
slot_fit_tol = 0.15;
// How far the head hooks under each lip (mm); head = mouth + 2*hook.
// Real M5 hammer T-nuts for the 6-series hook about 2.2.
lug_hook = 2.2;
// Head thickness under the lip (mm) — the engagement depth
lug_engage = 1.5;
// Fin length along the slot (mm)
lug_len = 10;
// Slide clearance per side of the head inside the cavity (mm)
cavity_tol = 0.3;
// First fin start and fin pitch along the slot (mm)
lug_x0 = 6;
lug_pitch = 24;

/* [Spool] */
// Spool bore diameter (mm) — caliper yours; 52 is the common 1 kg value
// (Prusament/Polymaker/eSUN). 55 (Bambu-style) and 30 (250 g) are -D
// overrides, not separate designs.
spool_bore = 52;
// Spool width between flange faces (mm), 1 kg typical minimum — the stub
// must reach past it so the spool cannot walk off. 66-71 covers the range.
spool_w = 66;
// Spool overall diameter (mm) — 1 kg typical; sets the cantilever moment
// the trunk carries (informational, not built).
spool_od = 200;

/* [Axle fit] */
// Diametral spin clearance between spool bore and axle stub (mm) —
// coupon-tuned; 0.6 turns freely without wobble on a bore-true spool.
bore_clearance = 0.6;
// Axle stub length past the seat shoulder (mm) — must seat past the
// spool's centre of mass (>= spool width).
axle_len = 68;
// Axle stub wall thickness (mm) — the stub is a hollow tube so a 1 kg
// spool does not cost a 150 g peg
axle_wall = 5;

/* [Body] */
// Rail face to spool seat (mm) — the spool flange clears the extrusion
// while spinning. Brief minimum 25.
standoff = 28;
// Seat shoulder diameter (mm) — the ring the near flange lands on; must
// be wider than the bore so the spool stops here, not on the trunk.
shoulder_d = 58;
// Seat shoulder height (mm)
seat_h = 3;
// Face plate thickness (mm) — 3+ perimeters at 0.4 nozzle
plate_t = 6;
// Face plate length / width (mm) — length covers the lug block, width
// overhangs the 20 mm extrusion face by 2 mm a side like the family
// bracket's plate
plate_x = 46;
plate_w = 24;

/* [Quality] */
// Iterating: 48. Production: 96+ (style_fn = 64).
$fn = style_fn;

/* [Hidden] */
part = "peg"; // [peg, coupon, fitcheck-slot, fitcheck-slot-ctrl, fitcheck-bore, fitcheck-bore-ctrl]

// ---- derived -----------------------------------------------------------
// Neck passes the mouth: family's 5.7 = 6.0 - 2*0.15.
lug_neck_w = slot_mouth - 2 * slot_fit_tol;
// Head hooks behind the lips: wider than the mouth, free in the cavity.
lug_head_w = slot_mouth + 2 * lug_hook;
// Head depth below the rail face plane — the print-pose bed offset.
head_depth = slot_lip_t + lug_engage;
// The blade (web + fin heads) runs along X from lug_x0 for two fins + gap.
lug_span = lug_len + lug_pitch;
x_c = lug_x0 + lug_span / 2;        // trunk / axle centre on the slot line
// Axle stub rides the spool bore.
axle_d = spool_bore - bore_clearance;
axle_bore_d = axle_d - 2 * axle_wall;
// Print-pose Z landmarks: bed at the head's outboard face, rail face
// plane at head_depth, seat plane at head_depth + standoff.
z_plate = head_depth;
z_shoulder = head_depth + standoff;
z_seat = z_shoulder + seat_h;
z_tip = z_seat + axle_len;
// Plate rounding fits the plate's own footprint (rounded_box's hull
// overshoots size when 2*r exceeds the smallest dimension).
r_plate = min(style_corner_r, plate_w / 2 - 0.5);

// The slide-in blade: a continuous neck-width web along the slot axis
// with a hammer head under each end. Plain boxes, constant
// cross-sections — every layer prints as drawn, widest at the bed.
module blade(neck_w = lug_neck_w) {
    head_w = slot_mouth + 2 * lug_hook;
    // web: neck through the mouth, buried into the plate at the top
    translate([lug_x0, -neck_w / 2, 0])
        cube([lug_span, neck_w, head_depth + 1]);
    // two hammer heads, constant cross-section on the bed
    for (x = [lug_x0, lug_x0 + lug_pitch])
        translate([x, -head_w / 2, 0])
            cube([lug_len, head_w, lug_engage]);
}

// Face plate against the extrusion face — bridges onto the blade (6-9 mm
// spans), so no bottom chamfer: anything below the rail-face plane must
// fit inside the mouth slit or a fin profile.
module plate() {
    translate([x_c - plate_x / 2, -plate_w / 2, z_plate])
        rounded_box([plate_x, plate_w, plate_t], r = r_plate,
                    bottom_chamfer = 0);
}

// Trunk: flare from the plate up to the seat shoulder, a hull so the
// slopes stay straight tangent lines — <= 38 degrees from vertical in
// the narrow direction, self-supporting. Local coordinates (origin at
// the axle centre): peg() already places this module at [x_c, 0, 0].
module trunk() {
    hull() {
        translate([-plate_x / 2, -plate_w / 2, z_plate + plate_t - 0.01])
            rounded_box([plate_x, plate_w, 0.02], r = r_plate,
                        bottom_chamfer = 0);
        translate([0, 0, z_shoulder - 0.01])
            cylinder(d = shoulder_d, h = 0.02);
    }
}

// Seat shoulder + axle stub: the shoulder is the ring the near flange
// lands on (and the inboard keeper — the bore cannot pass it), the stub
// is a hollow tube the spool spins on.
module axle() {
    translate([0, 0, z_shoulder])
        chamfered_cylinder(d = shoulder_d, h = seat_h + 0.01,
                           chamfer1 = 0, chamfer2 = 1);
    translate([0, 0, z_seat])
        difference() {
            chamfered_cylinder(d = axle_d, h = axle_len,
                               chamfer1 = 0, chamfer2 = 2);
            // bore through-cut: an enclosed ceiling would be a 41 mm
            // internal bridge no FDM printer can print without sagging
            translate([0, 0, -0.5])
                cylinder(d = axle_bore_d, h = axle_len + 1);
        }
}

module peg(fit_tol = slot_fit_tol) {
    blade(slot_mouth - 2 * fit_tol);
    plate();
    translate([x_c, 0, 0]) {
        trunk();
        axle();
    }
}

// "Print this first" coupon: the production blade + a strip of the
// production plate (tunes slot_fit_tol in your real rail), plus three
// axle rings sweeping bore_clearance (tunes the spin fit in your real
// spool). Ring OD = spool_bore - the embossed clearance.
module coupon() {
    sweep = [0.3, 0.6, 0.9];
    // lug strip: production blade under a plain plate strip, slot line
    // centred — slide it into your rail to tune slot_fit_tol
    blade();
    translate([lug_x0 - 3, -7, z_plate])
        cube([lug_span + 6, 14, plate_t]);
    // axle rings + one label bar island beside them (detached, so
    // nothing obstructs the ring bores when you trial-fit a spool)
    for (i = [0:2]) {
        x = lug_span + 42 + i * 62;
        translate([x, 0, 0])
            difference() {
                chamfered_cylinder(d = spool_bore - sweep[i], h = 10,
                                   chamfer1 = 0.6, chamfer2 = 0.6);
                translate([0, 0, -0.5])
                    cylinder(d = axle_bore_d, h = 11);
            }
    }
    translate([lug_span + 42 - 12, 30, 0])
        difference() {
            cube([62 * 2 + 24, 12, 2]);
            for (i = [0:2])
                translate([12 + i * 62, 6, 1.4])
                    linear_extrude(0.7)
                        text(str(sweep[i]), size = 5, halign = "center",
                             valign = "center");
        }
}

// The extrusion as the blade sees it, in the print pose: the rail-face
// plane is z = head_depth (the plate's bed side), so metal occupies the
// slot depth BELOW it, 20 mm wide, with the mouth slit cut through the
// lip zone and the cavity void opened behind the lips. The peg must
// thread its neck through the slit and keep its heads inside the cavity
// void — intersection with this solid is interference.
module extrusion_metal() {
    difference() {
        // top face 0.02 below the rail-face plane: the plate seats on the
        // real rail with zero clearance, and a coplanar boolean face emits
        // degenerate zero-volume facets that read as false interference
        translate([lug_x0 - 20, -10, z_plate - slot_depth])
            cube([lug_span + 40, 20, slot_depth - 0.02]);
        // mouth slit: through the lips, mouth wide
        translate([lug_x0 - 20, -slot_mouth / 2, z_plate - slot_lip_t])
            cube([lug_span + 40, slot_mouth, slot_lip_t + 0.1]);
        // cavity: behind the lips, cavity wide
        translate([lug_x0 - 20, -slot_cavity_w / 2,
                   z_plate - slot_depth - 0.1])
            cube([lug_span + 40, slot_cavity_w,
                  slot_depth - slot_lip_t + 0.1]);
    }
}

// A spool bore as the axle sees it: a thin tube the bore's inner surface
// would sweep, seated on the shoulder (0.05 off the seat plane so the
// check measures the radial fit, not a coincident face).
module bore_tube(id) {
    translate([x_c, 0, z_seat + 0.05])
        difference() {
            cylinder(d = id + 8, h = 71);
            translate([0, 0, -0.5]) cylinder(d = id, h = 72);
        }
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
    assert(standoff >= 25, "standoff under the brief's 25 mm minimum");
    assert(bore_clearance >= 0.3,
           "diametral bore clearance under 0.3 — the spool will bind");
    assert(shoulder_d > spool_bore + 0.5,
           "seat shoulder must stop the bore — wider than spool_bore");
    assert(axle_len >= spool_w,
           "axle stub shorter than the spool — it can walk off");
    assert(axle_wall >= 2.4, "axle wall under 2.4 mm (6 perimeters)");
    assert(plate_t >= 1.2 * 3, "walls under 3 perimeters at 0.4 nozzle");

    if (part == "coupon") coupon();
    else if (part == "fitcheck-slot")
        intersection() { peg(); extrusion_metal(); }
    else if (part == "fitcheck-slot-ctrl")
        // neck grown past the mouth: the negative control must interfere
        intersection() { peg(-0.15); extrusion_metal(); }
    else if (part == "fitcheck-bore")
        intersection() { peg(); bore_tube(spool_bore); }
    else if (part == "fitcheck-bore-ctrl")
        // bore tighter than the stub by 0.2 (a real bore 0.8 under
        // nominal at the default clearance): must interfere
        intersection() { peg(); bore_tube(axle_d - 0.2); }
    else peg();
}

main();
