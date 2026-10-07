// sbc-case — vented single-board-computer case (Raspberry Pi 4 primary target),
// deliberately hardware-rich: the reference / stress-test design for the
// assembly-instructions feature (scripts/assembly.sh, issues #98 → #156 → #158).
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// LICENSE NOTE: this design includes NopSCADlib (GPL-3.0) — it reads the board
// footprint, inserts, screws and fan from the vendored vitamin library and
// declares them in assembly.conf, which makes the exported geometry a GPL-3.0
// combined work (see docs/licensing.md and README.md#licensing).

use <printability.scad>        // repo FDM helpers (OPENSCADPATH="$PWD/lib:$PWD")
// NopSCADlib vitamins — the GPL opt-in. core.scad is utils + screws only; the
// pcb/insert/fan modules live in the singular files and their catalog
// constants (RPI4, F1BM3, fan40x11) in the plural ones, so all are included
// explicitly — an unresolved include/module only WARNs and exits 0, which
// would ship a watertight STL with the vitamins missing.
include <NopSCADlib/core.scad>
include <NopSCADlib/vitamins/pcb.scad>
include <NopSCADlib/vitamins/pcbs.scad>
include <NopSCADlib/vitamins/screw.scad>
include <NopSCADlib/vitamins/insert.scad>
include <NopSCADlib/vitamins/inserts.scad>
include <NopSCADlib/vitamins/fan.scad>
include <NopSCADlib/vitamins/fans.scad>

/* [Board] */
// NopSCADlib pcb type the case is sized around. The standoff pattern is
// generated from pcb_holes() of this type at build time — retargeting to
// another board in the catalog is this one variable (outline clearances are
// derived below, though tall/off-edge connectors of a very different board
// deserve a check of port_overhang_x/y).
board = RPI4;

/* [Case] */
// Perimeter wall thickness (mm) — 2.0 for a rigid case, keep >= 1.2
wall = 2.0;
// Floor thickness (mm)
floor_t = 2.0;
// Lid plate thickness (mm)
lid_t = 2.5;
// Clearance around the board inside the cavity (mm)
board_clr = 0.75;
// Standoff height under the board (mm) — brief allows 4–6; 5 clears pin
// headers / SD card under an RPI4
standoff_h = 5;
// Interior height above the floor (mm): board 1.4 + tallest component
// (usb_Ax2 stacked socket, 15.6) + standoff 5 + 2 spare = 24
interior_h = 24;
// Lid register lip: depth into the cavity (mm) and thickness (mm)
lip_depth = 2.5;
lip_t = 2.0;

/* [Fit & tolerances] */
// Lid register lip vs cavity wall (mm) — tune on the coupon first
fit_clearance = 0.25;
// 45° lead-in on the lip's entering (cavity) edge — feel only; fitchecks
// prove clearance at full seat (Jane, PM B5). Tune on the coupon first.
lip_lead_chamfer = 0.45;
// Board-hole-to-standoff alignment slop proven by the fit-pins fitcheck (mm)
pin_slop = 0.15;

/* [Fan] */
// NopSCADlib fan type bolted to the lid (catalog's 40 mm fan)
fan_type = fan40x11;
// Fan centre (mm); biased off geometric centre toward the RPI4 SoC
fan_center = [-10, 0];

/* [Ports & vents] */
// How far the +X connectors overhang the board edge (mm): usb_A body l=17
// centred at x=+36 and rj45 l=21 at x=+34 both reach x=+44.5 = edge + 2.0
port_overhang_x = 2.0;
// How far the -Y connectors overhang (mm): usb_C body spans y to -29.575
// = edge - 1.6
port_overhang_y = 1.6;
// Gap between the open-edge skirt top and the board underside (mm)
skirt_margin = 0.5;
// Bottom of the GPIO access notch in the +Y wall (mm) — clears the 2x20
// header (~8.5 above the board)
gpio_notch_bottom = 17.5;

/* [Hardware] */
// Heat-set insert for every M3 boss (lid screws, fan screws)
insert_type = F1BM3;
// Board screw — M2.5 into printed pilot bosses (F1BM2p5 exists in the
// vendored tree but is 5.8 long: too tall for a 5 mm standoff, so the board
// fastener is a screw into a boss, not an insert; see NOTES.md)
board_screw = M2p5_cap_screw;
// Lid screw, through the lid plate into F1BM3
lid_screw = M3_cap_screw;

/* [Quality] */
// Production value (64); 32 is fine while iterating.
$fn = 64;

