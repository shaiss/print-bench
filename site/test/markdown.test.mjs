// inlineExcerpt — linear-time safe renderer for aggregated surfaces
// (People-page charter cards, design timeline rows). Audit finding D1 /
// provenance quick win Q2: the Marked-backed path emitted javascript: hrefs,
// let external images through, and stack-overflowed on crafted `*` runs.

import { test } from "node:test";
import assert from "node:assert/strict";
import { performance } from "node:perf_hooks";

import { inlineExcerpt, escapeHtml } from "../lib/markdown.mjs";

// --- Safe markdown still works ---------------------------------------------

test("inlineExcerpt: emphasis, strong, and code spans render", () => {
  assert.equal(
    inlineExcerpt("**bold** and *italic* and `code`"),
    "<strong>bold</strong> and <em>italic</em> and <code>code</code>",
  );
  assert.equal(inlineExcerpt("_also_"), "<em>also</em>");
});

test("inlineExcerpt: safe http(s) and site-rooted links stay live", () => {
  assert.equal(
    inlineExcerpt("[docs](https://example.com/a)"),
    '<a href="https://example.com/a" rel="noopener noreferrer">docs</a>',
  );
  assert.equal(
    inlineExcerpt("[local](/designs/foo/)"),
    '<a href="/designs/foo/" rel="noopener noreferrer">local</a>',
  );
  assert.equal(
    inlineExcerpt("[wiki](https://en.wikipedia.org/wiki/Foo_(bar))"),
    '<a href="https://en.wikipedia.org/wiki/Foo_(bar)" rel="noopener noreferrer">wiki</a>',
  );
});

test("inlineExcerpt: relative links flatten to their text (no 404 on aggregate pages)", () => {
  assert.equal(inlineExcerpt("[sushi-battleship](../sushi-battleship/)"), "sushi-battleship");
  assert.equal(inlineExcerpt("see [x](./y.md) please"), "see x please");
});

test("inlineExcerpt: HTML in the source cannot survive as live markup", () => {
  const out = inlineExcerpt('hello <script>alert(1)</script> **ok**');
  assert.equal(
    out,
    `hello ${escapeHtml("<script>alert(1)</script>")} <strong>ok</strong>`,
  );
  assert.doesNotMatch(out, /<script>/i);
});

// --- XSS: dangerous hrefs --------------------------------------------------

test("inlineExcerpt: javascript: links never appear as href (audit D1)", () => {
  const cases = [
    "[[x]](javascript:alert(1))",
    "[x](javascript:alert(1))",
    "[click me](JAVASCRIPT:alert(1))",
    "[x](javascript:alert(1)//)",
    "[x](vbscript:msgbox(1))",
    "[x](data:text/html,hi)",
  ];
  for (const input of cases) {
    const out = inlineExcerpt(input);
    assert.doesNotMatch(
      out,
      /href\s*=\s*["']?\s*(javascript|vbscript|data)\s*:/i,
      `dangerous href leaked for ${JSON.stringify(input)} → ${out}`,
    );
    assert.doesNotMatch(out, /javascript:/i, `raw javascript: in output for ${JSON.stringify(input)}`);
  }
});

test("inlineExcerpt: protocol-relative and other schemes are not kept live", () => {
  assert.doesNotMatch(inlineExcerpt("[x](//evil.example/path)"), /<a\b/i);
  assert.doesNotMatch(inlineExcerpt("[x](ftp://evil.example/)"), /<a\b/i);
  assert.equal(inlineExcerpt("[x](//evil.example/path)"), "x");
});

// --- Images ----------------------------------------------------------------

test("inlineExcerpt: external / untrusted images are never emitted", () => {
  const cases = [
    "![x](https://evil.com/x.png)",
    "![x](http://evil.com/x.png)",
    "![x](//evil.com/x.png)",
    "![x](/local.png)",
    "![alt text](javascript:alert(1))",
  ];
  for (const input of cases) {
    const out = inlineExcerpt(input);
    assert.doesNotMatch(out, /<img\b/i, `img emitted for ${JSON.stringify(input)} → ${out}`);
  }
  // Alt text is preserved as prose so the excerpt stays readable.
  assert.equal(inlineExcerpt("![photo of cube](https://evil.com/x.png)"), "photo of cube");
});

// --- Linear time on adversarial input --------------------------------------

test("inlineExcerpt: adversarial emphasis runs finish in linear time (no Marked recursion)", () => {
  // Marked's emStrong recurses on this shape and hits Maximum call stack
  // around n≈8000. A linear scanner stays fast at much larger n.
  const sizes = [2000, 4000, 8000, 16000];
  const times = [];
  for (const n of sizes) {
    const s = "*".repeat(n) + "a" + "*".repeat(n);
    const t0 = performance.now();
    const out = inlineExcerpt(s);
    times.push(performance.now() - t0);
    assert.doesNotMatch(out, /javascript:/i);
    assert.ok(out.length > 0);
  }
  // 8× input (2000 → 16000) must not blow up past a generous linear bound.
  // Cap is absolute so a slow CI runner still fails closed on a quadratic path.
  const last = times[times.length - 1];
  assert.ok(
    last < 200,
    `expected O(n) render of 32k-star input under 200ms, got ${last.toFixed(1)}ms (times=${times.map((t) => t.toFixed(1)).join(",")})`,
  );
});

test("inlineExcerpt: nested-bracket javascript payload is stripped and stays fast", () => {
  const n = 5000;
  const s = "[".repeat(n) + "x" + "]".repeat(n) + "(javascript:alert(1))";
  const t0 = performance.now();
  const out = inlineExcerpt(s);
  const ms = performance.now() - t0;
  assert.doesNotMatch(out, /javascript:/i);
  assert.doesNotMatch(out, /<a\b/i);
  assert.ok(ms < 200, `nested-bracket payload took ${ms.toFixed(1)}ms`);
});
