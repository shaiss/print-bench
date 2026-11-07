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

use <printability.scad>
include <styles/workshop-utility/style.scad>

/* [Bar clamp — ISO 4210 grip section] */
// Handlebar grip-section diameter (mm) — ISO 4210-2 flat-bar default.
bar_d = 22.2;
// Diametral bore clearance over bar_d (mm) — repo FDM 0.2–0.4; coupon-tuned.
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
buckle_w = 28.6;
buckle_h = 4.9;
buckle_l = 25.6;
roof_overhang = 3.0;
wall_max = 3.95;
roof_top = 7.3;
guide_w = 3.5;
guide_h = 2.0;
guide_l = 34;
ease_in = 3.8;
hook_backlash = 1.4;
latch_w = 6.0;
latch_l = 2.5;
latch_depth = 1.0;
floor_t = 1.6;
buckle_fit = 0.2;
// Rotate receiver 90° (0 = slide along bar / +Y, 1 = slide across / +X)
buckle_rot = 0; // [0, 1]

/* [Style / quality] */
corner_r = style_corner_r;
edge_chamfer = style_edge_chamfer;
$fn = style_fn;

/* [Part] */
part = "preview"; // [preview, clamp-receiver, clamp-plain, coupon, assembled]

// ---------------------------------------------------------------------------
// Derived
// ---------------------------------------------------------------------------

bore_d = bar_d + bore_clear;
bore_r = bore_d / 2;
outer_r = bore_r + shell;
bolt_x = outer_r + flange_w / 2;
overall_x = 2 * (outer_r + flange_w);

recv_outer_w = buckle_w + 2 * wall_max + buckle_fit;
recv_outer_l = max(buckle_l, guide_l) + wall_max;
ch_h_nom = buckle_h + buckle_fit;
roof_t = max(roof_top - ch_h_nom, 1.2);
recv_h = floor_t + ch_h_nom + roof_t;

// Receiver footprint on the top pad after buckle_rot. Half_y must cover
// the FULL span so nothing cantilevers past the split or the pad face.
pad_margin = 1.0;
recv_span_y = (buckle_rot == 0) ? recv_outer_l : recv_outer_w;
recv_span_x = (buckle_rot == 0) ? recv_outer_w : recv_outer_l;
half_y = max(outer_r, recv_span_y + 2 * pad_margin);
// Flanges already set overall_x; assert the pad is wide enough in X too.
assert(overall_x >= recv_span_x + 2,
       "clamp overall_x too narrow for the receiver — widen flange_w");

assert(shell >= 1.2, "shell must be >= 1.2 mm");
assert(floor_t >= latch_depth + 0.4, "floor must out-depth the latch recess");
assert(bore_clear >= 0 && bore_clear <= 1.0, "bore_clear out of sane range");
assert(buckle_fit >= 0 && buckle_fit <= 1.0, "buckle_fit out of sane range");
assert(buckle_w > guide_w + 2, "buckle_w must clear the centre guide");
assert(roof_overhang > 0 && roof_overhang < buckle_w / 4, "roof_overhang");
assert(bar_d > 10 && bar_d < 50, "bar_d out of ISO flat-bar range");

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
                translate([0, half_y / 2 - socket_h / 2 + 0.01, 0])
                    rotate([90, 0, 0])
                        cylinder(d = socket_od, h = socket_h + 0.02,
                                 center = true);
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Buckle receiver
// ---------------------------------------------------------------------------

// Roof lips are a flat 3 mm shelf — under printcheck's 5 mm bridge budget,
// so they print without supports (the brief's bridge-free choice with the
// slot facing up). Keep the cut a clean cube; no 0.01-sliver hulls.
module buckle_receiver() {
    ch_w = buckle_w + buckle_fit;
    ch_h = buckle_h + buckle_fit;

