// nuggs-port-gauge — port-tolerance ladder for the NUGGS interlock.
// A reference head at nominal geometry plus two ladder plates carrying
// five port_tol steps (0.20 / 0.25 / 0.30 / 0.35 / 0.40). Mate the head
// against each step, feel which welds / locks crisply / slops, and write
// the winner into every NUGGS coupon on that printer.
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// HITL ladder-plate-layout = YES (2026-10-12): two plates, all five values.
// Style: none — a calibration artifact; the embossed numbers are the design.

use <nuggs-coupling.scad>

/* [What to render] */
// assembled = review preview of every plate; the rest are printable parts
// or boolean fit proofs (ci.fitchecks — never printed).
part = "assembled"; // [assembled, reference-head, ladder-3, ladder-2, coupon, mate-020, mate-025, mate-030, mate-035, mate-040, mate-ctrl, cutaway]

/* [The NUGGS standard — change these and nothing you already printed fits] */
// Internal bore (mm) — the headline number
bore_d = 80.0;
// Tube shell thickness (mm)
wall = 2.4;
// Radial depth of the coupling ring beyond the tube OD (mm)
lug_r = 6.0;
// Axial projection of the coupling sectors past the tube face (mm)
port_proj = 10.0;
// Coupling sectors per face
n_lug = 3;
// Angular width of each sector (deg)
lug_deg = 40;
// Radial depth of the locking rib (mm)
rib_h = 1.0;
// Axial width of the locking rib / groove (mm)
rib_w = 2.4;
// Angular width of the locking rib (deg)
rib_deg = 12;
// The locking twist (deg)
twist_deg = 14;
// Backing-collar thickness (mm)
collar_t = 3.0;
// Overlap fusing ribs into outer sectors (mm)
bite = 0.8;
// Nominal port_tol on the reference head (mm) — the inherited guess
ref_port_tol = 0.30;

/* [Ladder] */
// The five port_tol steps under test (mm). Do not reorder casually —
// plate assignment and fitcheck part names follow this list.
ladder_tols = [0.20, 0.25, 0.30, 0.35, 0.40];
// Centre-to-centre pitch between matable steps (mm). Must clear the
// Ø(2·r_out) mating envelope so the reference head can seat on one step
// without colliding with its neighbour. 97 is a hair over the Ø96.8
// envelope and keeps the 2-step plate under 200 mm wide.
step_pitch = 97.0;
// Extra full-round shell behind z_top on every neck (mm)
shell_extra = 8.0;
// Backplate thickness under the sector tips (mm)
plate_t = 3.2;
// Margin from the outermost ring to the backplate edge (mm)
plate_margin = 3.0;
// Emboss height of each step's value label (mm)
emboss_h = 0.60;
// Cap height of the embossed value text (mm)
label_h = 7.0;

/* [Reference head] */
// Grip-tab length past the neck OD (mm)
grip_len = 28.0;
// Grip-tab width (mm)
grip_w = 22.0;
// Grip-tab thickness (mm) — also the flat bed pad under the laid-down neck
grip_t = 4.0;
// 45° bed-edge chamfer on sector-tip OD (mm). Absorbs first-layer squish on
// the datum head/coupon; applied as a difference on the assembled part —
// never inside port_stub (N3). Plates bury tips in the backplate, so they
// do not take this cut.
tip_chamfer = 0.4;

/* [Print settings] */
// Nozzle diameter (mm) — feeds the wall and web guards in the lib
nozzle = 0.4;
// Welfare bore floor the lib asserts (mm)
min_bore_mm = 70;

/* [Quality] */
// Iterating: 32. Production curves come from the lib's pinned $fa/$fs.
$fn = 48;

// ---------------------------------------------------------------------------
// Derived
// ---------------------------------------------------------------------------

function cfg_at(tol) =
    nuggs_cfg(bore_d = bore_d, wall = wall, lug_r = lug_r,
              port_proj = port_proj, collar_t = collar_t, n_lug = n_lug,
              lug_deg = lug_deg, rib_h = rib_h, rib_w = rib_w,
              rib_deg = rib_deg, twist_deg = twist_deg, bite = bite,
              port_tol = tol, nozzle = nozzle, min_bore = min_bore_mm);

