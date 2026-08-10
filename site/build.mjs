#!/usr/bin/env node
// Build the static product site.
//
//   node site/build.mjs [--out <dir>]     (default: build/site)
//
// Everything it publishes already exists in the repo and is already gated by
// CI — product pages, previews, product shots, style specs. This turns that
// into a browsable site; it invents no content of its own.
//
// The output tree mirrors the repo tree (designs/<name>/ → /designs/<name>/),
// which is what lets a product page keep its `previews/foo.png` links with no
// rewriting. Any local reference that does not resolve on disk fails the
// build — a broken link should stop a deploy, not become a 404 in production.

import {
  mkdirSync,
  writeFileSync,
  copyFileSync,
  rmSync,
  readdirSync,
  readFileSync,
  statSync,
  existsSync,
} from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

import { ALL_AVATAR_STYLES } from "./lib/avatars.mjs";
import { readDesigns, readStyles } from "./lib/content.mjs";
import { readTeam } from "./lib/team.mjs";
import {
  shouldFetchReleases,
  fetchLatestReleaseManifests,
  manifestToDownloads,
} from "./lib/releases.mjs";
import { readTimeline } from "./lib/timeline.mjs";
import {
  shouldFetchHistory,
  fetchDesignCommits,
  commitsToEvents,
  loginHandleMap,
} from "./lib/history.mjs";
import { renderMarkdown, tocHtml } from "./lib/markdown.mjs";
import { stripReadmeMedia, designMedia, missingMediaRefs } from "./lib/media.mjs";
import { buildModel } from "./lib/model.mjs";
import {
  indexPage,
  designPage,
  stylesIndexPage,
  stylePage,
  peoplePage,
  howItWorksPage,
  redirectPage,
  FAVICON,
} from "./lib/templates.mjs";

const SITE_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(SITE_DIR, "..");
const OWNER = "shaiss";
const REPO = "print-bench";
const GITHUB_BASE = `https://github.com/${OWNER}/${REPO}/blob/main`;

function parseArgs(argv) {
  let out = join(REPO_ROOT, "build", "site");
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--out") {
      const v = argv[++i];
      if (!v) fail("--out needs a directory");
      out = resolve(process.cwd(), v);
    } else {
      fail(`unknown argument: ${argv[i]}`);
    }
  }
  return { out };
}

function fail(msg) {
  console.error(`error: ${msg}`);
  process.exit(2);
}

function write(outDir, relPath, contents) {
  const dest = join(outDir, relPath);
  mkdirSync(dirname(dest), { recursive: true });
  writeFileSync(dest, contents);
}

function copyTree(from, to, keep = null) {
  for (const entry of readdirSync(from, { withFileTypes: true })) {
    const src = join(from, entry.name);
    const dest = join(to, entry.name);
    if (entry.isDirectory()) {
      mkdirSync(dest, { recursive: true });
      copyTree(src, dest, keep);
    } else if (entry.isFile() && (!keep || keep(entry.name))) {
      mkdirSync(dirname(dest), { recursive: true });
      copyFileSync(src, dest);
    }
  }
}

// The runtime OpenSCAD build served to visitors, and the font it needs.
// Both come from pinned npm packages (see site/package.json and the lockfile)
// rather than a floating download, so what ships is reproducible.
const RUNTIME_PKG = "openscad-wasm";
const RUNTIME_FILE = join(SITE_DIR, "node_modules", RUNTIME_PKG, "openscad.js");
const FONT_FILE = join(SITE_DIR, "node_modules", "dejavu-fonts-ttf", "ttf", "DejaVuSans.ttf");
const FONT_LICENSE = join(SITE_DIR, "node_modules", "dejavu-fonts-ttf", "LICENSE");

// The 3D viewer's WebGL library (issue #100), vendored the same way as the
// OpenSCAD runtime and font: pinned npm packages copied into the build, so what
// ships is reproducible and the deploy needs no external reference. The two
// addons import from the bare specifier `three`, which the product page resolves
// with an import map pointing at the module build below.
const THREE_PKG = "three";
const THREE_DIR = join(SITE_DIR, "node_modules", THREE_PKG);
const THREE_FILES = [
  ["build/three.module.min.js", "three.module.min.js"],
  ["examples/jsm/loaders/STLLoader.js", "STLLoader.js"],
  ["examples/jsm/controls/OrbitControls.js", "OrbitControls.js"],
  ["LICENSE", "LICENSE.txt"],
];

