// Markdown → HTML for repo documents, with every local reference checked.
//
// The load-bearing idea: the output tree MIRRORS the repo tree, so a product
// page written as designs/<name>/README.md lands at /designs/<name>/ and its
// `previews/contact-sheet.png` keeps working with no rewriting at all. Only
// references the site does not itself serve (a .scad, a NOTES.md) get
// rewritten — to GitHub, where they really live.
//
// Anything that points at a file which does not exist is a build error, not
// a 404 discovered in production later.

import { Marked } from "marked";
import { dirname, resolve, relative, extname, join, sep } from "node:path";
import { existsSync, statSync } from "node:fs";
import { IMAGE_EXT } from "./content.mjs";

const ALERT = /^(NOTE|TIP|IMPORTANT|WARNING|CAUTION)$/;

export function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function slug(text) {
  return String(text)
    .toLowerCase()
    .replace(/<[^>]*>/g, "")
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
}

function isExternal(href) {
  return (
    /^[a-z][a-z0-9+.-]*:/i.test(href) || href.startsWith("//") || href.startsWith("#")
  );
}

/**
 * Render one markdown document.
 *
 * @param {string} markdown        the document source
 * @param {object} opts
 * @param {string} opts.repoRoot   absolute path to the repo root
 * @param {string} opts.sourcePath absolute path of the document being rendered
 * @param {(absPath: string) => void} opts.onAsset   called for every local image
 * @param {(message: string) => void} opts.onError   called for every broken reference
 * @param {string} opts.githubBase blob base URL for files the site does not serve
 * @param {(absPath: string) => (string|null)} [opts.pageFor] map a repo file to a site URL
 * @param {boolean} [opts.dropFirstH1] omit the leading H1 (the shell renders it)
 * @returns {{html: string, headings: {depth: number, id: string, text: string}[]}}
 */
export function renderMarkdown(markdown, opts) {
  const {
    repoRoot,
    sourcePath,
    onAsset,
    onError,
    githubBase,
    pageFor = () => null,
    dropFirstH1 = false,
  } = opts;

  const baseDir = dirname(sourcePath);
  const headings = [];
  const seenIds = new Map();
  let h1Dropped = false;

  function uniqueId(base) {
    const id = base || "section";
    const n = seenIds.get(id) || 0;
    seenIds.set(id, n + 1);
    return n === 0 ? id : `${id}-${n}`;
  }

  // Resolve a local reference and decide what it should become.
  function resolveRef(href, kind) {
    if (!href) return href;
    if (isExternal(href)) return href;

    const hashAt = href.indexOf("#");
    const fragment = hashAt >= 0 ? href.slice(hashAt) : "";
    const pathPart = hashAt >= 0 ? href.slice(0, hashAt) : href;
    if (!pathPart) return href; // pure "#anchor"

    const target = resolve(baseDir, decodeURIComponent(pathPart));
    const rel = relative(repoRoot, target);
    if (rel.startsWith("..")) {
      onError(`${short(sourcePath)}: ${kind} escapes the repo: ${href}`);
      return href;
    }
    if (!existsSync(target)) {
      onError(`${short(sourcePath)}: ${kind} points at a missing file: ${href}`);
      return href;
    }

    const ext = extname(target).toLowerCase();

    if (IMAGE_EXT.has(ext)) {
      if (!statSync(target).isFile()) {
        onError(`${short(sourcePath)}: ${kind} is not a file: ${href}`);
        return href;
      }
      onAsset(target);
      // Mirrored output tree — the relative path already resolves.
      return href;
    }

    // A document the site itself publishes: link to the page, not the source.
    const page = pageFor(target);
    if (page) return page + fragment;

    // Everything else lives in the repo; send readers to the real thing.
    return `${githubBase}/${rel.split(sep).join("/")}${fragment}`;
  }

  function short(p) {
    return relative(repoRoot, p) || p;
  }

  const marked = new Marked({ gfm: true });

  marked.use({
    renderer: {
      heading(token) {
        const text = this.parser.parseInline(token.tokens);
        if (token.depth === 1 && dropFirstH1 && !h1Dropped) {
          h1Dropped = true;
          return "";
        }
        const id = uniqueId(slug(token.text));
        if (token.depth === 2 || token.depth === 3) {
          headings.push({ depth: token.depth, id, text: token.text });
        }
        return `<h${token.depth} id="${id}">${text}</h${token.depth}>\n`;
      },

      link(token) {
        const href = resolveRef(token.href, "link");
        const text = this.parser.parseInline(token.tokens);
        const title = token.title ? ` title="${escapeHtml(token.title)}"` : "";
        const external = isExternal(href) && !href.startsWith("#");
        const attrs = external ? ' rel="noopener noreferrer"' : "";
        return `<a href="${escapeHtml(href)}"${title}${attrs}>${text}</a>`;
      },

      image(token) {
        const src = resolveRef(token.href, "image");
        const title = token.title ? ` title="${escapeHtml(token.title)}"` : "";
        const alt = escapeHtml(token.text || "");
        return `<img src="${escapeHtml(src)}" alt="${alt}"${title} loading="lazy" decoding="async">`;
      },

      blockquote(token) {
        let inner = this.parser.parse(token.tokens);
        const m = inner.match(
          /^\s*<p>\s*\[!([A-Z]+)\]\s*(?:<br\s*\/?>)?\s*/
        );
        if (m && ALERT.test(m[1])) {
          const label = m[1];
          inner = inner.replace(m[0], "<p>");
          return (
            `<blockquote class="admonition">` +
            `<span class="admonition-label">${label}</span>${inner}</blockquote>\n`
          );
        }
        return `<blockquote>${inner}</blockquote>\n`;
      },

      // Wrapped so a wide parameter table scrolls inside its own box instead
      // of forcing the whole page to scroll sideways on a phone.
      table(token) {
        const align = (i) =>
          token.align && token.align[i] ? ` style="text-align:${token.align[i]}"` : "";
        const head = token.header
          .map((cell, i) => `<th${align(i)}>${this.parser.parseInline(cell.tokens)}</th>`)
          .join("");
        const body = token.rows
          .map(
            (row) =>
              `<tr>${row
                .map(
                  (cell, i) =>
                    `<td${align(i)}>${this.parser.parseInline(cell.tokens)}</td>`
                )
                .join("")}</tr>`
          )
          .join("\n");
        return (
          `<div class="table-scroll"><table>\n<thead><tr>${head}</tr></thead>\n` +
          `<tbody>\n${body}\n</tbody>\n</table></div>\n`
        );
      },
    },
  });

  const html = marked.parse(markdown);
  return { html, headings };
}

