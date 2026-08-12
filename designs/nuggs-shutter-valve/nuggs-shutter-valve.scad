// N.U.G.G.S. shutter valve — an inline stop-gate module for an 80 mm-bore NUGGS
// run: a short straight section carrying the genderless quarter-turn port on
// each end, with a captive print-in-place shutter that slides across the bore
// to seal a run and retracts fully clear to reopen it.
// Requirements, welfare sources and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.
//
// STATUS: iteration 2 (co-design, issue #99) — orientation LOCKED to vertical
// tube / horizontal sideways gate (maintainer call), detent + end handle chosen.
// Still converging on gate-clean; the open item is the bore-slot roof overhang,
// which this file measures rather than assumes.
//
// PRINT ORIENTATION. Tube axis VERTICAL, standing on the bottom port's sector
// tips (the whole NUGGS family prints this way — see designs/nuggs, elbow). The
// shutter is a flat plate in the XY plane sliding in +Y, so slide_rail's
// 45-degree lip undersides face the bed and print supportless. z is up = the
// print direction; bottom-iso shows the true bed contact.
//
// CONSUMER OF TWO STANDARDS, redefining neither:
//   * NUGGS port — lib/nuggs-coupling.scad, one cfg via nuggs_cfg(), handed
//     around; every coupling guard fires inside the library.
//   * the print-in-place slide — lib/print-in-place.scad. NOTE the adaptation,
//     recorded in NOTES.md: slide_rail's CASTELLATED lips are a LIFT-OUT door
//     mechanism (it asserts travel > tab_len so the door frees at full slide).
//     A full-bore shutter must stay CAPTIVE across its whole travel, so this
//     design runs a CONTINUOUS lip built from the library's own exposed
//     clearance derivations — pip_lip_z(), pip_rail_h(), pip_lip_profile() —
//     and uses slide_tab for the door-side tabs and its acoustic body-shrink
//     `fit`. It consumes the library's clearance math (the acoustic property:
//     do NOT loosen the rail clearances; tune only door_fit on the coupon), not
//     its lift-out geometry.
use <nuggs-coupling.scad>
use <print-in-place.scad>

/* [What to render] */
// assembled/cutaway = review previews; valve = the printable part; shutter =
// the gate alone; coupon = the slide-fit test coupon.
part = "cutaway";  // [assembled, cutaway, valve, shutter, coupon]
// Gate position for the preview: 0 = closed (sealing the bore), 1 = fully open.
open = 0.0;  // [0:0.01:1]

/* [The NUGGS standard - inherited defaults, change nothing you printed fits] */
// Internal bore (mm) - the headline number. Asserted >= min_bore_mm by the lib.
bore_d = 80.0;
// Tube shell thickness (mm). ro = bore_d/2 + wall is the coupling datum.
wall = 2.4;
// Radial depth of the coupling ring beyond the tube OD (mm).
lug_r = 6.0;
// Axial projection of the coupling sectors past the tube face (mm).
port_proj = 10.0;
// Backing-collar thickness (mm).
collar_t = 3.0;
// Coupling sectors per face (3 = kinematically determinate).
n_lug = 3;
// Angular width of each sector (deg). Asserted lug_deg + twist_deg <= pitch/2.
lug_deg = 40;
// Radial depth of the locking rib (mm).
rib_h = 1.0;
// Axial width of the locking rib / groove (mm).
rib_w = 2.4;
// Angular width of the locking rib (deg).
rib_deg = 12;
// The locking twist (deg). Asserted rib_deg + twist_deg <= lug_deg.
twist_deg = 14;
// Overlap fusing the ribs into the outer sectors (mm). Never zero.
bite = 0.8;

/* [Fit & tolerances] */
// THE coupling knob. Uniform clearance on every coupling surface (mm). Owned by
// the standard; tuned on designs/nuggs's coupon. Asserted 0.10-0.60 by the lib.
port_tol = 0.30;
// Door-side slide fit (mm, + = looser). The ONE slide clearance this design may
// tune (on the coupon); the rail clearances stay the battleship's. -0.2 .. 0.5.
door_fit = 0.0;

