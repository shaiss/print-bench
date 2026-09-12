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
// assembled | hours-top | hours-bottom | minutes-top | minutes-bottom |
// hours-ball | minutes-ball | base-segment | base-end | mock-drive |
// base-mech | pod-drive
part = "assembled";

/* [Overall (from the reference: 383 x 78 x 163 mm)] */
// Ball outer diameter (mm)
ball_d = 78;
// Ball centre-to-centre spacing (mm)
ball_spacing = 200;
// Ball centre height above the desk (mm)
ball_center_z = 124;

/* [Ball surface] */
// Faceting: how far out the 20 triangle-corner-chamfer planes sit (× ball
// radius). 1.0 = biggest triangular facets (≈ an icosidodecahedron); 1.05 =
// dominant pentagon number-faces with crisp corners (the reference); >=1.12 = a
// plain dodecahedron with clean corners. The 12 numbered pentagons stay flush at
// the ball radius regardless.
facet = 1.05;
// Shell wall (mm) — keep >= 1.2
wall = 2.2;
// Numeral glyph height (mm) — bold, near the pentagon inradius so the numbers
// read across a room (the reference's headline feature)
glyph_h = 14;
// Numerals cut clean through the shell to the red interior (reference), stencilised
// so no counter drops out; false = debossed recess
numerals_through = true;
// Stencil bridge-bar width (mm) — the ties that keep 0/4/6/8/9 counters attached
bridge_w = 1.2;
// Helical mechanism-window width (mm) and how far it wraps (turns)
slot_width = 10;
slot_turns = 0.5;

/* [Ball seam] */
// The ball prints in two halves. It is tilted POLE-UP (a pentagon face to each
// pole) so the equatorial cut runs through the triangle band and bisects NO
// number face — even numbers land on the top half, odd on the bottom. The two
// halves locate on short alignment dowels seated in bosses at the seam (a keyed
// register; #602 upgrades this flat butt joint to a captive threaded/snap seam).
// Dowel diameter (mm) and how deep the dowel seat is (straddling the seam):
seam_dowel_d = 2.8;
seam_dowel_depth = 12;

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
  geodesic_ball(d = ball_d, nums = gb_hours(), tri_k = facet,
                wall = wall, glyph_h = glyph_h, through = numerals_through, bridge = bridge_w,
                slot = true, slot_width = slot_width, slot_turns = slot_turns);
}

module minutes_ball() {
  // opposite-handed slot differentiates it from the hours ball
  geodesic_ball(d = ball_d, nums = gb_minutes(), tri_k = facet,
                wall = wall, glyph_h = glyph_h, through = numerals_through, bridge = bridge_w,
                slot = true, slot_width = slot_width, slot_turns = -slot_turns);
}

// Pole-up tilt: bring a pentagon face to each ±z pole so the equatorial split
// runs through the triangle band and no number face is bisected. atan2(1,PHI)
// is the colatitude of icosa vertex [0,1,PHI], so this rotation lands it on +z.
_pole_up = atan2(1, PHI);

// Alignment-dowel bosses at the seam. Three lugs on the inner wall straddle the
// cut plane at irregular azimuths (so the halves seat at exactly one clocking);
// a dowel hole is drilled down each. Because they are drilled in the WHOLE ball
// before it is split, the two halves' holes register by construction.
_seam_boss_r  = ball_d / 2 - 4;   // lug seat radius (embedded in the wall)
_seam_az      = [24, 150, 262];   // irregular azimuths (deg), keyed clocking

module _seam_bosses() {
  for (a = _seam_az)
    rotate([0, 0, a]) translate([_seam_boss_r, 0, 0])
      cylinder(d = 8, h = 14, center = true, $fn = 32);   // lug straddling z=0
}
module _seam_dowels() {
  for (a = _seam_az)
    rotate([0, 0, a]) translate([_seam_boss_r, 0, 0])
      cylinder(d = seam_dowel_d, h = seam_dowel_depth, center = true, $fn = 24);
}

// The pole-up ball with dowel bosses added and their holes drilled — the common
// solid both printable halves are cut from.
module _ball_for_split(hours = true) {
  difference() {
    union() {
      rotate([_pole_up, 0, 0]) { if (hours) hours_ball(); else minutes_ball(); }
      _seam_bosses();
    }
    _seam_dowels();
  }
}

