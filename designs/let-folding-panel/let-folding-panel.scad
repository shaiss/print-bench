// let-folding-panel — two panels joined by a Lamina-Emergent Torsional (LET)
// joint: a compliant hinge fabricated FLAT from a single layer that folds up
// to ~90°. Reference design for docs/advanced-techniques.md Domain 1
// (compliant mechanisms), the lamina-emergent family — "the best FDM match"
// per the doc — and CC1 (orientation): it is flat by nature, so the flex is in
// the layer plane by construction.
//
// How a LET works, and how this models it. The fold line runs along X at y = 0.
// A thin TORSION STRIP lies on that line, spanning the whole width. Each panel
// reaches the strip only through a row of FINGERS, and the two rows are
// interdigitated — A-fingers at even pitches, B-fingers at odd. Fold the panels
// about X and adjacent fingers pull the strip in opposite Z directions, so each
// strip segment *between* two fingers TWISTS (torsion) while each finger root
// BENDS. Most of the compliance is torsion of the thin bars — which is what
// makes a LET high-ROM and low-stress where a plain living hinge is neither.
//
// Tune knobs (the doc's LET parameterization): the strip is thin (twists
// easily); add fingers for a softer joint (series) or widen the strip for a
// stiffer one. Everything prints flat, no supports. All dimensions in mm.
//
// NOTE: `demo_fold` rotates panel B for the preview only. The PRINTED part is
// always flat (demo_fold = 0); a folded model is not a printable model.

/* [Panels] */
// Hinge width along the fold line, X (mm)
hinge_w = 56;
// Each panel's depth away from the hinge, Y (mm)
panel_d = 20;
// Sheet thickness, Z — printed flat, so this is the layer-stack height (mm)
sheet_t = 2.0;

/* [LET joint] */
// Finger reach from panel edge to the fold line, Y (mm) — the bending length
finger_reach = 6;
// Number of fingers total (alternating A/B); more = softer joint
fingers = 9;
// Finger width along X (mm)
finger_w = 3.5;
// Torsion-strip width across the fold line, Y (mm) — thin ⇒ twists easily.
// This is the highest-leverage stiffness knob.
strip_w = 2.2;

/* [Preview only] */
// Fold angle for the preview pose (deg). PRINT AT 0.
demo_fold = 0; // [0:5:110]

/* [Quality] */
$fn = 48;

// ---- derived -----------------------------------------------------------
g      = finger_reach;                 // half-gap: fold line at y = 0
pitch  = hinge_w / fingers;
edge_a = -g;                           // panel A inner edge
edge_b =  g;                           // panel B inner edge

module panel_A_2d() {
    translate([0, edge_a - panel_d]) square([hinge_w, panel_d]);
}
module panel_B_2d() {
    translate([0, edge_b]) square([hinge_w, panel_d]);
}

// A-side fingers (tie panel A down to the torsion strip). Even indices.
module fingers_A_2d() {
    for (i = [0 : fingers - 1])
        if (i % 2 == 0) {
            x0 = i * pitch + (pitch - finger_w) / 2;
            translate([x0, edge_a]) square([finger_w, g + strip_w/2]);
        }
}
// B-side fingers (tie panel B up to the torsion strip). Odd indices.
module fingers_B_2d() {
    for (i = [0 : fingers - 1])
        if (i % 2 == 1) {
            x0 = i * pitch + (pitch - finger_w) / 2;
            translate([x0, -strip_w/2]) square([finger_w, g + strip_w/2]);
        }
}
// The torsion strip on the fold line — the member that twists.
module strip_2d() {
    translate([0, -strip_w/2]) square([hinge_w, strip_w]);
}

// Panel A + strip + A-fingers live flat; panel B + B-fingers optionally fold up
// about the fold line (y = 0) for the preview pose. PRINTED part is flat.
module main() {
    assert(strip_w >= 1.2, "torsion strip under 3 perimeters — it will tear");
    assert(finger_reach >= 3, "finger reach too short to bend without cracking");
    assert(pitch > finger_w + 1, "fingers too wide for the pitch — no torsion gap left");

    // fixed group: panel A, the torsion strip, and A's fingers
    linear_extrude(sheet_t) {
        panel_A_2d();
        strip_2d();
        fingers_A_2d();
    }
    // moving group: panel B with its own fingers (folds in the preview only)
    rotate([demo_fold, 0, 0])
        linear_extrude(sheet_t) {
            panel_B_2d();
            fingers_B_2d();
        }
}

main();
