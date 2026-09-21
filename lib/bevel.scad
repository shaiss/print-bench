// bevel.scad — FDM bevel (and spur) gear PAIRS from one generator, one clearance.
// All dimensions in millimeters, all angles in degrees. Use from a design with:
//   use <bevel.scad>          (or include <bevel.scad>; both work on 2021.01 and
//                              on the dev snapshots — see _bosl2_env below)
//
// Built on BOSL2's gears.scad (BSD-2-Clause, vendored at lib/BOSL2/). BOSL2
// already draws a bevel gear; what it does not do is keep a PAIR honest. Its
// bevel_gear() is called once per gear with the mate's tooth count passed by
// hand, its backlash and root clearance are two independent numbers, its
// mesh position is a worked example the caller retypes, and its default
// conical backing is an overhang when the gear is printed back-face-down.
// This library exists for the four things a printed pair needs on top of it:
//
//   1. ONE emitter for BOTH mates. bevel_pair() draws the pinion and the
//      crown from the same call, so the two profiles cannot drift apart —
//      the same rule threads-fdm.scad keeps between its neck and its bore.
//   2. ONE clearance. `tol` is the only fit number, in mm, and every surface
//      that faces the mate is derived from it (see "The one-tol rule").
//   3. A documented mesh frame and phase convention, plus the placement
//      functions a caller needs to put the pinion on an axle and the crown on
//      a tumble axis without re-deriving cone geometry.
//   4. Print-ready bodies: a flat back face, no overhang below it, a bore
//      with clearance and an optional D-flat.
//
// FDM choices, all deliberate: straight teeth (spiral = 0, no cutter arc) so
// the flanks print supportless; 20 degree pressure angle (the BOSL2 default and
// the only one this fit is proven at); no profile shift on bevel gears (BOSL2
// draws none); and a printable tooth-count floor rather than BOSL2's >= 3.
//
// PRINT ORIENTATION: back face down. bevel_gear_fdm(anchor = "back") emits the
// gear standing on its flat back face at z = 0 with the apex above it, which is
// the orientation to slice. The tooth tips and flanks lean inward going up;
// a gear with a cone angle below 45 degrees gets a hub under its teeth
// whose top is the back cone (see "The under-tooth fill" below), and one at
// or above 45 stands its tooth ends on a cylindrical backing, where they
// overhang by 45 degrees or less. Either way nothing on the outside faces
// down more steeply than that: the only horizontal underside is the back
// face itself, on the bed.
//
// ---------------------------------------------------------------------------
// The mesh frame ("apex frame")
// ---------------------------------------------------------------------------
//
// bevel_pair() emits both gears with their pitch-cone apexes at the ORIGIN:
//
//   * the PINION (n1 teeth) on the +z axis, body at z < 0: pitch base circle
//     at z = -bevel_apex_h(n1, n2, mod, sa), back face at
//     bevel_backface_z(n1, n2, mod, sa, tol, back1) (negative);
//   * the CROWN (n2 teeth) on the axis bevel_axis(sa) = [0, -sin sa, cos sa]
//     — the pinion's frame rotated by rotate([sa, 0, 0]) — with the same
//     signed distances measured along that axis.
//
// `sa` is the shaft angle: the angle between the two axes, 90 for a right-
// angle drive. Every placement function returns a SIGNED distance along the
// gear's own axis from the apex, so a caller places the pinion's axle with
// bevel_backface_z(...) directly and the crown's as that scalar times
// bevel_axis(sa). A single bevel_gear_fdm() uses the same frame (anchor =
// "apex", the default) so a gear emitted alone lands where the pair would
// have put it.
//
// ---------------------------------------------------------------------------
// The phase convention
// ---------------------------------------------------------------------------
//
// BOSL2 draws a gear with one tooth centred on its local +y axis, and in the
// apex frame the two pitch cones touch along the line [0, sin d1, -cos d1] —
// the +y side of the pinion. So at `phase` = 0 the pinion presents a TOOTH at
// the contact line, and the crown is spun so it presents a SPACE there: by
// 180/n2 when n2 is even (an even gear has a tooth diametrically opposite
// tooth 0, an odd one has a space). bevel_mate_phase(n1, n2, phase) is that
// offset plus the kinematic term:
//
//   crown spin = -phase * n1/n2 + (n2 even ? 180/n2 : 0)
//
// Rotating the pinion by `phase` about +z and the crown by that about its own
// axis keeps the pair meshed for every `phase`. That is the contract a
// kinematics gate can sweep: render bevel_pair_interference(..., phase = p)
// for a set of p and require zero facets from each. lib/bevel-mates.conf
// does it at three phases; a design's ci.fitchecks can do it at more.
//
// The spur pair uses the same convention with the wheel on the +x axis: the
// pinion is spun -90 so tooth 0 faces the wheel, the wheel by
// spur_mate_phase(n1, n2, phase) = -90 - phase * n1/n2 + (n2 even ? 180/n2 : 0).
// Place the wheel at spur_dist(n1, n2, mod), never at mod*(n1+n2)/2: BOSL2
// profile-shifts a spur gear with few teeth to avoid undercut (a 12-tooth
// pinion at mod 1 meshing with 30 sits at 21.28, not 21.0), and spur_dist()
// is BOSL2's own gear_dist() for the same profiles, so the two agree by
// construction. Bevel gears carry no profile shift (BOSL2 draws none).
//
// ---------------------------------------------------------------------------
// The one-tol rule
// ---------------------------------------------------------------------------
//
// `tol` is the clearance a printed surface needs from the surface it mates
// with — the same meaning threads-fdm.scad gives its radial tol. It is the
// ONLY fit number. Everything below is derived from it, never set beside it:
//
//   * FLANKS. The gap between a pinion flank and the crown flank facing it,
//     measured NORMAL to the flank, is `tol`. BOSL2's `backlash` thins each
//     tooth along the pitch circle; a circumferential gap b between two
//     flanks at pressure angle PA is b*cos(PA) normal to them, and the gap
//     is shared by two gears, so each gear is cut with
//         backlash = tol / (2 * cos(PA))            (bevel_backlash())
//     which at PA = 20 is 0.532*tol per gear, 1.064*tol circumferential in
//     total, and exactly `tol` flank to flank.
//   * TIP TO ROOT. BOSL2's standard root clearance is mod/4 (the geometry's
//     own number, present at tol = 0 too). The printed allowance is added to
//     it: clearance = mod/4 + tol, so a tip that prints `tol` oversize still
//     clears the root it runs over.
//   * BORE. `bore` is the SHAFT's nominal diameter. The hole is cut at
//     bore + 2*tol (tol per side), and a D-flat at its nominal offset + tol.
//   * THE UNDER-TOOTH FILL. Its top is the back cone shifted `tol` away from
//     the apex (see below), so the mate's tooth ends clear it by `tol`.
//
// The default, bevel_tol = 0.15, is where a 0.4 mm nozzle lands a running
// fit in PLA/PETG; a printer whose measured clearance differs sets it once
// (or reads it from printer.conf, see lib/printer-conf.scad). Raise it and
// every surface loosens together; there is no second number to chase.
//
// ---------------------------------------------------------------------------
// The under-tooth fill
// ---------------------------------------------------------------------------
//
// At the large end of a bevel gear the teeth end on the BACK CONE, a surface
// perpendicular to the pitch cone. For a pinion of cone angle d that surface
// leans only d degrees off horizontal — 30 for a 15:26 pair — so printed back
// face down it is an unprintable underside on every tooth, and BOSL2's
// default conical backing extends that same surface into the hub. The fix
// is material, not supports: the hub is a solid of revolution whose OUTER
// wall is vertical at the large-end tip radius and whose TOP is the back
// cone. The mate's teeth never cross the back cone (both gears' teeth lie on
// the apex side of it, and its trace in the axial plane is the same line for
// both), so nothing that fills the far side of it can touch the mate's TEETH.
// The fill's top is offset `tol` away from the apex because BOSL2's tooth
// ends are planar facets tangent to the cone, which sag below it by
// x^2/(2*pr)*tan(d) at a tooth's edges (~0.04 mm at mod 1.5): the offset
// keeps the mate's planar tooth ends clear of a true cone by the same
// allowance as everything else.
//
// What a fill CAN touch is the mate's fill. Both hubs would claim the far
// side of that same line around the contact point, and no fill radius
// avoids it — the contact point itself is inside both outer cylinders.
// Measured on the first cut, which filled every gear: 16.06 mm3 of
// interference at 15:26 with the teeth themselves clear, every vertex on
// one of the two fills' outer cylinders. So the fill goes only on a gear
// whose cone angle is below _BEVEL_FILL_BELOW (45): that is the gear whose
// tooth ends would overhang past 45 degrees, while its mate's tooth ends,
// at 90 - d or steeper for a right-angle pair, print on a plain cylindrical
// backing. A 90 degree pair therefore never carries two fills; a pair whose
// cone angles are BOTH below 45 (only possible at shaft angles under 90) is
// refused by _bevel_check rather than emitted with its hubs overlapping.
//
// ---------------------------------------------------------------------------
// Tessellation
// ---------------------------------------------------------------------------
//
// BOSL2 samples the involute with $gear_steps (16 by default), not $fn, so
// the flank geometry — and with it the fit — does not move with a caller's
// quality preset. The library pins $gear_steps anyway inside every geometry
// module, because the fit is proven at one value and a caller lowering it
// for speed would coarsen the flanks under a proven clearance (the issue #58
// / nuggs-coupling lesson). The bore, the fill and the D-flat are the only
// surfaces built with $fn and they are pinned too. The caller's $fn is
// untouched for the rest of the part.
//
// Print-ready details: bores with clearance and an optional D-flat; a
// minimum hub wall between the bore and the small-end root, guarded; and a
// 2 mm minimum plinth under the large-end root ring by default (`back`).
//
// For anything other than a straight-tooth external pair — internal gears,
// helical, worm, racks — reach for BOSL2's gears.scad directly.

