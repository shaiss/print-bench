# Battery caddy — product charter

## The product, in one paragraph

A one-piece wall-mounted AA/AAA caddy whose lanes store a gravity-fed column
of cells and dispense them one-handed: printed spring blades pinch each
lane's bottom cell against a tunable release force. For anyone whose battery
drawer is a box of rolling cells; the one thing it must do well is *retain
and release reliably* — a cell never falls out on its own, and one pull
always gets one cell.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Cells fit their lanes (owner's real cells, not just IEC nominal) | bore = cell Ø + 0.4, cells calipered before full print | brief #704 Must-fit (IEC R6/R03 assumed) | owner calipers a different envelope |
| N2 | Retention feel: holds shaken; ~5–10 N one-handed withdraw | `finger_t` 1.3 default, coupon-tuned per material | brief #704 (design target) | field-test evidence the target is wrong |
| N3 | Mounts with 2 × M4, Ø 4.5 clearance, 16 mm pitch | exactly realized on the spine | brief #704 Must-fit | a different rail/screw standard |
| N4 | Prints support-free, back-down, repo FDM defaults (0.4 nozzle, walls ≥ 1.2) | printcheck 100/100, slice-verified | repo FDM conventions | printer constraint changes |
| N5 | One piece, nothing bought (no metal springs, no rubber) | design is monolithic | brief #704 assumptions | — |

## Out of scope

**Deferred** — free-standing drawer tray variant; 18650/CR123A lane sizes;
push-button ejection; a lid (inverted-spill is disclosed instead). All named
follow-ups in the brief, ranked below.

**Never** — metal parts or bought hardware in the retention path (the brief's
premise is printed compliance); a second printable part (v1 is one body).

## v1 — definition of done

- [x] Gate: render clean, `gate.sh --slice` exit 0, printcheck 100/100 on
      body + coupon, all five fitchecks pass with firing negative controls
- [x] Brief's Must-fit realized: bores, throat pinch, M4/16 mm mount
- [x] Coupon ships with a tuning walkthrough; README names it first
- [ ] Owner calipers their cells and prints the coupon (field test) — N1/N2
      close only on a real print

## Product page & shots (art direction)

**Page promise.** "Your batteries, on the wall, one pull each."

**Mechanism honesty.** The spring grip is the mechanism; the as-printed
`contact-sheet` (what CI slices, back-down) is embedded beside the posed
shots, and `blade-band` shows the as-printed spring geometry in cutaway —
no pose hides the print orientation.

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the whole rail, both lane groups | high 3/4 | 8f9aa6 / satin | — (bare part) |
| contact-sheet | what you print | 4-view | — | default |
| mounted | scale + loaded lanes in use | front iso | — | `part="use"` |
| blade-band | the spring mechanism, honestly | cutaway ortho | — | `part="section"` |
| dispense | the one-hand gesture | close-up | — | `part="use"` |

**AI product stills — tier 1.5.** None yet — reopen when the page needs a
photoreal bare-part angle the tier-1 set lacks.

**Lifestyle scenes — tier 2.** None yet — a workshop-wall scene seeded from
`product-hero` is the obvious first candidate when the design has field
testlog entries.

**Motion clips — tier 2.** None yet — a pull-to-dispense clip only after a
real print proves the motion (the `animations.conf` GIF would be the
motion-true artifact).

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Field-test the coupon, tune `finger_t` | closes N2; the only open acceptance row | one coupon print (~1 h 53 m, 22 g) |
| B2 | Free-standing drawer-tray variant (feet, no mount) | most-requested sibling per the brief | a derivative design, ~1 session |
| B3 | 18650/CR123A lane presets | extends the household coverage | parameters + a new lane group |
| B4 | Tier-2 lifestyle scene | page polish only | one AI shot |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Household cell mix (4+4 default OK?) | no | 4 AA + 4 AAA, all `-D`-tunable |
| Exact retention force | no | feel target via coupon |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-09-22 | Charter written from brief #704 at design-run ship | the brief is the owner-approved spec; transcription, not invention |
| 2026-09-22 | Fitcheck proxies at grow 0.3/0.7, not the brief's literal Ø 14.9 | exact-bore proxy is a coincident-face boolean (phantom facets); documented in NOTES.md |
| 2026-09-22 | Ø 4.5 M4 hole over the style's `style_hole_d` 3.4 | brief names Ø 4.5; recorded style exception, printability wins |
