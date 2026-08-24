# support-free-bracket

A wall shelf bracket — 80 × 50 plate on two M5 screws, 60 mm arm — designed so
it prints with **zero support material**. It's a worked example of *designing
around supports* (`docs/advanced-techniques.md`, Domain 2): every feature that
would normally force supports has been reshaped so it doesn't.

![Studio product shot of the 3D-printed support-free-bracket](previews/hero.png)

![4-view contact sheet](previews/contact-sheet.png)

## What you get

- `support-free-bracket` — one part, ≈ 80 × 66 × 50 mm as printed (80 × 60 × 50
  in use). Wall plate with two M5 teardrop bores, shelf arm, and a vaulted
  brace closing the cavity under the arm.

## Why it needs no supports

![Side elevation: the 42-degree vault](previews/side-vault.png)

The cavity under the arm is closed by a diagonal brace whose inner face is a
**vault at 42° from vertical** — never a flat ceiling, which would print as an
unsupported bridge roof. Every layer of the vault rests on the one below it.

![Front view: both teardrop bores](previews/front-bores.png)

The M5 bores run horizontal in the print frame, so they are **teardrops** — a
45° peaked roof self-supports where a round bore's roof would droop.

![Bottom view: the proof shot](previews/bottom-iso.png)

Seen from below: the vault ceiling slopes over the open cavity and there is no
flat downward-facing surface anywhere. Print it with supports turned **off**.

## Print settings

- **Material:** any (PLA/PETG both fine — no living flex here)
- **Layer height:** 0.2 mm
- **Infill:** 20–40 %
- **Supports:** none — that's the whole point
- **Orientation:** as modelled — arm flat on the bed. To use, flip the print
  180° so the plate is against the wall and the arm is on top; the shelf board
  rests on the arm's smooth first-layer face.
- **Perimeters:** 3 (the 6 mm walls are three perimeters plus infill)

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `plate_w` | 80 mm | plate width, across the wall |
| `plate_h` | 50 mm | plate height up the wall |
| `plate_t` | 6 mm | plate thickness |
| `screw` | M5 | fastener size (M3–M6; bores are clearance holes) |
| `bore_inset_x` | 20 mm | bore inset from the plate ends |
| `bore_z_lo` / `bore_z_hi` | 10 / 28 mm | bore heights (staggered for pull-out resistance) |
| `arm_d` | 60 mm | arm depth out from the wall |
| `arm_t` | 6 mm | arm thickness — the shelf rests on this face |
| `vault_deg` | 42° | vault ceiling angle from vertical (guarded ≤ 45° — above that it needs supports) |
| `bottom_chamfer` | 0.8 mm | 45° chamfer on bed-contact edges |

All parameters are at the top of `support-free-bracket.scad`, grouped in
Customizer sections; override on the command line with `-D 'arm_d=80'`.

## Assembly & use

Fasten the plate to wall studs or anchors with two M5 screws (socket heads
land inside the cavity — no counterbore needed), flip-mounted with the arm on
top, and rest the shelf board on the arm. Sized as a reference design for a
~1 kg-per-bracket shelf; scale `plate_w`/`arm_d` for heavier loads and keep
`vault_deg` at or below 45° — the guard refuses anything steeper because it
would break the no-supports promise.
