// N.U.G.G.S. wheel — the exercise module: a segmented rim wheel on a
// NUGGS-port-anchored free-standing stand. Design brief: issue #834.
// Requirements, welfare numbers and decisions: see NOTES.md next to this
// file. All dimensions in millimeters.
//
// WHY THIS MODULE EXISTS. The ecosystem covers food, air, light/reach,
// routing, refuge and grooming — but nothing for locomotion. An exercise
// wheel is the standard welfare kit a hamster habitat has. The rim is
// printed in identical segments because a Syrian-appropriate Ø280 mm wheel
// exceeds the gate's 200 mm test-slice ceiling (#673) — segmentation is the
// design premise, not a compromise (alcove-rod-socket / ci.plate discipline).
//
// THE PORT. One face of the standard genderless coupling on the stand,
// taken bore-clean from the library via nuggs_neck(). Every coupling number
// is nuggs_cfg()'s default so the stand clicks into every existing module.
// port_tol is UNMEASURED — the coupon is mandatory.
//
// PRINT. Rim segment and hub print flat (back on the bed). Stand prints on
// its foot base with the port axis horizontal, ring bottom on the bed so
// the coupling does not face the bed as an overhang. Axle prints on its
// side. No slicer supports. PETG preferred for the rim; PLA ok for the stand.

use <nuggs-coupling.scad>

/* [What to render] */
// rim-segment / hub / stand / axle = printable parts;
// coupon = port stub + segment-joint pair + axle-in-bore;
// assembled / cutaway = review previews (never the sliceable deliverable);
// mates* / axle-fit* / joint-fit* = ci.fitchecks booleans (never printed)
part = "assembled"; // [rim-segment, hub, stand, axle, coupon, assembled, cutaway, mates, mates-ctrl, axle-fit, axle-fit-ctrl, joint-fit, joint-fit-ctrl]

/* [The NUGGS standard - change these and nothing you already printed fits] */
// Internal bore (mm) — the headline number. Asserted >= min_bore_mm by the lib
bore_d = 80.0;
// Tube shell thickness (mm). ro = bore_d/2 + wall is the coupling datum
wall = 2.4;
// Radial depth of the coupling ring beyond the tube OD (mm)
lug_r = 6.0;
// Axial projection of the coupling sectors past the tube face (mm)
port_proj = 10.0;
// Backing-collar thickness (mm)
collar_t = 3.0;
// Sectors per port face (3 is kinematically determinate)
n_lug = 3;
// THE fit knob, mm, everywhere. UNMEASURED — tune on the coupon in +/-0.05
port_tol = 0.30;

/* [Wheel] */
// Running-surface diameter (mm). Syrian welfare floor commonly cites ≥280;
// a parameter the owner sets to their animal — same logic as min_bore
wheel_d = 280;
// Running width (mm). Wider than the 80 mm bore so shoulders clear on entry
wheel_w = 90;
// Identical rim segments. Derived from the ≤180 mm part bound at Ø280
n_seg = 8;
// Rim wall thickness (mm) — ≥1.2 FDM floor
rim_t = 2.4;
// Closed back disc thickness (mm)
back_t = 2.4;
// Small outer lip above the running surface (mm) — keeps paws on the tread
lip_h = 3.0;
// Max bounding dimension any printable part may claim (mm) — #673 ceiling
// with margin under the 200 mm test-slice bound
max_part_bound = 180;

/* [Segment joint] */
// Circumferential lap of the shingle joint (mm). Along the run direction so
// there is never a butt gap a toe can drop into
joint_lap = 8.0;
// Radial step at the running-surface seam (mm). Asserted ≤ joint_step_max
joint_step = 0.20;
joint_step_max = 0.25;
// Locating peg diameter at each lap (mm)
joint_peg_d = 2.4;
// Clearance on the peg bore (mm)
joint_peg_clear = 0.20;

/* [Hub & axle] */
// Hub flange outer diameter (mm) — the ring the segment inner lips meet
hub_od = 48;
// Hub barrel length along the axle (mm)
hub_len = 22;
// Printed axle diameter (mm)
axle_d = 8.0;
// Diametral clearance in the plain bearing bore (mm). Quiet running is a
// product requirement — tune on the coupon in +/-0.05 steps
axle_clear = 0.35;
// Axle length past each bearing face (mm) — retention / washers
axle_overhang = 6.0;
// Hub-to-segment fastener: printed post diameter (mm)
hub_post_d = 3.2;
hub_post_clear = 0.25;
hub_post_h = 4.0;

