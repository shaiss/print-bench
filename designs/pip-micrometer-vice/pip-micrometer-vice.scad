// pip-micrometer-vice — a print-in-place bench vice whose entire drivetrain
// comes off the bed assembled: a printed trapezoidal screw, captive in the
// housing, that converts a twist of the knob into clamping travel. Per brief
// #516. Reference consumer for docs/advanced-techniques.md Domain 3 (print-in-
// place kinematics) crossed with lib/threads-fdm.scad — the catalog's PIP
// shelf had sliders, hinges, gears and snap bearings but no screw joint
// printed in place, and the screw is the one that turns rotation into travel.
//
// THE MECHANISM (bench-vice architecture, not tip-pusher):
//   The SCREW is axially FIXED. It spins in a plain guide bore through the
//   rear block, a thrust collar on the shaft captured in a collar chamber
//   takes the clamping reaction, and the thread runs the whole channel
//   between the block's front face and a free tip near the fixed jaw. The
//   MOVING JAW carries the NUT: a boss wrapped around the screw (its groove
//   cut by the screw's own world-space cutter, so male and female cannot
//   drift), straddling a low centre saddle that carries the screw's
//   underside along its whole exposed length. Turning the knob screws the
//   jaw along the stationary screw.
//
// WHY THE SCREW NEVER DANGLES: a horizontal cylinder printing in mid-air
// prints its underside on nothing. Here every millimetre of the screw is
// supported by proximity — inside the guide bore (0.5 gap, the pip_hinge
// precedent), inside the jaw's nut (thread-interleaved at thread_tol), and
// along the exposed span over the saddle (crest 0.4 above the saddle top,
// the same near-floor discipline the battleship's doors ride the lid plate
// with). The knob is a disc standing on the base top behind the rear block,
// so its own underside prints one gap above the plate.
//
// THE GUIDEWAY (a deliberate deviation from the brief's rail/tab vocabulary,
// recorded in NOTES.md): a 40 mm wide jaw face cannot travel between rails
// that also carry castellated capture lips — the lips occupy the very y-band
// the face sweeps, and notching the clamping face for them would gut it.
// It is also unnecessary here: the battleship's lips exist because a door
// is not strung on anything, and this jaw is strung on the screw — the nut
// bore wraps the thread, so lift is bounded by thread_tol at every pose.
// What remains for the guideway is side keying: plain rail walls at clr_h
// (the brief's anti-rotation key clearance) plus the saddle straddle and
// the base-top floor ride. Measured free tip: ~2 deg (clearance / lever
// from the screw axis to the key planes, axis_z above the bed), ~0.4 mm of
// sway at the face top — enough to develop clamping force (the thread seats
// the jaw against the workpiece), noted as the design's slop.
//
// CLEARANCES (two tuned fits, both coupon-swept):
//   screw-in-nut   thread_tol = 0.30 radial on the trapezoid pair
//                 (lib/threads-fdm.scad: crest/root exact, flanks via
//                 flank_add — never retype the split)
//   jaw-in-guideway clr_h = 0.30 side (the anti-rotation key clearance the
//                 brief names), gap_z = 0.6 floor (the battleship's
//                 review-set door clearance, non-acoustic here)
//
// PRINT FLAT, base down, jaw axis and screw axis horizontal, NO SUPPORTS —
// a support inside the thread welds it, which is the thing being proven. The
// printed pose is opening = 12 mm: every stop face stands off (a zero-gap
// stop face prints as a seam that welds shut — the czs-slider lesson).
// All dimensions in millimetres.

use <printability.scad>
use <threads-fdm.scad>
include <styles/workshop-utility/style.scad>

/* [Brief dimensions — the geometry solves from these] */
// Jaw opening, full travel of the moving jaw (mm)
travel = 30;
// Jaw face width across the vice (mm)
jaw_w = 40;
// Jaw face height (mm)
jaw_d = 20;
// Screw nominal (crest) diameter (mm)
thread_d = 12;
// Screw lead, travel per turn (mm). Single-start, so pitch = lead.
screw_lead = 2.0;
// Thread starts (whole number; 1 = single-start per the brief)
thread_starts = 1;

