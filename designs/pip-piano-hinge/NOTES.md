# pip-piano-hinge — engineering notes

**Reference design for** `docs/advanced-techniques.md` **Domain 3 (print-in-place
kinematics → hinges)** and **CC4 (grow the bore by a true `offset()`, not a
scaled teardrop)**. Tier-2 "harder". Built on `lib/print-in-place.scad`'s
teardrop profile and clearance derivations.

## Goal

A multi-knuckle hinge that comes off the plate assembled and swinging — the
Domain-3 pin-in-bore joint tiled into a real piano hinge, plus the two
piano-hinge-specific defenses (xy≠z clearance, per-knuckle axial play).

## What it reuses vs what it adds

- **Reuses:** `_pip_teardrop2d` (the gated teardrop profile) and `pip_hinge`'s
  barrel-radius formula `R = 0.8·pin_d + clear + wall` (sized so the promised
  wall holds at the bore's thinnest point — the teardrop tip). The CC4
  subtlety lives in the profile's use: the bore is grown by `offset(r =
  clear_xy)`, never scaled — a scaled teardrop leaves the 45° flank planes
  coincident with the pin's (a welded print that CGAL passes and only Manifold
  export catches).
- **Adds, in-design** (lib candidates noted below): the roof-up bore
  orientation, the xy≠z clearance split, the per-knuckle axial clearances, and
  the round pin.

## D1 — the round pin (the articulation finding)

The library's matching `pip_hinge_pin` is a **teardrop**, and a teardrop pin
cannot live in a hinge that rotates: both pin and bore carry material/air
wedges beyond the circular zone (the pin's tip reaches 0.8·pin_d at 45°–135°),
so the pin only clears the bore while both point the same way. Fold the leaf
90° and the pin's tip is under barrel material — a still render that cannot
fold. The first version of this design shipped exactly that (its folded-pose
preview was geometric fiction; the pose was never intersected). The fix is the
reference lesson: **the teardrop belongs to the bore (whose roof must bridge
supportless); the pin must be rotationally symmetric** (a plain round rod,
which prints fine horizontally at Ø4). The `fold90` fitcheck renders leaf B
folded 90° against leaf A ∪ pin and must be EMPTY — articulation is measured,
not posed. Gate evidence: `fold90` empty at 90°; the pose is 3 disjoint bodies
at 100° and 110° (the preview/hero poses).

## D2 — xy ≠ z clearance (the doc's clearance theory)

One tunable, `clear_xy = 0.25` (spread-limited; the doc's 0.15–0.25 range top
and `pip_hinge`'s 0.25 weld floor), from which the sag-limited z gap is
**derived whole-layer**:

```
clear_z = ceil(max(clear_xy, layer_h) / layer_h) · layer_h
        = ceil(max(0.25, 0.20) / 0.20) · 0.20 = 0.40   (two whole layers)
