// battery-caddy — wall-mounted AA/AAA cell caddy with printed spring fingers.
// Vertical lanes store a gravity-fed column of cells; the bottom cell sits in
// the throat of two compliant blades printed as part of the lane, and pulls
// out forward against a tuned low release force. Requirements and decisions:
// see NOTES.md next to this file. All dimensions in millimeters.
//
// Print orientation: back flat on the bed (the dispatch below rotates the
// body), lanes along the printer's X. The spring blades then print as
// constant-cross-section vertical fins standing on the lane floor — the blade
// profile, the pocket notches and the funnel flares all vary only in the bed
// plane, so nothing overhangs and nothing needs supports. Fatigue: the blades
// bend in the bed plane, so cyclic bending stress acts across roads within a
// layer, never between layer bonds (docs/advanced-techniques.md Domain 1).

include <styles/workshop-utility/style.scad>
use <printability.scad>

/* [Cells] */
// AA cell envelope diameter (mm) — IEC R6 nominal; caliper your cells, brands
// vary a few tenths (issue #704 brief, assumed-with-default)
aa_cell_d = 14.5;
// AA cell length including the + nub (mm)
aa_cell_l = 50.5;
// AA lanes (count); 4 is the v1 default footprint
aa_lanes = 4;
// Cells stored per AA lane (count) — sets the lane height
aa_cells = 4;
// AAA cell envelope diameter (mm) — IEC R03 nominal
aaa_cell_d = 10.5;
// AAA cell length including the + nub (mm)
aaa_cell_l = 44.5;
// AAA lanes (count)
aaa_lanes = 4;
// Cells stored per AAA lane (count)
aaa_cells = 4;

/* [Fit & tolerances] */
// Lane bore grown over the cell diameter (mm) — the brief's +0.4 bore
// clearance, applied the same way as the repo's fastener-hole convention
cell_clearance = 0.4;
// Spring pinch per side (mm): how far the blade throat intrudes inside the
// nominal cell surface. Retention knob #2 (grip force ~ pinch x stiffness);
// tune with the coupon
pinch = 0.35;
// Spring blade thickness (mm) — THE coupon knob: stiffness scales with t^3,
// so +-0.1 moves the release force ~25%. 1.3 targets ~5 N in PETG; PLA
// prints stiffer (pop-fidget-card field test), try 1.2 there
finger_t = 1.3;
// Air gap between the blade's back and the pocket wall at rest (mm); the
// blade must deflect outward by `pinch` and still clear — proven by the
// finger_relief fitcheck, not trusted from this number
pocket_clear = 0.9;
// Blade height above the lane floor, AA lanes (mm) — the grip band
finger_h_aa = 13;
// Blade height above the lane floor, AAA lanes (mm)
finger_h_aaa = 9.5;

/* [Structure] */
// Back plate thickness (mm) — the wall-mount rail
back_t = 3.2;
// Lane divider thickness (mm) — carries a spring pocket each side and must
// leave a >= 0.8 mm web between them (asserted). Also sets the divider-top
// bullnose radius (t/2): at 5.4 that is 2.7 mm, inside the style pack's
// corner-radius window, so the rolled lip IS the family rounding
divider_t = 5.4;
// Outer end wall thickness (mm)
end_t = 3.0;
// Lane floor thickness (mm) — the cell column stands on this
floor_t = 3.0;
// Mount spine width (mm) — the screw slot between the AA and AAA groups
spine_w = 12;
// Headroom above the top cell (mm)
top_gap = 1.5;
// Loading funnel: height of the flare at each lane's top opening (mm)
flare_h = 5;
// Loading funnel: how far the flare opens per side (mm)
flare_w = 1.1;

/* [Mount] */
// Wall-mount fastener (M preset from lib/printability.scad; M4 clearance is
// the brief's Ø 4.5)
mount_screw = "M4";
// Vertical spacing of the two mount holes (mm) — the brief's ~16 mm rail
// spacing, realized on the spine
mount_pitch = 16;

