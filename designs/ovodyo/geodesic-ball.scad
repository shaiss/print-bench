// geodesic-ball.scad — faceted "dice-ball" generator for the ovodyo clock.
//
// A sphere-inflated faceted solid on full icosahedral symmetry: 12 flat
// PENTAGONAL number-plaques at the icosahedron-vertex directions (the natural
// even spacing for 12 numbers), with a triangular field between them. The 12
// plaques carry numerals (debossed in v0; #601 converts them to true
// cut-through stencil with nozzle-tied bridges) and the shell carries one
// helical slot (#601 makes it a tunable brand module) that reveals the drive.
//
// Construction: intersection of a dodecahedron (its 12 faces ARE the pentagon
// plaques) with an icosahedron (its 20 faces cut the triangular field). Both
// are built by hull() of their canonical golden-ratio vertices, so the two are
// dual-aligned by construction — the dodeca faces point exactly along the
// icosa vertices, which is where the numerals go. `facet_mix` tunes the
// pentagon:triangle balance (the study left the exact frequency open; this is
// the free parameter). See designs/ovodyo and issue #600 (geodesic-ball lib).
//
// v0 scope: this is DESIGN-LOCAL to designs/ovodyo (not a shared lib yet).
// Issue #600 promotes it to lib/geodesic-ball.scad with the demo, guards.conf
// (refuse a plaque that makes two pentagons adjacent, a bridge below nozzle-tie)
// and mates the first-party-lib contract requires.
//
// Self-contained on purpose: no library includes, so the design renders under
// both the stable and the nightly/manifold CI engines with nothing to resolve.

PHI = (1 + sqrt(5)) / 2;

// Rotate children so local +Z points along `dir` (replaces BOSL2 rot(from,to)).
module _gb_align_z_to(dir) {
  d = dir / norm(dir);
  ax = [-d[1], d[0], 0];                       // cross([0,0,1], d)
  if (norm(ax) < 1e-9) {
    if (d[2] >= 0) children(); else rotate([180, 0, 0]) children();
  } else {
    rotate(a = acos(max(-1, min(1, d[2]))), v = ax) children();
  }
}

// 12 icosahedron vertex directions == the 12 pentagon-face normals.
function gb_icosa_verts() = [
  [ 0,  1,  PHI], [ 0,  1, -PHI], [ 0, -1,  PHI], [ 0, -1, -PHI],
  [ 1,  PHI, 0 ], [ 1, -PHI, 0 ], [-1,  PHI, 0 ], [-1, -PHI, 0 ],
  [ PHI, 0,  1 ], [ PHI, 0, -1 ], [-PHI, 0,  1 ], [-PHI, 0, -1 ],
];

// 20 dodecahedron vertices (dual-aligned with the icosa above).
function gb_dodeca_verts() = concat(
  [ for (x = [-1, 1], y = [-1, 1], z = [-1, 1]) [x, y, z] ],
  [ for (a = [-1, 1], b = [-1, 1]) [0, a * (1 / PHI), b * PHI] ],
  [ for (a = [-1, 1], b = [-1, 1]) [a * (1 / PHI), b * PHI, 0] ],
  [ for (a = [-1, 1], b = [-1, 1]) [a * PHI, 0, b * (1 / PHI)] ]
);

// circumradius of the raw coordinate sets (both dodeca families norm to this)
_GB_ICO_R = sqrt(1 + PHI * PHI);   // ~1.902
_GB_DOD_R = sqrt(3);               // ~1.732

// A convex solid = hull of tiny spheres at the given points, scaled so the
// coordinate circumradius maps to `circ`.
module _gb_hull(pts, raw_r, circ) {
  s = circ / raw_r;
  hull() for (p = pts) translate(p * s) sphere(r = 0.01, $fn = 6);
}

// The faceted ball solid (before hollowing / cutting).
//   d    outer diameter (plaque-to-opposite-plaque ~ d)
//   mix  icosa circumradius as a fraction of the dodeca's; lower = more
//        triangle, higher = more pentagon. 1.0 ~ icosidodecahedron-ish.
module gb_faceted_ball(d = 78, mix = 1.0) {
  r = d / 2;
  intersection() {
    _gb_hull(gb_dodeca_verts(), _GB_DOD_R, r);              // pentagons
    _gb_hull(gb_icosa_verts(),  _GB_ICO_R, r * mix);        // triangles
  }
}

// The 12 numeral cut/deboss tools, unioned. `nums` is a list of 12 strings in
// gb_icosa_verts() order. `through` cuts fully through the wall (islands are
// the caller's problem until #601 adds bridges); otherwise a debossed recess.
module gb_numbers(d = 78, nums = [], glyph_h = 11, depth = 0.8, through = false,
                  wall = 2.0, font = "Liberation Sans:style=Bold") {
  r = d / 2;
  face_r = r * 0.7947;                    // dodeca inradius / circumradius
  cut = through ? wall + 2 : depth + 0.2; // how deep the tool reaches
  z0  = through ? face_r - wall - 1 : face_r - depth;
  for (i = [0 : min(len(nums), 12) - 1]) {
    dir = gb_icosa_verts()[i];
    _gb_align_z_to(dir)
      translate([0, 0, z0])
        linear_extrude(height = cut)
          text(nums[i], size = glyph_h, halign = "center", valign = "center",
               font = font, $fn = 24);
  }
}

// One helical slot cut, bounded to the ball. Reveals the interior/drive.
module gb_slot(d = 78, width = 12, turns = 0.55, starts = 1) {
  r = d / 2;
  for (s = [0 : starts - 1])
    rotate([0, 0, s * 360 / starts])
      intersection() {
        sphere(r = r + 1, $fn = 96);
        linear_extrude(height = 2 * r + 2, twist = 360 * turns, center = true,
                       $fn = 96)
          translate([r * 0.55, 0])
            square([width, r * 1.6], center = true);
      }
}

// The finished part: a hollow faceted shell with numerals and the slot.
module geodesic_ball(d = 78, nums = [], mix = 1.0, wall = 2.0,
                     glyph_h = 11, deboss = 0.8, through = false,
                     slot = true, slot_width = 12, slot_turns = 0.55,
                     font = "Liberation Sans:style=Bold") {
  // Hollow with a SPHERICAL cavity sized to the plaque inradius, so the wall is
  // >= `wall` at every face and thicker toward the vertices — no knife-edge thin
  // spots the way a scaled-down faceted copy leaves. (0.7947 = dodecahedron
  // inradius/circumradius, the pentagon-face distance.)
  inner_r = d / 2 * 0.7947 - wall;
  difference() {
    difference() {
      gb_faceted_ball(d, mix);
      sphere(r = inner_r, $fn = 96);
    }
    gb_numbers(d, nums, glyph_h, deboss, through, wall, font);
    if (slot) gb_slot(d, slot_width, slot_turns);
  }
}

// convenient numeral sets
function gb_hours()   = ["12","1","2","3","4","5","6","7","8","9","10","11"];
function gb_minutes() = ["00","05","10","15","20","25","30","35","40","45","50","55"];
