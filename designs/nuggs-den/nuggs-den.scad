// N.U.G.G.S. Den — a terminal burrow refuge for one adult Syrian hamster.
// Requirements, welfare sources and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// This is NOT a tube and NOT an elbow. It is a single-port TERMINAL module: a
// rounded refuge bulb that caps the end of a NUGGS run, so a short bridge runs
// into a place to sit rather than a dead flat wall. It carries the one shared
// interlock — the genderless quarter-turn port in lib/nuggs-coupling.scad — so
// it mates any NUGGS face either way round, and it is a CONSUMER of that
// standard exactly like designs/nuggs: it builds one cfg with nuggs_cfg() and
// hands it around, restating none of the coupling's derivations.
//
// The features here are the ones a Syrian hamster would ask for and a person
// building a tube system would not think to add. They are argued in NOTES.md;
// in one line each:
//   * OPAQUE REFUGE. The bulb is solid-walled and windowless. A prey animal in
//     a clear tube has nowhere to be unseen; the whole point of a den is to be
//     out of sight, so the den is the one NUGGS module that is deliberately not
//     open.
//   * CHIMNEY VENTS. The standing critique of hamster tubes is that they cannot
//     be ventilated and they condense. A closed bulb would be the worst case,
//     so the crown carries a ring of TEARDROP vents: warm breath rises and
//     leaves out the top (a convective chimney), and the teardrop profile means
//     every vent prints with no support and no bridge — the detail only shows up
//     if you have actually sliced an FDM part.
//   * FLANK RUB RAIL. A Syrian hamster scent-marks by dragging the glands on
//     its flanks along a surface. A dwarf marks with its belly; a Syrian marks
//     with its sides, so the mark it wants is a horizontal RIDGE at flank
//     height, not a floor patch. The rail is that ridge, rounded so it is a
//     rub, never a chew-start edge, and run all the way round so it works
//     whichever way the animal curls.
//   * POUCH-RELIEF MOUTH. An animal arriving with both cheek pouches full is far
//     wider at the face than its body. The entry is flared so a loaded arrival
//     is funneled in and never scrapes a pouch on a square lip.
//
// ORIENTATION. Printed exactly as modelled: the port's sectors sit on the bed
// (that is what they are for — lug_deg is the first-layer anchor), the bore
// runs up, and the bulb closes above it. In USE you lay it however the run
// needs; every feature here is a full ring, so nothing depends on which way up
// it ends up.
use <nuggs-coupling.scad>
use <printability.scad>

/* [What to render] */
// chamber = the printable part; coupon = fit stub; cutaway = section preview
part = "chamber";  // [chamber, coupon, cutaway]

/* [The NUGGS standard - change these and nothing you already printed fits] */
// Revision of the PORT STANDARD in lib/nuggs-coupling.scad this module builds
// to. Names the standard, not this design — a printed module is identified
// years later by what it MATES with. Bump only on a breaking port change.
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

/* [Den bulb] */
// Outer radius of the refuge bulb at its widest (mm). Chamber OD = 2 x this.
bulb_r = 58;
// Chamber shell thickness (mm) — separate from the tube `wall` because the bulb
// carries no coupling load; keep >= 1.2 (3 perimeters at a 0.4 mm nozzle).
bulb_wall = 3.0;
// Height of the straight equator band between the shoulder flare and the crown
// cone (mm). The vents and rub rail live on this band.
eq_h = 26;
// Extra full-round shell above the port zone before the shoulder flares out
// (mm). Gives the port's inner sectors ring to fuse to before any widening.
neck_extra = 2.0;
// Shoulder/crown steepness. 1 = 45deg surfaces; >1 makes them steeper (safer
// overhang). At 1.2 every sloped surface sits at ~40deg from vertical.
shoulder = 1.2;
// Radius of the rounded cap that blunts the crown apex (mm). A bare cone ends
// in a spike — a poke point in the hand and a sharp singular vertex in the
// mesh. A small sphere over the tip rounds it off; it is tiny, so it still
// prints support-free at the very top.
crown_blunt = 5.0;

/* [Chimney vents] */
// Number of teardrop vents around the crown band
n_vent = 6;
// Teardrop vent bore diameter (mm)
vent_d = 9;

/* [Flank rub rail] */
// Radial reach of the scent-gland rub ridge into the bulb (mm)
rail_h = 4.0;
// Height of the rail's centre above the equator band bottom (mm)
rail_z = 6.0;

/* [Pouch-relief mouth] */
// Radial flare of the entry funnel at the mouth (mm). Opens the bore, so it is
// always welfare-positive; kept below `wall` so it never touches the coupling.
mouth_flare = 2.0;
// Axial depth the funnel runs back from the mouth (mm)
mouth_len = 6.0;

/* [Quality] */
// This design's own preset. Iterating: $fa=6/$fs=1.5. Production: $fa=2/$fs=0.5.
// It does NOT reach the coupling: the library pins its own $fa/$fs inside every
// port module body, deliberately, so the fit cannot move with a quality change.
$fa = 3;
$fs = 0.8;