/* [Stand] */
// Footprint depth along the wheel axis view (mm). ≥ 0.6 × wheel Ø for tip
// stability under a running animal (ci.cog gates the assembled stand)
stand_depth_mult = 0.60;
// Footplate width (mm) — ≥ 2·r_out so the port ring sits on the foot
stand_w = 100;
// Footplate thickness (mm)
stand_base_t = 3.6;
// Upright / axle-arm wall (mm)
stand_wall = 2.8;
// Clearance under the rim at bottom dead centre (mm)
wheel_floor_clear = 4.0;
// Axle arm thickness (mm)
arm_t = 8.0;
// Bearing boss OD on the stand arm (mm)
stand_boss_od = 18;
// Bearing boss length (mm)
stand_boss_l = 12;
// Port neck full-round length past the port zone (mm)
stand_port_neck = 18;

/* [Quality] */
// Visible cylinders. The coupling pins its own tessellation inside the lib
$fn = 96;  // production; drop to 48 while iterating

// ---------------------------------------------------------------------------
// Derived
// ---------------------------------------------------------------------------
function cfg_d() =
    nuggs_cfg(bore_d = bore_d, wall = wall, lug_r = lug_r,
              port_proj = port_proj, collar_t = collar_t, n_lug = n_lug,
              port_tol = port_tol);

ri          = nuggs_ri(cfg_d());
ro          = nuggs_ro(cfg_d());
r_out       = nuggs_r_out(cfg_d());
z_top       = nuggs_z_top(cfg_d());

r_run       = wheel_d / 2;                 // running-surface radius
r_outer     = r_run + rim_t;               // rim OD
r_hub       = hub_od / 2;
seg_ang     = 360 / n_seg;                 // nominal sector
// Each segment spans a little past nominal so the shingles overlap
seg_span    = seg_ang + joint_lap / r_run * 180 / PI;
axle_bore_d = axle_d + 2 * axle_clear;
axle_len    = wheel_w + 2 * stand_boss_l + 2 * axle_overhang;
stand_depth = stand_depth_mult * wheel_d;
axle_z      = r_run + wheel_floor_clear;   // axle height above floor
// Post circle — inset from the flange OD so posts fully union into the hub
r_post      = r_hub - hub_post_d;
// Inner radius of the back pie — reaches inside the post circle so the
// mount pads union into the pie (pad radius ≈ hub_post_d/2 + 1.2)
r_pie_in    = r_post - (hub_post_d / 2 + 1.6);

// Bounding-box diagonal of one annular-sector segment (back flat on bed).
// Conservative: outer chord + radial span, ignoring the lap's small add.
_seg_chord  = 2 * r_outer * sin(seg_span / 2);
_seg_radial = r_outer - r_pie_in;
_seg_diag   = sqrt(_seg_chord * _seg_chord + _seg_radial * _seg_radial);

// ---------------------------------------------------------------------------
// Asserts — welfare and the part-bound premise
// ---------------------------------------------------------------------------
assert(wheel_d >= 200, str(
    "WHEEL D: wheel_d = ", wheel_d, " mm is under the 200 mm absolute floor",
    " (Syrian welfare practice never below 200; default 280)."));
assert(wheel_w >= bore_d, str(
    "WHEEL W: wheel_w = ", wheel_w, " mm is under bore_d = ", bore_d,
    " mm — the animal enters from the open front through the habitat bore;",
    " a narrower tread pinches shoulders."));
assert(n_seg >= 6 && n_seg == floor(n_seg), str(
    "N SEG: n_seg = ", n_seg, " must be an integer ≥ 6 so each segment clears",
    " the ", max_part_bound, " mm part bound at Syrian-scale Ø."));
assert(_seg_diag <= max_part_bound, str(
    "PART BOUND: rim-segment XY diagonal ≈ ", _seg_diag, " mm exceeds",
    " max_part_bound = ", max_part_bound, " mm (#673). Raise n_seg or lower",
    " wheel_d."));
assert(joint_step > 0 && joint_step <= joint_step_max, str(
    "JOINT STEP: joint_step = ", joint_step, " mm must be in (0, ",
    joint_step_max, "] — a seam over 0.25 mm is a toe-pinch risk."));
assert(joint_lap >= 4, str(
    "JOINT LAP: joint_lap = ", joint_lap, " mm is under 4 mm — the shingle",
    " needs enough overlap that a butt gap cannot open under flex."));
