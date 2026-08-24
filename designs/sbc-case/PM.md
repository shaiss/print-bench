# sbc-case — product charter

## The product, in one paragraph

A parametric single-board-computer case — Raspberry Pi 4 as the primary
target — built deliberately **hardware-rich** to be the reference /
stress-test design for the assembly-instructions feature: it is the first
`assembly.conf` in the catalog declaring real `vitamin:` entries, so it
exercises the NopSCADlib vitamin path, the BOM collection pass and the
GPL-3.0 product-page disclosure nothing else does. It must also stand on
its own as an everyday print — a vented Pi 4 case that bolts the board down
and mounts a 40 mm fan in the lid. The customer is a stranger with a Pi 4
and a shopping list; the one thing it must do well is **assemble exactly as
the BOM and steps say**.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | Standoff pattern generated from `pcb_holes(board)` at build time — never hand-typed | 4 holes, from the vitamin | brief design note; gated by `ci.fitchecks` (`fit-pins` empty / `fit-pins-shift` interferes) | a future OpenSCAD makes derivation impossible — unlikely |
| N2 | `assembly.conf` declares real `vitamin:` entries (board, inserts, screws, washers, fan) | ≥ 5 distinct vitamin types | brief "Why it exists" — the hardware count **is** the deliverable, not gold-plating | the design stops being the assembly stress-test |
| N3 | Product page names **GPL-3.0** (NopSCADlib combined work) | req #11 | brief; `readme-gate.sh` branch b | the design drops NopSCADlib — then it must not claim it |
| N4 | Support-free: fan aperture and every port edge bridgeable or chamfered | printcheck 0 criticals | brief Printer & material | never |
| N5 | Walls ≥ 1.2 mm, target 2.0 | 2.0 mm | repo FDM default; brief | never |
| N6 | Lid fastens with screws into heat-set inserts — not self-tappers | 4 × F1BM3 + M3×10 | brief assumptions (rich hardware BOM is the goal) | never |

## Out of scope

**Deferred** — ranked in the backlog below.

**Never** — a passive no-fan variant (the fan is the BOM-richness
deliverable, brief Open question 4 says it stays); hand-typed board
footprints (defeats N1); a style pack (brief: `none` — the look is clean
vents and a tidy parting line).

## v1 — definition of done

- [x] `gate.sh --slice sbc-case` exits 0 on `base`, `lid` and the coupon
- [x] `ci.fitchecks` proves N1 on the exported mesh (pins through pilots /
      shifted pins interfere)
- [x] `assembly.conf` generates `previews/exploded.png` + `ASSEMBLY.md`
      with every vitamin in the BOM (N2)
- [ ] `readme-gate.sh sbc-case` passes incl. the GPL-3.0 disclosure (N3) —
      every requirement passes except the embedded CI-rendered images below
- [ ] CI `regen` has committed the shots and exploded view on the PR
      (manifests and embeds are ours; pixels are CI's)

## Product page & shots (art direction)

**Page promise.** A stranger sees exactly what to print and what to buy,
and believes the assembly before trying it.

**Shot list — tier 1 (real studio renders).**

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | the closed case, fan in the lid | hero | #35383d satin | `part="assembled"` |
| product-base | board on generated standoffs, ports open | high angle | #35383d satin | `part="base"` |

Frozen preview cameras (`previews/cameras.conf`): `iso`, `top`, `ports`
(assembled) and `board` (base) — add rows, never reframe.

No tier-1.5 / tier-2 AI shots: a functional print sells on the real
geometry, and the GPL/first-party story stays clean.

## Backlog, ranked by user value

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | Modeled per-port cutouts (USB/HDMI/Ethernet/USB-C) instead of open skirted edges | the biggest look upgrade; brief Open question 2 deferred it for support-free risk | medium — 4 cutout profiles + re-gate |
| B2 | Additional validated board presets (RPi 3B+/5, Zero 2 W) | `pcb_holes()` derivation makes it nearly free; each board still needs its port wall checked | low per board — parameter + render + check |
| B3 | Fan shroud / duct over the SoC | brief's optional part, declined for support-free; only worth it with a measured thermal story | medium — new part + slice gate |

## Open decisions

None open. The brief's four questions were all non-blocking and resolved on
their stated assumptions (see the decision log).

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-23 | Fan = `fan40x11` (catalog) | brief's 40×10 assumption explicitly swappable; 40×11 is the vendored catalog's 40 mm fan |
| 2026-08-23 | Board fastener = M2.5 cap screws into printed pilots | brief claimed no M2.5 insert exists — `F1BM2p5` does exist but is 5.8 mm long, taller than the 5 mm standoff; measurement over brief |
| 2026-08-23 | Port strategy = three open skirted edges | brief's own time-boxed default (Open question 2); modeled cutouts → B1 |
| 2026-08-23 | Fan in the lid, intake, biased to the SoC | brief assumption (Open question 3); side-wall fan never ranked |
| 2026-08-23 | Fan stays in the reference BOM | brief Open question 4, assumed yes |
| 2026-08-23 | `assembly.conf` vitamin lines name design-file wrapper modules, not raw constants | `assembly.sh`'s generated preview `use`s the design file — variables don't cross `use`, so `pcb(RPI4)` aborts; measured, filed as #368 |
| 2026-08-23 | Base shell drawn origin-centred (`translate` around `rounded_box`) | `rounded_box` is corner-anchored; un-translated it split the base into 7 disjoint bodies that every presence-only gate passed (printcheck 92 "fine if intentional", clean slice, empty fitchecks) — caught only by measuring the export, issue #69's class; fixed and re-measured 1 body, 100/100 |
