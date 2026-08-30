// N.U.G.G.S. turnaround node — the run-resetter: a widened chamber carrying the
// standard genderless quarter-turn port on two faces, wide enough inside that
// an adult Syrian hamster can enter, turn 180°, and leave. Requirements,
// welfare sources and decisions: see NOTES.md next to this file. All
// dimensions in millimeters.
//
// WHY THIS MODULE EXISTS (charter N2, designs/nuggs/PM.md): no continuously
// enclosed run may exceed 2 × body length between BREAKS, and there are only
// three breaks — an open end, an open module, and a turnaround node of clear
// internal width ≥ body length that is itself open to ventilated space. This
// is the third one; without it no layout larger than one straight is legal.
//
// TOPOLOGY. Two ports on the SAME face, axes parallel, one chamber: the animal
// enters port A, walks onto the chamber floor, pivots, leaves port B — the
// switchback every NUGGS run needs to double back. The ports stay parallel
// (never opposed): a U-bend TUBE would put its ceiling at 90° to the bed
// (issue #34's measured supportless ceiling is 45°), so the turn happens in a
// WIDENED CHAMBER instead, whose ceiling closes at the same shallow oblateness
// the den's crown cone uses.
//
// CONSTRUCTION — union(shells) − union(cavities), the y-splitter's discipline.
// The shell is the convex hull of the two full-round neck shells plus an
// oblate chamber ellipsoid: the hull fills the gap between the necks SOLID
// from the port faces up (the web — no bridge anywhere above z = 0, and the
// part's biggest adhesion patch beside the two port rings). The cavity is a
// UNION, never a hull: a hull of the two ri bores would bridge the 12 mm gap
// BETWEEN them at every height and hollow the web out under the chamber
// floor. Instead each bore stays its own cylinder open past its sector tips
// (the nuggs_bore_cut every port caller owes — a port is NOT bore-clean), and
// the inner ellipsoid swallows both bore caps whole (asserted below), so the
// finished interior is two 80 mm bores opening into one smooth dish — the
// passage only ever widens from each mouth, and a widening wall cannot catch
// a paw.
//
// THE FLOOR (N6/N11, the brief's "ramp ... meeting the bore's own arc"). The
// chamber floor is the ellipsoid's dish — its +x flank, which is the use-frame
// floor (print +x is use-down; see the frame note at `animal_path_sweep`).
// The ellipsoid is sized so its dish passes the mouth invert lines ~1 mm
// below the bore floor: the walking route steps DOWN 1.08 mm onto the dish (a
// widening, never a lip), then crosses at a grade that peaks 14.6 deg at the
// mouth lines, inside N4's 15 deg ceiling (asserted). The turn itself happens
// in the dish's bowl, which self-centres the animal.
//
// THE ONE BRIDGE (known, accepted): below z = 0 the mating tube's full-round
// body (radius ro about each port axis) must swing in unobstructed, so the
// web cannot start until the port face plane — the hull's flat underside
// spans the 12.2 mm gap between the necks at z = 0, 10 mm above the bed,
// anchored on the port faces' discs both sides. 12 mm is routine bridge
// territory for a stock slicer; recorded in NOTES.md, and printcheck + the
// test-slice gate it.
//
// PRINT. Both ports stand on their sector tips exactly like the NUGGS
// straight (the family bed-contact idiom), bore vertical at both ports; the
// solid web between them adds a 12 x 205 mm adhesion patch at the face plane.
// In USE the module lies ports-horizontal on any side that keeps the run
// near-level; the dish is the floor and the vented flank is the ceiling.
use <nuggs-coupling.scad>
use <printability.scad>   // teardrop_hole for the vents

/* [What to render] */
// turnaround = the printable part; coupon = fit stub; cutaway = section on the
// port-axis plane; cutaway-cross = section across the turn axis at y = 0;
// cutaway-ridge = section on the ridge plane (x = 0), where the roof slot
// lived (#499); path-clear / path-clear-ctrl = the swept-animal fitchecks
part = "turnaround";  // [turnaround, coupon, cutaway, cutaway-cross, cutaway-ridge, path-clear, path-clear-ctrl]

/* [The NUGGS standard - change these and nothing you already printed fits] */
// Every value here is a nuggs_cfg() default: this module inherits the standard
// so it mates with designs/nuggs and every other module. Exposed for the
// Customizer, not for tuning — the coupling guards fire inside nuggs_cfg().
// Internal bore (mm) — the headline number. Asserted >= min_bore_mm by the lib
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
// the standard; tuned on the coupon, not re-tuned here. Asserted 0.10-0.60
// by the lib
port_tol = 0.30;

