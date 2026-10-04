// NUGGS probe cap — the sealed sensor end-cap (brief #732): a flat plate with
// the standard quarter-turn bayonet port on one face, closing the open end of
// any NUGGS module while a temperature probe and a sensor cable pass through
// the wall without opening the tube to bedding, seed husks or drafts. The
// "sensor or tool mount" end-cap the NUGGS mandate names: #514's gauge and
// #515's bottle-adapter want an open end, #592's vent-cap breathes — nothing
// both seals the bore AND passes a sensor.
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// This design is a CONSUMER of the port standard, exactly like designs/nuggs
// and nuggs-open: ONE cfg from nuggs_cfg(), handed to every port call, and no
// coupling geometry of its own. The only new geometry is the GRIP — the split
// compression-grip pass-through — and the plate that seals the bore.
//
// THE GRIP, in one breath: each pass-through is a straight bore at nominal +
// grip_clearance through the plate and a boss above it, the boss wall split by
// axial slots into fingers, each finger a vertical wall rooted in the plate.
// The fingers make the bore wall compliant, so it conforms around what passes
// and seals the annulus; GRIP is what you tune on the coupon — shrink
// grip_clearance toward 0.1 / 0.05 and the fingers pinch. The default +0.2 is
// the repo's sliding-clearance convention: a Ø 6.0 probe passes free, and the
// 0.1 mm/side annulus is what keeps husks and drafts out (not rated airtight).
// "Split" matters both ways: the slots are what let the wall close onto a
// smaller cable, which is how one gland takes up everything from the probe's
// Ø 3.4 cable to a Ø 4–5 hygrometer lead.
//
// PRINT ORIENTATION. The part prints PORT-DOWN, standing on the coupling
// sectors' tips — every NUGGS module's pose. The plate stacks on top of the
// port zone, the grip bosses rise from the plate's keeper-side face, and
// every grip surface is a vertical wall printed layer-by-layer as in-plane
// arcs: no grip surface leaves the print plane, no supports, bed contact on
// the three sector tips and their ribs alone. The model frame IS the print
// frame (bed at z = 0), so printcheck scores the part exactly as it prints.
//
// The probes hang below the plate into the mate's bore at whatever depth the
// keeper seats them — that is the grip's point. A fully-home Ø 6 × 30 probe
// projects ~25 mm past the plate underside; the bore floor is 40 mm off-axis
// at the invert, so a centered probe cannot touch it. Blunt stainless at
// mid-bore is the keeper's call (see README); the cap presents no sharp edge
// of its own: the plate's habitat-side face is corrugated (concentric 50°
// V-grooves, the no-flat-ceiling rule every enclosed NUGGS bore follows) and
// the bore mouths are vertical tunnels.
use <nuggs-coupling.scad>

/* [What to render] */
// cap = the printable part; coupon = the print-this-first fit tab; pair =
// cap coupled to a tube end (review preview); cutaway = sectioned through
// the gland's plane; probe_seats / gland_seats = fitcheck: a nominal-size
// proxy through every grip must clear (zero facets); probe_jams /
// gland_jams = the negative control, deliberately oversized, must interfere.
part = "cap";  // [cap, coupon, pair, cutaway, probe_seats, probe_jams, gland_seats, gland_jams]

/* [The NUGGS standard - change these and nothing you already printed fits] */
// Every value here is a nuggs_cfg() default: this module inherits the
// standard so it mates with designs/nuggs and every other module. Exposed
// for the Customizer, not for tuning — the coupling guards fire inside
// nuggs_cfg().
// Internal bore diameter (mm) - the headline number. Asserted >= min_bore_mm
bore_d = 80.0;
// Tube shell thickness (mm). ro = bore_d/2 + wall is the datum every coupling
// radius is measured from
wall = 2.4;
// Radial depth of the coupling ring beyond the tube OD (mm)
lug_r = 6.0;
// Axial projection of the coupling sectors past the tube face (mm)
port_proj = 10.0;
// Backing-collar thickness (mm)
collar_t = 3.0;
// Coupling sectors per face (3 = kinematically determinate)
n_lug = 3;
// Angular width of each sector (deg)
lug_deg = 40;
// Radial depth of the locking rib (mm)
rib_h = 1.0;
// Axial width of the locking rib / groove (mm)
rib_w = 2.4;
// Angular width of the locking rib (deg)
rib_deg = 12;
// The locking twist (deg)
twist_deg = 14;
// Overlap fusing the ribs into the outer sectors (mm). Never zero
bite = 0.8;

