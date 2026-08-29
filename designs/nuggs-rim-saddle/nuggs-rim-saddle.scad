// N.U.G.G.S. rim saddle — the no-drill glass-enclosure entry port (charter
// backlog B3, brief #395): a saddle that clamps over the top rim of a glass
// cabinet (IKEA Detolf by default, parametrically) and carries one standard
// NUGGS genderless quarter-turn port, so a run starts from a glass tank the
// same way it starts from a plywood bulkhead. No drilling (N9 — tempered glass
// shatters), no adhesive, opens by hand in one action (N5).
// Requirements, welfare sources and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// THE BORE IS THE RAMP. The whole module is ONE tube whose axis is inclined
// exactly 15 deg (the N4 ceiling, asserted) descending into the tank: the
// "internal ramp" is the bore's invert — a round tube at 15 deg, so the
// walking surface is the bore arc (charter N11's zero-step argument holds by
// construction) and the animal climbs out the surface it descended. The mouth
// discharges into the enclosure, which is the N2/N3 break; the product page
// says so.
//
// THE CLAMP, in one breath: the bridge bears the panel's top edge, the inner
// skirt's pad bears the panel's inner face BELOW the seam zone (nothing bears
// silicone), and two IDENTICAL strap arms drop from above onto a latch flange
// at the outer skirt's foot — each arm's inner face bears the frame lip while
// its foot channel hooks the flange's inner end, closing the loop
// pad→lip→panel→inner pad→bridge→skirt→flange←hook. Release is one action:
// pull both arms outboard, the feet cam off the flange, lift the saddle off.
//
// PRINT ORIENTATION. body: port-down on the sector tips, bore axis vertical
// (the family way — lib/nuggs-coupling.scad's header says why the sectors
// must never face the bed). arms: flat on their back, profile in the bed
// plane. coupon: flat. Assembled renders are previews only — the 3MF plate
// from ci.plate is the deliverable.
use <nuggs-coupling.scad>

/* [What to render] */
// assembled = review preview on the rim; cutaway = same, half-panel removed;
// panel = the enclosure envelope alone (fitcheck reference, NOT printable);
// body / arms = the printable parts; coupon = both tuned fits in one;
// clamped = fitcheck: clamped parts MINUS the enclosure envelope, must be
// empty; clamped_neg = the same with the arms shifted inboard 1.2 mm (a rigid
// crush closing grip_gap + 1 mm), the negative control that must interfere.
part = "body";  // [assembled, cutaway, panel, body, arms, coupon, clamped, clamped_neg]
// Default is the printable body so the default render (render.sh, the bare
// contact-sheet line, the gallery) is the as-printed pose, never a preview
// pose — a posed/sectioned hero must not be the only geometry-true view.

/* [The NUGGS standard - inherited defaults, change nothing you printed fits] */
// Internal bore (mm) - the headline number. Asserted >= min_bore_mm by the lib.
bore_d = 80.0;
// Tube shell thickness (mm). ro = bore_d/2 + wall is the coupling datum.
wall = 2.4;
// Radial depth of the coupling ring beyond the tube OD (mm).
lug_r = 6.0;
// Axial projection of the coupling sectors past the tube face (mm).
port_proj = 10.0;
// Backing-collar thickness (mm).
collar_t = 3.0;
// Coupling sectors per face (3 = kinematically determinate).
n_lug = 3;
// Angular width of each sector (deg). Asserted lug_deg + twist_deg <= pitch/2.
lug_deg = 40;
// Radial depth of the locking rib (mm).
rib_h = 1.0;
// Axial width of the locking rib / groove (mm).
rib_w = 2.4;
// Angular width of the locking rib (deg).
rib_deg = 12;
// The locking twist (deg). Asserted rib_deg + twist_deg <= lug_deg.
twist_deg = 14;
// Overlap fusing the ribs into the outer sectors (mm). Never zero.
bite = 0.8;