assert(axle_d >= 6 && axle_d <= 12, str(
    "AXLE: axle_d = ", axle_d, " mm outside the 6–12 mm printed plain-bearing",
    " band this design targets."));
assert(axle_clear >= 0.15 && axle_clear <= 0.80, str(
    "AXLE CLEAR: axle_clear = ", axle_clear, " mm outside 0.15–0.80 — tune on",
    " the coupon; quiet running lives here."));
assert(rim_t >= 1.2 && back_t >= 1.2 && stand_wall >= 1.2, str(
    "WALL FLOOR: rim_t/back_t/stand_wall must be ≥ 1.2 mm (three perimeters)."));
assert(stand_depth_mult >= 0.55, str(
    "STAND FOOT: stand_depth_mult = ", stand_depth_mult, " is under 0.55 —",
    " tip stability under a running animal wants ≥ 0.6 × wheel Ø."));
assert(hub_od < 0.4 * wheel_d, str(
    "HUB: hub_od = ", hub_od, " mm is too large vs wheel_d — the hub must stay",
    " a small central part under the part bound."));
assert(stand_depth <= max_part_bound || stand_w <= max_part_bound, str(
    "STAND BOUND: both stand_depth and stand_w exceed max_part_bound — at",
    " least one footprint axis must clear ", max_part_bound, " mm."));
// Stand height (axle_z + boss) and foot depth are the two long axes
assert(axle_z + stand_boss_od / 2 <= max_part_bound, str(
    "STAND H: axle height + boss exceeds max_part_bound = ", max_part_bound));

// ---------------------------------------------------------------------------
// Rim segment — back flat on the bed, running surface extruded in +Z
// ---------------------------------------------------------------------------

// 2D annular sector from a to b (deg), radii rin..rout, centred on +X
module annular_sector_2d(rin, rout, a0, a1) {
    n = max(8, ceil(abs(a1 - a0)));
    da = (a1 - a0) / n;
    outer = [for (i = [0 : n]) let (a = a0 + i * da) [rout * cos(a), rout * sin(a)]];
    inner = [for (i = [0 : n]) let (a = a1 - i * da) [rin * cos(a), rin * sin(a)]];
    polygon(concat(outer, inner));
}

module rim_segment() {
    a0 = -seg_span / 2;
    a1 =  seg_span / 2;
    lap_ang = joint_lap / r_run * 180 / PI;
    // Rim wall spans the female pocket zone through the core; the male lap
    // zone is ONLY the recessed tongue (no full-thickness tread there).
    // 0.4° hairline at the core/tongue handoff so neighbouring full-thickness
    // cores never tessellate into a joint-fit interference sliver — the tongue
    // already overlaps the core by 1° and covers the gap.
    a_rim0 = a0;
    a_rim1 = a1 - lap_ang - 0.4;
    ov = 0.4;  // union bite — coplanar stacks export as separate volumes
    // Back pie stops short of the neighbour rim's start angle
    back_half = seg_ang / 2 - lap_ang / 2 - 0.5;
    difference() {
        union() {
            // Closed back pie — out to the running surface only (the tread
            // wall owns r ≥ r_run).
            linear_extrude(height = back_t)
                annular_sector_2d(r_pie_in, r_run + ov,
                                  -back_half, back_half);
            // Running-surface wall — slight downward bite into THIS segment's
            // own pie only (pie ends before the neighbour's rim begins)
            translate([0, 0, back_t - ov])
                linear_extrude(height = wheel_w + ov)
                    annular_sector_2d(r_run, r_outer, a_rim0, a_rim1);
            // Outer lip — same angular span as the rim wall, radial overlap
            translate([0, 0, back_t + wheel_w - lip_h - ov])
                linear_extrude(height = lip_h + ov)
                    annular_sector_2d(r_run + rim_t * 0.3, r_outer + lip_h,
                                      a_rim0, a_rim1);
            // Male shingle tongue: recessed by joint_step; angularly under-cut
            // by 0.3° vs the pocket so tessellation cannot invent interference
            translate([0, 0, back_t])
                linear_extrude(height = wheel_w)
                    annular_sector_2d(r_run + joint_step, r_outer - 0.5,
                                      a1 - lap_ang - 1, a1 - 0.3);
            // Locating pegs — short, fully inside the tongue
            for (z = [back_t + wheel_w * 0.30, back_t + wheel_w * 0.70])
                rotate([0, 0, a1 - lap_ang / 2])
                    translate([r_run + rim_t * 0.55, 0, z])
                        rotate([90, 0, 0])
                            cylinder(d = joint_peg_d, h = joint_lap * 0.6,
                                     center = true, $fn = 16);
            // Hub-mount pads at the pie inner edge
            for (s = [-1, 1])
                rotate([0, 0, s * seg_ang * 0.28])
                    translate([r_post, 0, 0])
                        cylinder(d = hub_post_d + 2.4, h = back_t + hub_post_h);
        }
        // Female pocket: slightly oversize vs the tongue
        translate([0, 0, back_t - 0.01])
            linear_extrude(height = wheel_w + 0.02)
                annular_sector_2d(r_run + joint_step - 0.05, r_outer - 0.3,
                                  a0 - 0.15, a0 + lap_ang + 0.15);
        // Peg bores in the female pocket
        for (z = [back_t + wheel_w * 0.30, back_t + wheel_w * 0.70])
            rotate([0, 0, a0 + lap_ang / 2])
                translate([r_run + rim_t * 0.55, 0, z])
                    rotate([90, 0, 0])
                        cylinder(d = joint_peg_d + 2 * joint_peg_clear,
                                 h = joint_lap * 1.0, center = true, $fn = 16);
        // Hub post holes
        for (s = [-1, 1])
            rotate([0, 0, s * seg_ang * 0.28])
                translate([r_post, 0, -0.1])
                    cylinder(d = hub_post_d + 2 * hub_post_clear,
                             h = back_t + hub_post_h + 0.2);
        // Lightening slots in the back pie
        for (k = [-1, 0, 1])
            rotate([0, 0, k * seg_ang * 0.22])
                translate([(r_pie_in + r_run) / 2, 0, -0.1])
                    cylinder(d = min(14, (r_run - r_pie_in) * 0.35),
                             h = back_t + 0.2, $fn = 32);
    }
}

