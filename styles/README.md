# Styles — design languages you can pick from

A style is a **design spec lifted from a reference model you like**, written
down in a form that both a person and an agent can follow, and checkable
against anything built afterwards. Point `stylelift` at an STL you admire, and
it measures how that object is shaped — the radius it reuses on its edges,
whether it chamfers or fillets, how smooth its curves are, what size holes it
drills — and writes those out as numbers to build with plus rules to be held
to.

The point is choice. "Make me a cable clip" leaves the look to chance;
"make me a cable clip in the `workshop-utility` style" doesn't.

## Available styles

<!-- Every directory here must be listed. scripts/docs-check.sh enforces it. -->

| Style | What it is |
|---|---|
| [`workshop-utility`](workshop-utility/STYLE.md) | Generously rounded utility parts with 45° bed chamfers and an M3 fastener vocabulary. |
| [`ribbed-industrial`](ribbed-industrial/STYLE.md) | Finned housings on a 1 mm module: 5 mm ribs, a 1 mm break on every edge, nothing that needs support. |
| [`orrery`](orrery/STYLE.md) | Twisted-blade vortex cages carrying captive free-spinning rings in a second, non-welding material, every seat and lead-in the same 50° self-supporting cone. |

`./scripts/style-lift.sh --list` prints the same list from the packs
themselves.

## What is in a style pack

| File | What it is |
|---|---|
| `STYLE.md` | The spec you read before modelling: rules, tokens, do/don't, and where the style came from. Its tables are generated from `style.json`. |
| `style.json` | Source of truth — measured evidence, tokens, and the conformance rules. The only file you hand-edit. |
| `style.scad` | Generated tokens (`style_corner_r`, `style_fn`, …) a design includes and builds with. |
| `swatch.scad` | A small part written in the style; the style's own regression test. |
| `previews/swatch.png` | What the style produces. |

## Using a style in a design

```scad
include <styles/workshop-utility/style.scad>
use <printability.scad>

$fn = style_fn;
rounded_box([w, d, h], r = style_corner_r, bottom_chamfer = style_edge_chamfer);
```

Building from the tokens rather than retyping their values means the design
passes the style's rules by construction. To have CI hold the design to the
style on every push, name it in `designs/<name>/style.conf`:

```text
workshop-utility
```

Then `./scripts/style-check.sh` renders the design's printable parts and checks
each one, reporting per-rule pass / fail / not-applicable.

## Making a new style

```bash
./scripts/style-lift.sh <name> <reference.stl> --source <url> --license <terms>
```

That writes a **draft**. Finishing it — deciding which measured numbers are
really the family, writing the prose, adding a swatch — is the judgement half,
and it is what `/style-spec` walks through.

Two things the tool cannot do for you:

- **Tell style from happenstance.** A reference measures whatever it happens to
  be. A 15 mm "corner radius" may be the barrel of the object rather than a
  treatment of its edges; a "wall thickness" may be how thick that one plate
  was. Prune before you commit.
- **See what isn't geometry.** Colour, material, finish, and what the thing is
  *for* never reach an STL. They go in `asserted`, marked as claims rather than
  measurements.
