# pip-ratchet — frozen preview cameras

Cameras are frozen once reviewed: a new region gets a new entry here, never a
reframe of an existing one. Re-render with
`./scripts/render.sh pip-ratchet --previews`.

- `contact-sheet` — the 4-view sheet (iso / top / front / bottom-iso); the
  bottom-iso quadrant is the overhang/bed-contact view. This is the as-printed
  pose CI slices — the mechanism has no other pose.
- `pawl-close` — one pawl up close: the constant-thickness beam band outside
  the tooth tips, the hook nose dropping between two teeth, and the frame
  block burying the beam root. Neighbouring teeth stay in frame for scale.
  Look-at on the beam mid-span (≈ −14°, r ≈ 28.8), tilted 55° so the
  beam-to-tip radial gap reads, spun 25° to center the nose-to-block
  assembly, pulled back far enough that the root block's full extent stays
  in frame.
