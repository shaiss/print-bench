// pip-planetary — a print-in-place planetary (epicyclic) gear set: sun, three
// planets and an internal ring, all printed as ONE assembled part. Turn the
// sun's crank; the carrier walks round at 5:1. The catalog's first toothed-gear
// design (docs/advanced-techniques.md Domain 3 "Gears & rotary").
//
// KINEMATICS (Willis; ring fixed, sun input, carrier output — the brief's
// stated mechanism): Zs=12, Zp=18, Zr=48 → ratio 1 + Zr/Zs = 1 + 48/12 = 5:1.
// (The brief's table labelled this expression "4:1"; the expression evaluates
// to 5 and the amendment on the issue thread keeps the counts, ships 5:1.)
// Assembly conditions hold: Zr = Zs + 2·Zp → 48 = 12+36 ✓, and
// (Zs+Zr)/N = 60/3 = 20 integer ✓ — so three planets space at exactly 120°
// and all three mesh sun and ring simultaneously.
//
// MESH PHASING — the alignment constraint a slider never exercises. With gear
// centers on the line of centers, the tooth phases must interleave at BOTH
// meshes of every planet at once. Empirically calibrated against BOSL2's
// profile origin (rendered intersections, zero-interference facets):
//   sun gear_spin 15° (half its 30° pitch), planet 10° (half its 20°), ring 0°.
// The analytic form: sun σ = 15 + 5θ, planet π = 10 − (5/3)θ at carrier angle
// θ — a planet's phase locus vs the sun's has slope −Zs/Zp·(Zs+Zr)/Zr = −2/3
// per the external counter-rotating mesh (verified: σ=7.5/π=15 renders clean,
// σ=7.5/π=5 collides). A wrong phase still renders watertight and slices —
// that is the silent failure the `fitcheck` and `fitcheck_phase` gates exist
// to catch (see ci.fitchecks).
//
// BACKLASH is TOOTH THINNING (BOSL2 backlash=, 0.125 per gear = 0.25 total in
// the mesh), never center-distance: a planet meshes the sun outside and the
// ring inside at one fixed 30 mm axis radius, so growing the center distance
// opens one mesh by exactly what it closes the other. Center distance stays
// exact at 30.00 (amendment 2 on the issue thread).
//
// STACKUP (bottom-up, all gaps whole layers per Domain 3):
//   base 3.0 | gap 0.4 | carrier 3.2 — a FULL DISC under the planets' whole
//   tip sweep, the pins rising from it | gap 0.4 | gears 12.0 | gap 0.4 |
//   lip 2.4 (annulus, 45-degree chamfered underside) over the planet tips |
//   crank above. The carrier sits BELOW the planets so its pins print as
//   supported towers, never overhangs; the top stays open so the walking
//   train is visible. Captivity: planets ↔ lip (up) / carrier (down) /
//   meshes (radial); sun ↔ capped post; carrier ↔ base (down) / post (radial).
//
// All dimensions in millimeters.

use <printability.scad>
include <BOSL2/std.scad>
include <BOSL2/gears.scad>

/* [Gear train] */
// Gear module (mm) — tooth size; 2.0 → 4.5 mm tooth depth ≈ 11 extrusion widths
gear_module = 2.0;
// Sun teeth
Z_sun = 12;
// Planet teeth
Z_planet = 18;
// Ring teeth (internal, cut into the housing wall)
Z_ring = 48;
// Planets, spaced 360/N apart (must divide Z_sun+Z_ring for assembly)
N_planets = 3;
// Gear face width (mm)
face_w = 12;
// Tooth-thinning backlash per gear (mm); total mesh backlash is 2x this
backlash_gear = 0.125;

/* [Fit & tolerances] */
// Diametral pin clearance (mm) — carrier pin in planet bore; tune on coupon
pin_diam_clear = 0.4;
// Diametral post/bore clearance (mm) — sun bore & carrier hub on the post
post_diam_clear = 0.4;
// Axial gaps, in WHOLE 0.2 mm layers (sag-limited: 2 layers everywhere)
z_gap_layers = 2;
// Layer height the axial gaps snap to (mm)
layer_h = 0.2;

/* [Sun input crank] */
// Crank arm radius to the pin centre (mm)
crank_r = 14;
// Crank pin diameter (mm)
crank_pin_d = 7;

/* [Structure] */
// Housing wall thickness outside the ring teeth (mm)
housing_wall = 4.5;
// Base plate thickness (mm)
base_t = 3.0;
// Carrier plate thickness (mm)
carrier_t = 3.2;
// Housing lip thickness over the planet tips (mm)
lip_t = 2.4;
// 45-degree chamfer on the lip underside and bed-contact edge (mm)
chamfer = 0.8;

