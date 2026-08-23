# sweetheart-hamster — engineering notes

Design brief: [issue #354](https://github.com/shaiss/print-bench/issues/354).
The product page for a stranger is `README.md`; this file is the engineering log.

## Goal

A palm-sized (~60 mm) jewelry box shaped like a chibi hamster **cradling a
heart**. It splits down the sagittal midline so the heart parts between the two
halves — "hamster together, heart when the pieces are apart." It is a
print-in-place clamshell: the two halves come off the bed as one piece, joined
along the dorsal seam by a living-hinge web, and fold shut into the hamster. A
heart-shaped pocket straddling the seam is the ring nest.

## Given / assumed measurements

All **assumed** (the brief supplied no measured constraint) with the brief's
stated defaults:

- Overall height ~60 mm → `S = 1.70` on the study-E massing. Built mesh
  (assembled) measures **52.8 W × 61.4 D × 60.1 H mm** — height on target; the
  chubby proportions run wider/deeper than the brief's rough 46×42 guess, which
  is the massing, not a miss.
- Ring nest heart cavity `nest_w = 22 mm`, `nest_depth = 6 mm` per half → a
  ~22 mm × ~12 mm pocket when closed, clears a typical ring.
- Wall / feature floor ≥ 1.2 mm (repo FDM default); printcheck confirms the
  built walls (main scores 84/100, coupon 92/100, both watertight, 1 body).

## Key decisions

- **Mechanism deviation from the brief (pip_hinge → living hinge).** The brief
  proposed a captive-pin `pip_hinge`. A *rounded* body split sagittally can't
  print both halves dome-up with a pin joint the naive way, so — following
  `snap-clamshell-box` (CC1) — the closure is a thin **living-hinge web** across
  the dorsal seam. Both halves print cut-face-down (domes up, self-supporting via
  the inward-tapering study-E massing), splayed open, no supports; fold to close.
  A `pip_hinge` variant that prints the halves flat about a horizontal dorsal pin
  is a viable future enhancement (works in PLA; see below) but was out of scope
  for the first gated PR.
- **Print orientation = flat/open (the default render).** `designs/.../*.scad`
  renders the *print pose* by default (what CI slices). `fold=90` folds it to the
  assembled hamster for previews; `previews/cameras.conf` drives the hero shots.
- **Heart is a shape motif, not hidden.** The owner explicitly chose the
  *shape* heart (visible on the belly, splits apart) over a hidden-inside heart —
  the two are mutually exclusive (a shape heart can't hide when assembled). The
  belly heart stands `heart_proud = 4 mm` off the skin so it reads in front of
  the cheeks; the same heart, in the nest, is the ring pocket.

## Print this first (coupon)

`sweetheart-hamster-coupon.scad` is a smaller copy (same modules, `S = 0.85`,
ring nest off) that prints fast so you can tune the two fits before the full
print:

- **Living-hinge web** (`web_t`, default 0.7 mm): flex it a few times. **PETG/PP
  fold for many cycles; PLA cracks.** If it tears, raise `web_t` or switch
  material. If you print in PLA, treat the halves as separable (the web is a thin
  tear-line) rather than a repeatedly-folding hinge.
- **Seam parting gap** (`part_gap`, default 0.5 mm total): the two halves must
  come apart cleanly. If they fuse at the seam, raise `part_gap` by 0.05 mm and
  reprint. The `ci.fitchecks` prove the modelled gap is real (the halves clear)
  and that the check can fail (a negative gap interferes).

## Known caveats

- **~3 % of the surface is unbridgeable overhang** (printcheck WARNING, not a
  fail): the ring-nest ceiling and a few underside curves (cheeks/feet). It
  slices and prints; use the slicer's supports for that 3 % or accept minor
  sag inside the nest (it's hidden). Not chased to zero — inherent to an organic
  body plus a hollow nest.
- The body is mostly solid apart from the nest; at default infill the full print
  is ~36 g / ~2.5 h. Drop infill to 10–15 % to cut both — it's a decorative box,
  not a structural part.

## Field test log

<!-- Append one FIELD-TEST entry per real print (templates/FIELD-TEST.md). -->
_None yet._
