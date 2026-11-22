// compliant-coupon.scad — printable stiffness coupon for every module in
// compliant.scad (issue #1049, stage 4/4 of #202). All dimensions in mm.
//
// Pattern proven twice in the tree:
//   designs/cross-axis-flexure-pivot/cross-axis-flexure-pivot-coupon.scad
//   designs/let-folding-panel/let-folding-panel-coupon.scad
// — t-ladder (t is the t³-leverage knob) + identical production-t twins,
// no overrides of harvest-site production values on the twins. Open this
// file to print a bed-sized plate (default coupon_plate=0; see below);
// `use <>` consumers ignore the top-level call. Open
// lib/compliant-coupon-demo.scad for the full multi-strip plate plus
// golden asserts (check.sh CGAL-renders that — bed fit is a separate
// printcheck behavioral test on each coupon_plate index).
// Override the ladder only to extend it, e.g.:
//   openscad -D 'coupon_ts_slfp=[0.9, 1.1]' lib/compliant-coupon.scad
//   openscad -D 'coupon_plate=1' -D 'coupon_ts_xafp=[0.6,0.8,1.0,1.2,1.4]' \
//     lib/compliant-coupon.scad
//
use <compliant.scad>

// ---------------------------------------------------------------------------
// PROTOCOL (tied to templates/FIELD-TEST.md / docs/print-feedback.md)
//
// The lib echoes predicted K / f_s / u_tr / σ — numbers a render cannot
// self-verify (issue #37). This coupon is what makes those echoes
// trustworthy: print it, measure, log under "## Field test log" in the
// adopting design's NOTES.md (or a scratch NOTES next to a one-off print).
//
// Echoed K is the pure-end-moment torsional stiffness K = E·I/L (N·mm/rad)
// for an SLFP (cross-axis echoes 8·E·I/L welded; LET echoes torsion
// K = n_parallel·G·J/L/n_series). Convert a bench measurement to that K:
//   • Pure end-moment:  K = M / θ
//   • End-force (load F at free length L, measure tip angle θ):
//                       K = F·L / (2θ)
//     (cantilever: θ = F·L²/(2·E·I) ⇒ F·L/θ = 2K)
//   • Tip-travel (load F, measure tip deflection δ):
//                       K = F·L² / (3δ)
//     (cantilever: δ = F·L³/(3·E·I) ⇒ F·L²/δ = 3K)
// Do not compare a raw F·L/θ reading to the echo — that is 2K for an
// end-force test. For the bistable arch, measure snap force f_s and
// centre travel u_tr instead (not a K conversion).
//
// Two measurements, every specimen:
//   1. Stiffness — hold one grip, apply a known end-moment / end-force /
//      tip travel, convert to K with the formulas above, compare to the
//      echo. Arch: f_s and u_tr.
//   2. Cycles-to-failure at θ_max — swing to the specimen's design stop
//      (arch: through snap and back; SLFP tip-load δ=1.2 mm → θ=0.15 rad,
//      matching lib/compliant-demo.scad; cross-axis ±stop_angle; LET 90°
//      fold), return, repeat. Whitening at a root is the warning; a crack
//      is the verdict. Record the cycle count next to the label.
//      Cycling is separate from the stiffness conversion above.
//
// Material ranking (docs/advanced-techniques.md Domain 1 — a HEURISTIC, not
// a universal law; real fatigue life shifts with grade, orientation, stress
// range, temperature and geometry):
//   TPU ≈ PP > Nylon > PETG ≫ PLA
// The twins exist precisely to prove beyond that heuristic on YOUR printer:
// print the strip once per filament and read the twin labelled for what is
// loaded. PLA is a poor default for a live flexure — treat it as unsuitable
// unless a coupon run says otherwise.
//
// Orientation: layers PARALLEL to the flex axis (bending across roads within
// a layer, never between layer bonds). 0.2 mm layers; high perimeters / 100%
// infill on the flexure section.
//
// Log each print with the FIELD-TEST block (templates/FIELD-TEST.md):
// printed-from / part / slicer / result / measured deviations (K_meas vs
// K_pred, cycles at θ_max) / carry-forward.
//
// Bed: printable units target a 220×220 mm bed (fits the repo's 256 mm
// Bambu P2S class with margin). coupon_plate selects one unit; the demo's
// full multi-strip composition is for check.sh, not for slicing.
// ---------------------------------------------------------------------------

$fn = 48;

