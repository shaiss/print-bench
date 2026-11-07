// auxetic-tile — re-entrant honeycomb stretch tile (ν < 0 demonstrator).
// Flat-printed lattice that gets wider when pulled: inward-pointing ribs
// rotate outward under tension (Lakes, Science 235, 1987). Embossed
// callout states the mechanism and the printability bound — not a promised
// Poisson ratio (docs/metamaterials-4d.md §1). Brief: issue #977.
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.

use <printability.scad>       // repo FDM helpers (OPENSCADPATH="$PWD/lib:$PWD")

/* [Lattice] */
// Re-entrant angle of the slanted rib from vertical (deg) — hard-capped at 45
reentrant_angle = 30;
// Slanted rib length / characteristic cell edge (mm)
cell_edge = 8;
// Horizontal rib length (mm) — longer than cell_edge so the neck stays open
// at the 30° default; neck guard (not the 45° printability max) caps θ at
// the shipped defaults — see NOTES.md
cell_horiz = 10;
// Rib width in-plane (mm) — repo wall floor 1.2; never below 0.8
rib_width = 1.2;
// Rib depth out-of-plane / print height (mm)
rib_depth = 8;

/* [Tile footprint] */
// Overall tile width (mm)
tile_w = 120;
// Overall tile depth (mm)
tile_d = 70;
// Solid outer-frame width (mm)
border = 6;
// Width of the emboss callout strip along +X (mm) — stays solid
callout_w = 26;
// Width of the conventional-honeycomb contrast band along −X (mm)
// Sized for one outward-neck (θ negated) column at the defaults
contrast_w = 22;
// Divider wall between contrast and auxetic bands (mm)
divider = 3;

/* [Coupon] */
// Cells across the coupon strip (hand-stretch demonstrator)
coupon_cells_x = 3;
// Cells along the coupon strip
coupon_cells_y = 2;
// Solid grip-tab length beyond the lattice (mm), each end
grip_tab = 16;
// Grip-tab depth as a fraction of lattice body depth (finger pad, not a rail)
grip_tab_d_frac = 0.72;

/* [Emboss] */
// Raised text height above the callout strip (mm) — two 0.2 mm layers
emboss_h = 0.4;
// How deep the text block roots into the strip (mm) — kills coplanar faces
text_sink = 0.2;

/* [Print] */
// 45° chamfer on bed-contact border edges (mm, 0 to disable)
bottom_chamfer = 0.6;

/* [Quality] */
// Facets on border rounds. Iterating: 24. Production: 48+.
$fn = 48;

part = "tile";

// ---------------------------------------------------------------------------
// Derived cell pitches (Yang-style re-entrant honeycomb; θ from vertical)
//   pitch_x = 2·l_horiz − 2·cell_edge·sin(θ)
//   pitch_y = 2·cell_edge·cos(θ)
// Brick (auxetic) rows sit on pitch_y/2 so neighbouring cells share slanted
// edges; an unshifted column (contrast) keeps full pitch_y so stacked cells
// share the horizontal ribs instead.
// ---------------------------------------------------------------------------
function _s(th) = sin(th);
function _c(th) = cos(th);
function pitch_x(th) = 2 * cell_horiz - 2 * cell_edge * _s(th);
function pitch_y(th) = 2 * cell_edge * _c(th);
function neck_w(th) = cell_horiz - 2 * cell_edge * _s(th);
function row_pitch(th, brick = true) = brick ? pitch_y(th) / 2 : pitch_y(th);

// Six centerline vertices of one re-entrant cell, origin at cell centre.
// Positive θ → necks indent (auxetic). Negative θ → necks push out
// (conventional / positive-Poisson contrast).
function cell_verts(th) =
    let (s = _s(th), c = _c(th),
         xo = cell_horiz / 2,
         xn = cell_horiz / 2 - cell_edge * s,
         y  = cell_edge * c)
    [
        [-xo, -y],   // 0 bottom-left outer
        [ xo, -y],   // 1 bottom-right outer
        [ xn,  0],   // 2 right neck
        [ xo,  y],   // 3 top-right outer
        [-xo,  y],   // 4 top-left outer
        [-xn,  0]    // 5 left neck
    ];

