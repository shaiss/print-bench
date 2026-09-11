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
use <threads-fdm.scad>        // the captive seam's male/female thread pair (#602)
use <printability.scad>       // chamfered_cylinder for the seam coupon pucks
include <tumble.scad>         // tumble-to-index kinematics: stop table, frames, landing probes (N2, #607)

/* [What to render] */
// assembled | hours-top | hours-bottom | minutes-top | minutes-bottom |
// hours-ball | minutes-ball | base-segment | base-end | mock-drive |
// base-mech | pod-drive | seam-coupon | seam-fit | seam-fit-ctrl |
// landing-flat | landing-flat-ctrl | landing-glyph | landing-glyph-rolled |
// landing-glyph-mirrored | hours-posed |
// base-core | base-plug | core-seat | core-seat-ctrl | pocket-clear | pocket-ctrl
part = "assembled";
// landing-pose stop index 0..11 (ci.kinematics): the stop the landing-* parts test
stop = 0;
// continuous yoke angle (deg) for posed previews (hours-posed)
yoke_deg = 0;

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
// halves join on a CAPTIVE THREADED SEAM (#602, lib/threads-fdm.scad): the
// bottom half grows a short male ring up from its flat seam face just inside
// the shell, the top half carries the matching female thread cut into an
// internal rim boss, and the halves screw closed in exactly ONE turn. The seam
// plane stays a true flat great circle. See NOTES.md "Ball seam" for the
// starts/pitch arithmetic and "Print this first" for tuning.
// Radial thread clearance (mm) — THE one tunable. Print the seam coupon first
// and step it by 0.05: bigger = looser.
seam_tol = 0.25;
// Thread crest (major) diameter of the male ring (mm)
seam_d = 70;
// Radial thread depth (mm); the flanks are 45° so both halves print supportless
seam_depth = 1.0;
// Pitch (mm). Single start, so pitch == lead; the neck is exactly one pitch
// tall, which makes the closing rotation exactly 360°.
seam_pitch = 5;
// Male ring wall under the thread root (mm)
seam_ring_w = 2.0;
// Half-height of the seam band (mm) in which the helical slot is interrupted so
// it never crosses the mating ring — the slot becomes two arcs either side of
// the seam. Numeral cuts come no closer than ~5.5 mm to the seam; keep <= 5.
seam_band = 5;
// 45° chamfer on the outer seam edge of each half (mm) so the seam reads as one
// crisp line and the mating faces meet square, not on an elephant's foot
seam_chamfer = 0.6;
// Helix segments per turn (thread_helix's `seg`); 48 is legal to d_major 93
seam_seg = 48;

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
// Wing tips: the last node rounds to a nose of this diameter (<= 2 x strut_d,
// the needle stays a needle) and the taper floor is small enough that the last
// station's strut ends sit inside that nose
tip_d = 2 * strut_d;
tip_nub = 0.01;
// Feet (vitamin: 4 x stick-on 5 mm hemispherical silicone bumpers, ~1.5 mm
// tall): a small flat pad under each wing's inner-end chord node with a shallow
// recess that locates the bumper. Recess < 5 mm so its roof is a bridgeable span.
foot_pad_d = 7;
foot_pad_drop = 0;        // pad bottom below the chord underside: 0 = flush, so the
                          // wing still prints on its chords; a 1.5 mm bumper stands 0.8 proud
foot_recess_d = 4.9;
foot_recess = 0.7;
// Red structural core ("base-core"): a keel that seats between the centre
// segment's bottom chords, its underside a diamond-channel NEGATIVE of the deck
// lattice (every socket is a real strut, placed from the node functions) so it
// drops onto the deck in exactly one pose; two sealed ballast pockets fill
// through a plugged port on the +x end face. Top stays under the 9 mm gear
// line; the PCB sits in the central trough.
core_len = 120;           // along x (inside the 127 mm centre segment)
core_w = 63;              // bottom width (between the chords: 76 - struts - slide clearance)
core_top_hw = 24.2;       // half-width at the top: clears the ridge posts when slid in raised
core_skirt = 2.6;         // vertical skirt before the flank leans in: taller than the
                          // socket crests, so every channel exits a vertical face (no cusp)
