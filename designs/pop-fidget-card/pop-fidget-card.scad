// pop-fidget-card — a print-in-place 1st-birthday keepsake card with working
// fidgets on its face: two captive bubble spinners, a bistable "bubble-pop"
// button, a captive bubble bead on a slider track, and a punched easel flap
// on a print-in-place piano hinge that props the card on a shelf.
// Brief: issue #342. Decisions and derivations: NOTES.md. All dims in mm.
//
// Prints FACE-UP in one piece, no supports, no assembly. Mechanism sources
// (values kept, geometry re-hosted on the card — see NOTES.md):
//   - spinners: designs/captive-spinner (45° cone-cap capture, CC3 anisotropy:
//     radial gap is spread-limited and tight, axial gaps are sag-limited and
//     snapped to whole layers)
//   - pop button: designs/bistable-toggle (fixed-fixed pre-buckled arch,
//     clamped into the card so the card is the frame; prints flat so bending
//     runs across roads within a layer)
//   - easel hinge: lib/print-in-place.scad pip_hinge/pip_hinge_pin (teardrop
//     bore grown by a true 2D offset), tiled piano-style like pip-piano-hinge
//   - slider: a LINEAR captive spinner — 45° self-supporting channel roof
//     capturing a mushroom bead's foot; NOT the lib rail stack, which needs
//     5.7 mm of wall this 2.8 mm card cannot host (NOTES.md)

use <printability.scad>
use <print-in-place.scad>

/* [Card] */
// Card face width, X (mm)
card_w = 120;
// Card face height, Y (mm)
card_h = 85;
// Card plate thickness (mm) — 14 layers at 0.2
card_t = 2.8;
// Corner radius (mm)
corner_r = 6;
// 45° chamfer on bed-contact edges (mm)
bottom_chamfer = 0.5;

/* [Message] */
// Child's name — appended to the greeting. Default EMPTY on purpose: committed
// previews stay generic; set at slice time with -D 'card_name="ALEX"'.
card_name = "";
// Greeting line along the bottom (name and "!" are appended)
greeting = "HAPPY 1st BIRTHDAY";
// Raised height of embossed text and bubbles (mm)
emboss_h = 0.8;
// Depth of engraved burst rays and crescents (mm)
engrave_d = 0.6;

/* [Fidget set] */
// Number of bubble spinners (0-2) — drop order says lose #2 first
spinner_count = 2;
// Bistable bubble-pop button
with_toggle = true;
// Captive bubble bead on the slider track
with_slider = true;
// Punched easel flap on the piano hinge
with_easel = true;
// Coupon mode: compact tile with one of each TUNED fit (see the -coupon wrapper)
coupon = false;

/* [Spinners] */
// Big bubble rotor outer radius (mm)
spin1_or = 13;
// Small bubble rotor outer radius (mm)
spin2_or = 9.5;
// Rotor thickness (mm)
rotor_h = 4.5;
// Fixed centre post radius (mm)
post_r = 4;
// Capture lip: cap overhang past the rotor bore (mm) — >= 1.5
cap_lip = 2.5;
// Finger scallops around each rotor rim
scallops = 8;
// Scallop radius (mm)
scallop_r = 2.2;

/* [Pop button] */
// Clamped span of the bistable arch (mm)
tog_span = 26;
// Arch mid-rise (mm) — bistable needs rise/beam_t >= 2.3
tog_rise = 4;
// Arch beam thickness (mm)
tog_beam_t = 1.5;
// Bubble nub diameter (mm)
tog_nub_d = 9;

/* [Slider] */
// Track slot width (mm)
slot_w = 6;
// Under-card channel width (mm) — capture engagement = (ch_w-slot_w)/2 - clearance
ch_w = 10;
// Bead foot thickness (mm)
foot_t = 1.2;
// Raised track bar width on the face (mm)
bar_w = 12;
// Raised track bar height above the face (mm)
bar_h = 1.6;

