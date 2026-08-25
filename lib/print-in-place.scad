// print-in-place.scad — print-in-place sliding mechanisms for FDM.
// All dimensions in millimeters. Use from a design with:
//   use <print-in-place.scad>
//
// Extracted from designs/sushi-battleship at v0.1 (issue #19). The battleship
// is ARCHIVED — frozen, retired from active CI — so unlike the threads-fdm
// extraction the design was NOT refactored onto this library: its inline
// copies stay exactly as they shipped, and this library is the review-hardened
// slide system lifted verbatim (module body text identical, the design's
// file-scope globals promoted to parameters defaulting to the battleship's
// values). The frozen design remains the reference implementation; this file
// is where the mechanism lives on.
//
// One-time extraction parity evidence (recorded here because the battleship's
// NOTES.md is frozen with the design; scratchpad fixtures, not committed —
// an extra lib/*.scad would read as a first-party library to docs-check):
// the battleship's lid_body() and door("A1"), rendered from the frozen design
// via `use <>`, against the same parts rebuilt on this library's modules
// (lips -> slide_rail, ridges -> end_stop, window cut -> sacrificial_membrane,
// tab loop -> slide_tab). OpenSCAD 2021.01 / CGAL, 2026-08-07:
//   door: lineage.sh mesh-hash IDENTICAL both sides
//         (2a12826549a478e761bc4fc8ec410ea759b0a68a067a6151a11cda2f3dc2d943)
//   lid:  facets 5680 = 5680, volume delta +0.000000%, CGAL stats identical
//         (2842 vertices / 1606 facets / 2 volumes), printcheck identical
//         (watertight, 1 body, same warnings, same 59/100 on the bare
//         lid_body), ASCII-STL facet multiset identical at export precision.
//         mesh-hash differs on exactly one derived coordinate: the
//         lip-underside/wall-face crossing (z ~ 4.70996) sits on a float32
//         rounding boundary, and 784 facets flip by one float32 ulp
//         (~0.5 um). Isolated by control fixtures: a verbatim copy, a
//         regrouped loop and a split translate all hash EQUAL to the
//         reference, and the library's own numbers (pip_lip_z, pip_rail_h,
//         the profile points, the centres) compare bit-equal (==) against
//         the design's inline values — the flip is OpenSCAD
//         construction-order sensitivity in the last double bits of one
//         computed intersection, five orders of magnitude below any
//         tolerance here, not a geometry change.
//
// THE ACOUSTIC PROPERTY (do not tune this away). The battleship's clearances
// (clr_h = 0.5, clr_v = 0.4, and the derived lip engagement) were reviewed to
// slide freely AND to not *rattle*. In a hidden-information game that is not
// polish, it is the rules: a door over a loaded cell that sounds different
// from a door over an empty one — under a table bump, a shake, a fidgeting
// player — is a wallhack no geometry check will ever catch (issue #19,
// fog-of-war review). If doors stick, tune door-side `fit` on a coupon in
// +-0.1 steps; do not "optimize" the rail clearances upward in a game design,
// or the audible tell comes back.
//
// The slide system in one paragraph: a door slides on side TABS (slide_tab)
// captured under castellated LIPS on the rail walls (slide_rail). Closed,
// every tab sits under a lip — the door is locked and cannot lift. Slid by
// `travel`, the tabs align with the gaps between lips and the door lifts
// straight out. END-STOP ridges (end_stop) bound the travel, and a one-layer
// SACRIFICIAL MEMBRANE (sacrificial_membrane) under each opening catches the
// door's drooped first-layer strands during the print. pip_hinge is the same
// print-in-place philosophy for a rotating joint, built on printability.scad's
// teardrop profile so the bore roof prints supportless — with the bore grown
// from the pin's profile by a true 2D offset, for a reason worth reading
// before touching it (see pip_hinge).

use <printability.scad>