/* [Quality] */
// Iterating: 48. Production: 96 (involute teeth and captive bores are
// $fn-sensitive; the mate check renders at 96)
$fn = 96;

// ---- derived ------------------------------------------------------------
z_gap  = z_gap_layers * layer_h;   // 0.4 axial gap, whole layers
mod    = gear_module;
rps    = Z_sun    * mod / 2;       // sun pitch radius   = 12
rpp    = Z_planet * mod / 2;       // planet pitch radius = 18
rpr    = Z_ring   * mod / 2;       // ring pitch radius   = 48
cd     = rps + rpp;                // sun-planet center distance = 30
                                  // (= rpr - rpp: one axis circle serves both meshes)
r_sun_tip  = outer_radius(mod=mod, teeth=Z_sun);
r_pl_tip   = outer_radius(mod=mod, teeth=Z_planet);
// BOSL2 names internal-gear radii by EXTENT, not tooth feature: for
// internal=true the ROOT radius (46) is the innermost extent = the tooth TIPS
// circle, and the OUTER radius (50.5) is the outermost = the tooth ROOTS.
// The wall's inner face must sit at the tooth roots (50.5) so the teeth exist.
r_ring_tip  = root_radius(mod=mod, teeth=Z_ring, internal=true);   // 46, inward
r_ring_root = outer_radius(mod=mod, teeth=Z_ring, internal=true);  // 50.5, outward
housing_ir  = r_ring_root;          // wall inner face = ring tooth roots
housing_or  = housing_ir + housing_wall;                            // 55

// mesh phases at carrier angle 0 — calibrated, see header
PH_SUN0   = 15;
PH_PLANET = 10;
PH_RING   = 0;

// pins & post
pin_d  = 6;                        // carrier pin diameter
pin_r  = pin_d / 2;
bore_d = pin_d + pin_diam_clear;   // planet bore
post_d = 8;                        // fixed central post
sun_bore_d   = post_d + post_diam_clear;
carrier_hub_od = 14;
carrier_hub_id = post_d + post_diam_clear;
crank_tube_od = 10;                // sun shaft extension, over the post
crank_tube_id = sun_bore_d;

// Z stack
z_base1     = base_t;
z_carrier0  = z_base1 + z_gap;
z_carrier1  = z_carrier0 + carrier_t;
z_gear0     = z_carrier1 + z_gap;
z_gear1     = z_gear0 + face_w;
z_lip0      = z_gear1 + z_gap;     // planets float this below the lip
z_lip1      = z_lip0 + lip_t;
z_wall_top  = z_lip1;

// crank (sits above the open top; clears the gear tops by 2.4 so its bridge
// cannot sag onto the teeth)
z_arm0      = z_gear1 + 2.4;
z_arm1      = z_arm0 + 2.4;
z_tube_top  = z_arm1;
cap_play    = z_gap;               // axial play of the sun under the post cap
z_cap0      = z_tube_top + cap_play;
cap_d       = crank_tube_od - 0.4; // overhangs the bore rim (bore d 8.4)
z_cap1      = z_cap0 + 0.8;        // cap disc top
z_crank_top = z_arm1 + 8;

pin_len   = z_gear1 - 0.4 - z_carrier1;  // pin tip 0.4 under the bore ceiling
// the carrier is a FULL DISC out to the planets' tip sweep (r 50): every
// square mm of a planet's underside prints 0.4 over carrier material, never
// over the 3.6 mm void above the base — spokes would hang the outer teeth in air
carrier_or = cd + r_pl_tip;
lip_ir     = carrier_or - 2.5;           // lip overlaps 2.5 mm of every planet's tips

// ---- guards -------------------------------------------------------------
module guards() {
    assert(Z_ring == Z_sun + 2 * Z_planet,
        "planetary assembly condition Zr = Zs + 2*Zp violated");
    assert((Z_sun + Z_ring) % N_planets == 0,
        "(Zs+Zr)/N must be an integer for planets to mesh at once");
    assert(pin_diam_clear >= 0.25 && pin_diam_clear <= 0.8,
        "pin clearance outside the printable PIP range");
    assert(z_gap >= layer_h, "axial gap below one layer");
    assert(gear_module >= 2.0, "module below 2 makes sub-line-width teeth");
    assert(backlash_gear > 0 && backlash_gear <= 0.3,
        "per-gear backlash outside the FDM range");
}

