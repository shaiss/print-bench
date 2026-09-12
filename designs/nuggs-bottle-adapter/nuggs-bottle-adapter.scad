// N.U.G.G.S. bottle adapter — screw a standard PCO-1881 water bottle into a
// NUGGS port, so an off-the-shelf bottle becomes a drop-in habitat module.
// Requirements, sources and decisions: NOTES.md next to this file. All
// dimensions in millimeters.
//
// WHAT IT IS. One printed body, two interfaces. Below: the standard genderless
// quarter-turn NUGGS port (lib/nuggs-coupling.scad at its default 80 mm bore —
// the library's constants ARE the standard). Above: a threaded throat that
// takes a stock PCO-1881 bottle finish (the world soda/water-bottle neck:
// SINGLE-start 2.7 mm pitch thread, 27.4 mm crest, 650 deg of engagement).
// Between them an exterior shoulder cone closes the 84.8 mm tube down to the
// ~34 mm throat while an interior funnel opens the bore up into that same
// throat — the passage never pinches below the bottle's own orifice.
//
// WHY A LIBRARY THREAD, NOT THE BOTTLE'S PROFILE. The bottle's flanks are
// ~15 deg helicoid; printed as a female cavity they would bridge and sag. The
// female thread here is lib/threads-fdm's 45-degree-flank trapezoidal helix —
// printable in a vertical bore — grown by `tol` off the bottle's crest
// diameter. That swap caps how deep the female thread can be: the FDM profile
// must fit inside one pitch (0.675 mm root width + flank widening + 2 x depth
// < 2.7 mm), so depth ~ 0.6 mm rather than the bottle's own 1.6. The coupon
// exists because that trade is exactly what a real bottle has to agree to.
//
// ORIENTATION. Prints standing on the port's sector tips, the family pose (see
// designs/nuggs-turnaround): every sloped surface — the ~40 deg exterior
// shoulder, the 44 deg interior funnel, the 45 deg thread flanks and the rim
// lead-in — sits at or under the 45-degree supportless ceiling, so the part
// needs no supports.
//
// LOAD PATH. The bottle screws in mouth-down and sits ABOVE the adapter, so
// gravity seats its lip ONTO the printed land annulus: the land carries the
// bottle's weight in compression and the thread only has to stop rotation
// (vibration, a nudging animal). The brief pictured the threads in tension —
// that is the bottle-up orientation; this arrangement is the stronger of the
// two, and the thread depth below is sized for retention, not for hanging.
//
// CONSTRUCTION — union(shells) − union(cavities), the turnaround discipline.
// The shell is the NUGGS port + the full-round shell behind it + the exterior
// shoulder cone + the throat tube, all unioned solid before anything is cut.
// The cavity is the port's owed bore cut (a port is NOT bore-clean) + the
// interior funnel + the throat's minor bore, helical thread groove and rim
// lead-in chamfer, all unioned before the single difference().

use <nuggs-coupling.scad>
use <threads-fdm.scad>

/* [Part] */
// What to render: the adapter body, the print-this-first fit coupon, or the
// half-section view (section on the y = 0 plane through the axis).
part = "adapter"; // [adapter, coupon, cutaway]

/* [NUGGS port] */
// Coupling bore diameter (mm) — the NUGGS standard bore. Must stay >= 70.
nuggs_bore_d = 80.0;
// Coupling wall thickness (mm) — the full-round shell behind the port face.
nuggs_wall = 2.4;
// Port radial clearance (mm), tunable 0.10-0.60. Tune on the coupon.
nuggs_port_tol = 0.30;

