// czs-slider — a print-in-place captive slider whose resistive force is
// near-constant across its stroke: a quasi-zero-stiffness (QZS) mechanism.
// Reference design for docs/advanced-techniques.md Domain 1 (bistable &
// constant-force) fused with Domain 3 (print-in-place kinematics), per brief
// #393 (child of the reference-design catalog #204, Tier 3 "advanced").
//
// THE MECHANISM (D1+D3 fusion, both elements between the same two rigid
// bodies — the slider and the frame — i.e. genuinely in parallel):
//   NEGATIVE stiffness — a fixed-fixed pre-buckled ARCH, chord along the
//     stroke axis, rise transverse. Advancing the slider shortens the chord
//     and drives the arch through its snap: over the snap its force FALLS,
//     which is negative slope. Dimensioned by the same two nondimensional
//     constants as designs/bistable-toggle (#389, the landed solve):
//       switch force   f_s * l^3 / (E*I*h) = 1486.57      (I = w*t^3/12)
//       travel         u_tr / h            = 1.98
//   POSITIVE stiffness — a V-BEAM (chevron) spanning the same two anchors,
//     apex offset transverse. Shortening its span bends its legs: positive
//     slope, k_v = E*w*t_v^3*sin^2(theta)/L^3 to first order (theta = the
//     leg's angle off the stroke axis; a stated model, not an exactness).
//   The slopes cancel over the working range => net stiffness ~ 0 => the
//   slider glides at ~constant force instead of fighting a rising spring.
//
// THE SOLVE (from the brief's targets, not by feel — every number below is
// derived; NOTES.md "The solve" records the chain and the predicted curve):
//   stroke 20 mm, flat zone = middle 70% = u in [3, 17] (14 mm)
//   arch snap travel  u_tr = 16 mm        -> h = u_tr/1.98 = 8.081 mm
//   arch thickness    t    = 0.82 mm      (bistability h/t >= 2.3 caps t at
//                                          3.51; 0.82 = the #389 production
//                                          thickness, proven against the 0.8
//                                          thin-wall floor on a curved band)
//   arch width        w    = 6 mm         (the #389 floor w >= 3, taken at
//                                          the same value as that solve)
//   arch switch force f_s  = 2.4 N        (chosen small so the slope match
//                                          is tolerant — NOTES.md ripple para)
//     -> span l = cbrt(1486.57*E*I*h/f_s) = 140.26 mm   (l/h = 17.4, shallow)
//   arch mean slope   k_a  = -2*f_s/u_tr  = -0.30 N/mm  (linear idealization:
//     the force falls from +f_s to -f_s between the limit points, the
//     zero-net-energy signature of a symmetric bistable)
//   V-beam sized so k_v straddles k_a across the flat zone: apex offset 50 mm
//     at the relaxed pose, t_v = 3.34 mm, sized by k_v(3)+k_v(17) = 2*|k_a| —
//     matched at the flat-zone ENDS so the chevron's geometric stiffening
//     straddles the target instead of drifting past it (k_v(10) = 0.301 vs
//     |k_a| = 0.300). A mid-stroke-only match leaves the second half of the
//     plateau rising ~+70% of target slope; NOTES.md shows both curves.
//   working point: the V-beam's relaxed geometry sits at u_free = 4.33 mm,
//     which sets the plateau level to the brief's ~2 N:
//     F_flat = f_s + k_v*(u_a - u_free) ~= 2.0 N
//   Predicted curve (linearized two-element model, u = 3..17 mm):
//     2.06 1.97 1.92 1.90 1.89 1.90 1.93 1.99 2.07 N — mean 1.97 N, ripple
//     +-5% on the model. No digital gate can measure force: the coupon finds
//     the real plateau, a FIELD-TEST entry verifies it (NOTES.md).
//
// THE SLIDE (D3, per designs/captive-spinner #387 — clearances derived from
// process constants, and xy and z are DIFFERENT numbers because different
// processes limit them):
//   radial/xy gap (slider flanks vs channel walls — vertical wall-to-wall,
//     spread-limited):      k_xy * line_w = 0.45 * (1.15*0.4) = 0.207 mm
//   axial/z gap  (slider top vs the capture deck — a roof over a moving
//     part, sag-limited):   z_layers * layer_h = 2 * 0.2 = 0.4 mm, whole
//     layers so the gap's floor and roof land on layer boundaries
// The slider rides ON the bed (its underside is first layers — no gap below
// to weld) and is trapped in Z by the deck, in X by the channel walls, in Y
// by the two body stops — the back wall standing stop_clear = 1 mm behind
// the rest face, so in the PRINTED POSE nothing touches but the designed
// spring welds (a zero-gap stop face prints as a seam and welds shut). The
// knob pokes up through a slot in the deck (same
// xy gap) — that is the push/pull affordance; both slot ends sit exactly one
// xy gap beyond the travel, so they can only ever act as Y-capture backups,
// never as the working stops (the #389 stem_clear ordering).
//
// HARD STOPS (the doc's fatigue rule: the real limit is off-axis overload,
// not primary-DOF motion): -Y the back wall's face; +Y the slider shoulder
// vs the stop bar (windowed for the tongue — its jambs are the stop face);
// +-X the channel walls in the slot and, in the chamber, the chamber walls
// placed sweep_clear = 0.6 mm beyond the arch's full snap sweep (band
// mirrored through the chord) and the V-beam's fullest apex; +Z the deck.
// The `fitcheck` part proves the cage clears EVERYTHING that moves across
// the full stroke and the full snap; `fitcheck_neg` proves it can fail.
//
// PRINT FLAT. The profile is in XY, extruded in Z; the arch and the V-beam
// legs are vertical bands standing on the bed along their whole curve, so
// every flexure bends in the layer plane — the #1 flexure rule. No supports;
// the one bridge is the capture deck over the 10.4 mm channel (sag into the
// 0.4 mm roof gap is the budget the z-gap derivation already charges for;
// the coupon's fit cells verify it on your printer). All dims in mm.
// Bed: ~201 x 93 mm — needs a 220 mm class bed (NOTES.md "Bed").

