# over-center-toggle-clamp — product charter

## The product, in one paragraph

A print-in-place over-center toggle clamp for makers who hold small work on a
bench: no hardware, no assembly, mounts with two M5 screws, and grips a
0–25 mm workpiece with a self-locking lever that stays open and closed on its
own. The one thing it must do well: **hold 30 N without creeping open, and
toggle with a 8–15 N deliberate snap.**

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Jaw opening / depth / face height | 25 / 30 / 20 mm | brief #285 | owner re-briefs |
| N2 | Switch (snap) force | 8–15 N | brief; asserted from PRBM `F_handle` | coupon measures outside ±35 % |
| N3 | Holding force budget | ~30 N | brief; carried by the linkage lock + structure, not the flexure | a field test shows creep or yield |
| N4 | Base mount | 2× M5 at 40 mm centres | brief | owner re-briefs |
| N5 | Material | PETG/PP, never PLA | brief (flexure fatigue) | never for PLA |
| N6 | One print, no hardware, support-free flat pose | — | brief (print-in-place showcase) | a gate can't be met without supports |

## Out of scope

**Deferred** — box-lid variant (two clamps holding a lid), jaw pad inserts,
rail length options for wider openings.

**Never** — machine-threaded hardware mounts baked into the print (breaks the
no-hardware promise); styling beyond clean functional geometry (brief says
`style: none`).

## v1 — definition of done

- [ ] All five gate-contract boxes green (G1–G5, claim comment on #285)
- [ ] Coupon printed and snapped by a human; measured f_snap recorded here
- [ ] Clamp mounted, holds a 3 kg pull at the jaws without opening
- [ ] 50 toggle cycles by hand with no change in snap feel

## Product page & shots

The page sells "hardware-free workholding with a snap you can trust": lead
with the iso-open hero (the mechanism visible, lever thrown), then the
contact sheet, then the plan view that shows the jaw gap and mounts, and the
coupon last as the credibility beat ("measure your own PETG"). Tone: shop
tool, not toy — dimensions and forces up front, no lifestyle framing
(brief style `none`; tier-1 renders only, no AI tiers).