// One printable HEMISPHERE, cut at the equator (through the triangle band) and
// sitting flat cut-face-down on the bed (dome up). `top` selects the +z half
// (even numbers) or the -z half (odd numbers); the bottom half is flipped so it
// too prints flat-face-down. Print two halves per ball — a top AND a bottom —
// to get all 12 numbers. #602 upgrades the flat butt joint + dowels to a
// captive threaded/snap seam; the faceted dome still has light overhangs (v0).
module ball_half(hours = true, top = true) {
  if (top)
    intersection() {
      _ball_for_split(hours);
      translate([0, 0, ball_d]) cube(ball_d * 2, center = true);   // keep z >= 0
    }
  else
    rotate([180, 0, 0])                                            // flip dome-up
      intersection() {
        _ball_for_split(hours);
        translate([0, 0, -ball_d]) cube(ball_d * 2, center = true); // keep z <= 0
      }
}

// ---- drivetrain gear primitives -------------------------------------------
// Hand-rolled gears (no BOSL2 dependency, fast to render): trapezoidal teeth on
// a pitch circle. Not true involute — these represent the mechanism in the
// preview, they are not cut for a running fit (a real involute differential
// gated as turning is issue #604). One 2D profile drives both the spur and the
// bevel, so a train and its right-angle take-off share a tooth count.

// module = mod (circular tooth size). pitch radius pr = mod*teeth/2; a pair
// meshes when their centre distance == pr1 + pr2.
function mech_pr(teeth, mod) = mod * teeth / 2;

// The 2D gear profile: root disc + `teeth` radial trapezoids (wide at the root,
// narrow at the tip), with the bore removed.
module mech_spur2d(teeth = 16, mod = 1.6, bore = 3.2) {
  pr = mech_pr(teeth, mod);
  rr = pr - 1.25 * mod;                    // dedendum (root) radius
  ra = pr + mod;                           // addendum (tip) radius
  tw = 360 / teeth;
  difference() {
    union() {
      circle(r = rr + 0.15, $fn = max(64, teeth * 4));
      for (i = [0 : teeth - 1]) rotate(i * tw)
        polygon([[rr, -mod * 1.05], [ra, -mod * 0.5], [ra, mod * 0.5], [rr, mod * 1.05]]);
    }
    if (bore > 0) circle(d = bore, $fn = 24);
  }
}

// A flat spur gear, `th` thick, with optional round lightening holes.
module mech_spur(teeth = 16, mod = 1.6, th = 4, bore = 3.2, lighten = false) {
  pr = mech_pr(teeth, mod);
  linear_extrude(height = th, convexity = 8) {
    difference() {
      mech_spur2d(teeth, mod, bore);
      if (lighten)
        for (i = [0 : 4]) rotate(i * 72)
          translate([pr * 0.5, 0]) circle(d = pr * 0.42, $fn = 20);
    }
  }
}

// A bevel gear: the same 2D profile tapered to a cone by linear_extrude(scale),
// so it hands a horizontal layshaft off to a vertical one at 90°. The scale
// shrinks the bore too, so it is re-drilled straight.
module mech_bevel(teeth = 16, mod = 1.6, face = 6, bore = 3.2) {
  difference() {
    linear_extrude(height = face, scale = 0.5, convexity = 8) mech_spur2d(teeth, mod, 0);
    translate([0, 0, -0.5]) cylinder(d = bore, h = face + 1, $fn = 24);
  }
}

// A 15 mm can-type geared stepper (the reference's 15 mm 1:99 unit): the motor
// can, a smaller gearhead collar, and the output shaft. Axis is +z; length runs
// back along -z. Rendered as the steel `mech_steel` vitamin.
module stepper15(shaft = 8) {
  color(mech_steel) {
    translate([0, 0, -20]) cylinder(d = 15, h = 15, $fn = 40);     // motor can
    translate([0, 0, -6])  cylinder(d = 12, h = 6,  $fn = 40);     // gearhead collar
  }
  color(mech_steel2) cylinder(d = 3, h = shaft, $fn = 20);         // output shaft
}