/* [Sensors - the pass-through loadout] */
// How many probe grips - 2 probes + 1 gland is the v1 loadout
n_probes = 2;
// Probe body diameter (mm) - DS18B20 waterproof probes are Ø 6 stainless;
// CALIPER THE OWNER'S before freezing (clones vary)
probe_d = 6.0;
// Probe body length (mm) - how far a fully-homed proxy reaches below the
// plate (the fitcheck proxy is cut this long, so the check proves the full
// seating depth, not just the mouth)
probe_len = 30;
// Cable gland nominal diameter (mm) - a round hygrometer / two-wire lead.
// The gland's grip reaches DOWN to probe_cable_d when coupon-tuned
gland_d = 4.0;
// Probe cable take-up diameter (mm) - the thinnest cable the gland must be
// able to close onto (the DS18B20's own lead)
probe_cable_d = 3.4;
// Placement radius of the pass-throughs from the cap axis (mm)
port_radius = 20.0;

/* [Fit & tolerances] */
// THE grip knob (mm): diametral clearance added to every grip bore. +0.2 =
// the repo's sliding convention (seals, passes free); tune DOWN on the
// coupon in 0.05 steps for a pinching grip. The port's own fit is port_tol,
// owned by the standard and tuned on designs/nuggs's coupon, not here
grip_clearance = 0.2;
// Asserted 0.10-0.60 by the lib; the port fit, not the grip fit
port_tol = 0.30;

/* [Grip fingers] */
// Radial wall thickness of each finger (mm) - >= 3 perimeters
finger_wall = 1.6;
// Finger length above the plate (mm) - also the grip's guided length
boss_h = 7.0;
// Fingers per grip (split count)
n_fingers = 3;
// Width of the splitting slots (mm) - printable gap, and the room the
// fingers deflect into when the bore pinches
slot_w = 1.5;
// Lead-in chamfer at each finger-tip mouth (mm) - self-centers the probe
lead_in = 0.8;
// How far past the whole tunable band the jam control's proxy is oversized
// (mm) - it must interfere no matter how the coupon was tuned
jam_oversize = 0.6;

/* [Plate] */
// Cap plate thickness (mm) - given as = wall by the brief; it is the seal
plate_t = 2.4;
// Depth of the ceiling-relief V-grooves (mm): concentric grooves carved into
// the plate's habitat-side face so the ceiling over the bore prints without
// supports. The groove root leaves plate_t - groove_d of seal (1.2 mm =
// 3 perimeters, the floor the wall guard below enforces)
groove_d = 1.2;

/* [Welfare limits - asserted, not tunable down] */
// DTSchG entrance minimum (mm). The bore floor itself is asserted in nuggs_cfg()
min_bore_mm = 70;

/* [Print settings] */
// Nozzle diameter (mm) - feeds the wall guards here and in the lib
nozzle = 0.4;

/* [Quality] */
// This design's own quality preset. Iterating: $fa=6/$fs=1.5.
// Production: $fa=2/$fs=0.5. It does NOT reach the coupling: the library
// pins its own $fa/$fs inside every geometry module body, deliberately, so
// the realised fit cannot move with a consumer's quality preset. The grip
// bores and their fitcheck proxies are both cut at THIS preset, so the
// boolean and the part share one tessellation.
$fa = 3;
$fs = 0.8;

/* [Hidden] */
eps = 0.01;