// ---------------------------------------------------------------------------
// Clearance math — the review-settled derivations, exposed so callers derive
// instead of retyping (and so a caller's wall can be sized to the rail).
// Expressions are kept textually identical to the battleship's derived-
// dimension block: parity of the extraction is bit-exact only because the
// float arithmetic is the same arithmetic.
// ---------------------------------------------------------------------------

// Height of the lip root above the lid plate top: the tab (riding at gap_z,
// tab_t thick) needs clr_v of air under the lip, and the lip's 45-degree
// underside starts clr_h before its root reaches full overhang.
function pip_lip_z(gap_z = 0.6, tab_t = 1.2, clr_v = 0.4, clr_h = 0.5) =
    gap_z + tab_t + clr_v - clr_h;

// Total rail-wall height above the lid plate top: lip root + 45-degree
// underside rise + the solid web above it.
function pip_rail_h(gap_z = 0.6, tab_t = 1.2, clr_v = 0.4, clr_h = 0.5,
                    lip_d = 3.2, rail_ext = 0.8) =
    pip_lip_z(gap_z, tab_t, clr_v, clr_h) + lip_d + rail_ext;

// The battleship's three tab/lip centres for a given window: tabs stay inside
// a span 10 mm narrower than the opening, outer centres at +-(span-tab_len)/2.
function pip_tab_centres(opening = 46, tab_len = 5.5) =
    let (span = opening - 10)
    [-(span - tab_len)/2, 0, (span - tab_len)/2];

// One lip's 2D profile (extruded along the rail): root edge buried side*eps
// into the rail wall, 45-degree underside out to the full overhang, then the
// solid web up to lip_top_drop below the rail top. The drop is mesh hygiene,
// not mechanism: a lip top exactly coplanar with the rail top leaves a
// shared-plane strip Manifold exports as a non-manifold seam (288 bad edges
// in the battleship's CI) while CGAL papers it over as zero-area triangles.
function pip_lip_profile(side, lz, rh, lip_d, lip_top_drop, eps) =
    [[side*eps, lz],
     [-side*lip_d, lz + lip_d],
     [-side*lip_d, rh - lip_top_drop],
     [side*eps, rh - lip_top_drop]];

// ---------------------------------------------------------------------------
// Modules
// ---------------------------------------------------------------------------

// Castellated lip row for ONE side of one door bay: the lips that capture a
// sliding door's tabs, 45-degree undersides so they print supportless on the
// rail wall. Origin: x = 0 at the rail wall's cell-side face (lip roots bury
// side*eps INTO the wall so lip and wall share volume, not just a face — a
// kiss contact is fused by CGAL but exported by Manifold as a separate
// shell), y = 0 at the bay centre, z = 0 at the lid plate TOP.
//
// The rail WALL itself stays caller-owned on purpose: in the battleship the
// walls are shared between columns and run the full lid — that is board
// layout, not mechanism. Size the wall with pip_rail_h() and bury it eps
// into the plate the same way (see the demo's reference bay).
//
// `travel` is the door's slide distance (no default — it is design-derived:
// the battleship computes it from the door end margins and the end-stop).
// `fit` is the mating door's fit adjustment, passed here so the pair's
// engagement cross-check lives with the lips it protects.
// clr_h/clr_v are THE acoustic clearances — see the header before touching.
module slide_rail(travel,
                  clr_v = 0.4, clr_h = 0.5,
                  tab_len = 5.5, lip_c = pip_tab_centres(),
                  lip_d = 3.2, gap_z = 0.6, tab_t = 1.2,
                  rail_ext = 0.8, lip_top_drop = 0.4,
                  side = 1, fit = 0, eps = 0.01) {
    assert(travel - tab_len >= 1, "slide travel too short to free the tabs");
    assert(lip_d - clr_h >= 2,     "not enough lip engagement");
    assert(len(lip_c) < 2
           || min([for (k = [0 : len(lip_c) - 2]) lip_c[k+1] - lip_c[k]])
              >= travel + tab_len + 0.5,
           "tabs would hit the lips at full slide; widen the lip spacing or shorten tab_len");
    assert(lip_d - clr_h - max(fit, 0) >= 1.5,
           "door_fit too loose; tabs would barely engage the lips");
    assert(lip_top_drop > 0 && lip_top_drop < rail_ext,
           "lip_top_drop must be greater than 0 and below rail_ext");
    lz = pip_lip_z(gap_z, tab_t, clr_v, clr_h);
    rh = pip_rail_h(gap_z, tab_t, clr_v, clr_h, lip_d, rail_ext);
    for (c = lip_c)
        translate([0, c + tab_len/2, 0])
            rotate([90, 0, 0])
                linear_extrude(tab_len)
                    polygon(pip_lip_profile(side, lz, rh, lip_d, lip_top_drop, eps));
}