/* [Fit & tolerances] */
// THE coupling knob. Uniform clearance on every coupling surface (mm). Owned
// by the standard; tuned on the family coupon in +/-0.05 steps.
port_tol = 0.30;
// Rim-grip clearance (mm): the arm's bearing face stands off the frame lip's
// outer face by this much when latched. 0 = metal-to-metal grip. THE clamp
// knob - tune on THIS design's coupon in +/-0.05 steps.
grip_gap = 0.20;

/* [Enclosure rim - Detolf defaults; CALIPER YOUR OWN CABINET] */
// Glass panel thickness (mm). Assumed 4 for a Detolf - measure yours.
glass_t = 4.0;
// Frame-lip projection off the panel's outer face (mm); the clamp's outer
// bearing. 0 = a frameless panel (the arm bears bare glass).
lip_d = 3.0;
// Frame-lip depth down from the panel's top edge (mm).
lip_h = 12.0;
// Top-edge silicone/seam bead width off the inner face and depth down from
// the top edge (mm) - the zone NOTHING may bear on (brief: the clamp bears on
// glass and frame only).
seam_w = 3.0;
seam_h = 4.0;
// Standoff between the bead zone and every inner bearing face (mm).
seam_clear = 1.0;
// How far the skirts reach down over the rim (mm) - the clamp's grip depth.
skirt_h = 42;

/* [Entry geometry] */
// Bore-axis incline, descending into the tank (deg). Exactly the N4 ceiling;
// asserted <= max_incline_deg, never raise either.
incline_deg = 15;
// Horizontal reach of the mouth into the tank from the rim plane (mm).
// Brief's assumed ~120; set it for your bedding depth / interior bracing.
ramp_len = 120;
// Horizontal setback of the port face outboard of the rim plane (mm) - room
// for the port's sectors and a hand to reach the joint.
port_setback = 20;
// Height of the bore axis above the panel's top edge where the axis crosses
// the rim plane (mm). Derived edge_clearance below is asserted >= 1.
h_face = 52;

/* [Clamp geometry] */
// Arm strap thickness (mm) - 4+ perimeters; PETG, a clamp is a bending member.
arm_t = 7.0;
// Arm strap depth in Y (mm) - the bearing width on the lip.
arm_w = 24;
// Latch flange thickness (mm) - the arm's foot channel seats on its top face.
flange_t = 6.0;
// Air between the flange's inner end and the glass outer face (mm). This gap
// is where the arm's channel wall hangs: it must fit ch_wall plus >= 1 mm of
// clearance to the panel, or the hook grinds the glass.
flange_clear = 3.0;
// Foot-channel wall thickness (mm) - the clamp's outboard stop face.
ch_wall = 2.0;
// Hook wrap below the flange's underside (mm) - an upward knock cannot kick
// the arm off; release is a deliberate ~5 mm lift.
hook_drop = 5.0;
// Vertical seat play: the roof rests on the flange top with this much gap
// until the clamp seats (mm).
seat_lift = 0.2;
// Arm pitch either side of the bore axis (mm) - the two clamp points.
arm_dy = 70;

/* [Welfare limits - asserted, not tunable down] */
// DTSchB entrance minimum, pouch-full criterion (mm). NEVER lower this.
min_bore_mm = 70;
// Charter N4 fall-risk ceiling (deg). NEVER raise this or incline_deg.
max_incline_deg = 15;

/* [Print settings] */
// Nozzle diameter (mm) - feeds the wall and web guards in the lib.
nozzle = 0.4;

/* [Quality] */
// MUST match the lib's pin (_NUGGS_FA/_NUGGS_FS) everywhere tube meets port:
// a mismatched tube surface splits into ~20 shells on the Manifold backend
// (issue #99 / PR #200). Do not "improve" these.
$fa = 3;
$fs = 0.8;

/* [Hidden] */
eps = 0.01;
// Fitcheck-only crush depth (mm) - the negative control's forced interference.
neg_crush = 1.0;

// ---------------------------------------------------------------------------
// Coupling configuration - ONE cfg, built once, handed to every port call.
// ---------------------------------------------------------------------------
cfg = nuggs_cfg(bore_d=bore_d, wall=wall, lug_r=lug_r, port_proj=port_proj,
                collar_t=collar_t, n_lug=n_lug, lug_deg=lug_deg, rib_h=rib_h,
                rib_w=rib_w, rib_deg=rib_deg, twist_deg=twist_deg, bite=bite,
                port_tol=port_tol, eps=eps, nozzle=nozzle, min_bore=min_bore_mm);

