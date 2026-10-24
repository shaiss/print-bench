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
  pegs). Printable female lip land `joint_lip = 1.0` mm; felt step
  `joint_step = 0.20` mm (≤ 0.25). Male tongue set back by
  `joint_lip + joint_step` so the lip is a real wall (Jane R1). Coupon has
  a flat stand-in; `joint-fit` gates the real curved pair.
- **Back pie lightening is blind** (`back_pocket_d = 1.0` mm from the inside
  face). Through-slots violated N3 (Drik F1); closed floor remains.
- **Back pies shingle** with a half-thickness circumferential lap
  (`back_clear_ang = 0.25°`, `back_z_clear = 0.20` mm; tongue/recess
  heights snapped to the 0.2 mm layer grid as **1.0 / 1.4 mm** summing to
  `back_t`; female recess angularly pad-clipped so it never nicks the
  hub-mount boss). A prior `back_half = seg_ang/2 − lap/2 − 0.5` left
  ~4.27° sunburst through-slots (~1.3 mm near the hub to ~10.4 mm at the
  tread). `back-closed` fitcheck (seam-wedge probes at z≈0.05–0.20 minus
  the assembled rim) must stay empty; ctrl omits one segment.
- **Rim-to-floor clearance** via `wheel_floor_clear = 15` (Drik F2). Axle at
  155 mm; use height (axle + boss/2) ~164 mm; lip underside ~6 mm above the
  footplate top. As-printed stand Z stays ~178 mm (driven by foot depth +
  port, not axle height).
- **Loose printed axle** (repairable default). PIP captive axle deferred —
  coupon may trial it later; not the shipped stand.
- **Stand prints port-down** (sector tips on the bed — the family idiom).
  A foot-down print with a horizontal port needed supports; printability
  wins over the brief's "on its base" orientation note. In use the foot
  is on the floor and the port is the anti-slide anchor.
- **Stand AABB ~178 mm vs 180 mm bound is intentional** (2 mm mesh headroom
  under #673). Measured on the print-pose export: **178 mm is Z (height)** —
  port-down, foot vertical — so a slicer brim never affects it; bed XY is
  **164 × 100 mm** (a prior 45° brace rotated into +Y and inflated bed Y to
  ~172 mm — fixed to the X–Z plane). Room for a normal brim on a 200 mm bed.
  The 180 mm bound is the CI/printcheck envelope, not the keeper's bed. Do
  not shrink geometry for that margin. (Drik R2 finding 8; R3 finding 4.)
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
   `port_tol` by ±0.05 (lib default 0.30 is unmeasured). Bed-side faces lose
   ~0.1–0.2 mm to first-layer squish — if the coupon port feels tight, raise
   `port_tol` before blaming the nominal.
2. **Axle / bore** — spin the sample shaft in the sleeve. Rattle → drop
   `axle_clear` 0.05; bind → raise 0.05. Quiet running is the product bar.
   **Listen on the first spins** — rattle or bind is what the coupon exists
   to catch; sound is the owner's only telemetry once the farm is printed.
3. **Joint** — dry-fit the flat male/female pair; caliper the step (≤ 0.25 mm)
   and peg fit. Run a fingernail across the female lip — it should feel like
   a real wall, not a hairline. Then trust `joint-fit` on the curved
   production geometry.

Same filament for coupon and production parts (PETG rim vs PLA stand may use
two coupons).

## Print settings

- **Rim segments / hub / back:** PETG preferred (impact at joints). Flat, back
  on the bed. No supports.
- **Stand:** PLA ok. Port-down on the coupling sector tips (foot vertical
  during print, on the floor in use). No supports.
- **Axle:** PLA or PETG; on its side. No supports.
- **Layer height:** 0.2 mm. **Infill:** 15–20 % for stand/hub; 20 %+ for rim.
- **Seam:** Away from the running surface and the port ring.

## Gate measurements (G4 — measured on export, not the typed parameter)

| Brief row | Parameter | Measured |
|---|---|---|
| bore 80 / port_tol 0.30 / port_proj 10 / n_lug 3 | `nuggs_cfg()` defaults | `mates` fitcheck empty (0 facets); `mates-ctrl` 1714 facets |
| Wheel Ø 280, width 90 | `wheel_d` / `wheel_w` | Rim segment AABB height (tread) **92.40 mm** = 90 + back_t; 8× segments close the circle by construction (`n_seg`/`seg_ang`) |
| Max part bound ≤ 180 | — | rim-segment max **129.5**; hub **48**; stand **178.0** (print Z); axle **126**; coupon **149** — all ≤ 180. Stand bed XY **164 × 100** (brace in X–Z; printcheck `--build-volume 180³`) |
| Joint step ≤ 0.25 | `joint_lip=1.0`, `joint_step=0.20` | `joint-fit` empty (mated shingle); `joint-fit-ctrl` interferes |
| Axle Ø 8 + clearance | `axle_d=8`, `axle_clear=0.35` → bore 8.70 | `axle-fit` empty; `axle-fit-ctrl` interferes; axle AABB Ø **8.00** |
| Stand footprint ≥ 0.6×Ø | `stand_depth_mult=0.60` → 168 | Foot depth in use frame 168; `ci.cog` STABLE, margin **23.81 mm** (> 2.0) with printed-part mass 383 g at axle |
| Lip vs footplate ≥ 5 | `wheel_floor_clear=15` → `axle_z=155` | Lip OD 145.4; lip underside 9.6; footplate top 3.6; clearance **6.0 mm**. Use height ~164 mm |
| Back closed | blind pockets + layer-snapped back-pie shingle (`tongue_h=1.0`, `recess_h=1.4`, pad keep-out) | `back-closed` fitcheck empty (seam probes at z≈0.05–0.20); `back-closed-ctrl` interferes; pockets only above z≈1.4 |

Gate scores (local Manifold nightly, `gate.sh --slice`, post pad/layer wrap-up):
rim-segment **92**/100 (caveats: thin-wall + overhang samples), hub **100**,
stand **84** (overhang + small bed contact on port-down pose), axle **100**,
coupon **92**. CoG uses printed-part mass **383 g** at the axle (was 180 g)
— STABLE, margin **23.81 mm**. Plate 4 objects (one of each; clone segment
×8 + spare). Fitchecks: `mates` / `axle-fit` / `joint-fit` / `back-closed`
empty; all `*-ctrl` interfere.

Slice estimates (same run): rim-segment **3h 37m / 45.5 g** (×8 ≈ 29h /
364 g), hub **1h 4m / 12.0 g**, stand **8h 27m / 117.5 g**, axle **22m /
4.8 g**, coupon **3h 7m / 35.9 g**. Full set (8× rim + hub + stand + axle)
≈ **39h / 499 g** before the coupon.

## Field test log

_(none yet)_
