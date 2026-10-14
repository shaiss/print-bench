// N.U.G.G.S. sand sieve — a bathing-sand sieve end-cap for the 80 mm-bore
// system: a shallow open basket with a printed grid floor and one standard
// genderless quarter-turn port face on the underside. Pour used sand in the
// top, shake gently — clean grains fall through the grid and the open bore
// back into the bath below; debris stays in the basket. Design brief: issue
// #835. Requirements and decisions: NOTES.md. All dimensions in millimeters.
//
// WHY THIS MODULE EXISTS. The sand bath (#667 → PR #674) created the weekly
// sift-not-replace workflow with nothing to do the sifting. This is the
// filter body that workflow names. It is maintenance kit, not corridor —
// docking onto a bath mouth (or hand-held over a bin) does not break a run
// (NOTES.md, "Docking pose / run-length").
//
// THE PORT. One face of the standard genderless coupling, taken bore-clean
// from the library via nuggs_neck(). Every coupling number is nuggs_cfg()'s
// default. port_tol is UNMEASURED — the coupon is mandatory.
//
// THE GRID. An orthogonal web lattice (square openings) at hole_d / web_w —
// continuous 1.2 mm bars, not a disc minus a thousand cylinders (CGAL cost
// and thin-island risk). Round holes were considered; NOTES.md records why
// square won for v1. If printcheck flags the webs, hole_d steps to 1.2
// before any web drops below 1.2.
//
// PRINT. Port-axis vertical, standing on the sector tips, mouth up — the
// family pose. The flare from tube OD to basket OD runs at ≤45°, basket
// walls are vertical, the pour lip is a ≤45° chamfer. No slicer supports.

use <nuggs-coupling.scad>

/* [What to render] */
// sieve = the printable basket; coupon = port stub + grid tile; cutaway =
// section preview; mates / mates-ctrl = ci.fitchecks booleans; sandbody =
// basket interior solid (capacity measurement aid)
part = "sieve"; // [sieve, coupon, cutaway, mates, mates-ctrl, sandbody]

/* [The NUGGS standard - change these and nothing you already printed fits] */
NUGGS_PORT_REV = 1;
// Internal bore (mm) — the headline number
bore_d = 80.0;
// Tube shell thickness (mm)
wall = 2.4;
// Radial depth of the coupling ring beyond the tube OD (mm)
lug_r = 6.0;
// Axial projection of the coupling sectors past the tube face (mm)
port_proj = 10.0;
// Sectors per port face (3 = kinematically determinate)
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
// THE fit knob (mm). UNMEASURED — tune on the coupon in +/-0.05 steps
port_tol = 0.30;

/* [Basket] */
// Open top inner diameter (mm) — matches the sand-bath mouth (~110)
top_id = 110.0;
// Basket inside depth above the grid floor (mm)
basket_depth = 25.0;
// Basket / flare shell thickness (mm) — three perimeters at 0.4 mm nozzle
basket_wall = 2.4;
// Floor slab thickness (mm)
floor_t = 2.4;
// Pour-lip chamfer depth along the rim (mm); 45 deg by construction
lip_chamfer = 2.0;
// How far the floor disc bites into the wall band to fuse (mm)
floor_bite = 1.2;
// Volumetric overlap at every shell joint (mm) — never a coplanar kiss
// (issue #99 / vent-cap seat_clear precedent)
ov = 0.2;

/* [Grid] */
// Clear opening of one grid cell, side length (mm). Passes 0.1–0.5 mm
// bathing-sand grains; retains 2–5 mm debris. Step to 1.2 if printcheck
// flags the webs — never thin web_w below 1.2.
hole_d = 1.0;
// Web width between openings (mm) — the wall floor
web_w = 1.2;

/* [Quality] */
// Match the library pin so the shell and port do not split under Manifold
// (issue #99). Do not "improve" these.
$fa = 3;
$fs = 0.8;

/* [Hidden] */
eps = 0.01;

// ---------------------------------------------------------------------------
// Coupling — ONE cfg, built once. Guards fire inside nuggs_cfg().
// ---------------------------------------------------------------------------
cfg = nuggs_cfg(bore_d    = bore_d,    wall      = wall,      lug_r    = lug_r,
                port_proj = port_proj, collar_t  = collar_t,  n_lug    = n_lug,
                lug_deg   = lug_deg,   rib_h     = rib_h,     rib_w    = rib_w,
                rib_deg   = rib_deg,   twist_deg = twist_deg, bite     = bite,
                port_tol  = port_tol,  eps       = eps);

ri    = nuggs_ri(cfg);
ro    = nuggs_ro(cfg);
r_out = nuggs_r_out(cfg);
z_tip = nuggs_z_tip(cfg);
z_top = nuggs_z_top(cfg);