ri    = nuggs_ri(cfg);      // bore radius (40)
ro    = nuggs_ro(cfg);      // tube outer radius (42.4)
r_out = nuggs_r_out(cfg);   // coupling ring OD (48.4)
z_top = nuggs_z_top(cfg);   // port zone ends here; shell behind it must be full-round

// ---------------------------------------------------------------------------
// Frame transforms. PART frame: the NUGGS port frame - bore axis +z, port
// face z=0, sectors -z, tank-ward +z. USE frame: the assembly on the rim -
// +X into the tank, +Z up, the glass plane x=0 with the panel's top edge at
// z=0. The bore axis runs (cos i, 0, -sin i) in the use frame; the port face
// centre sits at (-port_setback, 0, h_face).
// ---------------------------------------------------------------------------
module P2U() {                     // part frame -> use frame
    translate([-port_setback, 0, h_face]) rotate([0, 90 + incline_deg, 0]) children();
}
module U2P() {                     // use frame -> part frame (exact inverse)
    rotate([0, -(90 + incline_deg), 0]) translate([port_setback, 0, -h_face]) children();
}

// Axial length: horizontal run port-face -> mouth is setback + reach.
tube_len = (port_setback + ramp_len) / cos(incline_deg);

// The tube's outer wall must clear the panel's inner-top corner (the nearest
// enclosure point to the bore) - measured, not assumed.
edge_clear = h_face - (port_setback + glass_t / 2) * tan(incline_deg)
             - ro * cos(incline_deg);
// And the port face's lowest rim point must clear the same edge.
face_clear = h_face - r_out * cos(incline_deg);

// ---------------------------------------------------------------------------
// The enclosure envelope (USE frame) - glass panel + frame lip + seam bead.
// The fitcheck target: in the clamped pose, no saddle material may live
// inside any of it. Preview-only as `part = "panel"`; never printable.
// ---------------------------------------------------------------------------
// Check margin (mm): at rest the pad leaf, bridge underside and flange end
// sit in EXACT coplanar contact with the panel, lip and bead - the designed
// state, and a zero-volume intersection CGAL still exports as facets. The
// envelope pulls those faces in by this margin, so "empty" means "no overlap
// AND clear of every contact plane by >= margin". Real overlaps (the negative
// control's 1 mm crush) still land inside it.
check_margin = 0.05;
module enclosure_env() {
    panel_w = 180;                       // enough to span both arms in preview
    m = check_margin;
    // glass panel, top edge at z=0
    translate([-glass_t / 2 + m, -panel_w / 2, -skirt_h - 40])
        cube([glass_t - 2 * m, panel_w, skirt_h + 40 - m]);
    // frame lip on the outer face, down from the top edge
    translate([-(glass_t / 2 + lip_d) + m, -panel_w / 2, -lip_h])
        cube([lip_d - m, panel_w, lip_h - m]);
    // top-edge seam bead on the inner face - the zone nothing may bear on
    translate([glass_t / 2 + m, -panel_w / 2, -seam_h])
        cube([seam_w - m, panel_w, seam_h - m]);
}

// ---------------------------------------------------------------------------
// Bearing planes (USE frame), all derived from the parameters above.
//
//   lip_face   x of the lip's outer face (the arm's bearing target)
//   pad_x      x of the arm's inner bearing face, standoff grip_gap
//   in_face    x of the panel's inner face
//   in_pad_z   z where the inner skirt's pad MAY start (below the bead zone)
//
//   outer skirt stack (x, outboard -> in):  arm strap [pad_x-arm_t, pad_x],
//   gap arm_gap, skirt wall [sk_x1, sk_x0] (sk_x0 its inner face), with the
//   latch flange reaching inboard from the skirt's foot.
// ---------------------------------------------------------------------------
lip_face  = -(glass_t / 2 + lip_d);
pad_x     = lip_face - grip_gap;
in_face   = glass_t / 2;
in_pad_z  = -(seam_h + seam_clear);          // inner bearing starts below the bead
arm_gap   = 1.2;                             // strap-to-skirt running clearance
sk_x0     = pad_x - arm_t - arm_gap;         // skirt inner face
skirt_t   = 7.0;                             // skirt wall thickness
sk_x1     = sk_x0 - skirt_t;                 // skirt outer face
fl_x_in   = -(glass_t / 2) - flange_clear;   // flange inner end (the latch stop)
fl_x_out  = sk_x0 - 1.0;                     // flange outer end, 1 mm fused into the skirt
fl_top    = -skirt_h + flange_t;             // flange top face (the arm's z-seat)

