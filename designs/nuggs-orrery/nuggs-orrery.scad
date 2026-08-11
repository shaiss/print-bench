// nuggs-orrery — a dual-material kinetic NUGGS module: a vortex of twisted
// fins around the standard 80 mm bore, carrying three CAPTIVE, free-spinning
// orbit rings printed in a second material on the same plate. The rings are
// topologically trapped (their hole is smaller than the fin cage) so the
// assembled state cannot be assembled — it can only be printed. Requirements,
// derivations and the dual-material print contract: see NOTES.md.
// All dimensions in millimeters.
//
// TWO STLs, ONE COORDINATE FRAME. `part="body"` (nozzle 1, PETG — carries
// every hamster-contact surface) and `part="orbit"` (nozzle 2, PLA — the
// rings and their break-away sprue frame) export in the same frame, so a
// slicer that imports both as one object with two parts reproduces the
// co-print exactly. Neither STL may intersect the other; `part="fitcheck"`
// renders their intersection and must come out EMPTY (measured in NOTES.md).
//
// THE RACE IS THE SUPPORT. Each ring seats on a 50-degree conical race grown
// from the tube wall. During the print the ring's lower-outer face lies
// race_gap above the race, parallel to it, so the second material prints
// directly on the first with no generated support anywhere in the model —
// and PETG/PLA do not weld, so the interface that supported the ring is the
// bearing it spins on afterwards. That anti-bond release is why this module
// NEEDS both nozzles: one material cannot print a zero-support captive ring
// on its own race without fusing to it, and swapping materials through one
// nozzle at every ring layer is not a real print.

use <nuggs-coupling.scad>
// This design is the orrery style's reference — and it builds from the
// style's own tokens (declared in style.conf), so the family stays one
// family: the ramp angle, blade thickness, ring section and seat gap below
// are assigned from style_* rather than retyped.
include <styles/orrery/style.scad>

/* [Part selection] */
// assembled = co-print preview (body + orbit, print state); body / orbit = the two material STLs CI gates; kinetic = display state (rings seated, sprues snapped); coupon = one-station fit coupon; fitcheck = body∩orbit, must be empty
part = "assembled"; // [assembled, body, orbit, kinetic, coupon, fitcheck]

/* [Module] */
// Tube length, port face to port face (mm). One enclosed-run contribution — couplings do not reset the run rule.
tube_len = 146;
// Animal body length the run limit derives from (mm) — measure the animal
body_len_mm = 180;

/* [Vortex fins] */
// Fin count around the tube
fin_n = 6;
// Fin blade thickness (mm)
fin_th = style_blade_th;
// Fin outer radius (mm) — the cage every ring is trapped inside
fin_r = 57;
// Total helical twist over tube_len (deg)
fin_twist = 75;
// Clock of fin 0 at z = 0 (deg) — sets where the wall engraving's clear gap falls
fin_phase = 15;
// Fin zone inset from each tube face (mm)
fin_inset = 16;
// Self-supporting chamfer angle, deg from horizontal. 50, not 45: printcheck's overhang test is a strict > against cos 45 and inscribed polygons sit ~0.01 deg past nominal (designs/nuggs, round 3)
ramp_ang = style_ramp_deg;

/* [Orbit rings] */
// Race seat heights: z of each ring's bottom land at print time (mm)
ring_seats = [44, 68, 92];
// Ring inner face radius (mm). CAPTIVITY: must stay well under fin_r — the ring's hole is smaller than the cage, so it cannot come off
ring_r_in = 54.8;
// Ring outer face radius (mm)
ring_r_out = 57.6;
// Ring height (mm)
ring_h = style_ring_h;
// Flat bottom land width (mm) — the ring's first printed layers; keep >= 2 extrusion widths
ring_land = 0.8;
// THE dual-material fit knob: vertical gap between ring land and race at print time (mm). Print the coupon first; tune in +/-0.05 steps. PETG/PLA anti-bond pairs run 0.05-0.15; a single-material fallback print needs 0.20-0.30 to break free
race_gap = style_seat_gap;