/* [PCO-1881 bottle finish] */
// The standard the throat is cut to (ISBT PCO-1881; cross-checked against
// BOSL2's bottlecaps.scad). These are NOT tuning knobs: a PCO-1881 bottle
// defines them, and the owner's ruling on the brief was "the standard is the
// spec". Only bottle_tol below is tuned, on the coupon.
// Thread crest (major) diameter of the bottle's finish, mm.
bottle_thread_od = 27.4;
// Thread axial pitch, mm. PCO-1881 is SINGLE-start: the brief's "multi-start"
// row was corrected against the standard (NOTES.md, Key decisions).
bottle_thread_pitch = 2.7;
// Thread starts. 1 per the standard; exposed so a sibling finish (PCO-1880,
// 3-start) is a table edit, not a rewrite.
bottle_thread_starts = 1;
// Thread travel from first contact to seated, degrees (1.8 turns).
bottle_engagement_deg = 650;
// The bottle's orifice (inner opening) diameter, mm — the land opening must
// never pinch below it, or the adapter chokes what the bottle passes.
bottle_orifice_id = 21.74;
// The bottle's sealing lip (top bead) diameter, mm — the land must be at
// least this wide under it or the lip overhangs the opening.
bottle_lip_od = 25.07;
// Height of the lip's sealing face above the thread's first contact, mm —
// how far past the thread the throat must stay open.
bottle_lip_to_thread = 1.70;
// Top of the bottle's tamper ring below the lip face, mm — our rim must stay
// below this or the ring bottoms out on it before the thread seats.
bottle_tamper_below_lip = 10.8;

/* [Fit] */
// Female thread depth, mm. Capped by the FDM profile fitting inside one
// pitch (see the ridge-land assert): deeper grips more but thins the ridge
// between thread turns below two extrusion widths.
f_thread_depth = 0.6;
// Radial thread clearance, mm — THE tuning knob. Tune on the coupon in
// +/-0.05 steps: the station that grips without cracking is the value to
// set here. 0.15-0.38 swept on the coupon.
bottle_tol = 0.25;
// Coupon stations for bottle_tol, mm. Four tols on four labelled rings.
coupon_tols = [0.15, 0.22, 0.30, 0.38];

/* [Body] */
// Full-round shell height above the port face, mm — must back the whole port
// zone (z_top = 13 mm) so the sectors fuse to a ring, not a knife edge.
shell_h = 16;
// Interior funnel wall angle from vertical (deg) — the supportless ceiling
// over the bore. 44 leaves one degree of margin under the 45-degree limit.
funnel_deg = 44;
// Land annulus inner diameter, mm — the hole in the sealing floor. Must
// clear the bottle's orifice so the adapter never chokes the bottle.
land_opening_d = 22.0;
// Wall thickness around the thread groove, mm — from groove crest to part
// OD. The threaded section is the part's working surface; 3 mm is six
// extrusion widths at a 0.4 nozzle.
throat_wall = 3.0;
// Rim lead-in chamfer, mm — flares the bore mouth at 45 deg so the bottle's
// crest finds the groove instead of the rim's edge.
rim_chamfer = 1.5;

/* [Quality] */
// Curve resolution. Production 96; drop to 32 while iterating.
$fn = 96;
// Helix discretisation for the thread groove (facets per turn).
thread_seg = 96;

// ---------------------------------------------------------------------------
// Derived geometry. Computed once, asserted, echoed — never re-typed.
// ---------------------------------------------------------------------------

cfg   = nuggs_cfg(bore_d = nuggs_bore_d, wall = nuggs_wall,
                  port_tol = nuggs_port_tol);
ri    = nuggs_ri(cfg);      // bore radius                    40.0
ro    = nuggs_ro(cfg);      // tube OD radius                 42.4
r_out = nuggs_r_out(cfg);   // coupling ring OD radius        48.4
z_tip = nuggs_z_tip(cfg);   // sector tips (the bed)         -10.0
z_top = nuggs_z_top(cfg);   // port zone top                  13.0

land_ir   = land_opening_d / 2;                          // land opening  11.0
// Where the funnel reaches the land opening — the plane the bottle's lip
// seats on. The throat's bore cut is the wider surface there (f_minor_r >
// land_ir), so the BORE truncates the funnel, and the real pinch is the
// cone's radius at the plane the bore begins on. Aiming the cone at z_land
// let the opening drift slope*0.5 wide: measured Ø22.96 off the export
// against the 22.0 parameter, the issue #37 formula-vs-mesh drift class. So
// the cone is aimed past the plane — it crosses land_ir exactly at z_floor
// and keeps exactly funnel_deg throughout its visible span.
z_floor   = shell_h + (ri - land_ir) / tan(funnel_deg);  // land plane   ~46.0
z_land    = z_floor + 0.5;  // throat_cavity origin: its bore starts 0.5 low
cone_top_r = land_ir - 0.5 * tan(funnel_deg);            // cone end, interior
travel    = bottle_engagement_deg / 360 * bottle_thread_pitch
            * bottle_thread_starts;                     // seat travel 4.875
