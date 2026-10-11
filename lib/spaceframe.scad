// spaceframe.scad — the parametric space-frame truss generator.
// All dimensions in millimeters. Use from a design with:
//   use <spaceframe.scad>
//
// An exposed, airy bridge structure as an explicit engineering choice any
// design can make, not a one-off hull: two bottom chords and one top chord
// (a triangular cross-section — self-supporting slopes, no wide flat crown)
// with a web between them, spanning `length` along x and resting on the bed
// through the two bottom chords.
//
// THE FIVE THINGS IT STANDARDISES (issue #622, the platform half of #603):
//
//   space_frame(length, width, depth, bays,
//               topology = "warren", end_depth = 3,
//               strut_floor_mult = 3.5, x_depth = 0, part = "frame")
//
// 1. NAMED TOPOLOGY. "warren" (alternating face diagonals, ribs only at the
//    needle ends), "pratt" (a rib at every panel point plus face diagonals
//    descending toward midspan — each runs from the top chord at a panel's
//    outer station down to the bottom chord at its inner one, the tension
//    diagonals of a gravity-loaded pratt), "vierendeel" (ribs only — open
//    panels, no face diagonals). The rising mirror of pratt is the howe
//    truss, which this library does not offer. space_frame_diagonals()
//    exports the diagonal layout the module draws, so the direction is a
//    pinned contract (the demo asserts it), not a reading of the code. An
//    unknown name aborts the render; it never falls back silently.
//
// 2. TAPER. Frame depth (the outer z extent, bed plane to top-chord crown)
//    follows a raised-cosine law from `depth` at midspan out to `end_depth`
//    at the needle ends — tangential at the tips, so the needle eases in
//    with no kink. frame_depth_at(x, ...) is the curve, exported so a caller
//    can align features to the envelope. The chord centreline is a polyline
//    through the panel points — a chord approximation of the cosine: below
//    it across the concave midspan half, up to ~1 mm above it mid-bay in the
//    convex tip half (curvature x bay^2 / 8). The parameters are exact AT
//    the knots: the end nodes sit on the curve, so the measured needle depth
//    IS end_depth, never an extrapolation. `depth` is realised only where a
//    knot sits at midspan — an EVEN bay count. With an odd count the two
//    central knots straddle midspan and the built frame peaks below `depth`
//    (the demo's 5-bay main frame: ~16.5 mm at its central knots against
//    depth = 18), so use an even bay count when the midspan depth must be
//    realised.
//
// 3. SLENDERNESS TOKEN. strut_floor_mult states the strut section as a
//    multiple of the printable floor (0.8 mm, the repo's thin-feature
//    minimum), not a raw number; strut_section() derives the millimetres.
//    end_depth must be at least that section — a needle thinner than its
//    own members would measure fatter than the parameter claims, which is
//    exactly the silent lie the assert exists to prevent.
//
// 4. X-BRACING. x_depth in (0, 1] braces each vierendeel panel, per face,
//    with a hub-and-spoke X: four members from a central hub node to
//    attachment nodes on the panel's two ribs, spanning x_depth of the
//    panel height centred on its mid-depth (1 = the corner-to-corner
//    diagonals, halved at the hub; smaller = a shallower X nested in the
//    panel's middle). x_depth > 0 requires topology "vierendeel": warren and
//    pratt face diagonals already pass through the panel centres an X would
//    brace, so the combination is refused loudly rather than shipped as a
//    silently doubled-up braced frame.
//
// 5. THE RED STRUCTURAL CORE. part = "core" renders only the chord network —
//    the members that carry the span's bending, which is what a two-tone
//    export prints red (honest colour code: red = every working part).
//    part = "web" renders everything else (rungs, ribs, diagonals, X); the
//    default "frame" is their union. Each part is watertight on its own, and
//    their overlap is confined to joint halos around the shared panel nodes
//    (the beads, plus the wedge where a web member leaves a node it shares
//    with a chord at an angle) — quantified on the exports as
//    V(frame) = V(core) + V(web) − V(core ∩ web).
//
//    The web is not guaranteed to be one connected body, and does not need
//    to be: only the frame is the printable part. The warren zigzag reaches
//    alternate bottom nodes, so odd-station rungs bond to the frame through
//    the bottom chords, and a plain vierendeel web falls into one upright
//    per station (its X, or pratt's every-bay diagonals, bridge them).
//    Every web piece is closed and bed-resting — no floating fragments.
//
// THE JOINT SYSTEM. Every member is a cylinder whose flat end sits at a
// node centre, capped there by a JOINT BEAD — a sphere 15% fatter than the
// strut radius. The bead is not decoration: a same-radius sphere at a node
// where members arrive collinearly (the straight bottom chains; the top
// chain where the taper's bend passes through zero) is exactly inscribed in
// the member cylinder and touches it along a tangent circle, and CGAL exports
// that degenerate union as non-manifold edges with duplicate faces. A bead
// strictly fatter than every member through the node crosses all their walls
// transversally, so the union is clean at any member count — the classic
// ball-joint look of a real space frame. Top nodes are sunk by the bead
// excess so the bead's crown, not its centreline offset, defines the
// envelope: the outer z extent at every PANEL POINT is frame_depth_at(x)
// exactly (between panel points the chord approximation under TAPER applies).
//
// Members meet ONLY at shared node spheres: an endpoint of one member
// coincides with an endpoint (or a node placed on) another, and each part
// draws its own copy of every node its own members end at — that
// coincident-bead overlap is the core∩web joint-fusion zone the volume
// identity quantifies. Drawing
// one bead per node instead of one per member end is also what keeps a
// six-frame demo inside a civil CGAL render time. And it is why x_depth's X
// is hub-and-spoke rather than two diagonals crossing mid-member: two
// members whose AXES cross union as a degenerate pinch at the crossing,
// which exports as non-manifold. A shared endpoint sphere is a proper joint
// at any member count. Keep it that way when extending: never add a member
// whose axis merely crosses another's.
//
// BED CONTACT. Bottom nodes sit at (section/2 − squash) so the chords,
// rungs and end-node spheres are sunk slightly below z = 0 and then clipped
// by a halfspace: first-layer contact is a flat strip, not a tangent line a
// slicer cannot anchor to. The clip is applied identically to frame, core
// and web, which is what keeps the volume identity exact.
//
// TESSELLATION. This library does NOT pin $fa/$fs/$fn: a truss has no
// mating fit (hence no *-mates.conf — nothing here assembles against
// anything), so the caller's quality preset governs, as it does for the
// rest of their part. A capsule at a coarse $fn realises a slightly
// inscribed section (~2% at $fn = 16); that is the caller's trade-off, not
// a fit drifting.
//
// For a bracket that happens to need one rib, plain OpenSCAD is lighter;
// reach for this when the exposed structure IS the design.