/* [Shutter valve] */
// Straight full-round shell behind each port (mm). Backs the port (>= z_top)
// and gives a grip past the coupling collar.
lead_in = 30;
// Shutter plate thickness (mm). >= 2 perimeters + stiffness across the span.
gate_t = 3.0;
// How far the plate overreaches the bore edge when closed (mm), so it seals
// with margin rather than landing exactly on the bore circle.
gate_over = 3.0;
// Detent bump height (mm) — a light click that holds the gate at closed & open.
detent_h = 0.4;
// Handle: a pull-tab off the gate's outboard edge.
handle_w = 20; handle_t = 8; handle_reach = 14;

/* [Welfare limits - asserted, not tunable down] */
// DTSchB entrance minimum, pouch-full criterion (mm). NEVER lower this. The
// bore floor itself is asserted inside nuggs_cfg().
min_bore_mm = 70;

/* [Print settings] */
// Nozzle diameter (mm) - feeds the wall and web guards in the lib.
nozzle = 0.4;
// House angle for bore-mouth edge breaks and the slot-roof gable (deg).
chamfer_ang = 45;

/* [Quality] */
// Production preset. NOTE this is NOT cosmetic here: nuggs_port pins its own
// fine $fa/$fs internally, so a COARSE tube ($fa=6/$fs=1.5) fuses fine port
// sectors to a coarse shell — a facet mismatch at the fusion interface that
// CGAL merges but the OpenSCAD Manifold backend splits into ~20 shells
// (issue #99 / PR #200, the render-gate failure). Matching the shell to the
// port's resolution keeps the export a single watertight body. Drop to
// $fa=6/$fs=1.5 only for quick local iteration, never for a gated render.
$fa = 2;
$fs = 0.5;

/* [Hidden] */
eps = 0.01;

// ---------------------------------------------------------------------------
// The coupling configuration — ONE cfg, built once, handed to every port call.
// ---------------------------------------------------------------------------
cfg = nuggs_cfg(bore_d    = bore_d,    wall      = wall,      lug_r    = lug_r,
                port_proj = port_proj, collar_t  = collar_t,  n_lug    = n_lug,
                lug_deg   = lug_deg,   rib_h     = rib_h,     rib_w    = rib_w,
                rib_deg   = rib_deg,   twist_deg = twist_deg, bite     = bite,
                port_tol  = port_tol,  eps       = eps,       nozzle   = nozzle,
                min_bore  = min_bore_mm);

ri    = nuggs_ri(cfg);      // bore radius (40)
ro    = nuggs_ro(cfg);      // tube outer radius (42.4)
r_out = nuggs_r_out(cfg);   // coupling ring OD (46.4)
z_top = nuggs_z_top(cfg);   // top of the port zone; lead_in must back this much

// ---------------------------------------------------------------------------
// Slide clearances, taken from the library (the acoustic property). These are
// pip_*() defaults, named here so the geometry reads and so the design cannot
// silently drift from the library's derivation.
// ---------------------------------------------------------------------------
gap_z    = 0.6;                 // tab ride gap above the deck (slide_tab default)
tab_t    = 1.2;                 // tab slab thickness (slide_tab default)
tab_w    = 3.5;                 // tab reach sideways under the lip
lip_d    = 3.2;                 // lip overhang / engagement depth
lip_drop = 0.4;                 // lip-top mesh-hygiene drop
lz       = pip_lip_z(gap_z, tab_t);            // lip root height above deck (1.7)
rh       = pip_rail_h(gap_z, tab_t, 0.4, 0.5, lip_d);  // rail wall height (5.7)
// How deep the continuous lip roots into its backing wall/pillar. A real
// overlap, NOT an eps kiss: Manifold keeps face-coincident solids as separate
// shells (CGAL fuses them), so every join here interpenetrates by this weld.
lip_bury = 0.6;
weld     = 0.6;                                 // generic union overlap

