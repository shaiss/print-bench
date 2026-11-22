// tape-strip-rack — a blade-free multi-strip tape station: two rolls on a
// drop-in spindle, a hold-down gate both tapes pass under, and a row of thin
// fins. Pull both tapes along the rack, lower them, press them onto the fin
// tops and snip mid-gap with scissors: every strip is left stuck by its
// middle to one fin, both ends free to grab.
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// Frame: X runs along the tape (downstream = +X), Y across the lanes, Z up.
// Every part except the spindle is modelled, exported and printed exactly as
// it stands in use; the spindle is modelled standing on end, which is how it
// prints.

/* [Part] */
// What to render: the assembled preview, one of the four printable parts,
// the print-this-first joint coupon, a boolean fit proof (ci.fitchecks —
// never printed), or a preview-only pose.
part = "assembly"; // [assembly, cradle, spindle, rack, end-cap, joint-coupon, joint-fit, joint-fit-ctrl, joint-pull, joint-lift, joint-drop, spindle-fit, spindle-fit-ctrl, roll-fit, roll-fit-ctrl, nest-fit, nest-fit-ctrl, nested, joint-pair, cutaway]

/* [Tape — what it must hold] */
// Tape width (mm). 19 = 3/4 in desk tape. The lane formula takes 12 to 25;
// a narrower tape wants its own render, not a 19 mm print.
tape_w = 19;
// Inner diameter of the roll's core (mm). 25.4 = the common 1 in core.
// Caliper your own roll before printing the spindle.
core_id = 25.4;
// Largest roll outer diameter the cradle clears (mm).
roll_od_max = 62;
// Rolls side by side: 1 or 2. Each gets its own lane. The spindle is one
// piece, so it cannot take a third. One lane needs a narrower joint:
// -D joint_neck=6 -D joint_tip=13.
lanes = 2;

/* [Strips] */
// Strip length = fin pitch (mm), 40 to 60 (36 with ledge_l = 8). 40 is about
// 1.5 in; 50 gives 2 in strips and needs fins_per_rack = 4 to keep a segment
// on a 220 mm bed, 60 needs fins_per_rack = 3.
strip_len = 40;
// Fins on one rack segment (count). 5 x 40 mm fits a 220 mm bed.
fins_per_rack = 5;
// Rack segments in the assembled preview (count). Print this many racks.
racks = 2;

/* [Fins] */
// Height of the tape plane above the top of the base (mm) — scissor and
// fingertip room under a strip.
fin_h = 26;
// Length of the tape land along the tape = fin thickness at its top (mm).
land_l = 3.2;
// Fin thickness at its root (mm). The taper puts the material where a
// knocked fin would otherwise snap along a layer line.
fin_root_l = 5.2;
// Guide-post width across the rack at tape height (mm). Also the cradle
// wall thickness, so the walls line up with the outer posts.
post_w = 4.4;
// How far the guide posts stand above the tape plane (mm).
post_rise = 8;
// Flat on top of each guide post (mm) — blunt on purpose.
post_tip = 1.6;
// Clearance between a tape edge and the post beside it, each side (mm).
lane_clear = 1.5;
// Raised ribs per lane on each tape land (count). Fewer, narrower ribs
// make a strip easier to peel off; 0 makes the land one flat strip.
land_ribs = 3;
// Width of each land rib across the tape (mm).
land_rib_w = 2.4;
// Depth of the relief between ribs (mm).
land_relief = 0.6;

/* [Base & joint — the tuned fit] */
// Thickness of the rack base, and the height of the joint (mm).
base_h = 8;
// Dovetail key: width at its neck, top of the base (mm).
joint_neck = 16;
// Dovetail key: width at its tip, top of the base (mm).
joint_tip = 24;
// Dovetail key: how far it projects from the end face (mm).
joint_depth = 7;
// Draft of the joint (degrees from vertical). The key is wider at the bed
// than at the top, so a socket part can only be lowered onto it, and a
// straight lift of the key part catches the socket part. A part hanging off
// a lifted key is then held by friction on this taper — shallower holds
// better, steeper catches sooner.
joint_draft = 8;
// Clearance between key and socket, each face (mm). THE tuned fit: print
// the joint coupon and adjust in 0.05 steps (see NOTES.md).
joint_clear = 0.2;
// First-layer relief on the joint (mm): the key is drawn in and the socket
// flared by this much over the bottom half millimetre, so bed squish is not
// the tight spot. Raise it if the joint binds only for the last millimetre.
joint_ef = 0.4;
// Gap between the end faces of two joined parts (mm).
joint_gap = 0.3;

/* [Cradle] */
// Cradle floor thickness (mm).
floor_t = 2.4;
// Clearance between the largest roll and the cradle floor (mm).
roll_floor_clear = 3;
// Diametral clearance between the spindle hub and the roll core (mm). A
// loose running fit, not a tuned one.
hub_clear = 0.8;
// Diametral clearance between the spindle ends and their saddle pockets (mm).
saddle_clear = 0.6;
// Lean of the saddle slots, back from vertical (degrees). The tape pulls
// the spindle forward and down, into the seat.
saddle_lean = 25;
// Depth of the blind saddle pockets in each wall (mm). The skin left
// outside stops the spindle sliding out sideways.
saddle_pocket = 2.8;
// How far above the tape plane the hold-down gate sits (mm). The tapes
// pass under it, so a level pull clears every fin and the sticky side only
// touches down when the tape is lowered and pressed.
gate_rise = 3;
// Clear distance between the largest roll and the gate (mm): the slot a
// finger reaches into to thread a tape under the gate.
gate_roll_clear = 20;
// Length of the palm pad behind the rolls (mm): where the steadying hand
// presses while the other pulls. 0 removes it.
heel_l = 30;
// Radius of the outer corners at the two free ends — the back of the palm
// pad and the end of the end cap (mm). Rounded corners lift off the bed less.
corner_r = 4;

