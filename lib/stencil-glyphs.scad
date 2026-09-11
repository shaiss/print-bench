// stencil-glyphs.scad — clean-room parametric stencil digits 0-9, in 2D.
// All dimensions in millimeters. Use from a design with:
//   use <stencil-glyphs.scad>
//
// WHAT IT IS
// A bold single-stroke numeral family in the spirit of crate stencils, built
// from primitives only — rounded-rectangle strokes (hull of circles), obround
// bowl rings (rounded rect minus its offset()) and annulus arcs — with no
// text() and no TTF anywhere. That is the point of the "clean-room": a text()
// glyph depends on whichever font the machine resolves, so the same .scad
// exports different geometry on a laptop and in CI, and a gate that passed
// here can fail there. These digits are pure geometry, identical everywhere.
//
// Every glyph is the STROKE minus BRIDGE BARS. A stencil digit that is cut
// through a shell leaves its counters (the holes in 0, 4, 6, 8, 9) as islands
// of shell with nothing holding them; the bridge bars are explicit gaps of
// width `bridge` across the stroke, one horizontal bar through the vertical
// centre of each counter, so the island stays tethered to the shell on both
// sides. Tethers are strokes of shell, so `bridge` has a printability floor:
// `bridge_min` (default 0.8 mm — two 0.4 mm extrusion widths). A design may
// RAISE bridge_min; the guard refuses lowering it below 0.8.
//
// DESIGN INTENT (issue #612 part 1)
// The ovodyo clock numerals: cut through a 2.2 mm shell at glyph_h ~14 mm
// with bridge 1.2 (stroke 0.22*h = 3.08 mm, digit advance 0.70*h = 9.8 mm,
// so "12" spans ~21.3 mm). stencil_text() lays out every value "00".."59"
// and "1".."12" (and a ':' glyph) centred on the origin, and
// stencil_text_width() lets the caller centre it and check it fits.
//
// PROOF, and where it lives
// The counter-tether proof is the plate render in stencil-glyphs-demo.scad:
// all ten digits plus "12", "05", "10", "00" cut THROUGH a thin plate,
// CGAL-rendered by check.sh, and the plate must stay ONE body (Volumes: 2 in
// OpenSCAD's summary — one solid, one outer void). An island that came loose
// would show as an extra volume. That is the library's regression test; the
// gate that makes it enforceable on a SLICED part — where a tether can still
// weld or vanish under a slicer's own rules — is the two-sided fusecheck of
// #612 part 2 (tools/printcheck + gate.sh), which counts separable bodies on
// the sliced STL and asserts exactly N.
//
// The same modules serve the POSITIVE use: linear_extrude a glyph and it is a
// raised numeral, bridge gaps included (the family's stencil identity), or
// pass bridged = false for an unbroken raised glyph — the bars are the only
// thing the flag removes.
//
// API (all 2D, all centred on the origin, all sizes mm)
//   stencil_digit(n, h, stroke = 0.22*h, bridge = 0.8, bridge_min = 0.8,
//                 bridged = true)
//       one digit n (integer 0-9) of cap height h. The glyph box is
//       stencil_glyph_width(n, h) wide (0.70*h, tabular: every digit has the
//       same advance, so "11" and "00" align on a clock) by h tall.
//   stencil_colon(h, stroke = 0.22*h)
//       the ':' glyph — two dots — in a 0.36*h box.
//   stencil_text(s, h, stroke = 0.22*h, spacing = 0.12*h, bridge = 0.8,
//                bridge_min = 0.8, bridged = true)
//       a string of digits, ':' and ' ' laid out left to right and centred
//       on the origin, `spacing` between glyph boxes.
//   stencil_text_width(s, h, spacing = 0.12*h)      -> total width, mm
//   stencil_glyph_width(c, h)                       -> one glyph's advance, mm
//
// GUARDS (every one has a refusing case in stencil-glyphs-guards.conf)
//   h > 0; stroke >= 0.8 (two extrusion widths) and <= 0.26*h (heavier closes
//   the counters); bridge_min >= 0.8; bridge >= bridge_min and <= 0.25*h;
//   n an integer 0-9; stencil_text refuses a non-string, an empty string and
//   any character outside digits/':'/' '.
//
// $fn is the caller's: nothing here is a fit, so the glyph follows the
// design's quality preset. Curves are circles of diameter `stroke` and
// bowls of radius ~0.3*h, so $fn >= 48 is plenty at h = 14.

