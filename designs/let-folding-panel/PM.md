# let-folding-panel — product charter

## The product, in one paragraph

A reference-quality LET (Lamina-Emergent Torsional) joint: two rigid panels
that fold to 90° from one flat-printed sheet, for a maker who needs a fold
where a pin hinge is overkill — no clearance, no assembly, no rattle, no parts
to lose. The one thing it must do well: fold to 90° and survive hundreds of
cycles without tearing. It is also the committed worked example of the
lamina-emergent family from `docs/advanced-techniques.md` (Domain 1), so it
must read as a *teachable* LET, not just a working one.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Folds to the target angle | 90° | brief (#388, given) | the owner changes the brief |
| N2 | Min feature thickness (torsion bar) | t ≥ 0.8 mm | brief + repo floor (2 extrusion widths) — `assert` in `main()` | a smaller-nozzle profile becomes the target |
| N3 | Root fillet at every finger↔bar junction | r ≥ 0.5·t | doc stress rule (given) — `assert` in `main()` | the doc's rule changes |
| N4 | Prints flat, no supports | 0 support mm³ | doc CC1 / "best FDM match" (the point of the family) | — |
| N5 | One piece, zero assembly | 1 part | brief (part breakdown) | the brief changes |

## Out of scope

**Deferred** (backlog below): a fold-*hold* mechanism (detent / over-center
lock — the joint is elastic and springs back); `lib/compliant.scad` extraction
(#202 — stays in the design file this PR); an `animations.conf` fold animation.

**Never:** printing it in PLA as a live flexure (doc fatigue ranking — it
cracks); a posed `demo_fold ≠ 0` model as the deliverable (a folded model is
not a printable model).

## v1 — definition of done

- [x] Renders clean; `gate.sh --slice let-folding-panel` exits 0 for the part
      **and** the coupon (both scored 100/100)
- [x] Fold-to-90° shown geometry-true (`previews/folded-pose.png`) and the
      as-printed flat pose shown too (`contact-sheet`)
- [x] Echoed K / σ / τ predictions in the render output as calibration
      starting points (brief asked for exactly this)
- [x] Coupon ships with a "print this first" tuning path (t for stiffness,
      L for tearing)
- [x] `readme-gate.sh` passes

## Product page & shots (art direction)

**Page promise.** "A fold, not a hinge — printed flat, zero assembly." The
stranger should grasp in one image that this prints *flat* and *becomes* a
90° joint by flexing.

**Mechanism honesty.** This design folds, so the as-printed `contact-sheet`
(default flat pose, what CI slices) must stay on the page beside any posed
shot — it is; the folded pose is a clearly-labeled preview, never the only
view. (No fusecheck here: it is one elastic piece, not a print-in-place pair.)

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| hero | the fold itself — panel standing, hinge visible | hero | teal #1f9e89 / matte | `demo_fold=95` |
| contact-sheet | the as-printed flat truth | 4-view | OpenSCAD default | none (as printed) |
| folded-pose | fold-to-90° evidence, fingers visible | frozen preview | OpenSCAD default | `demo_fold=95` |

**Lifestyle scenes — tier 2 (AI, cosmetic, disclosed).**

| Shot | Seed | Scene |
|---|---|---|
| scene | hero | the folded part in use on a desk — a phone stand / cable guide made of the folded panel |

(Tier 1.5 stills and motion clips: none yet — backlog.)

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Fold-hold mechanism (detent / over-center) | the most common real need — a fold that stays folded | a second small feature + coupon re-tune |
| B2 | `animations.conf` fold GIF | the mechanism sells itself in motion; page currently static | one manifest entry |
| B3 | `lib/compliant.scad` extraction (#202) | only pays when a second design needs it | lib file + demo + guards/mates confs |
| B4 | Panel-size presets (A6/electronics enclosure) | sizing is already parametric; presets are convenience | trivial |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Should the joint *hold* 90°, or only fold there? | no | fold-only in v1; hold is B1 |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-24 | Panels 70 × 45 × 3 mm (assumed) | brief left size open; 3 mm ≈ 10 perimeters keeps panels rigid vs the 1.2 mm bar |
| 2026-08-24 | t = 1.2 mm default (floor is 0.8) | headroom in the t³ stiffness budget; sweep tunes it per printer |
| 2026-08-24 | v1 folds but does not hold | a torsional flexure is elastic by nature; a hold is a second mechanism (B1) |
| 2026-08-24 | No `lib/` changes this PR | #202 candidates recorded in NOTES.md; extraction waits for a second consumer |
