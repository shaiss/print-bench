// perspective-coin — a two-sided pocket coin of John Cena's watch engravings:
// "COMPARISON IS THE THIEF OF JOY" on one face (for when you feel you are not
// enough) and "MEMENTO MORI" on the other (for when your head gets too big).
// A keeper of perspective, not time.
//
// Two printable parts:
//   - `coin`     the bare two-sided coin: reeded edge, chamfered rims, both
//                faces engraved. Prints flat, no supports.
//   - `flipper`  (default render) the same coin captured PRINT-IN-PLACE in a
//                keyring gimbal: diamond-section stub axles on the coin ride
//                in teardrop sockets in the ring, so you flip the coin to the
//                reminder you need. One piece, no supports, no assembly.
//
// Print-in-place mechanics (see docs/advanced-techniques.md Domain 3):
//   - The axle cross-section is a 45-degree diamond, so the axle's own
//     overhang self-supports and its four vertices give the socket a light
//     line contact (low break-free torque, free spin).
//   - The socket is a TEARDROP bore (round bottom bowl, 45-degree roof), the
//     support-free horizontal-hole primitive, so the pocket roof never
//     bridges. Socket radius = axle vertex radius + `pivot_clear` — one
//     tuned radial clearance, printed horizontally, so it wants ~0.35 mm
//     (looser than a vertical-wall fit; tune on the coupon).
//   - The coin sits on the bed inside the ring with a huge radial moat
//     (`rim_gap`), so the only fused interface after printing is the
//     axle/socket annulus: a firm first flip shears it (break-free motion,
//     expected, not a defect).
//   - The two faces are engraved in coin-flip alignment about the pivot
//     axis: flip the charm end over end and the back face reads upright.
//
// All dimensions in millimeters.

/* [Coin] */
// Coin diameter (mm)
coin_d = 40;
// Coin thickness (mm) — also sets the pivot height (axles at half thickness)
coin_t = 5;
// 45-degree chamfer on both face rims (mm)
edge_chamfer = 0.8;
// Reeded-edge groove count (0 disables the reeding)
reed_n = 64;
// Reed groove depth into the edge (mm)
reed_depth = 0.4;
// Reed groove width (mm)
reed_w = 0.9;
// Half-angle around each pivot kept clear of reeds (deg) — protects axle roots
reed_skip = 14;

/* [Engraving] */
// Engrave the faces (coupon turns this off — the text doesn't scale down)
engrave = true;
// Engraving depth (mm) — 3 layers at 0.2; readable on the bed face too
engrave_depth = 0.6;
// Morphological closing radius on the face art (mm): acute letter crotches
// (inside N, M, V…) taper to a zero-width material wedge by typographic
// construction; closing truncates every such wedge at ~2x this width so no
// engraved land falls under a printable width. Also softens convex glyph
// corners the same way real die-stamped text is
engrave_relief = 0.25;
// Font for the legends (must be installed; Liberation ships with the repo CI)
font = "Liberation Sans:style=Bold";

/* [Flip ring] */
// Radial moat between coin edge and ring bore (mm) — big, so it never fuses
rim_gap = 1.5;
// Ring radial width (mm)
ring_w = 6;
// Ring height (mm) — must swallow the teardrop socket apex plus a roof
ring_t = 6;
// Keyring loop on the ring (the coupon keeps it — it makes a good handle)
loop = true;
// Keyring hole diameter (mm)
loop_hole_d = 4.5;

/* [Pivot — the tuned fit] */
// Axle vertex radius: half the diamond's corner-to-corner diagonal (mm)
axle_r = 1.5;
// Radial clearance, axle vertex to socket wall (mm) — TUNE ON THE COUPON.
// Horizontal-bore fit: sag-limited on the roof side, so looser than a
// vertical-wall 0.2. Fused after printing -> raise by 0.05; rattles -> lower.
pivot_clear = 0.35;
// How far each axle engages into its socket past the moat (mm)
socket_engage = 3.0;
// Axial clearance at the axle tip inside the pocket (mm)
socket_end_clear = 0.7;

/* [Display] */
// Present the coin MEMENTO MORI side up (display/product-shot only: same
// geometry, reoriented — the printable STL is unchanged either way)
flip_coin = false;

