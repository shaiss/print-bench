// N.U.G.G.S. feeder hopper — a gravity-fed top-fill food module.
// Requirements, welfare sources and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// This is the NUGGS ecosystem's FEEDING module: a shallow hopper bulb that
// caps a run with a printed lattice floor, holds a few days of food, and
// drops pellets into the enclosure as they are eaten. The owner refills from
// outside the cage through the open top port. The catalog had den, elbow,
// bridge, orrery and shutter-valve; a functional feed port was the gap.
//
// It is a CONSUMER of the port standard exactly like designs/nuggs and
// designs/nuggs-den: ONE cfg from nuggs_cfg() (every default, nothing
// redefined), one port at each end of the body, and no coupling derivation
// restated here. The only new geometry is the hopper between the ports.
//
// CONSTRUCTION — one outer revolve, one inner revolve, one floor. The body is
// a single rotate_extrude profile (bottom neck -> shoulder flare -> equator
// band -> crown -> waist -> top neck), the cavity a second full-length
// profile, exactly the nuggs-den construction with a second port at the top.
// That is deliberate: the run before this one built the bulb as a sphere
// unioned onto a cylinder and shipped three disconnected volumes — a body of
// revolution cannot come apart that way, because it is one swept polygon.
// The ONE inner profile spans the whole part (both mouths past their faces),
// so there is no separate bore-cut cylinder sharing radius ri with the cavity
// — the coincident-cylindrical-pair trap the library header warns about
// cannot occur, and the port's inboard anchor material is removed by the same
// subtraction (r < ri over the port zones), which is what nuggs_bore_cut()
// would exist to do.
//
// THE MESH FLOOR — a disc unioned in AFTER the cavity is cut (union it before
// and the cavity subtraction carries it straight back out; same reason the
// den adds rub_rail() after hollowing), then pierced by a square grid of
// vertical-wall openings. Openings are plain 8 mm squares on a 10.4 mm pitch:
// the walls are vertical (no face exceeds 45 deg), and the first layer over
// each 8 mm cell is an ordinary slicer bridge — the smallest bridge a
// filament printer does without complaint. The floor's underside between the
// cells is the one horizontal down-facing surface in the design; it shows up
// in printcheck as a few percent of overhang WARNING, the same tier the den
// ships with. A gabled (45 deg-flanked) cell was considered and dropped: it
// eliminates the warning but doubles the floor's thickness and closes the
// effective opening toward the top, against the direction food must pass.
//
// ORIENTATION. Printed exactly as modelled: the bottom port's coupling
// sectors sit on the bed (lug_deg is the first-layer anchor), the bore runs
// up, the mesh floor prints at z = 13, the bulb closes above it, and the top
// port's sectors are the last thing printed, pointing up. In USE the module
// stands the same way — bottom port coupled to a run or a cage-wall stub,
// food chute down, refill mouth up — so the print orientation IS the use
// orientation, and gravity is the only mechanism (brief: no metering).
use <nuggs-coupling.scad>

/* [What to render] */
// hopper = the printable part; coupon = fit stub; cutaway = section preview
part = "hopper";  // [hopper, coupon, cutaway]

/* [The NUGGS standard - change these and nothing you already printed fits] */
// Revision of the PORT STANDARD in lib/nuggs-coupling.scad this module builds
// to. Names the standard, not this design. Bump only on a breaking port change.
NUGGS_PORT_REV = 1;
// Internal bore (mm) — the headline number. Asserted >= min_bore_mm by the lib
// (the 70 mm Deutscher Tierschutzbund entrance floor for a pouched Syrian).
bore_d = 80.0;
// Tube shell thickness (mm)
wall = 2.4;
// Radial depth of the coupling ring beyond the tube OD (mm)
lug_r = 6.0;
// Axial projection of the coupling sectors past the tube face (mm)
port_proj = 10.0;
// Coupling sectors per face (3 = kinematically determinate)
n_lug = 3;
// Angular width of each sector (deg). Asserted lug_deg + twist_deg <= pitch/2.
lug_deg = 40;
// Radial depth of the locking rib (mm)
rib_h = 1.0;
// Axial width of the locking rib / groove (mm)
rib_w = 2.4;
// Angular width of the locking rib (deg)
rib_deg = 12;
// The locking twist (deg). Asserted rib_deg + twist_deg <= lug_deg.
twist_deg = 14;
// Backing-collar thickness (mm)
collar_t = 3.0;
// Overlap fusing the ribs into the outer sectors (mm). Never zero.
bite = 0.8;

