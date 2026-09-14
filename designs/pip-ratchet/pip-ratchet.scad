// pip-ratchet — a print-in-place ratchet wheel: one piece, printed as-is, that
// freewheels with a click one way and locks solid the other. Brief #668: a
// captive 24-tooth wheel driven between two diametric pawls, each a tangential
// cantilever beam cut from the frame, engaging teeth whose locking flank is
// RADIAL (0° from radial — the self-locking geometry docs/advanced-techniques.md
// Domain 1 names) and whose drive flank is a 60° ramp the pawl rides up.
//
// Prints in place, no supports, no assembly. The discipline is the
// captive-spinner's (its direct sibling — a captive rotor on a post + 45°
// cone cap) with the rotor now toothed and the "bearing" now two flexing pawls:
//   - RADIAL gaps (bore↔post, tooth tips↔frame, tooth wall↔pawl nose) are
//     spread-limited and tight: xy_tol = k_xy·line_w.
//   - AXIAL gaps (wheel↔base below, wheel↔cone above) are sag-limited, whole
//     layers: z_tol = z_layers·layer_h.
//   - The wheel's first layer prints z_tol above the base — the deliberate
//     weak fusion you shear on the break-free first motion (CC2).
//
// Handedness (derived, kept here because every tooth line depends on it):
// free = CCW. Each tooth's radial locking wall faces CW, so a CW-turning wheel
// presses its walls against the pawls' radial nose faces and stops dead; a
// CCW-turning wheel presents its 60° ramps, which cam the pawls outward a
// tooth-depth's worth and let go — the click. The raised arrow on the wheel
// top points CCW: the free direction.
//
// All dimensions in millimeters.

/* [Wheel] */
// Tooth-tip diameter (mm) — brief: wheel Ø56
wheel_dia = 56;
// Number of teeth (even: the two pawls sit diametric, in phase)
teeth = 24;
// Tooth depth (mm) — brief: 1.6
tooth_depth = 1.6;
// Locking flank angle from radial (deg) — brief GIVEN: 0 (radial = self-locking)
lock_flank_deg = 0;
// Drive flank angle from radial (deg) — the ramp the pawl rides up (assumed)
drive_flank_deg = 60;
// Wheel width / pawl engagement band (mm) — brief: 8
wheel_w = 8;

/* [Post & cap] */
// Fixed centre post radius (mm)
post_r = 9;
// Capture lip: how far the cap overhangs past the wheel bore (mm)
cap_lip = 2.5;

/* [Pawls] */
// Pawls, diametrically opposed (brief: 2)
pawls = 2;
// Pawl beam thickness, the bending direction (mm) — brief starting point 1.2;
// the coupon sweeps it — this is THE tuning knob (stiffness ~ t³)
pawl_t = 1.2;
// Pawl beam free length nose→root (mm) — brief said 10, which yields at the
// ride-up deflection; 18 with the root clamped by the frame block gives an
// honest effective ~13 (see NOTES.md "Key decisions")
pawl_l = 18;
// Pawl width, along the wheel axis (mm) — matches the tooth band
pawl_w = 8;
// Nose engagement: how deep the pawl tip reaches below the tooth tips (mm)
engagement = 0.85;
// Nose-face ↔ tooth-wall gap at the tooth tips (mm)
lock_gap = 0.5;
// Beam underside ↔ tooth-tip clearance while riding (mm)
web_clr = 0.2;
// Hook flank angle from radial (deg) — steep so a passing tooth tip cams the
// pawl out instead of levering the beam in bending mid-span
hook_flank_deg = 75;

/* [Frame] */
// Base disc radius (mm) — footprint is 2× this, brief budget 70
frame_r_out = 34.5;
// Base plate thickness (mm)
base_t = 2.4;
// Frame footprint budget (mm) — brief: ≤70×70×14
frame_xy_budget = 70;
frame_h_budget = 14;

