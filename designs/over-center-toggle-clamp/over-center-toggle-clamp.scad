// over-center-toggle-clamp — print-in-place over-center toggle clamp for
// bench-top workholding. One PETG print, no hardware: a fixed jaw and a
// sliding moving jaw on captured rails, driven by a lever + link whose
// over-center closed pose self-locks, with a buckled-beam (PRBM) arch that
// makes the toggle bistable and supplies the jaw preload.
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.

use <printability.scad>       // repo FDM helpers (OPENSCADPATH="$PWD/lib:$PWD")

/* [Workpiece & jaws] */
// Maximum workpiece thickness the open jaws accept (mm) — brief #285
jaw_gap_max = 25;
// Gripping depth of both jaw faces, Y (mm) — brief #285
jaw_depth = 30;
// Jaw face height above the base plate's top surface (mm) — brief #285
jaw_height = 20;
// Thickness of each jaw wall (mm)
face_t = 6;
// X position of the fixed jaw's gripping face (mm)
fixed_face_x = 92;

/* [Over-center linkage] */
// Lever crank radius: pivot B to link pin P2 (mm)
crank_r = 42;
// Lever angle at the closed seat (deg). Dead center is theta = 0 (P2 on the
// B->P3 line, maximum jaw extension); the seat must be NEGATIVE — past dead
// center — so a workpiece reaction torques the lever INTO the closed stop
// (the over-center lock). A positive seat sits BEFORE center and the same
// reaction throws the lever open (the round-1 sign error; see NOTES.md).
theta_closed = -6;
// Lever angle as printed / fully open (deg)
theta_open = 44.8;
// Jaw gap remaining at dead center (mm). The lever must CROSS dead center at
// a positive gap or the empty jaws jam before center; workpieces thicker than
// this are squeezed elastically while crossing, and the seat gap (echoed)
// sets the bottom of the locked band. Retune to your stock: locked thickness
// ~ dead_center_gap + 0.5 mm.
dead_center_gap = 0.8;
// Carrier pin P3 sits this far behind the moving jaw face (mm)
p3_off = 13;
// Estimated series stiffness of the clamping loop (N/mm): jaw walls, link,
// pins. Used only in the echoed locked-band estimate, never in geometry;
// calibrate against a real print if you care about the exact band.
k_struct = 200;

/* [Snap-through arch (PRBM, docs/advanced-techniques.md)] */
// Tensile modulus of the printed material (MPa). PETG ~2000, PP ~1500.
E_mod = 2000;
// Arch span between anchor posts (mm)
arch_span = 85;
// Arch rise: apex offset of the neutral axis from the anchor line (mm)
arch_rise = 3;
// Arch beam thickness (mm) — >= 1.2 (3 perimeters), bends across roads
arch_t = 1.2;
// Arch beam width in Z (mm)
arch_w = 5;
// X of the arch apex / cam nub (mm)
arch_apex_x = 20;
// Y of the arch neutral line at its anchors (mm)
arch_line_y = -28;
// Extra apex travel past the second stable state at the closed seat (mm)
preload_past = 0.8;
// Free lever travel (deg) between the printed pose and flank pick-up
engage_free = 2.8;

/* [Handle] */
// Lever handle paddle, inner/outer radius from pivot B (mm). r_in must reach
// inside the boss rim (boss_d/2) or the paddle islands off the lever — caught
// by the ci.fusecheck control, not by printcheck ("multiple bodies" is only
// an INFO there).
handle_r_in = 6;
handle_r_out = 33;
// Handle paddle half-angle (deg)
handle_half = 11;

/* [Structure] */
// Base plate thickness (mm)
plate_t = 7;
// Rail wall height above the plate (mm); the lever band clears its top by pip_z
rail_h = 5;
// Rail capture lip thickness (mm)
lip_t = 1.4;
// Rail wall thickness (mm)
rail_wall_t = 3;
// Carrier slab length behind the jaw wall (mm)
carrier_slab_l = 42;
// Lever band thickness (mm)
lever_t = 4;
// Link band thickness (mm)
link_t = 4;
// Hard-stop post diameter (mm)
stop_post_d = 6;

/* [Pivots] */
// Pivot pin diameter (mm)
pin_d = 5;
// Pin head cone height (mm, 45° self-supporting)
head_h = 1.5;
// Pivot boss diameter (mm)
boss_d = 16;
// Link eye outer diameter (mm)
eye_d = 13;

