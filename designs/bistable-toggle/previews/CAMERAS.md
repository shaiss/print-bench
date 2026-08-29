# Camera descriptions

Per-shot descriptions for `cameras.conf` (the freeze convention: a camera is
fixed once reviewed; a new region gets a new line).

- **contact-sheet** — the production toggle, 2×2 iso / top / front /
  bottom-iso. The bottom-iso is the print-orientation proof: flat bed contact,
  no supports.
- **coupon** — the print-this-first strip (`bistable-toggle-coupon.scad`),
  four cells sweeping `mid_rise/beam_t` 3 / 2.5 / 2 / 1.5 at `t = 0.82`.
  Read left to right: bistable, bistable (production ratio), monostable,
  monostable — the snap dying is the calibration signal.
- **coupon-close** — the strip's label row, close and near-top: all four
  base bars with their through-cut **3 / 2.5 / 2 / 1.5** digits legible,
  decimal points included. Added round 6 (a new line, never a reframe):
  the coupon shot frames the whole strip, so its 3.2 mm labels land on too
  few pixels to back the "feel the snap die between 2.5 and 2" instruction.
