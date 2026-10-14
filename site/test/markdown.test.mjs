// The excerpt renderer (lib/markdown.mjs inlineExcerpt): the markdown
// fragments shown AWAY from their source file — decision-log rows, field
// tests and changelog entries on a design's timeline, commit subjects, and
// agent mandates on the People page.
//
// These surfaces aggregate text, so the renderer is their injection
// boundary (audit defect D1). It replaced Marked's inline lexer plus a
// flatten regex, which let a nested label (`[[x]](javascript:…)`) or an
// escaped bracket (`[a\]b](javascript:…)`) through as a live `javascript:`
// href, emitted external `<img>` for images, and took seconds on crafted
// input. So four kinds of pinning, each with the case that must FAIL:
//
//   1. every injection vector comes out inert, and a structural check holds
//      every output to the only tags the renderer may emit;
//   2. the kept links stay live (a renderer that flattened everything would
//      pass 1 and be wrong);
//   3. parity with the old render on the WHOLE committed corpus — read from
//      the real repo files, so a new excerpt that renders differently fails
//      here rather than shipping a changed page;
//   4. the time bound and the 64 KB backstop.

import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { performance } from "node:perf_hooks";
import { Marked } from "marked";

import { escapeHtml, inlineExcerpt, EXCERPT_MAX_CHARS } from "../lib/markdown.mjs";
import { readTimeline } from "../lib/timeline.mjs";
import { readTeam } from "../lib/team.mjs";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

// ---------------------------------------------------------------------------
// The structural safety check: the only markup an excerpt may contain is
// <code>, <em>, <strong> and <a href="…"> with a kept href — no other tag, no
// other attribute, no quote or angle bracket inside the href value.
// ---------------------------------------------------------------------------

const KEPT_HREF = /^(?:https?:\/\/|\/(?![/\\]))[^"'<>\s]*$/;

function assertSafe(html, input) {
  const where = `for input ${JSON.stringify(input)}: ${JSON.stringify(html)}`;
  for (const [tag] of html.matchAll(/<[^>]*>?/g)) {
    if (/^<\/?(?:code|em|strong)>$/.test(tag) || tag === "</a>") continue;
    const a = tag.match(/^<a href="([^"]*)">$/);
    assert.ok(a, `unexpected markup ${JSON.stringify(tag)} ${where}`);
    assert.match(a[1], KEPT_HREF, `a live href that is not kept ${where}`);
  }
  assert.doesNotMatch(html, /<img/i, `an <img> ${where}`);
}

test("assertSafe can fail: it refuses an unsafe href, an <img> and a stray tag", () => {
  assert.throws(() => assertSafe('<a href="javascript:alert(1)">x</a>', "neg"));
  assert.throws(() => assertSafe('<a href="//evil.example">x</a>', "neg"));
  assert.throws(() => assertSafe('<a href="/\\evil.example">x</a>', "neg"));
  assert.throws(() => assertSafe('<img src="https://evil.example/p.png" alt="">', "neg"));
  assert.throws(() => assertSafe('<a href="https://ok.example/" onclick="x()">x</a>', "neg"));
  assert.throws(() => assertSafe("<script>alert(1)</script>", "neg"));
  assertSafe('<a href="https://ok.example/">x</a> <code>c</code> <em>e</em>', "pos");
});

// ---------------------------------------------------------------------------
// 1. Injection vectors — each exact, and each structurally safe.
// ---------------------------------------------------------------------------