/* [Quality] */
// Curves drawn at the style's resolution
$fn = style_fn;

// ---------------------------------------------------------------------------
// Derived layout. All lane-frame x positions are measured from the lane's
// left edge: the bore spans [0, bore_d], the right wall's inner face is at
// x = bore_d, the left wall's at x = 0.
// ---------------------------------------------------------------------------

function bore_d(cd) = cd + cell_clearance;
function group_w(cd, n) = n == 0 ? 0 : n * bore_d(cd) + (n - 1) * divider_t;
function has_spine() = aa_lanes > 0 && aaa_lanes > 0;
function aa_x0() = end_t;
function aaa_x0() =
    end_t + group_w(aa_cell_d, aa_lanes) +
    (has_spine() ? 2 * divider_t + spine_w : 0);
function body_w() =
    2 * end_t + group_w(aa_cell_d, aa_lanes) + group_w(aaa_cell_d, aaa_lanes) +
    (has_spine() ? 2 * divider_t + spine_w : 0);
function aa_lane_h() = floor_t + aa_cells * aa_cell_l + top_gap;
function aaa_lane_h() = floor_t + aaa_cells * aaa_cell_l + top_gap;
function body_h() = max(aa_lane_h(), aaa_lane_h());

// Pocket depth beyond the wall's inner face: blade protrusion plus the rest
// gap. One formula, used by the cutter, the guards and the relief fitchecks.
function pocket_d() = finger_t - cell_clearance / 2 - pinch + pocket_clear;

// Visit every lane with $cd/$cl/$fh/$lh set and the child translated to the
// lane's left-front-bottom corner.
module each_lane() {
    for (i = [0 : 1 : aa_lanes - 1]) {
        $cd = aa_cell_d; $cl = aa_cell_l; $fh = finger_h_aa; $lh = aa_lane_h();
        translate([aa_x0() + i * (bore_d(aa_cell_d) + divider_t), 0, 0])
            children();
    }
    for (i = [0 : 1 : aaa_lanes - 1]) {
        $cd = aaa_cell_d; $cl = aaa_cell_l; $fh = finger_h_aaa;
        $lh = aaa_lane_h();
        translate([aaa_x0() + i * (bore_d(aaa_cell_d) + divider_t), 0, 0])
            children();
    }
}

// How deep a lane's blades reach from the back, as a fraction of the bore
// depth. Past the centerline, so withdrawal drags the cell over the blade
// band instead of slipping off a single tangent line.
blade_reach = 0.8;

// ---------------------------------------------------------------------------
// Guards
// ---------------------------------------------------------------------------