/* [Targets — the geometry solves from these] */
// Plateau force across the flat zone (N) — the brief's "~2 N, feelable"
target_force = 2.0;
// Stroke (mm) — full travel of the slider
stroke = 20;
// Fraction of the stroke the plateau must span (middle of the travel)
flat_frac = 0.70;
// Young's modulus (MPa). PETG ~= 2000 — the datum the force solve uses; the
// echoed forces are predictions to verify with the coupon, not guarantees.
E = 2000;

/* [Arch — the negative-stiffness element, per the #389 solve] */
// Snap travel u_tr (mm) — derived: covers the flat zone with 1 mm shoulders
u_tr = stroke * flat_frac + 2;             // 16
// Mid-rise h (mm) — derived: u_tr / 1.98
mid_rise = u_tr / 1.98;                    // 8.081
// Band thickness t (mm) — see header; 0.82 clears the 0.8 floor on curves
beam_t = 0.82;
// Out-of-plane width w (mm) = slider height in Z (both flexures, one band)
width = 6;
// Switch force f_s (N) — chosen small so the slope match is tolerant
target_fs = 2.4;
// Clamped span l (mm) — derived from target_fs: cbrt(1486.57*E*I*h/f_s)
span = pow(1486.57 * E * (width * pow(beam_t, 3) / 12) * mid_rise / target_fs, 1 / 3);
// Arch centreline X (mm) — the line the chord runs on, left of centre
x_arch = -12;
// Where the snap starts (mm into the stroke) — derived: flat-zone start
u_engage = (1 - flat_frac) / 2 * stroke;   // 3

/* [V-beam — the positive-stiffness element] */
// Anchor line X (mm) — right of centre, clear of the arch's sweep
x_vbeam = 2;
// Apex offset at the relaxed pose (mm) — steep enough that the chevron's
// geometric stiffening stays gentle across the stroke (NOTES.md ripple para)
v_apex0 = 50;
// Leg thickness (mm) — slope-matched at the flat-zone ends (see header)
v_t = 3.34;

