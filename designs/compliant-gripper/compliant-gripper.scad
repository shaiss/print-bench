// compliant-gripper — a monolithic print-in-place PARALLEL-JAW gripper that
// comes off the plate assembled and working. Tier-3 reference design: the
// fusion of all three domains of docs/advanced-techniques.md in one part.
//
//   Domain 1 (compliant): each jaw rides a parallelogram of two leaf flexures
//     (in-plane S-bend, flex in-layer — the #1 orientation rule), and the
//     clamped state is held by a pre-buckled ARCH (the bistable-toggle solve)
//     whose apex tip rides a VALLEY detent on the actuator wing: push past
//     the crest and the tip drops into the valley, where the deflected arch
//     preloads it against the 80° hold face — the wedge turns that preload
//     into more holding force than the jaws' spring reaction (asserted), so
//     the gripper stays clamped with no force applied. The arch is
//     bistable-capable by construction (rise/t >= 2.3, asserted) but the
//     detent runs it in its pre-toggle regime — NOTES.md records why the
//     full-flip coupling was declined (it needs a follower body the one-part
//     constraint forbids).
//   Domain 3 (print-in-place): the push-actuator prints already captive in
//     its race — walled in XY between two side walls, roofed by a bridged
//     rail it cannot pass, held down over its nose by the jaw pin-arms, with
//     its travel bounded by its own cam notch ends (the captive-spinner
//     capture recipe, xy/z split and all).
//   Domain 2 (supports): printed FLAT. Every moving interface is either a
//     vertical wall gap (spread-limited) or a horizontal roof gap quantized to
//     whole layers (sag-limited) — the CC3 anisotropy, two different numbers.
//     Every fixed feature stands on solid material or a support shelf (the
//     corridor shelf under the arch beam, the wing table under the detent
//     band); the part's two deliberate bridges are the race rail's underside
//     and that wing table (each spanning between fixed walls).
//
// How it grips: the jaws rest OPEN (gap 33 mm for a Ø25 rod + 8 mm of travel).
// Push the rear tab forward: the plunger's diagonal edge-notch cams the jaw
// pin inward — the jaws close IN PARALLEL (the leaf parallelogram keeps the
// grip faces mutually parallel) — the pads pass the rod faces by 0.5 mm of
// flexure preload, the detent tip rides the 45° ramp over the crest, and the
// flexures seat it against the steep wall: held, zero applied force. Pull the
// tab back: the tip climbs the release face, the flexures push the jaws open.
//
// Technique lineage (the point of the tier — reused recipes, not re-derived):
//   - #387 captive-spinner: the xy/z clearance split, quantized roof gaps,
//     the captive-race capture and the break-free first motion.
//   - #388 let-folding-panel: the flexure guards (min leaf 1.2) and the
//     root-fillet discipline applied to every flexure root.
//   - #389 bistable-toggle: the arch solve — yc = h(1−cos(2πx/l))/2,
//     f_s·l³/(E·I·h) = 1486.57, u_tr = 1.98·h, bistability h/t >= 2.3.
//
// All dimensions in millimeters.

/* [Grip] */
// Diameter of the gripped cylinder (mm)
grip_od = 25;
// Total jaw travel, open → clamped (mm). Brief requires >= 8.
jaw_travel = 8;
// Grip-zone length along the rod axis (mm)
grip_len = 32;

/* [Jaw flexures (parallelogram leaves)] */
// Leaf thickness, the bending direction, Y (mm)
leg_t = 2.2;
// Leaf length between root and jaw (mm)
leg_l = 55;
// Distance between a jaw's two leaves (mm) — sets rotation stiffness
leg_spacing = 6;
// Leaf depth in Z (mm) — must stay clear of the detent wing band above
leg_z = 3.8;

/* [Actuator] */
// Notch ramp angle off the travel axis (deg) — sets force ratio and stroke
ramp_ang = 30;
// Flexure preload at full closure: the drive overcloses past the rod faces (mm)
preload = 0.5;
// Plunger blade width (mm)
plunger_w = 10;

