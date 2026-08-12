# captive-spinner — engineering notes

**Reference design for** `docs/advanced-techniques.md` **Domain 3 (print-in-place
kinematics)**, plus **CC3** (derive clearance; split xy from z) and **CC2** (the
break-free first motion). Tier-1 "easy".

## Goal

A one-piece, support-free, no-assembly fidget: a rotor ring captured on a fixed
post + cap, spinning about the vertical axis after you shear the break-in fusion.

## The anisotropy lesson (CC3) — the reason this design exists

Two different gaps, deliberately two different numbers:

| Gap | Interface | Physics | Value |
|---|---|---|---|
| **radial** | rotor bore ↔ post | vertical wall-to-wall → **spread-limited** | `xy_tol = 0.2` (≥ one line width) |
| **axial** | rotor ↔ base, rotor ↔ cap | roof/floor over part → **sag-limited** | `z_tol = z_layers·layer_h = 0.4` (2 layers, quantized) |

A single global tolerance is the classic print-in-place bug. If you tuned both to
the sag-limited 0.4, the rotor would wobble radially; if you tuned both to the
spread-limited 0.2, the axial roof would fuse. They are governed by different
processes, so they are different parameters.

## Capture geometry

The cap is a **45° cone widening upward** (`cylinder(r1=post_r, r2=r_cap)`), i.e.
a countersunk-head shape. Its capturing overhang is therefore a ≤45° locking lip
that self-supports — the doc's captive-joint primitive. `z_cone0` is placed so
the first cone material directly over the rotor bore edge lands exactly `z_tol`
above the rotor top:  `z_cone0 = rotor_top + z_tol − xy_tol`.

Guards: `xy_tol ≥ 0.15`, `cap_lip ≥ 1.5` (or the rotor pops off), `r_cap <
rotor_or` (or there's no ring to grip).

## Break-free first motion (CC2)

Printed in place, the rotor micro-fuses to base and cap across the gaps. First
spin shears that fusion — expected, not a defect. Designed for a low-torque
break-in (small contact annuli), never a seized part.

## Print this first

`captive-spinner-coupon.scad` — a small spinner (include + override, no copied
geometry). Print it and give the rotor a firm spin; if it's fused, raise `xy_tol`
by 0.05 mm and reprint; if it rattles, lower it. Tune `xy_tol` here before a
full-size print. Gated like any part.

## Status

- Renders clean; preview reviewed (rotor + scallops + capture cone).
- Print-in-place fit → this is its own mate. Before ship: `ci.fitchecks` proving
  the rotor renders as a *separate body* with 0 interference facets, plus a
  deliberately-interfering negative control (xy_tol driven to 0). TODO with gate.
- TODO: `gate.sh --slice`, README, product shot.
