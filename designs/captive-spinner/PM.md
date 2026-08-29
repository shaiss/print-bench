# captive-spinner — product charter

Transcribed from brief **#387** and the frozen SHIP-LOCK contract on that
thread (nothing invented here — the brief is the source of record).

## The product, in one paragraph

A one-piece, print-in-place fidget spinner: a scalloped rotor ring captured on a
fixed post under a self-supporting 45° cone cap, printed plate-down with no
supports and no assembly, spinning after a break-free first motion. It is the
**Tier-1 reference design** for `docs/advanced-techniques.md` Domain 3
(print-in-place kinematics) and the cross-cutting moves CC2/CC3 — the customer
is both the person who wants a fidget off the bed tonight and the person
learning how anisotropic print-in-place clearances are derived.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Radial gap derived from process constants, in the spread-limited window | `k_xy·line_w` ≈ 0.15–0.25 mm | brief (doc §Clearance theory); `assert(xy_tol >= 0.15)` guards the floor | a field test measures the window wrong on real hardware |
| N2 | Axial gap snapped to whole layers | `z_layers·layer_h`, 2×0.2 = 0.4 mm | brief (sag-limited); `assert(z_layers >= 1)` | a field test shows 2 layers fusing or 3+ rattling |
| N3 | Escape/capture lip ≤ 45° (self-supporting) | 45° cone by construction (`cone_h = r_cap − post_r`) | brief (given) | never — it is the printability of the capture itself |
| N4 | One piece, plate-down, support-free | 0 support enforcers; printcheck/slice green | brief | never |
| N5 | Rotor survives as its own body in the sliced STL | `ci.fusecheck` assert = 2 bodies, control = 1 | brief acceptance | never — this is the mechanism |
| N6 | Tuning coupon ships and is gated | `captive-spinner-coupon.scad` + "Print this first" in NOTES | brief | never |

## Out of scope

**Deferred** — sibling Domain-3 reference designs own them (parent #204):
bearing/marble variants, stacked or planetary rotors, machine-fit parts.

**Never** — style packs (brief says `Style: none`); assembly-required versions
(the one-piece property is the point); sub-0.15 mm "tighter is better" gaps.

## v1 — definition of done

The frozen gate contract on #387, checkable by anyone:

- [x] G1 — `render.sh captive-spinner` clean, bottom-iso inspected (2026-08-24)
- [x] G2 — `gate.sh --slice captive-spinner` exit 0: spinner 92/100, coupon
      100/100, both fitchecks, fusecheck assert 2 + control 1 (2026-08-24)
- [x] G3 — `readme-gate.sh captive-spinner` passes (2026-08-24)
- [x] G4 — every *Must fit / hold* row measured off the export within tolerance
      (post Ø 20.0000, OD 32.0001, width 10.0000, radial 0.2070, axial 0.4000/0.4000, lip 45.0°)
- [x] G5 — `/preflight` green (2026-08-24: readme-gate, check.sh, lineage
      selftest, gate --slice all exit 0)

## Product page & shots (art direction)

**Page promise.** "It comes off the print bed already assembled and spinning —
and the two gaps that make that possible are derived, not guessed."

**Mechanism honesty.** This design prints in its only pose — there is no
`-D` pose that could hide a weld. The as-printed `contact-sheet` (what CI
slices) is in the set, and `ci.fusecheck` is the deterministic backstop
proving the rotor separates. The hero shows the same one-piece pose.

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| hero | the finished fidget, one piece | hero | `6a4fb3` / gloss | none — as printed |
| contact-sheet | the truth: 4 views incl. bottom-iso | contact-sheet | render default | none |

**AI product stills — tier 1.5.** None (backlog B2 if wanted).

**Lifestyle scenes — tier 2 (AI, disclosed).**

| Shot | Seed | Scene |
|---|---|---|
| lifestyle-scene | hero | desk/hand staging, "geometry is approximate" caption |

**Motion clips — tier 2.** None — an AI clip inventing spin motion would
compete with the one true claim (it *does* spin); a turntable GIF is backlog B3.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Field-test print + record k_xy in NOTES (print-feedback) | reality is the only judge of a tuned fit | one coupon + one full print (~1 h, 10.9 g) |
| B2 | tier-1.5 product still seeded from hero | page polish only | one ZAI_KEY run |
| B3 | `animations.conf` turntable GIF | shows the spin deterministically | CI render only |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| none — the brief had no blocking open questions | — | — |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-24 | Charter transcribed from brief #387 + frozen contract | pm checkpoint; no charter existed |
| 2026-08-24 | Pre-existing scaffold aligned to the brief, not rebuilt | brief dimensions are the contract (G4); disclosure amendment on #387 |
| 2026-08-24 | `xy_tol` re-derived as `k_xy·line_w` (was hardcoded 0.2) | CC3 is the design's reason to exist; bare numbers can't be tuned per printer |
| 2026-08-24 | `ci.fusecheck` ships with no `flexure` zones | the rotor connects to nothing — a fuse can only be clearance collapse, so there is no legitimate bridge to excuse |