/* [Hidden] */
eps = 0.01;

// ---------------------------------------------------------------------------
// The coupling configuration — ONE cfg, built once, handed to every port call.
// Every coupling guard fires inside nuggs_cfg(); none is restated here.
// ---------------------------------------------------------------------------
cfg = nuggs_cfg(bore_d    = bore_d,    wall      = wall,      lug_r    = lug_r,
                port_proj = port_proj, collar_t  = collar_t,  n_lug    = n_lug,
                lug_deg   = lug_deg,   rib_h     = rib_h,     rib_w    = rib_w,
                rib_deg   = rib_deg,   twist_deg = twist_deg, bite     = bite,
                port_tol  = port_tol,  eps       = eps);

// The handful of contract values this design reaches for; the rest stay in the
// library.
ri    = nuggs_ri(cfg);       // bore radius
ro    = nuggs_ro(cfg);       // tube outer radius — the port fuses to this
z_tip = nuggs_z_tip(cfg);    // sector tips (bed contact), = -port_proj
z_top = nuggs_z_top(cfg);    // top of the port zone; the bulb must clear it

// ---------------------------------------------------------------------------
// Derived bulb geometry. The bulb is a solid of revolution: a full-round neck,
// a shoulder that flares out at <45deg, a straight equator band carrying the
// features, and a crown cone that closes to a point at <45deg. Both the outer
// shell and the inner cavity are ONE rotate_extrude polygon each, so no two
// swept faces ever share a radius — the coincident-cylinder trap the coupling
// library warns about at length cannot occur here.
// ---------------------------------------------------------------------------
neck_len = z_top + neck_extra;                 // full-round shell height
flare    = bulb_r - ro;                        // radial growth at the shoulder
z_eq     = neck_len + flare * shoulder;        // equator band bottom
zc_top   = z_eq + eq_h;                        // equator band top / crown start
apex_o   = zc_top + bulb_r * shoulder;         // outer crown apex
apex_i   = zc_top + (bulb_r - bulb_wall) * shoulder;  // inner ceiling apex

// Clear internal diameter at the widest point — the number that decides whether
// the animal can reorient in here (it cannot fully turn: see the welfare note).
inner_d  = 2 * (bulb_r - bulb_wall);

echo(str("nuggs-den: port standard R", NUGGS_PORT_REV, " at bore ", bore_d,
         " mm, port_tol ", port_tol, " mm -> web ", nuggs_web(cfg),
         " mm, bearing area ", nuggs_bearing_area(cfg), " mm2"));
echo(str("nuggs-den: bulb OD ", 2 * bulb_r, " mm, clear internal ", inner_d,
         " mm, overall height ", apex_o - z_tip, " mm, ", n_vent,
         " chimney vents"));

// ---------------------------------------------------------------------------
// Welfare and printability asserts. The coupling's guards live in nuggs_cfg();
// these are the ones that belong to THIS module's own geometry.
// ---------------------------------------------------------------------------

// The bulb has to actually be a chamber, not a bump on a tube.
assert(bulb_r >= ro + 10, str(
    "DEN BULB: bulb_r = ", bulb_r, " mm is within 10 mm of the tube OD ", ro,
    " — that is a bulge, not a refuge. Widen bulb_r."));
assert(bulb_wall >= 3 * nuggs_ro(cfg) * 0 + 1.2, str(
    "DEN WALL: bulb_wall = ", bulb_wall, " mm is under the 1.2 mm three-",
    "perimeter floor at a 0.4 mm nozzle."));
assert(shoulder >= 1.0, str(
    "DEN OVERHANG: shoulder = ", shoulder, " puts the shoulder and crown past ",
    "45deg of overhang, which prints without support only as a gamble. Use ",
    ">= 1.0 (1.0 is exactly 45deg; 1.2 is a comfortable ~40deg)."));

// The vents and the rail both live on the equator band; neither may run off it.
assert(vent_d > 0 && vent_d < eq_h - 4, str(
    "DEN VENT: vent_d = ", vent_d, " mm does not leave a band margin on the ",
    eq_h, " mm equator. Shrink the vent or grow eq_h."));
assert(n_vent >= 1, "DEN VENT: n_vent must be at least 1.");
assert(rail_h > 0 && rail_h < bulb_r - bulb_wall - ri, str(
    "DEN RAIL: rail_h = ", rail_h, " mm would reach past the bore line; a rub ",
    "rail must leave the animal its room. Cut rail_h."));
assert(rail_z - rail_h > 0 && rail_z + rail_h < eq_h, str(
    "DEN RAIL: the rail at rail_z = ", rail_z, " +/- rail_h = ", rail_h,
    " mm falls off the ", eq_h, " mm equator band. Move rail_z inward."));

