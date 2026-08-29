# bistable-toggle — product charter

## The product, in one paragraph

A monolithic bistable **push switch** — a pre-buckled fixed–fixed arch that
snaps between two stable states and holds either with zero power — for the
maker who wants a battery-free state-hold (a latch, a damper hold, a tactile
toggle) and for the compliant-curious who print it to *feel* the snap. The one
thing it must do well: **switch under a fingertip and hold**, at the briefed
3 N / 4 mm feel, on a stock FDM printer with no supports.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Switch force f_s (prediction, coupon-verified) | 3 N ± 0.2 | brief #389 | brief amended |
| N2 | Centre travel u_tr | 4 mm ± 0.1 | brief #389 | brief amended |
| N3 | Arch section floor w × t | ≥ 3 × 0.8 mm | brief #389 + repo two-perimeter floor; t ≥ 0.8 un-relaxable (the 0.82 fix bought clearance with material, never `--min-wall`) | never |
| N4 | Fixed–fixed arch, 2 stable states, `mid_rise/beam_t ≥ 2.3` (asserted) | ≥ 2.3 | brief #389 / arch mechanics | never |
| N5 | **The briefed interaction is deliverable by a hand**: the product's repeated action is *one motion of one finger, in both stable states* (PR #406 rounds 2–4 — the acceptance row no gate can check; a human verdict at review) | — | brief #389 "a push switch"; PM triage rounds 2–4 | brief amended via `accept-drag-switch-yes-no` |
| N6 | **Coupon fidelity**: a fix to the actuation path lands in the shared modules, so the calibration ritual teaches the same motion as the production part | — | PM triage round 4 (Drik `[used-it]` + Jane `[saw-it]`) | never |
| N7 | The opened cage still stops +Y over-travel — or the page says which duty moved where | stop_gap 0.4 | PM triage round 3 (Drik's rider) | never |

Rationale note under N5 (round 3): every CI gate asks *can the mechanism
move*, never *can a person make it move* — six green iterations shipped a
switch that couldn't be switched. That is why this row exists and stays human.

## Out of scope

**Deferred** — mounting-feature variant (screw bosses); lengthened coupon
cells matching production feel; see backlog.

**Never** — PLA or TPU builds (creep / modulus collapse — NOTES records why);
valve actuation as a pitch (never briefed; a monolithic bar carries no ports
or sealing — cut in round 1); relaxing t below 0.8 via `--min-wall`.

## v1 — definition of done

- [x] Gate green: production 100/100; coupon 92/100 on CI (thin-wall WARN: 2% of sampled surface under 0.8 mm — the sub-line-width label glyphs, the iteration-4/5 class; the four separate shells cost nothing), test-slices, fitchecks
      (empty + biting negative control).
- [x] Coupon sweeps the bistability threshold with negative controls.
- [x] A finger can switch it: one motion of one finger, in both stable
      states, on part *and* coupon cells (N5/N6 — reviewer-verified).
- [x] Product page: honest actuation + prediction framing, geometry-true
      hero + contact sheet, disclosed AI scene.
- [ ] FIELD-TEST entry with a real cycle count (B1 — post-merge).

## Product page & shots (art direction)

**Page promise.** Press it and it clicks to the other state and *stays* —
a battery-free state-hold you can print tonight, dimensioned from feel
targets you can verify with the coupon.

**Mechanism honesty.** The as-printed contact-sheet 4-view stays embedded
beside the hero (it is what CI slices); the AI lifestyle scene stays labelled
and captioned as geometry-approximate. The page may never claim an
interaction the artifact refuses (rounds 2–4's lesson).

**Shot list — tier 1.**

| Shot | What it sells | View | Look (color / finish) | Pose |
|---|---|---|---|---|
| hero | the whole mechanism: arch, proud stem, cage | low 3/4 (30,25,1.0) | red `d1495b`, satin | as printed |
| contact-sheet | as-printed truth, bed contact, overhangs | 2×2 iso/top/front/bottom-iso | — | as printed |
| coupon | the four-cell calibration story, labels legible | frozen cameras.conf line | — | as printed |

**Lifestyle scenes — tier 2.**

| Shot | Seed | Scene |
|---|---|---|
| lifestyle-scene | hero | the toggle at work on a desk — disclosed AI impression |

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | FIELD-TEST entry with cycle count (Drik's protocol: coupon + toggle on one plate, a week of flicking) | cycle life is the top open question no digital gate can answer | one real print, ~2 h / ~21 g |
| B2 | Seam reason swap (scarf seam; "stops mate on overload" as the true reason) | queue-tier text, third round at Jane's own tier | one line |
| B3 | Bold coupon labels (`Liberation Sans:style=Bold`) | legibility; re-kerns the iteration-5 fix so needs a gate re-run | .scad + gate run |
| B4 | Jane's filmed coupon die-out clip for the page | best explainer of bistability; needs B1's print and the owner's yes to the asset class | a video shoot |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Accept a real-print clip as a page asset class (B4)? | no | not until the owner says yes |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-24 | Round-1 triage: 11 act-now text edits, "valve actuator" cut | never briefed; page honesty |
| 2026-08-24 | Round 2: Drik's block upheld on the brief's "push switch" line; drag-only actuation is a different product | mechanism honesty (sweetheart-hamster class) |
| 2026-08-29 | Rounds 3–4: block upheld on an unmoved head; coupon-inheritance rider added (fix must land in modules); contingency `accept-drag-switch-yes-no` named but not fired | head byte-identical to blocked commit |
| 2026-08-29 | Push fix shipped: mirrored proud stems through lid/base windows, stops relocated to jambs at stop_gap, in the modules; accumulated text pass landed; this charter created (T3) | resolves N5/N6/N7 in one push, as round-4 triage scoped |
