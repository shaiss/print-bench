// nuggs-frieda — the NUGGS name bridge: a standard straight whose midspan is
// wrapped in a structural letter cage spelling the resident's name (FRIEDA),
// Word-World style — the module's silhouette IS the word.
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// The word is a SECOND wall, never the enclosure wall. The animal's tube is a
// full, continuous, standard NUGGS bore end to end; the letters stand on a
// separate shell outside it, tied to the tube by two conical skirts. A
// stencil tube — letters as the bore wall itself — was considered and
// refused: every void between glyphs is an opening the animal can reach, and
// anything between ~10 mm (bar-spacing safe) and 70 mm (full-passage floor,
// N1) is a head-trap. The double wall keeps every letter edge outside the
// enclosure, where the straight's own outer wall already lives (N6).
use <nuggs-coupling.scad>

/* [What to render] */
// bridge is the printable module; coupon is two port stubs for tuning port_tol
part = "bridge"; // [bridge, coupon]

/* [The word] */
// CAPITALS A-Z only. Lowercase is refused by the glyph table on purpose:
// x-height glyphs miss the cap rail and the i/j dot floats — every glyph in
// the cage must anchor rail to rail. (The brief allowed mixing case "as
// needed"; what the print needs is caps.)
name = "FRIEDA";
// Font size (mm). Cap height is ~0.688 x this (Liberation Sans Bold).
letter_size = 80;
// Advance multiplier. Under 1.0 tightens tracking so the word hugs together.
letter_track = 0.92;
// Extra mm removed from the gap AFTER each glyph (length = len(name)-1).
// This is structure, not taste: F's and E's free arm ends must land on the
// next letter's stem or they print as drooping cantilevers — the arm's
// underside is a flat face that appears in mid-air unless it bridges to the
// neighbour. Tune by looking at the F-R and E-D junctions in a render.
letter_kern = [8, 0, 0, 8, 0];
// Font. Metric-compatible with Arial Bold; the advance table below is its.
letter_font = "Liberation Sans:style=Bold";

/* [The NUGGS standard - change these and nothing you already printed fits] */
// Revision of the PORT STANDARD in lib/nuggs-coupling.scad this design builds
// to, engraved on the exposed tube wall below the letter cage.
NUGGS_PORT_REV = 1;
// Internal bore (mm) - the headline number. Asserted >= min_bore_mm by the lib
bore_d = 80.0;
// Tube shell thickness (mm)
wall = 2.4;
// Radial depth of the coupling ring beyond the tube OD (mm)
lug_r = 6.0;
// Axial projection of the coupling sectors past the tube face (mm)
port_proj = 10.0;
// Coupling sectors per face (3 = kinematically determinate)
n_lug = 3;
// Angular width of each sector (deg)
lug_deg = 40;
// Radial depth of the locking rib (mm)
rib_h = 1.0;
// Axial width of the locking rib / groove (mm)
rib_w = 2.4;
// Angular width of the locking rib (deg)
rib_deg = 12;
// The locking twist (deg)
twist_deg = 14;
// Backing-collar thickness (mm)
collar_t = 3.0;
// Overlap fusing the ribs into the outer sectors (mm)
bite = 0.8;

/* [Fit & tolerances] */
// The one knob. Uniform clearance on every coupling surface (mm).
// Tune on the coupon in +/-0.05 steps. Asserted 0.10-0.60 by the lib
port_tol = 0.30;

/* [Bridge] */
// Face-to-face length of the tube (mm). 160 = drop-in for the nuggs straight
straight_len = 160;

/* [Letter cage] */
// Radial gap between the coupling ring OD and the cage inner face (mm)
sleeve_clear = 1.6;
// Cage shell thickness (mm)
sleeve_t = 2.4;
// Height of the base/cap rails the glyphs fuse into (mm)
ring_h = 6.0;
// Rails sit this far inside the letter faces on both sides (mm), so no rail
// surface is ever coincident with a glyph surface — coincident cylinder pairs
// are how this repo has produced non-watertight meshes twice
ring_inset = 0.2;
// Conical skirt angle from horizontal (deg). Must stay > 45 so both skirts
// are self-supporting; 50 is the house angle (see nuggs NOTES.md)
cone_ang = 50;
// Axial thickness of the conical skirts (mm)
cone_ax = 3.0;
// Radial overlap fusing the skirts into the tube wall (mm)
cone_bite = 0.8;
// How far a glyph reaches past a rail edge to fuse with it (mm)
rail_overlap = 1.3;