// ---------------------------------------------------------------------------
// Derivations (public)
// ---------------------------------------------------------------------------

// The printable floor every strut section is a multiple of (mm) — the repo's
// 0.8 mm thin-feature minimum (CLAUDE.md, FDM conventions).
SF_PRINTABLE_FLOOR = 0.8;

// Raised-cosine taper weight w(u): 0 at a needle tip (u = 0), 1 at midspan
// (u = 1). Clamped, so callers may probe outside [0, length].
function _sf_taper_w(u) = (1 - cos(180 * min(max(u, 0), 1))) / 2;

// Frame depth — outer z extent, bed plane to top-chord crown — at station x.
function frame_depth_at(x, length, depth, end_depth) =
    let (u = min(x, length - x) / (length / 2))
    end_depth + (depth - end_depth) * _sf_taper_w(u);

// Strut section (mm) from the slenderness token: the token is a MULTIPLE of
// the printable floor, never a raw number.
function strut_section(strut_floor_mult) =
    assert(strut_floor_mult >= 1, str(
        "strut_floor_mult ", strut_floor_mult, " is below the printable minimum: ",
        "the section is strut_floor_mult x ", SF_PRINTABLE_FLOOR, " mm, so a multiple ",
        "under 1 puts every strut below the ", SF_PRINTABLE_FLOOR,
        " mm thin-feature floor"))
    strut_floor_mult * SF_PRINTABLE_FLOOR;

