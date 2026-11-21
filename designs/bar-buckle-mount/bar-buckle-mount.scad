// bar-buckle-mount — a split clamp for the ISO 4210 Ø22.2 mm flat-handlebar
// grip section that presents the de-facto action-cam two-finger quick-release
// buckle receiver, so a camera / light / remote that ships with the buckle
// clicks on and off the bar with no tools beyond the initial clamp install.
//
// Brief: issue #978. Style: workshop-utility.
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// Print orientation (brief): halves split on the bore axis; bore axis
// VERTICAL on the bed; buckle slot faces up on a supported top pad. Bolt
// holes are horizontal teardrops. No supports.
//
// Buckle-side numbers are community-measured (not a published GoPro spec) —
// sourced from Jay Abbott's 2014 quick-release clip (j-h-a/go-pro-mounts),
// caliper-fit to a genuine male buckle. Latch feel is coupon-tuned.
//
// The receiver sits entirely outside the continuing-bar silhouette on the
// end pad (y >= bar crown + margin), so a mid-bar ISO 4210 grip section
// can close without the fin colliding with the bar.

use <printability.scad>
include <styles/workshop-utility/style.scad>

/* [Bar clamp — ISO 4210 grip section] */
// Handlebar grip-section diameter (mm) — ISO 4210-2 flat-bar default.
bar_d = 22.2;
// Diametral bore clearance over bar_d (mm) — repo FDM 0.2–0.4; coupon-tuned.
// Also the total clamping take-up: each half leaves takeup/2 at the split
// so the flanges can close onto the bar instead of bottoming shell-to-shell.
bore_clear = 0.3;
// Clamp bearing width along the bar (mm) — the print height under the pad.
clamp_w = 20;
// Radial wall outside the bore (mm) — keep >= 1.2; 5 gives a stiff clamp.
shell = 5;

/* [Clamp bolt — purchased M5 + nyloc] */
bolt_d = screw_clearance_d("M5");
// Flange width past the bore OD (mm). Must clear socket_od/2 plus a
// printable wall after the style corner radius: 14 leaves ~2.5 mm.
flange_w = 14;
nut_af = 8.4;
nut_h = 5.0;
socket_h = socket_head("M5")[1];
socket_od = socket_head("M5")[0];

/* [Buckle receiver — community-measured, j-h-a/go-pro-mounts 2014] */
// Channel width (mm) — Abbott N2 table.
buckle_w = 28.6;
// Channel height under the roof lips (mm) — Abbott N2 table.
buckle_h = 4.9;
// Channel engagement length to the latch seat (mm) — Abbott N2 table.
buckle_l = 25.6;
// Roof lip shelf width each side (mm) — retains the buckle fingers.
roof_overhang = 3.0;
// Side wall outside the channel (mm) — Abbott N2 upper (3.3–3.95).
wall_max = 3.95;
// Height from channel floor to outer roof top (mm) — Abbott N2 table.
roof_top = 7.3;
// Centre guide ridge width (mm) — keeps the buckle centred.
guide_w = 3.5;
// Centre guide ridge height above the floor (mm).
guide_h = 2.0;
// Centre guide max length (mm); truncated short of the latch recess.
guide_l = 34;
// Lead-in length (mm) where the roof is fully open for finger entry.
ease_in = 3.8;
// Free travel past the latch before the hook bottoms (mm).
hook_backlash = 1.4;
// Latch catch recess width across the channel (mm).
latch_w = 6.0;
// Latch catch recess length along travel (mm).
latch_l = 2.5;
// Latch catch recess depth into the floor (mm) — coupon-tuned on the closed strip.
latch_depth = 1.0;
// Channel floor thickness (mm); must out-depth latch_depth.
floor_t = 1.6;
// Extra clearance on buckle channel W/H (mm) — open troughs sweep 0.0/0.2/0.4.
buckle_fit = 0.2;
// Rotate receiver 90° on the end pad.
// 0 = slide radially (over the bar); 1 = slide across the bar.
// No setting slides along the bar — the channel lives in the pad plane.
buckle_rot = 0; // [0, 1]