include <BOSL2/std.scad>
include <BOSL2/gears.scad>

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// Default clearance, mm (see "The one-tol rule"). Read it from a caller with
// bevel_tol_default() — `use` does not export variables.
bevel_tol = 0.15;

// Fewest teeth a gear may have. Below ~8 at a 20 degree pressure angle the
// involute is undercut so far that BOSL2's profile is mostly root fillet and
// the tooth prints as a stub; 8 still meshes and is the smallest pinion the
// fit here has been measured on.
bevel_min_teeth = 8;

// Smallest module, mm. The tooth at the small end of a face = A/3 gear is
// scaled by 2/3, so its pitch-line thickness is (pi*m/2)*(2/3) = 1.047*m;
// the 0.8 mm minimum feature rule (two extrusion widths) needs m >= 0.764.
bevel_min_mod = 0.8;

// Thinnest wall between the bore and the small-end root, mm (three
// perimeters at 0.4 mm).
bevel_min_wall = 1.2;

// Plinth under the large-end root ring when `back` is not given, mm.
_BEVEL_PLINTH = 2;

// Pressure angle. The fit derivation (bevel_backlash) is exact at this
// value and nothing here exposes it as a parameter.
_BEVEL_PA = 20;

// A gear whose cone angle is below this gets the under-tooth fill (see the
// header): its tooth ends would otherwise be an overhang steeper than 45
// degrees printed back face down. At or above it the tooth ends print on
// their own and the fill is omitted — which is also what keeps two fills
// from ever meeting, since a 90 degree pair has at most one gear below 45.
_BEVEL_FILL_BELOW = 45;

