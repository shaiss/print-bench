// tumble.scad — ovodyo tumble-to-index kinematics (charter N2): the frames, the
// baked 12-stop table, the numeral orientation that reads upright at each stop,
// and the landing-pose boolean parts ci.kinematics gates. DESIGN-LOCAL: included
// by ovodyo.scad after geodesic-ball.scad, and it reads the design's parameters
// (ball_d, wall, glyph_h, bridge_w, numerals_through, _pole_up, hours_ball()).
//
// SIGN CONVENTION (the one sentence the mechanism must match): with the mount
// M = rotate([-90,0,0]) carrying the ball's +z pole axis onto world +y, the bevel
// CROWN mounted on the +pole side of the hub axle with its teeth facing the ball
// centre, and the fixed bevel SUN on the stalk BELOW the ball centre, a yoke
// rotation of +phi about world +z spins the ball about its own +pole axis by
// -tumble_rho*phi (right-hand sense about the +pole direction), so the ball's
// orientation is Q(phi) = Rz(phi) * Ry(-tumble_rho*phi) * M  (world <- ball).
//
// Why that sign: a bevel planet rolling on a FIXED bevel sun with perpendicular
// axes has its instantaneous rotation axis through the shared cone apex (the
// ball centre) and the tooth-contact point; the contact generator points from
// the apex DOWN toward the sun and OUT toward the crown, so resolving
// omega = omega_yoke*z + omega_spin*a along it gives
// omega_spin = -omega_yoke*tan(gamma_sun) = -omega_yoke*n_sun/n_crown. Mount the
// crown on the -pole side instead and the spin flips to +rho*phi: then the Ry
// sign here, the whole stop table and every numeral rotation change — rerun
// tumble_stops.py with RHO negated, never hand-edit the baked block.
//
// Frames (right-handed; rotate() conventions):
//   WORLD  +x points at the viewer (the presenting direction F), +z up.
//   BALL   the design's POLE-UP frame: the generator's output rotated by
//          rotate([_pole_up,0,0]) so a pentagon plaque sits at each +-z pole;
//          ball +z is the hub axle (the 5-fold axis). tumble_ball_frame() takes
//          hours_ball()/minutes_ball() output into it.
//   M      tumble_mount(): rotate([-90,0,0]) — ball +z (pole) -> world +y.
//   Q(phi) tumble_pose(phi): rotate([0,0,phi]) rotate([0,-rho*phi,0]) M.
//
// A plaque LANDS at yoke angle phi when its outward normal is within
// tumble_tol_deg of +x; its numeral is upright when the numeral's in-plane 'up'
// is within the same tolerance of world +z. Two facts the table rests on:
//   * No single rotation axis can present the 12 dodecahedral plaques: the
//     rotation group has no order-12 element (orders 1/2/3/5 only), and at most
//     5 plaques share one cone about any axis — hence the compounded yoke+crown
//     motion, and a stop table that is irregular in yoke angle.
//   * The two POLE plaques' normals are +-the axle, which the yoke keeps
//     horizontal, so they can only ever land exactly for a HORIZONTAL viewer —
//     that is why F = +x is horizontal; they land at phi = 90 and 270 (mod 360).
// The numbers below are derived, not typed: designs/ovodyo/tumble_stops.py
// (stdlib+numpy) sweeps Q(phi) over the 5-yoke-turn cycle and bakes the block.

/* [Tumble mechanism] */
// Fixed bevel sun teeth (on the stator stalk)
tumble_n_sun = 12;
// Bevel crown teeth (on the ball's hub axle)
tumble_n_crown = 20;
// Crown turns per yoke turn = n_sun/n_crown (3/5); the cycle closes after 5
// yoke turns = 3 crown turns
tumble_rho = tumble_n_sun / tumble_n_crown;
// Landing tolerance (deg): plaque normal off +x, numeral 'up' off +z
tumble_tol_deg = 3;