module guards() {
    assert(cell_clearance >= 0.3,
        "cell_clearance under 0.3 mm won't seat a real cell");
    assert(finger_t >= 1.0,
        "finger_t under 1.0 mm is under 3 perimeters at a 0.4 nozzle");
    assert(pinch >= 0.15 && pinch <= 0.8,
        "pinch outside 0.15-0.8 mm: too little to feel, too much to load");
    assert(pocket_clear >= 0.5,
        "pocket_clear under 0.5 mm starves the blade's deflection room");
    assert(divider_t >= 2 * pocket_d() + 0.8,
        "divider_t too thin: the two spring pockets leave under a 0.8 mm web");
    assert(end_t >= pocket_d() + 0.8,
        "end_t too thin for its single spring pocket");
    assert(finger_h_aa >= 8 && finger_h_aa <= aa_cell_l / 2,
        "AA blade height outside 8 mm..half-cell");
    assert(finger_h_aaa >= 8 && finger_h_aaa <= aaa_cell_l / 2,
        "AAA blade height outside 8 mm..half-cell");
    assert(blade_reach * bore_d(aa_cell_d) >= bore_d(aa_cell_d) / 2 + 1,
        "AA blade does not wrap past the bore centerline");
    assert(blade_reach * bore_d(aaa_cell_d) >= bore_d(aaa_cell_d) / 2 + 1,
        "AAA blade does not wrap past the bore centerline");
    assert(floor_t >= 2.4 && back_t >= 2.4 && divider_t >= 2.4 && end_t >= 2.4,
        "a structural wall is under 2.4 mm (under 2 perimeters + fill)");
    assert(aa_lane_h() > floor_t + aa_cells * aa_cell_l,
        "AA lane height does not clear its column");
    assert(aaa_lane_h() > floor_t + aaa_cells * aaa_cell_l,
        "AAA lane height does not clear its column");
    assert(flare_h >= 2 && flare_w >= 0.5, "funnel flare too small to guide");
    assert(aa_lanes >= 0 && aaa_lanes >= 0 && aa_lanes + aaa_lanes >= 1,
        "no lanes at all");
    if (has_spine()) {
        assert(spine_w >= socket_head(mount_screw)[0] + 2,
            "spine_w too narrow for the screw head to seat beside the holes");
        assert(mount_pitch >= screw_clearance_d(mount_screw) + 6,
            "mount holes too close: their walls would merge");
        assert(body_h() / 2 + mount_pitch / 2 + screw_clearance_d(mount_screw)
               <= body_h() - 2,
            "mount hole too close to the plate's top edge");
    }
}

// ---------------------------------------------------------------------------
// Fixed structure (everything except the spring blades)
// ---------------------------------------------------------------------------

// Back plate: the wall rail, rounded in the vertical plane. Authored in a
// local frame and rotated so the style's corner radius lands on the wall
// face and the 0.6 mm chamfer on the bed face (use-y = 0).
module back_plate() {
    translate([0, back_t, 0]) rotate([90, 0, 0])
        rounded_box([body_w(), body_h(), back_t], r = style_corner_r,
                    bottom_chamfer = style_edge_chamfer);
}

// One wall segment: x span, bore depth, height.
// A lane wall: a slab depth-wise, with the dividers' tops rolled into a
// bullnose (r = w/2) — the style pack's rounded utility lip, and a smoother
// mouth for the loading funnel. The profile is drawn in (x, z) and extruded
// along y, so in bed orientation the bullnose is a vertical half-round of
// constant cross-section: it prints like the blades, no overhang.
module wall(x0, w, bore, h, bullnose = false) {
    if (bullnose) {
        r = w / 2;
        // 0.01 overlaps into the plate/floor on every joining face: a
        // touching union of transformed extrusions leaves non-manifold
        // duplicate faces (measured: 32 edges, score 59), an overlapping
        // one is robust
        translate([x0, back_t + bore, -0.01]) rotate([90, 0, 0])
            linear_extrude(bore + 0.02) {
                translate([0, -0.01]) square([w, h - r + 0.01]);
                translate([w / 2, h - r]) circle(r = r);
            }
    } else
        translate([x0, back_t, 0]) cube([w, bore, h]);
}

module fixed_walls() {
    b_aa = bore_d(aa_cell_d);
    b_aaa = bore_d(aaa_cell_d);
    h_aa = aa_lane_h();
    h_aaa = aaa_lane_h();
    // end walls — each borders whichever group is outermost on its side.
    // Too thin to carry an in-family bullnose (end_t/2 = 1.5 < the style's
    // corner window), so they stay square; the dividers carry the rounding
    if (aa_lanes > 0)  wall(0, end_t, b_aa, h_aa);
    else               wall(0, end_t, b_aaa, h_aaa);
    if (aaa_lanes > 0) wall(body_w() - end_t, end_t, b_aaa, h_aaa);
    else               wall(body_w() - end_t, end_t, b_aa, h_aa);
    // inner dividers
    for (i = [0 : 1 : aa_lanes - 2])
        wall(aa_x0() + (i + 1) * b_aa + i * divider_t, divider_t, b_aa, h_aa,
             bullnose = true);
    for (i = [0 : 1 : aaa_lanes - 2])
        wall(aaa_x0() + (i + 1) * b_aaa + i * divider_t, divider_t, b_aaa,
             h_aaa, bullnose = true);
    // the two spine-bounding dividers run the AA depth (the deeper bore) so
    // the screw slot is one clean channel
    if (has_spine()) {
        wall(end_t + group_w(aa_cell_d, aa_lanes), divider_t, b_aa, h_aa,
             bullnose = true);
        wall(aaa_x0() - divider_t, divider_t, b_aa, h_aa, bullnose = true);
    }
}

