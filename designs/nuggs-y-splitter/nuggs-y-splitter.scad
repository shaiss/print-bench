// N.U.G.G.S. Y-splitter — a junction module that branches an 80 mm-bore NUGGS
// run into two paths: one inlet port, two symmetric outlets at a 60 deg
// included angle (branch_half = 30 deg each off the inlet axis), all three
// faces carrying the standard genderless quarter-turn bayonet port.
// Branching was the one topology the NUGGS ecosystem could not do — every
// other module is a two-port single-path part. Requirements, welfare sources
// and decisions: see NOTES.md next to this file. All dimensions in mm.
//
// This design is a CONSUMER of the port standard, exactly like designs/nuggs
// and designs/nuggs-elbow: it builds ONE cfg with nuggs_cfg() defaults and
// hands it around, never redefining a coupling number. The only new geometry
// is the FORK, and the constraint on it is a NUGGS welfare non-negotiable:
// the animal's passage stays a smooth, continuous ~80 mm bore through the
// junction, no interior ledge.
//
// CONSTRUCTION — union(shells) - union(cavities), never per-arm. The three
// straight arm shells meet at the fork centre O; their union IS the miter.
// The cavity is ONE union of three ri cylinders PLUS a junction blend
// sphere at O, subtracted afterwards — the ordering that stops an interior
// wall standing across the fork (nuggs-yard's wye lesson). The sphere is the
// piece that makes the bore LEDGE-FREE rather than merely open: three flat
// cylinder caps meeting near each other's walls leave sub-mm exposed
// crescents (measured 0.45 mm at a 12 mm overrun — a lip on the passage
// wall), and a sphere of radius ro - 3*nozzle swallows every cap disc
// whole (farthest cap point sqrt(ri^2 + overrun^2) = 40.45 mm against the
// sphere's 41.2), so no cap face exists in the finished geometry at all.
// The interior is three 80 mm bores opening into one smooth 82.4 mm blend —
// the passage only ever widens, and a widening wall cannot catch a paw.
//
// No cap lands flush on a free face or on another cavity's wall: the port
// faces are cut square on the coupling planes (the elbow's flush-capped
// precedent), and every interior cap is buried inside the sphere, every
// intersection transverse — the coincident-surface class that CGAL tolerates
// and CI's Manifold backend does not (nuggs-yard defect 5) is absent by
// construction.
//
// WHY A MITER, NOT SWEPT ARCS: at 30 deg half-angle the two branch tubes
// (OD 84.8) stay fused until ro/sin(branch_half) = 84.8 mm from O whatever
// the path — the fork is intrinsically a long wedge — so arcs buy bulk, not
// welfare. A straight miter also puts every junction surface at 30 deg from
// vertical in the print pose (a 30 deg-tilted tube's lowest generator is a
// 30 deg-from-vertical plane), comfortably under the ~45 deg supportless
// ceiling issue #34 measured and the elbow documents as its own limit.
//
// PRINT: inlet port down, exactly like the NUGGS straight and elbow — the
// inlet's three coupling-sector tips are the bed contact, the bore vertical
// at the inlet, both branches rising at 30 deg.
use <nuggs-coupling.scad>

/* [What to render] */
// ysplit = the printable part; cutaway = sectioned to inspect the bore;
// coupon = the print-this-first fit coupon (normally via the wrapper)
part = "ysplit";  // [ysplit, cutaway, coupon]

/* [The NUGGS standard - change these and nothing you already printed fits] */
// Every value here is a nuggs_cfg() default: the Y-splitter inherits the
// standard so it mates with designs/nuggs, nuggs-elbow and every other
// module. Exposed for the Customizer, not for tuning — the coupling guards
// fire inside nuggs_cfg().
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
// The one knob. Uniform clearance on every coupling surface (mm). Owned by
// the standard; tuned on the coupon below and designs/nuggs's, not re-tuned
// here. Asserted 0.10-0.60 by the lib
port_tol = 0.30;

