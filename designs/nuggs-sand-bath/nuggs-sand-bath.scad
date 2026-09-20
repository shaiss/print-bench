// N.U.G.G.S. Sand Bath — the grooming module the ecosystem was missing.
// Requirements, assumptions and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// This is NOT a tube. It is a single-port OPEN MODULE: an open-topped bathing
// trough a NUGGS run dead-ends into. The animal walks the 80 mm bore, crosses
// the containment lip down a <=45deg beach, and stands on a flat sand floor
// wider than the bore; the mouth above it is open, so sand goes in from the
// top and the animal can be lifted out. It carries the one shared interlock —
// the genderless quarter-turn port in lib/nuggs-coupling.scad — so it mates
// any NUGGS face either way round, and it is a CONSUMER of that standard
// exactly like designs/nuggs: one cfg built with nuggs_cfg(), handed around,
// no coupling derivation restated.
//
// POSE. Modelled in the PRINT pose: port axis vertical, standing on the sector
// tips, the dish growing up out of the tube. In that frame every wall of the
// dish is VERTICAL — the floor and the mouth both face sideways — so nothing
// outside the coupling's own known tier needs support. In USE the module lies
// on its flat floor strip, port horizontal in the run wall, mouth up. The
// brief's "port-axis vertical standing on the sector tips, dish mouth up" is
// both poses in one sentence; NOTES.md ("Reading the print-pose line") records
// why they are read as print pose + use pose rather than one pose.
//
// HEIGHT. The CI test-slice runs PrusaSlicer's factory-default profile, which
// tops out at exactly 200 mm of build height (measured with calibration boxes:
// a 200 mm box slices, a 201 mm box fails "exceeds the maximum build volume
// height"; scripts/gate.sh slice_one() passes process flags only, so nothing
// in this repo raises it). 199 mm is therefore the hard ceiling here, and the
// STAGED widening below exists to buy capacity under it: one hull from tube
// straight to the dish section needs a corner-driven ~39 mm flare run, while
// a circle needs only lip_h. NOTES.md, "The height ceiling", records the
// depth-for-flat-run trade; the escape hatch on a taller printer is
// -D floor_run=<more>, never dish_w.
use <nuggs-coupling.scad>

/* [What to render] */
// body = the printable part; coupon = fit stubs; cutaway = section preview;
// mated / mated_neg = fitcheck interference solids; hero = use-pose preview;
// sandbody = the sand fill as a solid (measurement aid for the G4 audit)
part = "body";  // [body, coupon, cutaway, mated, mated_neg, hero, sandbody]

/* [The NUGGS standard - change these and nothing you already printed fits] */
// Revision of the PORT STANDARD in lib/nuggs-coupling.scad this module builds
// to. Names the standard, not this design. Bump only on a breaking port change.
NUGGS_PORT_REV = 1;
// Internal bore (mm) — the headline number. Asserted >= min_bore_mm by the lib
// (the 70 mm Deutscher Tierschutzbund entrance floor for a pouched Syrian).
bore_d = 80.0;
// Tube shell thickness (mm)
wall = 2.4;
// Radial depth of the coupling ring beyond the tube OD (mm)
lug_r = 6.0;
// Axial projection of the coupling sectors past the tube face (mm)
port_proj = 10.0;
// Coupling sectors per face (3 = kinematically determinate)
n_lug = 3;
// Angular width of each sector (deg). Asserted lug_deg + twist_deg <= pitch/2.
lug_deg = 40;
// Radial depth of the locking rib (mm)
rib_h = 1.0;
// Axial width of the locking rib / groove (mm)
rib_w = 2.4;
// Angular width of the locking rib (deg)
rib_deg = 12;
// The locking twist (deg). Asserted rib_deg + twist_deg <= lug_deg.
twist_deg = 14;
// Backing-collar thickness (mm)
collar_t = 3.0;
// Overlap fusing the ribs into the outer sectors (mm). Never zero.
bite = 0.8;

/* [Fit & tolerances] */
// The one knob. Uniform clearance on every coupling surface (mm). Tune on the
// coupon in +/-0.05 steps. Asserted 0.10-0.60 by the lib.
port_tol = 0.30;

