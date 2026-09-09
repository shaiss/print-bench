// ovodyo — kinetic "dice-ball" desk clock (v0 base, clean-room re-creation).
//
// Two faceted geodesic balls tumble on brass stalks over an exposed truss:
// left = hours (1-12), right = minutes (00-55 in 5s). Numerals sit on the 12
// pentagon plaques; a helical slot frames the internal drive. This is the v0
// BASE every improvement issue (#599 and its children) builds on — it is
// deliberately simplified; see NOTES.md "v0 simplifications" for what each
// issue upgrades. Requirements/decisions: NOTES.md. Charter: PM.md.
// All dimensions in millimeters.

include <geodesic-ball.scad>  // the faceted numbered-ball generator (#600)

/* [What to render] */
// assembled | hours-half | minutes-half | hours-ball | minutes-ball | base-segment | base-end | mock-drive
part = "assembled";

/* [Overall (from the reference: 383 x 78 x 163 mm)] */
// Ball outer diameter (mm)
ball_d = 78;
// Ball centre-to-centre spacing (mm)
ball_spacing = 200;
// Ball centre height above the desk (mm)
ball_center_z = 124;

/* [Ball surface] */
// Geodesic subdivision frequency: higher = finer triangular field, rounder ball
facet_freq = 3;
// Pentagon-plaque plane as a fraction of radius: smaller = larger number plaques
plaque = 0.92;
// Shell wall (mm) — keep >= 1.2
wall = 2.2;
// Numeral glyph height (mm)
glyph_h = 11;
// Numeral recess depth (mm). v0 = debossed; #601 makes it true cut-through.
deboss = 1.0;
// Helical mechanism-window width (mm) and how far it wraps (turns)
slot_width = 10;
slot_turns = 0.5;

/* [Stalks & base] */
// Brass support-shaft diameter (mm) — a bought rod (vitamin)
stalk_d = 4.5;
// Truss strut diameter (mm)
strut_d = 2.8;
// One base segment length (mm); 3 segments make the 383 mm base
seg_len = 127;
// Truss max width (deck chord spacing, mm) and max ridge height (mm), both at
// the centre; each tapers to a needle point at the ends
truss_w = 76;
truss_h = 34;
// Bays per segment
bays = 4;

/* [Quality] */
// Iterating: 40. Production: 64+ .
$fn = 48;

// ---- balls -----------------------------------------------------------------

module hours_ball() {
  geodesic_ball(d = ball_d, nums = gb_hours(), freq = facet_freq, plaque = plaque,
                wall = wall, glyph_h = glyph_h, deboss = deboss, through = false,
                slot = true, slot_width = slot_width, slot_turns = slot_turns);
}

module minutes_ball() {
  // opposite-handed slot phase differentiates it from the hours ball
  rotate([0, 0, 36])
    geodesic_ball(d = ball_d, nums = gb_minutes(), freq = facet_freq, plaque = plaque,
                  wall = wall, glyph_h = glyph_h, deboss = deboss, through = false,
                  slot = true, slot_width = slot_width, slot_turns = -slot_turns);
}

// One printable HEMISPHERE, cut at the equator and sitting flat on the bed
// (dome up). A sphere prints on a point; the real design splits each ball into
// two halves that print flat-face-down. v0 uses a crude flat great-circle cut;
// issue #602 turns it into a proper flat mating ring (threaded/snap seam).
module ball_half(hours = true) {
  intersection() {
    if (hours) hours_ball(); else minutes_ball();
    translate([0, 0, ball_d]) cube(ball_d * 2, center = true);  // keep z >= 0
  }
}

// ---- mock drive (v0 placeholder; real bevel differential is #604) ----------

// A mock toothed disc. Teeth straddle the rim so they stay ONE body with the
// hub (a real involute gear is lib/bevel.scad, issue #604).
module mock_gear(d = 24, h = 5, teeth = 20) {
  hub_r = d * 0.42;
  union() {
    cylinder(r = hub_r + 0.6, h = h);
    for (i = [0 : teeth - 1])
      rotate([0, 0, i * 360 / teeth])
        translate([hub_r, 0, h / 2])
          cube([2.6, 2.0, h], center = true);
  }
}

// v0 placeholder differential: a flat-sitting crown gear + hub + a 90-degree
// bevel pinion beside it, low and stable. Replaced by a real meshing bevel
// differential in issue #604 (and verified turning by the gate in #600).
module mock_drive() {
  union() {
    mock_gear(d = 30, h = 6, teeth = 26);                     // ring/crown gear, flat
    cylinder(d = 11, h = 9);                                  // hub
    translate([0, 0, 9]) cylinder(d = 4, h = 9);              // inner drive-shaft stub
    translate([23, 0, 0]) mock_gear(d = 16, h = 6, teeth = 16); // meshing pinion, flat
  }
}