/* [The turnaround] */
// Centre-to-centre separation of the two port axes (mm). Floor: a mating
// module sliding onto either port sweeps its sector tips at r_out about that
// axis — the other port's ring must stay out of that sweep (the same 2*r_out
// assembly bound the y-splitter asserts on its branch faces).
port_gap = 97;
// Chamber ellipsoid inner semi-axes (mm): x = use-vertical (headroom + dish),
// y = across the turn (the cavity's widest line along y is the clear internal
// width N2 gates — measured by crown guard (4), since the hip can trim it),
// z = the
// print-pose vertical / use-travel direction at the mouths' height. 90 keeps
// the total inside the 200 mm ceiling the gate's bare-default test-slice
// enforces (see the bed-fit assert) once the centre sits flush (chamber_zc).
// The far-end overhang is NOT this semi-axis' problem: it is the crown cap,
// and crown_zt below closes it on a cone (measured, gate iterations 2-3 —
// az 95->90 moved the printcheck overhang figure the WRONG way, 9274 ->
// 9459 mm2, because a flatter-in-z ellipsoid has a BIGGER near-horizontal
// polar cap; the fix is the cone, not the semi-axis).
chamber_ax = 47;
chamber_ay = 100;
chamber_az = 90;
// Chamber ellipsoid centre height above the port face plane (mm). The neck
// shells run from the face (z = 0) to exactly this height, where the
// ellipsoid is widest in x and the bore caps bury deepest. 92.4 = chamber_az
// + wall exactly: the outer belly's bottom pole then lands FLUSH with the
// port face plane, so no material hangs below the web bridge into air over
// the bed (at zc = 90 the pole dipped 2.4 mm below it — ~800 mm2 of measured
// unbridgeable overhang; over the bridge plane and the neck shells the same
// dome surface is layer-over-solid and prints fine). Asserted below.
chamber_zc = 92.4;

/* [Welfare limits - asserted, not tunable down] */
// Assumed adult-Syrian head-and-body length (mm) — Merck upper range, the
// recorded system assumption (designs/nuggs/NOTES.md). The chamber's clear
// internal width must meet or exceed it for this module to be a legal break.
body_len_mm = 180;
// DTSchB entrance minimum, pouch-full criterion (mm). NEVER lower this.
// The bore floor itself is asserted inside nuggs_cfg()
min_bore_mm = 70;
// Charter N4 maximum incline of any walkable ramp (deg). NEVER raise this.
max_incline_deg = 15;

/* [Vents] */
// Teardrop vents through the use-ceiling flank, so the chamber is open to
// ventilated space — the second half of N2's break definition (a sealed wide
// chamber is a dead volume, and N3 forbids it). Count and bore sized on the
// den's chimney vocabulary: the smallest pair whose open area matches the
// den's six 9 mm chimneys, derivation in NOTES.md. The flank is inverted in
// use, so a hole in it offers no purchase for powered gnawing (the den's
// recorded rationale) — and see the upper-half assert.
n_vent = 6;
vent_d = 9;

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
// settings shape the chamber shell, never the joint.
$fa = 3;
$fs = 0.8;

// Facets around each neck's tube section. Iterating: 48. Production: 64+.
// Ships at the production value: the bore is the walking surface, so
// smoother is the product's own priority.
tube_fn = 64;
// Facets on the ellipsoid's latitudes. The chamber is the animal's turning
// surface, so it gets the finer of the two presets.
ell_fn = 96;

/* [Hidden] */
eps = 0.01;
// Bore overrun past the sector tips (mm), so both mouths open past the tips
// and the port's inboard collar material is cut — the cut every nuggs_port()
// caller owes (the library header's watertight-with-plastic-in-the-bore trap).
bore_over = port_proj + 2;
// Bed-contact edge-break height at each bore mouth (mm)
chamfer_h = 1.0 / tan(90 - chamfer_ang);

// ---------------------------------------------------------------------------
// The coupling configuration — ONE cfg, built once, handed to every port
// call. Every coupling guard fires inside nuggs_cfg(); none is restated here.
// ---------------------------------------------------------------------------
cfg = nuggs_cfg(bore_d    = bore_d,    wall      = wall,      lug_r    = lug_r,
                port_proj = port_proj, collar_t  = collar_t,  n_lug    = n_lug,
                lug_deg   = lug_deg,   rib_h     = rib_h,     rib_w    = rib_w,
                rib_deg   = rib_deg,   twist_deg = twist_deg, bite     = bite,
                port_tol  = port_tol,  eps       = eps,       nozzle   = nozzle,
                min_bore  = min_bore_mm);

// The handful of contract values this design reaches for.
ri    = nuggs_ri(cfg);       // bore radius
ro    = nuggs_ro(cfg);       // tube outer radius — the port fuses to this
r_out = nuggs_r_out(cfg);    // coupling ring OD / envelope
z_tip = nuggs_z_tip(cfg);    // sector tips (bed contact), = -port_proj
z_top = nuggs_z_top(cfg);    // top of the port zone; a face needs this much shell

// Where the necks end and the chamber's hull takes over. The bores' and
// shells' top caps sit at the ellipsoid's equator height, where the inner
// ellipsoid is at its WIDEST in x — the cap burial condition (below) is then
// easiest to satisfy, and the mouth handoff sits at the chamber's midline.
z_join = chamber_zc;

