// gridfinity-starter — first-party Gridfinity starter set: a screw-down
// baseplate (3x3 by default) plus the open bins that drop into it
// (1x1x3U, 2x1x3U, and a 1x1x1U low tray).
//
// Gridfinity is an open standard (https://gridfinity.xyz). This is a
// clean-room, numbers-only implementation: no Gridfinity library is
// included; every spec constant below was read from the MIT-licensed
// reference kennetek/gridfinity-rebuilt-openscad and is sourced in
// NOTES.md ("Spec numbers"). Requirements and decisions: see NOTES.md.
// All dimensions in millimeters.

use <printability.scad>                       // screw_hole() for the M4 mounts
include <styles/workshop-utility/style.scad>  // style tokens; $fn from style_fn

/* [Part] */
// "" = assembled preview; else baseplate, bin-1x1, bin-2x1, tray-1x1, coupon
part = "";

/* [Baseplate] */
// Grid cells along X (each cell is 42 mm pitch)
grid_x = 3;
// Grid cells along Y
grid_y = 3;
// Solid border around the grid; carries the M4 corner mounts (mm)
margin = 14;
// Solid floor under the sockets (mm)
plate_floor = 2.0;
// M4 mount centres from the plate edge (mm)
mount_inset = 7;
// Cut the four M4 socket-head corner mounts
mounts = true;

/* [Bins] */
// Bin height in Gridfinity units; 1U = 7 mm including the base block
bin_units = 3;
// Bin wall above the base block (mm). Community bins use 0.95; this design
// keeps the repo FDM floor of 1.2 — the interior just gets smaller, every
// Gridfinity mating surface is outside the wall.
wall = 1.2;
// 1U tray: solid floor under the recess (mm)
recess_floor = 1.2;
// Flat label plate on the front lip slope
label_tab = true;
// Text raised on the label plate ("" = blank plate for a sticker)
label_text = "";
// Interior divider walls along X, evenly spaced across the bin (0 = open)
dividers_x = 0;
// Interior divider walls along Y, evenly spaced across the bin (0 = open)
dividers_y = 0;

/* [Fit] */
// Socket profile offset from the bin boss (mm). 0.1 is the community
// default => 0.25 mm/side clearance at the socket wall, 0.35 at the floor
// edge. Tune per printer with the coupon before printing a full set.
fit = 0.1;

/* [Quality] */
// style_fn = 64 (workshop-utility)
$fn = style_fn;

// ---- Gridfinity spec constants — sources in NOTES.md "Spec numbers" ----
gf_pitch = 42;    // grid pitch
gf_gap = 0.5;     // per-unit-side gap: bin top = n*42 - 0.5
gf_top_r = 3.75;  // corner radius: bin top, bridge and bin wall
// Bin boss profile, [inset from the top extent, height]:
// 45 deg / vertical / 45 deg — bottom face 35.6 square, corner r 0.8
gf_boss = [[0, 0], [0.8, 0.8], [0.8, 2.6], [2.95, 4.75]];
gf_base_h = 7;    // base block height = 1U (4.75 profile + 2.25 bridge)
gf_lip_h = 4.4;   // stacking lip height above the bin wall top
gf_socket_h = 5;  // plate socket depth (4.65 profile + 0.35 clearance)

// Bin footprint for a grid of [nx, ny] cells (mm)
function gf_foot(grid) =
    [grid[0] * gf_pitch - gf_gap, grid[1] * gf_pitch - gf_gap];

// Rounded square, centred, corner radius r. size may be a scalar (square)
// or [x, y] — several profile stages are square by construction.
module rsq2d(size, r) {
    sz = is_num(size) ? [size, size] : size;
    offset(r) square([sz[0] - 2 * r, sz[1] - 2 * r], center = true);
}

// Thin plate of a rounded square at height z, for hull lofts
module rsq_plate(size, r, z) {
    translate([0, 0, z]) linear_extrude(0.01) rsq2d(size, r);
}