// Groove start above the land: past one pitch of runout, past where the
// bottle's thread can first touch, plus margin so the runout scallop never
// kisses the land plane (a coincident surface).
thread_off  = max(bottle_thread_pitch, bottle_lip_to_thread + 0.5) + 0.3;
thread_zone = 2 * bottle_thread_pitch * bottle_thread_starts;  // 2 full turns
throat_top  = thread_off + thread_zone + rim_chamfer;  // rim above land  9.9
z_rim       = z_land + throat_top;                     // part top     ~55.9

// Per-tolerance female-thread values. The land outer edge IS the minor bore:
// engagement between the bottle's crest and that bore is depth - tol.
function f_minor_r(tol)   = bottle_thread_od / 2 - f_thread_depth + tol;
function groove_crest_r(tol) = bottle_thread_od / 2 + tol;
function throat_or(tol)   = groove_crest_r(tol) + throat_wall;
// Solid ridge left between consecutive thread grooves, mm — the printable
// floor for the female thread. 0.25*pitch is the FDM root width.
function ridge_land(tol)  = bottle_thread_pitch
    - (0.25 * bottle_thread_pitch + flank_add(tol) + 2 * f_thread_depth);

cone_deg = atan((ro - throat_or(bottle_tol)) / (z_land - shell_h)); // ~40.3

// ---------------------------------------------------------------------------
// Guards. Each names the number that fired it and what to do.
// ---------------------------------------------------------------------------

assert(shell_h >= z_top, str(
    "SHELL: shell_h = ", shell_h, " mm does not back the whole port zone",
    " (z_top = ", z_top, " mm). The port's inner sectors need full-round",
    " shell to fuse to, or they stand on a knife edge."));
assert(funnel_deg <= 45, str(
    "FUNNEL CEILING: funnel_deg = ", funnel_deg, " deg exceeds the 45 deg",
    " supportless ceiling — the interior funnel would need supports the",
    " design promises it doesn't."));
assert(cone_deg <= 45, str(
    "SHOULDER CONE: the exterior cone runs ", cone_deg, " deg off vertical",
    " (ro ", ro, " to throat ", throat_or(bottle_tol), " over ",
    z_land - shell_h, " mm), past the 45 deg supportless ceiling. Deepen the",
    " shoulder or widen the throat."));
assert(land_opening_d >= bottle_orifice_id + 0.2, str(
    "LAND OPENING: ", land_opening_d, " mm chokes the bottle's own ",
    bottle_orifice_id, " mm orifice. The adapter must never pass less than",
    " the bottle it carries."));
assert(f_minor_r(bottle_tol) >= bottle_lip_od / 2 + 0.05, str(
    "LAND WIDTH: the land's outer radius ", f_minor_r(bottle_tol),
    " mm does not stand clear of the bottle's ", bottle_lip_od,
    " mm lip — the lip would overhang the opening instead of seating."));
assert(f_minor_r(bottle_tol) - land_ir >= 1.0, str(
    "LAND WIDTH: only ", f_minor_r(bottle_tol) - land_ir,
    " mm of annulus is left for the bottle's lip to seat on (floor 1.0 mm",
    " — two extrusion widths plus squish)."));
assert(thread_off + thread_zone
       >= bottle_lip_to_thread + travel + 0.3, str(
    "THREAD COVERAGE: the groove spans ", thread_off, " to ",
    thread_off + thread_zone, " mm above the land, but the bottle's thread",
    " first touches at ", bottle_lip_to_thread, " and travels ", travel,
    " mm to seat — it would run off the top of the thread zone."));
assert(thread_off - bottle_thread_pitch >= 0.25, str(
    "THREAD RUNOUT: the groove's runout scallop bottoms out ",
    thread_off - bottle_thread_pitch, " mm above the land plane — too close.",
    " A coincident surface there is how this geometry goes non-watertight."));
assert(ridge_land(bottle_tol) >= 0.5, str(
    "RIDGE LAND: only ", ridge_land(bottle_tol), " mm of ridge is left",
    " between thread turns (floor 0.5 mm). The FDM profile must fit inside",
    " one pitch: 0.25*pitch + flank_add(tol) + 2*depth < pitch. At pitch ",
    bottle_thread_pitch, " that caps depth near 0.85; cut f_thread_depth or",
    " bottle_tol, or the ridge prints as a string of separated blobs."));
