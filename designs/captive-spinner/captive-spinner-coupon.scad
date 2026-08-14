// Print this first. A small version of the production spinner — nothing copied,
// just the entry design scaled down — to tune the radial clearance `xy_tol` for
// your printer fast. Print it and give the rotor a firm spin; if it's fused,
// raise `xy_tol` by 0.05 and reprint; if it rattles, lower it. See NOTES.md
// "Print this first". Overrides sit below the include (OpenSCAD resolves
// top-level variables last-assignment-wins).
include <captive-spinner.scad>
rotor_or = 12;
base_r   = 15;
rotor_h  = 7;