// One cell's boss: 35.6 (r 0.8) -> 37.2 (r 1.6) -> 41.5 (r 3.75), 4.75 tall
module gf_boss_cell() {
    top = gf_pitch - gf_gap;
    lo = gf_boss[1][0];   // 0.8 — lower chamfer run and rise
    mid_h = gf_boss[2][1];  // 2.6 — top of the vertical section
    hi = gf_boss[3][0];   // 2.95 — total horizontal run
    hi_h = gf_boss[3][1]; // 4.75 — profile height
    mid = top - 2 * (hi - lo);  // 37.2 at the vertical section
    hull() {
        rsq_plate(top - 2 * hi, gf_top_r - hi, 0);
        rsq_plate(mid, gf_top_r - hi + lo, lo);
    }
    translate([0, 0, lo]) linear_extrude(mid_h - lo) rsq2d(mid, gf_top_r - hi + lo);
    hull() {
        rsq_plate(mid, gf_top_r - hi + lo, mid_h);
        rsq_plate(top, gf_top_r, hi_h);
    }
}

// Bin base block: per-cell bosses + one merged bridge up to z = 7 (1U)
module gf_base(grid) {
    for (ix = [0 : grid[0] - 1], iy = [0 : grid[1] - 1])
        translate([(ix - (grid[0] - 1) / 2) * gf_pitch,
                   (iy - (grid[1] - 1) / 2) * gf_pitch, 0])
            gf_boss_cell();
    translate([0, 0, gf_boss[3][1]])
        linear_extrude(gf_base_h - gf_boss[3][1]) rsq2d(gf_foot(grid), gf_top_r);
}

// Bin wall from the bridge top (z = 7) to the bin top
module gf_wall(grid, h_top) {
    foot = gf_foot(grid);
    translate([0, 0, gf_base_h]) linear_extrude(h_top - gf_base_h)
        difference() {
            rsq2d(foot, gf_top_r);
            rsq2d(foot - [2 * wall, 2 * wall], gf_top_r - wall);
        }
}

// Stacking lip on the bin top: outer face flush with the wall, inner V is
// the socket profile so the next bin's boss drops in and seats on the V
// floor. Below the V floor the material chamfers back to the wall at 45
// deg so the inward lip prints support-free (opening-down orientation).
module gf_lip(grid, h_top) {
    foot = gf_foot(grid);
    lip_d = 2.6;  // lip depth incl. wall thickness
    v_mid = 1.9;  // V wall inset (lip line: 0.7 out / 1.8 up / 1.9 out)
    translate([0, 0, h_top]) difference() {
        union() {
            translate([0, 0, -(lip_d - wall)]) linear_extrude((lip_d - wall) + gf_lip_h)
                rsq2d(foot, gf_top_r);
            if (label_tab) gf_label(foot);
        }
        union() {
            // support chamfer: wall inner face up to the V floor opening
            hull() {
                rsq_plate(foot - [2 * wall, 2 * wall], gf_top_r - wall,
                          -(lip_d - wall) - 0.01);
                rsq_plate(foot - [2 * lip_d, 2 * lip_d], gf_top_r - lip_d, 0);
            }
            // V lower chamfer
            hull() {
                rsq_plate(foot - [2 * lip_d, 2 * lip_d], gf_top_r - lip_d, -0.01);
                rsq_plate(foot - [2 * v_mid, 2 * v_mid], gf_top_r - v_mid, 0.7);
            }
            // V vertical band
            translate([0, 0, 0.7]) linear_extrude(1.8)
                rsq2d(foot - [2 * v_mid, 2 * v_mid], gf_top_r - v_mid);
            // top slope back to a 0.3 flat rim (spec: knife edge at inset 0)
            hull() {
                rsq_plate(foot - [2 * v_mid, 2 * v_mid], gf_top_r - v_mid, 2.5);
                rsq_plate(foot - [0.6, 0.6], gf_top_r - 0.3, gf_lip_h);
            }
        }
    }
}

// Flat label plate replacing the front lip slope: the slope is capped at
// dy 3.2 over inset 0..1.3 — inside the stacking envelope (a stacked bin's
// boss needs inset >= 1.55 at that height, so stacking is unaffected).
module gf_label(foot) {
    w = 26;
    translate([0, -(foot[1] / 2 - 0.65), 1.5]) cube([w, 1.3, 3.4], center = true);
    if (label_text != "")
        translate([0, -foot[1] / 2 - 0.01, 1.5]) rotate([90, 0, 0])
            linear_extrude(0.31)
                text(label_text, size = 2.6, halign = "center", valign = "center");
}

// 1U tray recess CUTTER (differenced in gf_bin): 36.3 opening drafted down
// to a 1.2 floor so the walls left around it stay >= 1.2 mm at the boss
// waist. Called as a solid it buries harmlessly inside the base block and
// ships a tray that holds nothing — the cavity measurement in NOTES.md
// "Gate evidence" is the proof it actually cuts.
module gf_tray_recess(grid) {
    foot = gf_foot(grid);
    open = foot - [2 * 2.6, 2 * 2.6];
    hull() {
        rsq_plate(open, gf_top_r - 2.6, gf_base_h - 0.01);
        rsq_plate(open - [2.3, 2.3], gf_top_r - 2.6 - 1.15, recess_floor);
    }
}