// Pinned tessellation (see "Tessellation").
_BEVEL_GEAR_STEPS = 16;
_BEVEL_FN = 64;

// Cut-through overshoot for the bore, mm.
_EPS = 0.01;

// ---------------------------------------------------------------------------
// Functions
// ---------------------------------------------------------------------------

function bevel_tol_default() = bevel_tol;

// The one-tol derivations (see the header).
function bevel_backlash(tol) = tol / (2 * cos(_BEVEL_PA));
function bevel_clearance(mod, tol) = mod / 4 + tol;

// Pitch radius of an n-tooth gear of module `mod`.
function bevel_pitch_r(n, mod) = mod * n / 2;

// Pitch-cone half-angle of the gear with n teeth meshing with mate_n teeth
// at shaft angle sa. atan2 keeps the quadrant: a result >= 90 means the
// gear would need internal teeth, which _bevel_check refuses.
function bevel_cone_angle(n, mate_n, shaft_angle = 90) =
    atan2(sin(shaft_angle), mate_n / n + cos(shaft_angle));

// Cone distance: apex to the pitch circle at the large end. Shared by both
// gears of a pair.
function bevel_cone_dist(n, mate_n, mod, shaft_angle = 90) =
    bevel_pitch_r(n, mod) / sin(bevel_cone_angle(n, mate_n, shaft_angle));