// ---- gear bodies (each is one rotating assembly) -------------------------
module sun_gear(spin = PH_SUN0) {
    // gear + bore over the post + crank tube + arm + pin, one body. The gear
    // body sits at the gear stratum z_gear0 (same as the planets); the crank
    // tube/arm/pin above it use absolute z from the stackup.
    difference() {
        union() {
            translate([0, 0, z_gear0 + face_w / 2])   // BOSL2 gears anchor CENTER
                spur_gear(mod=mod, teeth=Z_sun, thickness=face_w,
                      profile_shift=0, backlash=backlash_gear,
                      gear_spin=spin);
            // crank tube: the sun's shaft extension, over the post
            translate([0, 0, z_gear1])
                cylinder(d = crank_tube_od, h = z_tube_top - z_gear1);
            // crank arm + pin
            translate([0, 0, z_arm0])
                hull() {
                    cylinder(d = crank_tube_od, h = 2.4);
                    translate([crank_r, 0, 0]) cylinder(d = crank_pin_d, h = 2.4);
                }
            translate([crank_r, 0, z_arm1])
                cylinder(d = crank_pin_d, h = z_crank_top - z_arm1);
        }
        // bore over the fixed post, through gear and tube
        translate([0, 0, z_gear0 - 0.01])
            cylinder(d = crank_tube_id, h = z_tube_top - z_gear0 + 0.02);
    }
}

module planet_gear(spin = PH_PLANET) {
    difference() {
        spur_gear(mod=mod, teeth=Z_planet, thickness=face_w,
                  profile_shift=0, backlash=backlash_gear, gear_spin=spin);
        // the gear body is CENTER-anchored (local z −face_w/2..+face_w/2): the
        // bore must span that whole band, so start at −face_w/2, not at 0 —
        // a bore from 0 cuts only the upper half and leaves a solid core in
        // the lower (the printbed-side) half
        translate([0, 0, -face_w / 2 - 0.01])
            cylinder(d = bore_d, h = face_w + 0.02);
    }
}

module planet_at(k, spin = PH_PLANET) {
    rotate([0, 0, 120 * k])
        translate([cd, 0, z_gear0 + face_w / 2])   // BOSL2 gears anchor CENTER
            planet_gear(spin);
}

// the revolving carrier: a full disc under the whole planet tip sweep (that is
// the printability point — every planet's first layer prints over carrier
// material 2 layers below, never over air), a hub sleeve riding the fixed
// post, and the three pins rising from the disc into the planet bores.
module carrier() {
    difference() {
        union() {
            // full disc out to the planets' tip sweep
            translate([0, 0, z_carrier0])
                cylinder(d = 2 * carrier_or, h = carrier_t);
            for (k = [0 : N_planets - 1])
                rotate([0, 0, 120 * k])
                    // the pin: a supported tower into the planet bore
                    translate([cd, 0, z_carrier1 - 0.01])
                        cylinder(d = pin_d, h = pin_len + 0.02);
        }
        // hub bore: the carrier rides on the fixed post
        translate([0, 0, z_carrier0 - 0.01])
            cylinder(d = carrier_hub_id, h = carrier_t + 0.02);
    }
}

// ---- fixed housing: base + wall with internal teeth + chamfered lip ------
// THE RING TEETH EXIST ONLY IF THE CUTTER BITES. The internal gear cutter's
// profile spans r_ring_tip (46) out to r_ring_root (50.5); if the wall's inner
// face were already bored at 50.5 the cut would intersect nothing and the
// planets would mesh air (the calibration rig proved the phases against an
// annulus reaching INWARD past 46 — the housing must present material there
// too). So: the cavity is bored at the ROOT radius above and below the gear
// stratum only, and across the stratum itself the tooth cutter alone carves
// the face — teeth point inward from 50.5 to 46 exactly where the planets run.
module housing() {
    union() {
        difference() {
            // base plate + outer wall, one solid cylinder up to the lip top
            translate([0, 0, 0])
                cylinder(d = 2 * housing_or, h = z_wall_top);
            // cavity above the gear stratum: wall face at the ring root
            translate([0, 0, z_gear1 - 0.01])
                cylinder(d = 2 * housing_ir, h = z_wall_top - z_gear1 + 0.02);
            // cavity below the gear stratum, above the solid base floor
            translate([0, 0, base_t - 0.01])
                cylinder(d = 2 * housing_ir, h = z_gear0 - base_t + 0.02);
            // the gear stratum itself: the tooth cutter alone carves the wall
            // face — material must reach inward past the tooth tips (r 46)
            // before the cut, so the teeth exist (see module header)
            translate([0, 0, z_gear0 + face_w / 2])  // BOSL2 gears anchor CENTER
                spur_gear(mod=mod, teeth=Z_ring, thickness=face_w,
                          profile_shift=0, backlash=backlash_gear,
                          gear_spin=PH_RING, internal=true);
        }
        // lip: an ANNULUS fused to the wall (it reaches housing_or, not just
        // past the root), 45-degree chamfered underside over the planet tips
        // so the capturing overhang self-supports. Inner radius overlaps every
        // planet's tip arc by 2.5 mm without nearing the sun (tip r 14).
        difference() {
            translate([0, 0, z_lip0 + chamfer])
                cylinder(d = 2 * housing_or, h = lip_t - chamfer);
            translate([0, 0, z_lip0 - 0.01])
                cylinder(d = 2 * lip_ir, h = lip_t + 0.02);
        }
        // chamfered lip underside: material grows from zero at the inner edge
        translate([0, 0, z_lip0])
            rotate_extrude()
                polygon([[lip_ir, 0], [lip_ir + chamfer, 0],
                         [lip_ir + chamfer, chamfer]]);
        // the fixed post + its cap (printed as part of the housing)
        post();
    }
}

