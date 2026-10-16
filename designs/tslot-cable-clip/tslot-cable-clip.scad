// tslot-cable-clip — a snap-in cable-clip family for standard 2020 T-slot
// aluminum extrusion. One hammer-head lug (the anchoring geometry
// extrusion-shelf-bracket proved against the same slot table) slides into
// the rail's side slot from an open end; the body stands on the rail face
// carrying a loop that routes a cable ALONG the rail — no zip ties, no
// adhesive, repositionable by sliding. Three v1 stations: Ø4 (PTFE Bowden /
// micro-USB), Ø6.2 (Cat5e / USB-A), Ø8 (pneumatic / small bundle).
//
// Retention is a closed snap loop: the bore is a full circle in plan and
// the only way out is a mouth narrower than the cable between two flex
// tabs, so a vertical run cannot fall out (the brief's drop-in alternative
// was declined for exactly that reason — see NOTES.md). The tabs bend IN
// the layer plane, the snap-cantilever-clip CC1 rule: the whole loop is a
// plan-view profile extruded up, so tab bending stress crosses roads
// inside a layer, never the bond between layers.
//
// Print orientation = use orientation stood on the rail axis: the plan
// profile extrudes up from the bed and the lug fin is a constant-cross-
// section extrusion standing against the body's back face, so the hammer
// head stacks as identical layers (the extrusion-shelf-bracket pose).
// Every wall is vertical (the 45° funnel lives in plan); the only
// horizontal faces are the flat bed face and top face. No supports.
//
// Slot ground truth: NopSCADlib E2020 (lib/NopSCADlib/vitamins/extrusions.scad)
// — mouth 6.0, cavity 12.0 wide / 8.0 deep from the face, lips 2.0 — as
// committed via designs/extrusion-shelf-bracket/NOTES.md. Never re-measured
// by hand; the constants are read from that table.
//
// Requirements and decisions: see NOTES.md next to this file.
// All dimensions in millimeters.

use <printability.scad>       // repo FDM helpers (OPENSCADPATH="$PWD/lib:$PWD")
include <styles/workshop-utility/style.scad>  // tokens: r=4, chamfer=0.6, fn=64

/* [Extrusion slot — E2020 ground truth] */
// 2020 T-slot mouth width (mm) — the narrow slit on the extrusion face.
// 6.0 is the common European square-slot value; 6.2 variants exist.
slot_mouth = 6.0;
// Undercut cavity width behind the lips (mm) — NopSCADlib E2020 "cwi"
slot_cavity_w = 12.0;
// Slot depth from the extrusion face (mm) — NopSCADlib E2020 "sq"
slot_depth = 8.0;
// Slot lip thickness (mm) — how deep the overhang runs — E2020 "t"
slot_lip_t = 2.0;

/* [Lug fit] */
// Slide clearance per side in the slot mouth (mm) — the production neck is
// slot_mouth - 2*slot_fit_tol. TUNE ON THE COUPON in 0.05 steps
// (6.2-mouth rails need ~0.20).
slot_fit_tol = 0.15;
// How far the head hooks under each lip (mm); head = mouth + 2*hook.
// Real M5 hammer T-nuts for the 6-series hook about 2.2.
lug_hook = 2.2;
// Head thickness under the lip (mm) — the engagement depth
lug_engage = 1.5;
// Fin length along the slot (mm) — one lug per clip (brief)
lug_len = 10;
// Slide clearance per side of the head inside the cavity (mm)
cavity_tol = 0.3;

/* [Cable loop] */
// The three v1 station cable Øs (mm) — 4.0 PTFE/micro-USB, 6.2 Cat5e/USB-A,
// 8.0 pneumatic/small bundle. A session may re-pick these (brief).
station_d = [4.0, 6.2, 8.0];
// Diametral bore growth over the cable Ø (mm) — the coupon sweeps
// 0.0 / 0.2 / 0.4; 0.2 lets a vertical run slide while looping it.
cable_fit = 0.2;
// Per-side throat narrowing below the cable Ø (mm) — the retention bite.
// The feel target the coupon prices; bigger bites harder, smaller rattles.
tab_bite = 0.8;
// Ring wall on the mount side (mm) — the stiff back of the loop
wall = 2.4;
// Flex-tab wall (mm) — thins to this over the front sector so the tabs
// bend. Highest-leverage feel knob: stiffness scales with t^3.
tab_t = 1.2;
// Straight throat run before the 45° funnel (mm) — the land the cable
// bears on when it pulls out
land = 0.6;
// Funnel half-width growth beyond the cable radius (mm) — the mouth
// lead-in a tilted cable can find
funnel_margin = 1.2;
// Plan angle of the thin flex sector, each side of the mouth axis (deg).
// 120 roots the tabs behind the body's shoulders; must stay under 135 so
// the relief never reaches the back web.
tab_sector = 120;

