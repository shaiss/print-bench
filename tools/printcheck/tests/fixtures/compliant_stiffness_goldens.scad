// Fixture for test_compliant_stiffness_coupon.py (#1049).
// demo_mode:
//   "ok"    — harvest-site goldens; must render (assert pass)
//   "bad_k" — deliberately wrong SLFP K golden; must abort (assert fail)
demo_mode = "ok";

use <compliant.scad>

// Independently recorded production span/rise (not inverse-solved).
arch_rise_g = 2.020202020202;
arch_span_g = 82.0288876896;

if (demo_mode == "ok") {
    assert(abs(bistable_arch_fs(arch_span_g, arch_rise_g, 0.82, 6) - 3) < 1e-6);
    assert(abs(bistable_arch_travel(arch_rise_g) - 4) < 1e-6);
    assert(abs(bistable_arch_rise_for(4) - arch_rise_g) < 1e-9);
    assert(abs(bistable_arch_span_for(3, arch_rise_g, 0.82, 6) - arch_span_g) < 1e-6);
    assert(abs(small_length_pivot_K(1.0, 12, 15) - 208.333333333) < 1e-3);
    assert(abs(cross_axis_pivot_K(0.8, 28, 8) - 195.047619048) < 1e-3);
    assert(abs(let_joint_K(1, 3, 2.0, 1.2, 14) - 110.388081894) < 1e-3);
    echo(str("GOLDEN_OK arch_fs=",
             bistable_arch_fs(arch_span_g, arch_rise_g, 0.82, 6),
             " slfp_K=", small_length_pivot_K(1.0, 12, 15),
             " xafp_K=", cross_axis_pivot_K(0.8, 28, 8),
             " let_K=", let_joint_K(1, 3, 2.0, 1.2, 14)));
    cube(0.1);
} else if (demo_mode == "bad_k") {
    // Negative control: a wrong golden MUST abort. If this ever renders,
    // the assert harness is inert.
    assert(abs(small_length_pivot_K(1.0, 12, 15) - 999) < 1e-3,
           "deliberate wrong golden — must fail");
    cube(0.1);
}
