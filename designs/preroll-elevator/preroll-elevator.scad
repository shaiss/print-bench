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
// What to render. The 5 printable parts, the two fit coupons, the assembled
// preview, the boolean thread-mate proofs (ci.fitchecks — never printed), and a
// section. Every ci.parts / ci.plate / ci.fitchecks / coupon name maps here.
part = "assembly"; // [assembly, body, lid, screw-knob, elevator, retainer, thread-coupon, tab-fit-coupon, fit-mate, fit-mate-ctrl, lid-fit-mate, lid-fit-mate-ctrl, cutaway]

/* [Size preset] */
// Pre-roll size. Picks roll length + a sensible diameter; "custom" exposes both.
size_preset = "dogwalker"; // [dogwalker, 1.25, 98, king, custom]
// Custom roll outer diameter (mm) — used only when size_preset = custom
roll_d_custom = 7.0;
// Custom roll length (mm) — used only when size_preset = custom
roll_len_custom = 70;
// How far the rolls rise above the rim at full extension = elevator travel (mm)
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
// Unthreaded stop collar at the top of the screw — the positive pop-up hard stop (mm)
top_stop_h = 3;

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
// Full-length through-slots in the wall (interleaved 45 deg between the cups)
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

/* [Base / retainer / knob] */
// Hex twist-knob (bolt head) across-flats (mm) — wider than the shank = a head
knob_af = 42;
// Hex knob height (mm)
knob_h = 12;
// Screw capture flange outer diameter, inside the body base (mm)
flange_od = 18;
// Plain journal shaft diameter that locates the screw in the body floor (mm)
journal_d = 12;
// Diametral spin clearance of the journal in the body floor bore (mm)
journal_clearance = 0.5;
// Retainer ring thickness (mm)
retainer_thickness = 2.5;
// Retainer counterbore diameter in the body base (mm)
retainer_cb = 24;
// Radial press/snap clearance of the retainer in its counterbore (mm)
retainer_fit = 0.2;
// Axial float between flange top and retainer underside (screw spins on the seat) (mm)
retainer_float = 0.4;
// Gap between knob top and body underside so the flange cone is the sole down-stop (mm)
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
// Cup bolt-circle: the binding constraint is clearing the central hub inside.
r_cup   = hub_od / 2 + g_in + cup_od / 2;    // 12.7  cup-centre radius
bcd     = 2 * r_cup;                          // 25.4
body_id = 2 * (r_cup + cup_od / 2 + g_out);  // 37.0  bore (clears the cup ring)
body_od = body_id + 2 * body_wall;           // 41.0  round shank OD

// Central screw thread (male on screw-knob, female nut in elevator)
screw_root     = screw_major - 2 * thread_depth;              // 7.6  male core
nut_minor_bore = screw_major - 2 * thread_depth + 2 * thread_tol; // 8.2 MANDATORY
screw_len      = nut_h + pop_up;              // 48  threaded run (nut + travel)

// Lid thread (male on body top neck, female in lid) — derived from the bore
lid_root       = body_id + 2 * lid_neck_wall;                 // 40.2  male core
lid_major      = lid_root + 2 * thread_depth;                 // 42.6
lid_minor_bore = lid_major - 2 * thread_depth + 2 * thread_tol; // 40.8 MANDATORY
lid_af         = lid_major + 2 * thread_tol + 2 * lid_wall;   // 47.2  cap-nut across-flats

// Z-levels (assembled frame: z = 0 at the body bottom face; knob below)
floor_base   = 2;                            // solid under the journal bore
seat_h       = 3;                            // 45-deg conical thrust seat rise
flange_flat  = 1;                            // flat above the cone
z_flange_top   = floor_base + seat_h + flange_flat;      // 6
z_retainer_bot = z_flange_top + retainer_float;          // 6.4
z_retainer_top = z_retainer_bot + retainer_thickness;    // 8.9
z_thread_start = z_retainer_top + 0.6;                   // 9.5  screw thread base
z_screw_top    = z_thread_start + screw_len + top_stop_h; // top of stop collar
// mouth (rim): retracted roll tops sit retract_gap below it
z_rim = z_thread_start + elevator_stack_h() + roll_len + retract_gap;
lid_neck_h  = lid_lead_in + lid_engage + 1.0;            // body top male neck height
z_body_top  = z_rim + lid_neck_h;