// The face-diagonal layout of a topology: one [top_station, bottom_station]
// pair per diagonal, stations indexed 0..bays along x. Both faces draw the
// same pairs (the top chord to the bottom chord on its side). space_frame()
// draws exactly this list, so a caller reads the member layout here instead
// of in the module, and the demo pins what each name promises:
//   warren     — alternating: even bays rise left-to-right (bottom i to
//                top i+1), odd bays fall (top i to bottom i+1).
//   pratt      — descending toward midspan: each diagonal's top end is the
//                panel's OUTER station (farther from midspan), its bottom end
//                the inner one. With an odd bay count the middle panel has
//                no inner side; it takes the left half's direction.
//   vierendeel — none (open panels).
// An unknown name aborts here too, so a direct caller cannot get a silent [].
function space_frame_diagonals(bays, topology) =
    assert(topology == "warren" || topology == "pratt" || topology == "vierendeel",
        str("space_frame_diagonals: unknown topology \"", topology,
            "\" — expected \"warren\", \"pratt\" or \"vierendeel\""))
    assert(bays == floor(bays) && bays >= 1,
        str("space_frame_diagonals: bays must be a whole number >= 1, got ", bays))
    topology == "warren"
        ? [for (i = [0:bays - 1]) i % 2 == 0 ? [i + 1, i] : [i, i + 1]]
    : topology == "pratt"
        ? [for (i = [0:bays - 1]) i < bays / 2 ? [i, i + 1] : [i + 1, i]]
    : [];

// ---------------------------------------------------------------------------
// Point helpers
// ---------------------------------------------------------------------------

function _sf_lerp(a, b, u) = [for (k = [0:2]) a[k] + u * (b[k] - a[k])];
function _sf_mid(a, b) = _sf_lerp(a, b, 0.5);
function _sf_vsub(a, b) = [a[0] - b[0], a[1] - b[1], a[2] - b[2]];

// ---------------------------------------------------------------------------
// Members
// ---------------------------------------------------------------------------

// A strut: a cylinder from p0 to p2, capped by the node beads the caller
// places at both ends (see THE JOINT SYSTEM above before adding anything
// that is not one of these). The flat end disc passes through the node
// centre, buried inside the fat bead there, so the joint closes
// transversally rather than tangentially.
module _sf_member(p0, p1, r) {
    v = _sf_vsub(p1, p0);
    translate(p0)
        // +z to v: yaw atan2(vy, vx) after pitch atan2(|v_xy|, vz) — the
        // Rz·Ry composition OpenSCAD's rotate([x, y, z]) applies.
        rotate([0, atan2(norm([v[0], v[1]]), v[2]), atan2(v[1], v[0])])
            cylinder(h = norm(v), r = r);
}

// A joint: one node bead. Members meet by ENDING here, never by crossing.
// rn is the bead radius (see THE JOINT SYSTEM); it exceeds the strut radius
// on purpose.
module _sf_node(p, rn) {
    translate(p) sphere(r = rn);
}

// The chord network — the red structural core (part = "core").
module _sf_chords(pts_bl, pts_br, pts_t, r, rn) {
    n = len(pts_bl) - 1;
    for (i = [0:n - 1]) {
        _sf_member(pts_bl[i], pts_bl[i + 1], r);
        _sf_member(pts_br[i], pts_br[i + 1], r);
        _sf_member(pts_t[i], pts_t[i + 1], r);
    }
    for (i = [0:n])
        for (p = [pts_bl[i], pts_br[i], pts_t[i]])
            _sf_node(p, rn);
}

// The web: rungs, ribs, face diagonals and X-bracing (part = "web").
// panel_nodes = true (part = "web") places the web's own node spheres at
// every panel node — coincident with the core's, and that duplicated sphere
// is the joint-fusion overlap V(core ∩ web) measures. part = "frame" passes
// false because the chords already placed those spheres: two coincident
// identical spheres union to exactly one, so skipping the duplicate changes
// no volume — the identity still holds against the standalone web export —
// while avoiding the degenerate coincident-surface union CGAL is slow at.
// The X attachment and hub nodes are always the web's alone.
module _sf_web(pts_bl, pts_br, pts_t, r, rn, topology, x_depth, panel_nodes) {
    n = len(pts_bl) - 1;

