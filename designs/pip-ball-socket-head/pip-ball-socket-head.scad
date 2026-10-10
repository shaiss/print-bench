// pip-ball-socket-head — a print-in-place ball-and-socket positioner: a stem
// that bolts to a desk or shelf, and a head that comes off the bed with its
// ball captived inside a clamping socket. Tilt it, aim it, and the printed
// slit-collar friction lock holds the pose.
//
// Reference design for docs/advanced-techniques.md Domain 3 ("Ball-and-socket
// captives use an annular undercut; the capture ratio (throat/ball) trades
// retention against swing angle" + "Bearings & first motion") and Domain 2
// ("Designed-in / breakaway supports", "Sacrificial bridging"): the socket's
// upper hemisphere is an undercut over the ball that no orientation removes —
// solved here not with a sacrificial column but by ANGLE: every undercut
// surface closes at <= 25 degrees from vertical, so each printed ring lands on
// the one below (or on the ball, across a sub-bead sliver), and the only
// deliberately-fused interface is the ball's first layer kissing the cavity
// floor one layer down — the doc's micro-fused race, sheared by the firm
// twist of the documented break-in.
//
// THE CAPTURE GEOMETRY (why the cavity is arc / cone / rim / dome). The
// obvious "socket = ball + clearance, then pinch a throat" fails twice at
// once: a throat that pinches below the ball's local radius INTERFERES with
// the ball at that height (the designed parts must be interference-free at
// every z — only the whole ball must fail to pass the hole), and a tight bore
// above the ball kills tilt (the stud sweeps a wide cone). So the cavity is
// four regimes: the offset-sphere cup below (uniform radial clearance, like
// every printed bowl — self-supporting), a capture cone closing at <= 25 deg
// from vertical to the rim throat, the rim itself at `capture_depth` inside
// the ball's max radius (this is the capture: the ball cannot pass a hole
// smaller than itself — it is printed in place and never has to), then a dome
// re-opening at `dome_angle` to an aperture sized for the TILTED stud, not the
// ball. The rim's clearance to the ball is asserted; the tilt sweep is
// MEASURED, not asserted — `fitcheck_tilt` renders the ball+stud swept through
// ±max_tilt against the socket and must come back EMPTY (the perspective-coin
// `fitcheck_flip` pattern: articulation is proven by the check, never promised
// by a pose).
//
// ORIENTATION IS A CLEARANCE DECISION (doc CC1): the head prints stem-down.
// The cup's lower hemisphere is then an every-layer-supported bowl; the
// capture cone and dome close at <= 25 / 15 deg from vertical; the stud is a
// vertical cylinder; the M4 nut sits in a side-entry trap with a 1.6 mm floor
// (Drik R4: an open-bed pocket lets the nut walk toward the bolt). The nut
// slot's roof is a 7.4 mm AF-wide bridge; the only other horizontal ceiling
// is the 2 mm top annulus around the stud aperture, landing on the dome cone.
// Printed upside down (stud down) every one of those inverts into a real
// overhang and the dome becomes a bridge over the whole ball — don't.
//
// THE FRICTION LOCK. One vertical slit (width `slit_w`) splits the socket ring
// from just below its equator up through the dome; two wings outside the slit
// are pinched between finger and thumb, closing the slit and gripping the
// ball. Wings sit at the capture band, where grip pays rent. PETG for the head
// is the recommendation (the collar is creep-loaded; see README), PLA works
// for lighter payloads. No metal screw in the clamp in v1 — if the clamp
// can't hold the payload unaided, that is a FIELD-TEST finding (the
// czs-slider break-in-torque pattern), not a silent hardware addition.
//
// All dimensions in millimeters.

include <BOSL2/std.scad>             // cuboid (chamfered wing pads)
include <BOSL2/screws.scad>          // the 1/4-20 payload stud (repo rule: BOSL2 for machine threads)
use <printability.scad>              // rounded_box, chamfered_cylinder, screw_clearance_d
include <styles/workshop-utility/style.scad>

