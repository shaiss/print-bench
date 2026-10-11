// hex-bit-rail — bench-top rail that stores 1/4" hex driver bits standing up,
// every one held by a printed hex pocket and presented label-up. The
// engineering is the fit: a hex pocket must register six faces accurately
// enough to grip a hardened steel shank printed against PLA — pure tolerance
// work, tuned on the coupon (PRINT THIS FIRST) and proved by ci.fitchecks.
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.

use <printability.scad>                      // rounded_box
include <styles/workshop-utility/style.scad> // family tokens; $fn set below

/* [Part] */
// What to render: the assembled preview (ghost bits), the two printable
// rails, the boolean fit proofs (ci.fitchecks — never printed), or the
// cutaway section.
part = "assembly"; // [assembly, rail-short, rail-long, fit-bit, fit-bit-ctrl, cutaway]

/* [Bit & pocket — the fit] */
// Hex shank across flats (mm) — 1/4" = 6.35. Caliper two or three of your
// own bits before trusting the coupon; drawers drift.
bit_af = 6.35;
// Hex fit clearance added to the pocket across-flats (mm). Printed hex holes
// come out undersize, so the production default is positive; the coupon
// sweeps pairs either side — set the winner here or with -D.
hex_fit = 0.1;
// Pocket depth, short-bit rail (mm) — seats the shank past the fluted
// driving end without bottoming
pocket_depth_short = 12.0;
// Pocket depth, long-bit rail (mm) — the deeper floor socket for 50/75 mm
// bits
pocket_depth_long = 18.0;
// Ball-detent notch depth from the bit tip (mm, assumed) — the pocket floor
// must land at least detent_clear below it so the rail's grip, not the
// bit's own detent, dominates
detent_depth = 11.5;
// How far past the detent the pocket floor must sit (mm)
detent_clear = 0.5;
// Full length of the bits the short rail holds (mm) — sets the stick-up
bit_len_short = 25;

/* [Rail layout] */
// Pockets per rail
pockets = 12;
// Pocket centre-to-centre spacing (mm)
pitch = 16;
// Margin from each rail end to the outer pocket centres (mm)
end_margin = 4.0;
// Rail width (mm)
rail_w = 40;
// Floor under the pockets (mm) — 3 perimeters at a 0.4 mm nozzle
floor_t = 2.4;

/* [Edges & labels] */
// 45-degree break at each pocket mouth (mm leg) — the one-handed
// insertion aid; style_edge_chamfer keeps the family's chamfer grammar
mouth_break = 0.6;
// Emboss the per-pocket fit value on the front wall (the coupon sets this;
// the production rail carries no text — label bosses are v1.1)
pocket_labels = false;

/* [Quality] */
$fn = style_fn; // 64 — the family's curve resolution

// ---------------------------------------------------------------------------
// Derived
// ---------------------------------------------------------------------------
rail_l = pockets * pitch + 2 * end_margin;          // 200 at the defaults
rail_h_short = pocket_depth_short + floor_t;        // 14.4
rail_h_long = pocket_depth_long + floor_t;          // 20.4
// Per-pocket hex clearance: uniform at the production fit; the coupon
// overrides this list to sweep undersize / nominal / oversize pairs
pocket_fits = [ for (i = [0 : pockets - 1]) hex_fit ];
// Widest pocket the current fit list makes (guards the inter-pocket wall)
af_max = bit_af + max([for (f = pocket_fits) f]);
ac_max = af_max / cos(30);                          // across corners
stickup_short = bit_len_short - pocket_depth_short; // ~13 — the grab

// The variant the current `part` renders (fit proofs ride the short rail)
pocket_depth = part == "rail-long" ? pocket_depth_long : pocket_depth_short;
rail_h = pocket_depth + floor_t;

// Guards: the brief's non-negotiables as render failures, not comments
assert(len(pocket_fits) == pockets, "pocket_fits needs one entry per pocket");
assert(min(pocket_fits) > -0.5 * bit_af, "a pocket fit that negative has no hex left");
assert(pocket_depth_short >= detent_depth + detent_clear,
    "short pocket floor lands above the bit's detent — the bit would hang on its own notch");
assert(stickup_short >= 12 && stickup_short <= 15, str(
    "short-bit stick-up ", stickup_short, " mm is outside the brief's ~13 mm grab"));
assert(rail_l <= 200 && rail_w <= 40, str(
    "footprint ", rail_l, " x ", rail_w, " exceeds the brief's 200 x 40 bench dead-zone"));
assert(pitch - ac_max - 2 * mouth_break >= 2.4, str(
    "only ", pitch - ac_max - 2 * mouth_break, " mm of wall between pockets after the",
    " mouth breaks — under 2.4 mm. Widen pitch or shrink the fit sweep."));
assert((rail_w - af_max) / 2 >= 1.2, str(
    "only ", (rail_w - af_max) / 2, " mm of side wall — under the 1.2 mm floor"));

// ---------------------------------------------------------------------------
// Hexagon helpers — flats normal to Y (corners on X), so across-flats is the
// pocket's Y extent and a measured export can read it straight off the wall
// planes.
// ---------------------------------------------------------------------------
module hex2d(af) {
    r = af / sqrt(3); // circumradius from across-flats
    polygon([for (a = [0 : 5]) r * [cos(60 * a), sin(60 * a)]]);
}

