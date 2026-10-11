// N.U.G.G.S. turnaround TEE — the three-port turnaround: everything the
// two-port node is, plus a third port on the chamber crown, anti-parallel to
// the bed ports, so a run can pass STRAIGHT THROUGH the turnaround instead of
// only switching back. Brief: issue #435 (the 2-vs-3-ports decision deferred
// from #394; owner decision on-thread: build it as a derivative). All
// dimensions in millimeters. Requirements, welfare sources and decisions:
// NOTES.md next to this file.
//
// DERIVATIVE of designs/nuggs-turnaround (single parent, include order in
// derives.conf). OpenSCAD cannot extend a module, so every module that bakes
// in a changed number is restated here; everything else — the coupling cfg,
// neck(), bore_lead(), vents' teardrops, the coupon, the fitcheck parts and
// the part dispatch — is inherited verbatim and routes to these redefinitions.
// No parent variable is reassigned (that would WARN on every render): the
// changed values get NEW names (tee_*) and the modules that read them are
// restated. What changes and why, in one place:
//
//   chamber_az  90 -> 84   the crown port's face must land at z = 177 so the
//   chamber_zc 92.4->86.4  whole part fits the 199 mm test-slice ceiling with
//                          the crown port's sectors on top (total 197). zc
//                          stays = az + wall exactly, keeping the parent's
//                          pole-flush belly (its own assert).
//   port C (new)           anti-parallel port on the crown at (x_c, 0), axis
//                          print-z, face up. ANTI-PARALLEL is the only legal
//                          clocking: a port angled off vertical would put its
//                          own bore ceiling beyond 45 deg (issue #34's
//                          supportless limit) somewhere around the mouth.
//   crown cap              REPAIRED, not inherited — see the cap block below.
//
// THE CROWN CAP REPAIR (the parent's roof slot). The parent closes the
// chamber's far end with a barrel vault: a gable whose ridge line runs along
// y at constant height. That ridge outruns the outer dome's y-falloff — the
// vault pokes THROUGH the roof for |y| > 27.6 mm (parent numbers), opening a
// through-slot up to ~60 mm wide over each y-end of the chamber. The parent's
// two crown asserts only guard the y = 0 statement (ridge under the pole), so
// nothing fires; its committed cutaway-cross camera sits at y = 0, where the
// slot is not, so no frozen shot shows it either. Measured on the parent
// mesh: outer pole 184.8, ridge 181.4, slot band |y| in [27.6, 84.9]. A tee
// cannot inherit that cap: port C's collar stands on the crown at y = 0 +- 48
// and the slot band starts at |y| = 32.8 in tee numbers — the port would open
// into open air. The repair keeps the vault's two >= 45 deg x-planes and ADDS
// the hip the vault always needed: two planes descending at 46 deg in |y|,
// positioned to pass 1.5 mm UNDER the inner ellipsoid where that surface
// crosses the ridge height, so the shallow polar band of the ellipsoid (the
// ~23 x ~77 mm ellipse about the pole where its own slope is under 45 deg —
// the measured 9400 mm2 unbridgeable ceiling the parent's gate iterations
// chased) is covered by a plane everywhere it would otherwise govern. The
// cavity's crown boundary becomes min(ellipsoid, x-gable, y-hip) pointwise:
// every governing surface is >= 45 deg by construction, and the roof keeps
// >= 2.7 mm of shell over it everywhere (sampled assert below — the guard the
// parent lacked, held over a grid rather than at y = 0 only).
//
// THE A->C ROUTE (why port C sits at x_c = +3, not on the chamber axis). In
// use the animal walks the dish floor (the ellipsoid's +x flank) and steps
// onto port C's bore floor, the plane x = x_c + ri. The dish meets that plane
// on its own meridian at z*, and the walking grade at the handoff is the
// dish's slope there — steeper the higher the crossing. x_c = 0 puts the bore
// floor at x = 40: crossing at z* = 130.5, grade 19.0 deg, over charter N4's
// 15 deg. x_c = +3 drops the bore floor INTO the dish (x = 43): crossing at
// z* = 120.3, grade 13.87 deg, inside N4 with margin, and the handoff is a
// pure widening — the dish's floor falls onto the bore's flat floor with no
// lip in either direction. From z* the route rides C's flat bore floor the
// remaining 57 mm to the face.
//
// PRINT. Exactly the parent's pose — ports A and B stand on their sector
// tips, bore vertical at both — with port C's ring uppermost (its tips at
// z = 197; the gate's bare-default test-slice ceiling is 199). In USE the
// module lies as the parent does: dish down, vented flank up, ports
// horizontal; port C is then the straight-through exit and A/B the switchback.

