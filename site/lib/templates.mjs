// Page shells. Plain template literals — the whole site is four page types,
// which is well under the weight where a framework starts paying for itself.

import { escapeHtml, inlineMarkdown, plainText } from "./markdown.mjs";
import { hasConfigurator } from "./model.mjs";
import { humanSize } from "./releases.mjs";
import { memberProfile, memberTeams } from "./profile.mjs";
import { teamContributions } from "./teams.mjs";

const SITE_NAME = "print-bench";
const TAGLINE = "Parametric 3D-printable designs, gated before they ship.";

/**
 * Applied before first paint so a stored theme choice never flashes.
 * Kept inline (and tiny) for that reason — site.js only wires the button.
 */
const THEME_BOOTSTRAP = `(function(){try{var t=localStorage.getItem("print-bench-theme");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t)}}catch(e){}})();`;

export function layout({ title, description, body, canonicalPath = "/", extraHead = "", extraScript = "" }) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<meta name="description" content="${escapeHtml(description || TAGLINE)}">
<meta property="og:title" content="${escapeHtml(title)}">
<meta property="og:description" content="${escapeHtml(description || TAGLINE)}">
<meta property="og:type" content="website">
<link rel="stylesheet" href="/assets/site.css">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<script>${THEME_BOOTSTRAP}</script>
${extraHead}
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<header class="site-head">
  <div class="wrap">
    <a class="brand" href="/"><span class="brand-mark">◧</span> ${SITE_NAME}</a>
    <nav class="site-nav">
      <a href="/"${canonicalPath === "/" ? ' aria-current="page"' : ""}>Designs</a>
      <a href="/styles/"${canonicalPath.startsWith("/styles") ? ' aria-current="page"' : ""}>Styles</a>
      <a href="/people/"${canonicalPath.startsWith("/people") ? ' aria-current="page"' : ""}>People</a>
      <a href="https://github.com/shaiss/print-bench" rel="noopener noreferrer">Source</a>
      <button class="theme-toggle" type="button" aria-label="Switch theme">☾</button>
    </nav>
  </div>
</header>
<main id="main">
${body}
</main>
<footer class="site-foot">
  <div class="wrap">
    <span>Every design here is rendered, printability-gated and test-sliced in CI before it lands.</span>
    <span><a href="https://github.com/shaiss/print-bench" rel="noopener noreferrer">shaiss/print-bench</a></span>
  </div>
</footer>
<script src="/assets/site.js" defer></script>
${extraScript}
</body>
</html>
`;
}

/** Links to a design's parents, in include order. */
function parentLinks(design) {
  return (design.parents || []).map(
    (p) => `<a href="/designs/${encodeURIComponent(p)}/">${escapeHtml(p)}</a>`
  );
}

/**
 * The credit sentence a derivative carries, word for word the one
 * scripts/gallery.sh writes into the README — including the multi-parent
 * form, where every parent is named rather than just the one the row nests
 * under, and the suffix says which of them wins.
 */
function lineageCredit(design) {
  const links = parentLinks(design);
  if (links.length === 0) return "";
  if (links.length === 1) return `derived from ${links[0]}`;
  const rest = links.slice(1).map((l) => `, then ${l}`).join("");
  return `derived from ${links[0]}${rest} — last include wins`;
}

function card(design) {
  const depth = design.depth || 0;
  const derived = depth > 0 && (design.parents || []).length > 0;
  const thumb = design.thumb
    ? `<a class="card-media" href="/${design.relDir}/"><img src="/${design.relDir}/previews/${design.thumb}" alt="${escapeHtml(design.name)} preview"></a>`
    : "";
  const tags = [];
  if (design.parts.length) {
    tags.push(`<span class="tag">${design.parts.length} printable parts</span>`);
  }
  if (design.hasCoupon) tags.push(`<span class="tag tag-plain">fit coupon</span>`);
  if (design.style) tags.push(`<span class="tag tag-plain">${escapeHtml(design.style)}</span>`);
  if (design.warning) {
    tags.push(`<span class="tag tag-warn">${escapeHtml(design.warning)}</span>`);
  }
  // A derivative is marked in three ways that survive a card grid reflowing
  // to one column: the ↳ lead-in, the credit line, and the indent. The credit
  // is the load-bearing one — the others are position, and position alone is
  // what let this read as an independent design.
  const open = derived
    ? `<article class="card card-derived" style="--lineage-depth:${depth}">`
    : `<article class="card">`;
  const lead = derived ? '<span class="lineage-mark" aria-hidden="true">↳</span> ' : "";
  const credit = derived
    ? `\n    <p class="card-lineage">${lineageCredit(design)}</p>`
    : "";
  return `${open}
  ${thumb}
  <div class="card-body">
    <h2>${lead}<a href="/${design.relDir}/">${escapeHtml(design.title)}</a></h2>
    <p>${inlineMarkdown(design.pitch)}</p>${credit}
    <div class="card-foot">${tags.join("\n      ")}</div>
  </div>
