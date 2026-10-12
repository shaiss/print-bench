// cross-axis-flexure-pivot — a desk-scale compliant hinge: two slender beams
// cross at mid-span and weld at the crossing, so the stage rotates about a
// NEAR-FIXED VIRTUAL CENTER — the pinless hinge that, unlike a single
// small-length flexural pivot, does not wander under light load. Tier-2
// technique reference for docs/advanced-techniques.md Domain 1 (flexure
// joint families): the catalog had the SLFP (snap-cantilever-clip), the LET
// panel and the bistable arch, but not the cross-axis row — "good in
// tension, WEAK IN COMPRESSION, near-fixed virtual center".
//
// Dimensioned from the WELDED geometry, not the unwelded leaf ideal:
//
//   I = w*t^3 / 12              second moment of area (mm^4)
//   K = 8*E*I / L               pivot stiffness (N*mm/rad): the weld pins the
//                               crossing (no lateral drift), so each strip is
//                               two half-beams of length L/2 in an S-bend,
//                               four half-beams in parallel → 8·EI/L
//   sigma_weld = 2*E*t*θ/L      peak bending stress at the weld under that
//                               pinned S-bend (M_weld = 4·EI·θ/L); the pure-
//                               moment leaf σ = E·t·θ/(2L) is ~4× lower and
//                               describes beams that cross WITHOUT touching
//
// and CC1 (orientation), the reason this prints flat: the whole silhouette
// lives in the XY (bed) plane and is extruded up in Z to `w`, so every beam
// bends IN the layer plane — bending stress runs across the roads inside a
// layer, never across the bond between layers. Upright beams are out of
// scope (brief: "orientation is the product").
//
// Mechanism: a rigid frame arc and a rigid stage arc share one center (the
// virtual center at the origin, left open — neither body covers it). Two
// beams at ±alpha span the `L` between the arcs' inner faces, weld to each
// where they cross, and root into the arcs. The arcs' end faces are the hard
// stops: the stage arc's face meets the frame arc's face exactly at
// ±stop_angle, face to face over the full ring wall, so the brief's
// "overload in compression" demo bends the beams, not the stops. Requirements,
// derivations and the tune order: NOTES.md. All dimensions in millimeters.

/* [Flexure - the crossed beams] */
// Beam thickness t (mm) — the highest-leverage knob: stiffness ~ t^3, root
// stress ~ t. Production floor 0.8 (2 extrusion widths); the coupon strip
// deliberately sweeps below it to show why.
t = 0.8;
// Beam free span L (mm) — root-to-root along each strip, between the arcs'
// inner faces. Longer = lower stress for the same angle (strain ~ 1/L).
L = 28;
// Beam width = part height (mm). Multi-perimeter so one bad road does not
// kill the beam; root stress does not depend on it.
w = 8;
// Root fillet (mm) — doc fatigue rule r >= 0.5*t. Applied at the eight ring
// roots AND the four re-entrant weld corners (the highest-moment real estate).
root_fillet = 0.6;
// Crossing half-angle (deg) — each strip is inclined ±alpha to the frame↔
// stage axis and the two weld where they cross. 45 is the classic symmetric
// cross; it puts all four roots at the same radius.
alpha = 45;
// Assumed Young's modulus (MPa) — design datum for the echoes below, a
// literature-ish PETG default, NOT a measured filament. The coupon is the
// truth (NOTES.md, "Print this first").
E = 2000;

/* [Frame, stage & hard stops] */
// Hard-stop angle (deg) — the stage arc's end face meets the frame arc's end
// face exactly here, both sides. The brief's ROM target; raise toward 60 only
// if a PETG coupon survives (root stress scales linearly).
stop_angle = 40;
// Ring wall (mm) — radial thickness of the frame/stage arcs. Rigid by
// design: all compliance belongs in the beams.
arc_wall = 6.5;
// Finger tab length × width (mm) and corner radius — the handle you twist,
// and its mirror on the frame (the part you hold).
tab_len = 10;
tab_w = 22;
tab_r = 4;
// Raised finger-pad height (mm) on the stage tab — marks the side that
// moves and lifts the fingertip clear of the bed. 0 disables.
h_pad = 4;

/* [Quality] */
// Production tessellation for the arcs and fillet arcs. Previews and the
// gated STL both use this value (no per-export override).
$fn = 64;

// ---- derived -----------------------------------------------------------
r_in     = L / 2;                    // arcs' inner faces = the free-span ends
r_out    = r_in + arc_wall;          // arcs' outer radius
arc_half = (180 - stop_angle) / 2;   // each arc's half-width: face-to-face
                                     // contact lands exactly at stop_angle
