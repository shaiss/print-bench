# nuggs-frieda — product charter

## The product, in one paragraph

The **name bridge** of the N.U.G.G.S. system: a standard 80 mm-bore straight
whose midspan is wrapped in a structural letter cage spelling the resident's
name (default **FRIEDA**). Its customer is the owner of an adult Syrian
already running a NUGGS habitat who wants the animal's commute to say whose
bedroom it is — and, queued behind them, everyone who opens `name = "…"` for
their own animal. The one thing it must do well: be a **drop-in NUGGS
straight** (same port, same bore floor, same run rule) whose letters are a
second wall outside the enclosure, never a stencil of the bore. The rename
path *is* the product.

Enforced by `/pm nuggs-frieda`. Engineering log: `NOTES.md`. Product page:
`README.md`. Inherits the system charter [`designs/nuggs/PM.md`](../nuggs/PM.md)
(N1–N11) in full — every NUGGS module does; this file records only what this
module adds on top.

## Non-negotiables

Inherited from `designs/nuggs/PM.md` **N1–N11** in full (bore floor, per-run
limit, no dead ends, incline, one-action open, no bore protrusions / chew
geometry, hand-wash only, no commercial reducers, no tempered-glass drill,
one interlock standard, open-module arc floor). This module adds:

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1–N11 | As in `designs/nuggs/PM.md` | — | System charter; NOTES names the inheritance | Same reopen rules as the system |
| F1 | Double wall — letters are a cage OUTSIDE a continuous standard tube, never the bore wall | sleeve_clear ≥ 1.0 mm; bore unbroken | Head-trap / N6 chew argument (NOTES 2026-08-11) | Never while N1 and N6 stand |
| F2 | Free-arm letter welds close (F→R, E→D on FRIEDA; per-name for renames) | mid-arm rib + letter_kern; `weld-fr` camera | Printability: one-ended shelves sag in PETG | A rename whose junctions pass the weld check |
| F3 | No modelled brim ears on sector tips | 0 ears | 2026-10-22 PM ruling — snipped nubs are an N6 chew risk at mouth height | Never; slicer brim + deburr is the substitute |

*(Charter F1–F3 are this module's added non-negotiables. NOTES.md's open-item
series is numbered **O1–O3** so the two F-series never collide.)*

## Out of scope

**Deferred** — see backlog (elephant-foot OD lead-in; drain-claim wash check).

**Never:**
- **Modelled brim ears** (or any other owner-snipped nub on a sector tip the
  animal can reach). Welfare ruling 2026-10-22; brim is a slicer setting, and
  the page owns the deburr step.
- **A stencil-tube variant** (letters as the enclosure wall). Head-trap between
  ~10 mm and 70 mm; refused at the first decision.
- **A second joint or family-specific port.** N10 — this module consumes
  `lib/nuggs-coupling.scad` at the standard defaults.

## v1 — definition of done

- [x] Mates the shared NUGGS port at standard defaults (`nuggs_cfg()`).
- [x] Double-wall letter cage; bore floor STL-measured ≥ 79.96 mm.
- [x] F→R / E→D welds closed (kern + mid-arm rib); `weld-fr` camera watches F→R.
- [x] No modelled brim ears; README brim why-clause + fingernail deburr step.
- [x] Welfare marks engraved at stroke ≥ 0.8 mm (`mark_h = 8`).
- [x] Port coupon + wordpair weld coupon ship and gate.
- [ ] Port coupon printed and `port_tol` tuned on real plastic (system-wide).
- [ ] Wordpair coupon printed; F→R weld held up to the light (F2).

## Product page & shots (art direction)

**Page promise.** *"The tunnel that says whose it is."* A stranger should see
the name as the module, grasp that the bore inside is a full NUGGS straight,
and know to print the coupons before the bridge.

**Shot list — tier 1 (real studio renders).** Live via `shots.conf` /
`cameras.conf` / `animations.conf`. Frozen once reviewed — add a row, never
repurpose one. `weld-fr` is load-bearing for renames.

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the name cage as a finished object | hero | pink satin PETG / matte | — |
| contact-sheet | as-printed 4-view (overhang / bed tips) | 4-view | OpenSCAD preview | — |
| word-front / word-back | the letter relief and mark bands | mid-word | OpenSCAD preview | — |
| weld-fr | F→R arm fuse (kern + rib) | ortho close-up | OpenSCAD preview | — |
| turntable | the wrap in the round (GIF) | orbit | OpenSCAD preview | — |

**Lifestyle scenes — tier 2 (AI, cosmetic, disclosed).** Live:
`lifestyle.conf` / `motion.conf`. Geometry approximate; disclosures required.

| Shot | Seed | Scene |
|---|---|---|
| bridge-in-use (still) | product-hero | name bridge in a real habitat run |
| product-hero (clip) | product-hero | illustrative orbit of the named bridge |

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Print port coupon; tune `port_tol` | System-wide; gates every coupling | ~2 h / coupon |
| B2 | Print wordpair coupon; confirm F→R weld in plastic | Unique risk of this module; CI prices the coupon at 2 h 25 m / ~26 g | ~2.4 h |
| B4 | First-wash FIELD-TEST for drain + twist-grip feel | Page now hedges ("designed to drain"); restore or reword from evidence once the entry lands; also note grip feel on the letter cage after wash cycles | 1 wash cycle |
| B5 | Rename cookbook (kern recipes for common free-arm endings) | Rename path is the product; NOTES O3 is still manual. Cookbook must say the wordpair coupon follows `name` (junction 0–1 at the caller's kern), include a per-name recipe for rehearsing a *different* risky junction, and Jane's tip: photograph the coupon against a window | docs |
| B3 | 45° elephant-foot lead-in on the sector OD at Z=0 | Jane: bore has `bore_lead`, OD is bare; tips are both bed feet *and* mating lugs, so first-layer squish lands on a coupling surface — still gated on B1 plastic tune | small chamfer |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| PETG vs PLA as the page default? | No | PETG (N7 / habitat toughness); page already says PLA prints the cage cleaner |
| Add an E→D freeze-window camera / second coupon sector? | No | Closed 2026-10-23 — see decision log |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-11 | Double-wall letter cage, not a stencil tube | Head-trap / N6; see NOTES |
| 2026-08-11 | All-caps only; `letter_kern` welds free arms | Rail-to-rail anchor; cantilevers become bridges |
| 2026-10-22 | **No modelled brim ears; slicer brim + deburr** | Removable ears cleared printcheck bed-contact but left chewable nubs on sector tips (N6). Page must say *why* the brim and *how* to deburr (fingernail test) |
| 2026-10-23 | `letter_kern` 8→12 + mid-arm `weld_rib`; `mark_h` 5→8 | Jane: E comb / F mid-arm short on outer face; welfare marks under 0.8 mm stroke. Rib stays in the cage annulus (N6: no bore protrusion) |
| 2026-10-23 | Wordpair weld coupon ships | Drik: port coupon cannot rehearse the letter-bridge risk; CI sticky prices it 2 h 25 m / 26.16 g |
| 2026-10-23 | E→D: no second camera, no second coupon sector | Render covered by the shared rib mechanism (`weld-fr`, word-front/word-back); plastic by the hold-to-light check on the printed bridge; second sector deliberately not added this round (optional B2 ride-along if ever wanted) |
| 2026-10-23 | Drain claim hedged to "designed to" | No FIELD-TEST entry yet; B4 owns the evidence pass and any restore/reword |