/* [Welfare limits - asserted, not tunable down] */
// DTSchB entrance minimum, pouch-full criterion (mm). NEVER lower this.
min_bore_mm = 70;
// Syrian head-and-body length (mm). MEASURE YOUR ANIMAL and change this.
body_len_mm = 180;

/* [Print settings] */
// Nozzle diameter (mm) - feeds the wall and web guards in the lib
nozzle = 0.4;
// House angle for every chamfer and cone (deg). Not 45 - see nuggs NOTES.md
chamfer_ang = 50;

/* [Revision mark] */
// Cap height of the engraved mark (mm). 0 leaves the part unmarked.
mark_h = 5.0;
// Engrave depth (mm). Recessed, never proud (a raised character is a
// chew-initiation edge, N6). Asserted to leave 3 perimeters.
mark_d = 0.6;
// Per-character advance along the marked surface (mm)
mark_adv = 4.8;
// Clear tube wall reserved for a mark band above/below the cage (mm)
mark_band = 17;

/* [Quality] */
// This design's own quality preset — the lib's extraction values, so the tube
// and cage tessellate exactly as the nuggs family does. NOTE it does not
// reach the coupling: the library pins its own $fa/$fs inside every geometry
// module, deliberately, so the realised fit cannot move with this preset.
$fa = 3;
$fs = 0.8;

/* [Hidden] */
eps = 0.01;

// ---------------------------------------------------------------------------
// The coupling configuration — ONE cfg, built once, handed to every port
// call. Every coupling guard (bore floor, wall, bayonet clearance and travel,
// port_tol band, web, circumferential regression pins) fires inside
// nuggs_cfg(); none is restated here. This design keeps every port parameter
// at the standard's defaults, so the built port is byte-for-byte the
// configuration lib/nuggs-coupling-mates.conf proves assembles.
// ---------------------------------------------------------------------------
cfg = nuggs_cfg(bore_d    = bore_d,    wall      = wall,      lug_r    = lug_r,
                port_proj = port_proj, collar_t  = collar_t,  n_lug    = n_lug,
                lug_deg   = lug_deg,   rib_h     = rib_h,     rib_w    = rib_w,
                rib_deg   = rib_deg,   twist_deg = twist_deg, bite     = bite,
                port_tol  = port_tol,  eps       = eps,       nozzle   = nozzle,
                min_bore  = min_bore_mm);

ri    = nuggs_ri(cfg);      // bore radius
ro    = nuggs_ro(cfg);      // tube outer radius — the marked surface
r_out = nuggs_r_out(cfg);   // coupling ring OD
z_top = nuggs_z_top(cfg);   // top of the port zone; cage and marks start past it

// ---------------------------------------------------------------------------
// Letter-cage derived geometry
// ---------------------------------------------------------------------------

r_si = r_out + sleeve_clear;        // cage inner radius
r_so = r_si + sleeve_t;             // cage outer radius
rr_i = r_si + ring_inset;           // rail inner radius
rr_o = r_so - ring_inset;           // rail outer radius
r_a  = ro - cone_bite;              // skirt root, buried in the tube wall
r_lm = r_si + sleeve_t / 2;         // glyph placement radius (arc -> angle)

// Cap height of Liberation Sans Bold as a fraction of the font size. If the
// font falls back (DejaVu Sans Bold is 0.729) glyph tops move by ~3 mm; the
// cap rail is ring_h tall and the glyphs are placed rail_overlap + slack into
// it, so a fallback still fuses — see the CAGE FIT assert below.
cap_factor = 0.688;
cap_h = cap_factor * letter_size;

