---
name: product-shots
description: Give a design's product page real-world-looking product shots — path-traced studio renders of the printed part (deterministic, CI-gated), plus optional AI-restyled lifestyle shots and motion clips via the CI-wired manifests. Use when asked for product shots, hero images, photoreal/real-world renders, motion or video previews, or when invoked as /product-shots [name].
---

# Product shots — real-world-looking images for the product page

A product page sells the print. The 4-view contact sheet proves geometry;
the **product shot** is what makes a stranger want the thing: the part as
it would look printed, sitting under studio light. Every design's README
should lead with one.

Two tiers, in order:

**CI renders and commits both tiers.** What you own is the *manifest* and
the *embed*: `shots.conf` says which shot exists and how it is framed,
README.md places it. The `regen` job in `.github/workflows/ci.yml` runs
`product-shot.sh` for every design a PR touches and pushes the PNGs to the
branch; the lifestyle workflows fire on a `lifestyle.conf` (still) or
`motion.conf` (clip) landing on main.
So you can write a manifest and push without `bpy` installed at all. Render
locally when you want to *judge* framing before pushing — that is a real
reason, and §"Judge the framing" below is about exactly that.

Two tiers, in order:

1. **Studio render (always — this is the geometry-true deliverable).**
   `./scripts/product-shot.sh <name>` exports the geometry-true STL with
   OpenSCAD and path-traces it with Blender's Cycles: seamless backdrop,
   soft key/fill/rim lighting, glossy floor with contact shadows, plastic
   material with FDM layer lines. Re-rendering an unchanged design
   reproduces the committed PNG pixel for pixel **on the same machine**, so
   shots diff cleanly across review rounds: hold the manifest, the scene
   code and the toolchain still, and a shot that moves means the geometry
   moved. Expect roughly a minute per shot. One caveat before trusting a
   byte-level comparison across machines: Cycles dispatches an SSE4.2 or
   AVX2 CPU kernel by what the host supports, and their rounding differs,
   so compare renders from different hardware perceptually, not byte-wise.
2. **AI-restyled lifestyle shot (optional — only when the session has an
   image-generation tool), and optionally an AI motion clip via CI.**
   Restyle the committed raytrace into a real-world scene — or animate it
   with the motion-clip pipeline (see the subsection at the end of Tier 2).
   This tier is **purely supplemental and cosmetic** — a general real-world
   impression for the reader, not a geometry-true render: assume it may be
   geometrically off. Never a substitute for tier 1, never the only image on
   the page, and it always ships with a visible warning note directly below
   it (see below).

## Tier 1 workflow

1. **Write the manifest** `designs/<name>/shots.conf` (format documented in
   `scripts/product-shot.sh`), one line per shot:

   ```text
   product-hero | e8734a | satin | 35,18,0.85 | 1280x960 | part="assembled"
   ```

   - Name the lead shot `product-hero`. Colors are `rrggbb` **without**
     `#` (a `#` starts a manifest comment). Pick a plausible filament
     color that flatters the part; vary colors across a repo so pages
     don't all look alike.
   - Camera is `rotz,elev,zoom`: three-quarter views (rotz 25–45,
     elev 12–25) read as product photography; flat wide parts want more
     elevation. Start at `35,18,0.85` and iterate.
   - `zoom` scales an automatic fit, so it means the same thing on every
     design regardless of size: 1.0 frames the part's bounding box with a
     small margin, below 1.0 pulls back for more room, above 1.0 crops in.
     The fit solves both the horizontal and vertical field of view, so a
     tall part cannot silently lose its top edge — you do not have to
     hand-check framing per design, only judge it.
   - Like `animations.conf`, entries are FIXED across review rounds so
     before/after images align — add a new entry rather than moving one.

2. **Embed it** near the top of the README (above the contact sheet), with
   descriptive alt text naming the material/color:

   ```markdown
   ![Product shot: the assembled board in charcoal PLA](previews/product-hero.png)
   ```

   Write the embed even when the PNG does not exist yet — CI renders it and
   commits it to the branch, and `readme-gate.sh` is what proves manifest,
   file and embed all line up (within the size budget in
   `scripts/preview-budget.sh`). A local readme-gate failure on a
   not-yet-rendered shot is expected, not a problem to solve.