// ---------------------------------------------------------------------------
// Hub — flat disc + bearing barrel + posts that enter the segment pads
// ---------------------------------------------------------------------------
module hub() {
    ov = 0.4;  // union bite — coplanar stacks export as separate volumes
    difference() {
        union() {
            // Flange the segment inner lips sit on
            cylinder(d = hub_od, h = back_t + ov);
            // Bearing barrel — overlaps the flange by ov
            translate([0, 0, back_t])
                cylinder(d = hub_od * 0.70, h = hub_len - back_t);
            // Posts into each segment (two per segment)
            for (i = [0 : n_seg - 1])
                for (s = [-1, 1])
                    rotate([0, 0, i * seg_ang + s * seg_ang * 0.28])
                        translate([r_post, 0, back_t - ov])
                            cylinder(d = hub_post_d, h = hub_post_h + ov, $fn = 24);
        }
        // Plain bearing bore
        translate([0, 0, -0.1])
            cylinder(d = axle_bore_d, h = hub_len + 0.2);
        // Chamfer lead-ins both ends (45°)
        translate([0, 0, -0.01])
            cylinder(d1 = axle_bore_d + 1.6, d2 = axle_bore_d, h = 0.8);
        translate([0, 0, hub_len - 0.79])
            cylinder(d1 = axle_bore_d, d2 = axle_bore_d + 1.6, h = 0.8);
    }
}

// ---------------------------------------------------------------------------
// Axle — plain Ø shaft, loose / repairable
// ---------------------------------------------------------------------------
module axle() {
    // Print on its side: flat, so orient with length on X for the part export
    // Default pose: along Z for assembled; printable pose flops it later
    cylinder(d = axle_d, h = axle_len, $fn = 48);
}

// Printable axle: on its side on the bed (length along X)
module axle_print() {
    rotate([0, 90, 0])
        translate([0, 0, -axle_len / 2])
            axle();
}

// ---------------------------------------------------------------------------
// Stand — USE frame: foot on z=0, port axis +X at the rear, axle arm up.
// PRINT pose (stand()): port-down on sector tips — the family bed-contact
// idiom. A horizontal port printed on the foot needed supports; printability
// wins over “foot on the bed” (brief orientation note → NOTES.md).
// ---------------------------------------------------------------------------
module stand_foot() {
    hull() {
        for (x = [stand_wall, stand_depth - stand_wall])
            for (y = [stand_wall, stand_w - stand_wall])
                translate([x, y, 0])
                    cylinder(r = stand_wall, h = stand_base_t, $fn = 32);
    }
}

