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
| B1 | Lid variant (hinged or lift-off) | named follow-up in the brief; keeps sand in during transport | a second part + its own gates |
| B2 | Multi-port in-run variant | explicitly out of scope v1; changes the run-break story | its own brief |
| B3 | `floor_run=140` recipe for ≥250 mm printers | documented escape hatch already in README; needs a real tall-printer field test | print time ~2× |
| B4 | Harness follow-up: printcheck 256³ vs slicer 200 mm ceiling mismatch | platform, not this design — flag in PR, file on the harness | an issue |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Run-break ruling (owner confirm) | no | recorded: open top counts as a run break — destination, not corridor |
| Sand depth 15 vs 20 mm | no | 18 (welfare 2–3 cm + capacity trade); `-D sand_depth=20` |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-09-14 | Run break: **yes** (open module precedent) | the mouth is the whole top side — same "in open air" condition as a ≥180° window module; recorded, owner confirms at PR |
| 2026-09-14 | `sand_depth = 18` | welfare source says 2–3 cm (15 is the floor, not the target); 18 closes capacity under the 199 mm ceiling with lip−sand ≥ 2 |
| 2026-09-14 | Staged widening (tube → circle → dish) | census-measured 59.6° corners on the single hull; two hulls fit the 199 mm ceiling at 197.155 mm |
| 2026-09-14 | `printcheck.args` stays 256³ | family-consistent with NUGGS modules; the 200 mm slicer ceiling is this design's own assert; mismatch flagged as B4 |
