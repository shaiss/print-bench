// pip-ratchet-pla — the pip-ratchet demonstrator re-sectioned for PLA.
// The parent (designs/pip-ratchet/) sizes its pawl beams for PETG: at
// E ≈ 2000 MPa a 1.2 mm beam delivers the shipped click force. PLA is
// ~1.75× stiffer (E ≈ 3500 MPa), so the same beam clicks ~1.75× harder
// and rides up at ~1.46× the root stress. Brief #675: re-derive the beam
// section for the same click force, re-check the stress, and let the
// coupon decide whether PLA is viable at all.
//
// DERIVATIVE: the parent is included verbatim below and NO module is
// redefined — the single override is the `pawl_t` assignment. It binds for
// the parent's own `main()` call sites (include-then-override: OpenSCAD
// resolves top-level variables last-assignment-wins — the same semantics
// every *-coupon wrapper here relies on, and the same silence: OpenSCAD
// never mentions an override, which is why derives.conf claims the default
// render and gate.sh proves the claim by mesh comparison against the
// parent; background docs/derivative-designs.md).
//
// Everything else — wheel, teeth, post, capture cone, frame, clearances,
// the part dispatch (fitcheck/fused poses included), $fn — is inherited
// unchanged. No geometry in the PETG design changes as part of this
// (brief #675).
//
// The parent's ci.fitchecks / ci.fusecheck manifests are NOT re-shipped
// here: their branch proof greps the entry .scad itself, and the branches
// live in the parent (functional through the include, invisible to the
// grep). Inheriting them would mean shadowing the parent's main() with a
// copied dispatcher — which freezes the parent's asserts at copy time and
// is the exact "redefined the dispatcher" smell gate.sh's derivative
// checks name. The proofs carry instead: pawl_t is clearance-invariant
// (every wheel-facing surface — web_in, nose face, lock_gap, hook — is
// pawl_t-free; thickness grows strictly outward, frame-side), so the
// parent's green fitcheck covers this build, and printcheck's bodies: 2
// on every export is the measured separability. NOTES.md decision 7.
//
// All dimensions in millimeters. Requirements and decisions: NOTES.md;
// product charter: PM.md.

include <../pip-ratchet/pip-ratchet.scad>

/* [PLA section — the #675 force-match re-derivation] */
// PLA flexural modulus (MPa) — brief #675 (typical printed PLA ≈ 3500)
e_pla = 3500;
// PETG flexural modulus (MPa) — the parent's material (pip-ratchet NOTES.md)
e_petg = 2000;
// Pawl beam thickness, force-matched for PLA (mm):
//   t = t_PETG · (e_petg/e_pla)^(1/3) = 1.2 · (2000/3500)^(1/3)
//     = 0.996 → 1.0  (the coupon sweep's 0.1 mm step; +1.3 % click force)
// Same K ∝ E·t³·w/(4·L³) law the parent's coupon tuning uses, holding
// E·t³ constant so the PLA demonstrator clicks like the shipped PETG one.
// THE tuning knob if your PLA differs — stiffness scales t³, stress t.
pawl_t = 1.0;

// ---- ride-up stress re-check (brief #675 step 1, second half) ----------
// σ = 3·E·t·δ / (2·L_eff²) with δ = ride_defl and L_eff = block_front_u
// (the frame clamp plane; the parent's NOTES.md decision 1 derives the
// effective cantilever from it). Echoed, not asserted: 32.6 MPa is above
// the PLA flexural-fatigue band, so the honest verdict — finite click life,
// coupon decides — is a documented outcome (NOTES.md), not a gate the
// digital checks could certify. The parent's PETG reference prints below.
sigma_pla  = 3 * e_pla  * pawl_t * ride_defl / (2 * block_front_u * block_front_u);
sigma_petg = 3 * e_petg * 1.2   * ride_defl / (2 * block_front_u * block_front_u);
echo(str("pip-ratchet-pla: pawl_t = ", pawl_t,
         " mm (force-matched from PETG 1.2); ride-up sigma = ", sigma_pla,
         " MPa vs parent PETG ", sigma_petg,
         " MPa. Fatigue verdict is the coupon's to return, not the gate's."));