// z stack, bottom to top: port zone (z_top), engraved rev band (mark_band),
// bottom skirt + base rail, glyphs, cap rail + top skirt (mirrored), rule
// band, top port zone.
z_cone0 = z_top + mark_band;                              // bottom skirt root
z_rail_top = z_cone0 + cone_ax + (rr_i - r_a) * tan(cone_ang) + ring_h;
z_base = z_rail_top - rail_overlap;                       // glyph baseline
z_cap  = z_base + cap_h;                                  // glyph top
z_mid  = (z_base + z_cap) / 2;                            // cage mirror plane
z_cone1 = 2 * z_mid - z_cone0;                            // top skirt root

// ---------------------------------------------------------------------------
// Glyph metrics — Liberation Sans Bold capital advances, thousandths of an
// em (metric-compatible with Arial Bold). A-Z only, and the restriction is
// the anchoring argument in the `name` comment, not laziness.
// ---------------------------------------------------------------------------
_ADV = [722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833,
        722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611];

function _adv_mm(ch) =
    let(o = ord(ch))
    assert(o >= 65 && o <= 90, str(
        "FRIEDA CAGE: '", ch, "' is not a capital A-Z. Every glyph must",
        " anchor rail to rail; x-height glyphs and floating dots cannot."))
    _ADV[o - 65] / 1000 * letter_size * letter_track;

function _vsum(v, n) = n <= 0 ? 0 : v[n - 1] + _vsum(v, n - 1);

assert(len(name) >= 1, "CAGE NAME: name must carry at least one capital.");
// A wrong-length kern list must REFUSE, not degrade: zero-filling it would
// silently drop the welds a renamed cage needs (F's and E's arms print as
// cantilevers with no diagnostic), which is exactly the silent-failure class
// this repo's guards exist to kill (CodeRabbit review, PR #192).
assert(len(letter_kern) == len(name) - 1, str(
    "CAGE KERN: letter_kern has ", len(letter_kern), " entries for a ",
    len(name), "-glyph name; it needs exactly ", len(name) - 1,
    " (one per gap). Any glyph with free-ended arms (E, F, L, T) wants a",
    " weld into its right-hand neighbour — see NOTES.md F3."));
advs   = [for (i = [0 : len(name) - 1]) _adv_mm(name[i])];
kerns  = letter_kern;
word_w = _vsum(advs, len(advs)) - _vsum(kerns, len(kerns));
// Centre angle of glyph i. Viewed from +X, +Y is screen-right and the
// rotate([90,0,90]) glyph frame maps text-x to +Y, so later letters advance
// with increasing angle and the word reads left to right from outside.
function letter_ang(i) =
    (_vsum(advs, i) - _vsum(kerns, i) + advs[i] / 2 - word_w / 2)
    / r_lm * 180 / PI;

// ---------------------------------------------------------------------------
// Design-level asserts. The coupling's own guards live in nuggs_cfg().
// ---------------------------------------------------------------------------
run_len   = straight_len + 2 * port_proj;
run_limit = 2 * body_len_mm;

assert(straight_len + 2 * port_proj <= 240,
       "BED: the bridge plus both port projections must fit a 256 mm bed \
printed upright (240 mm, leaving margin).");

// PM.md N2 (designs/nuggs/PM.md), condensed to what a person changing
// straight_len needs; the full rule and its sources are the nuggs straight's
// assert and docs/nuggs-research.md.
assert(run_len <= run_limit, str(
    "NUGGS RUN LENGTH: this module encloses ", run_len, " mm of bore against",
    " the ", run_limit, " mm per-run limit (2 x body_len_mm = ", body_len_mm,
    " mm; Deutscher Tierschutzbund 'Tierschutzwidriges Zubehoer', one limb of",
    " a conjunctive test). A COUPLING IS NOT A BREAK: modules twisted",
    " together are ONE run, which is why the limit is engraved on the part.",
    " Shorten straight_len or measure a longer animal."));

assert(cone_ang > 45 && cone_ang < 65, str(
    "CAGE SKIRT: cone_ang = ", cone_ang, " deg must sit in (45, 65): at 45 or",
    " under the skirt undersides stop being self-supporting, far above it the",
    " skirts eat the letter band's height for nothing."));

assert(sleeve_clear >= 1.0, str(
    "CAGE CLEARANCE: the cage inner face sits ", sleeve_clear, " mm outside",
    " the coupling ring OD; keep >= 1.0 so the cage never touches a mating",
    " module's ring and never becomes part of the fit."));

