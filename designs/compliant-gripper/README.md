# compliant-gripper

A print-in-place **parallel-jaw gripper** — one piece, off the bed assembled and
working. Push the tab and both jaws close **in parallel** (they stay mutually
parallel through the whole travel, so they clamp a cylinder on its full face,
not at two points); a bistable detent clicks in and **holds the grip with zero
applied force**. Pull the tab, the detent releases, and the leaf flexures spring
the jaws open. One of the "advanced" reference parts: it fuses all three domains
of `docs/advanced-techniques.md` in a single print.

![Studio product shot of the green 3D-printed compliant-gripper](previews/hero.png)

![3/4 view of the flat monolithic mechanism](previews/hero3q.png)

![Tilted top view — the mechanism layout](previews/top-plan.png)

![4-view contact sheet](previews/contact-sheet.png)

The cam that converts tab push into jaw closing (close-up) — the pin posts ride
the diagonal notches cut into the plunger blade's edge:

![Close-up of the cam notch and pin](previews/cam-closeup.png)

The bistable detent (close-up) — the pre-buckled arch's tip snaps over the crest
into the valley on the plunger wing and holds the clamped state:

![Close-up of the detent arch and tooth](previews/detent.png)

## What you get

- `compliant-gripper` — the part, **156 × 71 × 18 mm**, printed flat in one
  piece. Grips a **Ø 25 mm** cylinder with 0.5 mm of preload per jaw (the pads
  close to a 24.0 mm gap); **8 mm** of jaw travel; toggle force ≈ 3.8 N (a firm
  thumb push), held by the detent until you pull ≈ 5.7 N to release.
- `compliant-gripper-coupon` — the **print-this-first** coupon: the same
  mechanism with the grip zone shortened. Print it to check the clearances and
  feel the detent snap before committing 4¼ hours to the full part.

## Print settings

- **Material:** PETG (the leaf flexures and the detent arch are live springs;
  PLA works but tires)
- **Layer height:** 0.2 mm, 0.4 mm nozzle — the clearances are quantized to
  whole layers, so keep both
- **Infill:** 30–40 %
- **Supports:** none needed — and none wanted: a support inside the mechanism
  would weld it
- **Orientation:** as modelled, **flat on the bed** — the whole mechanism is one
  XY profile extruded in Z; printing it any other way breaks the flexures'
  in-layer bending and hangs the moving parts over air
- **First use:** work the tab once through its full stroke to free the race,
  then push it again and feel the detent click.

## How it works

Each jaw rides a **parallelogram of two leaf flexures**, so it translates in Y
without rotating — that is what keeps the grip faces parallel. A captive
**plunger** runs down the middle; its blade carries **diagonal edge-notches**,
and pin posts on the jaws ride in them, so one tab push converts into equal and
opposite jaw travel (a 30° wall: ×1.73 grip force per unit tab force, still
shallow enough to slide back on release). A pre-buckled **arch** along one edge
carries the detent tooth: push the tab and its tip climbs the ramp, passes the
crest, and drops into a **valley** whose floor holds the arch deflected — the
seat presses the tip against an 80° hold face, which holds the jaws' 3.9 N
spring-back with a 6.2 N wall. Pull past it and everything springs open.

The fusion: **leaf-flexure jaws + the bistable arch** (compliant mechanisms) ×
**captive plunger, pin arms and detent tip printed in place** with the PIP
clearance recipe (0.2 mm vertical walls, 0.4 mm = 2-layer roof gaps) ×
**support-free flat printing** (the flexures bend in-layer; every moving
underside floats exactly two layers over solid pocket floors). Committed
fit-checks (`ci.fitchecks`) prove the plunger is a free captive body **and**
that the cam mouth actually opens through the blade — and a fuse-check
(`ci.fusecheck`) proves nothing welds shut.

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `grip_od` | 25 mm | what it grips — the pads preload this Ø by 0.5 mm per jaw |
| `jaw_travel` | 8 mm | how far each jaw moves in Y (total gap closure 2×) |
| `preload` | 0.5 mm | grip interference at the clamped seat (the grip force) |
| `ramp_ang` | 30° | cam wall angle — force ratio vs self-return |
| `xy_tol` | 0.2 mm | wall-to-wall clearance of every captive sliding pair |
| `z_layers` | 2 | roof gaps, in whole 0.2 mm layers (0.4 mm) |
| `leg_l` / `leg_z` | 55 / 3.8 mm | leaf flexure length/thickness — the jaw spring rate |
| `arch_rise` / `arch_t` | 3.8 / 1.6 mm | the detent arch's rise and thickness — the toggle force |
| `seat_u` / `hold_ang` | 2.2 mm / 80° | detent valley depth and hold-face angle — the holding margin |

All parameters are at the top of `compliant-gripper.scad`, grouped in Customizer
sections; override on the command line with `-D 'grip_od=30'`. If you change the
grip size, the stroke and detent placement re-derive automatically — but keep
the detent's hold margin (the guards in the file refuse a set that loses it).

## If a fit is off

Print the coupon first. Plunger fused → raise `xy_tol` by 0.05 and reprint;
rattles → lower it the same. Detent won't hold → do **not** steepen `hold_ang`;
raise `seat_u` (deeper preload) or thin the leaves — the file's guards will tell
you which way the force balance still closes.