/* [Bath] */
// Containment lip: port invert height above the dish floor (mm). Keeps sand in
// and gives the animal a ramp to climb back out. Brief target ~20.
lip_h = 20;
// Bathing sand depth on the flat floor (mm). Brief floor >= 15 (assumed; the
// welfare source behind it says 2-3 cm, which a 20 mm lip cannot contain).
// 18 closes the ~250 mL capacity row under the height ceiling while keeping
// lip_h - sand_depth >= 2 (asserted below).
sand_depth = 18;
// Dish wall height above the sand surface (mm). Brief floor >= 15.
freeboard = 15;
// Inside width of the dish, across the port axis (mm). Brief ~110, taken
// exactly: with sand_depth 18 and floor_run 96 the measured sand fill is
// ~246 mL of the ~250 mL target, inside the CI test-slice's 200 mm height
// ceiling (measured, NOTES.md "The height ceiling").
dish_w = 110;
// Flat floor run beyond the widening zone, before the far ramp (mm). Sets
// capacity with the rows above; print height = 101 + floor_run, asserted
// under the 199 mm ceiling. A taller printer buys capacity here, not in
// dish_w: -D floor_run=140 on a 250 mm-tall volume.
floor_run = 96;
// Dish shell thickness (mm). Separate knob from the tube `wall`; keep >= 1.2
// (3 perimeters at a 0.4 mm nozzle).
dish_wall = 2.4;
// Corner radius of the dish's rounded-rectangle section (mm). Floors that
// meet walls in a fillet print as one clean seam and sweep clean.
corner_r = 12;

/* [Quality] */
// This design's own preset. Iterating: $fa=6/$fs=1.5. Production: $fa=3/$fs=0.8.
// It does NOT reach the coupling: the library pins its own $fa/$fs inside every
// port module body, deliberately, so the fit cannot move with a quality change.
// These values MATCH the library pin on purpose — where this file's tube meets
// the port, mismatched presets split the shell into ~20 bodies under Manifold
// (issue #99, PR #200). Do not improve these.
$fa = 3;
$fs = 0.8;

/* [Hidden] */
eps = 0.01;

// ---------------------------------------------------------------------------
// The coupling configuration — ONE cfg, built once, handed to every port call.
// Every coupling guard fires inside nuggs_cfg(); none is restated here.
// ---------------------------------------------------------------------------
cfg = nuggs_cfg(bore_d    = bore_d,    wall      = wall,      lug_r    = lug_r,
                port_proj = port_proj, collar_t  = collar_t,  n_lug    = n_lug,
                lug_deg   = lug_deg,   rib_h     = rib_h,     rib_w    = rib_w,
                rib_deg   = rib_deg,   twist_deg = twist_deg, bite     = bite,
                port_tol  = port_tol,  eps       = eps);

// The contract values this design reaches for; the rest stay in the library.
ri    = nuggs_ri(cfg);       // bore radius (invert at y = -ri in use)
ro    = nuggs_ro(cfg);       // tube OD radius — the port fuses to this
r_out = nuggs_r_out(cfg);    // ring OD / envelope
z_tip = nuggs_z_tip(cfg);    // sector tips (bed contact), = -port_proj
z_top = nuggs_z_top(cfg);    // top of the port zone; nothing but tube above it

// ---------------------------------------------------------------------------
// Derived dish geometry. Verticals are named in the USE frame (+Y up, port
// axis horizontal), because that is the frame the brief's welfare numbers live
// in; the solid itself is modelled in the print frame, which shares XY, so a
// use-frame "height" is just this frame's y.
// ---------------------------------------------------------------------------
y_floor_in  = -(ri + lip_h);            // the sand sits here
y_floor_out = y_floor_in - dish_wall;
y_sand      = y_floor_in + sand_depth;  // the filled-sand surface
y_rim       = y_sand + freeboard;       // lowest point of the mouth's rim
x_half_in   = dish_w / 2;
x_half_out  = x_half_in + dish_wall;
y_top_out   = ro + 1.6;                 // generous; the rim cut trims it back