// ---------------------------------------------------------------------------
// Gate + chamber geometry (all derived; NOTES.md has the picture).
//
// The shutter is a flat plate in XY sliding in +Y. Closed it covers the bore
// disc (radius gate_r); a full `travel` later it is entirely in the +Y pocket,
// clear of the bore. The plate rides gap_z above the deck (z_deck), its tabs
// captured under a CONTINUOUS lip that runs the whole slide.
// ---------------------------------------------------------------------------
gate_r  = ri + gate_over;                 // plate half-extent covering the bore (43)
gate_w  = 2 * gate_r;                     // plate width in X and closed length in Y
// Gate travel runs between the two housing walls, which ARE the travel stops
// (so no separate end-stop ridges): CLOSED = the plate's -Y edge resting on the
// closed-side wall (it covers the bore there); OPEN = the plate slid until its
// -Y edge is clear past +ri, entirely out of the bore.
y_closed = -(ri + 2) + gate_r;            // gate centre, closed (against the -Y wall)
y_open   = ri + gate_r + 2;               // gate centre, open (fully clear of the bore)
travel   = y_open - y_closed;
// The PRINTABLE part renders the gate OPEN — parked over the solid pedestal,
// where it prints as a trivial gap_z (0.6 mm) bridge onto solid material;
// modelled closed it would bridge the whole open bore. Print-in-place parts
// print in the pose that prints best; the operator slides it closed after.
// Previews (assembled/cutaway) honour the `open` param.
open_eff = (part == "valve") ? 1 : open;
open_y   = y_closed + (y_open - y_closed) * open_eff;   // gate centre in +Y

// rails just outboard of the plate; pillars carry flow past them
rail_wall = 3.0;
pillar    = 7.0;
wall_in   = gate_r + tab_w + 0.4;         // rail wall cell-side face
hx        = wall_in + rail_wall + pillar; // housing X half-extent

hy_closed = ri + 5;                       // -Y wall: caps the closed side
hy_open   = y_open + gate_r + handle_reach + 4;  // +Y end of the retract pocket (clears the open gate + handle)
core_y1   = r_out + 6;                     // bore-housing +Y extent
ped_y0    = r_out + 2;                     // drawer pedestal starts (clears the bottom port ring)

// z stack, bottom to top
z_deck   = lead_in;                       // deck top = slide origin plane (= lower tube top)
gate_z0  = z_deck + gap_z;                // plate underside
gate_z1  = gate_z0 + gate_t;              // plate top
// slot ceiling = rail height above the deck, so the housing pillar backs the
// FULL lip (no separate rail wall to create a coincident face) and the gate
// still keeps rh - (gap_z + gate_t) of headroom under the ceiling.
z_slotT  = z_deck + rh;
z_upper  = z_slotT;                       // upper tube resumes here
z_total  = z_upper + lead_in;             // top tube end face (top port sits here)
assert(z_slotT >= gate_z1 + 0.4, "SHUTTER: slot ceiling must clear the plate top.");

echo(str("nuggs-shutter-valve: bore ", bore_d, " (ri ", ri, "), gate ", gate_w,
         " x ", gate_w, " x ", gate_t, " mm, travel ", travel, " mm, rail_h ",
         rh, " mm, module ", 2 * hx, " x ", hy_closed + hy_open, " x ", z_total, " mm"));

// ---------------------------------------------------------------------------
// Design-level asserts (coupling guards live in nuggs_cfg()).
// ---------------------------------------------------------------------------
assert(lead_in >= z_top, str(
    "SHUTTER LEAD-IN: lead_in = ", lead_in, " mm is shorter than the port zone ",
    "z_top = ", z_top, " mm. Each port fuses to that much full-round shell."));
assert(gate_over > 0, "SHUTTER gate_over must be positive so the plate seals with margin.");
assert(wall_in > gate_r, "SHUTTER rail wall must sit outboard of the plate edge.");

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------
module shell(z0, z1) {
    translate([0, 0, z0]) difference() {
        cylinder(r = ro, h = z1 - z0);
        translate([0, 0, -eps]) cylinder(r = ri, h = z1 - z0 + 2 * eps);
    }
}

