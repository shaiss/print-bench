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

// The 20 dodecahedron-vertex directions == the 20 triangular-facet normals (the
// corners we shave off the dodecahedron). These are the icosahedral-face centres.
function gb_dodeca_verts() =
  let (I = 1 / PHI)
  concat(
    [ for (a=[-1,1], b=[-1,1], c=[-1,1]) [a, b, c] ],   // (±1,±1,±1)
    [ [0, I, PHI],[0, I,-PHI],[0,-I, PHI],[0,-I,-PHI] ],
    [ [I, PHI,0],[I,-PHI,0],[-I, PHI,0],[-I,-PHI,0] ],
    [ [PHI,0, I],[PHI,0,-I],[-PHI,0, I],[-PHI,0,-I] ]
  );

// The numbered pentagon faces sit at exactly d/2 — they are the OUTERMOST flush
// faces (the whole point, so the numerals read face-on instead of being buried
// in a valley the way a true icosidodecahedron recesses its pentagons). Kept as
// a fraction (=1) so gb_numbers, the cavity and ball_core share one plane
// definition. (The earlier 0.9510565 was doubly wrong: it wasn't the pentagon
// plane AND the icosidodecahedron recessed the pentagons, so the cavity sphere
// bulged out through each number face and difference() carved a round hole.)
_GB_PENT_R = 1.0;                        // centre → pentagon face = d/2

// How far out the 20 triangle-chamfer planes sit, as a multiple of d/2. The
// dodecahedron's own vertices are at 1.2584·(d/2); a chamfer plane between 1.0
// and 1.2584 shaves each vertex into a flat triangle while the 12 pentagons stay
// full-size and flush. Smaller = bigger (deeper) triangle facets; 1.0 cuts them
// level with the pentagons (≈ icosidodecahedron). The default reads like the
// reference: dominant number pentagons with crisp triangular corners.
_GB_TRI_K = 1.05;

// A half-space {p : p·n̂ <= dist}, as a large cube whose +face is that plane.
module _gb_halfspace(n, dist, big = 600) {
  _gb_align_z_to(n) translate([0, 0, dist - big / 2]) cube(big, center = true);
}

// The faceted ball solid (before hollowing / cutting): a dodecahedron whose 20
// vertices are chamfered into triangles — 12 big flush pentagon number-faces at
// d/2 plus 20 triangular corner facets. Built as the intersection of 12 pentagon
// half-spaces (at d/2) and 20 triangle half-spaces (at tri_k·d/2). `freq`/
// `plaque` are accepted for call-site compatibility but do not shape the solid.
module gb_faceted_ball(d = 78, freq = 2, plaque = 0.95, tri_k = _GB_TRI_K) {
  R = d / 2;
  // render() forces this convex solid to a concrete mesh even in preview, so
  // OpenSCAD reports its TRUE (tight) bounding box. Without it the rotated
  // half-space cubes below carry fat axis-aligned boxes that OpenSCAD unions for
  // the preview bbox, and --viewall (the contact-sheet, gallery thumbnails)
  // zooms the whole clock down to a speck.
  render()
  intersection() {
    intersection_for (n = gb_icosa_verts())  _gb_halfspace(n, R);          // 12 pentagons
    intersection_for (n = gb_dodeca_verts()) _gb_halfspace(n, R * tri_k);  // 20 triangles
  }
}

// A stencilised glyph string: the text with thin bridge bars SUBTRACTED, so when
// this is used as a cut tool through a shell every enclosed counter (0,4,6,8,9)
// stays joined to the surrounding wall by an uncut bridge — no island drops out.
// This is the reference's stencil look, and it is font-agnostic (no stencil font
// is installed here). Two horizontal bars cross the upper/lower counters and one
// vertical bar adds a central tie; `bridge` is their width (>= a few nozzle
// widths so each tie prints solid).
module _gb_stencil(s, size = 11, bridge = 1.3, font = "Liberation Sans:style=Bold") {
  bw = size * 2.8;                        // span comfortably past 1-2 digits
  bh = size * 1.7;
  difference() {
    text(s, size = size, halign = "center", valign = "center", font = font, $fn = 24);
    // Two full-width horizontal ties in the counter band (±0.13·bh, NOT out at the
    // edges) cross every digit's counter ring — including a 0/6/8/9 offset from
    // centre in a two-digit number like "10"/"00", which a single central vertical
    // tie misses (that was the dropped-island bug the mate/fuse gates would catch).
    for (yy = [-bh * 0.13, bh * 0.13]) translate([0, yy]) square([bw, bridge], center = true);
    square([bridge, bh], center = true);   // central vertical tie (helps tall counters)
  }
}