</article>`;
}

export function indexPage(designs) {
  const body = `<div class="wrap">
  <section class="hero">
    <p class="eyebrow">${escapeHtml(String(designs.length))} designs</p>
    <h1>${TAGLINE}</h1>
    <p>Each one is a parametric OpenSCAD model with a product page, previews
    rendered from its own source, and a printability gate it had to pass —
    watertightness, overhangs, thin walls and a real PrusaSlicer test-slice —
    before it was allowed to merge.</p>
  </section>
  <section class="grid">
${designs.map(card).join("\n")}
  </section>
</div>`;
  return layout({
    title: `${SITE_NAME} — ${TAGLINE}`,
    description: TAGLINE,
    body,
    canonicalPath: "/",
  });
}

/**
 * The in-browser configurator.
 *
 * Rendered as inert markup with the runtime URLs in data attributes; nothing
 * is fetched until the visitor presses the button. The OpenSCAD build is
 * ~14 MB, so loading it with the page would make every product page
 * expensive to read.
 */
function configuratorPanel(design, model) {
  const count = model.sections.reduce((n, s) => n + s.params.length, 0);
  return `
<section class="cfg" id="configure"
  data-configurator="/${design.relDir}/model.json"
  data-runtime="/assets/openscad/openscad.js"
  data-worker="/assets/openscad-worker.js"
  data-font="/assets/openscad/design.ttf">
  <h2>Make it fit</h2>
  <p>This design has <strong>${count} tunable parameters</strong>. Change them
  and render your own STL — OpenSCAD runs in your browser, so nothing is
  uploaded and nothing is installed.</p>
  <p class="cfg-caveat"><strong>An STL you configure here is ungated.</strong>
  The files this project ships have each passed a printability check and a
  PrusaSlicer test-slice; your variant has not. Treat it as a starting point,
  and print the fit coupon first if the design has one.</p>
  <button class="btn btn-primary" type="button" data-open>Open the configurator</button>
  <div class="cfg-panel" data-panel hidden>
    <div class="cfg-controls" data-controls></div>
    <div class="cfg-actions">
      <button class="btn btn-primary" type="button" data-render>Render STL</button>
      <button class="btn" type="button" data-reset>Reset</button>
      <a class="btn" data-download hidden>Download STL</a>
    </div>
    <p class="cfg-status" data-status></p>
    <div class="cfg-diagnostics" data-diagnostics hidden></div>
    <p class="cfg-foot muted">Rendering is done by
      <a href="/assets/openscad/README.txt">OpenSCAD compiled to WebAssembly</a>
      (GPL-2.0) on your own machine. The first render downloads it, about 14 MB.</p>
  </div>
</section>`;
}

/**
 * The in-browser 3D viewer (issue #100).
 *
 * Rendered as inert markup, exactly like the configurator: nothing loads until
 * the visitor presses "View in 3D". On press, viewer.js renders the design's
 * own source at its default parameters with the OpenSCAD-WASM worker the site
 * already ships — the same geometry the gate exports — and draws the resulting
 * STL with three.js. It sits on every product page, including designs with no
 * tunable parameters (which get no configurator), because every design has
 * geometry to inspect.
 *
 * Progressive enhancement: without JavaScript the <noscript> fallback points at
 * the rendered previews already shown above, and the rest of the page is
 * untouched.
 */
function viewerPanel(design) {
  const fallback = design.thumb
    ? `<img src="/${design.relDir}/previews/${escapeHtml(design.thumb)}" alt="${escapeHtml(design.name)} preview">`
    : "";
  return `
