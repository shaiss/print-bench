<!--
FIELD-TEST convention (issue #101) — the print-feedback half of the loop.

The digital gates prove a design is printable in theory; the coupons exist
because reality disagrees per printer. A field-test entry captures that reality
in a machine-readable-ish, human-reviewed place, so the NEXT design (or the
next print of this one) starts from measured tolerances instead of a generic
default.

Convention:
  * A design records real prints under a "## Field test log" section in its
    NOTES.md. Keep that section LAST in the file — entries are appended to the
    end (scripts/field-test.sh, and the "Log a print result" GitHub Action,
    both append there).
  * One entry per real print. Newest at the bottom (chronological).
  * When a measured deviation is worth carrying across designs (a real fit
    clearance, say), note it under "Carry forward" and copy it into
    printer.conf so opted-in designs pick it up.

This is a convention plus a template, not a gate: nothing content-judges an
entry (readme-gate/docs-check stay presence-only). Copy the block below.
-->

## Field test log

_Real prints of this design, newest at the bottom. See templates/FIELD-TEST.md
and docs/print-feedback.md for the convention._

### YYYY-MM-DD — <printer>
- **Printed from:** <design version / commit this print came from, e.g. v0.2>
- **Part(s):** <what was printed>
- **Slicer settings:** <profile · layer height · nozzle · material · infill · supports>
- **Result:** <what fit, what didn't, print-quality notes>
- **Measured deviations:** <e.g. slot 0.15 mm tight; M3 hole +0.1 mm loose>
- **Carry forward:** <printer.conf value(s) to update, or "none">