// CROWN CAP (printability, den's recorded rule: "no flat internal ceiling —
// close to a point"). Above the height crown_zt the cavity stops following
// the ellipsoid and closes on a HIP ROOF: the gable whose two roof planes
// rise from the cross-section's x extremes at atan(vault_h / crown_xt) >= 45
// deg (the supportless enclosed-ceiling limit issue #34 measured) to a ridge
// along y, PLUS two hip planes descending in |y| at crown_hip_deg — the
// cavity's crown boundary is the POINTWISE MINIMUM of (inner ellipsoid,
// x-gable, y-hip), built as one intersection() in chamber_cavity below,
// never a union. Three dead ends are recorded here because each looked
// right: (1) the ellipsoid's own polar cap is a near-horizontal ceiling —
// everything within atan(a/c) = 27.6 deg of the top pole in x exceeds 45
// deg, ~9400 mm2 of printcheck-measured unbridgeable overhang (gate
// iterations 2-3; a facet scan put the bulk at z = 160..180, the crown —
// NOT the belly the first fix chased); (2) a single-apex ELLIPTIC CONE over
// the same footprint went the WRONG way (9459 -> 15835 mm2, iteration 4):
// one apex over a 39 x 83 base cannot be 45 deg in both profiles — matching
// x forces the y-profile to a/b = 0.47, 25 deg from horizontal, a WORSE
// ceiling over more area; (3) the BARREL VAULT alone (the cap as first
// shipped, issue #499): a gable-and-prism vault UNIONED onto the truncated
// ellipsoid. Its ridge line ran along y at constant height z = 181.4 while
// the outer dome falls off in y — the dome crosses below the ridge at
// |y| = 27.6 mm, well inside the vault's |y| <= 84.9 footprint, so the
// cavity was OPEN TO THE AIR over both y-ends, up to ~60 mm wide (~2000 mm2
// per end). The union was the bug: a unioned cap can rise past the shell
// anywhere the outer surface falls faster than the cap does, and the y = 0
// crown asserts could not see it (y = 0 is the one meridian where the shell
// is thickest and the slot absent). An intersection cannot outrun the
// ellipsoid anywhere — the ceiling IS the lowest of the three surfaces —
// and the SAMPLED guards below hold shell over the whole crown, which is
// the check that would have fired. The gable's eaves still meet the inner
// ellipsoid's cross-section at crown_zt exactly (no step; the passage only
// ever widens downward), and the cap costs the animal nothing: the route's
// highest envelope point is chamber_zc + 32.4 = 124.8 mm.
crown_zt = 140;

// The dish depth at the mouth centreline (mm): how far the chamber floor
// stands BELOW the bore floor where they meet, both measured in print x (the
// use-frame vertical). Positive = the dish dips (a widening step-down the
// animal walks onto, never a lip). The union's transition spreads it over
// ~19 mm of travel, and the assert bounds it.
dish_at_mouth = chamber_ax * sqrt(1 - pow(port_gap / 2 / chamber_ay, 2)) - ri;

// Max lateral grade of the walking route across the dish (deg): mouth A's
// floor -> dish bottom -> mouth B's floor. The dish's slope, evaluated at the
// mouth's y — its steepest point ON the route (it eases to 0 deg at the bowl
// bottom, and the bore floor itself is flat).
function dish_grade_at(y) =
    atan(chamber_ax * y
         / (pow(chamber_ay, 2) * sqrt(1 - pow(y / chamber_ay, 2))));
dish_grade_deg = dish_grade_at(port_gap / 2);

echo(str("nuggs-turnaround: bore ", bore_d, " mm, ports ", port_gap,
         " mm apart, chamber ", 2 * chamber_ax, " x ", 2 * chamber_ay, " x ",
         2 * chamber_az, " mm"));
echo(str("nuggs-turnaround: dish dips ", dish_at_mouth, " mm at the mouths,",
         " route grade peaks ", dish_grade_deg, " deg, overall ",
         2 * (chamber_ay + wall), " x ", 2 * (chamber_ax + wall), " x ",
         chamber_zc + chamber_az + wall - z_tip, " mm on the bed"));

// ---------------------------------------------------------------------------
// Design-level asserts. These fail the render, not a lint pass. The coupling's
// own guards live in nuggs_cfg(); what is left belongs to THIS module.
// ---------------------------------------------------------------------------

// ASSEMBLY: a mating module sliding onto either port sweeps its sector tips
// at radius r_out about that axis; the other port's ring must stay out of
// that sweep (the y-splitter's bound).
assert(port_gap >= 2 * r_out, str(
    "TURNAROUND PORT GAP: port_gap = ", port_gap, " mm puts the two coupling",
    " rings (OD ", 2 * r_out, " mm) in each other's sector-tip sweep. A mating",
    " module cannot slide onto either port. Need >= ", 2 * r_out, " mm."));

// Each port face must be backed by at least z_top of FULL-ROUND shell (the
// nuggs_neck rule, restated because this design builds its own backing).
assert(z_join >= z_top, str(
    "TURNAROUND NECK: the neck shells run ", z_join, " mm but the port zone",
    " needs z_top = ", z_top, " mm of full-round shell behind the face or its",
    " inner sectors have no ring to fuse to."));

// THE BREAK (charter N2): clear internal width >= body length — the number
// that makes the module a legal run-resetter. Asserted with the crown guards
// below (#499): the hip makes the built cavity's widest line a function of
// the cap, so the check lives where the cap is defined.

