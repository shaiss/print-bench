// spring-rate-ladder — printed helical compression springs with derived k:
// one baseplate carrying three springs that differ only in active-coil count
// N, each with its predicted rate k = G·d⁴/(8·N·D³) embossed beside it, plus
// a guided-cap coupon that measures what the spring actually does on the
// owner's filament (issue #734).
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.

use <printability.scad>       // repo FDM helpers (OPENSCADPATH="$PWD/lib:$PWD")

/* [Spring] */
// Wire diameter (mm) — 4 extrusion widths at a 0.4 mm nozzle
d_wire = 1.6;
// Coil mean diameter (mm); spring index D/d = 10 at the defaults
d_mean = 16;
// Free length of every spring (mm)
l_free = 40;
// Closed (dead) coils at each end, for bearing and standing
end_coils = 1;
// Gap between the closed end coils (mm) — must stay > 0 so the sweep never
// self-touches (a self-tangent polyhedron is non-manifold); stays under one
// extrusion width so the dead coils weld in print, as a real closed end does
end_gap = 0.2;
// Active coils on the ladder stations, left to right (k ∝ 1/N)
ladder_ns = [4, 6, 8];

/* [Material] */
// Shear modulus PLA (MPa) — literature value; the coupon exists to measure
// your filament's real G (NOTES.md → "Print this first")
G_pla = 3500;
// Shear modulus PETG (MPa) — literature value; measure yours
G_petg = 1950;

/* [Ladder plate] */
// Station centre pitch along X (mm)
station_pitch = 36;
// Plate margin beyond the outer spring ODs (mm)
plate_end_margin = 18;
// Plate width across Y (mm)
plate_w = 44;
// Plate thickness (mm)
plate_t = 4;
// Spring centre offset behind the plate centreline (mm); text strip ahead
spring_y = 11;
// How deep the first closed coil sinks into the plate (mm) — roots the spring
spring_embed = 0.6;

/* [Coupon rig] */
// Active coils on the coupon spring (matches the middle ladder station)
coupon_n = 6;
// Guide post diameter (mm)
post_d = 5;
// Cap centre-hole clearance over the post (mm, on the diameter)
post_clearance = 0.6;
// Cap skirt clearance over the spring OD (mm, on the diameter)
cap_spring_clearance = 1.2;
// Cap skirt wall (mm)
cap_wall = 1.6;
// Cap skirt height (mm) — covers the top coil when seated
skirt_h = 10;
// Cap top disc thickness (mm)
cap_t = 4;
// Cap top disc diameter (mm)
cap_disc_d = 26;
// Resting gap between the cap disc underside and the spring's top wire
// SURFACE (mm) — one layer; the free spring holds the cap this far off
// contact, and it keeps the fitcheck boolean robustly empty at the seat
// (exact tangency hands CGAL a zero-volume contact to classify)
cap_seat_gap = 0.2;
// Coupon base pad diameter (mm)
coupon_pad_d = 26;
// Negative-control shrink (mm) for the fitcheck "interferes" pose — must
// overrun BOTH bore clearances (cap_spring_clearance, post_clearance)
fit_neg_delta = -1.6;

/* [Print] */
// Embossed text height above the plate (mm) — two 0.2 mm layers
emboss_h = 0.4;
// How deep the text block roots into the plate (mm) — kills the
// exactly-coplanar bottom face that corrupts CGAL unions once the springs
// subdivide the plate's top plane
text_sink = 0.2;

/* [Text layout] */
// Station text baselines (mm, plate coordinates): N label, PLA line, PETG
// line, plate footer
txt_label_y = -3.5;
txt_val1_y = -8;
txt_val2_y = -13;
txt_footer_y = -18;

/* [Quality] */
// Sweep steps per helix turn — resolution ALONG the wire; tied to the pitch,
// not to $fn, so a caller's cylinder quality cannot coarsen the coil
steps_per_turn = 48;
// Facets around the wire cross-section (Ø1.6 → 0.015 mm chord error at 20)
wire_sides = 20;
// Cylinders, pads, text arcs. Iterating: 32. Production: 64+.
$fn = 64;

part = "ladder";

// ---------------------------------------------------------------------------
// Spring mathematics
// ---------------------------------------------------------------------------