// The one-line pitches are markdown fragments lifted out of NOTES.md and
// README.md, so they carry emphasis and code spans. Escaping them wholesale
// puts literal ** on the page; parsing them as blocks wraps them in <p>.
const inline = new Marked({ gfm: true });

/** Render a markdown fragment as inline HTML (no block wrapper). */
export function inlineMarkdown(text) {
  return inline.parseInline(String(text || ""));
}

/**
 * Render a markdown fragment that is shown AWAY from its source file — a
 * charter excerpt on a PM's People-page card, a decision-log row on a design's
 * timeline. Same inline render as inlineMarkdown (emphasis, code spans), but
 * relative-href links are flattened to their text first: a charter's
 * `[x](../sibling/)` resolves against the charter's own directory, not the page
 * that aggregates it here, so left live it 404s (a PM card's parent-design
 * link did exactly that). Absolute (`http(s)://`) and site-rooted (`/…`) links
 * resolve the same everywhere, so they are kept.
 */
export function inlineExcerpt(text) {
  // Escape HTML FIRST so a stray tag can never survive as live markup — Marked
  // passes raw `<script>` through, so these aggregated surfaces keep their
  // injection guard only if nothing reaches the parser as HTML. escapeHtml
  // leaves markdown punctuation (* ` [ ] ( )) untouched, so emphasis, code
  // spans and the link flatten below still work on the escaped text.
  const escaped = escapeHtml(String(text || ""));
  const flattened = escaped.replace(
    /\[([^\]]*)\]\((?!https?:\/\/|\/)[^)]*\)/g,
    "$1",
  );
  return inlineMarkdown(flattened);
}

/** Same fragment with all markup removed — for <title>/<meta> attributes. */
export function plainText(text) {
  return String(text || "")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\*\*([^*]*)\*\*/g, "$1")
    .replace(/(^|[^*])\*([^*]+)\*/g, "$1$2")
    .replace(/_([^_]+)_/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");
}

/** Build a table-of-contents fragment from collected headings. */
export function tocHtml(headings) {
  const useful = headings.filter((h) => h.depth === 2);
  if (useful.length < 2) return "";
  const items = useful
    .map(
      (h) =>
        `<a class="toc-h${h.depth}" href="#${h.id}">${escapeHtml(h.text)}</a>`
    )
    .join("\n");
  return `<nav class="toc" aria-label="On this page">\n${items}\n</nav>`;
}

export { join };