/* [Slide — process constants per #387, split xy from z] */
// Nozzle diameter (mm)
nozzle_d = 0.4;
// Extruded line width (mm)
line_w = 1.15 * nozzle_d;
// Spread factor on the xy gap — THE tuning knob (coupon sweeps it)
k_xy = 0.45;
// Whole layers of roof gap (integer; sag budget for the capture deck)
z_layers = 2;
// Layer height (mm)
layer_h = 0.2;

/* [Slider & frame] */
// Slider body half-width (mm) — sets the channel; 10 mm keeps the deck's
// bridge at 10.4 mm (routine for a slicer, gentle on the 0.4 roof gap)
slider_hw = 5;
// Slider body length (mm) — equal to the stroke so both stops are body stops
slider_len = stroke;
// Tongue width (mm) — the narrow stem through the stop-bar window
tongue_w = 8;
// Tongue+head length (mm) from the body's +Y end to the head's +Y face;
// head clears the stop bar by 1 mm at u = 0
tongue_len = 31;
// Head (flexure anchor plate) X extent [min, max] (mm) — spans arch..V lines
head_x = [x_arch - 4, x_vbeam + 4];
// Head length in Y (mm)
head_len = 6;
// Knob half-width X (mm) — the push/pull affordance through the deck slot
knob_hw = 3;
// Knob proud height above the deck top (mm)
knob_proud = 2;
// Channel wall thickness (mm)
wall_t = 4;
// Clearance from the springs' full sweep to the chamber walls (mm)
sweep_clear = 0.6;
// Beam-anchor overlap into the frame/head solids (mm) — unions stay solid
ov = 1.2;
// Printed-pose clearance at the -Y stop (mm): the back wall stands this far
// behind the slider's rest face so NOTHING touches in the printed pose but
// the designed spring welds — a zero-gap stop face prints as a seam that
// welds shut (what iteration 1's fusecheck caught, on the part and on every
// coupon fit cell). Buys the same amount of protective -Y overtravel before
// the arch band goes into tension.
stop_clear = 1;
// Preview pose: slider displacement into the stroke, 0..stroke (mm).
// PRINT AT 0 — the as-solved rest pose.
demo_u = 0;

/* [Quality] */
// Production value 96; the arch band's curve resolution is NS below,
// independent of $fn.
$fn = 96;

// ---- derived ----------------------------------------------------------------
xy_tol = k_xy * line_w;                    // 0.207 — spread-limited
z_gap = z_layers * layer_h;                // 0.4 — sag-limited, whole layers
sh_h = width;                              // slider height = flexure band
deck_z0 = sh_h + z_gap;                    // 6.4 — roof gap above the slider
deck_t = 3.2;                              // capture deck thickness
frame_h = deck_z0 + deck_t;                // 9.6 — walls/deck top
knob_h = frame_h + knob_proud;             // 11.6 — knob top
NS = 60;                                   // arch band polygon resolution

fs_pred = 1486.57 * E * (width * pow(beam_t, 3) / 12) * mid_rise / pow(span, 3);
k_arch = 2 * target_fs / u_tr;             // |negative slope|, N/mm

// V-beam: leg length fixed by the relaxed pose (apex offset v_apex0 there);
// like the arch it is printed deflected — the pre-load IS its working point.
u_free = u_engage + (target_fs - target_force) / k_arch;   // 4.333
v_span0 = span - u_free;                   // 135.93 — relaxed span
v_L = pow(pow(v_span0 / 2, 2) + pow(v_apex0, 2), 0.5);     // 84.37
function v_half(s) = (span - s) / 2;                       // half-span at pose s
function v_apex(s) = pow(max(v_L * v_L - pow(v_half(s), 2), 0.01), 0.5);
function v_k(s) = E * width * pow(v_t, 3) * pow(v_apex(s) / v_L, 2) / pow(v_L, 3);