// Axial distance from the large-end pitch base to the apex.
function bevel_apex_h(n, mate_n, mod, shaft_angle = 90) =
    bevel_pitch_r(n, mod) / tan(bevel_cone_angle(n, mate_n, shaft_angle));

// Face width defaults and bound. AGMA's rule is A/3 (or 10 modules, whichever
// is smaller); the guard is at A/2, where the small-end tooth is half size
// and BOSL2's inner cone is one more halving from collapsing.
function bevel_face_default(n, mate_n, mod, shaft_angle = 90) =
    min(bevel_cone_dist(n, mate_n, mod, shaft_angle) / 3, 10 * mod);
function bevel_face_max(n, mate_n, mod, shaft_angle = 90) =
    bevel_cone_dist(n, mate_n, mod, shaft_angle) / 2;

// Dedendum: how far the root sits inside the pitch cone, measured on the
// back cone. addendum (mod) + root clearance.
function bevel_dedendum(mod, tol) = mod + bevel_clearance(mod, tol);

// Where the large-end root ring sits below the pitch base, axially.
function bevel_root_drop(n, mate_n, mod, shaft_angle, tol) =
    bevel_dedendum(mod, tol) * sin(bevel_cone_angle(n, mate_n, shaft_angle));

// Distance from the pitch base to the back face: the given `back`, or the
// root drop plus the plinth.
function bevel_back_default(n, mate_n, mod, shaft_angle = 90, tol = bevel_tol) =
    bevel_root_drop(n, mate_n, mod, shaft_angle, tol) + max(_BEVEL_PLINTH, 2 * mod);
function bevel_back_h(n, mate_n, mod, shaft_angle = 90, tol = bevel_tol, back = undef) =
    is_undef(back) ? bevel_back_default(n, mate_n, mod, shaft_angle, tol) : back;

// Signed axial positions in the apex frame (negative: the body hangs below
// the apex along its own axis).
function bevel_pitchbase_z(n, mate_n, mod, shaft_angle = 90) =
    -bevel_apex_h(n, mate_n, mod, shaft_angle);
function bevel_backface_z(n, mate_n, mod, shaft_angle = 90, tol = bevel_tol, back = undef) =
    -(bevel_apex_h(n, mate_n, mod, shaft_angle) + bevel_back_h(n, mate_n, mod, shaft_angle, tol, back));

// Largest radius of the printed gear: the large-end tip radius, which the
// under-tooth fill's outer wall stands at (plus the fill's tol offset).
function bevel_outer_r(n, mate_n, mod, shaft_angle = 90, tol = bevel_tol) =
    let(d = bevel_cone_angle(n, mate_n, shaft_angle))
    bevel_pitch_r(n, mod) + mod * cos(d) + tol * sin(d);

// Root radius at the small end (the hub's thinnest ring), for the bore guard.
function bevel_small_root_r(n, mate_n, mod, face, shaft_angle, tol) =
    let(
        d  = bevel_cone_angle(n, mate_n, shaft_angle),
        A  = bevel_cone_dist(n, mate_n, mod, shaft_angle),
        u  = (A - face) / A
    )
    u * (bevel_pitch_r(n, mod) - bevel_dedendum(mod, tol) * cos(d));

// The crown's axis in the apex frame.
function bevel_axis(shaft_angle = 90) = [0, -sin(shaft_angle), cos(shaft_angle)];

// Crown spin that keeps it meshed with a pinion spun by `phase` (see "The
// phase convention").
function bevel_mate_phase(n1, n2, phase = 0) =
    -phase * n1 / n2 + (n2 % 2 == 0 ? 180 / n2 : 0);

// Wheel spin for the spur pair (wheel on +x, pinion spun -90 + phase).
function spur_mate_phase(n1, n2, phase = 0) =
    -90 - phase * n1 / n2 + (n2 % 2 == 0 ? 180 / n2 : 0);

// Centre distance of the spur pair. BOSL2's gear_dist with backlash = 0 —
// the backlash is cut into the profiles, never added here too.
function spur_dist(n1, n2, mod) = gear_dist(mod = mod, teeth1 = n1, teeth2 = n2);

// ---------------------------------------------------------------------------
// Guards
// ---------------------------------------------------------------------------