/* [Landing probes (ci.kinematics)] */
// Flat-landing probe: a slab of this radius (mm) about the x axis, standing
// eps = r*sin(tol) above the plaque plane, so a plaque tilted past tol rises
// into it at the probe's edge
tumble_probe_r = 12;
// Probe slab depth along x (mm)
tumble_probe_h = 6;
// Numeral template growth (mm): the posed cutter must sit inside the upright
// stencil grown by this much
tumble_glyph_grow = 1.0;
// Band radius (mm) the glyph check is bounded to — clears the widest numeral
// ("12"/"10" at glyph_h 14 spans ~17 mm) so nothing of the glyph is clipped
tumble_glyph_band_r = 16;

// ---- BAKED by tumble_stops.py — do not edit by hand. Regenerate + verify with:
// ----   python3 designs/ovodyo/tumble_stops.py --write   (then --check)
// Yoke angle (deg) of stop k; stop k presents numeral k (0 = "12"/"00").
function tumble_stops() = [27.3361, 90.0000, 270.0000, 332.6639, 387.3361, 692.6639, 747.3361, 1052.6639, 1107.3361, 1412.6639, 1467.3361, 1772.6639];
// Face (gb_icosa_verts() index) presented at stop k — numeral k lives there.
function tumble_face_order() = [9, 3, 0, 10, 7, 4, 1, 2, 5, 6, 11, 8];
// Landing error (deg) of stop k: the presented normal's angle off +x.
function tumble_errors() = [1.6200, 0.0000, 0.0000, 1.6200, 1.6200, 1.6200, 1.6200, 1.6200, 1.6200, 1.6200, 1.6200, 1.6200];
// Per-FACE in-plane numeral rotation (deg, CCW seen from outside) so the
// numeral on face f reads upright at its own stop.
function tumble_rots() = [-18.0000, -89.2851, 90.7149, -54.0000, -139.0025, 104.4324, -39.5676, 76.9975, 144.7149, 144.7149, 36.7149, 36.7149];
// ---- end BAKED

// yoke angle (deg) of stop k (0..11, numeral order: 0 = "12"/"00")
function tumble_yoke(stop) = tumble_stops()[stop];
// the stop index at which face f (gb_icosa_verts() order) presents
function tumble_stop_of_face(f) = [for (k = [0 : 11]) if (tumble_face_order()[k] == f) k][0];
// a numeral list (numeral order, e.g. gb_hours()) REORDERED to face order for
// gb_numbers: nums_by_face[f] = numerals[k] where tumble_face_order()[k] == f
function tumble_nums(numerals) = [for (f = [0 : 11]) numerals[tumble_stop_of_face(f)]];
// crown (ball-about-axle) angle at yoke angle phi
function tumble_crown_deg(phi) = -tumble_rho * phi;
// [min, max] crown angle over the stop table — the stalk-gap sweep. The span
// exceeds 360, so the stalk sweeps the ball's whole equator over a cycle.
function tumble_crown_range() =
  let (c = [for (s = tumble_stops()) tumble_crown_deg(s)]) [min(c), max(c)];

// ---- frames ----------------------------------------------------------------
// generator output -> the pole-up BALL frame (the design's split/mount frame)
module tumble_ball_frame() rotate([_pole_up, 0, 0]) children();
// M: pole-up ball frame -> world, ball +z (pole axis) onto world +y
module tumble_mount() rotate([-90, 0, 0]) children();
// Q(phi): the ball posed at yoke angle phi (children in the pole-up ball frame)
module tumble_pose(phi)
  rotate([0, 0, phi]) rotate([0, -tumble_rho * phi, 0]) tumble_mount() children();

// vector rotations mirroring rotate([a,0,0]) / [0,a,0] / [0,0,a]
function _tumble_rx(v, a) = [v.x, cos(a) * v.y - sin(a) * v.z, sin(a) * v.y + cos(a) * v.z];
function _tumble_ry(v, a) = [cos(a) * v.x + sin(a) * v.z, v.y, -sin(a) * v.x + cos(a) * v.z];
function _tumble_rz(v, a) = [cos(a) * v.x - sin(a) * v.y, sin(a) * v.x + cos(a) * v.y, v.z];
// face f's outward normal in the pole-up ball frame
function tumble_face_normal_ball(f) =
  let (v = gb_icosa_verts()[f]) _tumble_rx(v / norm(v), _pole_up);