/* [Print-in-place fit] */
// Sliding XY clearance per side (mm) — spread-limited, tune on the coupon
pip_xy = 0.25;
// Layer-snapped Z clearance (mm) — 2 layers at 0.2 mm
pip_z = 0.4;
// Cam flank radial film over the nub (mm); the arch spring closes it in use
cam_gap = 0.25;
// Cam nub radius (mm)
r_nub = 2.5;

/* [Quality] */
// Production: 64. Iterating: 32 (2x faster, same topology).
$fn = 64;

/* [Part] */
// assembly (the print) | fused (zero-clearance control for ci.fusecheck) |
// coupon | workpiece-held (preview-only closed pose, never gated/printed)
part = "assembly";

// ---------------------------------------------------------------------------
// Effective PIP clearances: the "fused" control renders with every moving
// interface coincident, which must weld into ONE body (ci.fusecheck). The cam
// carve deliberately INTERFERES 0.3 mm in that pose: the nub-in-cavity contact
// is a curved-surface coincidence there, and a guaranteed overlap welds the
// known-fused control without depending on CGAL's coincidence handling.
// ---------------------------------------------------------------------------
eff_xy  = part == "fused" ? 0 : pip_xy;
eff_z   = part == "fused" ? 0 : pip_z;
eff_cam = part == "fused" ? -0.3 : cam_gap;

// ---------------------------------------------------------------------------
// Kinematics — closed-form. The link has one length L between P2 (on the
// lever crank at angle t) and P3 (on the carrier, which only translates in X):
// requiring the same L at dead center (theta = 0, where extension peaks at
// jaw gap = dead_center_gap) and at theta_open (jaw_gap_max open) solves the
// pivot B_x and L analytically. Solving at CENTER, not at the seat, is the
// round-1 sign fix: the closed seat now lies past center at a slightly larger
// gap (the retention bump), so a seated workpiece torques the lever into the
// stop instead of throwing it open.
// ---------------------------------------------------------------------------
p3_dc_x   = fixed_face_x - dead_center_gap - p3_off;   // P3 at dead center
p3_open_x = fixed_face_x - jaw_gap_max - p3_off;       // P3 as printed

_ao = crank_r * cos(theta_open);    _so = crank_r * sin(theta_open);

// From  B_x + R + L = p3_dc_x  and  B_x + R cos(to) + sqrt(L² − (R sin to)²)
// = p3_open_x:  L = (G² + (R sin to)²) / 2G  with  G = stroke − R(1 − cos to)
_stroke = jaw_gap_max - dead_center_gap;
_G = _stroke - crank_r * (1 - cos(theta_open));
assert(_G > 0, str("linkage insolvable: jaw_gap_max - dead_center_gap = ",
    _stroke, " must exceed crank_r*(1-cos(theta_open)) = ",
    crank_r * (1 - cos(theta_open)), " — raise the stroke or drop theta_open"));
L_link = (_G ^ 2 + _so ^ 2) / (2 * _G);
B_x = p3_dc_x - crank_r - L_link;
B_y = 0;

// Carrier pin / jaw face position at lever angle t (the + root: P3 is
// outboard of P2 along +X through the whole sweep)
function p3_at(t) =
    B_x + crank_r * cos(t) + sqrt(L_link ^ 2 - (crank_r * sin(t)) ^ 2);
function face_at(t) = p3_at(t) + p3_off;
// d p3 / d theta, per radian. Its sign at the seat is the whole lock: a
// workpiece reaction R on the carrier (-X) torques the lever by -R*dp3_drad,
// so dp3_drad > 0 at the seat means the reaction drives theta MORE negative —
// into the closed stop, never toward open.
function dp3_drad(t) = -crank_r * sin(t)
    * (1 + crank_r * cos(t) / sqrt(L_link ^ 2 - (crank_r * sin(t)) ^ 2));

// Cam map: where the flank holds the arch apex at lever angle t. Linear from
// the printed (first stable) state at pick-up to just past the second stable
// state at the closed seat. Above pick-up the arch is unloaded and sits in
// its first stable state — the map CLAMPS there (a linear extrapolation would
// push the apex past state 1, which no spring force does).
theta_engage = theta_open - engage_free;
function apex_y_at(t) =
    arch_line_y - arch_rise
    + min(t - theta_engage, 0) / (theta_closed - theta_engage)
      * (2 * arch_rise + preload_past);

