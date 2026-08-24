// captive-spinner — a print-in-place fidget spinner: a rotor ring captured on a
// fixed post and cap, printed as ONE piece, that spins after a break-free first
// motion. Reference design for docs/advanced-techniques.md Domain 3
// (print-in-place kinematics), and the cross-cutting moves CC3 (derive
// clearance from process constants — and split xy from z) and CC2 (the
// break-free first motion is a deliberate weak fusion you shear). Built to the
// brief (#387): post Ø20, ring OD 32 × 10 wide.
//
// Prints in place, no supports, no assembly. The whole discipline in one part:
// "engineer a gap the printer wants to close but must not, then trap geometry
// across it so it is captive but free."
//
// THE ANISOTROPY LESSON (CC3). There are two different gaps here and they are
// NOT the same number:
//   - RADIAL (rotor bore ↔ post): a vertical wall-to-wall gap. Spread-limited,
//     so it can be tight — xy_tol = k_xy · line_w (doc §Clearance theory).
//   - AXIAL (rotor ↔ base below, rotor ↔ cap above): a roof/floor-over-part
//     gap. Sag-limited, so it must be looser AND snapped to whole layers —
//     z_tol = z_layers · layer_h, so the gap's floor and roof land on real
//     layer boundaries.
// A single global tolerance is the classic print-in-place bug; this design
// keeps them separate on purpose.
//
// The cap is a 45° cone widening upward (a countersunk-head shape) so its
// capturing overhang self-supports — a locking overhang printed as a ≤45° lip,
// the doc's captive-joint primitive. All dimensions in millimeters.

/* [Rotor] */
// Rotor outer radius (mm) — brief: ring OD 32
rotor_or = 16;
// Rotor height (mm) — brief: ring width 10
rotor_h = 10;
// Number of finger scallops around the rim (grip)
scallops = 6;
// Scallop radius (mm)
scallop_r = 3.5;

/* [Post & cap] */
// Fixed centre post radius (mm) — brief: post Ø20
post_r = 10;
// Capture lip: how far the cap overhangs past the rotor bore (mm)
cap_lip = 3;

/* [Base] */
// Base disc radius (mm)
base_r = 22;
// Base thickness (mm)
base_t = 3;

/* [Process constants — the CC3 derivation] */
// Nozzle diameter (mm)
nozzle_d = 0.4;
// Extruded line width (mm) — doc: line_w ≈ 1.1–1.2 × nozzle_d
line_w = 1.15 * nozzle_d;
// XY clearance factor — doc: k_xy ≈ 0.4–0.6 (spread-limited)
k_xy = 0.45;
// Layer height the axial gap is quantized to (mm)
layer_h = 0.2;
// Axial float in WHOLE LAYERS (sag-limited; rotor floats this above the base
// and this below the cap)
z_layers = 2;

/* [Quality] */
// Iterating: 64. Production: 128 (a captive bore is $fn-sensitive).
$fn = 96;

// ---- derived -----------------------------------------------------------
// Radial gap, DERIVED from process constants (never a bare number): with the
// defaults, 0.45 × 0.46 ≈ 0.21 mm — inside the doc's 0.15–0.25 spread window.
xy_tol     = k_xy * line_w;
z_tol      = z_layers * layer_h;         // axial gap, integer layers
rotor_ir   = post_r + xy_tol;            // rotor bore (radial gap)
z0         = base_t + z_tol;             // rotor floats z_tol above the base
rotor_top  = z0 + rotor_h;
r_cap      = rotor_ir + cap_lip;         // cap must exceed the bore to capture
cone_h     = r_cap - post_r;             // 45° cone
// Cone base sits so the gap directly over the rotor's bore edge is exactly
// z_tol: at radius rotor_ir the cone begins z_tol above the rotor top.
z_cone0    = rotor_top + z_tol - xy_tol;

module base() {
    cylinder(r = base_r, h = base_t);
}

module post_and_cap() {
    // straight post through the rotor bore, merged into the base
    cylinder(r = post_r, h = z_cone0 + 0.01);
    // 45° capture cone (self-supporting locking overhang)
    translate([0, 0, z_cone0])
        cylinder(r1 = post_r, r2 = r_cap, h = cone_h);
}

module rotor(ir = rotor_ir) {
    translate([0, 0, z0])
        difference() {
            cylinder(r = rotor_or, h = rotor_h);
            // bore (radial gap around the post)
            translate([0, 0, -0.01])
                cylinder(r = ir, h = rotor_h + 0.02);
            // finger scallops around the rim
            for (i = [0 : scallops - 1])
                rotate([0, 0, i * 360 / scallops])
                    translate([rotor_or, 0, -0.01])
                        cylinder(r = scallop_r, h = rotor_h + 0.02);
        }
}

module fixed() { base(); post_and_cap(); }

// "" = the spinner. "fitcheck" = rotor ∩ fixed (must be EMPTY — the rotor is a
// free captive body). "fitcheck_neg" = the rotor with its bore shrunk onto the
// post (must be NON-EMPTY — proves the check can fail). "fused" = the whole
// assembled spinner with the bore shrunk onto the post (the KNOWN-FUSED pose
// for ci.fusecheck's control: it welds into one body). See ci.fitchecks and
// ci.fusecheck.
part = "";

module main() {
    assert(xy_tol >= 0.15, "radial gap below the spread-limited floor (0.15 mm)");
    assert(z_layers >= 1, "axial gap must be at least one whole layer");
    assert(cap_lip >= 1.5, "capture lip too small — the rotor could pop off");
    assert(r_cap < rotor_or, "cap wider than the rotor — nothing to grip");

    if (part == "fitcheck")
        intersection() { rotor(); fixed(); }
    else if (part == "fitcheck_neg")
        intersection() { rotor(ir = post_r - 0.4); fixed(); }   // bore bites the post
    else if (part == "fused")
        { fixed(); rotor(ir = post_r - 0.4); }                  // welded on purpose
    else {
        fixed();
        rotor();
    }
}

main();