cfg_ref = cfg_at(ref_port_tol);
r_out   = nuggs_r_out(cfg_ref);
z_top   = nuggs_z_top(cfg_ref);
z_tip   = nuggs_z_tip(cfg_ref);
neck_len = z_top + shell_extra;

// Plate assignments (HITL yes): 3-step + 2-step, all five values kept.
// On the 2+1 triangle, put 0.30 (decision-rule anchor) on a bottom centre
// with a free front label; apex gets 0.20 with its label aimed +y (outer
// edge) so nothing sits in the interior pocket (Drik r2).
tols_3 = [0.30, 0.25, 0.20];
tols_2 = [ladder_tols[3], ladder_tols[4]];                 // 0.35 0.40

// 2+1 triangle centres for the 3-step plate (equilateral side = step_pitch).
// Origin at the centroid of the three centres so the plate is centred.
_h3 = step_pitch * sqrt(3) / 2;
centres_3 = [
    [-step_pitch / 2, -_h3 / 3],
    [ step_pitch / 2, -_h3 / 3],
    [ 0,               2 * _h3 / 3]
];
centres_2 = [[-step_pitch / 2, 0], [step_pitch / 2, 0]];

// ---------------------------------------------------------------------------
// Guards
// ---------------------------------------------------------------------------

assert(len(ladder_tols) == 5, "ladder_tols must keep all five brief steps");
assert(ladder_tols == [0.20, 0.25, 0.30, 0.35, 0.40],
    "ladder_tols drifted from the brief / HITL set {0.20..0.40}");
assert(step_pitch + 1e-9 >= 2 * r_out, str(
    "STEP PITCH: step_pitch = ", step_pitch, " mm is under the mating",
    " envelope Ø", 2 * r_out, " mm — the reference head cannot seat on one",
    " step without hitting its neighbour. Raise step_pitch."));
assert(emboss_h >= 0.5 && emboss_h <= 1.2, str(
    "EMBOSS: emboss_h = ", emboss_h, " mm is outside the printable raised-",
    "label band (0.5–1.2)."));
assert(plate_t >= 1.2, str(
    "PLATE: plate_t = ", plate_t, " mm is under the 1.2 mm wall floor."));
assert(grip_t >= 1.2 && grip_w >= 12 && grip_len >= 16, str(
    "GRIP: tab ", grip_len, "×", grip_w, "×", grip_t,
    " mm is too small to hold."));

// ---------------------------------------------------------------------------
// Building blocks
// ---------------------------------------------------------------------------

// One port face on a short neck, in the library's native frame (sectors on
// −z, tube on +z). Prefer nuggs_neck() — it owns the bore cut.
module port_stub(tol) {
    nuggs_neck(cfg_at(tol), neck_len);
}

// Bed-frame cutter: 45° chamfer on the outer tip OD at z = 0. A full
// rotate_extrude only removes material where tips exist. N3: edge treatment
// on the part, not a coupling-profile change.
module tip_od_chamfer_cut(tol, ch = tip_chamfer) {
    r = nuggs_r_out(cfg_at(tol));
    ov = 0.05;
    rotate_extrude($fn = 96)
        polygon([
            [r - ch, -ov],
            [r + 1,  -ov],
            [r + 1,   ch],
            [r,       ch]
        ]);
}

// Value label embossed on the XY plane at z, centred. Uses text() — the
// ladder values need a decimal point, which stencil-glyphs does not carry.
// Format as two decimals so 0.20 does not render as "0.2".
function tol_label_str(tol) =
    let (cents = round(tol * 100),
         frac = cents < 10 ? str("0", cents) : str(cents))
        str("0.", frac);

module tol_label(tol) {
    linear_extrude(emboss_h)
        text(tol_label_str(tol), size = label_h, halign = "center",
             valign = "center", font = "Liberation Sans:style=Bold");
}

// Radial offset from a station centre to its label centreline (mm). Inner
// glyph edge lands at ≈ r_out − 1 — the label-clearance wall (see NOTES).
function label_r() = r_out + plate_margin / 2 + 1;

