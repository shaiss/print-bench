// printability.scad — small FDM-focused helpers shared across designs.
// All dimensions in millimeters. Use from a design with:
//   use <../../lib/printability.scad>
// These are deliberately lightweight (no BOSL2 dependency, fast to render).
// For fillets, real threads, attachments, etc. use BOSL2: include <BOSL2/std.scad>

// ---------------------------------------------------------------------------
// Metric fastener presets
// ---------------------------------------------------------------------------

// Clearance hole diameter ("normal" fit, ISO 273) — already includes clearance,
// no extra tolerance needed for FDM at typical accuracy.
function screw_clearance_d(size) =
    size == "M2"   ? 2.4 :
    size == "M2.5" ? 2.9 :
    size == "M3"   ? 3.4 :
    size == "M4"   ? 4.5 :
    size == "M5"   ? 5.5 :
    size == "M6"   ? 6.6 :
    assert(false, str("unknown screw size: ", size));

// Socket-cap head: [head diameter incl. 0.5 clearance, head height]
function socket_head(size) =
    size == "M2"   ? [4.3, 2.0] :
    size == "M2.5" ? [5.0, 2.5] :
    size == "M3"   ? [6.0, 3.0] :
    size == "M4"   ? [7.5, 4.0] :
    size == "M5"   ? [9.0, 5.0] :
    size == "M6"   ? [10.5, 6.0] :
    assert(false, str("unknown screw size: ", size));

// Heat-set insert hole diameter (typical brass inserts for plastic)
function heatset_hole_d(size) =
    size == "M2"   ? 3.2 :
    size == "M2.5" ? 3.6 :
    size == "M3"   ? 4.0 :
    size == "M4"   ? 5.6 :
    size == "M5"   ? 6.4 :
    assert(false, str("unknown insert size: ", size));

// ---------------------------------------------------------------------------
// Cutters (use inside difference()). All extend 0.01 past faces to avoid
// zero-thickness walls / z-fighting.
// ---------------------------------------------------------------------------

// Vertical clearance hole for a metric screw, optionally with a recessed head.
// l      — material thickness the hole passes through (hole spans z = 0..l)
// head   — "none" | "socket" (counterbore) | "countersunk" (90° csk)
// head_depth — counterbore depth; default = head height preset
module screw_hole(size = "M3", l = 10, head = "none", head_depth = undef) {
    d = screw_clearance_d(size);
    translate([0, 0, -0.01]) cylinder(d = d, h = l + 0.02);
    if (head == "socket") {
        hd = socket_head(size);
        depth = head_depth == undef ? hd[1] : head_depth;
        translate([0, 0, l - depth]) cylinder(d = hd[0], h = depth + 0.01);
    } else if (head == "countersunk") {
        ch = d; // 90° countersink: depth == radius growth
        translate([0, 0, l - ch]) cylinder(d1 = d, d2 = d + 2 * ch, h = ch + 0.01);
    }
}

// Teardrop-profile horizontal hole: prints without supports when the axis is
// horizontal. Axis along Y; the point of the teardrop faces +Z — pinned by
// lib/printability-mates.conf's independently-authored gauge plug, so a
// rotation-sign flip fails mate-check.sh instead of shipping silently
// (issue #398: the point faced -Z for years and nothing measured it).
module teardrop_hole(d = 5, l = 10) {
    rotate([90, 0, 0]) linear_extrude(l, center = true) {
        circle(d = d);
        // 45° roof so the top bridges cleanly
        intersection() {
            rotate(45) square(d * 0.72, center = false);
            circle(d = d * 1.6);
        }
    }
}

// ---------------------------------------------------------------------------
// Solids
// ---------------------------------------------------------------------------

// Boss for a heat-set insert: solid cylinder with the insert hole pre-cut.
// h — boss height; insert hole depth = insert length + 1 (pass insert_l).
module heatset_boss(size = "M3", h = 8, wall = 2.4, insert_l = 5) {
    hole_d = heatset_hole_d(size);
    difference() {
        cylinder(d = hole_d + 2 * wall, h = h);
        translate([0, 0, h - insert_l - 1]) cylinder(d = hole_d, h = insert_l + 1.01);
    }
}

// Cylinder with 45° chamfers so it prints cleanly and assembles easily.
// chamfer1/chamfer2 — bottom/top chamfer size (0 to disable either).
module chamfered_cylinder(d = 10, h = 10, chamfer1 = 0.6, chamfer2 = 0.6) {
    union() {
        if (chamfer1 > 0)
            cylinder(d1 = d - 2 * chamfer1, d2 = d, h = chamfer1);
        translate([0, 0, chamfer1])
            cylinder(d = d, h = h - chamfer1 - chamfer2);
        if (chamfer2 > 0)
            translate([0, 0, h - chamfer2])
                cylinder(d1 = d, d2 = d - 2 * chamfer2, h = chamfer2);
    }
}

// Box with rounded vertical edges and a chamfered bottom edge — the standard
// "sits nicely on the print bed" enclosure base shape.
module rounded_box(size = [40, 30, 15], r = 3, bottom_chamfer = 0.6) {
    hull() {
        for (x = [r, size[0] - r], y = [r, size[1] - r]) {
            translate([x, y, bottom_chamfer])
                cylinder(r = r, h = size[2] - bottom_chamfer);
            if (bottom_chamfer > 0)
                translate([x, y, 0])
                    cylinder(r1 = r - bottom_chamfer, r2 = r, h = bottom_chamfer);
        }
    }
}