/* [Races & grooves] */
// Race root radius — where the conical race bites into the tube wall (mm)
race_root_r = 41.5;
// Race shell thickness, measured vertically (mm); normal thickness is this * cos(ramp_ang)
race_t = 1.9;
// Race outer edge radius (mm) — how far the cone follows the ring's underside
race_edge_r = 57.2;
// Groove floor: fins are cut back to this radius around each ring (mm)
groove_floor_r = 53.0;
// Straight groove height above each seat before the 50-deg roof starts (mm) — sets the ring's free axial rattle
groove_head = 6.5;

/* [Break-away sprues] */
// Sprue count — the frame that makes the orbit STL one rigid, sliceable piece
sprue_n = 3;
// Sprue radial span (mm)
sprue_r0 = 58.3;
sprue_r1 = 59.3;
// Sprue angular width (deg)
sprue_arc = 4;
// Clock of sprue 0 (deg)
sprue_a0 = 30;

/* [Wall marks] */
// Engrave depth into the tube wall (mm); wall left = wall - mark_d, asserted >= 3 perimeters
mark_d = 0.7;
// Character size (mm)
mark_size = 2.8;
// Baseline z of the two engraved lines (mm)
mark_z = [100, 93];

/* [Quality] */
// Production values. The coupling library pins its own $fa/$fs internally (its fit must not move with this preset); these govern the fins, races and rings.
$fa = 3;
$fs = 0.8;
// Twist tessellation of the fin extrusion
twist_slices = 96;

// ---------------------------------------------------------------------------
// NUGGS standard + derived values
// ---------------------------------------------------------------------------

cfg = nuggs_cfg();                       // the standard: bore 80, every default
RI    = nuggs_ri(cfg);
RO    = nuggs_ro(cfg);
Z_TIP = nuggs_z_tip(cfg);
Z_TOP = nuggs_z_top(cfg);

ramp     = tan(ramp_ang);
env_r0   = RO - 1;                            // fin envelope root, buried in wall
fin_z0   = fin_inset;
fin_z1   = tube_len - fin_inset;
fin_rise = (fin_r - env_r0) * ramp;           // 50-deg lead-in/out of the fin band
fin_full_z0 = fin_z0 + fin_rise;              // full-radius fin zone
fin_full_z1 = fin_z1 - fin_rise;

// Ring cross-section, local z from the seat. Bottom land [land_r0, land_r1] is
// horizontal (the first printed layers and the printcheck plate face); both
// lower faces climb at ramp_ang so the ring is self-supporting above its race.
land_r1 = (ring_r_in + ring_r_out) / 2 + ring_land / 2;
land_r0 = land_r1 - ring_land;
lower_h = (ring_r_out - land_r1) * ramp;      // outer/inner lower-face height

// Race top surface: passes race_gap under the land's outer edge and runs
// parallel under the ring's whole lower-outer face.
function z_race(seat, r) = seat - race_gap + (r - land_r1) * ramp;

// Groove band per station: fins cleared to groove_floor_r from just below the
// seat up to groove_head above it, then a ramp_ang roof (the captivity ceiling).
function g0(seat) = seat - 1.0;
function g1(seat) = seat + groove_head;
// z where full fin radius resumes above a station's roof
function roof_end(seat) = g1(seat) + (fin_r - groove_floor_r) * ramp;

seat_lo = ring_seats[0];
seat_hi = ring_seats[len(ring_seats) - 1];

// ---------------------------------------------------------------------------
// Guards — every one is a silent wrong-geometry failure without it
// ---------------------------------------------------------------------------

// WELFARE (run length). One limb of the Deutscher Tierschutzbund conjunctive
// acceptability test (<= 2x body length AND ventilated), applied per RUN;
// a coupling is NOT a break and does not reset the count — this module adds
// its whole tube_len to whatever run it is built into. The reversing
// derivation behind the 2x figure is engineering judgement (designs/nuggs
// round 5), not a sourced tolerance.
assert(tube_len <= 2 * body_len_mm, str(
    "ORRERY RUN: tube_len = ", tube_len, " mm exceeds the ", 2 * body_len_mm,
    " mm per-run limit (2 x body_len_mm, DTSchB acceptability test, one limb",
    " of a conjunctive rule; couplings do not reset a run). Shorten the tube",
    " or re-measure the animal."));