// THE FLOOR (N6/N11): the dish must meet the bore's own arc. Two conditions:
// the dish never rises ABOVE the bore floor (that would be a lip into the
// bore), and it dips only a little (a deep ditch at the mouth is a bedding
// trap and a toe-stub of its own).
assert(dish_at_mouth >= 0, str(
    "TURNAROUND DISH: the chamber floor stands ", -dish_at_mouth,
    " mm ABOVE the bore floor at the mouth — that is a lip into the passage",
    " (N6) and a step up (N11). Raise chamber_ax or narrow chamber_ay until",
    " the dish meets the bore's own arc at or below the floor."));
assert(dish_at_mouth <= 1.5, str(
    "TURNAROUND DISH: the chamber floor dips ", dish_at_mouth,
    " mm below the bore floor at the mouth. Past ~1.5 mm the transition",
    " reads as a ditch across the walking route. Lower chamber_ax or widen",
    " chamber_ay."));
// ...and the passage only ever widens: the ellipsoid must be at least as wide
// as the bore IN THE MOUTH'S OWN SLICE, or the ceiling pinches in over the
// animal just past the mouth (the y-splitter's widening rule).
assert(chamber_ax * sqrt(1 - pow(port_gap / 2 / chamber_ay, 2)) >= ri, str(
    "TURNAROUND WIDENING: at the mouth's slice the chamber is ",
    chamber_ax * sqrt(1 - pow(port_gap / 2 / chamber_ay, 2)),
    " mm in radius against the bore's ", ri, " — the passage NARROWS past the",
    " mouth, and a narrowing wall can catch a paw. Raise chamber_ax."));

// N4: the walking route's grade across the dish, measured analytically at its
// steepest on-route point (the mouth lines).
assert(dish_grade_deg <= max_incline_deg, str(
    "TURNAROUND GRADE: the walking route crosses the dish at ",
    dish_grade_deg, " deg against N4's ", max_incline_deg,
    " deg maximum incline. Flatten the dish (widen chamber_ay or lower",
    " chamber_ax)."));

// CAP BURIAL (the y-splitter's discipline): each bore's top cap must sit
// strictly INSIDE the inner ellipsoid, or a crescent of cap face survives on
// the passage wall as a lip. The cap disc is ri about the neck axis,
// port_gap/2 off centre, at z = z_join where the ellipsoid is widest in x;
// its farthest point out of the ellipsoid is the rim in the x direction, so
// the burial test is the ellipsoid's x-extent at the mouth's centreline y.
assert(chamber_ax * sqrt(1 - pow(port_gap / 2 / chamber_ay, 2)) > ri + 0.5, str(
    "TURNAROUND CAP BURIAL: the inner ellipsoid's x-extent at the mouth's y (",
    chamber_ax * sqrt(1 - pow(port_gap / 2 / chamber_ay, 2)),
    " mm) does not bury the bore caps (rim at ", ri,
    " + 0.5 margin). An exposed cap crescent is an interior ledge."));
assert((chamber_ax + wall) * sqrt(1 - pow(port_gap / 2 / (chamber_ay + wall), 2))
       > ro + 0.3, str(
    "TURNAROUND CAP BURIAL (shell): the outer ellipsoid's x-extent at the",
    " necks' y (", (chamber_ax + wall)
        * sqrt(1 - pow(port_gap / 2 / (chamber_ay + wall), 2)),
    " mm) does not bury the neck-shell caps (rim at ", ro,
    " + 0.3 margin). An exposed shell cap is a coincident-face hazard."));

// BED FIT, measured not assumed: height from the sector tips to the crown,
// footprint across the full envelope including the port rings. The binding
// number is 199 — the gate's test-slice runs PrusaSlicer on BARE defaults,
// whose build volume caps Z at exactly 200.0 mm (measured here: a 200.0 mm
// box slices, a 201 mm box does not; XY is NOT enforced — 250 mm boxes slice
// clean). That is not the 250 mm Z of any stock printer definition and not
// printcheck's 256 mm class below, which gates the physical bed the design
// targets; the 1 mm inside the ceiling is parametric margin.
assert(chamber_zc + chamber_az + wall - z_tip <= 199, str(
    "TURNAROUND BED FIT: the print-pose height ",
    chamber_zc + chamber_az + wall - z_tip,
    " mm exceeds the 199 mm the gate's bare-default test-slice can cut",
    " (PrusaSlicer's default build volume caps Z at 200 mm — measured,",
    " not documented). Lower chamber_zc or chamber_az."));
assert(max(2 * (chamber_ay + wall), port_gap + 2 * r_out) <= 256, str(
    "TURNAROUND BED FIT: the print-pose width ",
    max(2 * (chamber_ay + wall), port_gap + 2 * r_out),
    " mm exceeds the 256 mm bed class this family targets."));
assert(2 * (chamber_ax + wall) <= 256, str(
    "TURNAROUND BED FIT: the chamber's x width exceeds the printcheck bed."));

// BELLY POLE FLUSH: the outer ellipsoid's bottom pole may not dip below the
// port face plane — below it the dome hangs over air between the ports (the
// web bridge starts AT the plane), and printcheck measured ~800 mm2 of
// unbridgeable overhang from a 2.4 mm dip. At or above the plane the same
// surface prints layer-over-solid (bridge, then neck shell).
assert(chamber_zc - (chamber_az + wall) >= -eps, str(
    "TURNAROUND BELLY: the chamber's bottom pole dips ",
    chamber_az + wall - chamber_zc,
    " mm below the port face plane — unbridgeable overhang under the web.",
    " Raise chamber_zc to at least chamber_az + wall."));

