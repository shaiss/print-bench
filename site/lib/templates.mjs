// Page shells. Plain template literals — the whole site is four page types,
// which is well under the weight where a framework starts paying for itself.

import { AVATAR_STYLES, AVATAR_BACKGROUND } from "./avatars.mjs";
import { escapeHtml, inlineMarkdown, plainText } from "./markdown.mjs";
import { hasConfigurator } from "./model.mjs";
import { humanSize } from "./releases.mjs";
import { memberProfile, memberTeams } from "./profile.mjs";
import { contributorRow, reviewedBy, historySlot } from "./teams.mjs";

/**
 * The product page's media stage (the media rework, PR #159): one large
 * viewer over a labeled thumbnail rail, replacing the README's stacked
 * image wall. Each rail entry is labeled with what the media *is* (studio
 * render / turntable / AI-styled scene / …), and AI media carry their
 * disclosure as a caption on exactly the media it applies to. Ships inert:
 * site.js wires the switching; without JavaScript the stage shows the hero
 * and the rail still shows every preview.
 */
function mediaStage(design, media) {
  // Even a single preview renders as a stage (rail-less): the README's embed
  // was lifted out of the prose, so the stage is where it now lives — a
  // design with one image must not lose it.
  if (!media || media.length === 0) return "";
  const first = media[0];
  // Filenames come from the committed previews directory, but they are still
  // interpolated into attributes — escape them like every other repo-derived
  // string here (the scad list, the alt text) rather than trusting the glob.
  const src = (m) => escapeHtml(`/${design.relDir}/previews/${m.file}`);
  const thumbs = media
    .map(
      (m, i) => `    <button class="stage-thumb${i === 0 ? " sel" : ""}" type="button" aria-current="${i === 0 ? "true" : "false"}"
      data-label="${escapeHtml(m.label)}" data-kind="${escapeHtml(m.kind)}"
      data-alt="${escapeHtml(m.alt)}"${m.disclosure ? ` data-disclosure="${escapeHtml(m.disclosure)}"` : ""}
      aria-label="${escapeHtml(m.label)} — ${escapeHtml(m.kind)}">
      <img src="${src(m)}" alt="" loading="lazy">
      <span class="stage-thumb-text"><span class="stage-thumb-label">${escapeHtml(m.label)}</span>
        <span class="stage-thumb-kind">${escapeHtml(m.kind)}${m.ai ? ' · <span class="stage-ai-mark">AI</span>' : ""}</span></span>
    </button>`
    )
    .join("\n");
  const rail =
    media.length > 1
      ? `
  <div class="stage-rail" data-stage-rail>
${thumbs}
  </div>`
      : "";
  // Every view renders server-side, all but the first hidden; site.js only
  // toggles `hidden` and writes captions via textContent, so no DOM-read
  // text ever reaches a URL or HTML sink (CodeQL js/xss-through-dom). The
  // hidden views are lazy — and the rail's thumbs use the same URLs, so a
  // view is in cache by the time it's unhidden.
  const views = media
    .map(
      (m, i) =>
        `<img class="stage-view" data-stage-view src="${src(m)}" alt="${escapeHtml(m.alt)}"${i === 0 ? "" : ' hidden loading="lazy"'}>`
    )
    .join("");
  return `<section class="media-stage${media.length > 1 ? "" : " media-stage-solo"}" data-media-stage aria-label="Design media">
  <div class="stage-main">
    <div class="stage-frame">${views}</div>
    <div class="stage-cap">
      <p class="stage-cap-row"><strong data-stage-label>${escapeHtml(first.label)}</strong>
        <span class="tag tag-plain" data-stage-kind>${escapeHtml(first.kind)}</span>
        ${media.length > 1 ? `<span class="stage-count" data-stage-count>1 / ${media.length}</span>` : ""}</p>
      <p class="stage-alt" data-stage-alt>${escapeHtml(first.alt)}</p>
      <p class="stage-disclosure" data-stage-disclosure${first.disclosure ? "" : " hidden"}>${escapeHtml(first.disclosure || "")}</p>
    </div>
  </div>${rail}
</section>`;
}

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
      <a href="https://github.com/shaiss/print-bench" rel="noopener noreferrer">Source ↗</a>
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

/**
 * The gallery card's pair credit — "Shai with Vera" — from the design's
 * committed roster (team.conf, resolved by readTeam). First names, humans
 * before agents; a rosterless design renders no credit (the site invents
 * no team).
 */
function pairCredit(roster) {
  if (!roster || !roster.core.length) return "";
  const first = (m) => m.name.split(" ")[0];
  const humans = roster.core.filter((m) => m.kind === "human").map(first);
  const agents = roster.core.filter((m) => m.kind !== "human").map(first);
  const text =
    humans.length && agents.length
      ? `${humans.join(" & ")} with ${agents.join(" & ")}`
      : (humans.length ? humans : agents).join(" & ");
  return `\n    <p class="card-credit">${escapeHtml(text)}</p>`;
}

