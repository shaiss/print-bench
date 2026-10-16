# tslot-cable-clip — engineering log

## Goal

A **snap-in cable-clip family for standard 2020 T-slot aluminum extrusion**:
one hammer-head lug slides into the rail's side slot (the anchoring geometry
`extrusion-shelf-bracket` already proved against the same slot table), and a
loop with two flex tabs routes a common cable **along the rail** — no zip
ties, no adhesive, repositionable by sliding. Three v1 stations: Ø4.0 (PTFE
Bowden / micro-USB), Ø6.2 (Cat5e / USB-A), Ø8.0 (pneumatic / small bundle).
Brief: issue #836 (design-brief, `workshop-utility` style).

## Given / assumed measurements

| Measurement | Value | Status |
|---|---|---|
| Slot mouth width | 6.0 mm | **given** (NopSCADlib E2020 via the shelf bracket's committed table; 6.2 variants ride `slot_mouth`) |
| Slot cavity width | 12.0 mm | **given** — NopSCADlib E2020 `cwi`, never re-measured by hand |
| Slot depth (from face) | 8.0 mm | **given** — NopSCADlib E2020 `sq` |
| Slot lip thickness | 2.0 mm | **given** — NopSCADlib E2020 `t` |
| Lug slot-fit tolerance | 0.15 mm/side | **given** — the shelf bracket's proven starting point (6.2 rails ≈ 0.20) |
| Station A / B / C cable Ø | 4.0 / 6.2 / 8.0 mm | **assumed** — common cable standards, a session may re-pick |
| Cable retention | push-in, two flex tabs, removable by hand | **assumed** — a feel target the coupon prices |
| Lugs per clip | 1 hammer-head | **assumed** — a clip is light; 2-lug "comb" is a named follow-up |
| Body height above rail face | ≤ 14 mm | **assumed** — clear of adjacent T-nuts and brackets |
| Lug hook per side / engagement / length | 2.2 / 1.5 / 10 mm | assumed — the shelf bracket's T-nut-derived values, reused verbatim |

## Key decisions

1. **Snap loop, not drop-in.** The brief left open-top drop-in vs closed
   snap loop "on coupon evidence". Declined drop-in on geometry, not feel:
   the stated use is routing a cable along a (typically vertical) rail
   face, and an open loop cannot retain a vertical run — the brief itself
   notes "snap retains vertical runs". The coupon still prices the feel
   (the loop strip sweeps `cable_fit` 0.0/0.2/0.4).
2. **Everything is a plan-view profile extruded up.** The loop, throat and
   funnel live in the XY plane; the body is that profile extruded `body_h`.
   Every wall prints vertical, and — the `snap-cantilever-clip` CC1 rule —
   the flex tabs bend **in the layer plane**, so bending stress crosses
   roads inside a layer, never the bond between layers.
3. **The lug fin is the shelf bracket's proven geometry**, copied with
   parameters (`slot_mouth - 2*slot_fit_tol` neck, `mouth + 2*lug_hook`
   head, 1 mm neck burial, constant cross-section standing on the bed so
   the hammer head stacks as identical layers). One lug per clip (brief).
4. **Flex comes from thinning the front sector, not from thin walls
   everywhere.** The ring is `wall` (2.4) thick around the back (the mount
   side, backed by the web) and thins to `tab_t` (1.2) over a ±120° sector
   around the mouth — the tabs are the thin front arcs, rooted in the
   full-thickness wall behind the shoulders. `tab_t` is the highest-leverage
   feel knob (stiffness ∝ t³); `tab_bite` (0.8/side) sets retention.
   The relief's cut radius reaches past the ring (`ro + corner_r + 1`) so
   it also clears the web's rounded corners inside the sector — at `ro`
   they survived as knife-edge ears (0.07 mm, printcheck's thinnest wall;
   removing them took stations A/coupon to 100/100). The remaining
   printcheck WARNING on stations B/C (2% of samples, 0.09 mm) is the
   tab-tip lip — the ~15° corner where the thin floor arc meets the 45°
   funnel line, gear-tooth-class and accepted: it is the snap edge the
   cable rides over, and rounding it via a double-offset would reshape
   every corner (and risks minting slivers on tessellated arcs) for a
   cosmetic score.
5. **Retention asymmetry from plan geometry, not ramps on ramps.** The
   mouth funnel is 45° (easy entry); the catch is the vertical step where
   the throat land meets the bore — pull-out rides a steep face, so
   removing takes a firmer pull than inserting.
6. **The bore is a full circle in plan.** The only exit is the throat, so
   a vertical run cannot lift out even with zero cable tension holding it.
7. **Style `workshop-utility`** wired in from the scaffold (per brief):
   the back web's plan corners round at the style's `style_corner_r` (4,
   clamped where a small station demands), curves at `style_fn` (64), no
   text, no decoration. **Recorded style exception:** the
   `style_edge_chamfer` (0.6) bed-edge chamfer is NOT applied — a
   delta-offset chamfer narrows the 1.2 mm flex tabs by the chamfer on
   both faces, annihilating them in the bottom layer and leaving the loop
   front bridging over air at z = 0.6 (measured on the export; printability
   wins per CLAUDE.md, exception recorded here). A loop part's dominant
   curves are its bore/outer circles by necessity (the loop IS the
   design); the style's letter is honoured on every edge the shape shares
   with the family, and that inherent-shape tension is recorded here.
8. **`ci.fitchecks` proves the lug fits the slot.** The E2020 slot
   negative (face at x=0, mouth through the 2 mm lips, 12 mm cavity) is
   intersected with the production clip — zero facets expected — and a
   deliberately oversize neck (tol −0.15) must interfere: the check can
   fail.
9. **The plate is the deliverable** (`ci.plate`: the three stations as a
   multi-object 3MF, `scripts/plate.sh`) — three separately-printed parts
   must not ship as one fused STL. The lineup render is a preview.

## Print orientation

As modeled — plan profile on the bed, body extruding up, fin standing
against the back face. Nothing rotates between print and use except
standing the clip on its rail axis. No supports; brim 3–4 mm on the coupon
only (narrow fin strip) and on station A (smallest footprint) if the first
layer lifts.

## Print this first

The coupon (`tslot-cable-clip-coupon.scad`, auto-gated by `gate.sh`):
the production lug on a strip of the production back, plus three
production loop sections at `cable_fit` 0.0 / 0.2 / 0.4 (left to right,
station Ø set by `coupon_d`, default 6.2). Print it (~20 min) **before**
committing to a plate:

1. **Slot fit** — slide the lug strip into your real rail's side slot
   from an open end.
   - Slides with light drag, no wobble → print the plate with defaults.
   - Won't go in → raise `slot_fit_tol` 0.05 at a time (0.15 → 0.20 → 0.25)
     and reprint the coupon. 6.2-mouth rails need ~0.20 (set `slot_mouth`
     too).
   - Rattles → lower `slot_fit_tol` by 0.05.
2. **Loop feel** — push your real cable into each loop section in turn.
   - The section that snaps in with a firm push and holds the cable
     hanging is your `cable_fit` (bore = cable Ø + fit).
   - Won't go in at all → `tab_bite` down 0.1 or `tab_t` down 0.1 (stiffness
     ∝ t³ — the stronger lever).
   - Falls out of 0.4 and rattles in 0.2 → `tab_bite` up 0.1.
3. Print the plate with the tuned values.

## Field test log

(none yet — append FIELD-TEST entries per `templates/FIELD-TEST.md`)
