# pip-ratchet-pla — product charter

**Product:** the pip-ratchet print-in-place ratchet demonstrator
re-sectioned for PLA — a one-variable derivative answering "what would the
pawls look like in the filament everyone actually owns?" **Customer:** the
printer owner whose spools are PLA and the bench's material-reference
shelf (a measured PLA counterpoint to the PETG demonstrator). **Promise:**
a PLA build that clicks like the PETG one, and a coupon honest enough to
say "don't".

## Non-negotiables

| # | Rule | Source | Reopens if |
|---|---|---|---|
| N1 | The PETG parent changes nothing — this design is a pure derivative | brief #675 ("No geometry in the PETG design changes as part of this") | any diff under `designs/pip-ratchet/` |
| N2 | The section is force-matched by derivation (E·t³ const), never eyeballed | brief #675 (the K ∝ E·t³·w/4L³ formula) | `pawl_t` moves without a recorded derivation |
| N3 | Ride-up stress re-checked and recorded (σ = 3E·t·δ/2L_eff²) | brief #675 | the number stops being echoed/recorded |
| N4 | Adoption is contingent on the coupon's click-count field test — PLA is "unsuitable unless a coupon proves otherwise" | docs/advanced-techniques.md fatigue ranking; parent PM N6 | the caveat disappears from the README |
| N5 | Ships the PLA coupon (mirrored `pawl_t`) + the parent's gate set to the extent a derivative can carry it: printcheck + slice on demonstrator and coupon, derivative mesh-prove, and the fit/separability obligations evidenced (NOTES decision 7: the parent's fitcheck manifests are entry-textual and not inheritable without a dispatcher shadow) | repo conventions; brief step 3; iteration-1 gate finding | the coupon or the evidence chain goes missing |

## Out of scope

- Any change to the parent design (brief; N1) — including "just flipping"
  the parent's `pawl_t`.
- Re-dimensioning the pawl free length L for PLA (the σ escape hatch if
  the coupon says not-viable — named in NOTES decision 6, a *different*
  design conversation).
- Click-force retargeting beyond the force-match; feel stays a coupon
  question (parent charter).
- Loaded-ratchet / cable-winder applications (parent's never-list).
- Running the field test itself — physical printing is the owner's; this
  design ships the protocol and the coupon to run it against.

## v1 definition of done

Gates green (render, printcheck + slice on demonstrator and coupon,
derivative mesh ≠ parent, readme-gate), the derivation measured on the
export (NOTES table), the click-count protocol published, previews
committed. **Two human gates, explicitly in order: shape approval at
merge; material adoption at the coupon.** The v1 page must survive a
field test that returns "not viable" — that is a recorded outcome, not a
rework.

## Art-direction brief (for /art-direction)

Page promise: "your PLA, the same click." Tier-1 shots (as shipped in
`previews/cameras.conf`): `contact-sheet` (the as-sliced pose CI gates),
`pawl-close` — the story, the parent's camera byte-for-byte so the thinner
band compares against the parent's published shot — and `coupon` (the
qualification artifact the page sends you to print; framing pixel-verified,
see `previews/CAMERAS.md`). No lifestyle scene until a field test exists
(same stance as the parent).

## Decision log

- 2026-10-04 — run started from brief #675 (design-run claim on the
  thread). Mechanism: derivative, single `pawl_t` override (NOTES
  decision 1). Section: 1.0 mm, force-matched (decision 2); σ = 32.6 MPa
  recorded (decision 3). Posture: conditionally viable, coupon decides.
- 2026-10-04 — iteration 1 finding: the parent's ci.fitchecks /
  ci.fusecheck cannot be re-shipped by a variable-only derivative (the
  branch proof greps the entry textually; the poses live in the parent's
  include). Dropped rather than shadowing the parent's dispatcher; the
  obligations carry with evidence — pawl_t-invariance argument + printcheck
  `bodies: 2` measured on both exports (NOTES decision 7). A future
  `gate.sh` include-closure branch proof would let derivatives inherit
  them; out of this run's Touches.