// ---------------------------------------------------------------------------
// The coupling configuration — ONE cfg, built once, handed to every port call.
// Every coupling guard fires inside nuggs_cfg(); they are not restated here.
// ---------------------------------------------------------------------------
cfg = nuggs_cfg(bore_d    = bore_d,    wall      = wall,      lug_r    = lug_r,
                port_proj = port_proj, collar_t  = collar_t,  n_lug    = n_lug,
                lug_deg   = lug_deg,   rib_h     = rib_h,     rib_w    = rib_w,
                rib_deg   = rib_deg,   twist_deg = twist_deg, bite     = bite,
                port_tol  = port_tol,  eps       = eps,       nozzle   = nozzle,
                min_bore  = min_bore_mm);

// The contract values this design reaches for.
ro     = nuggs_ro(cfg);      // tube OD radius; the shell and plate run at it
z_tip  = nuggs_z_tip(cfg);   // sector-tip plane in port frame
z_top  = nuggs_z_top(cfg);   // top of the port zone; the plate sits here
pitch  = nuggs_pitch(cfg);   // sector pitch

// ---------------------------------------------------------------------------
// Derived
// ---------------------------------------------------------------------------
// The model frame IS the print frame: sector tips on the bed at z = 0.
cap_z   = port_proj + z_top;             // plate underside (23.0)
plate_top = cap_z + plate_t;             // keeper-side plate face (25.4)
probe_bore = probe_d + grip_clearance;   // 6.2 - the sliding/sealing bore
gland_bore = gland_d + grip_clearance;   // 4.2
probe_od   = probe_bore + 2 * finger_wall;   // 9.4 - the grip boss
gland_od   = gland_bore + 2 * finger_wall;   // 7.4
n_features = n_probes + 1;               // probes + the one gland
// Adjacent feature centres, evenly spaced at port_radius. The tight pair is
// probe-gland, so that pair sizes the guard.
feature_gap = 2 * port_radius * sin(180 / n_features);
// The narrowest finger's arc at the grip's mid-wall (the gland's), after the
// slots take their bite.
finger_arc_gland = (PI * (gland_bore + finger_wall) - n_fingers * slot_w)
                   / n_fingers;

// ---------------------------------------------------------------------------
// Design-level asserts. These fail the render, not a lint pass. The coupling's
// own guards live in nuggs_cfg(). What is left belongs to THIS design.
// ---------------------------------------------------------------------------
assert(finger_wall >= 3 * nozzle, str(
    "GRIP WALL: finger_wall = ", finger_wall, " mm needs >= 3 perimeters at a ",
    nozzle, " mm nozzle (", 3 * nozzle, " mm). A thinner finger is a single",
    " perimeter wall; it prints as a blob and grips as a hinge."));
assert(slot_w >= 3 * nozzle, str(
    "GRIP SLOT: slot_w = ", slot_w, " mm needs >= ", 3 * nozzle,
    " mm or the slot bridges shut and the fingers never split - the wall is",
    " solid, nothing can close onto a smaller cable, and the part still",
    " renders watertight and gates green."));
assert(boss_h >= 3 * finger_wall, str(
    "GRIP LENGTH: boss_h = ", boss_h, " mm is under 3x the finger wall (",
    3 * finger_wall, " mm). A stub that short cannot flex - it is a stiff",
    " ring, and pinching the bore on the coupon just jams the part."));
assert(finger_arc_gland >= 3 * nozzle, str(
    "GRIP FINGER ARC: the narrowest finger (gland, mid-wall) is ",
    finger_arc_gland, " mm of arc - under ", 3 * nozzle,
    " mm it prints as a drip, not a wall. Fewer fingers or narrower slots."));
assert(gland_bore >= 3.0, str(
    "GRIP BORE: gland_bore = ", gland_bore, " mm is under the 3.0 mm FDM",
    " hole floor - small bores print undersize and the cable never passes."));
