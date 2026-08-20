# nuggs-hopper — engineering log

Source brief: issue #281 (product-scout draft, filed by hand). The product
page (README.md) is what a stranger reads; this is what the next session reads.

## Goal

The NUGGS ecosystem's feeding module: a shallow gravity hopper that mates the
standard quarter-turn port and holds a few days of food, dropping it into the
enclosure as it is eaten. Owner refills from outside the cage through the open
top port. The catalog had den, elbow, bridge, orrery and shutter-valve — all
tube or refuge; feeding was the gap (scout mandate: deepen the NUGGS
ecosystem).

## Given measurements

| Quantity | Value | Source |
|---|---|---|
| Port bore | 80.0 mm | brief, = `nuggs_cfg` default `bore_d` |
| Coupling clearance | 0.30 mm | brief, = `nuggs_cfg` default `port_tol` (unproven, issue #56 — tune on coupon) |
| Mesh opening | ~8 mm | brief assumption: stops head / stuffed pouch, passes pellet |
| Body length | ~120 mm | brief assumption: comparable to elbow footprint; "challenge freely" |
| All port geometry | `nuggs_cfg` defaults | brief: "none are re-derived" |

## Brief reading (recorded for the PR reader)

The brief's dimension row says "port face to **dome** end" while its part
breakdown says "two port faces inline with a bulb between". The functional
story decides it: gravity-fed **top-fill**, refill "from outside the cage
**through the open port**" — a top fill port is required, so the part
breakdown's inline reading wins. `body_len` = 120 mm is realised as the
port-face-to-port-face span; the "dome" is the crown shoulder that closes the
bulb back to the top neck. Carried forward through all four prior claims on
the issue; the human's preview reaction at the PR is where it is approved or
turned around.

## Key decisions

- **Consumer of the standard, like every NUGGS module.** ONE `nuggs_cfg()`
  with every default; no coupling number restated. Both ports come from
  `nuggs_port()`; the guards (70 mm welfare bore floor, bayonet
  clearance/travel, the circumferential regression pins) fire inside the lib.
- **One revolve, one cavity — the disconnected-volume fix.** The run before
  this built the bulb as sphere∪cylinder and shipped three disconnected
  volumes (G1 dead, hand-off comment 2026-08-17T11:50Z). This body is a
  single `rotate_extrude` polygon (nuggs-den's construction, with a second
  port at the top), which cannot come apart that way. The cavity is ONE
  full-length profile running at exactly `ri` over both port zones, so it also
  performs the port's mandatory bore cut — no second cutter at `ri` exists
  anywhere in the part, which kills the coincident-cylindrical-pair trap the
  library header warns about.
- **Mesh floor: disc, not gable.** A flat slab unioned in AFTER hollowing
  (union before and the cavity subtraction carries it back out — the same
  reason nuggs-den adds `rub_rail()` after the cavity). Cells are plain 8 mm
  squares on a 10.4 mm pitch, full unclipped squares only (a cell is emitted
  only where its farthest corner clears the bore wall). A gabled 45° cell
  profile was considered and dropped: it would print the floor warning-free
  but doubles slab thickness and closes the effective opening upward, against
  the direction food must pass. The floor's underside lands as a small
  overhang percentage (slicer bridges the 8 mm cells on layer 1) — expected,
  same tier as the den's.
- **8 mm is the opening, not the pitch** (carried from the prior run's
  hand-off). It is the entry barrier: `mesh_open = 8.0`, `mesh_rib_w = 2.4`
  (= `wall`, the brief's gnaw floor), pitch derived 10.4. Asserted band is a
  welfare bound (`max_mesh_open = 12`, never raised), not a tuning knob.
- **Coupon ships** (contract G2) even though nuggs-elbow ships none: the lib's
  mate-check owns the fit, but this design's contract froze the coupon, and
  `port_tol` is flagged unproven (issue #56). Library port stub via
  `nuggs_neck()`, the same shape the other modules tune on.
- **Mouth funnels at both faces** (den's pouch-relief, doubled): a loaded
  arrival funnels in below, a refill pour funnels in above. Each anchored at
  the tube END face, not the sector tips — the den's PR #189 lesson.

## Print orientation

Printed exactly as modelled, no rotation: bottom port's coupling sectors sit
on the bed (that is their job — `lug_deg` is the first-layer anchor), bore
straight up, mesh floor at z = 13 (three layers), bulb closing above, top
port's sectors printed last pointing up. In use the module stands the same
way: bottom port coupled to a run or cage-wall stub, refill mouth up. Gravity
is the only mechanism — no metering, no anti-hoarding (brief assumption).

Expected printcheck findings (mirroring the den's accepted state):
- Overhang WARNING of a few percent beyond 45°, mostly port geometry (the
  bare coupon shows ~7% on a smaller part) plus the mesh floor's down-face.
- Degenerate-face WARNING from the library port — the pure `nuggs_neck()`
  coupon shows the same; not fixable from the consumer side.

## Print this first

The fit is the whole part: if the bayonet won't quarter-turn, nothing else
matters. Print `nuggs-hopper-coupon` (two copies, or one plus any NUGGS
module) and check the joint before committing to the full hopper.

1. Print two coupons, PETG or PLA, 0.4 mm nozzle, >= 2.4 mm walls.
2. Mate them at the insertion clocking, twist to lock. It should seat with
   firm finger force, no tools, and hold when pulled.
3. Too tight / will not twist: raise `port_tol` by 0.05 and reprint.
   Sloppy / rattles: lower by 0.05. The asserted band is 0.10–0.60.
4. Only then print the hopper. If food bridges over the 8 mm cells with your
   pellets, widen `mesh_open` (never past 12 mm — welfare bound) and reprint;
   the floor is parameterised independently of the ports.

## Field test log
