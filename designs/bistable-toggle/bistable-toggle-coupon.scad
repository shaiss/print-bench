// Print this first. A four-cell strip of the production toggle at l = 35,
// sweeping mid_rise/beam_t across the bistability threshold (t = 0.82 = the
// production beam). Cells "3.0" and "2.5" (the production ratio) should snap
// and hold both states; "2.0" and "1.5" are deliberately monostable — the
// negative controls. Feel the snap die as the ratio falls: if "2.5" only
// springs back on YOUR printer, raise mid_rise (or accept a monostable
// button); if the snap is too fierce, lower it. See NOTES.md "Print this
// first". Overrides sit below the include (OpenSCAD resolves top-level
// variables last-assignment-wins).
include <bistable-toggle.scad>
part = "sweep";
