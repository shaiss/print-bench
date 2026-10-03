// compliant.scad — compliant-mechanism (flexure) primitives for FDM.
// All dimensions in millimeters. Use from a design with:
//   use <compliant.scad>
//
// Issue #202, STAGE 1 of 4 (harvest-first order, owner ruling): the bistable
// arch and the flexure-root fillet — the two primitives four shipped designs
// already re-derive inline. Pivots (small-length, cross-axis), the LET joint
// and the stiffness coupon are later stages. The knowledge behind every
// number here is docs/advanced-techniques.md, Domain 1.
//
// HARVESTED, NOT INVENTED. Every module below is lifted from a design that
// already proves it on the gate; the guards are the asserts those designs
// already enforce, each cited file:line at the guard. The designs keep their
// inline copies (the print-in-place precedent, issue #19): adopting this
// library is a per-design follow-up, never a side effect of this file.
//
//   bistable_arch_2d / bistable_arch   designs/bistable-toggle/bistable-toggle.scad:119-125
//                                      (also compliant-gripper.scad:349-361,
//                                       over-center-toggle-clamp.scad:311-322,
//                                       czs-slider.scad:251-260)
//   root_fillet_2d                     designs/snap-cantilever-clip/snap-cantilever-clip.scad:140-149
//   rooted_2d                          designs/let-folding-panel/let-folding-panel.scad:72-76
//
// One-time parity evidence (recorded here because the designs are not
// switched to this library — scratch fixtures that `use` each design and
// this file side by side, not committed: an extra lib/*.scad would read as a
// first-party library to docs-check). OpenSCAD 2021.01 / CGAL, 2026-10-03:
//   bistable-toggle   arch_beam_2d vs bistable_arch_2d, linear_extrude(6),
//                     at production (span 82.0289, rise 2.0202, t 0.82) AND
//                     all four coupon cells (l 35; h/t 3, 2.46, 2, 1.5):
//                     ASCII STL BYTE-IDENTICAL every time (production sha256
//                     b8790096…198638d3, 468 facets), both one-sided CGAL
//                     differences empty. Negative control: the lib at ns = 62
//                     against the design's NS = 60 leaves 928-facet
//                     differences both ways. The solve is bit-equal too:
//                     bistable_arch_span_for / _rise_for / _fs == the
//                     design's span / mid_rise / fs_pred (OpenSCAD ==).
//   compliant-gripper arch_beam_2d vs translate([10, 33]) mirror([0, 1])
//                     bistable_arch_2d(120, 3.8, 1.6): 2D (Clipper)
//                     symmetric difference empty both ways; 212 of 236 STL
//                     vertices identical, the other 24 one unit apart in the
//                     export's 6th significant digit (1e-4 at |y| ≈ 32 —
//                     doubles straddling a rounding boundary, because a
//                     mirror+translate placement does not replay the
//                     design's operation order bit-for-bit).
//   snap-cantilever-clip  its corner piece (copied verbatim, f 0.6, $fn 96)
//                     vs translate([0, 20]) mirror([0, 1]) root_fillet_2d(0.6,
//                     1.0): 2D symmetric difference empty both ways; and the
//                     design's clip2d() ∪ the lib piece minus clip2d() is
//                     EMPTY under CGAL (the piece adds nothing).
//   over-center-toggle-clamp  not a parity target (see below): its band is
//                     wrapped in a closing, which re-samples it: 24 of the
//                     bare band's 284 vertices survive, the rest sit up to
//                     3.3 µm from the nearest closed-band vertex along the
//                     band and the convex end corners come back cut by up to
//                     15.6 µm.
//   root_fillet = 0.5·t on the production toggle arch: a strict superset of
//                     the bare band, identical to it away from the roots,
//                     nothing outside the documented root footprint; with
//                     6 mm clamp posts, printcheck 100/100, 1 body, watertight.
//
// ---------------------------------------------------------------------------
// THE LOCAL FRAME (the reason this generator exists). An arch is built in its
// own frame and placed by the caller with translate/rotate/mirror:
//
//       y                      rise at x = span/2
//       ^               _..--''''''--.._
//       |          _.-''                ''-._        band = centreline ± t/2
//   ####|___..--''                          ''--..___|####
//   ####+--------------------------------------------+####--> x
//   clamp face x = 0                    clamp face x = span
//
//   centreline  y(x) = rise·(1 − cos(360°·x/span))/2,  x ∈ [0, span]
//
// the fixed–fixed first buckling mode: zero height AND zero slope at both
// clamp faces, which is the boundary condition the two constants below were
// derived for. `span` is therefore the FREE length between the clamp faces,
// and the caller's clamps must have their faces exactly at x = 0 and x = span.
//
// The generator owns its own sampling — it never takes a world coordinate.
// That is deliberate: compliant-gripper.scad:351-355 records the bug this
// makes impossible, where world x was fed into a local-x centreline, the dip
// landed off-centre and the BUILT rise/t measured 1.83 — under the 2.3
// bistable bar its own guard checked against the nominal. The one public
// entry that does take an x, bistable_arch_y(), refuses x outside [0, span].
//
// Harvest-site observations this frame also settles (recorded, not fixed
// here — the designs are not touched by this library's PR):
//   * over-center-toggle-clamp.scad:325-327 and compliant-gripper.scad:368-371
//     centre their clamp posts ON the arch ends, so 5 mm / 2.5 mm of each end
//     is buried and the free span is shorter than the span the force is
//     predicted from (f_s ∝ 1/l³). Here a buried end is `ov`, a FLAT
//     extension past the clamp face (zero height and zero slope, so C1 with
//     the clamped boundary) that never changes the free cosine.
//   * czs-slider.scad:276 passes the `ov`-extended chord INTO the cosine, so
//     the clamped boundary sits inside its anchors. Same fix, same knob.
//   * over-center-toggle-clamp.scad:321 applies its "root fillets by the
//     offset trick" closing to the band ALONE, which has no concave corner
//     for a closing to round — its roots, where the band leaves the 3D post
//     cubes, stay sharp. Here the fillet is placed at the clamp face itself
//     (root_fillet), which needs no clamp geometry to exist yet.
//
// The snapped (second) stable state is the as-built arch mirrored about its
// chord: mirror([0, 1]) bistable_arch_2d(...). To bow toward −Y as printed
// (compliant-gripper, over-center-toggle-clamp), mirror it the same way —
// `rise` itself is always positive.
//
// The band is offset VERTICALLY by ±t/2, as every harvest site builds it, so
// its normal thickness is t·cos(slope), slope ≤ atan(π·rise/span). The
// shallow-arch guard (span/rise ≥ 10) bounds that at ≥ 0.954·t; at
// bistable-toggle's numbers it is 0.997·t. Size t from the normal thickness
// you need if you sit near the floor (bistable-toggle.scad:22-25 does).
// ---------------------------------------------------------------------------

