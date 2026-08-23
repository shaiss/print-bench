# Alcove rod socket

A parametric, two-part screw-together end socket for a 40 mm curtain or
closet rod that spans a recess or alcove. A wall boss screws flat to each
facing wall; the rod's ends plug into knurled collars that hand-thread onto
the bosses. Curtains down for washing = unthread two collars, no tools.

> **v0.2** — ships the separable multi-object plate deliverable. v1 (#361)
> printed **fused** in the field (a single STL of the two parts slices as one
> welded body); v0.2 fixes the packaging, geometry unchanged. See *Deliverable*
> below and the field test log in NOTES.md.

![Product shot](previews/product-hero.png)

![4-view contact sheet](previews/contact-sheet.png)

![Section through the seated socket](previews/cutaway.png)

## What you get

Printed **in pairs** (one holder per wall, one pair per rod):

- `boss` — the wall plate: Ø58.8 × 18 mm disc with a countersunk M5 screw
  hole and an external printed thread (an optional second off-axis screw
  setting, `screw_count=2`, grows the flange for heavier installs).
- `collar` — the rod socket: Ø54 × 40.6 mm knurled tube, internal printed
  thread below, Ø40.6 rod bore above.
- `thread-coupon` / `bore-coupon` — the "print this first" fit checks (see
  Print settings).

**Deliverable — slice the plate, not a single STL.** `boss` and `collar` print
as separate parts, so the printable file is the multi-object 3MF plate
**`build/alcove-rod-socket-plate.3mf`** (`./scripts/plate.sh alcove-rod-socket`)
— the slicer imports it as two distinct objects. Do **not** export the two into
one STL: STL carries no object separation, so a slicer treats them as one fused
body and the print welds them together (that was v1's field-test failure — see
NOTES.md). Stacking the two on the bed to save space is fine; the 3MF keeps them
separate objects.

![The collar in its print orientation](previews/collar-print.png)

## Print settings

- **Material:** PLA is fine; PETG or ASA for a hot, sunny window.
- **Layer height:** 0.2 mm, 0.4 mm nozzle.
- **Perimeters:** 3 — the 3.2 mm walls carry the load.
- **Infill:** 20%.
- **Supports:** none needed anywhere, by design.
- **Bed adhesion:** enable a **brim** for the collar — its first layer is a thin
  annular rim, the part most prone to lifting; it helps the boss too. Cheap
  insurance against the first-layer detachment seen in the field (NOTES.md).
- **Orientation:** print every part as rendered — boss flange-down, collar
  rod-mouth-down (the internal thread prints at the top of the collar, never
  on the first layer).
- **Print order:** both coupons first, then tune (below), then a pair.

Measure your pole with calipers where it will sit and set `rod_d` to that
barrel reading — "40 mm" is sometimes the finial size, not the pole.

## Parameters

The ones you are most likely to touch (all in `alcove-rod-socket.scad`,
Customizer-grouped; override with `-D 'rod_d=38.5'`):

| Parameter | Default | What it does |
|---|---|---|
| `rod_d` | 40.0 mm | rod barrel outer Ø where it sits in the socket |
| `rod_clearance` | 0.6 mm | diametral slip added to `rod_d` → socket bore |
| `engagement_depth` | 28 mm | how deep the rod plugs in; print the far holder shallower (e.g. 12) for the push-in-deep / drop-in-shallow install |
| `thread_tol` | 0.3 mm | radial thread fit — dial on the thread coupon |
| `screw_count` | 1 | 1 central M5, or 2 off-axis (grows the flange; stops boss spin) |
| `knurl_flutes` | 36 | grip flute count — guarded to keep flutes printable |
| `wall` | 3.2 mm | structural wall everywhere |

## Assembly & use

1. Screw a boss to each facing wall, countersunk M5 head flush in the neck
   (use a drywall anchor appropriate for the wall).
2. Slide the collars over the rod before hanging it — one at each end.
3. Thread each collar onto its boss until the rim seats on the plate. For a
   rigid rod between two fixed walls: set one holder's `engagement_depth`
   deep and the other shallow (e.g. 12 mm) — push into the deep side, drop
   the shallow end in, tighten both collars.
4. To wash the curtains: unthread the collars (~1¼ turns each — 2-start
   thread) and lift the rod out. No tools.

If a fit is off, don't resize the parts — reprint the coupon and move the
tolerance (`thread_tol`, `rod_clearance`) in 0.05–0.1 mm steps; see
"Print this first" in NOTES.md, including a one-print tolerance sweep
(`./scripts/render.sh alcove-rod-socket --sweep thread_tol=0.2:0.4:0.05`).