/* [End cap] */
// Length of the tail ledge along the tape (mm).
ledge_l = 12;

/* [Preview] */
// Draw the rolls and the tape on the assembly. Off by default, so that the
// default render — and any STL exported from it — holds printed parts only.
// Turn it on to look at how the tape runs, not for a file you will slice.
show_payload = false;
// Roll diameter drawn in the preview (mm).
preview_roll_od = 50;
// How the tape is drawn. "cut": after pressing and cutting, a strip on every
// fin. "pulled": one taut tape per lane, just pulled and not yet pressed down.
tape_pose = "cut"; // [cut, pulled]
// Lift each part off its upstream neighbour by this much (mm) to show how
// the joint goes together. 0 = assembled.
explode = 0;

/* [Quality] */
// Curve resolution. Only the spindle, the saddle slots and four corners are
// round, so the production value costs nothing: 96.
$fn = 96;

/* [Hidden] */
// Where the cutaway is cut: "lane" = the middle of the first lane, "key" =
// through the joint's key (just inside a lane when the centre is a post).
cut_at = "lane";
// ---------------------------------------------------------------------------
// Derived
// ---------------------------------------------------------------------------
eps = 0.01;
ov = 0.4;                       // union overlap: pieces overlap by volume, never just touch
bed_ch = 0.5;                   // bed-edge chamfer, horizontal leg
bed_ch_h = 0.6;                 // bed-edge chamfer, vertical leg (50 deg)
z_in = floor_t / 2;             // where the cradle's nose and back wall start, inside the floor
// The side walls are extruded 2D profiles, and OpenSCAD snaps a 2D profile to
// a grid before it extrudes it: a wall drawn from z_in would start a hair
// off the nose block's z_in (0.000003 mm on OpenSCAD 2021.01), and where
// both meet the nose face the Manifold backend's export carries the two
// edges as zero-area triangles. So the walls start at a depth of their own,
// a quarter of the floor away from the nose, the back wall and the floor's
// top.
z_wall_in = floor_t * 3 / 4;    // 1.8
joint_ef_h = 0.5;               // height of the joint's first-layer relief
joint_tip_cut = 0.8;            // key tip corners cut back (corner relief)
mouth_relief = 1.6;             // how far each socket lip is squared back
joint_lead = 0.5;               // lead-in chamfer round the socket rim
joint_flank = atan((joint_tip - joint_neck) / 2 / (joint_depth + ov));   // flank angle off the X axis
// how far an offset of 1 pushes the dovetail's acute tip corner sideways
joint_mitre = tan(joint_flank) + 1 / cos(joint_flank);

lane_w = tape_w + 2 * lane_clear;                    // 22
W = lanes * lane_w + (lanes + 1) * post_w;           // 57.2
z_land = base_h + fin_h;                             // 34: the tape plane
rack_l = fins_per_rack * strip_len;                  // 200: one segment's pitch length
post_root_l = fin_root_l + 2.0;                      // 7.2
post_mid_l = land_l + 1.4;                           // 4.6

hub_d = core_id - hub_clear;                         // 24.6
r_s = (hub_d + saddle_clear) / 2;                    // 12.6: saddle slot radius
z_axis = floor_t + roll_floor_clear + roll_od_max / 2;   // 36.4
z_gate = z_land + gate_rise;                         // 37: underside of the gate
lintel_flat = 2.0;              // flat the tape slides under
lintel_w = 5.8;                 // lintel thickness along the tape
lintel_ch_h = (lintel_w - lintel_flat) / 2 * tan(50);    // 2.26
z_gate_top = z_gate + lintel_ch_h + 2.2;             // 41.46
nose_l = 12;                                         // full-height block that carries the key
x_gate = -nose_l / 2;                                // -6
x_axis = x_gate - lintel_w / 2 - gate_roll_clear - roll_od_max / 2;   // -59.9
back_t = 3;
back_inset = 0.8;               // the back wall sits this far inside the wall ends
cradle_l = -x_axis + roll_od_max / 2 + 3 + back_t + back_inset;   // 97.7: nose face to wall ends
// the floor always runs a little past the wall ends, so their end faces
// never share a plane with the floor's; with a palm pad it runs on further
heel_ext = max(heel_l, 0.4);
heel_round = heel_l >= corner_r + 2;                 // enough pad to round its corners
z_wall_top = z_axis + r_s + 9;                       // 58
// Where the rear edge of the saddle slot leaves the top of the wall, and how
// much wall top is left between it and the wall's rear corner chamfer.
x_slot_rear = x_axis - r_s * cos(saddle_lean)
            - (z_wall_top - z_axis + r_s * sin(saddle_lean)) * tan(saddle_lean);
saddle_land = x_slot_rear - (-cradle_l + 5);         // 8.8
cradle_in_w = W - 2 * post_w;                        // 48.4
spindle_play = 1.6;                                  // axial float of the spindle, total
spindle_l = cradle_in_w + 2 * saddle_pocket - spindle_play;   // 52.4
spindle_end_ch = 0.6;                                // length of the chamfer on each end of the spindle
flange_d = core_id + 3.6;                            // 29
flange_flat = 1.2;
flange_cone = (flange_d - hub_d) / 2 / tan(40);      // 2.62: a 40-deg-from-vertical shoulder
cap_post_root_l = ledge_l + 2 + (post_root_l - fin_root_l);   // 16: the end cap's posts at their root
cap_l = strip_len / 2 + cap_post_root_l / 2 + corner_r + 1;   // 33

