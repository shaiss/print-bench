# support-free-bracket — product charter

## The product, in one paragraph

A wall shelf bracket that is also a **teaching artifact**: the Tier-1 reference
design for `docs/advanced-techniques.md` Domain 2 (designing around supports),
demonstrating that a part which would need supports in a naive orientation
needs **none** here. Two customers: someone who needs a real ~1 kg-class shelf
bracket, and someone learning support-free FDM design who wants a worked
example where every feature that would force a support is reshaped instead.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Zero support material, by construction | vault ≤ 45° from vertical (modeled 42°, `assert`ed); horizontal bores are teardrops; no flat down-facing ceiling | brief #385 Must rows; Domain 2 charter | a field test shows a print failure support-free geometry cannot fix — that is a report, never a silent weakening |
| N2 | Wall fasteners | 2 × M5 clearance bores (Ø5.5), horizontal axis | brief #385 | the user names a different fastener — then it's a parameter change, still teardrops |
| N3 | Must-fit envelope | plate 80 × 50 × 6 mm; arm 60 deep × 6 thick (measured on the export: 80 × 66 × 50) | brief #385 | the shelf it must carry changes |
| N4 | The no-supports claim is falsifiable | `gate.sh --slice` green with supports **disabled** in the test-slice | brief #385 gate G2 | never |

## Out of scope

**Deferred** — the sibling #204 Domain designs, style packs (brief says
`Style: none`), and #204's cross-iteration stress-test gate. See backlog.

**Never** — a flat ceiling over the arm cavity; a bottom fillet at a
bed-contact edge (each is exactly the overhang this design exists to avoid);
supports in the slice profile (they would make the page's claim a lie).

## v1 — definition of done

- [x] G1 `render.sh` clean, bottom-iso inspected
- [x] G2 `gate.sh --slice` exit 0, supports disabled (92/100, caveat measured
      benign — teardrop-crown facets under nozzle width, see NOTES.md)
- [x] G3 `readme-gate.sh` passes
- [x] G4 every Must-fit row measured on the exported mesh, not the variable
- [ ] G5 `/preflight` green (running at ship time)
- [ ] Page previews depict current geometry (hero re-rendered by CI regen on
      the PR — stale bytes until then are disclosed, not hidden)

## Product page & shots (art direction)

**Page promise.** "This prints with supports turned off — and here is why,
feature by feature." The reference-design job outranks the shelf-bracket job
on the page.

Not a mechanism (nothing folds, slides or prints in place), so the honesty
risk is a camera hiding a flat ceiling — `bottom-iso` (the proof shot) and the
as-printed `contact-sheet` are both on the page and frozen.

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look (color / finish) | Pose |
|---|---|---|---|---|
| hero | the whole bracket, print orientation | 3/4 | warm satin (`2f6fb0`) | none |

Frozen geometry previews (`previews/cameras.conf`): `contact-sheet` (as
printed — what CI slices), `iso`, `bottom-iso` (the no-supports proof),
`front-bores` (teardrops head-on), `side-vault` (the 42° triangle).

**AI tiers (1.5 stills / 2 lifestyle / motion):** none. Tier 2 was removed —
the committed scene depicted the superseded rod-holder geometry, which is
worse than no scene (see decision log).

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Re-add a tier-2 lifestyle scene (write `lifestyle.conf` on main; the workflow auto-fires) | sells the use, not the technique | 1 conf line + CI key |
| B2 | Knife-edge teardrop crown once #398's lib fix lands — clears the 92/100 caveat | honest perfect score | lib PR + re-gate |
| B3 | Deeper/heavier arm variant (`arm_d` 100+, thicker vault band) | only if field tests ask | one param sweep + print |

## Open decisions

None blocking. The brief's one modeling-time fork — rib on the arm — is
resolved (no rib; the vault brace is the stiffener; derivation in NOTES.md).

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-24 | Full rewrite; the pre-existing rod-holder draft superseded | it failed 4 of 5 brief Must-fit rows — adaptation would have left neither design honest |
| 2026-08-24 | Vault at 42°, not the 45° limit | margin under the self-support limit costs 3 mm of cavity and buys layer-to-layer contact |
| 2026-08-24 | No rib on the arm (brief left it to modeling) | the vault ties full 80 mm width to the plate; a rib would hang into the cavity and re-open the overhang question |
| 2026-08-24 | Tier-2 lifestyle scene removed, not regenerated | it depicted the old geometry; CI's lifestyle workflow only fires when a manifest lands on main — re-adding there is the designed path (B1) |
| 2026-08-24 | Bore positions staggered x=20/z=10 and x=60/z=28 (assumed) | stagger resists pull-out better than a vertical pair; recorded as assumption in NOTES.md |
| 2026-08-29 | Bores moved z 10/28 → 11/25 (x unchanged); head-envelope guards added | head-envelope clearance (Jane round-2 finding, Drik round-1): M5 socket head fouled the vault at z_hi=28 and kissed the arm at z_lo=10; the reviewed 10→9 lower move was sign-inverted (measured: 9 interferes 25.9 mm³, 11 clears), so 11 landed; stagger survives |