// The matching door-side tabs: bottom-layer slabs sticking out sideways from
// the door body, one row per side, riding gap_z above the plate under the
// lips. Origin = door centre (same frame as the door body the caller draws).
// `body_w` is the door body width BEFORE fit; `fit` shrinks the body the tabs
// ride on symmetrically (+ = looser) while the tab slab itself never changes
// — so engagement loss per +fit step is bounded, and slide_rail's `fit`
// parameter carries the cross-check that refuses a fit the lips can't hold.
module slide_tab(body_w,
                 tab_c = pip_tab_centres(), tab_w = 3.5, tab_len = 5.5,
                 tab_t = 1.2, gap_z = 0.6, fit = 0) {
    assert(fit >= -0.2 && fit <= 0.5,
           "door_fit outside the safe range (-0.2 .. 0.5)");
    dw = body_w - 2*fit;
    for (s = [-1, 1], c = tab_c)
        translate([s*dw/2 - (s < 0 ? tab_w : 0), c - tab_len/2, gap_z])
            cube([tab_w, tab_len, tab_t]);
}

// Door end-stop ridge: a low bar the opening door's leading edge hits at full
// travel. Origin: x = 0 at the bay centre, y = 0 at the REAR face of the
// adjacent closed door (the one the ridge must never weld to — the ridge sits
// `gap` clear of it, folded into the geometry so the parameter is
// load-bearing), z = 0 at the lid plate top (the ridge buries eps into it).
// Kept 2*side_inset narrower than the door so it never reaches the tab/lip
// zone. The gap guard is the extraction's new-found precondition (the
// threads-fdm pattern: extraction turns a latent assumption into a guard) —
// the battleship's original 0.2 mm construction gap was under one extrusion
// width, and a closed door's draped first layer spot-welded to it (PR #3
// hardening round A).
module end_stop(door_w, gap = 0.5, side_inset = 2.8, ridge_w = 0.8,
                h = 1.4, eps = 0.01) {
    assert(gap > 0.4,
           "end-stop gap must exceed one 0.4 mm extrusion width — a closed door's draped first layer spot-welds to a nearer ridge");
    translate([-(door_w/2 - side_inset), -ridge_w - gap, -eps])
        cube([door_w - 2*side_inset, ridge_w, h + eps]);
}

// Sacrificial membrane under a print-in-place opening — INVERTED: this module
// emits the WINDOW CUTTER, raised `h` off the plate bottom, and the membrane
// is the plate material that cut SPARES below z = h. (In the battleship the
// membrane was never geometry — it was where the window cut chose to start.)
// Use inside difference() on a plate whose bottom is z = 0, passing the 2D
// window profile as the child:
//
//   difference() {
//       plate();
//       sacrificial_membrane(h = 0.2, cut_h = plate_t) square(46, center = true);
//   }
//
// h = 0.2 sits on the layer grid: exactly one printed layer at the common
// presets (0.3 lands mid-layer and can coin-flip into a two-layer punch-out).
// h = 0 is legal and means "no membrane" — the cut starts at the bed. The cut
// runs cut_h tall from z = h, so it clears a cut_h-thick plate's top by h
// automatically. The membrane only catches drooped strands from the part
// bridging above; it does NOT support the bridge — punch it out after
// printing.
module sacrificial_membrane(h = 0.2, cut_h = 3) {
    assert(h >= 0, "membrane thickness must not be negative");
    assert(cut_h > 0,
           "membrane cut height must be positive — a zero-height cutter leaves the plate uncut");
    translate([0, 0, h])
        linear_extrude(cut_h)
            children();
}

