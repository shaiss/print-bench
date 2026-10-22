# nuggs-port-gauge — engineering log

## Goal

A calibration gauge for the NUGGS genderless quarter-turn port: one
**reference head** at nominal geometry and two **ladder plates** carrying
five `port_tol` steps (0.20 / 0.25 / 0.30 / 0.35 / 0.40). The owner mates
the head against each step, scores won't seat or won't turn / seats and
clicks home / seats but wobbles, and the winner becomes the `port_tol`
every NUGGS coupon on that printer is cut at. Issue #514.

Who shouldn't buy it: if you will only ever build one NUGGS module, that
module's own coupon is the cheaper instrument. This gauge earns its keep
from module two onward (N ≥ 2).

## Given / assumed measurements

| Measurement | Value | Source |
|---|---|---|
| Bore / port standard | 80 mm bore, full `nuggs_cfg()` defaults | given — `lib/nuggs-coupling.scad` |
| `port_tol` steps | 0.20, 0.25, 0.30, 0.35, 0.40 | given — brief, bracketing the inherited 0.30 |
| Port projection | 10 mm | given — `nuggs_cfg()` default |
| Lugs per port | 3 | given |
| Mating envelope | Ø96.8 mm (`2 · r_out`) | measured from defaults (`r_out` = 48.4) |
| Step centre pitch | ≥ 96.8 mm (shipped 97) | HITL decision `ladder-plate-layout`; `step_pitch` in `.scad` |
| Value emboss | 0.60 mm | assumed — brief; above the ~0.5 mm close that blurred `perspective-coin` |
| Plate footprint | each plate on a 256³ bed | HITL yes — brief's ≤200×120 used the bore, not the ring |
| Style | none | given — calibration artifact |

## Key decisions

### HITL `ladder-plate-layout` = YES (2026-10-12)

Five steps cannot share one ≤200×120 plate once the mating envelope is the
ring OD (Ø96.8), not the 80 mm bore. Owner chose **two plates, all five
values**: `ladder-3` (0.20 / 0.25 / 0.30) in a 2+1 triangle + `ladder-2`
(0.35 / 0.40) side by side + one `reference-head`. Deliverable is the
3-object 3MF (`ci.plate`), never a merged STL.

### Everything prints standing on sector tips

A laid-down `nuggs_neck` (port axis horizontal) scores CRITICAL in
printcheck — ~26 % unbridgeable overhang on the bayonet ring — so both the
reference head and the ladder plates print in the family coupon pose: port
axis vertical, standing on sector tips. The reference head adds a bed-level
grip tab for handling; use pose is still "hold the tab and mate by hand."
Plate footprints at `step_pitch = 97` measure ~200×198 (3-step) and
~200×114 (2-step) — inside the committed 256³ volume. The HITL sketch's
≤200×135 for the 3-step cannot clear Ø96.8 centres in a 2+1 pack; the
envelope wins.

### Tip bed chamfer on head and coupon (not plates)

The reference head (and coupon stubs) stand on sector tips at z = 0, so
first-layer squish lives on the datum that touches every rung. A 0.4 mm 45°
chamfer on each outer tip OD is applied as a `difference` on the assembled
head/coupon; `port_stub` stays a one-line `nuggs_neck()` wrapper (N3 — no
coupling-profile change). Ladder-plate tips bury 0.8 mm into the backplate
and do not take the cut. Debur the head's port face before first use.

### Labels stay off the interior pocket

`ladder_station` takes a per-station `label_dir`. On the 2+1 triangle the
two base stations label −y (open front) and the apex labels +y (free outer
edge). Station order puts **0.30** (decision-rule anchor) on a bottom centre
so it is readable without crouching into the pocket; apex carries 0.20.
Centres stay on the 97 mm pitch (N2); all five values remain (N1).

**Label-clearance wall:** label centreline at `r_out + plate_margin/2 + 1`
(= 50.9 mm with defaults); 7 mm cap height → inner glyph edge ≈ `r_out − 1`.
All five labels share the same glyph count today, so nothing clips — check
this wall before a wider value or font change.

### One knob, five `nuggs_cfg(port_tol=…)` calls

No bespoke coupling geometry. Every step is `nuggs_neck(nuggs_cfg(port_tol=t),
…)`. The fitchecks prove each step accepts the nominal reference head at
the insertion clocking (`mate-0xx empty`) and that a mis-clocked pair still
interferes (`mate-ctrl`).

### No physical negative-control step

The brief's open question (a printed `port_tol = 0.10` "must not seat"
step) stays out of scope — the digital `mate-ctrl` covers falsifiability.
Mirror-readable embossing on the mating face is also out.

## Print this first

`nuggs-port-gauge-coupon.scad` — a reference stub and a receiving stub at
0.30, the same mate as the middle rung on `ladder-3`, small enough to catch
a bad first layer before the big plates. Print, pick up, mate and twist.
**Binds** (won't seat or won't turn): fix elephant foot / first-layer
squish before committing either ladder plate. **Flops** (seats but
wobbles): the printer probably wants a tighter `port_tol` — print
`ladder-3` first; `ladder-2` may be skippable. The coupon is the
catastrophe check; the tightest rung the head actually seats on the ladder
is the number. Then print `reference-head` + both plates from the
multi-object 3MF (`./scripts/plate.sh nuggs-port-gauge`).

CI print-time / filament estimates (printcheck sticky on PR #841; PLA
est.): coupon ~4 h 36 m / ~60 g; reference-head ~2 h 28 m / ~32 g;
`ladder-3` ~14 h 52 m / ~180 g; `ladder-2` ~9 h 27 m / ~113 g; **all four
~31 h / ~386 g**.

Tuning steps after a real ladder print:

1. Start at **0.40** (widest seats easiest first). Flip the reference head
   port-face down onto each ring, line the lugs up with the gaps,
   quarter-turn, and hold the plate flat with the other hand. Run 0.40 →
   0.20 then back (or have someone call rungs out of order) so the known
   0.30 default does not bias the call.
2. Score each rung: won't seat or won't turn / seats and clicks home /
   seats but wobbles.
3. **Decision rule:** choose the tightest rung that seats and clicks home
   without binding; if that rung is within one step of 0.30, keep 0.30.
   Confirm in a FIELD-TEST entry; if the winner is further away, set that
   value on the next NUGGS coupon and consider a `printer.conf` note.
4. **Session-level outs:** if all five rungs bind, fix the first layer
   before blaming `port_tol`. If even 0.40 wobbles, the printer needs
   attention before the port does.
5. **Wear:** rings are PLA mating surfaces; heavy use drifts readings
   looser. Re-run the ladder against a fresh coupon if the gauge is a year
   old or heavily used.

## Print settings

- **Orientation:** as modeled — standing on sector tips (plates on their
  backplate; reference head on tips + grip tab).
- **Supports:** none.
- **Material:** PLA fine for a gauge; PETG if it will live in a toolbox.
  Print all four pieces — head, coupon, and both plates — in the same
  filament.
- **Layer height:** 0.2 mm, 0.4 mm nozzle.
- **Infill:** 15–20 %.
- **Seam:** Back (or scarf) — the gauge reads finer than a stock seam ridge.
- **Brim:** optional 5 mm; check the plate doesn't rock on a flat table
  before gauging.
- **First use:** debur the head's port face (blade or fingernail) before
  the first session.

## Field test log

(none yet)
