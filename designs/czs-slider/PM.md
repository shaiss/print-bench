# czs-slider — product charter

## The product, in one paragraph

A one-piece captive slider that glides at a near-constant ~2 N across its
20 mm stroke — the reference demonstrator for the D1+D3 fusion
(quasi-zero-stiffness springs × print-in-place kinematics) in the
`docs/advanced-techniques.md` catalog (brief #393, child 9/9 of #204). The
customer is a printer owner who wants to *feel* negative-stiffness
cancellation work — and the catalog itself, which cites this design as the
worked example. The one thing it must do well: push the knob, meet ~2 N,
keep meeting ~2 N, all the way across.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Plateau force over the flat zone | ~2 N, ±25% over the middle 70% | brief #393 (assumed default) | a FIELD-TEST entry shows ripple or level outside the bar — then re-solve `v_t`/`target_fs`, never patch geometry by eye |
| N2 | One piece, captive, zero supports | 1 body by design | brief #393 (given) | the brief is amended — a lid or assembly breaks the reference claim |
| N3 | Anisotropic clearances, not one global tol | xy 0.207 mm / z 0.4 mm at 0.4 nozzle, 0.2 layers | #387 recipe | a different nozzle/layer target — then re-derive both from the process constants |
| N4 | Spring dimensions derived, not typed | `f_s` echo + `k_v(mid)` within 10% of `k_a` assert in-file | #389 solve; the #37 lesson | the solve constants (E datum, nondimensional pair) are re-measured |
| N5 | As-printed pose shown | `contact-sheet` embedded, no posed-only hero | readme-gate req 12 + the sweetheart-hamster lesson | never |

## Out of scope

**Deferred** — the backlog below.

**Never** — adjustable-force hardware (a screw or clamp breaks N2);
multi-material; a PLA variant (live flexures; PETG minimum by N1's stress
budget); restyling the page with AI tiers (a reference design shows real
geometry — see decision log).

## v1 — definition of done

- [x] `gate.sh --slice czs-slider` green incl. coupon, fitchecks
      (empty/interferes pair), fusecheck (2 / 7 / 1 with the fused control)
- [x] `readme-gate.sh` clean apart from the two `product-hero` lines CI's
      regen fills on the PR
- [x] NOTES.md carries the two-element model, the predicted force–stroke
      table, the fusion interactions, the FIELD-TEST path
- [ ] PR merged (the human's shape approval) and one FIELD-TEST entry
      recorded against N1

## Product page & shots (art direction)

**Page promise.** A drawer glide that never ramps: ~2 N, flat, all the way
— printed in place, zero supports.

**Mechanism honesty.** The set is all as-printed (`demo_u = 0`): the
`contact-sheet` 4-view is what CI slices and is embedded; `qzs-top` and
`qzs-midspan` are straight geometry-true views of the chamber; the coupon
shot is the as-printed coupon. The one studio hero (`product-hero`) is
cosmetic framing, never the only geometry-true view. Nothing is posed.

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the whole mechanism, knob forward | low 3/4 | slate `6b7f8e` / satin | none (as printed) |
| contact-sheet | the as-printed proof (bed-flat, one bridge) | 2×2 iso/top/front/bottom-iso | default | none |
| qzs-top | the parallel pair — arch −X, chevron +X | straight down | default | none |
| qzs-midspan | the springs crossing without touching | near-top close | default | none |
| coupon | print-this-first: fit cells + feeler | straight down | default | none |

**AI product stills — tier 1.5.** None — see decision log.

**Lifestyle scenes — tier 2.** None — see decision log.

**Motion clips — tier 2.** None yet; B2 in the backlog proposes a
deterministic (non-AI) `animations.conf` sweep.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | FIELD-TEST entry (kitchen-scale plateau + ripple) | closes N1's only open verification | one print + a scale |
| B2 | `animations.conf` u-sweep GIF | shows the *flat* character a still cannot | one render loop, ~1 MB GIF budget |
| B3 | mid-stroke cross-section preview shot | shows the 0.4 mm deck gap the plan views hide | one new cameras.conf line |

## Open decisions

None blocking. The brief's assumed values (stroke 20 mm, ~2 N, ±25%, 70%)
are realised as parameters, per contract.

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-30 | Style `none`, and no AI image tiers (1.5 / 2) | reference/teaching design: the page's value is geometry truth; AI restyle adds approximation to the one design whose point is exactness |
| 2026-08-30 | `u_free = 4.33` placed for ~1 N rest preload | self-advancing pair holds the slider on the −Y stop — no rattle, no clatter at arrival; modelled in NOTES |
| 2026-08-30 | coupon feeler at ~9 N (shorter span), not 2 N | the l³ law makes a 2 N feeler span the full part length; the feeler tests *character* (flat vs ramp vs snap), not level |
