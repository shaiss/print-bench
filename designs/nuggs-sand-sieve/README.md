# NUGGS sand sieve

A bathing-sand **sieve end-cap** for the 80 mm-bore N.U.G.G.S. system: a
shallow open basket with a printed grid floor and one standard quarter-turn
port on the underside. Pull the bath off the run and stand it port-up (sieve
mouth up on top), or hold the sieve over a bin — then pour used sand in the
top and shake gently. Clean grains fall back through the grid and the bore;
debris stays in the basket to tip out. Docking sideways while the bath is
still in the run wall dumps the pour on the floor. The maintenance half of
the sand-bath kit.

![Product shot](previews/product-hero.png)

![4-view contact sheet](previews/contact-sheet.png)

## What you get

- `sieve` — the basket end-cap (approx. Ø115 mm across the mouth, ~60 mm tall
  tip-to-rim; 80 mm bore, ~238 mL working volume above the grid).
- `coupon` — port stub + one grid tile at production hole/web sizes. Print
  this first; see [`NOTES.md`](NOTES.md).

One printed part. The port face is every `nuggs_cfg()` default, so it mates
with the sand bath, the straight, the elbow — any module on the standard.

![Grid floor from above](previews/grid.png)

## Print settings

- **Material:** PLA or PETG (PETG if you wash it often — sand is abrasive)
- **Layer height:** 0.2 mm
- **Infill:** 15 % grid
- **Supports:** **none** — flare ≤45°, walls vertical, pour lip 45°
- **Orientation:** as modelled — port axis vertical, standing on the coupling's
  sector tips, mouth up
- **Brim:** **recommended for the full basket** (sector-tip pose, small bed
  contact — printcheck warns under 5% footprint); optional for the coupon
- **Seam:** Back (or scarf) — stock Aligned can ridge the coupling ring and
  eat into `port_tol`

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `hole_d` | 1.0 mm | Clear grid opening (square). Passes bathing sand; retains 2–5 mm debris. Step to **1.2** if printcheck flags webs — never thin `web_w` below 1.2. |
| `web_w` | 1.2 mm | Web width between openings — the wall floor. |
| `basket_depth` | 25 mm | Inside depth above the grid. |
| `top_id` | 110 mm | Open top inner diameter — matches the sand-bath mouth. |
| `lip_chamfer` | 2.0 mm | 45° pour-lip depth at the rim. |
| `port_tol` | 0.30 mm | The fit knob. **Unmeasured** — tune on the coupon in ±0.05 steps. |
| `bore_d`, `wall`, … | 80 / 2.4 | The NUGGS standard. Changing these un-mates every module you already printed. |

All parameters are at the top of [`nuggs-sand-sieve.scad`](nuggs-sand-sieve.scad),
grouped in Customizer sections; override on the command line with
`-D 'hole_d=1.2'`.

![Section: port, flare drain, grid, basket, pour lip](previews/cutaway.png)

## Use & care

- **Fit:** push onto any NUGGS port face and twist a quarter turn. Tune
  `port_tol` on the coupon first if it rocks or binds (0.30 is the standard's
  default and has never been measured on a printer).
- **Sift:** pull the sand bath off the run and stand it **port-up** (mouth
  facing up), then quarter-turn the sieve on top — or hold the sieve over a
  bin. Pour used sand in, shake gently with **two hands when full** (smooth
  Ø115 exterior is intentional — no grip ribs), tip debris out. Re-seat the
  bath when done. Do **not** dock sideways while the bath is still in the run
  wall: that dumps sand on the floor.
- **Sand, not chinchilla dust:** fill and sift **bathing sand (0.1–0.5 mm
  grain) only — never chinchilla dust**, which is a respiratory irritant for
  hamsters. Same welfare line the sand bath carries.
- **Clear the lattice:** before washing, dislodge grains from the 1.0 mm cells
  with a soft brush from below or a reverse rinse — **no picks** (a pick can
  nick a 1.2 mm web).
- **Wash / heat:** hand-wash ≤ 50 °C, mild unscented dish soap, rinse and dry
  fully — **never a dishwasher** (the heated dry cycle exceeds even PETG, and
  a warped port is a narrowed bore). PLA/PETG at a room-temperature rinse is
  fine; food-safe claims are out of scope for v1.

## Follow-ups

A finer **woven steel drop-in replacement mesh** is a named follow-up, not
v1 — the printed grid is the subject of this design.