include <../nuggs-turnaround/nuggs-turnaround.scad>

// NUGGS-ecosystem declaration. This derivative incorporates the NUGGS coupling
// standard through its parent (nuggs-turnaround `use`s it), so the modules are
// already in scope — and the design catalog resolves that inheritance through
// the include closure (issue #517), so the tee is grouped under NUGGS as the
// module it is without redeclaring the `use` here.

/* [The tee] */
// Chamber ellipsoid inner z semi-axis (mm) — the use-travel/print-vertical
// direction. 84 (parent 90) drops the crown by 6 so port C's sectors top out
// at 197 mm, inside the 199 mm the gate's test-slice can cut. x/y semi-axes
// are the parent's (unchanged): the clear internal width 2*chamber_ay is the
// N2 number and does not move.
tee_az = 84;
// Chamber centre height above the port face plane (mm). = tee_az + wall
// exactly (the parent's pole-flush belly rule: the outer belly's bottom pole
// lands flush with the face plane so nothing hangs under the web bridge).
tee_zc = 86.4;
// Where the repaired crown cap takes over from the ellipsoid (mm). Must stay
// above the crossing route's envelope (tops at tee_zc + 32.4) and below the
// pole by enough that the x-gable still fits inside the shell.
tee_crown_zt = 125;

/* [Port C - the crown port] */
// Offset of port C's axis toward the use-floor (+x) from the chamber axis
// (mm). Derived from N4, not looks: +3 puts the bore floor at x = 43, where
// the dish crosses it at 13.87 deg; on-axis (0) the crossing grades 19.0 deg.
port_c_x = 3.0;
// Height of port C's face plane above the bed ports' face plane (mm). With
// the sectors on top the part totals port_c_face + 20 = 197 mm.
port_c_face = 177;
// Where port C's neck shell and bore cut start (mm) — deep enough that both
// base discs bury strictly inside the ellipsoids (sampled asserts below), so
// the dome-to-tube junction is a clean transverse pierce with no cap face
// surviving on any interior wall.
port_c_base = 113;

/* [The repaired crown cap] */
// Slope of the hip's y-planes (deg from horizontal). Just past the 45 deg
// supportless ceiling, matching the vault's own "just past" rule.
hip_deg = 46;

/* [Hidden] */
hip_k = tan(hip_deg);
// The vault, restated on tee numbers: crown cross-section semi-axes and the
// x-gable with its ridge. ridge stays 0.5+ under the outer pole at x = 0.
tee_crown_st = sqrt(1 - pow((tee_crown_zt - tee_zc) / tee_az, 2));
tee_cxt = chamber_ax * tee_crown_st;      // gable eaves half-span (x)
tee_cyt = chamber_ay * tee_crown_st;      // crown cross-section half-span (y)
tee_vault_h = tee_cxt + 1.5;              // just past 45 deg in x
tee_ridge = tee_crown_zt + tee_vault_h;
// Where the inner ellipsoid's own surface crosses the ridge height at x = 0
// (mm in y) — past this the ellipsoid dips under the gable while still
// SHALLOW (under 45 deg), which is exactly the sliver the hip must cover.
tee_y_cross = chamber_ay * sqrt(1 - pow((tee_ridge - tee_zc) / tee_az, 2));
// The hip planes pass 1.5 mm UNDER the ellipsoid at that crossing, so the
// shallow band never governs the roof (asserted by sampling below).
tee_z_hip = tee_ridge - 1.5 + hip_k * tee_y_cross;

// The cavity's crown boundary, pointwise (the repair): min of the ellipsoid,
// the x-gable and the y-hip. Every piece is a function of (x, y), so the
// ceiling has no overhangs and no closed pockets; every governing surface is
// >= 45 deg (the ellipsoid only governs where its own slope exceeds that —
// asserted by sampling).
function tee_z_in(x, y) =
    tee_zc + tee_az * sqrt(1 - pow(x / chamber_ax, 2) - pow(y / chamber_ay, 2));