// Interior divider walls: wall-thick slabs evenly spaced across the bin
// interior (in = usable width per axis) from the interior floor to the bin
// top (flush with the side-wall tops). Even spacing puts the first divider
// of a multi-cell bin exactly on the cell boundary — pitch-aligned with
// every community bin — while higher counts subdivide cells for small
// parts. Ends and floor are buried into the neighbouring solid: a slab
// that merely touches the walls/bridge face-to-face unions along coplanar
// faces and exports zero-area triangles. Burial depths stay inside the
// tightest outer boundary along the slab's full height (the 1U tray's
// boss lower chamfer, 35.6 + 2z, at its buried foot).
module gf_dividers(in, z0, h_top, div_x, div_y) {
    in_x = in[0];
    in_y = in[1];
    bury_z = 0.4;
    bury_end = 0.3;
    assert(div_x == 0 || in_x / (div_x + 1) >= 8,
           "dividers along X would leave compartments under 8 mm");
    assert(div_y == 0 || in_y / (div_y + 1) >= 8,
           "dividers along Y would leave compartments under 8 mm");
    // guarded loops: an unguarded [1:0] range renders empty but warns
    if (div_x > 0)
        for (i = [1 : div_x])
            translate([-in_x / 2 + i * in_x / (div_x + 1) - wall / 2,
                       -in_y / 2 - bury_end / 2, z0 - bury_z])
                cube([wall, in_y + bury_end, h_top - z0 + bury_z]);
    if (div_y > 0)
        for (j = [1 : div_y])
            translate([-in_x / 2 - bury_end / 2,
                       -in_y / 2 + j * in_y / (div_y + 1) - wall / 2, z0 - bury_z])
                cube([in_x + bury_end, wall, h_top - z0 + bury_z]);
}

// A bin: base block + wall + stacking lip, with the 1U tray's recess cut
// from the base block and optional interior dividers. units is the total
// height in 7 mm U (3U => bin top at 21).
module gf_bin(grid, units, div_x = 0, div_y = 0) {
    h_top = units * gf_base_h;
    if (h_top == gf_base_h)
        // 1U tray: the recess is a CUTTER into the base block — cut bosses
        // and bridge together, leaving the z < recess_floor plate, the
        // boss-profile outer shell (seating + socket faces intact) and a
        // drafted wall >= 1.2 mm at the boss waist.
        difference() {
            gf_base(grid);
            gf_tray_recess(grid);
        }
    else {
        gf_base(grid);
        gf_wall(grid, h_top);
    }
    if (div_x > 0 || div_y > 0) {
        // tray dividers live in the recess mouth (36.3, drafted below);
        // bin dividers inside the side walls (foot - 2*wall)
        foot = gf_foot(grid);
        in = h_top == gf_base_h ? foot - [2 * 2.6, 2 * 2.6]
                                : foot - [2 * wall, 2 * wall];
        gf_dividers(in, h_top == gf_base_h ? recess_floor : gf_base_h,
                    h_top, div_x, div_y);
    }
    gf_lip(grid, h_top);
}

// Plate socket cutter, z = 0 at the socket floor: the bin boss grown
// +0.5 mm total at the wall and lip, +0.7 at the floor edge (fit = 0.1).
module gf_socket() {
    cell = gf_pitch;
    p1 = gf_boss[1][0] - fit;    // 0.7 — lower chamfer top
    p2 = gf_boss[2][1] - fit;    // 2.5 — vertical band top
    p3x = gf_boss[3][0] - fit;   // 2.85 — floor edge inset
    p3y = gf_boss[3][1] - fit;   // 4.65 — profile top
    wall_in = gf_boss[3][0] - gf_boss[1][0];  // 2.15 — wall inset (fit-free)
    floor_e = cell - 2 * p3x;    // 36.3 floor-edge opening
    wall_e = cell - 2 * wall_in; // 37.7 at the vertical section
    top_e = cell;                // 42.0 at the lip
    hull() {
        rsq_plate(floor_e, style_corner_r - p3x, 0);
        rsq_plate(wall_e, style_corner_r - wall_in, p1);
    }
    translate([0, 0, p1]) linear_extrude(p2 - p1)
        rsq2d(wall_e, style_corner_r - wall_in);
    hull() {
        rsq_plate(wall_e, style_corner_r - wall_in, p2);
        rsq_plate(top_e, style_corner_r, p3y);
    }
    translate([0, 0, p3y]) linear_extrude(gf_socket_h - p3y)
        rsq2d(top_e, style_corner_r);
}