// ---------------------------------------------------------------------------
// PRBM predictions (docs/advanced-techniques.md, same model as bistable-toggle)
// ---------------------------------------------------------------------------
arch_I  = arch_w * arch_t ^ 3 / 12;                 // second moment of area (mm⁴)
f_snap  = 1486.57 * E_mod * arch_I * arch_rise / arch_span ^ 3;   // N
u_travel = 1.98 * arch_rise;                        // free apex travel (mm)
arm_flank = norm([arch_apex_x - B_x, arch_line_y - B_y]);          // mm
F_handle  = f_snap * arm_flank / handle_r_out;      // N at the paddle rim
kappa_s1  = 2 * PI ^ 2 * arch_rise / arch_span ^ 2; // curvature at state 1 (1/mm)
sigma_max = 1.3 * E_mod * (arch_t / 2) * kappa_s1;  // MPa incl. preload overshoot

// ---------------------------------------------------------------------------
// Z stack (all films are eff_z so the fused control truly welds)
// ---------------------------------------------------------------------------
arch_z0   = plate_t;                // arch stands directly on the plate: a
arch_z1   = plate_t + arch_w;       // downward apex load seats on the plate
rail_z1   = plate_t + rail_h;                        // rails top
lip_z0    = rail_z1 - lip_t;                         // capture lips underside
slab_z0   = plate_t + eff_z;                         // carrier slab bottom
slab_z1   = lip_z0 - eff_z;                          // under the lips
lever_z0  = rail_z1 + eff_z;                         // lever band clears rails
lever_z1  = lever_z0 + lever_t;
link_z0   = lever_z1 + eff_z;
link_z1   = link_z0 + link_t;
wall_z1   = plate_t + jaw_height;                    // jaw wall top
nub_z0    = arch_z1 - 1;                             // rooted 1 mm into the beam
nub_z1    = lever_z0 + lever_t - 1.4;                // engaged by the flank

// Rails: walls guide the carrier's Y; lips (x-clipped) capture its Z. The
// lips stop where the moving jaw wall begins its travel.
rail_x0   = 17;
rail_x1   = 91.5;
lip_x1    = 60.7;
channel_half = jaw_depth / 2 + eff_xy;               // rail wall inner face

// ---------------------------------------------------------------------------
// Guards — the render fails rather than shipping a silent geometry change
// ---------------------------------------------------------------------------
assert(arch_rise / arch_t >= 2.3,
    str("arch too flat to be bistable: rise/t = ", arch_rise / arch_t, " < 2.3"));
assert(arch_t >= 1.2, "arch beam under 3 perimeters (1.2 mm)");
assert(abs(face_at(theta_open) - (fixed_face_x - jaw_gap_max)) < 1e-6,
    "linkage closure identity failed: open gap != jaw_gap_max");
assert(abs(face_at(0) - (fixed_face_x - dead_center_gap)) < 1e-6,
    "dead-center identity failed: gap at theta 0 != dead_center_gap");
assert(dead_center_gap > 0,
    "the lever must cross dead center at a positive jaw gap, or the empty jaws jam before center");
assert(theta_closed < 0 && theta_closed > -12,
    "over-center margin: the closed seat must sit 0-12 deg PAST dead center (theta_closed < 0) so a workpiece reaction torques the lever INTO the closed stop");
assert(dp3_drad(theta_closed) > 0,
    str("no self-lock: dp3/dtheta at the seat = ", dp3_drad(theta_closed),
        " mm/rad must be > 0, so a seated workpiece reaction (-X on the",
        " carrier) makes a NEGATIVE lever torque - driving the lever into",
        " its stop, not toward open"));
assert(F_handle >= 8 && F_handle <= 15,
    str("predicted switch force ", F_handle, " N outside the 8-15 N brief band"));
// (plate bounds are derived below; the handle-sweep margin is asserted there)

// Locked band and its neighbours (documentation math — k_struct never shapes
// geometry). seat_gap is the jaw gap parked at the stop; retention is how far
// the face must be re-advanced (re-squeezing the workpiece) to escape back
// over center; theta_hump is where the arch's snap reverses direction.
seat_gap   = fixed_face_x - face_at(theta_closed);
retention  = face_at(0) - face_at(theta_closed);
t_lock_min = seat_gap + 30 / k_struct;          // holds the full 30 N budget
t_lock_max = dead_center_gap + 160 / k_struct;  // ~160 N crossing squeeze — a
                                                // firm press via the diverging
                                                // near-center advantage
