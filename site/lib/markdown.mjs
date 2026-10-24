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

/** Longest excerpt rendered in full (UTF-16 units); longer input is cut and gets "…". */
export const EXCERPT_MAX_CHARS = 64 * 1024;

/**
 * Render a markdown fragment that is shown AWAY from its source file — a
 * charter excerpt on a PM's People-page card, a decision-log row or a commit
 * subject on a design's timeline. Inline only: code spans, **strong**,
 * *emphasis* / _emphasis_, and `[text](href)` links, with the link rule that
 * makes an excerpt safe to aggregate: a link stays live ONLY when its href is
 * `http://…`, `https://…` or site-rooted `/…` (never `//host` or `/\host`,
 * which browsers read as another origin). Every other link — relative (a
 * charter's `[x](../sibling/)` resolves against the charter's own directory,
 * not the page that aggregates it, so left live it 404s; a PM card's
 * parent-design link did exactly that), `#anchor`, and any other scheme
 * (`javascript:`, `data:`, `mailto:`, mixed-case or obfuscated) — flattens to
 * its text, and an image renders as its alt text, never an `<img>`.
 *
 * Why not Marked, which inlineMarkdown uses: on these surfaces the input is
 * aggregated text, so the renderer is the injection boundary. Marked's link
 * grammar is wider than any flatten regex run in front of it (a nested label,
 * `[[x]](javascript:…)`, or an escaped bracket, `[a\]b](javascript:…)`, slipped
 * past one and came out a live `javascript:` href), it emits external `<img>`
 * for images, and its inline lexer is super-linear on crafted input (`[x](`
 * repeated to 4,000 chars took ~4 s). So this is a single pass over the text,
 * linear in its length, whose only markup is `<code>`, `<strong>`, `<em>`
 * and a kept `<a href>`.
 *
 * The input is HTML-escaped FIRST (escapeHtml leaves markdown punctuation
 * alone), so a stray tag can never survive as live markup and every text,
 * code-span and href byte this emits is already entity-safe; nothing is
 * escaped twice (a code span shows `<name>`, not `&lt;name&gt;`). Emphasis
 * follows the CommonMark delimiter rules, which is what Marked produced for
 * every committed excerpt; GFM strikethrough is deliberately not rendered —
 * here a `~` means "approximately", and Marked's single-tilde rule struck
 * through a decision-log row between two `~` measurements. Input longer than
 * EXCERPT_MAX_CHARS is cut there and ends in "…" — a backstop, not a layout
 * rule. test/markdown.test.mjs pins the parity with the old Marked render on
 * the whole committed corpus, every injection vector, and the time bound.
 */
export function inlineExcerpt(text) {
  let src = String(text || "");
  let cut = false;
  if (src.length > EXCERPT_MAX_CHARS) {
    let end = EXCERPT_MAX_CHARS;
    const last = src.charCodeAt(end - 1);
    if (last >= 0xd800 && last <= 0xdbff) end--; // never split a surrogate pair
    src = src.slice(0, end);
    cut = true;
  }
  return renderExcerpt(escapeHtml(src)) + (cut ? "…" : "");
}

// ---------------------------------------------------------------------------
// The excerpt renderer: a CommonMark-style inline parser (the commonmark.js
// shape — a node tree, a delimiter stack for emphasis, a bracket stack for
// links) cut down to the constructs above, over the ALREADY-ESCAPED text.
// Linear by construction: every lookahead a backtracking lexer would rescan
// is precomputed once (matching parens, next ")", backtick runs by length),
// and the emphasis pass bounds its opener search the way the spec's
// "process emphasis" does (openers_bottom), so no input position is revisited
// more than a constant number of times.
// ---------------------------------------------------------------------------