// face f's outward normal in WORLD at yoke angle phi (= Q(phi) applied)
function tumble_face_normal(f, phi) =
  _tumble_rz(_tumble_ry(_tumble_rx(tumble_face_normal_ball(f), -90), -tumble_rho * phi), phi);
// the landing error (deg) the geometry actually has at stop k — must equal
// tumble_errors()[k] (the python and the scad frames agree)
function tumble_landing_error(stop) =
  acos(min(1, tumble_face_normal(tumble_face_order()[stop], tumble_yoke(stop)).x));

// ---- landing-pose boolean parts (ci.kinematics) ----------------------------
// Geometry-true: every check is a real CGAL render whose facet count is read.

// The probe: x in [Rp+eps, Rp+eps+h] inside a cylinder of radius r about +x,
// Rp = ball_d/2 (the plaque plane), eps = r*sin(tol).
module _tumble_probe() {
  Rp  = ball_d / 2;
  eps = tumble_probe_r * sin(tumble_tol_deg);
  translate([Rp + eps, 0, 0]) rotate([0, 90, 0])
    cylinder(r = tumble_probe_r, h = tumble_probe_h, $fn = 48);
}

// landing_flat(stop): the hours ball as it ships (numerals in tumble order with
// their per-face rotations) posed at stop `stop`, intersected with the probe.
// EMPTY iff the presenting plaque is within tumble_tol_deg of +x: a tilted
// plaque rises into the slab at the probe's edge. `extra` de-tunes the pose
// for the negative control.
module landing_flat(stop, extra = 0) {
  intersection() {
    tumble_pose(tumble_yoke(stop) + extra) tumble_ball_frame() hours_ball();
    _tumble_probe();
  }
}
// negative control: 20 deg past the stop the plaque MUST hit the probe
module landing_flat_ctrl(stop) landing_flat(stop, extra = 20);

// the glyph band: cylinder about +x over the shell's radial band at the plaque
module _tumble_glyph_band() {
  Rp = ball_d / 2;
  translate([Rp - wall - 2, 0, 0]) rotate([0, 90, 0])
    cylinder(r = tumble_glyph_band_r, h = wall + 4, $fn = 48);
}
module _tumble_mirror2d(m) { if (m) mirror([1, 0]) children(); else children(); }
// the upright TEMPLATE: the same stencil extruded along +x at the presenting
// plaque's centre (cy, cz), its 2D up = world +z (rotate([90,0,90]) carries 2D
// +x -> world +y = the viewer's right, 2D +y -> world +z), grown by
// tumble_glyph_grow; `roll`/`mirrored` de-tune it for the controls.
module _tumble_template(s, cy, cz, roll = 0, mirrored = false) {
  Rp = ball_d / 2;
  translate([Rp - wall - 3, cy, cz]) rotate([90, 0, 90])
    linear_extrude(height = wall + 6, convexity = 6)
      offset(r = tumble_glyph_grow)
        rotate(roll) _tumble_mirror2d(mirrored) _gb_stencil(s, glyph_h, bridge_w);
}

// landing_glyph(stop): the presenting face's through-cut numeral SOLID (the very
// cutter gb_numbers subtracts, with its baked in-plane rotation) posed at the
// stop and bounded to the band, MINUS the upright template. EMPTY iff the
// numeral is aligned and unmirrored within ~tumble_glyph_grow.
module landing_glyph(stop, roll = 0, mirrored = false) {
  f    = tumble_face_order()[stop];
  phi  = tumble_yoke(stop);
  nums = tumble_nums(gb_hours());                 // the hours ball's numerals by face
  c    = (ball_d / 2) * tumble_face_normal(f, phi); // the presenting plaque's centre
  difference() {
    intersection() {
      tumble_pose(phi) tumble_ball_frame()
        gb_number_cutter(ball_d, nums[f], glyph_h, gb_icosa_verts()[f], tumble_rots()[f],
                         0.8, numerals_through, wall, bridge_w);
      _tumble_glyph_band();
    }
    _tumble_template(nums[f], c.y, c.z, roll, mirrored);
  }
}
// negative controls: a template rolled 30 deg / mirrored MUST leave material
module landing_glyph_rolled(stop)   landing_glyph(stop, roll = 30);
module landing_glyph_mirrored(stop) landing_glyph(stop, mirrored = true);