function tee_z_out(x, y) =
    tee_zc + (tee_az + wall)
        * sqrt(1 - pow(x / (chamber_ax + wall), 2)
                 - pow(y / (chamber_ay + wall), 2));
function tee_cap(x, y) =
    min(tee_z_in(x, y), tee_ridge - abs(x), tee_z_hip - hip_k * abs(y));
// Slope of the ellipsoid's own surface at (x, y) — the shallow-band test.
function tee_z_slope(x, y) =
    tee_az * sqrt(pow(x / pow(chamber_ax, 2), 2)
                + pow(y / pow(chamber_ay, 2), 2))
        / sqrt(1 - pow(x / chamber_ax, 2) - pow(y / chamber_ay, 2));
// The dish floor on the port-C meridian meets port C's bore floor (the plane
// x = port_c_x + ri) at z_hand, and the walking grade there is the dish's own
// slope — the N4 number for the A->C route.
tee_s_hand = (port_c_x + ri) / chamber_ax;
tee_z_hand = tee_zc + tee_az * sqrt(1 - pow(tee_s_hand, 2));
tee_grade_deg = atan(chamber_ax * (tee_z_hand - tee_zc)
                     / (pow(tee_az, 2) * tee_s_hand));

echo(str("nuggs-turnaround-tee: bore ", bore_d, " mm, ports ", port_gap,
         " mm apart + crown port at (", port_c_x, ", 0), chamber ",
         2 * chamber_ax, " x ", 2 * chamber_ay, " x ", 2 * tee_az,
         " mm, clear internal width ", 2 * chamber_ay, " mm"));
echo(str("nuggs-turnaround-tee: A->C handoff at z = ", tee_z_hand,
         " mm grades ", tee_grade_deg, " deg; cap = min(ellipsoid, gable ",
         tee_ridge, ", hip ", hip_deg, " deg from ", tee_z_hip, "); total ",
         port_c_face + 2 * port_proj, " mm on the bed"));

// ---------------------------------------------------------------------------
// Design-level asserts. The parent's own asserts all re-fired on the tee
// numbers before anything was drawn (NOTES.md); the ones whose variables
// moved are restated here on tee_*, and the cap gets the sampled guard the
// parent lacked.
// ---------------------------------------------------------------------------

// The parent's neck rule, on port C's own neck.
assert(port_c_face - port_c_base >= z_top, str(
    "TEE CROWN NECK: port C's shell runs ", port_c_face - port_c_base,
    " mm but the port zone needs z_top = ", z_top,
    " mm of full-round shell behind the face."));

// The parent's bed-fit ceiling, on the tee's new total height.
assert(port_c_face + port_proj - z_tip <= 199, str(
    "TEE BED FIT: the print-pose height ", port_c_face + port_proj - z_tip,
    " mm exceeds the 199 mm the gate's bare-default test-slice can cut.",
    " Lower port_c_face."));
// ...and the parent's own three, on the tee's chamber.
assert(tee_zc + tee_az + wall - z_tip <= 199, "TEE BED FIT: chamber crown.");
assert(tee_zc - (tee_az + wall) >= -eps, str(
    "TEE BELLY: the chamber's bottom pole dips ",
    tee_az + wall - tee_zc, " mm below the port face plane."));
assert(tee_zc >= z_top, "TEE NECK: the bed ports' shells run tee_zc < z_top.");

// The parent's crown feasibility pair, on the tee's cap.
assert(tee_crown_zt >= tee_zc + 35, str(
    "TEE CROWN: the cap starts at z = ", tee_crown_zt,
    " mm, low enough to cut into the crossing route's envelope (which tops",
    " out at ", tee_zc + 32.4, " mm)."));
assert(tee_ridge <= tee_zc + tee_az - 0.5, str(
    "TEE CROWN: the gable's ridge (z = ", tee_ridge,
    " mm) pokes through the chamber crown at x = 0."));

