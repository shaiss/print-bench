# constant-force-slider — engineering notes

**Advanced (Tier-3) capstone reference design.** Fuses the doc's hardest
compliant idea (quasi-zero-stiffness constant force) with a print-in-place slide.

## What it is

A linear shuttle that moves under ~constant force over its stroke. It rides a
guide slot (print-in-place sliding fit) and is returned by a QZS spring built
from two flexure families in parallel.

## The QZS mechanism (D1) — the star

From the doc's constant-force section: *"put a negative-stiffness element (a
bistable/buckled beam) in parallel with a positive one (a V-beam) so the slopes
cancel over a stroke."* Realised literally:

- **Positive spring — V-beam** (chevron): two legs from the shuttle top to an
  offset apex, then to the fixed top bar. Resists shortening (positive `k`).
- **Negative spring — pre-buckled arch** in parallel: a shallow clamped arch
  (`arch_rise/arch_t ≥ 2.3`, asserted — same bistability threshold as
  `bistable-toggle`). Over its snap region it has **negative** stiffness.
- Tune `arch_rise` so `−k_arch ≈ +k_vbeam` over the stroke ⇒ **net stiffness ≈ 0
  ⇒ constant force**. The geometry can't measure force; a coupon plots
  force-vs-displacement to find the plateau (and to tune the cancellation).

Both are anchored at the same two points (shuttle top, top bar) — genuinely in
parallel. Checked on the ortho top (`previews/qzs-spring.png`) that they do not
weld mid-span (arch at x≈−4, V-beam leg at x≈+2 at mid-height).

## The print-in-place slide (D3)

The shuttle tongue rides a guide slot with `slide_tol = 0.35` mm per side — a
vertical wall-to-wall gap, **spread-limited** (CC3), the printer must keep open.
The QZS spring tethers the shuttle (it can't fall out), so the spring is both
force element and retainer.

**Honest scope note (Z-capture).** A flat, Z-uniform print captures the shuttle
in X (slot walls) and holds it in Y (the spring); it's used lying flat. Full
Z-capture would need a T-slot rail (a Z-varying cross-section) — a deliberate
scope choice, called out so the reference doesn't overclaim. The `sushi-battleship`
slide (via `lib/print-in-place.scad`'s castellated `slide_rail`) is the Z-capturing
variant if one is wanted.

## Print (D2 / CC1)

Flat, profile in XY extruded in Z. Every flexure bends in the layer plane; the
slot walls are vertical; no overhangs, no supports. Live flexures → PETG/PP/nylon,
not PLA.

## Status

- Renders clean; QZS topology and the guide fit confirmed on ortho + iso.
- TODO: `gate.sh --slice`; a force-displacement coupon sweeping `arch_rise` to
  find the constant-force plateau (with a non-cancelling control); README +
  product shot.
