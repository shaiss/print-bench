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
| 2026-08-11 | `letter_kern` welds F→R and E→D (8 mm each) | F's and E's free arm ends otherwise print as ~25 mm one-end-anchored cantilevers — the arm underside is a flat face appearing in mid-air. Welded to the next stem it becomes a short two-end bridge. The `weld-fr` preview camera watches this junction |
| 2026-08-11 | Base/cap rails inset 0.2 mm radially from the letter faces | No rail surface is ever coincident with a glyph surface; coincident cylinder pairs have produced non-watertight meshes in this repo twice (`nuggs_sector()` header, nuggs-yard defect 3) |
| 2026-08-11 | Cage skirts are 50° cones, rooted 0.8 mm into the tube wall | >45° keeps both skirt undersides self-supporting printed upright; 50° is the house angle. The root bite is the fuse (a kiss contact leaves CGAL counting bodies) |
| 2026-08-11 | Marks engraved on the exposed tube bands, never on the cage | Same two rules as the straight: recessed never proud (N6), and only on faces that look at the room. Bottom band: `NUGGS PORT R1`; top band: `MAX RUN 360MM` / `COUPLINGS DONT RESET` — this module *will* mate with more of itself, so the per-run rule rides on the part |
| 2026-08-11 | `cap_factor = 0.688` (Liberation Sans Bold) with a font-fallback assert | If the font falls back (DejaVu Bold, 0.729) glyph tops move +3.3 mm; the CAGE FIT assert proves they still land inside the 6 mm cap rail, so a fallback render fuses instead of poking through |

## Defects found this session

1. **Phantom wedges in preview renders.** Early OpenCSG previews showed a
   floating triangular wedge in glyph gaps (including the empty A–F span,
   where no geometry exists). Full CGAL render shows nothing at those
   coordinates and the mesh gates clean — it is a preview-compositing
   artifact of the letter-band intersection, not geometry. Judge this
   design's cage from `--render` shots or the exported STL, not from F5
   previews.

## Gate results (2026-08-11, local CGAL 2021.01)

- **bridge**: 76/100 PRINTABLE WITH CAVEATS — watertight, 1 body,
  24,416 triangles, slices clean (204.6 g PLA-equivalent, ~15 h 45 m).
  The caveats, all accepted: 3,822 mm² of >45° downward surface (the port
  sectors, the cap-rail underside between glyph tops, arm undersides and
  counter ceilings — all short two-end bridges by construction, none
  cantilevers after the kern welds); 527 mm² bed contact on the sector tips
  (identical to the nuggs straight — brim recommended); 4 zero-area
  triangles (the known `nuggs_port()` sliver class, nuggs backlog B1b).
- **coupon**: 84/100 PRINTABLE WITH CAVEATS — watertight, 2 bodies (two
  stubs, intentional), slices clean (66.5 g, ~5 h).
- **Bore floor measured on the STL**, not trusted from the assert (the
  nuggs-yard lesson): inscribed bore ≥ **79.96 mm** at every enclosed
  station (z = 0, 20, 60, 75, 100, 140), against the 70 mm floor.

## Print this first — the coupon

`nuggs-frieda-coupon.scad` prints two bore-clean 25 mm port stubs
(`nuggs_neck`) side by side. Mate them by hand: push at the insertion
clocking, twist either way.

- **Won't seat / needs force:** raise `port_tol` 0.05 at a time.
- **Rattles when locked:** lower it 0.05 at a time.
- Start at **0.30** (the standard's default — proven in geometry by
  `lib/nuggs-coupling-mates.conf`, never yet tuned in plastic).
- Caliper the bore: under 79.0 mm means your printer is shrinking.

## Print settings

- **Orientation:** upright, bore axis vertical, standing on one port's
  sector tips — exactly as it renders. Both cage skirts are 50° cones and
  self-supporting.
- **Supports:** none. Letter-band internals (arm undersides, counter
  ceilings, the cap-rail underside between glyph tops) print as short
  bridges anchored at both ends — that is what the F→R / E→D welds are for.
- **Material:** PETG preferred (N7 thermal reasoning); PLA prints the same
  geometry.
- **Layer height:** 0.2 mm, 0.4 mm nozzle; tube wall 2.4 mm = 6 perimeters,
  cage shell 2.4 mm.
- **Brim:** recommended. The part stands 180 mm tall on three sector tips
  with the cage's mass at mid-height.

## Open items

| # | Item | Why |
|---|---|---|
| F1 | Print the coupon and tune `port_tol` | Inherited standing item from the standard: the fit is proven in geometry, not yet in plastic |
| F2 | Print the bridge and inspect the F→R / E→D weld bridges at 0.2 mm layers | The weld turns cantilevers into bridges; bridge quality over ~8-15 mm spans at 2.4 mm thickness is printer-dependent |
| F3 | Other names | `name` + the A–Z advance table make any capital name renderable; the wrap assert bounds length (~7-8 caps at `letter_size = 80`, more at smaller sizes). A per-name kern review is manual: any glyph with free-ended horizontal arms (E, F, and to a lesser degree L, T) wants a weld to its right neighbour |
