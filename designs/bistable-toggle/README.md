# bistable-toggle

A monolithic **bistable switch**: a pre-buckled arch with two stable states
(bowed up / bowed down) separated by a negative-stiffness region. Push the centre
nub through flat and it snaps to the other state and *stays* there — power is only
needed to switch, never to hold. Dimensioned from feel targets, not by eye: a
**3 N fingertip snap** with **4 mm of travel** (PETG), solved back to geometry
from published fixed–fixed-arch constants. A worked example of the bistable /
constant-force family (`docs/advanced-techniques.md`, Domain 1).

![Studio product shot of the red 3D-printed bistable-toggle](previews/hero.png)

![4-view contact sheet](previews/contact-sheet.png)

## What you get

- `bistable-toggle` — one flat part, ≈ 94 × 18 × 6 mm. The arch snaps inside a
  rigid stop cage (lid above, base bar below, rails flanking the nub) that
  absorbs over-travel and sideways shoves, so the flexure only ever feels the
  motion it was solved for. Use it as a latch, a valve actuator, or a tactile
  toggle that holds state with zero power.
- `bistable-toggle-coupon` — **print this first**: a 4-cell strip sweeping the
  bistability threshold on *your* printer (below).

![Coupon strip: four cells, bistability dying left to right](previews/coupon.png)

## Print settings

- **Material:** PETG / PP / nylon (live flexure). **Not PLA.**
- **Layer height:** 0.2 mm
- **Infill:** 100 % / high perimeters
- **Supports:** none — everything, the stop cage included, is pure profile and
  prints flat face-down. Keep auto-supports **off**; the mechanism needs none
  and painted ones would weld it.
- **Orientation:** flat, as modelled — the arch snaps in the layer plane, so
  bending stress runs across roads within a layer, not between them
- **Plate:** textured PEI if you have it — PETG over-welds on smooth, and the
  moving clearances touch the bed (next line)
- **First layer:** enable elephant-foot compensation. The 0.4 mm nub→lid slot
  runs the full height *including layer 1*, where squish can pinch it to a
  hairline web — expect to shear one thin web on the very first snap (every
  coupon cell has the same slot, so the strip shows you the feel first)
- **Seam:** Back (cosmetic — nothing mates on a perimeter)

The 0.82 mm arch beam prints as two clean perimeters at a 0.4 mm nozzle. If the
first snap feels dead or the "2.5" coupon cell only springs back, your material
landed outside the solve — calibrate with the coupon before blaming the part.

## How it's dimensioned

Pick the feel you want, the geometry follows: `h = u_tr/1.98` and
`l = (1486.57·E·I·h/f_s)^(1/3)` with `I = w·t³/12`. The defaults invert to
`f_s ≈ 3 N`, `u_tr ≈ 4 mm` (echoed at render, asserted against the targets).
Bistability requires `mid_rise/beam_t ≳ 2.3` — below that it's just a spring,
and the design refuses to build it. The full solve chain is in `NOTES.md`.

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `target_fs` | 3 N | target switch force — the solve derives `span` from it |
| `target_utr` | 4 mm | target centre travel — the solve derives `mid_rise` from it |
| `E` | 2000 MPa | Young's modulus (PETG datum) — scale to your measured snap |
| `mid_rise` | 2.02 mm | arch rise `h` (derived from `target_utr`) |
| `beam_t` | 0.82 mm | arch thickness `t` — window [0.8, 0.878]: 0.8 is the two-perimeter floor, 0.878 the bistability cap |
| `span` | ≈ 82 mm | clamped span `l` (derived from `target_fs`) |
| `width` | 6 mm | out-of-plane width = print height |
| `stop_gap` | 0.4 mm | travel past a stable state before a hard stop bites |

Bistability holds while `mid_rise/beam_t ≥ 2.3`. All parameters are at the top of
`bistable-toggle.scad`; override with `-D 'target_fs=2.5'` and the derived
dimensions follow.

## Print this first: the coupon

`bistable-toggle-coupon.scad` prints four small cells labelled **3 / 2.5 / 2 /
1.5** — their `mid_rise/beam_t` ratios at the production thickness. Left to
right: bistable, bistable (the production ratio), monostable, monostable. Feel
the snap die between 2.5 and 2 — that is your printer landing where the solve
assumed. If 2.5 only springs back for you, raise `mid_rise`; if the production
snap is too fierce, lower it. Steps in `NOTES.md` → "Print this first".

![AI-styled scene: bistable-toggle staged in a real-world setting](previews/lifestyle-scene.png)

*AI-styled scene — generated impression for illustration only; geometry is approximate and may not exactly match the printed part. See the studio render and contact sheet above, and the STL, for the true shape.*