// CROWN CAP FEASIBILITY: the cap must (a) start above the route's highest
// envelope point + margin, and (b) close inside the shell — the gable's
// ridge stays 0.5 mm under the inner ellipsoid's own crown, which is by
// construction a wall inside the outer one. The gable's pitch is
// atan(vault_h / crown_xt) with vault_h = crown_xt + 1.5 — just PAST 45
// deg, so the roof planes clear the supportless limit rather than sitting
// exactly on it. These two are the y = 0 statement, and #499's hole is why
// that stopped being enough on its own: the sampled guards below are what
// actually hold the roof closed.
crown_st = sqrt(1 - pow((crown_zt - chamber_zc) / chamber_az, 2));
crown_xt = chamber_ax * crown_st;      // gable eaves / ridge half-span basis
vault_h = crown_xt + 1.5;
vault_k = vault_h / crown_xt;          // gable slope as tan; atan() ~ 46.05 deg
vault_deg = atan(vault_k);
crown_ridge = crown_zt + vault_h;      // the gable's ridge line, at x = 0
// THE HIP (#499's repair): two planes descending in |y| at crown_hip_deg
// (just past 45 deg, the gable's own "just past" rule), positioned to pass
// 1.5 mm UNDER the inner ellipsoid where that surface crosses the ridge
// height (y = crown_y_cross). The ellipsoid's shallow polar band in y is
// then covered by a plane everywhere it would otherwise govern — exactly
// what the gable does for its shallow band in x.
crown_hip_deg = 46;
crown_hip_k = tan(crown_hip_deg);
crown_y_cross = chamber_ay * sqrt(1 - pow((crown_ridge - chamber_zc) / chamber_az, 2));
crown_z_hip = crown_ridge - 1.5 + crown_hip_k * crown_y_cross;
assert(crown_zt >= chamber_zc + 35, str(
    "TURNAROUND CROWN: the cap starts at z = ", crown_zt,
    " mm, low enough to cut into the route's crossing envelope (which tops",
    " out at ", chamber_zc + 32.4, " mm). Raise crown_zt."));
assert(crown_ridge <= chamber_zc + chamber_az - 0.5, str(
    "TURNAROUND CROWN: the gable's ridge (z = ", crown_ridge,
    " mm) pokes through the chamber crown — lower crown_zt or chamber_az."));

// THE CAP'S SAMPLED GUARDS (#499 — the check that would have fired here).
// The cavity's crown boundary pointwise, the shell over it, and the
// ellipsoid's own slope where it governs:
function roof_z_in(x, y) =
    chamber_zc + chamber_az * sqrt(1 - pow(x / chamber_ax, 2)
                                      - pow(y / chamber_ay, 2));
function roof_z_out(x, y) =
    chamber_zc + (chamber_az + wall)
        * sqrt(1 - pow(x / (chamber_ax + wall), 2)
                 - pow(y / (chamber_ay + wall), 2));
function roof_z_cap(x, y) =
    min(roof_z_in(x, y), crown_ridge - vault_k * abs(x),
        crown_z_hip - crown_hip_k * abs(y));
// (1) No poke, anywhere: shell over the ceiling at every sampled station of
//     the roof — the old slot measures 0 here; the minimum sits at the
//     ridge/hip handover. Stations on the footprint rim or at/below the
//     equator are side wall, not roof, and are skipped.
function roof_min_wall(n) =
    min([for (i = [0 : n], j = [0 : n])
            let (x = -chamber_ax + 2 * chamber_ax * i / n,
                 y = -chamber_ay + 2 * chamber_ay * j / n)
                (pow(x / chamber_ax, 2) + pow(y / chamber_ay, 2) >= 0.999
                     || roof_z_cap(x, y) <= chamber_zc)
                    ? 1000
                    : roof_z_out(x, y) - roof_z_cap(x, y)]);
roof_wall_min = roof_min_wall(120);
assert(roof_wall_min >= 2.3, str(
    "TURNAROUND CAP: the cavity's roof comes within ", roof_wall_min,
    " mm of the outer surface somewhere off the y = 0 plane — the #499",
    " roof-slot failure mode. Lower crown_ridge or crown_z_hip."));
// (2) Every governing surface >= 45 deg: wherever the ellipsoid's own
//     surface IS the roof (above the equator, under both plane pairs), its
//     slope must already exceed 45 deg — the gable and the hip exist to
//     cover its shallow polar bands, in x and in y respectively.
function roof_z_slope(x, y) =
    chamber_az * sqrt(pow(x / pow(chamber_ax, 2), 2)
                    + pow(y / pow(chamber_ay, 2), 2))
        / sqrt(1 - pow(x / chamber_ax, 2) - pow(y / chamber_ay, 2));