assert(f_thread_depth - bottle_tol >= 0.2, str(
    "ENGAGEMENT: f_thread_depth - bottle_tol = ",
    f_thread_depth - bottle_tol, " mm of radial engagement is under the",
    " 0.2 mm floor — the thread barely retains anything. Raise",
    " f_thread_depth (the ridge-land assert caps how far)."));
assert(throat_wall >= 3 * 0.4, str(
    "THROAT WALL: ", throat_wall, " mm around the groove is under three",
    " perimeters at a 0.4 mm nozzle — the working surface would delaminate",
    " under thread torque."));
assert(throat_top <= bottle_tamper_below_lip - 0.5, str(
    "TAMPER CLEARANCE: the rim tops out ", throat_top,
    " mm above the land, but the bottle's tamper ring reaches down ",
    bottle_tamper_below_lip, " mm below its lip — the ring would bottom on",
    " the rim before the thread seats. Cut rim_chamfer or thread_zone."));
assert(z_rim - z_tip <= 199 && 2 * r_out <= 210, str(
    "BED FIT: the part is ", z_rim - z_tip, " mm tall x ", 2 * r_out,
    " mm across — the 199 mm printable height / 210 mm tightest horizontal",
    " bed axis of the gate's defaults don't take it. gate.sh would fail."));

// ---------------------------------------------------------------------------
// The adapter
// ---------------------------------------------------------------------------

// The throat's cavity, with the LAND PLANE at z = 0: minor bore, helical
// groove, rim lead-in. Shared by the body (land at z_land, funnel below it)
// and each coupon ring (land on a 3 mm base), so the two cannot drift apart.
module throat_cavity(tol, h_above_land) {
    // Minor bore up from the land. Starts half a millimetre BELOW it so the
    // bore wall meets the land floor in a clean square edge, not a coincident
    // cap.
    translate([0, 0, -0.5])
        cylinder(r = f_minor_r(tol), h = h_above_land + 1.5);
    // The female thread: the lib's 45-degree-flank helix, grown by tol off
    // the bottle's crest diameter. The cutter clips itself to the groove
    // band and runs one pitch of runout out past each end.
    translate([0, 0, thread_off])
        thread_bore_cut(d_major = bottle_thread_od, depth = f_thread_depth,
                        pitch = bottle_thread_pitch,
                        starts = bottle_thread_starts, length = thread_zone,
                        tol = tol, seg = thread_seg);
    // Rim lead-in: flare the bore mouth at exactly 45 deg so the bottle's
    // crest rides into the groove instead of catching the rim's edge.
    translate([0, 0, h_above_land - rim_chamfer])
        cylinder(r1 = f_minor_r(tol), r2 = f_minor_r(tol) + rim_chamfer,
                 h = rim_chamfer + 0.5);
}

module adapter_shell() {
    nuggs_port(cfg);                              // sectors down to z_tip
    cylinder(r = ro, h = shell_h);                // full-round port backup
    translate([0, 0, shell_h])                    // exterior shoulder cone
        cylinder(r1 = ro, r2 = throat_or(bottle_tol), h = z_land - shell_h);
    translate([0, 0, z_land])                     // throat tube to the rim
        cylinder(r = throat_or(bottle_tol), h = throat_top);
}

module adapter_cavity() {
    // The port's owed bore cut: r = ri through the whole port zone, one
    // millimetre past the shell so its cap can never coincide with the
    // funnel's start.
    nuggs_bore_cut(cfg, z_tip - 2, shell_h + 1);
    // Interior funnel: ri at the shell top, crossing the land opening exactly
    // at z_floor (where the throat's bore truncates it) and running a
    // half-millimetre past into the bore's interior so the two cuts always
    // overlap, never coincide. One degree under the supportless ceiling.
    translate([0, 0, shell_h])
        cylinder(r1 = ri, r2 = cone_top_r, h = z_land - shell_h);
    // Throat: land plane at z_land.
    translate([0, 0, z_land]) throat_cavity(bottle_tol, throat_top);
}

module nuggs_bottle_adapter() {
    difference() {
        adapter_shell();
        adapter_cavity();
    }
}

// ---------------------------------------------------------------------------
// The coupon — print this first
// ---------------------------------------------------------------------------