function elevator_stack_h() = elevator_plate_t;          // cup floor above nut bottom

// Slots run from just above the base seat up THROUGH the top rim, so they are
// open at the top: the elevator tabs (which reach past the bore) can only enter
// from the open top, and this interrupts the lid thread into 4 arcs (still
// engages and self-locks). Bottom clears the retainer; top runs out past the rim.
z_slot_bot = z_thread_start;                 // 9.5, above the retainer top (8.9)
z_slot_top = z_body_top + 1;                 // open through the top rim
slot_len   = z_slot_top - z_slot_bot;

journal_bore_d = journal_d + journal_clearance;          // 12.5
retainer_od    = retainer_cb - retainer_fit;             // 23.8
retainer_id    = journal_d + 0.9;                        // 12.9  (< flange_od, traps it)

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
assert(retainer_id < flange_od, "retainer bore must be smaller than the flange to trap it.");
assert(slot_len >= pop_up + tab_len,
       str("slot ", slot_len, " shorter than travel+tab ", pop_up + tab_len));

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
        translate([0, 0, z_thread_start - 0.01])
            cylinder(d = body_id, h = z_body_top - z_thread_start + 0.02);
        // base central passage for the screw-knob
        translate([0, 0, -0.01]) cylinder(d = journal_bore_d, h = floor_base + 0.02);   // journal bore
        translate([0, 0, floor_base])                                                   // 45-deg cone seat
            cylinder(d1 = journal_bore_d, d2 = flange_od, h = seat_h);
        translate([0, 0, floor_base + seat_h - 0.01])                                   // flange pocket, up to the retainer cb (continuous passage)
            cylinder(d = flange_od, h = z_retainer_bot - (floor_base + seat_h) + 0.02);
        translate([0, 0, z_retainer_bot])                                               // retainer counterbore
            cylinder(d = retainer_cb, h = z_thread_start - z_retainer_bot + 0.02);
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
// SCREW-KNOB — hex bolt head + capture flange + journal + central male screw.
// Modelled in the assembled frame (knob below z=0); prints as-is, knob down.
// ===========================================================================
module screw_knob_use() {
    knob_top = -knob_body_gap;
    union() {
        // hex bolt-head knob
        translate([0, 0, knob_top - knob_h])
            hex_chamf(knob_af, knob_h, c1 = 1.0, c2 = 1.5);
        // lower journal up through the floor into the cone
        translate([0, 0, knob_top]) cylinder(d = journal_d, h = floor_base - knob_top + 0.01);
        // capture flange: 45-deg conical underside (thrust seat) + flat top
        translate([0, 0, floor_base]) cylinder(d1 = journal_d, d2 = flange_od, h = seat_h);
        translate([0, 0, floor_base + seat_h]) cylinder(d = flange_od, h = flange_flat);
        // upper journal through the retainer
        translate([0, 0, z_flange_top]) cylinder(d = journal_d, h = z_thread_start - z_flange_top + 0.01);
        // central male lead-screw
        translate([0, 0, z_thread_start])
            thread_neck(screw_major, thread_depth, thread_pitch, thread_starts,
                        screw_len, seg = screw_seg);
        // unthreaded top stop collar (defines pop-up)
        translate([0, 0, z_thread_start + screw_len - 0.01])
            cylinder(d = journal_d, h = top_stop_h + 0.01);
    }
}
// print orientation: lift so the knob's bottom sits on the bed
module screw_knob() { translate([0, 0, knob_body_gap + knob_h]) screw_knob_use(); }

