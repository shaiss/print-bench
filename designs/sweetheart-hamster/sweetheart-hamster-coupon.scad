// Print this first. A smaller Sweetheart Hamster — same production modules, just
// scaled down so it prints fast — to tune the LIVING-HINGE web and the SEAM
// parting gap for your printer/material before committing to the full print.
// Flex the hinge a few times: PETG/PP fold for many cycles, PLA cracks (raise
// web_t or switch material). If the halves won't part, that's usually first-layer
// flare, not the gap: enable 0.2 mm elephant-foot compensation first; raise part_gap
// only if it still binds, by 0.1 mm (0.05 buys just 0.025/side, under the noise
// floor). Overrides sit below the include (last-assignment-wins).
// See NOTES.md "Print this first". Clearances (web_t, part_gap) are absolute, so
// shrinking S tests them at their true values.
include <sweetheart-hamster.scad>
S = 0.85;
nest_on = false;   // the coupon tests the hinge + seam, not the ring nest
