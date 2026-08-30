// preroll-elevator — a chapstick / glue-stick-style twist tube that presents
// pre-rolls. Unscrew the hex cap-nut lid, twist the hex knob at the base: a
// central printable lead-screw raises an elevator carrying 4 rolls in a ring so
// their tops rise out the top to grab; twist back to retract, cap the lid to
// close. Styled as an industrial hex bolt with a nut on top — the elevator is
// literally a nut climbing a bolt.
// Requirements, decisions and derivations: see NOTES.md. Design brief: #471.
// All dimensions in millimeters.

use <printability.scad>     // chamfered_cylinder, screw presets (OPENSCADPATH=lib:.)
use <threads-fdm.scad>      // thread_neck (male) / thread_bore_cut (female)

/* [Part] */
// What to render. The 6 printable parts, the two fit coupons, the assembled
// preview, the boolean fit proofs (ci.fitchecks — never printed), and a section.
part = "assembly"; // [assembly, body, lid, screw, knob, elevator, cap, thread-coupon, tab-fit-coupon, fit-mate, fit-mate-ctrl, lid-fit-mate, lid-fit-mate-ctrl, knob-fit, knob-fit-ctrl, base-clear, base-clear-ctrl, cap-fit, cap-fit-ctrl, tip-clear, tip-clear-ctrl, cutaway]

/* [Size preset] */
// Pre-roll size. Picks roll length + a sensible diameter; "custom" exposes both.
size_preset = "dogwalker"; // [dogwalker, 1.25, 98, king, custom]
// Custom roll outer diameter (mm) — used only when size_preset = custom
roll_d_custom = 7.0;
// Custom roll length (mm) — used only when size_preset = custom
roll_len_custom = 70;
// Elevator TRAVEL (mm): how far the rolls rise. Rise ABOVE the rim is this minus
// retract_gap (~32 mm at defaults), since rolls start retract_gap below the rim.
pop_up = 36;

/* [Rolls & cups] */
// Number of rolls / cups (fixed at 4 for this design)
n_cups = 4;
// Diametral drop-in clearance: cup bore = roll_d + cup_slip (mm)
cup_slip = 0.6;
// Cup wall thickness (mm) — 3 perimeters at a 0.4 nozzle
cup_wall = 1.2;
// Cup depth: lateral support length around each roll (mm)
cup_depth = 26;

/* [Central screw thread — fixed FDM profile] */
// Major (crest) diameter of the central lead-screw (mm)
screw_major = 10.0;
// Radial thread depth = axial 45-deg flank run; shared by both threads (mm).
// FROZEN with pitch: depth 1.4 trips the library's w_root < lead guard.
thread_depth = 1.2;
// Axial rise per turn (single start) — shared by both threads (mm)
thread_pitch = 4.0;
// Thread starts. SINGLE START = self-locking (lead angle << PLA friction) so a
// loaded elevator holds its height and cannot back-drive closed. Do not raise.
thread_starts = 1;
// Radial thread fit clearance (mm), applied to the FEMALE only. Dial on the
// thread coupon. Shared by both threads — re-check the lid after changing it.
thread_tol = 0.3;
// Central-thread helix segments/turn (chord error < 0.01 mm at this major)
screw_seg = 64;
// Radial wall of the elevator nut hub over the female crest (mm, load-bearing)
nut_wall = 1.6;
// Female engagement height of the elevator nut = 3 turns (mm)
nut_h = 12;

/* [Top cap] */
// The positive pop-up stop is a SEPARATE printed part (the cap), pressed onto an
// unthreaded tip at the screw top AFTER the elevator threads on from the top. The
// tip MUST stay <= the nut bore, or it would trap the nut — a stop wider than the
// bore cannot be installed on a one-piece captured screw (see NOTES "Bugs caught").
// Unthreaded tip Ø at the screw top; the elevator threads on OVER this (<= nut bore) (mm)
cap_tip_d = 8.0;
// Tip height / cap grip length (mm)
cap_tip_h = 6;
// Cap outer Ø — the shoulder the elevator nut tops out against (> nut bore, < body bore) (mm)
cap_flange_d = 13;
// Cap total height (mm)
cap_h = 8;
// Diametral clearance of the cap bore over the tip — the press fit (dial like the knob) (mm)
cap_fit = 0.2;