// ---------------------------------------------------------------------------
// Proportions, as fractions of cap height h. The family is designed around
// these; they are deliberately not parameters (a width knob would break the
// tangent and clearance geometry below in ways no guard could see).
// ---------------------------------------------------------------------------
function _sg_w()      = 0.70;   // digit advance width
function _sg_wc()     = 0.36;   // ':' and ' ' advance width
function _sg_ym()     = 0.52;   // waist centre line of 3 and 8 (a hair above
                                // h/2 so the top bowl reads slightly smaller)
function _sg_diag()   = 0.90;   // diagonal strokes are drawn a little lighter
                                // than the stroke, as any bold face does
function _sg_stroke_default(h)  = 0.22 * h;
function _sg_spacing_default(h) = 0.12 * h;

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

// One glyph's advance width (mm) — digits are tabular.
function stencil_glyph_width(c, h) =
    assert(_sg_char_ok(c), str("stencil_glyph_width: unsupported character '", c,
                               "' (digits 0-9, ':' and ' ' only)"))
    (c == ":" || c == " ") ? _sg_wc() * h : _sg_w() * h;

// Total laid-out width (mm) of stencil_text(s, h, spacing = spacing).
function stencil_text_width(s, h, spacing = undef) =
    assert(is_string(s), str("stencil_text_width: s must be a string, got ", s))
    let (sp = is_undef(spacing) ? _sg_spacing_default(h) : spacing)
    len(s) == 0 ? 0 : _sg_x(s, len(s), h, sp) - sp;

module stencil_digit(n, h, stroke = undef, bridge = 0.8, bridge_min = 0.8,
                     bridged = true) {
    assert(is_num(n) && n == floor(n) && n >= 0 && n <= 9,
           str("stencil_digit: n must be an integer digit 0-9, got ", n));
    st = is_undef(stroke) ? _sg_stroke_default(h) : stroke;
    _sg_check("stencil_digit", h, st, bridge, bridge_min, bridged)
        translate([-_sg_w() * h / 2, -h / 2]) scale(h)
            _sg_glyph(str(n), st / h, bridge / h, bridged);
}

module stencil_colon(h, stroke = undef) {
    st = is_undef(stroke) ? _sg_stroke_default(h) : stroke;
    _sg_check("stencil_colon", h, st, 0.8, 0.8, false)
        scale(h) for (y = [0.28, 0.72])
            translate([0, y - 0.5]) circle(d = st / h);
}

module stencil_text(s, h, stroke = undef, spacing = undef, bridge = 0.8,
                    bridge_min = 0.8, bridged = true) {
    assert(is_string(s), str("stencil_text: s must be a string, got ", s));
    assert(len(s) > 0, "stencil_text: text must not be empty");
    assert(_sg_text_ok(s), str("stencil_text: unsupported character in \"", s,
                               "\" (digits 0-9, ':' and ' ' only)"));
    sp = is_undef(spacing) ? _sg_spacing_default(h) : spacing;
    st = is_undef(stroke) ? _sg_stroke_default(h) : stroke;
    tw = stencil_text_width(s, h, sp);
    for (i = [0 : len(s) - 1]) {
        c = s[i];
        x = -tw / 2 + _sg_x(s, i, h, sp) + stencil_glyph_width(c, h) / 2;
        if (c == ":") translate([x, 0]) stencil_colon(h, st);
        else if (c != " ")
            translate([x, 0])
                stencil_digit(_sg_digit_of(c), h, st, bridge, bridge_min, bridged);
    }
}

// ---------------------------------------------------------------------------
// Guards. A module so the geometry is only instantiated once every check has
// passed; children() is the glyph.
// ---------------------------------------------------------------------------
module _sg_check(who, h, s, bridge, bridge_min, bridged) {
    assert(is_num(h) && h > 0,
           str(who, ": cap height h must be positive (mm), got ", h));
    assert(is_num(s) && s >= 0.8,
           str(who, ": stroke must be at least 0.8 mm (two 0.4 mm extrusion widths), got ", s));
    assert(s <= 0.26 * h,
           str(who, ": stroke must not exceed 0.26*h = ", 0.26 * h,
               " mm (heavier closes the counters), got ", s));
    if (bridged) {
        assert(is_num(bridge_min) && bridge_min >= 0.8,
               str(who, ": bridge_min may be raised above 0.8 mm but never lowered below it, got ",
                   bridge_min));
        assert(is_num(bridge) && bridge >= bridge_min,
               str(who, ": bridge must be at least bridge_min = ", bridge_min,
                   " mm (the tether's printability floor), got ", bridge));
        assert(bridge <= 0.25 * h,
               str(who, ": bridge must not exceed 0.25*h = ", 0.25 * h,
                   " mm (a wider gap swallows the stroke), got ", bridge));
    }
    children();
}

