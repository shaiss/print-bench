# vesa-shelf — product charter

## The product, in one paragraph

A one-piece behind-monitor tray that bolts onto a display's published VESA
MIS-D hole pattern and hangs a small shelf in the dead space behind an
arm-mounted screen. For a stranger who wants a Pi, mini-PC, slim video bar,
USB hub, or cable loop back there without straps or adhesives. The one thing
it must do well is **mount on the real VESA interface and hold the stated
payload without eating the display's insert engagement budget**.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | VESA square pitch is a published MIS-D value | 100 default; 75 supported | VESA MIS-D / brief #976 | a different published pitch is evidenced |
| N2 | Screws are purchased M4×0.7 into the display inserts — never printed threads | M4 clearance Ø4.5 | VESA MIS-D; brief #976 | — |
| N3 | Plate + washer stack keeps display engagement ≤ 10 mm | `screw_len − plate_t − washer_t ≤ 10` | VESA MIS-D typical max / brief #976 | a display datasheet states a different max |
| N4 | Tray hangs below the bolted pattern | `tray_drop` ≥ 10 | brief #976 design call | structural evidence above-pattern is safer |
| N5 | Prints support-free, tray-down, repo FDM defaults | printcheck + slice | repo FDM conventions | printer constraint changes |
| N6 | Rated payload at defaults stays under the root-stress allow | ≤ 400 g → σ ≤ 10 MPa | brief #976 assumed payload | field-test evidence the allow is wrong |

## Out of scope

**Deferred** — hook variant (swap tray for two mirror hooks); strap-post
beyond the single cable-loop ear; multi-pitch plates that cover 75 and 100
in one print; clamp-on adapters for arm heads that fully cover the VESA
holes.

**Never** — printed threads into plastic for the VESA mount; adhesives or
strap-only mounting as the primary path; inventing VESA pitches beyond the
published 75 / 100 square patterns; a second design directory for 75 × 75
(pitch is a parameter).

## v1 — definition of done

- [ ] Gate: `render.sh` clean, `gate.sh --slice` exit 0, printcheck on `shelf`
- [ ] Brief Must-fit realized as parameters: pitch, M4 clearance, plate_t,
      tray 110×80, tray_drop 25, engagement assert
- [ ] README lists purchased M4 hardware and the arm-head coverage note
- [ ] Product page passes `readme-gate.sh` after regen commit-back
- [ ] No fit coupon (no printed mating fit)

## Product page & shots (art direction)

**Page promise.** "Your Pi, on the VESA holes you already have."

**Mechanism honesty.** No moving mechanism — the as-printed `contact-sheet`
(tray on the bed, plate standing) is the honest view beside the hero.

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | whole shelf, plate + tray + lip | high 3/4 from open-cable side | 2a9d8f / satin | — |
| contact-sheet | what you print | 4-view | — | default |

**AI product stills — tier 1.5.** None yet.

**Lifestyle scenes — tier 2.** None yet — a behind-monitor desk scene
seeded from `product-hero` once a field-test entry exists.

**Motion clips — tier 2.** None — nothing moves.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Field-test on a real 100×100 arm-mounted display | closes N3/N6 on hardware | one print + 4 screws |
| B2 | Hook variant (`part="hook"`) | brief optional; cable-only users | small session |
| B3 | Tier-2 lifestyle behind-monitor scene | page polish | one AI shot |
| B4 | Dual-pitch plate (75+100 holes) | niche; most users pick one | geometry + docs |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Does the user's arm head cover the VESA holes? | No | README disclosure; not geometry |
| Keep the hook variant? | No | Tray-only v1 |
| Is `tray_drop=25` the right reading of brief "standoff"? | No | Vertical drop; see NOTES.md |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-11-07 | Tray-only v1; hook deferred | Brief marks hook non-blocking; one part keeps the PR reviewable |
| 2026-11-07 | `tray_drop` = brief standoff 25 | Tray-below-pattern call; tray depth stays `tray_d=80` for Pi fit |
| 2026-11-07 | Stress assert, no `ci.fitchecks` | Repo fitchecks are boolean mates; no mating pair here |
| 2026-11-07 | Style `workshop-utility` | Brief Style line |
