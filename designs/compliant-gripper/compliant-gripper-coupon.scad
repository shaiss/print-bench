// Print this first. The production gripper with every moving interface at
// production values — plunger between the race walls, under the rail, pin in
// the cam notch, detent tip in the tooth valley — shortened only in the grip
// zone (grip_len 32 -> 16). The leaves stay at production length: the detent
// hold guard is a force balance (tan(hold_ang)·R_seat vs the jaw drive), and
// a shortened leaf is a stiffer leaf — it would out-drive the detent, so the
// guards refuse it and the coupon would prove a fit the real part doesn't
// have. Nothing copied; the override sits below the include (OpenSCAD
// resolves top-level variables last-assignment-wins). Print it, work the
// tab: if the plunger is fused, raise xy_tol by 0.05 mm and reprint; if it
// rattles, lower it. Tune xy_tol here before the full print.
// NOT a force coupon: the detent force reads on the full part, in the
// field-test log.
include <compliant-gripper.scad>
grip_len = 16;
