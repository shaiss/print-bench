// N.U.G.G.S. elbow — a curved tube module that routes an 80 mm-bore NUGGS run
// around a corner, carrying the genderless quarter-turn port on each end.
// Requirements, welfare sources and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// This design is a CONSUMER of the NUGGS port standard, exactly like
// designs/nuggs: it builds ONE cfg with nuggs_cfg() and hands it around, and it
// never redefines a coupling number. The only new geometry is the BEND between
// the two ports — a swept tube whose bore stays continuous and smooth through
// the corner (a NUGGS welfare non-negotiable: this routes a live animal and any
// interior ledge or step is a hazard).
//
// CONSTRUCTION — ONE BOSL2 path_sweep, so the tube is a single Manifold-clean
// polyhedron. The tube (and, subtracted, the bore) is one path_sweep() of the
// round section along the centerline path (inlet stub -> arc -> outlet stub): a
// single stitched mesh with no booleans and no coincident faces inside it,
// capped perpendicular to the tangent at each end — which is exactly the
// coupling-face plane, so no material stands past the joint and no clip is
// needed. The two ports fuse onto the straight port_stub ends just as they fuse
// to designs/nuggs's straight tube(). `normal = [0,1,0]` locks the section
// frame to the bend plane so the sweep does not twist.
// Getting here took four builds and only CI's Manifold backend told the truth —
// every failed one passed the local CGAL render (full story in NOTES.md): a
// hull-of-thin-discs loft fragmented into 19 shells (segments that only share a
// face stay separate volumes for Manifold); a straight cylinder butted onto a
// rotate_extrude bend left a non-manifold edge at the tangent (a straight
// primitive tangent to a curve never quite coincides with it); a chain of
// overlapping oriented cylinders exported non-manifold (the many intersection
// curves tessellate into edges shared by >2 triangles). The single path_sweep
// has no such junction to go wrong.
//
// PRINT ORIENTATION / THE 45-DEGREE CEILING (issue #34, adopted into #116).
// A vertically-printed enclosed bore has a ~45 deg overhang ceiling: issue #34
// measured 45 deg -> 92/100 with no overhang flag, 60 deg -> 9% overhang,
// 90 deg -> 11%. A single-piece 90 deg elbow would need support INSIDE the bore
// to hold its ceiling up, which violates the smooth-bore welfare rule even
// though 11% still passes printcheck (CRITICAL only escalates at >=25%). So the
// default bend_angle is 45 deg — the supportless, welfare-clean maximum —
// printed standing on the inlet flange. A 90 deg corner is TWO 45 deg elbows
// coupled (NUGGS is genderless and quarter-turn, so any 0-90 deg change in any
// plane is a pair of these). bend_angle stays tunable up to 90 for a one-piece
// corner, but past 45 you accept bore support — see NOTES.md.
use <nuggs-coupling.scad>
include <BOSL2/std.scad>   // path_sweep: one manifold mesh along the bend path

/* [What to render] */
// elbow = the printable part; pair = two elbows coupled into a 90 deg corner
// (review preview only); cutaway = elbow sectioned to inspect the bore.
part = "elbow";  // [elbow, pair, cutaway]

/* [The NUGGS standard - change these and nothing you already printed fits] */
// Every value here is a nuggs_cfg() default: the elbow inherits the standard so
// it mates with designs/nuggs and every other module. They are exposed for the
// Customizer, not for tuning — the coupling guards fire inside nuggs_cfg().
// Internal bore (mm) - the headline number. Asserted >= min_bore_mm by the lib
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
// Angular width of each sector (deg). Asserted lug_deg + twist_deg <= pitch/2
lug_deg = 40;
// Radial depth of the locking rib (mm)
rib_h = 1.0;
// Axial width of the locking rib / groove (mm)
rib_w = 2.4;
// Angular width of the locking rib (deg)
rib_deg = 12;
// The locking twist (deg). Asserted rib_deg + twist_deg <= lug_deg
twist_deg = 14;
// Overlap fusing the ribs into the outer sectors (mm). Never zero
bite = 0.8;

/* [Fit & tolerances] */
// The one knob. Uniform clearance on every coupling surface (mm). Owned by the
// standard; tuned on designs/nuggs's coupon, not re-tuned here. Asserted
// 0.10-0.60 by the lib
port_tol = 0.30;