/* [Detent arch — the bistable-toggle solve] */
// Arch span between posts (mm) — the "l"
arch_span = 120;
// Mid-rise of the arch (mm) — the "h". Bistable iff h/t >= 2.3.
arch_rise = 3.8;
// Arch beam thickness, the in-plane bending direction (mm) — the "t"
arch_t = 1.6;
// Arch out-of-plane width, the extrude height (mm) — the "w" in I = w·t³/12
arch_w = 2.2;
// Detent VALLEY: how far the seated tip lifts the arch (mm) — the preload
// that makes R(seat) > 0, without which no wall angle can hold the drive
seat_u = 2.2;
// Detent crest lift (mm) — must stay under arch_rise or the arch inverts
crest_u = 3.0;
// Hold-face angle off horizontal (deg). The seat holds by tan(hold_ang)·R;
// 80° keeps the wedge ratio ~5.7:1 so even the pessimistic R model holds.
hold_ang = 80;
// Assumed PETG tensile modulus (MPa) for the echoed force estimate
E_modulus = 1550;

/* [Structure] */
// Base plate thickness (mm)
base_t = 8;
// Jaw block height (mm)
jaw_h = 18;
// Pocket floor thickness under the jaw sweep (mm)
pocket_t = 3;
// Race side-wall top / rail top (mm)
race_h = 17;

/* [Clearances — the CC3 anisotropy (#387 recipe)] */
// Layer height the roof gaps quantize to (mm)
layer_h = 0.2;
// Vertical-wall gap (mm) — spread-limited, keep >= one line width
xy_tol = 0.2;
// Roof/floor gaps, in WHOLE LAYERS — sag-limited
z_layers = 2;

/* [Quality] */
// Iterating: 64. Production: 128.
$fn = 96;

// ---- derived -----------------------------------------------------------
z_tol    = z_layers * layer_h;           // 0.4 — every horizontal gap
half     = grip_od / 2;                  // clamped jaw faces reach ±12.5
open_f   = half + jaw_travel / 2;        // open jaw inner face, ±16.5
d_jaw    = jaw_travel / 2 + preload;     // 4.5 — notch drop per jaw
float_z  = pocket_t + z_tol;             // 3.4 — jaw underside over the pocket
pl_z0    = base_t + z_tol;               // 8.4 — plunger band floor
pl_z1    = pl_z0 + 4.2;                  // 12.6 — plunger band top
arm_z0   = pl_z1 + z_tol;                // 13.0 — pin arms ride over the blade
arch_z0  = pl_z0 + 1;                    // 9.4 — arch web sits inside the band
// x stations (mm)
x_tab0   = 2;                            // push-tab rear face
x_race0  = 8;    x_race1 = 44;           // race side walls
x_rail0  = 17;                           // rail front (the tab swings past under it)
x_twr0   = 54;   x_twr1 = 62;            // flexure anchor towers
x_leg0   = x_twr1;                       // 62 — leaf roots
x_leg1   = x_leg0 + leg_l;               // 112 — leaves meet the carriage
pin_x    = 103;                          // jaw pin centre in X (ground)
nose_f   = 105;                          // blade nose face (plunger-local X)
x_pad0   = x_leg1 + 3;   x_pad1 = x_pad0 + grip_len;   // grip zone, past the leaf tips
x_base1  = x_pad1 + 4;                   // 150 — base front edge
x_arch0  = 10;
x_arch1  = x_arch0 + arch_span;          // 130 — arch posts
apex_x   = x_arch0 + arch_span / 2;      // 70 — ground x of the detent tip
// y stations (mm)
y_race   = plunger_w / 2 + xy_tol;       // 5.2 — race wall inner face
race_wt  = 3.8;
y_pocket = 11.7;                         // pocket inner edge (base step)
jaw_w    = 12;                           // jaw block width in Y
leg_y_in = 17.5;  leg_y_out = leg_y_in + leg_spacing;   // leaf lines
y_wing1  = 20;                           // detent wing outer edge
arch_mid = 33;                           // arch centreline at the posts
pin_y    = 9.5;                          // pin centre in Y at open (−y jaw)
// actuator: stroke, leaf stiffness/strain, detent force budget
stroke   = d_jaw / tan(ramp_ang);        // plunger advance, full close
k_leaf   = 12 * E_modulus * (leg_z * leg_t^3 / 12) / leg_l^3;
k_jaw    = 2 * k_leaf;                   // both leaves in parallel
jaw_react= 2 * k_jaw * d_jaw * tan(ramp_ang);   // plunger reaction, both jaws
grip_f   = k_jaw * preload;              // pad force on the rod at the seat
strain   = 3 * leg_t * d_jaw / (leg_l * leg_l);      // guided S-bend
I_arch   = arch_w * arch_t^3 / 12;       // w·t³/12 — bending is in-plane
f_snap   = 1486.57 * E_modulus * I_arch * arch_rise / arch_span^3;
u_travel = 1.98 * arch_rise;
// detent tooth (plunger-local X): the tip rides the 45° advance ramp over the
// crest and SEATS IN A VALLEY that holds the arch deflected seat_u — the
// preload that gives the hold face a spring to push against. The valley is
// placed so the tip footprint is on the floor both at full advance (no rod)
// and where the pins jam with a Ø25 rod in (stroke−0.63): the seat must be
// reachable with the payload present, or the gripper parks on the crest and
// pops back. The −x end of the valley is a step down to the wing flank; the
// tip never passes it (release stops at the open pose).
pin_r      = 1.5;                                  // jaw pin radius
seat_clamp = apex_x - stroke;
valley_x1  = seat_clamp + pin_r + xy_tol + 0.59;   // valley +x edge (hold-face base)
valley_x0  = valley_x1 - 3.3;                      // valley −x edge (covers tip ± slop)
crest_x    = valley_x1 + (crest_u - seat_u) / tan(hold_ang);
ramp_x     = crest_x + crest_u;                    // 45° rideable advance face
// Arch apex resistance R(u) — the detent's spring. Two-term conservative
// model (NOTES.md derives it and brackets it against #389's f_s):
//   bending   192·E·I/l³ · u          (small-deflection fixed-fixed beam)
//   catenary  4·T(u)·u/l, T = E·A·ε/l (flattening a fixed-end arch must
//                                     stretch it: ε = π²(2hu−u²)/4l)
function arch_eps(u) = 9.8696 * (2 * arch_rise * u - u * u) / (4 * arch_span);
function arch_R(u) =
    (192 * E_modulus * I_arch / arch_span^3) * u
    + 4 * (E_modulus * arch_w * arch_t * arch_eps(u) / arch_span) * u / arch_span;
