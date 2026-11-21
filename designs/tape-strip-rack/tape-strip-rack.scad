// tape-strip-rack — a blade-free multi-strip tape station: two rolls on a
// drop-in spindle, a row of thin fins, and a hold-down gate that lays both
// tapes onto every fin top in one pull. Snip mid-gap with scissors and every
// strip is left stuck by its middle to one fin, both ends free to grab.
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
// never printed), or the cutaway section.
part = "assembly"; // [assembly, cradle, spindle, rack, end-cap, joint-coupon, joint-fit, joint-fit-ctrl, spindle-fit, spindle-fit-ctrl, roll-fit, roll-fit-ctrl, cutaway]

/* [Tape — what it must hold] */
// Tape width (mm). 19 = 3/4 in desk tape. The lane formula takes 12 to 25.
tape_w = 19;
// Inner diameter of the roll's core (mm). 25.4 = the common 1 in core.
// Caliper your own roll before printing the spindle.
core_id = 25.4;
// Largest roll outer diameter the cradle clears (mm).
roll_od_max = 62;
// Rolls side by side (count). Each gets its own lane.
lanes = 2;

/* [Strips] */
// Strip length = fin pitch (mm). 40 is about 1.5 in; 50 gives 2 in strips
// (set fins_per_rack = 4 to keep a segment on a 220 mm bed).
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
// than at the top, so a socket part can only be lowered onto it — and
// lifting the key part carries the socket part with it.
joint_draft = 10;
// Clearance between key and socket, each face (mm). THE tuned fit: print
// the joint coupon and adjust in 0.05 steps (see NOTES.md).
joint_clear = 0.2;
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
// Lean of the saddle slots, back from vertical (degrees). The tape always
// pulls the spindle forward and down, into the seat.
saddle_lean = 25;
// Depth of the blind saddle pockets in each wall (mm). The skin left
// outside stops the spindle sliding out sideways.
saddle_pocket = 2.8;
// How far above the tape plane the hold-down gate sits (mm). The tapes
// pass under it, so a level pull clears every fin and the tape only touches
// down when you lower it — and no pull can lift the spindle.
gate_rise = 3;
// Clear distance between the largest roll and the gate (mm) — finger room
// for threading.
gate_roll_clear = 8;

/* [End cap] */
// Length of the tail ledge along the tape (mm).
ledge_l = 12;

/* [Preview] */
// Show the rolls and the tape in the assembled preview. Set false for a
// product shot, where they would render as printed plastic.
show_payload = true;
// Roll diameter drawn in the preview (mm).
preview_roll_od = 50;
// Lift each part off its upstream neighbour by this much (mm) to show how
// the joint goes together. 0 = assembled.
explode = 0;

/* [Quality] */
// Curve resolution. Only the spindle and the saddle slots are round, so the
// production value costs nothing: 96.
$fn = 96;

// ---------------------------------------------------------------------------
// Derived
// ---------------------------------------------------------------------------
eps = 0.01;
ov = 0.4;                       // union overlap: nothing meets face-to-face
bed_ch = 0.5;                   // bed-edge chamfer, horizontal leg
bed_ch_h = 0.6;                 // bed-edge chamfer, vertical leg (50 deg)
z_in = 1.2;                     // where the cradle's upper pieces start, inside the floor
joint_ef = 0.4;                 // first-layer relief on key and socket
joint_ef_h = 0.5;
joint_tip_cut = 0.8;            // key tip corners cut back (corner relief)
mouth_relief = 1.6;             // how far each socket lip is squared back
joint_flank = atan((joint_tip - joint_neck) / 2 / (joint_depth + ov));   // flank angle off the X axis
joint_lead = 0.5;               // lead-in chamfer round the socket rim

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
x_axis = x_gate - lintel_w / 2 - gate_roll_clear - roll_od_max / 2;   // -47.9
back_t = 3;
back_inset = 0.8;               // the back wall sits this far inside the wall ends
plinth = 0.4;                   // the floor runs this far past the wall ends, so no two faces share a plane
cradle_l = -x_axis + roll_od_max / 2 + 3 + back_t + back_inset + plinth;   // 86.1
z_wall_top = z_axis + r_s + 9;                       // 58
cradle_in_w = W - 2 * post_w;                        // 48.4
spindle_play = 0.8;                                  // axial float of the spindle, total
spindle_l = cradle_in_w + 2 * saddle_pocket - spindle_play;   // 53.2
flange_d = core_id + 3.6;                            // 29
flange_flat = 1.2;
flange_cone = (flange_d - hub_d) / 2 / tan(40);      // 2.62: a 40-deg-from-vertical shoulder
cap_l = strip_len / 2 + ledge_l / 2 + 5;             // 31