// ── Derived from the vitamin, never hand-typed (G4: measure the export) ──
board_l  = pcb_length(board);     // 85
board_w  = pcb_width(board);      // 56
board_t  = pcb_thickness(board);  // 1.4
board_hole_d = pcb_hole_d(board); // 2.75

post_d   = 2 * insert_hole_radius(insert_type) + 2 * 1.6; // 7.2: insert hole + shell
post_r   = post_d / 2;
insert_d = 2 * insert_hole_radius(insert_type);           // 4.0 melt-in hole
standoff_d = 7;                                           // M2.5 boss around its pilot

cavity_x_half = board_l / 2 + port_overhang_x + board_clr;   // 45.25
cavity_y_half = board_w / 2 + board_clr + post_d + 0.15;     // 36.1: board + post inside wall
outer_l = 2 * (cavity_x_half + wall);                        // 94.5
outer_w = 2 * (cavity_y_half + wall);                        // 76.2

post_x  = 40;                            // lid-screw posts (clear of all cable bands)
post_y  = cavity_y_half - post_r + 0.25; // merges 0.25 into the side wall
skirt_top = floor_t + standoff_h - skirt_margin;  // 6.5: under the board, under every connector
base_top_z = floor_t + interior_h;                // 26: wall/post tops = lid underside
board_z  = floor_t + standoff_h;                  // 7: board underside plane
lid_top_z = base_top_z + lid_t;                   // 28.5
boss_h   = 7;                                     // fan insert boss: insert 5.8 + web
pilot_d  = 2 * screw_pilot_hole(board_screw);     // M2.5 tap drill

fan_bore_d = fan_bore(fan_type);   // 37
fan_pitch  = fan_hole_pitch(fan_type); // 16 -> holes 32 apart

echo(str("case outer: ", outer_l, " x ", outer_w, " mm; base ", base_top_z,
         " mm tall, fan stack ", boss_h + fan_depth(fan_type), " mm above it"));
echo(str("board: ", board_l, " x ", board_w, " x ", board_t, ", holes d", board_hole_d,
         " at ", [for (h = pcb_holes(board)) pcb_coord(board, h)]));

// ── Printable geometry ─────────────────────────────────────────────────────

module base() { //! printed base tray: floor, +Y wall, skirt rim, 4 insert posts, 4 board standoffs
    union() {
        difference() {
            // outer shell, bed-chamfered, hollowed above the floor.
            // rounded_box is corner-anchored (spans [0, size], like cube) —
            // translate it into this file's origin-centred frame, which every
            // other feature already speaks (NOTES decision 11)
            difference() {
                translate([-outer_l / 2, -outer_w / 2, 0])
                    rounded_box([outer_l, outer_w, base_top_z], r = 4, bottom_chamfer = 0.6);
                translate([0, 0, floor_t])
                    linear_extrude(interior_h + 1)
                        rounded_square([2 * cavity_x_half, 2 * cavity_y_half], r = 3, center = true);
            }
            // three open edges ABOVE the skirt: +X (USB-A x2 / Ethernet),
            // -X (micro-SD), -Y (USB-C / 2x micro-HDMI / jack). center=true is
            // REQUIRED — the translate points are the wall centrelines, so the
            // cut must straddle the wall in X/Y (deleting center shifts it onto
            // the centreline, leaving an inner sliver / missing the -Y wall). The
            // bug was the Z: translating to skirt_top with center=true centred
            // the cut ON z=6.5, spanning z[-3.75,16.75] — it deleted the 6.5 mm
            // skirt and left the wall a band floating 16.75 mm over the bed,
            // watertight and sliceable yet unprintable (angle-only gates can't
            // see a vertical curtain over air; NOTES decision 16). Fix: lift the
            // Z centre by half the cut height so the cube FLOOR rests on skirt_top.
            for (sx = [-1, 1])
                translate([sx * (cavity_x_half + wall / 2), 0, skirt_top + (base_top_z - skirt_top + 1) / 2])
                    cube([wall + 2.5, 2 * outer_w + 2, base_top_z - skirt_top + 1], center = true);
            translate([0, -(cavity_y_half + wall / 2), skirt_top + (base_top_z - skirt_top + 1) / 2])
                cube([2 * cavity_x_half + 1, wall + 2.5, base_top_z - skirt_top + 1], center = true);
            // GPIO access notch: cut down from the top edge of the +Y wall
            // over the 2x20 header — a notch, not a window, so nothing bridges
            translate([-37.5, cavity_y_half - 1, gpio_notch_bottom])
                cube([55, wall + 2, base_top_z - gpio_notch_bottom + 1]);
            // vent slots in the +Y wall: 4 slots on a 15 mm pitch, so 3 mm
            // webs separate them and each slot top is a real 12 mm bridge.
            // (Was 5 @ 11.5 mm pitch with a 12 mm slot — 0.5 mm overlap fused
            // them into one ~58 mm opening whose top bridged as a single
            // curtain that sags in PETG; NOTES decision 13.)
            for (i = [-1.5, -0.5, 0.5, 1.5])
                translate([i * 15, cavity_y_half + wall / 2, 12])
                    vent_slot();
        }
        // four lid-screw posts with through insert holes (through so an M3x10
        // bottoms out in free space, not in plastic)
        for (px = [-1, 1], py = [-1, 1])
            translate([px * post_x, py * post_y, floor_t])
                insert_post(base_top_z - floor_t, through = true);
        // board standoffs — positions generated from the vitamin's hole list
        translate([0, 0, board_z])
            pcb_screw_positions(board)
                standoff();
    }
}

