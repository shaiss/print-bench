// NUGGS open module — a straight with a longitudinal window, the part that
// RESETS a run. A NUGGS run of continuously-enclosed bore is capped at
// 2 x body length (charter N2, designs/nuggs/PM.md); an open module — a
// longitudinal window >= 180 deg whose floor is still the bore's own arc —
// is one of the only three things that break a run (open end, open module,
// turnaround node). This is that part: two `nuggs_neck()` ports joined by a
// tube whose midspan opens into the window. Drop it into a run anywhere you
// want to see and reach the animal without disconnecting anything.
// Requirements, welfare sources and decisions: see NOTES.md next to this
// file. All dimensions in millimeters.
//
// This design is a CONSUMER of the port standard, exactly like
// designs/nuggs and nuggs-elbow: it builds ONE cfg with nuggs_cfg() and
// hands it around, and it defines no coupling geometry of its own. The only
// new geometry is the WINDOW — and the window itself is the library's
// (nuggs_window), so what this file owns is the composition and the
// parameters. The floor is the ri arc, never a flat trough (charter N11),
// and the window clears the walk band (+/-40 deg about the invert), both
// asserted inside nuggs_window() itself.
//
// PRINT ORIENTATION (issue #34, adopted into #116). The part prints with
// the tube axis VERTICAL, standing on the lower port's sector tips — the
// same pose as every NUGGS module. In that pose the window's azimuth is
// horizontal by definition (it faces +X in the library frame, sideways),
// and that is print-irrelevant: every layer is the identical 170 deg
// annulus segment, so no window surface faces the bed, the two mouth
// planes print as flat 2.4 mm bridges and the two rim walls stand as the
// near-vertical shells the brief names. The brief forbids window-DOWN (the
// floor arc would overhang its own bore) — the vertical axis is the only
// self-supporting pose there is (a horizontal axis puts either the bore
// ceiling or the remaining hull's flanks past 45 deg), confirmed on the
// render and the test-slice: no supports, bed contact on the three sector
// tips alone. The 45 deg ceiling from bore-axis-vertical printing applies
// to the bore-mouth overhangs exactly as it does on the straight.
use <nuggs-coupling.scad>

/* [What to render] */
// open = the printable part; pair = two open modules coupled (review
// preview only); cutaway = sectioned to inspect the floor continuity.
part = "open";  // [open, pair, cutaway]

/* [The NUGGS standard - change these and nothing you already printed fits] */
// Every value here is a nuggs_cfg() default: this module inherits the
// standard so it mates with designs/nuggs and every other module. They are
// exposed for the Customizer, not for tuning — the coupling guards fire
// inside nuggs_cfg().
// Internal bore (mm) - the headline number. Asserted >= min_bore_mm by the lib
bore_d = 80.0;
// Tube shell thickness (mm). ro = bore_d/2 + wall is the datum every coupling
// radius is measured from
wall = 2.4;
// Radial depth of the coupling ring beyond the tube OD (mm)
lug_r = 6.0;
// Axial projection of the coupling sectors past the tube face (mm)
port_proj = 10.0;
// Backing-collar thickness (mm)
collar_t = 3.0;
// Coupling sectors per face (3 = kinematically determinate)
n_lug = 3;
// Angular width of each sector (deg). Asserted lug_deg + twist_deg <= pitch/2
lug_deg = 40;
// Radial depth of the locking rib (mm)
rib_h = 1.0;
// Axial width of the locking rib / groove (mm)
rib_w = 2.4;
// Angular width of the locking rib (deg)
rib_deg = 12;
// The locking twist (deg). Asserted rib_deg + twist_deg <= lug_deg
twist_deg = 14;
// Overlap fusing the ribs into the outer sectors (mm). Never zero
bite = 0.8;

/* [Fit & tolerances] */
// The one knob. Uniform clearance on every coupling surface (mm). Owned by
// the standard; tuned on designs/nuggs's coupon, not re-tuned here.
// Asserted 0.10-0.60 by the lib
port_tol = 0.30;