land     = arc_wall - 0.5;           // beam root buried inside the ring band
tab_cx   = r_out + tab_len / 2;      // finger-tab center radius (25.5 stock)
theta    = stop_angle * PI / 180;    // ROM in rad
I        = w * t * t * t / 12;       // second moment of area (mm^4)
// Welded (pinned-crossing) model — see header. The leaf formulas below are
// kept as the unwelded reference so a reader can see the ~4× gap.
K          = 8 * E * I / L;            // pivot stiffness (N*mm/rad)
sigma_weld = 2 * E * t * theta / L;    // peak at weld, pinned S-bend
sigma_leaf = E * t * theta / (2 * L);  // pure-moment leaf (unwelded ideal)
F_handle   = K * theta / tab_cx;       // fingertip force at the tab (N)

// fitcheck pocket probes: the four open pockets flanking the crossing, on
// the ±x/±y bisectors. A probe is valid while it stays clear of both beams.
probe_d  = 0.6 * r_in;
probe_r  = 1.5;
probe_pts = [[probe_d, 0], [0, probe_d], [-probe_d, 0], [0, -probe_d]];

echo(str("cross-pivot: K ~= ", K, " N*mm/rad at +/-", stop_angle,
         " deg  (welded / pinned-crossing: 8*E*I/L, I = ", I, " mm^4, E = ",
         E, " MPa assumed)"));
echo(str("weld stress at +/-", stop_angle, " deg: ", sigma_weld,
         " MPa (pinned S-bend) — leaf ideal would be ", sigma_leaf,
         " MPa; cycle the pivot itself for the weld, not only the coupon"));
echo(str("fingertip force at r = ", tab_cx, " mm: ", F_handle,
         " N — firm at desk scale under the welded model"));
if (t < 0.8)
    echo(str("WARNING: t = ", t, " is under the 0.8 mm production floor ",
             "(2 extrusion widths) — fine for a deliberate coupon row, ",
             "not for the pivot"));

module checks() {
    assert(t >= 0.5, "t under 0.5 mm will not extrude at all");
    assert(root_fillet >= 0.5 * t,
           "root fillet below 0.5*t — ring roots and weld corners are crack starters");
    assert(w >= 2.4, "beam width under 3 perimeters (2.4 mm) — one bad road kills the beam");
    assert(alpha > 10 && alpha < 80, "crossing half-angle outside 10-80 deg");
    assert(stop_angle > 5 && stop_angle < 80, "hard-stop angle outside 5-80 deg");
    assert(arc_wall >= 1.6, "ring wall under 1.6 mm — the arcs must be rigid, not a second flexure");
    // the arcs must cover both beam roots with land to spare
    assert(arc_half >= alpha + 6,
           "arc half-width does not cover the beam roots — lower stop_angle or alpha");
    // the buried beam end must stay inside the ring's outer face
    assert(pow(r_in + land, 2) + pow(t / 2, 2) < pow(r_out - 0.2, 2),
           "beam end pokes through the ring's outer face");
    // fitcheck probes must sit in open pocket, clear of both beams AND of
    // the weld-corner fillets that grow outward along the same bisectors
    assert(probe_d * sin(alpha) - t / 2 >= probe_r + 0.5,
           "pocket probes no longer clear the beams — move them or shrink probe_r");
    assert(probe_d - (t / 2) / sin(alpha) - max(root_fillet, 0.5 * t) >= probe_r + 0.5,
           "pocket probes collide with weld fillets — move them or shrink fillet/probe");
    // coupon guards
    assert(min(coupon_ts) >= 0.5, "coupon rows under 0.5 mm will not extrude");
    assert(max(coupon_ts) <= 1.6, "coupon rows over 1.6 mm stop being a flexure ladder");
}

// ---- 2D primitives (the whole part is one bed-plane silhouette) --------
module rounded2d(len, wid, r)   // convex-corner-rounded rectangle
    offset(r = r) offset(delta = -r) square([len, wid], center = true);

// annular band r_in..r_out over [-arc_half, +arc_half]. The wedge that cuts
// the band is a quad with a mid-radius point so its chord edges stay outside
// r_out at every arc_half this file allows.
module ring_arc_2d() {
    rb = r_out + 10;
    intersection() {
        difference() { circle(r_out); circle(r_in); }
        polygon([[0, 0],
                 [rb * cos(-arc_half), rb * sin(-arc_half)],
                 [rb, 0],
                 [rb * cos(arc_half), rb * sin(arc_half)]]);
    }
}

// the two strips, welded where they cross at the virtual center
module beams_2d()
    for (a = [alpha, -alpha])
        rotate([0, 0, a]) square([2 * (r_in + land), t], center = true);