assert(gland_bore - probe_cable_d <= 1.0, str(
    "GLAND TAKE-UP: the gland bore (", gland_bore, " mm) sits more than 1.0 mm",
    " wider than the probe cable (", probe_cable_d, " mm). The slots let each",
    " finger close roughly 0.5 mm radially on the coupon (~0.7% strain over a ",
    boss_h, " mm finger - elastic in PETG, marginal in PLA); a bore beyond that",
    " reach can never take up the ecosystem's thinnest cable - it rattles and",
    " the seal is theater. Lower gland_d or grip_clearance."));
assert(port_radius + probe_od / 2 <= ro - 1.2, str(
    "CAP LAYOUT: the probe grip's outer edge (", port_radius + probe_od / 2,
    " mm) runs within 1.2 mm of the plate rim (", ro, " mm). The bore needs a",
    " real wall around it or the seal leaks at the rim. Lower port_radius."));
assert(feature_gap >= (probe_od + gland_od) / 2 + 1.6, str(
    "CAP LAYOUT: adjacent pass-throughs are ", feature_gap, " mm apart -",
    " under the ", (probe_od + gland_od) / 2 + 1.6, " mm the two bosses plus a",
    " 1.6 mm wall need. The grips would merge into one lump. Lower",
    " port_radius or n_probes."));
assert(port_radius - probe_od / 2 >= 6, str(
    "CAP LAYOUT: the grips crowd the cap axis (inner edge at ",
    port_radius - probe_od / 2, " mm). Keep >= 6 mm so the plate stays a",
    " plate between the pass-throughs and the probes hang clear of each",
    " other below. Raise port_radius."));
assert(plate_t >= 3 * nozzle, str(
    "PLATE: plate_t = ", plate_t, " mm needs >= 3 perimeters (", 3 * nozzle,
    " mm). This plate IS the seal; any thinner and the bore mouths print as",
    " lace."));
assert(plate_t - groove_d >= 3 * nozzle - 1e-9, str(
    "CEILING: the relief groove root leaves ", plate_t - groove_d,
    " mm of plate - under the 3-perimeter floor (", 3 * nozzle,
    " mm). The groove would gut the seal. Lower groove_d. (The 1e-9 is the",
    " float boundary: 2.4 - 1.2 is not quite 1.2 in IEEE doubles, and this",
    " guard must not fire on the exact-floor default.)"));

// ---------------------------------------------------------------------------
// The grip. One construction for every pass-through, probe and gland alike:
// boss + bore + slots + lead-in, in a plate-top LOCAL frame (z = 0 is the
// plate's keeper-side face). Solid and cut are separate modules so the cap
// can union every solid FIRST and difference every cut once - a self-cut grip
// unioned onto the plate would seal its own bore with plate material. The
// coupon calls these same two modules, which is what "at production
// geometry" means here.
// ---------------------------------------------------------------------------
module grip_boss(d) {
    cylinder(d = d + grip_clearance + 2 * finger_wall, h = boss_h);
}

module grip_cut(d) {
    bore = d + grip_clearance;
    // The bore, through the boss and the full plate below it
    translate([0, 0, -plate_t - 1])
        cylinder(d = bore, h = plate_t + boss_h + 2);
    // Lead-in at the mouth: opens outward through the finger tips so a
    // blunt probe self-centers instead of snagging the tip edges
    translate([0, 0, boss_h - lead_in])
        cylinder(d1 = bore, d2 = bore + 2 * lead_in + 2, h = lead_in + 1);
    // The splits: radial cuts through the wall, from the plate's face to
    // above the tips. They stop AT the plate - a slot through the plate
    // would be a leak path past the seal, which is the one thing this
    // part exists to prevent.
    for (i = [0 : n_fingers - 1])
        rotate([0, 0, i * 360 / n_fingers])
            translate([bore / 2 - 1, -slot_w / 2, 0])
                cube([finger_wall + 2, slot_w, boss_h + 1]);
}

// The pass-throughs' placement. The gland sits at +X (the cutaway plane
// sections it); the probes share the remaining arc evenly.
module at_gland() { translate([port_radius, 0, 0]) children(); }
module at_probes() {
    for (i = [1 : n_probes])
        rotate([0, 0, i * 360 / n_features])
            translate([port_radius, 0, 0])
                children();
}