R_seat   = arch_R(seat_u);       // hold capacity = tan(hold_ang) · R_seat
R_crest  = arch_R(crest_u);
F_release = tan(hold_ang) * R_crest * 0.6;   // pull past the crest (drive falling)
// print-support shelving (round 2 — Jane's review, PR #410): fixed material
// under everything the frame used to hang over the pocket void. All derived
// from the moving parts' own envelopes, so the clearances hold by construction.
shelf_top = arch_z0 - z_tol;         // 9.0 — corridor shelf top; beam floats z_tol
shelf_y0  = leg_y_out + leg_t / 2 + 1;   // 25.6 — 1 mm past the leaf tips' rest
                                         // edge (leaves snap back +y on release)
shelf_y0j = open_f + jaw_w + 1;      // 29.5 — same margin past the jaw block edge
x_shelf_j = x_leg1 - 6 - xy_tol;     // where the corridor shelf steps for the jaw
table_z1  = pl_z0 - z_tol;           // 8.0 — wing table top; the band floats z_tol
table_z0  = float_z + leg_z + z_tol; // 7.6 — table underside roofs the leaf sweep
pad_y0    = y_wing1 + crest_u + xy_tol;  // 23.2 — tip pad clear of the tooth path

echo(str("actuator stroke = ", stroke, " mm (jaw travel ", jaw_travel,
         " + ", preload, " preload via ", ramp_ang, " deg notch)"));
echo(str("jaw flexures: k = ", k_jaw, " N/mm per jaw; root strain = ",
         strain * 100, " % (target < 2.5 %)"));
echo(str("grip: pad force at the clamped seat = ", grip_f,
         " N; jaw drive the detent must hold = ", jaw_react, " N"));
echo(str("detent arch: u_tr = 1.98 h = ", u_travel, " mm; toggle f_s ~ ",
         f_snap, " N at E = ", E_modulus, " MPa — coupon measures"));