/* [Process constants — the CC3 derivation] */
// Nozzle diameter (mm)
nozzle_d = 0.4;
// Extruded line width (mm) — line_w ≈ 1.1–1.2 × nozzle_d
line_w = 1.15 * nozzle_d;
// XY clearance factor — k_xy ≈ 0.4–0.6 (spread-limited)
k_xy = 0.45;
// Layer height the axial gaps are quantized to (mm)
layer_h = 0.2;
// Axial float in WHOLE LAYERS (sag-limited)
z_layers = 2;

/* [Quality] */
// Production: 96 (a captive bore is $fn-sensitive).
$fn = 96;

// ---- derived -----------------------------------------------------------
r_tip  = wheel_dia / 2;                 // 28
r_root = r_tip - tooth_depth;           // 26.4
tooth_pitch = 360 / teeth;              // 15°
xy_tol = k_xy * line_w;                 // ≈0.207 — radial gaps
z_tol  = z_layers * layer_h;            // 0.4 — axial gaps
bore   = post_r + xy_tol;               // wheel bore (radial gap)
z0     = base_t + z_tol;                // wheel floats z_tol above the base
wheel_top = z0 + wheel_w;               // 10.8
r_cap  = bore + cap_lip;                // cap must exceed the bore to capture
cone_h = r_cap - post_r;                // 45° cone
z_cone0 = wheel_top + z_tol - xy_tol;   // gap over the bore edge = z_tol exactly
total_h = z_cone0 + cone_h;             // 13.7 ≤ 14
// Tooth profile, in arc length from the locking wall:
tip_flat = 0.4;                         // tooth-tip land (one line width)
drive_run = tooth_depth * tan(drive_flank_deg); // arc the ramp spans
// Pawl placement, in arc length u from the nose face:
web_in  = r_tip + web_clr;              // beam underside rides this radius
beam_out = web_in + pawl_t;             // beam outer band
r_nose_in = r_tip - engagement;         // hook tip reaches inside the tips
ride_defl = web_in - r_nose_in;         // ride-up deflection the beam needs
hook_run = ride_defl * tan(hook_flank_deg); // arc the hook underside spans
lock_gap_deg = lock_gap / r_tip * 180 / PI; // angular form of the wall gap
// Frame block (the pawl's clamp): covers the root and nothing of the flexure
block_front_u = 13;                     // beam free from nose to here
block_back_u  = pawl_l + 4;             // and buried this far past the root
a_block_front = block_front_u / web_in * 180 / PI;
a_block_back  = block_back_u / beam_out * 180 / PI;
// Wheel phase: the locking wall that stops the first pawl sits lock_gap CCW
// of its nose face (the nose face points CCW; a CW turn sweeps that wall down
// onto it). CW of the nose would bury the tooth's tip land inside the hook.
pawl_angle = 15;                        // nose angle (deg) — arbitrary, fixed
wall_base = pawl_angle + lock_gap_deg;

// ---- tooth profile -----------------------------------------------------
// One tooth as (u, r) pairs: u = arc length CCW from the tooth's locking wall,
// r = radius. The locking wall itself is the radial segment at u=0; the drive
// flank is the straight 60° ramp from the tip land down to the root; the
// valley runs at r_root to the next wall. Shared verbatim with the coupon.
function tooth_profile() =
  let (
    ramp = [ for (s = [0.25, 0.5, 0.75, 1])
             let (r = r_tip - s * tooth_depth)
             [ tip_flat + s * drive_run, r ] ],
    u_end = ramp[len(ramp) - 1][0],
    valley = [ for (k = [1, 2, 3])
               [ u_end + k * (tooth_pitch_arc() - u_end) / 4, r_root ] ]
  )
  concat([[0, r_root], [0, r_tip], [tip_flat, r_tip]], ramp, valley);

// Tooth pitch as arc length at the root circle (the coupon unrolls at this)
function tooth_pitch_arc() = tooth_pitch * PI / 180 * r_root;