<section class="viewer" id="view-3d"
  data-viewer
  data-model="/${design.relDir}/model.json"
  data-runtime="/assets/openscad/openscad.js"
  data-worker="/assets/openscad-worker.js"
  data-font="/assets/openscad/design.ttf">
  <h2>View in 3D</h2>
  <p>Inspect the real geometry — drag to rotate, scroll to zoom. The model is
  rendered from this design's own source at its default settings, right in your
  browser; nothing is uploaded.</p>
  <button class="btn btn-primary" type="button" data-view-open>View in 3D</button>
  <div class="viewer-stage" data-stage hidden>
    <div class="viewer-canvas" data-canvas></div>
    <p class="viewer-status" data-view-status role="status" aria-live="polite"></p>
    <p class="viewer-foot muted">Rendered on your machine by
      <a href="/assets/openscad/README.txt">OpenSCAD compiled to WebAssembly</a>
      (GPL-2.0, about 14 MB on first use) and drawn with
      <a href="/assets/three/LICENSE.txt">three.js</a> (MIT).</p>
  </div>
  <noscript>
    <p class="muted">Enable JavaScript to inspect this design in 3D. A rendered
    preview is shown above.</p>
    ${fallback}
  </noscript>
</section>`;
}

/**
 * The Downloads rail-block (issue #139). Built from a release manifest fetched
 * at build time; null when the design has no release, so the block simply does
 * not appear (the site's no-404 rule — an absent release is not a broken link).
 * Each part links to its STL release asset with size and a short SHA-256; the
 * full checksum rides in the title so a careful downloader can verify.
 */
function downloadsBlock(downloads) {
  if (!downloads) return "";
  const rows = downloads.parts
    .map((p) => {
      const meta = [
        p.size != null ? humanSize(p.size) : "",
        p.sha256 ? p.sha256.slice(0, 12) : "",
      ]
        .filter(Boolean)
        .join(" · ");
      const title = p.sha256 ? ` title="sha256:${escapeHtml(p.sha256)}"` : "";
      return `      <li><a href="${escapeHtml(p.url)}" rel="noopener noreferrer">${escapeHtml(
        p.part
      )}</a>${meta ? ` <span class="dl-meta"${title}>${escapeHtml(meta)}</span>` : ""}</li>`;
    })
    .join("\n");
  return `<div class="rail-block">
    <h3>Downloads</h3>
    <p class="rail-note">Release <a href="${escapeHtml(
      downloads.releaseUrl
    )}" rel="noopener noreferrer"><code>${escapeHtml(
      downloads.version
    )}</code></a> — gated STLs, ready to slice.</p>
    <ul class="downloads">
${rows}
    </ul>
    <p><a class="btn" href="${escapeHtml(
      downloads.bundleUrl
    )}" rel="noopener noreferrer" download>Download all (zip)</a></p>
  </div>`;
}

export function designPage(design, { html, toc, githubBase, model, downloads = null, roster = null, specialists = [], events = [], people = new Map() }) {
  const showConfigurator = hasConfigurator(model);
  // The team-contributions section (the #122 IA, revised): who built this
  // product and its build history, shown here on the product page. Identity
  // only — the full profiles live on the People page. Rendered only when the
  // design has a committed roster; the site invents no team.
  const contributions = roster
    ? teamContributions(roster, { specialists, events, people })
    : "";
  const src = `${githubBase}/${design.relDir}`;
  const rail = `<aside class="rail">
  ${toc ? `<div class="rail-block"><h3>On this page</h3>${toc}</div>` : ""}
  ${downloadsBlock(downloads)}
  <div class="rail-block">
    <h3>Source</h3>
    <ul>