// A gear lying in the x–z plane (axis along y), so a whole train reads face-on
// from the front of the clock the way the reference's exposed gears do.
module gear_xz(teeth, mod, th = 5, bore = 3.2, lighten = false)
  rotate([90, 0, 0]) translate([0, 0, -th / 2]) mech_spur(teeth, mod, th, bore, lighten);

// One pod drivetrain (origin = the stalk foot; `sgn` = +1 right / −1 left so it
// builds outward toward the pod). A geared stepper at the outer end drives a
// pinion into a horizontal reduction chain that runs back to the stalk, where a
// bevel pair turns the last gear's motion up the vertical stalk at 90°. All the
// gears sit in the x–z plane at one shaft height, framed by the open lattice —
// the reference's "gears in the base". Preview-only (coloured working parts).
module pod_drive(sgn = 1) {
  m  = 1.0;                                   // gear module for the whole train
  z0 = 9;                                     // shaft height above the bottom deck
  th = 5;
  // Chain from the stalk (x=0) outward: final(18T) → idler(12T) → idler(16T) →
  // pinion(9T)+stepper. Each x-step is the meshing centre distance pr_a+pr_b.
  xF = 0;
  x2 = xF + sgn * (mech_pr(18, m) + mech_pr(12, m));
  x1 = x2 + sgn * (mech_pr(12, m) + mech_pr(16, m));
  x0 = x1 + sgn * (mech_pr(16, m) + mech_pr(9,  m));
  // final gear at the stalk foot + the take-off bevel that turns up the stalk
  translate([xF, 0, z0]) color(mech_red) gear_xz(18, m, th, 4, true);
  translate([xF, 0, z0]) color(mech_red2) rotate([90, 0, 0]) mech_bevel(14, m, 6, 4); // layshaft bevel (axis +z after this)
  translate([xF, 0, z0 + 2]) color(mech_red2) mech_bevel(14, m, 6, 4);                // stalk bevel (axis +z)
  // reduction idlers
  translate([x2, 0, z0]) color(mech_red)  gear_xz(12, m, th, 3, true);
  translate([x1, 0, z0]) color(mech_red)  gear_xz(16, m, th, 3, true);
  // pinion + geared stepper at the outer end (stepper can sits behind, −y)
  translate([x0, 0, z0]) {
    color(mech_red) gear_xz(9, m, th, 3);
    rotate([90, 0, 0]) stepper15();           // shaft +y into the pinion, can behind
  }
  // a slim layshaft tying the chain together, along x at the shaft line
  color(mech_steel2)
    translate([min(xF, x0) - 3, 0, z0]) rotate([0, 90, 0]) cylinder(d = 2, h = abs(x0 - xF) + 6, $fn = 16);
}

// Central electronics bay (the reference's middle segment): a PCB carrying the
// ATmega, the DRV8833 driver, a USB-C jack and a row of WS2812 LEDs — the
// board a stranger can see is doing the timekeeping. Preview vitamins.
module electronics_bay() {
  color(mech_pcb) translate([0, 0, 6]) cube([70, 26, 1.6], center = true);   // PCB
  color(mech_chip) {
    translate([-14, 4, 8]) cube([12, 12, 3], center = true);                 // ATmega
    translate([10, -3, 8]) cube([9, 7, 2.5], center = true);                 // DRV8833
  }
  color(mech_steel2) translate([34, 0, 6.5]) cube([8, 9, 3.5], center = true); // USB-C jack
  for (i = [-2 : 2])                                                          // WS2812 row
    color("#f8f8f8") translate([i * 12, -9, 7]) cube([4, 4, 1.4], center = true);
}

// The whole base drivetrain, placed in the truss: a pod at each stalk plus the
// centre bay. Preview-only (coloured working parts), never a printed part.
module base_mech() {
  translate([-ball_spacing / 2, 0, 0]) pod_drive(sgn = -1);
  translate([ ball_spacing / 2, 0, 0]) pod_drive(sgn =  1);
  electronics_bay();
}

// A single gated representative gear (keeps a printable drivetrain part in CI):
// the stage-1 reduction spur, the biggest single gear in the train.
module mock_drive() {
  mech_spur(30, 1.6, 6, 5, true);
  cylinder(d = 10, h = 9, $fn = 32);          // hub/boss
}