// The arm, canonical frame: its inner bearing face at profile x = 0 (placed
// at pad_x in the use frame), +x inboard. The wall-to-pad span is derived so
// that at any grip_gap the channel wall seats on the flange's inner end:
// shifting grip_gap shifts ONLY the pad standoff, never the latch - one knob,
// the same discipline as port_tol.
arm_top   = 16;                              // strap top above the rim plane

// ---------------------------------------------------------------------------
// THE BODY (part frame for the tube; use frame for the shell - one union,
// ONE bore cut in the part frame, the family rule).
// ---------------------------------------------------------------------------
// Port + solid tube, no cuts yet: the single nuggs_bore_cut below opens the
// bore through port, tube and shell alike, so every curved surface in the
// part shares one resolution and one bore cylinder (issue #99 / PR #200).
module port_tube_solid() {
    cylinder(r = ro, h = tube_len);
    nuggs_port(cfg);
}

// 45-degree lead at a bore mouth. Cut only; only ever widens the bore.
// The profile is exact: bore ri + 1 AT the mouth face plane z, tapering at
// exactly 45 deg to ri one mm inside the material — for dir=1 the material
// lies below z so the cone grows downward (rotate 180), for dir=-1 it lies
// above z and grows up. (Round-2 fix: the two dir branches were crossed,
// which inverted the in-tank lead into a groove-behind-a-lip and dropped the
// port-face cone below its own cutting plane — the exact "step" N11 forbids.)
// The cone OVERSHOOTS the face plane by `over` into open air, so its base
// disc is never coplanar with the mouth face and its tip under-runs the bore
// by eps: every boundary of the cut is a transversal crossing. A base disc
// sitting exactly in the face plane is a coincident-face subtraction — CGAL
// absorbs it, but the Manifold backend emits non-manifold edges and shell
// fragments along that plane (the round-2.1 59/100 NOT PRINTABLE: 15 shells,
// watertight False, every cluster on the in-tank mouth plane). The overshoot
// is safe at both mouths: the in-tank face fronts open tank air, and at the
// port face the nearest material below z=0 is the inner sectors' projecting
// half at i_in = ro + tol/2, well outboard of the cone's ri + 1 + over reach.
module bore_lead(z, dir = 1) {      // dir=1: mouth on +z; dir=-1: mouth on -z
    over = 0.5;                     // real overlap past the face plane (mm)
    translate([0, 0, z + (dir > 0 ? over : -over)])
        rotate([dir > 0 ? 180 : 0, 0, 0])
            cylinder(r1 = ri + 1.0 + over, r2 = ri - eps,
                     h = 1.0 + over + eps);   // slope (r1-r2)/h = 1: true 45
}

