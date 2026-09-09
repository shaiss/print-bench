// geodesic-ball.scad — faceted "dice-ball" generator for the ovodyo clock.
//
// A geodesic icosphere with the 12 fivefold vertices flattened into flat
// PENTAGONAL number-plaques (the natural even spacing for 12 numbers), the rest
// of the surface a fine TRIANGULAR field — the reference's "faceted dice-ball on
// full icosahedral symmetry" (spherical d12/d20). The 12 plaques carry numerals
// (debossed in v0; #601 converts them to true cut-through stencil with
// nozzle-tied bridges) and the shell carries one helical slot (#601 makes it a
// tunable brand module) that reveals the drive.
//
// Construction (faithful to the reference, replacing the coarse v0
// icosidodecahedron): subdivide each of the icosahedron's 20 triangular faces to
// frequency `freq`, project every point to the sphere, and take the convex hull
// — a geodesic ball whose only sharp points are the 12 fivefold icosa vertices.
// Then intersect with 12 planes (one per vertex direction, at radius r*plaque),
// which slices each 5-fold tip into a flat pentagon plaque for the numerals.
// `freq` sets the triangle fineness (higher = rounder, finer field, ~snub-
// dodecahedron density at 2-3); `plaque` sets how deep the plaque plane cuts
// (smaller = bigger pentagon). See designs/ovodyo and issue #600 (geodesic-ball
// lib), which promotes this to lib/ with the demo/guards/mates.
//
// v0 scope: DESIGN-LOCAL to designs/ovodyo (not a shared lib yet).
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

// 12 icosahedron vertex directions == the 12 pentagon-plaque normals (edge
// length 2 for these golden-ratio coords).
function gb_icosa_verts() = [
  [ 0,  1,  PHI], [ 0,  1, -PHI], [ 0, -1,  PHI], [ 0, -1, -PHI],
  [ 1,  PHI, 0 ], [ 1, -PHI, 0 ], [-1,  PHI, 0 ], [-1, -PHI, 0 ],
  [ PHI, 0,  1 ], [ PHI, 0, -1 ], [-PHI, 0,  1 ], [-PHI, 0, -1 ],
];

_GB_EDGE2 = 4.0;                    // squared icosahedron edge length for the above

function _gb_sq(a, b) =
  (a[0]-b[0])*(a[0]-b[0]) + (a[1]-b[1])*(a[1]-b[1]) + (a[2]-b[2])*(a[2]-b[2]);

// The 20 triangular faces, derived (not hand-typed): every vertex triple whose
// three pairwise distances are all one edge. The icosahedron graph's only
// 3-cliques are its faces, so this yields exactly the 20 faces.
function gb_icosa_faces() =
  let (V = gb_icosa_verts())
  [ for (i = [0:11]) for (j = [i+1:11]) for (k = [j+1:11])
      if (abs(_gb_sq(V[i], V[j]) - _GB_EDGE2) < 0.01
       && abs(_gb_sq(V[i], V[k]) - _GB_EDGE2) < 0.01
       && abs(_gb_sq(V[j], V[k]) - _GB_EDGE2) < 0.01)
      [i, j, k] ];

// Subdivide one face (A,B,C) to frequency f and project every point to radius R.
function _gb_face_pts(A, B, C, f, R) =
  [ for (i = [0:f]) for (j = [0:f-i])
      let (p = A + (B - A) * (i / f) + (C - A) * (j / f))
      p / norm(p) * R ];

// Every geodesic vertex, all 20 faces (duplicates on shared edges are harmless
// to the hull).
function gb_geo_pts(freq, R) =
  let (V = gb_icosa_verts(), F = gb_icosa_faces())
  [ for (f = F) each _gb_face_pts(V[f[0]], V[f[1]], V[f[2]], freq, R) ];

// The geodesic ball before the plaques are cut: convex hull of the projected
// points. Every projected point lies on radius R, so all are hull vertices.
module _gb_geo_hull(freq, R) {
  hull() for (p = gb_geo_pts(freq, R)) translate(p) sphere(r = 0.01, $fn = 4);
}

// Intersection of the 12 vertex-normal half-spaces {p . v_hat <= r_plaque}. Each
// plane clips only the small cap around its fivefold vertex, so intersecting the
// ball with this cell flattens all 12 tips into pentagons and leaves the
// triangular field between them untouched.
module _gb_plaque_cell(r_plaque) {
  BIG = 1000;
  intersection()
    for (v = gb_icosa_verts())
      _gb_align_z_to(v) translate([0, 0, r_plaque - BIG / 2]) cube(BIG, center = true);
}

// The faceted ball solid (before hollowing / cutting).
//   d       outer diameter (vertex-to-opposite-vertex ~ d)
//   freq    icosa-face subdivision frequency; higher = finer triangular field
//   plaque  plaque-plane radius as a fraction of r; smaller = larger pentagons
module gb_faceted_ball(d = 78, freq = 3, plaque = 0.94) {
  r = d / 2;
  intersection() {
    _gb_geo_hull(freq, r);
    _gb_plaque_cell(r * plaque);
  }
}

// The 12 numeral cut/deboss tools, unioned. `nums` is a list of 12 strings in
// gb_icosa_verts() order. `through` cuts fully through the wall (islands are the
// caller's problem until #601 adds bridges); otherwise a debossed recess. The
// glyphs sit on the flat pentagon plaques, so their plane is r*plaque.
module gb_numbers(d = 78, nums = [], glyph_h = 11, depth = 0.8, through = false,
                  wall = 2.0, plaque = 0.94, font = "Liberation Sans:style=Bold") {
  r = d / 2;
  face_r = r * plaque;                    // the flat pentagon-plaque plane
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
module geodesic_ball(d = 78, nums = [], freq = 3, plaque = 0.94, wall = 2.0,
                     glyph_h = 11, deboss = 0.8, through = false,
                     slot = true, slot_width = 12, slot_turns = 0.55,
                     font = "Liberation Sans:style=Bold") {
  // Hollow with a SPHERICAL cavity sized to the plaque plane minus `wall`, so
  // the wall is >= `wall` at the plaques (the closest-in outer surface) and
  // thicker everywhere the triangular field bulges out toward the vertices.
  inner_r = d / 2 * plaque - wall;
  assert(inner_r > 0.5,
         "geodesic_ball: wall too large for d/plaque — the inner cavity radius would be <= 0");
  difference() {
    difference() {
      gb_faceted_ball(d, freq, plaque);
      sphere(r = inner_r, $fn = 96);
    }
    gb_numbers(d, nums, glyph_h, deboss, through, wall, plaque, font);
    if (slot) gb_slot(d, slot_width, slot_turns);
  }
}

// convenient numeral sets
function gb_hours()   = ["12","1","2","3","4","5","6","7","8","9","10","11"];
function gb_minutes() = ["00","05","10","15","20","25","30","35","40","45","50","55"];