// ---------------------------------------------------------------------------
// The ceiling relief. The plate seals the mate's bore, and a flat ceiling
// spanning it is one unbridgeable shelf - issue #34 measured the supportless
// ceiling for enclosed bores at 45 degrees (45 -> clean, 60 -> 9 percent
// overhang), which is why nuggs-den allows no flat internal ceiling at all.
// Here the bore is too wide to close to a point inside the plate's 2.4 mm,
// so the habitat-side face is CORRUGATED instead: concentric V-grooves that
// leave every underside surface either a steep flank (groove_angle from
// horizontal, under printcheck's 45-degrees-from-vertical support threshold;
// nuggs-frieda's 50-degree house angle, with margin) or a flat annulus /
// center island narrower than the 5 mm span printcheck and a stock slicer
// bridge without support. The keeper-side face stays flat and the plate
// stays 2.4 mm at every tooth, so the brief's "flat cap plate, 2.4 = wall"
// holds where it matters: the seal face the grips stand on.
// ---------------------------------------------------------------------------
groove_angle = 50;                          // flank steepness from horizontal
groove_half  = groove_d / tan(groove_angle); // groove half-width at the face
tooth_w      = 1.2;                         // flat tooth-tip annulus width
groove_pitch = tooth_w + 2 * groove_half;   // centre-to-centre
rim_r        = bore_d / 2;                  // corrugation reaches the bore wall
n_grooves    = floor((rim_r - tooth_w - groove_half - 1.5) / groove_pitch) + 1;
// The un-grooved disc the pattern converges to at the axis
island_r     = rim_r - tooth_w - 2 * groove_half - (n_grooves - 1) * groove_pitch;

assert(island_r >= 1.0 && 2 * island_r <= 5.0, str(
    "CEILING: the relief pattern leaves a Ø ", 2 * island_r,
    " mm flat island at the cap axis. Keep it >= Ø 2 (a printable dot) and",
    " <= Ø 5 (the bridge span a flat ceiling may not exceed, printcheck's",
    " bridge_max_mm) - adjust tooth_w or add one groove."));

module ceiling_relief() {
    for (k = [0 : n_grooves - 1]) {
        r_k = rim_r - tooth_w - groove_half - k * groove_pitch;
        rotate_extrude()
            polygon([[r_k - groove_half, cap_z - 1],
                     [r_k + groove_half, cap_z - 1],
                     [r_k,               cap_z + groove_d]]);
    }
}

// ---------------------------------------------------------------------------
// The part. Port + shell + plate + grips, then the bore is opened ONCE and
// stops AT the plate: the plate is the seal, so the cut must never reach it.
// ---------------------------------------------------------------------------
module nuggs_probe_cap() {
    difference() {
        union() {
            translate([0, 0, port_proj]) cylinder(r = ro, h = z_top);  // shell
            translate([0, 0, port_proj]) nuggs_port(cfg);              // port
            translate([0, 0, cap_z]) cylinder(r = ro, h = plate_t);    // plate
            at_gland()  translate([0, 0, plate_top]) grip_boss(gland_d);
            at_probes() translate([0, 0, plate_top]) grip_boss(probe_d);
        }
        // The bore cut stops at the plate underside (cap_z): one mm short is
        // a void above the bed, one mm far eats a dimple into the seal.
        nuggs_bore_cut(cfg, port_proj + z_tip - 1, cap_z);
        ceiling_relief();
        at_gland()  translate([0, 0, plate_top]) grip_cut(gland_d);
        at_probes() translate([0, 0, plate_top]) grip_cut(probe_d);
    }
}

