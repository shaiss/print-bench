// Print this first (protocol: NOTES.md, "Print this first"). One strip,
// straight from the production modules: the t ladder (0.6 / 0.8 / 1.0 —
// 0.8 is the production beam) plus two IDENTICAL production-t twins, one to
// print in PETG and one in PLA, so the material ranking is measured, not
// assumed. Twist each specimen ±40 deg in the layer plane and count cycles
// to whitening / crack; the brief's target is >= 200 at ±40°. A ladder row
// that dies early is telling you where the floor is, not that the design
// failed. No overrides below the include on purpose — the twins must test
// true production values. Override the ladder only to extend it, e.g.:
//   cross-axis-flexure-pivot-coupon.scad + -D 'coupon_ts=[0.7, 0.9]'
include <cross-axis-flexure-pivot.scad>
part = "coupon";
