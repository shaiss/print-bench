# ovodyo — product charter

## The product, in one paragraph

A kinetic desk clock for makers and design-lovers: two faceted "dice-balls" that
tumble on brass stalks over an exposed truss and present the time on flat numbered
plaques — the hour on the left ball, five-minute steps on the right. It is a
showpiece that displays its own clockwork through a helical slot, not a quiet
utility object. Clean-room re-creation of Mectolab's "ovodyo"; the customer is
someone who wants to build and own a conversation-piece clock.

## Non-negotiables (the design's "soul")

Constraints that may **not** be weakened to make engineering easier. Each anti-
pattern below still scores 100/100 in print-bench's presence-only gates, which is
exactly why they live here.

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Two-tone is **cut-through geometry**, never paint: numerals and the slot are real voids to a red interior | 12 plaques + 1 slot cut through the shell | reference video/diagrams | a multi-material printer makes flush numerals read as through-cuts to a reviewer |
| N2 | **Tumble-to-index** motion: a fresh flat face lands upright at each stop, not a spin | built irregular yoke steps (≈54.7 / 62.7 / 180 / 305.3°); max landing error 1.62° — not a uniform 450°/90° index (reference quote was aspirational) | NOTES tumble stop table | never — this is the product |
| N3 | Heavy **faceted** spheres on **brass stalks** over a **genuinely airy** base | 12 pentagon plaques; base fills <25% of its bbox | reference | never |
| N4 | Honest colour code: **red = every working part** (gears, numerals, slot, core) | — | reference | never |

