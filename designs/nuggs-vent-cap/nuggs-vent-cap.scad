// N.U.G.G.S. vent cap — a breathing end-cap: the standard quarter-turn port
// face closed by a support-free lattice dome. Air and light pass, bedding
// stays, the animal cannot. Design brief: issue #592. Requirements, welfare
// numbers and decisions: see NOTES.md next to this file. All dimensions in
// millimeters.
//
// WHY THIS MODULE EXISTS (charter N3, designs/nuggs/PM.md): ventilation is a
// welfare feature — ammonia and CO2 build up in enclosed runs — and the
// ecosystem had no way to terminate a run while it breathes. Today an owner
// seals a tube dead (solid cap = stale air) or leaves it open (the animal
// exits). This is the third option: an ENCLOSED end that breathes. It does not
// break a run the way nuggs-open does — air passes, the animal cannot — so it
// is still an end for the run-length rule, not a break.
//
// THE DOME, AND THE ARITHMETIC THAT SHAPES IT. The design problem is closing
// an 80 mm bore with no slicer supports (docs/advanced-techniques.md, "Self-
// supporting substitution": flat ceiling -> cone/dome at <=45 deg). The rule
// behind that doctrine is an integral one: a support-free surface must climb
// at least 45 deg, so closing radius dr costs rise dz >= dr — a CONTINUOUS
// support-free closure of the full bore needs >= 40 mm of rise, and the brief's
// cap-length budget (~40 mm port face to dome tip, port zone already 13 of it)
// does not contain 40. So the closure is the brief's other option: "a woven
// lattice whose strands each bridge onto the previous ring". The dome is a
// 45 deg conical shell — support-free wherever it is continuous, and exactly
// at the printcheck threshold, never beyond — cut into a grid of strands
// running down from the wall rim to a crown disc that bridges the last hole.
// Every strand is 1.2 mm wide, so every overhanging underside is narrower than
// printcheck's 5 mm bridgeable bound by construction; the longest unsupported
// bridge in the whole part is the crown disc's radial strand, ~10 mm — same
// territory as the turnaround's accepted 12.2 mm web span. Physics puts the
// crown hole there (rise 28 closes 28 of radius, leaving r = 12); the lattice
// is what makes the closure printable inside the length budget.
//
// THE PORT. One face of the standard genderless coupling, taken bore-clean
// from the library: nuggs_neck() at its minimum length (the port zone z_top),
// because the dome springs straight off the full-round ring the port's inner
// sectors fuse to. Every coupling number is nuggs_cfg()'s default — the
// standard's, not this design's — so the cap clicks into every existing
// module. port_tol stays a tunable parameter and is UNMEASURED (the library
// header's own warning): the coupon is mandatory, see NOTES.md "Print this
// first".
//
// PRINT. Port-axis vertical, standing on the sector tips — the family
// bed-contact idiom (the dome rises from the bed, nothing ever prints over
// void except the bridges named above). PLA or PETG, no supports, no brim.

use <nuggs-coupling.scad>

/* [What to render] */
// vent-cap = the printable lattice cap; vent-cap-solid = the closed variant
// (lattice=false, taller by physics); coupon = print-this-first stub;
// cutaway = section on the port-axis plane; mates / mates-ctrl / bore-clean =
// the ci.fitchecks booleans (never printed)
part = "vent-cap";  // [vent-cap, vent-cap-solid, coupon, cutaway, mates, mates-ctrl, bore-clean]

