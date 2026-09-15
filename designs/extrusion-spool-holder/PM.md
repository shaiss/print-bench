# extrusion-spool-holder — product charter

## The product, in one paragraph

A one-print spool peg for people who store filament on 2020 T-slot
extrusion frames: it locks into any side slot from an open rail end and
cantilevers an axle the 1 kg spool drops onto and spins on its own bore.
The one thing it must do well: **the spool drops on and turns freely, with
zero hardware** — every other property (support-free print, one part,
coupon-tunable fits) serves that.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Lug geometry tracks the real 2020 slot: mouth / cavity / lip | 6.0 / 12.0×8.0 / 2.0 mm | NopSCADlib E2020 (slot ground truth, via extrusion-shelf-bracket) | a measured rail disagrees with E2020 (then fix the source, not this design) |
| N2 | Neck slides in the mouth with coupon-tuned clearance | 0.15 mm/side | family coupon value; user tunes ±0.05 on the coupon | a field test shows the family value wrong for this blade |
| N3 | Spool bore fit: stub under bore by coupon-swept clearance, stub ≥ spool width | 0.6 mm (sweep 0.3–0.9); 68 ≥ 66 mm | assumed 1 kg spool defaults (bore 52, width 66) | user's spool measurably outside (they `-D`, we don't redesign) |
| N4 | Standoff: rail face to spool | ≥25 mm (built 28) | brief #669 | the brief's number changes |
| N5 | Zero hardware, zero bearings | 0 vitamins | brief #669 | the owner explicitly reopens it (bearing variant is backlog B1, not v1) |
| N6 | Support-free print, walls ≥3 perimeters | trunk ≤38°, bridges ≤9.15 mm, walls ≥1.2 mm | repo FDM bar + printcheck (peg 92/100, only the intentional bridge warning) | printcheck regresses or a field print needs supports |

Each is backed by an `assert` in `extrusion-spool-holder.scad` (N1–N4, N6)
or by the BOM being empty (N5) — the render fails before a reviewer has to.

## Out of scope

**Deferred** — backlog below: 608ZZ bearing sleeve, studio product shot,
multi-speg rail plate, Bambu-bore preset.

**Never** — telescoping/adjustable axle (clamp creep + complexity against
a cantilever); other slot families (3030, 4040) without a measured brief;
metal inserts or printed threads in the load path (violates N5).

## v1 — definition of done

- [x] `render.sh` clean, bottom-iso inspected; `gate.sh --slice` exit 0
      (peg + coupon + all four fitchecks, negative controls firing)
- [x] Mesh measured against every brief number (NOTES.md table)
- [x] `readme-gate.sh` passes; previews frozen with CAMERAS.md
- [x] Page documents the vertical-rail friction margin honestly
- [ ] Owner reacts to the previews and merges (the human gate, by design)

## Product page & shots (art direction)

**Page promise.** "Drop a 1 kg spool on a peg that locks into your
extrusion — no hardware, no bearings, no supports."

**Mechanism honesty.** No mechanism here (single rigid part), but the
as-printed `contact-sheet` is embedded first regardless — what CI slices
is what the page leads with.

**Shot list — tier 1** (all committed locally from `cameras.conf`; no
`shots.conf` in v1 — a studio hero is backlog B2):

| Shot | What it sells | View | Look | Pose |
|---|---|---|---|---|
| contact-sheet | as-printed truth | built-in 4-view | neutral preview | default |
| peg-hero | the whole part reads in one look | ¾ from above-front | neutral preview | default |
| peg-bed | support-free print pose | from below | neutral preview | default |
| coupon | tune before you commit 4 h | strip, labelled rings | neutral preview | default |
| lug-closeup | the T-lug engagement reads at size (head 10.4 over neck 5.7) | dead-on along the blade at bed level; stub exits frame top by design | neutral preview | default |

Tier 1.5 / 2 (AI stills, lifestyle, motion): none in v1 — nothing to
disclose, nothing to fake.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | 608ZZ bearing sleeve variant (stub prints a bearing seat, bore spins on the bearing) | the biggest friction drop, but breaks N5 for v1 — needs the owner to reopen it | reprint stub section ~30 g |
| B2 | `shots.conf` studio hero + README lead image | page sells better; zero geometry risk | CI renders; ~0 local |
| B3 | Multi-peg rail plate (2–3 spools on one bracket) | real once one peg works; blocked on field test | new part ~80 g |
| B4 | Documented `-D` presets for Ø55 / Ø30 spools | cheap help for common spools; already works via parameters | docs only |
| B5 | Mechanical anti-slide (T-nut pocket in plate) if field tests show creep | only if the honest margin actually bites | small geometry change + re-gate |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Vertical-rail retention acceptable as-is? | no | documented honestly (README step 4 + NOTES load case); field test decides B5 |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-09-14 | Print pose rotated a quarter turn from use pose | only orientation where the stub is support-free and the lugs print flat |
| 2026-09-14 | Through-cut stub bore | enclosed 41.4 mm ceiling is an unprintable bridge |
| 2026-09-14 | Ø58 shoulder as inboard keeper | spool seats on a ring it cannot pass |
| 2026-09-14 | v1 ships no `shots.conf` | previews render locally with zero CI credentials; studio hero deferred to B2 |
| 2026-09-15 | Added `lug-closeup` frozen camera | Jane's freeze-window finding — the T-lug engagement had no close-up; added before any reviewer round, so nothing reframed |