${design.scads
  .map(
    (f) =>
      `      <li><a href="${src}/${encodeURIComponent(f)}" rel="noopener noreferrer"><code>${escapeHtml(f)}</code></a></li>`
  )
  .join("\n")}
      <li><a href="${src}/NOTES.md" rel="noopener noreferrer">Engineering notes</a></li>
      <li><a href="${src}/" rel="noopener noreferrer">Design directory</a></li>
    </ul>
  </div>
  ${
    design.parts.length
      ? `<div class="rail-block"><h3>Printable parts</h3><ul>${design.parts
          .map((p) => `<li><code>${escapeHtml(p)}</code></li>`)
          .join("")}</ul></div>`
      : ""
  }
  ${
    (design.parents || []).length
      ? `<div class="rail-block"><h3>Derived from</h3><ul>${parentLinks(design)
          .map((link) => `<li>${link}</li>`)
          .join("")}</ul>${
          design.parents.length > 1
            ? '<p class="rail-note">In include order — the last include wins.</p>'
            : ""
        }</div>`
      : ""
  }
  ${
    design.style
      ? `<div class="rail-block"><h3>Style</h3><ul><li><a href="/styles/${encodeURIComponent(design.style)}/">${escapeHtml(design.style)}</a></li></ul></div>`
      : ""
  }
</aside>`;

  const body = `<div class="wrap">
  <div class="design-layout">
    <article class="prose">
${html}
${viewerPanel(design)}
${showConfigurator ? configuratorPanel(design, model) : ""}
    </article>
${rail}
  </div>
${contributions}
</div>`;

  // The viewer's addons import the bare specifier `three`; an import map on the
  // page resolves it to the vendored module build. It must precede the module
  // script, which is why it goes in <head> — viewer.js loads at end of <body>.
  const importMap =
    '<script type="importmap">' +
    JSON.stringify({ imports: { three: "/assets/three/three.module.min.js" } }) +
    "</script>";

  const scripts = [
    // A module script is deferred by definition and imports nothing until the
    // viewer is opened, so shipping it on every product page costs a page load
    // nothing until a visitor asks to view.
    '<script type="module" src="/assets/viewer.js"></script>',
    showConfigurator ? '<script src="/assets/configurator.js" defer></script>' : "",
  ]
    .filter(Boolean)
    .join("\n");

  return layout({
    title: `${design.title} — ${SITE_NAME}`,
    description: plainText(design.pitch),
    body,
    canonicalPath: `/${design.relDir}/`,
    extraHead: importMap,
    extraScript: scripts,
  });
}

export function stylesIndexPage(styles, designs) {
  const cards = styles
    .map((s) => {
      const users = designs.filter((d) => d.style === s.name);
      const media = s.swatch
        ? `<a class="card-media" href="/${s.relDir}/"><img src="/${s.relDir}/${s.swatch}" alt="${escapeHtml(s.name)} swatch"></a>`
        : "";
      return `<article class="card">
  ${media}
  <div class="card-body">
    <h2><a href="/${s.relDir}/">${escapeHtml(s.title)}</a></h2>
    <p>${inlineMarkdown(s.summary)}</p>
    <div class="card-foot">${
      users.length
        ? users
            .map(
              (d) =>
                `<a class="tag" href="/${d.relDir}/">${escapeHtml(d.name)}</a>`
            )
            .join("")
        : '<span class="tag tag-plain">no design uses it yet</span>'
    }</div>
  </div>
</article>`;
    })
    .join("\n");

  const body = `<div class="wrap">
  <section class="hero">
    <p class="eyebrow">Design languages</p>
    <h1>Styles</h1>
    <p>A style is a look lifted off a reference model and written down as
    measurements — edge softness, the rounding vocabulary, chamfer grammar,
    feature sizes — so a new design can be told what to look like instead of
    getting whatever the session felt like. Parts that declare one are checked
    against it in CI.</p>
  </section>
  <section class="grid">
${cards || '<p class="muted">No styles yet.</p>'}
  </section>