/* [The NUGGS standard - change these and nothing you already printed fits] */
// Every value here is a nuggs_cfg() default: this module inherits the standard
// so it mates with designs/nuggs and every other module. Exposed for the
// Customizer, not for tuning — the coupling guards fire inside nuggs_cfg().
// Internal bore (mm) — the headline number. Asserted >= min_bore_mm by the lib
bore_d = 80.0;
// Tube shell thickness (mm). ro = bore_d/2 + wall is the datum every coupling
// radius is measured from — and the dome's seating ring buries in it
wall = 2.4;
// Radial depth of the coupling ring beyond the tube OD (mm)
lug_r = 6.0;
// Axial projection of the coupling sectors past the tube face (mm)
port_proj = 10.0;
// Backing-collar thickness (mm)
collar_t = 3.0;
// Sectors per port face (3 is kinematically determinate)
n_lug = 3;
// THE fit knob, mm, everywhere. UNMEASURED on any printer — tune on the
// coupon in +/-0.05 steps before trusting the cap (lib header's own warning)
port_tol = 0.30;

/* [The lattice dome] */
// Largest passage through the lattice (mm) — THE welfare number, the 1/4"
// hardware-cloth convention for small-animal enclosures. It is an ASSUMED
// ceiling (see the brief): 6.0 suits a Syrian; dwarf keepers want 5.0. The
// assert holds the ceiling; raising it un-escape-proofs the cap.
aperture_max = 6.0;
// Lattice strand width (mm). >= 1.2: three perimeters at a 0.4 mm nozzle, the
// repo wall floor — the strands are the dome's whole structure
strand_w = 1.2;
// Dome rise above the port zone (mm). Closes dome_rise of radius at 45 deg;
// the rest of the bore is the crown disc's bridge, so this knob IS the
// trade between cap length and how much hole the crown bridges
dome_rise = 28.0;
// Smallest share of the cap face that may be open (fraction). The brief's
// flow target: the lattice, not the strands, must never be the bottleneck.
// Asserted on the derived cell geometry, so it fails loudly if a knob pairing
// chokes the vent
open_area_min = 0.30;
// false = the brief's solid variant: a continuous <=45 deg cone, support-free
// by the same doctrine but taller — rise >= radius means it cannot close 40 mm
// of bore inside this cap's length budget, so it ends where the geometry puts
// it (~54 mm), not where the lattice cap does
lattice = true;

/* [Quality] */
// Visible cylinders (the dome's cone faces, the crown disc). The coupling
// pins its own tessellation inside the library and ignores this
$fn = 96;  // production; drop to 32 while iterating

// ---------------------------------------------------------------------------
// Derived geometry — the 45 deg dome, in one line of algebra
//
// Both dome surfaces are lines of constant r + z (45 deg in the r-z plane):
// the underside passes exactly through the bore's top edge (ri, z_top) so the
// mouth is exactly the bore — the passage never narrows at the lip — and the
// outer face is the same line pushed out by the perpendicular shell thickness.
// z_spring is where the outer line meets the wall OD: below z_top, so the
// dome's seating ring buries INSIDE the wall band and fuses to it instead of
// kissing its top face.
// ---------------------------------------------------------------------------
ri          = nuggs_ri(cfg_d());
ro          = nuggs_ro(cfg_d());
z_top       = nuggs_z_top(cfg_d());
dome_c_in   = ri + z_top;                        // underside: r + z = 53
dome_c_out  = dome_c_in + strand_w * sqrt(2);    // outer face, 45 deg offset
z_spring    = dome_c_out - ro;                   // seating ring's underside
dome_top_z  = z_top + dome_rise;                 // the dome tip = the cap length
r_crown_out = dome_c_out - dome_top_z;           // cone's outer radius at the tip
r_crown_in  = dome_c_in - dome_top_z;            // the crown hole the disc bridges

// On-surface cell pitch: slope-direction openings are vertical bands of
// strand_w on a 45 deg face, so the vertical pitch is stretched by sqrt(2)
slope_pitch = aperture_max + strand_w;
pitch_v     = aperture_max / sqrt(2) + strand_w;
// Rib count: tangential openings are worst at the widest circumference the
// grid crosses — the spring rim's outer face
r_lattice_max = ri + strand_w * sqrt(2);
n_rib       = ceil(2 * PI * r_lattice_max / slope_pitch);
// Crown grid: radial spokes every chord <= aperture_max at the rim
n_web       = ceil(180 / asin(min(0.999, aperture_max / (2 * r_crown_out))));