// Y coordinates of the frame (slider pose s: body tail at y = s)
y_slot0 = 0;                               // slider rest face (body tail at u=0)
y_chan0 = y_slot0 - stop_clear;            // channel -Y end / back wall face
y_slot1 = slider_len + stroke;             // 40 — stop bar face (+Y body stop)
y_bar_t = 4;                               // back wall / stop bar thickness
tip0 = slider_len + tongue_len;            // 51 — head +Y face at pose 0
y_far = tip0 + span;                       // 191.26 — far bar -Y face
y_far_t = 5;                               // far bar thickness

// sweep extremes (chamber walls and the fitcheck)
arch_sweep_hw = mid_rise + beam_t / 2;     // 8.49 — band's max |x - x_arch|
v_apex_max = x_vbeam + v_apex(stroke) + v_t / 2;
chamber_x = [x_arch - arch_sweep_hw - sweep_clear - wall_t, x_arch - arch_sweep_hw - sweep_clear];
chamber_x2 = [v_apex_max + sweep_clear, v_apex_max + sweep_clear + wall_t];
frame_x = [chamber_x[0], chamber_x2[1]];   // frame outer X extent

// ---- the mover (slider + tongue + head + knob), pose s ----------------------
function tip_y(s) = s + slider_len + tongue_len;   // head +Y face at pose s

// the mover's three features, split so the sweep can hull each one across
// the stroke (see sweep_2d)
module body_2d(s) {
    // body (guided + captured)
    translate([-slider_hw, s]) square([2 * slider_hw, slider_len]);
}
module tongue_2d(s) {
    // tongue through the stop-bar window
    translate([-tongue_w / 2, s + slider_len]) square([tongue_w, tongue_len - head_len]);
}
module head_2d(s) {
    // head: the rigid plate both flexures anchor into
    translate([head_x[0], tip_y(s) - head_len]) square([head_x[1] - head_x[0], head_len]);
}

module slider_2d(s) {
    union() { body_2d(s); tongue_2d(s); head_2d(s); }
}

module knob_2d(s) {
    // centred on the body; both slot ends sit one xy gap beyond the travel
    translate([-knob_hw, s + slider_len / 2 - knob_hw]) square([2 * knob_hw, 2 * knob_hw]);
}

module mover(s) {
    linear_extrude(sh_h) slider_2d(s);
    linear_extrude(knob_h) knob_2d(s);     // prints on the body, through the slot
}

// ---- the flexures, pose s ----------------------------------------------------
// clamped first-mode band; rise in +x from the chord line x_a (h < 0 mirrors)
function arch_rise_at(dy, chord, h) = h * (1 - cos(360 * dy / chord)) / 2;

module arch_band_2d(x_a, y0, y1, h, t) {
    chord = y1 - y0;
    top = [for (i = [0 : NS]) let (dy = chord * i / NS)
        [x_a + arch_rise_at(dy, chord, h) + t / 2, y0 + dy]];
    bot = [for (i = [NS : -1 : 0]) let (dy = chord * i / NS)
        [x_a + arch_rise_at(dy, chord, h) - t / 2, y0 + dy]];
    polygon(concat(top, bot));
}

module arch_root_gussets_2d(x_a, y0, y1, t) {
    // r = 0.5t root fillets (the doc's minimum), each disc `bite` PAST the
    // faces it joins — a tangent-only disc pinches the polygon at a point and
    // exports naked edges (the #389 coupon lesson). Both sides of both roots:
    // the band sweeps to -h, so the concave side flips after the snap.
    rf = t / 2;
    bite = 0.06;
    for (ry = [y0, y1], sy = [-1, 1], sx = [-1, 1])
        translate([x_a + sx * (rf - bite), ry + sy * (rf - bite)]) circle(rf);
}

module arch(s) {
    linear_extrude(sh_h)
        union() {
            arch_band_2d(x_arch, tip_y(s) - ov, y_far + ov, mid_rise, beam_t);
            arch_root_gussets_2d(x_arch, tip_y(s), y_far, beam_t);
        }
}