// Every guard fires here so a bad parameter set is refused before BOSL2 sees
// it — BOSL2 either produces garbage silently (a face wider than the cone)
// or aborts with a message that names its own argument, not the caller's.
function _bevel_check(n, mate_n, mod, face, shaft_angle, tol, bore, back, flat) =
    assert(is_num(shaft_angle) && shaft_angle > 0 && shaft_angle < 180,
           str("bevel: shaft_angle ", shaft_angle, " is outside (0, 180)"))
    assert(is_num(n) && n == floor(n) && n >= bevel_min_teeth,
           str("bevel: ", n, " teeth is below the printable minimum of ", bevel_min_teeth))
    assert(is_num(mate_n) && mate_n == floor(mate_n) && mate_n >= bevel_min_teeth,
           str("bevel: mate has ", mate_n, " teeth, below the printable minimum of ", bevel_min_teeth))
    assert(is_num(mod) && mod >= bevel_min_mod,
           str("bevel: module ", mod, " is below the printable minimum of ", bevel_min_mod))
    assert(is_num(tol) && tol >= 0,
           str("bevel: tol must not be negative (got ", tol, ")"))
    let(d = bevel_cone_angle(n, mate_n, shaft_angle),
        dm = bevel_cone_angle(mate_n, n, shaft_angle))
    assert(d < 90 && dm < 90,
           str("bevel: shaft_angle ", shaft_angle, " with ", n, ":", mate_n,
               " teeth would need internal teeth (cone angles ", d, " and ", dm, ")"))
    let(fmax = bevel_face_max(n, mate_n, mod, shaft_angle))
    assert(is_num(face) && face > 0,
           str("bevel: face width must be positive (got ", face, ")"))
    assert(face <= fmax,
           str("bevel: face width ", face, " exceeds what the cone allows (max ",
               fmax, " = half the cone distance)"))
    assert(d >= _BEVEL_FILL_BELOW || dm >= _BEVEL_FILL_BELOW,
           str("bevel: both cone angles (", d, " and ", dm, ") are below ", _BEVEL_FILL_BELOW,
               ": the under-tooth fills of the two gears would collide at the mesh — use a shaft angle of 90 or more"))
    let(drop = bevel_root_drop(n, mate_n, mod, shaft_angle, tol))
    assert(is_num(back) && back >= drop + bevel_min_wall,
           str("bevel: back ", back, " is too thin: the large-end root ring sits ",
               drop, " below the pitch base and needs ", bevel_min_wall, " of wall under it"))
    assert(is_num(bore) && bore >= 0,
           str("bevel: bore must not be negative (got ", bore, ")"))
    let(wall = bevel_small_root_r(n, mate_n, mod, face, shaft_angle, tol) - (bore / 2 + tol))
    assert(bore == 0 || wall >= bevel_min_wall,
           str("bevel: bore ", bore, " leaves a hub wall of ", wall,
               " mm at the small end (minimum ", bevel_min_wall, ")"))
    assert(is_num(flat) && (flat == 0 || (flat > bore / 2 && flat < bore)),
           str("bevel: flat ", flat, " must be 0 or between bore/2 and bore (bore ", bore, ")"))
    true;

function _spur_check(n, mate_n, mod, th, tol, bore, flat) =
    assert(is_num(n) && n == floor(n) && n >= bevel_min_teeth,
           str("spur: ", n, " teeth is below the printable minimum of ", bevel_min_teeth))
    assert(is_num(mate_n) && mate_n == floor(mate_n) && mate_n >= bevel_min_teeth,
           str("spur: mate has ", mate_n, " teeth, below the printable minimum of ", bevel_min_teeth))
    assert(is_num(mod) && mod >= bevel_min_mod,
           str("spur: module ", mod, " is below the printable minimum of ", bevel_min_mod))
    assert(is_num(tol) && tol >= 0,
           str("spur: tol must not be negative (got ", tol, ")"))
    assert(is_num(th) && th > 0,
           str("spur: thickness must be positive (got ", th, ")"))
    assert(is_num(bore) && bore >= 0,
           str("spur: bore must not be negative (got ", bore, ")"))
    let(wall = bevel_pitch_r(n, mod) - bevel_dedendum(mod, tol) - (bore / 2 + tol))
    assert(bore == 0 || wall >= bevel_min_wall,
           str("spur: bore ", bore, " leaves a hub wall of ", wall,
               " mm under the root (minimum ", bevel_min_wall, ")"))
    assert(is_num(flat) && (flat == 0 || (flat > bore / 2 && flat < bore)),
           str("spur: flat ", flat, " must be 0 or between bore/2 and bore (bore ", bore, ")"))
    true;