// Predicted rate (N/mm) of a round-wire helical compression spring:
//   k = G·d⁴ / (8·N·D³)      (G in MPa ≡ N/mm², lengths in mm)
// A prediction, not a measurement — the coupon measures the real k and backs
// out effective G for your filament. Literature G varies ±20 %, which is the
// uncertainty the coupon exists to remove.
function k_pred(G, n) = G * pow(d_wire, 4) / (8 * n * pow(d_mean, 3));

// Solid height (mm): every coil touching at pitch d_wire
function solid_height(n) = (n + 2 * end_coils) * d_wire;

// Force (N) the spring exerts compressed to solid — the coupon's max load
function f_solid(G, n) = k_pred(G, n) * (l_free - solid_height(n));

// Torsional shear stress at that force (MPa), Wahl-corrected
function tau_solid(G, n) =
    let (K_w = (4 * (d_mean / d_wire) - 1) / (4 * (d_mean / d_wire) - 4)
                       + 0.615 / (d_mean / d_wire))
    K_w * 8 * f_solid(G, n) * d_mean / (PI * pow(d_wire, 3));

// Fixed-point two decimals — str(0.1) prints "0.1", the plate wants "0.10"
function fmt2(v) =
    let (c = round(v * 100))
    str(floor(c / 100), ".", c % 100 < 10 ? "0" : "", c % 100);

function _unit(v) = v / norm(v);

// z of the wire centreline at turn-count u, piecewise pitch: closed ends at
// d_wire + end_gap, constant active pitch between them
function spring_z(u, e, n, p, pe) =
    u <= e       ? u * pe
  : u <= e + n   ? e * pe + (u - e) * p
  :                 e * pe + n * p + (u - e - n) * pe;

// ---------------------------------------------------------------------------
// The spring itself: one polyhedron sweeping a circular wire section along
// the helix. A circular section is invariant to frame twist, so the
// radial/tangential frame below needs no parallel transport — any orthonormal
// frame perpendicular to the tangent sweeps the same surface. The wire prints
// axis-vertical like a screw thread: the helix climbs at the lead angle
// atan(p / π·D) ≈ 10° at the defaults, so every wrap deposits on the wrap
// below it (the lib/threads-fdm.scad support-free argument, one tenth of the
// budget).
// ---------------------------------------------------------------------------
module helix_spring(d_wire, d_mean, n_active, l_free, end_coils = 1,
                    end_gap = 0.2, steps_per_turn = 48, wire_sides = 20) {
    pe = d_wire + end_gap;                  // closed-end pitch
    e = end_coils;
    turns = n_active + 2 * e;
    p = (l_free - 2 * e * pe) / n_active;   // active pitch

    assert(d_wire >= 1.2, "wire under the 3-perimeter wall floor (1.2 mm)");
    assert(n_active >= 2, "fewer than 2 active coils is not a spring");
    assert(p > d_wire,
        "free length leaves no active pitch — the spring is born solid");
    assert(atan(p / (PI * d_mean)) <= 45,
        str("active lead angle ", atan(p / (PI * d_mean)),
            "° exceeds 45° — the coil is no longer support-free"));
    assert(l_free >= turns * d_wire + 2,
        "free length under solid height + 2 mm — nothing left to measure");

    r = d_mean / 2;
    rw = d_wire / 2;
    S = ceil(turns * steps_per_turn);
    M = wire_sides;

    // OpenSCAD trig takes DEGREES — every angle below is 360*u / 360*j/M,
    // never 2π*u (that bug collapses the wire to a hair-thin strand).
    function path_point(u) =
        let (a = 360 * u)
        [r * cos(a), r * sin(a), spring_z(u, e, n_active, p, pe)];

    // Ring of M wire-surface points at sweep step i
    function ring(i) =
        let (u = turns * i / S,
             slope = u <= e ? pe : (u <= e + n_active ? p : pe),
             a = 360 * u,
             P = path_point(u),
             // d/du of the path, degree-consistent: xy turns at 360°/u, z at slope
             T = _unit([-r * sin(a), r * cos(a), slope / 360]),
             R = [cos(a), sin(a), 0],
             U = _unit(R - T * (T * R)),
             V = cross(T, U))
        [for (j = [0 : M - 1])
            let (phi = 360 * j / M)
            P + rw * (cos(phi) * U + sin(phi) * V)];

    n_pts = (S + 1) * M;
    points = concat([for (i = [0 : S]) each ring(i)],
                    [path_point(0), path_point(turns)]);
    // Side quads wound outward (U × V = T makes the (φ, u) triangle order the
    // outward normal); start cap fan reversed to face −T, end cap to face +T
    faces = [
        for (i = [0 : S - 1], j = [0 : M - 1])
            let (a = i * M + j,
                 b = i * M + (j + 1) % M,
                 c = (i + 1) * M + (j + 1) % M,
                 d2 = (i + 1) * M + j)
            each [[a, b, c], [a, c, d2]],
        for (j = [0 : M - 1])
            [n_pts, (j + 1) % M, j],
        for (j = [0 : M - 1])
            [n_pts + 1, S * M + j, S * M + (j + 1) % M]
    ];
    polyhedron(points, faces, convexity = 10);
}

