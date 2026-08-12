// compliant-gripper — a print-in-place collet grabber that fuses all three
// domains of docs/advanced-techniques.md into one part that comes off the plate
// working. Advanced (Tier-3) reference design.
//
//   Domain 1 (compliant mechanisms): the fingers are slotted flexure cantilevers
//     rooted in a base ring — no pins, no springs, they flex and self-return.
//   Domain 3 (print-in-place kinematics): a captive collar prints already around
//     the fingers, trapped between the base (below) and the fingers' outward cone
//     (above), free to slide — the collet actuator.
//   Domain 2 (designing around supports) / CC1: printed bore-axis vertical, so
//     the fingers are near-vertical walls and the ONLY floating face is the
//     collar underside, caught by the base across a layer-quantized z-gap.
//
// How it grips: the fingers form an OUTWARD cone (widest at the top), so at rest
// the collar sits low and the fingers are relaxed (bore open). Slide the collar
// UP and the cone cams the fingers inward — the bore closes on a rod. Release and
// the flexures spring the fingers back out, pushing the collar down. The collar
// cannot leave: its bore is narrower than the cone's top, and the base stops it
// below. That capture is the whole print-in-place trick, and it needs the CC3
// anisotropy — the collar↔finger gap is a vertical wall gap (spread-limited,
// tight) while the collar↔base float is a roof gap (sag-limited, quantized).
//
// All dimensions in millimeters.

/* [Fingers] */
// Number of collet fingers
fingers = 3;
// Finger zone height above the base (mm)
finger_h = 26;
// Outer radius at the finger roots / base (mm)
ro_base = 7;
// Outer radius at the finger tips — larger ⇒ outward cone the collar cams on (mm)
ro_tip = 10;
// Finger wall thickness, radial (mm)
finger_wall = 3;
// Slot width between fingers (mm)
slot_w = 2.2;
// Unslotted base-ring height that roots the fingers (mm)
root_h = 3;

/* [Collar] */
// Collar height (mm)
collar_h = 7;
// Collar wall thickness (mm)
collar_wall = 3.5;
// Push scallops around the collar for grip
collar_scallops = 6;

/* [Base] */
// Base disc thickness (mm)
base_t = 3;
// Extra base radius past the collar (mm)
base_margin = 3;

/* [Clearances — CC3 anisotropy] */
// Layer height the z gap quantizes to (mm)
layer_h = 0.2;
// Radial gap, collar bore ↔ fingers (mm) — spread-limited, keep tight
xy_tol = 0.35;
// Axial float of the collar above the base, in WHOLE LAYERS — sag-limited
z_layers = 2;

/* [Quality] */
$fn = 96;

// ---- derived -----------------------------------------------------------
z_tol        = z_layers * layer_h;
ri_base      = ro_base - finger_wall;         // grip bore at the roots
ri_tip       = ro_tip  - finger_wall;         // grip bore at the tips
collar_z0    = base_t + z_tol;                // collar floats above the base
// finger outer radius at absolute height z
function ro_at(z) = ro_base + (ro_tip - ro_base) * (z - base_t) / finger_h;
// The collar bore is cylindrical, so it must clear the WIDEST fingers it spans
// at rest — the fingers at the collar's TOP (the cone flares upward). Then
// sliding the collar up closes the gap uniformly (the cam). Looser at the
// bottom, just-clear at the top: exactly a collet nut at rest.
collar_ir    = ro_at(collar_z0 + collar_h) + xy_tol;
collar_or    = collar_ir + collar_wall;
base_r       = collar_or + base_margin;

module base_disc() {
    cylinder(r = base_r, h = base_t);
}

// The slotted flexure fingers as an outward cone shell, rooted in a solid ring.
module finger_cone() {
    translate([0, 0, base_t - 0.01])
    difference() {
        // cone shell
        difference() {
            cylinder(r1 = ro_base, r2 = ro_tip, h = finger_h);
            translate([0, 0, -0.02])
                cylinder(r1 = ri_base, r2 = ri_tip, h = finger_h + 0.04);
        }
        // slots (start above the root ring so the fingers stay rooted)
        for (i = [0 : fingers - 1])
            rotate([0, 0, i * 360 / fingers + 180 / fingers])
                translate([0, 0, root_h])
                    linear_extrude(finger_h)
                        translate([-slot_w/2, 0]) square([slot_w, ro_tip + 1]);
    }
}

// The captive collar: a scalloped ring floating around the finger roots.
module collar() {
    translate([0, 0, collar_z0])
        difference() {
            cylinder(r = collar_or, h = collar_h);
            translate([0, 0, -0.01])
                cylinder(r = collar_ir, h = collar_h + 0.02);
            for (i = [0 : collar_scallops - 1])
                rotate([0, 0, i * 360 / collar_scallops])
                    translate([collar_or, 0, -0.01])
                        cylinder(r = 2.2, h = collar_h + 0.02);
        }
}

module main() {
    assert(ro_tip > collar_ir,
           "cone top not wider than the collar bore — the collar would slide off (not captive)");
    assert(ri_tip > 1.5, "grip bore collapses at the tips");
    assert(collar_z0 + collar_h < base_t + finger_h,
           "collar taller than the finger zone");
    base_disc();
    finger_cone();
    collar();
}

main();