/* [Easel] */
// Hinge pin diameter (mm)
pin_d = 2.5;
// Knuckle wall around the bore (mm) — pip_hinge guards >= 1.2
knuckle_wall = 1.3;
// Radial pin clearance (mm) — pip_hinge guards >= 0.25
hinge_clear = 0.4;
// Axial gap between knuckles (mm)
axial_gap = 0.6;
// Flap-to-window perimeter gap (mm)
flap_gap = 0.5;
// Tongue relief ramp rise at the flap root (mm) — with ramp_run this sets the
// rotation stop, i.e. the shelf prop angle (see NOTES.md)
ramp_h = 2.0;
// Tongue relief ramp run from the root (mm)
ramp_run = 5.75;
// 45° relief chamfer on the main plate's root underside (mm)
root_chamfer = 2.5;
// Deployed fit-check angle (deg past stowed) — must clear; the stop must
// catch by easel_deploy + easel_overshoot (the fitcheck_neg)
easel_deploy = 104;
// Over-rotation used by fitcheck_neg (deg past easel_deploy)
easel_overshoot = 14;
// Preview-only: fold the easel flap out (deg). PRINT AT 0.
demo_easel = 0; // [0:4:108]

/* [Clearances — CC3 anisotropy] */
// Layer height axial gaps are quantized to (mm)
layer_h = 0.2;
// Radial gap, spinner bore <-> post (mm) — spread-limited, >= 0.15
xy_tol = 0.2;
// Radial gap, bead stem <-> slot wall, per side (mm)
slide_tol = 0.25;
// Bead foot <-> channel wall side gap (mm) — first-layer squish safe
foot_side_clear = 0.5;
// Axial gaps in WHOLE LAYERS (rotor float, bead dome float)
z_layers = 2;

/* [CI fit-check — not a print parameter] */
// "" = the card. "fitcheck" = every moving/fixed pairwise interference (must
// render EMPTY). "fitcheck_neg" = the flap over-rotated past its stop (must
// render NON-EMPTY — proves the stop exists and the check can fail).
// "flapsweep" with easel_test_angle = one interference probe for tuning.
part = "";
// Angle for part="flapsweep" (deg)
easel_test_angle = 104;

/* [Quality] */
// Captive bores are $fn-sensitive; production 96+.
$fn = 96;

// ---- layout (coupon compacts to one of each tuned fit) --------------------
cw       = coupon ? 66 : card_w;
chh      = coupon ? 46 : card_h;
n_spin   = coupon ? 1  : spinner_count;
use_tog  = coupon ? false : with_toggle;
use_slid = with_slider;
use_ease = with_easel;

spin1_pos = coupon ? [39, 31] : [26, 40];
spin2_pos = [93, 72];

// pop button (window centre)
tog_pos   = [89, 30];

// slider track: vertical, x centre / slot y span
track_x   = coupon ? 57 : 111;
track_y0  = coupon ? 12 : 20;
track_y1  = coupon ? 42 : 62;

// easel window: x span, window bottom edge y, flap top y
fx0  = coupon ? 6    : 42;
fx1  = coupon ? 24   : 70;
wlo  = coupon ? 6    : 10;
ftop = coupon ? 35.5 : 47.5;

// ---- derived: shared -------------------------------------------------------
z_tol   = z_layers * layer_h;         // axial float, whole layers
face    = card_t;                     // card face z

// ---- derived: spinner (captive-spinner formulas, base = the card face) -----
rotor_ir  = post_r + xy_tol;
r_cap     = rotor_ir + cap_lip;
cone_h    = r_cap - post_r;
spin_z0   = face + z_tol;                          // rotor float
function spin_cone0(rh) = spin_z0 + rh + z_tol - xy_tol;

// ---- derived: pop button ---------------------------------------------------
tog_travel = 1.98 * tog_rise;                       // doc constant
tog_under  = (tog_travel - tog_rise) + tog_beam_t + 1.5;
tog_over   = tog_rise + tog_nub_d - 1 + 1.5;

// ---- derived: slider -------------------------------------------------------
ch_v      = foot_t + z_tol;                        // vertical channel wall top
roof_rise = (ch_w - slot_w) / 2;                   // 45° roof
roof_apex = ch_v + roof_rise;
bar_top   = face + bar_h;
foot_d    = ch_w - 2 * foot_side_clear;
stem_d    = slot_w - 2 * slide_tol;
dome_z    = bar_top + z_tol;                       // bead dome float
bead_y    = track_y0;                              // printed park position
travel    = track_y1 - track_y0;
engage    = roof_rise - foot_side_clear;           // capture per side

