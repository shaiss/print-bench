# nuggs-open — engineering log

Design brief: #308. Charter: [`designs/nuggs/PM.md`](../nuggs/PM.md)
(N2 defines what a break is; N11 the arc floor; B4a the family). Runs under
`/pm nuggs`'s charter until a `PM.md` of its own exists — the open-module
family inherits every NUGGS non-negotiable (a new module family is not a
new charter).

## Goal

The first member of the NUGGS **open-module family**: a straight 80 mm-bore
module whose midspan opens into a longitudinal window ≥ 180° with the
bore's own arc as its floor. Under charter N2 an open module is one of only
three things that **reset a run** (an open end, an open module, a
turnaround node), so any layout longer than one straight *requires* a part
like this to stay legal. Who it's for: a NUGGS owner extending a run past
the 360 mm limit, or wanting a mid-run check/hand-access point without
disconnecting anything.

## Given / assumed measurements

| Quantity | Value | Given/assumed | Source |
|---|---|---|---|
| NUGGS port bore | 80.0 mm | given | `lib/nuggs-coupling.scad` `nuggs_cfg` default |
| Coupling clearance `port_tol` | 0.30 mm | given (flagged unproven, #56) | `nuggs_cfg` default; tuned on `designs/nuggs`'s coupon |
| Window arc | 190° (≥ 180° required) | given | charter N2 break definition; 190 default = shrink margin |
| Floor geometry | bore-arc floor | given | charter N11 (flat floor on the Never list) |
| Body length | 180 mm | assumed | same as the straight's `body_len_mm` default, so runs alternate predictably |
| Window longitudinal extent | 120 mm of the 180 | assumed | ~30 mm full-round each end for the port necks |
| Minimum animal passage | 70 mm bore throughout | given | NUGGS welfare floor (charter N1) |

## Key decisions

- **Everything from the library, nothing new.** Two `nuggs_neck()` ports
  (bore-clean by construction) + a plain `cylinder` midspan + one
  `nuggs_window()` cut. No coupling geometry of this design's own; the
  window is the library's. The walk-band guard inside `nuggs_window()`
  (±40° about the invert) is what keeps the floor arc the animal walks on
  intact — the "no interior ledge" welfare rule at the window *sides* is
  enforced by construction there.
- **Window-end treatment = the neck, not a ramp.** The window mouths land
  exactly at the necks' full-round shell (z = neck_len and body_len −
  neck_len), where the section steps from full tube to window in one
  plane. There is no interior ledge to ramp because the step is *radial*
  at the mouth plane, not axial along the bore: the bore is the same ri
  cylinder end-to-end; only the outer shell's coverage changes. A paw at
  the mouth meets the same continuous ri arc it meets everywhere else —
  measured on the export (G4).
- **`neck_len = 30` mm** — comfortably above the port-zone `z_top` = 13 mm
  the lib asserts, giving ~17 mm of grip past the coupling collar, and
  leaving exactly 180 − 2·30 = 120 mm of window, the brief's assumed
  extent.
- **`open_deg = 190`** — the brief's conservative default: just past the
  180° break threshold for margin against print shrink pulling the printed
  part under, 90° clear of the lib's 280° walk-band ceiling. Parameterized
  for the brief's non-blocking wider-access question.
- **Print pose: tube axis vertical, window sideways (+X).** The brief
  forbids window-down (the floor arc would overhang its own bore). With
  the axis vertical the window's azimuth is horizontal by definition and
  print-irrelevant — every layer is the same 170° annulus segment, nothing
  window-side faces the bed, the mouth planes print as flat 2.4 mm
  bridges, and the two rim walls stand as the near-vertical shells the
  brief's pose language names (a horizontal axis is *not* the
  self-supporting reading: the remaining hull's flanks pass 45°). The part
  stands on the lower port's sector tips — same bed contact as the
  straight, which round-3 widened `lug_deg` to 40 to solve. Confirmed on
  the render and the test-slice: no supports, sector-tips-only bed contact.
- **Coupon inherits, doesn't re-derive.** `nuggs_neck(cfg, z_top + 8)` —
  the identical shape `nuggs-den`/`-frieda`/`-orrery` ship. The fit is the
  standard's (`port_tol`), tuned on `designs/nuggs`'s coupon; this coupon
  re-proves the standard port at this design's own build.

## Measured on the export (G4, iterations 1→2)

Two silent geometry bugs iteration 1's gate could not see — both caught by
measuring the export, not reading the variables (issue #37's lesson; the part
was watertight, sliceable and 84/100 both times):

1. **Un-mirrored upper port.** `nuggs_neck()` puts its sectors on −z; placed
   un-mirrored at the top end they pointed *down into the tube* (ring material
   at z=140–163, nothing past the top face). The port cannot couple — the
   family idiom is `translate(...) mirror([0,0,1])` (straight `nuggs.scad:339`,
   elbow `:244`). Fixed; ring now at z=170–190 past the top face, symmetric
   with the lower port's −10…13.
