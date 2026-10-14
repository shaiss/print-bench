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
 * Href allowed to stay live on an aggregated excerpt surface.
 * http(s) absolutes and site-rooted paths (`/…`) resolve the same on every
 * page; everything else (relative, `//…`, `javascript:`, `data:`, …) does not.
 */
function isExcerptSafeHref(href) {
  if (!href || /[\0-\x1F\x7F\s]/.test(href)) return false;
  if (href.startsWith("/") && !href.startsWith("//")) return true;
  return /^https?:\/\//i.test(href);
}

/**
 * Parse `[text](href)` starting at `openBracket` (index of `[`).
 * The closing `]` is the one followed by `(` (so `[[x]](…)` is text=`[x]`,
 * matching CommonMark/Marked — the shape D1's javascript: payload uses).
 * Href parentheses are balanced so `http://example.com/foo_(bar)` works.
 * Returns null when the shape is incomplete. Linear in the span it covers.
 */
function parseBracketLink(src, openBracket) {
  if (src[openBracket] !== "[") return null;
  let search = openBracket + 1;
  let closeBracket = -1;
  while (search < src.length) {
    const q = src.indexOf("]", search);
    if (q < 0) return null;
    if (src[q + 1] === "(") {
      closeBracket = q;
      break;
    }
    search = q + 1;
  }
  if (closeBracket < 0) return null;
  let j = closeBracket + 2;
  let depth = 1;
  while (j < src.length && depth > 0) {
    const ch = src[j];
    if (ch === "\n" || ch === "\r") return null;
    if (ch === "(") depth += 1;
    else if (ch === ")") depth -= 1;
    j += 1;
  }
  if (depth !== 0) return null;
  return {
    text: src.slice(openBracket + 1, closeBracket),
    href: src.slice(closeBracket + 2, j - 1),
    end: j,
  };
}

/**
 * Linear-time safe inline renderer for excerpts shown away from their source
 * file (People-page charter cards, design timeline rows).
 *
 * Deliberately does NOT call Marked: its emphasis tokenizer is recursive and
 * stack-overflows / goes super-linear on crafted `*` runs (audit finding D1).
 * This scanner advances through the input once, emits only escaped text plus a
 * closed set of inline tags, never writes `javascript:` (or other non-http(s))
 * hrefs, and never emits `<img>` (aggregated surfaces have no asset pipeline).
 *
 * Kept live: absolute `http(s)://` and site-rooted `/…` links. Flattened to
 * their text: relative hrefs (a charter's `[x](../sibling/)` would 404 against
 * the aggregating page), protocol-relative `//…`, and every other scheme.
 */
export function inlineExcerpt(text) {
  return renderExcerpt(String(text || ""));
}

function renderExcerpt(src) {
  let out = "";
  let i = 0;
  const n = src.length;
  // Once a delimiter's closer is known absent from the remainder, skip
  // re-scanning for it — keeps adversarial runs of `[` / `*` / `` ` `` at O(n).
  let linksPossible = true;
  let strongPossible = true;
  let emPossible = true;
  let codePossible = true;

  while (i < n) {
    const c = src[i];

    // Image ![alt](href) — never <img>; render the alt as inline text.
    if (c === "!" && linksPossible && src[i + 1] === "[") {
      const parsed = parseBracketLink(src, i + 1);
      if (parsed) {
        out += renderExcerpt(parsed.text);
        i = parsed.end;
        continue;
      }
    }

    // Link [text](href)
    if (c === "[" && linksPossible) {
      if (src.indexOf("](", i + 1) < 0) {
        linksPossible = false;
      } else {
        const parsed = parseBracketLink(src, i);
        if (parsed) {
          const href = parsed.href.trim();
          const body = renderExcerpt(parsed.text);
          if (isExcerptSafeHref(href)) {
            out += `<a href="${escapeHtml(href)}" rel="noopener noreferrer">${body}</a>`;
          } else {
            out += body;
          }
          i = parsed.end;
          continue;
        }
      }
    }

    // Code span `...` (no newlines; empty span is not a match)
    if (c === "`" && codePossible) {
      const close = src.indexOf("`", i + 1);
      if (close < 0) {
        codePossible = false;
      } else if (close > i + 1 && !src.slice(i + 1, close).includes("\n")) {
        out += `<code>${escapeHtml(src.slice(i + 1, close))}</code>`;
        i = close + 1;
        continue;
      }
    }

    // Strong **...** — walk closers forward; one failing scan clears the flag.
    if (c === "*" && strongPossible && src[i + 1] === "*") {
      let from = i + 2;
      let matched = false;
      for (;;) {
        const close = src.indexOf("**", from);
        if (close < 0) {
          strongPossible = false;
          break;
        }
        if (close > i + 2) {
          const inner = src.slice(i + 2, close);
          if (!inner.includes("\n")) {
            out += `<strong>${renderExcerpt(inner)}</strong>`;
            i = close + 2;
            matched = true;
            break;
          }
        }
        from = close + 2;
      }
      if (matched) continue;
    }

    // Emphasis *...* (single asterisks; content has no `*`)
    if (c === "*" && emPossible) {
      const close = src.indexOf("*", i + 1);
      if (close < 0) {
        emPossible = false;
      } else if (close > i + 1) {
        const inner = src.slice(i + 1, close);
        if (!inner.includes("\n") && !inner.includes("*")) {
          out += `<em>${renderExcerpt(inner)}</em>`;
          i = close + 1;
          continue;
        }
      }
    }

    // Underscore emphasis _..._
    if (c === "_") {
      const close = src.indexOf("_", i + 1);
      if (close > i + 1) {
        const inner = src.slice(i + 1, close);
        if (!inner.includes("\n") && !inner.includes("_")) {
          out += `<em>${renderExcerpt(inner)}</em>`;
          i = close + 1;
          continue;
        }
      }
    }

    out += escapeHtml(c);
    i += 1;
  }
  return out;
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
