// sweetheart-hamster — a chibi hamster jewelry box that splits into a heart.
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// The hamster splits down its sagittal midline into a LEFT and RIGHT half,
// joined along the TOP (dorsal) seam by a thin LIVING-HINGE web — the built-in
// print-in-place "lid". It prints FLAT: the two halves lie cut-face-DOWN on the
// bed (domes up, self-supporting via the inward-tapering massing), splayed open
// about the dorsal hinge, so no supports (snap-clamshell-box, CC1, is the
// reference pattern). Fold the halves up about the hinge and the hamster
// closes, cradling a heart on its belly; open it and the heart parts between
// the two halves — the "two pieces apart look like a heart" reveal. A
// heart-shaped pocket straddling the seam is the ring nest.
//
// DEFAULT render (no -D) = the flat PRINT pose (what CI slices). `fold=90`
// gives the assembled hamster for previews; cameras.conf drives the hero shots.

use <printability.scad>   // rounded/chamfer helpers (OPENSCADPATH="$PWD/lib:$PWD")

/* [Show] */
// Fold of each half about the dorsal hinge: 0 = FLAT print pose (default),
// 90 = assembled hamster. Previews only; the PRINTED model is flat.
fold = 0;   // [0:5:90]

/* [Size] */
// Overall scale on the study-E massing (1.70 -> ~60 mm tall assembled)
S = 1.70;

/* [Heart] */
// Belly heart width (mm) — the visible "shape heart" the hamster cradles
heart_w = 20;
// Height of the heart's centre up the belly (mm, assembled frame, pre-scale)
heart_cz = 9;
// Forward position of the heart on the belly (mm, pre-scale)
heart_cy = -6;
// How far the belly heart stands proud of the front skin (mm) — chunky so it
// reads as a heart the hamster hugs, and sits in front of the cheeks
heart_proud = 4;
// Front of the belly at the heart height (scales with S) — the heart's front
// face lands heart_proud beyond this
belly_front = 15 * S;
// Ring-nest heart cavity width (mm) and depth into each half (mm)
nest_w = 22;
nest_depth = 6;
// Carve the ring-nest cavity. The coupon turns this OFF: it exists to tune the
// hinge/seam, and the absolute-size nest thins the walls of a downscaled coupon.
nest_on = true;

/* [Split & hinge] */
// Sagittal parting clearance, total across the seam (mm)
part_gap = 0.5;
// Dorsal hinge height in the assembled frame (mm, pre-scale) — the fold axis the
// two halves rotate flat about. v0.2 FIX (the fused-hinge bug): this MUST sit
// above the model's true top. The flat-pose transform maps a point at assembled
// height z to flat-x = z − hinge_z*S, so ANY material above the fold axis
// (z > hinge_z*S) lands on the far side of the seam and welds into the other
// half. v0.1 used hinge_z=30 (→51 mm), but the ears top out at 60.13 mm, so the
// 9 mm above the axis crossed the seam — a 1378-facet weld that printed as one
// solid, watertight body the hinge could not open (printcheck saw nothing, the
// fitcheck tested the wrong pose). hinge_z=36 (→61.2 mm) clears the ear-top, so
// each half stays on its own side and the halves connect ONLY through the web.
hinge_z = 36;
// Living-hinge web thickness (flexure) (mm) — thin; PETG/PP fold, PLA cracks
web_t = 0.7;
// Living-hinge web length along the dorsal seam (mm)
web_len = 16;
// Web overlap into each half's skin (mm). v0.2: widened from 3 → 6. With the
// fold axis above the ear-top the two halves' dorsal ridges sit ~4 mm either
// side of the seam centre (the ears are higher than the spine, so the spine
// ridge — where the web must bridge — lands a few mm out); the web has to reach
// both ridges to make the print one foldable piece, so it spans ±(g+web_ov).
web_ov = 6;

/* [CI fit-check — not a print parameter] */
// "" = the model (flat PRINT pose). "fitcheck" = boolean intersection of the two
// halves in the FLAT pose CI slices (must be EMPTY: they clear). "fitcheck_neg"
// and "fused" reproduce the v0.1 WELD by dropping the fold axis back below the
// top (fold_hz): the intersection INTERFERES (proves the empty check can fail),
// and the union is one connected body that fusecheck's control catches. Wired by
// ci.fitchecks and ci.fusecheck.
part = "";
// Fold axis for the deliberately-welded controls (pre-scale) — v0.1's value,
// which welds because it sits below the 60.13 mm top. Not a print parameter.
fused_hz = 30;

/* [Quality] */
$fn = 64;   // production 96 for the hero renders (cameras.conf overrides)

// ===========================================================================
// Massing — study E chibi hamster, sagittal plane X=0, base z=0, front -Y.
// Widest at a chamfered seat so each half prints cut-face-down without support.
// ===========================================================================
module blob() scale(S) union() {
    hull() {
        cylinder(d = 29, h = 3);                                   // seat (widest)
        translate([0, -2, 10.5]) sphere(r = 13.4);                 // belly
    }
    hull() {
        translate([0, -2, 11.5]) sphere(r = 10.5);                 // shoulders
        translate([0, -6, 21.5]) scale([1, 0.94, 1]) sphere(r = 12); // head
    }
    for (s = [-1, 1]) {
        translate([s*8, -9, 17.5]) sphere(r = 7.6);                // fat cheeks
        hull() {
            translate([s*8, -9, 17.5]) sphere(r = 4.6);
            translate([s*6, -3, 12.5]) sphere(r = 4);
        }
    }
    for (s = [-1, 1])
        translate([s*6.5, -5, 30]) scale([0.95, 0.8, 1]) sphere(r = 4.2); // ears
    hull() {                                                       // muzzle
        translate([0, -15, 18.5]) sphere(r = 4.0);
        translate([0, -17.5, 16.5]) sphere(r = 2.8);
    }
    translate([0, -19, 16]) sphere(r = 1.3);                       // nose
    for (s = [-1, 1]) translate([s*4.2, -15.8, 22]) sphere(r = 1.7); // beady eyes
    for (s = [-1, 1]) translate([s*2.6, -14, 7.5]) sphere(r = 2.6); // paws
    for (s = [-1, 1]) translate([s*8.5, -11, 1.6]) scale([1,1.55,0.5]) sphere(r = 4.2); // feet
    translate([0, 13.5, 7]) scale([1, 0.8, 1]) sphere(r = 3);      // tail
}

