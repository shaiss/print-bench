// The Content-Security-Policy (lib/csp.mjs), held to what it promises: every
// page the build writes carries exactly one policy, as the first element of
// <head>, naming the hash of every inline script that page actually serves —
// and nothing a hash cannot allow (an inline handler, a javascript: URL) ships
// at all. A wrong hash is invisible to every other check here: the page
// renders, and the browser silently refuses the script.
//
// The built-site checks run the real build into a temp dir (offline — the
// Vercel-scoped fetches are keyed on VERCEL, which is stripped) and re-derive
// each page's hashes with their own extraction, independent of the lib's
// tokenizer, so a tokenizer bug cannot vouch for itself. The browser half (the
// configurator, viewer, avatar studio and theme toggle running under the
// policy) cannot run here; the site README records how it was proven.

import { test, after } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtempSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { join, relative } from "node:path";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import {
  applyCsp,
  checkCsp,
  cspPolicy,
  isExecutableType,
  parsePolicy,
  scanHtml,
  scriptHash,
  toolbarAllowed,
} from "../lib/csp.mjs";

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));
const SITE_DIR = fileURLToPath(new URL("..", import.meta.url));

const TOOLBAR_ORIGINS = ["https://vercel.live", "https://vercel.com", "wss://ws-us3.pusher.com"];

/** Build the site into a temp dir under a controlled environment. */
function build(extraEnv = {}) {
  const env = { ...process.env, ...extraEnv };
  // Offline and deterministic: every deploy-time fetch keys on VERCEL (or an
  // explicit SITE_FETCH_*), and the toolbar sources key on VERCEL_ENV.
  for (const k of ["VERCEL", "SITE_FETCH_RELEASES", "SITE_FETCH_HISTORY", "SITE_FETCH_DECISIONS"]) {
    delete env[k];
  }
  if (!("VERCEL_ENV" in extraEnv)) delete env.VERCEL_ENV;
  const out = mkdtempSync(join(tmpdir(), "print-bench-csp-"));
  const res = spawnSync("node", [join(SITE_DIR, "build.mjs"), "--out", out], { encoding: "utf8", env });
  assert.equal(res.status, 0, `build.mjs failed: ${res.stderr || res.stdout}`);
  return out;
}

function htmlFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory()
      ? htmlFiles(join(dir, e.name))
      : e.name.endsWith(".html")
        ? [join(dir, e.name)]
        : []
  );
}

// One default build shared by the tests that read it (each build is a second
// or so; the preview build is its own, since VERCEL_ENV changes its output).
let defaultOut = null;
function defaultBuild() {
  if (!defaultOut) defaultOut = build();
  return defaultOut;
}
after(() => {
  if (defaultOut) rmSync(defaultOut, { recursive: true, force: true });
});

const META = /<meta http-equiv="Content-Security-Policy" content="([^"]*)">/g;

/**
 * The independent re-derivation: inline <script> bodies by a plain regex (no
 * comment handling — the built site has no commented-out scripts, which the
 * lib-side tokenizer tests cover), data blocks skipped, hashed with node's
 * crypto directly. Deliberately not lib/csp.mjs's scanner.
 */
function independentHashes(html) {
  const hashes = [];
  // Index-based on purpose (not a tag regex): an end tag is "</script"
  // followed by anything up to the next ">", so "</script >" and
  // "</SCRIPT\n>" close a script exactly as the browser closes it.
  const lower = html.toLowerCase();
  let at = 0;
  for (;;) {
    const open = lower.indexOf("<script", at);
    if (open < 0) break;
    const after = lower[open + 7];
    if (after !== ">" && !/\s/.test(after || "")) {
      at = open + 7;
      continue;
    }
    const tagEnd = html.indexOf(">", open);
    const close = lower.indexOf("</script", tagEnd);
    if (tagEnd < 0 || close < 0) break;
    const attrs = html.slice(open + 7, tagEnd);
    const body = html.slice(tagEnd + 1, close);
    at = html.indexOf(">", close) + 1 || html.length;
    if (/\ssrc=/.test(attrs)) continue;
    const type = (attrs.match(/\stype="([^"]*)"/) || [, ""])[1].toLowerCase();
    if (type && !["module", "importmap", "text/javascript"].includes(type)) continue;
    hashes.push(`'sha256-${createHash("sha256").update(body).digest("base64")}'`);
  }
  return hashes;
}

