# N.U.G.G.S. Turnaround Node

The **run-resetter** for the N.U.G.G.S. hamster-tunnel system: a widened
chamber carrying the standard genderless quarter-turn port on **two faces**, so
an adult Syrian can enter one port, pivot 180° on a shallow dish, and leave the
other — doubling a run back on itself. This is the module that makes layouts
larger than one straight tube legal: the welfare rule caps any continuously
enclosed run at two body lengths between *breaks*, and a chamber this wide that
is itself open to ventilated air is one of only three breaks.

![Studio product shot of the turnaround node](previews/product-hero.png)

![4-view contact sheet](previews/contact-sheet.png)

> **Work in progress — nothing in this system has been printed yet.** The node
> passes `gate.sh --slice` (printcheck + a real test-slice, support-free), but
> `port_tol = 0.30` is an untested guess inherited from the shared standard.
> **Print the coupon first** (see Assembly & use) and expect to tune it.

## Where a turnaround belongs

It is the counterpart of the [den](../nuggs-den/README.md), and the opposite
job: the den is a dead-end **refuge** (too narrow to turn in, does *not* reset
the run count); this is a **pass-through** wide enough to turn in, which does.
Put it wherever a run has to double back — along a wall, or at the end of a
shelf-line (closed loops: pending the N2 source read — the family charter has
only checked the open-run rule). The two ports are parallel and 97 mm
apart, so the modules mating them leave side by side; that spacing is derived
(`≥ 2 × port radius`) so two mating modules never collide. The full rule and
its source live in [`designs/nuggs/PM.md`](../nuggs/PM.md) (N2) and
[`docs/nuggs-research.md`](../../docs/nuggs-research.md).

## What you get

- `turnaround` — the node (≈ 99 × 205 × 195 mm at defaults): an oblate chamber
  over a solid web, two Ø80 mm ports on the underside, six ceiling vents.
- `coupon` — the standard NUGGS port stub (~21 mm, ~2 h 17 m to print) for
  tuning the joint fit before you commit ~21 h of printing.

The port faces the hero can't show are in the 4-view contact sheet's
bottom-iso quadrant — the port-face view, both rings on their sector feet —
and, at first-layer resolution, in
[`bed-contact.png`](previews/bed-contact.png).

![Three-quarter view of the node](previews/hero.png)

## The three things the shape is doing

- **A dish, not a floor.** The chamber floor is the widened bowl's own curve,
  and it meets each bore mouth ~1 mm *below* the bore floor — the route steps
  down, never onto a lip. The grade across the dish peaks at **14.6°**, inside
  the welfare ceiling of 15°, and eases to flat at the bottom of the bowl.
- **A hipped vault, not a dome.** An enclosed near-flat ceiling cannot print
  support-free, and a domed crown over a chamber this wide would be one. The
  chamber closes instead on a **hipped vault** — roof planes at ~46° meeting
  at a ridge, hipped at the same angle down into the ends. Because the
  ceiling is the pointwise *minimum* of the chamber and those planes, the
  cavity cannot run past the shell anywhere — closing the end windows that
  rule now guards against was issue #499. Every surface self-supporting by
  construction; that shape took the printcheck overhang figure from 9% to 2%
  of surface.
- **Vents where the air is.** Six Ø9 mm teardrop vents on the use-ceiling,
  the same count and size the den's chimney derivation gives, over ~2.4× the
  air volume with the same one-animal occupancy. Open to ventilated space is
  what makes the chamber a *legal* run break, not just a wide room; the
  teardrop profile prints support-free and gives a gnawing incisor no purchase.

![Section through both port axes — bores, web, dish handoff](previews/cutaway.png)

![Section across the turn axis — the vaulted crown over the dish](previews/cutaway-cross.png)

![Crown profile, dead-on — the two roof planes and ridge of the vault](previews/cutaway-profile.png)

![Section along the turn axis — the vault hipped down into the end](previews/cutaway-ridge.png)

## Print settings

- **Material:** PLA preferred; PETG if it must live warm — expect a sagged
  web underside, and slow the roof overhangs.
- **Layer height:** 0.2 mm.
- **Infill:** 15–20 % is plenty; the shell does the work.
- **Seam:** Back (or scarf) — same setting for the coupon and the node; stock
  Aligned stacks a ridge on the port collar that reads as `port_tol` too
  tight.
- **Supports:** **none needed.** Ports down on their sector tips, the bore
  ceilings close at the coupling's proven 45° class, the web is a 12 mm
  anchored bridge, the belly dome is pole-flush on the bed, and the crown is
  the hipped vault above. The whole part is support-free as modelled. Keep
  auto-supports **off** even if your slicer offers them: anything it builds
  inside the chamber is unreachable through six Ø9 mm vents.