/* [Fit & tolerances] */
// The one knob. Uniform clearance on every coupling surface (mm). Tune on the
// coupon in +/-0.05 steps. Asserted 0.10-0.60 by the lib.
port_tol = 0.30;

/* [Body] */
// Port face to port face (mm) — the module's overall span. Each end carries
// its port's sector projection (port_proj) BEYOND this, so the printed height
// is body_len + 2*port_proj.
body_len = 120;
// Outer radius of the hopper bulb at its widest (mm). Bulb OD = 2 x this.
bulb_r = 54;
// Bulb shell thickness (mm) — separate from the tube `wall` because the bulb
// carries no coupling load; keep >= 1.2 (3 perimeters at a 0.4 mm nozzle).
bulb_wall = 3.0;
// Height of the straight equator band between the shoulder flare and the
// crown (mm). Eats what would otherwise be a long bare waist between bulb
// and top port; capacity is whatever volume results, not a target.
eq_h = 40;
// Full-round shell above each port zone before the body flares (mm). Gives
// each port's inner sectors a ring to fuse to before any widening.
neck_extra = 3.0;
// Shoulder/crown steepness. 1 = 45 deg surfaces; >1 makes them steeper (safer
// overhang). At 1.2 every sloped surface sits at ~40 deg from vertical.
shoulder = 1.2;

/* [Mesh floor] */
// Clear opening of one mesh cell (mm). THE entry barrier: sized to stop a
// hamster head or a stuffed cheek pouch entering the hopper while passing a
// typical pellet. Brief's assumed value, 8; tune for your food.
mesh_open = 8.0;
// Rib width between cells (mm) — the gnaw-facing member, so it inherits the
// brief's >= 2.4 mm chew floor rather than a thinner default.
mesh_rib_w = 2.4;
// Floor slab thickness (mm). Three to four layers; thicker only droops more.
mesh_floor_t = 3.0;
// How far the floor disc bites into the tube wall band to fuse (mm). The
// disc's edge is buried INSIDE the shell so it never shares a cylindrical
// surface with the body — the coincident-face trap again.
floor_bite = 1.2;

/* [Pouch-relief mouths] */
// Radial flare of the funnel at each bore mouth (mm). Opens the bore at the
// tube face, so it is always welfare-positive; capped to leave >= 1.2 mm of
// tube wall behind it.
mouth_flare = 1.0;
// Axial depth each funnel runs back from its face (mm)
mouth_len = 6.0;

/* [Welfare limits - asserted, not tunable down] */
// DTSchB entrance minimum, pouch-full criterion (mm). NEVER lower this.
// The bore floor itself is asserted inside nuggs_cfg().
min_bore_mm = 70;
// Largest mesh cell that can still be called an entry barrier (mm). A Syrian
// head is ~30 mm and a stuffed pouch wider; 12 mm keeps a wide margin while
// admitting the coarsest useful pellet. NEVER raise this.
max_mesh_open = 12;

/* [Print settings] */
// Nozzle diameter (mm) - feeds the wall and web guards in the lib
nozzle = 0.4;

/* [Quality] */
// This design's own preset. Iterating: $fa=6/$fs=1.5. Production: $fa=2/$fs=0.5.
// It does NOT reach the coupling: the library pins its own $fa/$fs inside
// every port module body, deliberately, so the realised fit cannot move with
// a consumer's quality preset. These settings shape the revolve, never the
// joint.
$fa = 3;
$fs = 0.8;

/* [Hidden] */
eps = 0.01;

