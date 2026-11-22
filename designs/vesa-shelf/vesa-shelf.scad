// vesa-shelf — a behind-monitor tray that bolts onto a display's published
// VESA MIS-D hole pattern (default 100 × 100, also 75 × 75) and cantilevers
// a small shelf into the dead space behind an arm-mounted monitor. Holds a
// Pi / mini-PC, slim video bar, USB hub, or cable loop without straps or
// adhesives. Mounting screws are purchased M4×0.7 machine screws into the
// display's own inserts — nothing printed threads into plastic.
//
// Print orientation = use orientation: tray floor flat on the bed, VESA
// plate standing at the back, 45° gussets under the tray, front lip and
// cable-loop ear chamfered so the whole part prints support-free. The four
// M4 bores run horizontal through the plate as teardrops (point up).
//
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.

use <printability.scad>       // repo FDM helpers (OPENSCADPATH="$PWD/lib:$PWD")
include <styles/workshop-utility/style.scad>  // tokens: r=4, chamfer=0.6, fn=64

/* [VESA pattern] */
// Square hole-pattern pitch (mm) — VESA MIS-D publishes 100 and 75.
vesa_pitch = 100; // [75, 100]
// M4 clearance hole diameter (mm) — printability.scad M4 preset (ISO 273)
m4_clear_d = 4.5;
// Optional Ø cable pass in the plate centre (mm; 0 disables)
cable_pass_d = 20;

/* [Plate & screw stack] */
// Plate thickness (mm) — 3 perimeters + infill; part of the engagement budget
plate_t = 6;
// Purchased flat-washer thickness assumed in the engagement budget (mm)
washer_t = 1.0;
// Purchased M4 screw length under the head (mm) — listed in the README BOM
screw_len = 16;
// VESA MIS-D typical max engagement into the display insert (mm)
max_display_engage = 10;
// Margin from each VESA hole centre to the plate edge (mm)
plate_margin = 12;

/* [Tray] */
// Tray floor width, left–right (mm) — fits a Pi 4 case (91) with margin
tray_w = 110;
// Tray floor depth, out from the plate face into the behind-monitor gap (mm)
tray_d = 80;
// Tray floor thickness (mm)
tray_t = 4;
// Vertical drop from the lower VESA hole centres to the tray top (mm).
// Brief's "standoff" row — the tray hangs BELOW the bolted pattern.
tray_drop = 25;
// Front lip height above the tray floor (mm)
lip_h = 8;
// Front lip thickness (mm)
lip_t = 3;
// Side-wall height on the closed cable edge (mm; the other edge stays open)
side_h = 6;
// Side-wall thickness (mm)
side_t = 2.4;

/* [Arm / gusset] */
// 45° gusset run under the tray from the plate out (mm)
gusset_run = 28;
// Gusset wall thickness (mm)
gusset_t = 4;
// Rated payload (g) — drives the root-section assert; defaulted with margin
payload_g = 400;

/* [Cable-loop ear] */
// Ear outer diameter on the open tray edge (mm; 0 disables)
ear_d = 14;
// Ear hole diameter (mm)
ear_hole_d = 6;

/* [Fit & print] */
// 45° chamfer on bed-contact edges (mm) — style_edge_chamfer
bottom_chamfer = 0.6;
// Corner rounding radius (mm) — style_corner_r; clamped on thin standing parts
corner_r = 4;

/* [Quality] */
// Iterating: 48. Production: 64+ (style_fn).
$fn = style_fn;

/* [Hidden] */
part = "shelf"; // [shelf]

// ---- derived -----------------------------------------------------------
// Plate must cover the pattern with margin on every side, and be at least
// as wide as the tray so the tray roots into a continuous wall.
plate_w = max(tray_w, vesa_pitch + 2 * plate_margin);
// Lower hole centres sit tray_drop above the tray top; upper = lower + pitch.
hole_z_lo = tray_t + tray_drop;
hole_z_hi = hole_z_lo + vesa_pitch;
plate_h = hole_z_hi + plate_margin;
// Hole X positions, centred on the plate.
hole_x = [(plate_w - vesa_pitch) / 2, (plate_w + vesa_pitch) / 2];
// Rounding that fits a thin standing part (rounded_box hull overshoots when
// 2*r exceeds the smallest footprint dimension — same clamp as the extrusion
// shelf bracket).
r_plate = min(corner_r, plate_t / 2);
r_lip = min(corner_r, lip_t / 2);
// Engagement into the display insert for the recommended screw stack.
display_engage = screw_len - plate_t - washer_t;
// Root section under a centred payload: tray width × tray thickness at the
// plate face. Section modulus for a rectangular section about the bend axis
// is (w * t²) / 6. Allowable bending stress for PETG with SF≈5 ~ 10 MPa.
// Moment ≈ payload * g * (tray_d / 2). Guard: Z >= M / sigma_allow.
payload_n = payload_g / 1000 * 9.81;
moment_nmm = payload_n * (tray_d / 2);          // N·mm
section_mod = tray_w * tray_t * tray_t / 6;     // mm³
sigma_mpa = moment_nmm / section_mod;           // N/mm² = MPa
sigma_allow = 10;                               // MPa, PETG SF≈5

// VESA plate standing on the bed at y = 0 (monitor face = y = 0 in use).
module vesa_plate() {
    rounded_box([plate_w, plate_t, plate_h], r = r_plate,
                bottom_chamfer = bottom_chamfer);
}