// canonical root fillet: concave corner at the origin, rigid material at
// x >= 0 (the ring face), beam material at y <= 0 (the flank). The piece
// lives in x [-f,0] x y [0,f] outside the quarter-disc — the same
// corner-piece-outside-the-disc construction snap-cantilever-clip uses
// (the disc-intersection variant touches at tangent points and never welds).
module root_fillet_2d(f)
    difference() {
        translate([-f, 0]) square([f, f]);
        translate([-f, f]) circle(f);
    }

// four corners of one strip: e picks the end, s the flank; the flips must
// COMPOSE (nested single-axis mirrors) — a combined mirror([1,1]) is a
// reflection about y = -x, which the canonical piece is symmetric under, so
// the double-flip corner silently got no fillet at all (measured off the
// export: 6/8 corners carried the r=0.6 arc, this one carried none). a is
// the strip's inclination (0 for the coupon's straight specimens).
module root_fillets_at_2d(span, tt, a)
    for (e = [1, -1], s = [1, -1])
        rotate([0, 0, a])
            translate([e * span, s * tt / 2])
                mirror([e < 0 ? 1 : 0, 0])
                    mirror([0, s < 0 ? 1 : 0])
                        root_fillet_2d(max(root_fillet, 0.5 * tt));

// all eight on the pivot: 2 strips x 2 ends x 2 flanks
module root_fillets_2d(span, tt)
    for (a = [alpha, -alpha]) root_fillets_at_2d(span, tt, a);

// One fillet filling a concave notch of air-angle `psi` (deg). Local frame:
// corner at the origin, notch bisector along +x, walls at ±psi/2 from +x.
// Same square-minus-disc discipline as root_fillet_2d (shares a full edge
// with each wall) — generalized past the 90° case so the acute and obtuse
// weld notches (psi = 2*alpha and 180-2*alpha) both get r ≥ 0.5·t.
module notch_fillet_2d(f, psi) {
    hw = psi / 2;
    d  = f / sin(hw);       // corner → arc center along the bisector
    tl = f / tan(hw);       // corner → tangent point along each wall
    // CCW winding (OpenSCAD drops a clockwise polygon as empty area).
    difference() {
        polygon([[0, 0],
                 [tl * cos(hw), -tl * sin(hw)],
                 [tl * cos(hw),  tl * sin(hw)]]);
        translate([d, 0]) circle(f);
    }
}

// Four re-entrant corners of the welded X. Corners sit on the angle
// bisectors (the ±x / ±y axes) at distance (t/2)/sin(alpha) from the
// origin; x-bisector notches have air angle 2*alpha, y-bisector notches
// have 180-2*alpha. Same fatigue rule as the ring roots.
module weld_fillets_2d() {
    f = max(root_fillet, 0.5 * t);
    r_c = (t / 2) / sin(alpha);
    for (a = [0, 180])
        rotate([0, 0, a])
            translate([r_c, 0])
                notch_fillet_2d(f, 2 * alpha);
    for (a = [90, 270])
        rotate([0, 0, a])
            translate([r_c, 0])
                notch_fillet_2d(f, 180 - 2 * alpha);
}

// spine/arm: a capsule from inside the ring band out under the tab. Both
// circles stay inside the band radially (no lobe past the ring's outer
// face) and the far end stays inside the tab (no nub past its edge).
module arm_2d()
    hull() {
        translate([r_in + 3, 0]) circle(2);
        translate([tab_cx - 4, 0]) circle(2);
    }

module frame_2d()
    union() {
        rotate([0, 0, 180]) ring_arc_2d();
        mirror([1, 0]) arm_2d();                  // spine out to the grip tab
        translate([-tab_cx, 0]) rounded2d(tab_len, tab_w, tab_r);
    }

module stage_tab_2d()
    translate([tab_cx, 0]) rounded2d(tab_len, tab_w, tab_r);

module stage_2d()
    union() {
        ring_arc_2d();
        arm_2d();                                 // handle arm out to the tab
        stage_tab_2d();
    }

module pivot_2d()
    union() {
        frame_2d();
        beams_2d();
        root_fillets_2d(r_in, t);
        weld_fillets_2d();
        stage_2d();
    }