    difference() {
        translate([-recv_outer_w / 2, 0, 0])
            cube([recv_outer_w, recv_outer_l, recv_h]);

        // Main channel above the floor
        translate([-ch_w / 2, -0.01, floor_t])
            cube([ch_w, buckle_l + 0.01, ch_h + 0.01]);

        // Finger slots under the roof lips (bridge = roof_overhang <= 5)
        for (sx = [-1, 1]) {
            translate([
                sx * (ch_w / 2 - roof_overhang) - (sx < 0 ? roof_overhang : 0),
                ease_in,   // leave the entry lip open over ease_in
                floor_t + ch_h
            ])
                cube([roof_overhang,
                      buckle_l - hook_backlash - ease_in + 0.01,
                      roof_t + 0.02]);
        }

        // Entry ease-in: open the first ease_in mm of each lip fully
        for (sx = [-1, 1]) {
            translate([
                sx * (ch_w / 2 - roof_overhang) - (sx < 0 ? roof_overhang : 0),
                -0.01,
                floor_t + ch_h
            ])
                cube([roof_overhang, ease_in + 0.02, roof_t + 0.02]);
        }

        // Latch catch recess in the floor
        translate([-latch_w / 2,
                   buckle_l - hook_backlash - latch_l,
                   floor_t - latch_depth])
            cube([latch_w, latch_l, latch_depth + 0.01]);

        // Thumb-access window through the roof
        translate([-latch_w / 2 - 1,
                   buckle_l - hook_backlash - latch_l - 1,
                   floor_t + ch_h])
            cube([latch_w + 2, latch_l + 4, roof_t + 0.02]);
    }

    // Centre guide ridge on the channel floor
    translate([-guide_w / 2, 0, floor_t])
        cube([guide_w, min(guide_l, recv_outer_l - 0.2), guide_h]);
}

// Centre the receiver on the top pad. half_y / overall_x are sized so the
// rotated footprint stays inside the pad (no cantilever).
module receiver_on_top() {
    bury = 0.2;
    translate([0, half_y / 2, clamp_w - bury])
        rotate([0, 0, buckle_rot * 90])
            translate([0, -recv_outer_l / 2, 0])
                buckle_receiver();
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
    }
}

module part_clamp_plain() {
    difference() {
        clamp_half_body();
        bolt_features(nut_side = true);
    }
}

// Fit coupon — one base plate, vertical bore slice, three channel strips.
// Strips use the same 45° lip so they stay support-free and one body.
module part_coupon() {
    bore_h = 8;
    fits = [0.0, 0.2, 0.4];
    strip_gap = 3;
    oy = 14;
    ox = recv_outer_w;
    base_t = 1.6;
    bury = 0.3;

    bore_x = 2 * outer_r;
    bore_y = outer_r + 1;
    y0 = bore_y + 4;
    base_y1 = y0 + 3 * (oy + strip_gap) - strip_gap + 2;
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

        // Channel strips — open trough with 45° lips, no floating chips
        for (i = [0 : len(fits) - 1]) {
            f = fits[i];
            ch_w = buckle_w + f;
            ch_h = buckle_h + f;
            translate([-ox / 2,
                       y0 + i * (oy + strip_gap),
                       base_t - bury]) {
                difference() {
                    cube([ox, oy, floor_t + ch_h + 1.2]);
                    // Channel
                    translate([(ox - ch_w) / 2, -0.01, floor_t])
                        cube([ch_w, oy + 0.02, ch_h + 1.3]);
                    // 45° lip chamfers (same idea as the production receiver)
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
            cylinder(d = bar_d, h = clamp_w + 30, center = true);
}

module part_preview() {
    translate([-overall_x / 2 - 8, 0, 0])
        part_clamp_receiver();
    translate([overall_x / 2 + 8, 0, 0])
        part_clamp_plain();
}

if (part == "clamp-receiver")
    part_clamp_receiver();
else if (part == "clamp-plain")
    part_clamp_plain();
else if (part == "coupon")
    part_coupon();
else if (part == "assembled")
    part_assembled();
else
    part_preview();