/* [Lid thread] */
// Wall between the body bore and the external male lid-thread root at the top (mm)
lid_neck_wall = 1.6;
// Male lid-thread length on the body top neck = 2 turns to open (mm)
lid_engage = 8;
// Hex cap-nut wall over the internal lid thread (mm)
lid_wall = 2.0;
// Lid-thread helix segments/turn (larger major needs more; chord < 0.02 mm)
lid_seg = 96;
// Lead-in below the lid's engaging turns so first-layer squish tightens dead bore (mm)
lid_lead_in = 1.6;
// Flat closed-top thickness of the cap nut (mm)
lid_cap_t = 3.0;

/* [Body] */
// Bore-to-outer wall of the round bolt-shank body (mm)
body_wall = 2.0;
// Radial gap hub-outer to cup-inner-edge (static, on the elevator) (mm)
g_in = 0.8;
// Radial gap cup-outer-edge to body bore (this interface SLIDES) (mm)
g_out = 0.8;
// Clear gap under the retracted roll tops to the rim, so the lid closes (mm)
retract_gap = 4;

/* [Anti-rotation] */
// Full-length through-slots in the wall (interleaved 45 deg between the cups).
// They must stay OPEN to the top rim so the elevator's tabs can be inserted, so
// the body is a vented cage, not a sealed container (see README).
n_slots = 4;
// Circumferential slot width (mm)
slot_w = 4.0;
// Elevator tab width in the slot (slot_w - tab_w = total circumferential slop) (mm)
tab_w = 3.5;
// Axial tab height (long moment arm resists cocking) (mm)
tab_len = 8.0;

/* [Elevator] */
// Elevator base plate / spider-arm thickness (mm)
elevator_plate_t = 3.0;
// Elevator position for the assembly preview: 0 = retracted, 1 = fully popped up
elevator_pos = 1; // [0:0.05:1]
// Animation flag: when true, the elevator position follows $t (0->1->0) for the
// elevator-raising GIF (animations.conf); the lid is shown removed beside it.
animate = false;
// Ghost payload in the assembly/section previews only (the user's rolls, shown
// for context). The deterministic cameras.conf previews keep them per the
// charter; the product-shot manifests set this false so the geometry-true studio
// shots show only printed geometry (PM.md Never list). STL export drops color(),
// so a ghost left in a product shot would render as printed plastic.
ghost_rolls = true;
// Show the lid in the assembly/section previews. Detail shots that look into the
// mechanism (the tab-slot close-ups) set this false so the beside-placed lid does
// not intrude; the showroom previews keep it.
show_lid = true;

/* [Base / knob] */
// Solid floor thickness under the flange (carries the plain journal bore) (mm)
floor_base = 2;
// 45-deg conical thrust-seat height in the floor (the flange cone nests here) (mm)
seat_h = 3;
// Flat flange thickness above the cone (mm)
flange_flat = 2;
// Screw capture-flange outer diameter (mm)
flange_od = 18;
// Plain journal shaft diameter that locates the screw in the floor bore (mm)
journal_d = 12;
// Diametral spin clearance of the journal in the floor bore (mm)
journal_clearance = 0.5;
// Minimum hex knob (bolt head) across-flats (mm); the effective value tracks the
// body so the head is always wider than the shank across every preset.
knob_af_min = 42;
// Hex knob height (mm)
knob_h = 12;
// Hex torque-key across-flats: the screw's bottom stub, gripped by the knob (mm)
key_af = 9;
// Depth of the knob's hex socket / length of the stub inside it (mm)
socket_depth = 9;
// Hex socket clearance over the stub — dial for a firm, non-slipping twist (mm)
knob_key_clear = 0.25;
// Running gap between the knob top and the body underside; the knob captures the
// screw (up-stop) while the flange cone is the down-stop (mm)
knob_body_gap = 0.4;

/* [Quality] */
// Curve resolution for non-thread cylinders. Threads use screw_seg / lid_seg.
$fn = 64;

// ===========================================================================
// Preset resolution
// ===========================================================================
roll_d =
    size_preset == "dogwalker" ? 7.0 :
    size_preset == "1.25"      ? 7.5 :
    size_preset == "98"        ? 8.5 :
    size_preset == "king"      ? 8.5 :
    roll_d_custom;
