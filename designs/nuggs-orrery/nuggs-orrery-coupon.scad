// Print-this-first coupon for nuggs-orrery: ONE ring station (tube stub,
// fin band, race, captive ring) from the production modules. Tune race_gap
// in +/-0.05 steps until the ring releases with a light twist and spins
// free — see "Print this first" in NOTES.md. Overrides sit BELOW the
// include: OpenSCAD's include-then-override semantics mean a later
// assignment wins (sushi-battleship-coupon.scad is the reference).
include <nuggs-orrery.scad>
part = "coupon";