/* [Screw-in-nut fit] */
// Radial thread clearance male-to-female (mm) — coupon sweeps it
thread_tol = 0.30;
// Radial thread depth (mm). Guarded by the lib's w_root < lead bound: at
// lead 2.0 the female cutter caps depth near (2 - 0.5 - flank_add(tol))/2;
// 0.55 keeps the coupon's 0.35 sweep station legal with margin.
thread_depth = 0.55;
// Guide bore clearance around the plain shaft (mm)
bore_tol = 0.5;
// Saddle-to-crest gap under the exposed thread (mm)
saddle_gap = 0.4;

/* [Jaw-in-guideway fit] */
// Side clearance, jaw to rail walls (mm) — the brief's anti-rotation key
// clearance; the coupon sweeps it
clr_h = 0.30;
// Floor gap, jaw underside over the base top (mm) — the battleship's
// review-set door clearance, proven over a plate at this value
gap_z = 0.6;

/* [Layout] */
// Base plate footprint (mm): x length, y width
base = [80, 58];
// Base plate thickness (mm)
base_t = 6;
// Screw / jaw centrelane height above the bed (mm)
axis_z = 15;
// Moving jaw body thickness along x (mm)
jaw_t = 16;
// Nut boss length on the jaw's rear (mm)
nut_len = 10;
// Saddle half-width (mm); the jaw's straddle slot clears it +0.3 a side
saddle_hw = 7;
// Rail wall thickness (mm)
wall_t = 4;
// Rail height above the base top (mm) — the side-keying band
rail_h = 12;
// Knob diameter (mm) — capped by the base top under it (asserted below)
knob_d = 17;
// Knob thickness (mm)
knob_t = 5;
// Printed pose: jaw opening (mm). PRINT AT 12; 0 closes the jaws.
print_opening = 12;
// Preview pose override, jaw opening (mm); undef = print pose
demo_opening = undef;

/* [Quality] */
// Production value (workshop-utility token). The thread helix pins its own
// seg = 64 at every call — the fit must not move with this preset.
$fn = style_fn;

/* [Part selector] */
// "" = the printable assembly at print pose | coupon | fitcheck |
// fitcheck_neg | fused | cutaway (gate machinery and preview poses)
part = "";

// ---- derived ----------------------------------------------------------------
pitch = screw_lead / thread_starts;
d_core = thread_d - 2 * thread_depth;             // 10.9 plain shaft dia
assert(thread_starts == 1 || abs(pitch - 2.0) > 1e-9,
       "brief assumes single-start lead 2.0; pitch = lead / starts");

// x frame (rear to front)
x_base0  = -43;                // base rear edge (the knob stands clear of it)
x_base1  = 37;                 // base front edge (fixed jaw plate 8 thick)
x_knob0  = -42;                // knob rear face
x_knob1  = x_knob0 + knob_t;   // knob front face, 1.0 clear of the block
x_blk0   = -36;                // rear block rear face
x_blk1   = -23;                // rear block front face = the channel line
x_thr0   = x_blk1 + 0.5;       // thread rear start (clear of the bore)
x_thr1   = 25.5;               // thread front end
x_tip1   = 27.5;               // screw tip, 1.5 clear of the fixed jaw face
x_face   = 29;                 // fixed jaw clamping face
x_rail1  = x_face;             // saddle/channel front line (the fixed jaw
                               // face; the rails themselves run to x_base1)
y_rail_i = jaw_w / 2 + clr_h;  // rail inner face (20.3)
y_rail_o = y_rail_i + wall_t;  // rail outer face (24.3)
nut_bore_d = thread_d + 2 * thread_tol;  // female crest dia (12.6); also the
                                         // jaw's plain clearance bore

// heights
z_face0 = base_t + gap_z;      // 6.6 — both jaw faces start here (the moving
                               // jaw rides gap_z over the base top; the fixed
                               // jaw is body, but its face ALIGNS — a matched
                               // pair is what clamps)
