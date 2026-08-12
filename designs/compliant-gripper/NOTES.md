# compliant-gripper — engineering notes

**Advanced (Tier-3) reference design — fuses all three domains** of
`docs/advanced-techniques.md` into one part that prints assembled and working.

## What it is

A print-in-place collet grabber. Slotted flexure fingers form an outward cone; a
captive collar rides around them. Slide the collar up and the cone cams the
fingers inward (grip on a rod in the bore); release and the flexures spring back
and push the collar down. One piece, no supports, no assembly.

## The fusion (why it's a Tier-3 part)

| Domain | Where it lives here |
|---|---|
| **D1 compliant** | fingers are slotted cantilever flexures rooted in the base ring — self-returning, no spring |
| **D3 print-in-place** | the collar prints captive around the fingers, trapped by base (below) + cone (above), free to slide |
| **D2 supports / CC1** | printed bore-axis vertical: fingers are ~6° from vertical (self-supporting), the only floating face is the collar underside |
| **CC3 anisotropy** | collar↔finger gap is a vertical wall (spread-limited `xy_tol=0.35`); collar↔base float is a roof (sag-limited `z_tol = 2·layer_h`) |

## The two derivations that make it work

1. **Collar bore from the cone, not a guess.** The collar bore is cylindrical but
   the fingers flare, so the bore must clear the *widest* fingers it spans at rest
   — the fingers at the collar's **top**:
   `collar_ir = ro_at(collar_z0 + collar_h) + xy_tol`.
   The first render used `ro_base + xy_tol` and the flaring fingers grew *into* the
   collar over its height — fused, not captive. Cross-section confirmed the fix:
   collar is a separate body with a clear gap. Looser at the bottom, just-clear at
   the top — a collet nut at rest.
2. **Capture is the cone itself.** `ro_tip > collar_ir` (asserted) ⇒ the collar
   can't pass the wide top; the base stops it below. No separate cap needed.

## Camming

Cylindrical collar bore + conical fingers ⇒ sliding the collar up closes the gap
uniformly (`slope · travel`). That IS the actuator; no threads, no ramp part.

## Known TODO (hardening pass)

- **Slot-root fillets.** The slots bottom on a square edge at the finger root — a
  stress concentration. Add a stress-relief hole / fillet at each slot base
  (doc's `r ≥ 0.5t`) before ship; a fatigue coupon should sweep it.
- Print-in-place fit → `ci.fitchecks`: collar renders as a separate body, 0
  interference facets, with an interfering negative control (`xy_tol → 0`).
- Live flexure → PETG/nylon/PP, not PLA.

## Print this first

`compliant-gripper-coupon.scad` — a short collet (include + override, no copied
geometry). Print it and slide the collar; if it's fused, raise `xy_tol` by
0.05 mm and reprint; if it's sloppy, lower it. Tune `xy_tol` here before a
full-height print. Gated like any part.

## Status

- Renders clean; half-section confirms the captive collar clearance.
- TODO: gate + fitchecks, slot-root fillet, README, product shot.
