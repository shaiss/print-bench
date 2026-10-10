// Print this first. A 3-link stub of the production chain — nothing copied,
// just the entry design with a shorter run — to tune `clear_xy` for your
// printer before committing to the full 11-link bed. Print it flat as laid
// out, then flex each joint once to shear the break-in fusion; every joint
// should swing to its stops and back. If any joint binds or a stub snaps
// out, raise `clear_xy` by 0.05 and reprint (clear_z follows it in whole
// layers). See NOTES.md "Print this first". Overrides sit below the include:
// OpenSCAD resolves top-level variables last-assignment-wins, so main()
// renders these values.
include <pip-cable-chain.scad>
links     = 3;
end_tabs  = false;
