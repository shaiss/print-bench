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

// ---- Bin solids as single sweeps -------------------------------------
// Every bin surface is a rounded rectangle whose corner arcs share one
// centre (r = gf_top_r - inset), so a whole profile — the boss's three
// stages, the bin body, the cavity + stacking-lip V — is ONE closed
// polyhedron lofted through rings, never a union of stacked hulls and
// extrusions. Stacked pieces that only touch face-to-face (wall on bridge,
// cutter on cutter) are what Manifold exports as edges shared by more than
// two triangles plus zero-area slivers; a single sweep has no such seam.

function gf_cum(v, i) = i == 0 ? 0 : gf_cum(v, i - 1) + v[i - 1];

// Closed loft of rounded rectangles of outer size `size` centred at `c`;
// prof = [[inset, z], ...] bottom to top (z strictly increasing). An inset
// of gf_top_r gives sharp corners (r = 0), collapsed to one vertex each.
module gf_sweep(size, prof, c = [0, 0]) {
    n = max(1, ceil($fn / 4));  // segments per corner arc
    L = len(prof);
    M = 4 * (n + 1);
    cx = size[0] / 2 - gf_top_r;
    cy = size[1] / 2 - gf_top_r;
    sg = [[1, 1], [-1, 1], [-1, -1], [1, -1]];
    sharp = [for (p = prof) gf_top_r - p[0] <= 1e-6];
    cnt = [for (sh = sharp) sh ? 4 : M];
    base = [for (i = [0 : L - 1]) gf_cum(cnt, i)];
    pts = [for (i = [0 : L - 1])
              let(r = gf_top_r - prof[i][0], z = prof[i][1])
              each (sharp[i]
                  ? [for (q = [0 : 3]) [c[0] + sg[q][0] * cx, c[1] + sg[q][1] * cy, z]]
                  : [for (q = [0 : 3], k = [0 : n])
                        let(a = q * 90 + k * 90 / n)
                        [c[0] + sg[q][0] * cx + r * cos(a),
                         c[1] + sg[q][1] * cy + r * sin(a), z]])];
    E = [for (q = [0 : 3], k = [0 : n]) [q, k]];
    function id(i, e) = base[i] + (sharp[i] ? e[0] : e[0] * (n + 1) + e[1]);
    side = [for (i = [0 : L - 2], j = [0 : M - 1])
               let(a0 = id(i, E[j]), a1 = id(i, E[(j + 1) % M]),
                   b0 = id(i + 1, E[j]), b1 = id(i + 1, E[(j + 1) % M]))
               each (a0 == a1 && b0 == b1 ? []
                   : a0 == a1 ? [[a0, b0, b1]]
                   : b0 == b1 ? [[a0, b0, a1]]
                   : [[a0, b0, b1], [a0, b1, a1]])];
    bot = [for (k = [0 : cnt[0] - 1]) base[0] + k];
    top = [for (k = [cnt[L - 1] - 1 : -1 : 0]) base[L - 1] + k];
    polyhedron(points = pts, faces = concat([bot], side, [top]));
}

// One cell's boss: 35.6 (r 0.8) -> 37.2 (r 1.6) -> 41.5 (r 3.75), 4.75
// tall, plus `ov` straight up into the bin body so the joint is a real
// overlap (the outer rings match the body's vertex for vertex).
module gf_boss_cell(c, ov) {
    top = gf_pitch - gf_gap;
    gf_sweep([top, top],
             concat([for (p = gf_boss) [gf_boss[3][0] - p[0], p[1]]],
                    [[0, gf_boss[3][1] + ov]]), c);
}

// Bin base block bosses, one per cell, placed absolutely (no translate:
// the body's and the bosses' shared outer vertices must be bit-identical)
module gf_bosses(grid, ov) {
    for (ix = [0 : grid[0] - 1], iy = [0 : grid[1] - 1])
        gf_boss_cell([(ix - (grid[0] - 1) / 2) * gf_pitch,
                      (iy - (grid[1] - 1) / 2) * gf_pitch], ov);
}

