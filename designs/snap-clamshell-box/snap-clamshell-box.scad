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
// Wall height (each tray) (mm). 13 (not 12) so the closed cavity —
// 2*(wall_h - floor_t) = 22.8 mm — clears a 21.8 mm earbud with 1.0 mm to
// spare; the lifestyle scene stages the box with earbuds (issue #230 §3).
wall_h = 13;
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
// Outward standoff of the windowed strip from its original (flush) position
// (mm). The bug (issue #230 §1): at 0 the strip sits in the SAME wall plane the
// lid's front wall folds onto — 216 mm³ of interference, the first close jams.
// >= wall_t + a print clearance lifts the strip's inner face outboard of the
// closed lid wall so nothing clashes; the tab (protruding `hook`) still reaches
// through the window. A local buttress below the rim carries the offset strip so
// it still prints flat with no support. `latch_clr = 0` is the pre-fix pose the
// `closed-clash-ctrl` fitcheck renders as its negative control.
latch_clr = 2.0;

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

// Base latch: a compliant strip with a rectangular WINDOW, standing above the
// rim. It flexes outward as the lid's tab ramps past, then springs back so the
// tab is captured in the window. (tray frame: outer wall at y = td, rim at
// z = wall_h.)
//
// The strip is offset OUTWARD by `latch_clr` from the outer-wall plane. At the
// original `latch_clr = 0` the strip shared the exact plane the lid's front wall
// folds onto — the 216 mm³ closed-pose clash of issue #230. Offsetting it clear
// of the closed lid wall is the fix; a buttress below the rim (z <= wall_h,
// where the lid never reaches) carries the offset strip so it still prints flat.
lw     = 20;                          // latch strip width, X
win_z  = wall_h + latch_h * 0.55;     // window centre height (closed frame = same, base doesn't fold)
win_h  = 3.2;                          // window height
// The windowed compliant strip alone (no buttress). `clr` is the outward
// standoff; the fitchecks intersect THIS against the closed lid.
module latch_strip(clr = latch_clr) {
    y0 = td - wall_t + clr;               // strip inner face
    difference() {
        translate([-lw/2, y0, wall_h - 0.01])
            cube([lw, wall_t, latch_h]);           // raised compliant strip
        translate([-lw/2 + 3, y0 - 0.1, win_z - win_h/2])
            cube([lw - 6, wall_t + 0.2, win_h]);   // window
    }
}
// Buttress: fills from the tray outer wall out to the offset strip, bed to rim.
// Capped at the rim (z = wall_h) — the fold plane — so it is structurally part
// of the base and cannot reach into the lid's closed volume (z >= wall_h).
module latch_buttress() {
    translate([-lw/2, td - wall_t, 0])
        cube([lw, wall_t + latch_clr, wall_h]);
}
module base_latch() {
    latch_buttress();
    latch_strip();
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

// --- placement (shared by main() and the fitchecks so they cannot drift) -----
// Base tray + its windowed strip, extending −Y. The strip's outward standoff is
// `clr` (default latch_clr); the fitchecks pass 0 to recover the pre-fix pose.
module placed_base(clr = latch_clr) {
    translate([0, -hinge_gap/2, 0]) mirror([0, 1, 0]) {
        tray();
        base_latch();
    }
}
module placed_base_strip(clr = latch_clr) {
    translate([0, -hinge_gap/2, 0]) mirror([0, 1, 0]) latch_strip(clr);
}
// Lid tray, folded `fold`° about the SPINE TOP (y=0, z=wall_h). fold=0 is the
// flat print pose; fold=180 is the closed box. `with_tab` includes the ramped
// latch tab.
module placed_lid(fold, with_tab = true) {
    translate([0, 0, wall_h]) rotate([fold, 0, 0]) translate([0, 0, -wall_h])
        translate([0, hinge_gap/2, 0]) {
            tray();
            if (with_tab) lid_tab();
        }
}

module main() {
    assert(hinge_t >= 0.4, "living hinge under two layers — it will tear");
    assert(hinge_t <= 1.0, "living hinge too thick to fold without a huge radius");

    placed_base();                 // base tray + windowed latch strip, −Y
    placed_lid(demo_fold);         // lid tray + ramped tab, folds about spine top

    // living-hinge flexure across the spine (does not fold in the preview — it
    // is the thing that bends; kept flat so both attach points stay visible)
    living_hinge();
}

// --- part dispatch -----------------------------------------------------------
// Default (no -D part): the printable flat model. The `closed-clash*` parts are
// non-printable fit probes for designs/snap-clamshell-box/ci.fitchecks — they
// render the boolean of the latch strip against the CLOSED lid, never a part.
part = undef;
if (part == undef || part == "")      main();
else if (part == "closed-clash")
    // The fix in place: strip standoff = latch_clr → must be EMPTY (the strip
    // clears the closed lid wall). This is AC1 of issue #230.
    intersection() { placed_base_strip(latch_clr); placed_lid(180); }
else if (part == "closed-clash-ctrl")
    // Negative control: standoff forced to 0 (the pre-fix pose) → must INTERFERE
    // (the 216 mm³ clash returns), proving the check can fail.
    intersection() { placed_base_strip(0); placed_lid(180); }
else
    assert(false, str("unknown part: ", part));