echo(str("detent hold: R(seat_u=", seat_u, ") = ", R_seat, " N; wedge tan(",
         hold_ang, ") -> hold ", tan(hold_ang) * R_seat, " N vs jaw drive ",
         jaw_react, " N (x", tan(hold_ang) * R_seat / jaw_react,
         "); release pull ~ ", F_release, " N"));

module guards() {
    assert(jaw_travel >= 8, "brief requires jaw travel >= 8 mm");
    assert(leg_t >= 1.2, "flexure leaf under 3 perimeters — it will tear");
    assert(strain <= 0.025, "flexure root strain over 2.5 % — fatigue risk");
    assert(arch_rise / arch_t >= 2.3,
           "arch too flat to be bistable (rise/t < 2.3) — it would just spring back");
    assert(arch_t >= 1.2, "arch beam under 3 perimeters");
    assert(f_snap > 2 && f_snap < 4, "predicted toggle outside 2–4 N — retune");
    assert(arch_mid - arch_rise - arch_t > leg_y_out + leg_t,
           "arch beam corridor clips the outer flexure leaf");
    assert(nose_f > x_race1 + 4, "blade nose too close to the race front");
    assert(x_race0 + 0.2 + stroke < x_rail0 - 0.5,
           "the tab would hit the rail's front face at full advance");
    assert(float_z + leg_z <= pl_z0 - z_tol,
           "flexure tops reach the detent wing band — the wing would fuse");
    assert(table_z1 - table_z0 >= 2 * layer_h,
           "wing table under 2 layers thick — raising z_layers eats the band between the leaf tops and the wing; raise base_t by the same amount");
    // detent force vs jaw stiffness — the brief's named failure mode. The
    // clamped jaws drive the plunger backwards with jaw_react; the valley
    // preload makes the arch push the tip into the hold face with R_seat,
    // and the wedge turns that into tan(hold_ang)·R_seat of holding force.
    // Without the preload (R(0)=0) no wall angle holds — it just climbs.
    assert(tan(hold_ang) * R_seat >= 1.25 * jaw_react,
           "detent cannot hold the jaw drive — the gripper unclamps itself");
    assert(crest_u < arch_rise,
           "detent crest would invert the arch (u_max >= rise) — detent dies");
    assert(F_release <= 8,
           "release pull too heavy — flatten hold_ang or cut seat preload");
    // the cam must BITE: the notch has to open through the blade's edge or
    // the pin is never driven (formula-level; the drive_mouth fitcheck is
    // the same proof on the built geometry)
    assert(-(pin_y - d_jaw) + pin_r + xy_tol > -plunger_w / 2 + 0.1,
           "notch never opens through the blade edge — the drive is disconnected");
}

// ============ fixed frame =================================================
// Base: solid 0…pocket_t everywhere, then pocket_t…base_t with the jaw-sweep
// pocket and the rod trough cut, so the jaws and leaves float z_tol over a
// floor instead of fusing into the plate.
module plate_2d() { translate([0, -35.5]) square([x_base1, 71]); }
module pocket_cut_2d() {
    for (s = [1, -1])
        translate([x_leg0, s > 0 ? y_pocket : -35.5])
            square([x_base1 - x_leg0, 35.5 - y_pocket]);
}
module trough_cut_2d() {
    translate([x_pad0, -(grip_od / 2 + 0.4)]) square([grip_len, grip_od + 0.8]);
}

module race_walls_2d() {
    for (s = [1, -1])
        translate([x_race0, s > 0 ? y_race : -y_race - race_wt])
            square([x_race1 - x_race0, race_wt]);
}
// The rail is a lid over the blade, anchored on both walls; its underside is
// one of the part's two deliberate bridges (the wing table is the other),
// so the blade's roof gap is sag-limited.
module rail_2d() {
    translate([x_rail0, -y_race - race_wt + 0.2])
        square([x_race1 - x_rail0, 2 * (y_race + race_wt) - 0.4]);
}

module towers_2d() {
    for (s = [1, -1])
        translate([x_twr0, s > 0 ? leg_y_in - 2.5 : -(leg_y_out + 2.5)])
            square([x_twr1 - x_twr0, leg_spacing + 5]);
}

