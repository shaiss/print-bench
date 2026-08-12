# support-free-bracket

A small wall/desk bracket that holds a rod (up to ~10 mm) and mounts with two
screws — designed so it prints with **zero support material**. It's a worked
example of *designing around supports*: every feature that would normally need
support has been reshaped so it doesn't (`docs/advanced-techniques.md`, Domain 2).

![4-view contact sheet](previews/contact-sheet.png)

## What you get

- `support-free-bracket` — one part, ≈ 46 × 40 × 39 mm. A back plate with two
  countersunk mount holes and an arm carrying a horizontal rod bore.

## Print settings

- **Material:** any (PLA/PETG fine — no live flex here)
- **Layer height:** 0.2 mm
- **Infill:** 20–40 %
- **Supports:** none needed — that's the whole point
- **Orientation:** as modelled (back plate flat on the bed). In use, rotate 90°
  so the plate is vertical against the wall.

Why it needs no supports: the horizontal rod bore is a **teardrop** (its 45°
peaked roof self-supports), the mount holes run along the build axis so their
countersinks open upward, and the arm meets the plate with a **45° gusset
chamfer** — never a bottom fillet, which would curl into an overhang.

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `bore_d` | 10 mm | rod bore diameter (teardrop) |
| `arm_t` | 16 mm | arm thickness — must exceed `bore_d + 2.4` (guarded) |
| `arm_h` | 34 mm | arm height above the plate |
| `screw` | M4 | mount screw size (M3/M4/M5) |
| `gusset` | 10 mm | 45° gusset run onto the plate |

All parameters are at the top of `support-free-bracket.scad`; override on the
command line with `-D 'bore_d=8'`.
