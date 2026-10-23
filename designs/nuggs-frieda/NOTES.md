# nuggs-frieda — engineering log

Product page: `README.md`. The port standard this design consumes:
[`lib/nuggs-coupling.scad`](../../lib/nuggs-coupling.scad). The system
charter every NUGGS module inherits: [`designs/nuggs/PM.md`](../nuggs/PM.md)
(the reference consumer, archived at v0.1 — this design uses the extracted
library, not the archived design, so there is no `derives.conf`).

## Goal

A Word-World module: a NUGGS straight whose midspan is *made of* the
resident's name — **FRIEDA** wrapped around the tube as a structural letter
cage. Functionally it is a drop-in replacement for the nuggs straight
(same 160 mm face-to-face length, same port standard at the same defaults);
the letters are what it is *for*. The brief: "like Word World the object is
made of letters … the word is Frieda. you can mix case … as needed."

## Given / assumed measurements

| Value | Status | Note |
|---|---|---|
| The word: FRIEDA | **given** (2026-08-11) | Case left to the design ("mix case … as needed"); all-caps chosen — see decisions |
| Bore 80 mm, floor 70 mm | inherited, `nuggs` N1 | Asserted inside `nuggs_cfg()` |
| Per-run limit 2 × body length | inherited, `nuggs` N2 | This module encloses 180 mm; the rule is engraved on the part |
| `body_len_mm = 180` | assumed | Merck upper figure, same default as the straight |
| Port parameters | **standard defaults, unchanged** | The built port is exactly the config `lib/nuggs-coupling-mates.conf` proves assembles |
| PETG, 0.4 mm nozzle | assumed | Same welfare reasoning as `nuggs` (N7) |

## Key decisions

| Date | Decision | Reason |
|---|---|---|
| 2026-08-11 | **Double wall: the letters are a cage OUTSIDE a full standard tube, never the bore wall itself** | The load-bearing decision. A stencil tube (letters as the enclosure wall) puts every inter-glyph void within the animal's reach: anything between ~10 mm (cage-bar safe) and 70 mm (N1 full-passage floor) is a head-trap, and every glyph edge becomes reachable chew-initiation geometry (N6). Legible 55 mm letters cannot keep every void under 10 mm. The double wall keeps the bore a continuous standard NUGGS bore and every letter edge outside the enclosure, in the same reachability class as the straight's outer wall |
| 2026-08-11 | All-caps FRIEDA, not mixed case | Structure, not taste: every capital spans baseline to cap line, so every glyph anchors into both rails; x-height glyphs would miss the cap rail and a lowercase i's dot floats. The glyph table refuses non-caps with this argument in the message |
| 2026-08-11 | Glyphs are conformal: radial prisms intersected with the cage annulus | A flat letter chord across a 25°+ arc has a multi-mm sagitta — proud outside or shy inside. The intersection makes every letter exactly `sleeve_t` thick, following the cylinder |
| 2026-08-11 | `letter_kern` welds F→R and E→D (was 8 mm each; now 12 + mid-arm rib) | F's and E's free arm ends otherwise print as ~25 mm one-end-anchored cantilevers — the arm underside is a flat face appearing in mid-air. Welded to the next stem it becomes a short two-end bridge. The `weld-fr` preview camera watches this junction |
| 2026-10-23 | `letter_kern` 8→12 on F→R and E→D; mid-arm `weld_rib` | Jane round on `1013ffa`: fresh renders (not only committed previews) showed E as a three-tine comb and F's middle arm 3–5 mm short of R on the outer face — flat radial prisms meet at an angle, so kern that lands the top into the rail/neighbour can still leave the shorter middle arm open outside. Fix: kern 8→12 plus a circumferential `weld_rib` (rotate_extrude in the cage annulus at mid-arm height, spanning centre-to-centre + margin; no bore protrusion). A flat-prism arm extender cannot close a circumferential gap. Wordpair coupon prints the F→R junction for plastic confirmation |
| 2026-08-11 | Base/cap rails inset 0.2 mm radially from the letter faces | No rail surface is ever coincident with a glyph surface; coincident cylinder pairs have produced non-watertight meshes in this repo twice (`nuggs_sector()` header, nuggs-yard defect 3) |
| 2026-08-11 | Cage skirts are 50° cones, rooted past the bore into the tube wall | >45° keeps both skirt undersides self-supporting printed upright; 50° is the house angle. The root bite is the fuse (a kiss contact leaves CGAL counting bodies). `cone_bite` was raised from 0.8 to wall+eps (2.41) in #542 so Manifold's bore cut trims a clean skirt root instead of exporting a zero-area bore triangle |
| 2026-10-22 | No modelled brim ears; recommend a slicer brim and deburr | Removable ears cleared printcheck's small-bed-contact warning, but snipped ears leave nubs on the outer-sector tips that the animal can chew or rub — a welfare risk that depends on the owner deburring. Letter_kern welds, upright-on-port orientation, and `cone_bite = 2.41` stay. |
| 2026-08-11 | Marks engraved on the exposed tube bands, never on the cage | Same two rules as the straight: recessed never proud (N6), and only on faces that look at the room. Bottom band: `NUGGS PORT R1`; top band: `MAX RUN 360MM` / `COUPLINGS DONT RESET` — this module *will* mate with more of itself, so the per-run rule rides on the part |
| 2026-10-23 | `mark_h` 5→8, `mark_adv` 4.8→7.2 | Engraved welfare text at 5 mm was ~0.5 mm grooves — coin-flip on a 0.4 nozzle. 8 mm keeps stroke ≥ 0.8 mm so MAX RUN / COUPLINGS DONT RESET stay legible; advance scaled with height. Top mark band still has ~22 mm of tube (assert holds at `mark_band` 17) |
| 2026-08-11 | `cap_factor = 0.688` (Liberation Sans Bold) with a font-fallback assert | If the font falls back (DejaVu Bold, 0.729) glyph tops move +3.3 mm; the CAGE FIT assert proves they still land inside the 6 mm cap rail, so a fallback render fuses instead of poking through |