// Stacking lip + cavity profile above z_lip (the bin top): the inner V is
// the socket profile so the next bin's boss drops in and seats on the V
// floor; the 0.3 flat rim replaces the spec's knife edge at inset 0.
// Returned as [inset, z] rings for the cavity sweep in gf_bin.
function gf_lip_prof(z_lip, ov) =
    let(lip_d = 2.6,   // lip depth incl. wall thickness (the V floor ridge)
        v_mid = 1.9)   // V wall inset (lip line: 0.7 out / 1.8 up / 1.9 out)
    [[lip_d, z_lip],
     [v_mid, z_lip + 0.7],
     [v_mid, z_lip + 2.5],
     [0.3, z_lip + gf_lip_h],
     [0.3, z_lip + gf_lip_h + ov]];

// Flat label plate replacing the front lip slope: the slope is capped at
// dy 3.2 over inset 0..1.3 — inside the stacking envelope (a stacked bin's
// boss needs inset >= 1.55 at that height, so stacking is unaffected).
module gf_label(foot) {
    w = 26;
    translate([0, -(foot[1] / 2 - 0.65), 1.5]) cube([w, 1.3, 3.4], center = true);
    if (label_text != "")
        // starts 0.05 inside the face so the text fuses to the bin rather
        // than floating 0.01 off it as a separate shell
        translate([0, -foot[1] / 2 + 0.05, 1.5]) rotate([90, 0, 0])
            linear_extrude(0.31 + 0.05)
                text(label_text, size = 2.6, halign = "center", valign = "center");
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
    // counts must be whole and non-negative: the loops below iterate
    // [1 : div], so a fractional count would draw floor(div) walls while
    // spacing them for div — the guard and the geometry must agree
    assert(is_num(div_x) && div_x >= 0 && div_x == floor(div_x),
           "dividers_x must be a whole number >= 0");
    assert(is_num(div_y) && div_y >= 0 && div_y == floor(div_y),
           "dividers_y must be a whole number >= 0");
    // CLEAR compartment width: each divider consumes `wall` of the span
    assert(div_x == 0 || (in_x - div_x * wall) / (div_x + 1) >= 8,
           "dividers along X would leave compartments under 8 mm clear");
    assert(div_y == 0 || (in_y - div_y * wall) / (div_y + 1) >= 8,
           "dividers along Y would leave compartments under 8 mm clear");
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

// A bin: per-cell bosses + one body sweep (bridge, wall and lip outer face
// in a single loft), minus ONE cavity sweep — the 1U tray's drafted recess
// or the bin's wall interior + support chamfer, continuing into the lip V.
// units is the total height in 7 mm U (3U => bin top at 21).
module gf_bin(grid, units, div_x = 0, div_y = 0) {
    h_top = units * gf_base_h;
    foot = gf_foot(grid);
    ov = 0.1;  // overrun of every joint/cutter past the surface it meets
    tray = h_top == gf_base_h;
    // 1U tray: a recess CUTTER through bosses and bridge together — 36.3
    // opening drafted down to a sharp-cornered 34.0 at recess_floor, so
    // the walls left around it stay >= 1.2 mm at the boss waist; its
    // mouth is the lip's V-floor ridge. Bins: the wall interior up to the
    // support chamfer, which rises 45 deg from the wall's inner face to
    // the V-floor ridge so the inward lip prints support-free.
    cavity = concat(
        tray ? [[gf_top_r, recess_floor]]
             : [[wall, gf_base_h], [wall, h_top - (2.6 - wall) - 0.01]],
        gf_lip_prof(h_top, ov));
    difference() {
        union() {
            gf_bosses(grid, ov);
            gf_sweep(foot, [[0, gf_boss[3][1]], [0, h_top + gf_lip_h]]);
            if (label_tab) translate([0, 0, h_top]) gf_label(foot);
        }
        gf_sweep(foot, cavity);
    }
    // called unconditionally so its count guards also refuse a negative
    // count (its loops draw nothing at 0). Tray dividers live in the
    // recess mouth (36.3, drafted below); bin dividers inside the side
    // walls (foot - 2*wall).
    in = tray ? foot - [2 * 2.6, 2 * 2.6] : foot - [2 * wall, 2 * wall];
    gf_dividers(in, tray ? recess_floor : gf_base_h, h_top, div_x, div_y);
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
