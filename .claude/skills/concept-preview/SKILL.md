---
name: concept-preview
description: Draw a design's blueprint-style concept sheets — exterior elevation, cutaway half-section, top section, exploded view with bill of parts — as four checked SVGs in the one house drafting style, by composing a small placement spec the tool renders. Use when asked for a concept preview, concept sheets, a blueprint or technical-illustration view of a design (before or after it is modelled), a "how it works" cutaway, an exploded parts drawing, or when invoked as /concept-preview [name].
---

# Concept preview — the blueprint sheets a human reacts to

A concept sheet is what a person looks at to approve a design's *direction*
before (or beside) its geometry: what it looks like closed, how the mechanism
works, how the parts sit in plan, what it comes apart into. Every design gets
the **same four sheets in the same style**, so a reviewer builds an intuition
that transfers from one design to the next (#473) and the site can serve them
as crisp vector art (#474).

The split is the whole method: **you compose the spec; the tool owns the
look.** `designs/<name>/preview-spec.conf` says *what* is drawn and *where*;
`tools/concept-preview` decides every colour, line weight, font, hatch,
marker, header and title block, identically on every sheet. You never write
SVG, never pick a colour, never hand-edit an emitted sheet. The mechanics live
in `scripts/concept-preview.sh`; the judgment lives here.

This is an authoring skill — run by a human or a design session, never on a
schedule. It writes files in the design's directory and nothing else.

## 0. Load what the sheets must show

Read the design before drawing it:

- **`designs/<name>/NOTES.md`** — the goal, the given measurements, the
  mechanism, the intended print orientation. The concept is *this* design,
  not a generic one.
- **The entry `.scad`'s parameter block** — the numbers a dimension quotes
  come from here (or from NOTES.md's measurements when nothing is modelled
  yet). Never invent a dimension; a sheet that states a number the design
  does not have is worse than one that states none.
- **`designs/<name>/PM.md`** if it exists — what the page promises; the
  concept should show the thing the customer is buying.
- **`assembly.conf` / `ci.parts`** if they exist — the real part list, so the
  bill of parts and the balloons match what ships.

Before the design exists at all (an early brief), draw from the brief and
state on the sheet's note what is assumed.

## 1. The four sheets, and what each is for

| Sheet | Says | Typical rows |
|---|---|---|
| `exterior` | what it looks like, closed — the silhouette and the overall size | `hex`, `shank`, `leader`, `dim` |
| `cutaway` | how it works — a longitudinal half-section through the mechanism | `hatch` (cut walls), `shank`, `hex`, `balloon`, `leader`, `dim` |
| `section` | how the parts sit in plan — the top section A–A | `hatch` rings/discs, `leader`, `dim` |
| `exploded` | what it comes apart into, in assembly order, plus the bill of parts | `hex`, `shank`, `balloon` (keyed to `part:` rows), the `bom=` table |

All four are required, every time — the consistent set *is* the feature. Each
may carry one `note:` box (an assumption, a legend, assembly steps).

## 2. What the tool does for you

```bash
./scripts/concept-preview.sh --vocab          # every row and field the spec accepts
./scripts/concept-preview.sh <name>           # parse, draw, check, write the four sheets
./scripts/concept-preview.sh --check <name>   # the committed sheets are current and clean
```

The six primitives: `hatch` (hatched section — rect or ring), `shank`
(threaded shank), `hex` (hex head/nut), `dim` (dimension line), `balloon`,
`leader`. Their fields are in `--vocab` and the tool's README
(`tools/concept-preview/README.md`, with a worked spec); the fixture
`tools/concept-preview/fixtures/valid.conf` is a complete example.

Every write is preceded by every check, on every sheet: valid XML, no external
reference, **every element inside its sheet** (strokes and the leader dots and
arrowheads included), **no two labels overlapping**, **no leader or dimension
line struck through a label**, nothing on the title block or header — and
nothing is written unless all four pass. A refusal names the spec line
(`preview-spec.conf:31: …`); that is your feedback loop.

## 3. The loop

1. **Lay out each sheet on paper first.** Pick the scale (px per mm) for the
   sheet so the part fills the drawing area between the header band (the top
   ~104 px) and the title block (the bottom ~104 px, right-hand 236 px), with
   room on one side for labels. Coordinates are sheet pixels, origin top-left.
2. **Write the rows** — part geometry first (later rows paint over earlier
   ones), then leaders, dimensions and balloons. Put labels on the side with
   room and leave a line of space between neighbours.
3. **Run `./scripts/concept-preview.sh <name>`** and fix what it refuses. A
   collision means move a label — never shrink the text or reach for a
   different look; an overflow means shorten the words.
4. **Look at the sheets.** The checks prove the sheets are clean, not that they
   are *right*: does the cutaway actually explain the mechanism? does the
   exploded view read top-down in assembly order? Send the four SVGs to the
   human (`SendUserFile`) and let them react to the concept.
5. **Commit** the spec and the four sheets together; `--check` must pass.

## 4. Respect the standards — the freedom is in the composition

- **The look is not yours to change.** No colours, fonts, weights or furniture
  in the spec — there are no fields for them, by design. A sheet that needs a
  different look needs a palette change in `tools/concept-preview`, reviewed
  as a tool change for every design at once.
- **Explicit placement.** The tool does no auto-layout; you place everything.
  When a label collides, you move it.
- **Honest numbers.** Every dimension and callout traces to the `.scad`
  parameters or NOTES.md. "≈" for an approximate value, "NTS" stays on the
  title block (concept sheets are not to scale).
- **Never hand-edit an emitted sheet.** It is derived from the spec; edit the
  spec and re-run. `--check` fails on a sheet that no longer matches.
- **A concept is not the geometry.** The STL and the tier-1 render remain the
  source of truth for the shape; a concept sheet that disagrees with the model
  is a finding to reconcile, not a reason to leave the drawing as it is.

## 5. Output

Consulted directly: a short plan — the scale you chose per sheet, which
feature each sheet makes legible, and any number you could not source (left
off, or noted as assumed). Then write the spec, run the tool until it passes,
send the four sheets to the human, and update NOTES.md with a line saying the
concept sheets exist and what they assume.