// Two stations, one plate. Station 1: the library's own port stub in the
// family pose (nuggs_neck standing on its sector tips — the same shape every
// NUGGS module tunes port_tol on). Station 2: four labelled throat rings, one
// per coupon_tol, each carrying the production throat_cavity verbatim on a
// 3 mm base, with the land opening running through to the strip so air
// escapes when a bottle screws in. Two disconnected bodies on purpose: the
// coupon is a hand-held fixture, popped off the plate and tried.
ring_base_h = 3.0;   // material under the land, so the annulus is not a knife edge
ring_dx     = 40;    // ring spacing along the strip
ring_col_x  = [r_out + 4 + ring_dx / 2 + 2, r_out + 4 + ring_dx / 2 + 2 + ring_dx];
ring_row_y  = [-21, 21];
strip_x1    = ring_col_x[1] + throat_or(max(coupon_tols)) + 6.4;
strip_y     = 46;    // half-width

module coupon_ring(tol) {
    ring_h = ring_base_h + throat_top;
    difference() {
        cylinder(r = throat_or(tol), h = ring_h);
        // Land opening through to the strip: air escape when the bottle
        // screws in, and daylight through the seat for checking contact.
        translate([0, 0, -0.5]) cylinder(r = land_ir, h = ring_h + 1.5);
        translate([0, 0, ring_base_h]) throat_cavity(tol, throat_top);
    }
}

module bottle_fit_coupon() {
    assert(len(coupon_tols) == 4, str(
        "COUPON: this coupon is laid out 2x2 for four tols, got ",
        len(coupon_tols), "."));
    assert(strip_x1 <= 250 && 2 * strip_y <= 210, str(
        "COUPON BED FIT: the strip runs ", strip_x1, " x ", 2 * strip_y,
        " mm plus the port stub beside it — outside the gate's default",
        " build volume."));
    assert([for (t = coupon_tols) if (ridge_land(t) < 0.45) t] == [], str(
        "COUPON RIDGE: a station's ridge land fell under the 0.45 mm coupon",
        " floor (body floor is 0.5; a test ring may run a hair thinner,",
        " but not to stringiness)."));
    difference() {
        union() {
            // Station 1: the port stub in the family coupon pose.
            nuggs_neck(cfg, z_top + 8);
            // Station 2: the strip, rings, and the label bosses.
            translate([r_out + 4, -strip_y, 0])
                cube([strip_x1 - r_out - 4, 2 * strip_y, 2.4]);
            for (row = [0, 1])
                for (col = [0, 1])
                    translate([ring_col_x[col], ring_row_y[row], 2.4])
                        coupon_ring(coupon_tols[row * 2 + col]);
        }
        // Labels, cut 0.5 mm into the strip top outboard of each row: the
        // tol value beside the ring it sizes.
        for (row = [0, 1])
            for (col = [0, 1])
                translate([ring_col_x[col],
                           (row ? 1 : -1) * (strip_y - 4.5), 1.9])
                    linear_extrude(0.6)
                        text(str(coupon_tols[row * 2 + col]), size = 4,
                             halign = "center", valign = "center");
    }
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------

echo(str("nuggs-bottle-adapter: land z=", z_floor, "  rim z=", z_rim,
         "  height ", z_rim - z_tip, "  envelope ", 2 * r_out,
         "  cone ", cone_deg, " deg"));
echo(str("  thread: depth ", f_thread_depth, "  tol ", bottle_tol,
         "  engagement ", f_thread_depth - bottle_tol, "  ridge land ",
         ridge_land(bottle_tol), "  throat OD ", 2 * throat_or(bottle_tol)));
echo(str("  bottle seat: travel ", travel, "  groove ", thread_off, "-",
         thread_off + thread_zone, " above land  (lip contact ",
         bottle_lip_to_thread, "-", bottle_lip_to_thread + travel, ")"));

if (part == "adapter") nuggs_bottle_adapter();
else if (part == "coupon") bottle_fit_coupon();
else if (part == "cutaway")
    // Section on the y = 0 plane through the axis: the funnel opening into
    // the throat, the land annulus, the groove profile and the rim lead-in.
    difference() {
        nuggs_bottle_adapter();
        translate([0, -300, -200]) cube([300, 600, 600]);
    }
else assert(false, str("nuggs-bottle-adapter: unknown part '", part, "'"));
