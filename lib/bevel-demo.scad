// Smoke test / visual demo for bevel.scad.
// Not a printable design — rendered by scripts/check.sh to catch regressions.
// All dimensions in millimeters.
//
// Every module in the library is exercised below; every placement function
// is echoed for the 15:26 pair so a change to the cone geometry shows up in
// the log as well as in the mesh. Expected CGAL summary: Volumes: 11 — ten
// separate bodies (the two interference solids at the end contribute none,
// which is their point) plus the outer volume CGAL always counts.

use <bevel.scad>

$fn = 48;   // coarse for check.sh; the library pins its own fit-bearing tessellation

// The reference pair — the numbers lib/bevel-mates.conf measures.
n1  = 15;
n2  = 26;
mod = 1.5;

// 1. The pair, exploded 6 mm along each axis so both mates are visible, with
//    a 4 mm D-shaft bore in the pinion and a round 5 mm bore in the crown.
bevel_pair(n1, n2, mod, bore1 = 4, bore2 = 5, flat1 = 3.5, explode = 6);

// 2. The same pinion alone, in its PRINT orientation: back face on z = 0,
//    apex up. This is the part a design's ci.parts would export.
translate([50, 0, 0])
    bevel_gear_fdm(n1, n2, mod, bore = 4, flat = 3.5, anchor = "back");

// 3. The crown alone, print orientation. Its cone angle (60 deg) is above the
//    fill threshold, so its tooth ends print on a cylindrical backing with no
//    under-tooth fill — the other branch of the same module.
translate([100, 0, 0])
    bevel_gear_fdm(n2, n1, mod, bore = 5, anchor = "back");

// 4. A non-right-angle pair (110 deg shafts, 12:20 at mod 1), meshed at
//    phase 30, on the "pitchbase" anchor path for the lone gear beside it.
translate([0, 60, 0]) bevel_pair(12, 20, 1, shaft_angle = 110, phase = 30);
translate([50, 60, 0]) bevel_gear_fdm(12, 20, 1, shaft_angle = 110, anchor = "pitchbase");

// 5. The spur pair (a reduction stage), exploded 4 mm, and one spur gear
//    alone spun a third of a tooth.
translate([0, -50, 0]) spur_pair(12, 30, 1, 5, bore1 = 3, bore2 = 4, flat2 = 3.5, explode = 4);
translate([70, -50, 0]) spur_gear_fdm(12, 30, 1, 5, bore = 3, phase = 10);

// 6. The interference solids at the declared clearance: EMPTY by the mates
//    manifest, so these add no geometry. They are here so the demo covers
//    every module; the measurement that matters is lib/bevel-mates.conf.
bevel_pair_interference(n1, n2, mod, phase = 8);
spur_pair_interference(12, 30, 1, 5, phase = 11);

// 7. The placement contract, echoed. A consuming design reads these to put
//    the pinion on its axle and the crown on its tumble axis.
echo(bevel_tol = bevel_tol_default());
echo(cone_angles = [bevel_cone_angle(n1, n2), bevel_cone_angle(n2, n1)]);
echo(cone_dist = bevel_cone_dist(n1, n2, mod), face_default = bevel_face_default(n1, n2, mod),
     face_max = bevel_face_max(n1, n2, mod));
echo(pinion = [bevel_pitch_r(n1, mod), bevel_apex_h(n1, n2, mod), bevel_pitchbase_z(n1, n2, mod),
               bevel_backface_z(n1, n2, mod), bevel_outer_r(n1, n2, mod)]);
echo(crown = [bevel_pitch_r(n2, mod), bevel_apex_h(n2, n1, mod), bevel_pitchbase_z(n2, n1, mod),
              bevel_backface_z(n2, n1, mod), bevel_outer_r(n2, n1, mod)], axis = bevel_axis(90));
echo(mate_phase_at_8 = bevel_mate_phase(n1, n2, 8), spur_dist = spur_dist(12, 30, 1),
     spur_mate_phase_at_11 = spur_mate_phase(12, 30, 11));
echo(backlash_per_gear = bevel_backlash(bevel_tol_default()),
     root_clearance = bevel_clearance(mod, bevel_tol_default()));