## Defects found this session

1. **Phantom wedges in preview renders.** Early OpenCSG previews showed a
   floating triangular wedge in glyph gaps (including the empty A–F span,
   where no geometry exists). Full CGAL render shows nothing at those
   coordinates and the mesh gates clean — it is a preview-compositing
   artifact of the letter-band intersection, not geometry. Judge this
   design's cage from `--render` shots or the exported STL, not from F5
   previews.

## Gate results (2026-10-23, issue #542 — weld close + mark_h + wordpair)

Reeve's daily score-regression detector reads CI `gate-run` telemetry, which
is rendered with **openscad-nightly `--backend=manifold`**. Local
`openscad` 2021.01 (CGAL) differs on the library-port sliver class — report
both. Manifold nightly was not available in this session; CGAL numbers below
are measured. Prior Manifold bridge was **84/100** on `1013ffa` (same
overhang area 1343 mm² and bed contact ~528 mm² this edit does not change) —
expect CI Manifold ≥80.

| Part | Renderer | Score | Remaining warnings |
|---|---|---|---|
| bridge | CGAL 2021.01 (local) | **76/100** | 1% unbridgeable overhang (1343 mm²) — letter-arm / weld-rib bridges; accepted. Small bed contact (527 mm² / 5% footprint) — slicer brim recommended. 8 zero-area triangles (shared `nuggs_port()` sliver class + rib unions; Manifold clears the port class) |
| bridge | Manifold nightly (CI / prior) | **84/100** on `1013ffa`; re-check on this head | same overhang + bed contact class |
| coupon | CGAL 2021.01 | **92/100** | 4 zero-area `nuggs_port()` triangles; 2 intentional bodies |
| wordpair coupon | CGAL 2021.01 | **92/100** | thin-wall sample on letter edges (coupon only) |