// ---------------------------------------------------------------------------
// String helpers
// ---------------------------------------------------------------------------
function _sg_digit_of(c) = let (r = search(c, "0123456789")) len(r) == 1 ? r[0] : undef;
function _sg_char_ok(c) = c == ":" || c == " " || !is_undef(_sg_digit_of(c));
function _sg_text_ok(s, i = 0) =
    i >= len(s) ? true : (_sg_char_ok(s[i]) && _sg_text_ok(s, i + 1));
// x offset of glyph box i (sum of the advances and spacings before it)
function _sg_x(s, i, h, sp) =
    i <= 0 ? 0 : _sg_x(s, i - 1, h, sp) + stencil_glyph_width(s[i - 1], h) + sp;

// ---------------------------------------------------------------------------
// Geometry, in UNIT space: cap height 1, glyph box [0, _sg_w()] x [0, 1],
// stroke s and bridge b as fractions of h. stencil_digit scales by h.
// ---------------------------------------------------------------------------
module _sg_glyph(c, s, b, bridged) {
    difference() {
        _sg_stroke(c, s);
        if (bridged) _sg_bridges(c, s, b);
    }
}

// Bridge bars: one horizontal bar of height b across the whole glyph at the
// vertical centre of each counter. It removes the stroke on both sides of the
// counter and nothing else (the counter is not stroke), leaving two tethers
// of width b and length s. Digits without counters get no bars.
module _sg_bridges(c, s, b) {
    ym = _sg_ym(); hs = s / 2;
    ys = (c == "0") ? [0.5]
       : (c == "8") ? [(ym - hs + 1) / 2, (ym + hs) / 2]
       : (c == "6") ? [(ym + hs) / 2]
       : (c == "9") ? [1 - (ym + hs) / 2]
       : (c == "4") ? [0.50]
       : [];
    for (y = ys) translate([-1, y - b / 2]) square([_sg_w() + 2, b]);
}