// ============ jaws ========================================================
// Jaw A is the −y jaw (mirrored for +y). Drawn in the OPEN pose; every
// interface is a clearance gap, so the body is pose-independent.
module jaw_block_2d() {
    translate([x_leg1 - 6, -open_f - jaw_w]) square([x_base1 - x_leg1 + 6, jaw_w]);
}
// Flexure leaves for one jaw side: thin in Y, long in X, rooted 2 mm inside
// the tower and ending 2 mm inside the jaw block so both ends truly fuse.
module leaves_2d(side) {
    for (yy = [leg_y_in, leg_y_out])
        translate([x_leg0 - 2, side * yy - leg_t / 2]) square([leg_l + 4, leg_t]);
}
module jaw_arm_2d() {
    hull() {
        translate([x_leg1 - 6, -open_f - 5]) square([6, 5]);        // root
        translate([pin_x - 4.5, -pin_y - 4.5]) square([9, 9]);      // boss
    }
}

// ============ actuator ====================================================
// Plunger, drawn at s = 0. The notch is the pin's plunger-local path: the pin
// is fixed in X and slides from −pin_y (open) to −(pin_y − d_jaw) (closed)
// while the plunger advances, so the channel is that diagonal. It is an
// EDGE-notch, open at the blade's side: the pin arm wraps over the blade and
// the post drops into the channel.
module plunger_2d() {
    difference() {
        union() {
            // tab: rides between the race walls; taller than the rail's
            // underside so it can never escape over it
            translate([x_tab0, -plunger_w / 2])
                square([x_race0 - x_tab0 + 0.2, plunger_w]);
            // blade + nose, one profile between the race walls
            translate([x_race0, -plunger_w / 2])
                square([nose_f - x_race0, plunger_w]);
            // detent wing outboard on +y, beside the blade
            translate([apex_x - 12, plunger_w / 2])
                square([24, y_wing1 - plunger_w / 2]);
            // detent tooth: 45° advance ramp up to the crest, 80° hold face
            // down into the VALLEY — the seated tip is held there by the
            // preloaded arch pressing it against the hold face (guards()
            // asserts that wedge actually beats the jaw drive)
            translate([0, y_wing1 - 0.01])
                polygon([[valley_x0, 0], [valley_x0, seat_u],
                         [valley_x1, seat_u], [crest_x, crest_u], [ramp_x, 0]]);
        }
        notch_2d();
        mirror([0, 1]) notch_2d();
    }
}
module notch_2d() {
    // The FULL pin path, a→b, grown by the clearance. The bite this opens
    // through the blade's edge is the cam itself: the tangent wall is what
    // drives the pin, and the far cap is the stroke stop. (An earlier draft
    // hullled A with a point 2r short of B — with these parameters the
    // truncated cap landed exactly tangent to the blade edge, cut ZERO
    // material, and left the drive disconnected: every gate green, jaws that
    // could not close. `drive_mouth` in ci.fitchecks now proves the mouth
    // exists on the built geometry.)
    a = [pin_x, -pin_y];                       // pin at s = 0 (open)
    b = [pin_x - stroke, -(pin_y - d_jaw)];    // pin at s = stroke (closed)
    r = pin_r + xy_tol;
    hull() {
        translate(a) circle(r);
        translate(b) circle(r);
    }
}

// ============ detent arch (#389 solve) ====================================
// Beam corridor at arch_mid bowing −y toward the wing; posts drop to the base;
// the apex carries a short inboard tip that rides the wing's detent profile.
module arch_beam_2d() {
    NS = 60;
    // yc over LOCAL x (0..span): posts at 0, apex of the dip at span/2 —
    // i.e. world apex_x, where the detent tip rides. (Feeding world x here
    // skewed the whole arch: full dip at x_arch0+50, the tip on a flank,
    // and the built rise/t measured 1.83 — under the 2.3 bistable bar the
    // guard exists to hold.)
    function yc(x) = -arch_rise * (1 - cos(360 * (x - x_arch0) / arch_span)) / 2;
    top = [for (i = [0 : NS]) let (x = x_arch0 + arch_span * i / NS)
              [x, arch_mid + yc(x) + arch_t / 2]];
    bot = [for (i = [NS : -1 : 0]) let (x = x_arch0 + arch_span * i / NS)
              [x, arch_mid + yc(x) - arch_t / 2]];
    polygon(concat(top, bot));
}
module arch_tip_2d() {
    // from the wing flank up past the beam's apex (overlap = fused)
    translate([apex_x - 1.5, y_wing1 + xy_tol])
        square([3, arch_mid - arch_rise + 0.5 - (y_wing1 + xy_tol)]);
}
module arch_posts_2d() {
    for (xx = [x_arch0, x_arch1])
        translate([xx - 2.5, arch_mid - arch_t - 1]) square([5, 4]);
}

