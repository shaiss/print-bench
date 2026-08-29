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

## v0.2 — living-hinge fuse fix (why this version exists)

**The bug (v0.1, [#359](https://github.com/shaiss/print-bench/pull/359)).** The
sliced STL shipped with the living hinge **fused solid** — the halves could not
open. The printed part was watertight and a single connected body, so it looked
perfect to every gate.

**Root cause.** The flat-pose transform maps a point at assembled height `z` to
`flat-x = z − hinge_z*S`, so any material *above* the fold axis (`z > hinge_z*S`)
lands on the far side of the seam and welds into the other half. v0.1 set
`hinge_z = 30` (axis at `51 mm`), but the assembled model tops out at
**60.13 mm** (the ears), so the ~9 mm above the axis crossed the seam — a
**1378-facet weld** at the hinge. Two safety nets both missed it:
- `printcheck` structurally cannot see a fuse — a weld is watertight and (for a
  living hinge, which is legitimately one body) reads as a clean single body.
- the design's own `fitcheck` intersected the **closed** pose (`fold=90`), while
  CI slices the **flat** pose (`fold=0`). It verified a pose that never ships,
  so it passed green. (Reviewers never ran either — the platform-side holes are
  fixed in the fusecheck / reviewer-signoff / preview-honesty work.)

**The geometry fix.**
- `hinge_z 30 → 36` (`61.2 mm`), so the fold axis clears the **60.13 mm** ear
  top. Nothing sits above the axis, so each half stays on its own side of the
  seam and the halves connect **only** through the web. The margin is
  `(36 − 35.37)·S`, positive at every scale, so the coupon (small `S`) separates
  too.
- `web_ov 3 → 6`. With the axis above the ear top, the ears (higher than the
  spine) become the closest-to-seam material, and the **spine ridge** — where
  the web must actually bridge — lands ~4 mm either side of centre. The web now
  spans `±(g+web_ov)=±6.25 mm` so it reaches both ridges and the print is one
  foldable piece (verified: raw body-count 1 = connected; remove the web zone
  and it splits into exactly 2).

**The new gates that would have caught it** (both ship with this design):
- `ci.fusecheck` — removes the dorsal web zone from the sliced STL and asserts
  it splits into **2** bodies; the `part="fused"` control reproduces the v0.1
  weld and must stay **1**, proving the check can fire.
- `ci.fitchecks` — `fitcheck` now intersects the **flat** (sliced) pose and must
  be empty; `fitcheck_neg` drops the axis back below the top so the halves
  overlap and it interferes.

Measured on the fix: flat pose splits into 2 (fusecheck), `fitcheck` 0 facets,
`fitcheck_neg` 4856 facets, `fused` control 1 body, main printcheck 84/100
watertight, flat footprint ~126 mm wide.

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
  come apart cleanly. A seam that won't part is usually first-layer flare, not the
  gap: flex it, then enable 0.2 mm elephant-foot compensation and reprint. Raise
  `part_gap` only if it still binds — by 0.1 mm (0.05 moves each side just
  0.025 mm, under the printer's noise floor), coupon first. The `ci.fitchecks`
  prove the modelled gap is real (the halves clear)
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