/* [Ball joint] */
// Ball diameter (mm) — the joint scales from this
ball_d = 20;
// Radial ball-to-socket clearance (mm), spread-limited (doc: 0.15–0.25). THE
// tuned fit — sweep it on the coupon; 0.15/0.20/0.25 cells provided.
ball_xy_clear = 0.2;
// Capture depth (mm): how far the rim throat sits inside the ball's max
// radius. The ball is printed captive, never assembled, so this is margin,
// not a snap force.
capture_depth = 1.5;
// Latitude above the ball's equator (deg) where capture begins — start the
// cone there and its overhang stays shallow
capture_start = 20;
// Rim height above ball centre (mm). Sets the rim's clearance to the ball
// (asserted) and where the clamp grips.
rim_above_center = 5.8;
// Dome opening angle from vertical (deg) above the rim — prints supportless
// and re-opens for the tilted stud.
dome_angle = 15;
// Dome aperture height above ball centre (mm) — sized for the tilted stud
// sweep (checked by fitcheck_tilt), not the ball.
dome_apex_above_center = 14;
// Max articulation (deg each side of vertical) the geometry guarantees.
max_tilt = 20;

/* [Stem & socket body] */
// Socket wall (mm) — keep >= 1.2 (3 perimeters at 0.4 mm nozzle)
wall = 2.5;
// Cup floor thickness under the cavity (mm)
floor_t = 2.5;
// Stem diameter at the bed (mm) — the tenon that seats in the base recess
stem_d = 14;
// 0.5 mm 45° elephant-foot chamfer under the flare (Jane: the Ø14 first
// layer vs 0.3 mm radial recess clearance). A cut into the expanding flare
// leaves a knife-edge skirt (Drik R3.1); this is a real chamfered cylinder
// *under* the original 45° cone, which is why zc() includes it.
tenon_bed_chamfer = 0.5;
// Flare height from tenon to socket ring (mm) — 45-degree, self-supporting
flare_h = 6;
// Slit width (mm) — a real slot, never printed shut
slit_w = 1.2;
// How far below the ball centre the slit starts (mm); below it the ring is
// solid and anchors the socket to the stem
slit_below_center = 2;
// M4 nut trap (Drik R4): a 1.6 mm floor under the nut so the bolt pulls the
// HEAD down. Side window opposite the slit, AF-wide and stopped at x = 0 so
// the +X hex half survives (Drik R5: a cube to x = +AC/2 at Y = ±AC/2
// erased every flat and the nut spun). Slot 3.8 mm for a 3.2 mm nut — the
// extra 0.2 mm is PETG roof sag over a 7.4 mm bridge.
nut_floor = 1.6;
nut_slot_h = 3.8;
nut_hex_d = 8.55;
nut_af = nut_hex_d * cos(30);  // 7.4; $fn=6 vertices on ±X, flats at ±Y

/* [Clamp wings] */
// Wing pad: thickness across the slit side (mm, X), length out from the ring
// (mm, Y each side), height (mm, Z), centre height above ball centre (mm, at
// the capture band — where grip pays rent)
wing_th = 8;
wing_len = 14;
wing_t = 8;
wing_z = 3.5;

/* [Payload stud — 1/4-20] */
// Unthreaded shank diameter through the dome aperture (mm)
stud_shank_d = 8;
// Threaded length above the dome (mm) — the de-facto camera standard
stud_thread_len = 12;
// Printed-thread loosening: subtracted from the thread's major diameter (mm).
// Raise in 0.05 steps if the stud won't enter a camera body.
stud_undersize = 0.15;