function _which_check(which, a, b) =
    assert(which == "both" || which == a || which == b,
           str("bevel: which must be \"both\", \"", a, "\" or \"", b, "\" (got ", which, ")"))
    true;

// ---------------------------------------------------------------------------
// Bore cutter (shared by bevel and spur gears)
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// BOSL2's dynamic environment, re-established per call
// ---------------------------------------------------------------------------
// BOSL2 configures its attachment/tag machinery through `$` special variables
// assigned at the TOP LEVEL of its own files ($tags_shown = "ALL", $tag = "",
// $overlap = 0, ...). Special variables are dynamically scoped from the CALL
// SITE, and a file this library is `use`d from never ran those assignments:
// OpenSCAD 2021.01 happens to leak a used file's top-level `$` assignments
// into calls made from the importer, the 2025 dev snapshots (the manifold
// engine CI's render gate runs) do not — every BOSL2 gear call then trips
// `assert(is_list($tags_shown) || $tags_shown == "ALL")` in attachments.scad.
// Rather than requiring every consumer to `include <BOSL2/std.scad>` itself,
// the two modules that reach BOSL2 geometry run their bodies inside this
// wrapper, which sets every top-level special BOSL2 defines (attachments.scad
// L20-56, gears.scad L22-29, transforms.scad $transform) to BOSL2's own
// default. `use <bevel.scad>` and `include <bevel.scad>` therefore behave the
// same on both engines; mate-check.sh / guard-check.sh (which always `use`
// the library) pass under the nightly because of this block.
module _bosl2_env() {
    $tags = undef;          $save_tag = undef;      $tag = "";
    $tag_prefix = "";       $overlap = 0;           $color = "default";
    $save_color = undef;    $anchor_override = undef; $attach_to = undef;
    $attach_anchor = [CENTER, CENTER, UP, 0];       $attach_alignment = undef;
    $parent_anchor = BOTTOM; $parent_spin = 0;      $parent_orient = UP;
    $parent_size = undef;   $parent_geom = undef;   $parent_parts = undef;
    $change_anchors = undef; $attach_inside = false;
    $edge_angle = undef;    $edge_length = undef;
    $tags_shown = "ALL";    $tags_hidden = [];
    $ghost_this = false;    $ghost = false;         $ghosting = false;
    $highlight_this = false; $highlight = false;
    $parent_gear_type = undef; $parent_gear_pitch = undef; $parent_gear_teeth = undef;
    $parent_gear_pa = undef; $parent_gear_helical = undef; $parent_gear_thickness = undef;
    $parent_gear_dir = undef; $parent_gear_travel = 0;
    $transform = IDENT;
    children();
}

// PUBLIC: the same environment, for a caller that `use`s this library and
// transforms its gears at top level. `use <bevel.scad>` exposes BOSL2's
// modules transitively — including its `translate`/`rotate`/`scale`
// REDEFINITIONS (transforms.scad, "Saving and restoring of transformations"),
// which multiply into `$transform` — while a used file's top-level `$`
// assignments are not visible at the call site on the dev snapshots. So
// `use <bevel.scad>` + `translate(...) bevel_pair(...)` warns "unknown
// variable $transform" there (2021.01 leaks the used file's specials, which
// is why it passes locally). Wrap such calls: bevel_env() { translate(...)
// bevel_pair(...); }. A design that `include`s BOSL2 (or this library) does
// not need it — its own top level carries BOSL2's specials. Every module in
// this library already runs inside the environment, so bare calls are fine
// either way; only the caller's OWN transforms around them need the wrapper.
module bevel_env() { _bosl2_env() children(); }

