// Print this first. A short version of the production collet grabber — nothing
// copied, just the entry design with shorter fingers — to tune the collar
// clearance `xy_tol` for your printer fast. Print it, slide the collar; if it's
// fused, raise `xy_tol` by 0.05 and reprint; if it's sloppy, lower it. See
// NOTES.md "Print this first". Overrides sit below the include (OpenSCAD
// resolves top-level variables last-assignment-wins).
include <compliant-gripper.scad>
finger_h = 15;
collar_h = 6;
