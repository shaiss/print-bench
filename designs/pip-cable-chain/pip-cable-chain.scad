// pip-cable-chain — a print-in-place energy chain (drag chain): a run of
// links, each printed already captured inside its neighbor's clevis, that
// comes off the bed articulated. Flex the run once to shear the break-in
// fusion and you have a working cable chain with hard ±45° end stops per
// joint, ready to route a moving cable loom. The chain-link captive joint
// the catalog names but didn't have (docs/advanced-techniques.md → Captive
// joints) — the prismatic-repeat sibling of pip-piano-hinge, where tolerance
// stacks ALONG the run the way the hinge stacks it across knuckles.
//
// Built on lib/print-in-place.scad's gated teardrop profile
// (_pip_teardrop2d, CC4: grow the bore by a true offset(), never a scaled
// teardrop) with the moves a chain needs on top of it:
//
// THE ROUND PIN (pip-piano-hinge's articulation finding, inherited). The pin
// stubs are plain cylinders and the teardrop lives on the BORE only, whose
// roof must bridge supportless. A teardrop pin would jam against the bore's
// flanks within a few degrees; this chain articulates ±45°.
//
// XY != Z CLEARANCE (the doc's clearance theory). One tunable radial
// tolerance, `clear_xy` (spread-limited), from which the sag-limited Z gap
// is DERIVED whole-layer: clear_z = ceil(max(clear_xy, layer_h)/layer_h)
// * layer_h. The bore is the lib profile grown by offset(clear_xy) UNIONED
// with copies shifted +-(clear_z - clear_xy) along Z — the sides stay
// spread-limited, while the roof over the pin AND the gap under it (both
// horizontal gaps a sagging layer must cross) open to clear_z. Nothing is
// scaled, so the offset guarantees clear_xy on every flank (CC4 intact).
//
// THE BLIND BORE (the chain's captivity). Each ear's bore is cut from the
// ear's inner face to a depth one `cap_t` short of its outer face, so the
// pin stub it swallows during the print cannot slide out along its own
// axis — the capture-ratio trick from the doc's ball-and-socket, as a cup.
// The stub ends `axial_gap` short of the cup floor (>= one extrusion width:
// a draped first layer welds across a nearer gap, the end_stop lesson).
//
// LINK TOPOLOGY (the y-stack, inside → out per side):
//   |y| <= 6        cable passage; its ceiling is VAULTED at exactly 45° —
//                   support-free by geometry, not by bridging
//   |y| in [6, 9]   the LUG band: the pin-stub bar runs here (x >= arm_x0).
//                   NO wall can stand in this band rearward of the arm post
//                   — the previous link's bar sweeps through it — so the
//                   passage's side opening is bounded by the ear walls.
//   |y| in [9.4, ear_y_out]  the EAR: the rear clevis, grown forward into a
//                   long NOSE to x = arm_x0: between joints the ear nose IS
//                   the passage side wall. The band is exclusive against the
//                   neighbor's LUG and PLATES (they live in other bands), but
//                   the neighbor's own EAR shares it — so the nose's front
//                   face is what the previous ear's rear-top corner (chamfered
//                   for exactly this) must clear on the up-bend (D7).
//   plates span the full width: the tunnel floor/roof and the ear cheeks.
//
// THE END STOPS ARE THE PLATES (±stop_angle, no extra parts). Each link's
// lug-tip corner rides over the next link's pocket plate and digs into its
// INNER face (the tunnel floor/ceiling) at exactly `stop_angle`, the
// penetration growing with angle — the only corner-vs-plate contact that
// blocks monotonically (derivation in the derived block and NOTES.md D4;
// the ±44°/±47° fitcheck poses are the rendered proof of both).
//
// PRINT POSE: flat and straight, pin axes horizontal (Y), teardrop roofs
// up — orientation IS the clearance decision (doc CC1). Default 11 links =
// a ~189 mm run that fits a 200 mm bed; -D links=20 for a long bed.
// All dimensions in millimeters.

use <printability.scad>     // screw_hole (repo FDM helpers)
use <print-in-place.scad>   // _pip_teardrop2d (the gated teardrop profile, CC4)
include <styles/ribbed-industrial/style.scad>

