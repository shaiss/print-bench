// Content-Security-Policy, generated per page at build time.
//
// The site has exactly two kinds of inline script — the theme bootstrap every
// page carries in <head>, and the import maps that resolve `three` and
// `@dicebear/core` to their vendored builds — and nothing else that runs from
// markup: no inline event handlers, no javascript: URLs. So the policy can be
// strict without 'unsafe-inline': same-origin scripts, plus a 'sha256-…' source
// for each inline script the page actually serves.
//
// build.mjs applies it at write time, over each page's final HTML, so the hash
// list is a function of the bytes served and no later edit to a template can
// leave a page running a script its policy does not name — or naming one it no
// longer runs. checkCsp() is the same promise as a check: build.mjs fails a page
// it flags, and test/csp.test.mjs holds the whole built site to it.
//
// What is deliberately NOT restricted: default-src, style-src and font-src.
// The pages carry inline style attributes and the stylesheet loads its own
// fonts, and the Vercel Toolbar (previews only) injects styles of its own;
// those directives would buy little here and break real things. frame-ancestors
// cannot be set from a <meta> at all (browsers ignore it there), so it lives in
// vercel.json's site-wide header instead.

import { createHash } from "node:crypto";

// The JavaScript MIME type essences (WHATWG MIME Sniffing, "JavaScript MIME
// type"). A <script> whose type is one of these runs as a classic script.
const JS_MIME = new Set([
  "application/ecmascript",
  "application/javascript",
  "application/x-ecmascript",
  "application/x-javascript",
  "text/ecmascript",
  "text/javascript",
  "text/javascript1.0",
  "text/javascript1.1",
  "text/javascript1.2",
  "text/javascript1.3",
  "text/javascript1.4",
  "text/javascript1.5",
  "text/jscript",
  "text/livescript",
  "text/x-ecmascript",
  "text/x-javascript",
]);

// Non-classic script types the browser still treats as script, each held to
// script-src exactly like an inline classic script: an inline import map that
// is not hashed is refused, and every module import that needed it then fails.
const SCRIPT_TYPES = new Set(["module", "importmap", "speculationrules"]);

// The Vercel Toolbar's origins, from Vercel's published CSP list for it.
// Vercel injects the toolbar on preview deployments only, so only a preview
// build allows them; production, CI and local builds carry none.
const TOOLBAR = {
  "script-src": ["https://vercel.live"],
  "connect-src": ["https://vercel.live", "wss://ws-us3.pusher.com"],
  "img-src": ["https://vercel.live", "https://vercel.com"],
};

/** Whether this build should allow the Vercel Toolbar (preview deploys only). */
export function toolbarAllowed(env = process.env) {
  return env.VERCEL_ENV === "preview";
}

/**
 * Whether a <script type="…"> value runs. Absent or empty is classic script.
 * Deliberately conservative where the HTML spec is not: a JS MIME type with
 * parameters (`text/javascript; charset=utf-8`) is a data block to the
 * browser, but it is treated as executable here — hashing a script that never
 * runs costs one unused source, while missing one that does would ship a page
 * whose script is silently refused.
 */
export function isExecutableType(type) {
  if (type == null) return true;
  const t = type.trim().toLowerCase();
  if (t === "") return true;
  const essence = t.split(";")[0].trim();
  return JS_MIME.has(essence) || SCRIPT_TYPES.has(essence);
}

