// Exercises lib/compliant-coupon.scad — check.sh CGAL-renders every
// lib/*-demo.scad, so this is how the stiffness coupon stays in the check
// that matters (issue #1049). Also pins the harvest-site predicted K / f_s
// values with asserts that FAIL the render if a formula drifts — a wrong
// echo is catchable in CI, never restated-and-trusted (issue #37).
use <compliant.scad>
use <compliant-coupon.scad>

// ---------------------------------------------------------------------------
// Golden harvest-site predictions (OpenSCAD 2021.01 echoes, 2026-11-21).
// If a constant or formula in compliant.scad moves these, the assert fires
// and check.sh goes red — that is the point.
// ---------------------------------------------------------------------------
arch_rise_g = bistable_arch_rise_for(4);
arch_span_g = bistable_arch_span_for(3, arch_rise_g, 0.82, 6);
assert(abs(bistable_arch_fs(arch_span_g, arch_rise_g, 0.82, 6) - 3) < 1e-6,
       str("arch f_s golden drifted: got ",
           bistable_arch_fs(arch_span_g, arch_rise_g, 0.82, 6), " want 3"));
assert(abs(bistable_arch_travel(arch_rise_g) - 4) < 1e-6,
       str("arch u_tr golden drifted: got ",
           bistable_arch_travel(arch_rise_g), " want 4"));

assert(abs(small_length_pivot_K(1.0, 12, 15) - 208.333333333) < 1e-3,
       str("SLFP K golden drifted: got ", small_length_pivot_K(1.0, 12, 15),
           " want ~208.333"));

assert(abs(cross_axis_pivot_K(0.8, 28, 8) - 195.047619048) < 1e-3,
       str("cross-axis K golden drifted: got ",
           cross_axis_pivot_K(0.8, 28, 8), " want ~195.048"));

assert(abs(let_joint_K(1, 3, 2.0, 1.2, 14) - 110.388081894) < 1e-3,
       str("LET K golden drifted: got ", let_joint_K(1, 3, 2.0, 1.2, 14),
           " want ~110.388"));

echo(str("[compliant-coupon-demo] goldens OK: arch f_s=3 u_tr=4; ",
         "SLFP K=", small_length_pivot_K(1.0, 12, 15),
         "; XAFP K=", cross_axis_pivot_K(0.8, 28, 8),
         "; LET K=", let_joint_K(1, 3, 2.0, 1.2, 14)));

// The printable plate — every module, t-ladder + production twins.
compliant_coupon_plate();