assert(sleeve_t >= 3 * nozzle && rr_o - rr_i >= 3 * nozzle, str(
    "CAGE WALL: the cage shell (", sleeve_t, " mm) and the rails (",
    rr_o - rr_i, " mm) must both carry >= 3 perimeters at a ", nozzle,
    " mm nozzle (", 3 * nozzle, " mm)."));

// The cap-factor tolerance argument, held mechanically: even if the font
// falls back to DejaVu Sans Bold (cap 0.729), the glyph tops must still land
// inside the cap rail band, and at the declared font they must overlap it by
// rail_overlap without poking past.
assert(rail_overlap + (0.729 - cap_factor) * letter_size <= ring_h - 1, str(
    "CAGE FIT: a font fallback would push the glyph tops ",
    (0.729 - cap_factor) * letter_size, " mm past their placed height and out",
    " of the ", ring_h, " mm cap rail. Shrink letter_size or raise ring_h."));

assert(z_cone1 + mark_band <= straight_len - z_top, str(
    "CAGE LENGTH: the cage plus its mark bands needs z up to ",
    z_cone1 + mark_band, " mm of tube but the far port zone starts at ",
    straight_len - z_top, " mm. Lengthen straight_len or shrink letter_size."));

assert(word_w <= 2 * PI * r_lm - 5, str(
    "CAGE WRAP: '", name, "' needs ", word_w, " mm of arc against a ",
    2 * PI * r_lm, " mm circumference. Shrink letter_size or the name."));

// Each glyph is a flat prism intersected with the cage annulus, so a glyph
// wider than the prism's angular reach loses its edges. acos(prism_r0/r_si)
// bounds the reach; 50 deg keeps margin under it.
prism_r0 = 30;
prism_d  = r_so - prism_r0 + 4;
assert(max(advs) / 2 / r_lm * 180 / PI <= 50, str(
    "CAGE GLYPH WIDTH: the widest glyph subtends ",
    max(advs) / r_lm * 180 / PI, " deg; above 100 deg its edges fall outside",
    " the conformal prism. Shrink letter_size."));

assert(mark_d <= wall - 3 * nozzle,
       "MARK DEPTH: the revision engraving must leave >= 3 perimeters of tube \
shell behind it. Reduce mark_d or thicken wall.");

echo(str("nuggs-frieda: port standard R", NUGGS_PORT_REV, " at bore ", bore_d,
         " mm, port_tol ", port_tol, " mm (lib defaults; the exact config",
         " lib/nuggs-coupling-mates.conf gates)"));
echo(str("nuggs-frieda: run = ", run_len, " mm enclosed against the ",
         run_limit, " mm per-run limit; cage OD ", 2 * r_so, " mm, word '",
         name, "' at ", word_w, " mm of ", 2 * PI * r_lm, " mm circumference"));

// ---------------------------------------------------------------------------
// Primitives (tube, bore lead and wrap_text follow designs/nuggs, the
// family's reference consumer)
// ---------------------------------------------------------------------------

module tube(l, r_i = ri, r_o = ro) {
    difference() {
        cylinder(r = r_o, h = l);
        translate([0, 0, -eps]) cylinder(r = r_i, h = l + 2 * eps);
    }
}

// Internal edge break at a bore mouth: swallows elephant's foot so no lip is
// presented to a claw or a loaded cheek pouch (N6).
module bore_lead(z, dir = 1) {
    translate([0, 0, z])
        rotate([dir > 0 ? 0 : 180, 0, 0])
            cylinder(r1 = ri + 1.0, r2 = ri - eps,
                     h = 1.0 / tan(90 - chamfer_ang));
}

// Text wrapped around the outside of a cylinder of radius `r`, one character
// per tangent plane, reading left to right seen from outside. Returns the
// cutting solid — always subtract it.
module wrap_text(s, r, z, a0 = 0, h = mark_h, depth = mark_d, adv = mark_adv) {
    step = adv / r * 180 / PI;
    for (i = [0 : len(s) - 1])
        rotate([0, 0, a0 + (i - (len(s) - 1) / 2) * step])
            translate([r - depth, 0, z])
                rotate([90, 0, 90])
                    linear_extrude(depth + eps)
                        text(s[i], size = h, halign = "center",
                             valign = "center");
}