// ---- derived: easel (lib pip_hinge numbers) --------------------------------
R_k       = 0.8 * pin_d + hinge_clear + knuckle_wall;  // knuckle outer radius
y_ax      = wlo + R_k + 0.55;                      // hinge axis y (swing relief)
z_ax      = R_k;                                   // barrel bottoms rest on bed
tongue_root = y_ax + 0.25;                         // tongue root edge
plate_root  = y_ax + R_k + 0.4;                    // castellated main-plate root
hx0       = fx0 + flap_gap;                        // hinge span = flap width
hx1       = fx1 - flap_gap;
hinge_len = hx1 - hx0;
slot_k    = hinge_len / 3;                         // 3 knuckles: card,flap,card
barrel_len = slot_k - axial_gap;
function kx(k) = hx0 + (k + 0.5) * slot_k;         // knuckle centres
wtop      = ftop + flap_gap;                       // window top edge

// greeting auto-size (no textmetrics in 2021.01 — 0.62 em width factor)
line_txt  = card_name == "" ? str(greeting, "!")
                            : str(greeting, ", ", card_name, "!");
line_size = min(6, (cw - 14) / (0.62 * len(line_txt)));
font      = "Liberation Sans:style=Bold";

// ---------------------------------------------------------------------------
// 2D helpers
// ---------------------------------------------------------------------------
module stadium(y0, y1, w) {                        // vertical stadium at x=0
    hull() { translate([0, y0]) circle(d = w); translate([0, y1]) circle(d = w); }
}

module crescent(r) {                               // bubble-highlight moon
    difference() { circle(r); translate([r * 0.45, -r * 0.45]) circle(r); }
}

// ---------------------------------------------------------------------------
// Card plate + static decoration
// ---------------------------------------------------------------------------
module plate_with_bar() {
    rounded_box([cw, chh, card_t], r = corner_r, bottom_chamfer = bottom_chamfer);
    if (use_slid)                                  // raised track bar, chamfered top
        translate([track_x, 0, 0]) hull() {
            translate([0, 0, face - 0.01]) linear_extrude(bar_h - 0.6 + 0.01)
                stadium(track_y0 - 6, track_y1 + 6, bar_w);
            translate([0, 0, face - 0.01]) linear_extrude(bar_h + 0.01)
                stadium(track_y0 - 6, track_y1 + 6, bar_w - 1.2);
        }
}

module face_embosses() {
    if (!coupon) {
        // POP! headline
        translate([16, 59, face - 0.01]) linear_extrude(emboss_h + 0.01)
            text("POP!", size = 20, font = font);
        // greeting line (+ name parameter)
        translate([cw / 2, 4.5, face - 0.01]) linear_extrude(emboss_h + 0.01)
            text(line_txt, size = line_size, font = font, halign = "center");
        // bubble cluster drifting out of the "!" toward the small spinner
        for (b = [[64, 74, 3.5], [70, 68, 2.5], [76, 75, 2], [42, 77, 2], [57, 77, 1.7]])
            translate([b[0], b[1], face]) scale([1, 1, 0.45]) sphere(b[2]);
    }
}

module face_engraves() {                           // burst rays, top-left corner
    if (!coupon)
        for (a = [100, 135, 170])
            translate([12, 72, face - engrave_d]) rotate([0, 0, a])
                translate([4, -0.6, 0]) cube([7, 1.2, engrave_d + 0.02]);
}

// window / channel cutters ---------------------------------------------------
module toggle_window_cut() {
    translate([tog_pos[0] - tog_span / 2, tog_pos[1], -0.01])
        linear_extrude(card_t + 0.02)
            offset(r = 2) offset(r = -2)
                translate([0, -tog_under]) square([tog_span, tog_under + tog_over]);
}

module easel_window_cut() {
    translate([0, 0, -0.01]) linear_extrude(card_t + 0.02)
        offset(r = 2) offset(r = -2)
            polygon([[fx0, wlo], [fx1, wlo], [fx1, wtop], [fx0, wtop]]);
}

