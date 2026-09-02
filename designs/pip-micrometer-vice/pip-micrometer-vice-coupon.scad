// Print this first — the pip-micrometer-vice coupon: three screw/nut pairs
// sweeping thread_tol (1/2/3 = 0.25/0.30/0.35, production = 2) and three
// channel/slider pairs sweeping clr_h (A/B/C = 0.25/0.30/0.35, production
// = B). All geometry lives in the entry file; this wrapper only picks the
// part. Include first, override after (last-assignment-wins in root scope).
include <pip-micrometer-vice.scad>;

part = "coupon";