/* [Body] */
// Clip body height along the rail axis (mm) — derived per station:
// cable entry clearance top and bottom, and enough height for the fin.
// Hard cap from the brief: body height above rail face (standoff) <= 14.
standoff_max = 14;
// Corner rounding radius (mm) — style_corner_r, on the back-web corners
// (no bed-edge chamfer: see the clip() comment and NOTES.md)
corner_r = style_corner_r;

/* [Quality] */
// Iterating: 48. Production: 96+. Pinned to the style token (64).
$fn = style_fn;

/* [Hidden] */
part = "lineup"; // [lineup, station-a, station-b, station-c, coupon, lug-fit, lug-fit-tight, installed]
// Cable Ø the coupon's loop strip is cut at (mm) — a station Ø
coupon_d = 6.2;

// ---- derived -----------------------------------------------------------
// Neck passes the mouth (the shelf bracket's proven derivation).
lug_neck_w = slot_mouth - 2 * slot_fit_tol;
// Head hooks behind the lips: wider than the mouth, free in the cavity.
lug_head_w = slot_mouth + 2 * lug_hook;

// Ring radii for one cable Ø + fit: bore ri, outer ro. The ring centre
// sits one wall out from the seating face, so the rear wall is `wall`
// thick and the body extends 2*ro past the rail face.
function ring_ri(cd, fit) = (cd + fit) / 2;
function ring_ro(cd, fit) = ring_ri(cd, fit) + wall;
function ring_xc(cd, fit) = ring_ri(cd, fit) + wall;
// Throat half-width: the mouth narrows to cable Ø - 2*tab_bite.
function throat_hw(cd) = (cd - 2 * tab_bite) / 2;
// Body height: cable entry clearance, and always covers the fin.
function body_h(cd) = max(cd + 4, lug_len + 2);

// One hammer-head lug fin: constant cross-section standing on the bed
// against the body's back face (x = 0), extruded up `lug_len`. Neck passes
// the mouth (buried 1 mm into the body), head hooks under the lips — the
// extrusion-shelf-bracket geometry, tol-swapped so the negative-control
// fitcheck can build a deliberately oversize lug.
module lug_fin(tol = slot_fit_tol) {
    neck = slot_mouth - 2 * tol;
    head = slot_mouth + 2 * lug_hook;
    hx0 = -(slot_lip_t + lug_engage);   // head outboard face (under the lip)
    hx1 = -slot_lip_t;                  // head inboard face (lip inner edge)
    ny1 = 1;                            // neck buried into the body
    linear_extrude(lug_len)
        polygon([
            [hx0, -head / 2],
            [hx1, -head / 2],
            [hx1, -neck / 2],
            [ny1, -neck / 2],
            [ny1, neck / 2],
            [hx1, neck / 2],
            [hx1, head / 2],
            [hx0, head / 2],
        ]);
}

// Annular sector centred on (xc, 0), spanning +/-deg about the +x (mouth)
// axis, radii r_in..r_out — the front relief that thins the ring wall to
// tab_t over the flex sector, rooting the tabs in the full-thickness wall.
// The sector polygon must FAN THROUGH +x: a bare triangle on arms at
// +/-deg opens through 180 deg — the back wedge — whenever deg > 90
// (a triangle's apex angle cannot exceed 180 deg), which cut the ring's
// back instead of its front and thinned nothing. Caught by measuring the
// export: the front-most vertices sat on the OUTER ring at ~31 deg.
module front_relief(xc, r_in, r_out, deg) {
    R = r_out + 1;
    n = max(8, ceil(2 * deg / 15));
    intersection() {
        translate([xc, 0])
            difference() {
                circle(r_out);
                circle(r_in);
            }
        translate([xc, 0])
            polygon(concat(
                [[0, 0]],
                [for (i = [0:n])
                    let (a = -deg + i * 2 * deg / n)
                    [R * cos(a), R * sin(a)]]
            ));
    }
}