// The shell (USE frame): bridge over the rim + skirts down both faces +
// latch flanges + inner bearing pad. Faces that bear on the enclosure are
// exact; everything else stands off by seam_clear or grip_gap.
bridge_top  = 20;                     // shell depth above the rim plane
bridge_out  = sk_x1 - 8;              // bridge outer extent (covers the skirt)
bridge_in   = in_face + skirt_t + 6;  // inner extent (covers the inner skirt)
module shell() {
    difference() {
        union() {
            // outer skirt, flange foot, top fused 3 mm into the bridge (a
            // coplanar z=0 touch alone is not a fuse)
            translate([sk_x1, -(r_out + 14), -skirt_h])
                cube([skirt_t, 2 * (r_out + 14), skirt_h + 3]);
            // bridge slab: bears the panel's top edge strip along its underside
            translate([bridge_out, -(r_out + 14), 0])
                cube([bridge_in - bridge_out, 2 * (r_out + 14), bridge_top]);
            // inner skirt wall, standing off the bead footprint by seam_clear
            // in x, its top fused 3 mm into the bridge (a coplanar z=0 touch
            // alone is severed by the bead relief below)
            translate([in_face + seam_w + seam_clear, -(r_out + 14), -skirt_h])
                cube([skirt_t, 2 * (r_out + 14), skirt_h + 3]);
            // inner bearing pad + spine, ONE piece: the 2 mm leaf bears the
            // panel's inner face below the bead zone, and the spine runs
            // outboard to overlap the skirt by 1 mm - a leaf alone is an
            // island (iteration 1: it shipped floating inside the glass)
            translate([in_face, -(r_out + 14), -skirt_h])
                cube([2 + seam_w + seam_clear - 1, 2 * (r_out + 14),
                      skirt_h + in_pad_z]);
            // latch flanges: one under each arm, at the skirt's foot, inner
            // end at fl_x_in - the arm's outboard stop
            for (ay = [-arm_dy, arm_dy])
                translate([fl_x_in, ay - arm_w / 2 - 6, -skirt_h])
                    cube([fl_x_out - fl_x_in, arm_w + 12, flange_t]);
        }
        // the straps rise through the bridge to their grip above the rim:
        // one pass-through slot per arm, clear of the bearing strip on the
        // panel's top edge (which lives at |x| <= glass_t/2 + lip_d)
        for (ay = [-arm_dy, arm_dy])
            translate([pad_x - arm_t - 0.6, ay - arm_w / 2 - 0.6, -eps])
                cube([arm_t + 1.2, arm_w + 1.2, bridge_top + 2 * eps]);
        // bead relief: the bridge bears the top-edge strip and the lip only -
        // a seam_clear pocket over the bead footprint, so the silicone never
        // takes load (brief: the clamp bears on glass and frame only)
        translate([in_face, -(r_out + 14), -eps])
            cube([seam_w + seam_clear, 2 * (r_out + 14), seam_clear + eps]);
    }
}

module body() {                       // USE frame
    difference() {
        union() {
            P2U() port_tube_solid();
            shell();
        }
        P2U() nuggs_bore_cut(cfg, nuggs_z_tip(cfg) - 2, tube_len + 2);
        P2U() bore_lead(0, -1);                     // port-face bore mouth
        P2U() bore_lead(tube_len, 1);               // in-tank mouth
    }
}

// The printable body: part frame, standing on the sector tips (port down).
module body_part() {
    translate([0, 0, -nuggs_z_tip(cfg)]) U2P() body();
}