module slider_channel_cut() {
    translate([track_x, 0, 0]) {
        // bottom channel (open to bed)
        translate([0, 0, -0.01]) linear_extrude(ch_v + 0.02)
            stadium(track_y0, track_y1, ch_w);
        // 45° roof: hull of channel-width and slot-width slabs (self-supporting
        // on every side, ends included — no membrane needed anywhere)
        hull() {
            translate([0, 0, ch_v - 0.01]) linear_extrude(0.02)
                stadium(track_y0, track_y1, ch_w);
            translate([0, 0, roof_apex]) linear_extrude(0.02)
                stadium(track_y0, track_y1, slot_w);
        }
        // slot up through the face and the bar
        translate([0, 0, roof_apex - 0.01]) linear_extrude(card_t + bar_h - roof_apex + 0.02)
            stadium(track_y0, track_y1, slot_w);
    }
}

// ---------------------------------------------------------------------------
// Spinners (fixed halves + captive rotors)
// ---------------------------------------------------------------------------
module spinner_fixed(p, ror) {
    translate([p[0], p[1], 0]) {
        translate([0, 0, face - 0.4]) cylinder(r = post_r, h = spin_cone0(rotor_h) - face + 0.41);
        translate([0, 0, spin_cone0(rotor_h)]) cylinder(r1 = post_r, r2 = r_cap, h = cone_h);
    }
}

module spinner_rotor(p, ror, ir = rotor_ir) {
    translate([p[0], p[1], spin_z0]) difference() {
        cylinder(r = ror, h = rotor_h);
        translate([0, 0, -0.01]) cylinder(r = ir, h = rotor_h + 0.02);
        for (i = [0 : scallops - 1])
            rotate([0, 0, i * 360 / scallops])
                translate([ror, 0, -0.01]) cylinder(r = scallop_r, h = rotor_h + 0.02);
        // bubble-highlight crescent on the rotor top
        translate([-ror * 0.35, ror * 0.35, rotor_h - engrave_d + 0.01])
            linear_extrude(engrave_d) crescent(ror * 0.28);
    }
}

// ---------------------------------------------------------------------------
// Pop button (monolithic compliant part — fused to the card at the arch ends)
// ---------------------------------------------------------------------------
function tog_yc(x) = tog_rise * (1 - cos(360 * x / tog_span)) / 2;
TOG_NS = 60;

module toggle_body() {
    translate([tog_pos[0] - tog_span / 2, tog_pos[1], 0]) {
        linear_extrude(card_t)
            offset(r = -0.8) offset(r = 0.8) union() {
                // arch beam, ends running 4 mm into the card walls (the clamps)
                polygon(concat(
                    [for (i = [0 : TOG_NS]) let (x = tog_span * i / TOG_NS + (i == 0 ? -3 : 0) + (i == TOG_NS ? 3 : 0))
                        [x, tog_yc(min(max(tog_span * i / TOG_NS, 0), tog_span)) + tog_beam_t / 2]],
                    [for (i = [TOG_NS : -1 : 0]) let (x = tog_span * i / TOG_NS + (i == 0 ? -3 : 0) + (i == TOG_NS ? 3 : 0))
                        [x, tog_yc(min(max(tog_span * i / TOG_NS, 0), tog_span)) - tog_beam_t / 2]]));
                // bubble nub fused onto the apex
                translate([tog_span / 2, tog_rise + tog_nub_d / 2 - 1]) circle(d = tog_nub_d);
            }
        // proud dome cap on the nub so a thumb finds it
        translate([tog_span / 2, tog_rise + tog_nub_d / 2 - 1, face])
            scale([1, 1, 0.5]) sphere(d = tog_nub_d - 1.5);
    }
}