/* [The fork] */
// Branch half-angle (deg): each outlet axis sits this far off the inlet
// axis, so the included fork angle is twice this. DEFAULT 30 = the brief's
// assumed value: the fork's steepest interior surface then stands 30 deg
// from vertical in the print pose, supportless with margin under the ~45 deg
// overhang ceiling issue #34 measured. Bound 20-40: below 20 the fused
// wedge runs past the ports themselves; above 40 the fork interior enters
// the overhang class the elbow documents as needing bore support.
branch_half = 30;  // [20:40]
// Straight full-round shell behind each port (mm) — the port zone depth
// (z_top = 13) plus a short grip, exactly the elbow's port_stub. Each port's
// inner sectors fuse to this shell; inboard of it the arm is mitered at O.
port_stub = 16;
// Inlet axis length, fork centre O to the inlet coupling face (mm). The brief
// said ~80 assumed; 60 is what a 256×256×256 bed actually swallows (see the
// bed-fit assert and NOTES.md — PrusaSlicer's stock 250 mm Z height is the
// binding constraint, measured). The brief's "~80 mm" named the ATOMIC
// dimension, and the assert keeps the miter clear of the port zone; anything
// past 64 puts the sector tips over the height limit.
inlet_len = 60;

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
// Production: $fa=2/$fs=0.5. It does NOT reach the coupling: the library
// pins its own $fa/$fs inside every geometry module body, deliberately, so
// the realised fit cannot move with a consumer's quality preset. These
// settings shape the straight arm tubes, never the joint.
$fa = 3;
$fs = 0.8;

// Facets around each arm's tube section. Iterating: 48. Production: 64+.
tube_fn = 48;

/* [Hidden] */
eps = 0.01;
// Extra bore length past each port mouth (mm), so all three mouths open past
// their sector tips (which project port_proj past the coupling face). Same
// value and purpose as the elbow's bore_over.
bore_over = port_proj + 2;
// How far the INLET cavity runs past O before its cap (mm). The cap must
// bury inside the blend sphere (asserted), which caps the overrun at ~8 mm.
cav_in = 8;
// How far each BRANCH cavity runs past O (mm). Same burial constraint.
cav_br = 6;
// Bed-contact edge-break height at each bore mouth (mm)
chamfer_h = 1.0 / tan(90 - chamfer_ang);
// Coupon stub length (mm) - the wrapper overrides this
coupon_len = 24;

// ---------------------------------------------------------------------------
// The coupling configuration — ONE cfg, built once, handed to every port
// call. Every coupling guard fires inside nuggs_cfg(); they are not restated
// here.
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

// Junction blend sphere radius (mm): the largest sphere at O that leaves a
// 3-extrusion web at the x-side miter, where the sphere runs closest to the
// exterior (web = ro - sphere_r there, growing away from z = 0).
web_min  = 3 * nozzle;
sphere_r = ro - web_min;

// Branch arm length, DERIVED not a knob — from the ASSEMBLY clearance, which
// is the binding constraint at a fork. Sliding a mating module onto outlet A
// sweeps its sector tips (radius r_out about A's axis) down to 10 mm past
// A's face; outlet B's own ring (radius r_out about B's axis, outboard of
// B's face) must stay clear of that sweep. The closest approach works out to
// the two face centres' separation minus the two ring radii, so the arms must
// be at least 2*r_out apart at the faces; +5 mm margin (measured ~16 mm real
// clearance at branch_half = 30 — the bound is conservative because the two
// tip bands are coplanar-tilted, not facing). port_stub is the floor.
branch_len = max(port_stub + 5, 2 * r_out + 5);

// ---------------------------------------------------------------------------
// Design-level asserts. These fail the render, not a lint pass. The
// coupling's own guards live in nuggs_cfg(); what is left belongs to THIS
// design.
// ---------------------------------------------------------------------------
assert(branch_half >= 20 && branch_half <= 40, str(
    "YSPLIT BRANCH HALF-ANGLE: branch_half = ", branch_half, " deg must be in",
    " [20, 40]. Below 20 the fused wedge between the branches runs past the",
    " ports themselves; above 40 the fork interior enters the ~45 deg",
    " overhang class that needs support inside the bore (issue #34; the",
    " elbow documents 45 as the limit)."));
assert(port_stub >= z_top, str(
    "YSPLIT PORT STUB: port_stub = ", port_stub, " mm is shorter than the",
    " port zone z_top = ", z_top, " mm. Each port fuses to that much straight",
    " full-round shell; a shorter stub leaves its inner sectors fused to the",
    " mitered junction face instead of a ring. Raise port_stub."));
