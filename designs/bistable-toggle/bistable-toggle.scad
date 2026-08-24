// bistable-toggle — a fixed–fixed pre-buckled arch that snaps between two
// stable states. Reference design for docs/advanced-techniques.md Domain 1
// (compliant mechanisms) → bistable & constant-force, and CC1.
//
// A fixed–fixed buckled arch has two stable states (bowed up / bowed down)
// separated by a negative-stiffness region: power is needed only to SWITCH, not
// to HOLD. Push the centre nub down past flat and it snaps down and stays; push
// it back up and it snaps up. Switches, latches, valves, closures.
//
// DIMENSIONED FROM TARGETS (issue #389), not by feel. Pick the switch force
// f_s and travel u_tr, then invert the doc's two nondimensional constants
// (fixed–fixed shallow arch, I = w·t³/12):
//   switch force   f_s · l³ / (E·I·h) = 1486.57
//   travel         u_tr / h           = 1.98
// Defaults f_s = 3 N, u_tr = 4 mm, E = 2 GPa (PETG datum) give
//   h = u_tr/1.98 = 2.02 mm               (mid_rise, derived below)
//   t = 0.82 mm — bistability needs h/t ≥ 2.3, capping t at 0.878 mm, and the
//        repo floor is 0.8 (two perimeters): the window is [0.8, 0.878], and
//        0.82 sits a hair above the floor so the curved band's normal-ray
//        wall samples clear the 0.8 mm thin-wall check
//   l = (1486.57·E·I·h/f_s)^(1/3) ≈ 82 mm (span, derived below)
// main() re-derives f_s and u_tr from the built parameters and echoes them, so
// the solve cannot silently drift; NOTES.md "The solve" records the chain.
//
// BISTABILITY CONDITION: a fixed–fixed arch is only bistable when the rise is
// tall enough vs the beam thickness (mid_rise/beam_t ≳ 2.3). Asserted below —
// too flat and it just springs back (monostable). The coupon (part = "sweep")
// prints four cells across that threshold, two deliberately monostable, so you
// can feel where bistability dies on your printer.
//
// HARD STOPS (the doc's fatigue rule: the real limit is off-axis overload, not
// primary-DOF motion): the nub travels in a rigid cage — the lid above limits
// +Y over-travel, the base bar below limits −Y, and two rails hanging from the
// lid flank the raised nub to limit ±X shoves. The rails stop `stop_gap` above
// the arch's maximum reach: the arch sweeps through every interior x between
// states, so a stop reaching any lower would weld the mechanism solid. Z
// (out-of-plane) is left to geometry: that axis is (w/t)² ≈ 56× stiffer than
// the flexure axis. The `fitcheck` part proves the cage clears the arch's and
// nub's FULL travel; `fitcheck_neg` proves that check can fail.
//
// PRINT FLAT. The profile is in XY; the arch snaps in-plane, so bending stress
// runs across the roads within a layer — the #1 flexure rule. The stop cage
// too is pure profile: every feature prints face-down on the bed, no bridges,
// no supports. All dims in mm.

/* [Targets — the geometry solves from these] */
// Target switch force f_s (N) — finger-comfortable toggle (brief #389)
target_fs = 3;
// Target centre travel u_tr (mm) — a positive, feelable click
target_utr = 4;
// Young's modulus (MPa). PETG ≈ 2000 — the datum the force solve uses; the
// echoed f_s is a prediction to verify with the coupon, not a guarantee.
E = 2000;

/* [Arch] */
// Mid-rise h (mm) — derived: u_tr / 1.98. Bigger = firmer snap, more travel.
mid_rise = target_utr / 1.98;
// Arch beam thickness t (mm) — bistability (h/t ≥ 2.3) caps it at 0.878 and
// the repo's two-perimeter floor is 0.8; 0.82 sits just off the floor so the
// curved band's normal-ray wall samples clear the 0.8 mm thin-wall check.
beam_t = 0.82;
// Out-of-plane width w (mm) = extrude height Z. Brief floor: w ≥ 3.
width = 6;
// Clamped span l (mm) — derived from target_fs: cbrt(1486.57·E·I·h/f_s)
span = pow(1486.57 * E * (width * pow(beam_t, 3) / 12) * mid_rise / target_fs, 1 / 3);

/* [Frame & stops] */
// Post width at each clamped end, X (mm)
post_w = 6;
// Frame wall thickness (posts, base bar, lid) (mm)
frame_wall = 4;
// Stock thickness of the ±X stop rails (mm)
rail_w = 3;
// Travel past the stable state / off-axis rest before a hard stop bites (mm)
stop_gap = 0.4;
// Centre push-nub size [width X, height Y above the arch] (mm)
nub = [7, 4];