// ---------------------------------------------------------------------------
// Design asserts — the welfare numbers and the dome's own sanity, stated at
// the parameters that break them (the coupling's guards live in nuggs_cfg()).
// ---------------------------------------------------------------------------
assert(aperture_max <= 6.0, str(
    "VENT CAP APERTURE: aperture_max = ", aperture_max, " mm is over the 6.0 mm",
    " welfare ceiling — the 1/4 inch hardware-cloth convention the brief",
    " assumes. Above it the cap stops being escape-proof and starts being",
    " decor. Dwarf keepers: set 5.0. Raising it is a welfare decision, not a",
    " tuning one."));
assert(aperture_max >= 3.0, str(
    "VENT CAP APERTURE: aperture_max = ", aperture_max, " mm is under 3.0 mm —",
    " below that the lattice is a solid in disguise and the cap stops",
    " ventilating, which is the one thing it exists to do."));
assert(strand_w >= 1.2, str(
    "VENT CAP STRAND: strand_w = ", strand_w, " mm is under the 1.2 mm floor",
    " (three perimeters at a 0.4 mm nozzle). The strands are the dome's whole",
    " structure; a thinner strand prints as spaghetti."));
assert(wall > strand_w * sqrt(2), str(
    "VENT CAP SEATING: wall = ", wall, " mm must exceed strand_w*sqrt(2) = ",
    strand_w * sqrt(2), " mm, or the dome's outer line meets the wall OD at or",
    " above z_top and the seating ring has no wall band to bury in — the dome",
    " would balance on an edge, not fuse to the tube."));
assert(dome_rise >= ri - 13, str(
    "VENT CAP RISE: dome_rise = ", dome_rise, " mm closes only that much",
    " radius at 45 deg, leaving a crown hole of radius ", r_crown_in,
    " mm for the crown disc to bridge. Over a 13 mm crown radius the disc's",
    " radial strands span past ~10 mm of unsupported bridge — beyond the",
    " turnaround's accepted 12.2 mm web precedent. Raise dome_rise (a taller",
    " cap) or accept a riskier bridge (a welfare-relevant failure: a sagging",
    " crown narrows apertures unpredictably)."));
assert(dome_rise < ri, str(
    "VENT CAP RISE: dome_rise = ", dome_rise, " mm reaches the dome axis — the",
    " cone closes to a point and the crown disc has no hole to fill. It would",
    " render, but the cap length claim and the crown geometry both lie."));
assert(aperture_max * aperture_max / (slope_pitch * slope_pitch) >= open_area_min,
    str(
    "VENT CAP OPEN AREA: the derived on-slope cell fraction is ",
    aperture_max * aperture_max / (slope_pitch * slope_pitch), ", under the ",
    open_area_min, " floor the brief sets for flow — the lattice, not the",
    " strands, must never be the bottleneck. Widen aperture_max (within the",
    " welfare ceiling) or thin strand_w (within the FDM floor)."));

function cfg_d() =
    nuggs_cfg(bore_d = bore_d, wall = wall, lug_r = lug_r,
              port_proj = port_proj, collar_t = collar_t, n_lug = n_lug,
              port_tol = port_tol);

// ---------------------------------------------------------------------------
// Geometry
// ---------------------------------------------------------------------------

// The 45 deg conical shell: outer solid minus inner solid, both bounded by
// their r+z lines. The seating ring [r_in(z_spring), ro] at [z_spring, z_top)
// is inside the wall band and buries there; the underside meets the bore
// exactly at (ri, z_top).
module dome_shell() {
    difference() {
        rotate_extrude()
            polygon([[0, z_spring], [ro, z_spring],
                     [r_crown_out, dome_top_z], [0, dome_top_z]]);
        rotate_extrude()
            polygon([[0, z_spring], [dome_c_in - z_spring, z_spring],
                     [r_crown_in, dome_top_z], [0, dome_top_z]]);
    }
}
// (the cut solid's bottom edge is r = dome_c_in - z_spring, in from the
// outer line's ro, so the difference leaves a solid annulus at z_spring and
// never rides a zero-thickness bottom face)