const ASCII_PUNCT = /[!-/:-@[-`{-~]/; // CommonMark's backslash-escapable set
const PUNCT = /[\p{P}\p{S}]/u;
const SPACE = /\s/u;
// A char that ends a plain-text run: everything else is copied verbatim.
const SPECIAL = new Set(["\\", "`", "*", "_", "[", "]", "!"]);

function excerptNode(type, text = "") {
  return { type, text, href: null, parent: null, prev: null, next: null, first: null, last: null };
}

function appendChild(parent, child) {
  child.parent = parent;
  child.prev = parent.last;
  child.next = null;
  if (parent.last) parent.last.next = child;
  else parent.first = child;
  parent.last = child;
}

function insertAfter(ref, child) {
  child.parent = ref.parent;
  child.prev = ref;
  child.next = ref.next;
  if (ref.next) ref.next.prev = child;
  else ref.parent.last = child;
  ref.next = child;
}

function unlink(n) {
  if (n.prev) n.prev.next = n.next;
  else if (n.parent) n.parent.first = n.next;
  if (n.next) n.next.prev = n.prev;
  else if (n.parent) n.parent.last = n.prev;
  n.parent = n.prev = n.next = null;
}

/** Move every sibling after `from` (up to, not including, `stop`) into `into`. */
function adoptSiblings(from, stop, into) {
  let n = from.next;
  while (n && n !== stop) {
    const next = n.next;
    unlink(n);
    appendChild(into, n);
    n = next;
  }
}

/** The code point ending just before index i ("" at the start). */
function charBefore(s, i) {
  if (i <= 0) return "";
  const lo = s.charCodeAt(i - 1);
  if (lo >= 0xdc00 && lo <= 0xdfff && i >= 2) {
    const hi = s.charCodeAt(i - 2);
    if (hi >= 0xd800 && hi <= 0xdbff) return s.slice(i - 2, i);
  }
  return s[i - 1];
}

/** The code point starting at index i ("" at the end). */
function charAt(s, i) {
  return i < s.length ? String.fromCodePoint(s.codePointAt(i)) : "";
}

/** A dest char that ends a whitespace-free link destination. */
function breaksDest(s, i) {
  const c = s.charCodeAt(i);
  return c <= 0x20 || c === 0x7f || (c >= 0x80 && SPACE.test(s[i]));
}

const KEPT = /^(?:https?:\/\/|\/(?![/\\]))/;

/**
 * The href a kept link carries, or null when the link must flatten. The kept
 * prefix must be literal both in the source and in the href that ships (after
 * backslash-unescaping), so what is checked is what is emitted and an escaped
 * prefix (`https:\/\/…`, `/\/evil`) flattens as the old rule did. It is
 * matched on the escaped text, so an entity-spelled scheme (`&#106;avascript:`)
 * arrives as `&amp;#106;…` and matches nothing; and case-sensitively, like the
 * old rule: `HTTPS:` flattens. The value goes out the way Marked's renderer
 * sent it (encodeURI, existing %-escapes kept), then any quote or angle
 * bracket is entity-encoded — none can be present, so that is the guard
 * that keeps it true.
 */
function keptHref(dest) {
  const href = dest.replace(/\\([!-/:-@[-`{-~])/g, "$1");
  if (!KEPT.test(dest) || !KEPT.test(href)) return null;
  let encoded;
  try {
    encoded = encodeURI(href).replace(/%25/g, "%");
  } catch {
    return null; // a lone surrogate: Marked dropped the link too
  }
  return encoded
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderExcerpt(s) {
  const n = s.length;

  // Precompute 1 — the ")" matching each "(" inside a whitespace-free stretch
  // (backslash-escaped parens don't count), and where the destination of an
  // inline link opening at that "(" ends: at the ")" itself, or — CommonMark
  // lets whitespace sit before the ")" — where that whitespace starts. Only
  // the innermost open paren can end at whitespace (an outer one's
  // destination would hold an unbalanced "("). So `](` never rescans.
  const closeParen = new Int32Array(n).fill(-1);
  const destEnd = new Int32Array(n).fill(-1);
  const stack = new Int32Array(n);
  let sp = 0;
  for (let i = 0; i < n; i++) {
    if (s[i] === "\\" && i + 1 < n && ASCII_PUNCT.test(s[i + 1])) {
      i++;
      continue;
    }
    if (breaksDest(s, i)) {
      let j = i + 1;
      while (j < n && breaksDest(s, j)) j++;
      if (sp > 0 && s[j] === ")") {
        closeParen[stack[sp - 1]] = j;
        destEnd[stack[sp - 1]] = i;
        i = j; // that ")" is spent
      } else {
        i = j - 1;
      }
      sp = 0;
    } else if (s[i] === "(") stack[sp++] = i;
    else if (s[i] === ")" && sp > 0) {
      const open = stack[--sp];
      closeParen[open] = destEnd[open] = i;
    }
  }
  // Precompute 2 — the first ")" at or after each index: the old flatten
  // rule's `[^)]*\)` reach, kept so a malformed non-kept link (spaces in its
  // destination, an unbalanced paren) still flattens rather than showing its
  // markup.
  const nextClose = new Int32Array(n + 1).fill(-1);
  for (let i = n - 1; i >= 0; i--) nextClose[i] = s[i] === ")" ? i : nextClose[i + 1];
  // Precompute 3 — every maximal backtick run, by length: a code span closes
  // at the next run of exactly its opener's length, found by a per-length
  // cursor that only moves forward.
  const runsByLen = new Map();
  for (let i = 0; i < n; ) {
    if (s[i] !== "`") {
      i++;
      continue;
    }
    let j = i;
    while (j < n && s[j] === "`") j++;
    if (!runsByLen.has(j - i)) runsByLen.set(j - i, { at: [], cursor: 0 });
    runsByLen.get(j - i).at.push(i);
    i = j;
  }
  function codeCloser(len, from) {
    const runs = runsByLen.get(len);
    if (!runs) return -1;
    while (runs.cursor < runs.at.length && runs.at[runs.cursor] < from) runs.cursor++;
    return runs.cursor < runs.at.length ? runs.at[runs.cursor] : -1;
  }

  const root = excerptNode("root");
  let delims = null; // top of the emphasis delimiter stack
  let brackets = null; // top of the link/image opener stack
  // Links never nest: forming one deactivates every non-image opener before
  // it. Recorded as a position rather than by walking the stack (a run of
  // unclosed `[` followed by many links would make that walk quadratic): an
  // opener at or before the latest formed link's opener is inactive.
  let linkBarrier = -1;

  function text(str) {
    const t = excerptNode("text", str);
    appendChild(root, t);
    return t;
  }

  function removeDelim(d) {
    if (d.prev) d.prev.next = d.next;
    if (d.next) d.next.prev = d.prev;
    else delims = d.prev; // the top of the stack
  }

  // The CommonMark "process emphasis" pass over the delimiters above
  // `bottom`, with openers_bottom so each closer's backward opener search
  // never re-walks a span it already failed over.
  function processEmphasis(bottom) {
    if (delims === bottom) return; // nothing above it — and no walk below it
    const openersBottom = new Array(12).fill(bottom);
    let closer = delims;
    while (closer.prev !== bottom) closer = closer.prev;
    while (closer) {
      if (!closer.canClose) {
        closer = closer.next;
        continue;
      }
      const slot = (closer.cc === "*" ? 6 : 0) + (closer.canOpen ? 3 : 0) + (closer.orig % 3);
      let opener = closer.prev;
      let found = false;
      while (opener && opener !== bottom && opener !== openersBottom[slot]) {
        // The rule of 3: a run that can both open and close never pairs into
        // a multiple of 3 unless both runs are.
        const odd =
          (closer.canOpen || opener.canClose) &&
          closer.orig % 3 !== 0 &&
          (opener.orig + closer.orig) % 3 === 0;
        if (opener.cc === closer.cc && opener.canOpen && !odd) {
          found = true;
          break;
        }
        opener = opener.prev;
      }
      if (!found) {
        openersBottom[slot] = closer.prev;
        const next = closer.next;
        if (!closer.canOpen) removeDelim(closer);
        closer = next;
        continue;
      }
      const use = closer.count >= 2 && opener.count >= 2 ? 2 : 1;
      opener.count -= use;
      closer.count -= use;
      opener.node.text = opener.node.text.slice(0, opener.count);
      closer.node.text = closer.node.text.slice(0, closer.count);
      const emph = excerptNode(use === 1 ? "em" : "strong");
      adoptSiblings(opener.node, closer.node, emph);
      insertAfter(opener.node, emph);
      opener.next = closer; // the delimiters in between are now literal text
      closer.prev = opener;
      if (opener.count === 0) {
        unlink(opener.node);
        removeDelim(opener);
      }
      if (closer.count === 0) {
        const next = closer.next;
        unlink(closer.node);
        removeDelim(closer);
        closer = next;
      }
    }
    while (delims && delims !== bottom) removeDelim(delims);
  }

  let i = 0;
  while (i < n) {
    const c = s[i];
    if (c === "\\") {
      // A backslash before ASCII punctuation makes it literal. Before an
      // entity escapeHtml wrote (`\"` arrives as `\&quot;`) that leaves the
      // entity whole, so it shows the quote rather than `&quot;`.
      if (i + 1 < n && ASCII_PUNCT.test(s[i + 1])) {
        text(s[i + 1]);
        i += 2;
      } else {
        text("\\");
        i++;
      }
    } else if (c === "`") {
      let j = i;
      while (j < n && s[j] === "`") j++;
      const close = codeCloser(j - i, j);
      if (close < 0) {
        text(s.slice(i, j)); // no closing run of this length: literal
        i = j;
        continue;
      }
      // CommonMark/Marked normalisation: newlines read as spaces, and one
      // space is stripped from each end when both ends have one.
      let code = s.slice(j, close).replace(/\n/g, " ");
      if (/[^ ]/.test(code) && code[0] === " " && code[code.length - 1] === " ") {
        code = code.slice(1, -1);
      }
      appendChild(root, excerptNode("code", code));
      i = close + (j - i);
    } else if (c === "*" || c === "_") {
      let j = i;
      while (j < n && s[j] === c) j++;
      // Flanking, per the CommonMark rules; the text edges count as space.
      const before = charBefore(s, i);
      const after = charAt(s, j);
      const beforeSpace = before === "" || SPACE.test(before);
      const afterSpace = after === "" || SPACE.test(after);
      const beforePunct = PUNCT.test(before);
      const afterPunct = PUNCT.test(after);
      const left = !afterSpace && (!afterPunct || beforeSpace || beforePunct);
      const right = !beforeSpace && (!beforePunct || afterSpace || afterPunct);
      const canOpen = c === "*" ? left : left && (!right || beforePunct);
      const canClose = c === "*" ? right : right && (!left || afterPunct);
      const node = text(s.slice(i, j));
      if (canOpen || canClose) {
        const d = { cc: c, count: j - i, orig: j - i, node, canOpen, canClose, prev: delims, next: null };
        if (delims) delims.next = d;
        delims = d;
      }
      i = j;
    } else if (c === "[" || (c === "!" && s[i + 1] === "[")) {
      const image = c === "!";
      brackets = { node: text(image ? "![" : "["), image, at: i, delims, prev: brackets };
      i += image ? 2 : 1;
    } else if (c === "]") {
      const opener = brackets;
      if (!opener || (!opener.image && opener.at <= linkBarrier)) {
        if (opener) brackets = opener.prev; // an inactive opener is spent
        text("]");
        i++;
        continue;
      }
      // An inline link: "](" then a balanced, whitespace-free destination
      // and ")" — or, for the old flatten rule's reach, anything up to the
      // next ")" (never live). No ")" at all: not a link, the "]" is text.
      let end = -1;
      let dest = null;
      if (s[i + 1] === "(") {
        if (closeParen[i + 1] >= 0) {
          end = closeParen[i + 1];
          dest = s.slice(i + 2, destEnd[i + 1]);
        } else {
          end = nextClose[i + 2] ?? -1;
        }
      }
      brackets = opener.prev;
      if (end < 0) {
        text("]");
        i++;
        continue;
      }
      const link = excerptNode(opener.image ? "image" : "link");
      if (!opener.image && dest !== null) link.href = keptHref(dest);
      adoptSiblings(opener.node, null, link);
      appendChild(root, link);
      processEmphasis(opener.delims);
      unlink(opener.node);
      if (!opener.image) linkBarrier = opener.at;
      i = end + 1;
    } else {
      let j = i + 1;
      while (j < n && !SPECIAL.has(s[j])) j++;
      text(s.slice(i, j));
      i = j;
    }
  }
  processEmphasis(null);

  // Render without recursion — nesting depth is input-controlled. Inside an
  // image (`plain` > 0) only text comes out: an image is its alt text.
  let out = "";
  let plain = 0;
  const open = (node) => {
    if (node.type === "image") plain++;
    else if (!plain) {
      if (node.type === "link") out += node.href ? `<a href="${node.href}">` : "";
      else out += `<${node.type}>`;
    }
  };
  const close = (node) => {
    if (node.type === "image") plain--;
    else if (!plain) {
      if (node.type === "link") out += node.href ? "</a>" : "";
      else out += `</${node.type}>`;
    }
  };
  let cur = root.first;
  while (cur) {
    if (cur.type === "text") out += cur.text;
    else if (cur.type === "code") out += plain ? cur.text : `<code>${cur.text}</code>`;
    else {
      open(cur);
      if (cur.first) {
        cur = cur.first;
        continue;
      }
      close(cur);
    }
    while (!cur.next) {
      cur = cur.parent;
      if (cur === root) return out;
      close(cur);
    }
    cur = cur.next;
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
