# pop-fidget-card — product charter

## The product, in one paragraph

A print-in-place 1st-birthday keepsake card for the **parents of the birthday
kid** — the people who will stand it on a shelf and fidget with it during
phone calls for years. Bubble/"POP" party theme, four working mechanisms off
the bed in one piece, personalised with the child's name at slice time. The
one thing it must do well: **every fidget works on the first print** — a
keepsake that jams is a coaster.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Print-in-place: no supports, no assembly, nothing detachable | 0 parts to attach | brief #342 | never |
| N2 | Print time on the brief's printer class (stock MK4/Bambu-class 0.20 profile) | ≤ 120 min hard, 60 min target | filer, brief #342 | the filer relaxes the deadline |
| N3 | The child's name and the family's invitation stay out of the repo | `card_name = ""` default; no image | filer privacy choice, brief #342 | filer asks in writing |
| N4 | Product page carries the not-a-teether note | 1 visible note | keepsake-for-adults framing, brief | never |
| N5 | Mechanism clearances come from their proven sources, guarded by asserts | `xy_tol ≥ 0.15`, `engage ≥ 1.2`, `rise/t ≥ 2.3`, pip guards | captive-spinner / bistable-toggle / lib/print-in-place.scad | a coupon field test says otherwise |

## Out of scope

**Deferred** — third spinner (`spinner_count` already supports dropping, not
adding); tier-2 AI lifestyle scene; multi-color AMS profile; a portrait
variant.

**Never** — the real child's name in any committed file (N3); the invitation
image in-repo (N3); marketing it as an infant toy (N4); tuning the proven
rail/hinge clearances upward for looks (the acoustic-property lesson).

## v1 — definition of done

- [x] `gate.sh --slice` green: card + coupon + fitchecks (stop-angle negative control included)
- [x] N2 evidenced with both slice meters recorded in the PR
- [x] Previews committed (contact sheet, face, hero-iso, easel-open) + CI hero shot embedded
- [x] Easel props the card at 70–75° measured from the stop angle
- [x] Coupon ships with the "print this first" tuning ladder in NOTES.md

## Product page & shots (art direction)

**Page promise.** "A birthday card you can't put down" — the reader should
immediately want to flick something.

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| hero | the whole face: POP!, spinners, button, bead, the "1" flap | high 3/4 (20,55,1.0) | bubble-pink `e79ec6` / satin | — |

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Field-test the three tuned fits on a real printer, log FIELD-TEST | clearances are theory until one print | one coupon print |
| B2 | Tier-2 lifestyle scene (shelf with party detritus) | page warmth, after v1 | one manifest + CI run |
| B3 | Second greeting line (age/date) | reuse for later birthdays | small text-layout work |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| (none) | — | — |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-22 | Greeting re-set as an arced, per-letter bounced line pulled clear of the kickstand hinge | filer's direction mid-run: "letters a bit too close to the kickstand — be more creative with those" |
| 2026-08-22 | Slider re-based from the lib rail stack to a linear captive-spinner channel | rail stack needs 5.7 mm of wall a 2.4 mm card cannot host; NOTES.md has the math |
| 2026-08-22 | Card slimmed to 112 × 80 × 2.4, layout edge-derived | slice-clock data (CI round 1: 2 h 54 m on the gate's conservative meter) |
| 2026-08-22 | N2 evidenced by two meters (gate default + MK4-stock speeds) | the gate's bare-default profile is no printer's stock profile; brief names the printer class |
