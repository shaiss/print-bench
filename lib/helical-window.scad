// helical-window.scad — the ovodyo signature slot as a reusable brand mark.
// All dimensions in millimeters, angles in degrees. Use from a design with:
//   use <helical-window.scad>
//
// Extracted from the ovodyo epic (issue #599, workstream #601 item 5, filed
// as #613): a cut-through helical window both balls share and the base can
// deboss as a logo, with the sweep tied to the tumble-to-index motion — the
// brand parameterization is 450 deg of slot per 90 deg of index stop, a clean
// 5:1, so the mark spans exactly five stops of rise and lands coherent with
// the face that stops upright.
//
// The module is a CUTTER: difference() it from a shell to open the window,
// or pass depth = for a shallow deboss of the same mark. It knows nothing
// about the host beyond d and wall — the severance guard below protects the
// one property that lives in the window's own parameters.
//
// The sever bound is exact, and it is exact because the parameter domain is
// bounded to make it so. With this library's start convention (the same as
// threads-fdm's: starts are rotations of one helix, lead = pitch * starts),
// rotating by 360/starts translates axially by pitch — so at any fixed angle
// the window's passes sit exactly `pitch` apart, at EVERY starts. That makes
// severance a tiling question with a closed answer: passes `pitch` apart,
// each `width` tall, merge into one continuous encircling band exactly when
// width >= pitch. Measured on the export at pitch 8, sweep 450: width 7.9
// (a tenth inside the bound) leaves the shell one body; width 8.0 has no
// land at all and CGAL fails on the coincident faces ("mesh is not closed",
// a garbage STL, exit 0); width 8.5 with starts 2 renders and measures
// exactly two bodies. The full numbers are recorded in
// lib/helical-window-guards.conf.
//
// The bound is exact only because sweep >= 360 is REFUSED below one full
// turn. Under 360 deg a single start can never encircle — measured: sweep
// 270 at width 20 against pitch 4, a window five passes tall, still leaves
// the shell ONE body — but a multi-start set can tile the circle from
// partial windows (measured: sweep 270, starts 2, width 8.5 at pitch 8
// severs into two bodies), and no closed-form bound here promises to catch
// every such combination. The module refuses that regime rather than guard
// it approximately.

// Radial overcut on each side of the wall band, so the cutter clears the
// surfaces it cuts instead of kissing them — a coincident face is the classic
// CGAL artifact factory. One named number, same discipline as threads-fdm's
// _sink: the cutter must punch THROUGH, never terminate inside the wall.
_punch = 0.5;

// How far the polygonal sweep may let the cut edge fall inside the true helix
// it should trace — the chord error at the host's outer radius, same bound
// and same reasoning as threads-fdm's _max_chord (0.1 mm is a quarter of a
// 0.4 mm extrusion width). seg defaults to 96 rather than 48 because a brand
// mark's cut edge is the visible feature, not a flank hidden in a bore.
_max_chord = 0.1;