// ---------------------------------------------------------------------------
// Staged widening: tube -> stage 1 -> dish, two hulls instead of one. A hull
// between two sections slopes at atan(radial growth / run); a CIRCLE is the
// cheapest widening target there is — it reaches the dish's full depth with
// only lip_h of growth — while the rounded-rect corners sit farthest out and
// dominate a single-hull flare (~39 mm of run; the first revision's 59.6deg
// corners, NOTES.md "Overhang census"). Splitting the widening spends the
// cheap circle growth first and buys the height back for floor run. Above the
// widening zone every wall is a z-extrusion and prints vertical by
// construction (nz = 0 on any extrusion flank); only the two hulls and the
// two plane cuts carry the <=45deg rule.
// ---------------------------------------------------------------------------
r_stage1  = (y_top_out - y_floor_out) / 2;   // stage-1 circle radius
cy_stage1 = y_floor_out + r_stage1;          // ...centred so it spans the section
flare_run = lip_h + 2;                       // growth out of the tube is lip_h;
z_flare   = z_top + flare_run;               // +2 keeps every flank under 45deg

// The stage-1 circle's radius along a ray at angle theta from +X. Its centre
// is off-axis, so as seen from the origin the radius is not r_stage1.
function stage1_radius(theta) =
    let (cs = cy_stage1 * sin(theta))
    cs + sqrt(cs * cs + r_stage1 * r_stage1 - cy_stage1 * cy_stage1);

// Widening run: covers the growth from the stage-1 circle out to the dish
// CORNERS — the farthest boundary travel of the second hull — plus margin.
theta_corner = atan2(y_floor_out + corner_r, x_half_out - corner_r);
widen_run = norm([x_half_out - corner_r, y_floor_out + corner_r]) + corner_r
            - stage1_radius(theta_corner) + 2;
z_wide = z_flare + widen_run;

// Far wall as a raked ramp — the beach's mirror. The dish cannot end in a
// wall perpendicular to the run: in the print pose that wall is a flat
// ceiling spanning the trough (measured: a 110 x 31 mm bridge, NOTES.md).
// The ramp rises from the floor to the low rim over ramp_run at <=45deg,
// and like the beach it ADDS a sand wedge instead of costing floor.
ramp_rise = y_rim - y_floor_in;               // floor -> rim
ramp_run  = ramp_rise + 1;                    // 1 mm of margin under 45deg
z_far_out = z_wide + floor_run + ramp_run;    // top of the print

// The raked rim: a single plane from the tube crown (z_top, +ro) down to the
// low rim (z_far_out, y_rim). Everything above it is the open mouth.
rake_dz = z_far_out - z_top;
rake_dy = ro - y_rim;
rake_ang = atan2(rake_dy, rake_dz);     // from vertical; asserted <= 45 below

// Sand capacity, from the REAL cross-section shapes (a first draft used
// rectangle/diameter heuristics and ran ~10% hot vs the mesh — measured
// 221 mL where it claimed 242; the wedges are circular segments, not
// rectangles). Cross-section of the sand at the fill line:
//   a_circle — in the widening zone's stage-1 circle, the segment below fill
//   a_band   — in the trough proper, width x depth minus the four corner arcs
// The hulls' interpolated cross-sections average their end sections (the
// mesh runs ~1% convex above this — the honest direction).
// (OpenSCAD trig is degree-based: acos returns degrees, hence the PI/180.)
function circ_seg_below(r, cy, yf) =
    let (d = cy - yf)
        d >= r ? 0
      : d <= -r ? PI * r * r
      : r * r * acos(d / r) * PI / 180 - d * sqrt(r * r - d * d);

rc         = corner_r - dish_wall;   // inner corner radius after the offset
a_circle   = circ_seg_below(r_stage1 - dish_wall, cy_stage1, y_sand);
a_band     = dish_w * sand_depth
             - 4 * (1 - PI / 4) * rc * rc * min(1, sand_depth / rc);