// ---- pawl profile ------------------------------------------------------
// The pawl as (u, r) pairs: u = arc length from the nose face toward the root
// (CW on the wheel), r = radius. Nose face is the radial segment at u=0 from
// the hook tip up to the beam band; the beam is constant-thickness outside the
// tooth tips; the hook dips inside the tips only at the nose, on a steep flank.
// The two long beam edges are arc-sampled every ~2°: a single chord across the
// 28–35° span would sag ~0.8 mm inside the band and dive through the tooth
// tips mid-span. Shared verbatim with the coupon (extra samples are collinear
// in its linear mapping, so the coupon is unaffected).
function pawl_profile() =
  let (
    dip = web_in - r_nose_in,           // = ride_defl
    hook = [ for (s = [0.8, 0.6, 0.4, 0.2])
             [ s * hook_run, web_in - s * dip ] ],
    n_out = ceil(pawl_l / beam_out * 180 / PI / 2),
    n_in  = ceil((pawl_l - hook_run) / web_in * 180 / PI / 2)
  )
  concat(
    [[0, r_nose_in]],
    [ for (k = [0 : n_out]) [ k * pawl_l / n_out, beam_out ] ],
    [ for (k = [n_in : -1 : 0])
        [ hook_run + k * (pawl_l - hook_run) / n_in, web_in ] ],
    hook);

// Map a (u, r) profile pair to XY, polar: u arc at radius r, angle from a_ref.
function polar_pt(p, a_ref, dir) =
  let (a = a_ref + dir * p[0] / p[1] * 180 / PI)
  [ p[1] * cos(a), p[1] * sin(a) ];

// The wheel's toothed rim as one closed polygon (teeth + everything inside).
function wheel_pts() =
  let (
    walls = [ for (j = [0 : teeth - 1]) wall_base + j * tooth_pitch ],
    // each tooth's profile, polar-mapped CCW from its wall
    per_tooth = [ for (j = [0 : teeth - 1])
                    [ for (p = tooth_profile())
                      polar_pt(p, walls[j], 1) ] ]
  )
  [ for (t = per_tooth, pt = t) pt ];

// The pawl's 2D outline, nose at angle a_n (local frame: a_n = 0).
function pawl_pts(a_n) =
  [ for (p = pawl_profile()) polar_pt(p, a_n, -1) ];

// Annular sector polygon, r_in→r_out between angles a0 < a1 (deg), arcs
// sampled every 2° so a coarse chord can't shave the block faces.
function sector_pts(r_in, r_out, a0, a1) =
  let (n = max(2, ceil((a1 - a0) / 2)))
  concat(
    [ for (k = [0 : n]) let (a = a0 + k * (a1 - a0) / n)
        [ r_in * cos(a), r_in * sin(a) ] ],
    [ for (k = [n : -1 : 0]) let (a = a0 + k * (a1 - a0) / n)
        [ r_out * cos(a), r_out * sin(a) ] ]);

// ---- parts -------------------------------------------------------------
module base() {
  cylinder(r = frame_r_out, h = base_t);
}

module post_and_cap() {
  // straight post through the wheel bore, merged into the base
  cylinder(r = post_r, h = z_cone0 + 0.01);
  // 45° capture cone, narrow at the bottom widening up (self-supporting):
  // over the wheel's bore edge it starts exactly z_tol above the wheel top.
  translate([0, 0, z_cone0])
    cylinder(r1 = post_r, r2 = r_cap, h = cone_h);
}

module knurl_slots() {
  // finger grip on the wheel top face: radial slots, one per 10°. Slot width
  // 0.9 = two line widths — an engraved groove under ~2 lines on a 0.4 nozzle
  // is a coin flip between a slot and a scratch
  for (k = [0 : 35])
    rotate([0, 0, k * 10])
      translate([20, -0.45, wheel_w - 0.5])
        cube([5.5, 0.9, 0.51]);
}

