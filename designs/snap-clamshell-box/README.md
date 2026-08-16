# snap-clamshell-box

A small clamshell box that prints **flat and assembled in one piece**, folds
closed, and snaps shut — no supports, no fasteners, no assembly. It fuses two
independent compliant sub-mechanisms: a **living hinge** joins the two trays and a
**compliant snap latch** holds them closed (`docs/advanced-techniques.md`, Domain
1 flexures + Domain 2 orientation).

![Studio product shot of the amber 3D-printed snap-clamshell-box](previews/hero.png)

![AI-styled scene: snap-clamshell-box staged in a real-world setting](previews/lifestyle-scene.png)

*AI-generated impression for general illustration only — geometry is approximate and may not exactly match the printed part; see the studio render above and the STL for the true shape.*

![4-view contact sheet (printed flat)](previews/contact-sheet.png)

Closed and latched (preview pose):

![closed and latched](previews/closed-latched.png)

## What you get

- `snap-clamshell-box` — one flat print, ≈ 53 × 81 × 22 mm as printed (both trays
  open and flat, the latch strip standing proud of the rim); folds to a
  ≈ 53 × 43 × 26 mm closed box with two compartments. The closed interior clears
  ≈ 22.8 mm — enough to hold a pair of earbuds.

## Print settings

- **Material:** PETG / PP for the living hinge (it folds many times); PLA will
  crack at the hinge
- **Layer height:** 0.2 mm
- **Infill:** 20–30 %
- **Supports:** none needed
- **Orientation:** **flat, both trays open** (as modelled). Fold the lid 180° over
  the base after printing; the front tab snaps into the base window.

The two mechanisms: a thin **living-hinge web** across the spine (bends in the
layer plane), and a **tab-in-window snap** on the front whose halves are placed by
the 180° fold map (`tab_flat_z = 2·wall_h − win_z`) so they meet exactly when the
box closes.

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `inner_w` | 50 mm | inner tray width |
| `inner_d` | 34 mm | inner tray depth (each tray) |
| `wall_h` | 13 mm | wall height per tray (closed interior ≈ 2·(wall_h − floor_t)) |
| `hinge_t` | 0.6 mm | living-hinge web thickness (thin = folds easily; 0.4–1.0) |
| `hook` | 2.0 mm | latch tab protrusion (snap strength) |
| `latch_clr` | 2.0 mm | outward standoff of the latch strip so it clears the closed lid wall (≥ `wall_t` + a print clearance) |

All parameters are at the top of `snap-clamshell-box.scad`; override with
`-D 'inner_w=60'`. `demo_fold` is a preview pose only — print at 0.