// The avatar studio's DiceBear build (MIT), vendored the same way: the core
// engine plus every curated style, served from /assets/dicebear/ and only
// fetched when a visitor presses a re-roll glyph. The packages are plain ESM
// with relative imports and no runtime dependencies, so a filtered copy of
// each lib/ tree is the whole "bundle" — no bundler, same as everything else.
const DICEBEAR_PKGS = ["core", ...ALL_AVATAR_STYLES];

/**
 * GPL-2.0 requires that whoever receives the binary can get its source and
 * knows their rights. This ships next to the artifact and names the exact
 * version served, so the offer points at something specific.
 */
function runtimeNotice() {
  const pkg = JSON.parse(
    readFileSync(join(SITE_DIR, "node_modules", RUNTIME_PKG, "package.json"), "utf8")
  );
  return `OpenSCAD compiled to WebAssembly — licence and source
=========================================================

openscad.js in this directory is a build of OpenSCAD, which is free software
licensed under the GNU General Public License, version 2 or later.

  Artifact : npm "${RUNTIME_PKG}" version ${pkg.version}
  Licence  : ${pkg.license || "GPL-2.0"}
  Registry : https://registry.npmjs.org/${RUNTIME_PKG}/-/${RUNTIME_PKG}-${pkg.version}.tgz

The exact bytes served here are the ones npm resolves for that version; the
integrity hash that pins them is recorded in site/package-lock.json in the
source repository of this site.

CORRESPONDING SOURCE
--------------------
OpenSCAD's complete source is published by the OpenSCAD project at
https://github.com/openscad/openscad, and the WebAssembly build definition at
https://github.com/openscad/openscad-wasm. Both are GPL-2.0.

You may also request the corresponding source for the exact build served here
by opening an issue at https://github.com/shaiss/print-bench/issues — this is a
written offer, valid for as long as this site serves the binary.

You may redistribute and/or modify OpenSCAD under the terms of the GNU General
Public License as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version. It is distributed in the
hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License at https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
for more details.

FONT
----
design.ttf is DejaVu Sans, shipped because OpenSCAD's text() renders nothing
without a font on its virtual filesystem. Its licence is LICENSE-dejavu.txt in
this directory.
`;
}