/* [The bend] */
// Turn angle of the elbow (deg). DEFAULT 45 = the supportless, welfare-clean
// maximum (issue #34). Tunable up to 90 for a one-piece corner, but past 45 the
// bore ceiling needs support — see the header and NOTES.md.
bend_angle = 45;  // [15:90]
// Centerline radius of the bend (mm). ~1.5x bore: gentle, for animal welfare
// and a shallower overhang. The bore stays a full ri circle through the sweep,
// so the printable floor is set by the overhang, not by this radius
bend_radius = 120;
// Straight stub behind each port (mm). The port is designed to fuse to a
// straight full-round shell; this is that shell, and it gives a short grip past
// the coupling collar. Must be >= the port zone depth (z_top).
port_stub = 16;

/* [Welfare limits - asserted, not tunable down] */
// DTSchB entrance minimum, pouch-full criterion (mm). NEVER lower this.
// The bore floor itself is asserted inside nuggs_cfg()
min_bore_mm = 70;

/* [Print settings] */
// Nozzle diameter (mm) - feeds the wall and web guards in the lib
nozzle = 0.4;
// House angle for the bore-mouth edge break (deg)
chamfer_ang = 50;

/* [Quality] */
// This design's own quality preset. Iterating: $fa=6/$fs=1.5.
// Production: $fa=2/$fs=0.5. It does NOT reach the coupling: the library pins
// its own $fa/$fs inside every geometry module body, deliberately, so the
// realised fit cannot move with a consumer's quality preset. These settings
// shape the swept tube, never the joint.
$fa = 3;
$fs = 0.8;

// Facets around the swept tube section. Iterating: 32. Production: 64+.
tube_fn = 48;

/* [Hidden] */
eps = 0.01;
// Arc path step (deg): one path node every this many degrees around the bend.
// Small enough that the outer-wall facet is negligible.
arc_step = 2.5;
// Extra bore length past each mouth (mm), so both port mouths open past the
// sector tips (which project port_proj past the coupling face).
bore_over = port_proj + 2;

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

// The handful of contract values this design reaches for.
ri    = nuggs_ri(cfg);      // bore radius
ro    = nuggs_ro(cfg);      // tube outer radius
r_out = nuggs_r_out(cfg);   // coupling ring OD / envelope
z_top = nuggs_z_top(cfg);   // top of the port zone; the stub must back this much

// Bend geometry. The path is: a vertical inlet stub (z = 0 .. port_stub) at the
// inlet coupling face; a circular arc of radius bend_radius turning bend_angle
// toward +x; and an outlet stub tangent to the arc end. arc_pos(phi) is a point
// on the arc; dir_out is the outlet-stub direction; bend_end is the outlet
// coupling face (where the outlet port sits).
function arc_pos(phi) = [bend_radius * (1 - cos(phi)), 0,
                         port_stub + bend_radius * sin(phi)];
dir_out  = [sin(bend_angle), 0, cos(bend_angle)];
arc_top  = arc_pos(bend_angle);
bend_end = arc_top + port_stub * dir_out;

echo(str("nuggs-elbow: bend ", bend_angle, " deg at R", bend_radius,
         " mm, bore ", bore_d, " mm (ri ", ri, "), tube OD ", 2 * ro,
         " mm, port_tol ", port_tol, " mm"));
echo(str("nuggs-elbow: outlet coupling face at ", bend_end, " mm"));

// ---------------------------------------------------------------------------
// Design-level asserts. These fail the render, not a lint pass. The coupling's
// own guards live in nuggs_cfg(); what is left is what belongs to THIS design.
// ---------------------------------------------------------------------------
assert(bend_angle > 0 && bend_angle <= 90, str(
    "ELBOW BEND ANGLE: bend_angle = ", bend_angle, " must be in (0, 90]. Past 90",
    " a single sweep doubles back on itself; a full U-turn is a straight plus",
    " two of these elbows."));
assert(port_stub >= z_top, str(
    "ELBOW PORT STUB: port_stub = ", port_stub, " mm is shorter than the port",
    " zone z_top = ", z_top, " mm. Each port fuses to that much straight full-",
    " round shell; a shorter stub leaves its inner sectors fused to the curve.",
    " Raise port_stub."));
// The swept tube OD must clear the bend axis, or the sweep self-intersects.
assert(bend_radius > ro, str(
    "ELBOW BEND RADIUS: bend_radius = ", bend_radius, " mm must exceed the tube",
    " outer radius ro = ", ro, " mm, or the swept tube folds through the bend",
    " axis. ~1.5x bore (", 1.5 * bore_d, " mm) is the intended value."));

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

