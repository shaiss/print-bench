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
// header (~8.5 above the board). Cut size matches gpio_notch_w / gpio_notch_x0
// below; B7 measured this window, it does not reshape it.
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

// B7 — GPIO notch window vs a 2×20 IDC ribbon housing, notch occupied.
// The wall cut is 55 × 8.5; those two numbers are the cut (do not "fix"
// them here). A typical IDC is ~51 × 8 (catalog pin_socket(2p54header,20,2)
// is 51.3 × 5.0 × 8.5; strain-relief IDC bodies are the wider 8 mm).
gpio_notch_w  = 55;     // +Y wall cut width (mm) — keep in lockstep with the cube
gpio_notch_x0 = -37.5;  // cut origin X; 55 mm centred on the 2×20 at x = −10
idc_len = 51;           // typical 2×20 IDC housing along the header (mm)
idc_thk = 8;            // typical IDC body through the notch (mm)
lead_d  = 1.6;          // 28 AWG silicone pair, typical OD (mm)
gpio_notch_h    = base_top_z - gpio_notch_bottom;            // 8.5 wall opening
gpio_lip_free_h = (base_top_z - lip_depth) - gpio_notch_bottom; // 6.0 inside lid lip
gpio_pin_above  = 2p54header[2] - 2p54header[3];            // pin length − below = 8.4
gpio_pin_top    = board_z + board_t + gpio_pin_above;        // ~16.8
gpio_comp = [for (c = pcb_components(board))
    if (c[3] == "2p54header" && c[4] == 20 && c[5] == 2) c][0];
gpio_xy   = pcb_coord(board, [gpio_comp.x, gpio_comp.y]);    // (−10, 24.5)
echo(str("B7 GPIO notch: wall ", gpio_notch_w, " x ", gpio_notch_h,
         " mm; lid-lip inner height ", gpio_lip_free_h,
         " mm; 2x20 at ", gpio_xy, " pin tops z=", gpio_pin_top,
         "; IDC envelope ", idc_len, " x ", idc_thk,
         " mm; leftover width ", gpio_notch_w - idc_len,
         " mm for fan leads (d=", lead_d, ")"));

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
            translate([gpio_notch_x0, cavity_y_half - 1, gpio_notch_bottom])
                cube([gpio_notch_w, wall + 2, base_top_z - gpio_notch_bottom + 1]);
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
                linear_extrude(lip_depth + 0.01)
                    difference() {
                        ring2d(cavity_x_half - fit_clearance, cavity_y_half - fit_clearance, lip_t);
                        for (px = [-1, 1], py = [-1, 1])
                            translate([px * post_x, py * post_y])
                                circle(r = post_r + fit_clearance);
                    }
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

module coupon() { //! two crops of the -X,+Y corner: the base's (wall, skirt, post, generated standoff) in place, the lid's at print pose across the plate — flip the lid crop over and it nests on the base corner
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
            translate([-outer_l / 2 - 0.6, 20.5, -0.5])
                cube([outer_l / 2 - 14, 18.2, base_top_z + 1]);
        }
        // lid -X,+Y corner at print pose (outer face down), cropped in
        // assembled coords — the flip lands it on the -Y side of the plate,
        // clear of the base corner: plate, register lip with its post notch,
        // lid-screw hole. The crop must reach lid_top_z, not base_top_z — the
        // plate sits ABOVE base_top_z, and a base-height crop leaves the lip
        // ring standing on a 0.5 mm plate sliver (measured: crop spanned
        // z[2.0,5.0] at print pose). Flip it over and drop it on the base
        // corner: the notch engages the post, the lip face meets the wall
        translate([0, 0, lid_top_z]) rotate([180, 0, 0])
            intersection() {
                lid();
                translate([-outer_l / 2 - 0.6, 20.5, -0.5])
                    cube([outer_l / 2 - 33, 18.2, lid_top_z + 1]);
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

// B7 occupied-notch proof. The 51×8 IDC envelope sits IN the wall notch (the
// lid-on access window), not on the header in empty cavity: a seated socket
// lives around the pins (top ~ gpio_pin_top, below the 17.5 lip) and always
// clears the shell; the unmeasured edge is whether that housing can share
// the notch with the ASSEMBLY step-7 fan leads with the lid on.
//
// Placement: IDC centred on the 55 mm cut (2 mm leftover each side); two
// Ø1.6 leads stacked in Z in the −X leftover strip, below the lid lip.
module gpio_idc_envelope() {
    translate([gpio_notch_x0 + (gpio_notch_w - idc_len) / 2,
               cavity_y_half - 1,
               gpio_notch_bottom])
        cube([idc_len, wall + 2, idc_thk]);
}

module gpio_fan_leads() {
    leftover = (gpio_notch_w - idc_len) / 2; // 2 mm with a centred 51 mm IDC
    lead_x = gpio_notch_x0 + leftover / 2;
    for (i = [0, 1])
        translate([lead_x,
                   cavity_y_half + wall / 2,
                   gpio_notch_bottom + 1.0 + lead_d / 2 + i * (lead_d + 0.4)])
            rotate([90, 0, 0])
                cylinder(d = lead_d, h = wall + 6, center = true);
}

module gpio_printed() {
    // +0.05 on the lid: same as fit-lid, so coplanar wall-top contact is not
    // a false interfere.
    union() {
        base();
        translate([0, 0, 0.05]) lid();
    }
}

part = "assembled"; // [assembled, base, base-board, lid, coupon, fit-pins, fit-pins-shift, fit-lid, fit-lid-crush, fit-gpio-occupied, fit-gpio-leads]

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
} else if (part == "fit-gpio-occupied") {
    // IDC envelope + fan leads in the notch ∩ lid-on shell — must interfere:
    // idc_thk 8 > gpio_lip_free_h 6.0, so the housing hits the lid lip.
    intersection() { gpio_printed(); union() { gpio_idc_envelope(); gpio_fan_leads(); } }
} else if (part == "fit-gpio-leads") {
    // the same two leads, no IDC — empty proves ASSEMBLY step 7 still has a
    // path out the notch when the housing is not jammed through it
    intersection() { gpio_printed(); gpio_fan_leads(); }
}
