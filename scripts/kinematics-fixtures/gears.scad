// Kinematics-gate fixture (scripts/kinematics-check.sh --selftest): a BOSL2
// spur-gear pair swept through ONE mesh cycle, plus the two deliberately
// broken pairs that prove the rotational-mesh gate can fail. Units: mm.
//
// The gate sweeps `kin_phase` over [0,1) — one tooth pitch of gear A, so the
// pair returns to its start pose at 1 — and renders the boolean part named by
// `part` at every step, counting facets:
//   mesh-clear    gearA ∩ gearB                  empty at every phase → no interference
//   mesh-engaged  grow(gearA, engage_grow) ∩ gearB  non-empty at every phase → the teeth
//                                                   never separate (contact ratio > 1)
//   mesh-jam      gearA ∩ gearB at a SHRUNK centre distance — the empty-control:
//                 must interfere at some phase, or the empty checks are unfalsifiable
//   mesh-gap      grow(gearA) ∩ gearB at a GROWN centre distance — the
//                 nonempty-control: must gap out at some phase
//   assembled     both gears, for a human to look at (not gated)
// Coarse on purpose ($fn=24, 12/15 teeth, 3 mm thick): the selftest renders
// these dozens of times on a shared box.
include <BOSL2/std.scad>
include <BOSL2/gears.scad>

/* [Kinematics sweep] */
kin_phase = 0;          // fraction of one mesh cycle, swept over [0,1) by the gate
part = "assembled";     // which boolean to render (see the header)

/* [Gear pair] */
circ_pitch = 5;         // mm, circular pitch shared by both gears
teeth_a = 12;           // driver tooth count
teeth_b = 15;           // driven tooth count
thickness = 3;          // mm, face width
backlash = 0.1;         // mm, per-gear backlash (the clearance that keeps mesh-clear empty)
engage_grow = 0.6;      // mm, how far the driver is grown for the engaged proof
jam_shrink = 0.8;       // mm, centre-distance shrink of the jam control
gap_grow = 3;           // mm, centre-distance growth of the gap control

$fn = 24;               // coarse: fixture, never printed

// Nominal centre distance for this pair (BOSL2 accounts for the profile shift).
dist = gear_dist(circ_pitch=circ_pitch, teeth1=teeth_a, teeth2=teeth_b);

// Gear A at the origin, rotated through the cycle. `grow` inflates its 2D
// profile by that many mm (offset(r=)), which is how the engaged proof asks
// "are the teeth within `grow` of each other?" without a Minkowski sum.
module gear_a(grow=0) {
    linear_extrude(height=thickness, center=true)
        offset(r=grow)
            spur_gear2d(circ_pitch=circ_pitch, teeth=teeth_a, backlash=backlash,
                        gear_spin=-90 + kin_phase * 360 / teeth_a);
}

// Gear B at centre distance `d` on +X, counter-rotating so the two stay in
// mesh; the -180/teeth_b term is BOSL2's own tooth-to-gap alignment (see the
// gear_dist() example in lib/BOSL2/gears.scad).
module gear_b(d) {
    right(d) linear_extrude(height=thickness, center=true)
        spur_gear2d(circ_pitch=circ_pitch, teeth=teeth_b, backlash=backlash,
                    gear_spin=90 - 180 / teeth_b - kin_phase * 360 / teeth_b);
}

if (part == "mesh-clear") {
    intersection() { gear_a(); gear_b(dist); }
} else if (part == "mesh-engaged") {
    intersection() { gear_a(engage_grow); gear_b(dist); }
} else if (part == "mesh-jam") {
    intersection() { gear_a(); gear_b(dist - jam_shrink); }
} else if (part == "mesh-gap") {
    intersection() { gear_a(engage_grow); gear_b(dist + gap_grow); }
} else if (part == "assembled") {
    gear_a();
    gear_b(dist);
}
