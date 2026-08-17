# <Design name> — product charter

<!-- The charter the /pm skill enforces. Copy to designs/<name>/PM.md and
     fill in. This is what the design IS and who it is FOR; NOTES.md is the
     engineering log of what happened, and README.md is the product page a
     stranger reads. Keep this one short enough that a PM can hold it in
     mind — if it grows past a page it has stopped being a charter.
     Delete these comments. -->

## The product, in one paragraph

What it is, who it is for, and the one thing it must do well. If you
cannot name the customer, the design does not have a charter yet.

## Non-negotiables

Constraints that may **not** be weakened to make engineering easier. Each
needs a number and a source, and ideally an `assert` in the .scad so the
render fails rather than the reviewer catching it. State what would have
to be true to reopen each one.

| # | Constraint | Number | Source | Reopens if |
|---|---|---|---|---|
| N1 | | | | |

## Out of scope

**Deferred** — good ideas, not now, ranked in the backlog below.

**Never** — things this design will not do, with the reason. This list is
the PM's most useful asset; without it every session re-litigates the same
suggestions.

## v1 — definition of done

What must be true to call the first version finished. Checkable by someone
other than the author, and separate from "the gate is green" (which is
necessary, not sufficient).

- [ ] 

## Product page & shots (art direction)

How the product page should sell this design — the PM's creative brief, in
plain language. The `/art-direction` skill turns this into the shot manifests
(`shots.conf` and its AI siblings `product-still.conf`, `lifestyle.conf`,
`motion.conf`) and README embeds via `scripts/shot-spec.sh`, so write *intent*
here, not manifest syntax. The tables are separate because the page has a
**tiered image pipeline** and each tier's freedom differs — but they form one
**seed chain**, each AI hop image-to-image (or -video) from the render before it,
though on the current provider the seed does not constrain the part's shape to
the real mesh (issue #302), so every AI hop is cosmetic and geometry-approximate:
**tier 1** the geometry-true studio render (`shots.conf`), its levers
pose, color, finish and framing; **tier 1.5** an AI *product still* of the bare
part (`product-still.conf`), photoreal and in isolation, seeded from a tier-1
render; **tier 2** the AI *lifestyle scene* (`lifestyle.conf`) that stages a
world around the part, seeded from a tier-1 or tier-1.5 render; and the **tier-2
motion clip** (`motion.conf`), seeded from a tier-1 shot or a lifestyle still.
Every AI tier is disclosed as
approximate (the model repaints even a seeded shape) and ships the "geometry is
approximate" caption. Run `./scripts/shot-spec.sh views` and `… palette` for the
named framing and color vocabularies (or give a hex / a raw `rotz,elev,zoom`).

**Page promise.** The one thing a stranger must take away from the page.

**Shot list — tier 1 (real studio renders).** Ranked; the first is the hero.
Shots are frozen once reviewed — add a row, never repurpose one.

| Shot | What it sells | View | Look (color / finish) | Pose (`-D`, if any) |
|---|---|---|---|---|
| product-hero | | hero | | |

**AI product stills — tier 1.5 (AI, bare product, disclosed).** Optional. The
bare part, no scene, photoreal, and *shown on the page* — one row per angle,
where the angle **is** which tier-1 shot seeds it (an image-to-image still has no
camera of its own). A new angle means adding a tier-1 row above, then a still
that seeds it. Every still ships the "geometry is approximate" disclosure.

| Still | Seeds from (tier-1 shot) | Prompt/notes |
|---|---|---|

**Lifestyle scenes — tier 2 (AI, cosmetic, disclosed).** Optional. Describe the
*setting*, not fake detail; the scene is AI, seeded image-to-image from a real
render, but on the current provider the seed does not constrain the shape to the
real mesh (issue #302) — name the tier-1 or tier-1.5 render each scene seeds
from.

| Shot | Seed | Scene |
|---|---|---|

**Motion clips — tier 2 (AI, cosmetic, disclosed).** Optional; only motion the
print really performs. Seeded image-to-video from a tier-1 shot or a lifestyle
still — geometry approximate, and the motion itself illustrative.

| Shot | Seed | Scene/Motion |
|---|---|---|

## Backlog, ranked by user value

Ranked by what a real user hits most often, not by what is interesting to
build. Include the cost where the repo can tell you (print time, filament,
part count).

| # | Item | Why this rank | Cost |
|---|---|---|---|
| B1 | | | |

## Open decisions

Questions only the human can answer. Mark which ones **block** work versus
which can proceed on a stated assumption.

| Question | Blocking? | Assumption if unanswered |
|---|---|---|

## Decision log

Append-only. Date, decision, reason. A later session must be able to tell
a considered choice from an accident.

| Date | Decision | Reason |
|---|---|---|
