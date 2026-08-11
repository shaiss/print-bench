# nuggs-den — engineering notes

The resume-cold log for this design: the goal, the decisions and why, the
numbers that were derived rather than guessed, and the intended print
orientation. The product page (README.md) is what a stranger reads; this is
what the next session reads.

## Goal

A **terminal** NUGGS module — the first one in the system that is not a run of
bore. `nuggs` is the straight (the Bin Bridge); `nuggs-yard` is an open
playpen; the `nuggs` backlog lists elbow / node / open module / wye, all of
them still tube. This is the end-cap: a single-port rounded **refuge bulb**
that turns the dead flat wall at the end of a run into a place to sit, hoard
and hide.

It is deliberately framed as "the module a Syrian hamster would ask for." The
four features below are each a piece of hamster husbandry that a person
plumbing a tube system would not think to add. None is decoration — each
answers a documented welfare complaint or a real behaviour.

## It consumes the shared standard; it does not redefine it

Like `designs/nuggs`, this is a **consumer** of `lib/nuggs-coupling.scad`, not
a derivative of another design (no `derives.conf`): it `use`s the coupling
library and builds one `cfg` with `nuggs_cfg()` at the standard defaults
(bore 80 mm, `port_tol` 0.30), so it mates any NUGGS face either way round by
construction. Every coupling guard — the 70 mm welfare bore floor, the bayonet
clearance/travel, the circumferential-clearance regression pins — fires inside
`nuggs_cfg()`; none is restated here. If the port standard ever changes, this
module inherits it rather than drifting from it.

`NUGGS_PORT_REV = 1`, matching `nuggs`. There is no engraved revision mark on
this part: every outward face it has is either the crown (which points at the
room but is a curved spire with no flat to letter cleanly) or the coupling
(which mates and is not a reading surface). The straight carries the standard's
legend for the run; a terminal cap does not need to.

## The four hamster features

### 1. Opaque refuge bulb

The standing expert critique of hamster tubes (PLOS One 2022; Deutscher
Tierschutzbund Merkblatt 62, cited in `docs/nuggs-research.md`) is in part that
clear tube denies a **prey animal any refuge** — nowhere to be unseen. Every
other NUGGS module is short and open on purpose to answer *ventilation* and
*retrieval*. The den answers *refuge*: it is the one module that is
deliberately **closed and windowless**, a solid-walled bulb the animal can be
inside and out of sight. Opacity is free (solid PLA), but it is the point of
the part, so it is stated as a requirement, not a side effect.

### 2. Flank scent-gland rub rail

A **Syrian** hamster scent-marks with the sebaceous glands on its **flanks** —
it drags its side along a surface. (Dwarf species mark with a *ventral* gland,
i.e. the belly; that difference is exactly the kind of thing this feature
encodes.) So the mark a Syrian wants is a horizontal **ridge at flank height**,
not a floor patch. `rub_rail()` is a full-circle rounded ring ridge on the
equator's inner wall. Round, not sharp: it is a rub surface, never a
chew-initiation edge (the same anti-chew principle `nuggs` PM.md N6 states for
the bore). Run all the way round so it works whichever way the animal curls up.

### 3. Chimney teardrop vents

Merkblatt 62's other complaint is that tubes **cannot be ventilated and they
condense**. A *closed* bulb is the worst case for that, so the crown carries a
ring of vents: warm exhaled breath rises and leaves out the top — a convective
**chimney**, which a closed refuge needs far more than a through-tube does.

The vents are **teardrops, point up**, cut with `lib/printability.scad`'s
`teardrop_hole()`. A round horizontal hole in a printed wall has an unsupported
ceiling that sags; the teardrop's 45° gable roof bridges itself. Reaching for a
teardrop here is the "only-a-hamster-with-OpenSCAD-skills" tell: it costs
nothing, and it is invisible unless you have actually sliced an FDM part and
watched a round hole's roof droop.

### 4. Pouch-relief mouth

A hamster arriving with **both cheek pouches full** is dramatically wider at
the face than at the body. The coupling bore is already at the 70 mm entrance
floor for exactly this reason, but a square lip at the very mouth is still a
scrape hazard for a loaded arrival. `pouch_relief()` flares the bore from
`ri + mouth_flare` at the tube end face down to `ri` by `mouth_len` inboard, so
the entry is a funnel. It only ever **opens** the bore (welfare-positive), and
`mouth_flare` is asserted to leave `wall - mouth_flare >= 1.2` mm of tube shell
at the mouth, so the funnel never thins the wall below a printable three
perimeters.

> **The mouth is `z = 0`, not `z_tip`.** The coupling library puts the tube end
> face at `z = 0` and the sector tips at `z_tip = -port_proj`, 10 mm below it,
> in the region the *mate's* tube occupies. The first cut of this feature was
> anchored at `z_tip`, where the den has no bore wall — so it removed nothing
> and the "pouch-relief mouth" was silently absent from the print while every
> gate stayed green. Three independent PR-#189 reviewers caught it; the flare is
> now anchored at `z = 0` where the wall actually is. A no-op feature that
> passes every gate is exactly the failure mode this repo watches for.

## Geometry, and the traps avoided