async function main() {
  const { out } = parseArgs(process.argv.slice(2));

  const designs = readDesigns(REPO_ROOT);
  const styles = readStyles(REPO_ROOT);

  if (designs.length === 0) fail("no designs found under designs/");

  // Release download links (issue #139). Best-effort and Vercel-scoped: on the
  // deploy (which has network) each design's latest-release manifest becomes
  // per-part download links; locally and in CI the fetch is off, so the build
  // stays deterministic and simply shows no downloads. Any failure here leaves
  // the map empty — a missing release is never a broken build.
  let releaseManifests = new Map();
  if (shouldFetchReleases()) {
    try {
      releaseManifests = await fetchLatestReleaseManifests({
        owner: OWNER,
        repo: REPO,
        token: process.env.GITHUB_TOKEN,
      });
      console.log(
        `      releases: ${releaseManifests.size} manifest(s) fetched for download links`
      );
    } catch (err) {
      console.warn(
        `      releases: fetch skipped (${err.message}) — product pages show no downloads`
      );
    }
  }

  // Documents the site itself publishes, so links between them stay internal
  // instead of bouncing the reader out to GitHub.
  const pages = new Map();
  for (const d of designs) pages.set(d.readmePath, `/${d.relDir}/`);
  for (const s of styles) pages.set(s.specPath, `/${s.relDir}/`);
  const pageFor = (absPath) => pages.get(absPath) || null;

  const assets = new Set();
  const errors = [];
  const onAsset = (p) => assets.add(p);
  const onError = (m) => errors.push(m);

  // Lineage credits are emitted as raw markup by the templates, so unlike
  // every link inside a product page they never pass through the markdown
  // reference checker. Check them here, or a derivative would ship a dead
  // internal link with the build still green — the same class of silent
  // divergence issue #55 was filed for.
  const designNames = new Set(designs.map((d) => d.name));
  for (const design of designs) {
    if (design.lineageCycle) {
      onError(
        `designs/${design.name}/derives.conf: sits on a lineage cycle, so it has no place in the tree — run ./scripts/lineage.sh check`
      );
    }
    for (const parent of design.parents) {
      if (!designNames.has(parent)) {
        onError(
          `designs/${design.name}/derives.conf: names parent '${parent}', which the site does not publish`
        );
      }
    }
  }

  // Team data is structured the same way (#123): rosters and mandate
  // pointers never pass through the markdown checker, so resolve them here
  // — an unresolvable handle or mandate source must stop the deploy, not
  // render a hole in a future team page.
  const team = readTeam(REPO_ROOT, { onError, designNames });

  rmSync(out, { recursive: true, force: true });
  mkdirSync(out, { recursive: true });

  const rendered = [];

  // The "History of work together" timeline (issue #126): assemble each
  // rostered team's shared record from its own committed files (PM.md decision
  // log, optional NOTES.md field-test log) here, where the filesystem is
  // reachable. Each design's events feed its own product-page contributions
  // section (designPage, below) — the team is seen from the product now (the
  // #122 IA, revised). Problems go to the same accumulator as every other
  // structured source, so a drifted decision-log table fails ./scripts/site.sh
  // rather than rendering a hole. Product-scoped by construction: each team
  // reads only its own design's files.
  // Attribution map for git history: a member's committed `github:` login →
  // handle, keyed by canonical lowercase login. Built from committed data only,
  // so a git commit is attributed to a member only where this mapping derives
  // it — an author with no committed login renders unattributed (honest, not
  // guessed). Two members claiming one login is a data error that fails the
  // build, not a silent overwrite.
  const { map: loginToHandle, problems: loginProblems } = loginHandleMap(team.members);
  for (const p of loginProblems) onError(`people: ${p}`);

  // Git history is the first deploy-time source folded into the timeline (the
  // #126 seam, now fed): each rostered design's own path-filtered commits over
  // the GitHub API. Best-effort and Vercel-scoped (shouldFetchHistory) exactly
  // like release download links — locally and in CI no fetch runs, so the
  // timeline stays committed-only and the build is byte-for-byte reproducible;
  // on the deploy real commits appear, labelled `commit · git`.
  const commitsByDesign = new Map();
  if (shouldFetchHistory()) {
    for (const design of team.rosters.keys()) {
      const commits = await fetchDesignCommits({
        owner: OWNER,
        repo: REPO,
        design,
        token: process.env.GITHUB_TOKEN,
      });
      if (commits.length) commitsByDesign.set(design, commits);
    }
    const total = [...commitsByDesign.values()].reduce((n, c) => n + c.length, 0);
    console.log(`      history: ${total} commit(s) fetched for the team timeline`);
  }

  const timelines = new Map();
  for (const [design, roster] of team.rosters) {
    const pmPath = join(REPO_ROOT, "designs", design, "PM.md");
    const notesPath = join(REPO_ROOT, "designs", design, "NOTES.md");
    const pmText = existsSync(pmPath) ? readFileSync(pmPath, "utf8") : null;
    const notesText = existsSync(notesPath) ? readFileSync(notesPath, "utf8") : null;
    const gitEvents = commitsToEvents(commitsByDesign.get(design) ?? [], { loginToHandle });
    const { events, problems } = readTimeline({ pmText, notesText, roster, gitEvents });
    for (const p of problems) onError(`designs/${design}: timeline: ${p}`);
    timelines.set(design, events);
  }

  // The People page (the #122 IA, revised): the directory of everyone — the
  // core members and the shared review specialists — each as a full profile.
  // A product's own team and build history live on its product page's
  // contributions section, not here. Unconditional, like the designs index.
  rendered.push({
    path: "people/index.html",
    contents: peoplePage(team, { githubBase: GITHUB_BASE }),
  });

  // The "How it works" page: a behind-the-scenes of the pipeline, drawn from the
  // committed architecture docs (docs/architecture/*.md). Static, unconditional.
  rendered.push({
    path: "how-it-works/index.html",
    contents: howItWorksPage({ designCount: designs.length, githubBase: GITHUB_BASE }),
  });

  // Shared resources and the Teams page were both folded into People; keep a
  // redirect at each old route so inbound links and bookmarks survive the move.
  rendered.push({
    path: "shared/index.html",
    contents: redirectPage("/people/", "People"),
  });
  rendered.push({
    path: "teams/index.html",
    contents: redirectPage("/people/", "People"),
  });

  for (const design of designs) {
    // The media rework (PR #159): the README's image embeds and their AI
    // disclaimers move out of the prose into the media stage; the stage is
    // built from the same committed previews, hero first. The stage's files
    // are registered as assets by hand because — like the gallery thumbnails
    // below — no rendered markdown references them anymore.
    const { markdown: proseMarkdown, alts } = stripReadmeMedia(design.readme);
    // The stripper lifts embeds before renderMarkdown's reference checker
    // sees them, so a lifted embed naming a missing file must fail the build
    // here — silently dropping it would break the unresolved-local-reference
    // rule. (Embeds left in the prose still go through the checker.)
    for (const f of missingMediaRefs(alts, design.previews)) {
      onError(
        `${design.readmePath}: embeds previews/${f}, which does not exist in ${design.relDir}/previews/`
      );
    }
    const media = designMedia(design, alts);
    for (const m of media) assets.add(join(design.dir, "previews", m.file));

    const { html, headings } = renderMarkdown(proseMarkdown, {
      repoRoot: REPO_ROOT,
      sourcePath: design.readmePath,
      onAsset,
      onError,
      githubBase: GITHUB_BASE,
      pageFor,
    });

    // Every design gets a model bundle: the configurator reads its parameters,
    // and the 3D viewer renders its geometry (issue #100). A design with no
    // tunable parameters still has geometry to view, so this is unconditional.
    const model = buildModel(REPO_ROOT, design);
    rendered.push({
      path: `${design.relDir}/model.json`,
      contents: JSON.stringify(model),
    });

    const downloads = manifestToDownloads(releaseManifests.get(design.name), {
      owner: OWNER,
      repo: REPO,
    });
    rendered.push({
      path: `${design.relDir}/index.html`,
      contents: designPage(design, {
        html,
        toc: tocHtml(headings),
        githubBase: GITHUB_BASE,
        model,
        media,
        downloads,
        // The team-contributions section: who built this product and its
        // build history, product-scoped. Only a rostered design gets one.
        roster: team.rosters.get(design.name) || null,
        specialists: team.specialists,
        events: timelines.get(design.name) ?? [],
        people: team.people,
      }),
    });
  }

  for (const style of styles) {
    const { html, headings } = renderMarkdown(style.spec, {
      repoRoot: REPO_ROOT,
      sourcePath: style.specPath,
      onAsset,
      onError,
      githubBase: GITHUB_BASE,
      pageFor,
    });
    rendered.push({
      path: `${style.relDir}/index.html`,
      contents: stylePage(style, {
        html,
        toc: tocHtml(headings),
        githubBase: GITHUB_BASE,
        users: designs.filter((d) => d.style === style.name),
      }),
    });
  }

  // The gallery needs its card media even though no rendered markdown
  // references them: the cards are built from structured data, not prose.
  // The hero leads the card (the thumb stays the 3D-viewer's noscript
  // fallback), and the turntable GIF is the card's hover swap.
  for (const design of designs) {
    if (design.hero) assets.add(join(design.dir, "previews", design.hero));
    if (design.thumb) assets.add(join(design.dir, "previews", design.thumb));
    if ((design.previews || []).includes("turntable.gif"))
      assets.add(join(design.dir, "previews", "turntable.gif"));
  }
  for (const style of styles) {
    if (style.swatch) assets.add(join(style.dir, style.swatch));
  }

  if (errors.length) {
    console.error(`\n${errors.length} broken reference(s):`);
    for (const e of errors) console.error(`  ${e}`);
    console.error(
      "\nFix the source document — a link that does not resolve here would 404 in production."
    );
    process.exit(1);
  }

  for (const page of rendered) write(out, page.path, page.contents);

  write(out, "index.html", indexPage(designs, { rosters: team.rosters }));
  if (styles.length) write(out, "styles/index.html", stylesIndexPage(styles, designs));

  let assetBytes = 0;
  for (const abs of assets) {
    const rel = relative(REPO_ROOT, abs).split(sep).join("/");
    const dest = join(out, rel);
    mkdirSync(dirname(dest), { recursive: true });
    copyFileSync(abs, dest);
    assetBytes += statSync(abs).size;
  }

  mkdirSync(join(out, "assets"), { recursive: true });
  copyTree(join(SITE_DIR, "assets"), join(out, "assets"));
  write(out, "assets/favicon.svg", FAVICON);
  write(out, "robots.txt", "User-agent: *\nAllow: /\n");

  // OpenSCAD compiled to WebAssembly, plus the font text() needs. Served from
  // /assets/openscad/ and fetched only when a visitor opens a configurator —
  // it is ~14 MB, so it must never load with the page.
  //
  // OpenSCAD is GPL-2.0. Serving this build to visitors is distribution, so
  // the licence and the provenance of the exact artifact ship beside it.
  let runtimeBytes = 0;
  mkdirSync(join(out, "assets", "openscad"), { recursive: true });
  try {
    copyFileSync(RUNTIME_FILE, join(out, "assets", "openscad", "openscad.js"));
    runtimeBytes = statSync(RUNTIME_FILE).size;
    copyFileSync(FONT_FILE, join(out, "assets", "openscad", "design.ttf"));
    copyFileSync(FONT_LICENSE, join(out, "assets", "openscad", "LICENSE-dejavu.txt"));
    write(out, "assets/openscad/README.txt", runtimeNotice());
  } catch (err) {
    fail(
      `the OpenSCAD runtime is missing (${err.message}).\n` +
        `Run \`npm --prefix site ci\` first — the configurator cannot be built without it.`
    );
  }

  // three.js for the 3D viewer (issue #100). Served from /assets/three/ and,
  // like the OpenSCAD runtime, only fetched once a visitor opens a viewer —
  // the module script is deferred and imports nothing until then. three.js is
  // MIT; its LICENSE ships beside the artifact.
  let viewerBytes = 0;
  mkdirSync(join(out, "assets", "three"), { recursive: true });
  try {
    for (const [from, to] of THREE_FILES) {
      const src = join(THREE_DIR, from);
      copyFileSync(src, join(out, "assets", "three", to));
      viewerBytes += statSync(src).size;
    }
  } catch (err) {
    fail(
      `the 3D viewer library (three.js) is missing (${err.message}).\n` +
        `Run \`npm --prefix site ci\` first — the viewer cannot be built without it.`
    );
  }

  // The DiceBear engine + curated styles for the avatar studio, lazy-loaded
  // like the OpenSCAD runtime: nothing fetches until a re-roll glyph is
  // pressed. Only the runtime .js ships (the packages also carry .d.ts).
  let dicebearBytes = 0;
  try {
    for (const pkg of DICEBEAR_PKGS) {
      const from = join(SITE_DIR, "node_modules", "@dicebear", pkg, "lib");
      const to = join(out, "assets", "dicebear", pkg);
      mkdirSync(to, { recursive: true });
      copyTree(from, to, (name) => name.endsWith(".js"));
    }
    const corePkg = JSON.parse(
      readFileSync(join(SITE_DIR, "node_modules", "@dicebear", "core", "package.json"), "utf8")
    );
    write(
      out,
      "assets/dicebear/README.txt",
      `DiceBear (https://www.dicebear.com) — @dicebear/core ${corePkg.version} plus the\n` +
        `curated avatar styles (${ALL_AVATAR_STYLES.join(", ")}), MIT-licensed code;\n` +
        `each style's artwork credits its creator and license in the generated SVG's\n` +
        `embedded metadata. Exact versions are pinned in site/package-lock.json.\n`
    );
    for (const pkg of DICEBEAR_PKGS) {
      dicebearBytes += treeSize(join(out, "assets", "dicebear", pkg));
    }
  } catch (err) {
    fail(
      `the DiceBear avatar build is missing (${err.message}).\n` +
        `Run \`npm --prefix site ci\` first — the avatar studio cannot be built without it.`
    );
  }

  const models = rendered.filter((p) => p.path.endsWith("model.json")).length;
  const pageCount = rendered.length - models + 1 + (styles.length ? 1 : 0);
  console.log(
    `site: ${pageCount} pages, ${assets.size} assets ` +
      `(${(assetBytes / 1024 / 1024).toFixed(1)} MB) → ${relative(REPO_ROOT, out) || out}`
  );
  console.log(
    `      ${designs.length} designs, ${styles.length} styles, every local reference resolved`
  );
  console.log(
    `      ${team.members.length} people, ${team.rosters.size} team rosters, ` +
      `${team.members.reduce((n, m) => n + m.work.length, 0)} work entries, every handle resolved`
  );
  console.log(
    `      ${models} model bundles, OpenSCAD runtime ` +
      `${(runtimeBytes / 1024 / 1024).toFixed(1)} MB (lazy-loaded, GPL notice shipped)`
  );
  console.log(
    `      3D viewer: three.js ${(viewerBytes / 1024 / 1024).toFixed(1)} MB ` +
      `(vendored, MIT, lazy-loaded)`
  );
  console.log(
    `      avatar studio: DiceBear ${(dicebearBytes / 1024 / 1024).toFixed(1)} MB, ` +
      `${DICEBEAR_PKGS.length - 1} styles (vendored, MIT, lazy-loaded)`
  );
}

/** Total bytes of the files under a directory (recursive). */
function treeSize(dir) {
  let n = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) n += treeSize(p);
    else if (entry.isFile()) n += statSync(p).size;
  }
  return n;
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