function cell_half_extent_x(th) =
    max(cell_horiz / 2, abs(cell_horiz / 2 - cell_edge * _s(th)));

function lattice_span_x(nx, ny, th, brick = true) =
    let (px = pitch_x(th))
    (nx - 1) * px + (brick && ny > 1 ? px / 2 : 0)
        + 2 * cell_half_extent_x(th);

function lattice_span_y(ny, th, brick = true) =
    (ny - 1) * row_pitch(th, brick) + 2 * cell_edge * abs(_c(th));

// Soft max θ the neck stays ≥ rib at the shipped cell_horiz/cell_edge.
function neck_theta_max() =
    asin(max(0, min(1, (cell_horiz - rib_width) / (2 * cell_edge))));

// ---------------------------------------------------------------------------
// Guards — fail the render, not the reviewer
// ---------------------------------------------------------------------------
module lattice_guards(th) {
    // θ = 0 collapses the re-entrant indent (xn == xo → rectangle) while the
    // emboss still claims auxetic — refuse it for this demonstrator (T3 / Copilot).
    assert(reentrant_angle > 0 && reentrant_angle <= 45,
        str("reentrant_angle ", reentrant_angle,
            "° outside (0, 45] — must be re-entrant; docs/metamaterials-4d.md §1"));
    assert(abs(th) <= 45,
        str("|θ|=", abs(th), "° exceeds the 45° from-vertical printability max"));
    assert(rib_width >= 0.8,
        str("rib_width ", rib_width, " mm under the 0.8 mm absolute floor"));
    assert(cell_edge >= 2 * rib_width,
        "cell_edge too small for the rib width — lattice collapses");
    assert(neck_w(th) + 1e-6 >= rib_width,
        str("cell neck width ", neck_w(th),
            " mm < rib_width at θ=", th,
            "° — raise cell_horiz or lower the angle"));
    assert(pitch_x(th) > 2 * rib_width && pitch_y(th) > 2 * rib_width,
        "cell pitch under 2×rib — voids merge and ribs vanish");
    assert(rib_depth >= 2,
        "rib_depth under 2 mm — nothing left to grip");
}

// ---------------------------------------------------------------------------
// Lattice as solid-minus-voids.
// Brick rows use half-height spacing so slanted edges are shared. The SOLID
// is offset(union(cell polygons), +rib/2) — not a bounding rectangle — so
// material outside the tiling cannot form thick bypass webs; after punching
// inset voids the leftover is ~rib_width ribs. Tile still subtracts the same
// voids from its framed plate (frame = look-at demo).
// ---------------------------------------------------------------------------
module cell_poly_2d(th) {
    polygon(cell_verts(th));
}

module cell_void_2d(th) {
    offset(delta = -rib_width / 2)
        cell_poly_2d(th);
}

module lattice_cells_2d(nx, ny, th, brick = true) {
    px = pitch_x(th);
    rp = row_pitch(th, brick);
    for (j = [0 : ny - 1]) {
        row_shift = brick ? (j % 2) * px / 2 : 0;
        for (i = [0 : nx - 1])
            translate([i * px + row_shift, j * rp])
                cell_poly_2d(th);
    }
}

module lattice_voids_2d(nx, ny, th, brick = true) {
    px = pitch_x(th);
    rp = row_pitch(th, brick);
    for (j = [0 : ny - 1]) {
        row_shift = brick ? (j % 2) * px / 2 : 0;
        for (i = [0 : nx - 1])
            translate([i * px + row_shift, j * rp])
                cell_void_2d(th);
    }
}

// Rib-network plate: thicken the tiled cell union, then voids punch the cells.
module lattice_network_2d(nx, ny, th, brick = true) {
    difference() {
        offset(delta = rib_width / 2)
            lattice_cells_2d(nx, ny, th, brick);
        lattice_voids_2d(nx, ny, th, brick);
    }
}