module post() {
    // central post: carrier bearing (low) and sun bearing (full height),
    // capped above the crank tube rim to capture the sun axially
    translate([0, 0, base_t - 0.01])
        cylinder(d = post_d, h = z_cap0 - base_t + 0.01);
    // 45-degree chamfered cap (self-supporting overhang)
    translate([0, 0, z_cap0])
        cylinder(d1 = post_d, d2 = cap_d, h = 0.4);
    translate([0, 0, z_cap0 + 0.4])
        cylinder(d = cap_d, h = z_cap1 - z_cap0 - 0.4 + 0.01);
}

module assembly() {
    housing();
    carrier();
    sun_gear();
    for (k = [0 : N_planets - 1]) planet_at(k);
}

// ---- part dispatch ------------------------------------------------------
// "" = the assembled print. "coupon" = one pocket of the train (the tuned-fit
// coupon's geometry: sun + one planet + the ring segment they engage, cut to a
// wedge). "fitcheck" = union of pairwise intersections of every moving body
// (must render EMPTY). "fitcheck_neg" = pin clearance driven negative (must
// interfere). "fitcheck_phase" = sun phase typo'd to 0 (must interfere —
// proves the phasing constants are load-bearing).
part = "";

// wedge aperture for part="coupon": how much of the ring the coupon keeps.
// 0 = full ring (not a coupon); the coupon overrides this to a 100° pocket.
coupon_wedge_deg = 0;

module moving() {
    carrier();
    sun_gear();
    for (k = [0 : N_planets - 1]) planet_at(k);
}

module fixed_part() { housing(); }

// the tuned-fit coupon geometry: the full assembly intersected with a wedge
// (and with N_planets=1 via override) — one pocket of sun+planet+ring
module coupon_geom() {
    big = 4 * (housing_or + 1);
    intersection() {
        assembly();
        // a planar pie-slice of aperture coupon_wedge_deg about the +X axis
        // (two rotated half-spaces), centred on the planet at 0°
        intersection() {
            rotate([0, 0, -coupon_wedge_deg / 2])
                translate([-big / 2, 0, -1]) cube([big, big, z_crank_top + 2]);
            rotate([0, 0,  coupon_wedge_deg / 2])
                translate([-big / 2, -big, -1]) cube([big, big, z_crank_top + 2]);
        }
    }
}

module main() {
    guards();
    if (part == "coupon")
        coupon_geom();
    else if (part == "fitcheck") {
        // every moving body vs the fixed housing
        intersection() { moving(); fixed_part(); }
        // pairwise between moving bodies: sun vs each planet
        for (k = [0 : N_planets - 1])
            intersection() { sun_gear(); planet_at(k); }
        // planets vs each other
        for (k = [1 : N_planets - 1])
            intersection() { planet_at(0); planet_at(k); }
        // planets vs carrier (pins are in bores, arms clear the teeth)
        for (k = [0 : N_planets - 1])
            intersection() { carrier(); planet_at(k); }
        // sun vs carrier
        intersection() { sun_gear(); carrier(); }
    }
    else if (part == "fitcheck_neg")
        // the shrunken-bore planet must BITE the carrier's pin — the negative
        // control for the fitcheck's pin/bore pair
        intersection() {
            carrier();
            for (k = [0 : N_planets - 1])
                rotate([0, 0, 120 * k])
                    translate([cd, 0, z_gear0 + face_w / 2])
                        difference() {
                            spur_gear(mod=mod, teeth=Z_planet, thickness=face_w,
                                      profile_shift=0, backlash=backlash_gear,
                                      gear_spin=PH_PLANET);
                            translate([0, 0, -face_w / 2 - 0.01])
                                cylinder(d = pin_d - 0.6, h = face_w + 0.02);
                        }
        }
    else if (part == "fitcheck_phase")
        // the typo'd sun phase must COLLIDE with the planets — the negative
        // control for the fitcheck's mesh-phasing pair
        intersection() {
            sun_gear(spin = 0);
            for (k = [0 : N_planets - 1]) planet_at(k);
        }
    else
        assembly();
}

main();
