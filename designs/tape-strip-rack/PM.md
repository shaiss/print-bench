# tape-strip-rack — product charter

## The product, in one paragraph

A desk rack that turns one pull of tape into a row of equal strips, for someone wrapping a pile of gifts with one hand holding the paper down. Two rolls ride a spindle at one end; both tapes run under a hold-down gate and along ten fins; scissors cut mid-gap; each strip stays stuck by its middle to a fin with both ends free. The one thing it must do well: **a strip is there to grab, one-handed, when the other hand is busy.**

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Blade-free. The page never says or implies it cuts tape | 0 printed cutters; "scissors" on the page | brief #1062; D1 in NOTES | a field-tested tear edge exists (B1) |
| N2 | Every part prints upright and without supports | 4 parts, 0 supports; the only bridge is the 22 mm gate lintel | brief #1062 | never |
| N3 | Every part fits a 220 mm bed | longest part 208 mm; `printcheck.args` holds 220 × 220 | brief #1062 | the owner names a smaller bed |
| N4 | The joint is a parameter with a print-this-first coupon | `joint_clear` 0.2 mm; coupon 33 min, 7 g | repo convention | never — it is the design's one tuned fit |
| N5 | The deliverable is the multi-object plate, never the assembled render | 4 objects in `build/tape-strip-rack-plate.3mf` | the multi-part-fuse field test | never |
| N6 | The page is honest about what it needs: scissors, a steadying hand or stick-on feet, and a 1 in core | stated in Print settings and Use | design review for #1062 | ballast lands (B3) |
| N7 | No name, logo or dimension taken from the commercial reference | 0 | brief #1062, Open questions | never |

## Out of scope

**Deferred** — ranked in the backlog below.

**Never** — a metal blade (it would need hardware and a guard, and the page would have to carry a safety warning for a gift-wrapping tool); a merged single STL of the parts (N5); a claim that printed teeth cut polypropylene tape without a field test that shows it.

## v1 — definition of done

- [x] `gate.sh --slice tape-strip-rack` green: cradle, spindle, rack, end-cap and the joint coupon all 100/100 and sliced
- [x] `ci.fitchecks`: joint, spindle and roll proofs empty; each control interferes
- [x] `build/tape-strip-rack-plate.3mf` builds as 4 distinct objects
- [x] Every *Must fit / hold* row of the brief re-derived from the exported meshes (NOTES, Brief audit)
- [x] "Print this first" procedure in NOTES and on the page
- [x] Frozen previews committed and `readme-gate.sh` green
- [ ] One real print recorded in NOTES — joint coupon first, then one rack and the cradle with a real roll (post-merge; nothing has been printed)
- [ ] The owner's publish decision (Open decisions)

## Product page & shots (art direction)

**Page promise.** Pull once, snip, and eighteen strips are waiting — and it says plainly that the snipping is yours.

**Mechanism honesty.** Nothing folds, snaps or prints in place, and every part is shown as it prints: the assembled hero is also the print orientation of three of the four parts. The design ships `ci.fitchecks`, so `readme-gate.sh` requirement 12 applies and the as-printed `contact-sheet` is embedded. The `joint` shot shows the parts lifted apart, so the page cannot hide how they go together.

**Shot list — tier 1 (real renders).**

| Shot | What it sells | View | Look | Pose (`-D`) |
|---|---|---|---|---|
| product-hero | the whole rack as an object you would want on the table | 3/4 from the roll end | red, satin | `show_payload=false` |
| hero | what one pull leaves behind: two tapes, eighteen strips | 3/4 | preview colours | default |
| cradle | rolls, spindle and the gate the tapes pass under | close 3/4 | preview colours | default |
| section | the tape path: roll, under the gate, onto the fins | side, orthographic | preview colours | `part="cutaway"` |
| fins | ribbed lands and guide posts | close 3/4 | preview colours | `show_payload=false` |
| joint | the drop-in dovetail, parts lifted apart | close 3/4 | preview colours | `explode=16 show_payload=false` |
| coupon | what to print first | 3/4 | plain | coupon wrapper |
| contact-sheet | the as-printed four-view | standard | plain | default |

**AI tiers.** None: no `product-still.conf`, `lifestyle.conf` or `motion.conf`.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | A pull-over tear edge on the cradle nose, shipped as a coupon experiment first | scissors are the one thing the user must bring; matte and paper tape may tear on a printed edge | one coupon, a field test, then a cradle change |
| B2 | Independent hubs with a centre wall | changing one empty roll currently lifts both | a second spindle part and a cradle variant |
| B3 | A coin ballast trough or a palm pad behind the rolls | the rack is about 2.5 N with rolls against a 1–4 N pull per tape | longer cradle, about 30 mm |
| B4 | A presser that seats both tapes on a fin in one push | twenty finger presses per pull | one small part |
| B5 | Debossed load-direction mark on the cradle walls | a roll loaded backwards feeds sticky side up | text or icon; thin-wall risk in printcheck |
| B6 | One-lane and three-lane presets with a joint sized to match | `lanes = 1` needs two joint overrides today | parameter work |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| The reference appears to be a commercial product whose listings carry patent claims (unconfirmed, from search-result text). Should a functional look-alike be published on the public site? | The owner's call at merge | Built as an independent parametric model with no branding and no copied dimensions; not merged by the build session |
| 40 mm or 50 mm strips as the default? | No | 40 mm, as estimated from the photo |
| Is 26 mm of fin height enough for the owner's scissors? | No | Yes; `fin_h` is a parameter |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-11-21 | No printed cutter; scissors cut mid-gap | The reference is very likely blade-free, and printed teeth were estimated not to press-cut polypropylene tape |
| 2026-11-21 | Every part prints upright | With no teeth, the on-side rack had no remaining advantage and forced an unprintable socket on the cradle |
| 2026-11-21 | Drafted drop-in dovetail, key on the downstream end | One clearance for every joint, and the chain lifts from the cradle |
| 2026-11-21 | Hold-down gate 3 mm above the tape plane | A level pull clears the fins; the spindle cannot be lifted by the tape |
| 2026-11-21 | Style `none` | The style pack's required rounding does not apply to a spindle or a finned rack, and there is no waiver |
| 2026-11-21 | Feet recommended, not modelled | A foot recess is a flagged overhang; a flat underside takes stick-on dots |