function lane_y0(k) = post_w + k * (lane_w + post_w);
function lane_c(k) = lane_y0(k) + lane_w / 2;
function post_y0(j) = j * (lane_w + post_w);
function fin_x(i) = strip_len / 2 + i * strip_len;
function draft_run(z) = (base_h - z) * tan(joint_draft);
// The socket at the bed: the widest and the deepest the joint ever gets.
joint_bed_w = joint_tip + 2 * (draft_run(0) + joint_clear + joint_ef) * joint_mitre;   // 29.8
mouth_bed_w = joint_neck + 2 * (mouth_relief + draft_run(0) + joint_clear);            // 21.8
joint_reach = joint_depth + draft_run(0) + joint_clear + joint_ef;                     // 8.72
// What stops the joint pulling apart along the tape: how far the key's tip
// overlaps the socket's squared mouth, each side.
joint_hold = (joint_tip - joint_neck) / 2 - mouth_relief - joint_clear
           - joint_tip_cut * sin(joint_flank);                                         // 1.82
// Elevation of the tape from a roll of diameter od to the gate, in degrees;
// negative = running downhill to the gate.
function tape_elev(od) =
    let(px = x_gate - lintel_w / 2, pz = z_gate + lintel_ch_h,
        dx = x_axis - px, dz = z_axis - pz, d = sqrt(dx * dx + dz * dz),
        a = atan2(dz, dx) - asin(od / 2 / d) - 180)
    a < -180 ? a + 360 : a;
// The roll actually drawn: the preview size, kept between core and maximum.
roll_od_shown = min(max(preview_roll_od, core_id + 4), roll_od_max);
rib_inset = 1.2;                // outermost land rib to the tape edge
rib_gap = land_ribs > 1 ? (tape_w - 2 * rib_inset - land_ribs * land_rib_w) / (land_ribs - 1) : tape_w;

// Guards: the brief's numbers and the print floors as render failures.
// The spindle is one piece with a flange between each pair of rolls, and a
// roll cannot pass a flange: with three lanes the middle roll could not be
// put on at all.
assert(lanes == 1 || lanes == 2,
       str("lanes must be 1 or 2, not ", lanes, ": the spindle is one piece, and a roll between two of its",
           " flanges could not be put on"));
assert(tape_pose == "cut" || tape_pose == "pulled", str("tape_pose must be \"cut\" or \"pulled\", not ", tape_pose));
assert(cut_at == "lane" || cut_at == "key", str("cut_at must be \"lane\" or \"key\", not ", cut_at));
assert(fins_per_rack >= 1 && fins_per_rack == floor(fins_per_rack), "fins_per_rack must be a whole number, 1 or more");
assert(racks >= 1 && racks == floor(racks), "racks must be a whole number, 1 or more");
assert(land_ribs >= 0 && land_ribs == floor(land_ribs), "land_ribs must be a whole number, 0 or more");
assert(tape_w >= 12 && tape_w <= 25, str("tape_w ", tape_w, " is outside the 12-25 mm the lane formula was sized for"));
assert(hub_d >= 10, str("core_id ", core_id, " leaves a ", hub_d, " mm hub — too small to print standing"));
assert(hub_clear >= 0.4, "hub_clear under 0.4 mm will bind on a real roll core");
assert(roll_od_max >= core_id + 6, "roll_od_max must be at least 6 mm more than core_id");
assert(land_l >= 1.2 && fin_root_l >= land_l, str("fin ", land_l, " -> ", fin_root_l, " mm: the land must be at least 1.2 and the root no thinner than the land"));
assert(post_tip >= 0.8 && post_tip <= post_w, "post_tip must be between 0.8 mm and post_w");
assert(land_ribs == 0 || (land_rib_w >= 0.8 && land_ribs * land_rib_w <= tape_w - 2 * rib_inset),
       str(land_ribs, " ribs of ", land_rib_w, " mm do not fit under a ", tape_w, " mm tape"));
assert(land_ribs < 2 || rib_gap >= 0.8,
       str("only ", rib_gap, " mm between land ribs — under the 0.8 mm a nozzle can clear. Use fewer or narrower ribs."));
assert(fin_h >= 25, str("fin_h ", fin_h, " leaves less than the brief's 25 mm of scissor room under a strip"));
assert(strip_len - post_root_l >= 28,
       str("only ", strip_len - post_root_l, " mm between fins — under the brief's 28 mm for scissors and a thumb. Raise strip_len."));
assert(rack_l + joint_depth + draft_run(0) <= 210,
       str("a rack segment is ", rack_l + joint_depth + draft_run(0), " mm long — over the brief's 210 mm. Lower fins_per_rack."));
assert(z_wall_top <= 200, "the cradle is over the 200 mm the test-slice allows");
assert(floor_t >= 1.2, str("floor_t ", floor_t, " is under 1.2 mm: the cradle's walls would have nothing to stand in"));
assert(floor_t < base_h, str("floor_t ", floor_t, " is not under base_h (", base_h, "): the floor would bury the nose block"));
assert(saddle_land >= 1.2,
       str("only ", saddle_land, " mm of wall top is left behind the saddle slot — under 1.2 mm. Raise roll_od_max",
           " (now ", roll_od_max, ") or lower core_id (now ", core_id, ")."));
assert((W - max(joint_bed_w, mouth_bed_w)) / 2 >= 6,
       str("only ", (W - max(joint_bed_w, mouth_bed_w)) / 2, " mm of base beside the socket — under 6 mm.",
           " Narrow the joint (one lane: joint_neck = 6, joint_tip = 13) or widen the lanes."));
assert(joint_hold >= 0.8,
       str("the key's tip overlaps the socket mouth by only ", joint_hold, " mm a side — under 0.8 mm the joint",
           " pulls apart along the tape. Widen joint_tip or narrow joint_neck."));
assert(joint_clear > 0, "joint_clear must be positive: zero clearance prints as a weld");
assert(joint_ef >= 0 && joint_ef <= 0.8, "joint_ef outside 0-0.8 mm");
assert(joint_draft >= 5 && joint_draft <= 20, "joint_draft outside 5-20 deg: too little to catch a lift, or too much to hold by friction");
assert(joint_reach + 3 <= strip_len / 2 - post_root_l / 2,
       "the socket runs into the first fin — lower joint_depth or raise strip_len");