module vbeam(s) {
    // two hull-beams through the apex; the rounded apex doubles as the joint
    // fillet. Overlaps both anchors by ov (solid unions, no kissing edges).
    ap = [x_vbeam + v_apex(s), (tip_y(s) + y_far) / 2];
    linear_extrude(sh_h) union() {
        hull() { translate([x_vbeam, tip_y(s) - ov]) circle(v_t / 2); translate(ap) circle(v_t / 2); }
        hull() { translate(ap) circle(v_t / 2); translate([x_vbeam, y_far + ov]) circle(v_t / 2); }
    }
}

// ---- the cage (frame) --------------------------------------------------------
// deck = false omits the capture deck's footprint: that is the fitcheck's
// cage, compared against the movers' z <= deck_z0 sweep only, so the deck
// (a z > deck_z0 solid sharing the channel's footprint) must not read as an
// obstacle it is not.
module frame_2d(deck = true) {
    ch = slider_hw + xy_tol;               // channel half-width (the xy gap)
    fw = ch + wall_t;                      // frame half-width at the slot zone
    union() {
        // back wall (-Y overload stop, stop_clear behind the rest face) +
        // channel side walls + the capture deck
        translate([-fw, y_chan0 - y_bar_t]) square([2 * fw, y_bar_t]);
        translate([-fw, y_chan0]) square([wall_t, y_slot1 - y_chan0]);
        translate([ch, y_chan0]) square([wall_t, y_slot1 - y_chan0]);
        if (deck)
            translate([-ch, y_chan0]) square([2 * ch, y_slot1 - y_chan0]);
        // stop bar (+Y body stop, full chamber width — ties the walls)
        translate([frame_x[0], y_slot1]) square([frame_x[1] - frame_x[0], y_bar_t]);
        // chamber side walls (the springs' +-X overload stops)
        translate([chamber_x[0], y_slot1 + y_bar_t])
            square([wall_t, y_far + y_far_t - y_slot1 - y_bar_t]);
        translate([chamber_x2[0], y_slot1 + y_bar_t])
            square([wall_t, y_far + y_far_t - y_slot1 - y_bar_t]);
        // far bar (the flexures' fixed anchor)
        translate([frame_x[0], y_far]) square([frame_x[1] - frame_x[0], y_far_t]);
    }
}

// The below-deck cuts in 2D: the channel (from stop_clear behind the rest
// face to the stop bar) and the tongue window through the stop bar. Shared
// by frame_cuts_3d (the real part) and the fitcheck's cage, so the cage
// proves what the real frame actually is — a cage without the cuts would
// read the tongue's own window as an obstacle (iteration 1's finding).
module below_deck_cuts_2d(gap) {
    ch = slider_hw + gap;
    // channel: slider body
    translate([-ch, y_chan0]) square([2 * ch, y_slot1 - y_chan0]);
    // tongue window through the stop bar
    translate([-tongue_w / 2 - gap, y_slot1])
        square([tongue_w + 2 * gap, y_bar_t + 0.1]);
}

// z-banded cuts: the below-deck set under the deck, then the knob slot
// through the deck's own band. fused = true turns every clearance into
// 0.2 mm of interference — the fusecheck's known-fused control.
module frame_cuts_3d(fused = false) {
    gap = fused ? -0.2 : xy_tol;
    kh = knob_hw + gap;
    translate([0, 0, -0.1]) linear_extrude(deck_z0 + 0.1) below_deck_cuts_2d(gap);
    // knob slot through the deck: the knob's travel + one gap each end
    translate([0, 0, deck_z0]) linear_extrude(knob_h - deck_z0 + 0.1)
        translate([-kh, slider_len / 2 - knob_hw - gap])
            square([2 * kh, stroke + 2 * knob_hw + 2 * gap]);
}

module frame(fused = false) {
    difference() {
        linear_extrude(frame_h) frame_2d();
        frame_cuts_3d(fused);
    }
}

