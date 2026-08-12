# let-folding-panel — engineering notes

**Reference design for** `docs/advanced-techniques.md` **Domain 1 (compliant
mechanisms), the lamina-emergent (LET) family** — "the best FDM match" — and
**CC1**. Tier-2 "harder".

## Goal

Two panels joined by a Lamina-Emergent Torsional joint: fabricated flat from one
sheet, folds ~90°, zero clearance / zero assembly / no rattle. The alternative
to a pin hinge (Domain 3) when you want a fold, not a full revolution.

## Topology (how the model realises a LET)

Fold line along X at y = 0.

- A thin **torsion strip** lies on the fold line, spanning the full width.
- Each panel reaches the strip only through a row of **fingers**; the rows are
  **interdigitated** (A at even pitches, B at odd).
- Fold about X: adjacent fingers pull the strip in opposite Z directions, so each
  strip segment *between* two fingers **twists** (torsion) while each finger root
  **bends**. Most compliance is torsion of the thin bars — the LET signature, and
  why ROM is high and root stress low vs a plain living hinge.

Verified on the folded preview pose (`previews/folded-pose.png`, `demo_fold=95`):
panel B stands, its fingers reaching the flat strip, interdigitated with A's.

## Parameters (the doc's LET knobs)

| Knob | Effect |
|---|---|
| `strip_w` (2.2) | **highest leverage** — thin strip twists easily; widen to stiffen |
| `fingers` (9) | more fingers = softer joint (series), distributes strain |
| `finger_reach` (6) | bending length of the finger roots |
| `sheet_t` (2.0) | whole-sheet thickness; the part is flat so flex is in-layer by construction |

Guards: `strip_w ≥ 1.2` (3 perimeters), `finger_reach ≥ 3`, `pitch > finger_w+1`
(a real torsion gap must remain between fingers).

## Print

Flat, no supports — it is a flat sheet. `demo_fold` is a **preview-only** pose;
the printed model is always `demo_fold = 0`. Material matters for a live flexure:
PETG/PP/TPU/nylon fold happily, **PLA cracks** (doc Domain 1 fatigue ranking).

## Status

- Renders clean, folded pose confirms the mechanism.
- TODO: `gate.sh --slice`, README, product shot; consider an `animations.conf`
  turntable + a real fold animation once the fold-morph is worth the effort.