// The two nondimensional constants of a fixed–fixed shallow cosine arch,
// h = mid-span rise, I = w·t³/12 (Srivastava et al., "Design of an
// engaging-disengaging compliant mechanism by using bistable arches",
// arXiv:2511.06039 (2025) — recorded in docs/advanced-techniques.md,
// "Bistable & constant-force" and "Governing relations"):
//   switch force   f_s · l³ / (E·I·h) = 1486.57
//   travel         u_tr / h           = 1.98
_ARCH_FS_CONST = 1486.57;
_ARCH_TRAVEL_CONST = 1.98;

// Relative slack on the [0, span] domain check: `span * i / ns` at i = ns is
// not guaranteed to round back to exactly `span`.
_DOMAIN_EPS = 1e-9;

// ---------------------------------------------------------------------------
// Predictions and the inverse solve — functions so a design derives instead
// of retyping (bistable-toggle.scad:76/84 and czs-slider.scad:103/111 both
// solve span and rise FROM a target force and travel). Expressions are kept
// textually identical to bistable-toggle's, so a design adopting them gets
// bit-identical numbers. Valid only where the constants are: a shallow
// (span/rise ≥ 10), bistable (rise/t ≥ 2.3) fixed–fixed arch — the same
// envelope bistable_arch_2d's guards hold. E is the material datum in MPa
// (PETG ≈ 2000, the datum every harvest site uses); the result is in N.
// ---------------------------------------------------------------------------