// Plan-view loop profile for one cable Ø + diametral fit: back web +
// ring, minus bore, minus the mouth channel (throat land + 45° funnel),
// minus the front relief. Everything becomes vertical walls when extruded,
// which is what makes the tabs bend in the layer plane.
module loop_profile(cd, fit) {
    ri = ring_ri(cd, fit);
    ro = ring_ro(cd, fit);
    xc = ring_xc(cd, fit);
    hw_t = throat_hw(cd);               // throat half-width
    hw_f = cd / 2 + funnel_margin;      // funnel half-width at the face
    x1 = xc + ri + land;                // throat ends, funnel begins
    x2 = x1 + (hw_f - hw_t);            // 45° funnel reaches full width
    r_bc = min(corner_r, ro - 0.5);     // web corner radius (style, clamped)
    difference() {
        union() {
            // ring outer circle
            translate([xc, 0]) circle(ro);
            // back web: capsule with the style's corner radius, flat back
            // at x = 0 spanning the ring's width
            hull() {
                translate([r_bc, ro - r_bc]) circle(r_bc);
                translate([r_bc, -(ro - r_bc)]) circle(r_bc);
            }
        }
        // bore: a full circle in plan — the loop only opens at the mouth
        translate([xc, 0]) circle(ri);
        // mouth channel: from the bore out past the face, throat land then
        // a 45° funnel both sides. The step at the bore is the catch.
        polygon([
            [xc, -hw_t],
            [x1, -hw_t],
            [x2, -hw_f],
            [xc + ro + 2, -hw_f],
            [xc + ro + 2, hw_f],
            [x2, hw_f],
            [x1, hw_t],
            [xc, hw_t],
        ]);
        // front relief: thin the wall to tab_t over the flex sector. The
        // cut reaches PAST the ring (ro + corner_r + 1) so it also clears
        // the web's rounded corners where they wrap past the ring's sides
        // inside the sector — at r_out = ro the corners survived beyond
        // the annulus as knife-edge "ears" (0.07 mm, printcheck's
        // thinnest wall, measured on the export).
        front_relief(xc, ri + tab_t, ro + corner_r + 1, tab_sector);
    }
}

// One clip: the plan profile extruded `body_h`, plus the production lug
// fin. tol passes through to the fin for fitchecks.
// NO offset-shrunk bed chamfer: a delta=-c offset narrows the 1.2 mm flex
// tabs by c on BOTH faces (bore grows, floor shrinks), so c=0.6 — the
// style's edge chamfer — annihilated the tabs in the bottom layer and left
// the whole loop front bridging over air at z=0.6 (measured on the export:
// bed face ending at x=3.0, z=0.6 undersides out to x=7.5). A flat 90 deg
// bed edge is fully printable, so printability wins over the style token
// and the exception is recorded in NOTES.md. tol passes through to the fin.
module clip(cd, fit = cable_fit, tol = slot_fit_tol) {
    h = body_h(cd);
    assert(2 * ring_ro(cd, fit) <= standoff_max,
           str("body extends past the rail face over the brief's 14 mm cap (",
               2 * ring_ro(cd, fit), " mm) — lower wall or the station Ø"));
    union() {
        linear_extrude(h)
            loop_profile(cd, fit);
        lug_fin(tol);
    }
}

// E2020 rail negative for the boolean fit checks: extrusion face at x = 0,
// mouth through the 2 mm lips, 12 mm cavity behind them to the slot depth.
// Prismatic along the rail axis (z here), like the clip's own pose.
module rail_block() {
    h = max(body_h(station_d[0]), body_h(station_d[1]), body_h(station_d[2])) + 4;
    difference() {
        translate([-(slot_depth + 2), -(slot_cavity_w / 2 + 4), -1])
            cube([slot_depth + 2, slot_cavity_w + 8, h]);
        // mouth through the lips
        translate([-slot_lip_t - 0.01, -slot_mouth / 2, -0.5])
            cube([slot_lip_t + 0.02, slot_mouth, h + 1]);
        // cavity behind the lips (slot_depth measured from the face)
        translate([-(slot_depth + 0.01), -slot_cavity_w / 2, -0.5])
            cube([slot_depth - slot_lip_t + 0.02, slot_cavity_w, h + 1]);
    }
}

