# pop-fidget-card

A print-in-place **1st-birthday card that is also a fidget toy** — for the
parents. The bubble-themed face carries four working mechanisms straight off
the print bed, no supports, no assembly: two captive **bubble spinners**, a
bistable **"pop" button** that snaps between two states, a captive **bubble
bead** gliding on a slider track, and a punched **easel flap** (the big "1")
that folds out on a print-in-place piano hinge to stand the card on a shelf.
Personalise it at slice time — the child's name is one parameter — and print
the whole thing in about an hour on a modern machine.

![Studio product shot of the bubble-pink 3D-printed pop-fidget-card](previews/hero.png)

![Straight-on face view of the card layout](previews/face.png)

![4-view contact sheet](previews/contact-sheet.png)

![Easel flap folded out to its stop](previews/easel-open.png)

## What you get

- `pop-fidget-card` — the card, one print-in-place piece (112 × 80 × 2.4 mm
  plate; fidgets rise ≤ 8 mm above the face).
- `pop-fidget-card-coupon` — a 66 × 46 mm "print this first" tile with one of
  each tuned fit (spinner, slider, hinge) so you dial clearances in minutes.

## Print settings

- **Material:** PLA (any color; pastels suit the theme — an optional filament
  swap at the first text layer two-tones the lettering)
- **Layer height:** 0.20 mm (the axial clearances are quantized to it)
- **Infill:** 15 % (the plate is mostly top/bottom skins)
- **Supports:** none needed — every overhang is 45° by construction
- **Brim:** none — the moving parts are bed-anchored islands
- **Orientation:** as modeled, face up
- **First motion:** spin both rotors and push the bead firmly once (this
  shears the deliberate break-free welds), pop the button, fold the easel out
  until it stops (~72° shelf prop)

A note for gift-givers: this is a keepsake for the grown-ups' shelf. It is
print-in-place, so nothing detaches by design, but it is **not a teether** —
don't hand it to the birthday kid unsupervised.

## Parameters

| Parameter | Default | What it does |
|---|---|---|
| `card_name` | `""` | The child's name, appended to the greeting — set at slice time with `-D 'card_name="ALEX"'`; empty prints the generic card |
| `greeting` | `HAPPY 1st BIRTHDAY` | Bottom line text (name and `!` are appended) |
| `spinner_count` | 2 | Bubble spinners (0–2) — drop to 1 to shave minutes |
| `xy_tol` | 0.2 mm | Spinner bore ↔ post radial gap — tune on the coupon |
| `slide_tol` | 0.25 mm | Bead stem ↔ slot sliding gap per side |
| `hinge_clear` | 0.4 mm | Easel hinge pin clearance on every bore surface |
| `card_w` / `card_h` | 112 / 80 mm | Card face size |

All parameters are at the top of `pop-fidget-card.scad`, grouped in
Customizer sections; override on the command line with `-D 'name=value'`.

## Assembly & use

Nothing to assemble. Print the **coupon first** if this is your first run on
a printer (tuning order and steps are in NOTES.md "Print this first"), then
the card. After the break-free first motions everything runs free: the
spinners flick from the rim scallops, the pop button clicks between its two
states, the bead glides between the track ends, and the easel flap folds out
to its built-in stop so the card stands leaning back ~18° on a shelf. If a
fit is off, retune its parameter on the coupon and reprint — the card itself
rarely needs a second attempt.
