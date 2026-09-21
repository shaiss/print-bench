// pip-ratchet-coupon — print this first. One pawl (the production cross-section
// and profile, on the shared pawl_profile()) engaging a linear rack (the
// production tooth_profile() unrolled at the root circle), in a channel that
// confines the loose strip. Slide the rack +x (the arrow direction on the
// demonstrator): it should click and the pawl ride up each tooth; slide it −x:
// it must lock dead. No geometry is copied — the profiles come from the entry
// design, so what you tune here is what ships.
//
// WHAT TO TUNE: pawl_t, in 0.1 steps, via the sweep plate —
//   ./scripts/render.sh pip-ratchet --sweep pawl_t=0.9:1.5:0.1
// Stiffness (click force) scales ~ t³ and ride-up stress ~ t: thicker clicks
// harder and lives longer, thinner feels lighter. If the strip welds into the
// channel, raise k_xy by 0.05 in the entry file and reprint both. See NOTES.md
// "Print this first". Overrides sit below the include (OpenSCAD resolves
// top-level variables last-assignment-wins); "coupon" has no dispatch branch,
// so the demonstrator itself renders nothing here.
include <pip-ratchet.scad>
part = "coupon";

/* [Coupon] */
// Teeth on the rack strip — enough clicks to judge the feel
coupon_teeth = 6;
// Rack strip body thickness below the root line (mm)
rack_body = 4;
// Rack strip height (mm) — the pawl keeps the production 8 mm section
rack_h = 6;
// Guide rail thickness (mm)
rail_t = 1.4;
// Far-rail sliding clearance (mm) — guidance only; the fit under test is the
// tooth-tip-to-wall web_clr, which is the production number
rail_gap = 0.3;
// Near rail resumes this far ahead of the nose face (mm)
nose_clear = 1;

// ---- derived (linear unroll at the root circle) ------------------------
pitch_mm = tooth_pitch_arc();
x_w    = lock_gap;                // first tooth wall, lock_gap AHEAD (+x) of
                                   // the nose face — sliding −x drives the wall
                                   // onto the face (lock); +x presents ramps
x_rack0 = -block_back_u - 6;      // back margin reaches past the block zone
x_rack1 = x_w + coupon_teeth * pitch_mm + 4;
web_y  = web_in - r_root;         // beam underside plane = channel wall (1.8)
block_y_out = beam_out - r_root + 2.4;

function rack_pts() =
  let (teeth_pts = [ for (j = [0 : coupon_teeth - 1], p = tooth_profile())
                       [ x_w + j * pitch_mm + p[0], p[1] - r_root ] ])
  concat([[x_rack0, -rack_body], [x_rack0, 0]],
         teeth_pts,
         [[x_rack1, 0], [x_rack1, -rack_body]]);

function pawl_pts_linear() =
  [ for (p = pawl_profile()) [ -p[0], p[1] - r_root ] ];

module coupon() {
  assert(rack_h + z_tol < pawl_w, "bridge would sit above the pawl tops");
  assert(x_rack0 < -block_back_u - 2, "rack shorter than the pawl block zone");
  // the loose rack strip — slides in the channel, prints on the bed
  linear_extrude(rack_h) polygon(rack_pts());
  // the pawl, full production section, nose face at x = 0
  linear_extrude(pawl_w) polygon(pawl_pts_linear());
  // clamping block burying the pawl root (mirrors the demonstrator's sector)
  translate([-block_back_u, web_y, 0])
    cube([block_back_u - block_front_u, block_y_out - web_y, pawl_w]);
  // tooth-side channel wall, interrupted by the pawl: behind the block (its
  // end reaches 3 mm INSIDE the block's x-span — a tangent face-only contact
  // leaves the fixture as two shells, which the body count would read as a
  // third body), and ahead of the nose; between them the pawl's own underside
  // is the wall
  translate([x_rack0, web_y, 0])
    cube([-(block_front_u + 3) - x_rack0, rail_t, pawl_w]);
  translate([nose_clear, web_y, 0])
    cube([x_rack1 - nose_clear, rail_t, pawl_w]);
  // far-side rail: the click reaction pushes the strip against this
  translate([x_rack0, -rack_body - rail_gap - rail_t, 0])
    cube([x_rack1 - x_rack0, rail_t, pawl_w]);
  // z-confinement bridges over the strip, 2 layers above it (z_tol) —
  // printed between the rails; they reach 0.2 mm INTO the near-rail band (or
  // the block, for the one behind the pawl) so every fixture joint is
  // volumetric, not face-tangent. The −20 bridge lands over the block's clamp
  // zone — frame-welds to frame, clear of the flexure (which starts at
  // x = −block_front_u = −13) — and is what ties the far-rail/ahead-rail group
  // to the pawl/block group, so the fixture is ONE body.
  for (bx = [-20, 6, 16])
    translate([bx, -rack_body - rail_gap - rail_t, rack_h + z_tol])
      cube([6, web_y + rack_body + rail_gap + rail_t + 0.2,
            pawl_w - rack_h - z_tol]);
}

coupon();
