// Kinematics-gate fixture (scripts/kinematics-check.sh --selftest): a
// five-faced numeral shell posed at discrete LANDING STOPS, plus the
// reader-frame probes that decide whether the presenting face landed flat and
// whether its numeral reads upright — and the rolled/mirrored controls that
// prove each probe can fail. Units: mm.
//
// Frame: the shell's axis is X. The reader looks along -Y with Z up, so the
// presenting face is the one whose outward normal is +Y; its glyph is drawn
// in reader coordinates (u = reader's right = -X, v = up = +Z). Face k has
// its outward normal at k*360/faces from +Y (toward +Z) in the shell's own
// frame, and the pose that presents face k rolls the shell by -k*360/faces
// about X, so `stop` (an integer the gate steps through) both selects the
// face and poses it.
//
// The gate evaluates `part` at every declared stop and counts facets:
//   landing-flat          posed shell ∩ the slab beyond the landed face plane
//                         (offset by the roll tolerance) — empty when the face
//                         landed within tol_deg of reader-upright
//   landing-flat-in-tol   the same, rolled by HALF the tolerance — still empty,
//                         so the tolerance is a tolerance and not an equality
//   landing-flat-rolled   rolled by roll_err — the empty-control: the top
//                         vertex crosses the slab, so it must show facets
//   landing-glyph         posed numeral cutter ∩ the chiral-stroke probe (a box
//                         only the upright, right-handed numeral covers) —
//                         non-empty when the numeral reads correctly
//   landing-glyph-mirrored  the numeral engraved back-to-front — the
//                         nonempty-control: the stroke is on the other side
//   landing-glyph-rolled  the numeral rolled by roll_err — the second
//                         nonempty-control: the stroke has moved off the probe
//   landing-glyph-cover   upright template (shrunk by cover_tol) − posed cutter
//                         — empty when the posed numeral COVERS the upright
//                         template, the stronger form of the glyph proof
//   landing-glyph-cover-mirrored  the same against the mirrored numeral —
//                         empty-control: the template's stroke is uncovered
//   assembled             the posed shell, for a human to look at (not gated)

/* [Landing stop] */
stop = 0;               // integer stop index; face `stop` presents at this stop (gate-stepped)
part = "assembled";     // which boolean to render (see the header)

/* [Shell] */
faces = 5;              // faces around the axis (a pentagon shell)
R = 12;                 // mm, circumradius of the shell polygon
len = 10;               // mm, axial length of the shell
tol_deg = 3;            // deg, roll tolerance the flat probe allows
roll_err = 20;          // deg, the mis-landing the rolled controls exhibit
glyph_depth = 1;        // mm, the numeral engraving depth
cover_tol = 0.35;       // mm, the upright template is shrunk by this before the cover test

$fn = 24;               // coarse: fixture, never printed

step_deg = 360 / faces;
apothem = R * cos(180 / faces);                    // face-plane distance from the axis
// A landed face rolled by d puts its top vertex at R*cos(180/faces - d) from
// the axis, beyond the face plane; the slab starts where a tol_deg roll would
// put it, so anything within tolerance stays below the probe.
flat_eps = R * (cos(180 / faces - tol_deg) - cos(180 / faces));

// The numeral: a "7" in reader coordinates (u right, v up). Chiral on purpose
// — its stem leans, so a mirrored copy is a different shape and a probe can
// tell them apart.
seven = [[-2, 3], [2, 3], [2, 2], [-0.5, -3], [-1.5, -3], [1, 2], [-2, 2]];

// 2D numeral in the shell's XZ plane: reader u = -X, so the upright numeral
// is the mirror of `seven`; the mirrored numeral is `seven` as drawn.
module numeral2d(mirrored=false) {
    if (mirrored) polygon(seven); else mirror([1, 0]) polygon(seven);
}

// The cutter for face 0 (normal +Y): the numeral extruded from just outside
// the face plane down to glyph_depth into it.
module cutter0(mirrored=false) {
    translate([0, apothem + 0.5, 0]) rotate([90, 0, 0])
        linear_extrude(height=glyph_depth + 0.5) numeral2d(mirrored);
}

// Every face's cutter, in the shell frame.
module cutters(mirrored=false) {
    for (k = [0 : faces - 1]) rotate([k * step_deg, 0, 0]) cutter0(mirrored);
}

// The shell: a `faces`-gon prism along X with one face centred on +Y, the
// numerals engraved into every face.
module shell(mirrored=false) {
    difference() {
        rotate([90, 0, 90]) linear_extrude(height=len, center=true)
            polygon([for (k = [0 : faces - 1])
                let (a = 180 / faces + k * step_deg) [R * cos(a), R * sin(a)]]);
        cutters(mirrored);
    }
}

// Pose that presents face `stop`, plus an optional roll error.
module posed(err=0) {
    rotate([-stop * step_deg + err, 0, 0]) children();
}

// Probes, all in the reader frame on the presenting face.
module flat_probe() {
    translate([-len / 2 - 1, apothem + flat_eps, -R]) cube([len + 2, 5, 2 * R]);
}
// Inside the "7"'s stem near its foot: at v=-1.75 the upright stem spans
// u in [-0.875, 0.125], the mirrored one [-0.125, 0.875], and the rolled-180
// numeral's stem sits at u in [-1.875, -0.875]; the probe at u in [-0.8,-0.3]
// meets only the upright stroke.
module stroke_probe() {
    translate([0.3, apothem - glyph_depth + 0.1, -1.9]) cube([0.5, glyph_depth + 0.2, 0.3]);
}
// The upright numeral shrunk by cover_tol, spanning the engraved depth.
module cover_template() {
    translate([0, apothem - 0.2, 0]) rotate([90, 0, 0])
        linear_extrude(height=glyph_depth - 0.4)
            offset(delta=-cover_tol) numeral2d();
}

if (part == "landing-flat") {
    intersection() { posed() shell(); flat_probe(); }
} else if (part == "landing-flat-in-tol") {
    intersection() { posed(tol_deg / 2) shell(); flat_probe(); }
} else if (part == "landing-flat-rolled") {
    intersection() { posed(roll_err) shell(); flat_probe(); }
} else if (part == "landing-glyph") {
    intersection() { posed() cutters(); stroke_probe(); }
} else if (part == "landing-glyph-mirrored") {
    intersection() { posed() cutters(mirrored=true); stroke_probe(); }
} else if (part == "landing-glyph-rolled") {
    intersection() { posed(roll_err) cutters(); stroke_probe(); }
} else if (part == "landing-glyph-cover") {
    difference() { cover_template(); posed() cutters(); }
} else if (part == "landing-glyph-cover-mirrored") {
    difference() { cover_template(); posed() cutters(mirrored=true); }
} else if (part == "assembled") {
    posed() shell();
}