/* [Base — M4 foot plate] */
// Base plate width/depth (mm)
base_w = 48;
// Base plate thickness (mm)
base_t = 8;
// Pitch of the two M4 mounting holes (mm, X)
base_hole_pitch = 30;
// Recess the head's tenon seats in: diameter (mm) and depth (mm). Depth is
// whatever is left after the M4 socket-cap counterbore and a 1.6 mm web —
// the 45° flare only enters ~0.8 mm before it hits Ø14.6 (Drik R3.2).
tenon_recess_d = 14.6;
tenon_recess_depth = 2.4;
// How far the tenon actually sits into the recess (mm) — assembled preview.
// Not the recess depth: the cone wedges at Ø14.6 after ~0.8 mm.
tenon_seat = 0.8;

/* [Preview only] */
// Tilt the head for the assembled preview (deg). PRINT AT 0.
demo_tilt = 0; // [0:5:20]

/* [CI fit/fuse checks — not print parameters] */
// "" = assembled preview. "head"/"base" = printable parts. "coupon" = the fit
// coupon. "ball_only" = the ball body alone (mesh measurement). "fitcheck" =
// ball+stud ∩ socket at rest (must be EMPTY). "fitcheck_neg" = grown ball at
// rest (must INTERFERE — proves the check can fail). "fitcheck_tilt" = ball+stud
// swept through ±max_tilt ∩ socket (must be EMPTY — the articulation proof).
// "fitcheck_tilt_neg" = grown ball tilted (must INTERFERE). "fused" = the
// grown-ball weld for ci.fusecheck's known-fused control.
part = "";

/* [Quality] */
// Curves in this family draw at style_fn = 64; the ball is a large-radius
// curve — keep 96 (matches the sibling PIP designs).
$fn = 96;

// ---- derived -----------------------------------------------------------
ball_r  = ball_d / 2;
Rs      = ball_r + ball_xy_clear;      // cavity sphere radius (offset ball)
rim_r   = ball_r - capture_depth;      // rim throat radius
rho_a1  = Rs * cos(capture_start);     // cavity radius where capture begins
dz_a1   = Rs * sin(capture_start);     // its height above centre
apex_r  = rim_r + (dome_apex_above_center - rim_above_center) * tan(dome_angle);
ring_r  = Rs + wall;                   // socket ring outer radius
// capture cone angle from vertical, derived from the chosen rim (asserted)
capture_angle = atan((rho_a1 - rim_r) / (rim_above_center - dz_a1));
// rim's clearance to the ball at its own height (asserted)
rim_clear = rim_r - sqrt(ball_r^2 - rim_above_center^2);

// Ball-centre height above the head's bed: flare, cup floor, then the cavity
// sphere's lower half.
function zc(clear = ball_xy_clear) =
    tenon_bed_chamfer + flare_h + floor_t + (ball_d/2 + clear);

// The cavity's lower arc: offset-sphere from the bottom pole (latitude -90)
// to `capture_start` above the equator. Returns [r, z_rel_to_centre] points.
function arc_pts(Rs_, a1, n = 24) =
    [for (i = [0 : n])
        let (lat = -90 + (90 + a1) * i / n)
        [Rs_ * cos(lat), Rs_ * sin(lat)]];

// Cavity 2D profile, revolved about Z (r >= 0, z relative to ball centre).
// Four regimes (header): arc -> capture cone -> rim -> dome -> aperture bore,
// then up past the top so the cut is open.
function cavity_pts(clear) =
    concat(arc_pts(ball_d/2 + clear, capture_start),
           [[rim_r, rim_above_center],
            [apex_r, dome_apex_above_center],
            [apex_r, dome_apex_above_center + 6],
            [0, dome_apex_above_center + 6]]);

// Open-top coupon-cell cavity: arc -> capture cone -> rim -> short straight
// wall, no dome, no stud aperture.
function cell_cavity_pts(clear) =
    let (top = rim_above_center + 3)
    concat(arc_pts(ball_d/2 + clear, capture_start),
           [[rim_r, rim_above_center],
            [rim_r + 1, rim_above_center + 1.5],
            [rim_r + 1, top + 2],
            [0, top + 2]]);

// ---- bodies ------------------------------------------------------------

