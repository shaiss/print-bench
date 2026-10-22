# nuggs-port-gauge — product charter

## The product, in one paragraph

A calibration gauge for anyone printing NUGGS modules: one reference head
and a five-step `port_tol` ladder on two plates. It turns the inherited
`port_tol = 0.30` guess into a measured number for that printer.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | All five `port_tol` steps ship | {0.20, 0.25, 0.30, 0.35, 0.40} | brief + HITL `ladder-plate-layout` YES | owner revisits the HITL |
| N2 | Step centres clear the mating envelope | ≥ Ø96.8 mm (`2 · r_out`) | measured ring OD | `bore_d` / `lug_r` / `wall` change |
| N3 | Every step is `nuggs_cfg(port_tol=…)` only | no bespoke coupling | brief | lib API gains a second fit knob |
| N4 | Multi-object 3MF deliverable | 3 plate parts | `ci.plate` / alcove-rod-socket lesson | never a fused STL |
| N5 | Walls / emboss printable | wall ≥ 1.2, emboss 0.60 | repo FDM defaults + brief | nozzle class changes |

## Out of scope

**Deferred**

- Printed `port_tol = 0.10` negative-control step (brief open question).
- Mirror-readable emboss on the mating face.
- Writing `printer.conf` from a field result (print-feedback loop, post-print).

**Never**

- Changing `lib/nuggs-coupling.scad` or other modules' inherited 0.30.
- A full-run axial straightness check.
- A style pack — this is a calibration artifact.

## v1 — definition of done

- [ ] Three printable parts gate and slice clean (`gate.sh --slice`).
- [ ] All five steps present; fitchecks empty per step + interfering control.
- [ ] Product page passes `readme-gate.sh`.
- [ ] Multi-object plate builds with object count 3.

## Product page & shots (art direction)

**Page promise.** One gauge replaces N single-value NUGGS coupon reprints.

**Shot list — tier 1.** Geometry-true camera previews (no Cycles hero required
for v1): contact sheet of the assembled layout; reference head; ladder-3;
ladder-2; cutaway. All five shots are frozen as reviewed — any future
reframe is a new `cameras.conf` line, never a moved one. Lifestyle / AI
tiers: none — a calibration tool.

## Ranked backlog

1. Field-test the ladder on a real printer and log the winner — first thing
   after merge; no further work on this design before the first FIELD-TEST
   entry lands. On that first plate: note whether adjacent rungs felt
   identical (if ties are common, add an expectation line); if a glyph fuses
   into a lug edge, raise `plate_margin` by +1 mm (centres unmoved).
2. Optional physical 0.10 negative-control step if users ask.
3. Seed a `printer.conf` recipe from a decisive field result.
4. Fuller quarter-section cutaway shot (J7 + Drik r2): the committed cutaway reads as one shell rather than a mated pair; preview legibility only.

## Open decisions

(none — `ladder-plate-layout` resolved YES on 2026-10-12.)

## Decision log

| Date | Decision | Verdict | Notes |
|---|---|---|---|
| 2026-10-12 | `ladder-plate-layout` | YES — two plates, five values | Keel /decide on #514 |
