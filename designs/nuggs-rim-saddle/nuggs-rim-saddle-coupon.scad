// "Print this first" coupon (PRINT THIS FIRST): both tuned fits in one part.
// Zone A - port_tol: two port stubs, snap and twist; ±0.05 until it retains at
// sane torque. Zone B - grip_gap: the latch flange + one production arm; snap
// the arm home, it must latch and release with one finger pull; ±0.05 until
// the grip feels right. THEN caliper your panel (glass_t, lip_d, lip_h) and
// re-render the saddle before printing the body. See NOTES.md "Print this first".
include <nuggs-rim-saddle.scad>
part = "coupon";