// ---------------------------------------------------------------------------
// Slider bead (mushroom: foot on the bed, stem through the slot, bubble dome)
// ---------------------------------------------------------------------------
module bead() {
    translate([track_x, bead_y, 0]) {
        cylinder(d1 = foot_d - 0.6, d2 = foot_d, h = 0.3);          // elephant-foot relief
        translate([0, 0, 0.29]) cylinder(d = foot_d, h = foot_t - 0.29);
        cylinder(d = stem_d, h = dome_z + 0.01);                     // stem
        translate([0, 0, dome_z]) {
            cylinder(d1 = stem_d, d2 = 10, h = 2.25);                // 45° dome base
            translate([0, 0, 2.25]) cylinder(d = 10, h = 0.6);
            translate([0, 0, 2.85]) difference() {
                scale([1, 1, 0.5]) sphere(d = 10);                   // bubble cap
                translate([-1.8, 1.8, 2.5 - engrave_d])
                    linear_extrude(engrave_d + 0.01) crescent(1.6);
            }
        }
    }
}

// Deliberate weak fusion (CC2): one breakaway nib, foot -> channel end wall.
// Drawn OUTSIDE the fitcheck bodies — it is a declared weld, sheared on the
// first slide, excluded from the clearance proof on purpose (NOTES.md).
module bead_anchor() {
    translate([track_x - 0.4, bead_y - foot_d / 2 - foot_side_clear - 0.1, 0])
        cube([0.8, foot_side_clear + 0.2 + 0.1, 0.3]);
}

// ---------------------------------------------------------------------------
// Easel (punched flap, piano hinge, ground-stop ramp)
// ---------------------------------------------------------------------------
module card_knuckles() {                            // fixed half: barrels 0 & 2 + webs
    for (k = [0, 2]) {
        translate([kx(k), y_ax, z_ax]) rotate([0, 0, 90])
            pip_hinge(pin_d, hinge_clear, knuckle_wall, barrel_len);
        // web: barrel outer wall -> card edge below the window (outside the bore)
        translate([kx(k) - barrel_len / 2, wlo - 0.5, 0])
            cube([barrel_len, (y_ax - (pin_d / 2 + hinge_clear + 0.15)) - (wlo - 0.5), z_ax]);
    }
}

module flap_body() {
    fw0 = fx0 + flap_gap; fw1 = fx1 - flap_gap;
    difference() {
        union() {
            // main plate, castellated root, rounded top corners
            translate([0, 0, 0]) linear_extrude(card_t)
                offset(r = 2) offset(r = -2)
                    polygon([[fw0, plate_root], [fw1, plate_root], [fw1, ftop], [fw0, ftop]]);
            // hinge tongue (knuckle 1 span) reaching to the axis line
            translate([kx(1) - barrel_len / 2, tongue_root, 0])
                cube([barrel_len, plate_root - tongue_root + 0.02, card_t]);
            // flap knuckle barrel + web tying it to the tongue (outside the bore)
            translate([kx(1), y_ax, z_ax]) rotate([0, 0, 90])
                pip_hinge(pin_d, hinge_clear, knuckle_wall, barrel_len);
            translate([kx(1) - barrel_len / 2, y_ax + pin_d / 2 + hinge_clear + 0.15, 0])
                cube([barrel_len, R_k - (pin_d / 2 + hinge_clear + 0.15) + 0.4, z_ax]);
            // big "1" embossed on the flap face
            translate([(fw0 + fw1) / 2, (plate_root + ftop) / 2 - 8.5, face - 0.01])
                linear_extrude(emboss_h + 0.01)
                    text("1", size = coupon ? 14 : 24, font = font, halign = "center");
        }
        // tongue relief ramp: the underside rise whose contact with the window
        // edge IS the rotation stop (sets the prop angle — NOTES.md)
        translate([kx(1) - barrel_len / 2 - 0.01, tongue_root - 0.01, 0])
            rotate([0, 90, 0])
                linear_extrude(barrel_len + 0.02)
                    polygon([[0.01, 0], [0.01, ramp_run + 0.01], [-ramp_h, 0]]);
        // 45° root chamfer on the main plate underside (swing relief)
        translate([fw0 - 0.01, plate_root - 0.01, 0]) rotate([0, 90, 0])
            linear_extrude(fw1 - fw0 + 0.02)
                polygon([[0.01, 0], [0.01, root_chamfer + 0.01], [-root_chamfer, 0]]);
    }
}

module flap(a = 0) {                                // rotated about the hinge axis
    translate([0, y_ax, z_ax]) rotate([-a, 0, 0]) translate([0, -y_ax, -z_ax])
        flap_body();
}

