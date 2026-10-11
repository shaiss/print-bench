// Demo / regression render for helical-window.scad.
// Not a printable design — rendered by scripts/check.sh to catch regressions.
// All dimensions in millimeters, angles in degrees.

use <helical-window.scad>

$fn = 64;

// The ovodyo brand parameterization — the one a change to this library must
// not alter. 450 deg of slot per 90 deg of index stop is the locked 5:1: the
// slot spans exactly five stops of tumble, and at pitch 8 it climbs
// lead*90/360 = 2 mm per stop (10 mm over the sweep), so the mark stays
// coherent with the face that lands upright.
pitch = 8;     // pass spacing; the land budget lives here
sweep = 450;   // five index stops of slot
width = 4;     // the slot; land = pitch - width = 4, the brand's 50% land
d     = 30;    // plain demo shell, sized like an ovodyo ball's girth
wall  = 2;

// 1. Bare window cutter — the generator on its own: a helical ribbon one
//    wall plus two punches thick, `rise + width` tall, centred on z = 0.
helical_window(pitch, sweep, width, 1, d, wall);

// 2. The reference shell — the mark cut through a plain shell, the case the
//    guards.conf measurements are taken on. Rise 10 + width 4 = a 14 mm band
//    inside an 18 mm shell.
translate([45, 0, 0]) difference() {
    cylinder(d = d, h = 18);
    translate([0, 0, -0.01]) cylinder(d = d - 2 * wall, h = 18.02);
    translate([0, 0, 9]) helical_window(pitch, sweep, width, 1, d, wall);
}

// 3. Multi-start — two interleaved starts at the same pitch 8. Adjacent
//    passes still sit exactly pitch apart (starts are rotations of one
//    helix), so the sever bound does not move: this renders because width 3
//    clears pitch 8 by the same land it would need at starts = 1. Lead is
//    16 here, so the sweep climbs 20 mm — the taller shell.
translate([90, 0, 0]) difference() {
    cylinder(d = d, h = 26);
    translate([0, 0, -0.01]) cylinder(d = d - 2 * wall, h = 26.02);
    translate([0, 0, 13]) helical_window(pitch, sweep, 3, 2, d, wall);
}

// 4. Deboss — the same mark as the base's logo: depth = 1.2 cuts a shallow
//    relief into a solid boss instead of punching through. One geometry, two
//    brand uses; the sever bound applies unchanged because it lives in the
//    helix, not in how deep the cut runs. The boss is 18 tall for the same
//    14-tall band as case 2: a band that exactly meets the host's end faces
//    puts coincident faces into the difference, and CGAL answers coincident
//    faces with a non-manifold warning (found the hard way, at h = 14).
translate([135, 0, 0]) difference() {
    cylinder(d = d, h = 18);
    translate([0, 0, 9]) helical_window(pitch, sweep, width, 1, d, wall,
                                        depth = 1.2);
}

// 5. The accepting half of the sever bound's boundary.
//
//    This renders at width = 7.9 against pitch = 8 — one tenth of a
//    millimetre of land, far past anything printable and not a
//    recommendation, purely to pin the CONDITION's edge from the inside.
//    Its partner is severed-at-boundary in lib/helical-window-guards.conf,
//    which carries the refusing half: width = 8.0 at the same pitch must
//    abort. A guard manifest can only express refusals, so "7.9 is
//    accepted" has nowhere to live but a render — see threads-fdm-demo
//    case 5 for the pattern. Together the two say the bound is exact, not
//    approximately right: refuse 8.0, accept 7.9. (Shell 22 tall so the
//    17.9-tall band clears the end faces with real margin — the measured
//    one-body count for exactly this shape is in guards.conf.)
translate([180, 0, 0]) difference() {
    cylinder(d = d, h = 22);
    translate([0, 0, -0.01]) cylinder(d = d - 2 * wall, h = 22.02);
    translate([0, 0, 11]) helical_window(pitch, sweep, 7.9, 1, d, wall);
}

// 6. The brand ratio is arithmetic on the parameters, not a promise about
//    geometry — this echoes it only. Connectivity (a valid parameterization
//    leaving the shell ONE body, a severing one leaving two) is a mesh
//    property a render cannot measure: those numbers are measured on the
//    exported STL and recorded in lib/helical-window-guards.conf.
echo(str("brand ratio: rise per 90 deg stop = ", pitch * 1 * 90 / 360,
         " mm, land = ", pitch - width,
         " mm -- connectivity is measured on the export, not echoed here"));