// The dome's meridian slabs (vertical planes through the axis, strand_w wide)
// and latitude bands (horizontal slabs, pitch_v apart so the on-slope opening
// between bands is aperture_max). Intersected with the shell they leave the
// woven cone: ribs that climb at 45 deg and bands that tie them.
module dome_grid() {
    union() {
        for (i = [0 : n_rib - 1])
            rotate([0, 0, i * 360 / n_rib])
                translate([-strand_w / 2, -(ro + 2), z_spring - 1])
                    cube([strand_w, 2 * (ro + 2), dome_top_z - z_spring + 2]);
        for (k = [0 : floor((dome_top_z - z_spring) / pitch_v)])
            translate([-ro - 2, -ro - 2, z_spring + k * pitch_v])
                cube([2 * ro + 4, 2 * ro + 4, strand_w]);
    }
}

// The crown disc: bridges the hole the 45 deg rise leaves (r < r_crown_in),
// latticed with the same grammar — radial spokes chord-bounded by
// aperture_max, concentric bands every slope_pitch. Its strand undersides are
// the same 1.2 mm bridgeable strips; its longest unsupported run is a radial
// spoke from the rim band to the natural hub where the spokes cross.
module crown_disc() {
    intersection() {
        translate([0, 0, dome_top_z - strand_w])
            cylinder(r = r_crown_out, h = strand_w);
        union() {
            for (i = [0 : n_web - 1])
                rotate([0, 0, i * 360 / n_web])
                    translate([-strand_w / 2, -r_crown_out - 1, dome_top_z - strand_w - 1])
                        cube([strand_w, 2 * r_crown_out + 2, strand_w + 2]);
            for (j = [0 : floor((r_crown_out - strand_w / 2) / slope_pitch)])
                translate([0, 0, dome_top_z - strand_w / 2])
                    difference() {
                        cylinder(r = r_crown_out - j * slope_pitch + strand_w / 2,
                                 h = strand_w + 2, center = true);
                        translate([0, 0, -1])
                            cylinder(r = r_crown_out - j * slope_pitch - strand_w / 2,
                                     h = strand_w + 4, center = true);
                    }
        }
    }
}

// The vent cap: the library's bore-clean neck (port + full-round shell + the
// mandatory bore cut) at its minimum length, plus the dome. The shell springs
// straight off the full-round ring the port's inner sectors fuse to.
// lattice_on defaults from the top-level `lattice` so the part="vent-cap-solid"
// dispatch below can pass false — a module cannot see a caller's local
// assignment, only an explicit argument (the nuggs.scad coupon lesson).
module vent_cap(lattice_on = lattice) {
    union() {
        nuggs_neck(cfg_d(), z_top);
        if (lattice_on) {
            intersection() { dome_shell(); dome_grid(); }
            crown_disc();
        } else {
            // The solid variant: the same 45 deg cone run all the way to the
            // axis. Support-free like the lattice shell — more blocked, no
            // crown bridge — and taller, because rise >= radius (see header).
            rotate_extrude()
                polygon([[0, z_spring], [ro, z_spring],
                         [0, z_spring + ro]]);
        }
    }
}

// Section on the port-axis plane (y < 0 removed): port zone, seating ring,
// the 45 deg lattice falling off the wall, and the crown disc bridging.
module cap_cutaway() {
    difference() {
        vent_cap();
        translate([0, -300, -100]) cube([300, 300, 400]);
    }
}

