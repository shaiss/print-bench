// Kinematics-gate include-closure parent (issue #791): dispatch branches and
// the sweep/stops assignment live HERE. A variable-only child that only
// `include`s this file (or a mid file that includes it) must still pass the
// part-branch and parameter proofs. Units: mm. Tiny on purpose.
//
// `counterpart == "closure-nope"` is the lookalike the stricter matcher must
// still refuse when the child's manifest names that part.

/* [Landing stop] */
stop = 0;               // integer stop index; gate-stepped from the child
part = "assembled";     // which boolean to render

$fn = 8;

if (part == "closure-empty") {
    // Two disjoint cubes: the empty check's expected mesh.
    intersection() {
        cube(1);
        translate([10, 0, 0]) cube(1);
    }
} else if (part == "closure-solid") {
    cube(1);
} else if (counterpart == "closure-nope") {
    // Lookalike identifier: must NOT count as part == "closure-nope"
    cube(1);
} else if (part == "assembled") {
    cube(1);
}
