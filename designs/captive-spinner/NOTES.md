# captive-spinner — engineering notes

**Reference design for** `docs/advanced-techniques.md` **Domain 3 (print-in-place
kinematics)**, plus **CC3** (derive clearance; split xy from z) and **CC2** (the
break-free first motion). Tier-1 "easy". Built to brief **#387** (child of the
Domain-3 reference set #204).

## Goal

A one-piece, support-free, no-assembly fidget: a rotor ring captured on a fixed
post + cap, spinning about the vertical axis after you shear the break-in fusion.

## Given / assumed measurements (brief #387)

| Quantity | Value | Status |
|---|---|---|
| Post diameter | 20 mm (`post_r = 10`) | assumed (brief default) |
| Ring OD × width | 32 × 10 mm (`rotor_or = 16`, `rotor_h = 10`) | assumed (brief default) |
| Escape lip angle | ≤ 45° (45° cone cap) | given |
| Radial gap | `k_xy·line_w` ≈ 0.15–0.25 mm | derived (CC3, below) |
| Axial gap | whole layers, ≈ 0.20–0.40 mm | derived (CC3, below) |
| Process | 0.4 mm nozzle, 0.2 mm layers, PLA/PETG | given |

## The anisotropy lesson (CC3) — the reason this design exists

Two different gaps, deliberately two different numbers, each **derived from
process constants**, never typed as a bare tolerance:

| Gap | Interface | Physics | Formula | Value |
|---|---|---|---|---|
| **radial** | rotor bore ↔ post | vertical wall-to-wall → **spread-limited** | `k_xy · line_w = 0.45 × (1.15 × 0.4)` | **≈ 0.207 mm** |
| **axial** | rotor ↔ base, rotor ↔ cap | roof/floor over part → **sag-limited** | `z_layers · layer_h = 2 × 0.2` | **0.4 mm, integer layers** |

A single global tolerance is the classic print-in-place bug. If you tuned both to
the sag-limited 0.4, the rotor would wobble radially; if you tuned both to the
spread-limited 0.2, the axial roof would fuse. They are governed by different
processes, so they are different parameters — and the axial one is **quantized to
whole layers** (`z_layers` is an integer multiplied by `layer_h`) so the gap's
floor and roof land on real layer boundaries.

Derived chain (defaults): `line_w = 0.46`, `xy_tol = 0.207`, `rotor_ir = 10.207`,
`z0 = 3.4` (rotor floats 0.4 above the base), `rotor_top = 13.4`, `r_cap =
13.207` (`cap_lip = 3`), `cone_h = 3.2`.

## Capture geometry

The cap is a **45° cone widening upward** (`cylinder(r1=post_r, r2=r_cap)`), i.e.
a countersunk-head shape. Its capturing overhang is therefore a ≤45° locking lip
that self-supports — the doc's captive-joint primitive. `z_cone0` is placed so
the first cone material directly over the rotor bore edge lands exactly `z_tol`
above the rotor top:  `z_cone0 = rotor_top + z_tol − xy_tol`.

Captivation is both directions: the base blocks down-escape, and `r_cap >
rotor_ir` blocks up-escape past the cone.

Guards: `xy_tol ≥ 0.15` (spread floor), `z_layers ≥ 1` (whole-layer quantization
is not optional), `cap_lip ≥ 1.5` (or the rotor pops off), `r_cap < rotor_or`
(or there's no ring to grip).

## Break-free first motion (CC2)

Printed in place, the rotor micro-fuses to base and cap across the gaps — the
sub-0.25 mm radial gap and the bridged first layer of the ring weld lightly, and
the first spin shears it. Expected, not a defect. Designed for a low-torque
break-in (small contact annuli), never a seized part. The 2-layer axial gap is
what keeps that fusion a *shearable film* instead of a solid weld: sag into a
0.4 mm gap stays under one extrusion's cross-section.

## Print this first

`captive-spinner-coupon.scad` — a small spinner (Ø28 × 13.8 mm; include +
override of the proportion parameters only, no copied geometry). It keeps the
**same process constants** (`nozzle_d`, `line_w`, `k_xy`, `layer_h`), so the
`xy_tol` it prints is the `xy_tol` the full-size part gets — wall-to-wall spread
does not care about the post's radius. Print it and give the rotor a firm spin:

1. **Fused** → raise `k_xy` by 0.05 and reprint the coupon.
2. **Rattles** → lower `k_xy` by 0.05 and reprint.
3. Free with a hint of resistance → print the full-size part with those `k_xy`.

Then carry the tuned `k_xy` (not a tuned `xy_tol` — the clearance stays derived)
into the full-size print. Gated like any part.

## Verification (gate record)

All green on 2026-08-24, `./scripts/gate.sh --slice captive-spinner` exit 0:

- Render: CGAL-simple, 3 volumes (fixed body + free rotor), no errors.
- printcheck: spinner **92/100** (one WARNING: the rotor's annular underside is
  a 5.8 mm-wide bridge over the axial gap — that surface *is* the print-in-place
  mechanism, sag-budgeted by `z_layers = 2`; no supports, no criticals); coupon
  **100/100**.
- Test-slice: both parts slice; PrusaSlicer warns about the floating ring
  (stability note inherent to any print-in-place part) — warning-only.
- `ci.fitchecks`: `fitcheck` renders **empty** (rotor clears everything); the
  `fitcheck_neg` control (bore shrunk 0.4 mm onto the post) interferes with 768
  facets — the check can fail.
- `ci.fusecheck` (first manifest in the repo): both STLs assert **2 bodies**
  post-slice — the rotor survives as its own body in the exact STL the gate
  slices; the `fused` control stays **1 body**, so the check can still fire. No
  `flexure` zones on purpose: the rotor connects to *nothing* (a disjoint
  captive body), so there is no legitimate thin bridge to excuse — a fuse here
  can only mean clearance collapse and must read red.

## Provenance

A `designs/captive-spinner/` scaffold (wrong proportions: Ø36 rotor, bare
`xy_tol = 0.2`, no fusecheck) was already committed on main before this run —
no PR of its own, no gate record. Per the amendment on the brief
(#387, comment thread), this run aligned it to the brief's contract rather than
rebuilding: geometry re-proportioned to Ø32×10/post Ø20, clearances re-derived
from process constants, and the fitcheck/fusecheck manifests added.
