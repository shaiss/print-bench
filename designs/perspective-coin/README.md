# Perspective Coin

A two-sided pocket coin of the two engravings John Cena keeps on his watch —
**"COMPARISON IS THE THIEF OF JOY"** around a radiant sun on one face, for the
days you don't feel like enough, and **"MEMENTO MORI"** around an hourglass on
the other, for the days your head gets too big. Print the bare coin for your
pocket, or the **flipper**: a print-in-place keyring gimbal that holds the coin
on two tiny axles, so you flip it — literally — to the reminder you need.
A keeper of perspective, not time.

![Product shot](previews/hero.png)

![The MEMENTO MORI face](previews/memento.png)

![The flip](previews/flip.gif)

![4-view contact sheet](previews/contact-sheet.png)

## What you get

- `flipper` (default) — the coin captured in a keyring ring, printed as one
  piece: Ø55 × 6 mm plus the loop. No assembly; flip it firmly once to free
  the pivot.
- `coin` — the bare two-sided coin, Ø40 × 5 mm, reeded edge, chamfered rims.
- `perspective-coin-coupon` — a 24 mm pivot-tuning flipper. Print this first.

| Face A | Face B |
|---|---|
| ![JOY face](previews/face-a.png) | ![MEMENTO face](previews/face-b.png) |

## How the mechanism prints

The coin carries two diamond-section stub axles (45° cross-section — its own
overhang self-supports) that ride in **teardrop** sockets inside the ring, so
the socket roof never bridges. A 1.5 mm moat separates coin from ring
everywhere else; the only printed fusion is the thin axle/socket annulus, and
the first firm flip shears it. The engraved faces are in coin-flip alignment
about the pivot, so the back face reads upright after a flip.

![Pivot cutaway](previews/cutaway.png)

## Print settings

- **Material:** any rigid filament — PLA is the reference; gold silk PLA if
  you want it to look the part
- **Layer height:** 0.2 mm (the 0.6 mm engravings are exactly 3 layers)
- **Infill:** 15–25 % (it's a coin — top it up to 100 % if you want the heft)
- **Supports:** none needed — teardrop sockets and 45° axles by design
- **Orientation:** as modeled, flat on the bed; the flipper prints in place
- **Print order:** the coupon first — tune `pivot_clear` for your printer,
  then print the real thing

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `coin_d` | 40 mm | Coin diameter (legend artwork is tuned to 40) |
| `coin_t` | 5 mm | Coin thickness; the pivot axis sits at half of it |
| `pivot_clear` | 0.35 mm | **The tuned fit**: axle-to-socket clearance — tune on the coupon |
| `rim_gap` | 1.5 mm | Moat between coin edge and ring bore |
| `axle_r` | 1.5 mm | Axle diamond vertex radius |
| `reed_n` | 64 | Reeded-edge groove count (0 = smooth edge) |
| `engrave` | true | Face engravings on/off |
| `loop` | true | Keyring loop on the ring |

All parameters are at the top of `perspective-coin.scad`, grouped in
Customizer sections; override on the command line with `-D 'coin_d=45'`.

## Assembly & use

None to assemble. When the flipper comes off the bed the coin is lightly
fused to its sockets — hold the ring and flip the coin firmly once; after
that it swings freely. Ego inflating? Flip to the hourglass. Comparing
yourself into the ground? Flip to the sun: you are enough. The two engraved
diamonds at 3 and 9 o'clock mark the pivot so you always know where to push.
If the pivot is stiff or sloppy, reprint the coupon at ±0.05 mm
`pivot_clear` and carry the value over.