/* [Chain] */
// Number of links in the printed run. 11 = ~189 mm (fits a 200 mm bed);
// each extra link adds 16 mm.
links = 11;
// Link pitch: pin axis to pin axis (mm)
pitch = 16;
// Internal cable passage, width × height (mm) — the tunnel cross-section
passage_w = 12;
passage_h = 12;
// Flat mounting tabs with M4 holes on link 1 and link N only
end_tabs = true;

/* [Joint — the print-in-place fit] */
// Pin stub diameter (mm). Round, so it clears the bore at every angle.
pin_d = 5;
// THE tunable: radial pin-to-bore clearance in the horizontal plane (mm),
// spread-limited (doc: 0.15–0.25; pip_hinge's weld floor is 0.25). Tune on
// the coupon; clear_z follows.
clear_xy = 0.25;
// Print layer height (mm) — only used to snap the Z clearance to whole layers
layer_h = 0.2;
// Sag-limited Z gap, DERIVED whole-layer from clear_xy (doc's formula).
// Do not hand-edit: ceil(max(0.25, 0.2)/0.2)*0.2 = 0.4 = two whole layers.
clear_z = ceil(max(clear_xy, layer_h) / layer_h) * layer_h;
// Gap between the lug sides and the ear inner faces (mm) — vertical
// wall-to-wall, spread-limited
side_gap = 0.4;
// Gap between the pin stub end and the bore's blind floor (mm) — must
// exceed one extrusion width or a draped layer welds across it
axial_gap = 0.6;
// Articulation limit per joint (deg), realized by the plate placement
stop_angle = 45;

/* [Frame] */
// Tunnel wall thickness (mm) — ribbed-industrial builds at style_wall
wall = style_wall;
// Ear thickness beyond the side wall (mm): houses the blind bore + cap
ear_t = 5.7;
// Blind-bore outer cap thickness (mm) — keeps every wall >= 2 mm
// (ribbed-industrial chunky-sections)
cap_t = 2.0;
// Lug band half-height (mm) — the bar the pin stubs grow out of
lug_hz = 3.2;

/* [Preview only] */
// Bend joint 1 by this for the preview pose (deg). PRINT AT 0.
demo_bend = 0; // [0:5:45]

/* [CI fit/fuse checks — not print parameters] */
// "" = the straight run. "fitcheck" = overlap of every adjacent link pair
// at the print pose (must render EMPTY — they clear). "fitcheck_neg" = the
// same pair with an oversized pin stub (must render NON-EMPTY — proves the
// check can fail). "pose_up44"/"pose_dn44" = link 1 rotated ±44° about
// joint 1 against link 0 (must be EMPTY — articulation short of the stop).
// "stop_up47"/"stop_dn47" = rotated ±47° (must be NON-EMPTY — the printed
// stop blocks it). "fused" = oversized stubs at every joint, welding the
// run into ONE body for ci.fusecheck's known-fused control.
part = "";

/* [Quality] */
// A captive teardrop bore is $fn-sensitive — keep high (>= style_fn = 64).
$fn = 96;