core_h = 8.8;             // keel height above the deck plane (< 9 mm shaft line)
core_trough_w = 28;       // PCB trough width (26 mm PCB + clearance)
core_trough_z = 4.6;      // trough floor (PCB underside is at 5.2)
core_wall = 1.4;          // pocket / ceiling / end wall thickness (>= 1.2)
core_fit = 0.3;           // radial clearance of the strut sockets (mm)
core_port_d = 3.2;        // ballast fill port bore (mm), on the +x end face (round: a
                          // <5 mm roof bridges; sits above the socket crests with a full wall)
core_port_wall = 4.2;     // end wall the port bores through (plug seat)
plug_head_d = 5;          // plug head (sits proud on the end face, inside the joint gap)
plug_head_h = 1.2;

/* [Quality] */
// Iterating: 40. Production: 64+ .
$fn = 48;

// ---- balls -----------------------------------------------------------------

// Numerals are placed in TUMBLE order (tumble.scad): numeral k lives on the face
// that presents at stop k, clocked by tumble_rots() so it reads upright there.
module hours_ball() {
  geodesic_ball(d = ball_d, nums = tumble_nums(gb_hours()), tri_k = facet,
                wall = wall, glyph_h = glyph_h, through = numerals_through, bridge = bridge_w,
                slot = true, slot_width = slot_width, slot_turns = slot_turns,
                rots = tumble_rots());
}

module minutes_ball() {
  // opposite-handed slot differentiates it from the hours ball
  geodesic_ball(d = ball_d, nums = tumble_nums(gb_minutes()), tri_k = facet,
                wall = wall, glyph_h = glyph_h, through = numerals_through, bridge = bridge_w,
                slot = true, slot_width = slot_width, slot_turns = -slot_turns,
                rots = tumble_rots());
}

// Pole-up tilt: bring a pentagon face to each ±z pole so the equatorial split
// runs through the triangle band and no number face is bisected. atan2(1,PHI)
// is the colatitude of icosa vertex [0,1,PHI], so this rotation lands it on +z.
_pole_up = atan2(1, PHI);

// ---- captive threaded seam (#602) -----------------------------------------
// One thread pair from lib/threads-fdm.scad, so male and female cannot drift:
// the bottom half carries the male RING (thread_neck bored to a ring) standing
// on its seam face, the top half the female GROOVE (thread_bore_cut + the
// mandatory minor bore) in an internal rim boss. Single start, neck height ==
// pitch: the seated clocking is unique (the ball has NO rotational symmetry
// about the pole axis once it carries twelve different numerals, so only the
// identity clocking reassembles it — NOTES.md has the starts arithmetic) and
// the closing rotation is exactly 360°: line the facets up, drop the top on
// (it only enters at that one clocking), one full turn, and the facets are
// lined up again as the faces meet.
seam_len       = seam_pitch;                     // neck height: one lead, one turn
_seam_r_maj    = seam_d / 2;                     // male crest radius
_seam_r_min    = _seam_r_maj - seam_depth;       // male root radius
_seam_r_in     = _seam_r_min - seam_ring_w;      // male ring inner radius
_seam_r_bore   = _seam_r_min + seam_tol;         // female MINOR bore (mandatory)
_seam_over     = 0.3;                            // groove runs this far past the neck top, then closes
_seam_mouth    = 0.6;                            // female mouth chamfer (breaks the bore edge)
_cavity_r      = ball_d / 2 * _GB_PENT_R - wall; // the shell's spherical cavity radius
_seam_weld_r   = _cavity_r + 0.5;                // boss outer sphere: 0.5 mm into the wall, so it welds
// Rim-boss roof cone: radius grows tan(40°) per mm of height, i.e. the roof is
// 50° from horizontal — a 40° overhang, inside the 45° rule with margin (a
// roof at exactly 45° tessellates to 44.98° and sits on printcheck's threshold).
_seam_roof     = tan(40);
// Top boss height at the bore: the groove's closed top plus enough roof rise to
// keep >= 1.2 mm of wall outside the groove crest (radial seam_depth + 1.2)
_seam_boss_top = seam_len + _seam_over + (seam_depth + 1.2) / _seam_roof;
// Bottom foundation depth: the roof must reach the cavity wall from the ring's
// inner radius, plus a 2 mm plate where it meets the wall
_seam_found_h  = (_cavity_r - _seam_r_in) / _seam_roof + 2;