roll_len =
    size_preset == "dogwalker" ? 70 :
    size_preset == "1.25"      ? 84 :
    size_preset == "98"        ? 98 :
    size_preset == "king"      ? 109 :
    roll_len_custom;

// ===========================================================================
// Derived geometry — packing (all body dims follow from the roll + hub)
// ===========================================================================
cup_id  = roll_d + cup_slip;                 // 7.6  drop-in bore
cup_od  = cup_id + 2 * cup_wall;             // 10.0
hub_od  = screw_major + 2 * thread_tol + 2 * nut_wall;   // 13.8  elevator nut hub
r_cup   = hub_od / 2 + g_in + cup_od / 2;    // 12.7  cup-centre radius (clears the hub)
bcd     = 2 * r_cup;                          // 25.4
body_id = 2 * (r_cup + cup_od / 2 + g_out);  // 37.0  bore (clears the cup ring)
body_od = body_id + 2 * body_wall;           // 41.0  round shank OD

// Central screw thread (male on screw, female nut in elevator)
screw_root     = screw_major - 2 * thread_depth;                 // 7.6  male core
nut_minor_bore = screw_major - 2 * thread_depth + 2 * thread_tol; // 8.2 MANDATORY
screw_len      = nut_h + pop_up;              // 48  threaded run (nut + travel)
// Screw-clearance bore through the elevator's base disk: the lead-screw passes
// THROUGH the elevator (the nut above grips it), so the solid base disk must be
// bored to clear the crest — or it blocks the screw and the elevator can't ride it.
screw_clear_d  = screw_major + 2 * thread_tol + 1.0;             // 11.6 clears crest Ø10

// Lid thread (male on body top neck, female in lid) — derived from the bore
lid_root       = body_id + 2 * lid_neck_wall;                    // 40.2  male core
lid_major      = lid_root + 2 * thread_depth;                    // 42.6
lid_minor_bore = lid_major - 2 * thread_depth + 2 * thread_tol;  // 40.8 MANDATORY
lid_af         = lid_major + 2 * thread_tol + 2 * lid_wall;      // 47.2  cap-nut across-flats

// Base: the screw is captured by the floor between its flange (above) and the
// press-on knob (below). Z-levels (assembled frame: z = 0 at the body bottom face)
journal_bore_d = journal_d + journal_clearance;          // 12.5
z_cavity_floor = floor_base + seat_h;                    // 5   cavity Ø body_id starts here
z_thread_start = z_cavity_floor + flange_flat;           // 7   flange top / screw thread base
z_screw_top    = z_thread_start + screw_len + cap_tip_h;
z_rim = z_thread_start + elevator_plate_t + roll_len + retract_gap;  // mouth
lid_neck_h  = lid_lead_in + lid_engage + 1.0;            // body top male neck height
z_body_top  = z_rim + lid_neck_h;

// Effective hex knob across-flats: always wider than the shank (a real head)
eff_knob_af = max(knob_af_min, body_od + 4);

// Slots run from the flange level up THROUGH the top rim (open at the top, so the
// wide elevator tabs can enter). This interrupts the lid thread into 4 arcs
// (still engages, still self-locks) — and vents the body (not a sealed tube).
z_slot_bot = z_thread_start;
z_slot_top = z_body_top + 1;
slot_len   = z_slot_top - z_slot_bot;

// ===========================================================================
// Sanity guards (fail loudly on a bad preset / override)
// ===========================================================================
assert(cup_wall >= 0.8, "cup_wall below the 0.8 mm feature floor.");
assert(body_wall >= 1.2, "body_wall below the 1.2 mm (3-perimeter) floor.");
assert(nut_wall >= 1.2, "nut_wall below the 1.2 mm load-bearing floor.");
assert(r_cup - cup_od / 2 >= hub_od / 2 + g_in - 0.001,
       "radial pack: cups overlap the central hub — grow g_in or shrink cups.");
assert(bcd * sin(180 / n_cups) >= cup_od + 1.0,
       str("cups crowd circumferentially: pitch ", bcd * sin(180 / n_cups),
           " vs cup_od ", cup_od));
