# bar-buckle-mount — product charter

## The product, in one paragraph

A split clamp that grips a Ø22.2 mm flat handlebar and presents the
de-facto action-cam two-finger buckle receiver, so anything that ships
with that buckle — camera, light, remote, phone clamp — clicks on and
off the bar with no tools beyond the initial clamp install. For a
cyclist whose drawer is full of buckle accessories and whose bar is
bare. The one thing it must do well: **hold a genuine buckle against a
firm pull and release it on a thumb press, on a bar that matches ISO
4210.**

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Bar bore is the ISO 4210-2 22.2 mm grip section (other Øs are `bar_d`) | 22.2 mm | ISO 4210-2; brief #978 | A measured bar disagrees with the ISO section named |
| N2 | Buckle channel is community-measured, never guessed from memory | 28.6 × 4.9 × 25.6 mm + roof/guide table | Abbott 2014 `j-h-a/go-pro-mounts`; NOTES | Owner supplies a caliper set from a named buckle |
| N3 | Prints as-modeled, no supports; halves split on the bore axis | 0 support faces > 45° | brief #978; repo convention | — |
| N4 | Closure is purchased M5 + nyloc — no printed threads into plastic | M5×0.8 | brief #978 | — |
| N5 | Tuned fits ship with a print-this-first coupon | bore + buckle_fit ladders | repo convention; brief | — |

## Out of scope

**Deferred** — tool-free lever clamp; blank-plate sibling (same clamp,
plain back); field-measured buckle superseding Abbott 2014 numbers.

**Never** — printed threads into the clamp plastic; a one-off design per
bar diameter (use `bar_d`); guessing buckle geometry without a source.

## v1 — definition of done

- [ ] `clamp-receiver` and `clamp-plain` gate green (printcheck + test-slice)
- [ ] Coupon ships bore + buckle_fit open troughs + closed latch strip and gates green
- [ ] Bore on the export measures Ø(22.2 + bore_clear) ± 0.05
- [ ] Buckle channel on the export measures within 0.1 mm of the sourced table (+ `buckle_fit`)
- [ ] Product page passes `readme-gate.sh`; bill of hardware lists M5 + nyloc
- [ ] One real bar + real buckle field test recorded in NOTES (post-merge)

## Backlog (ranked)

1. **Field-measure a named buckle** — replace Abbott 2014 defaults if the
   owner's buckle disagrees; keep parameters, retune coupon. Retention is
   the hot path (~400–1,000 buckle cycles a year). Proving-ride notes fold
   in here: does the clamp rotate under a cantilevered camera bump, and
   does the fin wall survive a sideways knock?
2. **Blank-plate sibling** — same clamp, no receiver (brief non-blocking).
3. **Slimmer plain half** — bore + flanges only (shorter bolts, less
   glove-box bulk); re-derives the M5 length rule from `half_y`.
4. **25.4 / 31.8 presets** — documented `bar_d` pairs, not new designs.
5. **Tool-free lever variant** — explicit brief out-of-scope for v0.1.

## Open decisions

- **Buckle source set:** decided — Abbott 2014 community caliper numbers
  as the sourced stand-in for the brief's blocking measure-or-supply
  question; coupon + parametric knobs absorb a later field set.
  *Recorded at scaffold; the human's merge review is the approval.*
- **One-piece hinged vs two halves:** decided — two halves (NOTES #1).
- **Receiver orientation parameter:** decided — ship `buckle_rot` (0/1).

## Product page & shots (art direction)

**Page promise.** A stranger sees a bar clamp that takes the buckle they
already own — not another proprietary mount.

**Mechanism honesty.** Show the as-printed split-face-down pose (contact
sheet) and an assembled-on-bar view; never let a posed hero be the only
geometry-true view.

**Shot list — tier 1 (frozen OpenSCAD previews).**

1. `assembled` — both halves on a ghost bar, receiver outward (hero).
2. `receiver` — channel / roof lips / centre guide / latch window close-up.
3. `split` — both halves split-face-up so print orientation is obvious.
4. `coupon` — bore section + three open W/H troughs + closed latch strip.
5. `contact-sheet` — as-printed 4-view.

No AI tiers in v1 — the interface is the product.

## Decision log

- 2026-11-06 — charter written from brief #978 at design-run scaffold;
  buckle source set and two-halves orientation recorded.