assert(joint_reach + 3 <= strip_len / 2 - cap_post_root_l / 2,
       str("the socket runs under the end cap's ledge — lower ledge_l (now ", ledge_l, ") or joint_depth"));
assert(post_w - saddle_pocket >= 1.2, str("only ", post_w - saddle_pocket, " mm of wall outside the saddle pocket — under 1.2 mm"));
// Pushed against one wall, the spindle keeps saddle_pocket - spindle_play of
// its other end in that pocket. More than the end chamfer must stay in, or
// the end rests on its chamfer, or on nothing.
assert(round(1000 * (saddle_pocket - spindle_play - spindle_end_ch)) > 0,     // compared in whole microns
       str("pushed against one wall, the spindle has ", saddle_pocket - spindle_play, " mm of its other end in the",
           " saddle pocket; it needs more than its ", spindle_end_ch, " mm end chamfer. Deepen saddle_pocket (now ",
           saddle_pocket, ") or lower spindle_play (now ", spindle_play, ")."));
assert(lane_w <= 30, str("the gate bridges ", lane_w, " mm per lane — over 30 mm it will sag without support"));
assert(z_gate - base_h >= 15, "the threading window under the gate is under 15 mm tall");
assert(max(tape_elev(core_id + 4), tape_elev(roll_od_max)) <= saddle_lean - 5,
       str("the tape climbs ", max(tape_elev(core_id + 4), tape_elev(roll_od_max)), " deg to the gate, within 5 deg of the",
           " saddle lean (", saddle_lean, "): a pull could lift the spindle out. Lower gate_rise or fin_h, or raise saddle_lean."));
assert(post_w + 2 * lane_clear - flange_flat - 2 * flange_cone >= 0.4,
       "the spindle flange does not fit between two rolls — widen post_w or lane_clear");
assert(heel_l >= 0 && corner_r > bed_ch, "heel_l must be 0 or more, and corner_r more than the 0.5 mm bed chamfer");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
// Extrude a 2D profile drawn in (x, z) across Y, from y0 for w.
module y_extrude(w, y0 = 0) {
    translate([0, y0 + w, 0]) rotate([90, 0, 0]) linear_extrude(w) children();
}

// A box on the bed with its bed edge chamfered at 50 degrees. An end that
// carries a joint keeps a square, unchamfered edge (cx0 / cx1 = false): the
// dovetail has its own first-layer relief, and a chamfer there would leave
// feather edges. r0 / r1 round the two outer corners of that end.
module bed_box(x0, x1, y0, y1, h, cx0 = true, cx1 = true, r0 = 0, r1 = 0) {
    // one corner of the footprint: a square corner, or a rounded one
    module corner(x, y, sx, sy, r, cx) {
        if (r > 0) {
            translate([x + sx * r, y + sy * r, 0]) {
                cylinder(r = r - bed_ch, h = eps, $fn = 48);
                translate([0, 0, bed_ch_h]) cylinder(r = r, h = h - bed_ch_h, $fn = 48);
            }
        } else {
            translate([x + sx * cx - (sx < 0 ? eps : 0), y + sy * bed_ch - (sy < 0 ? eps : 0), 0])
                cube([eps, eps, eps]);
            translate([x - (sx < 0 ? eps : 0), y - (sy < 0 ? eps : 0), bed_ch_h])
                cube([eps, eps, h - bed_ch_h]);
        }
    }
    hull() {
        corner(x0, y0, 1, 1, r0, cx0 ? bed_ch : 0);
        corner(x0, y1, 1, -1, r0, cx0 ? bed_ch : 0);
        corner(x1, y0, -1, 1, r1, cx1 ? bed_ch : 0);
        corner(x1, y1, -1, -1, r1, cx1 ? bed_ch : 0);
    }
}

// One closed solid lofted through a stack of axis-aligned rectangles, each
// given as [x0, x1, y0, y1, z]. Every side face joins two parallel edges, so
// it is planar.
module rect_loft(rings) {
    n = len(rings);
    pts = [for (r = rings) each [[r[0], r[2], r[4]], [r[1], r[2], r[4]],
                                 [r[1], r[3], r[4]], [r[0], r[3], r[4]]]];
    sides = [for (i = [0 : n - 2]) for (k = [0 : 3])
                 [4 * i + k, 4 * (i + 1) + k, 4 * (i + 1) + (k + 1) % 4, 4 * i + (k + 1) % 4]];
    top = 4 * (n - 1);
    polyhedron(pts, concat([[0, 1, 2, 3]], sides, [[top + 3, top + 2, top + 1, top]]));
}

// One closed solid of revolution about Z, through a profile of [radius, z]
// stations (radius above zero, z rising), with n sides. Every face is a
// triangle, listed clockwise seen from outside, and each end is a fan about
// a centre point. It replaces rotate_extrude() for a part that is nothing
// but the revolved shape. A revolved profile that touches the axis carries
// four zero-area triangles per side: one at each pole and two along the
// axis. openscad-nightly writes a part that is a single primitive to STL as
// it stands, so they reach the gate; OpenSCAD 2021.01 builds the same mesh
// but its STL writer leaves them out, which is why the local gate cannot
// see them.
module ring_loft(prof, n) {
    m = len(prof);
    assert(n == floor(n) && n >= 3, str("ring_loft: n must be a whole number, 3 or more, not ", n));
    assert(m >= 2 && min([for (p = prof) p[0]]) > 0, "ring_loft: the profile needs two or more stations, every radius above zero");
    assert(min([for (i = [0 : m - 2]) prof[i + 1][1] - prof[i][1]]) > 0, "ring_loft: the profile's z must rise from each station to the next");
    function v(i, k) = i * n + k % n;
    pts = concat([for (p = prof) for (k = [0 : n - 1])
                      [p[0] * cos(360 * k / n), p[0] * sin(360 * k / n), p[1]]],
                 [[0, 0, prof[0][1]], [0, 0, prof[m - 1][1]]]);
    bottom = [for (k = [0 : n - 1]) [m * n, v(0, k), v(0, k + 1)]];
    sides = [for (i = [0 : m - 2]) for (k = [0 : n - 1]) each
                 [[v(i, k), v(i + 1, k), v(i + 1, k + 1)], [v(i, k), v(i + 1, k + 1), v(i, k + 1)]]];
    top = [for (k = [0 : n - 1]) [m * n + 1, v(m - 1, k + 1), v(m - 1, k)]];
    polyhedron(pts, concat(bottom, sides, top));
}