/* [The window] */
// Window arc (deg). >= 180 is what makes this module a break in a run
// (charter N2) and the default 190 buys margin against shrink pulling the
// printed part under 180. Asserted <= 280 by the lib (walk band).
open_deg = 190;
// Face-to-face body length (mm), same as the plain straight's body_len_mm
// default, so a run alternates straights and opens predictably
body_len = 180;
// Full-round shell kept at each end (mm). Must be >= the port zone z_top;
// it is what the port's inner sectors fuse to (a window edge would let
// them snap off, silently)
neck_len = 30;
// Full-round shell between a window mouth and the end of the window (mm),
// read-only derived: what is left of the body once the necks are taken
//window_len = body_len - 2 * neck_len;  // derived below

/* [Welfare limits - asserted, not tunable down] */
// DTSchB entrance minimum, pouch-full criterion (mm). NEVER lower this.
// The bore floor itself is asserted inside nuggs_cfg()
min_bore_mm = 70;
// A window below 180 deg does not break a run (charter N2) — this module
// would be a lie. A window past 280 eats the walk band (lib guard).
assert(open_deg >= 180, str(
    "OPEN DEG: open_deg = ", open_deg,
    " deg is below the 180 deg break threshold. Below 180 the wall tops rise",
    " above the springline, the opening stops being the widest part of the",
    " void, and the module stops being a break in a run — it is then just a",
    " straight with a slot, and a straight is designs/nuggs's part to be.",
    " Raise open_deg to >= 180 (default 190 for shrink margin)."));

/* [Print settings] */
// Nozzle diameter (mm) - feeds the wall and web guards in the lib
nozzle = 0.4;
// House angle for the bore-mouth edge break (deg)
chamfer_ang = 50;

/* [Quality] */
// This design's own quality preset. Iterating: $fa=6/$fs=1.5.
// Production: $fa=2/$fs=0.5. It does NOT reach the coupling or the window:
// the library pins its own $fa/$fs inside every geometry module body,
// deliberately, so the realised fit cannot move with a consumer's quality
// preset. These settings shape nothing of the joint or the window cut.
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

// The contract values this design reaches for.
ri    = nuggs_ri(cfg);      // bore radius
ro    = nuggs_ro(cfg);      // tube outer radius
r_out = nuggs_r_out(cfg);   // coupling ring OD / envelope
z_top = nuggs_z_top(cfg);   // top of the port zone; the neck must back this much
pitch = nuggs_pitch(cfg);   // sector pitch

// ---------------------------------------------------------------------------
// Window geometry
// ---------------------------------------------------------------------------
// Window longitudinal extent (mm): everything between the two necks. The
// brief assumes ~120 of the 180 body; with neck_len 30 that is exactly
// 180 - 2*30 = 120, and the window fills it, wall to wall — the mouths land
// exactly at the neck windows' edge. The lib asserts z0 >= z_top; the neck
// supplies that much full-round shell and more (30 > 13).
window_len = body_len - 2 * neck_len;

// The tube-with-a-window midspan. One continuous ri..ro shell from z0 to z1
// with the window cut through it; the floor stays the ri arc (N11).
//
// The window is centred on +X in the library frame; the invert (-X) is the
// floor. The port at z = 0 is the lower end (its sectors project to -z, the
// bed side); the port at z = body_len is mirrored so its sectors project
// to +z (away from the tube). Exactly the straight's two-port idiom.
module windowed_midspan(z0, z1) {
    difference() {
        translate([0, 0, z0]) cylinder(r = ro, h = z1 - z0);
        nuggs_window(cfg, z0, z1, open_deg);
    }
}

// Print this first: a bore-clean port on a short full-round stub — the same
// fit coupon designs/nuggs, nuggs-den, nuggs-frieda and nuggs-orrery ship.
// The fit is the standard's, owned by the lib and tuned on designs/nuggs's
// coupon; this coupon re-proves the port at this design's own build, it
// does not re-derive it.
module nuggs_open_coupon() {
    nuggs_neck(cfg, z_top + 8);
}

// ---------------------------------------------------------------------------
// Design-level asserts. These fail the render, not a lint pass. The coupling's
// own guards live in nuggs_cfg(); nuggs_window()'s walk-band and z0 guards
// fire where it is called. What is left belongs to THIS design.
// ---------------------------------------------------------------------------
assert(neck_len >= z_top, str(
    "OPEN NECK: neck_len = ", neck_len, " mm is shorter than the port zone",
    " z_top = ", z_top, " mm. Each port fuses to that much straight full-round",
    " shell; a shorter neck leaves its inner sectors fused to a window edge,",
    " where they snap off silently. Raise neck_len."));