// Internal edge break at a bore mouth. Cut only; only ever widens the bore.
module bore_lead(z, dir = 1) {
    translate([0, 0, z]) rotate([dir > 0 ? 0 : 180, 0, 0])
        cylinder(r1 = ri + 1.0, r2 = ri - eps, h = 1.0 / tan(90 - chamfer_ang));
}

// The bore-region housing (deck to slot ceiling), plus a 45-degree self-
// supporting skirt down to the tube so its wide underside never faces the bed
// as a flat overhang. The skirt bottoms out above the port zone so the bottom
// coupling stays free to mate.
module housing_core() {
    translate([-hx, -hy_closed, z_deck])
        cube([2 * hx, hy_closed + core_y1, z_slotT - z_deck]);
    // 45-degree skirt: full slab outline at the deck tapering to a tube-hugging
    // footprint ~ (hx - ro) below it, i.e. a 45-degree underside on the ±X sides.
    skirt_drop = hx - (ro + 2);
    hull() {
        // top slab overlaps the housing block by `weld` (not an eps kiss)
        translate([-hx, -hy_closed, z_deck]) cube([2 * hx, hy_closed + core_y1, weld]);
        translate([-(ro + 2), -(ro + 2), z_deck - skirt_drop])
            cube([2 * (ro + 2), (ro + 2) + core_y1, eps]);
    }
}

// The retract-drawer pedestal: a solid base from the bed up to the slot, under
// the +Y pocket, so the long drawer is carried on bed contact with vertical
// walls (no flat overhang) instead of cantilevering. Clears the bottom port
// (ped_y0 > r_out). The slide-chamber cut opens the gate slot through its top.
module pedestal() {
    // reaches the true bed plane (z = -port_proj, where the bottom port's
    // sector tips land) so it carries real first-layer contact and the tall
    // part does not stand only on the port tripod.
    translate([-hx, ped_y0, -port_proj])
        cube([2 * hx, hy_open - ped_y0, z_slotT + port_proj]);
}

// The slide chamber void: the thin slab the plate lives in and slides through,
// open to the +Y pocket. Leaves the ±X pillars and the -Y wall intact.
module slide_chamber() {
    // Starts at z_deck (not z_deck+gap_z): the gate rides gap_z (0.6 mm) above
    // the deck/pedestal, so that 0.6 mm band under the plate MUST be void — cut
    // it here or the plate welds to the seat with only an eps sliver of gap that
    // the mesh shows as two bodies but a slicer fuses solid.
    translate([-wall_in, -(ri + 2), z_deck - eps])
        cube([2 * wall_in, (ri + 2) + hy_open + eps,
              (z_slotT + eps) - (z_deck - eps)]);
}

// Continuous capture lip on one rail wall, over y0..y1. Built from the
// library's exposed lip profile so the acoustic clearances are the
// battleship's, not re-typed here. side = +1 / -1 picks the rail. The coupon
// reuses this over a short range, so tuning door_fit on it transfers exactly.
module cont_lip(side, y0 = -hy_closed, y1 = hy_open) {
    translate([side * wall_in, y1, z_deck])
        rotate([90, 0, 0])
            linear_extrude(y1 - y0)
                polygon(pip_lip_profile(side, lz, rh, lip_d, lip_drop, lip_bury));
}

// The caller-owned rail wall the lip lives on (pip_rail_h tall, eps into deck).
module rail_wall_solid(side, y0 = -hy_closed, y1 = hy_open) {
    translate([side * wall_in - (side > 0 ? 0 : rail_wall), y0, z_deck - eps])
        cube([rail_wall, y1 - y0, rh + eps]);
}

// A light detent: a low transverse bump on the deck that the plate's leading
// edge rides over, seating it at closed (y=0) and open (y=travel).
module detent_bump(y) {
    translate([0, y, z_deck]) rotate([0, 90, 0])
        cylinder(r = detent_h, h = gate_w * 0.7, center = true, $fn = 16);
}

