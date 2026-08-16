# snap-clamshell-box — engineering notes

**Advanced (Tier-3) reference design.** Fuses two independent compliant
sub-mechanisms in one support-free flat print.

## Goal

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
closed. Note `win_z = wall_h + latch_h·0.55` scales *with* `wall_h`, so the map
re-solves at any wall height: at `wall_h = 13`, `win_z = 17.95` and
`tab_flat_z = 8.05`. Verified on the export — the closed tab measures `z ∈
[16.75, 19.15]`, centred on the window band `[16.35, 19.55]`, with 42.8 mm³ of
tab-in-window overlap.

## The closed-pose clash and its fix (issue #230)

The strip was authored in the *outer-wall plane* (`y ∈ [td−wall_t, td]`). That is
exactly where the lid's own front wall lands when it folds over, so base strip ∩
closed lid = **216.00 mm³ (32 facets)** — ~100 % of the strip, and the box jams on
the first close. It was invisible to the flat-pose gates: nothing overlaps until
you fold. Fix: stand the strip off outward by `latch_clr` (default 2.0 mm =
`wall_t` + 0.4 mm print clearance) so its inner face sits proud of the closed lid
wall, and carry it on a buttress that fills from the outer wall out to the strip
but stops at the rim (`z ≤ wall_h`) — below the plane the lid ever reaches, so the
buttress is structurally base-side and cannot itself clash. The tab still
protrudes `hook = 2.0 mm`, enough to reach through the offset window (engagement
re-measured above). Locked in by `ci.fitchecks`: `closed-clash` must render empty,
`closed-clash-ctrl` (the same intersection with `latch_clr = 0`) must reproduce
the 216 mm³ interference — the negative control proving the check can fail.

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
- Closed-pose latch clash fixed and gated (`ci.fitchecks`, issue #230); `wall_h`
  raised to 13 so the closed interior (22.8 mm) holds an earbud.
- TODO: `gate.sh --slice` (needs PrusaSlicer; run in CI); `previews/cameras.conf`
  + an `animations.conf` fold animation; the deeper latch coupon sweeping the
  tab/window interference fit remains worthwhile for tuning.
