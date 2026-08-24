# pip-piano-hinge — product charter

## The product, in one paragraph

A Tier-2 **technique reference** in the #204 reference-design catalog: a
multi-knuckle print-in-place piano hinge that comes off the plate assembled and
swinging, demonstrating `docs/advanced-techniques.md` Domain 3 (hinges) and CC4
(offset, never scale) plus the xy≠z clearance split and per-knuckle axial play.
The customer is the **designer learning the technique** and the maker who wants
a parametric hinge to size; the one thing it must do well is *come off the
plate articulating ≥90° with the clearances the docs prescribe, and teach why*.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Bore grown by true `offset()`, never scaled | offset everywhere, 0 facets of interference | doc CC4; `ci.fitchecks` | A gate-proven offset construction is shown impossible |
| N2 | xy ≠ z clearance, z snapped to whole layers | 0.25 / 0.40 mm (2 layers) | doc clearance theory | A printer/profile is measured to need otherwise |
| N3 | Per-knuckle axial clearance, not a shared nominal | c_k = 0.6 + (2k+1)·0.05 | brief #390 tolerance-stacking row; doc Hinges | Shown to cause visible rattle without aiding freedom |
| N4 | Articulation measured, not posed | `fold90` empty; sliced STL = 3 bodies | brief #390; fusecheck discipline | — |
| N5 | Pin round (rotational symmetry inside the bore) | Ø4.000 measured | D1 finding (teardrop pin jams) | A fold-clearing non-round pin is demonstrated |

## Out of scope

**Deferred** — the ranked backlog below.

**Never** — editable `lib/print-in-place.scad` changes from this design (the
brief says design-first; candidates noted in NOTES D5, filed as #407); other
hinge styles (living hinge, flexure — other catalog children cover them);
style work (`Style: none` is the brief's decision).

## v1 — definition of done

- [x] `render.sh` clean; `gate.sh --slice` exit 0 including coupon
- [x] `ci.fitchecks`: pairwise clear + `fold90` empty + negative control fires
- [x] `ci.fusecheck`: 3 bodies on the sliced STL + `fused` control stays 1
- [x] Every *Must fit / hold* row measured on the export (NOTES D2/D3 tables)
- [x] NOTES records offset-vs-scale, per-knuckle derivation + stacking
      arithmetic, orientation decision
- [x] Product page passes `readme-gate.sh`
- [ ] Human approves the shape (the merge)

## Product page & shots (art direction)

**Page promise.** One print, three bodies, swings off the plate — and the page
explains *why* it swings (round pin, offset bore, split clearance) in one read.

**Mechanism honesty.** The as-printed `contact-sheet` (default pose) is
embedded beside the hero; the folded-pose is labelled a preview pose and its
`fold90` gate is named on the page. No posed shot is the only geometry-true view.

**Shot list — tier 1.**

| Shot | What it sells | View | Look | Pose |
|---|---|---|---|---|
| hero (shots.conf) | the hinge mid-swing, knuckles read | 40,25 iso | 8a8d91 satin | `demo_fold=100` |
| contact-sheet | the as-printed truth (4-view) | default | — | none |
| folded-pose (cameras.conf) | full articulation | 62° elev | — | `demo_fold=110` |

**Lifestyle — tier 2.** `lifestyle.conf`: `scene`, seeded from `hero` — a
workshop-bench staging (already committed; disclosed approximate).

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Lib fix/call for the teardrop orientation (#407) | Unblocks every future teardrop bore | one lib PR + mate/guard re-proof |
| B2 | `pip_hinge_pin_round` lib candidate (NOTES D5) | The round-pin lesson belongs in the lib | small module + mate case |
| B3 | Knuckle-count/length sweep preview | Sizing aid for makers | one cameras.conf line |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Lifestyle scene re-roll after geometry change? | No | Left committed (disclosed approximate); maintainer dispatch re-rolls |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-24 | Round pin over `pip_hinge_pin` | Teardrop pin cannot rotate (NOTES D1); measured |
| 2026-08-24 | Roof-up bore cut in-design, `pip_hinge` not used for knuckle | Lib points teardrop −Z (#407); reference design must be technique-true |
| 2026-08-24 | `clear_xy` 0.25 (was shared 0.4) | Doc spread range top = lib weld floor; z now handled by derived `clear_z` |
