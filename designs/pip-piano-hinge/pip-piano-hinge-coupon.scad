// Print this first. A fast 3-knuckle stub of the production hinge — nothing
// copied, just the entry design with a shorter length — to tune `clear` for
// your printer before committing to a full-length hinge. Print it, work the
// knuckles free; if any binds, raise `clear` by 0.05 and reprint. See NOTES.md
// "Print this first". Overrides sit below the include: OpenSCAD resolves
// top-level variables last-assignment-wins, so main() renders these values.
include <pip-piano-hinge.scad>
hinge_len = 27;
knuckles  = 3;
leaf_w    = 12;