// ---------------------------------------------------------------------------
// THE ARM (USE frame) - a flat strap clip, identical at both clamp points.
// Profile in (x, z) with the inner bearing face at x = 0 (placed at pad_x),
// +x inboard. The foot channel drops over the latch flange: the ROOF seats on
// the flange top (z-seat, seat_lift of play), the channel's inboard WALL is
// the outboard stop (metal-to-metal at the seat), and the wall's
// hook wraps hook_drop below the flange so a knock cannot kick the arm off.
// Release: lift ~hook_drop. Assembly: drop on, let it seat.
// ---------------------------------------------------------------------------
module arm_profile(gg) {
    // wall seating face, derived so the latch never moves with grip_gap
    wx  = fl_x_in - lip_face + gg;
    wo  = wx + ch_wall;
    rz  = -skirt_h + flange_t + seat_lift;    // roof underside (on the flange top)
    rt  = rz + 5;                             // the wall merges into the strap here
    tz  = -skirt_h - hook_drop;               // hook tip (foot bottom)
    // the wall hangs inboard of the pad face over z in [rz, rt]: that air is
    // only free if the frame lip has ended - and the wall's inboard face must
    // clear the glass outer face by >= 0.5 (absolute: pad_x + wo).
    assert(rt < -lip_h - 0.5, str(
        "ARM WALL: the channel wall protrudes inboard up to z=", rt,
        " but the frame lip runs to z=", -lip_h, " - the foot would hit it."));
    assert(pad_x + wo <= -glass_t / 2 - 0.5, str(
        "ARM WALL: the wall's inboard face reaches x=", pad_x + wo,
        ", inside the glass outer face (", -glass_t / 2, ") - the hook would",
        " grind the panel. Raise flange_clear (needs >= ch_wall + 0.5)."));
    polygon([
        [-arm_t, arm_top], [0, arm_top],        // strap top (pad face at x=0)
        [0, rt],                                 // bearing face down to the wall
        [wo, rt], [wo, tz],                      // wall inboard face to the tip
        [wx, tz], [wx, rz],                      // wall seating face (the stop)
        [-arm_t, rz], [-arm_t, arm_top]          // roof underside; strap closes it
    ]);
}
module arm(gg = grip_gap) {           // USE frame, seated pose
    // profile (x, z) -> use (x, z); extrusion (local +z) lands on use -y, so
    // center the extrude and place the strap's midplane at ay
    for (ay = [-arm_dy, arm_dy])
        translate([pad_x, ay, 0]) rotate([90, 0, 0])
            linear_extrude(arm_w, center = true) arm_profile(gg);
}
// The printable arms: both, flat on their back - profile polygons in the bed
// plane, thickness (arm_w) stacked up through the layers.
module arms_part() {
    for (k = [-1, 1])
        translate([k * 16, 0, 0])
            linear_extrude(arm_w) arm_profile(grip_gap);
}

// ---------------------------------------------------------------------------
// "Print this first" coupon: BOTH tuned fits in one part, straight from the
// production modules - nothing copied. Zone A: two stub necks side by side
// (port_tol). Zone B: the latch flange on a standing fixture + two production
// arms flat beside it (grip_gap). See NOTES.md "Print this first".
// ---------------------------------------------------------------------------
module coupon() {
    // Zone A - the port fit: two stub necks side by side (the family coupon
    // pattern from designs/nuggs): print, pick up, mate and twist. Tunes
    // port_tol and doubles as the bore gauge.
    for (x = [-1, 1])
        translate([x * (r_out + 6), 0, port_proj]) nuggs_neck(cfg, 18);
    // Zone B - the rim grip: the production flange on a skirt-foot fixture
    // standing clear of zone A (in +y), with two production arms as SEPARATE
    // flat bodies beside it - snap one on to feel the latch and the grip;
    // same geometry the body carries, nothing copied.
    fw   = arm_w + 14;                      // fixture depth in Y
    yb   = r_out + 30;                      // fixture centreline, clear of zone A
    lift = hook_drop + 5;                   // bed -> flange underside
    // bed-standing base filling the stub + flange footprint (the arm's hook
    // hangs in the air beside it, tip hook_drop above the bed)
    translate([sk_x1 - 3, yb - fw / 2, 0])
        cube([fl_x_in - (sk_x1 - 3), fw, lift]);
    translate([0, yb, skirt_h + lift]) {
        translate([sk_x1, -fw / 2, -skirt_h])
            cube([skirt_t, fw, skirt_h]);                       // skirt stub
        translate([fl_x_in, -fw / 2, -skirt_h])
            cube([fl_x_out - fl_x_in, fw, flange_t]);           // the flange
    }
    ya = yb + fw / 2 + 10;
    translate([-sk_x1 - arm_t - 2, ya, 0])      linear_extrude(arm_w) arm_profile(grip_gap);
    translate([-sk_x1 - arm_t - 2, ya + arm_w + 10, 0]) linear_extrude(arm_w) arm_profile(grip_gap);
}