module lane_floors() {
    // 0.01 into each flanking wall: a floor face exactly coplanar with a
    // divider face leaves non-manifold duplicates in the union
    each_lane()
        let (b = bore_d($cd))
        translate([-0.01, back_t, 0]) cube([b + 0.02, b, floor_t]);
}

// The notch that gives each blade room to deflect: cuts the adjacent wall
// from just inside the bore to the pocket floor, over the blade's y-z window,
// starting above the blade's rooted foot so the root stays welded to the wall.
// (b/pd are let()-bound, not plain assignments: OpenSCAD 2021.01 resolves
// plain-assignment RHS lexically, which drops each_lane's $cd — a silent
// wrong-geometry trap this repo's check.sh surfaces as WARNINGs.)
module spring_pockets() {
    each_lane()
        let (b = bore_d($cd), pd = pocket_d(), fh = $fh)
        for (x0 = [b - 0.01, -pd - 0.01])
            translate([x0, back_t - 0.01, floor_t + foot_h])
                cube([pd + 0.02, blade_reach * b + 0.52,
                      fh + 1.5 - foot_h + 0.02]);
}

// Top loading funnel: a wedge that flares each lane's opening near the top,
// so a cell dropped in square still finds the bore. The wedge widens upward
// from the wall's inner face — a slope in the bed plane, not an overhang.
module funnels() {
    each_lane()
        let (b = bore_d($cd), lh = $lh)
        for (s = [1, -1])
            translate([0, back_t - 0.01 + b + 0.02, 0])
                rotate([90, 0, 0])
                    linear_extrude(b + 0.02)
                        polygon(s > 0
                            ? [[b - 0.01, lh - flare_h],
                               [b + flare_w + 0.02, lh + 0.02],
                               [b - 0.01, lh + 0.02]]
                            : [[0.01, lh - flare_h],
                               [-flare_w - 0.02, lh + 0.02],
                               [0.01, lh + 0.02]]);
}

// Wall-mount holes through the back plate, on the spine.
module mount_holes_cut() {
    if (has_spine()) {
        cx = end_t + group_w(aa_cell_d, aa_lanes) + divider_t + spine_w / 2;
        for (dz = [-mount_pitch / 2, mount_pitch / 2])
            translate([cx, 0, body_h() / 2 + dz])
                rotate([-90, 0, 0])
                    screw_hole(mount_screw, l = back_t, head = "none");
    }
}

// The fixed body: everything a cell touches except the springs. The
// ci.fitchecks seat the cell proxy against THIS body — a rigid proxy cannot
// seat past a preloaded spring by construction, so the bore clearance is
// proven on the fixed bore and the spring geometry by throat_grip /
// finger_relief.
module fixed_body() {
    difference() {
        union() {
            back_plate();
            fixed_walls();
            lane_floors();
        }
        spring_pockets();
        funnels();
        mount_holes_cut();
    }
}

// ---------------------------------------------------------------------------
// Spring blades
// ---------------------------------------------------------------------------

foot_h = 0.8;   // rooted foot height: below this the blade is welded to the wall
foot_w = 0.35;  // root flare width, outboard (tension) face — the r >= 0.5 t
                // root rule approximated as a taper; cyclic stress is ~15% of
                // PETG yield, so this is comfort, not necessity