// ---------------------------------------------------------------------------
// Derived basket geometry (print frame: +z up, sector tips on the bed)
// ---------------------------------------------------------------------------
basket_ir = top_id / 2;
basket_or = basket_ir + basket_wall;
// Flare run: outward growth from tube OD to basket OD at ≤45°
flare_run = max(basket_or - ro, 0.1);
z_floor   = z_top + flare_run;          // underside of the grid floor
z_floor_top = z_floor + floor_t;        // top of the grid floor (= sand plane)
z_rim     = z_floor_top + basket_depth; // inside rim before lip cut
floor_r   = basket_ir + floor_bite;     // disc edge buried in the wall

// Grid pitch and bar centres. Openings are hole_d × hole_d squares; bars are
// web_w wide. Centres of bars sit on a pitch of hole_d + web_w.
grid_pitch = hole_d + web_w;
// Half-count of bars that still intersect the floor disc
grid_n = floor(floor_r / grid_pitch) + 1;

// Working capacity of the open cylinder above the floor (mL) — the G4 audit
// measures the sandbody mesh; this echo is the parameter claim.
capacity_ml = PI * basket_ir * basket_ir * basket_depth / 1000;

echo(str("nuggs-sand-sieve: port standard R", NUGGS_PORT_REV, " at bore ",
         bore_d, " mm, port_tol ", port_tol, " mm"));
echo(str("nuggs-sand-sieve: top_id ", top_id, " mm, depth ", basket_depth,
         " mm, capacity claim ", capacity_ml, " mL"));
echo(str("nuggs-sand-sieve: grid hole_d ", hole_d, " mm, web_w ", web_w,
         " mm, pitch ", grid_pitch, " mm, floor z ", z_floor, "..",
         z_floor_top));
echo(str("nuggs-sand-sieve: flare_run ", flare_run, " mm, printed height ",
         z_rim - z_tip, " mm"));

// ---------------------------------------------------------------------------
// Asserts — this module's own geometry (coupling guards live in nuggs_cfg)
// ---------------------------------------------------------------------------
assert(basket_wall >= 1.2, str(
    "SIEVE WALL: basket_wall = ", basket_wall, " mm is under the 1.2 mm",
    " three-perimeter floor."));
assert(floor_t >= 1.2, str(
    "SIEVE FLOOR: floor_t = ", floor_t, " mm is under the 1.2 mm floor."));
assert(web_w >= 1.2, str(
    "SIEVE WEB: web_w = ", web_w, " mm is under the 1.2 mm wall floor.",
    " Raise web_w; if printcheck flagged the webs, step hole_d up first",
    " (brief: never thin the web below 1.2)."));
assert(hole_d >= 0.8, str(
    "SIEVE HOLE: hole_d = ", hole_d, " mm is under the 0.8 mm printable-",
    "feature floor."));
assert(hole_d <= 2.0, str(
    "SIEVE HOLE: hole_d = ", hole_d, " mm is past 2.0 mm — debris retention",
    " for 2–5 mm scraps is lost. Tune on the coupon tile, not past here."));
assert(top_id > bore_d, str(
    "SIEVE TOP: top_id = ", top_id, " mm must exceed the bore ", bore_d,
    " mm or the basket is not a pour mouth."));
assert(basket_depth >= 10, str(
    "SIEVE DEPTH: basket_depth = ", basket_depth, " mm is under 10 mm —",
    " not a working basket."));
assert(lip_chamfer > 0 && lip_chamfer <= basket_depth / 2, str(
    "SIEVE LIP: lip_chamfer = ", lip_chamfer, " mm must sit in (0, ",
    basket_depth / 2, "]."));
assert(floor_bite > 0 && floor_r < basket_or, str(
    "SIEVE FLOOR BITE: floor edge at r = ", floor_r, " must bury in the",
    " wall band without reaching basket_or = ", basket_or, "."));
assert(flare_run + 1e-9 >= basket_or - ro, str(
    "SIEVE FLARE: flare_run = ", flare_run, " mm is shorter than the radial",
    " growth ", basket_or - ro, " mm — the exterior would exceed 45 deg."));

// ---------------------------------------------------------------------------
// Geometry
// ---------------------------------------------------------------------------

// Outer flare: tube OD at z_top → basket OD at z_floor. ≤45° by flare_run.
// Bottom foot buries ov into the neck so the joint is a real overlap, not a
// coplanar kiss at z_top (two-volume trap under CGAL/Manifold).
module flare_outer() {
    hull() {
        translate([0, 0, z_top - ov])
            cylinder(r = ro, h = eps);
        translate([0, 0, z_floor])
            cylinder(r = basket_or, h = eps);
    }
}

// Inner drain cavity through the flare: bore at z_top → basket ID at
// z_floor. Sand that passes the outer grid drains into the open bore.
module flare_inner() {
    hull() {
        translate([0, 0, z_top - ov - eps])
            cylinder(r = ri, h = eps);
        translate([0, 0, z_floor + eps])
            cylinder(r = basket_ir, h = eps);
    }
}

