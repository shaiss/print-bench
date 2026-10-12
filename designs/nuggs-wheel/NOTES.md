# nuggs-wheel — engineering log

## Goal

The NUGGS **exercise module** (issue #834): a segmented rim wheel on a
free-standing stand that anchors into a standard genderless quarter-turn port.
The ecosystem had no locomotion module; an exercise wheel is the standard
welfare kit a hamster habitat has. Segmentation is the design premise — a
Syrian-scale Ø280 mm wheel exceeds the gate's 200 mm test-slice ceiling (#673).

## Given / assumed measurements

| Dimension | Value | Given / assumed | Source |
|---|---|---|---|
| NUGGS bore | 80.0 mm | given | `nuggs_cfg()` default |
| port_tol | 0.30 mm | given — **untested; coupon mandatory** | lib header |
| port_proj / n_lug | 10 / 3 | given | `nuggs_cfg()` defaults |
| Wheel running Ø | 280 mm | assumed — Syrian welfare floor | brief |
| Wheel width | 90 mm | assumed | brief |
| Max part bound | ≤ 180 mm | given | #673 |
| Joint step | ≤ 0.25 mm | assumed | welfare (toe pinch) |
| Back | fully closed disc | given | wheel safety |
| Axle | Ø 8 printed plain | assumed | brief |
| Stand footprint depth | ≥ 0.6 × wheel Ø | assumed | tip stability |

## Key decisions

- **n_seg = 8** at Ø280: annular-sector XY diagonal ≈ 155 mm under the 180 mm
  bound; 6 segments would push the pie diagonal over.
- **Closed back is the segment pies**, not a monolithic Ø280 disc (that would
  violate the part bound). Hub is the small axle carrier the pies mount to.
- **Shingle joint** along the run direction (lap + recessed tongue + locating
  pegs). Step = 0.20 mm default. Coupon has a flat stand-in; `joint-fit`
  gates the real curved pair.
- **Loose printed axle** (repairable default). PIP captive axle deferred —
  coupon may trial it later; not the shipped stand.
- **Stand prints port-down** (sector tips on the bed — the family idiom).
  A foot-down print with a horizontal port needed supports; printability
  wins over the brief's "on its base" orientation note. In use the foot
  is on the floor and the port is the anti-slide anchor.
- **Style: none.** Port geometry is the look.
- **ci.cog adopted** for the stand + wheel point-mass at the axle (advisory).

## Run-break / destination ruling (brief)

**Treated as a destination, not a mid-run passage — and not a run break by
itself.** The wheel's stand anchors into a NUGGS port (anti-slide), but the
animal reaches the wheel from open enclosure space at the open front of the
rim, not by traversing enclosed bore through the stand. The stand's port is a
habitat anchor, not a tube the animal walks. Under the NUGGS length rule
(charter N2), a break is an open end, a ≥180° open module, or a turnaround
node — this module adds none of those on the bore path. Recorded here for the
owner's confirmation at the PR (sand-bath precedent: ruling in NOTES, not a
geometry input). Layout advice: place the wheel at an enclosure, not as a
bore-through mid-run module.

## Print this first

Print `nuggs-wheel-coupon.scad` (or `-D 'part="coupon"'`) before the full set:

1. **Port** — push the stub onto any NUGGS face; twist. If tight/loose, step
   `port_tol` by ±0.05 (lib default 0.30 is unmeasured).
2. **Axle / bore** — spin the sample shaft in the sleeve. Rattle → drop
   `axle_clear` 0.05; bind → raise 0.05. Quiet running is the product bar.
3. **Joint** — dry-fit the flat male/female pair; caliper the step (≤ 0.25 mm)
   and peg fit. Then trust `joint-fit` on the curved production geometry.

Same filament for coupon and production parts (PETG rim vs PLA stand may use
two coupons).

## Print settings

- **Rim segments / hub / back:** PETG preferred (impact at joints). Flat, back
  on the bed. No supports.
- **Stand:** PLA ok. Foot on the bed. No supports.
- **Axle:** PLA or PETG; on its side. No supports.
- **Layer height:** 0.2 mm. **Infill:** 15–20 % for stand/hub; 20 %+ for rim.
- **Seam:** Away from the running surface and the port ring.

## Field test log

_(none yet)_