// CAPTIVITY is the design. The ring's hole must be decisively smaller than
// the fin cage or the 'only possible on a printer' claim quietly becomes
// 'slides on from the end'.
assert(fin_r - ring_r_in >= 1.5, str(
    "ORRERY CAPTIVITY: ring_r_in = ", ring_r_in, " leaves only ",
    fin_r - ring_r_in, " mm of fin overlap; below 1.5 mm a printed ring",
    " flexes over the cage and the captive claim is false. Shrink ring_r_in",
    " or grow fin_r."));
assert(ring_r_in - groove_floor_r >= 1.0, str(
    "ORRERY GROOVE: the ring's inner face clears the fin stubs by ",
    ring_r_in - groove_floor_r, " mm; under 1.0 mm the spinning ring grinds",
    " the stubs. Lower groove_floor_r or raise ring_r_in."));

// The race must root INSIDE the wall (never through it into the bore) and
// clear the port zone, or the coupling standard is compromised.
assert(race_root_r > RI + 0.7 && race_root_r < RO - 0.7, str(
    "ORRERY RACE ROOT: race_root_r = ", race_root_r, " must sit inside the",
    " tube wall (", RI, " .. ", RO, ") with >= 0.7 mm on both sides; outboard",
    " it only kisses the wall, inboard it breaches the bore."));
assert(z_race(seat_lo, race_root_r) - race_t >= Z_TOP + 2, str(
    "ORRERY RACE vs PORT: the lowest race roots at z = ",
    z_race(seat_lo, race_root_r) - race_t, ", inside the port zone (z_top = ",
    Z_TOP, " + 2 margin). Raise ring_seats[0]."));

// Fin band bookkeeping: every station needs full-radius fin below its groove
// (the lower captivity wall) and above its roof (the upper one).
assert(g0(seat_lo) >= fin_full_z0 + 2, str(
    "ORRERY STATIONS: the first groove starts at ", g0(seat_lo),
    " but full fin radius only exists from ", fin_full_z0,
    "; the bottom captivity wall is missing. Raise ring_seats[0] or cut",
    " fin_inset."));
assert(roof_end(seat_hi) <= fin_full_z1 - 1.5, str(
    "ORRERY STATIONS: the last roof ends at ", roof_end(seat_hi),
    " but full fin radius ends at ", fin_full_z1,
    "; the top captivity wall is missing. Lower ring_seats or grow tube_len."));

// Fin lean: a twisted blade's surface leans atan(r * twist-rate) from
// vertical; past 45 deg it IS the overhang printcheck fails.
assert(atan(fin_r * (fin_twist * PI / 180) / tube_len) <= 40, str(
    "ORRERY TWIST: the fin surface leans ",
    atan(fin_r * (fin_twist * PI / 180) / tube_len),
    " deg from vertical at fin_r; keep <= 40 (45 is the support threshold,",
    " 5 deg is margin). Cut fin_twist or fin_r, or grow tube_len."));

// The sprue frame must never touch the body — it belongs to the orbit STL.
assert(sprue_r0 - fin_r >= 1.0, str(
    "ORRERY SPRUE: sprue_r0 = ", sprue_r0, " clears the fin cage by ",
    sprue_r0 - fin_r, " mm; under 1.0 mm co-print ooze welds the break-away",
    " frame to the body."));
assert(sprue_r0 - ring_r_out >= 0.5 && sprue_r0 - ring_r_out <= 1.2, str(
    "ORRERY TAB: the tab bridges ", sprue_r0 - ring_r_out,
    " mm from ring to sprue; keep 0.5-1.2 mm so it prints as a micro-bridge",
    " and still snaps clean."));