// ---------------------------------------------------------------------------
// Fitchecks (USE frame). `clamped`: body + arms latched MINUS the enclosure
// envelope - must render EMPTY (zero facets): nothing bears inside the glass,
// the lip or the bead, and the env's check_margin reads the designed rest
// contacts (pad leaf, bridge underside) as clear, not as slivers. `clamped_neg`:
// the arms RIGIDLY shifted inboard by grip_gap + neg_crush, so the pad lands
// 1 mm inside the lip - MUST interfere, proving the empty check can fail
// (designs/nuggs round 6.1).
// ---------------------------------------------------------------------------
module clamped_pose(gg, shift = 0) {
    body();
    translate([shift, 0, 0]) arm(gg);     // shift: rigid inboard crush, neg only
}
module fitcheck(gg, shift = 0) {
    intersection() {
        clamped_pose(gg, shift);
        enclosure_env();
    }
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------
if (part == "assembled") {
    body();
    arm();
} else if (part == "cutaway") {
    // section along the bore-axis plane (y=0): the ramp's true cross-section
    difference() {
        union() { body(); arm(); }
        translate([-500, 0, -500]) cube([1000, 1000, 1000]);
    }
} else if (part == "panel") {
    enclosure_env();
} else if (part == "body") {
    body_part();
} else if (part == "arms") {
    arms_part();
} else if (part == "coupon") {
    coupon();
} else if (part == "clamped") {
    fitcheck(grip_gap);
} else if (part == "clamped_neg") {
    // the arms crushed inboard by a RIGID shift (closes grip_gap, then 1 mm
    // into the lip). Growing gg instead would RELOCATE the latch wall - the
    // one-knob rule - and trip the arm's own guard rather than the glass.
    fitcheck(grip_gap, grip_gap + neg_crush);
} else {
    assert(false, str("unknown part: \"", part, "\" (expected assembled,",
        " cutaway, panel, body, arms, coupon, clamped, clamped_neg)"));
}

// ---------------------------------------------------------------------------
// Design-level asserts (coupling guards live in nuggs_cfg()).
// ---------------------------------------------------------------------------
assert(incline_deg <= max_incline_deg, str(
    "N4 INCLINE: incline_deg = ", incline_deg, " exceeds the ", max_incline_deg,
    " deg fall-risk ceiling. Syrians climb well but have almost no depth",
    " perception - never raise the incline or this assert's ceiling."));
assert(incline_deg > 0, "NUGGS SADDLE: the incline must be positive (a level bore never clears the rim).");
assert(edge_clear >= 1.0, str(
    "RIM CLEARANCE: the tube wall clears the panel's inner-top corner by only ",
    edge_clear, " mm (< 1). Raise h_face or port_setback."));
assert(face_clear >= 2.0, str(
    "FACE CLEARANCE: the port face's rim clears the panel edge by only ",
    face_clear, " mm (< 2). Raise h_face."));
assert(flange_clear >= ch_wall + 0.5, str(
    "FLANGE CLEARANCE: ", flange_clear, " mm between the flange's inner end and",
    " the glass outer face must also fit the arm's channel wall (", ch_wall,
    " mm) plus 0.5 mm - or the hook grinds the panel. Raise flange_clear."));
assert(grip_gap >= 0, str(
    "GRIP GAP: ", grip_gap, " is negative - the arm would ship crushing the",
    " lip by ", -grip_gap, " mm. Only clamped_neg may force interference."));
assert(skirt_h > lip_h + flange_t + 6, str(
    "SKIRT REACH: skirt_h = ", skirt_h, " must drop past the lip (", lip_h,
    ") plus the flange zone (", flange_t, ") with margin, or the clamp has no depth."));
assert(arm_t >= 2.5 * nozzle, str(
    "ARM WALL: arm_t = ", arm_t, " is under ", 2.5 * nozzle, " mm - the strap",
    " is a bending member, not a veneer."));
assert(tube_len >= z_top, str(
    "TUBE LENGTH: tube_len = ", tube_len, " is shorter than the port zone z_top = ",
    z_top, " - the port's inner sectors have no full-round shell to fuse to."));

echo(str("nuggs-rim-saddle: bore ", bore_d, " mm at ", incline_deg, " deg, mouth ",
    ramp_len, " mm into the tank, enclosed axial run ", tube_len,
    " mm (the port discharges into the enclosure - the N2/N3 break);",
    " edge clear ", edge_clear, " mm, grip ", grip_gap, " mm, lug bite ", bite, " mm"));
