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
// at 30° (and through the 45° printability max); see NOTES.md
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
grip_tab = 14;
// Extra Y padding around the coupon lattice window (mm)
grip_tab_w_extra = 4;

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
// ---------------------------------------------------------------------------
function _s(th) = sin(th);
function _c(th) = cos(th);
function pitch_x(th) = 2 * cell_horiz - 2 * cell_edge * _s(th);
function pitch_y(th) = 2 * cell_edge * _c(th);
function neck_w(th) = cell_horiz - 2 * cell_edge * _s(th);

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

function lattice_span_y(ny, th) =
    (ny - 1) * pitch_y(th) + 2 * cell_edge * abs(_c(th));

// ---------------------------------------------------------------------------
// Guards — fail the render, not the reviewer
// ---------------------------------------------------------------------------
module lattice_guards(th) {
    assert(reentrant_angle >= 0 && reentrant_angle <= 45,
        str("reentrant_angle ", reentrant_angle,
            "° outside [0, 45] — docs/metamaterials-4d.md §1 printability bound"));
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
// Lattice as solid-minus-voids (guarantees one body with the frame)
// Centerline hex inset by rib_width/2 → the cell VOID; ribs are whatever
// solid remains between neighbouring voids.
// ---------------------------------------------------------------------------
module cell_void_2d(th) {
    offset(delta = -rib_width / 2)
        polygon(cell_verts(th));
}

module lattice_voids_2d(nx, ny, th, brick = true) {
    px = pitch_x(th);
    py = pitch_y(th);
    for (j = [0 : ny - 1]) {
        row_shift = brick ? (j % 2) * px / 2 : 0;
        for (i = [0 : nx - 1])
            translate([i * px + row_shift, j * py])
                cell_void_2d(th);
    }
}

module lattice_voids_3d(nx, ny, th, brick = true) {
    translate([0, 0, -1])
        linear_extrude(rib_depth + 2, convexity = 8)
            lattice_voids_2d(nx, ny, th, brick);
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

    ax_nx = max(2, floor((ax_band_w - 2 * cell_half_extent_x(reentrant_angle))
                         / pitch_x(reentrant_angle)) + 1);
    ax_ny = max(2, floor((band_d - 2 * cell_edge * abs(_c(reentrant_angle)))
                         / pitch_y(reentrant_angle)) + 1);

    cx_th = -reentrant_angle;
    cx_nx = 1;
    cx_ny = ax_ny;

    ax_span_x = lattice_span_x(ax_nx, ax_ny, reentrant_angle, true);
    cx_span_x = lattice_span_x(cx_nx, cx_ny, cx_th, false);
    assert(cx_span_x <= contrast_w - 1,
        str("contrast cell span ", cx_span_x,
            " exceeds contrast_w ", contrast_w, " — widen the strip"));

    ax_band_xmin = -tile_w / 2 + border + contrast_w + divider;
    ax_origin_x = ax_band_xmin + ax_band_w / 2
                - ((ax_nx - 1) * pitch_x(reentrant_angle)
                   + (ax_ny > 1 ? pitch_x(reentrant_angle) / 2 : 0)) / 2;
    ax_origin_y = -tile_d / 2 + border + band_d / 2
                - ((ax_ny - 1) * pitch_y(reentrant_angle)) / 2;
    cx_origin_x = -tile_w / 2 + border + contrast_w / 2;
    cx_origin_y = ax_origin_y;

    union() {
        difference() {
            translate([-tile_w / 2, -tile_d / 2, 0])
                rounded_box([tile_w, tile_d, rib_depth], r = 3,
                            bottom_chamfer = bottom_chamfer);
            // Auxetic voids
            translate([ax_origin_x, ax_origin_y, 0])
                lattice_voids_3d(ax_nx, ax_ny, reentrant_angle, true);
            // Conventional contrast voids (θ negated, no brick)
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
             " ; mechanism: nu<0 from re-entrant rib rotation; no promised nu"));
}

// ---------------------------------------------------------------------------
// Coupon — solid plate with grip tabs; voids punched for the 3-cell strip
// ---------------------------------------------------------------------------
module coupon_part() {
    lattice_guards(reentrant_angle);
    nx = coupon_cells_x;
    ny = coupon_cells_y;
    span_x = lattice_span_x(nx, ny, reentrant_angle, true);
    span_y = lattice_span_y(ny, reentrant_angle);
    body_d = span_y + 2 * border + grip_tab_w_extra;
    total_w = span_x + 2 * grip_tab;

    origin_x = -((nx - 1) * pitch_x(reentrant_angle)
                 + (ny > 1 ? pitch_x(reentrant_angle) / 2 : 0)) / 2;
    origin_y = -((ny - 1) * pitch_y(reentrant_angle)) / 2;

    difference() {
        translate([-total_w / 2, -body_d / 2, 0])
            rounded_box([total_w, body_d, rib_depth], r = 2,
                        bottom_chamfer = bottom_chamfer);
        translate([origin_x, origin_y, 0])
            lattice_voids_3d(nx, ny, reentrant_angle, true);
    }

    echo(str("auxetic-tile coupon: cells=", nx, "x", ny,
             " th=", reentrant_angle, " edge=", cell_edge,
             " rib=", rib_width, " span=", span_x, "x", span_y));
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