cap_est_ml = (a_band * floor_run                       // the flat run
            + a_circle / 2 * flare_run                 // beach wedge
            + (a_circle + a_band) / 2 * widen_run      // widening wedge
            + a_band / 2 * sand_depth * ramp_run / ramp_rise)  // ramp wedge
            / 1000;

echo(str("nuggs-sand-bath: port standard R", NUGGS_PORT_REV, " at bore ", bore_d,
         " mm, port_tol ", port_tol, " mm -> web ", nuggs_web(cfg),
         " mm, bearing area ", nuggs_bearing_area(cfg), " mm2"));
echo(str("nuggs-sand-bath: dish ", dish_w, " mm wide, ", floor_run,
         " mm flat run inside, sand depth ", sand_depth, " mm -> ~", cap_est_ml,
         " mL (target ~250)"));
echo(str("nuggs-sand-bath: lip ", lip_h, " mm, beach flank ",
         atan2(lip_h, flare_run), " deg, rim rake ", rake_ang,
         " deg, print height ", z_far_out - z_tip, " mm"));

// ---------------------------------------------------------------------------
// Welfare and printability asserts. The coupling's guards live in nuggs_cfg();
// these belong to THIS module's own geometry.
// ---------------------------------------------------------------------------

// Sand must stay in the bath: the fill line sits below the port invert by a
// real margin, or every quarter-turn of the run shakes sand into the tube.
assert(lip_h - sand_depth >= 2, str(
    "BATH SAND: sand_depth = ", sand_depth, " mm comes within 2 mm of the lip ",
    lip_h, " mm (port invert above floor). Sand would spill into the run."));
assert(freeboard >= 15, str(
    "BATH FREEBOARD: freeboard = ", freeboard, " mm is under the 15 mm the ",
    "brief requires above the sand line. A bathing hamster throws sand."));
assert(dish_w >= bore_d + 20, str(
    "BATH WIDTH: dish_w = ", dish_w, " mm leaves under 10 mm of clearance per ",
    "side beyond the ", bore_d, " mm bore. A bath wider than the door only in ",
    "name is not a bath."));
assert(dish_wall >= 1.2, str(
    "BATH WALL: dish_wall = ", dish_wall, " mm is under the 1.2 mm three-",
    "perimeter floor at a 0.4 mm nozzle."));
assert(corner_r > dish_wall && corner_r <= x_half_out - 5, str(
    "BATH CORNER: corner_r = ", corner_r, " mm does not leave a sane rounded-",
    "rectangle section. Keep it above dish_wall and well inside the half-width."));

// Self-supporting budget: every sloped face this design adds (beach, staged
// skirts, far ramp, raked rim) stays at or under 45deg from the print vertical.
assert(flare_run >= lip_h, str(
    "BATH BEACH: flare_run = ", flare_run, " mm against a ", lip_h, " mm drop ",
    "puts the beach and stage-1 skirt past 45deg. Lengthen flare_run."));
assert(widen_run >= norm([x_half_out - corner_r, y_floor_out + corner_r])
                     + corner_r - stage1_radius(theta_corner), str(
    "BATH WIDENING: widen_run = ", widen_run, " mm does not cover the ",
    norm([x_half_out - corner_r, y_floor_out + corner_r]) + corner_r
        - stage1_radius(theta_corner),
    " mm of radial growth out to the dish corners — the stage-2 skirt would ",
    "pass 45deg and need support."));
assert(ramp_run >= ramp_rise, str(
    "BATH FAR RAMP: ramp_run = ", ramp_run, " mm against a ", ramp_rise,
    " mm rise puts the far wall past 45deg from vertical — a flat ceiling in ",
    "the print pose. Lengthen ramp_run."));
assert(rake_dz >= rake_dy, str(
    "BATH RIM: the raked rim runs ", rake_dy, " mm down over ", rake_dz,
    " mm — past 45deg from vertical. Lengthen the dish or raise y_rim."));

// Bed. Printed upright on the sector tips; the tallest point is the far wall.
// 199, not ~241: the CI test-slice's PrusaSlicer default profile tops out at
// exactly 200 mm of build height (measured with calibration boxes, NOTES.md
// "The height ceiling"), and gate.sh passes no printer profile to raise it.
assert(z_far_out - z_tip <= 199, str(
    "BATH BED: print height ", z_far_out - z_tip, " mm exceeds the 199 mm the ",
    "CI test-slice's default PrusaSlicer profile allows (200 mm hard, ",
    "measured). Cut floor_run or dish_w."));