module lid() { //! printed lid: plate, register lip (notched around the posts), aperture, insert bosses on the inner face, screw holes
    difference() {
        union() {
            // register lip: vertical ring dropping lip_depth into the cavity,
            // fit_clearance clear of the walls and notched around the posts
            // (the posts rise to the lid's underside; post + notch is what
            // locates the lid — proven by the fit-lid fitcheck)
            translate([0, 0, base_top_z - lip_depth])
                register_lip();
            // plate
            translate([0, 0, base_top_z])
                linear_extrude(lid_t)
                    rounded_square([outer_l, outer_w], r = 4, center = true);
            // fan insert bosses on the INNER face, hanging into the cavity: the
            // lid then prints outer-face-down with the lip ring and the bosses
            // as standing features (insert holes opening up), nothing bridging
            for (fx = [-1, 1], fy = [-1, 1])
                translate([fan_center[0] + fx * fan_pitch, fan_center[1] + fy * fan_pitch, base_top_z - boss_h])
                    difference() {
                        cylinder(d = post_d, h = boss_h);
                        translate([0, 0, -0.1])
                            cylinder(d = insert_d, h = insert_length(insert_type) + 0.1);
                    }
        }
        // lid screws into the base posts
        for (px = [-1, 1], py = [-1, 1])
            translate([px * post_x, py * post_y, base_top_z - 0.1])
                cylinder(d = 2 * screw_clearance_radius(lid_screw), h = lid_t + 0.2);
        // fan screws pass through the plate into the inner bosses (M3 x 20 =
        // fan 11 + plate 2.5 + insert 5.8)
        for (fx = [-1, 1], fy = [-1, 1])
            translate([fan_center[0] + fx * fan_pitch, fan_center[1] + fy * fan_pitch, base_top_z - 0.1])
                cylinder(d = 2 * screw_clearance_radius(lid_screw), h = lid_t + 0.2);
        // fan aperture = the fan's own bore
        translate([fan_center[0], fan_center[1], base_top_z - 0.1])
            cylinder(d = fan_bore_d, h = lid_t + 0.2);
    }
}

// ── Shared sub-modules (coupon and fitchecks reuse these, never copies) ────

module ring2d(x_half, y_half, t) { //! rounded-rect ring, outer half-extents given, thickness t
    difference() {
        rounded_square([2 * x_half, 2 * y_half], r = 3, center = true);
        rounded_square([2 * (x_half - t), 2 * (y_half - t)], r = 1.5, center = true);
    }
}

module register_lip_profile() { //! lip ring 2D (shared by lid, coupon, fitchecks)
    xo = cavity_x_half - fit_clearance;
    yo = cavity_y_half - fit_clearance;
    xi = cavity_x_half - fit_clearance - lip_t;
    yi = cavity_y_half - fit_clearance - lip_t;
    difference() {
        difference() {
            rounded_square([2 * xo, 2 * yo], r = 3, center = true);
            rounded_square([2 * xi, 2 * yi], r = 1.5, center = true);
        }
        for (px = [-1, 1], py = [-1, 1])
            translate([px * post_x, py * post_y])
                circle(r = post_r + fit_clearance);
    }
}

