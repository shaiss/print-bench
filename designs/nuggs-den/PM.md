# N.U.G.G.S. Den — product charter

## The product, in one paragraph

The **terminal module** of the N.U.G.G.S. system: a single-port rounded refuge
bulb that caps the end of a run. Its customer is the owner of an adult **Syrian
hamster** who is building a short NUGGS bridge and wants it to *end somewhere* —
a place to hide, hoard and scent-mark — rather than at a blank wall. The one
thing it must do well: be a genuine **refuge** (opaque, ventilated, its own) for
a prey animal, while still mating any NUGGS face by the shared quarter-turn
port. It is the only NUGGS module that is deliberately closed rather than open.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Mates the shared NUGGS port unchanged | `nuggs_cfg()` defaults, `port_tol 0.30` | `lib/nuggs-coupling.scad`; one interlock for the system (nuggs PM.md N10) | Never — a den that needs its own joint is not a NUGGS module |
| N2 | Bore clears a pouched Syrian | ≥ 70 mm | Deutscher Tierschutzbund entrance minimum (lib bore floor assert) | A larger sourced entrance figure |
| N3 | Opaque refuge — the bulb is closed and windowless | 0 windows | The refuge critique of clear tube (Merkblatt 62; `docs/nuggs-research.md`) | Never — opacity *is* the product |
| N4 | Ventilated despite being closed | ≥ 1 crown vent, teardrop (support-free) | The condensation critique of tube (Merkblatt 62) | Never — a sealed refuge is the failure mode it exists to avoid |
| N5 | Prints support-free in the coupling's own orientation | every slope ≤ 45°, `shoulder ≥ 1.0` assert | Repo FDM convention; NUGGS ports print on their lug tips | Never |
| N6 | No chew-initiation edges the animal contacts | rounded rail, flared mouth, blunted crown | nuggs PM.md N6 (anti-chew) | Never |

## Out of scope

**Deferred** — see backlog: a product studio shot (`shots.conf`), a sweep or
FIELD-TEST once printed, a size variant.

**Never:**
- **A turnaround.** The den is a dead-end refuge; making it wide enough to turn
  around in (≥ body length internal) is a *different* module (a node). Do not
  let a den masquerade as a run-length break — it does not reset the count.
- **A transparent/observation dome.** That is the opposite of the product (N3).
- **A food dish / water port / wheel mount.** Feature creep; the den is a room,
  not an appliance. Those are separate designs if wanted.

## v1 — definition of done

- [x] Mates the shared NUGGS port at standard defaults (uses `nuggs_cfg()`).
- [x] Closed opaque bulb with ≥ 1 support-free crown vent and an internal
      flank rub rail.
- [x] `gate.sh --slice` green; watertight, one body; warnings only.
- [x] Product page documents the dead-end scope honestly (not a run break).
- [ ] Coupon printed and `port_tol` tuned on real plastic (whole-system open).

## Product page & shots (art direction)

**Page promise.** *"The room your hamster tunnel has been missing."* A stranger
should grasp in one look that this is where a run **ends** — a cosy, opaque,
vented burrow-bulb — and that it clicks onto the same joint as everything else.

**Shot list — tier 1 (real studio renders).** Deferred to a follow-up (needs a
`shots.conf`; CI renders it). Until then the frozen `hero` and `cutaway`
previews carry the page.

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the turret as a finished object | hero | warm matte | — |
| product-cutaway | the refuge + rub rail inside | side section | warm matte | `part="cutaway"` |

**Lifestyle scenes — tier 2 (AI, cosmetic, disclosed).** Optional, deferred.

| Shot | Scene |
|---|---|
| den-in-use | a Syrian curled inside a bedding-lined den at the end of a short run |

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Print coupon, tune `port_tol` | The whole system is unproven in plastic | 1 coupon (~2 h) |
| B2 | Studio product shot (`shots.conf`) | Sells the page; the promise is visual | CI render |
| B3 | Smaller size variant (`bulb_r ~50`) | Default is ~10 h / 127 g; some want less | param only |
| B4 | FIELD-TEST after a real print | Close the print-feedback loop (#101) | 1 print |

## Open decisions

| Question | Blocking? | Assumption if unanswered |
|---|---|---|
| Is 116 mm OD / ~10 h an acceptable default, or ship smaller? | No | Ship generous (a refuge is a room); `bulb_r` is the lever |
| Add a studio product shot now or defer? | No | Defer; frozen previews carry the page (B2) |

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-10 | Terminal single-port refuge, not another tube/elbow | The system had no place to *stop*; the ask was a unique non-tube part |
| 2026-08-10 | Consumer of `lib/nuggs-coupling.scad`, no `derives.conf` | It includes the library, not another design's `.scad` |
| 2026-08-10 | Dead-end, explicitly not a run-length break | Honest welfare scope; 110 mm internal < body length, cannot turn around |
| 2026-08-10 | Crown as a support-free cone, tip blunted by a sphere | Support-free roof with no sharp poke point / singular apex |