// ---- harvest-site production values (twins use these EXACTLY) ------------
// Arch — bistable-toggle production (solved f_s=3 N, u_tr=4 mm).
arch_t_prod  = 0.82;
arch_w_prod  = 6;
arch_rise_prod = bistable_arch_rise_for(4);
arch_span_prod = bistable_arch_span_for(3, arch_rise_prod, arch_t_prod, arch_w_prod);
arch_post = 6;

// SLFP — snap-cantilever-clip production.
sl_t_prod = 1.0;
sl_L_prod = 12;
sl_w_prod = 15;
sl_f_prod = 0.6;

// Cross-axis — cross-axis-flexure-pivot production.
xa_t_prod = 0.8;
xa_L_prod = 28;
xa_w_prod = 8;
xa_f_prod = 0.6;
xa_alpha = 45;
xa_stop = 40;
xa_arc = 6.5;

// LET — let-folding-panel production.
let_ns_prod = 1;
let_np_prod = 3;
let_w_prod = 2.0;
let_t_prod = 1.2;
let_L_prod = 14;
let_g_prod = 6;
let_fw_prod = 3.5;
let_r_prod = 0.8;

// ---- t-ladders (override to extend; production t is always in the set) ---
coupon_ts_arch = [0.8, 0.82, 1.0];
coupon_ts_slfp = [0.8, 1.0, 1.2];
coupon_ts_xafp = [0.6, 0.8, 1.0];
coupon_ts_let  = [0.8, 1.2, 1.4];

function fmt_t(tt) = str(tt, tt == floor(tt) ? ".0" : "");

// ---- layout constants (bed-sized packing) --------------------------------
// Printable plates must fit a 220×220 mm bed (256 mm class with margin).
coupon_bed_mm = 220;

// Cross-axis strip grid (3 columns). pitch_y clears production tab_w=22.
coupon_xafp_cols = 3;
coupon_xafp_pitch_x = 70;
coupon_xafp_pitch_y = 80;
// Half-extent Y of one XAFP specimen (production tabs widest: tab_w/2=11,
// plus a few mm for the arc body so LET clearance stays conservative).
coupon_xafp_env_y = 14;

// LET strip grid (3 columns) — linear pitch_x=80×5 overflowed a 256 mm bed.
// pitch_x must exceed production strip_len (70) or adjacent twins share a
// face and fuse into one body.
coupon_let_cols = 3;
coupon_let_pitch_x = 72;
coupon_let_pitch_y = 42;
// Half-extent Y: gap + panel_d = 6+12 = 18, plus pad.
coupon_let_env_y = 20;
coupon_strip_gap = 8;

// Item count = ladder cells + PETG twin + PLA twin.
function coupon_xafp_n_items() = len(coupon_ts_xafp) + 2;
function coupon_xafp_nrows() =
    ceil(coupon_xafp_n_items() / coupon_xafp_cols);
function coupon_xafp_last_row_y() =
    (coupon_xafp_nrows() - 1) * coupon_xafp_pitch_y;

// LET Y origin below an XAFP strip that starts at xafp_y0 — grows when the
// ladder adds rows (documented -D coupon_ts_xafp=[...] extension).
function coupon_let_origin_y(xafp_y0 = 140) =
    xafp_y0 + coupon_xafp_last_row_y()
        + coupon_xafp_env_y + coupon_let_env_y + coupon_strip_gap;

function coupon_let_n_items() = len(coupon_ts_let) + 2;

// ---- specimen builders (each is one watertight body) ---------------------

module _arch_clamps_2d(span, hh) {
    for (x0 = [-arch_post, span]) translate([x0, -hh]) square([arch_post, 2 * hh]);
}

// Arch specimen at thickness tt. Ladder cells keep rise/t = 2.3 (on the
// bistable bar) at a short free span; production twins use the harvest
// span/rise/t exactly.
module _coupon_label_cut(label, size = 2.5) {
    // Deboss cutter — difference()'d into a grip so the specimen stays one
    // body (raised text() glyphs each count as their own volume).
    translate([0, 0, -0.2])
        linear_extrude(0.8)
            text(label, size = size, halign = "center", valign = "center");
}

module coupon_arch_specimen(tt, label, pos, production = false) {
    span = production ? arch_span_prod : 35;
    rise = production ? arch_rise_prod : 2.3 * tt;
    ww = arch_w_prod;
    translate(pos) difference() {
        union() {
            bistable_arch(span, rise, tt, ww, E = 2000,
                          root_fillet = 0.5 * tt, ov = 1.2);
            for (x0 = [-arch_post, span])
                translate([x0, -4, 0]) cube([arch_post, 8, ww]);
        }
        // Deboss into the +x clamp top face.
        translate([span + arch_post / 2, 0, ww])
            _coupon_label_cut(label, size = min(2.5, 5 / max(1, len(label))));
    }
}