// ---- derived -----------------------------------------------------------
z_pin   = wall + passage_h / 2;             // pin axis height above the bed
lug_y_in  = passage_w / 2;                  // lug inner face == tunnel side
lug_y_out = lug_y_in + wall;                // lug outer face == wall outer
ear_y_in  = lug_y_out + side_gap;           // ear inner face
ear_y_out = ear_y_in + ear_t;               // ear outer face == plate edge
plate_w   = 2 * ear_y_out;                  // roof/floor plate width
bore_circ = pin_d / 2 + clear_xy;           // bore's circular-zone radius
dz        = clear_z - clear_xy;             // whole-layer lift, roof + floor
bore_d    = ear_t - cap_t;                  // blind bore depth along Y
stub_y_out = ear_y_in + bore_d - axial_gap; // stub end short of the cup floor
stub_len   = stub_y_out - (lug_y_out - 1);  // stub, sunk 1 mm into the lug
bore_z_floor = z_pin - bore_circ - dz;      // lowest point of the bore cut
// Ear rear wall = ear_back - bore_circ >= 2 mm (chunky-sections: the p05
// wall-chord percentile — the thinnest 5% of the surface must still be 2 mm).
ear_back  = bore_circ + 2.0;                // ear rear face behind the axis
// Ear, main box: from just under the bore floor (0.3 wall) up 0.6 mm INTO
// the roof plate (overlap, never face-contact). Its stepped rear is
// structural, not sweep-clearance: the ear's y-band never overlaps the
// previous link's lug (side_gap apart), and its rear-top corner — the
// closest approach to the previous roof plate's front-top edge — must stay
// inside the radius that edge sweeps (asserted below).
ear_main_z0 = bore_z_floor + 0.3;
ear_z1      = wall + passage_h + 0.6;
// Ear, low web: ties the ear down into the floor plate. Overlaps the floor
// plate by 0.6 and the main ear by 0.3 (volumetric, not face-contact).
ear_low_x0 = -1.0;
ear_low_z0 = wall - 0.6;
ear_low_z1 = ear_main_z0 + 0.3;
// Lug arm: the wall band continued forward, x from arm_x0 (rear face) to the
// plate front edge. The post region (arm_x0..plate_x1, full height) ties
// floor + roof + lug into one body; everything of the PREVIOUS link that
// sweeps rearward past the joint (its floor plate's rear edge, its ear)
// stays below/above the plate bands or ahead of plate_x1, so arm_x0 is a
// stiffness choice, not a clearance one.
arm_x0 = 8.4;
// Ear nose: the ear boxes grow forward to the arm post's rear face, closing
// the passage's side between joints. Sweep-safe because the whole ear band
// (|y| >= ear_y_in) is exclusive to this link — no neighbor's geometry ever
// enters it at any bend angle (the previous bar and plates live in the lug
// band and the plate bands).
ear_nose = arm_x0;
plate_gap = 0.7;   // swept plate corner vs the next plate's front edge
// ---- The end-stop construction (a corner riding ONTO a plate face) ----
// In the rotating plate's frame the fixed lug-tip corner travels on
// x''(t) = lug_tip·cos t − lug_hz·sin t (decreasing) and z''(t) =
// −(lug_tip·sin t + lug_hz·cos t) (decreasing): it can only BLOCK by
// dropping through the plate's inner face plane z = ∓passage_h/2 —
// penetration (lug_tip·sin t + lug_hz·cos t − passage_h/2) then grows
// monotonically with t. A rear-face landing cannot block at all: the
// corner transits the plate and exits through the rear face (the v2
// up-stop missed exactly this way — window closed 0.4° before the check).
// So lug_tip puts the corner AT the inner face at exactly stop_angle:
lug_tip = (passage_h / 2 - lug_hz * cos(stop_angle)) / sin(stop_angle);
// and plate_x0 must be small enough that at stop_angle+2 the corner is
// still ON the plate (x'' > plate_x0 — it exits the rear face at
// lug_tip·cos 47° − lug_hz·sin 47° ~ 1.26, so 1.0 leaves 0.26 margin):
plate_x0 = 1.0;
// Pocket plates' front edge, DERIVED: the previous link's plate outer rear
// corner (plate_x0, ±(passage_h/2+wall)) sweeps back to x = plate_x0·cos
// − (passage_h/2+wall)·sin at stop_angle and must stay plate_gap ahead of
// this plate's front edge (−plate_back in joint-relative x).
plate_back = (passage_h / 2 + wall) * sin(stop_angle)
             - plate_x0 * cos(stop_angle) + plate_gap;