assert(race_gap >= 0.04 && race_gap <= 0.40, str(
    "ORRERY RACE_GAP: ", race_gap, " mm is outside the tunable band",
    " 0.04-0.40. Tune on the coupon in +/-0.05 steps."));
assert(cfg[1] - mark_d >= 3 * 0.4, str(          // cfg[1] = wall
    "ORRERY MARK: engraving ", mark_d, " mm into a ", cfg[1],
    " mm wall leaves less than 3 perimeters."));

// ---------------------------------------------------------------------------
// Body (material A: every hamster-contact surface, the coupling, the races)
// ---------------------------------------------------------------------------

// Raw fin cage: six petals swept with twist, clipped by a revolved envelope
// whose lead-in/out faces sit at ramp_ang so the band is self-supporting.
// Petals run from the axis outward; the final bore cut makes them blades.
module fins_raw() {
    intersection() {
        linear_extrude(height = tube_len, twist = -fin_twist,
                       slices = twist_slices, convexity = 10)
            for (i = [0 : fin_n - 1])
                rotate([0, 0, fin_phase + i * 360 / fin_n])
                    translate([0, -fin_th / 2]) square([fin_r, fin_th]);
        rotate_extrude(convexity = 4)
            polygon([[0, fin_z0], [env_r0, fin_z0],
                     [fin_r, fin_z0 + fin_rise], [fin_r, fin_z1 - fin_rise],
                     [env_r0, fin_z1], [0, fin_z1]]);
    }
}

// One station's groove: clears the fins around the ring's airspace. The roof
// climbs at ramp_ang so the fin face left above the groove is printable.
module groove_cut(seat) {
    rotate_extrude(convexity = 4)
        polygon([[groove_floor_r, g0(seat)], [fin_r + 3, g0(seat)],
                 [fin_r + 3, g1(seat) + (fin_r + 3 - groove_floor_r) * ramp],
                 [groove_floor_r, g1(seat)]]);
}

// One conical race: a ramp_ang shell from inside the tube wall out to
// race_edge_r, whose top surface runs race_gap under the ring's lower-outer
// face. Simultaneously the ring's print support (via the anti-bond
// interface), its bearing, and its lower hard stop.
module race(seat) {
    rotate_extrude(convexity = 4)
        polygon([[race_root_r, z_race(seat, race_root_r) - race_t],
                 [race_edge_r, z_race(seat, race_edge_r) - race_t],
                 [race_edge_r, z_race(seat, race_edge_r)],
                 [race_root_r, z_race(seat, race_root_r)]]);
}

// Wall engraving, one character per tangent plane (a flat cut across the arc
// has a sagitta of mm; per character it is hundredths — designs/nuggs round
// 4). Each line is centred on the fin gap at its own height: the gap tracks
// the twist, so the centre angle is a function of z.
mark_lines = ["NUGGS PORT R1", "MAX RUN 360MM"];
function gap_center(z) = fin_phase + 180 / fin_n + fin_twist * z / tube_len;
module marks() {
    adv = mark_size * 0.95;                       // char pitch, mm of arc
    da  = adv / RO * 180 / PI;
    for (li = [0 : len(mark_lines) - 1]) {
        line = mark_lines[li];
        zc   = mark_z[li];
        for (ci = [0 : len(line) - 1])
            rotate([0, 0, gap_center(zc) + (ci - (len(line) - 1) / 2) * da])
                translate([RO - mark_d, 0, zc]) rotate([90, 0, 90])
                    linear_extrude(mark_d + 1.0)
                        text(line[ci], size = mark_size,
                             halign = "center", valign = "center");
    }
}

module body() {
    difference() {
        union() {
            cylinder(r = RO, h = tube_len);
            nuggs_port(cfg);                                   // bottom port
            translate([0, 0, tube_len])                        // top port
                mirror([0, 0, 1]) nuggs_port(cfg);
            difference() {
                fins_raw();
                for (s = ring_seats) groove_cut(s);
            }
            for (s = ring_seats) race(s);
        }
        // The mandatory bore cut, once, through the whole part — the port
        // emits material inside the bore on purpose (see the library header).
        nuggs_bore_cut(cfg, Z_TIP - 1, tube_len - Z_TIP + 1);
        marks();
    }
}

