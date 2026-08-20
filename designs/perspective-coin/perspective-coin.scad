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
// Radial moat between coin edge and ring bore (mm) — big, so it never fuses.
// v2: 1.5 -> 1.2. At 1.5 the bed-level chamfers opened the *apparent* gap to
// ~2.8 mm and the coin read small in its ring; 1.2 keeps every guard's margin
// (bore still clears the flip sweep by 0.34) while tightening the look.
rim_gap = 1.2;
// Bore first-layer inset (mm): anti-elephant-foot relief on the bore bottom
// edge. v2: 0.5 -> 0.3, part of narrowing the apparent moat; still ~1.5 layers
bore_bottom_inset = 0.3;
// Ring radial width (mm)
ring_w = 6;
// Ring height (mm) — must swallow the teardrop socket apex plus a roof
ring_t = 6;
// Keyring loop on the ring (the coupon keeps it — it makes a good handle)
loop = true;
// Keyring hole diameter (mm)
loop_hole_d = 4.5;
// Loop through-hole wrap thickness (mm): a top-side 45° counterbore thins the
// hole region to this so a split ring threads over ~3 mm, not the full ring_t.
// v2 fix — at 6 mm the coils had to pry over the whole ring height (issue: the
// tab was as thick as the ring; keyfobs keep it ~2-3 mm).
loop_thick = 3.0;
// Loop-tab clearance (mm): the tab's inner bulge sits this far OUTSIDE the ring
// bore, at every coin_d / loop_hole_d by construction (the derived placement
// below). Raise it if a manual edit ever trips the loop-tab asserts.
tab_bore_margin = 0.2;

/* [Pivot — the tuned fit] */
// Axle vertex radius: half the diamond's corner-to-corner diagonal (mm)
axle_r = 1.5;
// Radial clearance, axle vertex to socket wall (mm) — TUNE ON THE COUPON.
// Horizontal-bore fit: sag-limited on the roof side, so looser than a
// vertical-wall 0.2. Fused after printing -> raise by 0.05; rattles -> lower.
pivot_clear = 0.35;
// How far each axle engages into its socket past the moat (mm)
socket_engage = 3.0;
// Axial clearance at the axle tip inside the pocket (mm) — sets the ALONG-axis
// float, which is 2x this. v2: 0.7 -> 0.4 (float 1.4 -> 0.8 mm; the first print
// had perceptible end-play). This is a vertical-wall gap (tip face vs pocket
// end face, no first-layer squish), so 0.4 splits cleanly. NOT pivot_clear —
// that is the radial annulus and cannot change the axial rattle.
socket_end_clear = 0.4;

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

// Loop-tab placement, DERIVED so the tab can never intrude into the bore or the
// flip path (v2 fix). The old hardcoded inner-disc offset put the tab 0.45 mm
// inside the full-size bore, and 0.05 mm from the coupon coin — assert-legal,
// but the coupon fused and jammed and loop_hole_d silently narrowed the flip
// pad. Deriving the inner disc from the bore makes the tab's inner bulge sit a
// fixed margin OUTSIDE the bore at every coin_d and every loop_hole_d by
// construction: tab_reach = tab_inner_y - tab_r = bore_r + tab_bore_margin
// (the input `tab_bore_margin` lives in [Flip ring]), independent of
// loop_hole_d (tab_r cancels).
tab_r    = loop_hole_d / 2 + 2.2;        // loop tab disc radius
tab_inner_y = bore_r + tab_r + tab_bore_margin;
tab_outer_y = tab_inner_y + 4.2;         // loop length (hole sits here)
tab_reach   = tab_inner_y - tab_r;       // closest approach of tab to centre

// ---- 2D artwork ---------------------------------------------------------

// Proportional advance-width table (Liberation Sans Bold caps, ~em). Uniform
// degrees-per-char gives a narrow glyph the same angular slot as a wide one,
// so "MORI" fans out to "MOR I" and "COMPARISON" to "COMPAR I SON". Advancing
// each glyph by its own width instead makes the legends read as words. The
// space is widened so word gaps stay legible on the tight bottom arc.
legend_adv_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ .";
legend_adv = [.72,.72,.72,.72,.67,.61,.78,.72,.28,.56,.72,.61,.83,
              .72,.78,.67,.78,.72,.67,.61,.72,.67,.94,.67,.67,.61,.28,.62];
function _adv(c) = let(k = search(c, legend_adv_chars))
                       len(k) > 0 ? legend_adv[k[0]] : 0.6;