// ---------------------------------------------------------------------------
// Reference head — one nominal neck + grip tab.
//
// Print pose is the family coupon stance (port axis vertical, standing on
// sector tips): a laid-down neck scores CRITICAL on unbridgeable overhang
// (the bayonet ring is ~26% downward face). Use pose is still "hold the
// grip and mate horizontally." See NOTES.md.
// ---------------------------------------------------------------------------

module reference_head() {
    difference() {
        union() {
            // Neck standing on its sector tips at z = 0
            translate([0, 0, -z_tip])
                port_stub(ref_port_tol);

            // Grip tab on the bed, fused into the sector-tip footprint via a
            // web that reaches inside r_out so the union is one body.
            translate([r_out - 8, -grip_w / 2, 0])
                cube([grip_len + 8, grip_w, grip_t]);

            translate([r_out - 8 + (grip_len + 8) / 2, 0, grip_t - 0.05])
                tol_label(ref_port_tol);
        }
        tip_od_chamfer_cut(ref_port_tol);
    }
}

// ---------------------------------------------------------------------------
// Ladder plates — ports stand on their sector tips (family coupon pose) on
// a stiff backplate so the mating face is approachable from above. Centres
// are ≥ step_pitch apart (HITL: Ø96.8 envelope). Labels emboss beside each
// ring on the backplate — per-station direction so the apex (0.30) on the
// 2+1 triangle sits on the free outer edge, not in the interior pocket.
//
// Print orientation note: the brief's "port axis horizontal" is the *use*
// pose (mate the reference head by hand). The plates print with port axes
// vertical — the same bed-stable sector-tip stance every NUGGS coupon uses —
// because a 2+1 of horizontal Ø96.8 envelopes cannot meet the decided
// ≤200×135 footprint while keeping centres ≥ 96.8. See NOTES.md.
// ---------------------------------------------------------------------------

// label_dir is a unit XY vector from the station centre toward the label.
module ladder_station(tol, cxy, label_dir = [0, -1]) {
    // Bury sector tips 0.8 mm into the backplate so the union cannot
    // kiss on a coplanar tip/plate pair (CGAL zero-volume facets).
    translate([cxy[0], cxy[1], plate_t - z_tip - 0.8])
        port_stub(tol);
    // Label just outside the ring — bury into the backplate so the emboss
    // unions instead of kissing as a second body.
    lr = label_r();
    translate([cxy[0] + label_dir[0] * lr,
               cxy[1] + label_dir[1] * lr,
               plate_t - 0.05])
        tol_label(tol);
}

module ladder_backplate(centres, label_dirs) {
    // Axis-aligned bounds of every ring plus margin, grown for each label
    xs = [for (c = centres) c[0]];
    ys = [for (c = centres) c[1]];
    lr = label_r();
    pad = label_h / 2 + 2;
    lx = [for (i = [0 : len(centres) - 1])
            centres[i][0] + label_dirs[i][0] * lr];
    ly = [for (i = [0 : len(centres) - 1])
            centres[i][1] + label_dirs[i][1] * lr];
    x0 = min(min(xs) - r_out - plate_margin, min(lx) - pad);
    x1 = max(max(xs) + r_out + plate_margin, max(lx) + pad);
    y0 = min(min(ys) - r_out - plate_margin, min(ly) - pad);
    y1 = max(max(ys) + r_out + plate_margin, max(ly) + pad);
    translate([x0, y0, 0])
        cube([x1 - x0, y1 - y0, plate_t]);
}

module ladder_plate(tols, centres, label_dirs) {
    assert(len(tols) == len(centres), "ladder_plate: tols/centres length mismatch");
    assert(len(label_dirs) == len(centres),
           "ladder_plate: label_dirs/centres length mismatch");
    union() {
        ladder_backplate(centres, label_dirs);
        for (i = [0 : len(tols) - 1])
            ladder_station(tols[i], centres[i], label_dirs[i]);
    }
}

// Bottom stations label −y (open front); apex labels +y (free outer edge).
dirs_3 = [[0, -1], [0, -1], [0, 1]];
dirs_2 = [[0, -1], [0, -1]];

module ladder_3() ladder_plate(tols_3, centres_3, dirs_3);
module ladder_2() ladder_plate(tols_2, centres_2, dirs_2);