assert(eff_knob_af > body_od,
       str("knob head ", eff_knob_af, " must be wider than the shank ", body_od));
assert(flange_od > journal_bore_d,
       "flange must be wider than the floor bore so the floor captures the screw.");
assert(key_af + knob_key_clear < journal_bore_d,
       "hex torque stub must pass through the floor bore.");
assert(slot_len >= pop_up + tab_len,
       str("slot ", slot_len, " shorter than travel+tab ", pop_up + tab_len));
assert(screw_clear_d > screw_major && screw_clear_d < hub_od,
       "base-disk screw clearance must clear the crest yet keep a nut ring.");
// The collar-class regression guard: NO feature above the thread may exceed the
// nut bore, or the elevator nut cannot be threaded on past it during assembly
// (the whole reason the top stop is a separate press-on cap, not an on-screw collar).
assert(cap_tip_d <= nut_minor_bore,
       str("screw-top tip ", cap_tip_d, " exceeds the nut bore ", nut_minor_bore,
           " — the elevator nut could not thread on past it (the collar-class assembly trap)."));
assert(cap_flange_d > nut_minor_bore && cap_flange_d < body_id,
       "cap flange must overhang the nut bore (to stop it) yet fit inside the body bore.");

// ===========================================================================
// Small helpers
// ===========================================================================
module hex_af(af, h) { rotate([0, 0, 30]) cylinder(r = af / (2 * cos(30)), h = h, $fn = 6); }

// Hex prism with 45-deg top/bottom chamfers (built by hulling inset hex slabs).
module hex_chamf(af, h, c1 = 1.0, c2 = 1.0) {
    R = af / (2 * cos(30));
    hull() {
        translate([0, 0, c1]) rotate([0, 0, 30]) cylinder(r = R, h = max(0.01, h - c1 - c2), $fn = 6);
        if (c1 > 0) rotate([0, 0, 30]) cylinder(r = (af - 2 * c1) / (2 * cos(30)), h = 0.01, $fn = 6);
        if (c2 > 0) translate([0, 0, h - 0.01]) rotate([0, 0, 30]) cylinder(r = (af - 2 * c2) / (2 * cos(30)), h = 0.01, $fn = 6);
    }
}

// Angular position of cup i and slot i
function cup_a(i)  = i * 360 / n_cups;
function slot_a(i) = i * 360 / n_slots + 45;

// ===========================================================================
// BODY — round bolt-shank tube. Prints base-down, mouth + external thread up.
// ===========================================================================
module body() {
    difference() {
        union() {
            // shank + solid base
            chamfered_cylinder(d = body_od, h = z_rim, chamfer1 = 1.0, chamfer2 = 0);
            // external male lid thread neck at the top (core = lid_root)
            translate([0, 0, z_rim])
                thread_neck(lid_major, thread_depth, thread_pitch, thread_starts,
                            lid_engage, seg = lid_seg);
            // plain collar between shank top and thread lead-in
            translate([0, 0, z_rim - 0.01])
                cylinder(d = lid_root, h = lid_lead_in + 0.01);
        }
        // main cavity bore, open to the top
        translate([0, 0, z_cavity_floor - 0.01])
            cylinder(d = body_id, h = z_body_top - z_cavity_floor + 0.02);
        // base central passage: plain journal bore then the 45-deg conical thrust seat
        translate([0, 0, -0.01]) cylinder(d = journal_bore_d, h = floor_base + 0.02);
        // 45-deg chamfer on the bore mouth at the bed face: first-layer squish here
        // pinches the journal clearance exactly where the knob stack passes at
        // assembly, so widen the mouth 0.6 mm to absorb it. (The outer base edge is
        // already chamfered 1.0 mm by chamfered_cylinder above.)
        translate([0, 0, -0.01])
            cylinder(d1 = journal_bore_d + 1.2, d2 = journal_bore_d, h = 0.61);
        translate([0, 0, floor_base])
            cylinder(d1 = journal_bore_d, d2 = flange_od + 0.4, h = seat_h + 0.01);
        // anti-rotation through-slots, open at the top rim
        for (i = [0 : n_slots - 1])
            rotate([0, 0, slot_a(i)])
                translate([body_od / 2, 0, (z_slot_bot + z_slot_top) / 2])
                    cube([body_wall * 4 + lid_neck_wall * 2, slot_w, slot_len], center = true);
    }
}