function _cum(v, i) = i <= 0 ? 0 : v[i - 1] + _cum(v, i - 1);  // prefix sum

// One character per proportional slot around the coin (0 deg = 12 o'clock).
// Every glyph's baseline sits on radius r, so the RADIAL extent is set by
// r + size (independent of `track`) while `track` scales only the angular
// spread — tune edge margin and letter-spacing separately. Top legends grow
// OUTWARD from r; bottom legends grow INWARD, so both share one annulus band.
module arc_legend(txt, r, size, track, top) {
    n = len(txt);
    adv = [for (i = [0 : n - 1]) _adv(txt[i]) * size * track];
    total = _cum(adv, n);
    for (i = [0 : n - 1]) {
        s = _cum(adv, i) + adv[i] / 2 - total / 2;   // arc-length to glyph mid
        a = s / r * 180 / PI;                         // -> degrees along the arc
        if (top)
            rotate([0, 0, -a]) translate([0, r, 0])
                text(txt[i], size = size, font = font,
                     halign = "center", valign = "baseline");
        else
            rotate([0, 0, a]) translate([0, -r, 0])
                text(txt[i], size = size, font = font,
                     halign = "center", valign = "baseline");
    }
}
module arc_text_top(txt, r, size, track = 1.0)    { arc_legend(txt, r, size, track, true);  }
module arc_text_bottom(txt, r, size, track = 1.0) { arc_legend(txt, r, size, track, false); }

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

// Stylized hourglass — the MEMENTO MORI emblem. v2 redesign: the v1 emblem
// read as a rune because end bar + outline + sand chevron merged into one void
// per bulb, leaving the "sand" as a floating negative island. Here the bowtie
// is a single bolder silhouette (two solid frame rails down the sides, apex to
// apex at the waist), the sand is one solid settled pile in the LOWER bulb, and
// a short stream tick falls through the waist — every filled region stays under
// the ~2.5 mm bed-face bridge budget, and the marks no longer overlap into mush.
module hourglass_2d() {
    hw = 4.6;    // bulb half-width at the bars
    by = 6.4;    // bar centre height
    // top and bottom end bars (solid, 1.6 mm tall < bridge budget)
    for (m = [0, 1]) mirror([0, m, 0])
        translate([0, by]) square([2 * hw + 2.2, 1.6], center = true);
    // the two side rails of the bowtie: each a thin quad from a bar corner to
    // the waist, giving the apex-to-apex hourglass silhouette without a big fill
    for (sx = [-1, 1]) for (m = [0, 1]) mirror([0, m, 0])
        polygon([[sx * hw, by - 0.8], [sx * (hw - 1.0), by - 0.8],
                 [sx * 0.35, 0.35],   [sx * 1.05, 0.35]]);
    // settled sand: one solid pile in the lower bulb (≤ 2.4 mm across)
    polygon([[-1.2, -4.9], [1.2, -4.9], [0, -3.0]]);
    // a grain still falling through the waist
    translate([0, -1.7]) square([0.9, 2.4], center = true);
}

// Small diamond marker at the two pivot positions — echoes the axle section.
module pivot_diamonds_2d(r) {
    for (a = [90, -90])
        rotate([0, 0, a]) translate([0, r, 0]) rotate([0, 0, 45])
            square(1.7, center = true);
}

// Face A — "COMPARISON / IS THE / THIEF OF JOY" around a radiant sun.
// v2.1 legends: proportional arc spacing (arc_legend) reads the words as
// words, and the TOP arc pulls in to r 14.0 so its outermost glyph lands at
// r ~17.8 — 1.4 mm off the rim bevel (v1/v2 sat 0.7 mm off). The BOTTOM arc
// keeps r 17.8 to preserve the IS THE clearance below.
module face_a_2d() {
    arc_text_top("COMPARISON", 14.0, 3.5, 1.34);
    // "IS THE": 3.2 mm, its row-corner at r ~13.9. THIEF stays at r 17.8 (its
    // inward glyph tops ~r 14.5) so this clearance holds at ~0.5 mm; the sun's
    // down-ray tip clears by ~2.3 mm (re-derive if you move either).
    translate([0, -10.7]) text("IS THE", size = 3.2, font = font,
                               halign = "center", valign = "center",
                               spacing = 1.0);
    arc_text_bottom("THIEF OF JOY", 17.8, 3.4, 1.42);
    sun_2d();
    pivot_diamonds_2d(16.3);
}