    // Panel beads the web EARNS: every bottom node carries a rung, but a
    // top node carries a web member only where a rib or diagonal ends there
    // (warren's zigzag reaches alternate top nodes; pratt and vierendeel,
    // with ribs at every panel point, reach them all). A bead at an
    // otherwise-untouched top node would be a floating body in the web-alone
    // export and pure colour-mix with no joint to fuse in the two-tone one.
    top_bead_at = topology == "warren"
        ? concat([0, n], [for (i = [1:n - 1]) if (i % 2 == 1) i])
        : [0:n];
    if (panel_nodes) {
        for (i = [0:n])
            for (p = [pts_bl[i], pts_br[i]])
                _sf_node(p, rn);
        for (i = top_bead_at)
            _sf_node(pts_t[i], rn);
    }

    // Transverse floor rung at every panel point, all topologies: what makes
    // this a space frame rather than two planar trusses, and the bed contact
    // between the chords. Endpoints coincide with bottom chord nodes.
    for (i = [0:n])
        _sf_member(pts_bl[i], pts_br[i], r);

    // Face ribs: T node down to each bottom chord node. Warren carries them
    // at the needle ends only (the bearing clusters); pratt and vierendeel
    // at every panel point.
    rib_at = topology == "warren" ? [0, n] : [0:n];
    for (i = rib_at) {
        _sf_member(pts_t[i], pts_bl[i], r);
        _sf_member(pts_t[i], pts_br[i], r);
    }

    // Face diagonals, drawn from the one exported layout (see
    // space_frame_diagonals): warren's alternating zig-zag, pratt's diagonals
    // descending toward midspan, none for vierendeel. Both faces in phase, so
    // the silhouette reads as one truss from either side. Each member is
    // drawn top node to bottom node: a cylinder from a to b and one from b to
    // a are the same faceted solid (the section polygon's vertex angles are
    // symmetric), so the draw direction changes no geometry.
    for (d = space_frame_diagonals(n, topology))
        for (base = [pts_bl, pts_br])
            _sf_member(pts_t[d[0]], base[d[1]], r);

    if (topology == "vierendeel" && x_depth > 0)
        // Hub-and-spoke X per panel per face: hub at the panel's centre, four
        // spokes to attachment nodes on the panel's ribs at u1/u2, spanning
        // x_depth of the panel height centred on its mid-depth. All spokes
        // END at shared node spheres (at x_depth = 1 the attachments are the
        // panel corners themselves), so nothing crosses mid-member.
        for (i = [0:n - 1])
            for (base = [pts_bl, pts_br]) {
                u1 = 0.5 - x_depth / 2;
                u2 = 0.5 + x_depth / 2;
                pl1 = _sf_lerp(base[i], pts_t[i], u1);
                pl2 = _sf_lerp(base[i], pts_t[i], u2);
                pr1 = _sf_lerp(base[i + 1], pts_t[i + 1], u1);
                pr2 = _sf_lerp(base[i + 1], pts_t[i + 1], u2);
                hub = _sf_mid(_sf_mid(base[i], pts_t[i]),
                              _sf_mid(base[i + 1], pts_t[i + 1]));
                for (p = [pl1, pl2, pr1, pr2]) {
                    _sf_member(hub, p, r);
                    _sf_node(p, rn);
                }
                _sf_node(hub, rn);
            }
}

// ---------------------------------------------------------------------------
// The generator
// ---------------------------------------------------------------------------