module coupon_slfp_specimen(tt, label, pos, production = false) {
    L = sl_L_prod;
    w = production ? sl_w_prod : 8;
    f = max(0.5 * tt, production ? sl_f_prod : 0.5 * tt);
    // Grip pads: strap at y>=0, tip pad past y=-L — one body with the beam.
    translate(pos) difference() {
        union() {
            translate([-6, 0, 0]) cube([12, 4, w]);
            small_length_pivot(tt, L, w, root_fillet = f, E = 2000);
            translate([-6, -L - 4, 0]) cube([12, 4, w]);
        }
        translate([0, 2, w])
            _coupon_label_cut(label, size = min(2.2, 9 / max(1, len(label))));
    }
}

module coupon_xafp_specimen(tt, label, pos, production = false) {
    // Ladder cells stay above every cross-axis guard floor (w ≥ 2.4,
    // tab_len ≥ 8, arc_wall ≥ 1.6); only L shrinks for plate density.
    // Twins keep the harvest-site numbers exactly — including xa_f_prod.
    L = production ? xa_L_prod : 20;
    w = production ? xa_w_prod : 2.4;
    f = production ? xa_f_prod : max(0.5 * tt, 0.3);
    aw = production ? xa_arc : 1.6;
    tlen = production ? 10 : 8;
    tw = production ? 22 : 12;
    tr = production ? 4 : 2;
    hpad = production ? 4 : 0;
    // Tabs sit on ±X at tab_cx = L/2 + arc_wall + tab_len/2; the raised
    // production pad is on the +X stage tab (z ∈ [w, w+hpad]).
    tab_cx = L / 2 + aw + tlen / 2;
    translate(pos) {
        if (label == "") {
            // Empty label: no cutter — used by the volume-delta test that
            // proves a non-empty label actually removes material.
            cross_axis_pivot(tt, L, w, f, alpha = xa_alpha, stop_angle = xa_stop,
                             arc_wall = aw, E = 2000, h_pad = hpad,
                             tab_len = tlen, tab_w = tw, tab_r = tr);
        } else difference() {
            cross_axis_pivot(tt, L, w, f, alpha = xa_alpha, stop_angle = xa_stop,
                             arc_wall = aw, E = 2000, h_pad = hpad,
                             tab_len = tlen, tab_w = tw, tab_r = tr);
            translate([tab_cx, 0, w + hpad])
                _coupon_label_cut(label, size = min(2.2, 8 / max(1, len(label))));
        }
    }
}

module coupon_let_specimen(tt, label, pos, production = false) {
    // Twins: exact harvest. Ladder: same plan dimensions, swept bar_t; root
    // fillet tracks max(harvest 0.8, 0.5·t) so the r ≥ 0.5·t guard holds.
    ns = let_ns_prod;
    np = production ? let_np_prod : 2;  // ladder: hand-scale 3 fingers
    bw = let_w_prod;
    bL = let_L_prod;
    gap = let_g_prod;
    fw = let_fw_prod;
    rf = production ? let_r_prod : max(0.8, 0.5 * tt);
    fingers = np + 1;
    pitch = fw + bL;
    strip_len = fingers * pitch;
    panel_d = 12;
    embed = 1;
    translate(pos) difference() {
        union() {
            let_joint(ns, np, bw, tt, bL, gap, finger_w = fw,
                      root_fillet = rf, embed = embed, E = 2000);
            // A / B grip panels — embed past the finger tips (harvest style).
            translate([0, -gap - panel_d, 0])
                cube([strip_len, panel_d + embed, tt]);
            translate([0, gap - embed, 0])
                cube([strip_len, panel_d + embed, tt]);
        }
        translate([strip_len / 2, gap + panel_d / 2, tt])
            _coupon_label_cut(label, size = min(2.5, 10 / max(1, len(label))));
    }
}

// ---- strips --------------------------------------------------------------

