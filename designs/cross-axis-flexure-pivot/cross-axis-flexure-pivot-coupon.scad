// Print this first (protocol: NOTES.md, "Print this first"). One strip of
// STRAIGHT single-beam specimens from the production modules: the t ladder
// (0.6 / 0.8 / 1.0 — 0.8 is the production beam) plus two IDENTICAL
// production-t twins. Print the strip once per material and read the twin
// labelled for what is loaded. Scope: qualifies t and filament only — there
// is no crossing and no weld on this strip; cycle the production pivot for
// the welded X. Swing each specimen ±40 deg in the layer plane and count
// cycles to whitening / crack. A ladder row that dies early is telling you
// where the floor is, not that the design failed. No overrides below the
// include on purpose — the twins must test true production values. Override
// the ladder only to extend it, e.g.:
//   cross-axis-flexure-pivot-coupon.scad + -D 'coupon_ts=[0.7, 0.9]'
include <cross-axis-flexure-pivot.scad>
part = "coupon";
