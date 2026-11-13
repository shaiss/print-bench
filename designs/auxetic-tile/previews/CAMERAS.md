# Preview shots — fixed cameras

The camera numbers live in [`cameras.conf`](cameras.conf) (format documented
in `scripts/render.sh`); regenerate every shot with:

```bash
./scripts/render.sh auxetic-tile --previews
```

Cameras are FIXED across review rounds so before/after comparisons align; a
new region gets a new `cameras.conf` line, never a moved camera.

## What each shot shows

- **contact-sheet.png** — 4-view overview of the deliverable `tile` part
  (iso / top / front / bottom-iso). Bottom-iso is the overhang / bed-contact
  check; the lattice is flat on the bed by construction.
- **tile-iso.png** — whole tile, 3/4: auxetic patch, conventional contrast
  column on the left, embossed callout on the right.
- **layout-top.png** — orthographic top: re-entrant cells readable next to
  the contrast column and the callout strip.
- **cell-close.png** — close on one re-entrant cell so the inward necks
  resolve.
- **coupon.png** — the hand-stretch coupon (`auxetic-tile-coupon.scad`) with
  grip tabs on the ends only (free-sided rib network), as printed.

Frozen camera numbers are unchanged from Round 0; the `render` opt was
added so CGAL evaluates the lattice booleans (OpenCSG under-draws them).