// The functions' own sign checks. A module reaches them only through
// _bistable_arch_guards, which already refuses these inputs, but a design that
// calls a function directly would otherwise get a NaN or ±inf back as if it
// were a number: span = 0 passes bistable_arch_y's domain check vacuously at
// x = 0 (both bounds are 0) and evaluates cos(0/0); span = 0 in the force
// divides by zero; a negative rise in the inverse solve takes the cube root
// of a negative, and rise = 0 solves to a zero span. Checked BEFORE the domain
// check, so a negative span is named as what it is rather than as an x off
// the span.

// Fixed–fixed first-mode centreline at LOCAL x (0 at the first clamp face).
function bistable_arch_y(x, span, rise) =
    assert(span > 0, str("bistable_arch_y: arch span must be positive (got ", span, ")"))
    assert(rise > 0, str("bistable_arch_y: arch rise must be positive (got ", rise,
                         ") — mirror([0, 1]) the arch to bow the other way"))
    assert(x >= -_DOMAIN_EPS * span && x <= span * (1 + _DOMAIN_EPS),
           str("bistable_arch_y: x = ", x, " is outside the arch's local span [0, ", span,
               "] — pass LOCAL x (0 at the first clamp face) and translate the arch, never a",
               " world coordinate (the compliant-gripper drift, compliant-gripper.scad:351-355)"))
    rise * (1 - cos(360 * x / span)) / 2;

// Predicted switch (snap-through) force, N.
function bistable_arch_fs(span, rise, t, width, E = 2000) =
    assert(span > 0, str("bistable_arch_fs: arch span must be positive (got ", span, ")"))
    assert(rise > 0, str("bistable_arch_fs: arch rise must be positive (got ", rise, ")"))
    _ARCH_FS_CONST * E * (width * pow(t, 3) / 12) * rise / pow(span, 3);

// Predicted centre travel between the two stable states, mm.
function bistable_arch_travel(rise) =
    assert(rise > 0, str("bistable_arch_travel: arch rise must be positive (got ", rise, ")"))
    _ARCH_TRAVEL_CONST * rise;

// Inverse: the rise that gives a target centre travel.
function bistable_arch_rise_for(travel) =
    assert(travel > 0, str("bistable_arch_rise_for: target travel must be positive (got ", travel, " mm)"))
    travel / _ARCH_TRAVEL_CONST;

// Inverse: the free span that gives a target switch force at this rise/t/width.
function bistable_arch_span_for(fs, rise, t, width, E = 2000) =
    assert(fs > 0, str("target switch force must be positive (got ", fs, " N)"))
    assert(rise > 0, str("bistable_arch_span_for: arch rise must be positive (got ", rise, ")"))
    pow(_ARCH_FS_CONST * E * (width * pow(t, 3) / 12) * rise / fs, 1 / 3);

// ---------------------------------------------------------------------------
// Guards
// ---------------------------------------------------------------------------

// The flexure-root fillet rule, shared by every module that places one:
// docs/advanced-techniques.md "Fatigue & material reality" — fillet the
// flexure root at r ≥ 0.5·t. Enforced inline today by
// snap-cantilever-clip.scad:100-101 and let-folding-panel.scad:136; the zero
// case is named on its own because issue #202 lists it as its own refusal (a
// sharp root is the crack starter the whole rule exists for).
module _root_fillet_guards(r, t) {
    assert(t > 0, str("flexure thickness t must be positive (got ", t, ")"));
    assert(r > 0, str("root fillet must be positive (got ", r,
                      ") — a sharp flexure root is a crack starter"));
    assert(r >= 0.5 * t, str("root fillet ", r, " below 0.5*t = ", 0.5 * t,
                             " — the flexure root is a crack starter (docs/advanced-techniques.md: r >= 0.5t)"));
}