z_face1 = z_face0 + jaw_d;     // 26.6 — both faces end here: 40 x 20 exactly
saddle_top = axis_z - thread_d / 2 - saddle_gap;   // 8.6
slot_hw = saddle_hw + clr_h;   // jaw straddle-slot half-width — tracks the
                               // swept key fit, or the saddle would cap the
                               // sweep at 0.3 and stations above it would lie
slot_z1 = axis_z - thread_d / 2 + 0.3;             // 9.3 — slot ceiling clears
                                                   // the crest sweep

// moving jaw x extents at opening o: front face at x_face - o
function jaw_x0(o) = x_face - o - jaw_t;
function jaw_x1(o) = x_face - o;

// thread engagement in the nut at opening o (mm) — >= nut_len - 0.5 at both
// pose extremes, asserted in main()
function nut_engage(o) = min(jaw_x0(o) + nut_len, x_thr1) - max(jaw_x0(o), x_thr0);

// ---- the screw ---------------------------------------------------------------
// Built along world x: the frame below is rotated so its +z IS +x, origin
// at x = 0 — inner z-offsets in this module are world x values. The solid
// is rotation-symmetric, so the fitcheck envelope in part 3 can stand in
// for the exact helix: knob disc, plain core, crest cylinder over the
// thread zone, crest cylinder, thrust collar, tip cone.

cl_w = 2.5;                    // thrust collar width (mm)
cl_x0 = -31.25;                // collar rear face: centred in its chamber,
                               // 0.75 axial play to each chamber wall
cl_d = 16.4;                   // collar diameter (mm)

module screw() {
    translate([0, 0, axis_z]) rotate([0, 90, 0]) union() {
        // knob: disc standing on the base top BEHIND the rear block
        translate([0, 0, x_knob0]) knob_solid();
        // plain shaft from the knob face out to the tip
        translate([0, 0, x_knob1])
            cylinder(d = d_core, h = x_tip1 - x_knob1, $fn = 64);
        // the thread itself (male; thread_neck chamfers both lead-ins)
        translate([0, 0, x_thr0])
            thread_neck(thread_d, thread_depth, pitch, thread_starts,
                        x_thr1 - x_thr0, seg = 64);
        // thrust collar, spinning free in the rear block's chamber
        translate([0, 0, cl_x0]) cylinder(d = cl_d, h = cl_w, $fn = 64);
        // tip: 45 deg cone, the shaft's own lead-out
        translate([0, 0, x_thr1])
            cylinder(d1 = d_core, d2 = d_core - 2 * (x_tip1 - x_thr1),
                     h = x_tip1 - x_thr1, $fn = 64);
    }
}

// knob: chamfered disc, six shallow rim flutes for grip. Local z-up frame,
// z = 0 at the knob's rear face — the caller places it.
module knob_solid() {
    difference() {
        chamfered_cylinder(d = knob_d, h = knob_t, chamfer1 = 0.8);
        for (k = [0:5])
            rotate([0, 0, k * 60])
                translate([knob_d / 2 - 0.5, 0, knob_t / 2])
                    rotate([0, 90, 0])
                        cylinder(d = 1.4, h = 2.0, $fn = 24);
    }
}

// ---- the static body ---------------------------------------------------------
// Base + rear block + rails + saddle + fixed jaw, with the shaft's guide
// bore, the collar chamber and the two M5 mounting holes cut. The moving
// jaw and the screw are separate bodies (they must stay separable), so
// body() is the static half of the print only.

// plain guide bore for the shaft, world-placed, full length of the block.
// TEARDROP, not a round bore: a horizontal round bore closes its roof as a
// bridge whose chord passes 45 degrees near the top, 0.5 mm over a shaft
// that SPINS — bridge sag there welds the drivetrain, the one failure this
// design exists to prove cannot happen (the printability-review round's
// finding; the 45-degree roof prints self-supporting, lib/printability's
// teardrop_hole, point up).
module screw_guide_bore(tol) {
    translate([(x_blk0 + x_blk1) / 2, 0, axis_z]) rotate([0, 0, 90])
        teardrop_hole(d = d_core + 2 * tol, l = x_blk1 - x_blk0 + 2);
}