module register_lip_outer_envelope(chamfer) { //! 45° outer taper volume; inner/notches unconstrained
    xo = cavity_x_half - fit_clearance;
    yo = cavity_y_half - fit_clearance;
    union() {
        translate([0, 0, chamfer])
            linear_extrude(lip_depth - chamfer + 0.01)
                rounded_square([2 * xo, 2 * yo], r = 3, center = true);
        translate([0, 0, -0.01])
            linear_extrude(chamfer + 0.02,
                           scale = [xo / (xo - chamfer), yo / (yo - chamfer)])
                rounded_square([2 * (xo - chamfer), 2 * (yo - chamfer)],
                               r = max(3 - chamfer, 1.5), center = true);
    }
}

module register_lip() { //! vertical register lip with optional 45° lead-in on the entering edge
    // 45° lead-in at the cavity tip (assembled z = base_top_z - lip_depth): the
    // outer face that enters the base when seating (Jane, PM B5). Full
    // register_lip_profile() intersected with a tapered outer envelope so only
    // the outer perimeter moves — inner face and post-notch cuts stay fixed.
    // Print pose: top of the standing lip — a shallow flare, not a mid-air bridge.
    chamfer = min(max(lip_lead_chamfer, 0), lip_depth - 0.05);
    if (chamfer < 0.05) {
        linear_extrude(lip_depth + 0.01)
            register_lip_profile();
    } else {
        render() intersection() {
            linear_extrude(lip_depth + 0.01)
                register_lip_profile();
            register_lip_outer_envelope(chamfer);
        }
    }
}

module insert_post(h, through) { //! vertical M3 insert boss; through=true bores clear for the screw tip
    difference() {
        cylinder(d = post_d, h = h);
        translate([0, 0, through ? -0.1 : h - insert_length(insert_type)])
            cylinder(d = insert_d, h = h + 0.2);
    }
}

module standoff() { //! one board standoff at a pcb hole; drawn hanging below the board plane
    translate([0, 0, -standoff_h])
        difference() {
            cylinder(d = standoff_d, h = standoff_h);
            translate([0, 0, 0.5])
                cylinder(d = pilot_d, h = standoff_h);
        }
}

module vent_slot() { //! one stadium vent through the +Y wall
    rotate([90, 0, 0])
        linear_extrude(wall + 2, center = true)
            rounded_square([12, 4.5], r = 2.2, center = true);
}

// ── Vitamins at their assembled positions (default render) ─

module board_vitamin() { translate([0, 0, board_z]) pcb(board); }
module fan_vitamin()   { translate([fan_center[0], fan_center[1], lid_top_z + fan_depth(fan_type) / 2]) fan(fan_type); }

// ── Vitamin wrappers for assembly.conf ──────────────────────────────────────
// scripts/assembly.sh builds its exploded view with `use <this file>` plus
// core.scad only. `use` re-exports this file's modules (including everything
// its includes define) but NOT its top-level variables — so a manifest line
// like `pcb(RPI4)` reaches pcb() with RPI4 undefined and aborts inside the
// vitamin (measured: pcb()'s rounded_square assert). These origin-only
// wrappers close over THIS file's scope, where every catalog constant
// resolves, and assembly.conf's vitamin: lines name them instead of the
// constants. Screw lengths here and the BOM descriptions in assembly.conf
// state the same hardware — keep them in sync.
module vitamin_pcb()          { pcb(board); }
module vitamin_insert()       { insert(insert_type); }
module vitamin_fan()          { fan(fan_type); }
module vitamin_board_screw()  { screw(board_screw, 6); }
module vitamin_lid_screw()    { screw(lid_screw, 10); }
module vitamin_fan_screw()    { screw(M3_dome_screw, 20); }
module vitamin_washer()       { washer(M3_washer); }

// ── Fit coupon (print this first) ───────────────────────────────────────────
// Lid crop +X/+Y track register_lip_profile() so tuning fit_clearance on the
// coupon does not re-slice the B5 chamfer band (Drik R3; see NOTES 27).
coupon_crop_y_min = 20.5; // shared −Y face for both corner crops
coupon_lid_crop_above_yi = 1.0; // crop top = yi + this (below chamfer slice band)
coupon_lid_crop_x_outboard = 0.15; // +X trim stays slightly outside lip_xi (R2 default)

