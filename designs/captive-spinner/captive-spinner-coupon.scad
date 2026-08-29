// Print this first. A small version of the production spinner — nothing copied,
// the entry design included and proportioned down — to tune the radial
// clearance for your printer fast. It keeps the SAME process constants
// (nozzle_d, line_w, k_xy, layer_h), so the xy_tol it prints is the xy_tol the
// full-size part gets: the wall-to-wall spread a printer lays down does not
// care about the post's radius. Print it and give the rotor a firm spin; if
// it's fused, raise k_xy by 0.05 and reprint; if it rattles, lower it. See
// NOTES.md "Print this first". Overrides sit below the include (OpenSCAD
// resolves top-level variables last-assignment-wins).
include <captive-spinner.scad>
post_r   = 7;
rotor_or = 11;
rotor_h  = 7;
base_r   = 14;
scallop_r = 2;   // rim wall is thinner at this size — keep >= 1.8 mm of ring
