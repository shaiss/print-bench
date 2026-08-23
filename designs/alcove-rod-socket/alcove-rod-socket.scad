// alcove-rod-socket — parametric two-part screw-together end socket for a
// round curtain / closet rod in a recess or alcove. Used in pairs: one boss
// screwed flat to each facing wall, the rod's ends plugging into knurled
// collars that hand-thread onto the bosses (rod axis ⟂ wall). Unthread the
// collar and the rod comes down tool-free.
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.

use <printability.scad>                      // screw presets, chamfered_cylinder
use <threads-fdm.scad>                       // thread_neck / thread_bore_cut
include <BOSL2/std.scad>                     // cyl with edge roundings
include <styles/workshop-utility/style.scad> // family tokens; $fn set below

/* [Part] */
// What to render: the two printable parts, the fit coupons, the assembled
// preview, or the boolean mate proofs (ci.fitchecks — never printed).
part = "assembly"; // [assembly, boss, collar, thread-coupon, bore-coupon, fit-mate, fit-mate-ctrl, cutaway]

/* [Rod & socket] */
// Rod barrel outer diameter, measured where it sits in the socket (mm)
rod_d = 40.0;
// Diametral slip clearance added to rod_d for the socket bore (mm)
rod_clearance = 0.6;
// How deep the rod end plugs into the collar (mm). Deep+shallow install
// pair: keep this side, print the far holder with a smaller value.
engagement_depth = 28;
// Structural wall thickness (mm) — load-bearing 40 mm part, not the 1.2 floor
wall = 3.2;

/* [Printed thread — fixed FDM profile] */
// Only the major diameter scales (with the bore); pitch/flanks/tol are the
// proven trapezoidal profile from lib/threads-fdm.scad (45° flanks print
// supportless in a vertical bore both ways).
// Thread flank depth (mm)
thread_depth = 1.2;
// Axial rise per start (mm)
thread_pitch = 4;
// Thread starts — 2 gives a fast close (lead 8 mm per turn)
thread_starts = 2;
// Radial thread fit clearance (mm) — dial on the thread coupon
thread_tol = 0.3;

/* [Boss] */
// Wall-plate (flange) thickness (mm)
flange_t = 6.4;
// Plain shoulder lifting the male thread off the bed (mm), so first-layer
// squish cannot fatten the first turns and jam the collar. Also the phase
// offset shared with the collar's groove — see collar_use().
lead_in = 1.6;
// Male thread length on the boss neck (mm)
neck_len = 10;
// Mounting screws: 1 central, or 2 off-axis for a heavier install (grows
// the flange so both heads clear the neck)
screw_count = 1; // [1,2]
// Metric size of the flat-head mounting screws
screw_size = "M5"; // [M2,M2.5,M3,M4,M5,M6]

/* [Collar] */
// Knurl flute count around the grip band (guarded: flutes must stay printable)
knurl_flutes = 36;
// Knurl flute depth (mm)
knurl_depth = 1.2;
// Minimum printed flute width (mm) — 3 extrusion widths at a 0.4 nozzle
knurl_min_width = 1.2;

/* [Quality] */
// Thread helix segments per turn — 96 holds chord error under 0.02 mm at
// this major diameter (the lib refuses coarser settings itself)
thread_seg = 96;

$fn = style_fn; // 64 — the family's curve resolution

// ---------------------------------------------------------------------------
// Derived
// ---------------------------------------------------------------------------
bore_d = rod_d + rod_clearance;                    // 40.6 — rod slip bore
thread_major = bore_d + 2 * wall;                  // 47.0 — scales with bore
thread_root_d = thread_major - 2 * thread_depth;   // 44.6 — neck core
female_bore_d = thread_root_d + 2 * thread_tol;    // 45.2 — collar base bore
collar_lower_od = thread_major + 2 * thread_tol + 2 * wall; // 54.0
rod_tube_od = bore_d + 2 * wall;                   // 47.0
collar_lower_h = lead_in + neck_len + 1.0;         // 12.6 — +1 relief past neck
collar_h = engagement_depth + collar_lower_h;      // 40.6
boss_h = flange_t + lead_in + neck_len;            // 18.0

shank_d = screw_clearance_d(screw_size);           // 5.5 for M5
csk_d = socket_head(screw_size)[0] + 0.5;          // 10.0 — flat-head recess
csk_h = (csk_d - shank_d) / 2;                     // 90° cone depth
screw_r2 = thread_root_d / 2 + csk_d / 2 + 1.5;    // off-axis screw radius
seat_lip = 2.4;                                    // flange edge past collar rim
flange_d = screw_count == 2
    ? 2 * (screw_r2 + csk_d / 2 + wall)
    : collar_lower_od + 2 * seat_lip;

