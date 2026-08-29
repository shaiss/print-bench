// snap-cantilever-clip — a one-piece clip that snaps onto a plate edge
// (3 mm card / shelf stock) and holds by cantilever deflection: the
// canonical snap-fit. Reference design for docs/advanced-techniques.md
// Domain 1 (compliant mechanisms) — the small-length flexural pivot (SLFP)
// used as a snap, dimensioned from the doc's relations instead of guessed:
//
//   K = E*I / L          flexural stiffness (N*mm/rad)
//   I = w*t^3 / 12       second moment of area (mm^4)
//   sigma ~= E*t*theta / (2L)   root stress, pure-moment ideal;
//                              a tip load (this snap) doubles it
//
// and CC1 (orientation): the silhouette lives in the XY (bed) plane and is
// extruded up in Z to `w`, so the finger bends IN the layer plane — bending
// stress runs across the roads inside a layer, never across the bond between
// layers. Print the same clip upright and the finger delaminates on the first
// insertion (doc Domain 1, the #1 rule).
//
// Mechanism: a channel one jaw of which is a cantilever finger carrying a
// lip (lead-in ramp ahead, steep retention shoulder behind). Pushing the
// clip onto the plate cams the lip over the plate faces — the finger
// deflects `delta` mm and swings `theta` — then springs back behind the
// plate end, preloaded, so the clip grips by spring force and the shoulder
// catches the plate edge on pull-out. A guard rail stands at the finger's
// overtravel limit (the doc's hard-stop rule). Requirements, derivation and
// the tune order: NOTES.md. All dimensions in millimeters.

/* [Plate] */
// Plate thickness to grip (mm)
plate_t = 3.0;
// How deep the plate seats into the channel (mm)
plate_depth = 20;
// Sliding clearance across the plate faces (mm)
plate_tol = 0.2;

/* [Flexure - the SLFP] */
// Beam thickness t (mm) — the highest-leverage knob: stiffness scales with
// t^3, root stress with t/L. Tune FIRST. Keep >= 0.8 (2 extrusion widths).
t = 1.0;
// Root-to-lip beam length L (mm) — thinner + longer lowers stress for the
// same rotation (doc, SLFP)
L = 12;
// Clip width = beam width w = print height (mm). Insertion force scales
// linearly with w; stress does not depend on it.
w = 15;
// Lip protrusion into the channel (mm) — the snap interference
grip_p = 1.4;
// Flexure root fillet (mm) — doc fatigue rule r >= 0.5*t. Tune SECOND.
root_fillet = 0.6;
// Lead-in ramp angle from the plate face (deg) — the insertion cam
ramp_deg = 30;
// Retention shoulder angle from the plate face (deg) — the removal cam.
// 90 = non-releasing; 45 ~= removable at roughly twice the insertion force.
shoulder_deg = 45;

/* [Body] */
// Stiff wall thickness (mm) — the plate's fixed jaw
wall = 3.0;
// Crown strap thickness (mm) — joins guard, finger and wall into one body
strap = 4.0;
// Guard rail thickness (mm) — the finger's motion-limiting hard stop
guard = 1.2;
// Travel past the snap deflection before the finger meets the guard (mm)
guard_overtravel = 0.3;
// Mouth funnel chamfer on the stiff wall (mm) — lets a tilted plate
// self-align on entry
lead = 1.2;

/* [Material datum] */
// PETG Young's modulus (MPa) — design datum for the echoes below; a
// calibration starting point, not a guarantee (NOTES.md, Fatigue)
E = 2000;

/* [Quality] */
// Production: 96. Only the root-fillet arc is curved, and it is the
// fatigue-critical surface, so it gets the smooth setting.
$fn = 96;

// ---- derived -----------------------------------------------------------
gap    = plate_t + plate_tol;       // channel gap across the plate
throat = gap - grip_p;              // mouth opening at the lip
delta  = grip_p - plate_tol;        // finger deflection: insertion peak
                                    // equals seated preload (same cam travel)