3. **Judge the framing** — the one part CI cannot do for you. A machine can
   confirm a PNG exists and is under budget; it cannot tell you the part is
   crushed against the frame edge or that you're selling its dull face. So
   render locally when framing is in question:

   ```bash
   # once; bpy is not installed by default. --force too: without it the hook
   # no-ops outside Claude Code on the web, so --with-bpy alone does nothing.
   .claude/hooks/session-start.sh --force --with-bpy
   ./scripts/product-shot.sh <name>
   ```

   Then actually view `designs/<name>/previews/<shot>.png` (Read it) and
   send it to the user with SendUserFile like any other preview. Iterate on
   the manifest's camera line, not on the committed file.

   If you skip this, the shot still lands — CI renders whatever the
   manifest says. Skipping it means nobody looked. On a new `shots.conf`
   entry, look; on a re-render of a frozen camera after a geometry change,
   the camera is by definition unchanged and CI's output is the answer.

Multi-part scenes: `tools/photoshot/photoshot.py` accepts multiple STLs
with per-mesh `--color` for two-tone assemblies; the manifest drives one
geometry per shot, so compose multi-STL shots manually and name the output
to match a manifest entry only if it is reproducible from source noted in
NOTES.md.

## Tier 2: AI-restyled lifestyle shot

Two ways to generate one, both landing the same disclosed
`previews/lifestyle-<shot>.png`:

- **In CI (the wired path).** Write `designs/<name>/lifestyle.conf` (one
  `<shot> | <prompt>` line, or `<shot> | seed=<ref> | <prompt>` — describe the
  *scene*, not fake detail) and land it on main. That is the whole trigger: the
  **Lifestyle shot (tier-2, AI)** workflow (`.github/workflows/lifestyle-shot.yml`,
  `scripts/lifestyle-shot.sh`) fires on the manifest itself, so writing the
  prompt *is* the request — no button to press. It calls the Z.AI GLM-Image
  API with the `ZAI_KEY` secret in **image-to-image** mode, **seeded from a
  committed geometry-true render** (`seed=<ref>` → `previews/<ref>.png`,
  defaulting to the shot's own name), sizes the result to budget, embeds it
  with the disclosure below, runs `readme-gate.sh`, and opens a **draft PR** to
  approve. The seed pins the part's shape to the real mesh, so the scene,
  lighting and materials are AI but the geometry is not hallucinated the way
  blind text-to-image did. It stays disclosed as approximate — the model still
  repaints — but it is a faithful restyle, not an invention. Dispatch the
  workflow by hand only to re-roll a shot you don't like, or to override the
  size.
- **In-session**, only when the session actually has an image-generation tool
  (check your available tools; do not shell out to external image APIs that
  aren't configured). If none is available, skip this tier silently — tier 1
  is the deliverable — and leave the idea in NOTES.md for a session that has
  one.

- **Prompt for the scene.** Describe the same object in a real setting
  relevant to the design's use (the battleship board on a dinner table set
  with sushi; the desiccant capsule beside a filament dry-box), natural
  lighting, shallow depth of field. The CI path is now **image-to-image seeded
  from the committed tier-1 raytrace** (issue #66, previously a tabled backlog
  item), so the part begins from the real mesh — you are restyling a true shape
  into a scene, not summoning geometry from words. The seed defaults to the
  shot's own name (`previews/<shot>.png`); add `seed=<ref>` to start from a
  different geometry-true render — a hero shot, a frozen `cameras.conf` view, or
  a custom-angle tier-1 render you add — so you can choose the angle that sells
  the scene. It is still disclosed as approximate (the model repaints), but the
  fidelity is far higher than the old text-to-image path.
- **It is cosmetic, so assume it is geometrically off.** Image generators
  add, drop, and reshape features, and we do **not** reject a lifestyle shot
  for that — chasing pixel-faithful geometry out of a restyle is a losing
  game, and the studio render (tier 1) and the STL are already the
  geometry-true artifacts on the page. What keeps the lifestyle shot honest
  is the *disclosure*, not a fidelity check. `readme-gate.sh` enforces the
  disclosure in a fixed, **canonical** form (it checks structure, not prose —
  the reviewers judge whether the words are honest), so follow it exactly:
  - Commit as `previews/lifestyle-<shot>.png`, where `<shot>` is the exact
    tier-1 manifest name it restyles (so `product-hero` becomes
    `lifestyle-product-hero.png`).
  - Embed it **only as an inline markdown image** — `![alt](path)` — never an
    HTML `<img>` tag or a reference-style link, and if the file appears more
    than once, *every* embed must be disclosed. (The gate refuses any other
    form so an undisclosed hero can't hide beside a disclosed decoy.)
  - The alt text must carry the label `AI-styled scene`.
  - Directly below the image, a **visible caption** that a reader of the
    rendered page sees (alt text is invisible there). It must contain the
    canonical phrase **`geometry is approximate`** verbatim — the gate keys on
    that fixed phrase, so a paraphrase won't pass; write the full sentence:

    ```markdown
    ![AI-styled scene: the board on a set dinner table](previews/lifestyle-product-hero.png)

    *AI-generated impression for general illustration only — geometry is
    approximate and may not exactly match the printed part; see the studio
    render above and the STL for the true shape.*
    ```
- The tier-1 shot stays on the page as the geometry-true reference; the
  lifestyle shot only augments it — never the hero or the only image —
  giving the reader a general real-world feel for the piece.

### Motion clips (tier-2 video)

The motion sibling of the lifestyle shot, and CI-wired the same way: write
`designs/<name>/motion.conf` (one `<shot> | <prompt>` line) and land it on
main — the **Lifestyle clip (tier-2, AI motion)** workflow
(`.github/workflows/lifestyle-clip.yml`, `scripts/lifestyle-clip.sh`) fires
on the manifest, animates the design's committed tier-1 shot with the Z.AI
Vidu 2 image-to-video API, transcodes the result to a GIF within the
animation budget, embeds it with the disclosure, runs `readme-gate.sh`, and
opens a draft PR to approve.

- **Name `<shot>` after the exact `animations.conf` or `shots.conf` entry it
  restyles** (so `turntable` becomes `previews/lifestyle-turntable.gif`) —
  the clip must sit beside its deterministic counterpart, never replace it.
- The disclosure rules above apply verbatim (inline embed only, `AI-styled
  scene` label, `geometry is approximate` caption) — the gate treats a
  `lifestyle-*.gif` exactly like a `lifestyle-*.png`, judged against the
  animation-GIF budget. Write the caption's motion clause too: the movement
  shown is illustrative, not a simulation.
- **A clip is doubly cosmetic**: the geometry is an impression *and the
  motion is invented by the model* — it can show a mechanism the print
  cannot perform. The `animations.conf` GIF is the motion-true artifact; a
  clip may only ever augment it, below it on the page.

Product shots follow the same freeze policy as `previews/CAMERAS.md`
cameras, `animations.conf` and `motion.conf`: once reviewers have compared
against a shot, don't silently re-frame it. The freeze lives in the manifest line, so
CI regenerating a shot never breaks it — same camera in, same framing out.

Keeping a shot current after a geometry change used to be a manual step in
the design's definition of done, and it failed exactly the way manual steps
do (issue #69: three previews with no generator went stale through a thread
redesign, and every check stayed green). It is CI's now: `regen` re-renders
the shots of every design in a change's blast radius and commits them, so a
committed PNG cannot depict older geometry than the `.scad` beside it. What
remains yours is the manifest — and the judgement about framing that no
gate can make.

Because renders are reproducible, staleness is *checkable* even though the
gate doesn't check it: re-run the shot on an unchanged design and the PNG
should come back byte-identical (`git status` stays clean). A shot that
moves without a geometry change means something else drifted — the
manifest, the scene code, or the Blender version — and is worth
understanding before committing. Across two different machines, expect a
near-identical but not byte-identical image; that is the CPU-kernel caveat
above, not drift.
