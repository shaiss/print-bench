# bar-buckle-mount

A split clamp for the standard Ø22.2 mm flat-handlebar grip that presents
the de-facto action-cam **two-finger quick-release buckle** receiver — so
the camera, light, or remote that already lives in your drawer clicks on
and off the bar with no tools beyond the initial clamp install. It is a
big, proud clamp: ~60 × 50+ mm footprint standing ~29 mm, two socket heads
proud on the outboard face — workshop-utility bulk, named honestly.

![Assembled on a ghost bar](previews/assembled.png)

Two halves bolt around the bar with a purchased M5 + nyloc; one half
carries the buckle channel on a pad that clears the continuing bar, the
other seats the nut. Print as the STL sits — end face on the bed, bore
vertical, buckle channel opening upward. No supports.

![Buckle receiver detail](previews/receiver.png)

## What you get

- `clamp-receiver` — bar half with the buckle channel on the top pad
  (envelope grows with `half_y`; defaults land near ~60 × 50 × 29 mm)
- `clamp-plain` — matching half with the nyloc hex recess
- `coupon` — short bore section + three open W/H troughs (0.0 / 0.2 / 0.4)
  + one closed latch strip (print this first)

## Bill of hardware

| Qty | Item | Notes |
|---|---|---|
| 2 | M5×0.8 socket-cap screw | length = 2·`half_y` + nyloc stack (~85–90 mm at the default shell; recalculate if you change `shell` / `flange_w` / `buckle_rot`) |
| 2 | M5 nylon-insert lock nut | seats in the plain half's hex recess; the nylon collar sits a little proud of the outer face — that proud collar is the push-out lever for disassembly |

Nothing in this design prints a thread into plastic.

## Print settings

- **Material:** PLA for print #1 (the ~23 mm bridged roof between the finger
  slots is at the comfort line in PLA and a lottery in PETG). PETG is fine
  outdoors once you have confirmed the buckle seats under the roof without
  drag; if it drags, bump `buckle_fit`. Coupon in the **same material** as
  the clamp.
- **Layer height:** 0.2 mm
- **Perimeters:** ≥ 3 (walls are ≥ 1.2 mm; shell is 5 mm)
- **Infill:** 30–40 %
- **Supports:** none
- **Orientation:** print as the STL sits — large end face on the bed, bore
  axis vertical, buckle channel opening upward. Do **not** let the slicer
  auto-orient the model; flipping onto the split face puts the bore
  horizontal and needs supports.
- **Seam:** Back (or scarf) — keeps the stacked ridge off the bore wall
  where the clamp grips the bar.
- **Brim:** 3–4 mm on the coupon if the first layer lifts

**Print the coupon first** before the halves — slide the bore onto a real
Ø22.2 grip (or a turned pin), push a genuine two-finger buckle into each
open trough (width/height drag; tight → loose = 0.0 / 0.2 / 0.4), then
click it into the closed latch strip. Tuning ladder is in `NOTES.md`.

![Fit coupon](previews/coupon.png)

## Parameters

The handful you are most likely to tune (all at the top of
`bar-buckle-mount.scad`, in Customizer sections):

| Parameter | Default | What it does |
|---|---|---|
| `bar_d` | 22.2 mm | Bar diameter — 25.4 / 31.8 for other ISO sections |
| `bore_clear` | 0.3 mm | Diametral bore clearance **and** clamping take-up. Too tight on the coupon? Up 0.1. Need hard torque to stop rotation? Down 0.1 — tune the fit, don't lean on the hex pockets. |
| `buckle_fit` | 0.2 mm | Extra clearance on buckle channel W/H. Open troughs sweep 0.0 / 0.2 / 0.4. |
| `buckle_rot` | 0 | `0` = buckle slides radially (over the bar); `1` = slides across. No setting slides along the bar. |
| `clamp_w` | 20 mm | Bearing width along the bar |
| `shell` | 5 mm | Radial wall outside the bore |

Buckle channel defaults (28.6 × 4.9 × 25.6 mm and the roof/guide table)
are the Abbott 2014 community-measured set — see `NOTES.md`. If your
buckle disagrees, change the parameters; do not guess new numbers.

## Assembly & use

1. Print `coupon`, check bore + open-trough drag + closed-strip latch
   click, tune if needed.
2. Print `clamp-receiver` and `clamp-plain`.
3. Seat the nylocs in the plain half's hex recesses (the proud nylon
   collar is the push-out lever later).
4. Place both halves around the Ø22.2 grip section. This is a **big
   clamp** — site it clear of cable housings and the stem; a clicked
   camera overflies the bar ~10–17 mm. The receiver faces radially (or
   across, at `buckle_rot=1`), not forward along the bar. Aiming means
   loosen the M5s, swivel the whole clamp, and re-snug — there is no
   tool-free swivel once the bolts are tight.
5. Fit the two M5 screws from the receiver half through to the nylocs.
   Snug until the clamp holds under a firm twist; if you are leaning on
   torque to stop rotation, that is a `bore_clear` −0.1 reprint, not more
   torque (PETG hex pockets creep under sustained clamp load).
6. Click a two-finger buckle into the receiver until the latch engages;
   press the buckle's release (or push through the roof thumb window) to
   remove.

![Split faces (as printed)](previews/split.png)

![Four-view contact sheet](previews/contact-sheet.png)
