// pip-ratchet-pla-coupon — print this first, IN PLA. The parent's coupon
// (a rack strip + one pawl on the shared production tooth/pawl profiles,
// nothing copied) with the beam re-sectioned for PLA: the single
// `pawl_t` override below mirrors pip-ratchet-pla.scad's #675 derivation —
// keep the two in sync (the wrapper cannot import the derivative's
// assignment without pasting the parent entry twice, which would
// double-draw; one mirrored constant is the smaller risk, and the sync is
// checked by eye against the echo in both files).
//
// WHAT TO TUNE / WHAT IT PROVES: in the parent this coupon only tunes feel
// (click force ~ t³); here it ALSO qualifies the material — PLA is ranked
// "unsuitable for a live flexure unless a coupon proves otherwise"
// (docs/advanced-techniques.md), so before printing the demonstrator you
// cycle this coupon to a click-count death and read the verdict against
// your target life (NOTES.md "Print this first", step 3). Breaking early
// is the coupon doing its job: it is the brief's "not viable" answer
// arriving before you spend the filament on the wheel.
//
// The sweep plate renders the neighbourhood if you want it:
//   ./scripts/render.sh pip-ratchet-pla --sweep pawl_t=0.9:1.5:0.1
include <../pip-ratchet/pip-ratchet-coupon.scad>
pawl_t = 1.0;   // the #675 PLA force-match, mirroring pip-ratchet-pla.scad