// collar chamber: the pocket the thrust collar spins in, sealed from the
// thread channel by the block's front wall (the thread starts 0.5 clear
// of it, so swarf never reaches the chamber). Same teardrop reasoning, at
// collar scale: the round roof would bridge ~12 mm over a rotating collar.
module collar_chamber(tol) {
    translate([cl_x0 + cl_w / 2, 0, axis_z]) rotate([0, 0, 90])
        teardrop_hole(d = cl_d + 2 * tol, l = cl_w + 2 * (0.75 + tol));
}

module body(fused = false) {
    // fused mode (the fusecheck control) shrinks the running clearances
    // 0.2 past touching so the assembly renders as one body — the proof
    // that the detector can still see a weld.
    bt = fused ? bore_tol - 0.2 : bore_tol;
    ct = fused ? 0.5 - 0.2 : 0.5;
    difference() {
        union() {
            // base plate, style-rounded: 80 x 58, AT the brief's 80 x 60
            // footprint cap
            translate([x_base0, -base[1] / 2, 0])
                rounded_box([base[0], base[1], base_t],
                            r = style_corner_r,
                            bottom_chamfer = style_edge_chamfer);
            // rear block: base top to above the collar chamber's teardrop
            // point — 0.8 * chamber dia (teardrop_hole's tip height) + a
            // 1.2 wall. The round-bore predecessor stopped at
            // axis_z + d_core / 2 + 4, which the teardrop points would
            // breach (guide bore tip z 24.5, chamber tip z 28.9).
            translate([x_blk0, -y_rail_o, base_t])
                cube([x_blk1 - x_blk0, y_rail_o * 2,
                      axis_z + 0.8 * (cl_d + 2 * 0.5) + 1.2 - base_t]);
            // rail walls: the jaw's side key, inner faces clr_h off the
            // 40 mm jaw width, full channel length. They run to the base
            // FRONT edge, not just the fixed jaw face: ending at x_face
            // left the rail end meeting the flank gusset's side plane on a
            // zero-area line, and that pinch exported as two non-manifold
            // edges (gate iteration 1). Overlapping the gusset in x makes
            // the contact a face — the rear block sits on the base the
            // same way and renders manifold.
            for (s = [-1, 1])
                translate([x_blk1, s > 0 ? y_rail_i : -y_rail_o, base_t])
                    cube([x_base1 - x_blk1, wall_t, rail_h]);
            // centre saddle: carries the screw's whole exposed underside
            translate([x_blk1, -saddle_hw, base_t])
                cube([x_rail1 - x_blk1, saddle_hw * 2, saddle_top - base_t]);
            // fixed jaw: front clamping face, 40 x 20 at x_face, 8 thick
            // so the style's r4 corner reads honestly
            translate([x_face, -jaw_w / 2, z_face0])
                rounded_box([x_base1 - x_face, jaw_w, jaw_d],
                            r = style_corner_r, bottom_chamfer = 0);
            // flank gussets: tie the rail ends and the fixed jaw into the
            // base's front corners
            for (s = [-1, 1])
                translate([x_face, s > 0 ? y_rail_o : -base[1] / 2, base_t])
                    cube([x_base1 - x_face, base[1] / 2 - y_rail_o, rail_h]);
        }
        // the two M5 base through-holes on the brief's 40 mm x-grid. M5 is
        // the workshop-utility pack's one deliberate deviation (its hole
        // vocabulary is M3) — recorded in NOTES.md. Depth reaches THROUGH
        // the saddle (both ±20 sit under it, y ±7): the cut tops out
        // saddle_top + 0.15, which clears the screw's lowest crest
        // (axis_z - thread_d/2 = 9.0) by 0.25 — pinned by the assert in
        // main(). base_t + 2 alone left a 1.6 mm cap of saddle over each
        // hole: positionally right, not a through-hole at all.
        for (hx = [-20, 20])
            translate([hx, 0, -1]) screw_hole("M5", saddle_top + 1.15);
        // shaft bore + collar chamber (skip in fused mode: the overlaps
        // themselves are the weld being proven)
        if (!fused) {
            screw_guide_bore(bt);
            collar_chamber(ct);
        }
    }
}

