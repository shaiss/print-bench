# hex-bit-rail — product charter

## The product, in one paragraph

A bench-top rail that stores ¼″ hex driver bits standing up, for anyone whose
bits live in a drawer and cost a thirty-second dig every time. The one thing
it must do well: hold each bit firmly by its hex shank, tuned to the owner's
printer via a test coupon, and release it one-handed.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | The hex fit is a parameter, never a literal | `hex_fit` +0.1 default; coupon sweeps −0.15 / 0 / +0.15 | brief #594; issue #37 (measure the export) | never — the tunable fit IS the design |
| N2 | Bench dead-zone footprint | ≤ 200 × 40 mm (assert in .scad) | brief #594 | owner wants > 12 pockets per rail |
| N3 | Short-bit stick-up ≈ 13 mm | 25 − 12, bounded 12–15 (assert) | brief #594 (the grab) | bits shorter than ~22 mm overall |
| N4 | Pockets print as drawn, support-free | open-top bores, 45° mouth break | co-design rules; bore walls must not see first-layer squish or support scars | never — scars destroy the fit |
| N5 | Walls: ≥ 1.2 mm side, ≥ 2.4 mm between pockets after mouth breaks | asserts in .scad | FDM wall floor (3 perimeters) | fit sweep widened past ±0.15 without widening pitch |

## Out of scope

**Deferred** — ranked in the backlog below: magnet retention (needs a real
magnet's dimensions — a Must-fit row nobody has measured), per-pocket
bit-type label bosses (v1.1; glyph-legibility failure class `perspective-coin`),
wall-mount flange (brief #396's territory), path-traced studio hero shot.

**Never** — no latch, spring or moving retention mechanism in v1 (the press
fit is the mechanism; adding one is a new design). Never a merged single STL
of the two rails — the plate 3MF is the deliverable (the multi-part-fuse
field test).

## v1 — definition of done

- [x] `gate.sh --slice hex-bit-rail` green: rail-short 100/100, rail-long
      100/100, coupon 92/100 (degenerate-faces WARNING only), slices clean
- [x] `ci.fitchecks`: `fit-bit` renders empty, `fit-bit-ctrl` interferes
- [x] `measure_fit.py` exits 0 on the exported meshes (af/pitch/depth/footprint)
- [x] `build/hex-bit-rail-plate.3mf` builds as 2 distinct objects
- [x] "Print this first" coupon procedure in NOTES.md
- [x] Frozen previews committed + `readme-gate.sh` green

## Product page & shots (art direction)

**Page promise.** In ten seconds a stranger knows: this holds twelve ¼″ bits
standing up, the fit is tuned on a coupon so it works on their printer, and
printing it is one flat plate with no supports.

**Mechanism honesty.** No moving parts, so the fused-mechanism rule does not
bite — but the design ships `ci.fitchecks`, which makes it a "mechanism" to
`readme-gate.sh` requirement 12, so the as-printed `contact-sheet` is
embedded regardless. That is the right call anyway: it is the print-orientation
proof.

**Shot list — tier 1 (frozen `previews/cameras.conf`, rendered locally).**
No `shots.conf` this version (see decision log): the path-traced hero is
backlog B4.

| Shot | What it sells |
|---|---|
| rail-short | the product: twelve pockets, one row, mouths chamfered |
| contact-sheet | the as-printed pose (2×2 iso/top/front/bottom-iso) with ghost bits seated |
| rail-long | the deeper socket for long bits |
| coupon | the fit sweep with embossed values — the "tuned fit" story |
| cutaway | full-rail section through the pocket axis |
| cutaway-close | the section a reader can measure: depth, floor, mouth break |

**AI tiers.** None — no `product-still.conf`, `lifestyle.conf` or
`motion.conf`. A shop-bench lifestyle scene is plausible later; it would seed
from `rail-short`.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Magnet retention row (optional magnet under each pocket) | the brief's own named follow-up; strongest "bits fall out" ask | needs real magnet dimensions first |
| B2 | Per-pocket bit-type label bosses | organizing a full rail by bit type | print time; glyph legibility risk (0.25 mm engraving class) |
| B3 | Wall-mount flange | some benches have no dead zone | small print-time add |
| B4 | Studio hero shot (`shots.conf`) | page polish, not function | bpy/CI render minutes |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Which `hex_fit` does the owner's printer want? | no | coupon's −0.15…+0.15 sweep covers it; production default +0.1 |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-09-12 | Press fit is the only retention in v1 | magnet dims unmeasured (a Must-fit row nobody gave); brief defers it |
| 2026-09-12 | No `shots.conf` this PR | path-traced hero needs bpy/CI; frozen `cameras.conf` previews committed locally satisfy readme-gate; hero = B4 |
| 2026-09-12 | Coupon pitch 24, not the production 16 | embossed fit labels need ~22 mm each; pitch carries no fit, so the sweep is unaffected |
| 2026-09-12 | Labels welded into the wall, strokes fattened (size 6, spacing 1.2, offset 0.25) | glyph strokes are walls to printcheck's thin-wall rays: size 3.2 measured 0.2–0.4 mm → 25 % thin → CRITICAL (gate iteration 2) |
