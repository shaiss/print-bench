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
closed. That map is correct, and `previews/closed-latched.png` does show the tab
arriving at the window height. What that render could not show — a union renders
interference as solid material — is that the strip and the lid's front wall were
fighting over the same Y band. See the next section.

## The closed-pose clash (issue #230)

The fold map places the latch halves in Z. Nothing placed them in **Y**, and that
is where the design was broken. The same 180° fold that brings the two rims
together also lays the lid's **front wall** onto the tray-frame band
`y ∈ [td − wall_t, td]` — the exact band the latch strip was built in, because the
strip was authored as the outer wall "extended above the rim". Flush meant
coincident: **216.00 mm³ across 32 facets**, ~100 % of the strip's material. The
first close was the failure.

Nothing here could see it. The design prints flat, so the default render, the
4-view sheet, printcheck and the test slice all inspect a pose where the two
halves are 76 mm apart. The one artifact that does fold the lid,
`previews/closed-latched.png`, unions the halves — and a union draws interference
as solid material.

Fix: `latch_clear` (0.4 mm) holds the strip outboard of the wall face, clear of
the band the lid occupies. A strip offset outboard has nothing under it, so a 45°
root gusset carries it out from the wall, placed entirely **below the rim**
(`z < wall_h`) — the one region the folded lid never reaches, since the closed lid
spans `z ∈ [wall_h, 2·wall_h]`. So the gusset can be as solid as it needs to be
without re-introducing the clash, and its 45° underside keeps the flat print
supportless. Cost: +41.98 mm³ of material and 2 mm of open-pose Y footprint
(78.5 → 80.5 mm). The closed box is unchanged at 24 mm.

The probe modules (`placed_base_latch`, `placed_lid`) are the same ones `main()`
builds the model from. A probe that re-typed the fold transform would only prove
its own arithmetic self-consistent — which is how this shipped in the first place.

The negative control is the interesting half. It rebuilds the strip at
`clear = −wall_t` — the shipped geometry — and reproduces 216.00 mm³ / 32 facets
exactly. It is `−wall_t` and deliberately **not** `0`: at `clear = 0` the strip is
already outboard and merely *touches* the lid wall at `y = td`, which intersects
to a degenerate zero-volume sliver. That sliver still counts facets, so a control
written at `0` would have "passed" while proving nothing.

### Measured after the fix

| Probe | Result |
|---|---|
| `part="fitcheck"` — latch ∩ closed lid shell | **0 facets** — clears |
| `part="fitcheck_neg"` — strip flush in the wall band | **216.00 mm³ / 32 facets** — control fires |
| tab material inside the window aperture | **42.79 mm³**, `z ∈ [15.82, 18.08]` in a window spanning `[15.35, 18.55]` — captured, ≈0.47 mm above and below |
| tab ∩ strip material, closed and at rest | **0** — the latch sits unloaded; the flex is the closing action only |
| closed bounding box | 53.2 × 39.3 × **24.00** mm |
| open bounding box | 53.2 × 80.5 × 20.99 mm |

Rendered with OpenSCAD 2021.01, the stable version CI's `check` job pins.

## Name note

The closure is a **snap** (two stable states, open/latched, separated by the
strip flexing), *not* a buckled-arch **bistable** — that primitive is the
`bistable-toggle` design. Named accordingly to not overclaim. A buckled-arch
bistable latch is a possible variant but wouldn't print as flat.

## Print

Flat, no supports. Living hinge → PETG/PP (folds), not PLA (cracks). Snap latch
material is less critical (few cycles).

## Status

- Renders clean as a single body; the closed-pose latch clash is fixed and gated
  (`ci.fitchecks`, issue #230).
- `gate.sh --slice` has **not** been run against the fixed geometry: the session
  that fixed the clash had OpenSCAD but no printcheck or PrusaSlicer, so CI is the
  first place the slice runs.
- `latch_clear = 0.4` is a generic FDM clearance, **not** a measured one. Whether
  the snap still holds with the strip standing 0.4 mm off the wall is a question
  only a printed part answers — it wants the coupon below.
- TODO: latch is a tuned fit → a coupon sweeping the tab/window interference (with
  an interfering negative control); `previews/cameras.conf` + an `animations.conf`
  fold animation.
- Known and deliberately left alone: `latch_t` (1.6 mm) is declared but never
  used — the strip is built from `wall_t`, so overriding `latch_t` does nothing.
