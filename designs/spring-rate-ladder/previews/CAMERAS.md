# Preview shots — fixed cameras

The camera numbers live in [`cameras.conf`](cameras.conf) (format documented
in `scripts/render.sh`); regenerate every shot with:

```bash
./scripts/render.sh spring-rate-ladder --previews
```

Cameras are FIXED across review rounds so before/after comparisons align; a
new region gets a new `cameras.conf` line, never a moved camera.

## What each shot shows

- **contact-sheet.png** — 4-view overview of the deliverable `ladder` part
  (iso / top / front / bottom-iso). The bottom-iso quadrant is the
  overhang/bed-contact view: the springs print axis-vertical like a screw
  thread (lead ≈ 5–10°), so every wrap deposits on the one below.
- **ladder-iso.png** — the whole ladder, 3/4 view: three stations on the one
  baseplate, embossed predictions facing the camera.
- **layout-top.png** — orthographic top: the embossed table reads as a
  table — `N=4/6/8` rows with `PLA`/`PETG` rates and the
  `k = G d^4 / 8 N D^3` footer along the front edge.
- **station-close.png** — close on the N=4 station (x = −36): single coils
  resolvable, the closed end coils at top and bottom, and the station's
  label row legible.
- **coupon.png** — the measurement rig (`spring-rate-ladder-coupon.scad`):
  pad, guide post and its N=6 spring, as printed (pad down).
- **cap.png** — the guided cap in its **print pose** (disc down, skirt up —
  `part="cap"` renders `cap_print()`), which is why it appears flipped
  relative to its working pose over the coupon.