// ===========================================================================
// ELEVATOR — spider: central female nut + plate + 4 cups + 4 anti-rotation tabs.
// Built hub-bottom at z=0; prints cups-up (as built). Placed in assembly by z.
// ===========================================================================
module central_nut(h) {
    // female nut with the near-bed engaging turns relieved by a plain counterbore
    difference() {
        cylinder(d = hub_od, h = h);
        translate([0, 0, -0.01]) cylinder(d = nut_minor_bore, h = h + 0.02);   // mandatory minor bore
        translate([0, 0, 2])
            thread_bore_cut(screw_major, thread_depth, thread_pitch, thread_starts,
                            h - 2, thread_tol, seg = screw_seg);
    }
}

module elevator() {
    disk_d = body_id - 2 * g_out;             // 35.4 — full base disk, slides in the bore
    cup_floor = elevator_plate_t;
    union() {
        central_nut(nut_h);
        // full base plate disk: ties the hub, cups and tabs together and provides
        // the sliding fit against the bore. Prints flat on the bed (cups up).
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
            rotate([0, 0, slot_a(i)])
                translate([disk_d / 2 - 0.5, -tab_w / 2, 0])
                    cube([body_od / 2 - (disk_d / 2 - 0.5) - 0.3, tab_w, tab_len]);
    }
}

// ===========================================================================
// RETAINER — flat capture ring; press-fits into the body base, traps the flange.
// ===========================================================================
module retainer() {
    difference() {
        cylinder(d = retainer_od, h = retainer_thickness);
        translate([0, 0, -0.01]) cylinder(d = retainer_id, h = retainer_thickness + 0.02);
        // 45-deg lead-in chamfers both bore edges
        cylinder(d1 = retainer_id + 2.0, d2 = retainer_id, h = 1.0);
        translate([0, 0, retainer_thickness - 1.0])
            cylinder(d1 = retainer_id, d2 = retainer_id + 2.0, h = 1.01);
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
        translate([disk_d / 2 - 0.5, -tab_w / 2, 0])
            cube([body_od / 2 - (disk_d / 2 - 0.5) - 0.3, tab_w, tab_len]);
    }
}

// ===========================================================================
// Boolean thread-mate proofs (ci.fitchecks — never printed). Single-start, so
// the interfering control is a HALF-lead (180 deg) rotation, not 90.
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

// ===========================================================================
// Assembly preview + section (never the deliverable — parts print separately)
// ===========================================================================
module assembly() {
    // $t-driven position when animating (0->1->0), else the static preview position
    pos = animate ? (0.5 - 0.5 * cos(360 * $t)) : elevator_pos;
    z_nut = z_thread_start + pos * pop_up;
    lid_on = !animate && pos < 0.5;
    body();
    screw_knob_use();
    color("#c9c9cf") translate([0, 0, z_nut]) elevator();
    translate([0, 0, z_retainer_bot]) retainer();
    // ghost rolls (preview only) — rise with the elevator
    for (i = [0 : n_cups - 1])
        rotate([0, 0, cup_a(i)]) translate([r_cup, 0, z_nut + elevator_plate_t])
            color("#e8c39a") cylinder(d = roll_d, h = roll_len);
    if (lid_on) {
        // closed: lid screwed onto the top neck (mouth down)
        lid_h = lid_cap_t + lid_lead_in + lid_engage + 1.0;
        translate([0, 0, z_rim - lid_lead_in + lid_h]) rotate([180, 0, 0]) lid();
    } else {
        // presenting: lid removed, set beside the base (shows the hex cap nut)
        translate([body_od / 2 + lid_af / 2 + 14, 0, 0]) lid();
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
else if (part == "screw-knob") screw_knob();
else if (part == "elevator") elevator();
else if (part == "retainer") retainer();
else if (part == "thread-coupon") thread_coupon();
else if (part == "tab-fit-coupon") tab_fit_coupon();
else if (part == "fit-mate") fit_mate();
else if (part == "fit-mate-ctrl") fit_mate(180);
else if (part == "lid-fit-mate") lid_fit_mate();
else if (part == "lid-fit-mate-ctrl") lid_fit_mate(180);
else if (part == "cutaway") cutaway();
else assembly();