// Capacity, guarded loosely on the shape-corrected estimate (+/-5% of the
// brief's ~250 mL); the audited number is measured off the exported mesh
// (NOTES.md, "Capacity"), never read from here.
assert(cap_est_ml >= 238 && cap_est_ml <= 262, str(
    "BATH CAPACITY: estimated ", cap_est_ml, " mL against the ~250 mL brief ",
    "target. Adjust floor_run or sand_depth."));

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

// Outer section of the trough: a rounded rectangle, flat side down in use,
// sized outside the tube circle so the flare skirt has somewhere to arrive.
module out_2d() {
    w = 2 * (x_half_out - corner_r);
    h = (y_top_out - y_floor_out) - 2 * corner_r;
    translate([-w / 2, y_floor_out + corner_r])
        offset(r = corner_r) square([w, h]);
}

// Inner section: the outer one pulled in by the shell thickness. The offset
// keeps floor and walls one constant dish_wall apart, corners included.
module in_2d() {
    offset(delta = -dish_wall) out_2d();
}

// Stage-1 section: a circle spanning the dish's full depth, centred off-axis.
// The circle is the cheapest widening target there is — growth out of the
// tube is lip_h regardless of how wide the dish is — so the first hull stays
// shallow and the height budget goes to floor run instead.
module stage1_2d() {
    translate([0, cy_stage1]) circle(r = r_stage1);
}

// Its inner face, one dish_wall in — the void the beach arrives into.
module stage1_in_2d() {
    translate([0, cy_stage1]) circle(r = r_stage1 - dish_wall);
}

// ---------------------------------------------------------------------------
// Parts
// ---------------------------------------------------------------------------

// The bath: ONE union of material (port, full-round neck, staged skirts,
// trough walls), ONE cavity cut (bore, beach, staged void, trough void, open
// mouth). The beach starts exactly at z_top: below that the bore floor is the
// ri arc, continuous with the mate's bore to 0.000 mm across the joint plane —
// a flat trough floor pulled down to the face instead would stand the mate's
// tube proud by 9.36 mm at the walk-band edge (lib/nuggs-coupling-mates.conf,
// the open-module case). The flat floor belongs wholly beyond the port zone.
module nuggs_sand_bath() {
    difference() {
        union() {
            cylinder(r = ro, h = z_top + 1);   // full-round neck past the port zone
            nuggs_port(cfg);                   // sectors on -z (bed); collar to z_top
            hull() {                           // stage 1: tube -> spanning circle
                translate([0, 0, z_top])
                    linear_extrude(eps) circle(r = ro);
                translate([0, 0, z_flare])
                    linear_extrude(eps) stage1_2d();
            }
            hull() {                           // stage 2: circle -> dish section
                translate([0, 0, z_flare])
                    linear_extrude(eps) stage1_2d();
                translate([0, 0, z_wide])
                    linear_extrude(eps) out_2d();
            }
            translate([0, 0, z_wide - 1])      // trough walls: vertical from here
                linear_extrude(z_far_out - z_wide + 1) out_2d();
        }
        union() {
            nuggs_bore_cut(cfg, z_tip - 1, z_top + 1);
            hull() {                           // the beach: bore -> spanning void
                translate([0, 0, z_top])
                    linear_extrude(eps) circle(r = ri);
                translate([0, 0, z_flare])
                    linear_extrude(eps) stage1_in_2d();
            }
            hull() {                           // widening void: circle -> trough
                translate([0, 0, z_flare])
                    linear_extrude(eps) stage1_in_2d();
                translate([0, 0, z_wide])
                    linear_extrude(eps) in_2d();
            }
            translate([0, 0, z_wide - 1])      // trough void; no flat far cap —
                linear_extrude(z_far_out - z_wide + 2) in_2d();  // ramp ends it
            mouth_open();
            far_ramp_cut();
        }
    }
}