// The pouch-relief funnel OPENS the bore (welfare-positive), but if it flared
// past the tube wall it would start eating the coupling instead of the bore.
assert(mouth_flare > 0 && mouth_flare < wall, str(
    "DEN MOUTH: mouth_flare = ", mouth_flare, " mm must stay below the tube ",
    "wall (", wall, " mm) so the funnel only ever opens the bore, never the ",
    "port that has to seat against the mate's tube."));

// Bed. Printed upright on the sector tips; the tallest point is the crown apex.
assert(apex_o - z_tip <= 250, str(
    "DEN BED: overall height ", apex_o - z_tip, " mm exceeds the 250 mm usable ",
    "height on a 256 mm bed. Lower bulb_r, eq_h or shoulder."));

// ---------------------------------------------------------------------------
// Profiles
// ---------------------------------------------------------------------------

// Outer shell of the bulb, from the tube end face (z = 0) up to the crown apex.
outer_profile = [
    [0,       0],
    [ro,      0],
    [ro,      neck_len],       // full-round neck the port fuses to
    [bulb_r,  z_eq],           // shoulder flare (<45deg)
    [bulb_r,  zc_top],         // equator band (vertical)
    [0,       apex_o]          // crown cone to a point (<45deg)
];

// Inner cavity. Starts BELOW the sector tips so it clears the port's inboard
// material exactly as nuggs_bore_cut() would, opens up through the neck at the
// bore radius, then follows the shell inward by bulb_wall. The ceiling closes
// to a point too, so there is never a flat unsupported roof to bridge.
inner_profile = [
    [0,                 z_tip - 1],
    [ri,                z_tip - 1],
    [ri,                neck_len],
    [bulb_r - bulb_wall, z_eq],
    [bulb_r - bulb_wall, zc_top],
    [0,                 apex_i]
];

// ---------------------------------------------------------------------------
// Feature modules
// ---------------------------------------------------------------------------

// The flank rub rail: a rounded ring ridge on the equator's inner wall. Its
// cross-section is a triangle with 45deg flanks (so its underside prints as a
// clean overhang), tipped rounded via the design $fs. The base bites 0.6 mm
// OUTWARD into the shell so it fuses as a real overlap, never a zero-area kiss.
module rub_rail() {
    r_wall = bulb_r - bulb_wall;
    z_lo   = z_eq + rail_z - rail_h;
    rotate_extrude()
        offset(r = 0.6) offset(delta = -0.6)   // soften the tip, keep the base
            polygon([[r_wall + 0.6, z_lo],
                     [r_wall - rail_h, z_lo + rail_h],
                     [r_wall + 0.6, z_lo + 2 * rail_h]]);
}

// One chimney vent: a teardrop hole (point up, so it prints without support)
// driven radially through the equator band. teardrop_hole()'s bore axis is +Y
// and its roof is +Z; rotating -90deg about Z aims the bore along +X while the
// roof stays up, and the outer rotate() distributes the ring. Length overshoots
// the wall on both sides so the pierce is clean.
module chimney_vents() {
    z_v = z_eq + eq_h * 0.62;                 // upper band, above the rail
    for (i = [0 : n_vent - 1])
        rotate([0, 0, i * 360 / n_vent + 180 / n_vent])
            translate([bulb_r - bulb_wall / 2, 0, z_v])
                rotate([0, 0, -90])
                    teardrop_hole(d = vent_d, l = bulb_wall * 4 + 4);
}

// The pouch-relief funnel at the mouth: a cone that opens the bore from ri to
// ri + mouth_flare over the first mouth_len of travel from the sector tips.
module pouch_relief() {
    translate([0, 0, z_tip - eps])
        cylinder(r1 = ri + mouth_flare, r2 = ri, h = mouth_len);
}

// ---------------------------------------------------------------------------
// Parts
// ---------------------------------------------------------------------------

// The den itself: port + bulb shell, hollowed, then the rail added onto the
// fresh inner wall, then the vents and the pouch funnel cut through everything.
// The rail is unioned AFTER the cavity is removed, or the cavity subtraction
// would carry it straight back out again.
module nuggs_den() {
    difference() {
        union() {
            difference() {
                union() {
                    rotate_extrude() polygon(outer_profile);
                    // round the crown spike into a nub (safety + a clean apex)
                    translate([0, 0, apex_o - crown_blunt]) sphere(r = crown_blunt);
                    nuggs_port(cfg);           // sectors on -z (bed); tube on +z
                }
                rotate_extrude() polygon(inner_profile);
            }
            rub_rail();
        }
        chimney_vents();
        pouch_relief();
    }
}

// Print-this-first fit coupon: one bore-clean port on a short stub. The fit is
// the library's, so the coupon is a library port stub — the same shape
// designs/nuggs tunes port_tol on. nuggs_neck() does the mandatory bore cut.
module nuggs_den_coupon() {
    nuggs_neck(cfg, z_top + 8);
}

if (part == "chamber") nuggs_den();
else if (part == "coupon") nuggs_den_coupon();
else if (part == "cutaway")
    difference() { nuggs_den(); translate([0, -200, -200]) cube(400); }
else assert(false, str("nuggs-den: unknown part '", part, "'"));