// ---------------------------------------------------------------------------
// Print-this-first coupon: the production port stub (every NUGGS module tunes
// port_tol on it) beside a flat gauge of the dome's own cell, at production
// pitch. Caliper the gauge's strands (strand_w) and openings (<= aperture_max)
// before committing to the full cap; the dome's print behaviour itself is
// printcheck's and the test-slice's to gate. See NOTES.md "Print this first".
// ---------------------------------------------------------------------------
module lattice_gauge() {
    intersection() {
        cylinder(r = 3.5 * slope_pitch, h = strand_w);
        union() {
            for (i = [0 : n_rib - 1])
                rotate([0, 0, i * 360 / n_rib])
                    translate([-strand_w / 2, -4 * slope_pitch, -1])
                        cube([strand_w, 8 * slope_pitch, strand_w + 2]);
            for (j = [0 : 3])
                difference() {
                    cylinder(r = strand_w / 2 + j * slope_pitch,
                             h = strand_w + 2, center = true);
                    translate([0, 0, -1])
                        cylinder(r = -strand_w / 2 + j * slope_pitch,
                                 h = strand_w + 4, center = true);
                }
        }
    }
}

module vent_cap_coupon() {
    translate([-(r_crown_out + 6 + ro), 0, 0]) nuggs_neck(cfg_d(), z_top + 8);
    translate([r_crown_out + 6 + ro, 0, 0]) lattice_gauge();
}

// ---------------------------------------------------------------------------
// Fitchecks (ci.fitchecks) — the mated proof. The mate is the library's own
// neck, mirrored so its sectors face the cap's, clocked by
// nuggs_clockings() — never a hardcoded angle — and pulled 0.01 mm: the seat
// and the tube face are both zero-clearance stops, and at pull = 0 the pair
// shares whole faces (the lib manifest measured 1466 zero-volume facets of
// exactly that). 0.01 mm is a fortieth of a layer; it separates coincident
// planes and nothing else.
// ---------------------------------------------------------------------------

// Insertion: the cap must ACCEPT the module — the pose that has to be free to
// come together. Empty = the port is the standard's.
module fit_mates() {
    intersection() {
        vent_cap();
        translate([0, 0, -0.01])
            rotate([0, 0, nuggs_clockings(cfg_d())[0]])
                mirror([0, 0, 1]) nuggs_neck(cfg_d(), 30);
    }
}

// The mandatory negative control: clocked at 0 instead of half a pitch, outer
// shell lands on outer shell at the same radii — grossly interfering (the lib
// manifest measured 9346 mm3 for the same mis-clocking). If this ever renders
// empty, the check above proves nothing.
module fit_mates_ctrl() {
    intersection() {
        vent_cap();
        translate([0, 0, -0.01])
            rotate([0, 0, 0])
                mirror([0, 0, 1]) nuggs_neck(cfg_d(), 30);
    }
}

// The bore-clean probe: a cylinder inset 0.5 mm from ri through the THROAT
// (z_tip .. z_top, the bore the coupling contract is about) must find nothing —
// the neck's cut ran and no cutter leaked material into the passage. Scoped to
// the throat on purpose: above z_top the dome fills the bore BY DESIGN, so a
// whole-cap probe would fail on the feature, not the defect.
module fit_bore_clean() {
    intersection() {
        vent_cap();
        translate([0, 0, (nuggs_z_tip(cfg_d()) + z_top) / 2])
            cylinder(r = ri - 0.5, h = z_top - nuggs_z_tip(cfg_d()), center = true);
    }
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------

if (part == "vent-cap") vent_cap();
else if (part == "vent-cap-solid") vent_cap(lattice_on = false);
else if (part == "coupon") vent_cap_coupon();
else if (part == "cutaway") cap_cutaway();
else if (part == "mates") fit_mates();
else if (part == "mates-ctrl") fit_mates_ctrl();
else if (part == "bore-clean") fit_bore_clean();
else assert(false, str("unknown part: ", part));
