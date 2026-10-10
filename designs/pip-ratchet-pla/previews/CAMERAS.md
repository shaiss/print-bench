# pip-ratchet-pla — frozen preview cameras

Cameras are frozen once reviewed: a new region gets a new entry here, never a
reframe of an existing one. Re-render with
`./scripts/render.sh pip-ratchet-pla --previews`.

The framing vocabulary is the parent's so the two pages read as siblings
(`designs/pip-ratchet/previews/CAMERAS.md`); `pawl-close` is that camera
byte-for-byte — compare this page's thinner beam band against the parent's
published shot.

- `contact-sheet` — the 4-view sheet (iso / top / front / bottom-iso); the
  bottom-iso quadrant is the overhang/bed-contact view. Same as-printed pose
  as the parent (identical except the beam band): base flat on z = 0, 134
  facets of bed contact, no supports.
- `pawl-close` — one pawl up close: the **1.0 mm** PLA beam band outside the
  tooth tips (the parent's PETG shot shows 1.2 — the delta this design is),
  the hook nose dropping between two teeth, and the frame block burying the
  beam root. Camera identical to the parent's `pawl-close` entry so the two
  images compare directly.
- `coupon` — the print-this-first coupon (rack strip + one PLA-section pawl
  in its channel): the artifact the README's qualification section sends you
  to print before the wheel. Look-at is the coupon's measured bbox center
  (74 mm strip, x centered ≈ 9). Framing was pixel-verified on the render,
  not eyeballed: the strip spans ~1137 px of the 1400 px frame with ≥ 105 px
  of clear margin on both sides (d=110 crops the far end of the strip, d=150
  leaves only 62 px — both caught in the pre-freeze framing pass); at that
  scale the 2.4 mm tooth pitch and the 0.85 mm channel gap both read clearly.
