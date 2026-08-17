# extrusion-shelf-bracket — engineering log

## Goal

A shelf corner bracket that locks into the **side slot of standard 2020
T-slot aluminum extrusion**: hammer-head lugs on the back of the plate
slide along the slot, so a shelf board attaches anywhere along a rail with
no T-nuts and no frame teardown. Horizontal arm carries the board between
45° gussets and a front stop lip. One printable part + a fit coupon.
Brief: issue #283 (design-brief, `workshop-utility` style).

## Given / assumed measurements

| Measurement | Value | Status |
|---|---|---|
| Slot mouth width | 6.0 mm | **given** (common European 2020; brief notes 6.2 variants exist) |
| Slot cavity width | 12.0 mm | **given** — NopSCADlib E2020 `cwi`, vendored ground truth |
| Slot cavity depth | 8.0 mm | **given** — NopSCADlib E2020 `sq` |
| Slot lip thickness | 2.0 mm | **given** — NopSCADlib E2020 `t` |
| Lug neck width | 5.7 mm | **given** (brief) = mouth 6.0 − 2×0.15 slide clearance |
| Lug head hook per side | 2.2 mm | **assumed** — real M5 hammer T-nut figure; head = mouth + 2×hook = 10.4 |
| Lug engagement under lip | 1.5 mm | **assumed** (T-nut range 1.2–1.8) |
| Lug length (along slot) | 10 mm | assumed — two lugs at 20 mm pitch |
| Shelf board thickness | 16 mm | **assumed** (brief default; sets stop-lip height) |
| Reach (face → front edge) | 120 mm | **assumed**, challengeable per brief |
| Width across part | 40 mm | assumed — matches a 2020 rail face + margin |
| Plate height above arm | 40 mm | assumed — two lug pitches + landings |
| Load | 5 kg / pair | **assumed** — gusseted 6 mm PETG carries this easily |
| Material | PETG | given (preferred) |

Slot ground truth is the vendored `lib/NopSCADlib/vitamins/extrusions.scad`
E2020 row — never re-measured by hand, always read from that table.

**Reinterpretation recorded in-run (brief comment):** the brief's "lug head
5.7 under the lips" read literally cannot hook a 6.0 mouth — a 5.7-wide head
would drop straight through. 5.7 is the **neck** that passes the mouth; the
head is derived (`lug_head_w = slot_mouth + 2*lug_hook` = 10.4, hooking 2.2
per side inside the 12.0 cavity). This matches real hammer T-nuts and is the
only reading that makes the mechanism work; flagged in the PR description for
the human to sanity-check.

## Key decisions

1. **Print orientation = use orientation.** The bracket prints in the pose it
   installs: arm 120×40 flat on the bed, back plate and stop lip standing up,
   gussets in-plane. Nothing rotates between print and use, so no layer-line
   weakness across the load path and no support scars on the slot-bearing
   faces.
2. **Lug fins are constant-cross-section vertical extrusions.** Every layer
   is the full T outline (neck + head), so the hammer head prints with zero
   overhang — it stacks as identical layers rather than bridging. This is the
   whole reason the pose works.
3. **Elevated fin gets a 45° lead-in ramp** (the `thread_neck` pattern from
   `lib/threads-fdm.scad`): the second fin starts 20 mm up the plate, and
   without the ramp its head's first layer would cantilever off the plate
   face. The ramp grows the head out of the plate at 45°, self-supporting.
4. **Slide-in-only installation.** The head is wider than the mouth, so the
   bracket slides on **along the rail axis from an open end** — it cannot be
   pressed straight on. Recorded in the README's assembly section; this is
   inherent to hammer-head T-slot geometry, not a limitation chosen.
5. **Slot-fit clearance is a coupon-tuned parameter** (`slot_fit_tol`, 0.15
   default), not a constant: the brief's 5.7 neck is the starting point, and
   the coupon is how a user tunes it for their rail and printer.
6. **`rounded_box` radius clamped to `t/2`** on 6 mm-thick standing parts
   (plate, lip): the hull-based helper overshoots its `size` when `2r`
   exceeds a footprint dimension; the arm keeps the full style `corner_r=4`.
7. **Style `workshop-utility`** wired in from the scaffold (per brief):
   tokens `style_corner_r=4`, `style_edge_chamfer=0.6`, `style_fn=64`;
   45° chamfer on bed edges, never fillet; no supports, no visible fastener
   vocabulary beyond the style's M3 hole.

## Print settings

- **Orientation:** as modeled — arm flat on the bed, plate and lip standing.
  Print orientation = use orientation; no rotation needed.
- **Supports:** none. Fins are constant cross-section; the elevated fin's
  head grows from a 45° ramp; gussets are 45°; bed edges chamfered.
- **Material:** PETG (brief preference; PLA fine for light duty).
- **Layer height:** 0.2 mm; 3 perimeters (walls are 6 mm = 3×2-perimeter
  pairs at 0.4 nozzle — well over the 1.2 mm minimum).
- **Infill:** 25% gyroid is plenty at 5 kg/pair.
- **Fits:** TUNE `slot_fit_tol` on the coupon before printing a bracket.

## Print this first

The coupon (`extrusion-shelf-bracket-coupon.scad`, auto-gated by `gate.sh`)
is the two production lug fins on a narrow strip of the production plate, in
the production orientation. Print it (~20 min) and slide it into your real
extrusion rail **before** committing to a bracket:

1. Print the coupon in PETG, 0.2 mm layers, as oriented.
2. Slide it into the rail's side slot from an open end.
   - **Slides with light drag, no wobble** → print the bracket with defaults.
   - **Won't go in** → raise `slot_fit_tol` in 0.05 steps (0.15 → 0.20 → 0.25)
     and reprint the coupon. 6.2-mouth variants need one step up.
   - **Rattles** → lower `slot_fit_tol` by 0.05.
3. Once the coupon slides clean, print the bracket with the same value.

## Field test log

(none yet — append FIELD-TEST entries per `templates/FIELD-TEST.md`)