tip_c = 0.8;    // 45-degree lead-in leg on the throat's top corner (kept
                // under finger_t, or the polygon self-intersects): the rim
                // of a descending cell rides this chamfer and cams the blade
                // open ("press the top cell down and the fingers ride the
                // cell's taper shoulder")

// One blade of a lane, profile in x-z extruded along the lane depth: side=+1
// the right blade, side=-1 the left (its polygon mirrored about the lane
// center, not the instance — see the note below the module). The throat face
// sits pinch inside the nominal cell surface.
module spring_blade(b, fh, side) {
    x_in = b - cell_clearance / 2 - pinch;  // throat face, from lane left edge
    pts = side > 0
        ? [[x_in, 0],
           [x_in + finger_t + foot_w, 0],
           [x_in + finger_t, foot_h],
           [x_in + finger_t, fh],
           [x_in + tip_c, fh],
           [x_in, fh - tip_c]]
        : [[b - x_in, 0],
           [b - x_in - finger_t - foot_w, 0],
           [b - x_in - finger_t, foot_h],
           [b - x_in - finger_t, fh],
           [b - x_in - tip_c, fh],
           [b - x_in, fh - tip_c]];
    translate([0, back_t - 0.01 + blade_reach * b, floor_t - 0.01])
        rotate([90, 0, 0])
            linear_extrude(blade_reach * b)
                polygon(pts);
}

// Both blades of every lane. `delta` rigidly offsets the blades outward for
// the relief fitchecks (the conservative worst case — a real deflection
// moves the tip more and the root not at all).
//
// (Transforms here are rotate/translate only, and the two blades of a lane
// are distinct polygons rather than one mirrored instance: OpenSCAD 2021.01
// fails to convert a cached extrusion reused under several mirror-bearing
// transforms — "The given mesh is not closed" — so mirroring is folded into
// the 2D profile instead.)
module blades(delta = 0) {
    each_lane()
        let (b = bore_d($cd)) {
        translate([delta, 0, 0]) spring_blade(b, $fh, 1);
        translate([delta, 0, 0]) spring_blade(b, $fh, -1);
    }
}

// ---------------------------------------------------------------------------
// Cell proxies (fitchecks + preview)
// ---------------------------------------------------------------------------

// Cell-envelope cylinders seated on the lane floors, centered in the bores.
// `grow` adds to the diameter: 0 = nominal cell, 0.3 = max-material envelope
// (nominal + the few-tenths brand spread, stated assumption), 0.7 = negative
// control. Seated 0.01 up so floor contact is not a coplanar boolean.
module cell_proxies(grow) {
    each_lane()
        let (b = bore_d($cd))
        translate([b / 2, back_t + b / 2, floor_t + 0.01])
            cylinder(d = $cd + grow, h = $cl - 0.02);
}

// The blades' free span — at or above the rooted foot, and in front of the
// back plate. The relief fitchecks clip to this so the rigid-translate proxy
// is judged on its working span, where a real blade actually deflects, and
// not on the root that cannot move. The y clip is not cosmetic: a blade's
// back face sits at back_t - 0.01, the same plane the pocket is cut from, so
// an intersection unclipped in y reports the shared boundary face as phantom
// interference (measured: 224 zero-volume facets, all within 0.01 mm of the
// wall — no real collision anywhere). The z clip sits 0.05 above the foot,
// not on it: the pocket floor is cut at exactly floor_t + foot_h, and a clip
// coplanar with it reports 32 phantom facets under the Manifold nightly
// backend (CI's render gate) while CGAL 2021.01 resolves it to zero — the
// same coincidence, resurfacing one boolean downstream on the other kernel.
module above_root() {
    translate([-1, back_t + 0.01, floor_t + foot_h + 0.05])
        cube([body_w() + 2, bore_d(aa_cell_d) + 2, body_h()]);
}

// ---------------------------------------------------------------------------
// Preview-only poses (cameras.conf; never printable parts)
// ---------------------------------------------------------------------------