/* [Quality] */
$fn = 48;

// ---- derived predictions (echoed; the asserts hold them to the targets) ----
fs_pred = 1486.57 * E * (width * pow(beam_t, 3) / 12) * mid_rise / pow(span, 3);
NS = 60;                                      // arch samples

// ---- geometry (all 2D in the XY profile; `width` is the extrusion) --------
// fixed–fixed first-mode arch centreline
function yc(x, l, h) = h * (1 - cos(360 * x / l)) / 2;

module arch_beam_2d(l, h, t) {
    top = [for (i = [0 : NS]) let (x = l * i / NS) [x, yc(x, l, h) + t/2]];
    bot = [for (i = [NS : -1 : 0]) let (x = l * i / NS) [x, yc(x, l, h) - t/2]];
    polygon(concat(top, bot));
}

module nub_2d(l, h, t) {
    translate([l/2 - nub[0]/2, h - t/2]) square([nub[0], t + nub[1]]);
}

module beam_gussets_2d(l, h, t) {
    // flexure-root fillets, r = 0.5t (the doc's minimum). Each disc sits
    // `bite` PAST the faces it joins, never tangent to them: a tangent-only
    // disc touches the union at a single point, pinching the polygon and
    // leaving naked edges in the mesh (the coupon render failure that bit this
    // module before `bite`). 0.06 mm is ~200× the $fn=48 arc error, so the
    // fillet still reads as tangent.
    rf = t / 2;
    bite = 0.06;
    // roots: the concave notch where the beam underside leaves each post face
    for (gx = [rf - bite, l - rf + bite])
        translate([gx, -t/2 - rf + bite]) circle(rf);
    // nub base: the corner where each nub side rises off the beam top
    for (sx = [-1, 1])
        let (fx = l/2 + sx * nub[0]/2)
            translate([fx + sx * (rf - bite), yc(fx, l, h) + t/2 + rf - bite])
                circle(rf);
}

function base_top(h, t) = -(h + t/2 + stop_gap);   // the −Y hard-stop face
function lid_bottom(h, t) = h + t/2 + nub[1] + stop_gap;  // the +Y hard-stop face

module frame_2d(l, h, t) {
    y0 = base_top(h, t) - frame_wall;
    y1 = lid_bottom(h, t) + frame_wall;
    // posts (the clamps), full height to the lid
    translate([-post_w, y0]) square([post_w, y1 - y0]);
    translate([l, y0]) square([post_w, y1 - y0]);
    // base bar (−Y over-travel stop) and lid (+Y over-travel stop)
    translate([-post_w, y0]) square([l + 2*post_w, frame_wall]);
    translate([-post_w, lid_bottom(h, t)]) square([l + 2*post_w, frame_wall]);
}

module x_rails_2d(l, h, t) {
    // ±X stop rails, hanging from the lid: they flank the raised nub so a
    // sideways shove cannot walk it off its line, and stop `stop_gap` above
    // the arch's maximum reach (h + t/2) — the arch sweeps through every
    // interior x between states, so a rail any lower would weld the mechanism.
    // The inner face clears the nub's gusset bumps, not the bare nub face: a
    // disc-union gusset protrudes 2·rf past the face (a true tangent fillet
    // would protrude rf), i.e. t − bite in practice — rails at bare-nub +
    // stop_gap sat exactly on the bump crests and fused the mechanism solid
    // (the bodies:1 weld caught at iteration 2)
    inner = nub[0]/2 + t + stop_gap;            // rail inner face off centre
    for (x0 = [l/2 - inner - rail_w, l/2 + inner])
        translate([x0, h + t/2 + stop_gap])
            square([rail_w, lid_bottom(h, t) - (h + t/2 + stop_gap)]);
}

module cage_2d(l, h, t) {
    frame_2d(l, h, t);
    x_rails_2d(l, h, t);
}

module toggle_2d(l, h, t) {
    // close-op rounds the cage's concave corners (r kept under t/2 so the thin
    // beam would survive the inward offset were it in this group); the beam
    // gets its own explicit 0.5t root fillets instead
    offset(r = -0.3) offset(r = 0.3) cage_2d(l, h, t);
    union() {
        arch_beam_2d(l, h, t);
        nub_2d(l, h, t);
        beam_gussets_2d(l, h, t);
    }
}

module toggle(l, h, t, w) {
    linear_extrude(w) toggle_2d(l, h, t);
}

