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
- [ ] Hundreds of toggle cycles by hand (300+) with no change in snap feel
  (raised from 50 per Drik's year-one math: ~700–1,000 cycles/year — 50 is
  an unboxing, not validation)

## Backlog (ranked)

1. Physical validation — v1 boxes 2–4 above (the boxes that would have
   caught the round-1 sign error are the human ones)
2. Linkage-lock proof coupon (grip, not snap — the current coupon measures
   the arch only)
3. Coupon v2 film-strip predictor (two-rail 0.25-gap strip, ~2 g — Jane)
4. Jaw pad inserts
5. Rail length options for wider openings

## Open decisions

- **Locked band t\* (owner fork — route through `/decide`):** the round-2
  re-solve delivers a true over-center lock, but a fixed linkage locks a
  *band*: ~1.4–1.6 mm stock locked structurally (sized for 1.6 mm PCB),
  spring-assisted hold to ~6.3 mm, no hold above that, no contact below
  0.8 mm — other stock via `dead_center_gap` retune-and-reprint. That makes
  the opening promise ("grips a 0–25 mm workpiece") materially partial as a
  single print. Fork: **accept + disclose the banded grip** (the page
  already discloses it) **vs owner re-briefs** (e.g. adjustable/serrated
  jaw, a different mechanism). N1's 25 mm *opening* is met either way.

## Decision log

- 2026-08-29 — **Re-solve, don't re-scope** (PM triage on PR #414, Drik's
  block): the +5° seat sat before dead center and the flexure carried the
  hold (N3 violated). Landed: linkage re-solved at dead center
  (`dead_center_gap` 0.8 mm, seat −6°, crank 45→42, pivot −12.77→−6.29),
  torque direction asserted (`dp3_drad > 0` at the seat), locked band
  echoed. Re-scoping to "light-duty spring clamp" was declined.
- 2026-08-29 — **N6 floors** (Jane's block): plate tab under the
  printed-pose crank eye + sacrificial film shelves under the lever band,
  designed against the re-solved pose; "Supports: none" is true again.

## Product page & shots

The page sells "hardware-free workholding with a snap you can trust": lead
with the iso-open hero (the mechanism visible, lever thrown), then the
contact sheet, then the plan view that shows the jaw gap and mounts, and the
coupon last as the credibility beat ("measure your own PETG"). Tone: shop
tool, not toy — dimensions and forces up front, no lifestyle framing
(brief style `none`; tier-1 renders only, no AI tiers).

Tier-1 shot list, still owed (new frozen `cameras.conf` lines — the
open-pose set stays frozen as the review record):

- Workpiece-holding shot: the clamp closed on locked-band stock (render-only
  pose hook; the shot that would have caught the round-1 sign error)
- Low-angle under-lever shot: able to see under the lever band (the angle
  that would have caught the mid-air band)
