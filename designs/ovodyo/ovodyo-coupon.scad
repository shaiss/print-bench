// Print this first: the ball seam's male ring and female puck side by side, cut
// from the production seam modules (nothing copied) so the seam_tol that fits
// here is the seam_tol the four ball halves get. Screw the puck onto the ring:
// it should turn on by hand with light drag and seat flat with no rattle. Too
// tight -> raise seam_tol by 0.05 and reprint; loose/rattly -> lower it. See
// NOTES.md "Print this first". Override sits below the include (last wins).
include <ovodyo.scad>
part = "seam-coupon";