// A through-hole of bore + 2*tol along z over [z0, z1], with an optional
// D-flat: `flat` is the shaft's across-flat dimension, so the flat face of
// the hole sits at x = flat - bore/2 + tol and the material beyond it stays.
// The flat faces +x.
module _bevel_bore(bore, tol, flat, z0, z1) {
    $fn = _BEVEL_FN;
    if (bore > 0) {
        d = bore + 2 * tol;
        translate([0, 0, z0 - _EPS]) intersection() {
            cylinder(d = d, h = z1 - z0 + 2 * _EPS);
            if (flat > 0)
                translate([-d, -d, 0]) cube([d + flat - bore / 2 + tol, 2 * d, z1 - z0 + 2 * _EPS]);
            else
                translate([-d, -d, 0]) cube([2 * d, 2 * d, z1 - z0 + 2 * _EPS]);
        }
    }
}

// ---------------------------------------------------------------------------
// One bevel gear
// ---------------------------------------------------------------------------

// n          teeth on this gear
// mate_n     teeth on the gear it meshes with (the cone angle depends on it)
// mod        module, mm
// face       face width along the pitch cone, mm; default bevel_face_default()
// shaft_angle  angle between the two axes, degrees; default 90
// tol        the one clearance, mm (see header); default bevel_tol
// bore       shaft diameter, mm; 0 for no bore. Cut at bore + 2*tol.
// back       pitch base to back face, mm; default bevel_back_default()
// flat       D-flat across-flat dimension of the shaft, mm; 0 for a round bore
// phase      spin about its own axis, degrees (0 = tooth 0 on +y)
// anchor     "apex" (default): apex at the origin, body below it — the mesh
//            frame; "back": back face on z = 0, body above — the print
//            orientation; "pitchbase": large-end pitch circle on z = 0.
module bevel_gear_fdm(n, mate_n, mod, face = undef, shaft_angle = 90, tol = bevel_tol,
                      bore = 0, back = undef, flat = 0, phase = 0, anchor = "apex") {
    _bosl2_env() {
        face_ = is_undef(face) ? bevel_face_default(n, mate_n, mod, shaft_angle) : face;
        back_ = bevel_back_h(n, mate_n, mod, shaft_angle, tol, back);
        ok = _bevel_check(n, mate_n, mod, face_, shaft_angle, tol, bore, back_, flat);
        assert(anchor == "apex" || anchor == "back" || anchor == "pitchbase",
               str("bevel: anchor must be \"apex\", \"back\" or \"pitchbase\" (got ", anchor, ")"));
        $gear_steps = _BEVEL_GEAR_STEPS;
        $fn = _BEVEL_FN;

        d     = bevel_cone_angle(n, mate_n, shaft_angle);
        pr    = bevel_pitch_r(n, mod);
        ded   = bevel_dedendum(mod, tol);
        apexh = bevel_apex_h(n, mate_n, mod, shaft_angle);
        // Large-end tip and root points on the back cone, in the pitchbase frame
        // (r, z), then the fill's top: that line shifted `tol` away from the apex.
        off   = tol * [sin(d), -cos(d)];
        tip   = [pr + mod * cos(d),  mod * sin(d)] + off;
        root  = [pr - ded * cos(d), -ded * sin(d)] + off;
        z_top = apexh;                          // the apex, above the small end

        dz = anchor == "apex" ? -apexh : anchor == "back" ? back_ : 0;
        translate([0, 0, dz]) difference() {
            union() {
                bevel_gear(mod = mod, teeth = n, mate_teeth = mate_n, shaft_angle = shaft_angle,
                           face_width = face_, bottom = back_, cone_backing = false,
                           pressure_angle = _BEVEL_PA,
                           clearance = bevel_clearance(mod, tol), backlash = bevel_backlash(tol),
                           spiral = 0, cutter_radius = 0, slices = 1,
                           gear_spin = phase, anchor = "pitchbase");
                // The under-tooth fill (see header), only where the tooth ends
                // would overhang.
                if (d < _BEVEL_FILL_BELOW)
                    rotate_extrude()
                        polygon([[0, -back_], [tip.x, -back_], tip, root, [0, root.y]]);
            }
            _bevel_bore(bore, tol, flat, -back_, z_top);
        }
    }
}

// ---------------------------------------------------------------------------
// The pair
// ---------------------------------------------------------------------------