// ===========================================================================
// LID — hex cap nut. Prints closed-flat-top DOWN, mouth + internal thread up.
// ===========================================================================
module lid() {
    lid_thread_h = lid_lead_in + lid_engage + 1.0;
    lid_h = lid_cap_t + lid_thread_h;
    difference() {
        // small top chamfer (c2) so the mouth rim keeps a solid wall, not a feather edge
        hex_chamf(lid_af, lid_h, c1 = 1.0, c2 = 0.8);
        // internal thread cut from the top (mouth), lead-in nearest the bed
        translate([0, 0, lid_cap_t - 0.01])                       // mandatory minor bore
            cylinder(d = lid_minor_bore, h = lid_thread_h + 0.02);
        translate([0, 0, lid_cap_t + lid_lead_in])
            thread_bore_cut(lid_major, thread_depth, thread_pitch, thread_starts,
                            lid_engage + 0.5, thread_tol, seg = lid_seg);
        // modest mouth lead-in chamfer (keeps rim wall > 0.8 mm)
        translate([0, 0, lid_h - 0.7])
            cylinder(d1 = lid_minor_bore, d2 = lid_minor_bore + 1.4, h = 0.71);
    }
}

// ===========================================================================
// SCREW — central male lead-screw with a flange (captured by the body floor) and
// a hex torque stub at the bottom that the knob grips. Modelled in the assembled
// frame; top-loaded into the body from above. Prints thread-up (stub on the bed).
// ===========================================================================
module screw_use() {
    // hex torque stub below the floor (the knob presses onto this)
    translate([0, 0, -(knob_body_gap + socket_depth)])
        hex_af(key_af, knob_body_gap + socket_depth + 0.01);
    // plain journal through the floor bore
    cylinder(d = journal_d, h = floor_base + 0.01);
    // capture flange: 45-deg conical underside (nests in the floor seat) + flat top
    translate([0, 0, floor_base]) cylinder(d1 = journal_d, d2 = flange_od, h = seat_h);
    translate([0, 0, z_cavity_floor]) cylinder(d = flange_od, h = flange_flat);
    // central male lead-screw
    translate([0, 0, z_thread_start])
        thread_neck(screw_major, thread_depth, thread_pitch, thread_starts,
                    screw_len, seg = screw_seg);
    // unthreaded tip at the screw top: the elevator threads on OVER this during
    // assembly (tip <= nut bore, so the nut passes it), then the printed cap presses
    // onto it as the positive pop-up stop. No on-screw collar — a collar wider than
    // the nut bore would trap the nut. Top chamfer eases the nut lead-on + cap start.
    translate([0, 0, z_thread_start + screw_len - 0.01])
        chamfered_cylinder(d = cap_tip_d, h = cap_tip_h + 0.01, chamfer1 = 0, chamfer2 = 0.8);
}
// print orientation: thread up, stub on the bed
module screw() { translate([0, 0, knob_body_gap + socket_depth]) screw_use(); }

// ===========================================================================
// KNOB — hex bolt-head that presses onto the screw's hex stub (torque key) and
// captures the screw against the floor from below. Prints hex-flat down, socket up.
// ===========================================================================
module knob_use() {
    difference() {
        translate([0, 0, -(knob_body_gap + knob_h)]) hex_chamf(eff_knob_af, knob_h, c1 = 1.0, c2 = 1.5);
        // hex socket opening upward to receive the stub. The floor is cut 0.5 mm
        // deeper than the stub tip so the press seats on feel (the knob wound up
        // until it nearly meets the body underside), not on a bulgy printed floor
        // — the ~0.09 mm tip-to-floor margin was smaller than a normal top-surface
        // bulge, making the stop depend on the floor's mood.
        translate([0, 0, -(knob_body_gap + socket_depth + 0.5)])
            hex_af(key_af + knob_key_clear, socket_depth + 0.6);
    }
}
module knob() { translate([0, 0, knob_body_gap + knob_h]) knob_use(); }