// ---- the moving jaw ----------------------------------------------------------
// One 40 x jaw_t x 20 block: its front face IS the clamping face (matched
// to the fixed jaw's), straddling the saddle, strung on the screw. grow
// serves the fitcheck negative control (widened/dropped blank that must
// bite); fused flips every clearance past touching for the weld control.

module jaw(opening = print_opening, grow = 0, fused = false) {
    x0 = jaw_x0(opening);
    hw = jaw_w / 2 + grow;                    // neg mode: bites the rails
    z0 = z_face0 - grow;                      // neg mode: bites the floor
    shw = fused ? saddle_hw - 0.2 : slot_hw;  // fused: bites the saddle
    sz1 = fused ? slot_z1 + 0.2 : slot_z1;
    difference() {
        translate([x0, -hw, z0])
            rounded_box([jaw_t, hw * 2, z_face1 - z0],
                        r = style_corner_r, bottom_chamfer = 0);
        // saddle straddle slot, through the jaw's full length
        translate([x0 - 1, -shw, z0 - 0.1])
            cube([jaw_t + 2, shw * 2, sz1 - z0 + 0.1]);
        // the nut: plain bore + thread groove, cut by the screw's own
        // world-space cutter so male and female cannot drift. The plain
        // bore runs past the tip so the closed-pose jaw front stays
        // clear of the tip cone.
        if (fused)
            screw_thread_cutter(tol = 0.05, shrink = 0.4);
        else
            screw_thread_cutter();
    }
}

// female cutter for the nut, WORLD-placed (the screw never translates, so
// generating the nut with the exact solid that occupies it is exact at
// every pose). The lib's cutters are z-up, so they are rotated onto the x
// axis like every other screw element here. shrink pulls the plain bore
// below the crest for the fused control; the groove's own tol stays >= 0
// (a lib guard).
module screw_thread_cutter(tol = thread_tol, shrink = 0) {
    translate([x_thr0 - 1, 0, axis_z]) rotate([0, 90, 0])
        cylinder(d = d_core + 2 * tol - 2 * shrink,
                 h = x_tip1 + 3 - x_thr0 + 1, $fn = 64);
    translate([x_thr0, 0, axis_z]) rotate([0, 90, 0])
        thread_bore_cut(thread_d, thread_depth, pitch, thread_starts,
                        x_thr1 - x_thr0, tol, over = 1, seg = 64);
}

// ---- fitcheck parts ----------------------------------------------------------

// Every pairwise intersection across the three printed bodies at the pose
// extremes. The motion is a monotone translation and every clearance in
// play (rails 0.3, floor 0.6, saddle 0.3, fixed face at closed) is
// pose-independent, so the extremes bound the whole travel. 0.5 stands the
// clamping faces just off closure — o = 0 is closure contact, which is the
// vice working, not a collision. RENDER MUST BE EMPTY.
module fitcheck() {
    for (o = [0.5, travel]) {
        intersection() { body(); jaw(o); }
        intersection() { screw(); jaw(o); }
    }
    intersection() { body(); screw(); }
}

// negative control: the same jaw grown 0.4 every way it slides — it MUST
// bite the rails and the base floor, proving the empty check can fail.
// RENDER MUST BE NON-EMPTY.
module fitcheck_neg() {
    intersection() { body(); jaw(opening = 1, grow = 0.4); }
}

// the known-fused control for ci.fusecheck: every running clearance
// flipped past touching — one body, and the detector must say so.
module fused_assembly() {
    body(fused = true);
    screw();
    jaw(opening = print_opening, fused = true);
}

// ---- the coupon --------------------------------------------------------------
// Two fits, six cells, one plate. Row 1: screw/nut PAIRS (print, then screw
// each nut onto its stub) at three thread_tol stations — digits 1/2/3 for
// 0.25/0.30/0.35 mm. Row 2: channel/slider pairs printed in place at three
// clr_h stations — A/B/C for 0.25/0.30/0.35 mm. Pick the station that
// turns/slides smooth without slop, set the parameter to its value,
// re-render, print. The coupon is the arithmetic whole: 7 bodies (plate +
// stubs + channels merged, 3 nuts, 3 sliders).

