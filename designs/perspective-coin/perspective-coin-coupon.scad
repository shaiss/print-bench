// Print this first. A small flipper — the production ring, sockets and
// diamond axles at a 24 mm coin — to tune `pivot_clear` for your printer
// fast. Print it, then flip the disc firmly: fused -> raise `pivot_clear`
// by 0.05 and reprint; rattles on its axles -> lower it. See NOTES.md
// "Print this first". Nothing copied: include + override only (OpenSCAD
// resolves top-level variables last-assignment-wins).
include <perspective-coin.scad>
coin_d  = 24;
engrave = false;   // the legends don't scale down to a coupon
reed_n  = 0;
ring_w  = 5;