// ---------------------------------------------------------------------------
// The coupling configuration — ONE cfg, built once, handed to every port call.
// Every coupling guard fires inside nuggs_cfg(); they are not restated here.
// ---------------------------------------------------------------------------
cfg = nuggs_cfg(bore_d    = bore_d,    wall      = wall,      lug_r    = lug_r,
                port_proj = port_proj, collar_t  = collar_t,  n_lug    = n_lug,
                lug_deg   = lug_deg,   rib_h     = rib_h,     rib_w    = rib_w,
                rib_deg   = rib_deg,   twist_deg = twist_deg, bite     = bite,
                port_tol  = port_tol,  eps       = eps,       nozzle   = nozzle,
                min_bore  = min_bore_mm);

// The handful of contract values this design reaches for.
ri    = nuggs_ri(cfg);       // bore radius
ro    = nuggs_ro(cfg);       // tube outer radius — each port fuses to this
z_tip = nuggs_z_tip(cfg);    // bottom port's sector tips (bed contact)
z_top = nuggs_z_top(cfg);    // top of each port zone; the body must back this much

// ---------------------------------------------------------------------------
// Derived body geometry, bottom port face at z = 0, top port face at z =
// body_len. Everything between the two port zones is one revolve profile.
// ---------------------------------------------------------------------------
neck_len   = z_top + neck_extra;              // full-round shell at each port
flare      = bulb_r - ro;                     // radial growth at the shoulder
z_eq       = neck_len + flare * shoulder;     // equator band bottom
zc_top     = z_eq + eq_h;                     // equator top / crown start
z_crown    = zc_top + flare * shoulder;       // crown closes back to the waist
bulb_in    = bulb_r - bulb_wall;              // cavity radius on the equator
z_crown_in = zc_top + (bulb_in - ri) * shoulder;  // cavity crown meets the bore

// The mesh floor sits directly above the bottom port zone: below it is pure
// bore (the food chute), above it the hopper. Its disc spans the wall band so
// the grid is fused to the shell all the way round.
z_floor    = z_top;                           // floor base = top of port zone
floor_r    = ri + floor_bite;                 // disc edge buried in the shell
mesh_pitch = mesh_open + mesh_rib_w;          // cell centre to cell centre
mesh_r_max = ri - 1.2 - mesh_open * sqrt(2) / 2;  // outermost cell centre line
mesh_n     = floor(mesh_r_max / mesh_pitch);  // grid half-extent
n_cells    = len([for (i = [-mesh_n : mesh_n], j = [-mesh_n : mesh_n])
                      if (norm([i, j]) * mesh_pitch <= mesh_r_max) 1]);

// Clear internal diameter at the bulb's widest — the number that decides how
// much food stands on the mesh at once.
inner_d = 2 * bulb_in;

echo(str("nuggs-hopper: port standard R", NUGGS_PORT_REV, " at bore ", bore_d,
         " mm (ri ", ri, "), tube OD ", 2 * ro, " mm, port_tol ", port_tol,
         " mm -> web ", nuggs_web(cfg), " mm, bearing area ",
         nuggs_bearing_area(cfg), " mm2"));
echo(str("nuggs-hopper: bulb OD ", 2 * bulb_r, " mm, clear internal ", inner_d,
         " mm, span ", body_len, " mm (printed height ",
         body_len + 2 * port_proj, " mm)"));
echo(str("nuggs-hopper: mesh ", n_cells, " cells of ", mesh_open, " mm on a ",
         mesh_pitch, " mm pitch, rib ", mesh_rib_w, " mm, floor z ", z_floor,
         "..", z_floor + mesh_floor_t));

// ---------------------------------------------------------------------------
// Welfare and printability asserts. The coupling's guards live in nuggs_cfg();
// these belong to THIS module's own geometry.
// ---------------------------------------------------------------------------

// The bulb has to actually be a hopper, not a bulge on a tube.
assert(bulb_r >= ro + 10, str(
    "HOPPER BULB: bulb_r = ", bulb_r, " mm is within 10 mm of the tube OD ",
    ro, " — that is a bulge, not a hopper. Widen bulb_r."));