theta_hump = theta_engage
    + arch_rise / (2 * arch_rise + preload_past) * (theta_closed - theta_engage);
t_spring_max = fixed_face_x - face_at(theta_hump);

echo(str("[over-center] pivot B = (", B_x, ", ", B_y, "), link L = ", L_link));
echo(str("[over-center] jaw face: seat x = ", face_at(theta_closed),
         " (gap ", seat_gap, "), dead center x = ", face_at(0),
         " (gap ", dead_center_gap, "), open x = ", face_at(theta_open),
         " -> gap = ", fixed_face_x - face_at(theta_open)));
echo(str("[over-center] LOCK: dp3/dtheta at seat = +", dp3_drad(theta_closed),
         " mm/rad -> closed-state workpiece reaction torque is NEGATIVE",
         " (into the stop); retention bump = ", retention, " mm"));
echo(str("[over-center] locked band ~ ", t_lock_min, "-", t_lock_max,
         " mm stock at k_struct = ", k_struct, " N/mm; spring-assisted hold",
         " (arch past its hump) up to ~", t_spring_max,
         " mm; thicker stock will not stay closed - retune dead_center_gap"));
echo(str("[over-center] arch: f_snap = ", f_snap, " N, u_travel = ", u_travel,
         " mm, apex map ", apex_y_at(theta_engage), " -> ", apex_y_at(theta_closed)));
echo(str("[over-center] switch force at handle rim = ", F_handle,
         " N (flank arm ", arm_flank, " mm)"));
echo(str("[over-center] arch bending stress ~ ", sigma_max, " MPa (PETG yield ~48)"));

// ---------------------------------------------------------------------------
// Layout bounds (derived, then guarded)
// ---------------------------------------------------------------------------
plate_x0 = B_x - handle_r_out - 2.4;   // clears the handle's closed-pose sweep
plate_x1 = fixed_face_x + face_t;
plate_y0 = -50;                        // clears the cam tail's closed-pose rim
plate_y1 = 24;

assert(B_x - handle_r_out > plate_x0 + 1,
    "handle sweep exceeds the plate's left margin");

// ---------------------------------------------------------------------------
// Small builders
// ---------------------------------------------------------------------------
// 2D annulus sector, angles in degrees
module annulus_sector(r_in, r_out, a0, a1) {
    steps = max(8, ceil((a1 - a0) / 5));
    outer = [for (i = [0:steps])
                let (a = a0 + (a1 - a0) * i / steps)
                [r_out * cos(a), r_out * sin(a)]];
    inner = [for (i = [steps:-1:0])
                let (a = a0 + (a1 - a0) * i / steps)
                [r_in * cos(a), r_in * sin(a)]];
    polygon(concat(outer, inner));
}

module pin_col(p, z0, z1) translate([p[0], p[1], z0])
    cylinder(d = pin_d, h = z1 - z0);

// 45° self-supporting retaining head, one pip_z above what it traps
module head_cone(p, zbase) translate([p[0], p[1], zbase])
    cylinder(d1 = pin_d, d2 = pin_d + 2 * head_h, h = head_h);

// ---------------------------------------------------------------------------
// Buckled-beam arch — neutral line y(x) bows toward -Y (first stable state as
// printed). Root fillets by the same offset trick bistable-toggle uses.
// ---------------------------------------------------------------------------
arch_x0 = arch_apex_x - arch_span / 2;
function arch_yc(x) =
    arch_line_y - arch_rise * (1 - cos(360 * (x - arch_x0) / arch_span)) / 2;

module arch_beam_2d() {
    n = 72;
    top = [for (i = [0:n]) let (x = arch_x0 + arch_span * i / n)
              [x, arch_yc(x) + arch_t / 2]];
    bot = [for (i = [n:-1:0]) let (x = arch_x0 + arch_span * i / n)
              [x, arch_yc(x) - arch_t / 2]];
    offset(r = -0.6) offset(r = 0.6) polygon(concat(top, bot));
}