2. **Solid core through the window span.** The midspan cylinder was solid, and
   `nuggs_window()` only removes a wedge from `ri−1` **outward** — it opens the
   wall, it does not hollow the tube. Without a through `nuggs_bore_cut()` the
   part ships a solid r=39 billet through the window: measured volume 687 cm³
   (852 g) vs the ~100 cm³ (124 g) of the fixed part, and slicer filament
   275 g → 117 g. The library doc says it — the window assumes a *tube* body,
   and the solid cylinder wasn't one. Fixed with the straight's one-cut idiom
   (`nuggs.scad:340`): `nuggs_bore_cut(cfg, -port_proj-2, body_len+port_proj+2)`.

Post-fix numbers, all measured off `build/nuggs-open.stl` (cross-sections at
z=35/90/145, exact edge-plane intersections):

| Brief row | Required | Measured |
|---|---|---|
| Window arc | ≥ 180° | 191° (material run 96°–264° at r=41) |
| Window extent | ~120 mm | 121 mm (void 29.5→150.5 at the crown) |
| Bore / passage | 80 / ≥ 70 mm | 80.0 mm / 80.0 mm (min vertex r 39.988) |
| Rim wall | ≥ 1.2 mm | 2.4 mm (radial crossings 40.0 → 42.4) |
| Body length | 180 mm | 180 mm (port faces z=0, 180; tips −10/190) |

## Product-page decisions (§5)

- **Preview set = the elbow's four + a `pair` shot.** Frozen in
  `previews/cameras.conf` (contact-sheet, hero, bottom-iso, bore-cutaway,
  pair), each verified on its rendered image before freezing: hero shows the
  window face-on with the bore visible; bottom-iso confirms the three
  sector-tip bed pads and no downward-facing window surface; the cutaway
  shows the bore-arc floor running the window with no ledge; the pair (the
  one shot the elbow doesn't have) is this part's reason to exist — the
  run's-eye view of two opens coupled, windows clocked half a pitch apart.
  All five rendered locally and committed byte-identical to the QA'd drafts.
- **Product hero (shots.conf) declares, CI renders.** `product-hero` at
  rotz 65 / elev 22 / satin — rotz 65 keeps the camera on the +X (window)
  side of the library frame, the aspect the frozen hero shows; the color
  `e8b7c8` is the module's tint in the pair preview, so the studio hero and
  the coupled view read as one product. The missing
  `previews/product-hero.png` is the expected pre-regen readme-gate line
  (the run's `github_token` is a PAT, so `regen` fires on the draft PR).
- **Charter conformance (B4a's "owes the gate a conformance case"):**
  - N1 — bore ≥ 70 mm: asserted in `nuggs_cfg` (`min_bore`), measured 80.0.
  - N2 — the ≥ 180° window is what makes this a break: asserted in this
    design, measured 191° at r=41.
  - N11 — arc floor: by construction (`nuggs_window()` only removes outward
    of ri−1; the floor *is* the ri surface); measured — bore a continuous
    80.0 mm through the window span, no interior ledge at the mouths.
  - Port fit — the library's, proven by `lib/nuggs-coupling-mates.conf`
    (155 cases, run by check.sh), re-proved at this build by the coupon.
  - Run-rule status documented in the README (family precedent: the elbow
    documents "a bend is not a break" rather than engraving it; only the
    straight carries the MAX RUN engraving).

## Print settings

- **Orientation:** tube axis vertical, standing on the lower port's sector
  tips; the window faces +X (sideways) — its azimuth is print-irrelevant in
  this pose. Exactly as it renders.
- **Supports:** none. The window's arc floor prints as a bridge crown; rim
  walls are near-vertical.
- **Material:** PETG (charter default) or PLA. 0.4 mm nozzle, ≥ 1.2 mm
  walls (the 2.4 mm shell is 6 perimeters).
- **Bed fit:** Ø96.8 mm envelope × 200 mm tall — fits a 256³ build volume
  (`printcheck.args`); the same as the straight's.

## Print this first

`nuggs-open-coupon.scad` — one bore-clean port stub (`part = "coupon"`).
Mate two of them (or one to any NUGGS module you already printed) and tune
`port_tol` in ±0.05 steps until the quarter-turn seats without forcing,
**then** commit to printing this module. The fit is the shared standard:
the number you find applies to every NUGGS module, and the coupon to print
is `designs/nuggs/nuggs-coupon.scad`'s — this one exists so the design
ships a design-scoped part (gate-level detail per the brief).

## Open items

- Window arc 190° vs 200–220° for easier hand access — brief's non-blocking
  open question; 190 ships as the conservative default, parameterized.
- Rounded outer rim lip (chew-safety, N6-style) — brief's non-blocking open
  question; session decides from the render. Default: none added (the rim
  is a full shell wall, meeting ≥ 1.2 mm by construction).
- The nuggs-yard rebuild onto the standard is its own PR (charter decision
  log); this is one module of that family, not the rebuild.
