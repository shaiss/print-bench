# Camera descriptions

Per-shot descriptions for `cameras.conf` (the freeze convention: a camera is
fixed once reviewed; a new region gets a new line).

- **contact-sheet** — the production pivot, 2×2 iso / top / front /
  bottom-iso. The bottom-iso is the print-orientation proof: the whole part is
  one bed-plane silhouette extruded to `w` (8 mm), so it lies flat with zero
  overhangs and no supports.
- **top** — plan view of the whole part. Read it as the mechanism diagram: the
  two beams cross at mid-span and weld where they meet; the frame arc
  (180° side) and the stage arc (0° side) share the open virtual center; the
  grip tabs point +x (stage, with the raised finger pad) and −x (frame); the
  four pockets flanking the crossing stay open.
- **crossing** — close plan view of the weld: both beams fused at the origin,
  the root fillets where each beam meets its arc, and the open center the
  arcs deliberately leave clear.
- **coupon** — the print-this-first strip (`cross-axis-flexure-pivot-coupon.scad`),
  two rows of single-beam specimens: row 0 is the t ladder **0.6 / 0.8 / 1.0**
  (0.8 = the production beam), row 1 two identical production-t twins labelled
  **PETG** and **PLA**, so the material ranking is measured, not assumed. Tilted
  (rx=55, rz=25), not plan: OpenSCAD shades by surface normal, and an embossed
  label's readable top is parallel to the pad it sits on — same shade — so only
  the thin dark side walls separate the letters. At this tilt the two rows
  overlap in projection (that is the price of giving the walls any contrast);
  the shot proves layout: five independent specimens, all labels on their pads,
  nothing fused. The letterforms themselves are the **coupon-label** line below.
- **coupon-label** — one specimen's +x grip close up (dist=45, ~40 px/mm): the
  embossed "0.6" at the scale where its side walls resolve and the label reads
  as raised letterforms — verified by read-back, not assumed. This is the
  legibility proof the wide coupon shot cannot be.