// Face B — "MEMENTO MORI" around an hourglass. v2.1: MEMENTO pulls in to
// r 13.9 (outermost glyph r ~17.5, ~1.7 mm off the bevel; v1/v2 sat 0.7 mm
// off), MORI to r 17.5; both proportionally spaced so "MORI" reads as a word.
module face_b_2d() {
    arc_text_top("MEMENTO", 13.9, 4.0, 1.28);
    arc_text_bottom("MORI", 17.5, 3.9, 1.35);
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
// (tilt only ever nonzero for the $t flip animation). `bare` draws the
// un-engraved blank — used by the swept-flip fitcheck, where the engraving and
// reeds are irrelevant (they only REMOVE material, so if the blank envelope
// clears the ring the real coin clears too) and skipping them keeps the
// multi-tilt CGAL intersection fast.
module rotor(tilt = 0, bare = false) {
    translate([0, 0, pivot_z]) rotate([tilt, 0, 0]) translate([0, 0, -pivot_z]) {
        if (bare) coin_blank(); else coin();
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
    oc = 0.8 * chamfer_rise;              // outer chamfer height
    bc = bore_bottom_inset * chamfer_rise; // bore first-layer inset height
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
    difference() {
        hull() {
            translate([0, tab_inner_y, 0]) chamfered_disc(tab_r, ring_t, 0.8);
            translate([0, tab_outer_y, 0]) chamfered_disc(tab_r, ring_t, 0.8);
        }
        // through-hole
        translate([0, tab_outer_y, -0.5])
            cylinder(d = loop_hole_d, h = ring_t + 1);
        // top-side 45° counterbore: thins the hole region to loop_thick so a
        // split ring threads over ~3 mm. Top-only keeps it support-free (a
        // bottom counterbore would leave an overhanging roof).
        cb_depth = ring_t - loop_thick;
        if (cb_depth > 0.1)
            translate([0, tab_outer_y, loop_thick])
                cylinder(r1 = loop_hole_d / 2, r2 = loop_hole_d / 2 + cb_depth,
                         h = cb_depth + 0.01);
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
// shows the axle sitting in its teardrop socket). "fitcheck" = rotor ∩ ring at
// REST (must render EMPTY). "fitcheck_neg" = sockets shrunk into the axles
// (must be NON-EMPTY). "fitcheck_flip" = rotor swept through the flip ∩ ring
// (must be EMPTY — proves the coin clears the bore AND the loop tab at every
// tilt, the check the rest-pose fitcheck and the bore assert could not make).
// "fitcheck_flip_neg" = an oversized coin flipped into the bore (must be
// NON-EMPTY — proves the swept check can fail). See ci.fitchecks.
part = "";

// Tilts sampled across the flip for the swept-flip fitcheck: small angles catch
// the coin grazing the loop tab at 12 o'clock, 90° catches the maximum radial
// excursion into the bore.
flip_tilts = [6, 15, 35, 60, 90];

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
    // Loop-tab guards (v2): the tab must never enter the coin's flip path or
    // the bore. Derived placement makes these true by construction, but the
    // asserts document the contract and catch a bad tab_bore_margin / manual
    // edit — the guard the old hardcoded tab silently lacked.
    assert(!loop || tab_reach >= flip_sweep_r + 0.8,
           "loop tab intrudes into the coin's flip path — raise tab_bore_margin");
    assert(!loop || tab_reach >= bore_r,
           "loop tab intrudes into the ring bore/moat — raise tab_bore_margin");
    assert(!loop || loop_thick <= ring_t && loop_thick >= 2,
           "loop_thick must be between 2 and ring_t");
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
    else if (part == "fitcheck_flip")
        // the real coin+axles swept through the flip must clear the ring and
        // the loop tab at every sampled tilt (bare blank = the outer envelope)
        for (t = flip_tilts) intersection() { rotor(tilt = t, bare = true); ring(); }
    else if (part == "fitcheck_flip_neg")
        // negative control: a coin one moat-width oversized cannot clear the
        // bore when flipped to 90° — proves the swept check detects a collision
        intersection() {
            translate([0, 0, pivot_z]) rotate([90, 0, 0]) translate([0, 0, -pivot_z])
                cylinder(r = bore_r + 1, h = coin_t);
            ring();
        }
    else {
        // $t drives the flip GIF only; every static render has $t = 0, so the
        // gated STL is the as-printed resting pose.
        rotor(tilt = $t * 360);
        ring();
    }
}

main();