module stand_arm() {
    arm_x = stand_depth * 0.55;
    arm_y = stand_w - stand_wall;
    upright_h = axle_z + stand_boss_od / 2;
    translate([arm_x - arm_t / 2, arm_y - stand_wall, 0])
        cube([arm_t, stand_wall, upright_h]);
    // 45° brace in the X–Z plane
    brace = axle_z * 0.50;
    translate([arm_x - arm_t / 2, arm_y - stand_wall, stand_base_t])
        rotate([0, -90, 0])
            linear_extrude(height = arm_t)
                polygon([[0, 0], [0, brace], [brace, 0]]);
    translate([arm_x, arm_y - stand_wall, axle_z])
        rotate([90, 0, 0])
            difference() {
                union() {
                    cylinder(d = stand_boss_od, h = stand_boss_l, $fn = 48);
                    translate([-stand_boss_od / 2, -stand_boss_od / 2, -1])
                        cube([stand_boss_od, stand_boss_od, 1.2]);
                }
                translate([0, 0, -1.1])
                    cylinder(d = axle_bore_d, h = stand_boss_l + 1.3, $fn = 48);
                translate([0, 0, -0.01])
                    cylinder(d1 = axle_bore_d + 1.6, d2 = axle_bore_d, h = 0.8);
            }
}

module stand_port() {
    neck_len = z_top + stand_port_neck;
    // Tube into the foot (+X), sectors out the back (−X)
    translate([0, stand_w / 2, r_out])
        rotate([0, 90, 0])
            nuggs_neck(cfg_d(), neck_len);
}

// Use-frame solid (foot down)
module stand_use() {
    difference() {
        union() {
            stand_foot();
            stand_arm();
            stand_port();
            // Fuse neck into the foot / upright root
            translate([0, stand_w / 2 - ro - 1, 0])
                cube([z_top + stand_port_neck * 0.5, 2 * ro + 2,
                      stand_base_t + r_out]);
        }
        translate([0, stand_w / 2, r_out])
            rotate([0, 90, 0])
                nuggs_bore_cut(cfg_d(), nuggs_z_tip(cfg_d()) - 1,
                               z_top + stand_port_neck + 1);
    }
}

// Printable stand — port axis vertical, standing on sector tips
module stand() {
    // Port centre in use frame: (0, stand_w/2, r_out). Map use +X → +Z.
    rotate([0, -90, 0])
        translate([0, -stand_w / 2, -r_out])
            stand_use();
}

// ---------------------------------------------------------------------------
// Coupon — port stub + segment-joint pair + axle-in-bore (production modules)
// ---------------------------------------------------------------------------
// Straight stand-ins for the curved shingle — same lap, step, peg sizes as
// production, flat on the bed so the coupon stays minutes-scale. The curved
// joint-fit ci.fitcheck gates the real sector geometry.
module coupon_joint_pair() {
    tw = 18;   // tread sample width
    th = 12;   // tread sample "along-run" length each half
    male_h = th + joint_lap;
    // Female half
    difference() {
        cube([rim_t, th + joint_lap, tw]);
        translate([joint_step, -0.01, -0.01])
            cube([rim_t, joint_lap + 0.02, tw + 0.02]);
        for (z = [tw * 0.30, tw * 0.70])
            translate([rim_t / 2, joint_lap / 2, z])
                rotate([0, 90, 0])
                    cylinder(d = joint_peg_d + 2 * joint_peg_clear,
                             h = rim_t + 2, center = true, $fn = 24);
    }
    // Male half (beside it)
    translate([rim_t + 6, 0, 0]) {
        cube([rim_t, th, tw]);
        translate([joint_step, th, 0])
            cube([rim_t - joint_step - 0.4, joint_lap, tw]);
        for (z = [tw * 0.30, tw * 0.70])
            translate([rim_t / 2, th + joint_lap / 2, z])
                rotate([0, 90, 0])
                    cylinder(d = joint_peg_d, h = rim_t - 0.4,
                             center = true, $fn = 24);
    }
}

module coupon_axle_bore() {
    bh = 16;
    difference() {
        cylinder(d = stand_boss_od, h = bh, $fn = 48);
        translate([0, 0, -0.1])
            cylinder(d = axle_bore_d, h = bh + 0.2, $fn = 48);
    }
    translate([stand_boss_od + 6, 0, 0])
        cylinder(d = axle_d, h = bh + 4, $fn = 48);
}