module hinge_pin() {
    translate([(hx0 + hx1) / 2, y_ax, z_ax]) rotate([0, 0, 90])
        pip_hinge_pin(pin_d, hinge_len - 0.6);
}

// ---------------------------------------------------------------------------
// Assembly
// ---------------------------------------------------------------------------
module fixed_body() {
    union() {
        difference() {
            union() { plate_with_bar(); face_embosses(); }
            if (use_tog)  toggle_window_cut();
            if (use_ease) easel_window_cut();
            if (use_slid) slider_channel_cut();
            face_engraves();
        }
        for (s = [0 : n_spin - 1])
            spinner_fixed(s == 0 ? spin1_pos : spin2_pos, s == 0 ? spin1_or : spin2_or);
        if (use_tog)  toggle_body();
        if (use_ease) card_knuckles();
    }
}

module movings() {
    for (s = [0 : n_spin - 1])
        spinner_rotor(s == 0 ? spin1_pos : spin2_pos, s == 0 ? spin1_or : spin2_or);
    if (use_slid) bead();
    if (use_ease) { flap(demo_easel); hinge_pin(); }
}

module guards() {
    assert(xy_tol >= 0.15, "spinner radial gap below a printable line width");
    assert(cap_lip >= 1.5, "spinner capture lip too small — the rotor could pop off");
    assert(r_cap < spin2_or, "spinner cap wider than the smallest rotor — nothing to grip");
    assert(!use_tog || tog_rise / tog_beam_t >= 2.3,
           "pop-button arch too flat to be bistable (rise/beam_t < 2.3)");
    assert(!use_tog || tog_beam_t >= 1.2, "pop-button arch under 3 perimeters");
    assert(!use_slid || engage >= 1.2,
           "bead capture engagement under 1.2 mm — the bead could pull out");
    assert(!use_slid || slide_tol >= 0.2, "bead stem gap below a sliding fit");
    assert(!use_slid || card_t + bar_h - roof_apex >= 0.8,
           "slot walls too shallow above the channel roof");
    assert(!use_slid || travel >= 20, "slider travel too short to be worth printing");
    assert(!use_ease || !use_tog || tog_pos[0] - tog_span / 2 - fx1 >= 2,
           "easel and pop-button windows too close — keep >= 2 mm of card between them");
    assert(!use_tog || !use_slid || coupon
           || track_x - ch_w / 2 - (tog_pos[0] + tog_span / 2) >= 3.5,
           "pop-button clamp anchor would reach into the slider channel");
    assert(coupon || line_size >= 4.5,
           "card_name too long — greeting strokes would drop under 0.8 mm");
    if (use_ease)
        echo(str("easel: stop ~", easel_deploy + 4, " deg -> shelf prop ~",
                 180 - (easel_deploy + 4), " deg (brief: 70-75)"));
    if (use_tog) echo(str("pop button: predicted travel ~", tog_travel, " mm"));
    if (use_slid) echo(str("slider travel: ", travel, " mm (brief: >= 40)"));
}

module main() {
    guards();
    if (part == "fitcheck") {
        // every moving/fixed pair must be EMPTY, flap through its whole swing
        for (s = [0 : n_spin - 1])
            intersection() {
                spinner_rotor(s == 0 ? spin1_pos : spin2_pos, s == 0 ? spin1_or : spin2_or);
                fixed_body();
            }
        if (use_slid) intersection() { bead(); fixed_body(); }
        if (use_ease) {
            for (a = [0, 35, 70, easel_deploy])
                intersection() { flap(a); fixed_body(); }
            intersection() { hinge_pin(); fixed_body(); }
            intersection() { hinge_pin(); flap(0); }
        }
    } else if (part == "fitcheck_neg") {
        // over-rotated flap MUST hit its stop — proves the stop exists and
        // that the interference check can fail
        intersection() { flap(easel_deploy + easel_overshoot); fixed_body(); }
    } else if (part == "flapsweep") {
        intersection() { flap(easel_test_angle); fixed_body(); }
    } else {
        fixed_body();
        movings();
        if (use_slid) bead_anchor();
    }
}

main();
