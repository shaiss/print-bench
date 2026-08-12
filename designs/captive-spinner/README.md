# captive-spinner

A one-piece fidget spinner that comes off the print bed already assembled and
spinning — no supports, no assembly. A rotor is captured on a fixed post under a
45° cone cap; the first spin shears the microscopic print-in-place fusion and
then it runs free. A worked example of print-in-place kinematics
(`docs/advanced-techniques.md`, Domain 3).

![4-view contact sheet](previews/contact-sheet.png)

## What you get

- `captive-spinner` — one print, ≈ 44 mm across × 16 mm tall, made of two
  separate bodies (fixed base+post+cap, and the free rotor).

## Print settings

- **Material:** PLA is fine
- **Layer height:** 0.2 mm (the clearances are quantized to it — see below)
- **Infill:** 15–20 %
- **Supports:** none needed
- **Orientation:** as modelled (base on the bed, axis vertical)
- **First use:** give the rotor a firm first spin to break it free.

The two gaps are deliberately **different numbers** because different physics
govern them: the radial bore↔post gap is spread-limited so it's tight
(`xy_tol = 0.2`), while the axial float below/above the rotor is sag-limited and
snapped to whole layers (`z_layers · layer_h = 0.4`). A single global tolerance
is the classic print-in-place bug.

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `xy_tol` | 0.2 mm | radial rotor↔post clearance (spread-limited) |
| `z_layers` | 2 | axial float in whole layers (sag-limited) |
| `rotor_or` | 18 mm | rotor outer radius |
| `cap_lip` | 3 mm | how far the cap overhangs the bore (capture) |
| `scallops` | 6 | finger grip notches |

All parameters are at the top of `captive-spinner.scad`; override with
`-D 'xy_tol=0.25'`. If the rotor won't free, print a copy with `xy_tol` +0.05.