// The moving body: ball + shank + 1/4-20 stud. One printed body, printed
// captive inside the socket. `growth` inflates the ball for the negative
// controls (the weld the fit/fuse checks must see).
module ball_stud(clear = ball_xy_clear, growth = 0, with_stud = true) {
    translate([0, 0, zc(clear)]) {
        sphere(ball_r + growth);
        // shank: buried 2 mm into the ball's top (volumetric overlap, not a
        // kiss — a face-contact union exports as two shells), standing
        // through the dome aperture to 1 mm above its edge
        translate([0, 0, ball_r - 2])
            cylinder(d = stud_shank_d,
                     h = dome_apex_above_center + 1 - (ball_r - 2));
        if (with_stud)
            // the thread starts 0.2 mm DOWN inside the shank for the same
            // reason: the junction must be a volume overlap
            translate([0, 0, dome_apex_above_center + 0.8])
                screw("1/4-20", length = stud_thread_len, head = "none",
                      anchor = BOT, tolerance = "1A",
                      shaft_undersize = stud_undersize);
    }
}

// The socket body: tenon flare -> cup floor -> ring -> chamfered top, with
// the cavity cut, the slit, the wings, and the side-entry M4 nut trap.
// `dome = false` gives the coupon cell's open-top ring; `collar = false`
// omits the slit and wings (the fit checks isolate the joint from them — the
// wings never reach the cavity, so they cannot grip or collide).
module socket_body(clear = ball_xy_clear, collar = true, dome = true) {
    Rs_ = ball_d/2 + clear;
    ring = Rs_ + wall;
    top_rel = dome ? dome_apex_above_center + 2 : rim_above_center + 3;
    difference() {
        union() {
            // 0.5 mm 45° elephant-foot chamfer as its own cylinder under the
            // flare (Drik R3.1: a cut into the expanding cone left a V-groove
            // and a knife-edge Ø14 skirt). Then the original 45° flare — do
            // not steal flare_h or the ring junction goes past 45°.
            cylinder(d1 = stem_d - 2 * tenon_bed_chamfer, d2 = stem_d,
                     h = tenon_bed_chamfer);
            translate([0, 0, tenon_bed_chamfer])
                cylinder(d1 = stem_d, d2 = 2 * ring, h = flare_h);
            // floor slab + ring, from the flare top to the chamfered top edge
            translate([0, 0, tenon_bed_chamfer + flare_h])
                chamfered_cylinder(d = 2 * ring, h = floor_t + Rs_ + top_rel,
                                   chamfer1 = 0, chamfer2 = 0.6);
            // clamp wings: two pads flanking the slit, pinched along Y to
            // close it. They live INSIDE the union on purpose — the cavity is
            // cut after them, so any pad material that reaches into the ball's
            // space is trimmed away by construction and a wing can never grip
            // the ball it must not touch. The pads overlap the ring wall
            // radially (inner corner inside ring_r) so they fuse to it — a
            // wing that only NEARS the ring prints as a separate, loose part.
            if (collar)
                for (s = [1, -1])
                    translate([ring + wing_th/2 - 4,
                               s * (ring + wing_len/2 - 6),
                               zc(clear) + wing_z])
                        // rounding (the style's required 4 mm corner radius)
                        // wins over the advisory 0.6 chamfer: cuboid refuses
                        // both, and a 4 mm-round pad reads as the family
                        cuboid([wing_th, wing_len, wing_t], rounding = 4);
        }
        // the cavity — the whole point
        translate([0, 0, zc(clear)])
            rotate_extrude()
                polygon(dome ? cavity_pts(clear) : cell_cavity_pts(clear));
        // the clamp slit: a real slot through the ring at +X, from below the
        // equator (below it the ring is solid and anchors the stem) up and
        // out the top. The wings flank it (|y| >= wing offset > slit_w/2), so
        // the slot cuts the ring, never the pads.
        if (collar)
            translate([2, -slit_w/2, zc(clear) - slit_below_center])
                cube([4 * ring, slit_w, top_rel + 4]);
        // M4 nut trap: 1.6 mm floor (Ø4.5 through it) so tightening pulls
        // the nut down against HEAD material, not out the bed (Drik R4).
        // Hex pocket + side window at -X (the slit is +X). Window is AF
        // wide and ends at x = 0, so the +X hex half keys the nut
        // (Drik R5). Relief to z=8.5, 0.5 mm under the cup floor.
        translate([0, 0, -0.01]) cylinder(d = 4.5, h = 8.52);
        translate([0, 0, -0.01])
            cylinder(d1 = 5.5, d2 = 4.5, h = 0.51);
        translate([0, 0, nut_floor])
            cylinder(d = nut_hex_d, h = nut_slot_h, $fn = 6);
        translate([-4 * ring, -nut_af/2, nut_floor])
            cube([4 * ring, nut_af, nut_slot_h]);
    }
}