/** Shared assertions over one built tree. */
function assertTree(out, { preview }) {
  const files = htmlFiles(out);
  assert.ok(files.length > 10, `expected a full site, found ${files.length} pages`);
  let scripted = 0;
  for (const file of files) {
    const rel = relative(out, file);
    const html = readFileSync(file, "utf8");
    assert.deepEqual(checkCsp(html), [], `${rel}: checkCsp`);

    const metas = [...html.matchAll(META)];
    assert.equal(metas.length, 1, `${rel}: exactly one CSP meta`);
    const firstScript = html.indexOf("<script");
    if (firstScript >= 0) {
      assert.ok(metas[0].index < firstScript, `${rel}: CSP meta precedes the first <script>`);
    }
    // A long policy must not push the charset declaration out of the first
    // 1024 bytes, where the HTML spec requires it.
    const charset = html.indexOf('<meta charset="utf-8">');
    assert.ok(charset >= 0 && charset + 22 <= 1024, `${rel}: charset meta within 1024 bytes`);

    const policy = parsePolicy(metas[0][1]);
    const scriptSrc = policy.get("script-src");
    const expected = independentHashes(html);
    if (expected.length) scripted++;
    for (const h of expected) assert.ok(scriptSrc.includes(h), `${rel}: script-src names ${h}`);
    // No source beyond self + wasm + this page's own hashes (+ toolbar on preview).
    const extra = scriptSrc.filter(
      (s) => !["'self'", "'wasm-unsafe-eval'", ...expected].includes(s)
    );
    assert.deepEqual(extra, preview ? ["https://vercel.live"] : [], `${rel}: no stray script-src source`);
    assert.ok(!policy.has("default-src"), `${rel}: no default-src`);
    assert.ok(!policy.has("style-src"), `${rel}: no style-src`);
    assert.ok(!policy.has("font-src"), `${rel}: no font-src`);
    assert.doesNotMatch(html, /<[a-z][^>]*\son[a-z]+\s*=/i, `${rel}: no inline event handler`);

    const hasToolbar = TOOLBAR_ORIGINS.some((o) => metas[0][1].includes(o));
    assert.equal(hasToolbar, preview, `${rel}: Vercel Toolbar origins ${preview ? "present" : "absent"}`);
  }
  // Every layout page carries the theme bootstrap; this floor only proves the
  // independent extraction above is finding scripts at all.
  assert.ok(scripted >= files.length / 2, `only ${scripted} of ${files.length} pages carry inline scripts`);
}

test("every page of a default build carries a sound policy, with no toolbar origins", () => {
  const out = defaultBuild();
  assertTree(out, { preview: false });
  // The policy shape on a page that uses every directive's reason.
  const html = readFileSync(join(out, "designs", "calibration-cube", "index.html"), "utf8");
  const policy = parsePolicy([...html.matchAll(META)][0][1]);
  assert.deepEqual(policy.get("worker-src"), ["'self'", "blob:"]);
  assert.deepEqual(policy.get("object-src"), ["'none'"]);
  assert.deepEqual(policy.get("base-uri"), ["'self'"]);
  assert.deepEqual(policy.get("img-src"), ["'self'", "data:", "blob:"]);
  assert.deepEqual(policy.get("connect-src"), ["'self'"]);
  // Two inline scripts on a product page: the theme bootstrap + the import map.
  assert.equal(policy.get("script-src").filter((s) => s.startsWith("'sha256-")).length, 2);
});

