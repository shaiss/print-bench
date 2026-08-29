# snap-cantilever-clip — product charter

Charter source: design brief #386 (epic #204, reference-design catalog,
Domain 1 — cantilever snap). Created at the pre-push PM checkpoint of the
first design run; the brief thread is authoritative where this is silent.

## The product, in one paragraph

A one-piece clip that snaps onto a 3 mm plate edge and holds by cantilever
deflection — the canonical snap-fit, built as the Tier-1 **reference
design** for `docs/advanced-techniques.md` Domain 1. Two customers: the
doc's reader, who downloads the part that embodies the SLFP relations
(K = E·I/L, I = w·t³/12, σ ≈ E·t·θ/(2L), r ≥ 0.5·t) and can read them off
a real, gated, printable part; and anyone who just wants to hang something
on shelf stock. The one thing it must do well: **snap on, hold by spring
preload, survive repeated insertions without cracking at the root.**

## Non-negotiables

Each is asserted in the `.scad` (`checks()`) so the render fails rather
than the reviewer catching it.

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Flexure root fillet r ≥ 0.5·t | r = 0.6, t = 1.0 | doc fatigue rule (brief, **given**) | A coupon field test shows the fillet intruding on the plate seat enough to matter |
| N2 | Flexure thickness t ≥ 0.8 mm | t = 1.0 | repo min feature (brief, **given**) | never below 2 extrusion widths — no reopening |
| N3 | Bending in the layer plane (CC1) | silhouette authored in XY, extruded Z | doc Domain 1 rule #1 (brief, **given**) | never — print orientation is load-bearing |
| N4 | Dimensioned from the SLFP relations, not guessed | F = 5.2 N ∈ [4,8]; σ_tip ≤ 25 MPa | brief (assumed band, E = 2000 MPa PETG datum) | a measured E from `printer.conf` field tests |
| N5 | Footprint ≤ 60 × 25 mm | 9.9 × 24 × 15 | brief (assumed) | a named plate that needs deeper seating |
| N6 | No lib/ changes in this design's PRs | — | epic #204 chunker ruling | the lib/compliant.scad PR (#202) lands and harvests NOTES.md's candidates |

## Out of scope

**Deferred** — backlog below.

**Never** — other catalog domains (the 8 sibling briefs #385, #387–#393);
machine-thread or BOSL2-screw variants (this is a flexure reference);
AI lifestyle/still/motion tiers (style is `none`; the v0 AI scene belonged
to the superseded cable-clip draft and was deleted, not restyled).

## v1 — definition of done

Checkable by someone other than the author; the gate is necessary, not
sufficient.

- [x] `gate.sh --slice` green, printcheck 100/100 on part + coupon
- [x] Every *Must fit / hold* row measured off the exported mesh (brief audit)
- [x] Predicted K, θ, F, σ echoed at render and recorded in NOTES.md
- [x] Coupon + "Print this first" tuning order (t → r → grip_p) shipped
- [ ] Human review of the **shape** — the merge decision (incl. accepting
      the 8.6°-vs-15° deviation below)
- [ ] Fatigue cycle target set at review; until then coupon-qualify (20×,
      no whitening at the root)

## Product page & shots (art direction)

**Page promise.** "This is what a snap-fit is when it's derived, not
guessed — and it's already the size of a test coupon."

**Mechanism honesty.** The hero is the **as-printed pose** (default render,
no `-D`), and the as-printed `contact-sheet` is embedded beside it. The
detail shots (profile/mouth/root) are honest by construction: `profile` is
orthographic top-down (nothing to hide behind), `mouth` and `root` are
exterior elevated angles chosen so every wall is visible. The one interior
feature without a robust camera corridor — the root fillet itself — is
**declared** in `previews/CAMERAS.md` and documented by the orthographic
`profile` shot rather than hidden behind a flattering angle.

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| hero (shots.conf) | the object, mouth first | 3/4 into the mouth, rotz 34° / elev 22° | orange e8552d / satin | none — as printed |
| contact-sheet | as-printed 4-view (what CI slices) | fixed 2×2 | render style | none |
| profile | the working drawing: every angle | orthographic +Z | render style | none |
| mouth | the insertion story | into the mouth | render style | none |
| root | the flexure root + guard rail | guard-side elevated | render style | none |

**AI tiers** — none (out of scope, above).

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Set the fatigue cycle target; qualify (coupon 20×→N×) | the one open number in the brief | one print + a review comment |
| B2 | `w` (width) presets for common shelf depths | most-likely user tweak after t | param only, no geometry |
| B3 | PP material note/field test (doc: PP ≫ PETG for cycles) | biggest lifetime lever | one print |
| B4 | Contribute weld-safe root fillet + cam lip to `lib/compliant.scad` | epic #204's harvest list | lib PR after #202 lands |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Cycle-count target for "done" | no | coupon-qualify 20×, no whitening (NOTES.md, Fatigue) |
| Accept θ = 8.6° in place of the brief's assumed ~15° | no (it **is** the merge review) | σ ≤ 25 MPa + F ∈ [4,8] govern; deviation documented in NOTES.md |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-24 | Supersede the v0 cable-clip draft wholesale | brief #386 defines a different object for the same catalog slot |
| 2026-08-24 | Design to σ/F targets, let θ land at 8.6°, not the assumed 15° | 15° at L=12 needs δ=4.19 mm (> channel) or σ≈44 MPa (near yield); θ is behaviour, coupon-tunable |
| 2026-08-24 | Keep r = 0.6 ≥ 0.5·t and accept ~0.15 mm shallow plate seating | clearing the plate fully needs r ≤ 0.2 < 0.5·t — trades a given fatigue rule for 0.15 mm |
| 2026-08-24 | No AI image tiers on the page | style `none`; the v0 AI scene depicted the superseded object |