/* [Style / quality] */
corner_r = style_corner_r;
edge_chamfer = style_edge_chamfer;
$fn = style_fn;

/* [Part] */
part = "preview"; // [preview, clamp-receiver, clamp-plain, coupon, assembled, fit-close, fit-close-ctrl, fit-insert, fit-insert-ctrl]

// ---------------------------------------------------------------------------
// Derived
// ---------------------------------------------------------------------------

bore_d = bar_d + bore_clear;
bore_r = bore_d / 2;
outer_r = bore_r + shell;
bolt_x = outer_r + flange_w / 2;
overall_x = 2 * (outer_r + flange_w);
takeup = bore_clear;               // total split-face close; half each side
bar_keepout_r = bar_d / 2 + 0.5;   // continuing-bar clearance radius past the pad

recv_outer_w = buckle_w + 2 * wall_max + buckle_fit;
recv_outer_l = max(buckle_l, guide_l) + wall_max;
ch_h_nom = buckle_h + buckle_fit;
roof_t = max(roof_top - ch_h_nom, 1.2);
recv_h = floor_t + ch_h_nom + roof_t;

// Receiver parked entirely outside the continuing-bar silhouette so a
// mid-bar grip section can close and a buckle can slide to the latch.
pad_margin = 1.0;
recv_y0 = bar_keepout_r + pad_margin;
recv_span_y = (buckle_rot == 0) ? recv_outer_l : recv_outer_w;
recv_span_x = (buckle_rot == 0) ? recv_outer_w : recv_outer_l;
half_y = recv_y0 + recv_span_y + pad_margin;
// Through-both-halves bolt path (rule for the BOM): 2·half_y + nyloc stack.
bolt_len = 2 * half_y + nut_h + 2;
assert(overall_x >= recv_span_x + 2,
       "clamp overall_x too narrow for the receiver — widen flange_w");

assert(shell >= 1.2, "shell must be >= 1.2 mm");
assert(floor_t >= latch_depth + 0.4, "floor must out-depth the latch recess");
assert(bore_clear >= 0 && bore_clear <= 1.0, "bore_clear out of sane range");
assert(buckle_fit >= 0 && buckle_fit <= 1.0, "buckle_fit out of sane range");
assert(buckle_w > guide_w + 2, "buckle_w must clear the centre guide");
assert(roof_overhang > 0 && roof_overhang < buckle_w / 4, "roof_overhang");
assert(bar_d > 10 && bar_d < 50, "bar_d out of ISO flat-bar range");
assert(recv_y0 >= bar_keepout_r, "receiver must clear the continuing bar");

// ---------------------------------------------------------------------------
// Clamp half — PRINT ORIENTATION
//   Z = bar axis (vertical on the bed); height = clamp_w
//   Y = 0 is the split plane; this half occupies y >= 0
//   X = across the flanges
//   Top pad at z=clamp_w fully supports the buckle receiver
// ---------------------------------------------------------------------------

module bore_cut(extra = 0.02) {
    translate([0, 0, -extra])
        cylinder(d = bore_d, h = clamp_w + 2 * extra);
}

// Continuing bar past the clamp end — used to carve residual fin collision
// and as the fitcheck mating solid.
module continuing_bar(grow = 0, extra_z = 40) {
    translate([0, 0, -extra_z])
        cylinder(d = bar_d + grow, h = clamp_w + recv_h + 2 * extra_z);
}