module hex_prism(af, h) {
    linear_extrude(h) hex2d(af);
}

// One pocket void: straight hex bore plus a 45-degree mouth break. The break
// is a hex frustum starting 0.02 inside the bore and reaching af + 2*leg at
// the mouth — the 0.02 inset keeps the two cutters' walls off coplanar
// contact, the same weld rule alcove-rod-socket records for face-touching
// unions. The mouth is at z = rail_h; the bore runs clean through the top
// face so the pocket prints exactly as drawn (no bridge, no support).
module pocket_void(af, depth, h) {
    union() {
        translate([0, 0, h - depth - 0.01]) hex_prism(af, depth + 0.02);
        translate([0, 0, h - mouth_break - 0.5])
            linear_extrude(mouth_break + 0.51,
                           scale = (af + 2 * mouth_break) / (af - 0.02))
                hex2d(af - 0.02);
    }
}

// Raised fit value on the front wall — the coupon's labels. Embedded into
// the wall so the union WELDS: a floating glyph shell is a 0.5 mm part of
// its own (the 21-shell coupon of iteration 1), while a welded one casts
// thickness rays into the solid bulk.
//
// The glyph SHAPES are walls too, and iterations 2–3 measured it: printcheck
// casts a ray inward from sampled surface and a ray across a stroke, a bar's
// height, an inter-glyph gap or a digit's counter all read as wall
// thickness. At size 3.2 the strokes measured 0.2–0.4 mm and 25% of the
// coupon's sampled surface fell under the 0.8 mm floor — a CRITICAL. So
// every such span is driven to ~1 mm: size 6 with spacing 1.2 for the gaps,
// offset(r = 0.25) to fatten strokes and bars to ≈ 1 mm (the coupon widens
// its pitch to 24 so the wider labels clear each other — a "-0.15" label
// this fat needs ≈ 22 mm, more than the production 16). spacing stays above
// the bistable-toggle lesson's tight-kern sliver class even after the
// offset closes 0.5 mm of each gap. The wall is vertical, so the glyphs
// stack like any other layer: no overhang.
module fit_label(v, x) {
    translate([x, -rail_w / 2 + 0.15, floor_t + 1.5])
        rotate([90, 0, 0])
            linear_extrude(0.5)
                offset(r = 0.25)
                    text(str(round(v * 100) / 100), size = 6, halign = "center",
                         spacing = 1.2);
}

// ---------------------------------------------------------------------------
// One printable rail: family-rounded body, pockets up, flat-side-down.
// Every pocket is drawn open-top and prints support-free; the pockets never
// see first-layer squish, which is what makes the hex fit tunable at all.
// ---------------------------------------------------------------------------
module rail(depth) {
    h = depth + floor_t;
    difference() {
        // rounded_box is corner-anchored (spans [0,size] in x/y/z), so shift
        // it y-centred about the pocket axis — pockets and labels are placed
        // at y = 0 / y = -rail_w/2 on that assumption. (Iteration 1 missed
        // this and the pockets opened through the front face.)
        translate([0, -rail_w / 2, 0])
            rounded_box([rail_l, rail_w, h], r = style_corner_r,
                        bottom_chamfer = style_edge_chamfer);
        for (i = [0 : pockets - 1])
            translate([end_margin + pitch * (i + 0.5), 0, 0])
                pocket_void(bit_af + pocket_fits[i], depth, h);
    }
    if (pocket_labels)
        for (i = [0 : pockets - 1])
            fit_label(pocket_fits[i], end_margin + pitch * (i + 0.5));
}

// Assembled preview: the short rail as used, the first three pockets' bits
// seated floor-on (ghost — preview only, never exported). The long rail is
// the same vocabulary at a deeper socket; see part = "rail-long".
module assembly() {
    rail(pocket_depth_short);
    for (i = [0 : 2])
        translate([end_margin + pitch * (i + 0.5), 0, floor_t])
            %hex_prism(bit_af, bit_len_short);
}

// Boolean fit proof (ci.fitchecks): a steel shank of `grow` over nominal,
// seated exactly as the bit seats — bottom on the pocket floor —
// intersected with the production rail solid. At grow = 0 the shank clears
// every pocket face by hex_fit/2, so the intersection must be EMPTY; grown
// 0.4 it must interfere: the negative control proving the check can fail.
module fit_check(grow = 0) {
    intersection() {
        rail(pocket_depth_short);
        translate([end_margin + pitch * 0.5, 0, floor_t])
            hex_prism(bit_af + grow, pocket_depth_short + 20);
    }
}

// Section through the pocket axis: the fit you cannot see from outside.
module cutaway() {
    difference() {
        assembly();
        translate([0, -rail_w, -1]) cube([rail_l, rail_w, 60]);
    }
}

if (part == "rail-short") rail(pocket_depth_short);
else if (part == "rail-long") rail(pocket_depth_long);
else if (part == "fit-bit") fit_check();
else if (part == "fit-bit-ctrl") fit_check(grow = 0.4);
else if (part == "cutaway") cutaway();
else assembly();