```

The bore is the union of three copies of `offset(r = clear_xy)` applied to the
same teardrop profile — the base and the same profile shifted ±`dz`
(= clear_z − clear_xy = 0.15) along the profile's point axis. Sides stay at
the spread-limited 0.25; the two **horizontal gaps a sagging layer must cross**
(the bore roof over the pin, and the pin's first layer over the bore floor)
open to 0.40, snapped to the layer grid. All three copies are true offsets —
nothing is scaled, so CC4 holds for every surface.

Measured on the exported mesh (`build/pip-piano-hinge.stl`, axis at z = 5.45):

| quantity | nominal | measured |
|---|---|---|
| pin diameter (x and z of the pin body) | 4.000 | **4.000 / 4.000** |
| bore half-width at the sides | 2.250 | 2.249–2.286 (tessellation + offset-corner arc) |
| bore floor below axis | 2.400 | **2.400** |
| bore roof tip above axis | 3.600 | **3.600** |
| → xy clearance (sides) | 0.25 | 0.249 min |
| → z clearance (roof tip, floor) | 0.40 | 0.400 |

## D3 — per-knuckle axial clearance (tolerance stacking)

The failure: a run of knuckles in series accumulates axial error, and a shared
nominal gap leaves the far end of the run with a fraction of the clearance the
near end enjoys. Each knuckle therefore gets its **own** derived clearance:

```
c_k = axial_gap + (2k + 1) · axial_err        (gap following knuckle k)
```

- `axial_gap = 0.6` is the **local worst case**: 2 × bead-spread (0.10 per end
  face, the doc's clearance theory) + one extrusion width (0.4) — under that, a
  single draped bead can weld the gap shut (same logic as the lib's `end_stop`
  guard).
- `axial_err = 0.05` is the **stacking term**: the worst-case axial error of
  one slot. A slot's length is two end faces whose systematic spread error
  mostly cancels in the length, leaving about one face's floor error (0.05).
  Knuckle k's centre can then sit k·axial_err from nominal, so the gap between
  knuckles k and k+1 must additionally absorb (2k+1)·axial_err worst-case. This
  is the conservative chained model — in one print slot errors are closer to
  independent, so realized gaps are looser than this bound; the bound is the
  design guarantee.
- Layout is by **faces on the slot grid** (knuckle k spans
  `[k·slot + c_{k−1}/2, (k+1)·slot − c_k/2]`, ends mirroring the adjacent gap),
  so every realized inter-knuckle gap is *exactly* its derived c_k and the
  total run length is hinge_len to the last decimal.

Stacking arithmetic for the shipped numbers (slot = 12, c = 0.65/0.75/0.85/0.95):

```
0.325 + 11.35 + 0.65 + 11.30 + 0.75 + 11.20 + 0.85 + 11.10 + 0.95 + 11.05 + 0.325 = 60.000
```

Measured on the export (barrel end faces, cross-leaf): **0.650 / 0.750 /
0.850 / 0.950** — the derivation is in the mesh, monotone exactly as derived.
The free pin's length is `hinge_len − c_0` (half a c_0 of end clearance each
side; total barrel growth in the worst case only pushes the run past the pin
ends, which costs protrusion, not freedom).

## D4 — orientation is a clearance decision (CC1)

**Axis horizontal, teardrop roofs up** — chosen from the clearance physics:

- *Axis vertical* would make every bore a perfect vertical ring (no roof to
  bridge — the entire teardrop apparatus becomes unnecessary, gaps purely
  spread-limited ~0.15–0.25) but stands the leaf plates on edge: 4 mm × 20 mm
  plates standing 60 mm tall on a 4 mm bed footprint. Unusable.
- *Axis horizontal* costs a sag-limited bore roof — paid for with the teardrop
  profile (45° roof, supportless) plus the whole-layer `clear_z`. That trade
  **is** this design's xy≠z split: the orientation decision and the clearance
  split are the same decision.

printcheck's auto-orientation hint ("rotate +90° about X reduces unsupported
overhang 687→402 mm²") is the vertical pose — rejected for the plate-on-edge
reason above; the 687 mm² it flags is dominated by the 45° teardrop roofs,
which are self-supporting by construction.

## D5 — the roof-up bore (lib finding, #407)

At design time, `teardrop_hole` (and so `pip_hinge`'s bore) pointed its
teardrop **−Z**, while both lib doc comments say +Z (measured on a Ø10 probe:
7.94 below the axis vs 5.00 above — see issue #407; **fixed upstream by PR
#424**, see the update below). A `pip_hinge` bore's roof was therefore a round
arch, not the 45° flanks. This design cuts its bore from the lib's
`_pip_teardrop2d` profile with `rotate([90, 0, 0])` so the point **is** the
roof, and does not use `pip_hinge` for the knuckle (at the time its baked-in
bore pointed the wrong way for a hinge).

**Update (post-merge of main):** the upstream sign fix LANDED as PR #424
(closing #398, the same defect this design filed as #407) — `teardrop_hole`
and `pip_hinge`'s bore now point +Z as documented, flipped in lockstep and
pinned by a mates manifest. This design's in-design roof-up cut is unchanged
and still correct (its `rotate([90, 0, 0])` is exactly the orientation the lib
now ships); the knuckle stays constructed in-design rather than via
`pip_hinge` because the xy≠z whole-layer split and the per-knuckle axial
clearances are not things `pip_hinge` provides. Remaining lib candidate (NOT
landed): a `pip_hinge_pin_round` / articulation parameter on the pair, with a
mate case proving fold clearance.

## Construction

Leaves interdigitate: even knuckles → leaf A (−X), odd → leaf B (+X). Each
leaf is a bed-level plate + its knuckles + a per-slot web fusing plate to
barrel at the barrel's **outer wall only** (`web_reach < R − (pin_d/2 +
clear_xy)` is asserted — a web into the bore grips the pin and locks the
hinge). `plate_edge = R + leaf_gap` keeps each plate edge off the opposing
leaf's barrels. One free round pin runs through all knuckles.

## Print

Flat as modelled, axis horizontal, roofs up, no supports. `pin $fn ≥ 64`
(captive bores are $fn-sensitive; set to 96). 0.2 mm layers (the layer the
`clear_z` snap assumes). PETG or PLA. First use: work the hinge back and forth
once to free the knuckles (break-free first motion is expected — the
printcheck stability warning on the test slice is the thin upright barrels +
the free pin, both normal for this mechanism).

Known printcheck reading: 92/100 with degenerate-face WARNINGs — inherited
from the offset-teardrop-∩-cylinder construction (the pre-redesign geometry
scored identically), harmless after slicer repair.

## Print this first

`pip-piano-hinge-coupon.scad` — a fast 3-knuckle stub (include + override, no
copied geometry). Print it and work the knuckles free; if any binds, raise
`clear_xy` by 0.05 mm and reprint (`clear_z` re-derives and re-snaps on whole
layers automatically). Tune on the coupon before committing to a full-length
hinge. Gated like any part (printcheck + test-slice).

## Gate evidence (2026-08-24, run for #390)

- `render.sh` clean (3 volumes); `gate.sh --slice` exit 0.
- fitchecks: `fitcheck` empty · `fitcheck_neg` interferes (4280 facets) ·
  `fold90` empty (≥90° articulation measured).
- fusecheck: sliced STL = **3 bodies** (assert ≥3), `fused` control stays 1.
- Measurements: see D2/D3 tables — every *Must fit / hold* row mapped.