function lane_y0(k) = post_w + k * (lane_w + post_w);
function lane_c(k) = lane_y0(k) + lane_w / 2;
function post_y0(j) = j * (lane_w + post_w);
function fin_x(i) = strip_len / 2 + i * strip_len;
function draft_run(z) = (base_h - z) * tan(joint_draft);
// outline of the socket at the bed: the widest the joint ever gets
joint_bed_w = joint_tip + 2 * (draft_run(0) + joint_clear + joint_ef);
// widest the squared mouth gets
mouth_bed_w = joint_neck + 2 * (mouth_relief + draft_run(0) + joint_clear);

// Guards: the brief's numbers and the print floors as render failures.
assert(lanes >= 1 && lanes == floor(lanes), "lanes must be a whole number, 1 or more");
assert(tape_w >= 12 && tape_w <= 25, str("tape_w ", tape_w, " is outside the 12-25 mm the lane formula was sized for"));
assert(hub_d > 0 && hub_clear >= 0.4, "hub_clear under 0.4 mm will bind on a real roll core");
assert(land_l >= 1.2 && fin_root_l >= land_l, str("fin ", land_l, " -> ", fin_root_l, " mm: the land must be at least 1.2 and the root no thinner than the land"));
assert(post_tip >= 0.8 && post_tip <= post_w, "post_tip must be between 0.8 mm and post_w");
assert(land_ribs == 0 || (land_rib_w >= 0.8 && land_ribs * land_rib_w <= tape_w - 2.4),
       str(land_ribs, " ribs of ", land_rib_w, " mm do not fit under a ", tape_w, " mm tape"));
assert(fin_h >= 25, str("fin_h ", fin_h, " leaves less than the brief's 25 mm of scissor room under a strip"));
assert(strip_len - post_root_l >= 28,
       str("only ", strip_len - post_root_l, " mm between fins — under the brief's 28 mm for scissors and a thumb. Raise strip_len."));
assert(rack_l + joint_depth + draft_run(0) <= 210,
       str("a rack segment is ", rack_l + joint_depth + draft_run(0), " mm long — over the brief's 210 mm. Lower fins_per_rack."));
assert(z_wall_top <= 200, "the cradle is over the 200 mm the test-slice allows");
assert((W - joint_bed_w) / 2 >= 6,
       str("only ", (W - joint_bed_w) / 2, " mm of base beside the socket — under 6 mm. Narrow the joint or widen the lanes."));
assert(joint_clear > 0 || part == "joint-fit-ctrl", "joint_clear must be positive: zero clearance prints as a weld");
assert(joint_draft >= 5 && joint_draft <= 20, "joint_draft outside 5-20 deg: too little to carry the chain, or too much to print");
assert(joint_gap + joint_depth + draft_run(0) + joint_clear + 3 <= strip_len / 2 - post_root_l / 2,
       "the socket runs into the first fin — lower joint_depth or raise strip_len");
