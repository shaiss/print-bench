// bistable-toggle — a fixed-fixed pre-buckled arch that snaps between two
// stable states. Reference design for docs/advanced-techniques.md Domain 1
// (compliant mechanisms) → bistable & constant-force, and CC1.
//
// A fixed–fixed buckled arch has two stable states (bowed up / bowed down)
// separated by a negative-stiffness region: power is needed only to SWITCH, not
// to HOLD. Push the centre nub down past flat and it snaps down and stays; push
// it back up and it snaps up. Switches, latches, valves, closures.
//
// Dimensioned from the doc's two nondimensional constants (the arch is the
// fixed–fixed first mode shape yc(x) = h·(1 − cos(2πx/l))/2):
//   switch force   f_s · l³ / (E·I·h) = 1486.57
//   travel         u_tr / h           = 1.98
// so with span `l`, mid-rise `h`, I = w·t³/12, the centre travels ≈ 1.98·h and
// the switch force follows from l, h, t, w and the material E. The design echoes
// the predicted travel; a coupon measures the real snap force + travel (the two
// numbers the geometry model can't self-verify).
//
// BISTABILITY CONDITION: a fixed–fixed arch is only bistable when the rise is
// tall enough vs the beam thickness (mid_rise/beam_t ≳ 2.3). Asserted below —
// too flat and it just springs back (monostable).
//
// PRINT FLAT. The profile is in XY; the arch snaps in-plane, so bending stress
// runs across the roads within a layer — the #1 flexure rule. All dims in mm.

use <printability.scad>

/* [Arch] */
// Clamped span of the arch, X (mm)  — the "l"
span = 50;
// Mid-rise of the arch, Y (mm) — the "h". Bigger = firmer snap, more travel.
mid_rise = 6;
// Arch beam thickness, Y-ish (mm) — the "t". Thin = easy snap, low stress.
beam_t = 1.6;
// Out-of-plane width = extrude height, Z (mm) — the "w"
width = 9;

/* [Frame & button] */
// Post width at each clamped end, X (mm)
post_w = 6;
// Frame wall thickness (posts + base bar) (mm)
frame_wall = 4;
// Extra clear depth below the arch so it can bow fully down (mm)
under_clear = 6;
// Centre push-nub size [width X, height Y] (mm)
nub = [7, 4];

/* [Quality] */
$fn = 48;

// ---- geometry ----------------------------------------------------------
// fixed–fixed first-mode arch centreline
function yc(x) = mid_rise * (1 - cos(360 * x / span)) / 2;

frame_h = mid_rise + beam_t + under_clear;   // interior depth below the arch
NS = 60;                                      // arch samples

module arch_beam_2d() {
    top = [for (i = [0 : NS]) let (x = span * i / NS) [x, yc(x) + beam_t/2]];
    bot = [for (i = [NS : -1 : 0]) let (x = span * i / NS) [x, yc(x) - beam_t/2]];
    polygon(concat(top, bot));
}

module frame_2d() {
    // left & right posts (the clamps), tops at the beam-root level (y = 0)
    translate([-post_w, -frame_h]) square([post_w, frame_h + beam_t/2]);
    translate([span,    -frame_h]) square([post_w, frame_h + beam_t/2]);
    // base bar tying the posts into one rigid frame
    translate([-post_w, -frame_h]) square([span + 2*post_w, frame_wall]);
}

module toggle_2d() {
    // fillet the concave beam roots (close op) so the clamps aren't crack starters
    offset(r = -0.8) offset(r = 0.8)
    union() {
        frame_2d();
        arch_beam_2d();
        // centre push nub, on top of the apex
        translate([span/2 - nub[0]/2, yc(span/2) - beam_t/2])
            square([nub[0], beam_t + nub[1]]);
    }
}

module main() {
    assert(mid_rise / beam_t >= 2.3,
           "arch too flat to be bistable (mid_rise/beam_t < 2.3) — it would just spring back");
    assert(beam_t >= 1.2, "arch beam under 3 perimeters");
    echo(str("predicted centre travel u_tr ≈ ", 1.98 * mid_rise, " mm"));
    linear_extrude(width) toggle_2d();
}

main();
