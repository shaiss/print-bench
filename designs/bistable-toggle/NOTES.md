# bistable-toggle — engineering notes

**Reference design for** `docs/advanced-techniques.md` **Domain 1 → bistable &
constant-force**, and **CC1**. Tier-2 "harder".

## Goal

A fixed–fixed pre-buckled arch with two stable states (bowed up / bowed down)
separated by a negative-stiffness region: power only to switch, not to hold. The
monostable snap of `snap-cantilever-clip` taken to genuine bistability.

## The solve (issue #389 — dimensioned from targets, not by feel)

The brief pinned the two feel targets — **switch force f_s = 3 N ± 0.2,
centre travel u_tr = 4 mm ± 0.1, PETG** — and the geometry is *inverted* from
them via the doc's two nondimensional constants (fixed–fixed shallow arch,
`I = w·t³/12`):

| step | relation | result |
|---|---|---|
| rise | `h = u_tr / 1.98` | **2.020 mm** (`mid_rise`, derived) |
| thickness window | bistability `h/t ≥ 2.3` caps t ≤ 0.878; repo floor t ≥ 0.8 | **t = 0.82 mm** (see below) |
| width | brief floor `w ≥ 3`; chose for finger-sized face | **6 mm** |
| span | `l = (1486.57·E·I·h/f_s)^(1/3)` | **82.03 mm** (`span`, derived) |

`t = 0.82`, not the 0.8 floor: the curved band's wall samples land at every
angle to the print plane, so some read slightly under the typed thickness —
0.82 keeps every normal-ray sample clear of printcheck's 0.8 mm thin-wall
check. That is an honest fix (more material), not a gate relaxed via
`printcheck.args --min-wall`. Inside the window either way: h/t = 2.46 ≥ 2.3.

`main()` re-derives `f_s` from the built parameters and asserts it against the
target (`fs_pred`), so the solve cannot silently drift. Measured off the export
(section at z = 3, not the typed variables): span 82.029, t 0.820,
h 2.020 (from `yc(l/4) = h/2`), w 6.000 → re-derived **f_s = 3.000 N,
u_tr = 4.000 mm** — both dead on the brief's targets.

Why solve at all when E varies ±20 % by filament? The solve fixes the
*proportions*; the coupon calibrates the *material*. `E` is a parameter —
measure your snap force, scale `E` (or `target_fs`) once, re-derive.

## Bistability condition (the load-bearing assert)

A fixed–fixed arch is bistable only when the rise is tall enough vs the beam
thickness: **`mid_rise / beam_t ≳ 2.3`**. Production 2.02 / 0.82 = 2.46 →
bistable. Below ~2.3 it's monostable (just springs back). Asserted in `main()`
— this is the one number that decides whether the part is a switch or a spring.

## Why it's stress-free in both states

Printed *in* the curved shape, so the as-fabricated up-arch is stress-free
(state 1). By symmetry the mirrored down-arch is also ~stress-free (state 2).
Snapping passes through the high-stress flat; the two rest states are
low-stress, which is why it holds indefinitely without creep.

## The hard-stop cage (the doc's fatigue rule)

The real limit on a bistable mechanism in use is off-axis overload, not
primary-DOF motion: a sideways shove or an over-travel yank takes the beam past
strain it was never solved for. So the nub travels in a rigid cage, all stops
pure profile (print flat, no bridges):

- **Lid (+Y)** — the frame's top bar limits upward over-travel.
- **Base bar (−Y)** — limits the snapped-down state's follow-through.
- **±X rails** — hang from the lid (they stop `stop_gap` above the arch's
  maximum reach) so a sideways shove cannot walk the nub off its line.
- **Z** left to geometry: out-of-plane is `(w/t)² ≈ 56×` stiffer than the
  flexure axis.

`stop_gap = 0.4 mm`: past a stable state or off-axis at rest, the moving solid
meets a stop 0.4 mm later. Verified in the export: nub→lid 0.400,
arch-down→base 0.400. Filleted as the brief asks: the cage carries the
`offset(±0.3)` close-op, which rounds every concave junction (rail→lid,
frame→bar) at r = 0.3, and the flexure roots get their own r = 0.5·t fillets.

**Why rails, not cheeks.** The arch sweeps through *every interior x* between
states — an earlier full-height cheek sat at x = ±3.9 where the arch itself
passes, welding the mechanism into a solid block (see the iteration log). Any
interior stop must be a short rail living above h + t/2. And the rail's inner
face clears **`nub[0]/2 + t + stop_gap`**, not the bare nub face: the nub's
root fillets are disc unions, which protrude `2·rf` (not `rf`) past a face — a
rail placed off the bare face sits exactly on the gusset crests and fuses.

### The fitcheck that proves it (`ci.fitchecks`)

