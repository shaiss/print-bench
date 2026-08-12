// constant-force-slider — a linear shuttle that moves under ~constant force
// over its stroke, guided by a print-in-place slot and returned by a
// quasi-zero-stiffness (QZS) compliant spring. Advanced (Tier-3) capstone
// reference for docs/advanced-techniques.md.
//
// THE FUSION
//   Domain 1 (compliant → constant-force / QZS): the return spring is a
//     POSITIVE-stiffness V-beam (chevron) in PARALLEL with a NEGATIVE-stiffness
//     pre-buckled ARCH. Over the stroke the arch's negative slope cancels the
//     V-beam's positive slope, so net stiffness ≈ 0 → the force plateaus
//     (constant-force spring). Straight from the doc's constant-force section:
//     "a negative-stiffness element in parallel with a positive one so the
//     slopes cancel over a stroke."
//   Domain 3 (print-in-place kinematics → slides): the shuttle rides a guide
//     SLOT printed in place, with a sliding clearance the printer must keep open
//     (CC3: the sliding faces are vertical walls ⇒ spread-limited `slide_tol`).
//     The QZS spring itself tethers the shuttle (it can't fall out), so the
//     spring is both the force element and the retainer.
//   Domain 2 / CC1: printed FLAT (profile in XY, extruded in Z). Every flexure
//     bends in the layer plane; no overhangs, no supports.
//
// Z-capture note: a flat, Z-uniform print captures the shuttle in X (slot walls)
// and holds it in Y (the spring tether); it is used lying flat. A full T-slot
// (Z-capture) would need a Z-varying rail — a deliberate scope choice, noted so
// the reference is honest.
//
// All dimensions in millimeters.

/* [Frame] */
// Overall frame width, X (mm)
frame_w = 56;
// Overall frame height, Y (mm)
frame_h = 72;
// Frame wall thickness (mm)
frame_wall = 4;
// Guide-block height (the slot region), Y (mm)
guide_len = 30;
// Extrude width, Z (mm)
width = 10;

/* [Shuttle] */
// Shuttle body width, X (mm)
shuttle_w = 16;
// Print-in-place sliding clearance per side (mm) — spread-limited (CC3)
slide_tol = 0.35;
// Push-knob height below the frame (mm)
knob_h = 9;

/* [QZS spring] */
// Stroke the shuttle travels, Y (mm)
stroke = 10;
// V-beam (positive) leg thickness (mm)
vbeam_t = 1.8;
// V-beam apex offset from centre, X (mm) — sets the positive stiffness
vbeam_apex = 12;
// Buckled-arch (negative) beam thickness (mm)
arch_t = 1.4;
// Buckled-arch mid-rise, X (mm) — sets the negative-stiffness magnitude
arch_rise = 6;

/* [Preview only] */
// Push the shuttle in by this fraction of the stroke (0..1). PRINT AT 0.
demo_push = 0; // [0:0.1:1]

/* [Quality] */
$fn = 48;

// ---- derived -----------------------------------------------------------
ch_hw     = shuttle_w/2 + slide_tol;          // guide-slot half width
push_y    = -demo_push * stroke;              // shuttle moves −Y when pushed
sh_top    = guide_len;                        // shuttle top at rest
bar_y     = frame_h - frame_wall;             // top crossbar underside (spring anchor)

// ---------- frame: outer border + guide block with a slot + open spring chamber
module frame_2d() {
    difference() {
        translate([-frame_w/2, 0]) square([frame_w, frame_h]);
        // spring chamber (open): above the guide block, below the top bar
        translate([-frame_w/2 + frame_wall, guide_len])
            square([frame_w - 2*frame_wall, frame_h - guide_len - frame_wall]);
        // guide slot through the bottom block (captures the shuttle in X)
        translate([-ch_hw, -1]) square([2*ch_hw, guide_len + 1.001]);
    }
}

// ---------- shuttle (moving): tongue in the slot + push knob below ----------
module shuttle_2d() {
    translate([0, push_y]) {
        translate([-shuttle_w/2, 0]) square([shuttle_w, guide_len]);
        translate([-shuttle_w/2 + 2, -knob_h]) square([shuttle_w - 4, knob_h + 0.5]);
    }
}

// ---------- QZS spring: V-beam (positive) ∥ buckled arch (negative) ----------
// beams overlap their anchors by `ov` so unions are solid (no kissing edges,
// which export as naked edges / non-watertight).
ov = 1.2;
module beam(p0, p1, t) { hull() { translate(p0) circle(d=t); translate(p1) circle(d=t); } }

module vbeam_2d() {
    y0 = sh_top + push_y - ov;                 // start inside the shuttle
    apex = [vbeam_apex, (sh_top + push_y + bar_y) / 2];
    beam([ shuttle_w/2 - vbeam_t/2, y0], apex, vbeam_t);   // right leg from shuttle top
    beam([-shuttle_w/2 + vbeam_t/2, y0], apex, vbeam_t);   // left leg  from shuttle top
    beam(apex, [0, bar_y + ov], vbeam_t);                   // apex into the fixed top bar
}

module arch_2d() {
    y0 = sh_top + push_y - ov;                 // clamp inside the shuttle
    y1 = bar_y + ov;                            // clamp inside the top bar
    NS = 32;
    // shallow buckled arch bowing −X, clamped at shuttle top and top bar
    left  = [for (i=[0:NS]) let(t=i/NS) [ -arch_rise*sin(180*t) - arch_t/2, y0 + t*(y1 - y0)]];
    right = [for (i=[NS:-1:0]) let(t=i/NS) [ -arch_rise*sin(180*t) + arch_t/2, y0 + t*(y1 - y0)]];
    polygon(concat(left, right));
}

module main() {
    assert(slide_tol >= 0.2, "guide slide clearance too tight to slide");
    assert(arch_rise / arch_t >= 2.3, "arch too flat to give negative stiffness");
    assert(bar_y - sh_top > stroke + 4, "not enough chamber for the spring + stroke");
    echo(str("QZS: positive V-beam ∥ negative arch (rise/t = ", arch_rise/arch_t,
             "); tune arch_rise so its negative slope cancels the V-beam over the stroke"));

    linear_extrude(width) {
        frame_2d();
        shuttle_2d();
        vbeam_2d();
        arch_2d();
    }
}

main();
