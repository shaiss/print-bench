// snap-clamshell-box — a clamshell box that prints flat and assembled, folds
// closed, and snaps shut. Advanced (Tier-3) reference design fusing two
// compliant sub-mechanisms in one support-free print.
//
// NAME NOTE: the closure is a compliant tab-in-window SNAP (two stable states,
// open/latched, separated by the strip flexing) — not a buckled-arch *bistable*.
// The true bistable primitive lives in the `bistable-toggle` design; this box
// deliberately reuses the simpler snap so the latch prints flat with the trays.
//
//   Domain 1 (compliant): a LIVING HINGE (thin flexure web along the spine)
//     joins the two trays — the doc's living/notch hinge — and a CANTILEVER
//     SNAP latch (a second, independent flexure) holds the box shut.
//   Domain 2 (supports) / CC1: printed FLAT, both trays open and coplanar on
//     the bed, so every wall is vertical and nothing overhangs. The living-hinge
//     web is a short top bridge; the latch prints flat. Zero supports.
//
// Print flat (this file's default pose), fold the lid 180° about the spine so the
// openings meet, and the front latch snaps over the lid rim. `demo_fold` folds
// the lid for preview only — the PRINTED model is flat.
//
// The living hinge is deliberately thin (one of the doc's flexure families):
// PETG/PP fold for many cycles, PLA cracks. All dimensions in millimeters.

use <printability.scad>

/* [Box] */
// Inner tray footprint width, X (mm)
inner_w = 50;
// Inner tray depth per tray, Y (mm)
inner_d = 34;
// Wall height (each tray) (mm)
wall_h = 12;
// Wall thickness (mm)
wall_t = 1.6;
// Floor thickness (mm)
floor_t = 1.6;

/* [Living hinge] */
// Flexure web thickness (mm) — thin: the doc's living-hinge family
hinge_t = 0.6;
// Gap between the two trays at the spine (mm)
hinge_gap = 2.0;

/* [Snap latch] */
// Latch arm thickness (mm)
latch_t = 1.6;
// Latch arm height above the rim (mm)
latch_h = 9;
// Hook depth (how far the hook reaches over the lid rim) (mm)
hook = 2.0;

/* [Preview only] */
// Fold the lid about the spine (deg). PRINT AT 0.
demo_fold = 0; // [0:5:180]

/* [Quality] */
$fn = 40;

// ---- derived -----------------------------------------------------------
tw = inner_w + 2 * wall_t;             // tray outer width (X)
td = inner_d + 2 * wall_t;             // tray outer depth (Y)

// One open tray, centred on X, hinge edge at y = 0, body extending +Y to td.
module tray() {
    translate([-tw/2, 0, 0])
    difference() {
        rounded_box([tw, td, wall_h], r = 3, bottom_chamfer = 0.6);
        translate([wall_t, wall_t, floor_t])
            cube([tw - 2*wall_t, td - 2*wall_t, wall_h]);   // open pocket
    }
}

// Base latch: the outer wall is extended above the rim into a compliant strip
// with a rectangular WINDOW. It flexes outward as the lid's tab ramps past, then
// springs back so the tab is captured in the window. (tray frame: outer wall at
// y = td, rim at z = wall_h.)
lw     = 20;                          // latch strip width, X
win_z  = wall_h + latch_h * 0.55;     // window centre height (closed frame = same, base doesn't fold)
win_h  = 3.2;                          // window height
module base_latch() {
    difference() {
        translate([-lw/2, td - wall_t, wall_h - 0.01])
            cube([lw, wall_t, latch_h]);           // raised compliant strip
        translate([-lw/2 + 3, td - wall_t - 0.1, win_z - win_h/2])
            cube([lw - 6, wall_t + 0.2, win_h]);   // window
    }
}

// Lid tab: a ramped nub protruding OUTWARD from the lid outer wall (tray frame
// y = td), at the flat height that folds to meet the base window
// (closed z = win_z ⇒ flat z = 2*wall_h − win_z). Ramp on the leading (lower-z)
// side so it cams the base strip out on the way in.
tab_flat_z = 2 * wall_h - win_z;
module lid_tab() {
    // hull a full-height slab at the wall to a smaller slab out at +hook: gives
    // a nub that protrudes `hook` and ramps on its outward face
    hull() {
        translate([-lw/2 + 3.5, td - 0.2, tab_flat_z - win_h/2 + 0.4])
            cube([lw - 7, 0.2, win_h - 0.8]);
        translate([-lw/2 + 3.5, td + hook, tab_flat_z - win_h/2 + 0.9])
            cube([lw - 7, 0.1, win_h - 1.8]);
    }
}

// Living-hinge web: thin flexure across the spine at the rim top, fused into
// both trays' hinge-edge wall tops.
module living_hinge() {
    ov = wall_t + 0.5;   // overlap into each tray wall
    translate([-tw/2, -(hinge_gap/2 + ov), wall_h - hinge_t])
        cube([tw, hinge_gap + 2*ov, hinge_t]);
}

module main() {
    assert(hinge_t >= 0.4, "living hinge under two layers — it will tear");
    assert(hinge_t <= 1.0, "living hinge too thick to fold without a huge radius");

    // base tray: extends −Y, carries the windowed latch strip
    translate([0, -hinge_gap/2, 0]) mirror([0, 1, 0]) {
        tray();
        base_latch();
    }
    // lid tray: extends +Y, folds about the SPINE TOP (y=0, z=wall_h) for the
    // preview so the openings meet correctly. Carries the ramped tab.
    translate([0, 0, wall_h]) rotate([demo_fold, 0, 0]) translate([0, 0, -wall_h])
        translate([0, hinge_gap/2, 0]) {
            tray();
            lid_tab();
        }

    // living-hinge flexure across the spine (does not fold in the preview — it
    // is the thing that bends; kept flat so both attach points stay visible)
    living_hinge();
}

main();