// Straight basket wall above the floor. Foot buries ov into the flare top.
module basket_wall_shell() {
    translate([0, 0, z_floor - ov])
        cylinder(r = basket_or, h = z_rim - (z_floor - ov));
}

// Basket interior window: opens the full ID from the floor underside up
// through the rim so the later grid_floor() can fill the floor plane
// (hopper discipline — hollow first, then union the mesh in).
module basket_cavity() {
    translate([0, 0, z_floor - eps])
        cylinder(r = basket_ir,
                 h = floor_t + basket_depth + lip_chamfer + 2 * eps);
}

// 45° pour-lip chamfer on the top inner edge: cuts INTO the wall corner
// (radial + axial = lip_chamfer). ≤45° by construction.
module pour_lip_cut() {
    rotate_extrude()
        polygon([
            [basket_ir - eps,              z_rim + eps],
            [basket_ir + lip_chamfer,      z_rim + eps],
            [basket_ir - eps,              z_rim - lip_chamfer],
        ]);
}

// Orthogonal web lattice floor. Bars in X and Y at grid_pitch, intersected
// with the floor disc so the edge is a clean buried cylinder. A solid rim
// ring in the wall band ties every bar end into the shell so the lattice
// cannot export as a second volume.
module grid_floor() {
    union() {
        intersection() {
            translate([0, 0, z_floor])
                cylinder(r = floor_r, h = floor_t);
            union() {
                for (i = [-grid_n : grid_n]) {
                    x = i * grid_pitch;
                    translate([x - web_w / 2, -floor_r - 1, z_floor - eps])
                        cube([web_w, 2 * floor_r + 2, floor_t + 2 * eps]);
                }
                for (j = [-grid_n : grid_n]) {
                    y = j * grid_pitch;
                    translate([-floor_r - 1, y - web_w / 2, z_floor - eps])
                        cube([2 * floor_r + 2, web_w, floor_t + 2 * eps]);
                }
            }
        }
        // Rim ring: buries in the wall annulus and overlaps the lattice edge
        difference() {
            translate([0, 0, z_floor])
                cylinder(r = floor_r, h = floor_t);
            translate([0, 0, z_floor - eps])
                cylinder(r = basket_ir - ov, h = floor_t + 2 * eps);
        }
    }
}

// One production cell tile for the coupon — outer = pitch + web so the free
// opening is exactly hole_d on both axes (same grammar as vent-cap's cell).
module grid_tile() {
    outer = grid_pitch + web_w;
    difference() {
        cube([outer, outer, floor_t]);
        translate([web_w, web_w, -eps])
            cube([hole_d, hole_d, floor_t + 2 * eps]);
    }
}

// The printable sieve: bore-clean neck + flare + wall, hollowed, lip cut,
// then the grid floor unioned in after the cavity (hopper discipline — union
// the floor before hollowing and the cavity subtraction carries it out).
module sieve() {
    union() {
        difference() {
            union() {
                nuggs_neck(cfg, z_top);
                flare_outer();
                basket_wall_shell();
            }
            flare_inner();
            basket_cavity();
            pour_lip_cut();
        }
        grid_floor();
    }
}

// Section on the port-axis plane (y < 0 removed).
module sieve_cutaway() {
    difference() {
        sieve();
        translate([0, -300, -100]) cube([300, 300, 400]);
    }
}

// Working-volume solid for the G4 capacity audit (no grid, no shell).
module sandbody() {
    translate([0, 0, z_floor_top])
        cylinder(r = basket_ir, h = basket_depth);
}

// ---------------------------------------------------------------------------
// Coupon — production port stub beside one grid tile at production sizes.
// Bed plane is z_tip: the neck stands on its sector tips there.
// ---------------------------------------------------------------------------
module sieve_coupon() {
    cell = grid_pitch + web_w;
    nuggs_neck(cfg, z_top + 8);
    translate([r_out + 4, -cell / 2, z_tip])
        grid_tile();
}

// ---------------------------------------------------------------------------
// Fitchecks — mate against a library neck. Pull 0.01 mm so coincident seat
// faces do not register as zero-volume facets (vent-cap / lib precedent).
// ---------------------------------------------------------------------------
module fit_mates() {
    intersection() {
        sieve();
        translate([0, 0, -0.01])
            rotate([0, 0, nuggs_clockings(cfg)[0]])
                mirror([0, 0, 1]) nuggs_neck(cfg, 30);
    }
}

module fit_mates_ctrl() {
    intersection() {
        sieve();
        translate([0, 0, -0.01])
            rotate([0, 0, 0])
                mirror([0, 0, 1]) nuggs_neck(cfg, 30);
    }
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------
if (part == "sieve") sieve();
else if (part == "coupon") sieve_coupon();
else if (part == "cutaway") sieve_cutaway();
else if (part == "mates") fit_mates();
else if (part == "mates-ctrl") fit_mates_ctrl();
else if (part == "sandbody") sandbody();
else assert(false, str("unknown part: ", part));
