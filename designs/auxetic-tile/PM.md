# auxetic-tile — product charter

## The product, in one paragraph

A **flat-printed re-entrant honeycomb** that gets wider when you pull it —
the negative-Poisson lattice the catalog did not have. The customer is the
catalog itself (credibility play for the advanced-technique mandate) and
anyone who wants to feel ν < 0 on their own PLA: one tile with an embossed
mechanism callout, a conventional contrast column, and a 3-cell coupon.
Compliance comes from **cell geometry**, not a designed joint.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Re-entrant angle stays printable | θ ≤ 45° from vertical | brief given — `docs/metamaterials-4d.md` §1 | a field test prints clean past 45° on this nozzle (then raise the assert, never silently) |
| N2 | Rib at or above the absolute floor | rib ≥ 0.8 mm (default 1.2) | brief + repo wall convention | measured single-extrusion ribs hold at < 0.8 on a 0.4 nozzle (unlikely) |
| N3 | Embossed values come from the same parameters as the geometry | always | brief ("spring-rate-ladder mold") + ladder N4 precedent | never — a hand-typed number on the strip is the one thing this product cannot ship |
| N4 | No mate / no `ci.fitchecks` | none | brief given — auxetics are coupon-based | a future derivative that adds a mating interface (separate design) |
| N5 | Emboss states mechanism + bound, not a promised ν | qualitative | brief assumption + metamaterials §1 strain caveat | a FIELD-TEST campaign produces a strain-conditioned ν worth embossing |

N1–N2 are `assert`s in `lattice_guards()`; N3 is `str()` from live parameters
plus an `echo()` for the gate log. All fail the render, not the reviewer.

## Out of scope

**Deferred** — in the backlog below.

**Never:**

- A promised numeric Poisson ratio on the emboss (N5).
- A `ci.fitchecks` mate (N4) — nothing mates.
- Promoting the cell generator to `lib/` in this PR (brief open Q → follow-up).
- A conforming pad / cuff / wearable derivative (application framing stays open
  on purpose so this stays one session).
- A style pack — measurement demonstrator, beside `spring-rate-ladder`.

## v1 — definition of done

- [x] `tile` — re-entrant lattice + conventional contrast column + solid
      border with embossed parameter/mechanism callout (120 × 70 × 8)
- [x] `coupon` — 3-cell strip with grip tabs
- [x] θ default 30°, hard max 45°; rib default 1.2 (≥ 0.8); cell edge 8;
      no mate
- [ ] `gate.sh --slice` green for tile + coupon; embossed-values echo present
- [ ] Product page passes `readme-gate.sh`; frozen previews committed
- [ ] A field test confirming the hand-stretch reads auxetic on a real print
      (owner's print; FIELD-TEST convention)

## Product page & shots (art direction)

**Page promise.** "Pull it — it gets wider. The negative-Poisson lattice,
printed flat in PLA."

**Mechanism honesty.** The as-printed `contact-sheet` (flat on the bed —
exactly what CI slices) is embedded beside the hero. A top ortho must show
the re-entrant cells and the conventional contrast column side by side so
the physics is readable without a second print.

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the whole tile as one honest object | 3/4, rotz 25 / elev 30 | teal `2a9d8f`, satin | none |
| contact-sheet | what actually goes on the bed | 4-view | — | none |
| layout-top | re-entrant cells + contrast + callout read as a diagram | ortho top | — | none |
| cell-close | one re-entrant cell resolvable | close 3/4 | — | none |
| coupon | the hand-stretch strip with grip tabs | 3/4 | — | coupon wrapper |

**AI product stills — tier 1.5.** None in v1.

**Lifestyle scenes — tier 2.** None in v1.

**Motion clips — tier 2.** None in v1 (the stretch is the field test's job).

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | FIELD-TEST: hand-stretch on PLA confirms wider-on-pull | the product's whole claim | one coupon print |
| B2 | Promote cell generator to `lib/` primitive (doc roadmap) | compounds; only after B1 | lib + demo + guards |
| B3 | Strain-conditioned ν coupon with a measured callout | upgrades N5 only with evidence | new coupon + procedure |
| B4 | Conforming pad / cuff derivative | application once the demonstrator lands | new design brief |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| none | — | — |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-11-07 | Emboss = mechanism + bound, not a ν value | brief assumption; metamaterials §1 strain caveat |
| 2026-11-07 | Include conventional contrast column | brief non-blocking open Q; sells the physics on the bed |
| 2026-11-07 | `cell_horiz = 10` (not equal to `cell_edge`) | equal-edge at 30° pinches neck to 0; 10 mm keeps neck ≈ 2 mm open at the 30° default. Neck guard (not the 45° printability max) caps the shipped defaults near ~33° — raise `cell_horiz` to push that cap toward 45°. |
| 2026-11-07 | No lib harvest in this PR | brief open Q → follow-up (B2) |
| 2026-11-07 | Brick auxetic rows at half-height; coupon free-sided | Round 1 (Drik block): full-pitch voids were isolated bowties; coupon rails loaded instead of cells. Tessellate so webs are `rib_width`; tabs attach to lattice ends only. |
