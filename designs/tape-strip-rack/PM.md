# tape-strip-rack — product charter

## The product, in one paragraph

A desk rack that turns one pull of tape into a row of equal strips, for someone wrapping a pile of gifts with one hand holding the paper down. Two rolls ride a spindle at one end; both tapes run under a hold-down gate and along ten fins; scissors cut mid-gap; each strip stays stuck by its middle to a fin with both ends free. The one thing it must do well: **a strip is there to grab, one-handed, when the other hand is busy.**

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Blade-free. The page never says or implies it cuts tape | 0 printed cutters; "scissors" on the page | brief #1062; D1 in NOTES | a field-tested tear edge exists (B1) |
| N2 | Every part prints upright and without supports | 4 parts, 0 supports; the only bridge is the 22 mm gate lintel | brief #1062 | never |
| N3 | Every part fits a 220 mm bed, and the page says how tight the rack is | longest part 207.8 mm; `printcheck.args` holds 220 × 220 | brief #1062; print review | the owner names a smaller bed |
| N4 | The joint is a parameter with a print-this-first coupon | `joint_clear` 0.2 mm; coupon 44 min, 10 g | repo convention | never — it is the design's one tuned fit |
| N5 | The deliverable is the multi-object plate, never the assembled render | 4 objects in `build/tape-strip-rack-plate.3mf` | the multi-part-fuse field test | never |
| N6 | The page claims only what was measured: it needs scissors, a steadying hand and a 1 in core; a hanging rack is held by friction; the tape must be pressed down | stated in Print settings and Assembly & use | reviews for #1062 | a field test supports a stronger claim |
| N7 | No name or logo, and no measured dimension, taken from the commercial reference. The fin count (10) and the pitch (40 mm, about twice the tape width) are estimates read off the owner's photo; every other number is a stated default | 0 names, 0 logos, 0 measurements; 2 photo estimates | brief #1062, Open questions | never |

## Out of scope

**Deferred** — ranked in the backlog below.

**Never** — a metal blade (it would need hardware and a guard, and the page would have to carry a safety warning for a gift-wrapping tool); a merged single STL of the parts (N5); a claim that printed teeth cut polypropylene tape without a field test that shows it.

## v1 — definition of done

- [x] `gate.sh --slice tape-strip-rack` green: cradle, spindle, rack, end-cap and the joint coupon all 100/100 and sliced
- [x] `ci.fitchecks`: eleven proofs — joint as joined, pulled, lifted and dropped; spindle; rolls; nesting — with their controls
- [x] `build/tape-strip-rack-plate.3mf` builds as 4 distinct objects
- [x] Every *Must fit / hold* row of the brief re-derived from the exported meshes (NOTES, Brief audit)
- [x] Three independent reviews of the built geometry (layer-by-layer print truth, use walkthrough, code) with every should-fix item closed
- [x] "Print this first" procedure in NOTES and on the page
- [x] Frozen previews committed and `readme-gate.sh` green
- [ ] One real print recorded in NOTES — the six questions under Session-resume context (post-merge; nothing has been printed)
- [ ] The owner's publish decision (Open decisions)

## Product page & shots (art direction)

**Page promise.** Pull once, press, snip, and eighteen strips are waiting — and it says plainly which of those steps are yours.

**Mechanism honesty.** Nothing folds, snaps or prints in place, and every part but the spindle is shown as it prints: the assembled hero is also the print orientation of three of the four parts, and the spindle prints on end. The design ships `ci.fitchecks`, so `readme-gate.sh` requirement 12 applies and the `contact-sheet` is embedded. The `joint` shot shows the parts lifted apart, so the page cannot hide how they go together.

**Shot list — tier 1 (real renders).**

| Shot | What it sells | View | Look | Pose (`-D`) |
|---|---|---|---|---|
| product-hero | the whole rack as an object you would want on the table | 3/4 from the roll end | red, satin | `show_payload=false` |
| hero | what one pull leaves behind: two tapes, eighteen strips | 3/4 | preview colours | default |
| cradle | rolls, spindle and the gate the tapes pass under | close 3/4 | preview colours | default |
| pad | the palm pad the steadying hand presses | from behind and above the rolls | preview colours | default |
| section | the tape path: roll, under the gate, onto the fins | side, orthographic | preview colours | `part="cutaway"` |
| fins | ribbed lands and guide posts | close 3/4 | preview colours | `show_payload=false` |
| joint | the drafted dovetail key, under a rack lifted off it | low, from the side | preview colours | `explode=16 show_payload=false` |
| nested | two rack segments stored fin-into-gap | 3/4 | preview colours | `part="nested"` |
| coupon | what to print first | 3/4 | plain | coupon wrapper |
| contact-sheet | the assembled four-view; three of the four parts as they print | standard | preview colours | default |

**AI tiers.** None: no `product-still.conf`, `lifestyle.conf` or `motion.conf`.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | A pull-over tear edge on the cradle nose, shipped as a coupon experiment first | scissors are the one thing the user must bring; matte and paper tape may tear on a printed edge | one coupon, a field test, then a cradle change |
| B2 | A positive latch on the joint (a snap detent on the flanks) | a hanging rack is held by friction only, and the end cap lifts off with the tails | a flexure in the socket, a second tuned fit, a coupon |
| B3 | A presser that seats both tapes on a fin in one push | twenty fingertip presses per pull | one small part |
| B4 | Independent hubs with a centre wall | changing one empty roll currently lifts both | a second spindle part and a cradle variant |
| B5 | A coin ballast trough in the palm pad | the rack is about 3.3 N with rolls against a 2–8 N pull; ballast helps but two lanes still need a hand | a trough and a lid |
| B6 | Taller entry posts on the end cap, or a two-tape pull tab | both tapes must be landed 26.4 mm apart in a funnel that forgives 2.9 mm | geometry on one part |
| B7 | Debossed load-direction mark on the cradle walls | a roll loaded backwards feeds sticky side up | text or icon; thin-wall risk in printcheck |

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
| 2026-11-21 | Drafted drop-in dovetail, key on the downstream end | One clearance for every joint; it cannot pull apart along the rack |
| 2026-11-21 | Hold-down gate 3 mm above the tape plane | A level pull clears the fins; the tape cannot lift the spindle. The price is a fingertip pass to press the tape down |
| 2026-11-21 | Style `none` | The style pack's required rounding does not apply to a spindle or a finned rack, and there is no waiver |
| 2026-11-21 | Feet recommended, not modelled | A foot recess is a flagged overhang; a flat underside takes stick-on dots |
| 2026-11-21 | Palm pad, rounded free ends and a nesting proof added | The owner asked for the design to be refined; the rack slides unless held and a hand on the cradle lands on the rolls |
| 2026-11-21 | Joint draft 10° to 8°; carrying claim withdrawn | Review found a hanging rack is held by friction only; a shallower taper holds better, and the page now says to carry it from underneath |
| 2026-11-21 | 20 mm between the largest roll and the gate | Review measured 8 mm, with solid walls either side: no room to thread a full roll |
| 2026-11-21 | End-cap ledge ribbed like the fins | Review measured the flat ledge at ten times a fin's contact on the lightest, lift-free part |
