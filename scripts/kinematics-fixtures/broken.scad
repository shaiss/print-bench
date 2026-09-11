// Kinematics-gate fixture (scripts/kinematics-check.sh --selftest): sources
// the gate must REFUSE or FAIL rather than measure. Each branch is one way a
// manifest can look green over nothing:
//   broken-in-line-comment    named only inside a // comment (the trailing one
//                             on the first `if` below) — the raw-source grep
//                             the gate used to run matched it; comments are
//                             stripped before the dispatch check now
//   broken-in-block-comment   the same, named only inside a /* */ block
//   broken-assert             a branch that aborts on an assert: the render
//                             FAILS, and the gate must say so in the line
//                             shape gate-summary.py collects
//   broken-unknown-module     a branch calling a module that does not exist:
//                             OpenSCAD only WARNs, skips the call and renders
//                             EMPTY — which an `empty` check would pass with a
//                             mesh that is not the design's; the gate reads
//                             the render log and fails on the WARNING
//   broken-solid              a plain cube, the control that lets the
//                             manifests above be well-formed
//   assembled                 the same cube (not gated)
// Units: mm. Tiny on purpose — the selftest renders it, nobody prints it.

/* [Landing stop] */
stop = 0;               // integer stop index, stepped by the gate
part = "assembled";     // which branch to render (see the header)

/*
 * A dispatch branch that exists only in prose — a raw grep matches it:
 *   } else if (part == "broken-in-block-comment") { cube(1); }
 * and the block comment is what the stripper must see through.
 */

if (part == "broken-assert") {          // if (part == "broken-in-line-comment") — prose, not a branch
    assert(false, "kinematics fixture: this branch fails on purpose");
    cube(1);
} else if (part == "broken-unknown-module") {
    no_such_module();                   // WARNING: Ignoring unknown module — renders empty
} else if (part == "broken-solid") {
    cube(1);
} else if (part == "assembled") {
    cube(1);
}