assert(window_len > 0, str(
    "OPEN WINDOW LEN: window_len = body_len - 2*neck_len = ", window_len,
    " mm must be positive. The window has to fit between the two necks."));
// The window cannot be wider than the walk band allows; the lib asserts
// open_deg <= 360 - 2*40 = 280 at the call. 190 <= 280 with 90 deg to spare.
// The rim walls: at open_deg = 190, each rim wall spans (360-190)/2 = 85 deg
// of arc on the ri..ro shell. Minimum wall thickness = wall (2.4) — the rim
// is a full shell wall, not a thin fin. The brief's >= 1.2 mm rim floor is
// met by construction and measured on the export (G4).

// ---------------------------------------------------------------------------
// The part
// ---------------------------------------------------------------------------
module nuggs_open() {
    difference() {
        union() {
            nuggs_neck(cfg, neck_len);                     // lower port + shell
            // Upper port MIRRORED so its sectors project +z, out past the top
            // face — the straight's second-port idiom (nuggs.scad:339, elbow
            // :244). Unmirrored they point DOWN into the tube and the port
            // cannot couple; the part still reads watertight and gates green,
            // which is exactly why this is measured on the export (G4), not
            // read off the variable. Mirror about z = body_len: tube spans
            // body_len-neck_len..body_len, sector tips reach body_len+port_proj.
            translate([0, 0, body_len]) mirror([0, 0, 1])
                nuggs_neck(cfg, neck_len);                 // upper port + shell
            // Midspan, built upward from the lower neck's top face.
            windowed_midspan(neck_len, body_len - neck_len);
        }
        // ONE continuous bore cut, through the whole part — the straight's
        // idiom (nuggs.scad:340). Not optional here: the necks cut their own
        // bores, but the midspan cylinder is SOLID, and nuggs_window() only
        // removes a wedge from ri-1 OUTWARD — it opens the wall, it does not
        // hollow the tube. Without this cut the part ships a solid core of
        // radius ri-1 through the window span: watertight, sliceable, gate
        // 84/100, 687 cm3, and no animal fits through it. Measured, not
        // guessed (G4: 852 g computed vs ~124 g expected).
        nuggs_bore_cut(cfg, -port_proj - 2, body_len + port_proj + 2);
        // Edge break at both bore mouths (chew-safety, N6): the mouths are
        // at -port_proj (lower sectors project down) and +body_len+port_proj
        // (upper mirrored port projects up past the face).
        translate([0, 0, -port_proj]) bore_lead(0.001);
        translate([0, 0, body_len + port_proj])
            mirror([0, 0, 1]) bore_lead(0.001);
    }
}

// Internal edge break at a bore mouth: swallows any first-layer lip so no
// edge is ever presented to a claw or a loaded cheek pouch. Cut, never
// added; it only ever widens the bore. Local frame: mouth at z, opening
// toward -z.
module bore_lead(z) {
    translate([0, 0, z])
        cylinder(r1 = ri + 1.0, r2 = ri - eps, h = 1.0 / tan(90 - chamfer_ang));
}

// Two open modules coupled: the run's-eye view. Review preview only — the
// window does not couple to anything; each part prints as the `open` part.
// Part 2 is mirrored ABOUT THE TOP FACE PLANE z = body_len (z' = 2*body_len -
// z), so its face lands on part 1's face with its sectors interleaved into
// part 1's (elbow pair idiom: the genderless interleave is half a pitch).
module pair() {
    color("#e8b7c8") nuggs_open();
    translate([0, 0, 2 * body_len]) rotate([0, 0, pitch / 2])
        mirror([0, 0, 1]) color("#cdd6e0") nuggs_open();
}

if (part == "open") nuggs_open();
else if (part == "coupon") nuggs_open_coupon();
else if (part == "pair") pair();
// Section on the y=0 plane, keeping y<0, through the window's crown (+X):
// shows the bore-arc floor running the full window with no interior ledge
// (the elbow's cutaway idiom, elbow.scad:278 — the cube must START at y=0,
// not straddle it, or the section removes the whole part).
else if (part == "cutaway")
    difference() { nuggs_open(); translate([-300, 0, -50]) cube([600, 300, 600]); }
else assert(false, str("nuggs-open: unknown part '", part, "'"));
