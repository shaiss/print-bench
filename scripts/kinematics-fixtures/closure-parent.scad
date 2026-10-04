// Kinematics-gate fixture parent (scripts/kinematics-check.sh --selftest,
// issue #791): the live `part ==` dispatcher and the top-level `stop`
// assignment a variable-only child inherits via include. Tiny cubes — the
// selftest renders them; nobody prints them. Units: mm.
//
//   closure-empty   two disjoint cubes intersected → 0 facets
//   closure-solid   a cube → non-empty (empty-control / nonempty check)
//   assembled       the same cube (ungated default)
//   counterpart == "closure-counterpart-only" is a lookalike that must NOT
//                   satisfy a `part == "…"` dispatch check on the child.

/* [Landing stop] */
stop = 0;
part = "assembled";

$fn = 12;

if (part == "closure-empty") {
    intersection() {
        cube(1);
        translate([10, 0, 0]) cube(1);
    }
} else if (part == "closure-solid") {
    cube(1);
} else if (counterpart == "closure-counterpart-only") {
    cube(1);
} else if (part == "assembled") {
    cube(1);
}