cp_t = 3.5;      // coupon plate thickness (mm)
cp_pad = [32, 24];  // one cell's pad footprint (mm)
cp_tols = [0.25, 0.30, 0.35];

// one screw/nut cell: stub stands on the pad, nut beside it
module coupon_thread_cell(tol, idx) {
    // stub x: its Ø12 crest reaches x + 6, and the nut's near face is at
    // x 12 — at 7 the two overlapped 1 mm of solid (the bore is centred on
    // the nut, so the overlap sat in nut wall), welding nut-to-stub and so
    // nut-to-plate even after the 0.6 pad lift: that lift cured the bed-face
    // weld, not this lateral one (fusecheck still read 4 bodies, iter 2).
    // 5.4 + 6 = 11.4 leaves the same 0.6 the nut rides over the pad.
    translate([5.4, 0, cp_t])
        thread_neck(thread_d, thread_depth, pitch, thread_starts, 14,
                    seg = 64);
    difference() {
        // nut rides 0.6 over the pad — the battleship's proven
        // flat-over-a-plate clearance. Flush on the pad it printed as a
        // bed-level face weld (fusecheck iteration 1: the coupon read 4
        // bodies, not 7 — plate + 3 welded nuts + 3 sliders), the same
        // zero-gap-stop-face lesson as the print pose.
        translate([12, -8, cp_t + 0.6]) cube([16, 16, 9]);
        translate([20, 0, cp_t - 1])
            cylinder(d = d_core + 2 * tol, h = 11, $fn = 64);
        translate([20, 0, cp_t + 0.6])
            thread_bore_cut(thread_d, thread_depth, pitch, thread_starts,
                            9, tol, over = 1, seg = 64);
        // station digit on the camera-facing (+y) nut face — the one surface
        // nothing occludes. A plate strip beside the row is unreadable at any
        // tilt: at 52-deg elevation the sightline to a strip 3.9 mm in front
        // of the nut passes through it at z 7, mid-face of its 3.5..12.5 span
        // (measured — digits proven present in the mesh, invisible in the
        // render). rotate([90,0,0]) stands the glyph upright but extrudes it
        // -y — away from a +y-side reader, i.e. seen from behind its own
        // writing plane, which mirrors it (verified: the rendered glyph read
        // as its mirror's mirror). Upright AND front-facing is a reflection,
        // not a rotation, so the mirror([1,0,0]) is load-bearing. It flips
        // about the halign="center" origin, so the glyph stays put.
        translate([20, 8.2, cp_t + 0.6 + 2.8]) rotate([90, 0, 0])
            linear_extrude(1.4)
                mirror([1, 0, 0])
                    text(idx, size = 5.5, halign = "center",
                         font = "Liberation Sans:style=Bold");
    }
}

// one channel/slider cell: slider printed in place on the pad's rails
module coupon_guide_cell(clr, idx) {
    ch = 12;        // channel length (mm)
    // rails + centre stub, all one with the plate
    for (s = [-1, 1])
        translate([0, s > 0 ? 10 + clr : -10 - clr - 3, cp_t])
            cube([ch, 3, 5]);
    translate([0, -3, cp_t]) cube([ch, 6, 2.6]);
    // slider: 20 wide, straddling the stub, 0.6 floor gap over the pad
    difference() {
        translate([1, -10, cp_t + 0.6]) cube([10, 20, 8]);
        // straddle groove over the stub: BOTH side interfaces track the
        // station (like slot_hw in the vice), not just the outer rails
        translate([0, -(3 + clr), cp_t - 1]) cube([ch, 6 + 2 * clr, 4.3]);
        // label: letter cut into the slider's top face
        translate([3.5, -1.6, cp_t + 0.6 + 8 - 0.8])
            linear_extrude(1)
                text(idx, size = 4, font = "Liberation Sans:style=Bold");
    }
}