// ===========================================================================
// CAP — the positive pop-up stop, a SEPARATE printed part. Any on-screw stop
// wider than the nut bore would trap the nut (the collar-class bug), so the stop
// is pressed onto the screw tip AFTER the elevator threads on. Prints flat, bore
// UP: a plain disc on the bed and a clean vertical bore — supportless, no bridge,
// and the 0.2 mm press-fit mouth sits 8 mm clear of first-layer squish. cap_use()
// flips it bore-down onto the screw tip for the assembled frame — the same
// print-vs-use split as knob()/knob_use().
// ===========================================================================
module cap() {
    difference() {
        cylinder(d = cap_flange_d, h = cap_h);
        // bore opens at the TOP (print orientation): keeps the press mouth off the bed
        translate([0, 0, cap_h - cap_tip_h]) cylinder(d = cap_tip_d + cap_fit, h = cap_tip_h + 0.01);
    }
}
// flipped bore-down and placed on the screw tip; its flange underside at the
// thread top is the elevator nut's up-stop. Same assembled position as before —
// only the printed (exported) orientation changed.
module cap_use() {
    translate([0, 0, z_thread_start + screw_len + cap_h]) rotate([180, 0, 0]) cap();
}

// ===========================================================================
// ELEVATOR — spider: central female nut + full base disk + 4 cups + 4 tabs.
// Built hub-bottom at z=0; prints cups-up (as built). Placed in assembly by z.
// ===========================================================================
// One anti-rotation tab, rooted in the elevator disk edge and reaching out through
// the g_out gap into a body slot (tip just inside the OD). The bottom outer + side
// edges are chamfered so first-layer squish doesn't bind the tab at full retract.
// SHARED by elevator() and tab_fit_coupon() so the coupon stays the EXACT production
// pair — no copied cube that could silently drift from the part it exists to detect.
module anti_rot_tab() {
    x0    = (body_id - 2 * g_out) / 2 - 0.5;   // disk-edge root
    reach = body_od / 2 - x0 - 0.3;            // tip just inside the OD
    ch    = 0.5;                                // bottom-edge chamfer
    translate([x0, -tab_w / 2, 0]) hull() {
        translate([0, 0, ch]) cube([reach, tab_w, tab_len - ch]);
        translate([0, ch, 0])  cube([reach - ch, tab_w - 2 * ch, 0.01]);
    }
}

module central_nut(h) {
    // female nut: the MANDATORY plain minor bore plus the groove cutter (full
    // height, matching the fitcheck ring). Prints cups-up with the hub at the
    // bed; the near-bed first turn is squish-compensated by the coupon-tuned
    // thread_tol (it is NOT relieved — the coupon shares this orientation).
    difference() {
        cylinder(d = hub_od, h = h);
        translate([0, 0, -0.01]) cylinder(d = nut_minor_bore, h = h + 0.02);   // mandatory minor bore
        thread_bore_cut(screw_major, thread_depth, thread_pitch, thread_starts,
                        h, thread_tol, seg = screw_seg);
    }
}

module elevator() {
    disk_d = body_id - 2 * g_out;             // 35.4 — full base disk, slides in the bore
    cup_floor = elevator_plate_t;
    difference() {
        union() {
            central_nut(nut_h);
            // full base plate disk: ties hub, cups and tabs together; the sliding fit.
            cylinder(d = disk_d, h = elevator_plate_t);
            // cups on the ring
            for (i = [0 : n_cups - 1])
                rotate([0, 0, cup_a(i)])
                    translate([r_cup, 0, 0]) difference() {
                        cylinder(d = cup_od, h = elevator_plate_t + cup_depth);
                        translate([0, 0, cup_floor]) cylinder(d = cup_id, h = cup_depth + 0.01);
                    }
            // anti-rotation tabs at 45 deg between cups, rooted in the disk edge and
            // reaching out through the g_out gap into the body slots (tip just inside OD)
            for (i = [0 : n_slots - 1])
                rotate([0, 0, slot_a(i)]) anti_rot_tab();
        }
        // screw-clearance bore through the base disk so the lead-screw passes
        // THROUGH the elevator (the nut above provides the threaded grip); without
        // it the solid disk blocks the screw and the elevator cannot ride it.
        translate([0, 0, -0.01]) cylinder(d = screw_clear_d, h = elevator_plate_t + 0.02);
    }
}