module wheel_coupon() {
    // Port stub at the origin (sector tips on the bed — family pose)
    nuggs_neck(cfg_d(), z_top + 8);
    // Axle / bore pair just outside the coupling ring
    translate([r_out + stand_boss_od + 8, 0, 0])
        coupon_axle_bore();
    // Segment-joint pair further out on the same bed plane as the sector tips
    translate([r_out + 8, r_out + 10, -nuggs_z_tip(cfg_d())])
        coupon_joint_pair();
}

// ---------------------------------------------------------------------------
// Assembled preview (not printable — use ci.plate for the deliverable)
// ---------------------------------------------------------------------------
module wheel_assembled_rim() {
    for (i = [0 : n_seg - 1])
        rotate([0, 0, i * seg_ang])
            rim_segment();
}

module assembled() {
    // Use-frame stand (foot on the floor)
    stand_use();
    arm_x = stand_depth * 0.55;
    arm_y = stand_w - stand_wall;
    wheel_y = arm_y - stand_wall - stand_boss_l - wheel_w / 2;
    translate([arm_x, wheel_y, axle_z]) {
        rotate([90, 0, 0])
            translate([0, 0, -wheel_w / 2 - back_t]) {
                wheel_assembled_rim();
                hub();
            }
        rotate([90, 0, 0])
            translate([0, 0, -axle_len / 2])
                axle();
    }
}

module cutaway() {
    difference() {
        assembled();
        translate([-500, stand_w / 2, -10])
            cube([1000, 500, 500]);
    }
}

// ---------------------------------------------------------------------------
// Fitchecks
// ---------------------------------------------------------------------------

// Stand port vs a library mate neck at the insertion clocking (library frame)
module fit_mates() {
    neck_len = z_top + stand_port_neck;
    intersection() {
        nuggs_neck(cfg_d(), neck_len);
        translate([0, 0, -0.01])
            rotate([0, 0, nuggs_clockings(cfg_d())[0]])
                mirror([0, 0, 1]) nuggs_neck(cfg_d(), 30);
    }
}

module fit_mates_ctrl() {
    neck_len = z_top + stand_port_neck;
    intersection() {
        nuggs_neck(cfg_d(), neck_len);
        translate([0, 0, -0.01])
            rotate([0, 0, 0])
                mirror([0, 0, 1]) nuggs_neck(cfg_d(), 30);
    }
}

// Axle inside the production bearing bore — must be empty (clearance)
module fit_axle() {
    bh = hub_len;
    intersection() {
        difference() {
            cylinder(d = stand_boss_od, h = bh, $fn = 48);
            translate([0, 0, -0.1])
                cylinder(d = axle_bore_d, h = bh + 0.2, $fn = 48);
        }
        translate([0, 0, -1])
            cylinder(d = axle_d, h = bh + 2, $fn = 48);
    }
}

// Negative control: axle grown past the bore — must interfere
module fit_axle_ctrl() {
    bh = hub_len;
    intersection() {
        difference() {
            cylinder(d = stand_boss_od, h = bh, $fn = 48);
            translate([0, 0, -0.1])
                cylinder(d = axle_bore_d, h = bh + 0.2, $fn = 48);
        }
        translate([0, 0, -1])
            cylinder(d = axle_bore_d + 0.4, h = bh + 2, $fn = 48);
    }
}

// Two segments mated at one joint — interference solid must be empty
// (within the designed shingle; pegs occupy the holes)
module fit_joint() {
    // Male of segment 0 into female of segment 1 (rotated by seg_ang)
    intersection() {
        rim_segment();
        rotate([0, 0, seg_ang]) rim_segment();
    }
}

// Negative control: collapse the lap clearance (step → 0 and no female cut
// equivalent) by overlapping two identical un-rotated segments — must collide
module fit_joint_ctrl() {
    intersection() {
        rim_segment();
        translate([0, 0, 0]) rim_segment();  // coincident — solid self ∩ self
    }
}

// ---------------------------------------------------------------------------
// Dispatch
// ---------------------------------------------------------------------------
if (part == "rim-segment") rim_segment();
else if (part == "hub") hub();
else if (part == "stand") stand();
else if (part == "axle") axle_print();
else if (part == "coupon") wheel_coupon();
else if (part == "assembled") assembled();
else if (part == "cutaway") cutaway();
else if (part == "mates") fit_mates();
else if (part == "mates-ctrl") fit_mates_ctrl();
else if (part == "axle-fit") fit_axle();
else if (part == "axle-fit-ctrl") fit_axle_ctrl();
else if (part == "joint-fit") fit_joint();
else if (part == "joint-fit-ctrl") fit_joint_ctrl();
else assert(false, str("nuggs-wheel: unknown part '", part, "'"));
