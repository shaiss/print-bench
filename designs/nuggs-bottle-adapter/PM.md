# nuggs-bottle-adapter — product charter

## The product, in one paragraph

The one part that turns an off-the-shelf PCO-1881 water bottle into a
N.U.G.G.S. habitat module, for keepers who want bottle service (water,
bedding dispensing) without special hardware. The one thing it must do well:
grip a standard bottle securely enough that a nudging animal cannot unscrew
it, while never passing less than the bottle's own orifice. This is a
**service** module, not a transit module — the animal does not pass through
it, and the NUGGS welfare charter's transit rules apply to the port below,
which stays full standard.

## Non-negotiables

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | NUGGS port = the standard, unmodified | 80 mm bore, full `nuggs_cfg()` defaults | the NUGGS standard (`designs/nuggs/PM.md`) | the standard itself changes |
| N2 | Thread form = PCO-1881, single-start | crest 27.4, pitch 2.7, 650° | ISBT standard; owner ruling on #515 "the standard is the spec" | a sibling finish is added deliberately (then it's a parameter, not a change) |
| N3 | Passage never chokes the bottle | land opening ≥ 21.74 mm | the standard's orifice | a sealed variant is chartered |
| N4 | Supportless in the family pose | every surface ≤45°, port-down | bench printability rule (issue #34's measured ceiling) | measured failure on a real printer |
| N5 | Coupon gates the fit before the body is trusted | 4 tols swept | issue #515 brief | — |

## Out of scope

**Deferred** — backlog, ranked: (1) O-ring/watertight sealing variant (brief
left watertightness non-blocking; default is the printed land); (2) male
cap-plug variant (brief's non-blocking question); (3) PCO-1880 (3-start)
sibling finish — the parameter exists, a variant is a copy.

**Never:** making the throat a transit path (the passage is the bottle's own
orifice — widening it means the bottle falls through), and hand-tuning
thread geometry off the library profile (`lib/threads-fdm.scad` keeps male
and female from drifting apart).

## v1 — definition of done

- [ ] All five gate-contract boxes on issue #515 pass (render, gate --slice,
      readme-gate, measured Must-fit realization, /preflight)
- [ ] Coupon's port station locks with a mating NUGGS module (field check)
- [ ] At least one coupon ring grips a real PCO-1881 bottle without cracking
      or skipping (field check), and `bottle_tol` is set to it
- [x] NOTES.md records the single-start correction and the load-path
      correction against the brief