module _sg_stroke(c, s) {
    w = _sg_w(); cx = w / 2; ym = _sg_ym(); k = _sg_diag(); hs = s / 2;
    if (c == "0") {
        _sg_bowl(0, 0, w, 1, s);
    } else if (c == "1") {
        _sg_seg([cx, hs], [cx, 1 - hs], s);                 // stem
        _sg_seg([cx - 0.22, hs], [cx + 0.22, hs], s);       // foot
        _sg_seg([cx, 1 - hs], [cx - 0.22, 0.70], s * k);    // flag
    } else if (c == "2") {
        // Top bowl kept from its left equator over the top and down the
        // right side to the point where a straight diagonal to the
        // bottom-left corner leaves it tangentially (the tangent from the
        // corner to the side semicircle), then the base bar.
        y0 = ym - hs; rc = min(w, 1 - y0) / 2; yct = (y0 + 1) / 2;
        C = [w - rc, yct]; rm = rc - hs; Q = [hs, hs];
        d = Q - C; phi = atan2(d[1], d[0]); al = acos(rm / norm(d));
        th = phi + al;
        P = C + rm * [cos(th), sin(th)];
        intersection() {
            _sg_bowl(0, y0, w, 1, s);
            union() {
                translate([-1, yct]) square([w + 2, 2]);
                _sg_wedge(C, th, 90, 3);
            }
        }
        translate([hs, yct]) circle(d = s);                 // top-left terminal
        _sg_seg(P, Q, s * k);                               // diagonal
        _sg_seg(Q, [w - hs, hs], s);                        // base bar
    } else if (c == "3") {
        y0 = ym - hs; y1 = ym + hs; yct = (y0 + 1) / 2; ycb = y1 / 2;
        intersection() {
            _sg_bowl(0, y0, w, 1, s);
            union() {
                translate([-1, yct]) square([w + 2, 2]);
                translate([cx, -1]) square([w, 3]);
            }
        }
        intersection() {
            _sg_bowl(0, 0, w, y1, s);
            union() {
                translate([-1, -1]) square([w + 2, 1 + ycb]);
                translate([cx, -1]) square([w, 3]);
            }
        }
        translate([hs, yct]) circle(d = s);                 // top terminal
        translate([hs, ycb]) circle(d = s);                 // bottom terminal
        translate([cx, ym]) circle(d = s);                  // waist bar's end
    } else if (c == "4") {
        // Open-topped 4: the left arm rises vertically from the crossbar,
        // then runs diagonally to the stem's top. A closed 4 has no counter
        // left at this weight; the vertical arm keeps one.
        xs = 0.48; yc = 0.27; yk = 0.64;
        _sg_seg([xs, hs], [xs, 1 - hs], s);                 // stem
        _sg_seg([hs, yc], [w - hs, yc], s);                 // crossbar
        _sg_seg([hs, yc], [hs, yk], s);                     // left arm
        _sg_seg([hs, yk], [xs, 1 - hs], s * 0.85);          // diagonal, lighter still
    } else if (c == "5") {
        yb = 0.55; y1 = yb + hs; rc = min(w, y1) / 2; ye = rc;
        CL = [rc, ye]; rm = rc - hs; ta = 210;
        _sg_seg([hs, 1 - hs], [w - hs, 1 - hs], s);         // top bar
        _sg_seg([hs, yb], [hs, 1 - hs], s);                 // stem
        _sg_seg([hs, yb], [rc + 0.01, yb], s, true, false); // waist bar, into the ring's top run
        intersection() {
            _sg_bowl(0, 0, w, y1, s);
            union() {
                translate([rc, -1]) square([w, 3]);         // right of the left semicircle's centre
                _sg_wedge(CL, ta, 270, 3);                  // bottom-left, down to the terminal
            }
        }
        translate(CL + rm * [cos(ta), sin(ta)]) circle(d = s);
    } else if (c == "6") {
        // Bottom bowl, a vertical spine tangent to its left side, and a top
        // arc of radius w/2 that hooks over to about one o'clock. The hook's
        // terminal stays clear of the bowl's top by ~0.09*h (1.3 mm at 14),
        // so the shell between the two cuts is a printable rib, not a sliver.
        y1 = ym + hs; rc = min(w, y1) / 2; ye = rc;
        C = [cx, 1 - cx]; R = cx; rm = R - hs; te = 50;
        _sg_bowl(0, 0, w, y1, s);
        translate([0, ye]) square([s, C[1] - ye]);          // spine, square both ends
        _sg_arc(C, R, s, te, 180);
        translate(C + rm * [cos(te), sin(te)]) circle(d = s);
    } else if (c == "7") {
        _sg_seg([hs, 1 - hs], [w - hs, 1 - hs], s);         // top bar
        _sg_seg([w - hs, 1 - hs], [0.25, hs], s * k);       // diagonal
    } else if (c == "8") {
        _sg_bowl(0, ym - hs, w, 1, s);
        _sg_bowl(0, 0, w, ym + hs, s);
    } else if (c == "9") {
        translate([w, 1]) rotate(180) _sg_stroke("6", s);   // the 6, turned
    }
}

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

// Straight stroke of width wd from p to q; r0/r1 round the ends (a square
// end is for a stroke that continues into a curve, where a round cap would
// poke into the counter).
module _sg_seg(p, q, wd, r0 = true, r1 = true) {
    d = q - p; L = norm(d); a = atan2(d[1], d[0]);
    translate(p) rotate(a) {
        translate([0, -wd / 2]) square([L, wd]);
        if (r0) circle(d = wd);
        if (r1) translate([L, 0]) circle(d = wd);
    }
}

// Rounded rectangle [x0,x1] x [y0,y1] with corner radius rc.
module _sg_rrect(x0, y0, x1, y1, rc) {
    hull() for (x = [x0 + rc, x1 - rc], y = [y0 + rc, y1 - rc])
        translate([x, y]) circle(r = rc);
}

// Bowl ring: a rounded rectangle with the largest corner radius its box
// allows (an obround), minus its inward offset by the stroke — so the
// counter is the same shape one stroke smaller.
module _sg_bowl(x0, y0, x1, y1, s) {
    rc = min(x1 - x0, y1 - y0) / 2;
    difference() {
        _sg_rrect(x0, y0, x1, y1, rc);
        offset(r = -s) _sg_rrect(x0, y0, x1, y1, rc);
    }
}

// Fan polygon from C spanning angles a0..a1 (degrees, CCW) out to `far`.
module _sg_wedge(C, a0, a1, far) {
    n = max(2, ceil((a1 - a0) / 30));
    polygon(concat([C], [for (i = [0 : n])
        let (a = a0 + (a1 - a0) * i / n) C + far * [cos(a), sin(a)]]));
}

// Annulus arc: outer radius R, stroke s, angles a0..a1 about C.
module _sg_arc(C, R, s, a0, a1) {
    intersection() {
        translate(C) difference() { circle(r = R); circle(r = R - s); }
        _sg_wedge(C, a0, a1, 3 * R);
    }
}