/* [Quality] */
// Iterating: 48. Production: 96 (the flip clearance is a swept circle).
$fn = 96;

// ---- derived -----------------------------------------------------------
// Chamfer HEIGHT runs 1.2x the radial bite: a 45.0-degree cone tessellates
// to facets fractionally past 45 and lights up overhang checks; ~40 degrees
// reads identical and stays safely self-supporting.
chamfer_rise = 1.2;
coin_r   = coin_d / 2;
bore_r   = coin_r + rim_gap;            // ring bore
ring_or  = bore_r + ring_w;             // ring outer radius
pivot_z  = coin_t / 2;                  // pivot axis height (coin mid-plane)
socket_r = axle_r + pivot_clear;        // teardrop bore radius
axle_len = rim_gap + socket_engage;     // axle beyond the coin edge
pocket_d = socket_engage + socket_end_clear;  // socket depth past the bore
// Radius the flipping coin actually sweeps (edge corner about the pivot axis)
flip_sweep_r = sqrt(coin_r * coin_r + pivot_z * pivot_z);

// ---- 2D artwork ---------------------------------------------------------

// One character per slot, fanned around the TOP of the coin: char i sits at
// angle a0 - i*dpc (0 deg = 12 o'clock, +CCW), baseline on radius r, glyph
// growing outward, upright along its local radial.
module arc_text_top(txt, r, size, dpc) {
    n = len(txt);
    for (i = [0 : n - 1])
        rotate([0, 0, (n - 1) * dpc / 2 - i * dpc])
            translate([0, r, 0])
                text(txt[i], size = size, font = font,
                     halign = "center", valign = "baseline");
}

// Fanned around the BOTTOM, reading left to right, glyphs growing inward
// from baseline radius r (so top and bottom legends share one annulus band).
module arc_text_bottom(txt, r, size, dpc) {
    n = len(txt);
    for (i = [0 : n - 1])
        rotate([0, 0, -(n - 1) * dpc / 2 + i * dpc])
            translate([0, -r, 0])
                text(txt[i], size = size, font = font,
                     halign = "center", valign = "baseline");
}

// Radiant sun — the JOY side emblem. Every filled region stays under
// ~2.5 mm across: when this face prints downward, each engraved void's roof
// is a bridge, and short spans keep the slicer's bridging happy.
module sun_2d() {
    difference() { circle(3.2); circle(2.0); }   // annulus, 1.2 stroke
    circle(0.8);                                 // core dot
    for (i = [0 : 11])
        rotate([0, 0, i * 30])
            polygon([[-1, 4.0], [1, 4.0], [0, i % 2 == 0 ? 8.8 : 6.8]]);
}

// Stylized hourglass — the MEMENTO MORI emblem. Bulbs are stroked outlines
// (not fills) for the same short-bridge reason as the sun.
module hourglass_2d() {
    // Bulb bases and both sand wedges OVERLAP the end bars: a near-touch
    // would leave a sub-nozzle sliver of face between two engraved voids.
    bulb = [[-3.9, 5.2], [3.9, 5.2], [0, 0.5]];
    for (m = [0, 1]) mirror([0, m, 0]) {
        translate([0, 5.6]) square([10.5, 1.5], center = true);  // end bar
        difference() { polygon(bulb); offset(delta = -1.1) polygon(bulb); }
    }
    polygon([[-1.4, 4.9], [1.4, 4.9], [0, 3.2]]);    // sand still up top…
    polygon([[-1.4, -4.9], [1.4, -4.9], [0, -3.2]]); // …and the pile below
}

// Small diamond marker at the two pivot positions — echoes the axle section.
module pivot_diamonds_2d(r) {
    for (a = [90, -90])
        rotate([0, 0, a]) translate([0, r, 0]) rotate([0, 0, 45])
            square(1.7, center = true);
}

