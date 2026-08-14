# snap-cantilever-clip — engineering notes

**Reference design for** `docs/advanced-techniques.md` **Domain 1 (compliant
mechanisms)** — the simplest case, a cantilever/snap flexure — and **CC1
(orientation)**. Tier-1 "easy".

## Goal

A screw-down cable clip (≈6 mm cable) whose two retaining lips are cantilever
flexures. Push a cable into the mouth, the lips spread a known amount over the
snap interference, the cable seats in the pocket, the lips spring back to retain.

## The one lesson — print it flat

The silhouette is authored in the XY (bed) plane and extruded up in Z to
`width`. So the lips flex **in the layer plane**: bending stress runs across the
roads *within* a layer, never across the weak bond *between* layers. This is the
doc's #1 flexure rule made structural — print this clip upright and a lip
delaminates on the first insertion.

## Numbers

- `throat = cable_d − grip` (default 6 − 1 = 5 mm). Each lip flexes ≈ `grip/2`
  = 0.5 mm to admit the cable. Larger `grip` = harder retention, more deflection,
  more root stress.
- Root fillet `root_fillet ≥ 0.5·wall` — the doc's stress-concentration rule,
  asserted. Realised with `offset(r=−f) offset(r=+f)` (a morphological *close*),
  which rounds the concave lip roots while leaving convex corners crisp.
- Mount hole runs along the build axis (Z) → support-free.

## Status

- Renders clean; preview reviewed (centred foot + hole, symmetric C-mouth).
- This clip has a *tuned fit* (the snap interference), so before ship it wants a
  **coupon** sweeping `grip` and a "print this first" note. TODO with the gate.
- TODO: `gate.sh --slice`, README, product shot.