module lattice_voids_3d(nx, ny, th, brick = true) {
    translate([0, 0, -1])
        linear_extrude(rib_depth + 2, convexity = 8)
            lattice_voids_2d(nx, ny, th, brick);
}

module lattice_network_3d(nx, ny, th, brick = true) {
    linear_extrude(rib_depth, convexity = 8)
        lattice_network_2d(nx, ny, th, brick);
}

// ---------------------------------------------------------------------------
// Embossed callout — qualitative mechanism + bound (NOT a ν value).
// Numbers are str()'d from the same parameters that build the mesh, so the
// strip cannot state a value the lattice didn't use (spring-rate-ladder N4).
// ---------------------------------------------------------------------------
module callout_text() {
    lines = [
        "AUXETIC",
        str("th=", reentrant_angle, " deg"),
        str("edge ", cell_edge, "  rib ", rib_width),
        "pull -> wider",
        "nu < 0  (mech.)",
        "th max 45 deg"
    ];
    sizes = [4.2, 3.4, 3.0, 3.0, 3.0, 2.8];
    bases = [18, 11, 5, -1, -7, -13];
    translate([0, 0, rib_depth - text_sink])
        for (i = [0 : len(lines) - 1])
            translate([0, bases[i]])
                linear_extrude(emboss_h + text_sink)
                    text(lines[i], size = sizes[i], halign = "center",
                         valign = "center",
                         font = "Liberation Sans:style=Bold");
}

// ---------------------------------------------------------------------------
// Tile — one solid plate, voids punched for auxetic + contrast bands
// Frame stays (look-at demo); the band itself is a tessellating rib network.
// ---------------------------------------------------------------------------
module tile_part() {
    lattice_guards(reentrant_angle);

    // Layout: [border][contrast band][divider][auxetic band][callout]
    ax_band_w = tile_w - contrast_w - divider - callout_w - border;
    band_d = tile_d - 2 * border;
    assert(ax_band_w > 2 * pitch_x(reentrant_angle),
        "tile footprint too narrow for even two auxetic cells — grow tile_w");
    assert(band_d > pitch_y(reentrant_angle),
        "tile footprint too shallow for one auxetic row — grow tile_d");

    ax_rp = row_pitch(reentrant_angle, true);
    ax_nx = max(2, floor((ax_band_w - 2 * cell_half_extent_x(reentrant_angle))
                         / pitch_x(reentrant_angle)) + 1);
    ax_ny = max(2, floor((band_d - 2 * cell_edge * abs(_c(reentrant_angle)))
                         / ax_rp) + 1);

    cx_th = -reentrant_angle;
    cx_rp = row_pitch(cx_th, false);
    cx_nx = 1;
    // Contrast column keeps full-pitch stacking; fit as many as the band holds.
    cx_ny = max(1, floor((band_d - 2 * cell_edge * abs(_c(cx_th)))
                         / cx_rp) + 1);

    ax_span_x = lattice_span_x(ax_nx, ax_ny, reentrant_angle, true);
    cx_span_x = lattice_span_x(cx_nx, cx_ny, cx_th, false);
    assert(cx_span_x <= contrast_w - 1,
        str("contrast cell span ", cx_span_x,
            " exceeds contrast_w ", contrast_w, " — widen the strip"));

    ax_origin_x = -tile_w / 2 + border + contrast_w + divider + ax_band_w / 2
                - ((ax_nx - 1) * pitch_x(reentrant_angle)
                   + (ax_ny > 1 ? pitch_x(reentrant_angle) / 2 : 0)) / 2;
    ax_origin_y = -tile_d / 2 + border + band_d / 2
                - ((ax_ny - 1) * ax_rp) / 2;
    cx_origin_x = -tile_w / 2 + border + contrast_w / 2;
    cx_origin_y = -tile_d / 2 + border + band_d / 2
                - ((cx_ny - 1) * cx_rp) / 2;

