# concept-preview

Blueprint-style SVG **concept sheets** for a design, in one house drafting
style (issue #472). A design session composes a small spec of explicit
placements; this package owns the look and draws four standalone, checked
sheets from it:

| Sheet | File | Shows |
|---|---|---|
| 1 | `concept-exterior.svg` | exterior elevation |
| 2 | `concept-cutaway.svg` | cutaway / longitudinal half-section — how it works |
| 3 | `concept-section.svg` | top section |
| 4 | `concept-exploded.svg` | exploded view + bill of parts |

`scripts/concept-preview.sh <name>` reads `designs/<name>/preview-spec.conf`
and writes the four sheets to `designs/<name>/previews/`. The `/concept-preview`
skill is the authoring half: the model composes the spec, the tool owns the
look. Stdlib-only, no network, no install — the script runs the package
straight from `src/`, the `tools/cogcheck` / `tools/lineage` pattern.

## The style, and where it comes from

The drafting system — palette, grid, hatch, line and text classes, the amber
rule under the heading, title-block layout, dot and arrow markers, the
`SHEET n / 4` subtitle — is lifted from the approved **pre-roll elevator**
concept canvas: the four hand-authored sheets from that design's brief
session (issue #471), recorded in `designs/preroll-elevator/NOTES.md` and
published at
<https://claude.ai/code/artifact/b3e488f9-be4b-4bb9-a8c3-b8bc56c484d3>.

Those sheets each restated the same stylesheet. Here it is defined **once**,
in [`palette.py`](src/concept_preview/palette.py), and every emitted sheet
embeds the byte-identical `<style>` and `<defs>` — a test holds that — so two
sheets cannot drift apart and no consumer restyles anything:

- **Ground** `#0e2740` with a 20 px and a 100 px grid; **ink** `#d6e8f7`,
  secondary lines `#7fa8c9`, **amber** accents `#f4b24a`.
- **Line classes** `ln` `ln2` `metal` `cut` `amb` `ambd` `lead` `dimln` `cl`
  `tb` `bal`; **text classes** `t-h` (heading), `t-sub`, `t-lbl`, `t-amb`,
  `t-tb` (title block).
- **Fonts:** the reference loaded Oswald and IBM Plex Mono from Google Fonts.
  A served sheet carries **no external reference** (the product site's
  no-CDN rule, #474), so the stacks name those faces first — used when
  installed — and fall back through local families to `sans-serif` /
  `monospace`. Nothing is fetched; the checker refuses any `@import`, remote
  `url()`, non-fragment `href`, script or image.
- The sheet carries its own ground colour, so it reads the same under either
  site theme.

## The spec: `designs/<name>/preview-spec.conf`

The house `key: value` / pipe-row format. Coordinates are sheet pixels, origin
top-left, `x,y`; sizes are `WxH`. Rows draw in file order (a later row paints
over an earlier one). Comments are whole lines starting with `#` (a `#` inside
a value is kept). The full field list is generated from the parser —
`./scripts/concept-preview.sh --vocab` — so it cannot drift from what is
accepted.

```text
title: PRE-ROLL ELEVATOR
rev: A

sheet: exterior | subtitle=EXTERIOR ELEVATION — CLOSED
sheet: cutaway  | subtitle=LONGITUDINAL HALF-SECTION
sheet: section  | heading=TOP SECTION A–A
sheet: exploded | bom=372,176

part: n=1 | name=Lid — hex cap nut | print=open up

hex: exterior | at=162,182 | size=176x78 | ends=top | chamfer=16
shank: exterior | at=170,260 | size=160x368 | pitch=12
leader: exterior | at=140,210 | to=176,214 | text=HEX CAP-NUT LID | sub=unscrew to open
dim: exterior | from=384,182 | to=384,700 | text=≈ 130 | ext=338,342
balloon: exploded | at=120,176 | n=1 | to=196,176
note: exterior | head=NOMINAL | line=4 rolls @ Ø7 × 70 mm
```

All four `sheet:` rows are required (every design presents the same set — the
point of #473's consistent HITL previews), the exploded sheet needs `bom=`,
and there must be at least one `part:`. A complete worked spec is the
selftest fixture, [`fixtures/valid.conf`](fixtures/valid.conf).

The parser is **fail-loud**: an unknown key, primitive, sheet or field, a
missing or repeated field, a malformed value, a balloon naming no declared
part — each refuses the whole spec with `file:line: message`. A silently
skipped row would be a part missing from a sheet that every check then passes.

## The six primitives

Pure functions in [`primitives.py`](src/concept_preview/primitives.py), each
returning an SVG fragment plus its footprint and label footprints. Placement
is explicit — a primitive never nudges, wraps or reflows; it refuses only what
it cannot draw honestly, and that refusal becomes a spec error at its line.

| Row | Primitive | Draws |
|---|---|---|
| `hatch` | hatched section | a cut face: `at=`+`size=` (rect) or `center=`+`r=`[+`ri=`] (ring / solid disc) |
| `shank` | threaded shank | body outline, a thread profile anchored to the shank's own flanks every `pitch` px |
| `hex` | hex head / nut | side elevation across corners: chamfered `ends`, face edges at the quarter points, optional `grip` ticks |
| `dim` | dimension line | axis-aligned amber line with arrows, optional extension lines from `ext=`, the value beside it (`flip` for the other side) |
| `balloon` | balloon | a numbered circle keyed to a `part:`, optional plain leader to the part |
| `leader` | leader | a label (+ optional quieter `sub` line) with a dotted leader to its feature; `tone=amber` for callouts |

The sheet furniture — header, note box, bill of parts, title block — is the
emitter's, laid out the same on every sheet. Furniture text that would overflow
its box is a spec error naming the line ("shorten it — the emitter does not
wrap"), never a reflow.

## The checks

[`check.py`](src/concept_preview/check.py) re-measures every emitted sheet from
the **file**, not from the emitter's bookkeeping (a test holds each
primitive's footprint equal to the checker's measurement):

| Rule | Proves |
|---|---|
| `xml` | the sheet parses as XML |
| `contract` | the sheet stays in the vocabulary the checker can measure — every drawable element inside a `cp-<kind>` group naming its spec line, ground/header/**title block** present exactly once, only absolute `M L H V Z` paths, no transform but a text quarter-turn, the palette's stylesheet byte for byte (no inline `style=`, no presentation attribute on a container — root, group, `<defs>`, `<marker>` — to inherit down), markers only at the ends of an open outline. Anything else is refused, never skipped. |
| `external` | no external reference of any kind |
| `bounds` | everything an element *paints* lies inside the sheet's viewBox — half its stroke width past the outline, each miter tip, and each marker (a leader's dot, a dimension's arrowheads) as the sheet's own `<marker>` draws it |
| `collision` | no two labels overlap; no label or shape intrudes on the furniture; and no connecting line — a leader, a balloon's leader, a dimension or extension line — runs through a label or the furniture (measured segment by segment, not by the annotation's box) |

Labels are measured with a deterministic monospace model: every face in the
mono stack advances 0.6 em per glyph, which makes a label's footprint
computable without a renderer. A balloon sitting on the part it names is
allowed (a drafting convention the reference uses); label-on-label is not —
the exact class of bug a manual second pass caught on the pre-roll canvas.

`build` writes the four sheets only when all four pass — a sheet set is
committed whole or not at all.

## Commands

```bash
./scripts/concept-preview.sh <name>          # write designs/<name>/previews/concept-*.svg
./scripts/concept-preview.sh --check <name>  # fail if the committed sheets are stale/missing/failing
./scripts/concept-preview.sh --vocab         # the spec vocabulary
./scripts/concept-preview.sh --selftest      # fixture + negative controls (run by check.sh)

# the package directly (what the script runs)
PYTHONPATH=tools/concept-preview/src python3 -m concept_preview build <spec> --out <dir> [--verify]
PYTHONPATH=tools/concept-preview/src python3 -m concept_preview check <svg>...
```

Exit codes: `0` pass; `1` a check failed (or `--verify`/`--check` found the
sheets stale); `2` the spec was refused or bad usage.

## Selftest and tests

`--selftest` runs [`fixtures/valid.conf`](fixtures/valid.conf) — four sheets
that must pass every check — then appends each `fixtures/neg-*.conf` delta to
it and requires that it **fail with the check it names** on its first line
(`# expect: spec|bounds|collision`): a malformed spec, an out-of-bounds
element, two overlapping labels. The base passing first proves each control
fails because of its own lines. The selftest also fails when a control
passes, fires the wrong check, or when the set stops covering all three
classes — deleting a control cannot leave the run green.

```bash
python -m pytest tools/concept-preview/tests -q
```

The suite pins every parser refusal at its line, each primitive's guards and
checker parity, every checker rule on a real emitted sheet with one injected
defect, the drafting system embedded identically on every sheet with no
colour outside the palette, deterministic output, the selftest's own
meta-controls, and the package shape (stdlib only, nothing network-capable,
`cli.py` the only filesystem writer). CI runs it as `concept-preview unit
tests` when the tool, the wrapper or `ci.yml` change.

## Not in v1

- **No design consumer yet.** A `designs/preroll-elevator/preview-spec.conf`
  reproducing the approved canvas is the natural first one (a follow-up).
- **Not regenerated by CI.** The sheets are derived from the spec, so they
  could join the `regen` job beside the other previews; v1 commits them from
  the skill run and `--check` proves them current.
- **Six primitives.** Centre lines, motion arrows, payload ghosts and a hex
  plan view are drawn in the reference canvas and are candidates for later.
- **No model step in the tool.** The model's role is composing the spec, in
  the `/concept-preview` skill; the deterministic emitter is the source of
  truth for the look.
- Downstream reuse is tracked separately: consistent previews in
  initial-design HITL gates (#473) and concept SVGs on the product site (#474).
