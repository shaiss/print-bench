# snap-clamshell-box — engineering notes

**Advanced (Tier-3) reference design.** Fuses two independent compliant
sub-mechanisms in one support-free flat print.

## What it is

A clamshell box: two trays joined at a spine by a **living hinge**, closed by a
**compliant snap latch** (tab-in-window). Prints flat and open, folds 180° so the
openings meet, and the front latch clicks shut. One piece, no supports, no
assembly.

## The fusion

| Technique | Where |
|---|---|
| **D1 — living hinge** | a thin flexure web (`hinge_t = 0.6`) across the spine at the rim top; the doc's living/notch hinge |
| **D1 — snap latch** | the base's front wall extends into a compliant strip with a WINDOW; the lid's ramped TAB flexes it out on close and is captured — a second, independent flexure |
| **D2 / CC1 — orientation** | printed FLAT, both trays coplanar and open: every wall vertical, nothing overhangs; the hinge web is a short top bridge |

## The one non-obvious derivation — the fold map

The latch's two halves are authored in the flat print but must meet after a 180°
fold about the spine top `(y=0, z=wall_h)`. That fold maps a point
`(y, z) → (−y, 2·wall_h − z)`. So the lid tab's flat height is
`tab_flat_z = 2·wall_h − win_z`, which lands it exactly at the base window when
closed. Verified on the closed pose (`previews/closed-latched.png`): the tab sits
captured in the window.

## Name note

The closure is a **snap** (two stable states, open/latched, separated by the
strip flexing), *not* a buckled-arch **bistable** — that primitive is the
`bistable-toggle` design. Named accordingly to not overclaim. A buckled-arch
bistable latch is a possible variant but wouldn't print as flat.

## Print

Flat, no supports. Living hinge → PETG/PP (folds), not PLA (cracks). Snap latch
material is less critical (few cycles).

## Status

- Renders clean; folded + latch-face poses confirm the box closes and the tab
  seats in the window.
- TODO: `gate.sh --slice`; latch is a tuned fit → a coupon sweeping the tab/window
  interference (with an interfering negative control); README + product shot;
  `previews/cameras.conf` + an `animations.conf` fold animation.