plate_x1 = pitch - plate_back;
// Floor extension's rear edge. Its bottom-rear corner is at bed level, so it
// sits >= z_pin from the axis — a bigger radius than the previous plate's
// front-TOP corner — and at the down-bend pose it rides onto that corner's
// plate (measured: a rear edge at -1.0 interfered 4.0 mm^3 at 44 deg). 0.6
// keeps the landing at stop_angle 0.2+ ahead of the plate front edge.
floor_ext_x0 = 0.6;
// The ridge's rear face. A ridge point at joint-relative (x_r, z_r) lands at
// pitch + x_r*cos(a) - z_r*sin(a) when the joint bends up by a; the worst
// point is the crest. The rear face must sit far enough forward that the
// crest still lands ahead of the previous plate's front edge at the pose
// angle (stop_angle-1) — plate_back's discipline, solved for the taller
// profile the flat-plate derivation never saw (measured: a rear face at
// plate_x0 interfered 13.2 mm^3 at 44 deg).
ridge_c = 1;       // flat crest half-width (>= 2 mm material at the peak)
crest_z = wall + passage_h + wall + passage_w / 2 - ridge_c;
ridge_x0 = (plate_x1 + 0.3 - pitch
            + (crest_z - z_pin) * sin(stop_angle - 1)) / cos(stop_angle - 1);
arm_x1b = plate_x1;   // arm front face flush with the plate front edge

// The bore cutter: the lib's gated teardrop profile, offset-grown (CC4)
// with the ±dz copies that open roof AND floor to the whole-layer clear_z.
// Same construction as pip-piano-hinge's knuckle. Cut from an ear's inner
// face outward, leaving the blind cap.
module bore_cutter() {
    rotate([90, 0, 0])   // +90: the teardrop point becomes the +Z roof
        linear_extrude(bore_d + 0.01)
            union() {
                offset(r = clear_xy) _pip_teardrop2d(pin_d);
                translate([0,  dz]) offset(r = clear_xy) _pip_teardrop2d(pin_d);
                translate([0, -dz]) offset(r = clear_xy) _pip_teardrop2d(pin_d);
            }
}

// A slab (floor or roof plate, or a tab) chamfered 45° on one face at
// style_edge_chamfer — the style's edge break, by hull of two footprints
// whose inset equals their rise, so the flank is 45° by construction.
module chamfered_slab(x0, x1, z_bot, h, top) {
    c = style_edge_chamfer;
    y0 = -plate_w / 2;
    hull() {
        translate([x0, y0, top ? z_bot : z_bot + c])
            cube([x1 - x0, plate_w, h - c]);
        translate([x0 + c, y0 + c, top ? z_bot + h - 0.01 : z_bot + 0.01])
            cube([x1 - x0 - 2 * c, plate_w - 2 * c, 0.01]);
    }
}

// The 45° VAULT (the roof over the passage). A flat tunnel ceiling is a
// 12 mm bridge — printable, but ribbed-industrial demands support-free
// GEOMETRY (no downward face shallower than 45°), and a bridge is exactly
// that face. So the passage ceiling is two 45° planes meeting at a ridge:
// every downward face of the roof is at or steeper than 45°, genuinely
// support-free even on a printer that can't bridge. The ridge prism stands
// on the plate's shoulders (volumetric overlap at its feet) and is cut by
// the vault void from below, so the finished ceiling is the void's 45°
// planes. The vault lives strictly inside |y| < passage_w/2: the ±45° STOP
// lands on the flat ceiling over the lug band (|y| in [6, 9.4]), which the
// vault never reaches.
module roof_ridge() {
    yv = passage_w / 2;
    zc = wall + passage_h;
    cr = ridge_c;
    // (u,v) profile in (y,z), extruded -X from the plate's front face;
    // the profile is y-symmetric so the rotate's y-mirror is a no-op.
    translate([plate_x1, 0, 0]) rotate([90, 0, 0]) rotate([0, -90, 0])
        linear_extrude(plate_x1 - ridge_x0)
            polygon([[-yv, zc + wall],
                     [-cr, zc + wall + yv - cr], [cr, zc + wall + yv - cr],
                     [yv, zc + wall],
                     [yv - 0.3, zc], [0, zc + yv - 0.3],
                     [-(yv - 0.3), zc]]);
}