*v0 status:* N1 now holds geometrically — the numerals are **cut clean through**
the shell to a red interior (stencilised, island-free), alongside the real
through-slot (the tunable-brand-module part of [#601](https://github.com/shaiss/print-bench/issues/601) remains). N2 is not
yet truly mechanized — the base now carries a full *represented* drivetrain
(geared steppers + reduction gear-trains + bevel take-offs), but a real meshing
involute differential the kinematics gate proves lands a face upright is
[#604](https://github.com/shaiss/print-bench/issues/604). N3 holds (chamfered-dodecahedron faceted balls, brass
stalks, airy tapered truss). N4 holds in the preview (red = every working part:
gears, numerals, slot, core); a committed two-tone reveal render is [#600](https://github.com/shaiss/print-bench/issues/600).

## Out of scope

**Deferred** (in the [#599](https://github.com/shaiss/print-bench/issues/599) backlog), ranked:
1. **printable two-tone insert** (red inner half-shells under the seam mouth —
   N1-compatible, no paint; flush inlay is the readable form; composes with #604)
2. geodesic-ball lib (#600)
3. true stencil numerals (#601)
4. tapered space-frame base (#603)
5. real bevel differential + **ball-side stalk hub/socket** (#604 — brass rods
   seat in `base-end` today; the hero's "reaches the ball centre" is preview-only
   until the hub lands). The v0 `ci.plate` multi-object plate already ships.

**#602** (flat parting seam) **shipped** as the captive threaded seam — v1 box 1
then waits only on #601's stencil numerals.

**Never:**
- **Painted two-tone** — the colour comes from geometry + material, not paint (N1).
- **A hidden mechanism / solid base** — enclosing the gears or slabbing the truss
  kills the "mechanism as ornament" identity (N3).
- **A monochrome clock** — white-only or red-only reads as a different object (N4).
- **Electronics/firmware in this design** — the geometry design carries mounts and
  clearances; the controller, motors and homing are the builder's, documented not
  modelled.

## v1 — definition of done

- [ ] Balls are true cut-through stencil numerals (#601), gate-green (captive threaded seam already ships).
- [ ] Base is the tapered space-frame; deliverable ships as a multi-object plate.
- [ ] A real bevel differential that the kinematics gate proves lands a face upright.
- [ ] Product page shows the two-tone render (red reads through the cuts).
- [ ] Human approves the shape (taste is a merge decision, not a gate).

## Product page & shots (art direction)

**Page promise.** A desk conversation piece you can build this weekend: two
faceted dice-balls over an airy truss — honest about v0 (hand-set desk die; it
does not yet move), with the two-tone hero as intent and `what-ships` as what
arrives in single material.

**Mechanism honesty.** Contact-sheet (as-printed) stays embedded; hero may show
preview-only drivetrain and stalk joins, always captioned. `what-ships` sits
beside the banner, never replaces the hero.

**Shot list — tier 1 (real studio / OpenSCAD previews).** Frozen once reviewed;
new region = new camera line.

| Shot | What it sells | View | Look | Pose |
|---|---|---|---|---|
| hero | assembled clock intent (two-tone) | three-quarter | red preview + white | assembled |
| what-ships | single-material honesty | three-quarter | monochrome | `part="what-ships"` |
| hours-ball | one faceted die, numerals + slot | three-quarter | shell | `part="hours-ball"` |
| slot-path | #768 corner-crossing band | near-equator | shell (`render`) | `part="hours-ball"` |
| slot-window | aperture as a window | into the slot | OpenCSG red core | `part="hours-ball"` |
| base-mech-in-situ | drivetrain has scale + home | side | preview gears in truss | `part="base-mech-in-situ"` |
| contact-sheet | as-printed 4-view | iso/top/front/bottom-iso | — | default |

**Lifestyle scenes — tier 2 (AI, cosmetic, disclosed).** None — keep the page
on geometry-true renders until a PM deliberately asks for one.

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Owner `/decide yes` on #768 / merge PR #914? | Yes (merge) | Stay ready-for-review; geometry + page honesty land together |
| Household measure for ~20 g ball heft? | No | Keep grams until someone weighs a spoonful once |
| Bumper-recess lead-in chamfer on next base touch? | No | Queued to #603 |

## Decision log (recent)

| When | Decision | Source |
|---|---|---|
| 2026-10-24 | #768 chamfer normals + slot clip fixed; facet default kept 1.05 | issue #768 / PR #914 |
| 2026-10-24 | Ball-side stalk hub/socket deferred to #604; page carries interim display | Drik block → coach/PM fork (b) |
| 2026-10-24 | Vitamins bless Ø4 mm rod + tape shim (boss Ø4.9); Ø5 ream alternative | Drik used-it / PM triage |
| 2026-10-24 | What-ships monochrome preview beside banner (hero stays two-tone) | Drik used-it / PM triage D4 |
| 2026-10-24 | #604 note: numeral shadow-hole legibility at 288 indexes/day is a hot path once driven | Drik customer-sense / PM queue |
| 2026-10-24 | Re-rank #604: ball-side hub/socket **first** within the issue (demo ↔ chipped plaque) | Drik used-it / PM triage |
| 2026-10-24 | #601 approach: swap `text()` numerals for `lib/stencil-glyphs.scad` `stencil_text()` | Jane bench-sense / PM queue |
| 2026-10-24 | v0 desk-die framing adopted (until #604) | Drik customer-sense / PM triage |
| 2026-10-24 | Interim ballast-in-balls: packed pour blessed, loose shot forbidden (rattle) | Drik customer-sense / PM ruling |
| 2026-10-24 | Kinematics proof table resolved (landing-flat 10–11 empty; ctrls 236/108) | Drik hunch / NOTES hygiene |
| 2026-10-24 | Numeral legibility is a **v0** hot path (reads/day start day one), not only post-#604 | Drik used-it / PM triage → #601 |
| 2026-10-24 | New `slot-window` camera sells the aperture; base-mech embedded | Drik/Jane / PM triage |
| 2026-10-24 | `slot-window` reframed while unfrozen; three-description sync (README / cameras.conf / CAMERAS.md) — promise what the pixels show, not "red lit" | Drik used-it / PM triage |
| 2026-10-24 | Ridge-chord ~32 mm bridge disclosure in Print settings; `bays` retaste queued to #603 | Jane bench-sense / PM triage |
| 2026-10-24 | 220×220 extents note (every part clears; coupon longest); 256 mm two-plate stays recommended | Drik customer-sense / PM triage |
| 2026-10-24 | Slot-as-grip line on the desk-die usage path | Drik customer-sense / PM triage |
| 2026-10-24 | #604 test note: does a bare empty ball rest pole-down on a plaque without wandering? | Drik hunch / PM decline→queue |
| 2026-10-24 | In-situ caption: pods aren't mirrors — hours/minutes reductions differ (N2) | Drik hunch / PM triage |
| 2026-10-24 | #601 eyetest note: when a printed half exists, photograph at reading distance (~60 cm, desk lamp) | Drik used-it / PM queue |
| 2026-10-24 | #602 captive threaded seam marked shipped; printable red insert stays top-ranked #599 deferred | PM triage charter follow-up |
| 2026-10-24 | Care: hedged seam-as-release-plane + ambient lamplight clause; vitamins where-to-buy for Ø2 shot | Drik / PM triage |
| 2026-10-24 | N2 Number cell → built stop table (irregular steps); printable red insert ranked first above #600 | Drik / PM triage |
| 2026-10-24 | what-ships camera frozen as-is — caption carries grounded-ness; no reframe | Jane / PM triage |
| 2026-10-24 | CA-lock ballast after STABLE fill; brim-ON default for base-segment/base-end; slot-path green-artifact caption | Jane/Drik / PM triage |
| 2026-10-24 | #601 gains reading-distance land-check + new close-up camera when glyphs change; #603 gains bumper-recess lead-in | Jane/Drik / PM queue |
| 2026-10-24 | CAMERAS.md: base-mech-in-situ mid-base pose / #604 re-seat caveat; what-ships renderer-tint clause | Jane / PM triage |
| 2026-10-24 | Heft: ~20 g/ball unmeasured first guess; both-halves / seam-centred pack; tumbles-to-reading wording | Drik / PM triage |
| 2026-10-24 | #601 eyetest also covers slot-rim polish/patina after a month of handling | Drik / PM queue |
| 2026-10-24 | cameras.conf slot-corner comment synced to CAMERAS.md (freeze holds) | Jane / PM triage |
| 2026-10-24 | Ridge-chord finished look (~1 mm PLA droop); cross-thread diagnostic; X1/P1 front-left nudge; rod dry-fit; pour ~5 min tapping | Jane/Drik / PM triage |
| 2026-10-24 | #601 eyetest gains showroom-squint evidence (render "4"/"00" misread) + rim-wear look | Drik / PM queue |