module _bistable_arch_guards(span, rise, t, root_fillet, ov, ns, allow_monostable) {
    // bistable-toggle.scad:307 and czs-slider.scad:501 — the repo's
    // two-perimeter floor. (compliant-gripper.scad:216 and
    // over-center-toggle-clamp.scad:224 hold their arches to 1.2, a design
    // choice above this floor, not the floor.)
    assert(t >= 0.8, str("arch beam t = ", t, " under the two-perimeter floor (0.8 mm)"));
    // Not in any design: there `rise` is always positive because the 2.3 bar
    // below implies it. With allow_monostable that implication is gone, so it
    // is stated on its own.
    assert(rise > 0, str("arch rise must be positive (got ", rise,
                         ") — mirror([0, 1]) the arch to bow the other way"));
    // THE bistability bar: bistable-toggle.scad:305-306,
    // compliant-gripper.scad:214-215, over-center-toggle-clamp.scad:222-223,
    // czs-slider.scad:499-500, constant-force-slider.scad:120. Below it the
    // arch is monostable and just springs back. allow_monostable exists for
    // ONE consumer: a calibration coupon that prints cells across the
    // threshold on purpose (bistable-toggle.scad:266-271, cells h/t = 2 and
    // 1.5 are its deliberate negative controls).
    assert(allow_monostable || rise / t >= 2.3,
           str("arch too flat to be bistable (rise/t = ", rise / t,
               " < 2.3) — it would just spring back"));
    // bistable-toggle.scad:309-310 and czs-slider.scad:503-504: the two
    // constants are for a SHALLOW fixed–fixed arch.
    assert(span / rise >= 10, str("arch not shallow enough for the fixed-fixed constants (span/rise = ",
                                  span / rise, " < 10)"));
    // Not in any design (they hardcode NS = 60 / 72): the apex is a sample
    // only when ns is even, so an odd count builds a LOWER rise than the one
    // the bistability bar just judged — the compliant-gripper failure class
    // (built rise != judged rise). ns >= 16 bounds the chord sag of the
    // sampled centreline to ≤ 1% of the rise (sag ≈ π²·rise/(4·ns²)).
    assert(ns >= 16 && ns % 2 == 0,
           str("arch sample count ns = ", ns, " must be even and >= 16 — the apex must be a",
               " sample so the built rise is the rise the bistability bar judged"));
    // A negative ov would build a square of negative size: an empty or
    // inverted clamp overlap, silently.
    assert(ov >= 0, str("clamp overlap ov must not be negative (got ", ov, ")"));
    if (!is_undef(root_fillet)) {
        _root_fillet_guards(root_fillet, t);
        // let-folding-panel.scad:138 — the fillets must leave free flexure
        // between them.
        assert(root_fillet < span / 2,
               str("root fillet ", root_fillet, " leaves no free arch between the roots (span ", span, ")"));
    }
}

// ---------------------------------------------------------------------------
// Modules
// ---------------------------------------------------------------------------

// The bare band polygon — bistable-toggle.scad:121-125, point for point (same
// sample order, same float expressions), so the parity is bit-exact.
module _arch_band_2d(span, rise, t, ns) {
    top = [for (i = [0 : ns]) let (x = span * i / ns) [x, bistable_arch_y(x, span, rise) + t/2]];
    bot = [for (i = [ns : -1 : 0]) let (x = span * i / ns) [x, bistable_arch_y(x, span, rise) - t/2]];
    polygon(concat(top, bot));
}