assert(bulb_wall >= 1.2, str(
    "HOPPER WALL: bulb_wall = ", bulb_wall, " mm is under the 1.2 mm three-",
    "perimeter floor at a 0.4 mm nozzle."));
assert(shoulder >= 1.0, str(
    "HOPPER OVERHANG: shoulder = ", shoulder, " puts the shoulder and crown ",
    "past 45 deg of overhang, which prints without support only as a gamble.",
    " Use >= 1.0 (1.0 is exactly 45 deg; 1.2 is a comfortable ~40 deg)."));

// Both ports need their full-round shell: the body must be long enough to
// back each port zone with room for the bulb between.
assert(body_len >= 2 * neck_len + flare * shoulder, str(
    "HOPPER BODY: body_len = ", body_len, " mm cannot hold two port zones (",
    neck_len, " mm each) plus a shoulder (", flare * shoulder,
    " mm). Lengthen body_len or shrink the bulb."));
assert(z_crown <= body_len - neck_len, str(
    "HOPPER CROWN: the crown closes at z = ", z_crown, " mm, past the top ",
    "port's shell zone, which starts at ", body_len - neck_len,
    " mm. The top port's inner sectors must fuse to straight full-round shell,",
    " not to the crown curve. Lengthen body_len or shrink eq_h."));
assert(body_len + 2 * port_proj <= 250, str(
    "HOPPER BED: printed height ", body_len + 2 * port_proj,
    " mm exceeds the 250 mm usable height on a 256 mm bed. Shorten body_len."));

// THE entry barrier. A mesh that opens past max_mesh_open is a hole a hamster
// climbs through, whatever the food-size argument for widening it.
assert(mesh_open > 0 && mesh_open <= max_mesh_open, str(
    "HOPPER MESH: mesh_open = ", mesh_open, " mm is outside the entry-barrier",
    " band (0, ", max_mesh_open, "]. The cell must stop a hamster head or a",
    " stuffed cheek pouch entering the hopper; a Syrian head is ~30 mm and a",
    " pouched arrival wider. This is a welfare bound, not a tuning knob."));
assert(mesh_rib_w >= 1.2, str(
    "HOPPER MESH RIB: mesh_rib_w = ", mesh_rib_w, " mm is under the 1.2 mm ",
    "three-perimeter floor. The ribs are the gnaw-facing member of the part."));
assert(n_cells >= 12, str(
    "HOPPER MESH: only ", n_cells, " cells fit at mesh_open = ", mesh_open,
    " mm — that is a perforated patch, not a feeding floor. Widen mesh_open",
    " or the bulb."));
assert(floor_bite > 0 && floor_r < ro, str(
    "HOPPER FLOOR: the disc edge at r = ", floor_r,
    " mm must bite INTO the wall band (", ri, "..", ro,
    ") without reaching the tube OD. A zero bite is a zero-volume kiss; an",
    " edge at or beyond ro shares a cylindrical surface with the shell."));

// The mouth funnels OPEN the bore (welfare-positive), but they cut into the
// tube wall at each face, so they must leave a printable wall behind.
assert(mouth_flare > 0 && wall - mouth_flare >= 1.2, str(
    "HOPPER MOUTH: mouth_flare = ", mouth_flare, " mm leaves ",
    wall - mouth_flare, " mm of tube wall at the face (wall - mouth_flare), ",
    "under the 1.2 mm three-perimeter floor. Cut mouth_flare or thicken wall."));

// ---------------------------------------------------------------------------
// Profiles
// ---------------------------------------------------------------------------

// Outer shell: bottom port face (z = 0) to top port face (z = body_len).
// Bottom neck -> shoulder flare -> equator band -> crown -> waist -> top neck.
// ONE polygon, so the body is one solid of revolution by construction.
outer_profile = [
    [0,      0],
    [ro,     0],
    [ro,     neck_len],       // full-round neck the bottom port fuses to
    [bulb_r, z_eq],           // shoulder flare (< 45 deg)
    [bulb_r, zc_top],         // equator band (vertical)
    [ro,     z_crown],        // crown closing back to the waist (< 45 deg)
    [ro,     body_len],       // waist + full-round neck the top port fuses to
    [0,      body_len]
];

