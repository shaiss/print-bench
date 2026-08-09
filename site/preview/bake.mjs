// site/preview/bake.mjs — bakes the media-rework preview SPA from the repo's
// real committed content (designs, READMEs, previews). Run from the repo root:
//
//   node site/preview/bake.mjs                  # → site/preview/media-rework.html
//                                               #   (media referenced by relative path;
//                                               #    serve the repo root to view it)
//   EMBED_DIR=<dir> node site/preview/bake.mjs  # media inlined as data URIs from a
//                                               #   pre-downscaled mirror of
//                                               #   designs/<name>/previews (for a
//                                               #   self-contained preview file)
//
// This is a design *preview*, not a build artifact: it exists so the gallery
// and product-page media rework can be reviewed as a clickable page before the
// real templates in site/lib/templates.mjs are changed. It invents no content —
// every word and image comes from the committed READMEs and previews.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { marked } from "marked";
import { readDesigns } from "../lib/content.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..", "..");
const embedDir = process.env.EMBED_DIR || null;
const outFile =
  process.env.OUT || path.join(here, embedDir ? "media-rework-embedded.html" : "media-rework.html");

const MEDIA_EXT = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp"]);

function prettify(file) {
  return file
    .replace(/\.[a-z0-9]+$/i, "")
    .replace(/^lifestyle-/, "")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function classify(file) {
  const gif = /\.gif$/i.test(file);
  if (/^lifestyle-/.test(file))
    return { kind: gif ? "AI motion clip" : "AI-styled scene", ai: true, motion: gif };
  if (/^product-hero\./.test(file)) return { kind: "Studio render", ai: false, motion: false };
  if (/^turntable\./.test(file)) return { kind: "Turntable", ai: false, motion: true };
  if (/^contact-sheet\./.test(file)) return { kind: "4-view contact sheet", ai: false, motion: false };
  return { kind: gif ? "Animation" : "Detail", ai: false, motion: gif };
}

function mimeOf(buf, file) {
  if (buf.length > 3 && buf[0] === 0x89 && buf[1] === 0x50) return "image/png";
  if (buf.length > 2 && buf[0] === 0x47 && buf[1] === 0x49) return "image/gif";
  if (buf.length > 2 && buf[0] === 0xff && buf[1] === 0xd8) return "image/jpeg";
  if (buf.length > 11 && buf.toString("ascii", 8, 12) === "WEBP") return "image/webp";
  const ext = path.extname(file).toLowerCase().slice(1);
  return `image/${ext === "jpg" ? "jpeg" : ext}`;
}

function mediaSrc(design, file) {
  if (!embedDir) return `../../designs/${design}/previews/${file}`;
  const p = path.join(embedDir, design, file);
  const buf = fs.readFileSync(p);
  return `data:${mimeOf(buf, file)};base64,${buf.toString("base64")}`;
}

// Split a README into (a) the media embeds with their alt text, and (b) the
// text body with the H1, the leading archived blockquote, top-level image
// embeds and the italic AI disclaimers removed — the SPA renders those as
// structured pieces (title, banner, media stage) instead.
function splitReadme(md) {
  const alts = new Map();
  const kept = [];
  let state = "pre-h1"; // pre-h1 → lead (H1 seen, blockquote/blanks droppable) → body
  for (const line of md.split("\n")) {
    const t = line.trim();
    if (state === "pre-h1") {
      if (/^#\s/.test(t)) state = "lead";
      continue;
    }
    if (state === "lead") {
      if (t === "" || t.startsWith(">")) continue;
      state = "body";
    }
    const img = /^!\[([^\]]*)\]\(previews\/([^)\s]+)\)$/.exec(t);
    if (img) {
      alts.set(img[2], img[1]);
      continue;
    }
    if (/^\*(AI-generated|This is an AI)/.test(t)) continue;
    if (/geometry is approximate/.test(t) && /^\*.*\*$/.test(t)) continue;
    kept.push(line);
  }
  return { alts, body: kept.join("\n").trim() };
}

const designs = readDesigns(repoRoot);
const data = designs.map((d) => {
  const md = fs.readFileSync(path.resolve(repoRoot, d.readmePath), "utf8");
  const { alts, body } = splitReadme(md);
  const files = d.previews.filter((f) => MEDIA_EXT.has(path.extname(f).toLowerCase()));
  // Stage order: hero first, then README embed order, then the rest, contact sheet last.
  const order = (f) =>
    /^product-hero\./.test(f) ? 0 : /^contact-sheet\./.test(f) ? 2 : 1;
  const embedOrder = [...alts.keys()];
  files.sort(
    (a, b) =>
      order(a) - order(b) ||
      (embedOrder.indexOf(a) + 1 || 999) - (embedOrder.indexOf(b) + 1 || 999)
  );
  const media = files.map((f) => ({
    file: f,
    src: mediaSrc(d.name, f),
    label: prettify(f),
    alt: alts.get(f) || `${d.title} — ${prettify(f)}`,
    ...classify(f),
  }));
  const spin = media.find((m) => /^turntable\./.test(m.file)) || null;
  return {
    name: d.name,
    title: d.title,
    pitch: marked.parseInline(d.pitch || ""),
    archived: d.warning && /archived/i.test(d.warning) ? d.warning : null,
    parts: d.parts.length,
    coupon: d.hasCoupon,
    parents: d.parents,
    depth: d.depth,
    media,
    spin: spin ? spin.src : null,
    body: marked.parse(body),
  };
});

const fontPath = path.join(repoRoot, "site/assets/fonts/archivo-latin.woff2");
const fontSrc = embedDir
  ? `data:font/woff2;base64,${fs.readFileSync(fontPath).toString("base64")}`
  : "../assets/fonts/archivo-latin.woff2";

const template = fs.readFileSync(path.join(here, "template.html"), "utf8");
const html = template
  .replace("__FONT__", fontSrc)
  .replace("/*__DATA__*/", `const DESIGNS = ${JSON.stringify(data)};`);
fs.writeFileSync(outFile, html);
const size = (fs.statSync(outFile).size / 1024 / 1024).toFixed(2);
console.log(`baked ${outFile} (${size} MB, ${data.length} designs, embed=${!!embedDir})`);