// Knurl geometry: one cylindrical cutter per flute, axis outside the surface
// so the groove bottom lands knurl_depth below the rim.
knurl_arc_w = PI * collar_lower_od / knurl_flutes; // flute pitch at surface
knurl_flute_r = 0.4 * knurl_arc_w;                 // cutter radius
knurl_groove_w = 2 * sqrt(knurl_flute_r ^ 2
    - (knurl_flute_r - knurl_depth) ^ 2);          // printed groove width

assert(knurl_flutes >= 6, "knurl_flutes: fewer than 6 is not a grip.");
assert(knurl_groove_w >= knurl_min_width, str(
    "knurl groove prints ", knurl_groove_w, " mm wide — under the ",
    knurl_min_width, " mm floor. Reduce knurl_flutes or knurl_depth."));
assert(knurl_arc_w >= knurl_groove_w + 0.8, str(
    "knurl flutes merge: ", knurl_arc_w, " mm pitch vs ", knurl_groove_w,
    " mm groove. Reduce knurl_flutes."));
assert(knurl_depth <= wall - 1.2, str(
    "knurl_depth ", knurl_depth, " leaves under 1.2 mm of wall over the ",
    "thread groove. Cut knurl_depth."));
// The screw head must stay below the plane the rod bottoms on, or the rod
// seats on the screw instead of the shoulder.
assert(boss_h - csk_h < flange_t + collar_lower_h,
    "screw head recess breaks through the collar's rod seat — raise the neck.");

// ---------------------------------------------------------------------------
// Boss — wall plate + male thread. Printed flange-down (its use orientation:
// the flange face at z=0 goes against the wall).
// ---------------------------------------------------------------------------
module boss() {
    difference() {
        union() {
            // wall plate: family chamfers on both edges (anchor=BOTTOM — BOSL2
            // cylinders are origin-centered by default, and a centered flange
            // here would float 3.2 mm off the bed)
            cyl(d = flange_d, h = flange_t,
                anchor = BOTTOM,
                chamfer1 = style_edge_chamfer,
                chamfer2 = style_edge_chamfer);
            // plain lead-in shoulder for the thread, embedded 0.5 mm into the
            // flange — a union that only touches on a face renders as two
            // shells and slices with an empty layer
            translate([0, 0, flange_t - 0.5])
                cylinder(d = thread_root_d, h = lead_in + 0.51);
            // male thread; its own top chamfer lets the collar find the start
            translate([0, 0, flange_t + lead_in])
                thread_neck(thread_major, thread_depth, thread_pitch,
                            thread_starts, neck_len, seg = thread_seg);
        }
        mount_screw_holes();
    }
}

// Central screw through plate + neck (head recessed flush in the neck's top
// face), plus the optional off-axis pair for screw_count = 2.
module mount_screw_holes() {
    translate([0, 0, -0.01]) cylinder(d = shank_d, h = boss_h + 0.02);
    translate([0, 0, boss_h - csk_h])
        cylinder(d1 = shank_d, d2 = csk_d, h = csk_h + 0.01);
    if (screw_count == 2)
        for (a = [0, 180]) rotate([0, 0, a]) {
            translate([screw_r2, 0, -0.01])
                cylinder(d = shank_d, h = flange_t + 0.02);
            translate([screw_r2, 0, flange_t - csk_h])
                cylinder(d1 = shank_d, d2 = csk_d, h = csk_h + 0.01);
        }
}

// ---------------------------------------------------------------------------
// Collar — the knurled rod socket, use orientation: rim at z=0 (seats on the
// boss's flange face), rod enters the bore from the top.
//
// Phase alignment: the female groove cut starts lead_in above the rim — the
// same offset the boss lifts its male thread — so when the rim seats on the
// flange face, rib and groove are exactly in phase. That is what makes the
// fit-mate boolean an exact proof rather than a coincidence of rotation.
// ---------------------------------------------------------------------------
module collar_use() {
    flare_h = (collar_lower_od - rod_tube_od) / 2;  // 45° flare, 3.5
    difference() {
        union() {
            chamfered_cylinder(d = collar_lower_od, h = collar_lower_h,
                               chamfer1 = style_edge_chamfer,
                               chamfer2 = style_edge_chamfer);
            // 45° flare from the grip band down to the rod tube (embedded 1
            // mm so the union welds, not kisses)
            translate([0, 0, collar_lower_h - 1.0])
                cylinder(d1 = collar_lower_od, d2 = rod_tube_od, h = 1.0 + flare_h);
            translate([0, 0, collar_lower_h + flare_h - 0.5])
                chamfered_cylinder(d = rod_tube_od,
                                   h = engagement_depth - flare_h + 0.5,
                                   chamfer1 = 0, chamfer2 = style_edge_chamfer);
        }
        // female thread: the mandatory minor bore, then the groove cutter
        translate([0, 0, -0.01])
            cylinder(d = female_bore_d, h = collar_lower_h + 0.01);
        translate([0, 0, lead_in])
            thread_bore_cut(thread_major, thread_depth, thread_pitch,
                            thread_starts, collar_lower_h - lead_in, thread_tol,
                            seg = thread_seg);
        // rod bore with a 45° lead-in mouth where the rod enters
        translate([0, 0, collar_lower_h - 0.01])
            cylinder(d = bore_d, h = engagement_depth + 0.02);
        translate([0, 0, collar_h - 1.0])
            cylinder(d1 = bore_d, d2 = bore_d + 2.0, h = 1.01);
        knurl_cut();
    }
}