const VECTORS = [
  // The two confirmed bypasses of the old flatten-then-Marked render.
  ["[[x]](javascript:alert(1))", "[x]"],
  ["[a\\]b](javascript:alert(1))", "a]b"],
  // Every scheme but http(s), however it is spelled.
  ["[x](javascript:alert(1))", "x"],
  ["[x](JavaScript:alert(1))", "x"],
  // Whitespace makes the destination malformed: it flattens up to the first
  // ")" — the old rule's reach — so the rest of the parens is text.
  ["[x](  javascript:alert(1))", "x)"],
  ["[x](java\tscript:alert(1))", "x)"],
  ["[x](java\nscript:alert(1))", "x)"],
  ["[x](&#106;avascript:alert(1))", "x"],
  ["[x](jav&#x61;script:alert(1))", "x"],
  ["[x](%6Aavascript:alert(1))", "x"],
  ["[x](data:text/html,<script>alert(1)</script>)", "x"],
  ["[x](vbscript:msgbox(1))", "x"],
  ["[x](mailto:someone@example.com)", "x"],
  ["[x](HTTPS://evil.example/)", "x"],
  ["[x](Http://evil.example/)", "x"],
  // The kept prefix must be literal: an escaped one flattens, as before.
  ["[x](https:\\/\\/evil.example/)", "x"],
  // Another origin dressed as site-rooted: //host, /\host, /\/host.
  ["[x](//evil.example/)", "x"],
  ["[x](/\\evil.example/)", "x"],
  ["[x](/\\/evil.example/)", "x"],
  // Relative and in-page links flatten, as they always did (they resolve
  // against the source file's directory, not the aggregating page).
  ["[x](../sibling/)", "x"],
  ["[x](sibling.md)", "x"],
  ["[x](#top)", "x"],
  ["[x]()", "x"],
  // Images are their alt text, never an <img>, whatever the src.
  ["![](https://evil.example/p.png)", ""],
  ["![logo](https://evil.example/p.png)", "logo"],
  ["![a *b* `c`](x.png)", "a b c"],
  ["[![a](https://evil.example/p.png)](javascript:alert(1))", "a"],
  // Bracket tricks: links never nest, and the outer one is spent text.
  [
    "[[a](https://ok.example/)](javascript:alert(1))",
    '[<a href="https://ok.example/">a</a>](javascript:alert(1))',
  ],
  // An href cannot break out of its attribute; a label cannot carry markup.
  [
    '[x](https://ok.example/"onmouseover="alert(1))',
    '<a href="https://ok.example/&quot;onmouseover=&quot;alert(1)">x</a>',
  ],
  [
    "[<img src=x onerror=alert(1)>](https://ok.example/)",
    '<a href="https://ok.example/">&lt;img src=x onerror=alert(1)&gt;</a>',
  ],
  ["<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;"],
  ["`[x](javascript:alert(1))`", "<code>[x](javascript:alert(1))</code>"],
  // Bare URLs and addresses are text — only a [text](href) link is live.
  ["see javascript:alert(1) or a@b.example", "see javascript:alert(1) or a@b.example"],
];

for (const [input, expected] of VECTORS) {
  test(`inert: ${JSON.stringify(input)}`, () => {
    const html = inlineExcerpt(input);
    assertSafe(html, input);
    assert.equal(html, expected);
  });
}

test("a seeded fuzz over link/image/bracket syntax never emits unsafe markup", () => {
  const parts = [
    "[", "]", "(", ")", "![", "\\", "`", "*", "_", " ", "\t", "x", "/", "//", "/\\",
    "javascript:", "JavaScript:", "data:", "https://ok.example/", "http:", "#", "&#58;", '"', "'", "<", ">",
  ];
  let seed = 2026;
  const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
  for (let t = 0; t < 4000; t++) {
    let s = "";
    const len = 1 + Math.floor(rnd() * 16);
    for (let k = 0; k < len; k++) s += parts[Math.floor(rnd() * parts.length)];
    assertSafe(inlineExcerpt(s), s);
  }
});

// ---------------------------------------------------------------------------
// 2. What still renders — the positive controls.
// ---------------------------------------------------------------------------

const RENDERS = [
  ["[docs](https://example.com/a?b=1&c=2)", '<a href="https://example.com/a?b=1&amp;c=2">docs</a>'],
  ["[old](http://example.com/)", '<a href="http://example.com/">old</a>'],
  ["[home](/designs/calibration-cube/)", '<a href="/designs/calibration-cube/">home</a>'],
  ["[root](/)", '<a href="/">root</a>'],
  ["[**b**](https://example.com)", '<a href="https://example.com"><strong>b</strong></a>'],
  ["[x](https://example.com )", '<a href="https://example.com">x</a>'],
  ["[x](https://en.example/Foo_(bar))", '<a href="https://en.example/Foo_(bar)">x</a>'],
  // An escaped paren is part of the destination, not its end.
  ["[x](https://example.com/a\\)b)", '<a href="https://example.com/a)b">x</a>'],
  ["[x](/a\\(b)", '<a href="/a(b">x</a>'],
  ["*a [b](/c) d*", '<em>a <a href="/c">b</a> d</em>'],
  ["[x](https://example.com/é)", '<a href="https://example.com/%C3%A9">x</a>'],
  ["[x](https://example.com/%20a)", '<a href="https://example.com/%20a">x</a>'],
  ["`lead_in` 1.6 mm", "<code>lead_in</code> 1.6 mm"],
  ["``a ` b``", "<code>a ` b</code>"],
  ["` x `", "<code>x</code>"],
  ["**both reviewers pass**", "<strong>both reviewers pass</strong>"],
  ["only *shortened* the ramp", "only <em>shortened</em> the ramp"],
  ["an _emphasised_ word", "an <em>emphasised</em> word"],
  ["***both***", "<em><strong>both</strong></em>"],
  ["**a `c` b**", "<strong>a <code>c</code> b</strong>"],
  ["snake_case_name stays", "snake_case_name stays"],
  ["a\\*b\\* stays literal", "a*b* stays literal"],
  ["[pr-number | designs/<name>]", "[pr-number | designs/&lt;name&gt;]"],
  ["cursor[bot]", "cursor[bot]"],
  ["the brief's \"~1–2\"", "the brief&#39;s &quot;~1–2&quot;"],
  ["a & b", "a &amp; b"],
  ["&amp; is shown, not decoded", "&amp;amp; is shown, not decoded"],
  ['\\"quoted\\"', "&quot;quoted&quot;"],
  ["line one\nline two", "line one\nline two"],
  ["", ""],
];

