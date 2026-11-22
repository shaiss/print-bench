# vesa-shelf — engineering log

## Goal

A plate that bolts onto a monitor's VESA mounting holes (the same four M4
threaded inserts a monitor arm or wall mount uses) and cantilevers a small
tray into the dead space behind an arm-mounted display. For a stranger who
wants to stash a Raspberry Pi / mini-PC, slim video bar, USB hub, or cable
loop behind the screen without straps or adhesives. Brief: issue #976
(`design-brief`, `workshop-utility` style). Catalog hole: no prior
`designs/` entry referenced VESA.

## Given / assumed measurements

| Measurement | Value | Status |
|---|---|---|
| VESA hole pattern (square pitch) | 100 × 100 (param; also 75) | **given** — VESA MIS-D |
| Mounting screw | M4×0.7 machine screw, purchased | **given** — VESA MIS-D |
| Screw engagement into display | ≤ 10 mm | **given** — VESA MIS-D typical max |
| M4 clearance hole | Ø4.5 | **assumed** — `screw_clearance_d("M4")` |
| Plate thickness | 6 mm | **assumed** — brief; keeps engagement budget |
| Washer thickness (purchased) | 1.0 mm | **assumed** — common M4 flat washer |
| Recommended screw length | 16 mm under head | **assumed** — 16 − 6 − 1 = 9 mm engage ≤ 10 |
| Tray payload | ≤ 400 g | **assumed** — brief default with margin |
| Tray floor | 110 × 80 mm | **assumed** — Pi 4 case 91 × 62 with margin |
| Tray drop below pattern | 25 mm | **assumed** — brief "standoff" row, see below |
| Cable pass | Ø20 centre | **assumed** — brief optional |

**Reinterpretation recorded in-run (brief "standoff" row):** the brief's
"Standoff from display back | 25" pairs two ideas — behind-monitor gap, and
"the tray hangs in the plate's plane, offset below the pattern." The
geometry that matches the tray-below-pattern design call is a **vertical
drop** from the lower VESA hole centres to the tray top (`tray_drop = 25`).
Tray depth into the gap is the separate `tray_d = 80` (Pi-case fit). The
README tells the user to check their arm head clears both the plate and the
chosen `tray_d`. Flagged in the PR for the human to sanity-check.

## Key decisions

1. **Tray hangs below the bolted pattern** (brief design call). Load hangs
   on the plate in a stable posture; the tray never cantilevers above the
   screws.
2. **Print orientation = use orientation.** Tray floor flat on the bed,
   plate standing at the back, gussets in-plane at 45°. No supports; M4
   bores are horizontal teardrops through the plate.
3. **No printed threads, no fit coupon.** Fits are purchased M4 screws into
   the display's inserts. Engagement budget is an `assert` on
   `screw_len - plate_t - washer_t ≤ max_display_engage` (and ≥ 4 mm).
4. **Root-section assert instead of a deflection fitcheck.** The brief
   asked for a `ci.fitchecks` pair proving a load-deflection budget;
   fitchecks in this repo are boolean empty/interferes gates, not a
   deflection solver. The equivalent checkable gate is the bending-stress
   assert (`sigma_mpa ≤ 10` at `payload_g` over `tray_d/2`) — same numbers
   live in NOTES so a reviewer can re-derive them. No coupon, no
   `ci.fitchecks`.
5. **Tray-only v1.** Hook variant deferred (brief: not blocking). One
   closed side wall + open cable edge + cable-loop ear on the open side.
6. **Style `workshop-utility`** from scaffold: `style_corner_r=4`,
   `style_edge_chamfer=0.6`, `style_fn=64`.
7. **Pitch is a parameter**, default 100; Customizer offers 75 and 100
   only — the two published MIS-D square pitches. No invented sizes.

## Arm section derivation

At the default payload and tray depth:

- `W = payload_g/1000 · 9.81 · (tray_d/2)` = 0.4 · 9.81 · 40 = **156.96 N·mm**
- Section modulus of the tray root `Z = tray_w · tray_t² / 6`
  = 110 · 16 / 6 = **293.3 mm³**
- `σ = W/Z ≈ 0.53 MPa` ≪ 10 MPa allow (PETG, SF≈5)

Two 4 mm 45° gussets add path redundancy; the assert ignores them (conservative).

## Print settings

- **Orientation:** as modeled — tray floor on the bed, plate standing.
- **Supports:** none. Teardrop M4 bores; 45° gussets; chamfered bed edges;
  lip and ear grow from the tray.
- **Material:** PETG preferred (loaded cantilever); PLA acceptable at the
  stated 400 g payload.
- **Layer height:** 0.2 mm; ≥3 perimeters on the plate (6 mm).
- **Infill:** 25 % gyroid.
- **Hardware:** 4× M4×0.7 × 16 mm machine screws + 4× M4 flat washers
  (purchased). Confirm engagement ≤ 10 mm for your screw length.

## Field test log

(none yet — append FIELD-TEST entries per `templates/FIELD-TEST.md`)