// ---- base truss (tapered space-frame → needle points at both ends) ---------
// The reference base is a long, shallow lattice that tapers to sharp points at
// both ends, in three bolted segments: a constant-section CENTRE and two
// tapering END wings that carry the stalk bosses over the motor pods. The
// triangular section (two bottom chords + a ridge) shrinks in BOTH width and
// height toward the tips. (The reusable lib/spaceframe.scad and the red
// structural core are issue #603; this is the in-design silhouette.)

n_bays  = 3 * bays;                       // stations 0..n_bays over the whole base
base_L  = 3 * seg_len;                     // total length (383 mm)
base_half = base_L / 2;

// taper: 1 across the centre segment, then linear down to a small tip over each
// end segment (so the middle third is full-section and the outer thirds point)
function base_t(x) =
  (abs(x) <= seg_len / 2) ? 1
  : max(0.05, 1 - (abs(x) - seg_len / 2) / seg_len);

function base_h(x) = truss_h * base_t(x);            // ridge height at x
function _bw(x)    = truss_w / 2 * base_t(x);        // deck half-width at x
function _bx(i)    = -base_half + i * (base_L / n_bays);   // station x

// the three section nodes at station i
function _BL(i) = [_bx(i), -_bw(_bx(i)), 0];
function _BR(i) = [_bx(i),  _bw(_bx(i)), 0];
function _RD(i) = [_bx(i), 0, base_h(_bx(i))];

module strut(p1, p2, d = strut_d) {
  hull() {
    translate(p1) sphere(d = d, $fn = 16);
    translate(p2) sphere(d = d, $fn = 16);
  }
}

// the lattice for stations [a..b]: bottom + ridge chords, a Warren diagonal in
// the bottom deck, and per-station triangular cross-bracing. Near a tip the
// section shrinks to a small nub, so degenerate near-zero struts are harmless.
module base_truss(a, b) {
  for (i = [a : b - 1]) {
    strut(_BL(i), _BL(i + 1));             // bottom chords
    strut(_BR(i), _BR(i + 1));
    strut(_RD(i), _RD(i + 1));             // ridge chord
    if (i % 2 == 0) strut(_BL(i), _BR(i + 1));   // Warren diagonal (bottom deck)
    else            strut(_BR(i), _BL(i + 1));
  }
  for (i = [a : b]) {
    strut(_BL(i), _BR(i));                 // cross tie
    strut(_BL(i), _RD(i));                 // ridge posts
    strut(_BR(i), _RD(i));
  }
}

// a stalk boss sitting on the ridge at x (its height follows the taper)
module stalk_boss(x) {
  translate([x, 0, base_h(x)])
    cylinder(d = stalk_d + 5, h = 6, $fn = 32);
}

// CENTRE segment (constant section) — the gated representative part
module base_segment() { base_truss(bays, 2 * bays); }

// one END wing, tapering to a needle point, with its stalk boss over the pod
module base_end() {
  base_truss(0, bays);
  stalk_boss(-ball_spacing / 2);
}

module full_base() {
  base_truss(0, n_bays);                   // the whole tapered lattice
  stalk_boss(-ball_spacing / 2);
  stalk_boss( ball_spacing / 2);
}

// ---- assembled preview -----------------------------------------------------

module stalk(x) {
  translate([x, 0, base_h(x)])
    cylinder(d = stalk_d, h = ball_center_z - base_h(x), $fn = 32);
}

module assembled() {
  full_base();
  stalk(-ball_spacing / 2);
  stalk( ball_spacing / 2);
  // hours ball (left) with mock drive peeking through the slot
  translate([-ball_spacing / 2, 0, ball_center_z]) {
    hours_ball();
    mock_drive();
  }
  // minutes ball (right)
  translate([ball_spacing / 2, 0, ball_center_z]) {
    minutes_ball();
    mock_drive();
  }
}

// ---- dispatch --------------------------------------------------------------

if      (part == "assembled")    assembled();
else if (part == "hours-half")   ball_half(hours = true);   // printable hemisphere
else if (part == "minutes-half") ball_half(hours = false);
else if (part == "hours-ball")   hours_ball();              // full shell (preview)
else if (part == "minutes-ball") minutes_ball();
else if (part == "base-segment") base_segment();           // constant centre segment
else if (part == "base-end")     base_end();               // tapering end wing
else if (part == "mock-drive")   mock_drive();
else assembled();