module coupon() { //! two crops of the -X,+Y corner: the base's (wall, skirt, post, generated standoff) in place, the lid's at print pose across the plate — flip the lid crop over and it nests on the base corner
    lip_xi = cavity_x_half - fit_clearance - lip_t;
    lip_yi = cavity_y_half - fit_clearance - lip_t;
    // Above default clearance the lip/chamfer moves; trim +Y a hair so the
    // crop plane does not re-slice the band (measured: +0.05 needs ~0.2 mm).
    lid_crop_y_pad = coupon_lid_crop_above_yi
        - max(0, fit_clearance - 0.25) * 4;
    lid_crop_xw = outer_l / 2 + 0.6 - lip_xi + coupon_lid_crop_x_outboard;
    lid_crop_yh = lip_yi + lid_crop_y_pad - coupon_crop_y_min;
    union() {
        // base -X,+Y corner as printed (floor down): real wall the lid lip
        // registers against, skirt profile, the through-insert lid-screw post,
        // one generated board standoff (the RPI4 hole pattern is centered at
        // x = -10, so the -X corner is the one that carries a standoff), and —
        // crop widened (-33 -> -14, X to ~-14.6) — the leftmost vent slot, so
        // the coupon rehearses the 12 mm PETG bridge before the full base does
        // (Jane, PR #397). It stays the fit AND structure proof.
        intersection() {
            base();
            translate([-outer_l / 2 - 0.6, coupon_crop_y_min, -0.5])
                cube([outer_l / 2 - 14, 18.2, base_top_z + 1]);
        }
        // lid -X,+Y corner at print pose (outer face down), cropped in
        // assembled coords — the flip lands it on the -Y side of the plate,
        // clear of the base corner: plate, register lip with its post notch,
        // lid-screw hole. The crop must reach lid_top_z, not base_top_z — the
        // plate sits ABOVE base_top_z, and a base-height crop leaves the lip
        // ring standing on a 0.5 mm plate sliver (measured: crop spanned
        // z[2.0,5.0] at print pose). Flip it over and drop it on the base
        // corner: the notch edge meets the post, the lip face meets the wall.
        // Lid crop +X at −lip_xi (lip inner): the old +X face at x ≈ −33.6
        // bisected the +Y lip through the B5 chamfer band (~0.03 mm mesh
        // slivers, coupon 92/100). +Y top at lip_yi + coupon_lid_crop_above_yi
        // tracks fit_clearance — a fixed crop top re-slices the chamfer when
        // clearance moves (NOTES 27). Rehearses −X wall register, the −X lip
        // face, the lower +Y lip band and lead-in on the straight −X approach;
        // the outer −X,+Y corner arc and the post-notch arc above that band
        // stay on the full lid.
        translate([0, 0, lid_top_z]) rotate([180, 0, 0])
            intersection() {
                lid();
                translate([-outer_l / 2 - 0.6, coupon_crop_y_min, -0.5])
                    cube([lid_crop_xw, lid_crop_yh, lid_top_z + 1]);
            }
    }
}

// ── Boolean fit checks (ci.fitchecks) ───────────────────────────────────────
// fit-pins: pins at the vitamin's hole positions rise through the standoff
// pilots — empty proves the standoff pattern is generated from pcb_holes().

module fit_pins(dx = 0) {
    translate([dx, 0, board_z - standoff_h + 0.5])
        pcb_screw_positions(board)
            cylinder(d = pilot_d - pin_slop, h = standoff_h + 0.5);
}

part = "assembled"; // [assembled, base, base-board, lid, coupon, fit-pins, fit-pins-shift, fit-lid, fit-lid-crush]

if (part == "assembled") {
    base();
    lid();
    board_vitamin();
    fan_vitamin();
} else if (part == "base") {
    base();
} else if (part == "base-board") {
    // base tray with the Raspberry Pi seated on the generated standoffs (no
    // lid, no fan) — the "board on the standoffs, ports open" pose the product
    // page promises, so a stranger sees their own board on it, not a bare tray
    base();
    board_vitamin();
} else if (part == "lid") {
    // printed orientation: outer face down (flipped) — flat bed face, lip and
    // bosses standing up, insert holes opening up
    translate([0, 0, lid_top_z]) rotate([180, 0, 0]) lid();
} else if (part == "coupon") {
    coupon();
} else if (part == "fit-pins") {
    intersection() { base(); fit_pins(); }
} else if (part == "fit-pins-shift") {
    intersection() { base(); fit_pins(0.6); }   // 0.6 mm off-pattern must interfere
} else if (part == "fit-lid") {
    // seated +0.05: strictly clear of walls, posts and standoffs (the seat
    // itself is coplanar contact, which renders no facets either way)
    intersection() { base(); translate([0, 0, 0.05]) lid(); }
} else if (part == "fit-lid-crush") {
    intersection() { base(); translate([0, 0, -1]) lid(); }  // seated 1 mm low must interfere
}