// Face A — "COMPARISON / IS THE / THIEF OF JOY" around a radiant sun.
// Arc spacing rule of thumb: wide glyphs (M, W) graze their fanned
// neighbors when the slot arc at the baseline drops under ~3.5 mm, so each
// zone carries few enough characters to stay clear (measured: the original
// single 17-char top arc left 0.01 mm between O and M).
module face_a_2d() {
    arc_text_top("COMPARISON", 14.8, 3.6, 14.4);
    translate([0, -11.2]) text("IS THE", size = 2.6, font = font,
                               halign = "center", valign = "center",
                               spacing = 1.15);
    arc_text_bottom("THIEF OF JOY", 17.8, 3.5, 11.2);
    sun_2d();
    pivot_diamonds_2d(16.3);
}

// Face B — "MEMENTO MORI" around an hourglass.
module face_b_2d() {
    arc_text_top("MEMENTO", 14.6, 4.2, 17);
    arc_text_bottom("MORI", 17.8, 4.2, 17);
    hourglass_2d();
    pivot_diamonds_2d(16.3);
}

// ---- coin ---------------------------------------------------------------

module coin_blank() {
    ch = edge_chamfer * chamfer_rise;
    rotate_extrude()
        polygon([[0, 0],
                 [coin_r - edge_chamfer, 0],
                 [coin_r, ch],
                 [coin_r, coin_t - ch],
                 [coin_r - edge_chamfer, coin_t],
                 [0, coin_t]]);
}

// Vertical V-grooves around the edge, clamped to the straight band between
// the rim chamfers (a groove crossing the chamfer cone leaves paper-thin
// slivers). The sectors around each axle root stay smooth so the reeding
// never thins the axle attachment.
module reeds_cut() {
    // 0.6 land between groove ends and the chamfer cones — the chamfer
    // meets the edge cylinder at z = ch, so anything less leaves a
    // sub-nozzle shelf between groove top and rim.
    z_lo = edge_chamfer * chamfer_rise + 0.6;
    z_hi = coin_t - edge_chamfer * chamfer_rise - 0.6;
    for (i = [0 : reed_n - 1]) {
        a = i * 360 / reed_n;
        near_pivot = min(abs(a), abs(a - 180), abs(a - 360)) < reed_skip;
        if (!near_pivot)
            rotate([0, 0, a])
                translate([coin_r + reed_w / sqrt(2) - reed_depth, 0, z_lo])
                    rotate([0, 0, 45])
                        cube([reed_w, reed_w, z_hi - z_lo], center = false);
    }
}

// Engraving cutter for the TOP face (z = coin_t). The offset pair is the
// closing described at `engrave_relief` (dilate, then erode).
module top_face_cut() {
    translate([0, 0, coin_t - engrave_depth])
        linear_extrude(engrave_depth + 0.02)
            offset(r = -engrave_relief) offset(r = engrave_relief) children();
}

// Same cutter flipped onto the BOTTOM face by a 180-degree turn about the
// pivot (X) axis — so the two faces are in coin-flip alignment: flip the
// charm end over end and the back face reads upright.
module bottom_face_cut() {
    translate([0, 0, coin_t]) rotate([180, 0, 0]) top_face_cut() children();
}

module coin() {
    difference() {
        coin_blank();
        if (reed_n > 0) reeds_cut();
        if (engrave) {
            top_face_cut()    face_a_2d();
            bottom_face_cut() face_b_2d();
        }
    }
}

// ---- pivot & ring -------------------------------------------------------

// One diamond-section axle along +X, rooted 1 mm inside the coin edge.
module axle() {
    translate([coin_r - 1, 0, pivot_z])
        rotate([0, 90, 0])
            linear_extrude(axle_len + 1)
                rotate([0, 0, 45]) square(axle_r * sqrt(2), center = true);
}

// The captive body: coin plus both axles, tilted about the pivot axis
// (tilt only ever nonzero for the $t flip animation).
module rotor(tilt = 0) {
    translate([0, 0, pivot_z]) rotate([tilt, 0, 0]) translate([0, 0, -pivot_z]) {
        coin();
        axle();
        rotate([0, 0, 180]) axle();
    }
}

// Support-free horizontal bore section: round bowl, 45-degree roof to a point.
module teardrop_2d(r) {
    circle(r);
    polygon([[-r / sqrt(2), r / sqrt(2)], [0, r * sqrt(2)], [r / sqrt(2), r / sqrt(2)]]);
}