// THE REPAIR'S OWN GUARDS — sampled over a grid, because the parent's y = 0
// assert is exactly what let the roof slot through.
// (1) No poke, anywhere: the cavity's crown boundary keeps shell over it at
//     every sampled station of the roof (min measured 2.72 mm at the
//     gable/hip handover; the parent's slot measures 0).
function tee_min_roof_wall(n) =
    min([for (i = [0 : n], j = [0 : n])
            let (x = -chamber_ax + 2 * chamber_ax * i / n,
                 y = -chamber_ay + 2 * chamber_ay * j / n)
                (pow(x / chamber_ax, 2) + pow(y / chamber_ay, 2) >= 0.999
                     || tee_cap(x, y) <= tee_zc)
                    ? 1000
                    : tee_z_out(x, y) - tee_cap(x, y)]);
assert(tee_min_roof_wall(120) >= 2.3, str(
    "TEE CAP: the cavity's roof comes within ", tee_min_roof_wall(120),
    " mm of the outer surface somewhere off the y = 0 plane — the parent's",
    " roof-slot failure mode. Lower tee_ridge or tee_z_hip."));
// (2) Every governing surface is >= 45 deg: wherever the ellipsoid's own
//     surface is the roof (above the equator), its slope must already exceed
//     45 deg — the hip exists to keep its shallow polar band covered.
function tee_min_gov_slope(n) =
    min([for (i = [0 : n], j = [0 : n])
            let (x = -chamber_ax + 2 * chamber_ax * i / n,
                 y = -chamber_ay + 2 * chamber_ay * j / n)
                (pow(x / chamber_ax, 2) + pow(y / chamber_ay, 2) >= 0.999
                     || tee_z_in(x, y) >= min(tee_ridge - abs(x),
                                              tee_z_hip - hip_k * abs(y))
                     || tee_z_in(x, y) <= tee_zc + 1)
                    ? 1000
                    : tee_z_slope(x, y)]);
assert(tee_min_gov_slope(120) >= 1.0, str(
    "TEE CAP: the ellipsoid governs the roof with slope ",
    atan(tee_min_gov_slope(120)), " deg somewhere — a near-horizontal",
    " enclosed ceiling. Lower tee_z_hip so the hip covers the shallow band."));
// (3) The hip actually caps: its planes must sit under the ellipsoid at the
//     crossing with real margin, or the shallow sliver returns.
assert(tee_z_hip - hip_k * tee_y_cross <= tee_z_in(0, tee_y_cross) - 1.0, str(
    "TEE CAP: the hip planes pass only ",
    tee_z_in(0, tee_y_cross) - (tee_z_hip - hip_k * tee_y_cross),
    " mm under the ellipsoid at the ridge crossing — raise hip_deg or lower",
    " tee_z_hip."));

// Port C's junction, both burials sampled around the full rim: each base disc
// must sit strictly inside its ellipsoid or a cap face survives as a ledge.
function tee_bore_rim_max(n) =
    max([for (k = [0 : n])
            let (t = 360 * k / (n + 1),
                 X = port_c_x + ri * cos(t), Y = ri * sin(t))
                pow(X / chamber_ax, 2) + pow(Y / chamber_ay, 2)
                    + pow((port_c_base - tee_zc) / tee_az, 2)]);
function tee_shell_rim_max(n) =
    max([for (k = [0 : n])
            let (t = 360 * k / (n + 1),
                 X = port_c_x + ro * cos(t), Y = ro * sin(t))
                pow(X / (chamber_ax + wall), 2) + pow(Y / (chamber_ay + wall), 2)
                    + pow((port_c_base - tee_zc) / (tee_az + wall), 2)]);
assert(tee_bore_rim_max(72) <= 0.97, str(
    "TEE CROWN BORE: port C's bore-cut cap disc is not buried in the inner",
    " ellipsoid (rim at ", tee_bore_rim_max(72), " of the ellipsoid). An",
    " exposed cap crescent is an interior ledge — lower port_c_base."));
assert(tee_shell_rim_max(72) <= 0.97, str(
    "TEE CROWN SHELL: port C's neck-shell base disc is not buried in the",
    " outer ellipsoid (rim at ", tee_shell_rim_max(72), "). A coincident",
    " base rim is the shared-surface class CI's Manifold backend rejects."));