function card(design, roster = null) {
  const depth = design.depth || 0;
  const derived = depth > 0 && (design.parents || []).length > 0;
  // The card leads with the design's hero shot (the media rework, PR #159):
  // grayscale at rest per the Modernist imagery rule, color + the turntable
  // GIF on hover when the design ships one (site.js swaps the src; without
  // JavaScript the card is simply the still hero). The contact sheet stays
  // the fallback for a design with no product shot.
  const previews = design.previews || [];
  const spin = previews.includes("turntable.gif") ? "turntable.gif" : null;
  const mediaCount = previews.length;
  // Both frames render server-side and CSS does the hover swap — no script
  // ever writes a URL it read from the DOM (CodeQL js/xss-through-dom, the
  // same rule avatar-studio is structured around). The GIF is lazy and
  // display:none until hover, so it isn't fetched with the page.
  const thumb = design.hero
    ? `<a class="card-media" href="/${design.relDir}/"><img class="card-hero" src="${escapeHtml(`/${design.relDir}/previews/${design.hero}`)}" alt="${escapeHtml(design.name)} preview" loading="lazy">${
        spin
          ? `<img class="card-spin" src="${escapeHtml(`/${design.relDir}/previews/${spin}`)}" alt="" loading="lazy">`
          : ""
      }${
        mediaCount > 1 ? `<span class="media-chip">${mediaCount} media</span>` : ""
      }${spin ? `<span class="media-chip media-chip-spin">turntable</span>` : ""}</a>`
    : "";
  const tags = [];
  if (design.parts.length) {
    tags.push(
      `<span class="tag">${design.parts.length} ${design.parts.length === 1 ? "part" : "parts"}</span>`
    );
  }
  if (design.hasCoupon) tags.push(`<span class="tag tag-plain">fit coupon</span>`);
  if (design.style) tags.push(`<span class="tag tag-plain">${escapeHtml(design.style)}</span>`);
  if (design.warning) {
    // The archived banner is boilerplate — compact it to a badge so it can't
    // clip mid-word at card width. Any *other* warning ("do not print yet")
    // is load-bearing content and renders in full, wrapping as needed.
    const compact = /^Archived at v[\d.]+/.test(design.warning)
      ? `Archived ${design.warning.match(/v[\d.]+\d/)?.[0] ?? ""}`.trim()
      : null;
    tags.push(
      `<span class="tag tag-warn"${compact ? ` title="${escapeHtml(design.warning)}"` : ""}>${escapeHtml(compact || design.warning)}</span>`
    );
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
    <div class="card-foot">${tags.join("\n      ")}</div>${pairCredit(roster)}
  </div>
</article>`;
}

export function indexPage(designs, { rosters = new Map() } = {}) {
  const body = `<div class="wrap">
  <section class="hero">
    <p class="eyebrow">${escapeHtml(String(designs.length))} designs · every one gated in CI</p>
    <h1>Parametric designs,<br>gated before they ship.</h1>
    <p>OpenSCAD models co-designed by humans and AI reviewers. Previews render
    from source; a printability gate — watertight, overhang-checked,
    test-sliced — passes before merge.</p>
  </section>
  <section class="grid">
${designs.map((d) => card(d, rosters.get(d.name) || null)).join("\n")}
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

/**
 * The lineage strip a derivative's page opens with (wireframe 1d): the
 * parent chain as ruled nodes, current design filled — same include order
 * as the rail's "Derived from" block, kept there too for the words.
 */
function lineageStrip(design) {
  if (!(design.parents || []).length) return "";
  const nodes = design.parents.map(
    (p) =>
      `<a class="lineage-node" href="/designs/${encodeURIComponent(p)}/">${escapeHtml(p)}</a><span class="lineage-arrow" aria-hidden="true">↳</span>`
  );
  return `<p class="lineage-strip">${nodes.join("")}<span class="lineage-node lineage-node-current">${escapeHtml(design.name)}</span></p>`;
}

export function designPage(design, { html, toc, githubBase, model, media = [], downloads = null, roster = null, specialists = [], events = [], people = new Map() }) {
  const showConfigurator = hasConfigurator(model);
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

  // The product page's own header owns the design's identity (lineage strip,
  // title, pitch, primary actions), so the README's H1 — the same title —
  // would repeat directly under it. Drop that one heading; everything else in
  // the README renders untouched.
  const prose = html.replace(/^\s*<h1[^>]*>[\s\S]*?<\/h1>\n?/, "");

  // One concern on screen at a time (wireframe 1d): Overview / Workbench /
  // History / Team. The tab bar ships hidden and every panel visible, each
  // opening with its own ruled label — site.js unhides the bar and starts
  // hiding unselected panels, so without JavaScript the page is simply the
  // stacked document and nothing is unreachable. History and Team exist only
  // for a design with a committed roster; the site invents no team.
  const panels = [
    {
      id: "overview",
      label: "Overview",
      body: `${mediaStage(design, media)}
  <div class="design-layout">
    <article class="prose">
${prose}
    </article>
${rail}
  </div>`,
    },
    {
      id: "workbench",
      label: "Workbench",
      body: `${viewerPanel(design)}
${showConfigurator ? configuratorPanel(design, model) : ""}`,
    },
    roster
      ? {
          id: "history",
          label: "History",
          body: historySlot(roster.design, { events, people }),
        }
      : null,
  ].filter(Boolean);

  const tabBar = `<div class="design-tabs" role="tablist" data-tabs hidden>
${panels
  .map(
    (p, i) =>
      `    <button class="design-tab" role="tab" type="button" id="tab-${p.id}" aria-controls="${p.id}" aria-selected="${i === 0 ? "true" : "false"}">${p.label}</button>`
  )
  .join("\n")}
  </div>`;

  const panelHtml = panels
    .map(
      (p) => `  <section class="tab-panel" id="${p.id}" role="tabpanel" aria-labelledby="tab-${p.id}">
    <p class="panel-label">${p.label}</p>
${p.body}
  </section>`
    )
    .join("\n");

  const actions = [
    downloads
      ? `<a class="btn btn-primary" href="${escapeHtml(downloads.bundleUrl)}" rel="noopener noreferrer" download>Download STLs</a>`
      : "",
    `<a class="btn" href="#workbench">Open workbench →</a>`,
  ]
    .filter(Boolean)
    .join("\n      ");

  const body = `<div class="wrap">
  <header class="design-head">
    ${lineageStrip(design)}
    <h1>${escapeHtml(design.title)}</h1>
    <p class="design-sub">${inlineMarkdown(design.pitch)}</p>
    ${
      roster
        ? `<div class="contributions-team">
    <p class="eyebrow">Built by</p>
    ${contributorRow(roster.core)}
    ${reviewedBy(specialists)}
  </div>`
        : ""
    }
    <div class="btn-row">
      ${actions}
    </div>
  </header>
${tabBar}
${panelHtml}
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
    <p class="card-credit">STYLE.md · style.json</p>
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
    <p class="eyebrow">${escapeHtml(String(styles.length))} ${styles.length === 1 ? "style" : "styles"}</p>
    <h1>How the previews get their look.</h1>
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

  // The avatar studio's data block: the curated style sets and the commit
  // paths, read by /assets/avatar-studio.js when a re-roll glyph is pressed.
  // Data only — the studio is browser-local, and committing the lines it
  // shows (or dispatching the Regenerate-avatar Action) is what changes the
  // site for everyone.
  // Styles and the background token only — the GitHub commit-target URLs
  // live as literals in avatar-studio.js itself, so no DOM-read text ever
  // reaches an href (CodeQL js/xss-through-dom).
  const studioData = `<script type="application/json" id="avatar-studio-data">${JSON.stringify({
    styles: AVATAR_STYLES,
    background: AVATAR_BACKGROUND,
  })}</script>`;

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

  // The vendored DiceBear style modules import the bare specifier
  // "@dicebear/core"; this resolves it to the vendored engine — same
  // no-external-reference pattern as the product page's `three` map. It must
  // precede any module load, hence <head>.
  const importMap =
    '<script type="importmap">' +
    JSON.stringify({ imports: { "@dicebear/core": "/assets/dicebear/core/index.js" } }) +
    "</script>";

  return layout({
    title: `People — ${SITE_NAME}`,
    description:
      "Everyone who builds print-bench — the humans and PM agents on each product, and the shared review specialists.",
    body,
    canonicalPath: "/people/",
    extraHead: importMap,
    extraScript: studioData,
  });
}

/**
 * A tiny redirect page kept at a retired route so inbound links and bookmarks
 * survive a move. No nav, no chrome — it exists only to forward. Used for both
 * `/shared/` and `/teams/`, the two routes the revised IA folded into
 * `/people/`. `to` and `label` are trusted call-site literals.
 */
export function redirectPage(to, label) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=${to}">
<link rel="canonical" href="${to}">
<title>Moved to ${label} — ${SITE_NAME}</title>
</head>
<body>
<p>This page has moved to <a href="${to}">${label}</a>.</p>
</body>
</html>
`;
}

export const FAVICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" fill="#201e1d"/>
<path d="M8 22V10h7a5 5 0 0 1 0 10H8z" fill="none" stroke="#ec3013" stroke-width="2.4" stroke-linejoin="round"/>
<rect x="20.5" y="19" width="4" height="4" fill="#ec3013"/>
</svg>
`;