// ---------------------------------------------------------------------------
// The joint — a drafted dovetail, drawn once and used for key and socket.
// Local frame: x = 0 is the key part's end face, the key projects along +X,
// y = 0 is the joint's centreline.
// ---------------------------------------------------------------------------
// `tip_cut` truncates the two acute tip corners: the key is cut back, the
// socket keeps its sharp inner corners, so a seam blob there has somewhere
// to go.
module joint_profile(tip_cut = 0) {
    fl = sqrt(pow(joint_depth + ov, 2) + pow((joint_tip - joint_neck) / 2, 2));
    ux = (joint_depth + ov) / fl;                 // unit vector along a flank
    uy = (joint_tip - joint_neck) / 2 / fl;
    half = tip_cut > 0
        ? [[-ov, joint_neck / 2],
           [joint_depth - tip_cut * ux, joint_tip / 2 - tip_cut * uy],
           [joint_depth, joint_tip / 2 - tip_cut]]
        : [[-ov, joint_neck / 2], [joint_depth, joint_tip / 2]];
    polygon(concat([for (q = half) [q[0], -q[1]]],
                   [for (i = [len(half) - 1 : -1 : 0]) half[i]]));
}
// The socket's mouth, squared off so its two lips end in a flat, not a
// 60-degree knife edge. Long enough to end inside the dovetail at every
// height, so no sliver of base is left between the mouth and the flank.
module mouth_profile() {
    translate([-ov - 1, -joint_neck / 2 - mouth_relief])
        square([ov + 1 + joint_gap + mouth_relief / tan(joint_flank) + 0.4,
                joint_neck + 2 * mouth_relief]);
}
// A thin slab of the dovetail (or, with mouth = true, of the squared mouth)
// at height z, grown by d. `chamfer` clips the offset's acute corners.
module joint_slab(z, d, tip_cut = 0, mouth = false, chamfer = false) {
    translate([0, 0, z]) linear_extrude(eps) offset(delta = d, chamfer = chamfer) {
        if (mouth) mouth_profile();
        else joint_profile(tip_cut);
    }
}
// The key: widest half a millimetre above the bed, drawn in below that so
// first-layer squish cannot make it the tight spot.
module key_solid() {
    hull() {
        joint_slab(0, draft_run(joint_ef_h) - joint_ef, joint_tip_cut);
        joint_slab(joint_ef_h, draft_run(joint_ef_h), joint_tip_cut);
        joint_slab(base_h - eps, 0, joint_tip_cut);
    }
}
// The socket cutter, in five pieces: the key's loft grown by `clear` on
// every face and run past both ends of the base; a squared mouth following
// the same draft; a relief flare at the bed; and a lead-in chamfer round the
// rim of each. The flare and the lead-ins take chamfered offset corners and
// start at different heights, so no two pieces' corner edges pass through
// one point — an emulation of the Manifold backend (manifold3d, not the
// nightly) exported such a crossing as edges shared by four triangles.
module socket_main(clear) {
    hull() {
        joint_slab(-1, draft_run(-1) + clear);
        joint_slab(base_h + 1, draft_run(base_h + 1) + clear);
    }
}
module socket_mouth(clear) {
    hull() {
        joint_slab(-1, draft_run(-1) + clear, mouth = true);
        joint_slab(base_h + 1, draft_run(base_h + 1) + clear, mouth = true);
    }
}
module socket_flare(clear) {
    hull() {
        joint_slab(-eps, draft_run(0) + clear + joint_ef, chamfer = true);
        joint_slab(joint_ef_h, draft_run(joint_ef_h) + clear - 0.02, chamfer = true);
    }
}
module socket_lead(clear, mouth = false) {
    z0 = base_h - joint_lead - (mouth ? 0.2 : 0);
    hull() {
        joint_slab(z0, draft_run(z0) + clear - 0.02, mouth = mouth, chamfer = true);
        joint_slab(base_h, clear + joint_lead, mouth = mouth, chamfer = true);
    }
}
module socket_cut(clear = joint_clear) {
    socket_main(clear);
    socket_mouth(clear);
    socket_flare(clear);
    socket_lead(clear);
    socket_lead(clear, mouth = true);
}

// ---------------------------------------------------------------------------
// Fins
// ---------------------------------------------------------------------------
// One guide post at fin centre xc: a tapered column up to the tape plane,
// then a horn whose lane faces lean away from the lane (a funnel). One
// closed solid lofted through three rectangles, so there is no seam where
// column meets horn.
module post(xc, j, root_l, mid_l) {
    y0 = post_y0(j);
    ty = j == 0 ? y0 : j == lanes ? y0 + post_w - post_tip : y0 + (post_w - post_tip) / 2;
    rect_loft([[xc - root_l / 2, xc + root_l / 2, y0, y0 + post_w, base_h - ov],
               [xc - mid_l / 2, xc + mid_l / 2, y0, y0 + post_w, z_land],
               [xc - post_tip / 2, xc + post_tip / 2, ty, ty + post_tip, z_land + post_rise]]);
}