// Print this first: one probe grip and one cable gland at production
// geometry - the very modules the cap calls, not a copy - on a small tab.
// Tune grip_clearance here in +/-0.05 steps: +0.2 slides and seals, +0.1
// pinches lightly, +0.05 grips hard. See NOTES.md "Print this first".
module coupon() {
    tab_l = probe_od + gland_od + 16;
    tab_w = max(probe_od, gland_od) + 8;
    x_probe = -tab_l / 2 + 4 + probe_od / 2;
    x_gland =  tab_l / 2 - 4 - gland_od / 2;
    difference() {
        union() {
            translate([-tab_l / 2, -tab_w / 2, 0]) cube([tab_l, tab_w, plate_t]);
            translate([x_probe, 0, plate_t]) grip_boss(probe_d);
            translate([x_gland, 0, plate_t]) grip_boss(gland_d);
        }
        translate([x_probe, 0, plate_t]) grip_cut(probe_d);
        translate([x_gland, 0, plate_t]) grip_cut(gland_d);
    }
}

// ---------------------------------------------------------------------------
// Fitchecks (ci.fitchecks). A NOMINAL proxy - the pass-through's own size,
// e.g. the Ø 6.0 probe through the Ø 6.2 bore - pushed through every grip of
// that kind, full seating depth, must clear with ZERO facets: no finger, no
// slot burr, no plate mis-drill reaches inside the bore the coupon tunes.
// Never make the proxy exactly the bore size: identical cylinders at the
// same tessellation share boundary faces, and CGAL resolves that as a
// zero-volume shell of facets - counted as interference, the very false
// reading the check exists to prevent. The jam control is the negative
// counterpart: grow the proxy past the whole tunable band (clearance +
// jam_oversize) and it MUST interfere, or the empty proof proves nothing.
// Proxy and bore are cut at this file's $fa/$fs, so they share one
// tessellation and the boundary case cannot sliver on a preset mismatch.
// ---------------------------------------------------------------------------
module grip_proxy(d, grow, below) {
    pd = d + grow;
    // Reaches from `below` under the plate (probe_len for probes, a short
    // stub for the gland) to above the finger tips; only the grip-zone
    // overlap can produce facets.
    translate([0, 0, cap_z - below])
        cylinder(d = pd, h = plate_t + boss_h + 2 + below);
}

module fitcheck(at, d, extra, below) {
    intersection() {
        nuggs_probe_cap();
        at() grip_proxy(d, extra, below);
    }
}

module probe_seats() { fitcheck(at_probes, probe_d, 0, probe_len); }
module probe_jams()  {
    fitcheck(at_probes, probe_d, grip_clearance + jam_oversize, probe_len);
}
module gland_seats() { fitcheck(at_gland, gland_d, 0, 8); }
module gland_jams()  {
    fitcheck(at_gland, gland_d, grip_clearance + jam_oversize, 8);
}

// ---------------------------------------------------------------------------
// Review previews (never printed). pair = the cap closing a tube end; the
// tube is a plain neck + a mirrored top port - the y-splitter's end-port
// idiom - so the two faces nest at half a pitch like every NUGGS joint.
// ---------------------------------------------------------------------------
tube_len = 60;  // preview stub only

module tube_stub() {
    difference() {
        union() {
            translate([0, 0, -tube_len]) nuggs_neck(cfg, tube_len);
            mirror([0, 0, 1]) nuggs_port(cfg);
        }
        nuggs_bore_cut(cfg, -tube_len - 11, 11);
    }
}

module pair() {
    color("#cdd6e0") nuggs_probe_cap();
    translate([0, 0, port_proj]) rotate([0, 0, pitch / 2])
        color("#e8b7c8") tube_stub();
}

if (part == "cap") nuggs_probe_cap();
else if (part == "coupon") coupon();
else if (part == "pair") pair();
// Section on the y = 0 plane keeping y < 0, through the gland's axis: shows
// the plate sealing the bore and the gland's fingers cut open (the elbow's
// cutaway idiom - the cube must START at y = 0, not straddle it).
else if (part == "cutaway")
    difference() { nuggs_probe_cap(); translate([-300, 0, -50]) cube([600, 300, 600]); }
else if (part == "probe_seats") probe_seats();
else if (part == "probe_jams") probe_jams();
else if (part == "gland_seats") gland_seats();
else if (part == "gland_jams") gland_jams();
else assert(false, str("nuggs-probe-cap: unknown part '", part, "'"));