    union() {
        difference() {
            translate([-tile_w / 2, -tile_d / 2, 0])
                rounded_box([tile_w, tile_d, rib_depth], r = 3,
                            bottom_chamfer = bottom_chamfer);
            // Auxetic voids — brick / half-height tessellation
            translate([ax_origin_x, ax_origin_y, 0])
                lattice_voids_3d(ax_nx, ax_ny, reentrant_angle, true);
            // Conventional contrast voids (θ negated, full-pitch, no brick)
            translate([cx_origin_x, cx_origin_y, 0])
                lattice_voids_3d(cx_nx, cx_ny, cx_th, false);
        }
        translate([tile_w / 2 - callout_w / 2, 0, 0])
            callout_text();
    }

    echo(str("auxetic-tile emboss: th=", reentrant_angle,
             " deg (max 45); edge=", cell_edge,
             " horiz=", cell_horiz,
             " rib=", rib_width,
             " depth=", rib_depth,
             " footprint=", tile_w, "x", tile_d,
             " cells=", ax_nx, "x", ax_ny,
             " pitch=", pitch_x(reentrant_angle), "x", pitch_y(reentrant_angle),
             " neck=", neck_w(reentrant_angle),
             " neck_th_max~", neck_theta_max(),
             " ; mechanism: nu<0 from re-entrant rib rotation; no promised nu"));
}

// ---------------------------------------------------------------------------
// Coupon — free-sided rib network with grip tabs on the ±X ends only.
// Built as ONE 2D union (network + overlapping tab pads) then a single
// extrude — a 3D union of an extruded network with separate tab solids
// left non-manifold edges under Manifold (CI gate). Tab comfort = rounded
// finger pads (no separate ridge shells).
// ---------------------------------------------------------------------------
module grip_tab_2d(w, d) {
    r = min(2.5, w * 0.28);
    offset(r = r)
        translate([r, r])
            square([max(0.1, w - 2 * r), max(0.1, d - 2 * r)]);
}

module coupon_part() {
    lattice_guards(reentrant_angle);
    nx = coupon_cells_x;
    ny = coupon_cells_y;
    span_x = lattice_span_x(nx, ny, reentrant_angle, true);
    span_y = lattice_span_y(ny, reentrant_angle, true);
    // Tab depth tracks the lattice span so the pad sits on the end ribs.
    tab_d = max(span_y * grip_tab_d_frac, 2 * cell_edge * abs(_c(reentrant_angle)));
    tab_ov = max(2.0, 2 * rib_width);
    total_w = span_x + rib_width + 2 * grip_tab;

    origin_x = -((nx - 1) * pitch_x(reentrant_angle)
                 + (ny > 1 ? pitch_x(reentrant_angle) / 2 : 0)) / 2;
    origin_y = -((ny - 1) * row_pitch(reentrant_angle, true)) / 2;

    linear_extrude(rib_depth, convexity = 8)
        union() {
            translate([origin_x, origin_y])
                lattice_network_2d(nx, ny, reentrant_angle, true);
            // Left / right pads — overlap the network in 2D so the extrude
            // is a single body with no shell-kiss at the weld.
            translate([-total_w / 2, -tab_d / 2])
                grip_tab_2d(grip_tab + tab_ov, tab_d);
            translate([total_w / 2 - grip_tab - tab_ov, -tab_d / 2])
                grip_tab_2d(grip_tab + tab_ov, tab_d);
        }

    echo(str("auxetic-tile coupon: cells=", nx, "x", ny,
             " th=", reentrant_angle, " edge=", cell_edge,
             " rib=", rib_width, " span=", span_x, "x", span_y,
             " tabs=", grip_tab, "x", tab_d));
}

// ---------------------------------------------------------------------------
// Dispatch
// ---------------------------------------------------------------------------
module main() {
    if (part == "tile")
        tile_part();
    else if (part == "coupon")
        coupon_part();
    else
        assert(false, str("unknown part: ", part,
            " (expected tile, coupon)"));
}

main();
