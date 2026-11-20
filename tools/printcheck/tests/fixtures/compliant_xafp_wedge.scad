// Fixture for test_compliant_xafp_wedge.py — Copilot/CodeRabbit #1052.
// Renders the large-span cross-axis pivot (demo station 9 numbers) alone so
// a body-count check can see whether the wedge mask severs the rigid arcs.
//
//   demo_fixed_wedge = false (default): use the library (derived rb).
//   demo_fixed_wedge = true:            old harvest-site `r_out + 10` wedge
//                                       only — severs the arcs at these
//                                       numbers (the negative control).
//
// Not a library surface. Invoked only by the pytest under -D.
use <compliant.scad>

demo_fixed_wedge = false;

t = 0.8;
L = 120;
w = 2.4;
root_fillet = 0.6;
alpha = 45;
stop_angle = 40;
arc_wall = 1.6;
tab_len = 10;
tab_w = 22;
tab_r = 4;

r_in     = L / 2;
r_out    = r_in + arc_wall;
arc_half = (180 - stop_angle) / 2;
land     = arc_wall - 0.5;
tab_cx   = r_out + tab_len / 2;
arm_inset = min(4, tab_len / 2 - 1);

// The pre-fix wedge: fixed r_out+10, which at L=120 / arc_wall=1.6 puts the
// chord inside the bore and severs the ring (the defect the lib's derived
// rb = max(r_out+10, r_out/cos(arc_half/2)) closes).
module broken_ring_arc_2d() {
    rb = r_out + 10;
    intersection() {
        difference() { circle(r_out); circle(r_in); }
        polygon([[0, 0],
                 [rb * cos(-arc_half), rb * sin(-arc_half)],
                 [rb, 0],
                 [rb * cos(arc_half), rb * sin(arc_half)]]);
    }
}

module broken_pivot_2d() {
    $fn = 64;
    module arm()
        hull() {
            translate([r_in + 3, 0]) circle(2);
            translate([tab_cx - arm_inset, 0]) circle(2);
        }
    module tab()
        offset(r = tab_r) offset(delta = -tab_r)
            square([tab_len, tab_w], center = true);
    module frame()
        union() {
            rotate([0, 0, 180]) broken_ring_arc_2d();
            mirror([1, 0]) arm();
            translate([-tab_cx, 0]) tab();
        }
    module stage()
        union() {
            broken_ring_arc_2d();
            arm();
            translate([tab_cx, 0]) tab();
        }
    // Beams + fillets omitted on purpose: the negative control only needs the
    // severed arcs (frame/stage each split). Including them would re-bridge
    // through the crossing and hide the wedge defect.
    union() { frame(); stage(); }
}

if (demo_fixed_wedge)
    linear_extrude(w) broken_pivot_2d();
else
    cross_axis_pivot(t, L, w, root_fillet, alpha = alpha, stop_angle = stop_angle,
                     arc_wall = arc_wall, E = 2000, h_pad = 0,
                     tab_len = tab_len, tab_w = tab_w, tab_r = tab_r);
