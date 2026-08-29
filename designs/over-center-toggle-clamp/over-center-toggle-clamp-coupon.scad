// Print this first — and measure with it. The brief's force artifact: the
// PRODUCTION arch (same parameters, same modules) between two M5-anchored
// posts, with a pull tab on the apex. Bolt the posts to anything rigid with
// the tab hanging DOWN, add weight to the tab hole until the beam snaps
// through: that weight is the arch's snap force f_snap, and the clamp's
// switch force is f_snap * arm_flank / handle_r_out (values echoed by the
// parent file). If the snap weight is more than ~35% off the predicted
// value, your PETG modulus differs from E_mod — tune E_mod, not the geometry.
include <over-center-toggle-clamp.scad>
part = "coupon";