// The vault void: the passage space above the old flat ceiling, bounded by
// two exact-45° planes (dz/dy = 1). Sunk 0.02 below the ceiling plane so
// the difference never leaves a zero-thickness sliver at the foot.
module vault_void() {
    yv = passage_w / 2;
    zc = wall + passage_h;
    // spans exactly the ridge's x-extent: carve past it and the flat ceiling
    // behind ridge_x0 opens a hole in the roof
    translate([plate_x1 + 0.01, 0, 0]) rotate([90, 0, 0]) rotate([0, -90, 0])
        linear_extrude(plate_x1 - ridge_x0 + 0.02)
            polygon([[-yv, zc - 0.02], [0, zc - 0.02 + yv],
                     [yv, zc - 0.02]]);
}

// One link, printed. Origin at ITS rear joint axis (x = 0), bed at z = 0.
// `stub_d` grows the pin stubs (the negative controls' oversized pin).
// `tab_rear`/`tab_front` add the M4 mounting plates (link 1 / link N only).
// Every internal joint overlaps volumetrically — face-only contacts export
// as coincident-facet non-manifold shells (found the hard way, iter 0).
module link(tab_rear = false, tab_front = false, stub_d = pin_d) {
    // Ear: the rear clevis, one per side. Main box from under the bore up
    // into the roof plate; low web down into the floor plate (stepped rear
    // faces to clear the previous link's swept plate corner — see header).
    // Bore is the blind cut from the ear's inner face.
    for (sy = [-1, 1])
        difference() {
            union() {
                // main box, extruded along Y from an (x,z) profile so its
                // REAR-TOP corner carries a chamfer: the sharp corner sweeps
                // into the previous link's ear-nose front face past ~42 deg
                // (measured 0.9 mm^3 per ear at 44 deg); the chamfer keeps
                // the ear's worst radius inside the nose face's own minimum.
                translate([0, sy > 0 ? ear_y_in + ear_t : -ear_y_in, 0])
                    rotate([90, 0, 0])   // profile u->x, v->z, extrudes -Y
                        linear_extrude(ear_t)
                            polygon([[-ear_back, ear_main_z0],
                                     [-ear_back, ear_z1 - style_edge_chamfer],
                                     [-ear_back + style_edge_chamfer, ear_z1],
                                     [ear_nose, ear_z1],
                                     [ear_nose, ear_main_z0]]);
                translate([ear_low_x0, sy < 0 ? -ear_y_out : ear_y_in, ear_low_z0])
                    cube([ear_low_x0 * -1 + ear_nose, ear_t, ear_low_z1 - ear_low_z0]);
            }
            // Both sides extrude -Y (profile roof stays +Z); the origin sits
            // at the bore floor on +Y, 0.01 outside the inner face on -Y —
            // a sy*-mirrored rotation would flip the teardrop roof down.
            translate([0, sy > 0 ? ear_y_in + bore_d : -(ear_y_in - 0.01), z_pin])
                bore_cutter();
        }
    // Pocket roof and floor plates, full width (they are the tunnel AND the
    // ear cheeks AND the end stops). Their inner faces are the ±stop_angle
    // stops — the previous link's lug-tip corners land ON them, ~0.5 mm in
    // from the rear edge. Both LANDING faces must be FLAT: the roof vaults
    // only the passage's center (|y| < 6) and chamfers its TOP (outer) face
    // only, and the floor plate is a PLAIN slab — a top chamfer there would
    // slope the landing zone (the chamfer band reaches 1 mm in from the rear
    // edge; the landing sits at lug_tip·cos45° − lug_hz·sin45° − plate_x0
    // ≈ 0.47 mm in). The floor plate's bottom is bed contact, exactly flat.
    // The floor's rear extension carries the cable floor toward the joint
    // mouth as far as the sweep allows (floor_ext_x0): past that its
    // bed-level rear corner rides onto the previous plate's front-top corner
    // on the down-bend. Under the ears the low web reaches further back —
    // its rear corner sits higher, on a smaller radius, and clears.
    translate([plate_x0, -plate_w / 2, 0])
        cube([plate_x1 - plate_x0, plate_w, wall]);
    translate([floor_ext_x0, -plate_w / 2, 0])
        cube([plate_x0 + 0.2 - floor_ext_x0, plate_w, wall]);
    difference() {
        union() {
            chamfered_slab(plate_x0, plate_x1, wall + passage_h, wall, true);
            roof_ridge();
        }
        vault_void();
    }
    // Lug arm: the wall band continued forward — a short post (arm_x0 to the
    // plate front edge, full height: ties floor + roof + lug together) and
    // the lug bar itself (reduced height, running to the tip whose corners
    // are the stop faces — left SHARP, the derivation depends on them).
    for (sy = [-1, 1]) {
        translate([arm_x0, sy < 0 ? -lug_y_out : lug_y_in, wall - 0.6])
            cube([arm_x1b - arm_x0, wall, passage_h + 1.2]);
        translate([arm_x0, sy < 0 ? -lug_y_out : lug_y_in, z_pin - lug_hz])
            cube([pitch + lug_tip - arm_x0, wall, 2 * lug_hz]);
    }
    // Pin stubs: round cylinders from inside the lug out through the side
    // gap into the ears' blind bores, on the joint axis so relative
    // rotation never moves them.
    for (sy = [-1, 1])
        translate([pitch, sy * stub_y_out, z_pin])
            rotate([90 * sy, 0, 0]) cylinder(d = stub_d, h = stub_len);
    // Mounting tabs: flat bed-level plates with an M4 hole, ends only. The
    // front tab stops short of the next link's ear low web (x = pitch-1).
    if (tab_rear)
        difference() {
            chamfered_slab(-8, plate_x0, 0, wall, true);
            translate([-4, 0, -0.01]) screw_hole("M4", l = wall + 0.02);
        }
    if (tab_front)
        difference() {
            chamfered_slab(plate_x1 - 1, pitch + ear_low_x0 - 0.4, 0, wall, true);
            translate([(plate_x1 + pitch + ear_low_x0 - 0.4) / 2, 0, -0.01])
                screw_hole("M4", l = wall + 0.02);
        }
    // Roof fins: twin proud ribs at the style's tokens (crest 1, flanks 45°
    // by rise = run), one period per link on each flat band of the plate's
    // top. They flank the vault ridge (which is itself the big center rib)
    // — one full-width fin would bury itself in the ridge. Extruded -Y,
    // profile up, sunk 0.3 into the plate.
    rib_x = (plate_x0 + plate_x1) / 2 - style_rib_depth - style_rib_crest / 2;
    rib_half = plate_w / 2 - style_edge_chamfer - 0.5;
    rib_len = rib_half - (passage_w / 2 + 0.6);   // ridge foot + 0.6 clear
    for (sy = [-1, 1])
        translate([rib_x, sy < 0 ? -(passage_w / 2 + 0.6) : rib_half,
                  wall + passage_h + wall - 0.3])
            rotate([90, 0, 0])   // extrude -Y, profile up
                linear_extrude(rib_len)
                    polygon([[0, -0.3],
                             [0, 0],
                             [style_rib_depth, style_rib_depth],
                             [style_rib_depth + style_rib_crest, style_rib_depth],
                             [2 * style_rib_depth + style_rib_crest, 0],
                             [2 * style_rib_depth + style_rib_crest, -0.3]]);
}