// The reliefs between the land ribs of lane k, as one cutter per gap.
module land_reliefs(xc, k, cut_l) {
    y_tape = lane_c(k) - tape_w / 2;
    pitch = land_ribs > 1 ? land_rib_w + rib_gap : 0;
    function rib_y(i) = land_ribs > 1 ? y_tape + rib_inset + i * pitch : lane_c(k) - land_rib_w / 2;
    edges = concat([lane_y0(k) - eps],
                   [for (i = [0 : land_ribs - 1]) each [rib_y(i), rib_y(i) + land_rib_w]],
                   [lane_y0(k) + lane_w + eps]);
    for (g = [0 : land_ribs])
        translate([xc - cut_l / 2, edges[2 * g], z_land - land_relief])
            cube([cut_l, edges[2 * g + 1] - edges[2 * g], land_relief + 1]);
}

// A fin: a tapered wall across the full width, its top the tape land, with
// a guide post at every lane edge. `ribs = 0` leaves the land flat.
module fin(xc, land = land_l, root = fin_root_l, ribs = land_ribs) {
    difference() {
        hull() {
            translate([xc - root / 2, 0, base_h - ov]) cube([root, W, eps]);
            translate([xc - land / 2, 0, z_land - eps]) cube([land, W, eps]);
        }
        if (ribs > 0)
            for (k = [0 : lanes - 1]) land_reliefs(xc, k, 2 * root);
    }
    for (j = [0 : lanes])
        post(xc, j, root + (post_root_l - fin_root_l), land + (post_mid_l - land_l));
}

// ---------------------------------------------------------------------------
// Printable parts
// ---------------------------------------------------------------------------
// One rack segment, in its pitch frame: fins at strip_len/2 + i*strip_len,
// the socket at x = 0 (set back by joint_gap), the key at x = rack_l.
module rack() {
    difference() {
        union() {
            bed_box(joint_gap, rack_l, 0, W, base_h, cx0 = false, cx1 = false);
            for (i = [0 : fins_per_rack - 1]) fin(fin_x(i));
            translate([rack_l, W / 2, 0]) key_solid();
        }
        translate([0, W / 2, 0]) socket_cut();
    }
}

// The end cap: a socket, and one wide fin whose top is the ledge the tape
// tails are stuck to. It sits one pitch past the last fin, so the last fin
// still yields a full-length strip. The ledge is ribbed like the fins: the
// cap is the lightest part, and a flat ledge would hold the tails harder
// than the cap's own weight holds it down.
module end_cap() {
    difference() {
        union() {
            bed_box(joint_gap, cap_l, 0, W, base_h, cx0 = false, r1 = corner_r);
            fin(strip_len / 2, land = ledge_l, root = ledge_l + 2);
        }
        translate([0, W / 2, 0]) socket_cut();
    }
}

// Cradle side-wall profile in (x, z): tall round the saddle, sloping down
// to the gate. It starts inside the floor, which carries the bed chamfer —
// at z_wall_in, a depth no other piece uses — and stops at the wall ends,
// short of the floor's back edge.
module cradle_wall_2d() {
    // top of the hook in front of the saddle slot, 6 mm clear of the slot
    x_slot_top = x_axis + r_s * cos(saddle_lean)
               - (z_wall_top - z_axis - r_s * sin(saddle_lean)) * tan(saddle_lean);
    polygon([[-cradle_l, z_wall_in], [0, z_wall_in], [0, z_gate_top],
             [x_gate - lintel_w / 2 - 0.5, z_gate_top],
             [x_slot_top + 6, z_wall_top],
             [-cradle_l + 5, z_wall_top], [-cradle_l, z_wall_top - 5]]);
}
// The saddle slot in (x, z): the spindle seat, open up-and-back.
module saddle_2d() {
    hull() {
        translate([x_axis, z_axis]) circle(r_s);
        translate([x_axis - 60 * sin(saddle_lean), z_axis + 60 * cos(saddle_lean)]) circle(r_s);
    }
}
// The gate lintel in (x, z): a 2 mm flat the tape slides under, flared at
// 50 degrees so it prints as a short bridge and then grows.
module lintel_2d() {
    polygon([[x_gate - lintel_flat / 2, z_gate], [x_gate + lintel_flat / 2, z_gate],
             [x_gate + lintel_w / 2, z_gate + lintel_ch_h], [x_gate + lintel_w / 2, z_gate_top],
             [x_gate - lintel_w / 2, z_gate_top], [x_gate - lintel_w / 2, z_gate + lintel_ch_h]]);
}

// The cradle's pieces. Each overlaps its neighbours by volume; where two
// outer faces share a plane, one piece's face covers the other's edge.
// The floor, running on behind the wall ends as the palm pad.
module cradle_floor() {
    bed_box(-cradle_l - heel_ext, 0, 0, W, floor_t, cx1 = false,
            r0 = heel_round ? corner_r : 0);
}
// Grip ribs across the palm pad.
module cradle_heel_ribs() {
    n = floor((heel_l - 12) / 6) + 1;
    if (heel_l >= 14)
        for (i = [0 : n - 1])
            translate([-cradle_l - heel_l + 7 + 6 * i, corner_r + 2, floor_t - ov])
                cube([2, W - 2 * corner_r - 4, 1.2 + ov]);
}
// Nose block: full joint height, carries the key and the gate.
module cradle_nose() {
    translate([-nose_l, post_w - ov, z_in]) cube([nose_l, cradle_in_w + 2 * ov, base_h - z_in]);
}
// Low back wall, set in from the wall ends.
module cradle_back() {
    translate([-cradle_l + back_inset, post_w - ov, z_in])
        cube([back_t, cradle_in_w + 2 * ov, 14 - z_in]);
}
// A side wall (side 0 or 1); its nose end is an outer gate post.
module cradle_wall(side) {
    y_extrude(post_w, side == 0 ? 0 : W - post_w) cradle_wall_2d();
}
// Inner gate posts, one between each pair of lanes; each ends inside the lintel.
module cradle_gate_posts() {
    if (lanes > 1)
        for (j = [1 : lanes - 1])
            translate([x_gate - lintel_w / 2 + 0.3, post_y0(j), base_h - ov])
                cube([lintel_w - 0.6, post_w, z_gate + lintel_ch_h + 1 - base_h + ov]);
}
// The lintel, bridging each lane from post to post.
module cradle_lintel() {
    y_extrude(cradle_in_w + 2 * ov, post_w - ov) lintel_2d();
}
// A blind saddle pocket, cut into the inner face of a wall.
module cradle_pocket(side) {
    y_extrude(saddle_pocket + eps, side == 0 ? post_w - saddle_pocket : W - post_w - eps) saddle_2d();
}