for (const [input, expected] of RENDERS) {
  test(`renders: ${JSON.stringify(input)}`, () => {
    const html = inlineExcerpt(input);
    assertSafe(html, input);
    assert.equal(html, expected);
  });
}

test("null and undefined render as the empty string, like before", () => {
  assert.equal(inlineExcerpt(null), "");
  assert.equal(inlineExcerpt(undefined), "");
});

test("old defect fixed: a code span is escaped once, not twice", () => {
  // Marked re-escaped what escapeHtml had already escaped, so the page
  // showed the literal text `&lt;name&gt;-coupon.scad`.
  assert.equal(
    inlineExcerpt("does not steal `<name>-coupon.scad`"),
    "does not steal <code>&lt;name&gt;-coupon.scad</code>",
  );
});

test("old defect fixed: a `~` is approximately, never a strikethrough", () => {
  // GFM single-tilde strikethrough struck the text between two "~N mm"
  // measurements in a committed decision-log row.
  const html = inlineExcerpt("top at ~16.9 mm while the housing (~19.4 mm) clears; ~~x~~");
  assert.equal(html, "top at ~16.9 mm while the housing (~19.4 mm) clears; ~~x~~");
});

// ---------------------------------------------------------------------------
// 3. Parity with the old render over every committed excerpt.
// ---------------------------------------------------------------------------

// The renderer this replaced, verbatim: escapeHtml, the relative-link flatten
// regex, then Marked's inline parse.
const oldMarked = new Marked({ gfm: true });
function oldInlineExcerpt(text) {
  const escaped = escapeHtml(String(text || ""));
  const flattened = escaped.replace(/\[([^\]]*)\]\((?!https?:\/\/|\/)[^)]*\)/g, "$1");
  return oldMarked.parseInline(flattened);
}

// The old render's two non-security defects (pinned above), undone on the OLD
// side so everything else must match byte for byte: code-span text escaped
// twice, and single-tilde strikethrough (rewritten back to its "~"s — a
// committed `~~strike~~` would therefore surface here as a difference, on
// purpose: it renders literally now).
function withoutOldDefects(html) {
  return html
    .replace(/<code>([\s\S]*?)<\/code>/g, (_, c) =>
      `<code>${c.replace(/&amp;(lt|gt|quot|#39|amp);/g, "&$1;")}</code>`,
    )
    .replace(/<\/?del>/g, "~");
}

test("withoutOldDefects only undoes the two defects (negative control)", () => {
  assert.equal(withoutOldDefects("<code>&amp;lt;n&amp;gt;</code>"), "<code>&lt;n&gt;</code>");
  assert.equal(withoutOldDefects("~a <del>b </del>c"), "~a ~b ~c");
  // Outside a code span a double escape is real content and stays.
  assert.equal(withoutOldDefects("&amp;lt;"), "&amp;lt;");
  assert.equal(withoutOldDefects('<a href="javascript:x">y</a>'), '<a href="javascript:x">y</a>');
});

/**
 * Every excerpt the site renders from committed files, read the way the build
 * reads them: each design's PM.md decision log and NOTES.md field-test log and
 * changelog through readTimeline (rosterless designs included — the input is
 * the same whether or not a page shows it today), and every member's mandate
 * summary and text through readTeam. Commit subjects are deploy-time data and
 * not in the tree, so they are covered by the unit cases above instead.
 */
function committedExcerpts() {
  const out = [];
  const designsDir = join(REPO_ROOT, "designs");
  for (const design of readdirSync(designsDir).sort()) {
    const dir = join(designsDir, design);
    if (!statSync(dir).isDirectory()) continue;
    const read = (f) => (existsSync(join(dir, f)) ? readFileSync(join(dir, f), "utf8") : null);
    const { events } = readTimeline({ pmText: read("PM.md"), notesText: read("NOTES.md"), roster: null });
    for (const e of events) {
      out.push({ where: `designs/${design} ${e.source} text`, text: e.text });
      if (e.detail) out.push({ where: `designs/${design} ${e.source} detail`, text: e.detail });
    }
  }
  const { people } = readTeam(REPO_ROOT);
  for (const m of people.values()) {
    if (m.mandate.summary) out.push({ where: `people/${m.handle} summary`, text: m.mandate.summary });
    out.push({ where: `people/${m.handle} mandate`, text: m.mandate.text });
  }
  return out;
}