// Tray floor on the bed, extending +Y from the plate's outer face.
module tray_floor() {
    translate([ (plate_w - tray_w) / 2, plate_t - 0.01, 0 ])
        rounded_box([tray_w, tray_d + 0.01, tray_t], r = corner_r,
                    bottom_chamfer = bottom_chamfer);
}

// Low front lip at the outer tray edge — 45° bed chamfer, no supports.
module front_lip() {
    translate([ (plate_w - tray_w) / 2,
                plate_t + tray_d - lip_t,
                tray_t - 0.01 ])
        rounded_box([tray_w, lip_t, lip_h + 0.01], r = r_lip);
}

// Closed side wall on −X; +X stays open as the cable edge.
module side_wall() {
    translate([ (plate_w - tray_w) / 2,
                plate_t - 0.01,
                tray_t - 0.01 ])
        rounded_box([side_t, tray_d + 0.01, side_h + 0.01],
                    r = min(corner_r, side_t / 2));
}

// 45° gusset under the tray: triangle in the YZ plane, swept along X.
// Sunk 0.5 mm into plate and tray so the union is solid (Manifold-safe).
// rotate([90,0,90]) maps local (X,Y) → world (Y,Z) with extrusion → +X.
module gusset(x) {
    y0 = plate_t - 0.5;
    z0 = tray_t - 0.5;
    translate([x, 0, 0])
        rotate([90, 0, 90])
            linear_extrude(gusset_t)
                polygon([
                    [y0, z0],
                    [y0 + gusset_run, z0],
                    [y0, z0 + gusset_run],
                ]);
}

// Cable-loop ear on the open (+X) tray edge — a flat tab with a Ø ear_hole.
module cable_ear() {
    if (ear_d > 0) {
        ex = (plate_w + tray_w) / 2;
        ey = plate_t + tray_d * 0.55;
        difference() {
            hull() {
                translate([ex - side_t, ey - ear_d / 2, 0])
                    cube([side_t, ear_d, tray_t]);
                translate([ex + ear_d / 2 - 1, ey, 0])
                    cylinder(d = ear_d, h = tray_t);
            }
            translate([ex + ear_d / 2 - 1, ey, -0.01])
                cylinder(d = ear_hole_d, h = tray_t + 0.02);
        }
    }
}

// Four M4 teardrop bores through the plate (axis along Y, point +Z).
module vesa_bores() {
    for (x = hole_x, z = [hole_z_lo, hole_z_hi])
        translate([x, plate_t / 2, z])
            teardrop_hole(d = m4_clear_d, l = plate_t + 4);
}

// Optional centre cable pass — teardrop like the M4 bores so the roof
// self-supports (a round horizontal Ø20 left 94 mm² of unbridgeable overhang).
module cable_pass() {
    if (cable_pass_d > 0) {
        translate([plate_w / 2, plate_t / 2, (hole_z_lo + hole_z_hi) / 2])
            teardrop_hole(d = cable_pass_d, l = plate_t + 4);
    }
}

module shelf() {
    difference() {
        union() {
            vesa_plate();
            tray_floor();
            front_lip();
            side_wall();
            cable_ear();
            // Gussets at the tray's ±X lands (extrude in +X from each x).
            for (x = [ (plate_w - tray_w) / 2,
                       (plate_w + tray_w) / 2 - gusset_t ])
                gusset(x);
        }
        vesa_bores();
        cable_pass();
    }
}

module main() {
    assert(vesa_pitch == 75 || vesa_pitch == 100,
           "vesa_pitch must be a published MIS-D square pitch (75 or 100)");
    assert(plate_t >= 1.2 * 3, "plate under 3 perimeters at 0.4 nozzle");
    assert(tray_t >= 1.2 * 2, "tray floor under 2 perimeters");
    assert(display_engage <= max_display_engage,
           str("screw engagement into display is ", display_engage,
               " mm — shorten screw_len or thicken plate/washer to stay ≤ ",
               max_display_engage));
    assert(display_engage >= 4,
           str("screw engagement into display is only ", display_engage,
               " mm — lengthen screw_len or thin the plate/washer stack"));
    assert(m4_clear_d >= screw_clearance_d("M4") - 0.05,
           "m4_clear_d below the printability M4 preset");
    assert(sigma_mpa <= sigma_allow,
           str("root bending stress ", sigma_mpa,
               " MPa exceeds ", sigma_allow,
               " MPa allow — thicken tray_t or shorten tray_d"));
    assert(gusset_run <= tray_d - lip_t - 2,
           "gusset run collides with the front lip");
    assert(tray_drop >= 10, "tray_drop too small — payload fouls the lower screws");
    assert(lip_h >= 4, "front lip too short to retain a device");
    assert(hole_z_lo - m4_clear_d / 2 >= tray_t + 2,
           "lower VESA holes foul the tray floor");
    assert(plate_margin >= m4_clear_d,
           "plate_margin leaves no land around a VESA hole");
    if (cable_pass_d > 0)
        assert(cable_pass_d + 4 < vesa_pitch - m4_clear_d,
               "cable pass overlaps a VESA hole land");

    if (part == "shelf") shelf();
    else assert(false, str("unknown part: ", part));
}

main();