// ===========================================================================
// Fit coupons ("print this first")
// ===========================================================================
// Central thread coupon: production male stub + female nut ring, side by side.
module thread_coupon() {
    gap = 10;
    stub = nut_h + 4;
    translate([-(hub_od + 8 + gap) / 2, 0, 0])
        union() {
            chamfered_cylinder(d = hub_od + 6, h = 2.0, chamfer2 = 0);
            translate([0, 0, 1.5]) cylinder(d = screw_root, h = 0.51);
            translate([0, 0, 2.0]) thread_neck(screw_major, thread_depth, thread_pitch,
                                               thread_starts, stub, seg = screw_seg);
        }
    translate([(hub_od + 8 + gap) / 2, 0, 0]) central_nut(nut_h);
}

// Anti-rotation slide-fit coupon: a slot section of wall + the elevator tab.
module tab_fit_coupon() {
    seg_h = tab_len + 8;
    gap = 8;
    // wall slice with the through-slot
    translate([-(body_od / 2 + gap), 0, 0]) difference() {
        chamfered_cylinder(d = body_od, h = seg_h, chamfer1 = 0.6, chamfer2 = 0.6);
        translate([0, 0, -0.01]) cylinder(d = body_id, h = seg_h + 0.02);
        translate([body_od / 2, 0, seg_h / 2]) cube([body_wall * 4, slot_w, seg_h + 1], center = true);
    }
    // a stub of elevator edge carrying one production tab (same reach as elevator())
    disk_d = body_id - 2 * g_out;
    translate([body_od / 2 + gap, 0, 0]) union() {
        cylinder(d = 10, h = elevator_plate_t);
        translate([0, -3, 0]) cube([disk_d / 2 - 0.5, 6, elevator_plate_t]);
        anti_rot_tab();
    }
}

// ===========================================================================
// Boolean fit proofs (ci.fitchecks — never printed). The threads are single-
// start, so the interfering control is a HALF-lead (180 deg) rotation, not 90.
// The hex torque key is 60-deg symmetric, so its control is a 30 deg rotation.
// ===========================================================================
module central_male_short() {
    thread_neck(screw_major, thread_depth, thread_pitch, thread_starts, nut_h + 2, seg = screw_seg);
}
module central_female_ring() {
    difference() {
        cylinder(d = hub_od, h = nut_h);
        translate([0, 0, -0.01]) cylinder(d = nut_minor_bore, h = nut_h + 0.02);
        thread_bore_cut(screw_major, thread_depth, thread_pitch, thread_starts, nut_h, thread_tol, seg = screw_seg);
    }
}
module fit_mate(rot = 0) {
    intersection() { central_male_short(); rotate([0, 0, rot]) central_female_ring(); }
}
module lid_male_short() {
    thread_neck(lid_major, thread_depth, thread_pitch, thread_starts, lid_engage, seg = lid_seg);
}
module lid_female_ring() {
    difference() {
        cylinder(d = lid_af, h = lid_engage);
        translate([0, 0, -0.01]) cylinder(d = lid_minor_bore, h = lid_engage + 0.02);
        thread_bore_cut(lid_major, thread_depth, thread_pitch, thread_starts, lid_engage, thread_tol, seg = lid_seg);
    }
}
module lid_fit_mate(rot = 0) {
    intersection() { lid_male_short(); rotate([0, 0, rot]) lid_female_ring(); }
}
module knob_stub_solid() { hex_af(key_af, socket_depth); }
module knob_socket_ring() {
    difference() {
        cylinder(d = key_af * 1.7, h = socket_depth);
        translate([0, 0, -0.01]) hex_af(key_af + knob_key_clear, socket_depth + 0.02);
    }
}
module knob_fit(rot = 0) {
    intersection() { knob_stub_solid(); rotate([0, 0, rot]) knob_socket_ring(); }
}
// Base-disk screw-clearance proof: the lead-screw passes THROUGH the elevator, so
// its base disk (below the threaded nut) must clear the crest. The disk carries no
// thread, so this needs no clocking — `empty` = the bored disk clears the screw,
// and the `interferes` control is the old SOLID disk that blocked it. This is the
// check whose absence let the disk-block bug ship (fit-mate tests only the nut ring).
module elevator_base(bored = true) {
    disk_d = body_id - 2 * g_out;
    difference() {
        cylinder(d = disk_d, h = elevator_plate_t);
        if (bored) translate([0, 0, -0.01]) cylinder(d = screw_clear_d, h = elevator_plate_t + 0.02);
    }
}
module base_clear_mate(bored = true) {
    intersection() { elevator_base(bored); central_male_short(); }
}
// Cap press fit + the assembly-feasibility proof that the elevator nut clears the
// screw tip during installation (the collar-class bug's check-in-mesh — the guard
// that a stop wider than the nut bore can never come back). Round parts, no clocking.
module cap_tip_solid(oversize = 0) { cylinder(d = cap_tip_d + oversize, h = cap_tip_h); }
module cap_bore_ring() {
    difference() {
        cylinder(d = cap_flange_d, h = cap_tip_h);
        translate([0, 0, -0.01]) cylinder(d = cap_tip_d + cap_fit, h = cap_tip_h + 0.02);
    }
}
// cap-fit: empty = the cap bore clears the tip; ctrl oversizes the tip so it interferes.
module cap_mate(oversize = 0) {
    intersection() { cap_tip_solid(oversize); cap_bore_ring(); }
}
// tip-clear: empty = the elevator nut passes the tip during install; ctrl oversizes
// the tip past the nut bore so it interferes (proving the check can fire).
module tip_clear_mate(oversize = 0) {
    intersection() { central_nut(nut_h); cap_tip_solid(oversize); }
}