// ---- ball red interior (PREVIEW-ONLY two-tone; never in the printed shell) --
// The reference is white shell + red working parts: the numerals read red
// because they cut through to a red interior, and the slot frames a red spiral
// gear. These modules colour that interior for the assembled/ball previews.
// They are deliberately NOT part of hours_ball()/minutes_ball() (which ball_half
// slices for printing), so the printable hemisphere stays a clean white shell.

// Working-parts palette (PREVIEW-ONLY, hoisted so the drivetrain above can use
// it): the reference is a white shell over red mechanism, with steel motors and
// a green PCB. Never affects a printed part (colour is ignored on STL export).
mech_red    = "#c0231f";                 // primary red mechanism
mech_red2   = "#8f1a16";                 // shaded red (bevels / recessed parts)
mech_steel  = "#9aa0a6";                 // motor can
mech_steel2 = "#c8ccd0";                 // shafts / connectors
mech_pcb    = "#1f6f43";                 // PCB substrate
mech_chip   = "#141414";                 // chips

// The red working-parts interior for a ball (the reference's white-shell /
// red-numerals two-tone). Two red elements, both PREVIEW-ONLY and never part of
// the printed white hemisphere:
//   1. a red numeral INLAY that fills each cut-through glyph flush with the
//      plaque, so the numbers read bold red (a backing sphere alone left them as
//      dark slits behind a 2 mm-deep cut);
//   2. a red core sphere just inside the cavity, so the slot window frames red.
// `nums` is the ball's numeral set so the inlay lands exactly in its cut voids.
module ball_core(nums) {
  inner_r = ball_d / 2 * _GB_PENT_R - wall;                       // the cavity radius
  color(mech_red) {
    sphere(r = inner_r, $fn = 72);                                // red core, framed by the slot
    intersection() {
      gb_numbers(ball_d, nums, glyph_h, 0, true, wall, bridge = bridge_w);
      gb_faceted_ball(ball_d - 0.8, tri_k = facet);               // inlay, recessed ~0.4 mm (no z-fight)
    }
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
// A boss on the ridge that RECEIVES the brass support rod: a socket bored to the
// rod diameter + a printer clearance, so the vitamin actually seats (it used to
// be a solid stub the rod had nowhere to enter).
module stalk_boss(x) {
  translate([x, 0, base_h(x)])
    difference() {
      cylinder(d = stalk_d + 5, h = 8, $fn = 32);
      translate([0, 0, 2])
        cylinder(d = stalk_d + 0.4, h = 8, $fn = 32);   // rod socket, 0.4 mm clearance
    }
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
  base_mech();                          // the red gear-trains, motors and PCB in the base
  stalk(-ball_spacing / 2);
  stalk( ball_spacing / 2);
  // hours ball (left): white shell with the red interior read through numerals + slot
  translate([-ball_spacing / 2, 0, ball_center_z]) {
    hours_ball();
    ball_core(gb_hours());
  }
  // minutes ball (right)
  translate([ball_spacing / 2, 0, ball_center_z]) {
    minutes_ball();
    ball_core(gb_minutes());
  }
}

// ---- dispatch --------------------------------------------------------------

if      (part == "assembled")    assembled();
else if (part == "hours-top")    ball_half(hours = true,  top = true);   // even numbers + 12
else if (part == "hours-bottom") ball_half(hours = true,  top = false);  // odd numbers
else if (part == "minutes-top")  ball_half(hours = false, top = true);
else if (part == "minutes-bottom") ball_half(hours = false, top = false);
else if (part == "hours-ball")   { hours_ball();   ball_core(gb_hours()); }    // preview (two-tone)
else if (part == "minutes-ball") { minutes_ball(); ball_core(gb_minutes()); }
else if (part == "base-segment") base_segment();           // constant centre segment
else if (part == "base-end")     base_end();               // tapering end wing
else if (part == "mock-drive")   mock_drive();
else if (part == "base-mech")    base_mech();              // preview: the base drivetrain
else if (part == "pod-drive")    pod_drive();              // preview: one pod's gear train
else assembled();
