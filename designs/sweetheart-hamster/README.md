# Sweetheart Hamster

> [!WARNING]
> **Known v0.1 defect — the seam prints fused.** The living-hinge spine tends
> to weld solid in the flat print pose, so the two halves don't fold apart: the
> closed and opened poses below show the intended design, not what v0.1
> delivers off the bed. A fix (v0.2) is queued; until it lands, no setting or
> coupon tune prevents the weld (see *Print this first*).

A palm-sized jewelry box shaped like a chubby chibi hamster **cradling a heart**.
It prints in one piece — no assembly — and folds open along a living-hinge spine
like a locket. Closed, it's a cute hamster hugging a heart; split down the
middle, the heart parts between the two halves, and a heart-shaped pocket inside
nestles a ring. A giftable little keepsake for a proposal, an anniversary, or a
Valentine.

![Sweetheart Hamster — assembled, cradling the heart](previews/hero.png)

![Opened along the spine — the heart splits between the halves](previews/open-heart.png)

![Print layout — both halves lie flat, cut-face-down, joined by the hinge](previews/contact-sheet.png)

## What you get

One print-in-place part — the two hamster halves come off the bed joined by a
thin living-hinge web along the dorsal seam, so it prints already assembled and
folds shut.

- `sweetheart-hamster` — the hamster locket, **~53 × 61 × 60 mm** assembled;
  ring nest ~22 mm across. Prints flat/open, ~120 mm wide on the bed.
- `sweetheart-hamster-coupon` — a smaller "print this first" copy that exercises
  the hinge's flex and the seam clearance in its own pose — a per-printer fit
  check. It cannot predict the full print's flat-pose seam weld (the known
  v0.1 defect above); no coupon setting tunes that away.

## Print settings

- **Material:** PETG or PP recommended — the living-hinge spine flexes for many
  open/close cycles. **PLA works but is brittle at the hinge:** treat the halves
  as separable (the thin web is a tear-line) rather than a repeatedly-folding
  lid.
- **Layer height:** 0.2 mm.
- **Infill:** 10–15 % is plenty (decorative box). Default-density slicing runs
  ~36 g / ~2.5 h; low infill cuts both substantially.
- **Supports:** none for the body — it prints flat/open, cut-faces down, domes
  self-supporting. ~3 % of the surface (the ring-nest ceiling and a couple of
  underside curves) is technically overhang; enable supports if you want a clean
  nest interior, or ignore it — the sag is hidden inside.
- **Orientation:** as modelled — the default render **is** the print pose (both
  halves flat, cut-face-down, hinge in the middle). Don't re-orient.
- **Print this first:** the coupon, to check hinge flex and seam clearance on
  your printer — it cannot predict the full print's flat-pose seam weld (see
  the banner above).

## Parameters

The handful worth tuning; all parameters are at the top of
`sweetheart-hamster.scad`, grouped in Customizer sections.

| Parameter | Default | What it does |
|---|---|---|
| `S` | 1.70 | Overall scale (1.70 ≈ 60 mm tall assembled) |
| `heart_w` | 20 mm | Width of the belly heart the hamster cradles |
| `heart_proud` | 4 mm | How far the belly heart stands off the skin |
| `nest_w` | 22 mm | Ring-nest heart cavity width |
| `nest_depth` | 6 mm | Nest depth into each half (total ≈ 12 mm closed) |
| `part_gap` | 0.5 mm | Seam parting clearance — raise if the halves fuse |
| `web_t` | 0.7 mm | Living-hinge flexure thickness |
| `fold` | 0 | Preview only: 0 = flat print pose, 90 = assembled |

Override on the command line, e.g. `-D 'S=1.5'` for a smaller hamster or
`-D 'fold=90'` to preview it closed.

## Assembly & use

Nothing to assemble — it prints as one piece. Gently fold the two halves shut
about the spine; open it like a locket to drop a ring into the heart pocket. If
the halves come off the bed welded along the seam, that's the known v0.1
defect (see the banner) — no setting tunes it away; watch for v0.2. If they
merely fit tight, that's per-printer fit: raise `part_gap` and reprint, tuned
on the coupon. Print in PETG if you want the hinge to fold repeatedly.
