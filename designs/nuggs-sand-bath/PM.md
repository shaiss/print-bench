# NUGGS Sand Bath — product charter

Chartered from brief issue #667 (the `design-brief` body is the source of
every row below; nothing here is invented). NOTES.md is the engineering log;
README.md is the product page. `/pm` enforces this file.

## The product, in one paragraph

The grooming module the NUGGS hamster-tunnel system was missing: an
open-topped bathing-sand dish that quarter-turns onto one standard 80 mm
NUGGS port face. The customer is a NUGGS owner adding the welfare station to
a habitat they already run. The one thing it must do well: hold ~250 mL of
bathing sand the animal walks into, rolls in, and walks back out of — with
the sand staying in the dish, not the run, and no supports anywhere.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Bore / port geometry comes from the shared interlock, never restated | 80.0 bore, 10.0 proj, 3 lugs | brief, *given* (`lib/nuggs-coupling.scad`) | the lib changes its own defaults |
| N2 | Port tolerance is untested on every printer — the coupon ships and the page says print it first | `port_tol = 0.30`, ±0.05 steps | brief, *given* — coupon **mandatory** | a FIELD-TEST entry measures the fit on a real printer |
| N3 | No slicer supports | 0.0 mm² >45° non-bridge overhang | brief printer row | a census of the export measures otherwise |
| N4 | The dish floor over the bore is a ≤45° vault, never a flat ceiling | raked rim 21.7°; no plane crosses the bore | brief printer paragraph (`docs/advanced-techniques.md`, Domain 2) | — |
| N5 | Containment lip crossed by smooth ≤45° ramps on **both** faces | lip 20; beach 42.27°, far ramp 44.16° (asserted) | brief, *assumed* (rim-saddle precedent) | the welfare rule itself changes |
| N6 | The page says **sand, never chinchilla dust** (respiratory) | one line in README | brief assumptions | — |
| N7 | Dish dimensions are parameters, not literals | all `-D`-overridable | brief assumptions | — |
| N8 | Everything printed — no hardware, mesh, or glued floor | zero fasteners | brief assumptions | a v2 brief says otherwise |

## Out of scope

