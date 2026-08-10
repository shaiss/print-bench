// N.U.G.G.S. elbow — a curved tube module that routes an 80 mm-bore NUGGS run
// around a corner, carrying the genderless quarter-turn port on each end.
// Requirements, welfare sources and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// This design is a CONSUMER of the NUGGS port standard, exactly like
// designs/nuggs: it builds ONE cfg with nuggs_cfg() and hands it around, and it
// never redefines a coupling number. The only new geometry is the BEND between
// the two ports — a swept annular tube whose bore stays continuous and smooth
// through the corner (a NUGGS welfare non-negotiable: this routes a live animal
// and any interior ledge or step is a hazard).
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
// Straight lead-in past each port collar (mm). Clears the coupling ring and
// gives a grip. Must be >= the port zone depth (z_top); asserted below
lead_in = 30;

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
// shape the tube and the bend sweep, never the joint.
$fa = 3;
$fs = 0.8;

/* [Hidden] */
eps = 0.01;
// Arc sweep step (deg): the bend is lofted as a chain of hull segments; this is
// the angular stride between cross-sections. Small enough that the chord error
// on the outer wall is negligible; it does not touch the coupling.
arc_step = 2;

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
z_top = nuggs_z_top(cfg);   // top of the port zone; the leg must back this much

// Bend geometry. The centerline is a circular arc of radius bend_radius,
// starting at the top of the inlet leg with the tube axis vertical (+z) and
// turning by bend_angle toward +x. Derived once here so no module restates it.
bend_end   = [bend_radius * (1 - cos(bend_angle)),
              0,
              lead_in + bend_radius * sin(bend_angle)];   // outlet-leg origin
// Centerline point on the arc at sweep angle phi (deg), and on the outlet leg
// at distance s past the bend. The arc starts vertical at the inlet-leg top and
// turns toward +x; the outlet leg runs tangent from bend_end.
function arc_pos(phi) = [bend_radius * (1 - cos(phi)), 0,
                         lead_in + bend_radius * sin(phi)];
function out_pos(s)   = bend_end + s * [sin(bend_angle), 0, cos(bend_angle)];

echo(str("nuggs-elbow: bend ", bend_angle, " deg at R", bend_radius,
         " mm, bore ", bore_d, " mm (ri ", ri, "), tube OD ", 2 * ro,
         " mm, port_tol ", port_tol, " mm"));
echo(str("nuggs-elbow: outlet-end centre at ", bend_end, " mm"));

// ---------------------------------------------------------------------------
// Design-level asserts. These fail the render, not a lint pass. The coupling's
// own guards live in nuggs_cfg(); what is left is what belongs to THIS design.
// ---------------------------------------------------------------------------
assert(bend_angle > 0 && bend_angle <= 90, str(
    "ELBOW BEND ANGLE: bend_angle = ", bend_angle, " must be in (0, 90]. Past 90",
    " a single sweep doubles back on itself; a full U-turn is a straight plus",
    " two of these elbows."));
assert(lead_in >= z_top, str(
    "ELBOW LEAD-IN: lead_in = ", lead_in, " mm is shorter than the port zone",
    " z_top = ", z_top, " mm. Each port's inner sectors fuse to the leg's",
    " full-round shell over that depth; a shorter leg leaves them fused to",
    " nothing. Raise lead_in."));
// The inner wall of the bend must not fold through the centre: the tube OD
// swept at bend_radius has to clear the axis, or the sweep self-intersects.
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

// One cross-section disc of radius r, centred at pos, its face normal along the
// local tube axis (tilted ang degrees off vertical toward +x). Thin on purpose:
// it is a loft station, not a solid.
module _disc(r, pos, ang) {
    translate(pos) rotate([0, ang, 0]) cylinder(r = r, h = 0.05, center = true);
}