// ---------------------------------------------------------------------------
// The ladder: baseplate, three springs, embossed predictions
// ---------------------------------------------------------------------------
module station_text(x, n) {
    translate([x, 0, plate_t - text_sink]) {
        translate([0, txt_label_y])
            linear_extrude(emboss_h + text_sink)
                text(str("N=", n), size = 4.5, halign = "center");
        translate([0, txt_val1_y])
            linear_extrude(emboss_h + text_sink)
                text(str("PLA ", fmt2(k_pred(G_pla, n))),
                     size = 3.2, halign = "center");
        translate([0, txt_val2_y])
            linear_extrude(emboss_h + text_sink)
                text(str("PETG ", fmt2(k_pred(G_petg, n))),
                     size = 3.2, halign = "center");
    }
}

module footer_text() {
    translate([0, txt_footer_y, plate_t - text_sink])
        linear_extrude(emboss_h + text_sink)
            text("k = G d^4 / 8 N D^3   (N/mm, predicted)",
                 size = 2.6, halign = "center");
}

module ladder_plate() {
    n_st = len(ladder_ns);
    assert(n_st >= 2, "a ladder needs at least two stations to compare");
    assert(station_pitch >= d_mean + d_wire + 6,
        "stations closer than spring OD + 6 mm — the springs merge");
    assert(plate_end_margin >= (d_mean + d_wire) / 2 + 2,
        "end margin under spring radius + 2 mm");
    assert(spring_y - (d_mean + d_wire) / 2 >= txt_label_y + 4.5 + 0.5,
        "station text collides with the spring footprint");
    assert(txt_footer_y - 2.6 >= -plate_w / 2 + 1,
        "footer text runs off the plate front edge");

    plate_l = (n_st - 1) * station_pitch + 2 * plate_end_margin;
    // rounded_box is corner-anchored ([0,size] in x/y) — center it so the
    // origin-centered station layout (and its text) lands on the plate
    translate([-plate_l / 2, -plate_w / 2, 0])
        rounded_box([plate_l, plate_w, plate_t], r = 3, bottom_chamfer = 0.6);

    for (i = [0 : n_st - 1]) {
        n = ladder_ns[i];
        x = (i - (n_st - 1) / 2) * station_pitch;
        translate([x, spring_y, plate_t - spring_embed])
            helix_spring(d_wire, d_mean, n, l_free, end_coils, end_gap,
                         steps_per_turn, wire_sides);
        station_text(x, n);
    }
    footer_text();
}

// ---------------------------------------------------------------------------
// The coupon rig: one spring rooted on a guided pad (the cap is the separate
// `cap` part — the rig's guided top plate the owner presses on)
// ---------------------------------------------------------------------------
// z of the coupon spring's top wire tangent (CENTERLINE) above the pad
function coupon_spring_top() = plate_t - spring_embed + l_free;

// z of the cap disc underside at its resting pose: the spring's top wire
// surface (centerline + wire radius) plus the seat gap — the pose the cap
// drops to before the spring takes load, and what ci.fitchecks gates
function coupon_cap_seat() = coupon_spring_top() + d_wire / 2 + cap_seat_gap;