// Port C assembly: a mating module sliding on sweeps its sector tips at
// r_out about port C's axis down to face - port_proj; nothing of this part
// may stand in that cylinder. Sampled around the sweep's rim.
function tee_sweep_max_z(n) =
    max([for (k = [0 : n])
            let (t = 360 * k / (n + 1),
                 X = port_c_x + r_out * cos(t), Y = r_out * sin(t))
                (pow(X / (chamber_ax + wall), 2)
                 + pow(Y / (chamber_ay + wall), 2)) >= 1
                    ? -1000
                    : tee_z_out(X, Y)]);
assert(tee_sweep_max_z(72) <= port_c_face - port_proj - 2, str(
    "TEE CROWN ASSEMBLY: this part stands ", tee_sweep_max_z(72),
    " mm tall inside port C's sector-tip sweep — a mating module cannot",
    " slide on. Move port C or lower the chamber."));

// N4 on the A->C route: the grade at the dish/bore-floor handoff (its
// steepest on-route point; the bore floor itself is flat).
assert(tee_grade_deg <= max_incline_deg, str(
    "TEE GRADE: the A->C route hands off to port C's bore floor at ",
    tee_grade_deg, " deg against N4's ", max_incline_deg,
    " deg maximum. Move port_c_x further toward the floor (+x)."));
// ...and the handoff must be a widening, never a lip: port C's bore floor
// sits strictly inside the dish's widest (the equator), so the dish falls
// ONTO it going up, and never rises above it going down.
assert(port_c_x + ri <= chamber_ax - 1, str(
    "TEE HANDOFF: port C's bore floor (x = ", port_c_x + ri,
    ") sits outside the dish's equator extent (", chamber_ax,
    ") — the route would step UP onto it (N6/N11)."));
assert(port_c_x >= 0, str(
    "TEE HANDOFF: port_c_x < 0 lifts port C's bore floor above the bore's",
    " own arc at the equator — a lip into the passage (N6)."));

// ---------------------------------------------------------------------------
// Geometry — restatements of the parent modules that bake in tee_zc/tee_az,
// plus port C and the repaired cap. Everything else is inherited.
// ---------------------------------------------------------------------------

// The chamber as a scaled unit sphere (parent, on the tee's centre height).
module chamber(sx, sy, sz) {
    translate([0, 0, tee_zc]) scale([sx, sy, sz]) sphere(1, $fn = ell_fn);
}

// One bed-port neck (parent, on the tee's join height).
module neck(s) {
    translate([0, s * port_gap / 2, 0]) {
        nuggs_port(cfg);
        cylinder(r = ro, h = tee_zc, $fn = tube_fn);
    }
}

// The vents (parent, on the tee's equator height).
module vents() {
    for (i = [0 : n_vent - 1])
        let (t  = (i - (n_vent - 1) / 2) / max(1, (n_vent - 1) / 2),
             yv = t * 0.6 * chamber_ay,
             xc = -(chamber_ax + wall)
                  * sqrt(1 - pow(yv / (chamber_ay + wall), 2)))
            translate([xc, yv, tee_zc])
                rotate([0, 0, -90])
                    teardrop_hole(d = vent_d, l = 2 * (chamber_ax + wall) + 8);
}

// The repaired crown cap: the cavity's crown boundary is
// min(inner ellipsoid, x-gable, y-hip), built as one intersection of three
// solids. The half-space wedges are oversized cubes rotated to the plane
// angles and translated to the heights; the ellipsoid supplies its own bound
// (and the footprint), so no truncation plane and no footprint prism is
// needed — the ceiling is simply the lowest of the three surfaces.
module chamber_cavity() {
    intersection() {
        chamber(chamber_ax, chamber_ay, tee_az);
        // the x-gable: z <= tee_ridge - |x| (two planes just past 45 deg)
        intersection() {
            translate([0, 0, tee_ridge]) rotate([0, 45, 0])
                translate([-500, -500, -1000]) cube(1000);
            translate([0, 0, tee_ridge]) rotate([0, -45, 0])
                translate([-500, -500, -1000]) cube(1000);
        }
        // the y-hip: z <= tee_z_hip - hip_k*|y| (two planes at hip_deg)
        intersection() {
            translate([0, 0, tee_z_hip]) rotate([hip_deg, 0, 0])
                translate([-500, -500, -1000]) cube(1000);
            translate([0, 0, tee_z_hip]) rotate([-hip_deg, 0, 0])
                translate([-500, -500, -1000]) cube(1000);
        }
    }
}

