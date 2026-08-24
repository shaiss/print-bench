// Tuned-flexure coupon (PRINT THIS FIRST): the production LET joint at hand
// scale — 2 A-fingers + 1 B-finger, so 2 real torsion spans, straight from
// the production modules (nothing copied). Fold it to 90° and cycle it ~50
// times; it should fold smooth and hold. Feels wrong? Stiffness is t^3 —
// tune t in ±0.2 steps (sweep in NOTES.md "Print this first"); TEARING is
// strain (θ·r/L), so fix tears by lengthening L (drop a finger) or narrowing
// w, not by thickening t.
include <let-folding-panel.scad>
fingers = 3;     // one full torsion pair
hinge_w = 52.5;  // = 3 × pitch — panels end flush with the bar
panel_d = 15;    // short panels: the joint is what you are testing