// A start tag (quote-aware, so a `>` inside an attribute value does not end
// it), an end tag, or a comment. The alternatives inside a tag are disjoint on
// their first character, so a malformed tag cannot trigger catastrophic
// backtracking.
const TOKEN = /<!--[\s\S]*?(?:-->|$)|<\/[a-zA-Z][^>]*>|<([a-zA-Z][^\s/>]*)((?:[^>"']|"[^"]*"|'[^']*')*)>/g;
const ATTR = /([^\s"'>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;

// Elements whose content is raw text (or escapable raw text): markup inside
// them is not markup, so a `<script>` written in a <title> or a <textarea> is
// text and must not be mistaken for a script.
const RAW_TEXT = new Set(["script", "style", "textarea", "title"]);

function parseAttrs(source) {
  const attrs = new Map();
  for (const m of source.matchAll(ATTR)) {
    const name = m[1].toLowerCase();
    // The first occurrence wins, as it does in the browser's tokenizer.
    if (!attrs.has(name)) attrs.set(name, m[2] ?? m[3] ?? m[4] ?? "");
  }
  return attrs;
}

/**
 * Tokenise a page the way the browser's tokenizer would for the parts a CSP
 * cares about: every start tag outside comments and raw text, and every
 * <script> with its raw body. Not a general HTML parser — just enough that a
 * commented-out script is not counted and a script's body ends where the
 * browser ends it (the first `</script` followed by whitespace, `/` or `>`).
 */
export function scanHtml(html) {
  const tags = [];
  const scripts = [];
  TOKEN.lastIndex = 0;
  let m;
  while ((m = TOKEN.exec(html))) {
    if (!m[1]) continue; // a comment or an end tag
    const name = m[1].toLowerCase();
    const attrs = parseAttrs(m[2]);
    tags.push({ name, attrs, index: m.index });
    if (!RAW_TEXT.has(name)) continue;
    const close = new RegExp(`</${name}[\\s/>]`, "gi");
    close.lastIndex = TOKEN.lastIndex;
    const end = close.exec(html);
    const bodyEnd = end ? end.index : html.length;
    if (name === "script") {
      const type = attrs.has("type") ? attrs.get("type") : null;
      scripts.push({
        index: m.index,
        attrs,
        type,
        inline: !attrs.has("src"),
        executable: isExecutableType(type),
        body: html.slice(TOKEN.lastIndex, bodyEnd),
      });
    }
    const gt = end ? html.indexOf(">", end.index) : -1;
    TOKEN.lastIndex = gt < 0 ? html.length : gt + 1;
  }
  return { tags, scripts };
}

// The named character references that decode to something a URL scheme check
// can see: the ':' that ends a scheme, and the tab and newline the URL parser
// drops from anywhere in a URL. No named reference decodes to an ASCII letter,
// so these are the only ones that can disguise a `javascript:`. All three need
// their semicolon (none is a legacy reference) and are case-sensitive:
// `&Colon;` is U+2237.
const NAMED_REFS = { colon: ":", Tab: "\t", NewLine: "\n" };
const CHAR_REF = /&#(?:[xX]([0-9a-fA-F]+)|([0-9]+));?|&(colon|Tab|NewLine);/g;

/**
 * An attribute value with its character references decoded the way the
 * browser's tokenizer decodes them, as far as a URL scheme check needs:
 * numeric references (decimal or hex, digits consumed greedily, semicolon
 * optional) and NAMED_REFS. A reference to NUL, a surrogate or past U+10FFFF
 * becomes U+FFFD, as in the browser. The C1 remap (&#x80;–&#x9F; to
 * windows-1252) is skipped: neither side of it is ASCII, so it cannot make or
 * break a scheme.
 */
export function decodeCharRefs(value) {
  return value.replace(CHAR_REF, (ref, hex, dec, name) => {
    if (name) return NAMED_REFS[name];
    const cp = hex ? parseInt(hex, 16) : parseInt(dec, 10);
    if (!(cp > 0 && cp <= 0x10ffff) || (cp >= 0xd800 && cp <= 0xdfff)) return "�";
    return String.fromCodePoint(cp);
  });
}

/**
 * Whether an attribute value is a javascript: URL to the browser: references
 * decoded, then what the URL parser strips before it reads a scheme — every
 * ASCII tab or newline, and leading C0 controls and spaces. Leading whitespace
 * in the wider \s sense is stripped too, which the parser does not do; that
 * can only flag more.
 */
export function isJavascriptUrl(value) {
  const url = decodeCharRefs(value).replace(/[\t\n\r]/g, "").replace(/^[\s\x00-\x1f]+/, "");
  return /^javascript:/i.test(url);
}

/** The scripts a policy has to name: inline and executable. */
function hashableScripts(scripts) {
  return scripts.filter((s) => s.inline && s.executable);
}

/**
 * The CSP hash source for an inline script's text. The browser hashes the
 * element's text after input-stream preprocessing, which turns CRLF and a lone
 * CR into LF, so the same normalisation is applied before hashing.
 */
export function scriptHash(text) {
  const normalised = text.replace(/\r\n?/g, "\n");
  return `'sha256-${createHash("sha256").update(normalised, "utf8").digest("base64")}'`;
}

/** The policy string for one page, given its inline-script hash sources. */
export function cspPolicy({ hashes = [], preview = false } = {}) {
  const directives = [
    ["script-src", ["'self'", "'wasm-unsafe-eval'", ...hashes]],
    // The configurator and viewer render in a same-origin module worker.
    ["worker-src", ["'self'", "blob:"]],
    ["object-src", ["'none'"]],
    ["base-uri", ["'self'"]],
    // data: carries a visitor's re-rolled avatar (an inline SVG data URL).
    ["img-src", ["'self'", "data:", "blob:"]],
    ["connect-src", ["'self'"]],
  ];
  return directives
    .map(([name, sources]) =>
      [name, ...sources, ...(preview ? TOOLBAR[name] || [] : [])].join(" ")
    )
    .join("; ");
}

const META_RE = /^content-security-policy$/i;

function cspMetas(tags) {
  return tags.filter((t) => t.name === "meta" && META_RE.test(t.attrs.get("http-equiv") || ""));
}

/** A policy string → Map of directive name → its source list. */
export function parsePolicy(policy) {
  const directives = new Map();
  for (const part of policy.split(";")) {
    const [name, ...sources] = part.trim().split(/\s+/);
    if (name && !directives.has(name.toLowerCase())) directives.set(name.toLowerCase(), sources);
  }
  return directives;
}

/**
 * Insert the page's policy as the first child of <head>, ahead of any script
 * it governs (a <meta> policy applies only to what comes after it). Throws on
 * a page with no <head>, a script ahead of it, or a policy already present —
 * a page that cannot carry its policy correctly must not ship without one.
 */
export function applyCsp(html, { preview = false } = {}) {
  const head = /<head(?:\s[^>]*)?>/i.exec(html);
  if (!head) throw new Error("page has no <head> to carry its Content-Security-Policy");
  const { tags, scripts } = scanHtml(html);
  if (cspMetas(tags).length) throw new Error("page already carries a Content-Security-Policy meta");
  if (scripts.some((s) => s.index < head.index)) {
    throw new Error("a <script> precedes <head>, where no <meta> policy can cover it");
  }
  const hashes = [...new Set(hashableScripts(scripts).map((s) => scriptHash(s.body)))];
  const at = head.index + head[0].length;
  const meta = `<meta http-equiv="Content-Security-Policy" content="${cspPolicy({ hashes, preview })}">`;
  return `${html.slice(0, at)}\n${meta}${html.slice(at)}`;
}

/**
 * Everything that would make a page's policy wrong in a browser, as a list of
 * problems (empty = sound): not exactly one CSP <meta>; that meta not the first
 * element in <head>, or behind a script; an inline executable script whose
 * hash script-src does not name; a weakening source ('unsafe-inline',
 * 'unsafe-eval', 'unsafe-hashes'); and markup no hash can ever allow — an
 * inline event handler attribute or a javascript: URL.
 */
export function checkCsp(html) {
  const problems = [];
  const { tags, scripts } = scanHtml(html);
  const metas = cspMetas(tags);
  if (metas.length !== 1) {
    problems.push(`expected exactly one Content-Security-Policy meta, found ${metas.length}`);
  }
  const meta = metas[0];
  if (meta) {
    const headAt = tags.findIndex((t) => t.name === "head");
    if (headAt < 0 || tags[headAt + 1] !== meta) {
      problems.push("the Content-Security-Policy meta is not the first element in <head>");
    }
    if (scripts.length && scripts[0].index < meta.index) {
      problems.push("a <script> precedes the Content-Security-Policy meta");
    }
    const scriptSrc = parsePolicy(meta.attrs.get("content") || "").get("script-src") || [];
    for (const weak of ["'unsafe-inline'", "'unsafe-eval'", "'unsafe-hashes'"]) {
      if (scriptSrc.includes(weak)) problems.push(`script-src allows ${weak}`);
    }
    const allowed = new Set(scriptSrc);
    for (const s of hashableScripts(scripts)) {
      if (!allowed.has(scriptHash(s.body))) {
        const preview = s.body.trim().slice(0, 60).replace(/\s+/g, " ");
        problems.push(`inline script not hashed in script-src: ${preview}`);
      }
    }
  }
  for (const t of tags) {
    for (const [name, value] of t.attrs) {
      if (/^on/.test(name)) problems.push(`inline event handler ${name}= on <${t.name}>`);
      if (["href", "src", "action", "formaction"].includes(name) && isJavascriptUrl(value)) {
        problems.push(`javascript: URL in ${name}= on <${t.name}>`);
      }
    }
  }
  return problems;
}