// Both mates in the apex frame (see header): pinion (n1) on +z, crown (n2)
// on bevel_axis(shaft_angle), meshed at `phase` (pinion degrees). `which`
// selects "both", "pinion" or "crown"; `explode` slides each gear that far
// away from the apex along its own axis for an exploded preview.
module bevel_pair(n1, n2, mod, face = undef, shaft_angle = 90, tol = bevel_tol,
                  bore1 = 0, bore2 = 0, which = "both", explode = 0, phase = 0,
                  back1 = undef, back2 = undef, flat1 = 0, flat2 = 0) {
    _bosl2_env() {
        ok = _which_check(which, "pinion", "crown");
        if (which != "crown")
            translate([0, 0, -explode])
                bevel_gear_fdm(n1, n2, mod, face, shaft_angle, tol, bore1, back1, flat1,
                               phase = phase, anchor = "apex");
        if (which != "pinion")
            rotate([shaft_angle, 0, 0]) translate([0, 0, -explode])
                bevel_gear_fdm(n2, n1, mod, face, shaft_angle, tol, bore2, back2, flat2,
                               phase = bevel_mate_phase(n1, n2, phase), anchor = "apex");
    }
}

// The interference solid of the meshed pair: pinion ∩ crown. Empty (zero
// facets) when the pair assembles at `tol` and `phase`. This is what
// lib/bevel-mates.conf measures and what a design's ci.fitchecks can sweep
// over phase. `crown_phase`, when given, overrides the meshed crown spin —
// the negative controls use it to put tooth on tooth.
module bevel_pair_interference(n1, n2, mod, face = undef, shaft_angle = 90, tol = bevel_tol,
                               phase = 0, crown_phase = undef) {
    _bosl2_env() {
        intersection() {
            bevel_gear_fdm(n1, n2, mod, face, shaft_angle, tol, phase = phase);
            rotate([shaft_angle, 0, 0])
                bevel_gear_fdm(n2, n1, mod, face, shaft_angle, tol,
                               phase = is_undef(crown_phase) ? bevel_mate_phase(n1, n2, phase) : crown_phase);
        }
    }
}

// ---------------------------------------------------------------------------
// Spur pair (the same discipline, for a reduction train)
// ---------------------------------------------------------------------------

// One spur gear standing on z = 0, th thick, axis +z, tooth 0 on +y before
// `phase`. Same one-tol rule and bore/flat as the bevel gear.
module spur_gear_fdm(n, mate_n, mod, th, tol = bevel_tol, bore = 0, flat = 0, phase = 0) {
    _bosl2_env() {
        ok = _spur_check(n, mate_n, mod, th, tol, bore, flat);
        $gear_steps = _BEVEL_GEAR_STEPS;
        $fn = _BEVEL_FN;
        difference() {
            spur_gear(mod = mod, teeth = n, thickness = th, pressure_angle = _BEVEL_PA,
                      clearance = bevel_clearance(mod, tol), backlash = bevel_backlash(tol),
                      gear_spin = phase, anchor = BOTTOM);
            _bevel_bore(bore, tol, flat, 0, th);
        }
    }
}

// Pinion (n1) at the origin, wheel (n2) at x = spur_dist(n1, n2, mod), both
// standing on z = 0, meshed at `phase` (pinion degrees). `explode` slides
// the wheel that much further out along +x.
module spur_pair(n1, n2, mod, th, tol = bevel_tol, bore1 = 0, bore2 = 0,
                 which = "both", explode = 0, phase = 0, flat1 = 0, flat2 = 0) {
    _bosl2_env() {
        ok = _which_check(which, "pinion", "wheel");
        if (which != "wheel")
            spur_gear_fdm(n1, n2, mod, th, tol, bore1, flat1, phase = -90 + phase);
        if (which != "pinion")
            translate([spur_dist(n1, n2, mod) + explode, 0, 0])
                spur_gear_fdm(n2, n1, mod, th, tol, bore2, flat2, phase = spur_mate_phase(n1, n2, phase));
    }
}

// Pinion ∩ wheel for the spur pair; `wheel_phase` overrides the meshed spin
// for negative controls.
module spur_pair_interference(n1, n2, mod, th, tol = bevel_tol, phase = 0, wheel_phase = undef) {
    _bosl2_env() {
        intersection() {
            spur_gear_fdm(n1, n2, mod, th, tol, phase = -90 + phase);
            translate([spur_dist(n1, n2, mod), 0, 0])
                spur_gear_fdm(n2, n1, mod, th, tol,
                              phase = is_undef(wheel_phase) ? spur_mate_phase(n1, n2, phase) : wheel_phase);
        }
    }
}