// The shutter plate + tabs + handle, in its current (open-fraction) position.
module shutter() {
    dw = gate_w - 2 * door_fit;
    translate([0, open_y, 0]) {
        // sealing plate (fit-shrunk so door_fit tunes the slide, not the seal)
        translate([-dw / 2, -gate_r, gate_z0]) cube([dw, gate_w, gate_t]);
        // door-side tabs riding under the continuous lip
        translate([0, 0, gate_z0]) slide_tab(gate_w, tab_c = [0], fit = door_fit, gap_z = 0);
        // handle: a pull-tab off the +Y (outboard) edge
        translate([-handle_w / 2, gate_r, gate_z0])
            cube([handle_w, handle_reach, gate_t + handle_t]);
    }
}

// ---------------------------------------------------------------------------
// The valve — one captive print-in-place part.
// ---------------------------------------------------------------------------
module valve() {
    union() {
        difference() {
            union() {
                nuggs_port(cfg);                                  // bottom port
                translate([0, 0, z_total]) mirror([0, 0, 1]) nuggs_port(cfg);
                shell(0, z_total);                                // ONE full-height tube (housing wraps it)
                housing_core();
                pedestal();
            }
            nuggs_bore_cut(cfg, -port_proj - 2, z_total + port_proj + 2);
            translate([0, 0, -port_proj]) bore_lead(0.001, 1);
            translate([0, 0, z_total + port_proj]) mirror([0, 0, 1]) bore_lead(0.001, 1);
            slide_chamber();
            // (No pocket-roof cut: nothing is built above the slot ceiling over
            // the drawer, so the pocket is already open-topped. An earlier cut
            // here sliced tangentially into the round upper tube and the top
            // port's +Y sectors — a grazing cut that shatters the OpenSCAD
            // Manifold export into 20 shells while CGAL/manifold3d paper over it.
            // Issue #99 / PR #200: this is the "only Manifold tells the truth" bug.)
        }
        // The capture lips are added AFTER the cuts: they root deep into the
        // surviving housing pillars (a real `lip_bury` overlap Manifold fuses,
        // not a coincident-face kiss) and their overhang reaches into the
        // just-cut chamber without being clipped. Travel is bounded by the
        // housing walls themselves — the -Y wall is the closed stop, the +Y
        // pocket end the open stop — so there are no separate end-stop ridges,
        // and no deck detent (the closed position sits over the open bore, which
        // has no deck to carry a bump; friction + the wall stops hold it).
        for (s = [-1, 1]) cont_lip(s);
        shutter();
    }
}

// ---------------------------------------------------------------------------
// "Print this first" coupon: the slide fit as a compact fixture, straight from
// the same rail/lip/tab modules the valve uses (nothing copied), so door_fit
// tuned here transfers exactly. Full gate WIDTH (the rattle across the span is
// the acoustic property), short LENGTH so it prints in minutes. Dropped so the
// deck sits near the bed. See NOTES.md "Print this first".
// ---------------------------------------------------------------------------
module coupon() {
    clen  = 46;                         // slide length
    cglen = 30;                         // gate length in Y (short)
    cw    = wall_in + rail_wall;        // coupon base half-width
    dz    = 3 - z_deck;                 // drop the deck plane to z = 3
    translate([0, 0, dz]) {
        translate([-cw, 0, z_deck - 3]) cube([2 * cw, clen, 3]);   // base to bed
        for (s = [-1, 1]) { rail_wall_solid(s, 0, clen); cont_lip(s, 0, clen); }
        dw = gate_w - 2 * door_fit;
        gy = cglen / 2 + 3;
        translate([0, gy, 0]) {                                    // captive gate
            translate([-dw / 2, -cglen / 2, gate_z0]) cube([dw, cglen, gate_t]);
            translate([0, 0, gate_z0]) slide_tab(gate_w, tab_c = [0], fit = door_fit, gap_z = 0);
        }
        detent_bump(gy);   // the closed-position click, so the coupon tests feel too
    }
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------
if (part == "valve" || part == "assembled") valve();
else if (part == "shutter") shutter();
else if (part == "cutaway")
    difference() { valve(); translate([-300, 0, -50]) cube([600, 300, 600]); }
else if (part == "coupon") coupon();
else assert(false, str("unknown part: ", part));