// The straight printed run.
module run(stub_d = pin_d) {
    for (i = [0 : links - 1])
        translate([i * pitch, 0, 0])
            link(tab_rear = end_tabs && i == 0,
                 tab_front = end_tabs && i == links - 1,
                 stub_d = stub_d);
}

// Links j..N-1 rotated `a` degrees about joint j's pin axis (at
// x = j*pitch, z = z_pin) — the pose the fitcheck checks sweep through.
module bend_from(j, a) {
    translate([j * pitch, 0, z_pin])
        rotate([0, -a, 0])
            translate([-j * pitch, 0, -z_pin])
                for (i = [j : links - 1])
                    translate([i * pitch, 0, 0])
                        link(tab_rear = end_tabs && i == 0,
                             tab_front = end_tabs && i == links - 1);
}

module main() {
    assert(links >= 2, "a chain needs at least two links");
    assert(clear_xy >= 0.25,
           "clear_xy under 0.25 mm welds at typical layer heights (pip_hinge's floor)");
    assert(clear_z >= clear_xy, "clear_z must not undercut clear_xy");
    assert(abs(clear_z / layer_h - round(clear_z / layer_h)) < 1e-9,
           "clear_z must land on whole layers — derive it, don't hand-edit it");
    assert(axial_gap >= 0.5,
           "axial gap under one extrusion width — the stub end welds to the cup floor");
    assert(side_gap >= 0.25, "side_gap under 0.25 mm welds lug to ear");
    assert(2 * lug_hz < passage_h, "lug taller than the passage — it cannot swing");
    assert(lug_tip > 0, "lug_hz too tall for the stop derivation — lower it");
    assert(stop_angle > 0 && stop_angle <= 60, "stop_angle out of range");
    assert(bore_d > pin_d / 2, "blind bore too shallow to capture the stub");
    assert(stub_len > 1, "axial_gap leaves no stub length");
    assert(plate_x0 > 0, "plate rear edge crossed the joint axis — derivation broken");
    assert(plate_x1 > plate_x0 + 1, "pocket plates degenerate");
    assert(lug_tip < plate_x1, "lug tip pokes past the pocket front edge");
    assert(lug_tip * cos(stop_angle + 2) - lug_hz * sin(stop_angle + 2)
               > plate_x0 + 0.15,
           "lug corner exits the plate rear face before stop_angle+2 — the stop window is too short (lower plate_x0)");
    assert(arm_x0 > 0 && arm_x1b > arm_x0 + 1, "lug arm degenerate");
    assert(sqrt(pow(ear_back, 2) + pow(ear_z1 - z_pin, 2))
               < sqrt(pow(plate_back, 2) + pow(passage_h / 2, 2)) - 0.3,
           "ear rear-top corner sweeps into the previous roof plate's front edge (D7)");
    assert(ear_nose > bore_circ + 2, "ear nose leaves no front wall around the bore");
    assert(pitch + floor_ext_x0 * cos(stop_angle) - z_pin * sin(stop_angle)
               > plate_x1 + 0.15,
           "floor extension's rear-bottom corner sweeps into the previous floor plate on the down-bend");
    assert(sqrt(pow(ear_back - style_edge_chamfer, 2) + pow(ear_z1 - z_pin, 2))
               < sqrt(pow(pitch - ear_nose, 2) + pow(ear_main_z0 - z_pin, 2)) - 0.15,
           "ear rear-top corner sweeps into the previous link's ear nose (chamfer too small)");
    assert(ridge_x0 > plate_x0 && plate_x1 - ridge_x0 > 3,
           "vault ridge span degenerate — the ceiling would open or the ridge vanish");

