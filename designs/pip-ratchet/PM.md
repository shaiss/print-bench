# pip-ratchet — product charter

**Product:** a print-in-place ratchet demonstrator — one captive wheel that
freewheels with a click one way and locks solid the other, printed as a single
piece. **Customer:** the bench itself (a Domain-1/Domain-3 reference design)
and any printer owner who wants a working mechanism off the bed with zero
assembly. **Promise:** ratchet behavior you can feel in the first minute after
the print, tuned by a coupon instead of guess-prints.

## Non-negotiables

| # | Rule | Source | Reopens if |
|---|---|---|---|
| N1 | Locking flank at 0° from radial (self-locking; no ejection force on the pawl) | brief #668, GIVEN (docs/advanced-techniques.md Domain 1) | any lock-flank change |
| N2 | One piece, printed in place: wheel + 2 compliant pawls + frame, no supports | brief #668 | any assembly step appears |
| N3 | Frame footprint ≤ 70 × 70 × 14 mm | brief #668 | envelope grows |
| N4 | Ships the coupon (rack + one pawl, sweeping pawl_t) and a fusecheck that proves the wheel is a separate body | brief #668 + repo PiP convention | either goes missing |
| N5 | Pawl cross-section starts from the brief's 1.2 × 10 × 8 and only deviates with a documented stress derivation | brief #668 | an undocumented dimension change |
| N6 | PETG preferred for the pawls (cyclic flex); PLA variant is a separate, deferred beam-thickness exercise | brief #668 (pop-fidget-card field test) | someone "simplifies" to PLA-in-place |

## Out of scope

- **Deferred:** PLA variant with thinner pawl beams — needs its own stress
  pass and coupon sweep; follow-up issue on the brief.
- **Never (this design):** cable-winder/tensioner applications, external
  payload on the wheel, sprag/roller-ratchet variants — brief's out-of-scope
  list. A loaded ratchet is a different safety conversation.
- Click force as a gate: it is a feel target tuned on the coupon
  (brief marks it a field-test acceptance, not a gate).

## v1 definition of done

Gates green (render, printcheck + slice, fusecheck 2-body, readme-gate),
coupon sweep plate renders, every Must-fit/hold row measured on the export
(NOTES.md table), previews committed. Human approves the shape at merge.

## Art-direction brief (for /art-direction)

Page promise: "a mechanism that works the moment it leaves the bed."
Tier-1 shots: `hero` — high 3/4 angle, pawl visibly engaged with a tooth at
the rim, arrow readable on the wheel top, warm orange on studio grey.
No lifestyle scene in v1; revisit once a field test exists.

## Decision log

- 2026-09-14 — run started from brief #668 (design-run claim on the thread).
- 2026-09-14 — geometry gate-green on iteration 1 (printcheck 92/100 both
  parts, test-slices clean, fitcheck empty + negative control fires, fusecheck
  2/2/1). Session-2 geometry fixes recorded in NOTES.md decision 7. No scope
  change; PM checkpoint passed with the two v1-DoD conditions (measured table
  in NOTES.md, PLA follow-up issue filed and linked).