// "Print this first" coupon: the production lug on a strip of the
// production back (tune slot_fit_tol against the real rail), plus a strip
// of production loop sections sweeping cable-Ø clearance 0.0 / 0.2 / 0.4
// (tune cable_fit by feel). One base plate carries all of it; the fin
// starts on top of the base with solid material under its full footprint,
// so it still prints as stacked identical layers.
module coupon() {
    cd = coupon_d;
    h = body_h(cd);
    ro = ring_ro(cd, cable_fit);
    strip_w = lug_head_w + 3;           // back strip width (fin + margin)
    pitch = 2 * ro + 3;                 // loop section spacing
    fits = [0.0, 0.2, 0.4];
    // loop section centres along y, clear of the lug strip
    y0 = strip_w / 2 + ro + 4;
    ys = [for (i = [0:2]) y0 + i * pitch];
    total_w = ys[2] + ro + 3;
    base_x = 2 * ro + 3;
    base = [-(slot_lip_t + lug_engage + 1), -(strip_w / 2 + 2), total_w + strip_w / 2 + 2];
    difference() {
        union() {
            // base plate under everything (fin footprint included)
            translate([base[0], base[1], 0])
                rounded_box([base_x - base[0], base[2] - base[1], 1.6],
                            r = min(corner_r, 2), bottom_chamfer = 0);
            // back strip + the production lug fin on top of the base
            translate([0, 0, 1.6])
                rounded_box([3, strip_w, h - 1.6], r = min(corner_r, 1.5),
                            bottom_chamfer = 0);
            translate([0, 0, 1.6])
                lug_fin();
            // the three loop sections, cable_fit swept
            for (i = [0:2])
                translate([0, ys[i], 1.6])
                    linear_extrude(h)
                        loop_profile(cd, fits[i]);
        }
    }
}

module main() {
    assert(lug_neck_w < slot_mouth - 0.2,
           "lug neck must slide through the slot mouth — lower slot_fit_tol");
    assert(lug_head_w > slot_mouth + 0.5,
           "lug head must be wider than the mouth to hook the lips");
    assert(lug_head_w < slot_cavity_w - 2 * cavity_tol,
           "lug head too wide — it will not slide inside the cavity");
    assert(slot_lip_t + lug_engage <= slot_depth - 0.5,
           "lug bottoms out in the cavity before the body seats on the face");
    assert(tab_t >= 0.8, "flex-tab wall under 2 extrusion widths");
    assert(wall >= 1.2, "ring wall under 3 perimeters at 0.4 nozzle");
    assert(tab_sector < 135, "front relief would reach the back web");
    for (cd = station_d)
        assert(throat_hw(cd) >= 0.6,
               str("throat under 1.2 mm wide at station ", cd,
                   " — lower tab_bite"));

    if (part == "lineup") {
        // family preview: the three stations in a row (left to right
        // A / B / C). A preview, not the deliverable — the plate is.
        gap = 6;
        w = [for (cd = station_d) 2 * ring_ro(cd, cable_fit)];
        ys = [-(w[1] / 2 + gap + w[0] / 2), 0, w[1] / 2 + gap + w[2] / 2];
        for (i = [0:2])
            translate([0, ys[i], 0])
                clip(station_d[i]);
    } else if (part == "station-a") {
        clip(station_d[0]);
    } else if (part == "station-b") {
        clip(station_d[1]);
    } else if (part == "station-c") {
        clip(station_d[2]);
    } else if (part == "coupon") {
        coupon();
    } else if (part == "lug-fit") {
        // production lug in the production rail: nothing may overlap
        intersection() {
            clip(station_d[1]);
            rail_block();
        }
    } else if (part == "lug-fit-tight") {
        // negative control: a deliberately oversize neck (tol = -0.15)
        // must overlap the lips — proves the check can fail
        intersection() {
            clip(station_d[1], tol = -0.15);
            rail_block();
        }
    } else if (part == "installed") {
        // README preview only (not in ci.parts): station B seated in a
        // short rail section — the fitcheck pair posed together; the
        // fitcheck proves they do not overlap.
        rail_block();
        clip(station_d[1]);
    }
}

main();
