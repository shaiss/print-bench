# site/preview — media-rework preview SPA

A clickable, hash-routed preview of the **gallery + product-page media rework**
(from the "Product Page Media Rework" design export), built so the redesign can
be reviewed as a page before `site/lib/templates.mjs` is changed for real.

```bash
node site/preview/bake.mjs        # → site/preview/media-rework.html
python3 -m http.server 8000       # from the repo root, then open
# http://localhost:8000/site/preview/media-rework.html
```

`bake.mjs` reads the same committed sources the real site builds from
(`site/lib/content.mjs`, the design READMEs, `designs/<name>/previews/`) and
bakes them into one static page — it invents no content. `EMBED_DIR=<dir>`
inlines media as data URIs from a pre-downscaled mirror, for a fully
self-contained file; that mode writes `media-rework-embedded.html` instead.

What the preview changes, relative to the live site:

- **Gallery cards lead with the design's `product-hero` shot** (grayscale at
  rest, color + turntable GIF on hover) instead of the flat 4-view contact
  sheet; the card meta becomes proper wrapping tags, so the archived notice
  can no longer clip mid-word.
- **The product page's media wall becomes a stage + labeled thumbnail rail**:
  one large viewer, each entry labeled with its kind (studio render,
  turntable, AI-styled scene, contact sheet, detail), the AI disclosure shown
  as a caption on exactly the media it applies to instead of italic
  paragraphs interleaved through the README.
- The README's text sections render unchanged below the stage; the H1, the
  archived blockquote and the image embeds are lifted out as structured
  pieces (title, banner, media stage).

The baked pages are **not committed** (they're gitignored): they embed a full
copy of every README, so a committed copy would drift silently the moment a
design changes — the repo's regenerated artifacts stay under CI control, and
this one has no CI job, so it stays out of git instead. Bake it when you want
to look. Nothing in the real site build (`site/build.mjs`) or its tests reads
this directory.

**Status: the rework this previewed has landed** in the real site
(`site/lib/media.mjs`, `site/lib/templates.mjs`, `site/build.mjs`,
`site/assets/site.css`/`site.js` — same PR). This directory stays as the
design-review harness for future page-design rounds: bake, look, then port.