// Inner cavity: ONE full-length profile from below the bottom port's sector
// tips to above the top face, so both bores and the whole hopper void come
// from a single subtraction. Below the flare and above the crown it runs at
// exactly ri — which also removes each port's inboard anchor material, the
// cut nuggs_bore_cut() exists to make. There is no second cutter at ri
// anywhere, so no coincident cylindrical pair exists in this part.
inner_profile = [
    [0,        z_tip - 1],
    [ri,       z_tip - 1],
    [ri,       neck_len],
    [bulb_in,  z_eq],
    [bulb_in,  zc_top],
    [ri,       z_crown_in],
    [ri,       body_len + 1],
    [0,        body_len + 1]
];

// ---------------------------------------------------------------------------
// Features
// ---------------------------------------------------------------------------

// The mesh floor: a disc spanning the wall band, pierced by the cell grid.
// Built as ONE slab minus the cells (not as rib boxes unioned) so the floor's
// outer edge is a clean buried cylinder and the cells are simple through-cuts.
// Cell centres sit on a square grid at mesh_pitch; a cell is emitted only
// where its farthest corner stays clear of the bore wall, so no cell notches
// the shell and every cell is a full unclipped square.
module mesh_floor() {
    difference() {
        translate([0, 0, z_floor])
            cylinder(r = floor_r, h = mesh_floor_t);
        for (i = [-mesh_n : mesh_n], j = [-mesh_n : mesh_n])
            if (norm([i, j]) * mesh_pitch <= mesh_r_max)
                translate([i * mesh_pitch - mesh_open / 2,
                           j * mesh_pitch - mesh_open / 2,
                           z_floor - eps])
                    cube([mesh_open, mesh_open, mesh_floor_t + 2 * eps]);
    }
}

// Pouch-relief funnel at a bore mouth. `up` = true at the top face (widest at
// the face, narrowing downward); false at the bottom face (widest at the
// face, narrowing upward). Cut, never added; each only ever opens the bore.
// Same shape as nuggs-den's pouch_relief, anchored at the tube END FACE — the
// sectors below the face sit in the region the mate's tube occupies.
module mouth_funnel(up) {
    r_face = ri + mouth_flare;
    if (up)
        translate([0, 0, body_len - mouth_len])
            cylinder(r1 = ri, r2 = r_face, h = mouth_len + eps);
    else
        translate([0, 0, -eps])
            cylinder(r1 = r_face, r2 = ri, h = mouth_len + eps);
}

// ---------------------------------------------------------------------------
// Parts
// ---------------------------------------------------------------------------

// The hopper: body revolve + a port at each face, hollowed by the single
// cavity profile, THEN the mesh floor unioned onto the fresh bore wall (union
// it before the subtraction and the cavity carries it straight back out),
// then the mouth funnels cut through everything.
module nuggs_hopper() {
    difference() {
        union() {
            difference() {
                union() {
                    rotate_extrude() polygon(outer_profile);
                    nuggs_port(cfg);                      // sectors on -z: bed
                    translate([0, 0, body_len]) mirror([0, 0, 1])
                        nuggs_port(cfg);                  // sectors on +z: cap
                }
                rotate_extrude() polygon(inner_profile);
            }
            mesh_floor();
        }
        mouth_funnel(false);
        mouth_funnel(true);
    }
}

// Print-this-first fit coupon: one bore-clean port on a short stub. The fit
// is the library's, so the coupon is a library port stub — the same shape the
// other NUGGS modules tune port_tol on. nuggs_neck() does the bore cut.
module nuggs_hopper_coupon() {
    nuggs_neck(cfg, z_top + 8);
}

if (part == "hopper") nuggs_hopper();
else if (part == "coupon") nuggs_hopper_coupon();
else if (part == "cutaway")
    difference() { nuggs_hopper(); translate([0, -200, -200]) cube(400); }
else assert(false, str("nuggs-hopper: unknown part '", part, "'"));