module coupon_rig() {
    assert(skirt_h >= 3 * d_wire, "skirt too short to guide the top coil");
    chamfered_cylinder(d = coupon_pad_d, h = plate_t, chamfer1 = 0.6, chamfer2 = 0);
    // Guide post: rooted through the pad, 3 mm above the free spring top
    chamfered_cylinder(d = post_d, h = coupon_spring_top() + 3,
                       chamfer1 = 0, chamfer2 = 0.4);
    translate([0, 0, plate_t - spring_embed])
        helix_spring(d_wire, d_mean, coupon_n, l_free, end_coils, end_gap,
                     steps_per_turn, wire_sides);
}

// ---------------------------------------------------------------------------
// The guided top cap, working pose (skirt mouth at z = 0, disc above it).
// `delta` shifts the two bore clearances only: 0 is the production cap,
// fit_neg_delta is the deliberately undersized fitcheck negative control.
// ---------------------------------------------------------------------------
module cap_working(delta = 0) {
    spring_od = d_mean + d_wire;
    skirt_id = spring_od + cap_spring_clearance + delta;
    post_hole = post_d + post_clearance + delta;
    assert(skirt_id + 2 * cap_wall <= cap_disc_d,
        "skirt wall grows past the cap disc");
    assert(skirt_id > 0 && post_hole > 0, "negative control shrank a bore solid");
    difference() {
        union() {
            cylinder(d = skirt_id + 2 * cap_wall, h = skirt_h + cap_t);
            translate([0, 0, skirt_h]) cylinder(d = cap_disc_d, h = cap_t);
        }
        // spring pocket, open at the mouth
        translate([0, 0, -1]) cylinder(d = skirt_id, h = skirt_h + 1);
        // mouth lead-in so the cap finds the spring without shaving it
        translate([0, 0, -0.01])
            cylinder(d1 = skirt_id + 1.0, d2 = skirt_id, h = 0.5);
        // guide-post hole, through
        translate([0, 0, -1])
            cylinder(d = post_hole, h = skirt_h + cap_t + 2);
    }
}

// The cap as printed: disc down on the bed, skirt walls up — a cup, so the
// bearing face is a first-layer surface and nothing bridges
module cap_print() {
    translate([0, 0, skirt_h + cap_t]) rotate([180, 0, 0]) cap_working();
}

// ---------------------------------------------------------------------------
// Boolean fit gates (ci.fitchecks): the seated cap against spring + post.
// fitcheck (delta 0) must render EMPTY — the cap seats over the spring OD and
// rides the post at clearance. fitcheck_neg must render facets — the same
// pose with both bores undersized, proving the empty check can fail.
// ---------------------------------------------------------------------------
module fitcheck(delta) {
    assert(fit_neg_delta <= -(cap_spring_clearance + 0.4),
        "negative control does not overrun the skirt clearance — it would render empty and prove nothing");
    assert(fit_neg_delta <= -(post_clearance + 0.4),
        "negative control does not overrun the post clearance");
    intersection() {
        translate([0, 0, coupon_cap_seat() - skirt_h]) cap_working(delta);
        union() {
            translate([0, 0, plate_t - spring_embed])
                helix_spring(d_wire, d_mean, coupon_n, l_free, end_coils,
                             end_gap, steps_per_turn, wire_sides);
            chamfered_cylinder(d = post_d, h = coupon_spring_top() + 3,
                               chamfer1 = 0, chamfer2 = 0.4);
        }
    }
}

// ---------------------------------------------------------------------------
// Dispatch
// ---------------------------------------------------------------------------
module main() {
    if (part == "coupon")
        coupon_rig();
    else if (part == "cap")
        cap_print();
    else if (part == "fitcheck")
        fitcheck(0);
    else if (part == "fitcheck_neg")
        fitcheck(fit_neg_delta);
    else {
        ladder_plate();
        // The prediction the embossing states, echoed for the gate log —
        // the coupon's job is to measure where reality disagrees
        for (n = ladder_ns)
            echo(str("N=", n, ": k_pla=", fmt2(k_pred(G_pla, n)),
                     " k_petg=", fmt2(k_pred(G_petg, n)), " N/mm",
                     "  F_solid=", fmt2(f_solid(G_pla, n)), "/", fmt2(f_solid(G_petg, n)), " N",
                     "  tau_solid=", fmt2(tau_solid(G_pla, n)), "/", fmt2(tau_solid(G_petg, n)), " MPa"));
    }
}

main();