// The open mouth: everything above the raked rim plane, gone. The plane starts
// tangent at the tube crown (z_top, +ro) so the rim meets the neck with no
// step, and descends to the low rim at the far wall — that rake IS the vault
// over the entry: nowhere does a flat ceiling cross the bore (the self-
// supporting substitution, docs/advanced-techniques.md).
module mouth_open() {
    translate([0, ro, z_top - 0.01])    // 0.01 into the crown: a tangent cut
        rotate([rake_ang, 0, 0])        // leaves zero-area facets behind
            translate([-100, 0, 0])
                cube([200, 150, norm([0, rake_dy, rake_dz]) + 1]);
}

// The far end raked: everything beyond the ramp plane, gone. The plane runs
// from the floor at z_far_out - ramp_run up to the low rim point
// (y_rim, z_far_out), where it meets the mouth's rake — full freeboard at
// the far end, and the wall prints as a slope, never a bridge.
module far_ramp_cut() {
    translate([0, y_floor_in, z_far_out - ramp_run])
        rotate([atan2(ramp_run, ramp_rise), 0, 0])
            translate([-100, 0, 0])
                cube([200, 100, 260]);
}

// The sand fill as a solid: the bath's void primitives with the same far-ramp
// cut the cavity takes, clipped at the fill surface (y <= y_sand). NOT a
// printable part — a measurement aid, exported so the capacity audit measures
// the mesh (G4), never the parameter (issue #37's lesson). Volume in mm^3 /
// 1000 = mL of sand. (The ramp enters as a DIFFERENCE: the sand lies on the
// near side of the ramp plane; far_ramp_cut() itself is the beyond-the-ramp
// half-space — the far wall's material side.)
module sand_body() {
    difference() {
        intersection() {
            union() {
                nuggs_bore_cut(cfg, z_tip - 1, z_top + 1);
                hull() {
                    translate([0, 0, z_top])
                        linear_extrude(eps) circle(r = ri);
                    translate([0, 0, z_flare])
                        linear_extrude(eps) stage1_in_2d();
                }
                hull() {
                    translate([0, 0, z_flare])
                        linear_extrude(eps) stage1_in_2d();
                    translate([0, 0, z_wide])
                        linear_extrude(eps) in_2d();
                }
                translate([0, 0, z_wide - 1])
                    linear_extrude(z_far_out - z_wide + 2) in_2d();
            }
            translate([-200, -200, -200]) cube([400, 200 + y_sand, 700]);
        }
        far_ramp_cut();
    }
}

// Print-this-first fit coupon: two bore-clean port stubs, the family pattern.
// The fit is the library's, so the coupon is a library port stub — mate two
// of them (or one to any NUGGS module) and tune port_tol.
module sand_bath_coupon() {
    for (side = [-1, 1])
        translate([side * (r_out + 6), 0, 0])
            nuggs_neck(cfg, z_top + 8);
}

// The mate, per lib/nuggs-coupling-mates.conf: same neck, mirrored so its
// sectors face ours, rotated by a clocking from nuggs_clockings() — never a
// hardcoded angle — and pulled 0.01 in z so the zero-clearance seat reads as
// clearance, not as a zero-volume shell of coincident planes.
module mate_neck(clocking) {
    translate([0, 0, -0.01])
        rotate([0, 0, clocking])
            mirror([0, 0, 1])
                nuggs_neck(cfg, 30);
}

if (part == "body") nuggs_sand_bath();
else if (part == "coupon") sand_bath_coupon();
else if (part == "cutaway")
    difference() { nuggs_sand_bath(); translate([0, -150, -50]) cube(300); }
else if (part == "mated")
    intersection() { nuggs_sand_bath(); mate_neck(nuggs_clockings(cfg)[0]); }
else if (part == "mated_neg")
    intersection() { nuggs_sand_bath(); mate_neck(0); }
else if (part == "sandbody") sand_body();
else if (part == "hero") rotate([-90, 0, 0]) nuggs_sand_bath();
else assert(false, str("nuggs-sand-bath: unknown part '", part, "'"));
