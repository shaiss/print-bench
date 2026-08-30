// let-folding-panel — two panels joined by a Lamina-Emergent Torsional (LET)
// joint: a compliant hinge fabricated FLAT from a single sheet that folds up
// to ~90°. Reference design for docs/advanced-techniques.md Domain 1
// (compliant mechanisms), the lamina-emergent family — "the best FDM match"
// per the doc — and CC1 (orientation): it is flat by nature, so the flex is in
// the layer plane by construction.
//
// How a LET works, and how this models it. The fold line runs along X at y = 0.
// A thin TORSION BAR lies on that line, split half into each panel's group.
// Each panel reaches the bar only through a row of FINGERS, and the two rows
// are interdigitated — A-fingers at even pitches, B-fingers at odd. Fold the
// panels about X and adjacent fingers pull the bar in opposite Z directions, so
// each bar segment *between* two fingers TWISTS (torsion) — most of the
// compliance, which is what makes a LET high-ROM where a plain living hinge
// would crack. The parameterization below is the doc's: t (dominant, t^3),
// free span L, bar width w, root fillet r >= 0.5*t, target angle theta_max;
// main() echoes the predicted joint stiffness K and the root stress numbers.
//
// The hinge zone (bar + fingers) is printed THIN (t) while the panels stay at
// panel_t, so the compliance is concentrated in the joint, not the panels.
// Every finger root carries an in-plane fillet r (the doc's stress-rule),
// realised as a morphological closing on the hinge silhouette. Everything
// prints flat, no supports. All dimensions in millimeters.
//
// NOTE: `demo_fold` rotates panel B's group for the preview only. The PRINTED
// part is always flat (demo_fold = 0); a folded model is not a printable model.

/* [Panels] */
// Panel width along the fold line, X (mm)
hinge_w = 70;
// Each panel's depth away from the hinge, Y (mm)
panel_d = 45;
// Panel sheet thickness, Z (mm) — the rigid members; only the hinge zone is thin
panel_t = 3.0;

/* [LET joint — the doc's knobs] */
// Torsion-bar thickness, Z (mm) — THE dominant knob (stiffness ~ t^3). Floor
// 0.8 = repo minimum feature (2 extrusion widths at 0.4 nozzle).
t = 1.2;
// Free torsion span between adjacent finger attachments, X (mm) — longer bar
// twists at lower strain; with w this sets the fold-life trade.
L = 14;
// Torsion-bar width across the fold line, Y (mm)
w = 2.0;
// Root fillet at every finger↔bar junction (mm) — doc rule: r >= 0.5*t
r = 0.8;
// Target fold angle (deg) — what the echoed predictions are quoted at
theta_max = 90;
// Total interdigitated fingers (alternating A/B, so keep >= 3)
fingers = 4;
// Finger width along X (mm)
finger_w = 3.5;
// Finger run from panel edge across the fold line, Y (mm)
finger_reach = 6;

/* [Preview only] */
// Fold angle for the preview pose (deg). PRINT AT 0.
demo_fold = 0; // [0:5:110]

/* [Quality] */
$fn = 48;

// ---- derived -----------------------------------------------------------
// pitch is built FROM L so the free span is exactly the L you set (a realized
// dimension, not a nominal one); the bar spans fingers*pitch, flush with the
// panels at the defaults.
pitch     = finger_w + L;
strip_len = fingers * pitch;
g         = finger_reach;      // panel inner edges sit at y = ∓g
n_spans   = fingers - 1;       // torsion spans, all twisted by the fold angle

// morphological closing: rounds every concave (root) corner with radius r,
// leaves convex corners and the silhouette otherwise untouched.
module rooted_2d() {
    offset(r = -r) offset(r = r) children();
}

module panel_A_2d() {
    translate([0, -g - panel_d]) square([hinge_w, panel_d]);
}
module panel_B_2d() {
    translate([0, g]) square([hinge_w, panel_d]);
}

// A-side hinge silhouette: the near half of the torsion bar plus A's fingers
// (even slots), each embedded 1 mm into its panel for a robust union.
module hinge_A_2d() {
    rooted_2d() {
        translate([0, -w / 2]) square([strip_len, w / 2]);
        for (i = [0 : fingers - 1])
            if (i % 2 == 0) {
                x0 = i * pitch + (pitch - finger_w) / 2;
                translate([x0, -g - 1]) square([finger_w, g + 1 + w / 2]);
            }
    }
}
// B-side hinge silhouette: the far half of the bar plus B's fingers (odd
// slots), likewise embedded. Both halves carry their own root fillets, so the
// joint is symmetric in stress as well as in shape.
module hinge_B_2d() {
    rooted_2d() {
        translate([0, 0]) square([strip_len, w / 2]);
        for (i = [0 : fingers - 1])
            if (i % 2 == 1) {
                x0 = i * pitch + (pitch - finger_w) / 2;
                translate([x0, -w / 2]) square([finger_w, w / 2 + g + 1]);
            }
    }
}

// Predictions per the doc's governing relations — calibration starting points
// for the coupon, never a guarantee (that is what the coupon is for).
module echo_predictions() {
    E  = 2000;                  // PETG modulus, MPa (assumed — see NOTES.md)
    nu = 0.4;
    Gs = E / (2 * (1 + nu));    // shear modulus, MPa
    th = theta_max * PI / 180;  // rad
    // St-Venant torsion constant of the w × t rectangular bar, mm^4
    J  = w * t^3 / 3 * (1 - 0.63 * (t / w) + 0.052 * (t / w)^5);
    K_bar = Gs * J / L;               // N·mm/rad — one span
    K_tot = n_spans * K_bar;          // spans act in parallel across X
    L_bend = g - w / 2;               // finger-root bending length, mm
    sigma  = E * t * th / (2 * L_bend);  // doc: sigma ~ E·t·θ / (2L), MPa
    r_c = sqrt((w / 2)^2 + (t / 2)^2);   // corner fiber distance from the axis
    tau = Gs * th * r_c / L;            // torsion surface shear, MPa
    echo(str("LET predictions @ theta_max=", theta_max, "deg (E=", E,
             " MPa assumed): K_joint = ", K_tot, " N·mm/rad (", n_spans,
             " spans x ", K_bar, "), sigma_root = ", sigma,
             " MPa (doc upper bound if a root took the full fold), tau_bar = ",
             tau, " MPa (the design stress here — torsion dominates).",
             " Coupon arbitrates; these are starting points."));
}

module main() {
    assert(t >= 0.8, "torsion bar under the 0.8 mm minimum feature");
    assert(r >= 0.5 * t, "root fillet violates the doc rule r >= 0.5*t");
    assert(w >= 1.2, "torsion bar under 3 perimeters — it will tear");
    assert(L > 2 * r, "no free torsion span left after the root fillets");
    assert(fingers >= 3, "a LET needs at least 2 fingers on one side");
    assert(g > w / 2 + 2, "fingers too short to bridge the panels");
    echo_predictions();

    // fixed group: panel A and its half of the bar + A's fingers, all flat
    linear_extrude(panel_t) panel_A_2d();
    linear_extrude(t) hinge_A_2d();

    // moving group: panel B, its half-bar and its fingers, folded for preview
    rotate([demo_fold, 0, 0]) {
        linear_extrude(panel_t) panel_B_2d();
        linear_extrude(t) hinge_B_2d();
    }
}

main();
