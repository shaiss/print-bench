// Fixture for test_compliant_stiffness_coupon.py body-count cases (#1049).
// demo_mode selects one production twin; each must be exactly one body.
demo_mode = "arch";

use <compliant-coupon.scad>

if (demo_mode == "arch")
    coupon_arch_specimen(0.82, "PETG", [0, 0, 0], production = true);
else if (demo_mode == "slfp")
    coupon_slfp_specimen(1.0, "PETG", [0, 0, 0], production = true);
else if (demo_mode == "xafp")
    coupon_xafp_specimen(0.8, "PETG", [0, 0, 0], production = true);
else if (demo_mode == "let")
    coupon_let_specimen(1.2, "PETG", [0, 0, 0], production = true);