// The male ring: the library neck (lead-in chamfer included) bored to a ring
// `seam_ring_w` thick under the root. Sits on z = 0, rises `seam_len`.
module _seam_neck() {
  difference() {
    thread_neck(seam_d, seam_depth, seam_pitch, 1, seam_len, seg = seam_seg);
    translate([0, 0, -1]) cylinder(r = _seam_r_in, h = seam_len + 2, $fn = 96);
  }
}

// The female cutter, rising from z = 0: the MANDATORY minor bore (per
// thread_bore_cut's doc it cuts the groove only — without the bore the top
// half is a solid plug the ring cannot enter, watertight and gate-passing),
// the groove itself, and a small mouth chamfer on the bore edge.
module _seam_female_cut() {
  translate([0, 0, -1]) cylinder(r = _seam_r_bore, h = _seam_boss_top + 3, $fn = 96);
  thread_bore_cut(seam_d, seam_depth, seam_pitch, 1, seam_len, seam_tol,
                  over = _seam_over, seg = seam_seg);
  translate([0, 0, -0.01])
    cylinder(r1 = _seam_r_bore + _seam_mouth, r2 = _seam_r_bore, h = _seam_mouth + 0.01, $fn = 96);
}

// The rim boss inside the cavity at the seam — the top half's female blank
// (bore radius `_seam_r_bore`, `_seam_boss_top` tall) or the bottom half's
// neck foundation (bore `_seam_r_in`, `_seam_found_h` deep). Bounded by the
// cavity sphere grown 0.5 mm (so it welds into the wall) and by a roof cone
// (`_seam_roof`) from the bore edge out to the wall, so its cavity-facing end
// is never a flat ledge: printed pole-down that end faces the bed, and the
// roof prints as a 40° overhang. The roof also keeps the boss clear of the
// numeral cuts, which come no closer than r ≈ 36.6 within 7 mm of the seam
// (the boss is at r <= 35.0 by z = 7).
module _seam_boss(top = true) {
  r0  = top ? _seam_r_bore : _seam_r_in;
  h   = top ? _seam_boss_top : _seam_found_h;
  zlo = top ? -1 : -h - 1;
  difference() {
    intersection() {
      sphere(r = _seam_weld_r, $fn = 96);
      if (top) cylinder(r1 = r0 + _seam_roof * h, r2 = r0, h = h, $fn = 96);
      else translate([0, 0, -h]) cylinder(r1 = r0, r2 = r0 + _seam_roof * h, h = h, $fn = 96);
    }
    translate([0, 0, zlo]) cylinder(r = r0, h = h + 2, $fn = 96);
  }
}

// Refills the shell WALL (not the cavity) within |z| <= seam_band, which is
// how the helical slot is clipped short of the seam in each half: the slot
// becomes two arcs reading as one interrupted helix, and never crosses the
// mating ring (a deliberate divergence from the reference's "the slot is the
// seam", accepted in #602). Numeral cuts stay outside the band.
module _seam_band_fill() {
  intersection() {
    difference() {
      rotate([_pole_up, 0, 0]) gb_faceted_ball(ball_d, tri_k = facet);
      sphere(r = _cavity_r, $fn = 96);
    }
    cube([ball_d * 2, ball_d * 2, 2 * seam_band], center = true);
  }
}