// 2D heart (point down), width w.
module heart2d(w = 24) {
    r = w/4;
    offset(r = 1.0) offset(delta = -1.0)
    union() {
        translate([-r, r]) circle(r = r);
        translate([ r, r]) circle(r = r);
        rotate(45) square(2*r, center = true);
    }
}

// Belly heart, standing proud of the front skin, straddling X=0. A point-DOWN
// heart prism in the X-Z plane, centred at the belly front so ~heart_proud of it
// protrudes (in front of the cheeks) and the rest embeds into the body — the
// heart the hamster cradles. rotate([90,0,0]) gives point-down, extruding −Y.
module belly_heart() {
    L = 2 * heart_proud + 6;              // proud + embedded depth
    translate([0, -(belly_front - (L/2 - heart_proud)), heart_cz*S])
        rotate([90, 0, 0])
            linear_extrude(L, center = true) heart2d(heart_w);
}

// Heart-shaped ring-nest cavity straddling the seam (in X-Z), extruded through Y
// but kept blind (inside the skin) so the closed box holds the ring.
module nest_cavity() {
    translate([0, heart_cy*S, heart_cz*S])
        rotate([90, 0, 0])
            linear_extrude(nest_depth*2, center = true) heart2d(nest_w);
}

// The whole hamster solid with the heart features, before splitting.
module hamster() {
    difference() {
        union() { blob(); belly_heart(); }
        if (nest_on) nest_cavity();
    }
}

// One half: side=-1 (left, x<=-gg) / +1 (right, x>=+gg). gg = half the parting
// gap; the fitcheck negative control passes gg<0 so the halves overlap.
g = part_gap/2;
// Clip cubes are kept TIGHT (not 600 mm) on purpose: OpenSCAD's preview
// `--viewall` frames the pre-CSG bounding box, so oversized clip cubes shrink
// the rendered part to a dot (and would wreck the committed preview).
module half_solid(side, gg = g) {
    intersection() {
        hamster();
        if (side < 0) translate([-60-gg, -35, -2]) cube([60, 65, 67]);
        else          translate([ gg,     -35, -2]) cube([60, 65, 67]);
    }
}

// A half laid FLAT on the bed (native print pose): the assembled half rotated so
// its dorsal seam edge sits on the fold axis (x=0, z=0) and its cut face lies on
// the bed (z=0), dome up. Left splays −X, right +X. `hz` is the fold-axis height
// (pre-scale): the production default `hinge_z` clears the top so the halves
// don't weld; the welded controls pass `fused_hz` to reproduce the v0.1 bug.
module half_flat(side, gg = g, hz = hinge_z) {
    rotate([0, side < 0 ? 90 : -90, 0])
        translate([0, 0, -hz*S])
            half_solid(side, gg);
}

// Living-hinge web: thin flexure bridging the two halves at the dorsal seam,
// on the bed fold line (x=0, z=0). Drawn flat (print pose); like
// snap-clamshell-box it is not folded in the preview.
module hinge_web() {
    translate([-(g + web_ov), -web_len/2, 0])
        cube([2*(g + web_ov), web_len, web_t]);
}

// Place a half at the given fold about the bed hinge line (x=0, z=0, axis Y):
// fold=0 = FLAT print pose (default), fold=90 = folded up to assembled. `hz`
// selects the fold-axis height (production default, or fused_hz for a control).
module place(side, f, gg = g, hz = hinge_z) {
    rotate([0, side < 0 ? -f : f, 0]) half_flat(side, gg, hz);
}

// ===========================================================================
module model() {
    place(-1, fold);
    place( 1, fold);
    // The web is drawn flat (not folded); show it in the print pose and while
    // opening, but hide it in the near-closed preview so the hero isn't marred
    // by a flat tab across the dorsal seam.
    if (fold < 60) hinge_web();
}

// --- part dispatch (ci.fitchecks + ci.fusecheck) --------------------------
if (part == "" || part == undef) {
    model();
} else if (part == "fitcheck") {
    // FLAT (printed) pose — the pose CI actually slices: do the two half-bodies
    // overlap where they shouldn't? Must be EMPTY. v0.1 tested the CLOSED pose
    // (fold=90) here, which is exactly why the flat-pose weld shipped green.
    intersection() { place(-1, 0); place(1, 0); }
} else if (part == "fitcheck_neg") {
    // The v0.1 welded flat pose (fold axis dropped below the top): the halves
    // overlap, so the intersection INTERFERES — proving the empty check above
    // can actually fail.
    intersection() { place(-1, 0, g, fused_hz); place(1, 0, g, fused_hz); }
} else if (part == "fused") {
    // The v0.1 WELD as one solid — both halves plus the web at the low fold
    // axis. fusecheck's negative control: removing the web AABB still leaves
    // ONE connected body, because the halves weld to each other beyond the web.
    // This is what shipped in v0.1; it proves fusecheck can fire.
    place(-1, 0, g, fused_hz);
    place( 1, 0, g, fused_hz);
    hinge_web();
} else {
    assert(false, str("unknown part: ", part));
}