module arrow() {
  // raised index marker on the wheel top, pointing CCW = the free direction
  rotate([0, 0, 90])
    translate([13, 0, 0])
      linear_extrude(0.4)
        polygon([[0, -1.2], [0, 1.2], [4, 0]]);
}

module wheel(bore_r = bore) {
  translate([0, 0, z0])
    difference() {
      union() {
        linear_extrude(wheel_w) polygon(wheel_pts());
        translate([0, 0, wheel_w]) arrow();
      }
      translate([0, 0, -0.01])
        cylinder(r = bore_r, h = wheel_w + 0.02);
      knurl_slots();
    }
}

// One pawl + its clamping block, nose at local angle 0; the caller rotates
// this to each pawl_angle. The block is an annular sector from the beam's
// underside radius out to the frame edge: its inner face IS the plane the
// tooth tips clear by web_clr, and it buries the beam's root end.
module pawl_assembly() {
  translate([0, 0, z0])
    linear_extrude(pawl_w)
      polygon(pawl_pts(0));
  linear_extrude(wheel_top)
    polygon(sector_pts(web_in, frame_r_out, -a_block_back, -a_block_front));
}

module fixed() {
  base();
  post_and_cap();
  for (i = [0 : pawls - 1])
    rotate([0, 0, pawl_angle + i * 360 / pawls])
      pawl_assembly();
}

// "" = the demonstrator (the one printable piece). "wheel" / "frame" =
// inspection exports for measuring the built mesh. "fitcheck" = wheel ∩ fixed
// (must be EMPTY — the wheel is a free captive body clearing post, cap, base,
// blocks and both pawls). "fitcheck_neg" = the bore shrunk onto the post
// (must be NON-EMPTY — proves the check can fail). "fused" = the assembled
// demonstrator with the bore shrunk onto the post (the KNOWN-FUSED pose for
// ci.fusecheck's control). "coupon" renders nothing here — the coupon wrapper
// supplies its own geometry on the shared profile functions.
part = "";

module main() {
  assert(xy_tol >= 0.15, "radial gap below the spread-limited floor (0.15 mm)");
  assert(z_layers >= 1, "axial gap must be at least one whole layer");
  assert(cap_lip >= 1.5, "capture lip too small — the wheel could pop off");
  assert(r_cap < r_root, "cap wider than the wheel's solid centre");
  assert(teeth >= 4 && teeth % 2 == 0,
         "diametric pawls in phase need an even tooth count");
  assert(lock_flank_deg <= 0,
         "self-locking requires the locking flank at or below radial");
  assert(drive_flank_deg >= 40 && drive_flank_deg <= 70,
         "drive flank outside the printable ramp range (40–70° from radial)");
  assert(pawl_t >= 0.8, "pawl beam below the 0.8 mm FDM minimum feature");
  assert(engagement >= 0.5, "nose engages less than 0.5 mm of the tooth wall");
  assert(web_clr >= 0.15, "beam-to-tip clearance below the spread floor");
  assert(2 * frame_r_out <= frame_xy_budget, "footprint over the brief budget");
  assert(total_h <= frame_h_budget, "height over the brief budget");
  assert(block_front_u > hook_run + 4,
         "frame block crowds the hook — the beam cannot flex");
  assert(block_back_u > pawl_l + 3,
         "frame block does not bury the pawl root");

  if (part == "fitcheck")
    intersection() { wheel(); fixed(); }
  else if (part == "fitcheck_neg")
    intersection() { wheel(bore_r = post_r - 0.4); fixed(); }  // bore bites the post
  else if (part == "fused")
    { fixed(); wheel(bore_r = post_r - 0.4); }                 // welded on purpose
  else if (part == "wheel")
    wheel();
  else if (part == "frame")
    fixed();
  else if (part == "coupon")
    ;                                     // the coupon wrapper's geometry
  else {
    fixed();
    wheel();
  }
}

main();