// The teardrop 2D profile — textually the same profile printability.scad's
// teardrop_hole() extrudes (circle + 45-degree roof, point +Y in 2D). Kept
// here so the hinge BORE can be built as a true 2D offset of the pin's
// profile, which a 3D module cannot express. If the printability profile
// ever drifts from this copy the hinge pair's fit drifts with it — and
// print-in-place-mates.conf's hinge cases measure that fit on the exported
// mesh, so the drift fails check.sh. That manifest is the declared guard
// binding the two copies.
module _pip_teardrop2d(d) {
    circle(d = d);
    intersection() {
        rotate(45) square(d * 0.72, center = false);
        circle(d = d * 1.6);
    }
}

// Print-in-place hinge knuckle: a barrel with a teardrop bore (axis along Y,
// point +Z — printability.scad's teardrop_hole orientation), sized so the
// pin printed captive inside it clears by `clear` on EVERY surface and both
// the bore roof and the pin top print supportless with the axis horizontal.
//
// The bore is the pin's own 2D profile grown by offset(r = clear) — a true
// uniform clearance — and NOT a scaled-up teardrop_hole(pin_d + 2*clear).
// That obvious construction is wrong in a way no still render shows: the
// teardrop's 45-degree flank planes pass through its origin, so scaling the
// profile about that origin leaves the flank planes FIXED — the pin's flanks
// end up exactly coplanar with the bore's, i.e. zero clearance along both
// flanks, a welded print. CGAL renders the coincident planes as a clean
// kissing mate (0 facets of interference), which is how it survived the
// stable gate; CI's Manifold pass exported the same kiss as an 8-facet
// sliver, which is what caught it. The offset bore restores `clear` on the
// flanks and everywhere else by construction (Minkowski property), and the
// hinge-pin-play mate case pins the flank clearance under CGAL too.
//
// The outer radius is derived from the OFFSET bore's apex (0.8*pin_d +
// clear), not the bore circle, so the promised `wall` holds at the knuckle's
// thinnest point — the teardrop point — not just at the circular sides.
// The bore is $fn-sensitive — pin $fn >= 64 in any design that renders one
// (the demo does). `clear` is an acoustic clearance like the rail's — 0.25
// is the weld floor, and tuning it far upward buys a rattling joint (see
// the header).
module pip_hinge(pin_d = 4, clear = 0.5, wall = 2.4, l = 8) {
    assert(clear >= 0.25,
           "print-in-place hinge clearance under 0.25 mm welds at typical layer heights");
    assert(wall >= 1.2,
           "knuckle wall under 1.2 mm (3 perimeters at a 0.4 mm nozzle)");
    difference() {
        rotate([-90, 0, 0])
            cylinder(r = 0.8*pin_d + clear + wall, h = l, center = true);
        // The bore extrudes at +90, NOT the barrel's -90: that sign is what
        // aims the teardrop point +Z to match the pin (teardrop_hole). The
        // barrel's own sign is irrelevant — it is a cylinder — but the two
        // rotations matching here is not coincidence to tidy away; the bore
        // and teardrop_hole carried the same flipped -90 through issue #398,
        // mutually consistent and both undocumented.
        rotate([90, 0, 0])
            linear_extrude(l + 0.02, center = true)
                offset(r = clear)
                    _pip_teardrop2d(pin_d);
    }
}

// The matching pin: printability.scad's teardrop_hole solid at the pin's own
// diameter — the same profile the bore is offset from, so the clearance
// delivered is exactly pip_hinge's `clear` on every surface. Print it
// captive (same teardrop orientation) or as a separate part pushed in after.
module pip_hinge_pin(pin_d = 4, l = 8) {
    teardrop_hole(d = pin_d, l = l);
}