// ============ assembly ====================================================
// Print-support shelving (round 2, Jane's block on PR #410). Three fixed
// pieces, none touching a moving part — every top face sits exactly z_tol
// under what floats over it:
//   corridor shelf — under the arch beam's whole span (frame under frame; the
//     beam keeps its full Y freedom, it just floats 2 layers over the shelf
//     instead of over the pocket void). Steps outboard past the jaw blocks.
//   wing table — a 2-layer plate roofing the leaf sweep (z_tol over the leaf
//     tops) so the wing band and the tooth print on the standard roof gap
//     instead of as an 8 mm ceiling. Bridges base step → corridor shelf: the
//     part's second deliberate bridge, welded on three sides (base step, the
//     solid band west of the pocket, the shelf).
//   tip pad — a riser on the table under the detent tip's rest footprint,
//     clear of the tooth's travel by xy_tol, so the restarted tip's first
//     layer lands on a roof gap, not on air.
module base_2d() {
    difference() { plate_2d(); pocket_cut_2d(); trough_cut_2d(); }
}
module shelf_2d() {
    translate([x_arch0 - 2.7, shelf_y0])
        square([x_shelf_j - (x_arch0 - 2.7), 35.2 - shelf_y0]);
    translate([x_shelf_j, shelf_y0j])
        square([x_arch1 + 2.7 - x_shelf_j, 35.2 - shelf_y0j]);
}
module table_2d() {
    translate([x_leg0 - 2, y_pocket - 0.3])
        square([apex_x + 13 - (x_leg0 - 2), shelf_y0 + 0.7 - (y_pocket - 0.3)]);
}
module pad_2d() {
    translate([apex_x - 4, pad_y0]) square([8, shelf_y0 + 0.7 - pad_y0]);
}

module frame() {
    // The base and shelving extrude in z-bands, each band one 2D union, so
    // the continuous roof planes (base top + table top at table_z1, shelf
    // top + pad top at shelf_top) tessellate as single faces instead of
    // coplanar seams between separate prisms (degenerate-triangle bait).
    linear_extrude(pocket_t) plate_2d();
    translate([0, 0, pocket_t]) linear_extrude(table_z0 - pocket_t) base_2d();
    translate([0, 0, table_z0]) linear_extrude(table_z1 - table_z0)
        { base_2d(); table_2d(); }
    linear_extrude(table_z1) shelf_2d();
    translate([0, 0, table_z1]) linear_extrude(shelf_top - table_z1)
        { shelf_2d(); pad_2d(); }
    // race side walls to race_h, and the bridged rail over the blade
    linear_extrude(race_h) race_walls_2d();
    translate([0, 0, arm_z0]) linear_extrude(race_h - arm_z0) rail_2d();
    // flexure anchor towers stand on the solid plate
    linear_extrude(base_t) towers_2d();
    // arch: posts rise to the web, web + tip ride in the plunger band. The
    // tip starts AT the beam's underside (arch_z0), never below it: material
    // below arch_z0 there would print as a floating island over the moving
    // outer leaf and weld the arch to the jaw (Jane's block finding, PR #410).
    linear_extrude(arch_z0 + 0.1) arch_posts_2d();
    translate([0, 0, arch_z0]) linear_extrude(arch_w) arch_beam_2d();
    translate([0, 0, arch_z0]) linear_extrude(pl_z1 - arch_z0) arch_tip_2d();
}

module jaw_side() {
    // block + pad
    translate([0, 0, float_z]) linear_extrude(jaw_h - float_z) jaw_block_2d();
    // leaves (float over the pocket floor, rooted in the tower)
    translate([0, 0, float_z]) linear_extrude(leg_z) leaves_2d(-1);
    // pin arm over the blade + pin post down beside/into the notch
    translate([0, 0, arm_z0]) linear_extrude(3) jaw_arm_2d();
    translate([0, 0, pl_z0]) linear_extrude(arm_z0 - pl_z0 + 1)
        translate([pin_x, -pin_y]) circle(pin_r);
}

