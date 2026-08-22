// Print this first. A 72 x 56 tile carrying all FOUR mechanisms: one of each
// tuned fit — spinner radial gap (xy_tol), bead slide fit (slide_tol), hinge
// clearance (hinge_clear) — plus the pop button, which has no parameter but
// a feel to check (a fat first layer turns the snap mushy). Tune on your
// printer in ~45 min before spending ~80 on the full card. See NOTES.md
// "Print this first". The wrapper relies on include-then-override:
// `coupon = true` re-lays the same production modules onto the tile
// (nothing copied).
include <pop-fidget-card.scad>
coupon = true;