module coupon_arch_strip(origin = [0, 0, 0]) {
    n = len(coupon_ts_arch);
    pitch_x = arch_span_prod + 2 * arch_post + 8;
    pitch_y = 28;
    translate(origin) {
        for (i = [0 : n - 1])
            coupon_arch_specimen(coupon_ts_arch[i], fmt_t(coupon_ts_arch[i]),
                                 [i * (35 + 2 * arch_post + 6), 0, 0],
                                 production = false);
        // Production twins — exact harvest geometry, labelled for filament.
        coupon_arch_specimen(arch_t_prod, "PETG",
                             [0, pitch_y, 0], production = true);
        coupon_arch_specimen(arch_t_prod, "PLA",
                             [pitch_x, pitch_y, 0], production = true);
    }
}

module coupon_slfp_strip(origin = [0, 0, 0]) {
    n = len(coupon_ts_slfp);
    pitch_x = 22;
    translate(origin) {
        for (i = [0 : n - 1])
            coupon_slfp_specimen(coupon_ts_slfp[i], fmt_t(coupon_ts_slfp[i]),
                                 [i * pitch_x, 0, 0], production = false);
        coupon_slfp_specimen(sl_t_prod, "PETG",
                             [n * pitch_x, 0, 0], production = true);
        coupon_slfp_specimen(sl_t_prod, "PLA",
                             [(n + 1) * pitch_x, 0, 0], production = true);
    }
}

module coupon_xafp_strip(origin = [0, 0, 0]) {
    n = len(coupon_ts_xafp);
    cols = coupon_xafp_cols;
    pitch_x = coupon_xafp_pitch_x;
    pitch_y = coupon_xafp_pitch_y;
    translate(origin) {
        for (i = [0 : n - 1])
            coupon_xafp_specimen(coupon_ts_xafp[i], fmt_t(coupon_ts_xafp[i]),
                                 [(i % cols) * pitch_x,
                                  floor(i / cols) * pitch_y, 0],
                                 production = false);
        coupon_xafp_specimen(xa_t_prod, "PETG",
                             [(n % cols) * pitch_x,
                              floor(n / cols) * pitch_y, 0],
                             production = true);
        coupon_xafp_specimen(xa_t_prod, "PLA",
                             [((n + 1) % cols) * pitch_x,
                              floor((n + 1) / cols) * pitch_y, 0],
                             production = true);
    }
}

module coupon_let_strip(origin = [0, 0, 0]) {
    n = len(coupon_ts_let);
    cols = coupon_let_cols;
    pitch_x = coupon_let_pitch_x;
    pitch_y = coupon_let_pitch_y;
    translate(origin) {
        for (i = [0 : n - 1])
            coupon_let_specimen(coupon_ts_let[i], fmt_t(coupon_ts_let[i]),
                                [(i % cols) * pitch_x,
                                 floor(i / cols) * pitch_y, 0],
                                production = false);
        coupon_let_specimen(let_t_prod, "PETG",
                            [(n % cols) * pitch_x,
                             floor(n / cols) * pitch_y, 0],
                            production = true);
        coupon_let_specimen(let_t_prod, "PLA",
                            [((n + 1) % cols) * pitch_x,
                             floor((n + 1) / cols) * pitch_y, 0],
                            production = true);
    }
}

// Full multi-strip composition (demo / check.sh) OR one bed-sized print
// plate. which:
//   "all" — every module, LET Y derived from XAFP row count
//   0     — arch + SLFP
//   1     — cross-axis
//   2     — LET
module compliant_coupon_plate(which = "all") {
    xafp_y0 = 140;
    if (which == "all") {
        coupon_arch_strip([0, 0, 0]);
        coupon_slfp_strip([0, 90, 0]);
        coupon_xafp_strip([0, xafp_y0, 0]);
        coupon_let_strip([0, coupon_let_origin_y(xafp_y0), 0]);
    } else if (which == 0) {
        coupon_arch_strip([0, 0, 0]);
        coupon_slfp_strip([0, 70, 0]);
    } else if (which == 1) {
        coupon_xafp_strip([0, 0, 0]);
    } else if (which == 2) {
        coupon_let_strip([0, 0, 0]);
    } else {
        assert(false, str("compliant_coupon_plate: unknown which=", which,
                          " (want \"all\" / 0 / 1 / 2)"));
    }
}

// Print entrypoint — opening this file yields a bed-sized plate.
// Override with -D 'coupon_plate=1' (or 2). `use <>` ignores top-level
// calls. Fixtures that `include` this file set coupon_emit=false (after
// the include; last-assignment-wins) so only their own geometry runs.
coupon_plate = 0;
coupon_emit = true;
if (coupon_emit)
    compliant_coupon_plate(coupon_plate);
