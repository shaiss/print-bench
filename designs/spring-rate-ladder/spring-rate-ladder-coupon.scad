// Print this first — the spring-rate-ladder coupon: one N=6 spring (the
// middle ladder station) rooted on a guided base pad. Print it beside the
// `cap` part, compress it against a kitchen scale, and read your filament's
// real spring rate; NOTES.md → "Print this first" walks the steps. All
// geometry lives in the entry file; this wrapper only picks the part.
// Include first, override after (last-assignment-wins in the root scope).
include <spring-rate-ladder.scad>;

part = "coupon";
