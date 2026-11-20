// Fixture for test_compliant_xafp_wedge.py — Copilot/CodeRabbit/Bugbot #1052.
// Three modes (demo_mode) so the wedge defect is isolated from beam bridging:
//
//   "lib"         — full library pivot (beams + arcs). Expect 1 body.
//   "arcs_ok"     — beam-free frame+stage with the library's derived rb.
//                   Expect exactly 2 bodies (frame, stage — intentionally
//                   disconnected so the wedge is what is under test).
//   "arcs_broken" — same beam-free geometry with the old fixed r_out+10
//                   wedge. Expect >2 bodies (each arc severed).
//
// Not a library surface. Invoked only by the pytest under -D.
use <compliant.scad>

demo_mode = "lib";

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
tab_cx   = r_out + tab_len / 2;
arm_inset = min(4, tab_len / 2 - 1);

module ring_arc_2d(rb) {
    intersection() {
        difference() { circle(r_out); circle(r_in); }
        polygon([[0, 0],
                 [rb * cos(-arc_half), rb * sin(-arc_half)],
                 [rb, 0],
                 [rb * cos(arc_half), rb * sin(arc_half)]]);
    }
}

module arm_2d()
    hull() {
        translate([r_in + 3, 0]) circle(2);
        translate([tab_cx - arm_inset, 0]) circle(2);
    }

module tab_2d()
    offset(r = tab_r) offset(delta = -tab_r)
        square([tab_len, tab_w], center = true);

// Beam-free frame + stage: only the wedge decides whether each arc stays
// one piece. Matching geometry on both arcs_* modes (Bugbot/CodeRabbit).
module arcs_only_2d(rb) {
    $fn = 64;
    module frame()
        union() {
            rotate([0, 0, 180]) ring_arc_2d(rb);
            mirror([1, 0]) arm_2d();
            translate([-tab_cx, 0]) tab_2d();
        }
    module stage()
        union() {
            ring_arc_2d(rb);
            arm_2d();
            translate([tab_cx, 0]) tab_2d();
        }
    union() { frame(); stage(); }
}

rb_ok     = max(r_out + 10, r_out / cos(arc_half / 2));  // library formula
rb_broken = r_out + 10;                                   // pre-fix harvest

if (demo_mode == "lib")
    cross_axis_pivot(t, L, w, root_fillet, alpha = alpha, stop_angle = stop_angle,
                     arc_wall = arc_wall, E = 2000, h_pad = 0,
                     tab_len = tab_len, tab_w = tab_w, tab_r = tab_r);
else if (demo_mode == "arcs_ok")
    linear_extrude(w) arcs_only_2d(rb_ok);
else if (demo_mode == "arcs_broken")
    linear_extrude(w) arcs_only_2d(rb_broken);
else
    assert(false, str("unknown demo_mode: ", demo_mode));
