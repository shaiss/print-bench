// Fixture for bed-fit + non-intersection behavioral tests (#1049 / #1060).
// demo_mode:
//   "plate0" / "plate1" / "plate2" — one bed-sized print unit
//   "all"                          — full multi-strip composition
//   "overlap_control"              — two specimens forced to share volume;
//                                    must fuse to 1 body (falsifiability)
//
// Extended XAFP ladder: the test passes
//   -D 'coupon_ts_xafp=[0.6,0.8,1.0,1.2,1.4]' with demo_mode="all"
// (include, not use: -D must reach the strip modules).
demo_mode = "plate0";

include <compliant-coupon.scad>
// Last-assignment-wins: suppress the library print entrypoint so only the
// selected demo_mode geometry is emitted.
coupon_emit = false;

if (demo_mode == "plate0")
    compliant_coupon_plate(0);
else if (demo_mode == "plate1")
    compliant_coupon_plate(1);
else if (demo_mode == "plate2")
    compliant_coupon_plate(2);
else if (demo_mode == "all")
    compliant_coupon_plate("all");
else if (demo_mode == "overlap_control") {
    // Negative control: two production LET grips overlapping must fuse.
    coupon_let_specimen(1.2, "A", [0, 0, 0], production = true);
    coupon_let_specimen(1.2, "B", [25.5, 0, 0], production = true);
}