// Baseplate: solid slab (grid + margin) with one socket per cell and four
// M4 socket-head corner mounts in the margin.
module gf_plate(grid, plate_margin, floor_t) {
    // Adjacent socket mouths (42.0 at 42 pitch) leave zero web, so the
    // neighbouring cutters touch along a line and CGAL's boolean emits
    // coarse 45-degree crease strips between the funnels. At the style's
    // own fn=64 (and still at 128 on a 3x3) those strips out-share the
    // drawn arcs and stylelift reads the plate's dominant curve band as
    // fn 8 — below the style's floor of 44. Measured matrix (dominant
    // implied_fn by grid x $fn): 1x1 tracks $fn exactly at 64/128/256, so
    // the drawn arcs are fine; 3x3 reads 8 at both 64 and 128 and only
    // passes at 256, where the whole part — slab, mounts and sockets — is
    // drawn fine enough for the arcs to dominate. The bump therefore sits
    // here, not in gf_socket: the whole plate part draws at 4x style_fn.
    // Every dimension is unchanged; only the sampling moves.
    $fn = 4 * style_fn;
    X = grid[0] * gf_pitch + 2 * plate_margin;
    Y = grid[1] * gf_pitch + 2 * plate_margin;
    H = floor_t + gf_socket_h;
    difference() {
        linear_extrude(H) rsq2d([X, Y], style_corner_r);
        for (ix = [0 : grid[0] - 1], iy = [0 : grid[1] - 1])
            translate([(ix - (grid[0] - 1) / 2) * gf_pitch,
                       (iy - (grid[1] - 1) / 2) * gf_pitch, floor_t])
                gf_socket();
        if (mounts)
            for (sx = [-1, 1], sy = [-1, 1])
                translate([sx * (X / 2 - mount_inset), sy * (Y / 2 - mount_inset), 0])
                    screw_hole("M4", l = H, head = "socket");
    }
}

// Flip a part so its print orientation is bed-down (bins opening-down,
// plate grid-down) — the exported STL is what CI slices.
module print_orient(h) {
    translate([0, 0, h]) rotate([180, 0, 0]) children();
}

module main() {
    if (part == "baseplate")
        print_orient(plate_floor + gf_socket_h)
            gf_plate([grid_x, grid_y], margin, plate_floor);
    else if (part == "bin-1x1")
        print_orient(bin_units * gf_base_h + gf_lip_h)
            gf_bin([1, 1], bin_units, dividers_x, dividers_y);
    else if (part == "bin-2x1")
        print_orient(bin_units * gf_base_h + gf_lip_h)
            gf_bin([2, 1], bin_units, dividers_x, dividers_y);
    else if (part == "bin-2x1-div")
        // gated proof of the divider option (one wall, on the cell boundary)
        print_orient(bin_units * gf_base_h + gf_lip_h)
            gf_bin([2, 1], bin_units, 1, 0);
    else if (part == "tray-1x1")
        print_orient(gf_base_h + gf_lip_h)
            gf_bin([1, 1], 1, dividers_x, dividers_y);
    else if (part == "coupon") {
        // fit proof: one socket + one 1x1 bin, production fit, print-oriented
        translate([-52.75, 0, 0]) print_orient(plate_floor + gf_socket_h)
            gf_plate([1, 1], 8, plate_floor);
        print_orient(gf_base_h + gf_lip_h) gf_bin([1, 1], 1);
    } else {
        // assembled preview — a preview, never the sliceable deliverable
        gf_plate([grid_x, grid_y], margin, plate_floor);
        place = [[0.5, 0, [2, 1], bin_units],   // 2x1 bin, bottom row
                 [2, 0, [1, 1], bin_units],     // 1x1 bin
                 [0, 2, [1, 1], 1],             // tray
                 [2, 2, [1, 1], 1]];            // tray
        for (p = place)
            translate([(p[0] - (grid_x - 1) / 2) * gf_pitch,
                       (p[1] - (grid_y - 1) / 2) * gf_pitch, plate_floor])
                gf_bin(p[2], p[3]);
    }
}

main();
