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
- [x] Easel props the card from the stop angle (v0.1: ~72°; v0.2 hinge field
      fix: ~76–80°, a deliberate trade for a rigid, grounded hinge — see log)
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
| B1 | ✅ **Done (2026-08-22 field test).** All four mechanisms printed and were assessed on a real Bambu-class PLA print. Spinners + slider: pass (spinner clearance +0.01). Button: worked, softened for PLA. Hinge: FAILED (living hinge) → fixed v0.2. Bubble-shine + named-greeting fit: failed → fixed v0.2. Log in NOTES.md. | clearances and the button's snap were theory until this print | done |
| B2 | ✅ **Done (2026-08-22).** Greeting v2 = auto-shorten when named + fit floor 4.5 → 5.0, field-validated by the owner's own workaround. Remaining sub-item (a second age/date line) deferred. | the name is the emotional payload; the field print forced the decision | done |
| B3 | Tier-2 lifestyle scene (shelf with party detritus) | page warmth, after v1 | one manifest + CI run |
| B4 | Second real print to confirm the v0.2 fixes (hinge, button, shine, greeting) and the +0.01 spinner clearance; promote to `printer.conf` if it agrees | v0.2 is one-print-validated on diagnosis but the fixes themselves are unfielded | one card print |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| _(resolved 2026-08-22 by the field test — see decision log)_ Greeting-line stroke floor: **auto-shorten** was chosen. The field print showed the full greeting + a 6-letter name did not fit, and the owner's own workaround was to shorten it — so the named card now auto-drops "BIRTHDAY" (`greeting_named = "HAPPY 1st"`) and the fit floor rose 4.5 → 5.0. | — | — |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-22 | Greeting re-set as an arced, per-letter bounced line pulled clear of the kickstand hinge | filer's direction mid-run: "letters a bit too close to the kickstand — be more creative with those" |
| 2026-08-22 | Slider re-based from the lib rail stack to a linear captive-spinner channel | rail stack needs 5.7 mm of wall a 2.4 mm card cannot host; NOTES.md has the math |
| 2026-08-22 | Card slimmed to 112 × 80 × 2.4, layout edge-derived | slice-clock data (CI round 1: 2 h 54 m on the gate's conservative meter) |
| 2026-08-22 | N2 evidenced by two meters (gate default + MK4-stock speeds) | the gate's bare-default profile is no printer's stock profile; brief names the printer class |
| 2026-08-22 | Owner-directed post-signoff round: per-mechanism CI fitchecks (spin/slide + falsifiers), animated previews (easel-fold, turntable), and an 8-config time sweep | owner asked to keep working the design in parallel experiments; every addition gate-checked |
| 2026-08-22 | 60-min bonus target closed as **measured-not-reachable** on the 0.2 stock profile with all four mechanisms (floor ≈ 67 min at `spinner_count=1`; NOTES has the sweep) | slice data across 8 configs, matrix-verified; the charter's "fidget set not gutted for the bonus" stands |
| 2026-08-22 | Jane's crescent-horn finding declined (soft horns are on-theme for bubbles) | triage ruling; re-enters with B1 field-test evidence |
| 2026-08-22 | **Crescent finding re-opened and fixed (v0.2)** — the field print confirmed the sub-nozzle horns slice away ("gets hidden and doesn't work"). Crescent → constant-width dot; guard added | the decline's own clause fired: field evidence overrode the on-theme ruling |
| 2026-08-22 | **Hinge field fix (v0.2):** grounded the flap root neck (0.36 mm floating flexure → 2.15 mm grounded rigid link) by shrinking the swing reliefs; accepted ~5–8° more upright prop (76–80° vs 72°) | field print cracked the unintended living hinge in PLA; a rigid hinge that props slightly steeper beats a flexure that fails. N5 held — the fix stayed inside the proven pip_hinge clearances, only the flap's own relief geometry moved |
| 2026-08-22 | **Spinner clearance N5 reopen (v0.2):** `xy_tol 0.20 → 0.21` | N5's "a coupon field test says otherwise" clause: the H2C print ran 0.20 slightly tight (+0.005–0.01) |
| 2026-08-22 | **Pop-button beam PLA-tuned (v0.2):** `tog_beam_t 1.5 → 1.3` | field print: bistable snap too stiff in PLA; PETG can return to 1.5. Bistability guard only gets safer as the beam thins |
| 2026-08-22 | **Greeting v2 (v0.2):** named cards auto-shorten to "HAPPY 1st, <name>!"; fit floor 4.5 → 5.0 | field print: full greeting + 6-letter name overran; owner's hand-shortening was the fix |
| 2026-08-22 | Kept `with_easel` default ON (fixed), not flipped to OFF | the easel is the headline "1" feature and the living-hinge failure is now fixed; the toggle exists and cleanly removes it for anyone who wants a plain card (owner's "defaultable off like any variable" — it is) |
| 2026-08-22 | **Hinge fix v0.3 — removed the tongue relief ramp entirely** (`ramp_h`/`ramp_run` deleted); tongue is now a full-thickness rigid link, fold is wholly the pin hinge | owner call on the reprint: "we have a real hinge, we don't need a living hinge too." v0.2 only *shortened* the ramp and left a ~0.8 mm ramped flexure at the tongue root — a living hinge in series with the pin. Interference sweep proved the ramp vestigial (free through 96°, plate-root chamfer is the real stop at ~97°); same prop angle, no thin flexure. Jane/Drik round found no gate/geometry issues — this was the one substantive item |
| 2026-08-22 | **Embossed "1" nudged down 1 mm** (cosmetic, off the fold line) | owner note "move the 1 so it doesn't fuse the kickstand"; the "1" already cleared the hinge by ~6 mm in the mesh (what looked fused on the v0.1 print was the living-hinge blob, now removed), so this is margin, not a fix. One-line to reposition if the owner wants it centred |
| 2026-08-22 | Reviewer-round doc polish landed in v0.3 (seam note names the hinge barrels; coupon-first names the hinge as the field-failure; card_name row tells long-name users to slice-preview; prop-angle stated two ways) | Jane + Drik in-session (CI reviewer chain account-down); all advisory, all doc-level, none blocking |