// The cradle. Downstream face at x = 0, the key projecting beyond it.
module cradle() {
    difference() {
        union() {
            cradle_floor();
            cradle_heel_ribs();
            cradle_nose();
            cradle_back();
            cradle_wall(0);
            cradle_wall(1);
            cradle_gate_posts();
            cradle_lintel();
            translate([0, W / 2, 0]) key_solid();
        }
        cradle_pocket(0);
        cradle_pocket(1);
    }
}

// The spindle, standing on end (its print orientation): one hub for every
// roll, a small flange with 40-degree shoulders between each pair. One
// lofted solid, so there is no union to seam. `grow` oversizes the hub
// for the fit proof's negative control.
module spindle(grow = 0) {
    r = (hub_d + grow) / 2;
    rf = flange_d / 2 + grow / 2;
    y_s0 = post_w - saddle_pocket + spindle_play / 2;       // spindle's z = 0 in cradle Y
    function zc(j) = post_y0(j) + post_w / 2 - y_s0;         // flange centre along the axis
    flanges = lanes > 1
        ? [for (j = [1 : lanes - 1]) each [
              [r, zc(j) - flange_flat / 2 - flange_cone], [rf, zc(j) - flange_flat / 2],
              [rf, zc(j) + flange_flat / 2], [r, zc(j) + flange_flat / 2 + flange_cone]]]
        : [];
    // a whole number of sides, 3 or more, as rotate_extrude() would take a
    // $fn above zero; with $fn = 0 it is 96, not what $fa and $fs would give
    ring_loft(concat([[r - 0.4, 0], [r, spindle_end_ch]], flanges,
                     [[r, spindle_l - spindle_end_ch], [r - 0.4, spindle_l]]),
              max(3, floor($fn > 0 ? $fn : 96)));
}
// The spindle laid in its saddles.
module spindle_use(grow = 0) {
    translate([x_axis, post_w - saddle_pocket + spindle_play / 2, z_axis])
        rotate([-90, 0, 0]) spindle(grow);
}

// ---------------------------------------------------------------------------
// Payload (preview and fit proofs only — never printed)
// ---------------------------------------------------------------------------
module rolls(od = roll_od_shown) {
    for (k = [0 : lanes - 1])
        translate([x_axis, lane_c(k) - tape_w / 2, z_axis]) rotate([-90, 0, 0])
            difference() {
                cylinder(d = od, h = tape_w);
                translate([0, 0, -1]) cylinder(d = core_id, h = tape_w + 2);
            }
}

// The tape. "cut" (the default) is the state after the cuts: the feed from
// the roll under the gate to its parked tail past fin 0, one strip centred
// on every later fin, and the tails on the end cap's ledge. "pulled" is the
// moment before pressing: one taut run from the gate to the ledge, hovering
// over the fins. Drawn just under the lintel and a hair above the lands, so
// it touches neither, and 0.3 mm thick so that it shows.
module tape(od = roll_od_shown) {
    t = 0.3;
    lift = 0.02;
    n = racks * fins_per_rack;
    px = x_gate - lintel_w / 2;  pz = z_gate + lintel_ch_h;   // where the tape meets the gate
    dx = x_axis - px;  dz = z_axis - pz;
    d = sqrt(dx * dx + dz * dz);
    th = atan2(dz, dx) - asin(od / 2 / d);                    // upper tangent off the roll
    tl = sqrt(d * d - od * od / 4);
    x_tail = fin_x(n) + ledge_l / 2 + 8;                      // where the tails end, past the ledge
    // [x, z of the tape's underside]: off the roll and under the gate, then
    // either down onto fin 0, or straight to the near edge of the ledge
    feed = [[px + tl * cos(th), pz + tl * sin(th)], [px - 0.2, pz - t - 0.1],
            [x_gate - lintel_flat / 2, z_gate - t - lift], [x_gate + lintel_flat / 2, z_gate - t - lift]];
    path = concat(feed, tape_pose == "pulled"
        ? [[fin_x(n) - ledge_l / 2, z_land + lift], [x_tail, z_land + lift]]
        : [[fin_x(0), z_land + lift], [fin_x(0) + strip_len / 2 - 1, z_land + lift]]);
    for (k = [0 : lanes - 1]) {
        for (s = [0 : len(path) - 2])
            hull() for (p = [path[s], path[s + 1]])
                translate([p[0], lane_c(k) - tape_w / 2, p[1]]) cube([eps, tape_w, t]);
        if (tape_pose == "cut") {
            if (n > 1)
                for (i = [1 : n - 1])
                    translate([fin_x(i) - strip_len / 2 + 1, lane_c(k) - tape_w / 2, z_land + lift])
                        cube([strip_len - 2, tape_w, t]);
            translate([fin_x(n) - strip_len / 2 + 1, lane_c(k) - tape_w / 2, z_land + lift])
                cube([x_tail - (fin_x(n) - strip_len / 2 + 1), tape_w, t]);
        }
    }
}

