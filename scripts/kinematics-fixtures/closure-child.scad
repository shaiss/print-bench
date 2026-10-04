// Two-hop include of closure-parent.scad — the variable-only-derivative
// shape (issue #791): this file has no `part ==` dispatcher and no top-level
// `stop` of its own. Entry-file grep is blind; the include-closure walk
// must still accept the parent's kinematics parts.
include <closure-mid.scad>