// ---------------------------------------------------------------------------
// The letter cage
// ---------------------------------------------------------------------------

// One skirt-plus-rail: a conical skirt rooted in the tube wall rising at
// cone_ang to the rail band the glyphs fuse into. ONE swept polygon — the
// rail and skirt must not be separate solids sharing a cylindrical surface
// (the coincident-face trap nuggs_sector() documents).
module cage_ring(z0) {
    rotate_extrude(angle = 360)
        polygon([[r_a,  z0],
                 [rr_o, z0 + (rr_o - r_a) * tan(cone_ang)],
                 [rr_o, z_rail_top],
                 [rr_i, z_rail_top],
                 [rr_i, z0 + cone_ax + (rr_i - r_a) * tan(cone_ang)],
                 [r_a,  z0 + cone_ax]]);
}

// The glyphs, conformal: each letter is a radial prism clipped to the cage
// annulus, so the letter face follows the cylinder at exactly sleeve_t thick
// — flush logic, no chord standing proud or shy. The prism starts well
// inside r_si (prism_r0) because a wide glyph's lateral edges meet the
// annulus at a smaller x than its centre does.
module cage_letters() {
    intersection() {
        translate([0, 0, z_base - 2])
            difference() {
                cylinder(r = r_so, h = cap_h + 4);
                translate([0, 0, -eps])
                    cylinder(r = r_si, h = cap_h + 4 + 2 * eps);
            }
        union()
            for (i = [0 : len(name) - 1])
                rotate([0, 0, letter_ang(i)])
                    translate([prism_r0, 0, z_base])
                        rotate([90, 0, 90])
                            linear_extrude(prism_d)
                                text(name[i], size = letter_size,
                                     font = letter_font, halign = "center",
                                     valign = "baseline");
    }
}

module cage() {
    cage_ring(z_cone0);
    translate([0, 0, 2 * z_mid]) mirror([0, 0, 1]) cage_ring(z_cone0);
    cage_letters();
}

// ---------------------------------------------------------------------------
// Marks — engraved, never proud, and only on tube wall that faces the room
// (the exposed bands between each port zone and its skirt).
// ---------------------------------------------------------------------------
function mark_rev()  = str("NUGGS PORT R", NUGGS_PORT_REV);
function mark_rule() = [str("MAX RUN ", run_limit, "MM"), "COUPLINGS DONT RESET"];

module marks() {
    if (mark_h > 0) {
        wrap_text(mark_rev(), ro, (z_top + z_cone0) / 2);
        zt = (z_cone1 + straight_len - z_top) / 2;
        wrap_text(mark_rule()[0], ro, zt + mark_h * 0.8);
        wrap_text(mark_rule()[1], ro, zt - mark_h * 0.8);
    }
}

// ---------------------------------------------------------------------------
// Parts
// ---------------------------------------------------------------------------

// The name bridge: a standard straight (identical port at each end, one bore
// cut through the whole part — nuggs_port() is NOT bore-clean, see the lib
// header) wearing the letter cage.
module bridge() {
    difference() {
        union() {
            tube(straight_len);
            nuggs_port(cfg);
            translate([0, 0, straight_len]) mirror([0, 0, 1]) nuggs_port(cfg);
            cage();
        }
        nuggs_bore_cut(cfg, -port_proj - 2, straight_len + port_proj + 2);
        translate([0, 0, -port_proj]) bore_lead(0.001, 1);
        translate([0, 0, straight_len + port_proj])
            mirror([0, 0, 1]) bore_lead(0.001, 1);
        marks();
    }
}

// Print this first: two bore-clean port stubs (nuggs_neck does its own bore
// cut), mated by hand to tune port_tol before committing to the bridge.
module coupon() {
    for (x = [-1, 1])
        translate([x * (r_out + 6), 0, 0]) nuggs_neck(cfg, 25);
}

if      (part == "bridge") bridge();
else if (part == "coupon") coupon();
else assert(false, str("unknown part: ", part));
