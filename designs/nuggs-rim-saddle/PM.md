# nuggs-rim-saddle — product charter

## The product, in one paragraph

The no-drill entry port that lets a NUGGS run start from a **glass** enclosure:
a saddle that clamps over the top rim of a glass cabinet (IKEA Detolf by
default, parametrically) and carries one standard NUGGS port on a 15° inclined
bore. For the owner of a glass tank who was told "you can't put a port on
that — it's tempered." The one thing it must do well: **hold on the rim
without drilling or adhesive, and release in one action when it matters.**

## Non-negotiables

Inherited wholesale from the family charter (`designs/nuggs/PM.md`, N1–N11);
the ones this design realizes carry an `assert` in the `.scad` where a number
can be checked.

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Bore floor | ≥ 70 mm (`bore_d` asserted) | family charter N1 | The family charter reopens it |
| N4 | Ramp incline from port invert | ≤ 15° (`incline_deg` asserted) | family charter N4 (fall risk) | Same |
| N5 | Release is one action, tool-free | 2 identical arms, 1 two-finger spread | family charter N5 (wedged animal) | A measured-release need the spread can't meet |
| N6 | Nothing protrudes into the bore | one `nuggs_bore_cut`, clamp stays outside | family charter N6 | — |
| N9 | Never drill or adhesive the rim | by construction (clamp only) | family charter N9 (tempered glass) | The owner certifies the rim non-tempered — still declined: the clamp is the product |
| Seam | Nothing bears on the silicone bead | `seam_clear` = 1.0 mm standoff + relief pocket | brief (clamp reach row) | A rim whose bead geometry defeats the standoff |

## Out of scope

**Deferred** — see backlog.

**Never** — a screw-tightened clamp (N5: one action), a mirrored arm pair (one
spare must serve both sides), drilling/adhesive (N9), any second port on this
saddle (print another module).

## v1 — definition of done

- [x] G1 `render.sh` clean, bottom-iso inspected
- [x] G2 `gate.sh --slice` exit 0 — body, arms, coupon, plate, both fitchecks
- [ ] G3 `readme-gate.sh` passes — hero PNG lands via CI regen, then green
- [x] G4 every *Must fit / hold* row measured off the export, not the typed parameter
- [x] G5 `/preflight` — verdict **"CI would pass"**; both local failures are preflight §3's sanctioned regen items (hero PNG, gallery row)

Plus: a human approves the shape (the merge).

## Product page & shots (art direction)

**Page promise.** "Your glass tank can start a NUGGS run — tonight, without
drilling."

**Mechanism honesty.** The assembled hero is *not* the only geometry-true view:
the contact sheet (as-printed 4-view) and `print-pose` show the real bed pose,
and `cutaway` proves the bore is one clean inclined tube with nothing in it.

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look | Pose |
|---|---|---|---|---|
| product-hero | the whole saddle, clamped shape | hero orbit | green satin PETG | `part="assembled"` |
| contact-sheet | what CI slices, as printed | 4-view | — | default |
| cutaway | one straight 15° bore, nothing in it | section along bore axis | — | `part="cutaway"` |
| clamp | the latch: pad on lip, hook under flange | outboard close-up | — | `part="assembled"` |
| print-pose | port-down bed pose, supports story | from below | — | `part="body"` |

No AI tiers for v1 — the product is geometry-honesty-first (a clamp that holds
glass); add lifestyle scenes only after a real rim photo validates the fit.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Measured Detolf rim profile replaces assumed dims | The one assumption every owner hits | calipers + `-D` |
| B2 | Wider-lip variant (`lip_d` presets for common cabinets) | Second-most common rim | parametric, near-zero |
| B3 | — this design **is** the family's B3 | — | — |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Real Detolf rim cross-section (lip depth/height, bead size) | no | brief's assumed values + coupon calibration path |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-26 | Two identical arms, not mirrored halves or a screw knob | N5 one-action release; one spare serves both sides; brief left mechanism to the session |
| 2026-08-26 | One straight inclined bore — the ramp IS the tube invert | N11 zero-step holds by construction; no separate ramp part to align |
| 2026-08-26 | PETG mandatory for arms | A clamp is a bending member; PLA creeps |
