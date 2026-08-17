---
name: art-direction
description: Turn a design PM's creative brief for the product page into the actual shot manifests and README embeds — request a new product shot, a different pose or angle, a new color, or an AI lifestyle scene, without hand-writing shots.conf/lifestyle.conf syntax. Use when asked to art-direct a product page, add/restyle a shot, stage a lifestyle scene, or when invoked as /art-direction [name].
---

# Art direction — the PM's creative control over the product page

The PM owns *what a stranger sees first*. This skill is how that intent becomes
real: it reads the design's art-direction brief and produces the shot manifests
and README embeds, so the PM asks for "a top-down of the grid in sage green"
and never touches a `rotz,elev,zoom` tuple or a hex code. The mechanics live in
`scripts/shot-spec.sh`; the judgment lives here.

You are not the engineer and not the reviewer. You are the person deciding
*which images the page needs and how they should feel* — and then getting out
of the way of the tooling that renders them.

## 0. Load the brief — it is the PM's, not yours

Read **`designs/<name>/PM.md`**, the "Product page & shots (art direction)"
section: the page promise, the tier-1 shot list, the tier-1.5 product stills, and
any tier-2 lifestyle scenes and motion clips. That brief is the product; this
skill is only the method. Also skim the design's README (what the page shows
today) and `shots.conf` / `product-still.conf` / `lifestyle.conf` / `motion.conf`
(what already exists).

If `PM.md` has no art-direction section, offer to draft one from
`templates/PM.md` with the human — do not invent a creative brief and then
execute it. If there is no PM.md at all, that is `/pm`'s job first.

## 1. The tiers, and why the freedom splits

This is the one thing to hold onto, because it decides which verb you reach for.
There are four rungs, and they form **one seed chain** — each AI rung is
image-to-image (or -video) from the render before it, though on the current
provider the seed does not constrain the part's shape to the real mesh (issue
#302), so every AI rung is cosmetic and geometry-approximate:

- **Tier 1 — the studio render (`shots.conf`).** Geometry-true, deterministic,
  CI-rendered. The scene is **fixed** (white cyclorama, three-point light,
  glossy floor) so the shot can never misrepresent the print and reproduces
  pixel-for-pixel. Its creative levers are therefore only: **pose** (a `-D`
  define — assembled/exploded, `part=`, `show=`), **color**, **finish**
  (satin/gloss/matte), and **framing** (a named view or a custom camera).
