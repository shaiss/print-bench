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
// assembled | hours-half | minutes-half | hours-ball | minutes-ball | base-segment | mock-drive
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
// Truss depth (side chord spacing, mm) and height (ridge, mm)
truss_w = 66;
truss_h = 30;
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

// ---- base truss ------------------------------------------------------------

module strut(p1, p2, d = strut_d) {
  hull() {
    translate(p1) sphere(d = d, $fn = 16);
    translate(p2) sphere(d = d, $fn = 16);
  }
}

// one triangular-section truss segment, its near end at x=0
module base_segment(L = seg_len) {
  bl = L / bays;
  w = truss_w / 2;
  // bottom chords + ridge chord
  strut([0, -w, 0], [L, -w, 0]);
  strut([0,  w, 0], [L,  w, 0]);
  strut([0, 0, truss_h], [L, 0, truss_h]);
  for (i = [0 : bays]) {
    x = i * bl;
    // cross tie + ridge posts (triangular section)
    strut([x, -w, 0], [x, w, 0]);
    strut([x, -w, 0], [x, 0, truss_h]);
    strut([x,  w, 0], [x, 0, truss_h]);
  }
  // Warren diagonals in the bottom deck
  for (i = [0 : bays - 1]) {
    x = i * bl;
    if (i % 2 == 0) strut([x, -w, 0], [x + bl, w, 0]);
    else            strut([x, w, 0], [x + bl, -w, 0]);
  }
  // a stalk boss on the ridge mid-segment
  translate([L / 2, 0, truss_h])
    cylinder(d = stalk_d + 5, h = 6, center = false, $fn = 32);
}

module full_base() {
  // three segments end to end, centred on x=0
  total = 3 * seg_len;
  for (s = [0 : 2])
    translate([-total / 2 + s * seg_len, 0, 0]) base_segment();
}

// ---- assembled preview -----------------------------------------------------

module stalk(x) {
  translate([x, 0, truss_h])
    cylinder(d = stalk_d, h = ball_center_z - truss_h, $fn = 32);
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
else if (part == "base-segment") base_segment();
else if (part == "mock-drive")   mock_drive();
else assembled();
