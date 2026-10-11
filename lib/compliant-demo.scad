// Exercises every module in compliant.scad — check.sh CGAL-renders this on
// every run, so it is the library's geometry regression test (the guards
// have their own negative suite in compliant-guards.conf: a firing assert
// aborts the render it lives in, so a demo can only ever show the accepting
// half). Not a printable design. All dimensions in millimeters.
use <compliant.scad>

// The root-fillet arcs are the library's only curved surfaces (the arch band
// is sampled by its own `ns`, independent of $fn). bistable-toggle's
// production value.
$fn = 48;

// ---------------------------------------------------------------------------
// Station 1: bistable-toggle's production arch, SOLVED from its targets with
// the library's inverse functions (f_s = 3 N, u_tr = 4 mm, t = 0.82,
// w = 6, E = 2000 → span ≈ 82.03, rise ≈ 2.02 — bit-identical to the design's
// own derivation), filleted at r = 0.5·t, unioned in 2D with caller-owned
// clamp posts whose faces sit exactly at x = 0 and x = span (the library's
// frame). Beside it, the snapped second state: the same arch mirrored about
// its chord.
// ---------------------------------------------------------------------------
t1 = 0.82; w1 = 6;
rise1 = bistable_arch_rise_for(4);
span1 = bistable_arch_span_for(3, rise1, t1, w1);
post = 6;

module clamps_2d(span, hh) {
    for (x0 = [-post, span]) translate([x0, -hh]) square([post, 2 * hh]);
}

linear_extrude(w1) union() {
    clamps_2d(span1, 4);
    bistable_arch_2d(span1, rise1, t1, root_fillet = 0.5 * t1);
}
translate([0, -12, 0]) linear_extrude(w1) union() {
    clamps_2d(span1, 4);
    mirror([0, 1]) bistable_arch_2d(span1, rise1, t1, root_fillet = 0.5 * t1);
}

// ---------------------------------------------------------------------------
// Station 2: the 3D path — bistable_arch() extruded by the library (echoes
// the predicted switch force and travel), BURIED ov = 1.2 into 3D clamp
// cubes rather than kissing them (a face-to-face kiss is fused by CGAL but
// exported by Manifold as a separate shell). The cubes cover the documented
// root footprint: |y| ≤ t/2 + root_fillet over x ∈ [−ov, 0].
// ---------------------------------------------------------------------------
translate([0, 16, 0]) {
    bistable_arch(span1, rise1, t1, w1, E = 2000, root_fillet = 0.5 * t1, ov = 1.2);
    for (x0 = [-post, span1]) translate([x0, -4, 0]) cube([post, 8, w1]);
}

// ---------------------------------------------------------------------------
// Station 3: a calibration-coupon cell — bistable-toggle's sweep at l = 35,
// h/t = 1.5, deliberately MONOSTABLE (its negative control; the snap should
// die here). Only allow_monostable lets the library build it; the echo says
// so instead of printing a switch force the arch does not have.
// ---------------------------------------------------------------------------
translate([100, 0, 0]) {
    bistable_arch(35, 1.5 * t1, t1, w1, root_fillet = 0.5 * t1, ov = 1.2,
                  allow_monostable = true);
    for (x0 = [-post, 35]) translate([x0, -4, 0]) cube([post, 8, w1]);
}

// ---------------------------------------------------------------------------
// Station 4: root_fillet_2d — snap-cantilever-clip's root: a t = 1.0 finger
// (x ∈ [−t, 0]) hanging from a strap (y ≥ 20), the fillet in the concave
// corner (x > 0, y < 20), r = 0.6 — placed exactly as the clip places it.
// Beside it, the same corner with a 0.06 mm bite (area weld, for curved
// faces or a 3D union).
// ---------------------------------------------------------------------------
translate([100, 20, 0]) linear_extrude(15) union() {
    translate([-1, 10]) square([1, 14]);           // finger
    translate([-1, 20]) square([8, 4]);            // strap
    translate([0, 20]) mirror([0, 1]) root_fillet_2d(0.6, 1.0);
    translate([12, 0]) {
        translate([-1, 10]) square([1, 14]);
        translate([-1, 20]) square([8, 4]);
        translate([0, 20]) mirror([0, 1]) root_fillet_2d(0.6, 1.0, bite = 0.06);
    }
}

// ---------------------------------------------------------------------------
// Station 5: rooted_2d — let-folding-panel's LET hinge silhouette (one half:
// the torsion-bar strip plus alternate fingers, t = 1.2, r = 0.8): every
// finger↔bar root filleted by one closing. No clearance gap inside the
// wrapped silhouette — a closing fills any slot narrower than 2·r.
// ---------------------------------------------------------------------------
translate([0, 40, 0]) linear_extrude(1.2) rooted_2d(0.8, 1.2) {
    square([70, 1]);
    for (i = [0 : 2 : 3]) translate([i * 17.5 + 7, -7]) square([3.5, 8]);
}

// ---------------------------------------------------------------------------
// Station 6: boundary-accepting renders — the accepting halves of the range
// guards, which a refusals-only guards manifest cannot express: t at the
// 0.8 floor; and an arch exactly ON every other bar at once (rise/t = 2.3,
// span/rise = 10, root_fillet = 0.5·t, ns = 16).
// ---------------------------------------------------------------------------
translate([100, 50, 0]) {
    linear_extrude(4) union() {
        clamps_2d(30, 3);
        bistable_arch_2d(30, 2.0, 0.8, root_fillet = 0.4);
    }
    translate([0, 12, 0]) linear_extrude(4) union() {
        clamps_2d(23, 3);
        bistable_arch_2d(23, 2.3, 1, root_fillet = 0.5, ns = 16);
    }
}

echo(str("[compliant-demo] solve: rise = ", rise1, " mm, span = ", span1,
         " mm; predicted f_s = ", bistable_arch_fs(span1, rise1, t1, w1), " N, u_tr = ",
         bistable_arch_travel(rise1), " mm; centreline at mid-span = ",
         bistable_arch_y(span1 / 2, span1, rise1), " mm"));
echo(str("[compliant-demo] boundary arch: rise/t = ", 2.3 / 1, ", span/rise = ", 23 / 2.3,
         " — both exactly on their bars, accepted"));