**Deferred** — backlog below. **Never** (v1): multi-port in-run variant (its
own follow-up brief per the brief's own open-questions list); added hardware
or mesh floors.

## v1 — definition of done

Checkable by someone other than the author, beyond "gate green":

- [x] Every *Must fit / hold* row realised in a parameter and measured on the
      export (audit table in the PR)
- [x] Run-break ruling recorded in NOTES.md (not assumed) — owner confirms at
      the PR, per the brief's ask
- [x] README carries the sand-not-dust line and the coupon-first instruction
- [x] Coupon + `ci.fitchecks` (empty positive, interfering negative) ship
- [ ] Human approves the shape — the merge, by construction of `/design-run`

## Product page & shots (art direction)

**Page promise.** "Print one part, twist it on, pour sand: the bath your
NUGGS run was missing — no supports, no hardware."

**Mechanism honesty.** Not a mechanism (nothing folds, snaps, slides or
prints in place), so no posed-hero trap — but the as-printed pose is in the
set anyway: `contact-sheet` (what CI slices) is embedded beside the use-pose
hero, and `print-pose` exists in `cameras.conf`.

**Shot list — tier 1 (real studio renders).** Style is `none` — the port's
own geometry is the look.

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the bath as mounted: mouth up, port in the run wall | hero | `c9a86a` satin | `part="hero"` |
| contact-sheet | the printable truth — 4-view of what CI slices | default | — | default `body` |
| cutaway | the walk: bore → beach → floor → ramp | section | — | `part="cutaway"` |
| print-pose | support-free claim, staged skirts, three tips | from below | — | `part="body"` |

No tier 1.5 / 2 / motion tiers — nothing cosmetic between the geometry-true
render and the stranger's decision.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Lid variant (hinged or lift-off) | nightly sand containment (~100:1 vs transport — Drik usage math on PR #674); chew-safety, ventilation and bore-entry compatibility are the lid brief's open questions | a second part + its own gates |
| B5 | Single-stub coupon override + groove-witness patch | promoted #2 (PM triage 2026-10-11): `coupon_stubs=1` for keepers who already mate against a habitat port (~30 g / ~2¼ h) **and** a patch of fill-line groove so the coupon answers port fit + groove legibility in one print (Jane 1b + Drik D11); two-stub default stays deliberate until then. **Retire the fill-line camera when the groove-witness patch lands** (PM triage 2026-10-23 — concession closed the preview path; plastic proof is B5's job). | one `-D` path + coupon geometry |
| B2 | Multi-port in-run variant | explicitly out of scope v1; changes the run-break story | its own brief |
| B3 | `floor_run=140` + `max_build_height=250` for ≥250 mm printers | documented escape hatch in README; needs a real tall-printer field test | print time ~2× |
| B4 | Harness follow-up: printcheck 256³ vs slicer 200 mm ceiling mismatch | platform, not this design — flag in PR, file on the harness (#673) | an issue |
| B7 | `ci.cog` advisory for port dead-load moment | Drik: filled bath ~0.65–0.7 kg a hand-span out on one port; care line already rock-checks; advisory manifest is the cheap gate follow-up (low) | one `ci.cog` + densities |
| B6 | Turntable reveal + `hero-wide` companion | Jane bonus: chimney → dish by lying down, plus a wider hero crop (frozen `hero` stays for cross-round comparison; listing lead is `product-hero`); post-freeze cosmetic tier. **Third unchanged hero round** (PM triage 2026-10-23 at `ad39c8ab` — Jane [saw-it] crop note queued here, no reframe). | anim entry + new camera line + GIF/PNG budget |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Run-break ruling (owner confirm) | no | recorded: open top counts as a run break — destination, not corridor |
| Sand depth 15 vs 20 mm | no | 18 (welfare 2–3 cm + capacity trade); full 2 cm needs `-D sand_depth=20 -D lip_h=22` (lip−sand ≥ 2) |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-09-14 | Run break: **yes** (open module precedent) | the mouth is the whole top side — same "in open air" condition as a ≥180° window module; recorded, owner confirms at PR |
| 2026-09-14 | `sand_depth = 18` | welfare source says 2–3 cm (15 is the floor, not the target); 18 closes capacity under the 199 mm ceiling with lip−sand ≥ 2 |
| 2026-09-14 | Staged widening (tube → circle → dish) | census-measured 59.6° corners on the single hull; two hulls fit the 199 mm ceiling at 197.155 mm |
| 2026-09-14 | `printcheck.args` stays 256³ | family-consistent with NUGGS modules; the 200 mm slicer ceiling is this design's own assert; mismatch flagged as B4 |
| 2026-10-04 | Interior fill-line witness at `y_sand` | Drik first-customer nit on PR #674: first fill was eyeball + cup; a groove on the vertical trough walls at the existing fill plane (not a new height). B1 lid stays backlog, unteased. |
| 2026-10-11 | Fill-mark resized to 0.8 × 1.5 mm | Jane [saw-it] on PR #674: 0.4 × 0.8 mm printed as a ghost under the two-line floor; assert ceiling `dish_wall/2` = 1.2 still holds. New `fill-line` camera (freeze respected — `hero` untouched). |
| 2026-10-11 | B1 *why* rewritten (nightly containment) | Drik [customer-sense]: transport is ~2–5/yr; dig-kick containment is nightly (~100:1). Lid brief must pre-scope chew-safety, ventilation, bore-entry. |
| 2026-10-11 | Fill-mark depth 0.8 → 1.2 mm (`fill_mark_h` stays 1.5) | Jane [bench-sense] round 2 / Drik co-sign on PR #674: 0.8 sat on the engraved-feature coin-flip (~2 line widths); 1.2 is the asserted `dish_wall/2` ceiling ≈ 3 line widths. |
| 2026-10-11 | `fill-line` camera reframed pre-freeze | Both reviewers authorized: ~half distance, wall edge-on so the nick throws a shadow, floor-to-wall junction in frame; `hero` untouched. |
| 2026-10-11 | Fill emphasis flipped rim-relative-primary | Drik D10: mid-pour the groove is a fingertip feature; page now leads with "15 mm below the low rim" and the groove as tactile confirmation along both long side walls. |
| 2026-10-11 | B5 promoted #2, re-scoped | Single-stub override + groove-witness patch (Jane 1b + Drik D11); B7 proposed (ci.cog advisory); B6 gains hero-wide companion. |
| 2026-10-12 | Fill-line image adjudication + one-nudge bound | Jane r4 `[saw-it]` (nick still unread in `fill-line.png`) vs Drik 00:36 `[used-it]` (shadow visible). Committed PNG at `c081b578` corroborates Jane — interior wall featureless; stippled mid-wall patch is not a readable fill line. One last unfrozen `fill-line` camera nudge (~25–30° off wall normal, floor junction + interior corner anchored; `hero` untouched). **Bound:** if the regen still does not read, concede — do not iterate cameras further; rim-relative 15 mm line stays primary (README); B5 groove-witness patch carries the plastic proof. Embed of `fill-line.png` stays declined until a shot verifiably shows the nick. |
| 2026-10-23 | fill-line conceded per one-nudge bound, Jane r5 | Jane r5 confirms the post-nudge regen still does not read the nick. Conceded: `CAMERAS.md` caption rewritten to an honest wall/floor-junction description (no nick, no shadow claim); camera id + parameters unchanged; `hero` frozen; rim-relative 15 mm stays primary; `fill-line.png` embed stays declined; B5 groove-witness patch remains the plastic proof. |
| 2026-10-23 | Far-end containment closed (Bugbot High) | Empirically confirmed open: +Z ray from sand cavity exited to infinity; far-end sections were side stubs only. `far_wall()` now unions a `dish_wall` plate on the ramp plane after the cavity difference. Sand mesh still 245.5 mL. |
| 2026-10-23 | Far-end hollow tail trimmed (Bugbot Medium) | Empirically confirmed: through trough shell continued past `far_wall` outer face (~`ramp_run` open U-channel under the ramp). `far_tail_cut()` subtracts that half-space; wall overhang still ≤45°. Sand mesh still 245.5 mL; body slice ~11 h / 146 g. |
| 2026-10-23 | Docs pass (PM triage at `ad39c8ab`) | Coupon brim-knit sentence; rim-deburr already bold; filled-weight beside rock-check; page time ~10 h; FIELD-TEST #5 feel wording; ragged-rim adjudication = render tessellation + groove catching light (no camera move); B6 third unchanged hero round; B5 gains fill-line-camera retire note. |