// Internal edge break at a bore mouth: swallows any first-layer lip so no edge
// is ever presented to a claw or a loaded cheek pouch. Cut, never added; it
// only ever widens the bore. Local frame: mouth at z, opening toward -z.
module bore_lead(z) {
    translate([0, 0, z])
        cylinder(r1 = ri + 1.0, r2 = ri - eps, h = 1.0 / tan(90 - chamfer_ang));
}

// A tube_fn-sided circle of radius r as a 2D point list (the swept section).
function _circ(r) = [for (a = [0 : 360 / tube_fn : 359.999]) r * [cos(a), sin(a)]];

// The centerline path: a vertical inlet stub, the arc, and the tangent outlet
// stub. `ext` extends both straight ends past their coupling faces (used only
// for the bore, so both mouths open). Consecutive points are distinct:
// arc_pos(0) is the inlet stub's top and arc_top is the outlet stub's start, so
// the arc runs from the first step to bend_angle and each straight is one span.
function _path(ext) = concat(
    [[0, 0, -ext], [0, 0, port_stub]],
    [for (i = [1 : max(2, ceil(bend_angle / arc_step))])
        arc_pos(i * bend_angle / max(2, ceil(bend_angle / arc_step)))],
    [arc_top + (port_stub + ext) * dir_out]);

// The whole tube as ONE swept polyhedron of section radius r — no booleans, no
// coincident faces, capped perpendicular to the tangent at each end (which is
// exactly the coupling-face plane). normal locks the section's frame to the
// bend plane so it does not twist along a planar path.
module elbow_solid(r, ext = 0) {
    path_sweep(_circ(r), _path(ext), normal = [0, 1, 0]);
}

// ---------------------------------------------------------------------------
// The elbow: a genderless NUGGS port at each end of the swept tube, sharing one
// cfg. The outer body is tube_outer() with a port fused onto each straight stub;
// then ONE bore (radius ri, overrunning both mouths) is subtracted, so the
// interior is smooth end to end and both mouths open.
//
// Every nuggs_port() is deliberately NOT bore-clean (its collar and inner
// sectors reach inboard of ri to fuse to the tube); the single bore below
// removes that material, exactly as designs/nuggs's straight does with
// nuggs_bore_cut. Here the straight bore cut is the swept bore, which follows
// the tube through the corner. See the library header.
// ---------------------------------------------------------------------------
module nuggs_elbow() {
    difference() {
        union() {
            // Inlet port at the inlet coupling face (z = 0), sectors projecting
            // DOWN to z_tip (the part stands on those sector tips — bed contact).
            nuggs_port(cfg);
            // The swept tube, capped flush at both coupling faces; the ports fuse
            // to its straight stub ends exactly as they do to the straight's tube.
            elbow_solid(ro);
            // Outlet port at the outlet coupling face, on the tilted outlet axis,
            // mirrored so its sectors project outward (away from the tube) —
            // same idiom as the straight's second port.
            translate(bend_end) rotate([0, bend_angle, 0])
                mirror([0, 0, 1]) nuggs_port(cfg);
        }
        // ONE continuous bore, swept the same way and overrunning both ends.
        elbow_solid(ri, bore_over);
        // Edge break at both bore mouths. The inlet mouth is at z = -port_proj
        // (sectors project to z_tip); the outlet port is MIRRORED, so its mouth
        // is at +port_proj in the outlet frame — the same +port_proj offset the
        // straight uses for its mirrored end (nuggs.scad: `l + port_proj`). A
        // -port_proj here would chamfer the tube side and leave the mouth sharp.
        translate([0, 0, -port_proj]) bore_lead(0.001);
        translate(bend_end) rotate([0, bend_angle, 0])
            translate([0, 0, port_proj]) mirror([0, 0, 1]) bore_lead(0.001);
    }
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------

// Two elbows coupled into a 90 deg corner: the intended way to turn a full
// right angle without bore support. Review preview only — each half prints as
// the single `elbow` part. The second elbow is mated to the first's outlet at
// the insertion clocking (half a pitch) and turned a quarter turn in the bend
// plane to sweep the corner the rest of the way.
module pair() {
    color("#e8b7c8") nuggs_elbow();
    translate(bend_end) rotate([0, bend_angle, 0])
        rotate([0, 0, nuggs_pitch(cfg) / 2])
            mirror([0, 0, 1]) color("#cdd6e0") nuggs_elbow();
}

if (part == "elbow") nuggs_elbow();
else if (part == "pair") pair();
else if (part == "cutaway")
    difference() { nuggs_elbow(); translate([-300, 0, -50]) cube([600, 300, 600]); }
else assert(false, str("unknown part: ", part));