test("parity: every committed excerpt renders exactly as the old Marked render did", () => {
  const corpus = committedExcerpts();
  let rendered = "";
  for (const { where, text } of corpus) {
    const html = inlineExcerpt(text);
    assertSafe(html, text);
    assert.equal(html, withoutOldDefects(oldInlineExcerpt(text)), `${where}: ${JSON.stringify(text)}`);
    rendered += html;
  }
  // Not vacuous: the real corpus is large and exercises every construct, so a
  // loader that silently read nothing cannot pass this test.
  assert.ok(corpus.length >= 150, `only ${corpus.length} committed excerpts found`);
  const count = (re) => (rendered.match(re) || []).length;
  assert.ok(count(/<code>/g) >= 80, "corpus code spans");
  assert.ok(count(/<strong>/g) >= 40, "corpus strong");
  assert.ok(count(/<em>/g) >= 8, "corpus emphasis");
});

// ---------------------------------------------------------------------------
// 4. Time and size bounds.
// ---------------------------------------------------------------------------

/** Best of several runs: the floor is the algorithm, the rest is GC and JIT. */
function bestMs(fn, runs = 7) {
  let best = Infinity;
  for (let r = 0; r < runs; r++) {
    const t0 = performance.now();
    fn();
    best = Math.min(best, performance.now() - t0);
  }
  return best;
}

// The required crafted runs (Marked took ~650 ms on 2,000 chars of "[x](" and
// ~3.9 s on 4,000), plus delimiter-stack shapes that would expose a quadratic
// emphasis or code-span search — "_a b* " is the one only openers_bottom
// keeps linear (every "*" closer would re-walk all the "_" openers before it),
// and "*a [b](/c) " forms a link over an ever-deeper delimiter stack.
const CRAFTED = ["[x](", "[[x](", "![a](", "**", "`", "*a ", "a* ", "_a b* ", "`a``", "*a [b](/c) "];

for (const unit of CRAFTED) {
  test(`linear time: ${JSON.stringify(unit)} repeated to 2k, 8k and 64k chars`, () => {
    const at = (k) => unit.repeat(Math.ceil(k / unit.length)).slice(0, k);
    inlineExcerpt(at(2048)); // warm the JIT so the 2k figure is the algorithm
    const ms = {};
    for (const k of [2048, 8192, 65536]) {
      const s = at(k);
      ms[k] = bestMs(() => inlineExcerpt(s));
      assert.ok(ms[k] < 50, `${k} chars took ${ms[k].toFixed(1)} ms`);
    }
    // 32x the input may cost ~32x the time; a quadratic renderer costs ~1000x.
    assert.ok(
      ms[65536] < 40 * ms[2048] + 25,
      `64k took ${ms[65536].toFixed(1)} ms vs ${ms[2048].toFixed(2)} ms at 2k`,
    );
  });
}

test("nesting depth is not a stack: 10k nested emphasis renders", () => {
  const html = inlineExcerpt("*a ".repeat(10000) + "b" + " c*".repeat(10000));
  assert.ok(html.startsWith("<em>a <em>a "));
  assert.equal((html.match(/<em>/g) || []).length, 10000);
});

test("64 KB backstop: longer input is cut there and ends in an ellipsis", () => {
  const max = EXCERPT_MAX_CHARS;
  assert.equal(max, 64 * 1024);
  assert.equal(inlineExcerpt("a".repeat(max)), "a".repeat(max), "at the limit: untouched");
  assert.equal(inlineExcerpt("a".repeat(max + 1)), "a".repeat(max) + "…", "one past: cut");
  const huge = "[x](".repeat(1 << 18); // 1 MiB of the crafted run
  const ms = bestMs(() => inlineExcerpt(huge), 3);
  const html = inlineExcerpt(huge);
  assert.ok(html.endsWith("…"));
  assert.ok(html.length <= max + 1, `rendered ${html.length} chars`);
  assert.ok(ms < 50, `1 MiB took ${ms.toFixed(1)} ms — the backstop did not bound it`);
  // The cut never splits a surrogate pair.
  const emoji = inlineExcerpt("a".repeat(max - 1) + "😀b");
  assert.equal(emoji, "a".repeat(max - 1) + "…");
});