Before #542 the bridge was 76/100 on both renderers. Path 1 cleared the
Manifold bore degenerate (`cone_bite` past the bore). Removable brim ears
briefly cleared bed-contact (Manifold 92) but were removed on PM ruling;
with `cone_bite` alone Manifold is 84 and CGAL is 76. This round's weld rib
does not change the overhang mm² or bed-contact class.

- **Bore floor measured on the STL**, not trusted from the assert (the
  nuggs-yard lesson): inscribed bore ≥ **79.96 mm** at every enclosed
  station (z = 0, 20, 60, 75, 100, 140), against the 70 mm floor.

## Print this first — the coupons

`nuggs-frieda-coupon.scad` prints two bore-clean 25 mm port stubs
(`nuggs_neck`) side by side. Mate them by hand: push at the insertion
clocking, twist either way.

- **Won't seat / needs force:** raise `port_tol` 0.05 at a time.
- **Rattles when locked:** lower it 0.05 at a time.
- Start at **0.30** (the standard's default — proven in geometry by
  `lib/nuggs-coupling-mates.conf`, never yet tuned in plastic).
- Caliper the bore: under 79.0 mm means your printer is shrinking.

`nuggs-frieda-wordpair-coupon.scad` prints one F→R junction of the
production cage (`part = "wordpair"` — include-and-override, no copied
geometry). Hold it up to the light: the middle arm of F must fuse into R's
stem (same check `previews/weld-fr.png` watches). Minutes of print against
the ~16 h bridge.

## Print settings

- **Orientation:** upright, bore axis vertical, standing on one port's
  sector tips — exactly as it renders. Both cage skirts are 50° cones and
  self-supporting.
- **Supports:** none. Letter-band internals (arm undersides, counter
  ceilings, the cap-rail underside between glyph tops) print as short
  bridges anchored at both ends — that is what the F→R / E→D welds and
  mid-arm ribs are for. Keep auto-supports OFF: supports under the letter
  band land in the 1.6 mm sleeve gap and cannot be removed.
- **Material:** PETG preferred (N7 thermal reasoning); PLA prints the letter
  cage cleaner. In PETG expect slight underside droop on the letter bridges
  — cosmetic, not a failed print; slow bridge speed on the letter band.
- **Layer height:** 0.2 mm, 0.4 mm nozzle; tube wall 2.4 mm = 6 perimeters,
  cage shell 2.4 mm.
- **Seam:** Back or scarfed — avoids a full-height ridge on the word or a
  port sector.
- **Brim:** a slicer brim is recommended on the bridge — it stands 180 mm
  tall on three small sector tips. After the print: snap the brim, then
  deburr each sector tip until a fingernail drags across without catching.

## Open items

| # | Item | Why |
|---|---|---|
| F1 | Print the coupon and tune `port_tol` | Inherited standing item from the standard: the fit is proven in geometry, not yet in plastic |
| F2 | Print the wordpair coupon, then the bridge; inspect the F→R / E→D weld bridges at 0.2 mm layers | The weld turns cantilevers into bridges; bridge quality over ~8-15 mm spans at 2.4 mm thickness is printer-dependent. Wordpair coupon rehearses F→R in minutes |
| F3 | Other names | `name` + the A–Z advance table make any capital name renderable; the wrap assert bounds length (~7-8 caps at `letter_size = 80`, more at smaller sizes). A per-name kern review is manual: any glyph with free-ended horizontal arms (E, F, and to a lesser degree L, T) wants a weld to its right neighbour. Names *ending* on E/F/L/T have no right-hand weld target — check junctions against `previews/weld-fr.png` |

## Product-shot provenance

The committed `previews/lifestyle-bridge-in-use.png` and `lifestyle-product-hero.gif`
were generated **blind (text-to-image)**, before the pipeline gained image-to-image
seeding. The `seed=product-hero` field now in `lifestyle.conf` pins the shape to the
real mesh only from the **next re-roll** onward — it does not retroactively describe
the currently committed image.