</div>`;

  return layout({
    title: `Styles — ${SITE_NAME}`,
    description: "Design languages lifted from reference models, and the parts held to them.",
    body,
    canonicalPath: "/styles/",
  });
}

export function stylePage(style, { html, toc, githubBase, users }) {
  const rail = `<aside class="rail">
  ${toc ? `<div class="rail-block"><h3>On this page</h3>${toc}</div>` : ""}
  <div class="rail-block">
    <h3>Pack</h3>
    <ul>
      <li><a href="${githubBase}/${style.relDir}/style.json" rel="noopener noreferrer"><code>style.json</code></a></li>
      <li><a href="${githubBase}/${style.relDir}/style.scad" rel="noopener noreferrer"><code>style.scad</code></a></li>
      <li><a href="${githubBase}/${style.relDir}/swatch.scad" rel="noopener noreferrer"><code>swatch.scad</code></a></li>
    </ul>
  </div>
  ${
    users.length
      ? `<div class="rail-block"><h3>Used by</h3><ul>${users
          .map((d) => `<li><a href="/${d.relDir}/">${escapeHtml(d.name)}</a></li>`)
          .join("")}</ul></div>`
      : ""
  }
</aside>`;

  const body = `<div class="wrap">
  <div class="design-layout">
    <article class="prose">
${html}
    </article>
${rail}
  </div>
</div>`;

  return layout({
    title: `${style.title} — ${SITE_NAME}`,
    description: plainText(style.summary),
    body,
    canonicalPath: `/${style.relDir}/`,
  });
}

/**
 * The People page (the #122 IA, revised): the directory of everyone who
 * builds here — the humans and PM agents on the product cores, and the shared
 * review specialists — each rendered as the full member profile in the
 * cross-team scope, so a profile shows the person's mandate, the product teams
 * they've been part of (the team chips), and their recent work across teams.
 * This is where a person's whole story lives; a *product's* team and build
 * history live on its product page (designPage's contributions section). The
 * shared specialists (formerly their own Shared resources page) are folded in
 * here — their `shared: true` pill still marks them as owned by no one team.
 * Core folks first, shared specialists last.
 */
export function peoplePage(team, { githubBase }) {
  const ordered = team.members
    .slice()
    .sort((a, b) => Number(a.shared) - Number(b.shared));
  const cards = ordered
    .map(
      (m) => `<div class="card profile-card">
${memberProfile(m, { scope: null, teams: memberTeams(m, team.rosters), githubBase })}
</div>`
    )
    .join("\n");

  const body = `<div class="wrap">
  <section class="hero">
    <p class="eyebrow">${escapeHtml(String(team.members.length))} people</p>
    <h1>People</h1>
    <p>Everyone who builds here — the humans and PM agents on each product's
    core team, and the shared specialists who review every design. Each profile
    shows the person's mandate and the product teams they've been part of; a
    product's own team and build history live on its product page.</p>
  </section>
  <section class="grid profile-grid">
${cards || '<p class="muted">No one registered yet.</p>'}
  </section>
</div>`;

  return layout({
    title: `People — ${SITE_NAME}`,
    description:
      "Everyone who builds print-bench — the humans and PM agents on each product, and the shared review specialists.",
    body,
    canonicalPath: "/people/",
  });
}

/**
 * A tiny redirect kept at the old /shared/ route so inbound links survive the
 * fold of Shared resources into the People page. No nav, no chrome — it exists
 * only to forward.
 */
export function sharedRedirect() {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=/people/">
<link rel="canonical" href="/people/">
<title>Moved to People — ${SITE_NAME}</title>
</head>
<body>
<p>Shared resources are now part of <a href="/people/">People</a>.</p>
</body>
</html>
`;
}

export const FAVICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" rx="6" fill="#14171a"/>
<path d="M8 22V10h7a5 5 0 0 1 0 10H8z" fill="none" stroke="#ff9166" stroke-width="2.4" stroke-linejoin="round"/>
<circle cx="22.5" cy="21" r="2" fill="#ff9166"/>
</svg>
`;