// Print orientation: rod mouth on the bed, thread at the top of the print —
// the internal thread never sees first-layer squish.
module collar() {
    translate([0, 0, collar_h]) rotate([180, 0, 0]) collar_use();
}

module knurl_cut() {
    r_axis = collar_lower_od / 2 + knurl_flute_r - knurl_depth;
    z0 = style_edge_chamfer + 0.2;
    for (i = [0 : knurl_flutes - 1])
        rotate([0, 0, i * 360 / knurl_flutes])
            translate([r_axis, 0, z0])
                cylinder(r = knurl_flute_r, h = collar_lower_h - 2 * z0);
}

// ---------------------------------------------------------------------------
// Fit coupons ("print this first")
// ---------------------------------------------------------------------------

// Thread coupon: the production male thread as a short stub plus the
// production bore + groove as a ring. Screw the ring onto the stub: it should
// run free with slight play and hold without cross-threading.
module thread_coupon() {
    stub_neck = 6;
    ring_h = lead_in + stub_neck + 0.6;
    gap = 8;
    translate([-(collar_lower_od + gap) / 2, 0, 0])
        union() {
            chamfered_cylinder(d = collar_lower_od, h = 2.0, chamfer2 = 0);
            // shoulder embedded 0.5 mm into the base and 0.01 into the neck —
            // face-touching unions export as non-manifold shells
            translate([0, 0, 1.5])
                cylinder(d = thread_root_d, h = lead_in + 0.51);
            translate([0, 0, 2.0 + lead_in])
                thread_neck(thread_major, thread_depth, thread_pitch,
                            thread_starts, stub_neck, seg = thread_seg);
        }
    translate([(collar_lower_od + gap) / 2, 0, 0])
        difference() {
            chamfered_cylinder(d = collar_lower_od, h = ring_h);
            translate([0, 0, -0.01])
                cylinder(d = female_bore_d, h = ring_h + 0.02);
            translate([0, 0, lead_in])
                thread_bore_cut(thread_major, thread_depth, thread_pitch,
                                thread_starts, ring_h - lead_in, thread_tol,
                                seg = thread_seg);
        }
}

// Bore coupon: a slice of the production rod tube — slide it along the real
// rod. Mouths are chamfered so a tight fit reads as drag on the straight
// section, not a wedge jamming at the rim.
module bore_coupon() {
    ring_h = 12;
    difference() {
        chamfered_cylinder(d = rod_tube_od, h = ring_h);
        translate([0, 0, -0.01]) cylinder(d = bore_d, h = ring_h + 0.02);
        translate([0, 0, -0.01]) cylinder(d1 = bore_d + 2.0, d2 = bore_d, h = 1.0);
        translate([0, 0, ring_h - 1.0])
            cylinder(d1 = bore_d, d2 = bore_d + 2.0, h = 1.01);
    }
}

// ---------------------------------------------------------------------------
// Proofs and previews (never printed)
// ---------------------------------------------------------------------------

// Boolean mate proof: the production male thread intersected with the
// production collar solid, seated exactly as the assembly seats. Zero facets
// = the thread mates at thread_tol. The 90° control must interfere: at
// starts = 2 a quarter turn parks every rib half a pitch from every groove,
// which is real volumetric overlap, not a coincident-surface artifact.
module fit_mate(rot = 0) {
    intersection() {
        translate([0, 0, flange_t + lead_in])
            thread_neck(thread_major, thread_depth, thread_pitch,
                        thread_starts, neck_len, seg = thread_seg);
        translate([0, 0, flange_t]) rotate([0, 0, rot]) collar_use();
    }
}

module assembly() {
    boss();
    translate([0, 0, flange_t]) collar_use();
    // ghost rod showing engagement (preview only — never exported)
    %translate([0, 0, flange_t])
        cylinder(d = rod_d, h = collar_h - flange_t + 25);
}

module cutaway() {
    difference() {
        assembly();
        translate([0, -75, -1]) cube([75, 150, 120]);
    }
}

if (part == "boss") boss();
else if (part == "collar") collar();
else if (part == "thread-coupon") thread_coupon();
else if (part == "bore-coupon") bore_coupon();
else if (part == "fit-mate") fit_mate();
else if (part == "fit-mate-ctrl") fit_mate(90);
else if (part == "cutaway") cutaway();
else assembly();