y_tip  = plate_depth - L;           // lip apex sits L below the strap face
rail_in = -(t + delta + guard_overtravel);   // guard face the finger stops on
I      = w * t * t * t / 12;        // second moment of area (mm^4)
K      = E * I / L;                 // SLFP stiffness (N*mm/rad)
F_snap = 3 * E * I * delta / pow(L, 3);      // tip force at delta (N)
theta  = 1.5 * delta / L;           // tip rotation (rad), tip-load shape
sigma_tip = E * t * theta / L;      // root stress, tip load = 2x doc ideal
sigma_doc = sigma_tip / 2;          // doc's pure-moment E*t*theta/(2L)

echo(str("SLFP: K = ", K, " N*mm/rad  (I = ", I, " mm^4, E = ", E, " MPa)"));
echo(str("snap: delta = ", delta, " mm, theta = ", theta * 180 / PI,
         " deg, tip force = ", F_snap, " N"));
echo(str("root stress: ", sigma_tip, " MPa tip-load bound; ",
         sigma_doc, " MPa doc pure-moment ideal"));

module checks() {
    assert(t >= 0.8, "t below 0.8 mm (2 extrusion widths) - the flexure will not print");
    assert(root_fillet >= 0.5 * t,
           "root fillet below 0.5*t - the flexure root is a crack starter");
    assert(throat >= 0.8, "throat below 0.8 mm - the plate cannot enter");
    assert(delta > 0, "grip_p must exceed plate_tol or there is no snap");
    assert(ramp_deg >= 15 && ramp_deg <= 40, "lead-in ramp outside 15-40 deg");
    assert(shoulder_deg >= 30 && shoulder_deg <= 90,
           "retention shoulder outside 30-90 deg");
    assert(guard_overtravel > 0,
           "the guard must sit past the snap deflection, not inside it");
    assert(guard > 0.8, "guard rail below 0.8 mm will not print");
}

// The bed-plane silhouette. Plate slides in +Y from the mouth at y=0 and
// seats against the strap face at y=plate_depth; the channel spans
// x in [0, gap], the finger hangs at x in [-t, 0] with its lip tooth
// reaching to x=grip_p, the stiff wall closes the far side.
module clip2d() {
    f = root_fillet;
    ramp_rise     = grip_p / tan(ramp_deg);       // vertical rise of the lead-in
    shoulder_rise = grip_p / tan(shoulder_deg);   // vertical rise of the shoulder
    apex = 0.4;                   // half-flat of the blunt lip apex (no knife edge)
    y_bot = y_tip - apex - ramp_rise;             // finger's flat bottom face
    top   = plate_depth + strap;

    union() {
        // crown strap — the stiff ground guard, finger and wall hang from
        translate([rail_in - guard, plate_depth])
            square([gap + wall - rail_in + guard, strap]);
        // stiff wall — the plate's fixed jaw, full channel length, with a
        // 45 deg funnel chamfer at the mouth corner
        polygon([[gap + lead, 0], [gap + wall, 0], [gap + wall, top],
                 [gap, top], [gap, lead]]);
        // guard rail — the hard stop the finger meets at delta + overtravel
        translate([rail_in - guard, y_tip - 1]) square([guard, top - y_tip + 1]);
        // cantilever finger
        translate([-t, y_bot]) square([t, top - y_bot]);
        // lip tooth: shallow ramp ahead, blunt apex, steep shoulder behind
        polygon([[0, y_bot],
                 [grip_p, y_tip - apex], [grip_p, y_tip + apex],
                 [0, y_tip + apex + shoulder_rise]]);
        // flexure-root fillet — the corner piece of the square [0,f] x
        // [plate_depth-f, plate_depth] OUTSIDE the disc: material added into
        // the channel at the concave root corner (finger face x=0 meets
        // strap face y=plate_depth), bounded by the arc. The disc itself
        // (intersection) would touch both walls at single tangent points
        // and never weld into the union — 12 naked edges.
        difference() {
            translate([0, plate_depth - f]) square([f, f]);
            translate([f, plate_depth - f]) circle(f);
        }
    }
}

module main() {
    checks();
    linear_extrude(height = w) clip2d();
}

main();
