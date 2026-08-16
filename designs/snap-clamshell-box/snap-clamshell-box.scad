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
// Outward clearance between the latch strip and the folded lid's front wall (mm)
latch_clear = 0.4;

/* [Preview only] */
// Fold the lid about the spine (deg). PRINT AT 0.
demo_fold = 0; // [0:5:180]

/* [CI fit-check — not a print parameter] */
// "" = the box. "fitcheck" = the closed-pose interference between the base
// latch and the folded lid's shell (must render EMPTY — the strip clears the
// lid wall). "fitcheck_neg" = the same probe with the strip rebuilt flush inside
// the wall band, the geometry this design shipped with (must render NON-EMPTY —
// proves the check can fail). Wired by designs/snap-clamshell-box/ci.fitchecks.
part = "";

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

// Base latch: a compliant strip above the rim carrying a rectangular WINDOW. It
// flexes outward as the lid's tab ramps past, then springs back so the tab is
// captured in the window. (tray frame: outer wall at y = td, rim at z = wall_h.)
//
// The strip stands OUTBOARD of the wall face by `clear`, and that offset is the
// whole point: the 180° fold maps the lid's own front wall onto the tray-frame
// band y ∈ [td − wall_t, td] — exactly where the strip used to be built — so a
// strip flush with the wall is coplanar-coincident with the closed lid over the
// strip's full height. That shipped as 216.00 mm³ of interference (issue #230):
// the first close was the failure, and no flat-pose gate could see it, because
// in the printed (flat) pose the two halves are 76 mm apart.
//
// A strip offset outboard has nothing under it, so a 45° root gusset carries it
// out from the wall. The gusset sits entirely BELOW the rim (z < wall_h), which
// is the one region the folded lid never occupies — the lid spans
// z ∈ [wall_h, 2·wall_h] — so it can be as thick as it needs to be without
// re-introducing the clash. Its underside is a 45° ramp, so it still prints
// supportless in the flat pose.
lw     = 20;                          // latch strip width, X
win_z  = wall_h + latch_h * 0.55;     // window centre height (closed frame = same, base doesn't fold)
win_h  = 3.2;                          // window height
module base_latch(clear = latch_clear) {
    y0  = td + clear;                 // strip inner face, outboard of the wall
    off = clear + wall_t;             // total outward reach at the rim
    union() {
        // 45° root gusset: wall face → strip, all of it below the rim
        hull() {
            translate([-lw/2, td - wall_t, wall_h - off - 0.01])
                cube([lw, wall_t, 0.01]);
            translate([-lw/2, td - wall_t, wall_h - 0.02])
                cube([lw, off + wall_t, 0.01]);
        }
        difference() {
            translate([-lw/2, y0, wall_h - 0.4])
                cube([lw, wall_t, latch_h + 0.39]);    // raised compliant strip
            translate([-lw/2 + 3, y0 - 0.1, win_z - win_h/2])
                cube([lw - 6, wall_t + 0.2, win_h]);   // window
        }
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

// ---- placement -----------------------------------------------------------
// The placed halves live in modules so the fit check below and the model itself
// are driven by the SAME transforms. A probe that re-typed the fold would only
// prove the probe's arithmetic agrees with itself, which is how the clash got
// through in the first place.

// base tray: extends −Y, carries the windowed latch strip
module placed_base_tray() {
    translate([0, -hinge_gap/2, 0]) mirror([0, 1, 0]) tray();
}
module placed_base_latch(clear = latch_clear) {
    translate([0, -hinge_gap/2, 0]) mirror([0, 1, 0]) base_latch(clear);
}
// lid tray: extends +Y, folds about the SPINE TOP (y=0, z=wall_h) for the
// preview so the openings meet correctly. Carries the ramped tab.
module placed_lid(fold = demo_fold, with_tab = true) {
    translate([0, 0, wall_h]) rotate([fold, 0, 0]) translate([0, 0, -wall_h])
        translate([0, hinge_gap/2, 0]) {
            tray();
            if (with_tab) lid_tab();
        }
}

module main() {
    assert(hinge_t >= 0.4, "living hinge under two layers — it will tear");
    assert(hinge_t <= 1.0, "living hinge too thick to fold without a huge radius");
    // The strip now stands `latch_clear` outboard of the wall, so the tab has to
    // reach across that offset AND the strip's own thickness before it is inside
    // the window at all. Without this the latch silently stops engaging.
    assert(hook >= latch_clear + wall_t,
           "latch tab cannot reach through the offset strip — raise hook or lower latch_clear");

    if (part == "fitcheck") {
        // CLOSED POSE, the pose no other check renders: the base latch must
        // clear the folded lid's shell. The lid is taken WITHOUT its tab —
        // tab-in-window is the intended engagement, not interference.
        intersection() { placed_base_latch(); placed_lid(180, false); }
    } else if (part == "fitcheck_neg") {
        // clear = −wall_t puts the strip's inner face back at td − wall_t, i.e.
        // flush inside the wall band — the geometry this design shipped with.
        // MUST produce facets. Note it is −wall_t and not 0: at clear = 0 the
        // strip is already outboard and merely *touches* the lid wall at y = td,
        // which intersects to a degenerate zero-volume sliver. That would still
        // count facets and "pass" the control while proving nothing.
        intersection() { placed_base_latch(-wall_t); placed_lid(180, false); }
    } else {
        placed_base_tray();
        placed_base_latch();
        placed_lid();

        // living-hinge flexure across the spine (does not fold in the preview —
        // it is the thing that bends; kept flat so both attach points stay
        // visible)
        living_hinge();
    }
}

main();