function roof_min_gov_slope(n) =
    min([for (i = [0 : n], j = [0 : n])
            let (x = -chamber_ax + 2 * chamber_ax * i / n,
                 y = -chamber_ay + 2 * chamber_ay * j / n)
                (pow(x / chamber_ax, 2) + pow(y / chamber_ay, 2) >= 0.999
                     || roof_z_in(x, y) >= min(crown_ridge - vault_k * abs(x),
                                               crown_z_hip - crown_hip_k * abs(y))
                     || roof_z_in(x, y) <= chamber_zc + 1)
                    ? 1000
                    : roof_z_slope(x, y)]);
roof_gov_slope_min = roof_min_gov_slope(120);
assert(roof_gov_slope_min >= 1.0, str(
    "TURNAROUND CAP: the ellipsoid governs the roof at ",
    atan(roof_gov_slope_min), " deg somewhere — a near-horizontal enclosed",
    " ceiling (issue #34). Lower crown_z_hip so the hip covers the band."));
// (3) The hip actually caps: its planes must sit under the ellipsoid at the
//     ridge crossing with real margin, or the shallow sliver returns.
assert(crown_z_hip - crown_hip_k * crown_y_cross
       <= roof_z_in(0, crown_y_cross) - 1.0, str(
    "TURNAROUND CAP: the hip planes pass only ",
    roof_z_in(0, crown_y_cross) - (crown_z_hip - crown_hip_k * crown_y_cross),
    " mm under the ellipsoid at the ridge crossing — raise crown_hip_deg or",
    " lower crown_z_hip."));
// (4) The break itself (charter N2, re-homed here by #499): clear internal
//     width is the widest straight line through the BUILT cavity, not
//     2*chamber_ay. Along x = 0 (the widest station) the half-span at height
//     z is the min of the ellipsoid's slice and the hip's allowance — the
//     gable never binds at x = 0 — and the max over z sits a fraction of a
//     mm UNDER the equator, where the ellipsoid is again the binding surface.
//     The old 2*chamber_ay form read green either way: a 65 deg hip narrows
//     the bowl past body_len_mm with that assert silent, the same
//     guard-samples-where-the-geometry-isn't hole the roof slot came through.
function cavity_half_span(z) =
    min(chamber_ay * sqrt(1 - pow((z - chamber_zc) / chamber_az, 2)),
        (crown_z_hip - z) / crown_hip_k);
clear_w = 2 * max([for (i = [0 : 720])
                       cavity_half_span(chamber_zc - chamber_az
                                            + 2 * chamber_az * i / 720)]);
assert(clear_w >= body_len_mm, str(
    "TURNAROUND CLEAR WIDTH: the cavity's widest line is ", clear_w,
    " mm against body_len_mm = ", body_len_mm,
    ". Under it this module is NOT a break — a run through it still counts",
    " its full enclosed length against N2. Widen chamber_ay or lower",
    " crown_hip_deg: the hip is trimming the bowl."));
echo(str("nuggs-turnaround: crown cap = min(ellipsoid, ", vault_deg,
         " deg gable, ", crown_hip_deg, " deg hip); sampled min roof shell ",
         roof_wall_min, " mm, ellipsoid governs at >= ",
         atan(roof_gov_slope_min), " deg; cavity widest line ", clear_w, " mm"));

// VENTS: enough open area to matter, small enough to stay a teardrop, and —
// the welfare line — every vent strictly on the CEILING half of the chamber's
// cross-section at its station (its inboard edge above the equator plane in
// use). "Out of reach" is not literally available in any NUGGS-scale chamber
// (the ceiling itself is within a standing animal's reach); the den's
// recorded standard is that an INVERTED teardrop hole gives a gnawing incisor
// no purchase, and these asserts hold every vent to that inverted ceiling.
assert(n_vent >= 4, str(
    "TURNAROUND VENTS: n_vent = ", n_vent, " is under the ventilation floor",
    " (4). A sealed wide chamber is a dead volume — N3 as much as N2."));
assert(vent_d >= 6 && vent_d <= 14, str(
    "TURNAROUND VENTS: vent_d = ", vent_d, " mm must be in [6, 14]: under 6",
    " the open area stops mattering, over 14 the teardrop roof stops fitting",
    " the wall curvature cleanly."));
vent_smin = sqrt(1 - pow(0.6, 2));   // shape factor at the outermost station
assert((chamber_ax + wall) * vent_smin - vent_d / 2 > 0, str(
    "TURNAROUND VENT PLACEMENT: a vent's inboard edge crosses the equator",
    " plane onto the wall half — a side-wall hole is at gnawing height.",
    " Shrink the vent spread or vent_d."));

// ---------------------------------------------------------------------------
// Geometry
// ---------------------------------------------------------------------------

// One full-round neck: port at the face (sectors projecting to z_tip, tube up
// through z_top — the library's own cylinder + port union, the nuggs_neck
// body unrolled) plus the shell cylinder the chamber hull wants, face to
// z_join. The port is deliberately NOT bore-clean; the cavity below cuts it.
module neck(s) {
    translate([0, s * port_gap / 2, 0]) {
        nuggs_port(cfg);
        cylinder(r = ro, h = z_join, $fn = tube_fn);
    }
}