assert(post_w - saddle_pocket >= 1.2, str("only ", post_w - saddle_pocket, " mm of wall outside the saddle pocket — under 1.2 mm"));
assert(lane_w <= 30, str("the gate bridges ", lane_w, " mm per lane — over 30 mm it will sag without support"));
assert(z_gate - base_h >= 15, "the threading window under the gate is under 15 mm tall");
assert(post_w + 2 * lane_clear - flange_flat - 2 * flange_cone >= 0.4,
       "the spindle flange does not fit between two rolls — widen post_w or lane_clear");
assert(preview_roll_od <= roll_od_max && preview_roll_od > core_id + 4, "preview_roll_od must sit between the core and roll_od_max");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
// Extrude a 2D profile drawn in (x, z) across Y, from y0 for w.
module y_extrude(w, y0 = 0) {
    translate([0, y0 + w, 0]) rotate([90, 0, 0]) linear_extrude(w) children();
}

// A box on the bed with its bed edge chamfered at 50 degrees. An end that
// carries a joint keeps a square edge (cx0 / cx1 = false): the joint has its
// own first-layer relief, and a chamfer there would leave feather edges.
module bed_box(x0, x1, y0, y1, h, cx0 = true, cx1 = true) {
    a = cx0 ? bed_ch : 0;
    b = cx1 ? bed_ch : 0;
    hull() {
        translate([x0 + a, y0 + bed_ch, 0])
            cube([x1 - x0 - a - b, y1 - y0 - 2 * bed_ch, eps]);
        translate([x0, y0, bed_ch_h]) cube([x1 - x0, y1 - y0, h - bed_ch_h]);
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
// The socket's mouth, squared off so its two lips end in a 2 mm flat, not a
// 60-degree knife edge.
module mouth_profile() {
    // long enough to end inside the dovetail at every height, so no sliver
    // of base is left between the mouth and the flank
    translate([-ov - 1, -joint_neck / 2 - mouth_relief])
        square([ov + 1 + joint_gap + mouth_relief / tan(joint_flank) + 0.4,
                joint_neck + 2 * mouth_relief]);
}
module joint_slab(z, d, tip_cut = 0) {
    translate([0, 0, z]) linear_extrude(eps) offset(delta = d) joint_profile(tip_cut);
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
// The socket cutter: the key's loft grown by `clear` on every face and run
// past both ends of the base, with a squared mouth following the same
// draft, a relief flare at the bed and a lead-in chamfer round the rim.
// Each extra piece starts just inside the main loft, so the surfaces cross
// cleanly instead of meeting edge-on.
module socket_cut(clear = joint_clear) {
    hull() {
        joint_slab(-1, draft_run(-1) + clear);
        joint_slab(base_h + 1, draft_run(base_h + 1) + clear);
    }
    hull() {
        translate([0, 0, -1]) linear_extrude(eps)
            offset(delta = draft_run(-1) + clear) mouth_profile();
        translate([0, 0, base_h + 1]) linear_extrude(eps)
            offset(delta = draft_run(base_h + 1) + clear) mouth_profile();
    }
    hull() {
        joint_slab(-eps, draft_run(0) + clear + joint_ef);
        joint_slab(joint_ef_h, draft_run(joint_ef_h) + clear - 0.02);
    }
    for (q = [0, 1])
        hull() {
            translate([0, 0, base_h - joint_lead]) linear_extrude(eps)
                offset(delta = draft_run(base_h - joint_lead) + clear - 0.02)
                    if (q == 0) joint_profile(); else mouth_profile();
            translate([0, 0, base_h]) linear_extrude(eps)
                offset(delta = clear + joint_lead)
                    if (q == 0) joint_profile(); else mouth_profile();
        }
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
    inset = 1.2;
    y_tape = lane_c(k) - tape_w / 2;
    pitch = land_ribs > 1 ? (tape_w - 2 * inset - land_rib_w) / (land_ribs - 1) : 0;
    function rib_y(i) = land_ribs > 1 ? y_tape + inset + i * pitch : lane_c(k) - land_rib_w / 2;
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

// The end cap: a socket, and one wide fin whose flat top is the ledge the
// tape tails are stuck to. It sits one pitch past the last fin, so the last
// fin still yields a full-length strip.
module end_cap() {
    difference() {
        union() {
            bed_box(joint_gap, cap_l, 0, W, base_h, cx0 = false);
            fin(strip_len / 2, land = ledge_l, root = ledge_l + 2, ribs = 0);
        }
        translate([0, W / 2, 0]) socket_cut();
    }
}

// Cradle side-wall profile in (x, z): tall round the saddle, sloping down
// to the gate. It starts inside the floor (z_in), which carries the bed
// chamfer; every piece of the cradle overlaps its neighbours instead of
// meeting them on a shared edge.
module cradle_wall_2d() {
    // top of the hook in front of the saddle slot, 6 mm clear of the slot
    x_slot_top = x_axis + r_s * cos(saddle_lean)
               - (z_wall_top - z_axis - r_s * sin(saddle_lean)) * tan(saddle_lean);
    xb = -cradle_l + plinth;      // the walls stop just short of the floor's back edge
    polygon([[xb, z_in], [0, z_in], [0, z_gate_top],
             [x_gate - lintel_w / 2 - 0.5, z_gate_top],
             [x_slot_top + 6, z_wall_top],
             [xb + 5, z_wall_top], [xb, z_wall_top - 5]]);
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

// The cradle. Downstream face at x = 0, the key projecting beyond it.
module cradle() {
    difference() {
        union() {
            bed_box(-cradle_l, 0, 0, W, floor_t, cx1 = false);
            // nose block: full joint height, carries the key and the gate
            translate([-nose_l, post_w - ov, z_in])
                cube([nose_l, cradle_in_w + 2 * ov, base_h - z_in]);
            // low back wall, set in from the wall ends
            translate([-cradle_l + plinth + back_inset, post_w - ov, z_in])
                cube([back_t, cradle_in_w + 2 * ov, 14 - z_in]);
            // side walls; their nose ends are the outer gate posts
            y_extrude(post_w, 0) cradle_wall_2d();
            y_extrude(post_w, W - post_w) cradle_wall_2d();
            // inner gate posts, one between each pair of lanes; each ends
            // inside the lintel
            if (lanes > 1)
                for (j = [1 : lanes - 1])
                    translate([x_gate - lintel_w / 2 + 0.3, post_y0(j), base_h - ov])
                        cube([lintel_w - 0.6, post_w, z_gate + lintel_ch_h + 1 - base_h + ov]);
            // the lintel, bridging each lane from post to post
            y_extrude(cradle_in_w + 2 * ov, post_w - ov) lintel_2d();
            translate([0, W / 2, 0]) key_solid();
        }
        // blind saddle pockets, cut into the inner face of each wall
        y_extrude(saddle_pocket + eps, post_w - saddle_pocket) saddle_2d();
        y_extrude(saddle_pocket + eps, W - post_w - eps) saddle_2d();
    }
}

// The spindle, standing on end (its print orientation): one hub for every
// roll, a small flange with 40-degree shoulders between each pair. One
// revolved profile, so there is no union to seam. `grow` oversizes the hub
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
    rotate_extrude()
        polygon(concat([[0, 0], [r - 0.4, 0], [r, 0.6]], flanges,
                       [[r, spindle_l - 0.6], [r - 0.4, spindle_l], [0, spindle_l]]));
}
// The spindle laid in its saddles.
module spindle_use(grow = 0) {
    translate([x_axis, post_w - saddle_pocket + spindle_play / 2, z_axis])
        rotate([-90, 0, 0]) spindle(grow);
}

// ---------------------------------------------------------------------------
// Payload (preview and fit proofs only — never printed)
// ---------------------------------------------------------------------------
module rolls(od = preview_roll_od) {
    for (k = [0 : lanes - 1])
        translate([x_axis, lane_c(k) - tape_w / 2, z_axis]) rotate([-90, 0, 0])
            difference() {
                cylinder(d = od, h = tape_w);
                translate([0, 0, -1]) cylinder(d = core_id, h = tape_w + 2);
            }
}

// The tape after the cuts: the feed from the roll under the gate to its
// parked tail past fin 0, one strip centred on every later fin, and the
// tails on the end-cap ledge.
module tape(od = preview_roll_od) {
    t = 0.3;
    n = racks * fins_per_rack;
    px = x_gate - lintel_w / 2;  pz = z_gate + lintel_ch_h;   // where the tape meets the gate
    dx = x_axis - px;  dz = z_axis - pz;
    d = sqrt(dx * dx + dz * dz);
    th = atan2(dz, dx) - asin(od / 2 / d);                    // upper tangent off the roll
    tl = sqrt(d * d - od * od / 4);
    path = [[px + tl * cos(th), pz + tl * sin(th)], [px, pz],
            [x_gate - lintel_flat / 2, z_gate], [x_gate + lintel_flat / 2, z_gate],
            [fin_x(0), z_land], [fin_x(0) + strip_len / 2 - 1, z_land]];
    for (k = [0 : lanes - 1]) {
        for (s = [0 : len(path) - 2])
            hull() for (p = [path[s], path[s + 1]])
                translate([p[0], lane_c(k) - tape_w / 2, p[1]]) cube([eps, tape_w, t]);
        for (i = [1 : n - 1])
            translate([fin_x(i) - strip_len / 2 + 1, lane_c(k) - tape_w / 2, z_land])
                cube([strip_len - 2, tape_w, t]);
        translate([fin_x(n) - strip_len / 2 + 1, lane_c(k) - tape_w / 2, z_land])
            cube([strip_len / 2 - 1 + ledge_l / 2 + 8, tape_w, t]);
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
    if (show_payload) {
        color("#f1ead8") rolls();
        if (explode == 0) color("#ffffff", 0.75) tape();
    }
}

// Section through the middle of the first lane: the tape path from roll,
// under the gate, onto the fins.
module cutaway() {
    difference() {
        assembly();
        translate([-cradle_l - 20, -1, -1]) cube([cradle_l + racks * rack_l + cap_l + 40, lane_c(0) + 1, 120]);
    }
}

// Short stubs carrying the production key and the production socket.
module key_stub(w) {
    bed_box(-18, 0, -w / 2, w / 2, base_h, cx1 = false);
    key_solid();
}
module socket_stub(w, clear = joint_clear) {
    difference() {
        bed_box(joint_gap, joint_gap + 18, -w / 2, w / 2, base_h, cx0 = false);
        socket_cut(clear);
    }
}

// "Print this first": the production key and the production socket as two
// loose stubs, side by side on the bed. Lower the socket stub onto the key
// stub and tune joint_clear before printing a rack.
module joint_coupon() {
    w = joint_bed_w + 12;
    translate([18, w / 2, 0]) key_stub(w);
    translate([18 + joint_depth + draft_run(0) + 6, w / 2, 0]) socket_stub(w);
}

// Fit proof: key in socket, posed exactly as joined. Empty at the production
// clearance; a negative clearance is the control that must interfere.
module joint_fit(clear = joint_clear) {
    w = joint_bed_w + 12;
    intersection() { key_stub(w); socket_stub(w, clear); }
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
else if (part == "spindle-fit") spindle_fit();
else if (part == "spindle-fit-ctrl") spindle_fit(saddle_clear + 0.6);
else if (part == "roll-fit") roll_fit();
else if (part == "roll-fit-ctrl") roll_fit(2 * roll_floor_clear + 2);
else if (part == "cutaway") cutaway();
else if (part == "assembly") assembly();
else assert(false, str("unknown part: ", part));