// Port C's neck: the full-round shell from its buried base to the face, with
// the port itself rotated a half-turn about x — a proper rotation, so the
// coupling is the standard port rigidly reoriented (sectors projecting +z
// from the face, backing below it), never a mirror.
module crown_neck() {
    translate([port_c_x, 0, port_c_base])
        cylinder(r = ro, h = port_c_face - port_c_base, $fn = tube_fn);
    translate([port_c_x, 0, port_c_face]) rotate([180, 0, 0]) nuggs_port(cfg);
}

// Port C's bore cut — the nuggs_bore_cut every port caller owes: open past
// the sector tips so the mouths open and the inboard collar material is cut.
module crown_bore() {
    translate([port_c_x, 0, port_c_base])
        cylinder(r = ri, h = port_c_face + bore_over - port_c_base,
                 $fn = tube_fn);
}

// Port C's mouth edge break (the parent's bore_lead, mirrored to an
// upward-facing mouth): wide end outermost, at the tips. Cut, never added.
module crown_lead() {
    translate([port_c_x, 0, port_c_face + z_tip])
        cylinder(r1 = ri - eps, r2 = ri + 1.0, h = chamfer_h, $fn = tube_fn);
}

// The tee itself: the parent's construction verbatim on tee numbers — hull of
// the two bed-port neck shells and the outer ellipsoid (one envelope, the
// solid web), the ports fused on, ONE cavity union subtracted — with port C's
// neck added to the shell union, its bore to the cavity union, and its mouth
// break to the cuts. Port C's neck is UNIONED, not hulled: a hull would flare
// a skirt around the tube where it leaves the dome; the union keeps the
// dome-and-tube silhouette and their junction a clean transverse pierce.
module nuggs_turnaround() {
    difference() {
        union() {
            hull() {
                for (s = [-1, 1])
                    translate([0, s * port_gap / 2, 0])
                        cylinder(r = ro, h = tee_zc, $fn = tube_fn);
                chamber(chamber_ax + wall, chamber_ay + wall, tee_az + wall);
            }
            neck(-1);
            neck(1);
            crown_neck();
        }
        union() {
            for (s = [-1, 1])
                translate([0, s * port_gap / 2, z_tip - bore_over])
                    cylinder(r = ri, h = tee_zc - z_tip + bore_over,
                             $fn = tube_fn);
            chamber_cavity();
            crown_bore();
        }
        vents();
        bore_lead(-1);
        bore_lead(1);
        crown_lead();
    }
}

// ---------------------------------------------------------------------------
// Fitchecks (ci.fitchecks) — the swept-animal proof, extended to the tee's
// three routes. The parent's A<->B switchback is restated on tee numbers
// (the crossing rides the same dish, whose floor is unchanged in x/y; only
// its print-z station moves with tee_zc), and the A->C through-route is
// added: bowl -> up the port-C meridian (floor-normal offsets, the parent's
// degenerate-tangency discipline) -> the handoff -> port C's flat bore floor
// and out past the face.
// ---------------------------------------------------------------------------

// Named tee_* (not a redefinition of the parent's cross_centre): the parent
// computes its own top-level route_centres at include position — before any
// tee_* variable below exists — and a redefined cross_centre evaluated there
// would read tee_zc as unknown and silently write undef stations into it.
// Top-level assignments evaluate eagerly in file order; only module
// instantiations bind after the whole scope is read. So anything the parent
// assigns at its own top level keeps the parent's definition, and the tee's
// sweep below uses this one.
function tee_cross_centre(y) =
    let (xf = chamber_ax * sqrt(1 - pow(y / chamber_ay, 2)),
         g  = dish_grade_at(y))
        [xf - route_standoff * cos(g), y - route_standoff * sin(g),
         tee_zc];

// Floor point and inward unit normal on the port-C meridian (y = 0) at
// height z — the climb leg's surface.
// climb_floor: the +x flank point at height z on the y = 0 meridian, with the
// INWARD unit normal. The normal is the normalized gradient of the ellipsoid
// constraint x^2/ax^2 + (z-zc)^2/az^2 — note every component carries its own
// division (xf/ax^2, u/az): dropping the /az on the z-term once shipped a
// "unit" vector ~14x too long, which threw the 31 mm standoff ~450 mm below
// the part and speared the climb straight through the web. path-clear caught
// it (1796 facets); the assert on tee_route_centres below now catches it
// before the render.
function climb_floor(z) =
    let (u  = (z - tee_zc) / tee_az,
         xf = chamber_ax * sqrt(1 - pow(u, 2)),
         n  = sqrt(pow(xf / pow(chamber_ax, 2), 2) + pow(u / tee_az, 2)))
        [[xf, 0, z], [-xf / pow(chamber_ax, 2), 0, -u / tee_az] / n];