// The 45° chamfer along the OUTER seam edge, following every facet: within
// `seam_chamfer` of the seam each of the ball's 32 face planes n·p <= D is
// tightened to n·p <= D - c + sgn·z, i.e. the half-space with normal
// (n - sgn·ẑ) at offset D - c, so the surface pulls in by (c - |z|) along its
// own normal and the two halves meet on a crisp V line with square faces.
function _seam_rotx(v, a) = [v[0], v[1] * cos(a) - v[2] * sin(a), v[1] * sin(a) + v[2] * cos(a)];
function _seam_planes() = let (R = ball_d / 2)
  concat([for (n = gb_icosa_verts())  [_seam_rotx(n / norm(n), _pole_up), R]],
         [for (n = gb_dodeca_verts()) [_seam_rotx(n / norm(n), _pole_up), R * facet]]);
module _seam_halfspace(n, dist, big = 600) {           // {p : n̂·p <= dist}
  d  = n / norm(n);
  ax = [-d[1], d[0], 0];
  if (norm(ax) < 1e-9)
    translate([0, 0, (d[2] >= 0 ? dist - big / 2 : -dist + big / 2)]) cube(big, center = true);
  else
    rotate(a = acos(max(-1, min(1, d[2]))), v = ax)
      translate([0, 0, dist - big / 2]) cube(big, center = true);
}
module _seam_edge_chamfer(sgn = 1) {
  tilted = [for (pl = _seam_planes()) let (m = pl[0] - [0, 0, sgn])
              if (norm(m) > 0.3) [m / norm(m), (pl[1] - seam_chamfer) / norm(m)]];
  intersection_for (t = tilted) _seam_halfspace(t[0], t[1]);
}

// The pole-up ball with the seam band refilled — the common shell both halves
// are cut from (the bosses differ per half, so they are added in ball_half_seated).
module _ball_body(hours = true) {
  rotate([_pole_up, 0, 0]) { if (hours) hours_ball(); else minutes_ball(); }
  _seam_band_fill();
}

// One HEMISPHERE in the ball frame at the SEATED pose: seam plane z = 0, the
// top half above it carrying the female boss, the bottom half below it with
// the male ring standing up through z = 0. This is the frame the fit checks
// intersect in (`seam-fit`); ball_half() orients it for the bed.
module ball_half_seated(hours = true, top = true) {
  if (top)
    difference() {
      intersection() {
        union() { _ball_body(hours); _seam_boss(top = true); }
        translate([0, 0, ball_d]) cube(ball_d * 2, center = true);   // keep z >= 0
        _seam_edge_chamfer(1);
      }
      _seam_female_cut();
    }
  else
    union() {
      intersection() {
        union() { _ball_body(hours); _seam_boss(top = false); }
        translate([0, 0, -ball_d]) cube(ball_d * 2, center = true);  // keep z <= 0
        _seam_edge_chamfer(-1);
      }
      _seam_neck();
    }
}

// One printable HEMISPHERE, POLE-DOWN on the bed: the flat pole pentagon is the
// first layer, the seam ring is the top of the print. `top` selects the +z half
// (even numbers, female thread) or the -z half (odd numbers, male ring). Print
// two halves per ball — a top AND a bottom — to get all 12 numbers. Pole-down
// is forced by the seam (a ring standing on the seam face cannot print
// seam-face-down) and is also the overhang-free orientation for a hollow
// hemisphere: the cavity is an open bowl, not a ceiling, and the faces next to
// the pole lean out at 26.6°.
module ball_half(hours = true, top = true) {
  translate([0, 0, ball_d / 2])
    if (top) rotate([180, 0, 0]) ball_half_seated(hours, true);
    else     ball_half_seated(hours, false);
}

// Fit proof (designs/ovodyo/ci.fitchecks): the male ring intersected with the
// top half at the seated pose must render EMPTY at seam_tol; the control parks
// the top half a quarter-turn off (pitch/4 axial mismatch) and must interfere.
module seam_fit(ctrl = false) {
  intersection() {
    _seam_neck();
    rotate([0, 0, ctrl ? 90 : 0]) ball_half_seated(hours = true, top = true);
  }
}