// length — span along x (mm); the frame occupies x = [0, length]
// width   — bottom chord separation along y (mm); top chord at y = 0
// depth   — the taper curve's outer z extent at midspan (mm); the built
//           frame reaches it only when a panel point sits at midspan, i.e.
//           an even bay count (see TAPER)
// bays    — panel count along the span (whole number >= 1)
// topology     — "warren" | "pratt" (diagonals descending toward midspan) |
//                "vierendeel"
// end_depth    — outer z extent at the needle ends (>= strut section)
// strut_floor_mult — strut section as a multiple of the 0.8 mm printable floor
// x_depth      — X-bracing depth as a fraction of panel height, (0, 1],
//                vierendeel only; 0 (default) = no X
// part         — "frame" (default) | "core" (chords only) | "web" (the rest)
module space_frame(length, width, depth, bays,
                   topology = "warren", end_depth = 3,
                   strut_floor_mult = 3.5, x_depth = 0, part = "frame") {
    s = strut_section(strut_floor_mult);
    r = s / 2;

    assert(length > 0 && width > 0 && depth > 0,
        "space_frame: length, width and depth must be positive");
    assert(bays == floor(bays) && bays >= 1,
        str("space_frame: bays must be a whole number >= 1, got ", bays));
    assert(topology == "warren" || topology == "pratt" || topology == "vierendeel",
        str("space_frame: unknown topology \"", topology,
            "\" — expected \"warren\", \"pratt\" or \"vierendeel\""));
    assert(depth >= end_depth,
        str("space_frame: depth must be >= end_depth (the taper runs from the ",
            "midspan depth down to the needle ends), got ", depth, " < ", end_depth));
    assert(end_depth > 0,
        str("space_frame: degenerate taper — end_depth must be positive, got ",
            end_depth));
    // The 1e-9 slack absorbs the section's floating-point product
    // (3.5 x 0.8 = 2.8000000000000003), so an end_depth stated as exactly
    // the section passes instead of being refused as "2.8 thinner than 2.8".
    assert(end_depth >= s - 1e-9,
        str("space_frame: end_depth ", end_depth,
            " is thinner than the strut section ", s,
            " — a needle cannot be thinner than its own members; raise end_depth ",
            "or strut_floor_mult"));
    assert(x_depth >= 0 && x_depth <= 1,
        str("space_frame: x_depth must be within (0, 1], or 0 for no X-bracing, ",
            "got ", x_depth));
    assert(x_depth == 0 || topology == "vierendeel",
        str("space_frame: x_depth > 0 needs topology \"vierendeel\" — warren and ",
            "pratt diagonals already pass through the panel centres an X would ",
            "brace, so the combination is refused rather than shipped with ",
            "doubled-up bracing"));
    assert(part == "frame" || part == "core" || part == "web",
        str("space_frame: unknown part \"", part,
            "\" — expected \"frame\", \"core\" or \"web\""));

    bay_x = length / bays;
    // Joint bead radius: 15% over the strut radius, so a bead is never
    // tangent-inscribed in a member through its node (see THE JOINT SYSTEM).
    rn = 1.15 * r;
    // Bottom nodes sunk by the squash so the clip below leaves a flat strip
    // of bed contact instead of a tangent line. Top nodes sunk by the FULL
    // bead radius so the bead's crown rides the taper envelope exactly.
    zb = r - min(0.5, 0.2 * s);
    pts_bl = [for (i = [0:bays]) [i * bay_x, -width / 2, zb]];
    pts_br = [for (i = [0:bays]) [i * bay_x,  width / 2, zb]];
    pts_t  = [for (i = [0:bays])
        [i * bay_x, 0, frame_depth_at(i * bay_x, length, depth, end_depth) - rn]];

    module body() {
        if (part != "web")  _sf_chords(pts_bl, pts_br, pts_t, r, rn);
        if (part != "core")
            _sf_web(pts_bl, pts_br, pts_t, r, rn, topology, x_depth,
                    panel_nodes = part == "web");
    }

    // Clip everything below the bed plane. Applied to frame, core and web
    // alike, so the volume identity holds on the parts exactly as shipped.
    // The clip's footprint is sized from the beads, not from the span: every
    // bead and member lies within rn of [0, length] x [-width/2, width/2],
    // so a margin of rn + 1 covers a frame of any width — a footprint scaled
    // from `width` alone let the bottom beads' undersides escape the clip on
    // frames narrower than two bead radii.
    m = rn + 1;
    difference() {
        body();
        translate([-m, -width / 2 - m, -s - 1])
            cube([length + 2 * m, width + 2 * m, s + 1]);
    }
}