module cell_prop(cd, cl) {
    // + nub down: the taper shoulder then faces up the lane, so a descending
    // cell presents its shoulder to the blade lead-ins exactly as when loading
    cylinder(d = cd - 9, h = 1.2);
    translate([0, 0, 1.2]) cylinder(d = cd, h = cl - 1.2);
}

aa_fill = [4, 3, 4, 2];    // one lane short, one mid-dispense
aaa_fill = [4, 4, 1, 0];

module cells_preview() {
    for (i = [0 : 1 : aa_lanes - 1]) {
        n = i < len(aa_fill) ? aa_fill[i] : 0;
        for (j = [0 : 1 : n - 1]) {
            // the bottom cell of lane 2 half-pulled out of the channel —
            // the dispense gesture the blade grip resists
            pulled = (i == 1 && j == 0);
            translate([aa_x0() + i * (bore_d(aa_cell_d) + divider_t) +
                       bore_d(aa_cell_d) / 2,
                       back_t + bore_d(aa_cell_d) / 2 + (pulled ? 12 : 0),
                       floor_t + j * aa_cell_l + (pulled ? 4 : 0)])
                cell_prop(aa_cell_d, aa_cell_l);
        }
    }
    for (i = [0 : 1 : aaa_lanes - 1]) {
        n = i < len(aaa_fill) ? aaa_fill[i] : 0;
        for (j = [0 : 1 : n - 1])
            translate([aaa_x0() + i * (bore_d(aaa_cell_d) + divider_t) +
                       bore_d(aaa_cell_d) / 2,
                       back_t + bore_d(aaa_cell_d) / 2, floor_t + j * aaa_cell_l])
                cell_prop(aaa_cell_d, aaa_cell_l);
    }
}

// Horizontal slab through the blade band of the leftmost AA lanes: throat,
// pockets and blade roots in one section — internal geometry a plain render
// cannot show.
module section_slab() {
    translate([end_t - 1, -1, -1])
        cube([bore_d(aa_cell_d) * 2 + divider_t + 2, 22,
              floor_t + finger_h_aa + 4]);
}

// ---------------------------------------------------------------------------
// Assembly
// ---------------------------------------------------------------------------

module body_use() {
    union() {
        fixed_body();
        blades();
    }
}

// Bed orientation: back flat on the bed, lanes along the printer's X — the
// 4-high AA column (206.5 mm) lands on the 250 mm axis, everything else
// inside 210 x 220 with room to spare (width 164.4 mm on the 210 axis).
module print_body() {
    rotate([0, 0, 90]) rotate([90, 0, 0]) body_use();
}

part = "";  // "" printable body (bed orientation) · "use" preview with cells ·
            // "section" slice at the blade band · fitcheck parts (ci.fitchecks)
            // — preview and fitcheck parts are never printable

module main() {
    guards();
    if (part == "fitcheck")
        // max-material cell clears the fixed bore (the brief's Ø+bore-size
        // proxy would sit coincident with the bore surface — a degenerate
        // boolean — so the envelope stops 0.1 short of it; see NOTES.md)
        intersection() { fixed_body(); cell_proxies(0.3); }
    else if (part == "fitcheck_neg")
        intersection() { fixed_body(); cell_proxies(0.7); }
    else if (part == "throat_grip")
        // the pinch is real on the built mesh: a nominal cell overlaps the
        // blades by `pinch` per side
        intersection() { blades(); cell_proxies(0); }
    else if (part == "finger_relief")
        // the blades, pushed outward by the pinch, still clear the fixed body
        intersection() { fixed_body(); blades(pinch); above_root(); }
    else if (part == "finger_relief_neg")
        intersection() { fixed_body(); blades(pinch + pocket_clear + 0.2); above_root(); }
    else if (part == "use") {
        body_use();
        cells_preview();
    }
    else if (part == "section")
        intersection() { body_use(); section_slab(); }
    else
        print_body();
}

main();