module plunger() {
    translate([0, 0, pl_z0]) linear_extrude(pl_z1 - pl_z0) plunger_2d();
    // tab upper band — taller than the blade, caught by the rail above
    translate([0, 0, pl_z1]) linear_extrude(race_h - pl_z1 - z_tol)
        translate([x_tab0, -plunger_w / 2])
            square([x_race0 - x_tab0 + 0.2, plunger_w]);
}

part = "";  // "" gripper · "fitcheck" free-body intersection (empty) ·
            // "fitcheck_neg" interfering control · "drive_mouth" cam proof ·
            // "side_section" preview-only cross-section at the detent station
            // (keeps x >= 65) — the z-stack review shot in cameras.conf ·
            // "loaded" preview-only pose with a prop rod in the trough — the
            // `loaded` shot in cameras.conf, never a printable part

// PROOF the cam is connected, on the built geometry: the pin's own swept
// body (r = pin_r, shrunk 0.05), above the blade's −y edge, must be free of
// plunger material. A notch that lands tangent or short — as the first
// draft did — cuts nothing there, and a disconnected cam still renders
// watertight, slices clean and scores well: no other gate can see it.
// (The +y side is the mirror; proving one side proves the generator.)
module drive_mouth() {
    translate([0, 0, pl_z0]) linear_extrude(pl_z1 - pl_z0)
        intersection() {
            hull() {
                translate([pin_x, -pin_y]) circle(pin_r - 0.05);
                translate([pin_x - stroke, -(pin_y - d_jaw)]) circle(pin_r - 0.05);
            }
            // strictly above the blade's −y edge: only the bite can clear this
            translate([0, -plunger_w / 2 + 0.05]) square([nose_f, plunger_w]);
        }
}

module main() {
    guards();
    if (part == "fitcheck")
        intersection() { plunger(); frame(); jaw_side(); mirror([0, 1]) jaw_side(); }
    else if (part == "fitcheck_neg")
        intersection() {
            plunger();
            union() {
                frame(); jaw_side(); mirror([0, 1]) jaw_side();
                // race walls grown onto the blade — must interfere
                translate([0, 0, pl_z0]) linear_extrude(pl_z1 - pl_z0)
                    translate([x_race0, -plunger_w / 2 + 0.6])
                        square([nose_f - x_race0, plunger_w - 1.2]);
            }
        }
    else if (part == "drive_mouth")
        intersection() { plunger(); drive_mouth(); }
    else if (part == "side_section")
        // Preview-only cross-section at the detent station: one frame showing
        // every layer of the z-stack (leaves over the pocket floor, wing table
        // over the leaves, wing band + tooth over the table, tip pad, beam
        // over the corridor shelf, blade over the base) — the review shot
        // Jane's round-1 freeze-window ask exists for: fixed-over-air is
        // invisible from every show angle, and visible here.
        intersection() {
            union() { frame(); jaw_side(); mirror([0, 1]) jaw_side(); plunger(); }
            translate([apex_x - 5, -40, -1]) cube([x_base1, 80, race_h + 2]);
        }
    else if (part == "loaded") {
        // Preview-only LOADED pose (round 2, Drik's "no preview shows it
        // holding anything", PR #410): the as-printed part plus a PROP ROD —
        // a Ø grip_od cut-dowel segment lying in the trough between the
        // jaws, resting on the base deck (top = table_z1) and overhanging
        // the front edge the way a real cut dowel does. The mechanism stays
        // at its printed OPEN pose; the rod is a camera prop for the
        // cameras.conf `loaded` shot, never a printable or gated part (not
        // in ci.parts). Rear end stops 0.5 mm clear of the pin-arm bosses;
        // the rod sinks 0.15 into the deck so the resting contact is a real
        // intersection, not a tangency (a tangent union is non-manifold).
        frame(); jaw_side(); mirror([0, 1]) jaw_side(); plunger();
        translate([x_pad0 - 7, 0, table_z1 + half - 0.15]) rotate([0, 90, 0])
            cylinder(h = x_base1 + 44 - (x_pad0 - 7), r = half);
    }
    else {
        frame(); jaw_side(); mirror([0, 1]) jaw_side(); plunger();
    }
}

main();