// ---------------------------------------------------------------------------
// Orbit (material B: the rings + the break-away sprue frame)
// ---------------------------------------------------------------------------

// One ring at its print seat. Flat bottom land (the first layers, and the
// plate-contact face printcheck measures on the lowest ring), lower faces at
// ramp_ang — the outer one parallel to the race race_gap below it.
module ring_at(seat) {
    rotate_extrude(convexity = 4)
        polygon([[land_r0, seat], [land_r1, seat],
                 [ring_r_out, seat + lower_h], [ring_r_out, seat + ring_h],
                 [ring_r_in, seat + ring_h], [ring_r_in, seat + lower_h]]);
}

// The break-away frame: sprue_n vertical spars outboard of everything,
// joined to each ring by a snappable tab. It exists for three reasons: the
// orbit STL slices as one continuous object (a slicer hard-fails on the
// empty layers between floating rings), it ships and mounts as one rigid
// piece, and after the print the tabs snap and the spars fall away — they
// are captive to nothing.
module sprues() {
    b = seat_lo + 0.5;
    t = seat_hi + ring_h - 0.2;
    for (k = [0 : sprue_n - 1]) rotate([0, 0, sprue_a0 + k * 360 / sprue_n]) {
        rotate_extrude(angle = sprue_arc, convexity = 4)     // the spar
            polygon([[sprue_r0, b + (sprue_r1 - sprue_r0) * ramp],
                     [sprue_r1, b], [sprue_r1, t], [sprue_r0, t]]);
        for (s = ring_seats)                                  // the tabs
            rotate([0, 0, (sprue_arc - 3) / 2])
                rotate_extrude(angle = 3, convexity = 4)
                    polygon([[ring_r_out - 0.3, s + 1.5],
                             [sprue_r0 + 0.2, s + 1.5],
                             [sprue_r0 + 0.2, s + 2.5],
                             [ring_r_out - 0.3, s + 2.5]]);
    }
}

module orbit() {
    for (s = ring_seats) ring_at(s);
    sprues();
}

// ---------------------------------------------------------------------------
// Coupon: one full ring station on a tube stub — the "print this first" part.
// Tunes race_gap (release + spin) without committing to the full module.
// ---------------------------------------------------------------------------

coupon_z0 = ring_seats[0] - 8;
coupon_z1 = ring_seats[0] + 22;
module coupon() {
    translate([0, 0, -coupon_z0]) {
        intersection() {
            body();
            translate([0, 0, coupon_z0])
                cylinder(r = fin_r + 5, h = coupon_z1 - coupon_z0);
        }
        ring_at(ring_seats[0]);
    }
}

// ---------------------------------------------------------------------------
// Part dispatch
// ---------------------------------------------------------------------------

if (part == "assembled") {
    body();
    color("deepskyblue") orbit();
} else if (part == "body") {
    body();
} else if (part == "orbit") {
    orbit();
} else if (part == "kinetic") {
    body();
    color("deepskyblue") for (s = ring_seats) ring_at(s - race_gap);
} else if (part == "coupon") {
    coupon();
} else if (part == "fitcheck") {
    // Must render EMPTY (zero facets, no STL written). Non-empty = the two
    // material STLs interfere and the co-print welds or collides.
    intersection() {
        body();
        orbit();
    }
}

echo(str("orrery: ring cage fin_r = ", fin_r, ", ring hole r = ", ring_r_in,
         " (captive overlap ", fin_r - ring_r_in, " mm); race_gap = ",
         race_gap, " mm; lift headroom above each seat = ",
         g1(ring_seats[0]) + (ring_r_in - groove_floor_r) * ramp
         - ring_seats[0] - ring_h, " mm"));
echo(str("orrery: enclosed run contribution ", tube_len, " mm of ",
         2 * body_len_mm, " mm per-run budget; couplings do not reset it"));