// ---- everything that moves, swept over the full stroke and the full snap ----
// PER-FEATURE hulls: every mover feature translates monotonically in +Y, so
// the hull of its two extreme poses IS its swept volume. Hulling the whole
// mover instead bridges body->head diagonally through the channel walls and
// reports phantom interference on walls no real pose touches (iteration 1's
// finding). The arch hulls its four extreme poses (+/- rise at both stroke
// ends); each V leg hulls its four endpoint circles, the far anchor pulled
// v_t/2 back of the far bar — the real leg overlaps the bar by `ov` as its
// designed weld, which is not the sweep's business.
module sweep_2d() {
    hull() { body_2d(0); body_2d(stroke); }
    hull() { tongue_2d(0); tongue_2d(stroke); }
    hull() { head_2d(0); head_2d(stroke); }
    hull() { knob_2d(0); knob_2d(stroke); }
    hull() {
        arch_band_2d(x_arch, tip_y(0), y_far, mid_rise, beam_t);
        arch_band_2d(x_arch, tip_y(0), y_far, -mid_rise, beam_t);
        arch_band_2d(x_arch, tip_y(stroke), y_far, mid_rise, beam_t);
        arch_band_2d(x_arch, tip_y(stroke), y_far, -mid_rise, beam_t);
    }
    y_a = y_far - v_t / 2 - 0.05;            // far anchor clear of the bar
    for (leg = [0, 1]) hull()
        for (s = [0, stroke]) {
            ap = [x_vbeam + v_apex(s), (tip_y(s) + y_far) / 2];
            translate(leg == 0 ? [x_vbeam, tip_y(s)] : [x_vbeam, y_a]) circle(v_t / 2);
            translate(ap) circle(v_t / 2);
        }
}

// ---- the coupon: 3 fit cells (k_xy sweep) + 1 QZS feeler cell ----------------
// Fit cells: the production channel section with free sliders at k_xy =
// 0.40 / 0.45 (production) / 0.50, labelled 1/2/3 (no "0" glyphs — an
// enclosed counter cuts loose as a floating chip). Feeler: a shorter-span QZS
// pair (same t, h, w, channel section; l/h = 11.1) whose plateau is firmer
// but teaches the same glide — and which way to tune when your E is off the
// datum. Printed at rest like the production part.
fit_cell_len = 26;
fit_kxy = [0.40, 0.45, 0.50];

module fit_cell(k, label) {
    ch = slider_hw + k * line_w;
    fw = ch + wall_t;
    difference() {
        linear_extrude(frame_h)
            difference() {
                union() {
                    // back wall, 5 tall: room for the label with >= 0.8 mm
                    // of wall above and below the glyphs (thin-wall floor)
                    translate([-fw, -5]) square([2 * fw, 5]);
                    translate([-fw, 0]) square([2 * fw, fit_cell_len]);
                }
                translate([0, -4.1]) text(label, size = 3.2, halign = "center", spacing = 1.5);
            }
        // channel: ends 4 short of the block's +Y face (the +Y end wall)
        translate([0, 0, -0.1]) linear_extrude(deck_z0 + 0.1)
            translate([-ch, 0]) square([2 * ch, fit_cell_len - wall_t + 0.1]);
        // knob slot: knob travels y in [3, 19] (body 12 long, +-5 mm glide)
        translate([0, 0, deck_z0]) linear_extrude(frame_h - deck_z0 + 0.1)
            translate([-knob_hw - k * line_w, 3 - k * line_w])
                square([2 * (knob_hw + k * line_w), 16 + 2 * k * line_w]);
    }
    // the free slider, knob up through the slot (printed standing on the
    // body). It sits stop_clear into the channel so its rest face cannot
    // seam-weld to the label wall — the cell exists to test the SIDE and
    // ROOF clearances, and a welded slider tests nothing.
    linear_extrude(sh_h) translate([-slider_hw, stop_clear]) square([2 * slider_hw, 12]);
    linear_extrude(knob_h) translate([-knob_hw, 3 + stop_clear]) square([2 * knob_hw, 2 * knob_hw]);
}