// The chamber as a scaled unit sphere — semi-axes given directly, so the
// outer body is the inner's semi-axes each grown by `wall` (a near-uniform
// gap at every pole; scaling both by one factor would thin the squashed x
// direction below the 1.2 mm wall floor).
module chamber(sx, sy, sz) {
    translate([0, 0, chamber_zc]) scale([sx, sy, sz]) sphere(1, $fn = ell_fn);
}

// One descending plane pair, as an oversized rotated-cube half-space: the
// solid below z <= z0 - tan(slope_deg) * |u|, where u is x (rotated about y)
// or y (rotated about x). Two cubes, one per plane, intersected.
module roof_wedge(z0, slope_deg, about_x) {
    intersection() {
        translate([0, 0, z0])
            rotate(about_x ? [slope_deg, 0, 0] : [0, slope_deg, 0])
                translate([-500, -500, -1000]) cube(1000);
        translate([0, 0, z0])
            rotate(about_x ? [-slope_deg, 0, 0] : [0, -slope_deg, 0])
                translate([-500, -500, -1000]) cube(1000);
    }
}

// The chamber's inner cavity, crown cap included (#499's repair): the crown
// boundary is the POINTWISE MINIMUM of the inner ellipsoid, the x-gable and
// the y-hip — one intersection(), never a union. The old cap unioned a
// gable-and-prism vault onto the truncated ellipsoid; its ridge ran along y
// at constant height past where the outer dome falls off in y, and the
// cavity poked through the roof for |y| > 27.6 mm. An intersection cannot
// outrun the ellipsoid anywhere — the ceiling is the lowest of the three
// surfaces — and the sampled asserts above hold shell over all of it.
module chamber_cavity() {
    intersection() {
        chamber(chamber_ax, chamber_ay, chamber_az);
        roof_wedge(crown_ridge, vault_deg, false);    // the x-gable
        roof_wedge(crown_z_hip, crown_hip_deg, true); // the y-hip
    }
}

// Internal edge break at a bore mouth: swallows any first-layer lip so no
// edge is ever presented to a claw or a loaded cheek pouch. Cut, never added;
// it only ever widens the bore. Wide end (r1) outermost, at the tips.
module bore_lead(s) {
    translate([0, s * port_gap / 2, z_tip])
        cylinder(r1 = ri + 1.0, r2 = ri - eps, h = chamfer_h, $fn = tube_fn);
}

// The vents: teardrop bores through the use-ceiling flank (print -x), spaced
// along the chamber's length at the ellipsoid's equator height, where the
// flank is widest and the wall runs thickest. teardrop_hole bores along y
// with its 45 deg peak at +z (the lib's documented orientation since #424);
// the z-spin below turns the axis to x and leaves the peak up — a horizontal
// hole in the print pose with its peak up, which is the whole point of the
// teardrop: it bridges supportlessly.
// Each bore is centred ON the outer surface and overshoots both ways, so the
// pierce through the curved wall is clean and stops inside the open cavity
// well short of the floor flank.
module vents() {
    for (i = [0 : n_vent - 1])
        let (t  = (i - (n_vent - 1) / 2) / max(1, (n_vent - 1) / 2),  // -1..1
             yv = t * 0.6 * chamber_ay,
             xc = -(chamber_ax + wall)
                  * sqrt(1 - pow(yv / (chamber_ay + wall), 2)))
            translate([xc, yv, chamber_zc])
                rotate([0, 0, -90])
                    teardrop_hole(d = vent_d, l = 2 * (chamber_ax + wall) + 8);
}

// The module itself: hull of the two neck shells and the outer ellipsoid (ONE
// envelope — the web between the necks fills solid), the two ports fused on,
// then ONE cavity union subtracted — the two ri bores (each open past its
// sector tips: the nuggs_bore_cut every port caller owes) plus the inner
// ellipsoid that swallows both bore caps, cone-capped at the far end — and
// the vents and mouth edge breaks cut through everything.
module nuggs_turnaround() {
    difference() {
        union() {
            hull() {
                for (s = [-1, 1])
                    translate([0, s * port_gap / 2, 0])
                        cylinder(r = ro, h = z_join, $fn = tube_fn);
                chamber(chamber_ax + wall, chamber_ay + wall, chamber_az + wall);
            }
            neck(-1);
            neck(1);
        }
        union() {
            for (s = [-1, 1])
                translate([0, s * port_gap / 2, z_tip - bore_over])
                    cylinder(r = ri, h = z_join - z_tip + bore_over,
                             $fn = tube_fn);
            chamber_cavity();
        }
        vents();
        bore_lead(-1);
        bore_lead(1);
    }
}

// Print-this-first fit coupon: one bore-clean port on a short stub. The fit
// is the library's, so the coupon is a library port stub — the same shape
// every NUGGS module tunes port_tol on. nuggs_neck() does the bore cut.
module turnaround_coupon() {
    nuggs_neck(cfg, z_top + 8);
}