assert(inlet_len >= port_stub + 10, str(
    "YSPLIT INLET LENGTH: inlet_len = ", inlet_len, " mm must exceed",
    " port_stub (", port_stub, ") by at least 10 mm so the miter at O clears",
    " the port zone; otherwise the junction geometry eats the port's backing",
    " shell."));
// Bed fit, measured not assumed: the print-pose envelope is
// inlet_len + port_proj tall on the inlet side plus (branch_len + port_proj)
// * cos(branch_half) on the branch side, and (branch_len + port_proj)
// * sin(branch_half) + r_out wide. 250 is PrusaSlicer's STOCK build height
// (the number the gate's test-slice enforces); the design targets the same
// 256x256x256 class of bed the elbow records, so 200 leaves headroom for a
// brim and a colder chamber.
assert(inlet_len + port_proj + (branch_len + port_proj) * cos(branch_half)
       <= 200, str(
    "YSPLIT BED FIT: the print-pose height ", inlet_len + port_proj +
    (branch_len + port_proj) * cos(branch_half), " mm exceeds the 200 mm",
    " self-imposed height budget (PrusaSlicer's stock 250 mm Z is the hard",
    " wall; the gate's test-slice fails above it). Cut inlet_len."));
assert(bore_over >= port_proj + 2, str(
    "YSPLIT BORE OVERRUN: bore_over = ", bore_over, " must open every mouth",
    " past the sector tips (port_proj + 2 = ", port_proj + 2, ")."));
// The ledge-free guarantee, stated as the burial condition: every cavity cap
// disc must sit strictly inside the blend sphere, or a crescent of cap face
// survives on the passage wall as a lip. The disc's farthest point from O is
// its rim, at sqrt(ri^2 + overrun^2).
assert(sphere_r > sqrt(pow(ri, 2) + pow(cav_in, 2)) + 0.3, str(
    "YSPLIT CAP BURIAL (inlet): sphere_r = ", sphere_r, " does not bury the",
    " inlet cavity cap (rim at sqrt(ri^2+cav_in^2) = ",
    sqrt(pow(ri, 2) + pow(cav_in, 2)), " with cav_in = ", cav_in,
    "). An exposed cap crescent is an interior ledge — cut cav_in or raise",
    " sphere_r toward ro - 3*nozzle."));
assert(sphere_r > sqrt(pow(ri, 2) + pow(cav_br, 2)) + 0.3, str(
    "YSPLIT CAP BURIAL (branch): sphere_r = ", sphere_r, " does not bury the",
    " branch cavity cap (rim at sqrt(ri^2+cav_br^2) = ",
    sqrt(pow(ri, 2) + pow(cav_br, 2)), " with cav_br = ", cav_br,
    "). An exposed cap crescent is an interior ledge — cut cav_br or raise",
    " sphere_r toward ro - 3*nozzle."));
assert(sphere_r > ri + 1, str(
    "YSPLIT BLEND: sphere_r = ", sphere_r, " must open the junction at least",
    " 1 mm past the bore radius (", ri, ") or it blends nothing and the cap",
    " burial above has no margin to work in."));
// Assembly clearance: a mating module sliding onto either outlet sweeps its
// sector tips at radius r_out about that axis; the other outlet's ring must
// not stand in the sweep. At the faces the closest approach is the face
// centres' separation minus the two ring radii.
assert(branch_len > 2 * r_out, str(
    "YSPLIT ASSEMBLY: branch_len = ", branch_len, " mm does not separate the",
    " two outlet faces enough to mate a module onto either one — a mating",
    " port's sector-tip sweep (radius ", r_out, " about the axis) collides",
    " with the other outlet's coupling ring. Need > ", 2 * r_out, " mm."));

echo(str("nuggs-y-splitter: ", bore_d, " mm bore, fork 2x", branch_half,
         " deg, inlet ", inlet_len, " mm, branches ", branch_len, " mm,",
         " blend sphere R", sphere_r, ", tube OD ", 2 * ro, ", ring OD ",
         2 * r_out));

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