- **Orientation:** as modelled — both ports down, sector tips on the bed, the
  chamber up. Do not rotate it.
- **Brim:** off. Only the sector tips touch the bed (the web is the bridge at
  the port plane, 10 mm up), so the first ~50 layers print as twelve small
  islands that merge at the port plane — expected, not a fault. A brim would
  weld across the mating feet. Give it a clean sheet and no draft over the
  bed, and watch the first hour — twelve free-standing islands is where a
  21 h print dies if it's going to.
- **Heads up:** ~195 mm tall — check your Z. It fits the 256×256×256 class
  this family gates on, but it is a big print: CI's test-slice reports
  **~21 h and ~300 g** at 0.2 mm (the coupon is ~2 h 17 m).

## Parameters

The handful most worth tuning; the rest are grouped in the Customizer sections
at the top of [`nuggs-turnaround.scad`](nuggs-turnaround.scad).

| Parameter | Default | What it does |
|---|---|---|
| `port_tol` | 0.30 mm | The one fit knob for the quarter-turn joint. Tune on the coupon in ±0.05 steps. |
| `bore_d` | 80 mm | Internal bore — the shared NUGGS headline number. |
| `body_len_mm` | 180 mm | The animal's body length. The clear-width assert keys on it: the chamber must stay at least this wide inside. |
| `chamber_ay` | 100 mm | Chamber half-width along the turn axis — the cavity's widest line tracks 2× this (~200 mm at defaults; measured, because the roof's hip planes trim the ends). |
| `chamber_ax` | 47 mm | Chamber half-width across the route — sets the dish the animal crosses and the bore-mouth handoff. |
| `max_incline_deg` | 15° | The welfare ceiling on route grade. The dish-grade assert keys on it (14.6° at defaults). |
| `n_vent` / `vent_d` | 6 / 9 mm | Ceiling vent count and diameter. |
| `wall` | 2.4 mm | Shell thickness — about six perimeters at a stock 0.42 line width; leave wall loops at default. |

Override on the command line with, e.g., `-D 'port_tol=0.35'`. Every dimension
above is enforced by an `assert` in the `.scad`, so a value that breaks the
welfare geometry fails the render instead of shipping.

## Assembly & use

1. **Print the coupon first** (`nuggs-turnaround-coupon.scad`, ~21 mm stub) —
   in the same material as the node. If this is your first NUGGS module, print
   the coupon twice (~4 h 35 m / ~60 g for the pair). Mate two of them (or one
   to any NUGGS module) — it must insert to the collar face and lock with a
   light quarter turn: firm, no rattle, no forcing. Forcing loose → raise
   `port_tol` +0.05; will not lock → lower 0.05. If it inserts but the
   quarter-turn grinds near the lock, deburr the sector tips' first layer with
   a blade before touching `port_tol` — or set Elephant foot compensation to
   0.2 mm for the coupon and the node.
   The coupon also previews what the first ~50 layers will look like: the
   same sector feet, printed as free-standing islands.
2. **Print the node** ports-down, no supports, no brim.
3. **Fit it** between any two NUGGS faces: push together and twist a quarter
   turn either way — **one port at a time**, twisting whichever half is still
   free in the air (two engaged bayonets 97 mm apart on a rigid body cannot
   turn together). The same order is the emergency order: twist one, twist
   t'other.
4. **Place it** where the run doubles back — for the shelf planner, the node
   in use stands 195 mm along the tube run and 205 mm across it. The animal
   enters, climbs the ~1 mm step *down* onto the dish, crosses, pivots in the
   200 mm-wide bowl, and leaves the second port. Bedding will collect in the
   dish; that is fine — it is a pass-through, not a refuge, and the den is the
   module that wants the bedding — but strip the dish's bedding at the weekly
   clean: the vents' no-purchase argument assumes the ceiling stays a full
   standing reach away, and a packed mound shortens it. Clean it hand-wash
   only, lukewarm (≤ 50 °C), never the dishwasher: heat deforms PLA, and a
   deformed tube is a *narrowed* tube — the material failure mode is the
   injury failure mode (family charter N7).

One stated trade, so it isn't an omission: the chamber is opaque, and **you
will never see the turn** — you'll hear her cross before you see her (six
open vents carry sound, and ~300 g of hollow shell is a drum at 2 a.m., her
prime time). If watching matters, transparent PETG buys you a silhouette; a
windowed variant is a possible future derivative.