// The whole tube — inlet leg, bend, outlet leg — as ONE lofted SOLID of radius
// r, from z0 (inlet-leg bottom, on the +z axis) through the arc to distance z1
// along the outlet leg. It is built as a chain of hull() segments that SHARE
// their boundary discs: the top disc of one segment IS the bottom disc of the
// next (same primitive, same tessellation), so the union has no coincident-but-
// mismatched faces — which is exactly the non-manifold trap a cylinder butted
// against a rotate_extrude bend falls into. Straight runs need no subdivision
// (one hull spans them); only the arc is stepped, by arc_step.
module elbow_solid(r, z0, z1) {
    nseg = max(2, ceil(bend_angle / arc_step));
    // inlet leg (vertical): one clean frustum from z0 up to the arc start
    hull() { _disc(r, [0, 0, z0], 0); _disc(r, arc_pos(0), 0); }
    // the arc, stepped
    for (i = [0 : nseg - 1])
        hull() {
            _disc(r, arc_pos(i       * bend_angle / nseg), i       * bend_angle / nseg);
            _disc(r, arc_pos((i + 1) * bend_angle / nseg), (i + 1) * bend_angle / nseg);
        }
    // outlet leg (tangent): one clean frustum from the arc end out to z1
    hull() { _disc(r, out_pos(0), bend_angle); _disc(r, out_pos(z1), bend_angle); }
}

// ---------------------------------------------------------------------------
// The elbow: a genderless NUGGS port at each end of a bent tube, sharing one
// cfg. Built as a single SOLID body (inlet leg + bend + outlet leg + both port
// rings), then ONE continuous bore is subtracted through the whole path so the
// interior is smooth end to end with no ledge at either junction.
//
// Every nuggs_port() is deliberately NOT bore-clean (its collar and inner
// sectors reach inboard of ri to fuse to the tube); the single bore cut below
// removes that material, exactly as designs/nuggs's straight does. See the
// library header.
// ---------------------------------------------------------------------------
module nuggs_elbow() {
    difference() {
        union() {
            // Inlet port at z = 0, sectors projecting DOWN to z_tip (the part
            // stands on those sector tips — this is the bed contact).
            nuggs_port(cfg);
            // The whole tube body: inlet leg + bend + outlet leg, one lofted
            // solid the two ports fuse to over their full-round shells.
            elbow_solid(ro, 0, lead_in);
            // Outlet port at the far end of the outlet leg, mirrored so its
            // sectors project outward (away from the tube), same idiom as the
            // straight's second port.
            translate(bend_end) rotate([0, bend_angle, 0])
                translate([0, 0, lead_in]) mirror([0, 0, 1]) nuggs_port(cfg);
        }
        // ONE continuous bore, lofted the same way as the body so the interior
        // is smooth end to end, overshooting past both port mouths.
        elbow_solid(ri, -port_proj - 2, lead_in + port_proj + 2);
        // Edge break at both bore mouths.
        translate([0, 0, -port_proj]) bore_lead(0.001);
        translate(bend_end) rotate([0, bend_angle, 0])
            translate([0, 0, lead_in + port_proj]) mirror([0, 0, 1])
                bore_lead(0.001);
    }
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------

// Two elbows coupled into a 90 deg corner: the intended way to turn a full
// right angle without bore support. Review preview only — each half prints as
// the single `elbow` part. The second elbow is mated to the first's outlet at
// the insertion clocking (half a pitch) and rotated a quarter turn in the
// bend plane to sweep the corner the rest of the way.
module pair() {
    color("#e8b7c8") nuggs_elbow();
    translate(bend_end) rotate([0, bend_angle, 0])
        translate([0, 0, lead_in]) rotate([0, 0, nuggs_pitch(cfg) / 2])
            mirror([0, 0, 1]) color("#cdd6e0") nuggs_elbow();
}

if (part == "elbow") nuggs_elbow();
else if (part == "pair") pair();
else if (part == "cutaway")
    difference() { nuggs_elbow(); translate([-300, 0, -50]) cube([600, 300, 600]); }
else assert(false, str("unknown part: ", part));