module coupon() {
    labels = ["A", "B", "C"];
    union() {
        // plate: 3 columns x 2 rows. Station labels live on the parts they
        // label, not the plate between the rows: digits on the nut front
        // faces (camera-facing, nothing above them), letters on the slider
        // tops. A label cut must belong to the solid's own difference() —
        // OpenSCAD silently no-ops a subtraction that misses it (the first
        // attempt engraved the nut's air and vanished from the render —
        // caught by an edge-density measurement, not a look).
        translate([0, -(cp_pad[1] * 2 + 6) / 2, 0])
            rounded_box([cp_pad[0] * 3 + 4, cp_pad[1] * 2 + 6, cp_t],
                        r = style_corner_r,
                        bottom_chamfer = style_edge_chamfer);
        for (i = [0:2]) {
            // row 1 (rear, +y): thread cells
            translate([2 + i * cp_pad[0], cp_pad[1] / 2 + 3, 0])
                coupon_thread_cell(cp_tols[i], str(i + 1));
            // row 2 (front, -y): guide cells, centred on the channel. The
            // cell origin sits 1.7 inboard of the row line so the -y rail
            // (channel centre - 10 - clr - 3) stays on the plate, not
            // cantilevered past its edge.
            translate([8 + i * cp_pad[0], -(cp_pad[1] / 2 + 1.7), 0])
                coupon_guide_cell(cp_tols[i], labels[i]);
        }
    }
}

// ---- cutaway preview ---------------------------------------------------------
// Sectioned at y = 0.05: the -y half of the assembly, showing the channel,
// the straddle slot, the nut wrapping the screw and the collar chamber.

module cutaway() {
    difference() {
        assembly();
        translate([x_base0 - 2, 0.05, -1])
            cube([base[0] + 4, base[1], z_face1 + 2]);
    }
}

module assembly() {
    o = is_undef(demo_opening) ? print_opening : demo_opening;
    body();
    screw();
    jaw(o);
}

// ---- dispatch + evidence -----------------------------------------------------
// part: "" (the printable assembly, at print pose) | coupon | fitcheck |
//       fitcheck_neg | fused | cutaway

module main() {
    if (part == "")
        assembly();
    else if (part == "coupon")
        coupon();
    else if (part == "fitcheck")
        fitcheck();
    else if (part == "fitcheck_neg")
        fitcheck_neg();
    else if (part == "fused")
        fused_assembly();
    else if (part == "cutaway")
        cutaway();
    else
        assert(false, str("unknown part: ", part));

    // ---- G4 evidence: derived off the parameters the mesh is built from;
    // the measured-off-export proof lives in the PR audit table.
    assert(nut_engage(0) >= nut_len - 0.5
           && nut_engage(travel) >= nut_len - 0.5,
           str("nut leaves the thread at a pose extreme: ",
               nut_engage(0), " closed / ", nut_engage(travel), " open"));
    assert(axis_z - knob_d / 2 >= base_t + 0.5,
           "knob must ride >= 0.5 above the base top");
    assert(saddle_gap >= 0.35, "saddle-to-crest gap below the 0.35 weld floor");
    assert(print_opening >= 2, "printed pose must stand every stop face off");
    assert(x_tip1 <= x_face - 1.5, "screw tip must clear the fixed jaw face");
    assert(jaw_x0(travel) >= x_blk1 + 4,
           "jaw leaves the rails at full open");
    assert(saddle_top + 0.15 <= axis_z - thread_d / 2 - 0.2,
           "M5 through-cut must clear the screw's lowest crest by >= 0.2");
    echo(str("G4: lead ", screw_lead, " mm/turn, single-start (pitch ",
             pitch, "), nominal dia ", thread_d, " mm"));
    echo(str("G4: travel ", travel, " mm; jaw faces ", jaw_w, " x ", jaw_d,
             " mm, z ", z_face0, "..", z_face1));
    echo(str("G4: base footprint ", base[0], " x ", base[1],
             " mm (brief cap 80 x 60)"));
    echo(str("G4: key clearance clr_h = ", clr_h,
             " mm; thread_tol = ", thread_tol, " mm (both coupon-swept)"));
    echo(str("G4: nut engagement ", nut_engage(0), " mm closed / ",
             nut_engage(travel), " mm open (nut_len ", nut_len, ")"));
    echo(str("G4: M5 mounts on a 40 mm x-grid at (±20, 0)"));
}

main();