test("a preview build (VERCEL_ENV=preview) allows exactly the Vercel Toolbar origins", () => {
  const out = build({ VERCEL_ENV: "preview" });
  try {
    assertTree(out, { preview: true });
    const html = readFileSync(join(out, "index.html"), "utf8");
    const policy = parsePolicy([...html.matchAll(META)][0][1]);
    // Exact source lists: the Toolbar origins and nothing else are added.
    assert.deepEqual(policy.get("connect-src"), ["'self'", "https://vercel.live", "wss://ws-us3.pusher.com"]);
    assert.deepEqual(policy.get("img-src"), ["'self'", "data:", "blob:", "https://vercel.live", "https://vercel.com"]);
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test("only VERCEL_ENV=preview turns on the toolbar origins", () => {
  assert.equal(toolbarAllowed({ VERCEL_ENV: "preview" }), true);
  for (const env of [{}, { VERCEL_ENV: "production" }, { VERCEL_ENV: "development" }, { VERCEL: "1" }]) {
    assert.equal(toolbarAllowed(env), false, JSON.stringify(env));
  }
  assert.doesNotMatch(cspPolicy({ hashes: [] }), /vercel|pusher/);
});

test("checkCsp flags an unhashed inline script injected into a built page (negative control)", () => {
  const page = applyCsp(
    `<!doctype html>\n<html><head>\n<meta charset="utf-8">\n<script>var a=1;</script>\n</head><body><p>x</p></body></html>\n`
  );
  assert.deepEqual(checkCsp(page), [], "the untouched page is sound");

  const injected = page.replace("<p>x</p>", "<p>x</p><script>alert(1)</script>");
  const problems = checkCsp(injected);
  assert.equal(problems.length, 1, problems.join("; "));
  assert.match(problems[0], /inline script not hashed in script-src: alert\(1\)/);

  // The same on a real page from the default build, in a copy.
  const real = readFileSync(join(defaultBuild(), "designs", "calibration-cube", "index.html"), "utf8");
  assert.deepEqual(checkCsp(real), []);
  const copy = real.replace("</main>", '<script type="module">import "/x.js";</script></main>');
  assert.ok(
    checkCsp(copy).some((p) => /inline script not hashed/.test(p)),
    "an injected inline module script must be flagged"
  );
  // Editing an already-hashed script's bytes is the same failure.
  const edited = real.replace('<script type="importmap">{', '<script type="importmap">{ ');
  assert.ok(checkCsp(edited).some((p) => /inline script not hashed/.test(p)));
});

test("checkCsp flags what no hash can allow, and a misplaced or weakened policy", () => {
  const ok = applyCsp(`<html><head><title>t</title></head><body><a href="/">x</a></body></html>`);
  assert.deepEqual(checkCsp(ok), []);
  const cases = [
    [ok.replace('<a href="/">', '<a href="/" onclick="go()">'), /inline event handler onclick=/],
    [ok.replace('<a href="/">', '<a href="/" ONMOUSEOVER=go()>'), /inline event handler onmouseover=/],
    [ok.replace('href="/"', 'href=" javascript:void(0)"'), /javascript: URL in href=/],
    [ok.replace("script-src 'self'", "script-src 'self' 'unsafe-inline'"), /script-src allows 'unsafe-inline'/],
    [ok.replace("script-src 'self'", "script-src 'self' 'unsafe-eval'"), /script-src allows 'unsafe-eval'/],
    [ok.replace(/<meta http-equiv[^>]*>/, ""), /exactly one Content-Security-Policy meta, found 0/],
    [ok.replace("</head>", `${ok.match(/<meta http-equiv[^>]*>/)[0]}</head>`), /found 2/],
    [ok.replace("<head>", "<head><title>t</title>"), /not the first element in <head>/],
  ];
  for (const [html, expected] of cases) {
    assert.ok(
      checkCsp(html).some((p) => expected.test(p)),
      `expected ${expected} in: ${checkCsp(html).join("; ")}`
    );
  }
  // Text that only looks like a handler is not one.
  const prose = applyCsp(`<html><head></head><body><p title="set onclick=x">a onclick=b</p></body></html>`);
  assert.deepEqual(checkCsp(prose), []);
});

test("the tokenizer counts only scripts the browser would run", () => {
  const html = [
    "<html><head>",
    "<!-- <script>commented()</script> -->",
    '<script type="application/json" id="d">{"a":1}</script>',
    '<script type="importmap">{"imports":{}}</script>',
    '<script src="/assets/site.js" defer></script>',
    "<title>&lt;script&gt; <script>not()</script></title>",
    "<script>one()</script >",
    "<script>two()</script/>",
    "</head><body></body></html>",
  ].join("\n");
  const { scripts } = scanHtml(html);
  const hashable = scripts.filter((s) => s.inline && s.executable).map((s) => s.body);
  assert.deepEqual(hashable, ['{"imports":{}}', "one()", "two()"]);
  assert.ok(scripts.some((s) => s.type === "application/json" && !s.executable), "data block seen, not executable");
  assert.ok(scripts.some((s) => !s.inline), "external script seen as external");
  // A commented-out script and a <script> inside <title> are text, not scripts.
  assert.ok(!scripts.some((s) => /commented|not\(\)/.test(s.body)));
  const policy = parsePolicy(applyCsp(html).match(/content="([^"]*)"/)[1]).get("script-src");
  for (const body of hashable) assert.ok(policy.includes(scriptHash(body)), body);
  assert.equal(policy.filter((s) => s.startsWith("'sha256-")).length, 3);
});

test("script types: classic, module, importmap and speculationrules run; data blocks do not", () => {
  for (const t of [null, "", " ", "text/javascript", "TEXT/JavaScript", "application/javascript", "module", "importmap", "speculationrules", "text/javascript; charset=utf-8"]) {
    assert.equal(isExecutableType(t), true, String(t));
  }
  for (const t of ["application/json", "application/ld+json", "text/plain", "text/template", "x-shader/x-vertex"]) {
    assert.equal(isExecutableType(t), false, t);
  }
});

test("hashes are the browser's: base64 SHA-256 over the LF-normalised text", () => {
  // Known answer: SHA-256 of the empty string, base64 (not hex).
  assert.equal(scriptHash(""), "'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='");
  assert.equal(scriptHash("a\r\nb\rc"), scriptHash("a\nb\nc"));
  assert.notEqual(scriptHash("a();"), scriptHash("a(); "));
});

test("applyCsp is pure, inserts first in <head>, and refuses a page it cannot cover", () => {
  const page = `<!doctype html>\n<html>\n<head>\n<meta charset="utf-8">\n<script>x()</script>\n</head><body></body></html>\n`;
  const once = applyCsp(page);
  assert.equal(applyCsp(page), once, "same input, same bytes");
  assert.equal(once.replace(/\n<meta http-equiv="Content-Security-Policy" content="[^"]*">/, ""), page);
  assert.match(once, /<head>\n<meta http-equiv="Content-Security-Policy" content="script-src 'self' 'wasm-unsafe-eval' 'sha256-/);
  assert.throws(() => applyCsp("<html><body><script>x()</script></body></html>"), /no <head>/);
  assert.throws(() => applyCsp("<script>x()</script><html><head></head></html>"), /precedes <head>/);
  assert.throws(() => applyCsp(once), /already carries/);
});

test("vercel.json: the site-wide CSP header never restricts scripts; the worker's allows wasm", () => {
  const vercel = JSON.parse(readFileSync(join(REPO_ROOT, "vercel.json"), "utf8"));
  const cspOf = (source) => {
    const rule = vercel.headers.find((r) => r.source === source);
    assert.ok(rule, `vercel.json has a ${source} header rule`);
    const h = rule.headers.find((x) => x.key.toLowerCase() === "content-security-policy");
    assert.ok(h, `${source} sets Content-Security-Policy`);
    return parsePolicy(h.value);
  };
  // The site-wide header also reaches the worker script and every asset, so a
  // script-src (or a default-src, which script-src falls back to) here would
  // govern the OpenSCAD worker's own imports and WebAssembly compile.
  const site = cspOf("/(.*)");
  for (const d of ["script-src", "script-src-elem", "default-src", "worker-src"]) {
    assert.ok(!site.has(d), `site-wide header must not set ${d}`);
  }
  assert.deepEqual(site.get("frame-ancestors"), ["'none'"]);
  assert.deepEqual(site.get("object-src"), ["'none'"]);
  assert.deepEqual(site.get("base-uri"), ["'self'"]);

  // The worker gets its policy from its own response, not the page's <meta>.
  // A superset of the site-wide directives, so the effective policy is the
  // same whether Vercel sends both matching headers or the later one alone.
  const worker = cspOf("/assets/openscad-worker.js");
  assert.deepEqual(worker.get("script-src"), ["'self'", "'wasm-unsafe-eval'"]);
  assert.deepEqual(worker.get("connect-src"), ["'self'"]);
  for (const [d, v] of site) assert.deepEqual(worker.get(d), v, `worker header repeats ${d}`);
  const order = vercel.headers.map((r) => r.source);
  assert.ok(order.indexOf("/assets/openscad-worker.js") > order.indexOf("/(.*)"), "worker rule after the site-wide one");
});