// the nub's full designed Y travel, grown by `m` — including its gusset
// bumps, which reach (t − bite) past each nub face: the sweep must model the
// solid that actually moves, or a stop sitting on a bump crest reads clear
// here while the printed part is fused (the iteration-2 lesson)
module nub_sweep_2d(l, h, t, m = 0) {
    xh = nub[0]/2 + t + m;                      // half-extent incl. gussets
    translate([l/2 - xh, -(h + t/2) - m])
        square([2 * xh, 2*(h + t/2) + nub[1] + 2*m]);
}

// everything that moves — the arch band mirrored through the snap (state 2 is
// state 1 reflected about the chord) plus the nub riding the apex — grown by
// `m`. What the cage must clear; `m > 0` is the negative control's overlap.
module travel_sweep_2d(l, h, t, m = 0) {
    nub_sweep_2d(l, h, t, m);
    polygon(concat(
        [for (i = [0 : NS]) let (x = l * i / NS) [x,  yc(x, l, h) + t/2 + m]],
        [for (i = [NS : -1 : 0]) let (x = l * i / NS) [x, -yc(x, l, h) - t/2 - m]]));
}

// ---- the coupon: h/t swept across the bistability threshold ---------------
// Four cells at l = 35 (quick print), t = 0.82 = production. Ratios 3.0 and
// 2.53 (production) are bistable; 2.0 and 1.5 are deliberately monostable —
// the negative controls. Feel the snap die as h shrinks; the label on each
// base bar is its mid_rise/beam_t ratio.
sweep_l = 35;
sweep_cells = [               // [label, h]: cell 2 IS the production mid_rise
    // no "0" glyphs in the labels — a 0's enclosed counter cuts loose as a
    // floating chip in the bar (found as 2 stray 17 mm³ shells at iteration 3)
    ["3", 3.0 * beam_t], ["2.5", mid_rise], ["2", 2.0 * beam_t], ["1.5", 1.5 * beam_t],
];

module coupon_strip() {
    for (i = [0 : len(sweep_cells) - 1]) {
        h = sweep_cells[i][1];
        cell_w = sweep_l + 2*post_w;
        translate([i * (cell_w + 3), 0, 0])
            linear_extrude(width)
            difference() {
                toggle_2d(sweep_l, h, beam_t);
                // baseline 1.1 above the bar's bottom edge (the period glyph
                // dips ~0.28 below the baseline — the bar strip under it must
                // stay ≥ 0.8 mm), spacing 1.5 because the period kerns tight
                // against the next digit and left a ~0.04 mm wall in the gap
                // (the iteration-4/5 warnings)
                translate([sweep_l/2, base_top(h, beam_t) - frame_wall + 1.1])
                    text(sweep_cells[i][0], size = 3.2, halign = "center", spacing = 1.5);
            }
    }
}

// "" = the toggle. "sweep" = the print-this-first coupon. "fitcheck" = the
// mechanism's full travel (arch through both states + nub) ∩ the stop cage
// (must be EMPTY — the cage bites only on over-travel/off-axis load, and this
// is the check that catches a stop placed where the arch sweeps). "fitcheck_
// neg" = that travel grown past the stops (must be NON-EMPTY — proves the
// check can fail). See ci.fitchecks.
part = "";

module main() {
    assert(mid_rise / beam_t >= 2.3,
           "arch too flat to be bistable (mid_rise/beam_t < 2.3) — it would just spring back");
    assert(beam_t >= 0.8, "arch beam under the two-perimeter floor (0.8 mm)");
    assert(width >= 3, "out-of-plane width under the brief's 3 mm floor");
    assert(span / mid_rise >= 10,
           "arch not shallow enough for the fixed–fixed constants (l/h < 10)");
    assert(abs(fs_pred - target_fs) < 0.05,
           str("solve drifted: echoed f_s = ", fs_pred, " N vs target ", target_fs, " N"));
    echo(str("predicted switch force f_s ≈ ", fs_pred, " N  (target ", target_fs, " N)"));
    echo(str("predicted centre travel u_tr ≈ ", 1.98 * mid_rise, " mm  (target ", target_utr, " mm)"));

    if (part == "sweep")
        coupon_strip();
    else if (part == "fitcheck")
        linear_extrude(width)
            intersection() { cage_2d(span, mid_rise, beam_t); travel_sweep_2d(span, mid_rise, beam_t); }
    else if (part == "fitcheck_neg")
        linear_extrude(width)
            intersection() { cage_2d(span, mid_rise, beam_t); travel_sweep_2d(span, mid_rise, beam_t, stop_gap + 0.3); }
    else
        toggle(span, mid_rise, beam_t, width);
}

main();
