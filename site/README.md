# site/ — the static product site

Turns what this repo already commits — product pages, previews, product
shots, style specs — into a browsable site, deployed on Vercel. It invents
no content: every word and image traces to a **provenanced source** — a
committed, CI-gated file, or a first-party record (a GitHub Release manifest,
this repo's own history) fetched at deploy time — never to the model. ("Static"
here means static *hosting*, not a flat page: see [Scopes](#scopes--build-deploy-served-output).)

```bash
./scripts/site.sh           # build into build/site
./scripts/site.sh --serve   # build, then serve at http://localhost:8000
```

Vercel runs the same generator (`vercel.json` at the repo root pins the
install and build commands), so a green local build means the deploy builds.

## What it publishes

| Page | Built from |
|---|---|
| `/` | every `designs/<name>/` with a `<name>.scad` and a `README.md` |
| `/designs/<name>/` | that design's `README.md`, rendered |
| `/styles/` | every `styles/<name>/` with a `STYLE.md` |
| `/styles/<name>/` | that style's `STYLE.md`, rendered |
| `/people/` | every `people/<handle>.md` — the product cores and the `shared: true` review specialists — as full member profiles with the product teams each has been on |
| `/how-it-works/` | a behind-the-scenes of the pipeline, presented from the committed architecture docs (`docs/architecture/*.md`); every mechanism links to the file that implements it |
| `/designs/<name>/` (team section) | for a design with a committed `team.conf`, the product page also carries a "team contributions" section: who built it (identity, linking to their `/people/` profile), a light reviewed-by reference, and the build-history timeline (its `PM.md` decision log and `NOTES.md` field tests, plus — on the Vercel deploy — its own git commits) |
| `/llms.txt` | the machine-readable index of every markdown source the site serves ([llms.txt](https://llmstxt.org/) convention), derived from the docs' own titles and summaries — never hand-maintained (`lib/llms.mjs`) |
| `/llms-full.txt` | the platform docs (contributing + architecture) concatenated into one fetch |
| `/docs/contributing/*.md`, `/docs/architecture/*.md` | the contributor and architecture docs, served **verbatim** as raw markdown (so their repo-relative links resolve in the repo, not necessarily on this host — see the scoped exception under "Two decisions worth knowing") |
| `/designs/<name>/README.md`, `/styles/<name>/STYLE.md` | the markdown source of each rendered page, served beside it |

Adding a design requires no edit here — the generator finds it by the same
entry-point rule `gate.sh` and `gallery.sh` use.

## Two decisions worth knowing

**The output tree mirrors the repo tree.** `designs/nuggs/README.md` becomes
`/designs/nuggs/`, and its images are copied to `/designs/nuggs/previews/`.
That is what lets a product page keep writing `previews/contact-sheet.png`
and have it resolve on the site with no rewriting at all. Only references
the site does *not* serve — a `.scad`, `NOTES.md`, a `.conf` — get rewritten,
to GitHub, where they really live.

**A broken local reference fails the build.** Every non-external link and
image is resolved against the filesystem; anything missing is collected and
reported, and the build exits non-zero. A link that would 404 in production
stops the deploy instead. One scoped exception: markdown served **verbatim**
(the `/docs/**.md` routes and the per-page `.md` sources below) is by
definition never rewritten, so its repo-relative links are checked against
the **repo tree** — they resolve in a checkout or on GitHub, and a link to a
file the site doesn't serve (`CLAUDE.md`, a script) 404s on the served host
by design. The no-404 rule governs rendered pages; verbatim sources trade it
for byte-fidelity with the repo.

**Lineage is ported, not re-derived — and the port is cross-checked.** Index
order and nesting come from the lineage record, so a derivative appears under
the design whose geometry it reuses and credits it, exactly as
`scripts/gallery.sh` does for the README gallery. The site cannot ask the real
resolver: `vercel.json` pins the deploy to `npm --prefix site ci` +
`node site/build.mjs`, and `./scripts/lineage.sh` needs Python. So `lib/`
carries a port — and `test/lineage.test.mjs` runs the port and `tools/lineage`
over the same fixture trees and fails on any disagreement about order or
parentage. Two surfaces of this repo silently disagreeing about what a design
*is* was [issue #55](https://github.com/shaiss/print-bench/issues/55); the
cross-check is what stops it recurring.

**The index is grouped, and the grouping is ported the same way.** The catalog
is split into a NUGGS ecosystem collection plus the technique domains from
`docs/advanced-techniques.md` — the same groups, in the same order, the README
gallery renders (issue #374). The authority is `scripts/catalog.sh`, driven by
the closed vocabulary in `designs/categories.conf` and each design's
`category:` key; `lib/catalog.mjs` re-implements that rule in JS (the deploy
can't run bash+Python), and `test/catalog.test.mjs` runs both over the same
trees — including the real repo — and fails on any disagreement about a
design's group or the order, the `lineage.mjs` cross-check pattern again.
Within a group, lineage order and derivative nesting are preserved.

## Scopes — build, deploy, served output

Several of this site's guarantees read like one blanket "the site is sealed"
rule, but they live at three different layers, and conflating them is what
makes the site look more locked-down than it is. Kept apart:

- **The build is deterministic and offline.** A plain `./scripts/site.sh`
  performs no network I/O and reproduces byte-for-byte, so a local build and
  the CI build always agree on the **committed baseline** of a deploy — the
  pages the deploy then augments with live data (below). This is a property of
  the *build*, not a ban on fetching.
- **The deploy may fetch live first-party data.** On Vercel the build is
  allowed to pull data it cannot commit — through a deploy-scoped, best-effort
  seam that renders *empty* on any failure and runs only behind a deploy-only
  flag, so it is purely additive and never breaks a build. `lib/releases.mjs`
  is the reference implementation (`SITE_FETCH_RELEASES=1`, the latest GitHub
  Release manifest → download links; nothing locally, no broken build when the
  API is down). `lib/history.mjs` is the second (`SITE_FETCH_HISTORY=1`): a
  design's own git commits over the GitHub API, folded into the team timeline as
  `commit · git` events, attributed to a member via their committed `github:`
  login. `lib/decisions.mjs` is the third (`SITE_FETCH_DECISIONS=1`): the open
  `needs-decision` queue over the GitHub search API, mapped by `notifications.mjs`
  into the header notification bell — empty locally, so the bell shows its
  "all caught up" state. Any further deploy-time source — PR / review history —
  follows the same shape.
- **The served output references nothing external.** Every asset the *browser*
  loads is vendored (three.js, the OpenSCAD-WASM runtime, the `text()` font),
  resolved by an inline import map, never a CDN. "No external references" is a
  rule about the bytes we serve, not about what the builder reads at deploy
  time — a GitHub API or a Release manifest is a *source*, not a served
  reference.

The principle spanning all three is **invent no content**, and its real test
is *provenance*, not "committed on disk": a committed, CI-gated file qualifies,
and so does a first-party authoritative record fetched at deploy time — a
Release manifest authored by the CI that published it, or this repo's own
GitHub history. Model-invented text is what the rule forbids. Likewise
**static** means static *hosting* — build-time output on a CDN, no per-request
server compute — while the page still runs real client-side compute in the
visitor's browser (the configurator and 3D viewer below).

The one-line pitch on each gallery card is the same one `scripts/gallery.sh`
puts in the README gallery — NOTES.md's `## Goal` paragraph, falling back to
the product page's intro. `site/lib/content.mjs` ports that rule deliberately;
if `gallery.sh` changes how it picks, change this with it, or the gallery in
`README.md` and the gallery on the site start describing designs differently.

## The configurator

Each product page carries an in-browser configurator: controls built from the
design's own Customizer parameters, a render button, and a download. OpenSCAD
is compiled to WebAssembly and runs on the **visitor's** machine, so nothing is
uploaded, nothing is installed, and the render costs us no compute.

`lib/scadparams.mjs` reads the parameter block straight out of the `.scad` at
build time — sections, descriptions, `[min:step:max]` and dropdown annotations
— so the controls cannot drift from the source. It is deliberately
conservative: a parameter is exposed only when its value is a literal that
round-trips through `-D name=value`. Computed values, `[Hidden]` sections,
`$fn`/`$fa`/`$fs`, and anything below where geometry starts are all skipped.

Four things here were established by running the binary, not by reading docs.
Change them at your peril:

1. **The flag is `--backend=manifold`.** The upstream openscad-wasm README
   still shows `--enable=manifold`, which is an obsolete spelling that does
   *not* error — OpenSCAD prints "Ignoring request to enable unknown feature"
   and silently runs the old CGAL backend, measured **145× slower**. The worker
   therefore also checks the geometry line says `(manifold)` and reports it if
   not.
2. **One module instance per render.** A second `callMain()` on the same
   instance throws *and* the previous run's output file is still readable — so
   reuse hands the visitor the previous model.
3. **`OPENSCADPATH` works — but only from `preRun`.** The runtime reads its
   environment at startup, so assigning `ENV` afterwards is too late, and
   OpenSCAD's parser only registers search paths that *exist* when `callMain`
   is called. Set it in `preRun`, create the directories first, and the repo's
   own `lib:root` search path works unchanged — which is why the browser
   mirrors the repo layout under `/repo` instead of flattening includes to
   basenames. Flattening would have worked today (nothing uses a nested
   include) and broken the first time a design wrote `include <BOSL2/std.scad>`
   or `include <styles/<name>/style.scad>`.
4. **`text()` needs a font.** Without a TTF on the virtual filesystem it emits
   a warning and contributes *no* geometry — calibration-cube's embossed size
   marker just vanishes while the render still reports success. DejaVu Sans
   ships for this reason (20 triangles without it, 1300 with).

The runtime is ~13 MB and is fetched only when a visitor opens a configurator
or the 3D viewer, never with the page.

**Licence.** OpenSCAD is GPL-2.0, so serving this build is distribution. The
build writes `/assets/openscad/README.txt` next to the binary naming the exact
pinned artifact, linking upstream source, and carrying a written offer for the
corresponding source; the font's licence ships beside it.

**The pin is worth revisiting.** The artifact is the npm package
`openscad-wasm`, pinned with its integrity hash in `package-lock.json` and
verified to be OpenSCAD 2025.07.18 with a working Manifold backend. The
*preferable* artifact is the build the official OpenSCAD playground ships
(`files.openscad.org`), which keeps `openscad.wasm` as a separate file and so
gets streaming compilation and independent caching, instead of base64-inlining
it into a 13 MB JS bundle. It was unreachable from the environment this was
built in, so it could not be verified or pinned here.

## The 3D viewer

Every product page also carries a **"View in 3D"** viewer
([issue #100](https://github.com/shaiss/print-bench/issues/100)): press it and
the design's own `<name>.scad` is rendered at its **default parameters** by the
same OpenSCAD-WASM worker the configurator uses — so the geometry on screen is
the geometry the gate exports — and drawn with [three.js](https://threejs.org/)
(WebGL): drag to rotate, scroll to zoom.

It is on *every* design, including those with no tunable parameters (which get
no configurator), because every design has geometry to inspect. The model
bundle it renders — entry, source, and the include closure — is built once by
`lib/model.mjs` and written to `/designs/<name>/model.json`; the configurator
reads the same bundle for its controls.

Three things make it consistent with the rest of the site:

- **No committed meshes, no new render pipeline.** The viewer reuses the WASM
  runtime already shipped; nothing renders STLs at build time (the deploy has no
  OpenSCAD), and no `.stl` is committed. It shows the real geometry by rendering
  the real source, client-side.
- **Nothing external.** three.js (the ~676 KB minified module build plus
  `STLLoader` and `OrbitControls`) is vendored under `/assets/three/`. The two
  addons import the bare specifier `three`, which each product page resolves
  with an inline import map — no CDN, same no-external-reference rule as the rest
  of the deploy.
- **Lazy and progressive.** The module script is deferred and imports nothing
  until the button is pressed; the 14 MB runtime loads only then. Without
  JavaScript the panel's `<noscript>` fallback points at the previews already on
  the page, and nothing else on the page depends on it.

## Release downloads

Every product page can show **per-part download links** — one per gated STL, with
its size and SHA-256, plus a "download all" zip — pulled from the design's latest
[GitHub Release](https://github.com/shaiss/print-bench/releases) manifest (the
build half of [issue #102](https://github.com/shaiss/print-bench/issues/102),
consumed here for [#139](https://github.com/shaiss/print-bench/issues/139)). Three
things keep it consistent with the rest of the site:

- **Best-effort, never a broken build.** The manifest is fetched at build time
  (`lib/releases.mjs`); a design with no release, or an unreachable/rate-limited
  API, simply renders no Downloads block. The no-404 rule still holds for
  *committed* references — release links are external and absent when the release
  is.
- **Vercel-scoped, so local and CI stay deterministic.** The fetch runs only on
  the deploy (which has network) or under `SITE_FETCH_RELEASES=1`; a plain
  `./scripts/site.sh` build performs no network I/O and shows no downloads, so its
  output is reproducible.
- **Provenance-true checksums.** The manifest is authored by the CI build that
  published the release, so the SHA-256 shown is of the exact bytes a visitor
  downloads — a local re-render never forges them.

## Layout

- `build.mjs` — the generator; discovery, render, asset copy, link check
- `avatars.mjs` — the member-avatar generator: regenerates each committed
  `assets/avatars/<handle>.svg` from the member's `people/<handle>.md` header
  (`npm --prefix site run avatars`); its `--set` mode (updating the
  `avatar-style:`/`avatar-seed:` keys, then regenerating) is what the
  *Regenerate avatar* Action runs
- `lib/avatars.mjs` — the avatar layer's single source of truth: the curated
  human/agent style sets, the header→config resolution and the DiceBear
  options; consumed by team.mjs (validation), avatars.mjs (generation),
  test/avatars.test.mjs (the drift gate: every committed SVG must equal what
  its member's header derives) and peoplePage (the studio's data block)
- `lib/content.mjs` — what exists: designs, styles, pitches, parts, previews
- `lib/lineage.mjs` — `derives.conf` → gallery order and parentage, ported from `tools/lineage`
- `lib/catalog.mjs` — `designs/categories.conf` + each design's `category:` → the index's catalog groups, ported from `scripts/catalog.sh` and cross-checked against it (issue #374)
- `lib/markdown.mjs` — markdown → HTML, link resolution and rewriting
- `lib/llms.mjs` — the AI-native serving layer: discovers the docs served
  verbatim (`docs/contributing/`, `docs/architecture/`), checks their local
  references against the repo tree (served raw means nothing rewrites them,
  so a broken link must fail the build here), and derives `/llms.txt` +
  `/llms-full.txt` from the served set — the index cannot drift from the tree
  because it is a function of it; `test/llms.test.mjs` pins the rules and
  censuses the real repo's doc set
- `lib/scadparams.mjs` — Customizer parameters and include closure from a `.scad`
- `lib/team.mjs` — the roster layer (issue #123): `people/<handle>.md` + `designs/<name>/team.conf` + the interim `people/work.conf` recent-work manifest (issue #124) → resolved member records, agent mandates read from their charters at build time; an unresolvable handle, mandate source, or cited work artifact fails the build
- `lib/profile.mjs` — the reusable member profile component (issue #124): identity, cited mandate, team chips, scope-filtered recent work; the People page renders it in the cross-team scope
- `lib/teams.mjs` — the team/org building blocks (issue #122, revised IA): the product page's "team contributions" section (`teamContributions` — light identity cards linking to People, a reviewed-by reference, the build-history timeline) and the shared `historySlot`; pure functions of the roster data
- `lib/timeline.mjs` — the "History of work together" timeline (issue #126): a source-adapter seam plus the sources it runs (the committed `PM.md` decision log and `NOTES.md` field-test log, and the deploy-time git history from `history.mjs`) → product-scoped, attributed, newest-first events, and the `timelineEvents` render the product page's contributions section hosts; a drifted decision-log shape fails the build
- `lib/history.mjs` — the deploy-time git-history source for the team timeline: a design's path-filtered commits over the GitHub API (best-effort and Vercel-scoped, like `releases.mjs`; merge commits dropped) → attributed `commit · git` events, the author mapped to a member by their committed `github:` login. The pure commit→event transform is unit-tested; the fetch boundary is stubbed, never the network
- `lib/model.mjs` — the per-design model bundle (entry, source, files, sections, asserts) the configurator and viewer share
- `lib/releases.mjs` — release download links (issue #139): the pure manifest → per-part download-link mapping, and the best-effort, Vercel-scoped fetch of the latest release's manifests (injectable `fetch`, empty on any failure)
- `lib/decisions.mjs` — the deploy-time source for the parked-decision queue (issue #181): the open `needs-decision` issues/PRs over the GitHub search API (best-effort and Vercel-scoped, like `releases.mjs`). The pure search-item → row transform is unit-tested; the fetch boundary is stubbed, never the network
- `lib/notifications.mjs` — the generic notification model the header bell renders from: a data source (today `decisions.mjs`) → a `{items, actions}` bundle, via `setNotifications` in `templates.mjs`. Pure and total on junk; the base every future notification source funnels through (`mergeBundles`) instead of growing another page panel
- `lib/templates.mjs` — the page shells
- `test/` — `npm --prefix site test`; run by `./scripts/site.sh` and CI
- `assets/` — `site.css` (the Modernist design system from the site-wireframes
  design export: Archivo, ink on a light ground, one red accent, zero radius,
  2px rules; dark is a derived variant so the toggle survives), `site.js`
  (theme toggle, the header notification bell's outside-click/Escape close, and
  the product page's tabs, which fall back to a stacked document without
  JavaScript), `configurator.js` (the panel), `viewer.js`
  (the 3D viewer) and `openscad-worker.js` (the renderer), plus two vendored
  asset dirs — `fonts/` (Archivo variable woff2, OFL 1.1) and `avatars/`
  (one DiceBear SVG per `people/` member, provenance in its README) — all
  copied to `/assets/` verbatim; the vendored `three/` build is copied there
  by `build.mjs`

## Avatars

Member avatars are [DiceBear](https://www.dicebear.com/) SVGs, committed
under `assets/avatars/` (provenance in that directory's README). Three
layers, deliberately separated:

- **Committed config is identity.** A member's `people/<handle>.md` header
  may carry `avatar-style:` (validated against the curated set for their
  kind — people-like styles for humans, machine-like for agents, so the
  visual distinction survives any choice) and `avatar-seed:`; absent keys
  fall back to notionists/bottts seeded by first name. `avatars.mjs`
  regenerates the SVGs from exactly this, DiceBear is deterministic under
  the pinned packages, and `test/avatars.test.mjs` fails on any committed
  SVG that no longer matches its header.
- **The avatar studio is a personal lens.** Every profile on `/people/`
  carries a re-roll glyph: it regenerates the avatar in the visitor's
  browser (vendored DiceBear under `/assets/dicebear/`, lazy-loaded like the
  OpenSCAD runtime) and persists in localStorage only — site-wide for that
  visitor, invisible to everyone else. The panel shows the header lines a
  member commits to make a combination official.
- **The `Regenerate avatar` Action** (`.github/workflows/avatar.yml`) is the
  easy commit path: dispatch it with a handle (and optionally a style/seed),
  and it updates the header, regenerates the SVG, proves the drift test, and
  opens a draft PR.

## Dependencies

All pinned in `package-lock.json`:

| Package | Why | Size |
|---|---|---|
| `marked` | markdown → HTML | ~470 KB, no transitive deps |
| `openscad-wasm` | the configurator's and viewer's renderer (GPL-2.0) | ~13 MB, lazy-loaded |
| `dejavu-fonts-ttf` | a font for `text()`, without which glyphs vanish | one 750 KB TTF is shipped |
| `three` | the 3D viewer's WebGL renderer (MIT) | ~676 KB minified module, vendored + lazy-loaded |
| `@dicebear/core` + 12 style packages | the avatar generator and studio (MIT; pinned exact for byte-determinism) | ~1.5 MB vendored, lazy-loaded |

Everything else is Node's standard library. There is no framework and no
bundler.