// ---------------------------------------------------------------------------
// Assembly, coupon, fit proofs
// ---------------------------------------------------------------------------
module assembly() {
    color("#c0343c") {
        cradle();
        for (i = [0 : racks - 1]) translate([i * rack_l, 0, (i + 1) * explode]) rack();
        translate([racks * rack_l, 0, (racks + 1) * explode]) end_cap();
    }
    color("#8f2029") spindle_use();
    // The rolls and the tape are illustration: drawn only when asked for.
    if (show_payload) {
        color("#f1ead8") rolls();
        if (explode == 0) color("#ffffff", 0.75) tape();
    }
}

// Section along the tape: the path from roll, under the gate, onto the
// fins. Cut through the middle of the first lane, or (cut_at = "key")
// through the joint's key — half a millimetre inside the next lane when the
// centre of the rack is a post, so that lane's tape still shows beyond.
module cutaway() {
    y_cut = cut_at == "key" ? W / 2 + (lanes % 2 == 0 ? post_w / 2 + 0.5 : 0) : lane_c(0);
    difference() {
        assembly();
        color("#5a5a5a") translate([-cradle_l - heel_ext - 20, -1, -1])
            cube([cradle_l + heel_ext + racks * rack_l + cap_l + 40, y_cut + 1, 120]);
    }
}

// Two rack segments nested for storage: the second turned over and shifted
// half a pitch, its fins in the first one's gaps, 0.2 mm of air between
// them. `shift` exists for the fit proof's control.
module nested_pose(shift = strip_len / 2) {
    translate([shift, W, 2 * base_h + fin_h + post_rise + 0.2]) rotate([180, 0, 0]) children();
}
module nested_pair(shift = strip_len / 2) {
    rack();
    nested_pose(shift) children();
}
// Drawn in two tones, so the two segments read as two.
module nested() {
    color("#c0343c") rack();
    color("#e9b3b7") nested_pose() rack();
}
module nest_fit(shift = strip_len / 2) {
    intersection() {
        rack();
        translate([shift, W, 2 * base_h + fin_h + post_rise + 0.2]) rotate([180, 0, 0]) rack();
    }
}

// Short stubs carrying the production key and the production socket, as
// wide as the rack itself — a narrower stub would have springier socket
// arms than the joint it stands in for.
coupon_w = W;
module key_stub() {
    bed_box(-18, 0, -coupon_w / 2, coupon_w / 2, base_h, cx1 = false);
    key_solid();
}
module socket_stub(clear = joint_clear) {
    difference() {
        bed_box(joint_gap, joint_gap + 18, -coupon_w / 2, coupon_w / 2, base_h, cx0 = false);
        socket_cut(clear);
    }
}

// "Print this first": the production key and the production socket as two
// loose stubs, side by side on the bed. Lower the socket stub onto the key
// stub and tune joint_clear before printing a rack.
module joint_coupon() {
    translate([18, coupon_w / 2, 0]) key_stub();
    translate([18 + joint_reach + 6, coupon_w / 2, 0]) socket_stub();
}

// Preview only: the same two stubs as a pair, the socket stub lifted
// straight off the key stub — the one way the joint comes apart — and
// drawn lighter, so the key and the socket each read whole.
joint_pair_lift = 20;
module joint_pair() {
    color("#c0343c") key_stub();
    color("#e9b3b7") translate([0, 0, joint_pair_lift]) socket_stub();
}

// Fit proofs for the joint, on the two stubs posed as joined.
// As joined: empty at the production clearance; a negative clearance is the
// control that must interfere.
module joint_fit(clear = joint_clear) {
    intersection() { key_stub(); socket_stub(clear); }
}
// Pulled 3 mm apart along the tape: must interfere — the joint holds.
module joint_pull() {
    intersection() { key_stub(); translate([3, 0, 0]) socket_stub(); }
}
// Key part lifted 3 mm with the socket part left behind: must interfere —
// a straight lift of the key part catches the socket part.
module joint_lift() {
    intersection() { translate([0, 0, 3]) key_stub(); socket_stub(); }
}
// Socket part lifted 3 mm: must be empty — that is how it comes apart.
module joint_drop() {
    intersection() { key_stub(); translate([0, 0, 3]) socket_stub(); }
}
// Fit proof: the spindle in its saddle pockets and between the walls.
module spindle_fit(grow = 0) {
    intersection() { cradle(); spindle_use(grow); }
}
// Fit proof: the largest roll the brief names, on the spindle, in the
// cradle — clear of the floor, the walls, the gate and the flange.
module roll_fit(extra = 0) {
    intersection() {
        union() { cradle(); spindle_use(); }
        rolls(roll_od_max + extra);
    }
}

if (part == "cradle") cradle();
else if (part == "spindle") spindle();
else if (part == "rack") rack();
else if (part == "end-cap") end_cap();
else if (part == "joint-coupon") joint_coupon();
else if (part == "joint-fit") joint_fit();
else if (part == "joint-fit-ctrl") joint_fit(-0.15);
else if (part == "joint-pull") joint_pull();
else if (part == "joint-lift") joint_lift();
else if (part == "joint-drop") joint_drop();
else if (part == "spindle-fit") spindle_fit();
else if (part == "spindle-fit-ctrl") spindle_fit(saddle_clear + 0.6);
else if (part == "roll-fit") roll_fit();
else if (part == "roll-fit-ctrl") roll_fit(2 * roll_floor_clear + 2);
else if (part == "nest-fit") nest_fit();
else if (part == "nest-fit-ctrl") nest_fit(shift = 0);
else if (part == "nested") nested();
else if (part == "joint-pair") joint_pair();
else if (part == "cutaway") cutaway();
else if (part == "assembly") assembly();
else assert(false, str("unknown part: ", part));
