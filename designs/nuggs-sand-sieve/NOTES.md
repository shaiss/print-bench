# nuggs-sand-sieve — engineering log

## Goal

A **bathing-sand sieve end-cap** for the 80 mm-bore N.U.G.G.S. system (issue
#835): a shallow open basket whose floor is a printed grid, with one standard
genderless quarter-turn port face on the underside. Snap it onto the sand
bath's mouth (or any port), pour used sand in the top, shake gently — clean
grains fall through the grid and the open bore back into the bath below;
debris (seed husks, droppings, bedding scraps) stays in the basket to be tipped
out. The filter body the ecosystem's sand-bath workflow names but no module
served.

## Given / assumed measurements

| Measurement | Value | Source |
|---|---|---|
| Bore / port standard | 80 mm bore, full `nuggs_cfg()` defaults | given — `lib/nuggs-coupling.scad` |
| `port_tol` | 0.30 mm | given — **unmeasured**, coupon-tuned |
| Port projection / lugs | 10 mm / 3 | given — `nuggs_cfg()` defaults |
| Grid hole (clear opening) | 1.0 mm | assumed — passes 0.1–0.5 mm sand, retains 2–5 mm debris |
| Grid web width | ≥ 1.2 mm | given — repo wall floor |
| Basket inside depth | 25 mm | assumed — one bath's debris between empties |
| Open top inner Ø | ≈ 110 mm | assumed — matches sand-bath mouth (#667) |
| Working capacity | ≈ 250 mL | assumed — one sand-bath charge (#667) |
| Pour lip | chamfered ≤ 45° | assumed |
| Style | none | given |

## Key decisions

### Orthogonal square-opening lattice (not round holes)

**Round vs staggered-square** was non-blocking in the brief. v1 uses an
**orthogonal web lattice** of `web_w` bars leaving `hole_d` × `hole_d` square
openings. Reasons:

1. Continuous bars are what printcheck's thin-wall check actually sees — the
   same grammar as the hopper mesh, not a disc minus ~1000 cylinders.
2. CGAL cost of a thousand `cylinder()` differences at production `$fa/$fs`
   is untenable in CI; the bar union is ~2×`grid_n` cubes.
3. At equal clear opening (1.0 mm), sand grains (0.1–0.5 mm) still pass and
   2–5 mm debris still retains; the coupon tile is where a real grain sample
   gets checked.

If a later field test wants round holes, that is a parameter-shaped follow-up
(swap the bar lattice for a pierced disc), not a redesign of the basket.

### hole_d = 1.0 kept until printcheck says otherwise

Brief: if printcheck flags the webs, step hole Ø to 1.2 before any web drops
below 1.2. v1 ships at **1.0 / 1.2**. Gate observation recorded below under
**Gate results** once `gate.sh --slice` runs — do not thin `web_w`.

### Docking pose / run-length (brief open question)

**Maintenance kit, not corridor.** Precedence: the sand bath's own ruling
(PR #674 NOTES — destination / open module). This sieve docks onto a bath
mouth for a sift, or is hand-held over a bin; it is not left in a run as
passage. Geometry does not prefer either pose. **No run-length implication** —
it does not sit mid-run, so it neither breaks nor extends an enclosed length.
Recorded here per the brief; owner confirmation welcome at the PR.

### Capacity claim vs cylinder math

Parameter defaults `top_id = 110`, `basket_depth = 25` give a clear cylinder
of π·55²·25 / 1000 ≈ **237.6 mL**. The brief's ≈250 mL is the target band
(matching #667's assumed bath charge); G4 measures the `sandbody` mesh. No
geometry chase for the last 12 mL — depth and top Ø stay the brief defaults.

### Flare drain under the full-width grid

The grid spans the full basket ID so debris catches everywhere. Below the
floor, a ≤45° flare drains the outer annulus into the 80 mm bore — otherwise
sand that passed the outer cells would sit on a solid shelf. `flare_run =
basket_or − ro` pins the exterior at exactly 45°.

## Print this first

`nuggs-sand-sieve-coupon.scad` — one bore-clean port stub plus one grid tile
at production `hole_d` / `web_w` / `floor_t`.

1. Print the coupon in the **same filament** as the basket.
2. Mate the stub to any NUGGS port (or a second stub). If it scratches then
   firms past the tip, scrape elephant foot off the sector tips before
   touching `port_tol`. Tune `port_tol` in ±0.05 steps.
3. Drop a pinch of your bathing sand on the tile; grains should fall through.
   A 2–5 mm scrap should not. If grains lodge, step `hole_d` to 1.2 (keep
   `web_w ≥ 1.2`) and reprint the tile only.

## Print settings

- **Orientation:** as modelled — port axis vertical, sector tips on the bed,
  mouth up.
- **Supports:** none.
- **Material:** PLA or PETG.
- **Layer height:** 0.2 mm.
- **Infill:** 15 % in the flare/wall; the grid is solid bars.

## Gate results

Local `./scripts/gate.sh --slice nuggs-sand-sieve` (2026-10-12):

| Part | printcheck | slice | notes |
|---|---|---|---|
| `sieve` | **84/100** | ok (~12 h 47 m / 92 g) | WARN: 2 degenerate faces; small bed-contact patch (sector tips — family pose). Webs at 1.0/1.2 **not** flagged — hole_d stays 1.0. |
| `coupon` | **92/100** | ok (~2 h 18 m / 30 g) | 2 bodies intentional (stub + tile). |

Fitchecks: `mates` empty; `mates-ctrl` interferes (1060 facets).

### G4 — Must-fit/hold measured on exported STL

| Row | Claim | Measured | How |
|---|---|---|---|
| Bore | 80.0 | **Ø 80.0** (first solid at r = 40.0 at z = 0; r ≈ 40.05 at z = 5–10) | `contains` radial probe |
| `port_tol` / proj / lugs | 0.30 / 10 / 3 | library defaults via `nuggs_cfg()`; fitcheck mates clear | ci.fitchecks |
| Grid hole clear | 1.0 | **1.00 mm** open spans at y = pitch/2, z = 29.2 | slab `contains` |
| Grid web | ≥ 1.2 | **1.19 mm** solid runs (tessellation; pitch 2.2 − hole 1.0) | slab `contains` |
| Basket depth | 25 | **25.00 mm** | sandbody AABB |
| Top inner Ø | ≈ 110 | **Ø 110.2** (r = 55.1 at z = 32–50; lip flares to r = 56.1 at z = 54.5) | radial probe |
| Capacity | ≈ 250 mL | **237.5 mL** | sandbody mesh volume |
| Pour lip | ≤ 45° | 45° by construction (`lip_chamfer` equal radial/axial) | parameter |
| Envelope | — | **114.8 × 114.8 × 65.4 mm** (z = −10 .. 55.4) | sieve AABB |

`hole_d = 1.0` kept: printcheck did not flag the webs.

## Out of scope (v1)

- Woven steel drop-in replacement mesh — **named follow-up**, not v1.
- Hardware, adhesives.
- Washability gating (README care line only).

## Field test log

*(none yet)*