// feeler: production flexure profile at a 90 mm span, 12 mm stroke; its own
// plateau starts at u = 2 and runs to the end of its travel
feel_span = 90;
feel_stroke = 12;
feel_fs = 1486.57 * E * (width * pow(beam_t, 3) / 12) * mid_rise / pow(feel_span, 3);
feel_apex0 = 32;                           // relaxed apex offset (at u = 2)
feel_L = pow(pow((feel_span - 2) / 2, 2) + pow(feel_apex0, 2), 0.5);   // 54.41
feel_vt = 3.32;                            // slope-matched at the flat ends
function feel_half(s) = (feel_span - s) / 2;
function feel_apex(s) = pow(max(feel_L * feel_L - pow(feel_half(s), 2), 0.01), 0.5);

module feeler() {
    ch = slider_hw + xy_tol;
    fw = ch + wall_t;
    ftip = 12 + 20;                        // head +Y face at rest (tongue 20)
    yffar = ftip + feel_span;              // 128 — far bar -Y face
    fx = [x_arch - arch_sweep_hw - sweep_clear - wall_t, 0];
    fx2 = [x_vbeam + feel_apex(feel_stroke) + feel_vt / 2 + sweep_clear,
           x_vbeam + feel_apex(feel_stroke) + feel_vt / 2 + sweep_clear + wall_t];
    difference() {
        linear_extrude(frame_h)
            union() {
                translate([-fw, y_chan0 - y_bar_t]) square([2 * fw, y_bar_t]);
                translate([-fw, y_chan0]) square([wall_t, 24 - y_chan0]);
                translate([ch, y_chan0]) square([wall_t, 24 - y_chan0]);
                translate([-ch, y_chan0]) square([2 * ch, 24 - y_chan0]);
                translate([fx[0], 24]) square([fx2[1] - fx[0], y_bar_t]);
                translate([fx[0], 24 + y_bar_t]) square([wall_t, yffar + y_far_t - 24 - y_bar_t]);
                translate([fx2[0], 24 + y_bar_t]) square([wall_t, yffar + y_far_t - 24 - y_bar_t]);
                translate([fx[0], yffar]) square([fx2[1] - fx[0], y_far_t]);
            }
        translate([0, 0, -0.1]) linear_extrude(deck_z0 + 0.1)
            translate([-ch, y_chan0]) square([2 * ch, 24 - y_chan0 + 0.1]);
        translate([0, 0, deck_z0]) linear_extrude(frame_h - deck_z0 + 0.1)
            translate([-knob_hw - xy_tol, 3 - xy_tol])
                square([2 * (knob_hw + xy_tol), feel_stroke + 2 * knob_hw + 2 * xy_tol]);
        translate([0, 0, -0.1]) linear_extrude(deck_z0 + 0.1)
            translate([-tongue_w / 2 - xy_tol, 24]) square([tongue_w + 2 * xy_tol, y_bar_t + 0.1]);
    }
    // mover at rest: body + tongue + head + knob
    linear_extrude(sh_h) union() {
        translate([-slider_hw, 0]) square([2 * slider_hw, 12]);
        translate([-tongue_w / 2, 12]) square([tongue_w, 20 - head_len]);
        translate([head_x[0], ftip - head_len]) square([head_x[1] - head_x[0], head_len]);
    }
    linear_extrude(knob_h) translate([-knob_hw, 3]) square([2 * knob_hw, 2 * knob_hw]);
    // springs: the arch modules at the shorter span + the slope-matched V
    linear_extrude(sh_h) union() {
        arch_band_2d(x_arch, ftip - ov, yffar + ov, mid_rise, beam_t);
        arch_root_gussets_2d(x_arch, ftip, yffar, beam_t);
    }
    fap = [x_vbeam + feel_apex(0), (ftip + yffar) / 2];
    linear_extrude(sh_h) union() {
        hull() { translate([x_vbeam, ftip - ov]) circle(feel_vt / 2); translate(fap) circle(feel_vt / 2); }
        hull() { translate(fap) circle(feel_vt / 2); translate([x_vbeam, yffar + ov]) circle(feel_vt / 2); }
    }
}