module arch_assembly() {
    translate([0, 0, arch_z0]) linear_extrude(arch_w) arch_beam_2d();
    for (xe = [arch_x0, arch_x0 + arch_span])
        translate([xe - 5, arch_line_y - 5, plate_t])
            cube([10, 10, arch_w]);
    // cam nub: rooted in the beam, standing into the lever band
    translate([arch_apex_x, arch_yc(arch_apex_x), nub_z0])
        cylinder(r = r_nub, h = nub_z1 - nub_z0);
}

// ---------------------------------------------------------------------------
// Base: plate, fixed jaw, rails + lips, arch, lever pivot, hard stops, mounts
// ---------------------------------------------------------------------------
// Stop posts seat the paddle at the closed pose and 2.5° past the printed
// open pose (never touching at rest — that seam would weld).
closed_stop_ang = theta_closed + 180 - handle_half - asin(stop_post_d / 2 / 28);
open_stop_ang   = theta_open + 2.5 + 180 + handle_half + asin(stop_post_d / 2 / 23.5);

module stop_post(ang, r) translate([B_x + r * cos(ang), r * sin(ang), plate_t])
    cylinder(d = stop_post_d, h = lever_z1 - plate_t);

// Printed-pose link pin P2 (world) — the crank eye centre as printed
P2_open = [B_x + _ao, _so];

// Sacrificial film shelves under the printed-pose lever band. Without them
// the crank arm, handle paddle and crank eye extrude at lever_z0 over a
// 5.4 mm void (Jane's block, PR #414): the band's first layer had nothing to
// print on. Shelf tops sit at rail_z1 = lever_z0 - eff_z, so the band prints
// the same separable 0.4 mm film it already prints over the rail tops — and
// in the fused control (eff_z = 0) they weld, as every PIP interface must.
// Footprints are inset from the band outline so the film's perimeter always
// overhangs the shelf and cannot fuse laterally. The cam tail gets no shelf:
// it already films over the arch beam and rail tops, and a shelf there would
// either weld the arch span or block the carrier's swept volume.
module band_shelves() {
    // under the crank arm + eye (boss d16 / eye d13 -> shelf d10 / d8)
    translate([0, 0, plate_t]) linear_extrude(rail_z1 - plate_t) hull() {
        translate([B_x, B_y]) circle(d = 10);
        translate([P2_open[0], P2_open[1]]) circle(d = 8);
    }
    // under the handle paddle (sector inset 2 mm radially, 1.5 deg angularly)
    translate([B_x, B_y, plate_t]) linear_extrude(rail_z1 - plate_t)
        annulus_sector(handle_r_in + 2, handle_r_out - 2,
                       theta_open + 180 - handle_half + 1.5,
                       theta_open + 180 + handle_half - 1.5);
}

module base() {
    lip_w = channel_half - jaw_depth / 2 + 2;   // reach in over the slab
    difference() {
        union() {
            translate([plate_x0, plate_y0, 0])
                rounded_box([plate_x1 - plate_x0, plate_y1 - plate_y0, plate_t],
                            r = 6, bottom_chamfer = 0.6);
            // plate tab under the printed-pose crank eye + P2 pin column,
            // which otherwise stand past the plate's back edge (Jane's
            // block): plate under the eye, then the shelf films above it.
            // Starts at P2_open[0] - 12 (round 2): the crank shelf's left
            // hull edge crosses the plate's back edge at ~P2_open[0] - 11.7,
            // and a - 9 start left a ~2.7 mm sliver of shelf bottom bridging
            // over air there; the right edge stays at P2_open[0] + 9.
            translate([P2_open[0] - 12, plate_y1 - 3, 0])
                rounded_box([21, P2_open[1] + eye_d / 2 + 2.4 - (plate_y1 - 3),
                             plate_t], r = 3, bottom_chamfer = 0.6);
            band_shelves();
            // fixed jaw
            translate([fixed_face_x, -jaw_depth / 2, plate_t])
                cube([face_t, jaw_depth, jaw_height]);
            // rails + capture lips
            for (s = [-1, 1]) {
                translate([rail_x0,
                           s > 0 ? channel_half : -channel_half - rail_wall_t,
                           plate_t])
                    cube([rail_x1 - rail_x0, rail_wall_t, rail_h]);
                translate([rail_x0,
                           s > 0 ? channel_half - lip_w : -channel_half,
                           lip_z0])
                    cube([lip_x1 - rail_x0, lip_w, lip_t]);
            }
            arch_assembly();
            // lever pivot B: pedestal, pin, retaining head
            translate([B_x, B_y, plate_t]) cylinder(d = 9, h = rail_z1 - plate_t);
            pin_col([B_x, B_y], rail_z1, lever_z1);
            head_cone([B_x, B_y], lever_z1 + eff_z);
            stop_post(closed_stop_ang, 28);
            stop_post(open_stop_ang, 23.5);
        }
        // two M5 bench-mount holes at 40 mm centres (brief #285)
        for (hx = [-26, 14])
            translate([hx, 0, 0]) screw_hole(size = "M5", l = plate_t,
                                             head = "countersunk");
    }
}