// ONE face's numeral tool — the per-face body of gb_numbers, exposed so the
// tumble kinematics check (designs/ovodyo/tumble.scad) can pose a single
// numeral's cutter exactly as the ball ships it. The stencil of `s` sits on the
// plaque whose outward normal is `face_dir`, turned `rot` degrees in-plane
// (CCW as seen from outside the ball, i.e. about the outward normal) before it
// is extruded along that normal; rot = 0 is the un-rotated placement (the 2D
// glyph's +y is _gb_align_z_to's image of +y).
module gb_number_cutter(d = 78, s = "", glyph_h = 11, face_dir = [0, 0, 1], rot = 0,
                        depth = 0.8, through = false, wall = 2.0, bridge = 1.3,
                        font = "Liberation Sans:style=Bold") {
  r = d / 2;
  face_r = r * _GB_PENT_R;                 // the flat pentagon-face plane
  cut = through ? wall + 2 : depth + 0.2; // how deep the tool reaches
  z0  = through ? face_r - wall - 1 : face_r - depth;
  _gb_align_z_to(face_dir)
    translate([0, 0, z0])
      rotate([0, 0, rot])
        linear_extrude(height = cut)
          _gb_stencil(s, glyph_h, bridge, font);
}

// The 12 numeral tools, unioned. `nums` is a list of 12 strings in
// gb_icosa_verts() order. `through` cuts a real stencil void clean through the
// wall to the (red) interior — the reference's read-through numerals — using
// _gb_stencil so no counter drops out; otherwise a debossed recess. The glyphs
// sit on the flat pentagon plaques, so their plane is r*plaque. `rots` is an
// optional list of per-FACE in-plane rotations (deg, same order as `nums`) so a
// numeral can be clocked to read upright when its face presents (the tumble
// stop table); a missing entry means 0.
module gb_numbers(d = 78, nums = [], glyph_h = 11, depth = 0.8, through = false,
                  wall = 2.0, plaque = 0.94, bridge = 1.3,
                  font = "Liberation Sans:style=Bold", rots = []) {
  for (i = [0 : min(len(nums), 12) - 1])
    gb_number_cutter(d, nums[i], glyph_h, gb_icosa_verts()[i],
                     (i < len(rots)) ? rots[i] : 0, depth, through, wall, bridge, font);
}

// One helical slot: a narrow radial blade swept with a twist and clipped to the
// wall shell (inner_r .. r+2), so it cuts clean THROUGH the wall wherever it
// runs and reads as a thin band spiralling around the ball (the reference's
// "swirl") rather than a wide crater. `inner_r` is the cavity radius so the clip
// spans the whole wall including the recessed pentagon faces.
module gb_slot(d = 78, width = 7, turns = 0.5, starts = 1, inner_r = 0) {
  r  = d / 2;
  ir = (inner_r > 0) ? inner_r - 0.5 : r * 0.78;  // clip below the innermost face
  for (s = [0 : starts - 1])
    rotate([0, 0, s * 360 / starts])
      intersection() {
        difference() { sphere(r = r + 2, $fn = 96); sphere(r = ir, $fn = 96); }  // wall shell
        linear_extrude(height = 2 * r + 4, twist = 360 * turns, center = true, $fn = 120)
          translate([r * 0.5, 0]) square([r * 1.2, width], center = true);       // thin blade
      }
}

// The finished part: a hollow faceted shell with numerals and the slot. `tri_k`
// sets the corner-chamfer depth (see gb_faceted_ball); `freq`/`plaque` are kept
// for call-site compatibility and no longer shape the solid; `rots` is the
// optional per-face numeral clocking gb_numbers documents.
module geodesic_ball(d = 78, nums = [], freq = 3, plaque = 0.94, wall = 2.0,
                     glyph_h = 11, deboss = 0.8, through = false, bridge = 1.3,
                     slot = true, slot_width = 12, slot_turns = 0.55,
                     tri_k = _GB_TRI_K, font = "Liberation Sans:style=Bold",
                     rots = []) {
  // Hollow with a SPHERICAL cavity sized to the pentagon plane minus `wall`, so
  // the wall is >= `wall` at the pentagon number-faces (the closest-in outer
  // surface) and thicker everywhere the triangles/vertices bulge outward.
  inner_r = d / 2 * _GB_PENT_R - wall;
  assert(inner_r > 0.5,
         "geodesic_ball: wall too large for d — the inner cavity radius would be <= 0");
  difference() {
    difference() {
      gb_faceted_ball(d, freq, plaque, tri_k);
      sphere(r = inner_r, $fn = 96);
    }
    gb_numbers(d, nums, glyph_h, deboss, through, wall, plaque, bridge, font, rots);
    if (slot) gb_slot(d, slot_width, slot_turns, inner_r = inner_r);
  }
}

// convenient numeral sets
function gb_hours()   = ["12","1","2","3","4","5","6","7","8","9","10","11"];
function gb_minutes() = ["00","05","10","15","20","25","30","35","40","45","50","55"];
