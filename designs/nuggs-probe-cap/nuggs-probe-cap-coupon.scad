// Print-this-first fit coupon for the NUGGS probe cap. Include-and-override
// on the production entry point — no copied geometry: the two grips are the
// very grip_boss/grip_cut modules the cap calls, at production parameters.
// The wrapper relies on include-then-override semantics: the override stays
// above nothing (there is no geometry above it in this file), and the entry
// point dispatches on `part`.
// Tune here, in +/-0.05 steps on -D grip_clearance=... :
//   0.20 (default) - slides free, seals the annulus (bedding/draft tight)
//   0.10 - light pinch, holds the probe by friction
//   0.05 - hard grip, needs PETG fingers; PLA may crack them
include <nuggs-probe-cap.scad>
part = "coupon";
