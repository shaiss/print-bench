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

import { readDesigns, readStyles } from "./lib/content.mjs";
import { readTeam } from "./lib/team.mjs";
import { readTimeline } from "./lib/timeline.mjs";
import { renderMarkdown, tocHtml } from "./lib/markdown.mjs";
import { buildModel } from "./lib/model.mjs";
import {
  indexPage,
  designPage,
  stylesIndexPage,
  stylePage,
  sharedPage,
  teamsPage,
  FAVICON,
} from "./lib/templates.mjs";

const SITE_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(SITE_DIR, "..");
const GITHUB_BASE = "https://github.com/shaiss/print-bench/blob/main";

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

function copyTree(from, to) {
  for (const entry of readdirSync(from, { withFileTypes: true })) {
    const src = join(from, entry.name);
    const dest = join(to, entry.name);
    if (entry.isDirectory()) {
      mkdirSync(dest, { recursive: true });
      copyTree(src, dest);
    } else if (entry.isFile()) {
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

function main() {
  const { out } = parseArgs(process.argv.slice(2));

  const designs = readDesigns(REPO_ROOT);
  const styles = readStyles(REPO_ROOT);

  if (designs.length === 0) fail("no designs found under designs/");

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

  // The Shared resources page (issue #124): the registry's shared
  // specialists rendered as full member profiles. Unconditional, like the
  // designs index — the page saying "none registered yet" is truer than the
  // nav linking a page that does not exist.
  rendered.push({
    path: "shared/index.html",
    contents: sharedPage(team, { githubBase: GITHUB_BASE }),
  });

  // The "History of work together" timeline (issue #126): assemble each
  // rostered team's shared record from its own committed files (PM.md
  // decision log, optional NOTES.md field-test log) here, where the
  // filesystem is reachable, and hand the events to the team page. Problems
  // go to the same accumulator as every other structured source, so a
  // drifted decision-log table fails ./scripts/site.sh rather than rendering
  // a hole. Product-scoped by construction: each team reads only its own
  // design's files.
  const timelines = new Map();
  for (const [design, roster] of team.rosters) {
    const pmPath = join(REPO_ROOT, "designs", design, "PM.md");
    const notesPath = join(REPO_ROOT, "designs", design, "NOTES.md");
    const pmText = existsSync(pmPath) ? readFileSync(pmPath, "utf8") : null;
    const notesText = existsSync(notesPath) ? readFileSync(notesPath, "utf8") : null;
    const { events, problems } = readTimeline({ pmText, notesText, roster });
    for (const p of problems) onError(`designs/${design}: timeline: ${p}`);
    timelines.set(design, events);
  }

  // The Teams page (issue #125): the switcher over every rostered product and
  // the product-scoped team page for the worked example. Unconditional, same
  // reasoning as the Shared resources page above — the switcher saying which
  // teams exist is truer than a nav link to a page that does not.
  rendered.push({
    path: "teams/index.html",
    contents: teamsPage(team, designs, { githubBase: GITHUB_BASE, timelines }),
  });

  for (const design of designs) {
    const { html, headings } = renderMarkdown(design.readme, {
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

    rendered.push({
      path: `${design.relDir}/index.html`,
      contents: designPage(design, {
        html,
        toc: tocHtml(headings),
        githubBase: GITHUB_BASE,
        model,
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

  // The gallery needs its thumbnails even though no rendered markdown
  // references them: the cards are built from structured data, not prose.
  for (const design of designs) {
    if (design.thumb) assets.add(join(design.dir, "previews", design.thumb));
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

  write(out, "index.html", indexPage(designs));
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
}

main();