// Internal edge break at a bore mouth: swallows any first-layer lip so no
// edge is ever presented to a claw or a loaded cheek pouch. Cut, never
// added; it only ever widens the bore. Local frame: the WIDE end (r1) at
// z = 0 — the mouth's outermost reach — narrowing back into the bore.
module bore_lead() {
    cylinder(r1 = ri + 1.0, r2 = ri - eps, h = chamfer_h);
}

// ---------------------------------------------------------------------------
// The Y-splitter. PRINT frame: fork centre O at the origin, inlet axis along
// -z (coupling face at z = -inlet_len, sectors beyond it to -inlet_len -
// port_proj = the bed contact), branches along rotate([+/-branch_half, 0, 0])
// of +z, fork plane the yz-plane.
// ---------------------------------------------------------------------------
module ysplit() {
    difference() {
        union() {
            // Inlet arm: port at the face, sectors toward the bed (unmirrored
            // — the straight's and elbow's inlet idiom), plus its straight
            // shell from the face up to O. The shell's top cap at z = 0 is an
            // INTERIOR face: it is covered by the branch shells above it
            // everywhere inboard of the miter line.
            translate([0, 0, -inlet_len]) nuggs_port(cfg);
            translate([0, 0, -inlet_len]) cylinder(r = ro, h = inlet_len,
                                                   $fn = tube_fn);
            // Branch arms: shell from O out to the coupling face, port
            // mirrored there so its sectors project AWAY from the body (the
            // elbow's outlet idiom) and its tube body fuses back into the
            // shell's last z_top mm.
            for (s = [-1, 1]) {
                rotate([s * branch_half, 0, 0]) {
                    cylinder(r = ro, h = branch_len, $fn = tube_fn);
                    translate([0, 0, branch_len]) mirror([0, 0, 1])
                        nuggs_port(cfg);
                }
            }
        }
        // ONE cavity: three ri cylinders plus the blend sphere, as a single
        // union so nothing internal survives the fork. Inlet: open past the
        // mouth (tips at -inlet_len - port_proj), capped cav_in past O —
        // buried in the sphere. Branches: open past the mouth, capped cav_br
        // past O — buried the same way.
        union() {
            translate([0, 0, -inlet_len - bore_over])
                cylinder(r = ri, h = inlet_len + bore_over + cav_in,
                         $fn = tube_fn);
            for (s = [-1, 1])
                rotate([s * branch_half, 0, 0])
                    translate([0, 0, -cav_br])
                        cylinder(r = ri, h = branch_len + bore_over + cav_br,
                                 $fn = tube_fn);
            sphere(r = sphere_r, $fn = tube_fn * 2);
        }
        // Edge breaks at all three bore mouths. Inlet mouth (unmirrored
        // port): tips at -inlet_len - port_proj, wide end outermost. Branch
        // mouths (mirrored ports): tips at branch_len + port_proj along the
        // branch axis; the mirror flips bore_lead's taper to put the wide
        // end outermost there too.
        translate([0, 0, -inlet_len - port_proj]) bore_lead();
        for (s = [-1, 1])
            rotate([s * branch_half, 0, 0])
                translate([0, 0, branch_len + port_proj])
                    mirror([0, 0, 1]) bore_lead();
    }
}

// "Print this first" coupon: two production port stubs side by side, straight
// from the production cfg and modules — nothing copied. Tune port_tol here in
// +/-0.05 steps before committing a full splitter to the bed, and caliper the
// bore: under 79.0 mm means the printer is shrinking.
module ysplit_coupon(stub = coupon_len) {
    for (s = [-1, 1])
        translate([0, s * (r_out + 6), 0]) {
            nuggs_port(cfg);
            difference() {
                cylinder(r = ro, h = stub, $fn = tube_fn);
                translate([0, 0, -bore_over])
                    cylinder(r = ri, h = stub + 2 * bore_over, $fn = tube_fn);
            }
        }
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------

if (part == "ysplit") ysplit();
else if (part == "coupon") ysplit_coupon();
else if (part == "cutaway")
    // Section through the fork plane (the yz-plane) — shows both branch bores
    // and the inlet meeting at O inside the blend sphere.
    difference() { ysplit(); translate([-300, 0, -150]) cube([600, 300, 400]); }
else assert(false, str("unknown part: ", part));