// "Print this first": the male ring on a thin chamfered flange (the seam face
// stand-in) beside a chamfered puck carrying the female cut, mouth UP the way
// the top half prints — both from the production seam modules, nothing copied.
// Tune seam_tol on this pair before printing four ball halves.
module seam_coupon() {
  gap      = 6;
  flange_r = _seam_r_maj + seam_tol + 2;     // 2 mm past the female crest, like the seam face
  puck_r   = _seam_r_maj + seam_tol + 3;     // 3 mm of wall around the groove crest
  puck_h   = _seam_boss_top;
  translate([-(puck_r + gap), 0, 0]) {
    difference() {
      chamfered_cylinder(d = 2 * flange_r, h = 1.5, chamfer1 = 0.6, chamfer2 = 0);
      translate([0, 0, -1]) cylinder(r = _seam_r_in, h = 4, $fn = 96);
    }
    translate([0, 0, 1.5 - 0.01]) _seam_neck();
  }
  translate([puck_r + gap, 0, puck_h]) rotate([180, 0, 0])
    difference() {
      chamfered_cylinder(d = 2 * puck_r, h = puck_h, chamfer1 = 0.6, chamfer2 = 0.6);
      _seam_female_cut();
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
      gb_numbers(ball_d, tumble_nums(nums), glyph_h, 0, true, wall, bridge = bridge_w,
                 rots = tumble_rots());                            // same tumble order/clocking as the cuts
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
  : max(tip_nub, 1 - (abs(x) - seg_len / 2) / seg_len);

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

// ---- wing tip, feet -------------------------------------------------------

// The needle's nose: one round node of tip_d at the tip station, enclosing the
// three shrunken strut ends there (tip_nub keeps them inside it), so the wing
// ends in a single Ø5.6 bead — no cap, no truncated bay, base_t untouched.
module tip_nose(x) {
  // bottom flush with the chord underside, so the wing still prints on its chords
  translate([x, 0, tip_d / 2 - strut_d / 2]) sphere(d = tip_d, $fn = 24);
}

// A foot: a small flat pad hanging under a bottom-chord node (inboard of the
// chord's outer face, so it is invisible from the side/hero and shows only in
// the bottom-iso view) with a shallow recess that locates a stick-on bumper.
// `side` = -1 (BL chord) / +1 (BR chord). The pad's top reaches into the chord
// so it fuses; its bottom is the print's lowest face (flat bed contact).
module foot_pad(x, side) {
  h = strut_d / 2 + foot_pad_drop;           // from the deck plane down to the pad bottom
  translate([x, side * (_bw(x) - 2), 0])
    difference() {
      translate([0, 0, -h]) cylinder(d = foot_pad_d, h = h + 0.6, $fn = 32);
      translate([0, 0, -h - 1]) cylinder(d = foot_recess_d, h = foot_recess + 1, $fn = 32);
    }
}

// the two feet of one wing, just inboard of its wide (joint) end
module wing_feet() {
  x = _bx(bays) - foot_pad_d / 2 - 0.5;
  foot_pad(x, -1);
  foot_pad(x,  1);
}

// ---- red structural core (base-core) + ballast plug (base-plug) ------------
// The keel's y–z section: flat bottom, a short vertical skirt, flanks leaning
// in to core_top_hw, a flat rail top each side and the PCB trough between.
function _core_sec() = [
  [-core_w / 2, 0], [core_w / 2, 0], [core_w / 2, core_skirt],
  [core_top_hw, core_h], [core_trough_w / 2, core_h],
  [core_trough_w / 2, core_trough_z], [-core_trough_w / 2, core_trough_z],
  [-core_trough_w / 2, core_h], [-core_top_hw, core_h],
  [-core_w / 2, core_skirt]
];

// section -> solid along x, centred; `shrink` erodes the section (and the
// ends) by that much — the fitcheck's "inside the wall" region.
module _core_extrude(sec, len, shrink = 0) {
  rotate([90, 0, 90]) linear_extrude(len - 2 * shrink, center = true)
    offset(r = -shrink) polygon(sec);
}

// A 45°-ish diamond (peak up/down, roof just steeper than 45° so it is never
// an overhang) with horizontal inradius r: the channel section a round strut
// nests in support-free.
// (after rotate([0, 90, 0]) the 2D x axis is the world vertical, so the 1.06
// stretch is applied to x.)
module _diamond(r) { scale([1.06, 1]) rotate(45) square(2 * r, center = true); }

// One socket: a diamond prism along a deck strut p1->p2 (both at z = 0).
// r = the strut radius + clearance (+ wall, for the pocket-side hump).
module _core_socket(p1, p2, r) {
  v = p2 - p1;
  translate(p1) rotate([0, 0, atan2(v[1], v[0])]) rotate([0, 90, 0])
    linear_extrude(norm(v)) _diamond(r);
}

// every deck strut of the centre segment: the ties and Warren diagonals —
// the same node functions base_truss draws them from, so the sockets ARE the
// lattice and the core can seat in one pose only (the zigzag is not 180°-
// symmetric about the segment centre).
module _core_sockets(r) {
  for (i = [bays : 2 * bays]) _core_socket(_BL(i), _BR(i), r);
  for (i = [bays : 2 * bays - 1])
    if (i % 2 == 0) _core_socket(_BL(i), _BR(i + 1), r);
    else            _core_socket(_BR(i), _BL(i + 1), r);
}

// One ballast pocket (side s = ±1), y–z section: floor at core_wall, a
// vertical inner wall then a 44°-from-vertical slope out, a vertical outer wall
// up to the skirt height then a 44.5° slope in (never an overhang from inside),
// and a flat ceiling strip < 5 mm wide (a bridgeable span). `zc` is the ceiling
// height (the control raises it through the roof). The socket humps (sockets
// grown by the wall) are removed so the cavity keeps >= core_wall to every
// channel. yo1 sits inside the flank eroded by the wall (pocket-clear proves it).
function _pocket_sec(s, zc) =
  let (w = core_wall, yi = core_trough_w / 2 + w, zi = zc - 4.0,
       yo1 = core_top_hw - 0.5, yo0 = yo1 + (zc - core_skirt) * 0.983)
  [ for (p = [[yi, w], [yo0, w], [yo0, core_skirt], [yo1, zc], [yi + 3.9, zc], [yi, zi]])
      [s * p[0], p[1]] ];

module _core_pocket(s, zc = core_h - core_wall) {
  x0 = -core_len / 2 + core_wall;
  x1 =  core_len / 2 - core_port_wall;
  difference() {
    translate([(x0 + x1) / 2, 0, 0])
      rotate([90, 0, 90]) linear_extrude(x1 - x0, center = true) polygon(_pocket_sec(s, zc));
    _core_sockets(strut_d / 2 + core_fit + core_wall);
  }
}
module _core_cavity(zc = core_h - core_wall) { _core_pocket(-1, zc); _core_pocket(1, zc); }

// fill port: a round bore along x through the +x end wall into each pocket,
// placed above every socket crest (a full wall under it) and clear of the
// end-bay diagonal hump inside the cavity; the plug head sits proud on the end
// face, inside the 3.5 mm gap to the segment's end tie.
function _port_y(s) = s * (core_trough_w / 2 + core_wall + 6.6);
_port_z = 5.75;
module _core_ports() {
  for (s = [-1, 1]) translate([core_len / 2, _port_y(s), _port_z])
    rotate([0, 90, 0]) cylinder(d = core_port_d, h = 2 * core_port_wall + 2, center = true, $fn = 32);
}

// the printed core: keel body − strut sockets − ballast pockets − ports.
// Modelled in place (seated pose), flat bottom on z = 0: prints as-is.
module core_body() {
  difference() {
    _core_extrude(_core_sec(), core_len);
    _core_sockets(strut_d / 2 + core_fit);
    _core_cavity();
    _core_ports();
  }
}

// the ballast plug (print two): flat head down, a tapered shank that wedges in
// the port bore. Tip Ø < bore, root Ø slightly > bore.
module core_plug() {
  cylinder(d = plug_head_d, h = plug_head_h, $fn = 40);
  translate([0, 0, plug_head_h])
    cylinder(d1 = core_port_d + 0.1, d2 = core_port_d - 0.5, h = core_port_wall + 0.3, $fn = 40);
  // (prints head-down: a cone narrowing upward, no overhang)
}
// a plug seated in its port (preview): head on the end face, shank into the bore
module core_plug_seated(s) {
  translate([core_len / 2 + plug_head_h, _port_y(s), _port_z]) rotate([0, -90, 0]) core_plug();
}

// ---- fit checks (ci.fitchecks; dispatch parts, never printed) ------------
// core-seat: the seated core ∩ the centre segment's struts must be EMPTY (the
// core nests without cutting a strut). core-seat-ctrl shifts it half a bay so
// the ties run through the keel — the mandatory negative control.
module core_seat_check(shift = 0) {
  intersection() {
    translate([shift, 0, 0]) core_body();
    base_segment();
  }
}
// pocket-clear: the ballast cavity ∩ the core's outer 1.2 mm shell wall must be
// EMPTY (the cavity is fully enclosed, wall >= 1.2 everywhere: outer skin,
// ends, trough, and every strut channel). pocket-ctrl over-fills the cavity up
// through the roof so it MUST overlap.
module _core_shell_wall(t = 1.2) {
  difference() {
    difference() { _core_extrude(_core_sec(), core_len); _core_sockets(strut_d / 2 + core_fit); }
    difference() { _core_extrude(_core_sec(), core_len, shrink = t); _core_sockets(strut_d / 2 + core_fit + t); }
  }
}
module core_pocket_check(overfill = false) {
  intersection() {
    _core_cavity(zc = overfill ? core_h - 0.4 : core_h - core_wall);
    _core_shell_wall();
  }
}

// ---- segments ---------------------------------------------------------------

// CENTRE segment (constant section) — the gated representative part
module base_segment() { base_truss(bays, 2 * bays); }

// one END wing, tapering to a needle point, with its stalk boss over the pod,
// its Ø5.6 nose, and the two feet at its wide end
module base_end() {
  base_truss(0, bays);
  stalk_boss(-ball_spacing / 2);
  tip_nose(_bx(0));
  wing_feet();
}

module full_base() {
  base_truss(0, n_bays);                   // the whole tapered lattice
  stalk_boss(-ball_spacing / 2);
  stalk_boss( ball_spacing / 2);
  tip_nose(_bx(0));
  tip_nose(_bx(n_bays));
  wing_feet();
  mirror([1, 0, 0]) wing_feet();
  color(mech_red) {                        // red = working part: the structural core + its plugs
    core_body();
    core_plug_seated(-1);
    core_plug_seated(1);
  }
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
else if (part == "seam-coupon")  seam_coupon();            // print this first: male ring + female puck
else if (part == "seam-fit")     seam_fit(false);          // fitcheck: must render EMPTY
else if (part == "seam-fit-ctrl") seam_fit(true);          // fitcheck control: must interfere
// tumble kinematics (N2, ci.kinematics): landing-pose booleans at stop `stop`
else if (part == "landing-flat")           landing_flat(stop);           // empty: plaque within tol of +x
else if (part == "landing-flat-ctrl")      landing_flat_ctrl(stop);      // control: 20 deg off, must hit
else if (part == "landing-glyph")          landing_glyph(stop);          // empty: numeral upright + unmirrored
else if (part == "landing-glyph-rolled")   landing_glyph_rolled(stop);   // control: template rolled 30 deg
else if (part == "landing-glyph-mirrored") landing_glyph_mirrored(stop); // control: template mirrored
else if (part == "hours-posed")            // preview: the hours ball posed at yoke_deg, viewer at +x
  tumble_pose(yoke_deg) tumble_ball_frame() { hours_ball(); ball_core(gb_hours()); }
else if (part == "base-core")    core_body();              // red structural core (ballast keel)
else if (part == "base-plug")    core_plug();              // ballast port plug (print two)
else if (part == "core-seat")      core_seat_check();               // fitcheck: seated core ∩ segment = empty
else if (part == "core-seat-ctrl") core_seat_check(shift = base_L / n_bays / 2);  // control: half a bay off → interferes
else if (part == "pocket-clear")   core_pocket_check();             // fitcheck: cavity ∩ 1.2 mm shell = empty
else if (part == "pocket-ctrl")    core_pocket_check(overfill = true);  // control: cavity through the roof → interferes
else assembled();