The bulb is two solids of revolution: `outer_profile` (the shell) and
`inner_profile` (the cavity), each **one** `rotate_extrude` polygon. That is
the deliberate defence against the coincident-cylinder trap the coupling
library warns about at length — two swept arcs sharing an exact radius leave a
coincident surface and CGAL returns a non-watertight mesh. Because the whole
shell is one polygon and the whole cavity is another, no two swept faces ever
share a radius. Confirmed: `Simple: yes`, one body, watertight.

- **The neck fuses the port.** The shell is full-round `ro` from `z = 0` to
  `neck_len = z_top + neck_extra`, so the port's inner sectors have the ring
  they must fuse to over the whole port zone (`0..z_top`). The shoulder does
  not begin to flare until *above* `z_top`, so it never fouls the coupling ring.
- **One cavity cut serves as the bore cut too.** `inner_profile` starts below
  the sector tips (`z_tip - 1`) at radius `ri`, so subtracting it removes the
  port's inboard anchoring material exactly as the mandatory `nuggs_bore_cut()`
  would — the den does not, and must not, forget the cut, because the cavity
  *is* the cut.
- **No flat internal ceiling.** Both the shell crown and the cavity ceiling
  close to a point (`shoulder`-steepened cones), so the roof self-supports
  layer on layer — there is no horizontal internal span to bridge. The outer
  point is then blunted by a small sphere (`crown_blunt`) so the physical part
  ends in a rounded finial, not a spike.
- **The rail is added after the cavity is cut.** It protrudes *into* the
  cavity, so if it were unioned before the subtraction the cavity would carry
  it straight back out. Its base bites 0.6 mm outward into the shell so it
  fuses as a real overlap, never a zero-area kiss (the CGAL-separate-bodies
  trap).

`shoulder = 1.2` puts every sloped surface at ~40° from vertical — inside the
45° support-free budget with margin. A guard refuses `shoulder < 1.0`.

## Print orientation

Printed exactly as modelled, no rotation: the **coupling sectors sit on the
bed** (that is their job — `lug_deg` is the first-layer anchor), the bore runs
straight up, and the bulb closes above it. Consequences, all expected and
shared with every NUGGS part:

- **Small bed contact** (~527 mm², a WARNING). The part stands on three sector
  tips, by design. **Use a brim.** This is the same footprint every `nuggs`
  module prints on.
- **~4 % overhang beyond 45°** (a WARNING). Almost all of it is the port
  geometry itself (the bare coupon shows 7 % on a smaller part); the bulb's own
  shoulder and crown are held under 45° by `shoulder`.
- **2 degenerate faces** (a WARNING). These come from the **library port**, not
  the bulb — the pure `nuggs_neck()` coupon shows the same two. Not fixable
  from here without editing the shared library; harmless per printcheck.

`gate.sh --slice` exits 0 at **76/100 PRINTABLE WITH CAVEATS** — warnings only,
the same tier the other NUGGS modules ship at.

In **use** you orient it however the run needs; every feature is a full ring,
so nothing depends on which way up it lands.

## Welfare scope — read before overselling this part

This is a **dead-end**. Clear internal diameter is `2*(bulb_r - bulb_wall)` =
**110 mm** at the default `bulb_r = 58`, which is **less than a Syrian's
~180 mm body length** (`nuggs` `body_len_mm`), so the animal **cannot turn
around** in it and must **reverse out**. Under the `nuggs` run-length rule
(PM.md N2; `docs/nuggs-research.md` §11) the den is therefore **not a "break"**:
it does not reset the run count. A turnaround node needs clear width ≥ body
length; this is a refuge, not a turnaround.

So the honest placement is: **cap a short stub**, where the reverse-travel
budget (half the run ≤ one body length) is not already spent by the tube
feeding it. The den buys *refuge, opacity and ventilation* for a run end; it
does **not** buy length. Do not chain a long run into one on the theory that
"there's a room at the end."

## Print this first

`nuggs-den-coupon.scad` renders a bore-clean port stub (`nuggs_neck()`). The
fit is the shared library standard, so this is the same coupon `designs/nuggs`
tunes: mate two of them (or one to any NUGGS module) and adjust `port_tol` by
0.05 mm per iteration (e.g. 0.25, 0.30, 0.35) until the quarter-turn seats
without forcing, then set that value here.
Nothing in this system has been printed yet — `port_tol = 0.30` is a guess.

## Parameters worth knowing

- `bulb_r` (58) — half the chamber OD. The refuge-vs-print-time knob: a wider
  bulb is a bigger room but, because the crown must stay support-free, a taller
  and heavier print (the default is ~140 mm tall, ~127 g, ~10 h).
- `bulb_wall` (3.0) — chamber shell; separate from the tube `wall` because the
  bulb carries no coupling load.
- `eq_h` (26) — equator band height; the vents and rail live on it.
- `n_vent` (6) / `vent_d` (9) — the chimney ring.
- `rail_h` (4) / `rail_z` (6) — the flank rub ridge.
- `crown_blunt` (5) — the rounded finial radius.

## Open items

1. **Nothing printed.** Whole system is geometry-only. Coupon first, then this.
2. **`port_tol` unproven** — inherited 0.30 guess from the shared standard.
3. **Print weight/time** — ~127 g / ~10 h at defaults is a lot; the bulb is
   large because a refuge is large. A smaller `bulb_r` is the lever if that
   matters, at the cost of room.
