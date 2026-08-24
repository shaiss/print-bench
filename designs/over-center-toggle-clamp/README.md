# Over-center toggle clamp

A print-in-place toggle clamp for bench-top workholding: squeeze the lever,
the jaw closes on your workpiece, the linkage passes dead center and
**self-locks**, and a buckled-beam arch gives the toggle a positive snap so
it holds both open and closed. One PETG print, four moving parts, zero
hardware, no supports.

![The clamp at its printed open pose](previews/iso-open.png)

![4-view contact sheet](previews/contact-sheet.png)

## What you get

- `over-center-toggle-clamp` — the clamp, ~146 × 88 × 27 mm (the handle
  overhangs the plate's back edge; the plate itself is 146 × 74). Jaws take a
  workpiece up to **25 mm** thick, **30 mm** deep, **20 mm** tall of face;
  mounts with two M5 screws at 40 mm centres.
- `over-center-toggle-clamp-coupon` — print this first: the same production
  flexure in a test frame, ~103 × 24 × 22 mm, and the **force-measuring
  artifact** (see below).

## Print settings

- **Material:** PETG (PP works; do not use PLA — the flexure fatigues)
- **Layer height:** 0.2 mm (the Z clearances are two layers; coarser layers
  change the fit)
- **Infill:** 25 %, 3 perimeters
- **Supports:** none — everything prints flat as rendered; the moving parts
  ride 0.4 mm films and a self-supporting bridge set
- **Orientation:** exactly as rendered (plate down, lever open) — the flexure
  must bend across printed roads, which the flat pose guarantees
- **Before the real print:** run the coupon and check two things — the beam
  snaps through cleanly (hang ~1 kg on the tab), and no film fused. A fused
  coupon means over-extrusion; fix flow before spending the ~150 g on the clamp.

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `jaw_gap_max` | 25 mm | Thickest workpiece at full open |
| `jaw_depth` | 30 mm | Gripping depth of the jaw faces |
| `jaw_height` | 20 mm | Jaw face height above the base plate |
| `arch_rise` | 3 mm | Arch rise — the snap-strength knob (with `arch_t`) |
| `arch_t` | 1.2 mm | Flexure thickness; ≥ 1.2 mm (3 perimeters) |
| `E_mod` | 2000 MPa | PETG modulus; set 1500 for PP. Tune from the coupon |
| `pip_xy` / `pip_z` | 0.25 / 0.4 mm | Sliding film / layer-snapped film — raise `pip_xy` by 0.05 if a joint is tight |
| `theta_closed` | 5° | How far past dead center the closed seat sits |

All parameters are at the top of `over-center-toggle-clamp.scad` in
Customizer sections; override with `-D 'arch_rise=3.4'`. The file echoes its
derived numbers on every render (`[over-center]` lines): snap force, switch
force, apex map, stress — check them against what you meant.

## Assembly & use

None to assemble — the clamp arrives working off the plate (if a joint feels
frozen, flex it gently; the fuse gate proves it printed free). Mount with two
M5 screws and nuts (or countersunk flat-head into tapped holes), 40 mm apart.

To use: press the handle down/over to close — you will feel the arch snap
just before the seat; the workpiece reaction then pushes the linkage *further
into* the stop (that is the over-center lock — vibration cannot release it).
Lift the handle past center to open.

**Measuring the forces:** the coupon is the instrument. Bolt its posts to
anything rigid with the pull tab hanging down, add weight to the tab hole
until the beam snaps through — that weight is the arch's snap force
(~1.05 kg predicted). Switch force at the handle ≈ that weight × 1.31;
holding force is set by the linkage lock and the jaw structure, not the
flexure (~30 N design budget). If the snap weight is more than ~35 % off
prediction, tune `E_mod` to your roll of PETG and let the asserts re-derive
the rest.

![Coupon — the force-measuring artifact](previews/coupon.png)

![Plan view: jaws, rails, mounts](previews/top-open.png)

![Side elevation: the Z stack and the arch](previews/mechanism.png)

![Cam flank and handle at the printed pose](previews/cam-closeup.png)