// ---------------------------------------------------------------------------
// Carrier: sliding slab (captured under the lips), jaw wall, pin tower
// ---------------------------------------------------------------------------
module carrier(F) {
    P3 = [F - p3_off, 0];
    translate([F - face_t - carrier_slab_l, -jaw_depth / 2, slab_z0])
        cube([carrier_slab_l, jaw_depth, slab_z1 - slab_z0]);
    translate([F - face_t, -jaw_depth / 2, slab_z0])
        cube([face_t, jaw_depth, wall_z1 - slab_z0]);
    translate([P3[0], P3[1], slab_z1])
        cylinder(d = 9, h = lever_z1 - slab_z1);
    pin_col(P3, lever_z1, link_z1);
    head_cone(P3, link_z1 + eff_z);
}

// ---------------------------------------------------------------------------
// Lever: boss + crank arm + handle paddle + cam tail, carved by the sweep of
// the arch nub (tangential contact at every angle by construction)
// ---------------------------------------------------------------------------
// Carve sweep: 1 deg along the deflecting map, 0.5 deg across the free window
// (pick-up -> printed pose, where the nub is stationary and the tail rotates
// past it), and theta_open itself appended — the range alone can stop short of
// a non-integer pose, and the PRINTED pose must be carved or the tail welds
// into the nub. List comprehensions, not bare ranges: concat() passes a range
// literal through as a range object, and the carve silently no-ops on it.
cam_sweep = concat([for (i = [theta_closed : 1 : theta_engage]) i],
                   [for (i = [theta_engage + 0.5 : 0.5 : theta_open - 0.25]) i],
                   [theta_open]);

// Tail sector bounds, derived from the swept nub channel so a linkage
// re-solve cannot strand the flank (hardcoded bounds sized for the round-1
// pivot would leave the nub outside the tail at the new seat). The open-side
// edge sits exactly at the channel edge — no end wall there, so the lever can
// over-travel to its open stop — while the seat side keeps a 1.7 deg wall
// beyond the channel (flank material past the parked nub).
function nub_r_at(t)   = norm([arch_apex_x - B_x, apex_y_at(t) - B_y]);
function nub_ang_at(t) = atan2(apex_y_at(t) - B_y, arch_apex_x - B_x) - t;
tail_r_out = nub_r_at(theta_open) + r_nub + cam_gap + 0.6;
tail_a0 = nub_ang_at(theta_open)
    - asin((r_nub + cam_gap) / nub_r_at(theta_open));
tail_a1 = nub_ang_at(theta_closed)
    + asin((r_nub + cam_gap) / nub_r_at(theta_closed)) + 1.7;

module cam_carve() {
    for (t = cam_sweep)
        rotate([0, 0, -t])
            translate([arch_apex_x - B_x, apex_y_at(t) - B_y, 0])
                cylinder(r = r_nub + eff_cam, h = 60, center = true);
}

module lever() {                    // lever-local: pivot at origin, crank +X
    difference() {
        union() {
            translate([0, 0, lever_z0]) linear_extrude(lever_t)
                union() {
                    circle(d = boss_d);
                    hull() {
                        circle(d = boss_d);
                        translate([crank_r, 0]) circle(d = eye_d);
                    }
                    annulus_sector(handle_r_in, handle_r_out,
                                   180 - handle_half, 180 + handle_half);
                    annulus_sector(6, tail_r_out, tail_a0, tail_a1); // cam tail
                }
            // link pin P2 rises from the crank eye; its head traps the link
            pin_col([crank_r, 0], lever_z1, link_z1);
            head_cone([crank_r, 0], link_z1 + eff_z);
        }
        translate([0, 0, lever_z0 - 1])
            cylinder(d = pin_d + 2 * eff_xy, h = lever_t + 2);
        cam_carve();
    }
}