module coupon() {
    pitch = 2 * (slider_hw + 0.5 * line_w + wall_t) + 4;
    for (i = [0 : len(fit_kxy) - 1])
        translate([i * pitch, 0, 0]) fit_cell(fit_kxy[i], str(i + 1));
    // feeler alongside, long axis along +X (rotate -90 turns its +Y to +X)
    translate([3 * pitch + 6, 26 + 6, 0]) rotate(-90) feeler();
}

// "" = the production part (a monolith: the springs ARE the slider-frame
// connection, like bistable-toggle's fixed-fixed arch — bodies:1 is correct
// and the flex proof is the travel-sweep fitcheck + the fusecheck's
// chamber-drop). "coupon" = print this first. "fitcheck" = cage MINUS deck,
// intersected with everything that moves across stroke+snap (must be EMPTY).
// "fitcheck_neg" = that sweep grown past the clearances (must interfere —
// proves the check can fail). "fused" = every clearance turned into
// interference (the fusecheck control: must slice to 1 body).
part = "";

module main() {
    assert(mid_rise / beam_t >= 2.3,
           "arch too flat to be bistable (mid_rise/beam_t < 2.3)");
    assert(beam_t >= 0.8, "arch band under the two-perimeter floor (0.8 mm)");
    assert(width >= 3, "flexure width under the 3 mm floor");
    assert(span / mid_rise >= 10,
           "arch not shallow enough for the fixed-fixed constants (l/h < 10)");
    assert(abs(fs_pred - target_fs) < 0.05,
           str("solve drifted: echoed f_s = ", fs_pred, " N vs target ", target_fs, " N"));
    assert(u_engage + u_tr <= stroke,
           "the snap does not complete inside the stroke");
    assert(u_engage + u_tr >= (1 + flat_frac) / 2 * stroke - 0.001,
           "the snap finishes before the flat zone ends");
    assert(abs(v_k(stroke / 2) - k_arch) / k_arch <= 0.10,
           str("V-beam slope mismatch: k_v(mid-stroke) = ", v_k(stroke / 2),
               " N/mm vs |k_arch| = ", k_arch, " N/mm"));
    assert(z_layers >= 1, "the roof gap must be whole layers");
    assert(k_xy * line_w >= 0.15, "xy gap under the spread floor (0.15 mm)");
    echo(str("predicted switch force f_s = ", fs_pred, " N (target ", target_fs, " N)"));
    echo(str("predicted plateau ~ ", target_force, " N over u in [", u_engage, ", ",
             u_engage + u_tr, "] (middle ", flat_frac * 100, "% of the ", stroke, " mm stroke)"));
    echo(str("slope match: k_v(mid-stroke) = ", v_k(stroke / 2), " N/mm vs |k_arch| = ", k_arch, " N/mm"));
    echo(str("V-beam leg strain estimate ",
             1.5 * v_t * (v_apex(stroke) - v_apex(0)) / pow(v_L, 2) * 100, " % (PETG yield ~2-3%)"));
    echo(str("coupon feeler: f_s = ", feel_fs, " N, plateau ~9 N over u in [2, 12]"));

    if (part == "coupon")
        coupon();
    else if (part == "fitcheck")
        // cage = the frame as it exists below the deck — the footprint MINUS
        // the channel and tongue window (clearances, not obstacles) — met
        // with the full sweep. Must be EMPTY.
        linear_extrude(deck_z0) intersection() {
            difference() { frame_2d(false); below_deck_cuts_2d(xy_tol); }
            sweep_2d();
        }
    else if (part == "fitcheck_neg")
        linear_extrude(deck_z0) intersection() {
            difference() { frame_2d(false); below_deck_cuts_2d(xy_tol); }
            offset(0.5) sweep_2d();
        }
    else if (part == "fused") {
        difference() { linear_extrude(frame_h) frame_2d(); frame_cuts_3d(true); }
        mover(0);
        arch(0);
        vbeam(0);
    }
    else {
        frame();
        mover(demo_u);
        arch(demo_u);
        vbeam(demo_u);
    }
}

main();
