// Fusecheck-gate fixture (scripts/fusecheck-check.sh --selftest, issue #627):
// a tiny two-pose design the fixture manifests gate. Each pose is one way a
// body count can land, and the manifests pin the verdict each must produce:
//   separable   two cubes with a 2 mm gap — two separable bodies (the count
//               every passing assert row expects)
//   fused       two cubes sharing a full face — one connected body over the
//               face-adjacency graph (the count the WARN row cannot meet and
//               the mandatory control must stay at)
//   assembled   both poses side by side, the ungated default render
// Units: mm. Plain cubes on purpose — the selftest renders it, nobody prints
// it, and the body count must stay 2 / 1 at any curve quality.
part = "assembled";     // which pose to render (see the header)

module separable() {
    translate([-6, 0, 0]) cube([10, 10, 10]);
    translate([+6, 0, 0]) cube([10, 10, 10]);
}

module fused() {
    translate([-10, 0, 0]) cube([10, 10, 10]);
    cube([10, 10, 10]);
}

module assembled() {
    translate([-30, 0, 0]) separable();
    translate([+30, 0, 0]) fused();
}

if (part == "separable") separable();
else if (part == "fused") fused();
else assembled();