// The base: M4 foot plate — two mounting holes through, a centre recess the
// head's tenon nose seats in, an underside socket-cap counterbore so the
// plate sits flat on the mount, and a through hole for the M4×8 that pulls
// the tenon's captured hex nut down.
module base() {
    hd = socket_head("M4");
    difference() {
        rounded_box([base_w, base_w, base_t], r = style_corner_r,
                    bottom_chamfer = style_edge_chamfer);
        // tenon recess. Lead-in at the TOP mouth: wide at the plate top,
        // narrowing into the pocket (the previous cone was inverted and
        // lived above the part — Drik R3.2).
        translate([0, 0, base_t - tenon_recess_depth])
            cylinder(d = tenon_recess_d, h = tenon_recess_depth + 0.01);
        translate([0, 0, base_t - 0.6])
            cylinder(d1 = tenon_recess_d, d2 = tenon_recess_d + 1.2, h = 0.61);
        // M4 socket-cap counterbore on the underside, then a through hole.
        // Head below the recess floor so the tenon never sits on the bolt.
        translate([0, 0, -0.01]) cylinder(d = hd[0], h = hd[1] + 0.01);
        translate([0, 0, -0.01]) cylinder(d = 4.5, h = base_t + 0.02);
        // two M4 mounting holes (the brief's assumed shelf mount)
        for (x = [-base_hole_pitch/2, base_hole_pitch/2])
            translate([x, 0, -0.01])
                cylinder(d = screw_clearance_d("M4"), h = base_t + 0.02);
    }
}

// Head at the printed pose (part="head").
module head() {
    ball_stud();
    socket_body();
}

// The head tilted `a` degrees about the ball centre — pivot at the installed
// position for the preview: the tenon nose in the recess at `tenon_seat`
// (not the full recess depth — the cone cannot reach the floor).
module head_tilted(a) {
    translate([0, 0, base_t - tenon_seat + zc()])
        rotate([a, 0, 0])
            translate([0, 0, -zc()])
                head();
}

// tilt about the ball centre (the joint's pivot), at the head's own origin
module pose(a) {
    translate([0, 0, zc()])
        rotate([a, 0, 0])
            translate([0, 0, -zc()])
                children();
}

// The fit coupon (part="coupon"): three capture cells sweeping the clearance
// (0.15 / 0.20 / 0.25 — production = 0.20) plus the slit-collar station plus
// a short ¼″-20 stub. Each cell is the production cavity, open-topped: it
// tests the break-in fusion at the cup floor, the capture-cone clearance and
// the rim fit by feel — the dome/aperture sweep is CI's fitcheck_tilt's job,
// not a thumb's. The stub is the payload interface a camera body has to
// accept, so a rejected thread is not a multi-hour head reprint (Jane R2).
module coupon() {
    clears = [0.15, 0.20, 0.25];
    pitch = 2 * (ball_d/2 + 0.25 + wall) + 8;
    for (i = [0 : len(clears) - 1])
        translate([i * pitch, 0, 0]) {
            socket_body(clear = clears[i], collar = false, dome = false);
            ball_stud(clear = clears[i], with_stud = false);
        }
    // the collar station: production cavity at production clearance, slit +
    // wings, so the clamp grip and the wing pinch are tested before the real
    // multi-hour head
    translate([3 * pitch, 0, 0]) {
        socket_body(collar = true, dome = false);
        ball_stud(with_stud = false);
    }
    // 8 mm ¼″-20 stub on a 12 mm pad — one extra body on the strip
    translate([4 * pitch, 0, 0]) {
        cylinder(d = 12, h = 1.6);
        translate([0, 0, 1.4])
            screw("1/4-20", length = 8, head = "none",
                  anchor = BOT, tolerance = "1A",
                  shaft_undersize = stud_undersize);
    }
}

