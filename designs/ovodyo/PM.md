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
| N2 | **Tumble-to-index** motion: a fresh flat face lands upright at each stop, not a spin | hours index 450°, minutes 90° | reference text | never — this is the product |
| N3 | Heavy **faceted** spheres on **brass stalks** over a **genuinely airy** base | 12 pentagon plaques; base fills <25% of its bbox | reference | never |
| N4 | Honest colour code: **red = every working part** (gears, numerals, slot, core) | — | reference | never |

*v0 status:* N1 is represented as debossed numerals + a real through-slot (true
cut-through numerals = [#601](https://github.com/shaiss/print-bench/issues/601)); N2 is not yet mechanized (mock
drive; real differential + verification = [#604](https://github.com/shaiss/print-bench/issues/604)/[#600](https://github.com/shaiss/print-bench/issues/600));
N3/N4 hold geometrically (two-tone shown only in the two-tone render, [#600](https://github.com/shaiss/print-bench/issues/600)).

## Out of scope

**Deferred** (in the [#599](https://github.com/shaiss/print-bench/issues/599) backlog): the geodesic-ball lib
(#600), true stencil numerals (#601), flat parting seam (#602), tapered
space-frame base (#603), real bevel differential + `ci.plate` deliverable (#604).

**Never:**
- **Painted two-tone** — the colour comes from geometry + material, not paint (N1).
- **A hidden mechanism / solid base** — enclosing the gears or slabbing the truss
  kills the "mechanism as ornament" identity (N3).
- **A monochrome clock** — white-only or red-only reads as a different object (N4).
- **Electronics/firmware in this design** — the geometry design carries mounts and
  clearances; the controller, motors and homing are the builder's, documented not
  modelled.

## v1 — definition of done

- [ ] Balls are true cut-through stencil numerals + a proper flat seam, gate-green.
- [ ] Base is the tapered space-frame; deliverable ships as a multi-object plate.
- [ ] A real bevel differential that the kinematics gate proves lands a face upright.
- [ ] Product page shows the two-tone render (red reads through the cuts).
- [ ] Human approves the shape (taste is a merge decision, not a gate).