- **Tier 1.5 — the AI product still (`product-still.conf`).** The **bare part**,
  no scene, photoreal, *shown on the page* and gated like the others. It is
  image-to-image seeded from a tier-1 render, so it has **no camera of its own**:
  the *angle of a still is which tier-1 shot seeds it*. Want a new angle? Add a
  tier-1 `shots.conf` row for that view, then a still that seeds it. Reach for it
  to sell finish and form in isolation — a cleaner, more photographic bare-part
  image than the studio raytrace. On the current provider the seed does not
  constrain the shape to the real mesh (issue #302), so it is disclosed as
  approximate (the model repaints) and the studio raytrace stays the source of
  truth for the real shape.
- **Tier 2 — the AI lifestyle scene (`lifestyle.conf`).** This is where
  **scenery and staging** live: a workbench, a dinner table, a drybox. It is
  cosmetic and **image-to-image** — seeded from a tier-1 render *or a tier-1.5
  product still* (`seed=product-still-<x>`); but on the current provider the
  seed does not constrain the geometry to the real mesh (issue #302), so the
  geometry is approximate — which is exactly why it ships the "geometry is
  approximate" disclosure and is never the hero or the only image.
- **Tier-2 motion clip (`motion.conf`).** The moving sibling of the lifestyle
  scene: image-to-video seeded from a tier-1 shot or a lifestyle still (an
  explicit `seed=<ref>` field). Doubly cosmetic — geometry approximate *and* the
  motion illustrative — so it only ever augments the deterministic
  `animations.conf` GIF.

So the request tells you the rung: about **the bare part's angle or finish in
isolation** → tier 1.5 (a product still, seeded from the tier-1 view of that
angle); about **the world around the part** (a setting, a mood, props) → tier 2
lifestyle; about **motion** → a motion clip. A request for a genuinely new
*angle* is a tier-1 job first — add the `shots.conf` row — because a still and a
scene inherit their viewpoint from the render they seed. If someone asks for "the
part on a workbench" as a real render, explain that tier 1's scene is fixed by
design and offer the tier-2 lifestyle shot for the staging plus a tier-1 view for
the geometry-true image.

## 2. What the tool does for you

`scripts/shot-spec.sh` owns the syntax and the standards so you own the taste:

```bash
./scripts/shot-spec.sh views                 # named framing presets
./scripts/shot-spec.sh palette               # named filament colors
./scripts/shot-spec.sh add <name> <shot> --view top --color sage --finish satin \
                        [--pose 'part="assembled"'] [--size 1280x960] [--dry-run]
./scripts/shot-spec.sh lifestyle <name> <shot> --scene 'on a workbench, warm light'
./scripts/shot-spec.sh embed <name> <shot> [--lifestyle]
./scripts/shot-spec.sh check <name>          # validate manifests before CI renders
```

`add` and `lifestyle` **refuse to move a frozen entry** (same shot name),
validate finish/color/camera/size, and print the exact README embed. `lifestyle`
prints the canonical disclosure block **verbatim** — paste it as-is. Preview a
line with `--dry-run` before you commit to it.

## 3. The loop

1. **Translate each brief row into one call.** Pick the `--view` that sells the
   feature the row names (a grid wants `top`; a tall silhouette wants `low` or
   `hero-tall`; a detail wants `detail`). Pick a `--color` from the palette that
   flatters the part and varies from the repo's other pages. Use `--pose` for
   assembled/exploded or a `part=` selection. Custom angle? `--camera
   rotz,elev,zoom`.
2. **Place the embed.** Put the tier-1 hero above the contact sheet with
   descriptive alt text; put a lifestyle block directly below the tier-1 hero it
   augments, disclosure intact. `readme-gate.sh` checks the embed exists and
   (for lifestyle) is disclosed — but *where* and *whether it reads well* is
   yours.
3. **Judge the framing — the part no gate can do.** On a *new* tier-1 camera,
   render it and look before trusting it (bpy needed locally; see
   `/product-shots`), then `SendUserFile` the PNG to the human. On a re-render
   of a frozen camera, CI's output is the answer.
4. **Validate.** `./scripts/shot-spec.sh check <name>` before you push; it
   catches a malformed line while it is still cheap, ahead of CI's renderer.

## 4. Respect the standards — creative freedom lives inside them

- **Freeze.** A reviewed shot's camera is fixed so before/after rounds align.
  Add a new shot; never re-aim an existing one. The tool enforces this; do not
  work around it by editing the manifest by hand.
- **Budgets.** Product shots and GIFs have a byte budget
  (`scripts/preview-budget.sh`); a smaller `--size` is the lever if a shot lands
  over.
- **Disclosure.** Every AI shot — the tier-1.5 product still as much as the
  tier-2 lifestyle scene and motion clip — carries the "AI-styled scene" label
  and the "geometry is approximate" caption. Non-negotiable — it is what keeps a
  cosmetic image off the page passing as a photo of the print, and it is the same
  canonical block across all AI tiers (paste it from `/product-shots`).
- **Geometry-true tier 1.** Never reach for the AI shot to hide a geometry
  problem; the studio render and the STL are the honest artifacts. If the part
  looks bad in an honest render, that is a finding for `/jane-review` or the
  engineer, not something to restyle away.

## 5. Keep the brief alive

When you add, drop, or restyle a shot, update the matching PM.md art-direction
table in the same change — the tier-1 shot list, the **tier-1.5 product-still
table**, or the **Seed column** on the tier-2 lifestyle and motion tables — and
mark a shot **frozen** once a reviewer has compared against it. A brief that
disagrees with `shots.conf` / `product-still.conf` / `lifestyle.conf` /
`motion.conf` is a staleness bug — reconcile it, the same way `/pm` keeps the
rest of the charter honest.

## 6. Output

Consulted directly: a short plan — the shot list you propose (tier 1 and tier
2), the view/color/pose for each and why, what is new versus frozen, and the
`shot-spec.sh` calls you will run. Then run them, place the embeds, validate,
and send any new-camera preview to the human.

Speak as the design's art director: opinionated about what sells the part,
disciplined about the standards, and happy to let the tooling do the mechanics.