// A pre-buckled fixed–fixed arch, 2D, in the local frame above: the band
// between the clamp faces x = 0 and x = span, rising `rise` at mid-span.
//
//   span          free length between the clamp faces (mm)
//   rise          mid-span rise of the centreline, h (mm); > 0
//   t             band thickness in the bending direction (mm); ≥ 0.8
//   root_fillet   undef (default) = bare band: the caller fillets the roots
//                 (bistable-toggle and czs-slider do, outside their
//                 generators; over-center-toggle-clamp's closing is inside
//                 its generator, :321, and rounds nothing — see above;
//                 compliant-gripper places no in-plane root fillet). A
//                 number = all four roots filleted at that radius, ≥ 0.5·t,
//                 with root_fillet_2d corner pieces (see _arch_root_pair_2d
//                 for the placement). Both faces of both roots: the band
//                 sweeps to −rise on the snap, so the concave side flips
//                 (czs-slider.scad:262-266).
//   ov            flat extension of the band past each clamp face (mm), for
//                 a caller that unions the arch with its clamps in 3D: a
//                 face-to-face kiss is fused by CGAL but exported by Manifold
//                 as a separate shell (lib/print-in-place.scad's lesson), so
//                 a 3D union wants the arch BURIED in the clamp. Zero height
//                 and slope, so it is C1 with the clamped boundary and never
//                 changes the free cosine (unlike czs-slider.scad:276).
//   ns            centreline samples; even and ≥ 16 (60 = bistable-toggle)
//   allow_monostable  skip the rise/t ≥ 2.3 bar — calibration coupons only
//
// ROOT FOOTPRINT (what the caller's clamps must cover): at each clamp face
// the arch occupies |y| ≤ t/2 + root_fillet (root_fillet = 0 when undef),
// and reaches past the face by ov — or by the fillet pieces' 0.06 mm bite
// when filleted with ov = 0. A clamp face shorter than that leaves the
// fillet standing as a free flange.
module bistable_arch_2d(span, rise, t, root_fillet = undef, ov = 0, ns = 60,
                        allow_monostable = false) {
    _bistable_arch_guards(span, rise, t, root_fillet, ov, ns, allow_monostable);
    rf = is_undef(root_fillet) ? 0 : root_fillet;
    hh = t/2 + rf;                          // root footprint half-height
    _arch_band_2d(span, rise, t, ns);
    if (rf > 0) {
        yr = bistable_arch_y(rf, span, rise);
        _arch_root_pair_2d(t, rf, yr);
        translate([span, 0]) mirror([1, 0]) _arch_root_pair_2d(t, rf, yr);
    }
    if (ov > 0)
        for (x0 = [-ov, span]) translate([x0, -hh]) square([ov, 2 * hh]);
}

// The bite the arch's root fillet pieces take into the band and the clamp:
// bistable-toggle.scad:156-159's value ("~200x the $fn=48 arc error"), so
// every contact is an area overlap, never a shared edge on a curved face.
_ROOT_BITE = 0.06;

// The two root fillets at the x = 0 clamp face (the far face mirrors it).
// Each is a root_fillet_2d corner piece whose straight band-side leg is
// placed ON OR INSIDE the band over the whole of x ∈ [0, r], so the piece
// neither leaves a sliver gap under a curved face nor stands proud of it:
//   top face      rises away from its leg (y = t/2 + y(x) ≥ t/2): the leg
//                 goes at y = t/2, the root corner itself;
//   underside     rises away from the fillet side (y = −t/2 + y(x)), so a
//                 leg at −t/2 would leave a gap of y(x) under the band — the
//                 leg goes at −t/2 + y(r), where the band is at x = r.
// The arc meets the band at x ≈ r with a slope mismatch of
// y'(r) = π·rise/span·sin(360°·r/span): 0.14° at bistable-toggle's numbers,
// ≤ 2.5° for any bistable arch the guards accept at r = 0.5·t (worst case
// rise = 2.3·t, span = 10·rise); it grows with r. NOT the
// closing (rooted_2d) on purpose: a closing re-samples the
// whole band (measured on over-center-toggle-clamp's band: vertices up to
// 3.3 µm off along it, end corners cut by up to 15.6 µm), where these pieces
// leave the cosine bit-exact away from the roots.
module _arch_root_pair_2d(t, r, yr) {
    translate([0, t/2]) root_fillet_2d(r, t, _ROOT_BITE);
    translate([0, -t/2 + yr]) mirror([0, 1]) root_fillet_2d(r, t, _ROOT_BITE);
}