module main() {
    assert(ball_xy_clear >= 0.15,
           "ball_xy_clear under 0.15 mm is inside the bead-spread floor (doc: 0.15–0.25) — the joint welds");
    assert(wall >= 1.2, "socket wall under 1.2 mm (3 perimeters at a 0.4 mm nozzle)");
    assert(floor_t >= 1.2, "cup floor under 1.2 mm");
    assert(slit_w >= 0.8, "slit under one 0.4 mm extrusion width prints shut");
    assert(capture_depth >= 1 && capture_depth < ball_r,
           "capture_depth must be a real capture (>= 1 mm) but leave the rim a ring, not a point");
    assert(rim_clear >= ball_xy_clear + 0.05,
           "the rim interferes with the ball at its own height — raise rim_above_center or shallow capture_depth");
    assert(capture_angle <= 45,
           "capture cone overhangs past 45 degrees from vertical — raise rim_above_center or capture_start");
    assert(dome_apex_above_center > rim_above_center + 1,
           "the dome needs height above the rim to re-open");
    assert(apex_r > stud_shank_d/2 + ball_xy_clear,
           "the dome aperture does not pass the shank at rest");
    assert(rim_r < ball_r,
           "the rim is not inside the ball's radius — nothing captures the ball (the aperture may exceed it: the rim is the capture, not the aperture)");
    assert(flare_h >= ring_r - stem_d/2,
           "the flare is steeper than 45 degrees — the cup floor's underside overhangs");

    if (part == "head") {
        // demo_tilt is preview-only (PRINT AT 0). The tilted-pose camera
        // passes it with part="head" so the articulation is visible on the
        // printable body; gate.sh does not override it, so the gated STL
        // stays the as-printed pose.
        pose(demo_tilt) head();
    } else if (part == "base") {
        base();
    } else if (part == "coupon") {
        coupon();
    } else if (part == "ball_only") {
        ball_stud(with_stud = false);
    } else if (part == "fitcheck") {
        // at rest: the moving body must clear the socket on every surface
        intersection() { ball_stud(); socket_body(collar = false); }
    } else if (part == "fitcheck_neg") {
        // grown ball MUST overlap — proves the empty check can fail
        intersection() { ball_stud(growth = 1); socket_body(collar = false); }
    } else if (part == "fitcheck_tilt") {
        // articulation, measured: the stud sweeps a cone through the dome
        // aperture at every tilt — any pose that grips shows facets here
        union()
            for (a = [-max_tilt : 5 : max_tilt])
                intersection() {
                    pose(a) ball_stud();
                    socket_body(collar = false);
                }
    } else if (part == "fitcheck_tilt_neg") {
        // grown ball tilted MUST overlap — the sweep check's own control
        intersection() {
            pose(max_tilt) ball_stud(growth = 1);
            socket_body(collar = false);
        }
    } else if (part == "fused") {
        // ci.fusecheck's known-fused control: the grown ball welds into the
        // socket, collapsing the print into one body
        ball_stud(growth = 1);
        socket_body();
    } else {
        // assembled preview: head seated on the base, tilted to show the pose
        base();
        head_tilted(demo_tilt);
    }
}

main();