// ---------------------------------------------------------------------------
// Coupon — one reference stub beside one mid-ladder step (0.30), both in
// the family standing pose. Print this first to confirm the printer can
// reproduce the nominal joint before committing a full ladder plate.
// ---------------------------------------------------------------------------

module coupon() {
    pitch = 2 * r_out + 12;
    difference() {
        union() {
            translate([-pitch / 2, 0, -z_tip])
                port_stub(ref_port_tol);
            translate([ pitch / 2, 0, -z_tip])
                port_stub(0.30);
        }
        translate([-pitch / 2, 0, 0]) tip_od_chamfer_cut(ref_port_tol);
        translate([ pitch / 2, 0, 0]) tip_od_chamfer_cut(0.30);
    }
}

// ---------------------------------------------------------------------------
// Fitchecks — reference head ∩ each ladder step at the insertion clocking.
// Mirrored mate, pulled 0.01 mm (the lib's own seat-face discipline). Empty
// = that step accepts the nominal head. mate-ctrl is the mandatory
// negative: clocked at 0 so outer lands on outer.
// ---------------------------------------------------------------------------

module fit_mate(step_tol, clock = undef) {
    // Same pose as designs/nuggs-vent-cap and lib/nuggs-coupling-mates.conf:
    // both necks in the library frame, mate mirrored and pulled 0.01 mm so
    // the zero-clearance seat/tube faces do not share whole facets.
    cfg_s = cfg_at(step_tol);
    clk = is_undef(clock) ? nuggs_clockings(cfg_s)[0] : clock;
    intersection() {
        nuggs_neck(cfg_s, neck_len);
        translate([0, 0, -0.01])
            rotate([0, 0, clk])
                mirror([0, 0, 1])
                    nuggs_neck(cfg_ref, neck_len);
    }
}

module fit_mate_ctrl() {
    // Deliberately wrong clocking — must interfere
    fit_mate(ref_port_tol, 0);
}

// ---------------------------------------------------------------------------
// Assembled preview — the three printable objects laid out on the bed
// ---------------------------------------------------------------------------

module assembled() {
    translate([0, 0, 0])
        ladder_3();
    translate([0, - (2 * r_out + 40 + _h3), 0])
        ladder_2();
    // Reference head off to the side
    translate([step_pitch + 2 * r_out + 40, 0, 0])
        reference_head();
}

module cutaway() {
    // Section through one ladder step + the reference head mated at 0.30.
    // Cut plane at y = −6 (not through the axis) so the cylinder OD is not
    // tangent to the cut — a through-axis half left a paper sliver at ±x
    // (the right crop edge). Fuller quarter-section is backlog, not now.
    difference() {
        union() {
            translate([0, 0, -z_tip])
                nuggs_neck(cfg_at(0.30), neck_len);
            translate([0, 0, -0.01])
                rotate([0, 0, nuggs_clockings(cfg_ref)[0]])
                    mirror([0, 0, 1])
                        translate([0, 0, -z_tip])
                            nuggs_neck(cfg_ref, neck_len);
        }
        translate([-200, -6, -200])
            cube([400, 400, 400]);
    }
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------

echo(str("nuggs-port-gauge: r_out=", r_out, " envelopeØ=", 2 * r_out,
         " step_pitch=", step_pitch, " neck_len=", neck_len));
echo(str("  ladder-3 tols ", tols_3, "  ladder-2 tols ", tols_2));
echo(str("  ref_port_tol=", ref_port_tol, " emboss_h=", emboss_h));

if (part == "assembled") assembled();
else if (part == "reference-head") reference_head();
else if (part == "ladder-3") ladder_3();
else if (part == "ladder-2") ladder_2();
else if (part == "coupon") coupon();
else if (part == "mate-020") fit_mate(0.20);
else if (part == "mate-025") fit_mate(0.25);
else if (part == "mate-030") fit_mate(0.30);
else if (part == "mate-035") fit_mate(0.35);
else if (part == "mate-040") fit_mate(0.40);
else if (part == "mate-ctrl") fit_mate_ctrl();
else if (part == "cutaway") cutaway();
else assert(false, str("unknown part: ", part));
