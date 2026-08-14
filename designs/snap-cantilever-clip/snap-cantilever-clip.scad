// snap-cantilever-clip — a screw-down cable clip whose retaining lips are
// cantilever flexures. Reference design for docs/advanced-techniques.md
// Domain 1 (compliant mechanisms), the simplest case: a cantilever beam used
// as a snap. Also CC1 (orientation) — the flat print IS the flexure rule.
//
// The one lesson: PRINT IT FLAT. The silhouette lives in the XY (bed) plane and
// is extruded UP in Z to `width`. So the flexing lips bend *in the layer plane*
// — bending stress runs across the roads inside a layer, never across the bond
// between layers. Print the same clip upright and the lip delaminates on the
// first cable you push in (docs Domain 1, "the #1 rule").
//
// A C-ring holds the cable; its mouth (throat) is a touch narrower than the
// cable, so seating the cable spreads the two lips a known amount (a cantilever
// deflection you can compute) and they spring back to retain it. Roots are
// filleted at r >= 0.5·t so the stress concentration doesn't crack them.
// All dimensions in millimeters.

use <printability.scad>

/* [Cable] */
// Nominal cable / rod diameter to retain (mm)
cable_d = 6;
// Throat is this much narrower than the cable — the snap interference the lips
// must flex over (mm). Bigger = grips harder, flexes more.
grip = 1.0;

/* [Flexure & body] */
// Ring / lip wall thickness = the flexure beam thickness (mm). Thinner flexes
// easier and lowers root stress for a given spread, but grips softer.
wall = 2.4;
// Extrude height = clip width along the cable (mm)
width = 10;
// Root fillet at the lip/body junction (mm) — the doc's r >= 0.5·t stress rule
root_fillet = 1.4;

/* [Mount foot] */
// Foot length behind the ring (mm)
foot_l = 15;
// Mounting screw size (hole runs along the build axis Z — support-free)
screw = "M3"; // [M3, M4]

/* [Quality] */
// Iterating: 48. Production: 96.
$fn = 64;

// ---- derived -----------------------------------------------------------
pocket_r = cable_d / 2;
R_out    = pocket_r + wall;      // ring outer radius
throat   = cable_d - grip;       // mouth width (< cable_d ⇒ snap)
cx       = foot_l + pocket_r;    // ring centre X (ring overlaps the foot)
cy       = R_out;                // ring centre Y (bottom of ring near y=0)
scr_d    = screw_clearance_d(screw);

module clip2d() {
    // fillet the concave roots: erode-then-dilate rounds inside corners
    offset(r = -root_fillet) offset(r = root_fillet)
    difference() {
        union() {
            // mounting foot — full ring height so the ring sits centred on it
            translate([0, 0]) square([cx, 2 * R_out]);
            // ring outer
            translate([cx, cy]) circle(r = R_out);
        }
        // cable pocket
        translate([cx, cy]) circle(r = pocket_r);
        // throat: slot opening toward +X, centred on the ring centre height
        translate([cx, cy - throat/2]) square([R_out + wall + 1, throat]);
        // screw hole through the foot (axis Z, support-free)
        translate([foot_l/2, cy]) circle(d = scr_d);
    }
}

module main() {
    assert(root_fillet >= 0.5 * wall,
           "root fillet below 0.5·t — the flexure root is a crack starter");
    assert(throat > 0, "grip exceeds cable_d — the mouth would close");
    linear_extrude(width) clip2d();
}

main();
