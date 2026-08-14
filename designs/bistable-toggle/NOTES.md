# bistable-toggle — engineering notes

**Reference design for** `docs/advanced-techniques.md` **Domain 1 → bistable &
constant-force**, and **CC1**. Tier-2 "harder".

## Goal

A fixed–fixed pre-buckled arch with two stable states (bowed up / bowed down)
separated by a negative-stiffness region: power only to switch, not to hold. The
monostable snap of `snap-cantilever-clip` taken to genuine bistability.

## The design theory (straight from the doc)

Arch centreline is the fixed–fixed first mode: `yc(x) = h·(1 − cos(2πx/l))/2`.
Dimensioned from the two nondimensional constants:

- switch force: `f_s · l³ / (E·I·h) = 1486.57`
- travel: `u_tr / h = 1.98`  → the model `echo`s `u_tr ≈ 11.9 mm` for the defaults.

with `l = span`, `h = mid_rise`, `I = w·t³/12`. Choose a target force + travel,
solve back for `l` and `h`. The geometry can't measure its own snap force — a
coupon does (torque/force-vs-displacement).

## Bistability condition (the load-bearing assert)

A fixed–fixed arch is bistable only when the rise is tall enough vs the beam
thickness: **`mid_rise / beam_t ≳ 2.3`**. Defaults 6 / 1.6 = 3.75 → bistable.
Below ~2.3 it's monostable (just springs back). Asserted — this is the one number
that decides whether the part is a switch or a spring.

## Why it's stress-free in both states

Printed *in* the curved shape, so the as-fabricated up-arch is stress-free (state
1). By symmetry the mirrored down-arch is also ~stress-free (state 2). Snapping
passes through the high-stress flat; the two rest states are low-stress, which is
why it holds indefinitely without creep.

## Print

Flat (profile in XY, snap in-plane → flex in the layer plane). No supports; the
frame interior is open so the arch can bow fully down (`under_clear`). Live
flexure → PETG/PP/TPU/nylon, **not PLA**.

## Status

- Renders clean; ortho top confirms a symmetric, uniform-thickness arch with
  filleted roots (the perspective contact-sheet only *looked* asymmetric).
- TODO: `gate.sh --slice`; a coupon sweeping `mid_rise` across the bistable
  threshold (incl. a deliberately-monostable value as the negative control);
  README + product shot.