module clamp_half_body() {
    r_use = min(corner_r, flange_w / 2 - 0.1, half_y / 2 - 0.1);
    difference() {
        intersection() {
            // Full rounded block centred on the bar…
            translate([-overall_x / 2, -half_y, 0])
                rounded_box([overall_x, 2 * half_y, clamp_w],
                            r = r_use,
                            bottom_chamfer = edge_chamfer);
            // …kept strictly at y >= 0. A bury past the split mints a
            // paper-thin sliver (printcheck min wall ≈ 0.00 mm).
            translate([-overall_x / 2 - 1, 0, -1])
                cube([overall_x + 2, half_y + 1, clamp_w + 2]);
        }
        bore_cut();
        // Clamping take-up: leave takeup/2 at the split so the flanges can
        // close onto the bar (effective bore → bar_d) instead of bottoming
        // shell-to-shell on an oversized hole.
        translate([-overall_x / 2 - 1, -0.01, -1])
            cube([overall_x + 2, takeup / 2 + 0.01, clamp_w + 2]);
    }
}

module bolt_features(nut_side = false) {
    for (sx = [-1, 1]) {
        translate([sx * bolt_x, half_y / 2, clamp_w / 2]) {
            teardrop_hole(d = bolt_d, l = half_y + 0.2);
            if (nut_side) {
                translate([0, half_y / 2 - nut_h / 2 + 0.01, 0])
                    rotate([90, 0, 0])
                        cylinder(d = nut_af / cos(30), h = nut_h + 0.02,
                                 center = true, $fn = 6);
            } else {
                // Socket recess with a light cheek chamfer on the outer rim
                // so the proud head doesn't present a sharp corner to knees.
                translate([0, half_y / 2 - socket_h / 2 + 0.01, 0])
                    rotate([90, 0, 0])
                        cylinder(d = socket_od, h = socket_h + 0.02,
                                 center = true);
                translate([0, half_y / 2 + 0.01, 0])
                    rotate([90, 0, 0])
                        cylinder(d1 = socket_od + 1.2, d2 = socket_od,
                                 h = 0.8, center = false);
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Buckle receiver — Abbott 2014 channel table (N2) untouched.
// Cross-section is a T-slot: full-width body under the lips, narrower
// centre opening between them so the 3 mm side shelves retain the fingers.
// ---------------------------------------------------------------------------

module buckle_receiver() {
    ch_w = buckle_w + buckle_fit;
    ch_h = buckle_h + buckle_fit;

    difference() {
        translate([-recv_outer_w / 2, 0, 0])
            cube([recv_outer_w, recv_outer_l, recv_h]);

        // Main channel above the floor (full Abbott width)
        translate([-ch_w / 2, -0.01, floor_t])
            cube([ch_w, buckle_l + 0.01, ch_h + 0.01]);

        // Centre top opening BETWEEN the roof lips — lips stay as shelves
        // of width roof_overhang on each side.
        translate([
            -(ch_w - 2 * roof_overhang) / 2,
            ease_in,
            floor_t + ch_h - 0.01
        ])
            cube([
                ch_w - 2 * roof_overhang,
                buckle_l - ease_in - hook_backlash + 0.02,
                roof_t + 0.04
            ]);

        // Lead-in: open the roof fully for the first ease_in of travel so
        // fingers can enter, then the lips catch.
        translate([-ch_w / 2, -0.01, floor_t + ch_h - 0.01])
            cube([ch_w, ease_in + 0.02, roof_t + 0.04]);

        // Latch catch recess in the floor
        translate([-latch_w / 2,
                   buckle_l - hook_backlash - latch_l,
                   floor_t - latch_depth])
            cube([latch_w, latch_l, latch_depth + 0.01]);

        // Thumb-access window through the roof (push-out port)
        translate([-latch_w / 2 - 1,
                   buckle_l - hook_backlash - latch_l - 1,
                   floor_t + ch_h])
            cube([latch_w + 2, latch_l + 4, roof_t + 0.02]);
    }

    // Centre guide ridge on the channel floor — stops short of the latch
    // recess so the lock tab can drop into the pocket.
    guide_end = min(guide_l, buckle_l - hook_backlash - latch_l - 0.5);
    if (guide_end > 0.5) {
        translate([-guide_w / 2, 0, floor_t])
            cube([guide_w, guide_end, guide_h]);
    }
}

// Park the receiver entirely at y >= recv_y0 (clear of the continuing bar).
module receiver_on_top() {
    bury = 0.2;
    if (buckle_rot == 0) {
        translate([0, recv_y0, clamp_w - bury])
            buckle_receiver();
    } else {
        // 90°: channel runs along X; keep the block's world-Y span at
        // [recv_y0, recv_y0 + recv_outer_w].
        translate([0, recv_y0 + recv_outer_w / 2, clamp_w - bury])
            rotate([0, 0, 90])
                translate([0, -recv_outer_l / 2, 0])
                    buckle_receiver();
    }
}

// ---------------------------------------------------------------------------
// Printable parts
// ---------------------------------------------------------------------------

module part_clamp_receiver() {
    difference() {
        union() {
            clamp_half_body();
            receiver_on_top();
        }
        bolt_features(nut_side = false);
        // Belt-and-suspenders: carve any residual fin collision with the
        // continuing bar PAST the clamp body. Must not start below
        // clamp_w — a full-height oversize cylinder would widen the tuned
        // bore past bore_clear and defeat coupon tuning (Jane [saw-it]).
        translate([0, 0, clamp_w])
            cylinder(d = bar_d + 1.0, h = recv_h + 40);
    }
}

module part_clamp_plain() {
    difference() {
        clamp_half_body();
        bolt_features(nut_side = true);
    }
}

// Fit coupon — bore section + three open W/H troughs (0.0 / 0.2 / 0.4) +
// one closed production-geometry strip (roof lips + latch) for the click.
module part_coupon() {
    bore_h = 8;
    fits = [0.0, 0.2, 0.4];
    strip_gap = 3;
    oy = 14;
    ox = recv_outer_w;
    base_t = 1.6;
    bury = 0.3;
    // Closed strip is a full production buckle_receiver() — base must
    // cover recv_outer_l, not just buckle_l (Bugbot: coupon undershoot).
    closed_oy = recv_outer_l + 2;

    bore_x = 2 * outer_r;
    bore_y = outer_r + 1;
    y0 = bore_y + 4;
    y_closed = y0 + 3 * (oy + strip_gap);
    base_y1 = y_closed + closed_oy + 2;
    base_x0 = -max(bore_x, ox) / 2 - 2;
    base_x1 = max(bore_x, ox) / 2 + 2;

    union() {
        translate([base_x0, -2, 0])
            rounded_box([base_x1 - base_x0, base_y1 + 2, base_t],
                        r = min(2, corner_r / 2),
                        bottom_chamfer = 0);

        // Vertical bore section
        translate([0, 0, base_t - bury])
            difference() {
                translate([-bore_x / 2, 0, 0])
                    rounded_box([bore_x, bore_y, bore_h],
                                r = min(2, corner_r / 2),
                                bottom_chamfer = 0);
                translate([0, 0, -0.01])
                    cylinder(d = bore_d, h = bore_h + 0.02);
                translate([-bore_x / 2 - 1, -bore_y, -1])
                    cube([bore_x + 2, bore_y, bore_h + 2]);
            }

        // Open troughs — width/height drag ladder (tight → loose:
        // buckle_fit 0.0 / 0.2 / 0.4). No roof, no latch — they do not
        // test the click.
        for (i = [0 : len(fits) - 1]) {
            f = fits[i];
            ch_w = buckle_w + f;
            ch_h = buckle_h + f;
            translate([-ox / 2,
                       y0 + i * (oy + strip_gap),
                       base_t - bury]) {
                difference() {
                    cube([ox, oy, floor_t + ch_h + 1.2]);
                    translate([(ox - ch_w) / 2, -0.01, floor_t])
                        cube([ch_w, oy + 0.02, ch_h + 1.3]);
                    for (sx = [0, 1]) {
                        x_edge = (ox - ch_w) / 2 + (sx == 0 ? 0 : ch_w);
                        hull() {
                            translate([x_edge - (sx == 0 ? 0 : 0.01),
                                       -0.01, floor_t + ch_h - 0.01])
                                cube([0.01, oy + 0.02, 1.3]);
                            translate([
                                x_edge + (sx == 0 ? roof_overhang
                                                  : -roof_overhang)
                                    - (sx == 0 ? 0 : 0.01),
                                -0.01,
                                floor_t + ch_h + roof_overhang - 0.01
                            ])
                                cube([0.01, oy + 0.02, 0.3]);
                        }
                    }
                }
                translate([(ox - guide_w) / 2, 0, floor_t])
                    cube([guide_w, oy, guide_h]);
            }
        }

        // Closed latch strip — production roof lips + latch recess at the
        // default buckle_fit. This is the strip that hears the click.
        translate([0, y_closed, base_t - bury])
            buckle_receiver();
    }
}

module part_assembled() {
    module half_in_use_frame(plain = false) {
        rotate([90, 0, 0])
            if (plain) part_clamp_plain();
            else part_clamp_receiver();
    }
    color("SteelBlue")
        mirror([0, 0, 1])
            half_in_use_frame(plain = true);
    color("LightSlateGray")
        half_in_use_frame(plain = false);
    color("Silver", 0.35)
        rotate([90, 0, 0])
            cylinder(d = bar_d, h = clamp_w + 40, center = true);
}

module part_preview() {
    translate([-overall_x / 2 - 8, 0, 0])
        part_clamp_receiver();
    translate([overall_x / 2 + 8, 0, 0])
        part_clamp_plain();
}

// ---------------------------------------------------------------------------
// Boolean fit proofs (ci.fitchecks) — never printed or sliced.
// fit-close: closed clamp ∩ continuing bar → empty at grow=0.
// fit-insert: buckle travel column ∩ continuing bar → empty at grow=0.
// Each empty row has a grown-bar interferes control so the check can fail.
// ---------------------------------------------------------------------------

module closed_clamp() {
    union() {
        part_clamp_receiver();
        mirror([0, 1, 0]) part_clamp_plain();
    }
}

module fit_close(grow = 0) {
    intersection() {
        closed_clamp();
        continuing_bar(grow = grow);
    }
}

// Channel cross-section extruded from fully-out through the seat — the
// volume a buckle sweeps. Buckle-agnostic and strictly stronger than any
// real two-finger buckle (fingers span ±buckle_w/2).
module buckle_travel_column() {
    ch_w = buckle_w + buckle_fit;
    ch_h = buckle_h + buckle_fit;
    // From the channel mouth (fully-out, still clear of the bar) through
    // the seat. Do not start below recv_y0 — that re-enters the bar disc.
    if (buckle_rot == 0) {
        translate([-ch_w / 2, recv_y0, clamp_w - 0.2 + floor_t])
            cube([ch_w, buckle_l + 2, ch_h]);
    } else {
        translate([-buckle_l / 2 - 1,
                   recv_y0 + (recv_outer_w - ch_w) / 2,
                   clamp_w - 0.2 + floor_t])
            cube([buckle_l + 2, ch_w, ch_h]);
    }
}

module fit_insert(grow = 0) {
    intersection() {
        buckle_travel_column();
        continuing_bar(grow = grow);
    }
}

if (part == "clamp-receiver")
    part_clamp_receiver();
else if (part == "clamp-plain")
    part_clamp_plain();
else if (part == "coupon")
    part_coupon();
else if (part == "assembled")
    part_assembled();
else if (part == "fit-close")
    fit_close();
else if (part == "fit-close-ctrl")
    fit_close(grow = 2.0);
else if (part == "fit-insert")
    fit_insert();
else if (part == "fit-insert-ctrl")
    fit_insert(grow = 8.0);
else if (part == "preview")
    part_preview();
else
    assert(false, str("bar-buckle-mount: unknown part '", part, "'"));