    if (part == "fitcheck") {
        // every adjacent pair at the print pose must clear — zero facets
        for (i = [0 : links - 2])
            intersection() {
                translate([i * pitch, 0, 0]) link();
                translate([(i + 1) * pitch, 0, 0]) link();
            }
    } else if (part == "fitcheck_neg") {
        // an oversized stub in link 0 MUST overlap link 1's ears — proves
        // the interference check can fail (the weld this gate exists to see)
        intersection() {
            translate([0, 0, 0]) link(stub_d = pin_d + 2 * clear_xy + 1);
            translate([pitch, 0, 0]) link();
        }
    } else if (part == "pose_up44") {
        // articulation measured, not posed: 1° short of the stop must clear
        intersection() { link(); bend_from(1, stop_angle - 1); }
    } else if (part == "pose_dn44") {
        intersection() { link(); bend_from(1, -(stop_angle - 1)); }
    } else if (part == "stop_up47") {
        // 2° past the stop MUST overlap — the printed stop blocks it
        intersection() { link(); bend_from(1, stop_angle + 2); }
    } else if (part == "stop_dn47") {
        intersection() { link(); bend_from(1, -(stop_angle + 2)); }
    } else if (part == "fused") {
        // ci.fusecheck's known-fused control: oversized stubs weld every
        // joint, the whole run renders as ONE body
        run(stub_d = pin_d + 2 * clear_xy + 1);
    } else if (demo_bend > 0) {
        link();                 // preview pose: joint 1 bent, the rest straight
        bend_from(1, demo_bend);
    } else {
        run();                  // the printed artifact
    }
}

main();