// The arch extruded to `width` (the out-of-plane depth = print height Z for a
// flat-printed arch, which is the #1 flexure rule: the band bends in the
// layer plane, across the roads, never across a layer bond). Echoes the
// predicted switch force and travel — predictions for a coupon to verify,
// never a guarantee. E in MPa (PETG ≈ 2000 is the datum).
module bistable_arch(span, rise, t, width, E = 2000, root_fillet = undef, ov = 0,
                     ns = 60, allow_monostable = false) {
    _bistable_arch_guards(span, rise, t, root_fillet, ov, ns, allow_monostable);
    // Not in any design (they extrude a positive literal): a zero width
    // extrudes NOTHING, silently, and a non-positive E echoes a nonsense force.
    assert(width > 0, str("arch width must be positive (got ", width, ") — it would extrude nothing"));
    assert(E > 0, str("arch modulus E must be positive (got ", E, " MPa)"));
    if (rise / t >= 2.3)
        echo(str("[compliant] bistable_arch: predicted switch force f_s = ",
                 bistable_arch_fs(span, rise, t, width, E), " N, centre travel u_tr = ",
                 bistable_arch_travel(rise), " mm (span ", span, ", rise ", rise, ", t ", t,
                 ", width ", width, ", E ", E, " MPa datum; f_s*l^3/(E*I*h) = 1486.57,",
                 " u_tr/h = 1.98) — a prediction for the coupon to verify"));
    else
        echo(str("[compliant] bistable_arch: MONOSTABLE by design (rise/t = ", rise / t,
                 " < 2.3, allow_monostable) — no switch force, it springs back"));
    linear_extrude(width)
        bistable_arch_2d(span, rise, t, root_fillet, ov, ns, allow_monostable);
}

// ONE weld-safe flexure-root fillet piece, for a single concave corner
// between two straight faces — snap-cantilever-clip.scad:140-149.
//
// Canonical frame: the corner at the origin, the two walls occupying x ≤ 0
// and y ≤ 0, the fillet filling the corner of the +x/+y quadrant (the
// square [0, r]² minus the disc centred at (r, r)). Place it with
// translate/rotate/mirror; e.g. snap-cantilever-clip's root (finger face
// x = 0, strap face y = plate_depth, concave side x > 0, y < plate_depth) is
//   translate([0, plate_depth]) mirror([0, 1]) root_fillet_2d(f, t);
//
// Why this shape and not the disc: the disc quadrant (an intersection)
// touches each wall at a single tangent point and never welds into the
// union — snap-cantilever-clip's iteration 1 shipped 12 naked edges and
// 75/100 that way. The corner piece shares a full EDGE with each wall, which
// a 2D union merges exactly. `bite` (≥ 0) grows the square that far INTO
// both walls, so the piece welds by area overlap rather than a shared edge —
// use it when a wall face is slightly curved (an arch root) or when the
// piece is extruded and unioned in 3D. Both walls must be at least `bite`
// thick behind the corner and at least r long along it.
module root_fillet_2d(r, t, bite = 0) {
    _root_fillet_guards(r, t);
    assert(bite >= 0, str("root fillet bite must not be negative (got ", bite,
                          ") — the piece would stand off its walls and never weld"));
    difference() {
        translate([-bite, -bite]) square([r + bite, r + bite]);
        translate([r, r]) circle(r);
    }
}

// Fillet EVERY concave corner of the children at radius r — the
// morphological closing of let-folding-panel.scad:72-76, verbatim. Straight
// edges and convex corners come back nominally as they were (see the cost
// below); a fillet follows a curved face, which the corner piece above
// cannot. The cost: the two offsets re-sample any polygonal curve they pass
// over (measured on over-center-toggle-clamp's arch band: vertices up to
// 3.3 µm off along it, its convex end corners cut by up to 15.6 µm) — which
// is why bistable_arch_2d places corner pieces instead of closing its band.
//
// WELD HAZARD — read before wrapping a silhouette in this: a closing also
// FILLS every gap or slot narrower than 2·r. Wrap only the flexure's own
// silhouette (the beam and what it roots in), never a profile that contains a
// print-in-place clearance, or the closing welds the mechanism shut.
// bistable-toggle.scad:217-225 closes its stop cage on its own and unions the
// arch afterwards, so the cage↔arch clearances never enter a closing.
module rooted_2d(r, t) {
    _root_fillet_guards(r, t);
    offset(r = -r) offset(r = r) children();
}
