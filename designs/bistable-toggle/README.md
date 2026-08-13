# bistable-toggle

A monolithic **bistable switch**: a pre-buckled arch with two stable states
(bowed up / bowed down) separated by a negative-stiffness region. Push the centre
nub through flat and it snaps to the other state and *stays* there — power is only
needed to switch, never to hold. A worked example of the bistable / constant-force
family (`docs/advanced-techniques.md`, Domain 1).

![Studio product shot of the red 3D-printed bistable-toggle](previews/hero.png)

![AI-styled scene: bistable-toggle staged in a real-world setting](previews/lifestyle-scene.png)

*AI-generated impression for general illustration only — geometry is approximate and may not exactly match the printed part; see the studio render above and the STL for the true shape.*

![4-view contact sheet](previews/contact-sheet.png)

## What you get

- `bistable-toggle` — one flat part, ≈ 62 × 24 × 9 mm, with an open frame the
  arch snaps down into. Use it as a latch, a valve actuator, or a tactile toggle.

## Print settings

- **Material:** PETG / PP / nylon (live flexure). **Not PLA.**
- **Layer height:** 0.2 mm
- **Infill:** 100 % / high perimeters
- **Supports:** none
- **Orientation:** flat, as modelled — the arch snaps in the layer plane.

The arch is dimensioned from published constants: it's the fixed–fixed first
mode `yc(x) = h·(1 − cos(2πx/l))/2`, with centre travel `≈ 1.98·h` (echoed at
render). Bistability requires `mid_rise/beam_t ≳ 2.3` — below that it's just a
spring, and the design refuses it.

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `mid_rise` | 6 mm | arch rise `h` — firmer snap and more travel when larger |
| `beam_t` | 1.6 mm | arch thickness `t` — thin = easy snap, low stress |
| `span` | 50 mm | clamped span `l` |
| `width` | 9 mm | out-of-plane width |

Bistability holds while `mid_rise/beam_t ≥ 2.3`. All parameters are at the top of
`bistable-toggle.scad`; override with `-D 'mid_rise=7'`.