// ===========================================================================
// Assembly preview + section (never the deliverable — parts print separately)
// ===========================================================================
module assembly() {
    // $t-driven position when animating (0->1->0), else the static preview position
    pos = animate ? (0.5 - 0.5 * cos(360 * $t)) : elevator_pos;
    z_nut = z_thread_start + pos * pop_up;
    lid_on = !animate && pos < 0.5;
    body();
    screw_use();
    knob_use();
    cap_use();
    color("#c9c9cf") translate([0, 0, z_nut]) elevator();
    // ghost rolls (preview only) — rise with the elevator. Suppressed in the
    // geometry-true product shots (shots.conf sets ghost_rolls=false) so they
    // never export as printed plastic; kept in the deterministic previews.
    if (ghost_rolls)
        for (i = [0 : n_cups - 1])
            rotate([0, 0, cup_a(i)]) translate([r_cup, 0, z_nut + elevator_plate_t])
                color("#e8c39a") cylinder(d = roll_d, h = roll_len);
    if (show_lid) {
        if (lid_on) {
            lid_h = lid_cap_t + lid_lead_in + lid_engage + 1.0;
            translate([0, 0, z_rim - lid_lead_in + lid_h]) rotate([180, 0, 0]) lid();
        } else {
            translate([body_od / 2 + eff_knob_af / 2 + 14, 0, 0]) lid();
        }
    }
}

module cutaway() {
    difference() {
        assembly();
        translate([0, -60, -40]) cube([60, 120, 220]);
    }
}

// ===========================================================================
// Dispatch
// ===========================================================================
if (part == "body") body();
else if (part == "lid") lid();
else if (part == "screw") screw();
else if (part == "knob") knob();
else if (part == "elevator") elevator();
else if (part == "thread-coupon") thread_coupon();
else if (part == "tab-fit-coupon") tab_fit_coupon();
else if (part == "fit-mate") fit_mate();
else if (part == "fit-mate-ctrl") fit_mate(180);
else if (part == "lid-fit-mate") lid_fit_mate();
else if (part == "lid-fit-mate-ctrl") lid_fit_mate(180);
else if (part == "knob-fit") knob_fit();
else if (part == "knob-fit-ctrl") knob_fit(30);
else if (part == "base-clear") base_clear_mate();
else if (part == "base-clear-ctrl") base_clear_mate(false);
else if (part == "cap") cap();
else if (part == "cap-fit") cap_mate();
else if (part == "cap-fit-ctrl") cap_mate(cap_fit + 0.2);
else if (part == "tip-clear") tip_clear_mate();
else if (part == "tip-clear-ctrl") tip_clear_mate(cap_fit + 0.2);
else if (part == "cutaway") cutaway();
else assembly();
