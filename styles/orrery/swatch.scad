// orrery — the style's swatch: a miniature vortex cage with one captive ring.
//
// Written FROM the tokens, never from retyped numbers, so it satisfies the
// style's rules by construction. ./scripts/style-check.sh orrery renders this
// and holds it to styles/orrery/style.json — if the swatch cannot pass, the
// spec is wrong, not the swatch.
//
// Everything the family is, in 48 mm: five knife-edged blades twisted at
// style_blade_twist_rate, every lead-in / roof / seat cut at the ONE
// style_ramp_deg angle, and a captive ring (hole smaller than the cage —
// printed there, never installed) resting style_seat_gap above its conical
// seat. In a real print the ring is the second, non-welding material; the
// swatch renders it in place as one file for the gate.
include <styles/orrery/style.scad>

$fn = style_fn;

/* [Swatch] */
hub_r   = 12;               // hub outer radius (mm)
H       = 48;               // overall height (mm)
blade_n = 5;                // blade count
blade_r = 22;               // blade cage radius (mm)
ring_ri = 18.6;             // ring inner face (mm) — 3.4 mm under the cage: captive
ring_ro = 21.4;             // ring outer face (mm)
seat    = 22;               // ring seat height (mm)
floor_r = 16.8;             // blade cutback radius around the ring
head    = 5;                // straight groove above the seat (mm)

ramp    = tan(style_ramp_deg);
bore_r  = hub_r - style_blade_th;             // hub wall = one blade thickness
twist   = style_blade_twist_rate * H;         // deg over the swatch height
land_r1 = (ring_ri + ring_ro) / 2 + 0.4;      // 0.8 mm bottom land
land_r0 = land_r1 - 0.8;
lower_h = (ring_ro - land_r1) * ramp;
env_r0  = hub_r - 1;
rise    = (blade_r - env_r0) * ramp;

function z_race(r) = seat - style_seat_gap + (r - land_r1) * ramp;

module blades() {
    difference() {
        intersection() {
            linear_extrude(height = H, twist = -twist, slices = 48,
                           convexity = 10)
                for (i = [0 : blade_n - 1])
                    rotate([0, 0, i * 360 / blade_n])
                        translate([0, -style_blade_th / 2])
                            square([blade_r, style_blade_th]);
            rotate_extrude(convexity = 4)
                polygon([[0, 4], [env_r0, 4], [blade_r, 4 + rise],
                         [blade_r, H - 4 - rise], [env_r0, H - 4], [0, H - 4]]);
        }
        rotate_extrude(convexity = 4)                       // ring groove
            polygon([[floor_r, seat - 1], [blade_r + 3, seat - 1],
                     [blade_r + 3, seat + head + (blade_r + 3 - floor_r) * ramp],
                     [floor_r, seat + head]]);
    }
}

module race() {
    rotate_extrude(convexity = 4)
        polygon([[bore_r + 0.6, z_race(bore_r + 0.6) - 1.9],
                 [ring_ro - 0.4, z_race(ring_ro - 0.4) - 1.9],
                 [ring_ro - 0.4, z_race(ring_ro - 0.4)],
                 [bore_r + 0.6, z_race(bore_r + 0.6)]]);
}

module ring() {
    rotate_extrude(convexity = 4)
        polygon([[land_r0, seat], [land_r1, seat],
                 [ring_ro, seat + lower_h], [ring_ro, seat + style_ring_h],
                 [ring_ri, seat + style_ring_h], [ring_ri, seat + lower_h]]);
}

difference() {
    union() {
        cylinder(r = hub_r, h = H);
        blades();
        race();
    }
    translate([0, 0, -1]) cylinder(r = bore_r, h = H + 2);
}
ring();