// ---------------------------------------------------------------------------
// Link, placed at the printed (open) pose
// ---------------------------------------------------------------------------
module link() {
    P2o = [B_x + _ao, _so];
    P3o = [p3_open_x, 0];
    difference() {
        translate([0, 0, link_z0]) linear_extrude(link_t)
            hull() {
                translate(P2o) circle(d = eye_d);
                translate(P3o) circle(d = eye_d);
            }
        for (p = [P2o, P3o])
            translate([p[0], p[1], link_z0 - 1])
                cylinder(d = pin_d + 2 * eff_xy, h = link_t + 2);
    }
}

// ---------------------------------------------------------------------------
// Coupon — the brief's force-measuring artifact. The PRODUCTION arch between
// two M5-anchored posts with a pull tab on the apex. Bolt the posts to
// anything rigid with the tab DOWN (+Y of the arch facing down), hang weight
// from the tab hole until the beam snaps through: that weight is f_snap.
// ---------------------------------------------------------------------------
module coupon() {
    floor_t = 6;
    wall_h = 16;
    half_l = arch_span / 2 + 9;
    difference() {
        union() {
            translate([-half_l, -12, 0]) cube([2 * half_l, 24, floor_t]);
            for (s = [-1, 1])
                translate([s * (arch_span / 2) + (s > 0 ? -3 : -9), -6, floor_t])
                    cube([12, 12, wall_h]);
            translate([-arch_apex_x, -arch_line_y, floor_t - plate_t])
                translate([0, 0, arch_z0])
                    linear_extrude(arch_w) arch_beam_2d();
            // pull tab on the apex
            translate([-3, -9, floor_t]) cube([6, 12, wall_h]);
        }
        // M5 anchor holes through the posts (same bolts as the base mount)
        for (s = [-1, 1])
            translate([s * (arch_span / 2 + 3), 0, -1])
                cylinder(d = 5.5, h = floor_t + wall_h + 2);
        // pull hole through the tab, on the arch neutral axis
        translate([0, -3, floor_t + 12]) rotate([0, 90, 0])
            cylinder(d = 5.5, h = 12, center = true);
    }
}

// ---------------------------------------------------------------------------
// Assembly at the printed (open) pose — the deliverable
// ---------------------------------------------------------------------------
module main() {
    base();
    carrier(face_at(theta_open));
    translate([B_x, B_y, 0]) rotate([0, 0, theta_open]) lever();
    link();
}

// ---------------------------------------------------------------------------
// Preview-only closed pose — NEVER gated, never printed (the "workpiece-held"
// camera in previews/cameras.conf). The clamp seated at theta_closed with a
// PCB-class plate in the jaws: link_pose() re-draws the link at any lever
// angle (link() stays the printed-pose original the gate hashes), and the
// workpiece is colored so it cannot be mistaken for part of the print. The
// 1.6 mm plate sits in the ~1.26 mm seat gap the way the real one does —
// squeezed: the ~0.17 mm/side interpenetration is the elastic squeeze a
// rigid preview cannot draw.
// ---------------------------------------------------------------------------
// Preview workpiece thickness (mm) — PCB-class stock in the locked band
workpiece_t = 1.6;

module link_pose(t) {               // link between P2(t) and P3(t)
    P2 = [B_x + crank_r * cos(t), crank_r * sin(t)];
    P3 = [p3_at(t), 0];
    difference() {
        translate([0, 0, link_z0]) linear_extrude(link_t)
            hull() {
                translate(P2) circle(d = eye_d);
                translate(P3) circle(d = eye_d);
            }
        for (p = [P2, P3])
            translate([p[0], p[1], link_z0 - 1])
                cylinder(d = pin_d + 2 * eff_xy, h = link_t + 2);
    }
}

module workpiece() {
    color("darkseagreen")
        translate([fixed_face_x - (seat_gap + workpiece_t) / 2, -24, plate_t])
            cube([workpiece_t, 48, 38]);
}

module workpiece_held() {
    base();
    carrier(face_at(theta_closed));
    translate([B_x, B_y, 0]) rotate([0, 0, theta_closed]) lever();
    link_pose(theta_closed);
    workpiece();
}

if (part == "fused" || part == "assembly") main();
else if (part == "coupon") coupon();
else if (part == "workpiece-held") workpiece_held();
else assert(false, str("unknown part: ", part));