function climb_centre(z) =
    let (f = climb_floor(z)) f[0] + route_standoff * f[1];

tee_route_centres = concat(
    // bore A: face plane to equator, riding the bore's floor side
    [for (z = [0 : 5 : tee_zc]) [ri - route_standoff, port_gap / 2, z]],
    // the A<->B crossing: mouth A's line to the bowl bottom and on to B's
    [for (y = [port_gap / 2, 44, 38, 32, 24, 14, 0]) tee_cross_centre(y)],
    [for (y = [-14, -24, -32, -38, -44, -port_gap / 2]) tee_cross_centre(y)],
    // bore B: equator back down to the face plane (B exits — the parent's
    // route, complete)
    [for (z = [tee_zc : -5 : 0]) [ri - route_standoff, -port_gap / 2, z]],
    // THE TEE LEG, continuous with the above (a swept proof cannot jump):
    // back up bore B and re-cross the bowl to its bottom — the retraced
    // stations are the same ones, so this adds no swept volume, it only
    // keeps the polyline connected on the way to the climb
    [for (z = [0 : 5 : tee_zc]) [ri - route_standoff, -port_gap / 2, z]],
    [for (y = [-port_gap / 2, -44, -38, -32, -24, -14, 0]) tee_cross_centre(y)],
    // the climb: up the bowl and along the port-C meridian (y = 0) to the
    // handoff, floor-normal offsets at every station
    [for (z = [tee_zc : 5 : tee_z_hand]) climb_centre(z)],
    // ...and out port C's flat bore floor, past the face
    [for (z = [tee_z_hand : 10 : port_c_face])
        [port_c_x + ri - route_standoff, 0, z]]);

// The route is the fitcheck's input, so it gets its own artifact-level guard:
// every station must sit inside the part's z span (bed faces to port C's
// face). A station that has fallen out of the part means a standoff vector
// was not unit — the formula asserts above re-derive the grades, but they
// cannot see the built list (issue #37's lesson, learned here the hard way:
// the broken normal passed every analytic assert and only path-clear's mesh
// intersection caught it).
assert(min([for (p = tee_route_centres) p[2]]) >= z_tip
    && max([for (p = tee_route_centres) p[2]]) <= port_c_face,
    "nuggs-turnaround-tee: route station outside the part's z span — a standoff vector is not unit");

module animal_path_sweep() {
    union() {
        for (i = [0 : len(tee_route_centres) - 2])
            hull() {
                translate(tee_route_centres[i])
                    sphere(r = route_env_r, $fn = 24);
                translate(tee_route_centres[i + 1])
                    sphere(r = route_env_r, $fn = 24);
            }
    }
}

// ---------------------------------------------------------------------------
// Fitcheck dispatch — restated in THIS file (deliberate duplicate)
// ---------------------------------------------------------------------------
// gate.sh's fitcheck gate proves a manifest entry is a real dispatch selector
// by grepping the ENTRY .scad for `part == "<name>"`: a part value with no
// branch renders nothing, and `empty` would wave a typo through forever. A
// derivative inherits the parent's if/else chain, not its text, so the
// selector must be restated here or the gate cannot tell `path-clear` from a
// misspelling. The parent's inherited chain fires these same branches at
// include position and these lines fire them again after the tee's own
// definitions; both resolve through late binding to the tee's rebuilt sweep
// (`animal_path_sweep` above, on `tee_route_centres`). The boolean therefore
// renders twice and unions with itself, which flips neither verdict: a clear
// route's empty intersection stays empty, and the +6 mm control stays
// non-empty. Fitcheck parts are never printchecked or sliced, so the
// duplicate geometry has no consumer beyond the render itself.

if (part == "path-clear") fit_path_clear();
else if (part == "path-clear-ctrl") fit_path_ctrl();