// ---------------------------------------------------------------------------
// Fitchecks (ci.fitchecks) — the swept-animal proof.
//
// FRAME: print pose is the model frame; in USE the module lies ports-
// horizontal — print z (the port axes) becomes the use travel axis, print +x
// becomes use-DOWN (the dish is the ellipsoid's +x flank), print y stays the
// turn axis. So the animal's route is: along bore A (print z at y =
// +port_gap/2), across the dish at the equator height (print z = chamber_zc,
// riding the dish floor), and out bore B.
//
// The envelope: a 60 mm-wide round body (route_env_r = 30) — the pouched-face
// criterion the N1 floor serves, comfortably over the ~45 mm shoulder — swept
// along that route. Its intersection with the module must be EMPTY: the route
// clears floor, walls and ceiling for the whole transit.
//
// The route, as sphere CENTRES, derived not typed:
//   - Bore legs: riding the bore's floor side, ri - 31 in x — the sphere
//     stands 1 mm off the bore WALL (30 + 9 = 39 against ri = 40), from the
//     face plane up to the equator.
//   - The crossing: 31 mm off the dish floor ALONG THE FLOOR NORMAL. Offset
//     along plain -x would leave the sphere TANGENT to the tilted floor: the
//     dish grades 14.6 deg at the mouth line, and 31*cos(14.6 deg) = 30.0 —
//     zero air, degenerate facets, a fitcheck that renders a zero-volume
//     kiss. The normal offset holds a true 1 mm of air at every station.
//   - Stations are dense enough that consecutive capsules stay on the
//     floor-normal path between them.
// Verified numerically BEFORE rendering (NOTES.md): the r=30 ball clears the
// walls along all 658 sample stations of this polyline, worst air 1.00 mm
// (the bore walls), and the +6 mm control below interferes at every station.
// The sweep is a UNION OF CONSECUTIVE 2-sphere HULLS — one hull over every
// sphere would take the convex hull of the whole route, which is a different,
// much fatter solid (the U-shaped route is anything but convex; its hull
// reaches 61 mm past centre at the bowl, 14 mm through the floor).
route_env_r   = 30;   // envelope radius: the 60 mm pouched-face criterion
route_standoff = 31;  // centre height above the local surface: env + 1 mm air

function cross_centre(y) =
    let (xf = chamber_ax * sqrt(1 - pow(y / chamber_ay, 2)),
         g  = dish_grade_at(y))
        // plain y - standoff*sin(g) is correct on both halves: sin(g) carries
        // y's sign, so the offset always pulls the centre toward the bowl
        [xf - route_standoff * cos(g), y - route_standoff * sin(g),
         chamber_zc];

route_centres = concat(
    // bore A: face plane to equator, riding the bore's floor side
    [for (z = [0 : 5 : chamber_zc]) [ri - route_standoff, port_gap / 2, z]],
    // the crossing: mouth A's line to the bowl bottom, floor-normal offsets
    [for (y = [port_gap / 2, 44, 38, 32, 24, 14, 0]) cross_centre(y)],
    // ...and on to mouth B's line
    [for (y = [-14, -24, -32, -38, -44, -port_gap / 2]) cross_centre(y)],
    // bore B: equator back down to the face plane
    [for (z = [chamber_zc : -5 : 0]) [ri - route_standoff, -port_gap / 2, z]]);

module animal_path_sweep() {
    union() {
        for (i = [0 : len(route_centres) - 2])
            hull() {
                translate(route_centres[i]) sphere(r = route_env_r, $fn = 24);
                translate(route_centres[i + 1]) sphere(r = route_env_r, $fn = 24);
            }
    }
}

module fit_path_clear() {
    intersection() { nuggs_turnaround(); animal_path_sweep(); }
}

// The mandatory negative control: the same sweep pushed 6 mm into the floor
// flank. It MUST interfere — at the mouths the sphere rides 6 mm past the
// bore wall, at the bowl 6 mm past the dish — proving the empty check above
// can fail.
module fit_path_ctrl() {
    intersection() {
        nuggs_turnaround();
        translate([6, 0, 0]) animal_path_sweep();
    }
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------

if (part == "turnaround") nuggs_turnaround();
else if (part == "coupon") turnaround_coupon();
else if (part == "cutaway")
    // Section on the plane through both port axes: shows both bores, the web
    // between them, and the dish handing off to each mouth.
    difference() {
        nuggs_turnaround();
        translate([0, -300, -200]) cube([300, 600, 600]);
    }
else if (part == "cutaway-cross")
    // Section across the turn axis at mid-span (y = 0): shows the crown cap's
    // own profile — the two >=45 deg vault planes meeting at the ridge — and
    // the dish floor the route crosses. The y = 0 plane misses both bores
    // (they sit at y = +-port_gap/2); `cutaway` is the shot that shows those.
    difference() {
        nuggs_turnaround();
        translate([-300, 0, -200]) cube([600, 300, 600]);
    }
else if (part == "cutaway-ridge")
    // Section on the ridge plane (x = 0) — the plane the roof slot lived on
    // (#499). The ceiling reads as the flat ridge band, then hands over to
    // the two >= 45 deg hip planes that close ahead of the outer dome's
    // y-falloff. The y = 0 sections cannot show this: the slot started
    // 27.6 mm off that plane, which is exactly how it survived review.
    difference() {
        nuggs_turnaround();
        translate([0, -300, -200]) cube([300, 600, 600]);
    }
else if (part == "path-clear") fit_path_clear();
else if (part == "path-clear-ctrl") fit_path_ctrl();
else assert(false, str("nuggs-turnaround: unknown part '", part, "'"));