// One helical window, swept `starts` times.
//   pitch    axial spacing between passes at a fixed angle; lead = pitch*starts
//   sweep    total angular extent of each start's slot, degrees (>= 360)
//   width    axial width of the slot; the land between passes is pitch - width
//   starts   number of helical starts (>= 1, whole)
//   d        host outer diameter the window is cut around
//   wall     host wall thickness, so the cutter can punch through it
//   depth    radial cut depth for a DEBOSS; leave undef for a cut-through
//   seg      sweep samples per full turn, the $fn of the helix
//
// The sweep is centred on z = 0: the slot climbs `rise` = lead*sweep/360 over
// its travel, so it spans rise + width axially, symmetric about the origin —
// translate to mid-shell in the caller.
module helical_window(pitch, sweep, width, starts, d, wall, depth = undef,
                      seg = 96) {
    // These guards travel with the module on purpose: left behind in the
    // calling design, a severing parameter set renders as two clean bodies
    // with no warning at all — the failure this library exists to refuse.
    assert(pitch > 0, "helical_window pitch must be positive.");
    assert(width > 0, "helical_window width must be positive.");
    assert(starts >= 1, "helical_window starts must be at least 1.");
    // A fractional `starts` scales `lead` continuously while the [0:starts-1]
    // sweep rounds down — the same self-disagreement threads-fdm refuses.
    assert(starts == floor(starts), "helical_window starts must be a whole number.");
    // The domain restriction that makes the sever bound below exact. Measured
    // on the export: sweep 270 at width 20 against pitch 4 — a window five
    // passes tall — still leaves the shell ONE body, because a single start
    // cannot encircle; but sweep 270 with starts 2 at width 8.5, pitch 8
    // severs it into two. Partial multi-start windows tile the circle in
    // combinations no closed-form bound here promises to catch, so the module
    // refuses the regime rather than guard it approximately. The brand mark
    // sweeps 450 deg.
    assert(sweep >= 360, str(
        "helical_window sweep must be at least one full turn: sweep = ", sweep,
        " deg. Below 360 a single start cannot encircle the shell, but a ",
        "multi-start set can tile the circle in combinations the severance ",
        "bound does not promise to catch — the module refuses the regime ",
        "rather than guard it approximately. The brand mark sweeps 450 deg."));
    // THE sever guard. At width >= pitch the land between passes closes, the
    // slot stops being a helix, and the window becomes a continuous band
    // that encircles the shell and cuts it into two bodies — watertight,
    // sliceable, and scored 100/100 by everything that does not count
    // bodies (measured at pitch 8, starts 2, width 8.5: exactly two). Strict
    // <, because at equality the passes' faces coincide and the land is
    // exactly gone — and that is not merely topological: width 8.0 at pitch
    // 8 fails CGAL with "mesh is not closed", exports a garbage STL, and
    // still exits 0. The bound is the same at every starts since adjacent
    // passes always sit `pitch` apart (see the header); the multi-start case
    // below refuses the same inequality from the other side.
    //
    // The land is also the mark's look — the ovodyo window runs width 4
    // against pitch 8, a 50% land — but printability of a thin land is the
    // caller's call, not this guard's: it protects connectivity, nothing else.
    assert(width < pitch, str(
        "helical_window severs the shell: width = ", width, " must stay below ",
        "pitch = ", pitch, " — at width >= pitch the land between passes ",
        "(pitch - width = ", pitch - width, ") closes, the window stops being ",
        "a helix and becomes a continuous band that cuts the shell into two ",
        "bodies. Raise pitch or narrow width."));
    // `seg` samples the helix as a polygon, so the cut edge lands inside the
    // helix it is meant to trace — the silent shrink of issue #58, bounded
    // here exactly as threads-fdm bounds it: as a chord tolerance in mm, with
    // the message naming the seg that would satisfy it. Computed once and
    // reused by both the condition and the message so the number that FIRES
    // cannot drift from the number it REPORTS.
    chord_err = (d / 2) * (1 - cos(180 / seg));
    assert(chord_err <= _max_chord, str(
        "helical_window seg = ", seg, " chords too coarsely at d = ", d,
        ": chord error (d/2)*(1 - cos(180/seg)) = ", chord_err,
        " mm exceeds the ", _max_chord, " mm budget, letting the cut edge ",
        "fall that far inside the helix it should trace. Raise seg to at ",
        "least ", ceil(180 / acos(1 - 2 * _max_chord / d)), "."));

    lead  = pitch * starts;
    rise  = lead * sweep / 360;               // axial climb over the sweep
    r_out = d / 2 + _punch;
    r_in  = is_undef(depth) ? d / 2 - wall - _punch : d / 2 - depth;
    // Reaching the axis degenerates the sweep — CGAL answers with a bare
    // "assertion violation!" and exit 0, the garbage-STL failure the
    // threads-fdm core guard exists for. The bound covers both cut modes,
    // since r_in is whichever of the two applies here.
    assert(r_in > 0, str(
        "helical_window cutter reaches the axis: r_in = ", r_in,
        " must be positive. Raise d, or cut wall/depth."));
    // The depth override must actually cut something: a depth of 0 would
    // build a cutter exactly on the surface — a coincident face, not a mark.
    assert(is_undef(depth) || depth > 0, str(
        "helical_window depth must be positive for a deboss: ", depth,
        " would lay the cutter exactly on the surface it should cut."));

    // Rectangle profile in (r, z): the slot's axial width is `width` at every
    // radius, which is what makes the tiling arithmetic of the sever bound
    // exact. Sweeping it is thread_helix's machinery: end caps plus
    // triangulated side quads, explicit points and faces, convexity pinned.
    prof = [
        [r_in,  -width / 2],
        [r_out, -width / 2],
        [r_out,  width / 2],
        [r_in,   width / 2]
      ];
    k   = len(prof);
    N   = ceil(seg * sweep / 360);
    da  = sweep / N;
    dz  = rise / N;
    pts = [for (i = [0:N], p = prof)
              [p[0] * cos(i * da), p[0] * sin(i * da),
               p[1] + i * dz - rise / 2]];
    faces = concat(
        [[for (j = [k-1:-1:0]) j]],                 // start cap
        [[for (j = [0:k-1]) N * k + j]],            // end cap
        [for (i = [0:N-1], j = [0:k-1])                     // side quads,
            [i*k + j, i*k + (j+1)%k, (i+1)*k + (j+1)%k]],   // triangulated
        [for (i = [0:N-1], j = [0:k-1])
            [i*k + j, (i+1)*k + (j+1)%k, (i+1)*k + j]]
    );
    for (s = [0:starts-1])
        rotate([0, 0, s * 360 / starts])
            polyhedron(points = pts, faces = faces, convexity = 10);
}
