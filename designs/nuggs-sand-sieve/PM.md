# nuggs-sand-sieve — product charter

## The product, in one paragraph

A bathing-sand **sieve end-cap** for the 80 mm-bore N.U.G.G.S. hamster-tunnel
system: the maintenance half of the sand-bath kit. An owner docks it on the
bath (or holds it over a bin), pours used sand into the open basket, shakes —
clean sand falls back through the printed grid and the bore; debris stays to
be tipped out. The one thing it must do well: pass bathing-sand grains and
retain bedding scraps, on the standard NUGGS port, with no slicer supports.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | NUGGS port = the standard, unmodified | 80 mm bore, full `nuggs_cfg()` defaults | `lib/nuggs-coupling.scad` | the standard itself changes |
| N2 | Grid web ≥ wall floor | ≥ 1.2 mm | repo FDM conventions | measured print failure |
| N3 | Supportless in the family pose | every surface ≤45°, port-down | bench printability rule | measured failure on a real printer |
| N4 | Coupon gates the port fit before the basket is trusted | stub + grid tile | issue #835 brief | — |
| N5 | Sand, not chinchilla dust — welfare line on the page | README | sand-bath precedent (#667) | — |

## Out of scope

**Deferred — ranked backlog:** (1) woven steel drop-in replacement mesh;
(2) staggered / round hole option if field sand demands it; (3) matched
sand-bath docking clocking marks.

**Never:** hardware or adhesives; leaving the sieve mid-run as corridor
passage; thinning webs below 1.2 mm to chase open area.

## v1 — definition of done

- [ ] Gate contract on issue #835 (G1–G5) green locally
- [ ] Coupon + `ci.fitchecks` (mates empty + mates-ctrl interferes)
- [ ] README carries sand-not-dust welfare line and wash/heat caveat
- [ ] NOTES records docking/run-length ruling and hole-shape decision
- [ ] Draft PR closes #835

## Product page & shots (art direction)

**Page promise.** This is the missing half of the sand-bath kit — sift, don't
replace.

**Shot list — tier 1.**

| Priority | Shot | Why |
|---|---|---|
| 1 | `product-hero` | Whole sieve, port down, mouth up — the use/print pose |
| 2 | contact-sheet | Honest print pose / bed contact |
| 3 | `grid` | The lattice at print scale |

**Tier 1.5 / 2.** None for v1.
