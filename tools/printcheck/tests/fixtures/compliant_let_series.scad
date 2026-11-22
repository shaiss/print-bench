// Fixture for test_compliant_let_series.py — Copilot #1057.
// Two modes (demo_mode) so the series-row connectivity is falsifiable:
//
//   "lib"     — library let_joint with n_series=2 (odd row flips finger
//               parity so facing fingers share an X pitch and union).
//               Expect exactly 1 body.
//   "broken"  — same dimensions, two unflipped harvest rows stacked at
//               2·gap (the pre-fix defect). Expect >1 bodies.
//
// Not a library surface. Invoked only by the pytest under -D.
use <compliant.scad>

demo_mode = "lib";

n_parallel = 3;
bar_w = 2.0;
bar_t = 1.2;
bar_L = 14;
gap = 6;
finger_w = 3.5;
root_fillet = 0.8;
embed = 1;

// Unflipped stack — the defect Copilot named: both rows use harvest A/B
// parity, so facing fingers sit on different X pitches and never meet.
module broken_two_row() {
    $fn = 48;
    for (s = [0, 1])
        translate([0, s * 2 * gap])
            // Private row helper is not reachable via `use`; rebuild the
            // harvest silhouette inline (flip = false both times).
            let_joint_2d(1, n_parallel, bar_w, bar_t, bar_L, gap,
                         finger_w = finger_w, root_fillet = root_fillet,
                         embed = embed);
}

if (demo_mode == "lib")
    let_joint(2, n_parallel, bar_w, bar_t, bar_L, gap,
              finger_w = finger_w, root_fillet = root_fillet, embed = embed);
else if (demo_mode == "broken")
    linear_extrude(bar_t) broken_two_row();
else
    assert(false, str("unknown demo_mode=", demo_mode));