// Both socket pockets, cut into the ring bore. `clear` is overridable so the
// negative fitcheck can drive the socket into the axle.
module sockets_cut(clear = pivot_clear) {
    sr = axle_r + clear;
    for (a = [0, 180])
        rotate([0, 0, a])
            translate([bore_r - 0.5, 0, pivot_z])
                rotate([0, 90, 0])
                    linear_extrude(pocket_d + 0.5)
                        rotate([0, 0, 90]) teardrop_2d(sr);  // apex up
}

module ring_body() {
    oc = 0.8 * chamfer_rise;   // outer chamfer height
    bc = 0.5 * chamfer_rise;   // bore chamfer height
    rotate_extrude()
        polygon([[bore_r + 0.5, 0],
                 [ring_or - 0.8, 0],
                 [ring_or, oc],
                 [ring_or, ring_t - oc],
                 [ring_or - 0.8, ring_t],
                 [bore_r + 0.5, ring_t],
                 [bore_r, ring_t - bc],
                 [bore_r, bc]]);
}

// Cylinder with sub-45-degree rim chamfers (same chamfer_rise trick as the
// coin blank); hulled in pairs to form the loop tab.
module chamfered_disc(r, h, c) {
    ch = c * chamfer_rise;
    rotate_extrude()
        polygon([[0, 0], [r - c, 0], [r, ch], [r, h - ch], [r - c, h], [0, h]]);
}

module loop_tab() {
    tab_r = loop_hole_d / 2 + 2.2;
    difference() {
        hull() {
            translate([0, ring_or - 2, 0]) chamfered_disc(tab_r, ring_t, 0.8);
            translate([0, ring_or + 2.2, 0]) chamfered_disc(tab_r, ring_t, 0.8);
        }
        translate([0, ring_or + 2.2, -0.5])
            cylinder(d = loop_hole_d, h = ring_t + 1);
    }
}

module ring(clear = pivot_clear) {
    difference() {
        union() {
            ring_body();
            if (loop) loop_tab();
        }
        sockets_cut(clear);
    }
}

// ---- parts --------------------------------------------------------------

// "" / "flipper" = the print-in-place charm. "coin" = the bare coin.
// "cutaway" = the charm halved through the pivot axis (preview/QA only —
// shows the axle sitting in its teardrop socket). "fitcheck" = rotor ∩ ring
// (must render EMPTY — the rotor is a free captive body). "fitcheck_neg" =
// sockets shrunk into the axles (must be NON-EMPTY — proves the check can
// fail). See ci.fitchecks.
part = "";

module main() {
    assert(pivot_clear >= 0.25,
           "pivot_clear below a printable horizontal-bore clearance");
    assert(rim_gap >= 1.0, "rim moat small enough to fuse coin to ring");
    assert(pivot_z - socket_r >= 0.6,
           "socket bowl breaks through the ring underside — thicken coin_t");
    assert(ring_t - (pivot_z + socket_r * sqrt(2)) >= 0.6,
           "socket apex breaks through the ring top — raise ring_t");
    assert(socket_engage >= 2, "axle engagement too short to stay captive");
    assert(ring_w >= pocket_d + 1.2, "socket pocket breaks out of the ring OD");
    assert(bore_r >= flip_sweep_r + 0.8,
           "coin can't flip — its swept edge hits the ring bore");
    assert(engrave_depth <= coin_t / 4, "engraving deep enough to weaken the coin");
    assert(reed_n == 0 || coin_t - 2 * edge_chamfer * chamfer_rise - 0.3 >= 1,
           "no straight edge band left for the reeding — thicken coin_t");

    if (part == "coin") {
        if (flip_coin)
            translate([0, 0, coin_t]) rotate([180, 0, 0]) coin();
        else
            coin();
    }
    else if (part == "cutaway")
        difference() {
            union() { rotor(); ring(); }
            translate([-500, 0.01, -500]) cube(1000);  // keep the y<0 half
        }
    else if (part == "fitcheck")
        intersection() { rotor(); ring(); }
    else if (part == "fitcheck_neg")
        intersection() { rotor(); ring(clear = -0.5); }  // socket bites the axle
    else {
        // $t drives the flip GIF only; every static render has $t = 0, so the
        // gated STL is the as-printed resting pose.
        rotor(tilt = $t * 360);
        ring();
    }
}

main();