// ---- the coupon: flexure fatigue ladder --------------------------------
// Print this first (NOTES.md has the protocol): a strip of single-beam
// specimens straight from the production dimensions — the t ladder
// (coupon_ts) plus two IDENTICAL production-t twins, one to print in PETG
// and one in PLA, so the material ranking is measured, not assumed.
// SCOPE: the coupon qualifies a STRAIGHT beam (t ladder + material twin).
// It has no crossing and no weld — the pivot's highest-stress junction is
// absent. Cycle the production pivot itself for the welded X; use the
// coupon to pick t and filament before that print.
coupon_ts = [0.6, 0.8, 1.0];
// pitch >= specimen length (L + 2*tab_len) + clearance, or adjacent grips
// fuse and the ladder prints as one untestable lump
coupon_pitch_x = L + 2 * tab_len + 4;
coupon_pitch_y = tab_w + 6;

module coupon_specimen_2d(tt)
    union() {
        square([L, tt], center = true);
        root_fillets_at_2d(L / 2, tt, 0);         // straight specimens
        for (s = [1, -1])
            translate([s * (L / 2 + tab_len / 2), 0])
                rounded2d(tab_len, tab_w, tab_r);
    }

module coupon_specimen(tt, label, pos) {
    translate(pos) {
        linear_extrude(w) coupon_specimen_2d(tt);
        // embossed label on the +x grip, raised so it survives handling.
        // Label size caps at what the pad fits: a glyph runs ~0.9*size wide
        // (measured off the export — "PETG" at size 3 spanned 10.6 mm), so a
        // fixed size 3 hung 0.3 mm of the 4-glyph "PETG" past each pad edge
        // into mid-air. 1 mm total margin.
        translate([L / 2 + tab_len / 2, 0, w])
            linear_extrude(0.6)
                text(label, size = min(3, (tab_len - 1) / (0.9 * len(label))),
                     halign = "center", valign = "center");
    }
}

// ladder labels keep one decimal: str(1.0) is "1", which reads as a typo
// next to 0.6 and 0.8
function fmt_t(tt) = str(tt, tt == floor(tt) ? ".0" : "");

module coupon_strip() {
    n = len(coupon_ts);
    for (i = [0 : n - 1])
        coupon_specimen(coupon_ts[i], fmt_t(coupon_ts[i]),
                        [(i % 3) * coupon_pitch_x,
                         floor(i / 3) * coupon_pitch_y, 0]);
    // the PLA / PETG pair: identical production-t geometry, different filament
    coupon_specimen(t, "PETG",
                    [(n % 3) * coupon_pitch_x, floor(n / 3) * coupon_pitch_y, 0]);
    coupon_specimen(t, "PLA",
                    [((n + 1) % 3) * coupon_pitch_x,
                     floor((n + 1) / 3) * coupon_pitch_y, 0]);
}

// ---- dispatch ----------------------------------------------------------
// "" = the pivot. "coupon" = the print-this-first strip. "fitcheck" = the
// check that catches a fused-solid bug (ci.fitchecks): the rigid bodies'
// overlap at rest (must be EMPTY — they meet only through the flexures) plus
// pocket probes through the part (must be EMPTY — the four pockets flanking
// the crossing stay open). "fitcheck_neg" = the stage driven 5 deg PAST the
// hard stop (must INTERFERE — the stops bite, and the check can fail).
// "fitcheck_stop_lo"/"_hi" = the ROM bound itself: 0.5 deg inside the stop
// must clear and 0.5 deg past it must interfere, so the exported ROM is
// measured at stop_angle ± 0.5 deg, not asserted.
part = "";

module main() {
    checks();

    if (part == "coupon")
        coupon_strip();
    else if (part == "fitcheck")
        linear_extrude(w)
            union() {
                intersection() { frame_2d(); stage_2d(); }
                intersection() {
                    pivot_2d();
                    for (p = probe_pts) translate(p) circle(probe_r);
                }
            }
    else if (part == "fitcheck_neg")
        linear_extrude(w)
            intersection() { frame_2d(); rotate([0, 0, stop_angle + 5]) stage_2d(); }
    else if (part == "fitcheck_stop_lo")
        // ROM measured bound, − side: half a degree INSIDE the stop must
        // still clear — the arcs have not touched yet
        linear_extrude(w)
            intersection() { frame_2d(); rotate([0, 0, -(stop_angle - 0.5)]) stage_2d(); }
    else if (part == "fitcheck_stop_hi")
        // ROM measured bound, + side: half a degree PAST it must interfere —
        // so the export's ROM is stop_angle +/- 0.5 deg, not "about 40"
        linear_extrude(w)
            intersection() { frame_2d(); rotate([0, 0, stop_angle + 0.5]) stage_2d(); }
    else if (part == "") {
        linear_extrude(w) pivot_2d();
        if (h_pad > 0) translate([0, 0, w]) linear_extrude(h_pad) stage_tab_2d();
    } else
        assert(false, str("unknown part: ", part));
}

main();
