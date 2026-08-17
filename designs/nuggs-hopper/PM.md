# N.U.G.G.S. Feeder Hopper — product charter

Enforced by `/pm nuggs-hopper`. Engineering log: `NOTES.md`. Product page:
`README.md`. Design brief: #281. Inherits the system charter
[`designs/nuggs/PM.md`](../nuggs/PM.md) (N1–N11) — a module is not a new
charter, so only the hopper-specific lines live here.

## The product, in one paragraph

The **feeding module** of the N.U.G.G.S. system: a gravity-fed top-fill hopper
that couples onto any NUGGS face, holds a few days of pellets behind a printed
mesh floor, and drops them into the enclosure as they are eaten. Its customer
is the owner of an adult **Syrian hamster** running a NUGGS bridge who wants
feeding to be a refill-from-outside action instead of a reach-into-the-cage
one. The one thing it must do well: **feed reliably by gravity alone** —
pellets in at the top, pellets out at the bottom, nothing the animal or the
food can jam — while mating the shared quarter-turn port unchanged.

## Non-negotiables

Inherited whole from `designs/nuggs/PM.md` (N1–N11). Hopper-specific:

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| H1 | Mates the shared NUGGS port unchanged, both ends | `nuggs_cfg()` defaults, `port_tol 0.30` | `lib/nuggs-coupling.scad`; nuggs N10 | Never — a hopper with its own joint partitions the kit |
| H2 | Bore clears a pouched Syrian at every passage | ≥ 70 mm | nuggs N1 (lib bore-floor assert) | A larger sourced figure |
| H3 | Mesh opening is an entry barrier, not a grate | ≤ 12 mm | brief: sized to stop a head / stuffed pouch (issue #281); welfare cap | Never for convenience. Tunable down/up only within the cap for pellet size |
| H4 | Gravity only — no metering, no anti-hoarding mechanism | 0 mechanisms | brief assumption, issue #281 | A jammed feeder is a starved animal; a mechanism that can jam is worse than no mechanism |
| H5 | Prints support-free in the coupling's own orientation | every slope ≤ 45°, `shoulder ≥ 1.0` assert | Repo FDM convention; ports print on their lug tips | Never |
| H6 | No chew-initiation edges the animal contacts | rounded funnels, buried floor edge, rib ≥ gnaw floor | nuggs N6 | Never |

## Out of scope

**Deferred** — see backlog: a studio product shot, a trapped **steel** mesh
variant (the brief's open question), a FIELD-TEST entry, capacity variants.

**Never:**
- **A metering or anti-hoarding auger.** H4 — the brief scoped it out and a
  jam is the failure this module exists to avoid.
- **An in-cage mounting orientation.** The hopper couples to a run or a
  cage-wall stub with ports vertical; an in-cage L is nuggs charter Never
  scope.
- **A food dish / water / wheel integration.** Feature creep; separate designs.

## v1 — definition of done

- [x] Mates the shared NUGGS port at standard defaults, both ends
      (uses `nuggs_cfg()`; no coupling number restated).
- [x] Gravity-fed: continuous bore top to bottom, mesh floor passable by
      pellet, impassable by head or stuffed pouch (8 mm cells, H3-capped).
- [x] `gate.sh --slice` green; watertight, one body; warnings only.
- [x] Coupon ships (fit unproven, issue #56) and the page says print it first.
- [x] Product page documents the assumption trail (mesh size, body length).
- [ ] Coupon printed and `port_tol` tuned on real plastic (whole-system open).

## Product page & shots (art direction)

**Page promise.** *"Fill it from outside; gravity does the rest."* A stranger
should grasp in one look that this is the feeding module — a hopper bulb on
the same quarter-turn joint as everything else, refilled through its own top
port without opening the cage.

**Shot list — tier 1 (real studio renders).** Ranked; the first is the hero.

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| hero | The whole module standing as used — bulb, both ports | three-quarter | natural PETG, matte | — |
| cutaway | The feed path: bore, cavity, mesh floor | sagittal section | neutral, cut faces | `part="cutaway"` |
| floor | The 8 mm entry barrier itself | top-down through fill port | neutral | — |

No tier-1.5 / tier-2 rows yet — the AI tiers are backlog until the geometry
tiers are reviewed (see backlog B3).

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | **Print the coupon, tune `port_tol`** | The fit is the whole part; every number is a guess until plastic says otherwise (nuggs B1a, issue #56) | ~30 g, ~2¼ h ×2 |
| B2 | Capacity variants (`bulb_r`, `eq_h` presets) | Second thing a real user asks after "does it fit": "can it be bigger/smaller". Parameters already exist; presets are a README row | page edit only |
| B3 | Tier-1.5 product still + tier-2 lifestyle scene | The page sells a *feeding story*; a staged scene (hopper on a cage, pellets) would carry it. AI tiers wait for the geometry review | one manifest + CI |
| B4 | Trapped steel mesh variant | The brief's open question — a replaceable mesh for chewing-heavy households. Needs a rim trap design and a sourcing note | real design work |
| B5 | Turntable animation | Shows the quarter-turn coupling and the fill action; cheap once frozen cameras exist | `animations.conf` |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Real pellet size for the 8 mm cell | Not blocking | General hamster mix; `mesh_open` tunable within the H3 cap |
| Replaceable (trapped) steel mesh vs printed-in | Not blocking — backlog B4 | Printed-in (brief's first-pass scope) |
| Mounting: which face / cage-wall stub pairing | Not blocking | Ports vertical on any up-facing NUGGS stub |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-17 | Two ports inline (brief's part breakdown) over dome-end (its dimension row) | Top-fill "through the open port" requires a top port; recorded in NOTES.md for the PR reader |
| 2026-08-17 | Mesh floor is a flat disc, not a gabled profile | A gable would clear the overhang warning but doubles slab thickness and closes the opening upward — against food flow (H4's spirit) |
| 2026-08-17 | 8 mm is the *opening*, not the pitch | Carried from the prior run's hand-off; rib 2.4 mm derives pitch 10.4 mm |
| 2026-08-17 | Coupon ships even though elbow ships none | `port_tol` is flagged unproven (issue #56) and the contract froze G2 on it |
| 2026-08-17 | One-revolve body (nuggs-den construction) | The prior run's sphere∪cylinder shipped three disconnected volumes; a single revolve profile cannot come apart |