`fitcheck` intersects the cage with **`travel_sweep_2d`** — the arch band
mirrored through the snap (state 2 = state 1 reflected about the chord) plus
the nub *with its gusset bumps* — and must render **empty**: the stops bite
only on over-travel/off-axis load, never during a normal switch. This is the
check that catches a stop placed where the arch sweeps — a mechanism that
prints fused solid, which `bodies: 1` cannot see because the production part is
*supposed* to be one body (monolithic flexure). `fitcheck_neg` grows the sweep
past `stop_gap` and must interfere, proving the check can fail.

`bodies: 1` on the production part is correct, not a red flag: the arch is
rigidly clamped to the posts by design (fixed–fixed), so the *flex* proof is
the travel-sweep fitcheck, not a body count.

## Print this first

`tuned-fit` design → coupon: `bistable-toggle-coupon.scad` (`part = "sweep"`).
Four cells at l = 35, t = 0.82 (production), labelled by their
`mid_rise/beam_t` ratio: **3 / 2.5 / 2 / 1.5**. Cell "2.5" *is* the production
ratio (h = mid_rise); 2 and 1.5 are deliberately monostable — the negative
controls.

1. Print the coupon flat, no supports, in your production material.
2. Feel left to right: 3 and 2.5 should snap and hold both states; 2 and 1.5
   should only spring back. The snap dying between 2.5 and 2 is the
   calibration — it proves your printer/material landed where the solve
   assumed.
3. If "2.5" only springs back **on your printer**: raise `mid_rise` (or accept
   a monostable button — also a useful part). If the snap is too fierce: lower
   it. Re-derive nothing else — `span`/`fs_pred` follow.
4. Only then print the toggle. If the first snap needs more than fingertip
   force, your E is higher than the 2000 MPa datum: scale `E` up and re-solve
   rather than thinning the beam below 0.8.

## Iteration log (gate runs, 6 of the 8 allowed)

| # | finding (from the gate, not the eye) | fix |
|---|---|---|
| 1 | coupon render "mesh is not closed" ×4; production 24 naked edges → 75/100 | tangent-only fillet discs pinch the polygon at single points → `bite = 0.06` overlap past each joined face (`beam_gussets_2d`) |
| 2 | analytic (before render): full-height cheeks at ±3.9 sit where the arch passes — printed solid; old fitcheck swept only the nub so missed it | cheeks → lid-hung ±X rails; new `travel_sweep_2d` covers the arch through both states |
| 3 | rails at bare-nub + stop_gap fused on the gusset crests (bodies:1 mid-span weld; 0.04 mm slivers in the coupon) | rails to `nub[0]/2 + t + stop_gap`; `nub_sweep_2d` models the real solid incl. bumps |
| 4 | coupon 92/100: thin-wall 0.07 mm — period glyph dips ~0.28 below the baseline | label baseline offset 0.35 → 1.1 above the bar edge |
| 5 | coupon thin-wall 0.04 mm — period kerns tight against the next digit | `spacing = 1.5` on the label `text()` |
| 6 | green — production 100/100, coupon 100/100 (4 shells = 4 cells, intentional), both fitchecks ok | — |

Also caught: coupon cells "3.0"/"2.0" cut loose the 0-glyph's enclosed counter
as two 17 mm³ floating chips (6 shells). Labels now carry no "0". Scores
75 → 75/75 → 100/92 → 100/92 → 100/100.

## Print

Flat (profile in XY, snap in-plane → flex in the layer plane). No supports, no
bridges — the cage too is pure profile. Live flexure → PETG/PP/TPU/nylon,
**not PLA**. Overall 94 × 17.7 × 6 mm; ~6 g, ~31 min at 0.2 mm layers.

**First-layer squish (the one thing no gate models):** the clearances live in
the extruded profile, so they touch the bed at Z=0 — elephant foot (0.1–0.2 mm
per side) can pinch the 0.4 mm nub→lid slot to a hairline web on layer 1 that
the first snap shears. Not a defect, but say it in the README (compensation on,
expect the web) or a first-printer reads "stiff first snap" as a failed solve.
Jane review pass 2026-08-24 — folded into Print settings above.

## Status

Done at the #389 pass (2026-08-24) — the old TODO list is closed:

- ✅ `gate.sh --slice` green: production + coupon 100/100, test-slices ok,
  fitchecks ok (see the iteration log).
- ✅ coupon sweeping `mid_rise/beam_t` across the bistability threshold with
  deliberately-monostable negative controls.
- ✅ README + hero shot (`shots.conf`; CI renders) + frozen previews
  (`previews/cameras.conf`: contact-sheet + coupon) + AI lifestyle scene
  (disclosed).
- Solve evidence (measured off the export): f_s = 3.000 N, u_tr = 4.000 mm,
  h/t = 2.46, l/h = 40.6, w·t = 4.92 mm² — every brief row met.

**Digital gates end where physics starts (brief's caveat):** snap force,
travel and cycle life are *predictions* echoed from E = 2000 MPa until a real
print says otherwise. Verifying them is a FIELD-TEST entry
(`templates/FIELD-TEST.md`, appended under a `## Field test log` heading
below), not a digital gate — the coupon is the calibration bridge between the
two.
