// The deploy-time fetch seams, end to end through the real build.mjs.
//
// Why this exists: every seam, renderer and log formatter is unit-tested in
// isolation (seam/history/releases/decisions/notifications.test.mjs), but the
// wiring between them lives only in build.mjs — runSeam per seam, the WARN
// lines, and handing each seam's status to designPage and the header bell. CI's
// site-build job builds offline, where every seam is `off`, so no other check
// ever runs a non-off path through build.mjs. Measured: dropping
// `releaseStatus:` and `historyStatus:` from build.mjs's designPage call, or
// passing the bell `status: SEAM.EMPTY`, left every other site test green —
// which would silently bring back the fail-open this work closed, on Vercel
// only. So this runs the real build with every seam armed and the platform
// `fetch` replaced by a stub (a `--import` preload — no network, ever):
//   - every request answered 401: the build stays green, prints one WARN per
//     seam naming the failure class, and every page says what couldn't load —
//     never "You're all caught up", never a silent missing Downloads block;
//   - every request answered with a genuinely empty 200 (the negative
//     control): no WARN, no couldn't-load note, and the bell is "all caught
//     up" — while the log proves each seam really ran, so the empty build is
//     not an `off` build in disguise.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, readFileSync, readdirSync, rmSync, existsSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

import { readDesigns } from "../lib/content.mjs";
import { readTeam } from "../lib/team.mjs";
import { HISTORY_UNAVAILABLE } from "../lib/teams.mjs";
import { DECISIONS_UNAVAILABLE } from "../lib/notifications.mjs";
import { escapeHtml } from "../lib/markdown.mjs";

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));
const SITE_DIR = fileURLToPath(new URL("..", import.meta.url));

const DOWNLOADS_NOTE = "Couldn't check for release downloads on this deploy";

// The two stubbed GitHubs. Each is the body of a preload module that replaces
// globalThis.fetch before build.mjs runs — the seams read it at call time.
const STUBS = {
  // Every request refused — the measured 401 that used to render "queue empty".
  unauthorized: `
globalThis.fetch = async () =>
  new Response(JSON.stringify({ message: "Bad credentials" }), {
    status: 401,
    headers: { "content-type": "application/json" },
  });
`,
  // Every seam fetched fine and found nothing. An unexpected URL throws, so a
  // seam this stub doesn't know about lands as a WARN and fails the test.
  empty: `
const json = (body) =>
  new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
globalThis.fetch = async (url) => {
  const u = new URL(String(url));
  if (u.pathname.endsWith("/releases/latest")) return json({ tag_name: "v0.1", assets: [] });
  if (u.pathname.endsWith("/commits")) return json([]);
  if (u.pathname === "/search/issues") return json({ total_count: 0, incomplete_results: false, items: [] });
  throw new Error("build-seams stub: unexpected URL " + u.href);
};
`,
};

/** Run the real build with every seam armed and `fetch` stubbed; returns the run + a reader. */
function buildWith(stub) {
  const dir = mkdtempSync(join(tmpdir(), "print-bench-seams-"));
  const preload = join(dir, "fetch-stub.mjs");
  writeFileSync(preload, STUBS[stub]);
  const out = join(dir, "site");
  // Start from this process's environment minus anything that would arm,
  // disarm or authenticate a seam behind the test's back.
  const env = { ...process.env };
  for (const k of ["VERCEL", "GITHUB_TOKEN", "SITE_FETCH_HISTORY", "SITE_FETCH_RELEASES", "SITE_FETCH_DECISIONS"]) {
    delete env[k];
  }
  Object.assign(env, { SITE_FETCH_HISTORY: "1", SITE_FETCH_RELEASES: "1", SITE_FETCH_DECISIONS: "1" });
  const res = spawnSync(
    process.execPath,
    ["--import", pathToFileURL(preload).href, join(SITE_DIR, "build.mjs"), "--out", out],
    { encoding: "utf8", env }
  );
  const read = (rel) => readFileSync(join(out, rel), "utf8");
  return { res, out, read, cleanup: () => rmSync(dir, { recursive: true, force: true }) };
}

/** Every built .html page, relative to the output root. */
function htmlPages(root, rel = "") {
  const pages = [];
  for (const e of readdirSync(join(root, rel), { withFileTypes: true })) {
    const r = rel ? `${rel}/${e.name}` : e.name;
    if (e.isDirectory()) pages.push(...htmlPages(root, r));
    else if (e.name.endsWith(".html")) pages.push(r);
  }
  return pages;
}

const designs = readDesigns(REPO_ROOT);
const team = readTeam(REPO_ROOT, { designNames: new Set(designs.map((d) => d.name)) });
const rostered = designs.filter((d) => team.rosters.has(d.name));
const rosterless = designs.filter((d) => !team.rosters.has(d.name));

test("build: every seam unavailable (401) — green build, a WARN per seam, a note on every affected page", () => {
  assert.ok(rostered.length > 0 && rosterless.length > 0, "the real repo has both kinds of design");
  const { res, out, read, cleanup } = buildWith("unauthorized");
  try {
    assert.equal(res.status, 0, `an unavailable seam must never fail the build:\n${res.stderr}`);

    // Item 2: one WARN per seam, naming the seam and the failure class.
    assert.match(res.stderr, /WARN releases: fetch unavailable \(HTTP 401\) — /);
    assert.match(
      res.stderr,
      new RegExp(`WARN history: fetch unavailable for ${rostered.length} design\\(s\\) \\(HTTP 401\\) — History tabs show 'unavailable'`)
    );
    assert.match(res.stderr, /WARN decisions: fetch unavailable \(HTTP 401\) — /);
    // ...and never the misleading counts this replaced.
    assert.doesNotMatch(res.stdout, /history: 0 commit\(s\)/);
    assert.doesNotMatch(res.stdout, /queue empty/);

    // Item 3b: the bell says it couldn't load the queue — on every page.
    const index = read("index.html");
    assert.match(index, /class="notif-empty notif-unavailable"/);
    assert.ok(index.includes(escapeHtml(DECISIONS_UNAVAILABLE)), "the bell names what couldn't load");
    const pages = htmlPages(out);
    assert.ok(pages.length > designs.length, "the build wrote its pages");
    for (const p of pages) {
      const html = read(p);
      assert.doesNotMatch(html, /all caught up/, `${p}: an unread queue is not "all caught up"`);
      assert.doesNotMatch(html, /Reviewed by/, `${p}: no per-PR "Reviewed by" claim`);
    }

    for (const d of designs) {
      const html = read(`${d.relDir}/index.html`);
      // Item 3c: a release we couldn't read is never a silently absent block.
      assert.ok(html.includes(DOWNLOADS_NOTE), `${d.name}: the Downloads block says it couldn't check`);
      // Item 3a: only a rostered design has a History tab to carry the note.
      if (team.rosters.has(d.name)) {
        const history = html.slice(html.indexOf('id="history"'));
        assert.ok(history.includes(HISTORY_UNAVAILABLE), `${d.name}: the History tab carries the note`);
      } else {
        assert.ok(!html.includes(HISTORY_UNAVAILABLE), `${d.name}: rosterless — no History tab, no note`);
      }
    }
  } finally {
    cleanup();
  }
});

test("build: every seam fetched and genuinely empty — no WARN, no note, the bell is all caught up", () => {
  // The negative control for the test above: same build, same assertions'
  // targets, an honest empty GitHub — every couldn't-load surface must be gone.
  const { res, out, read, cleanup } = buildWith("empty");
  try {
    assert.equal(res.status, 0, `build failed:\n${res.stderr}`);
    assert.doesNotMatch(res.stderr, /WARN (releases|history|decisions)\b/);
    // Each seam really ran (an `off` build would print none of these).
    assert.match(res.stdout, /releases: no release manifests published/);
    assert.match(res.stdout, /history: 0 commit\(s\) fetched for the team timeline/);
    assert.match(res.stdout, /decisions: queue empty/);

    const index = read("index.html");
    assert.match(index, /You're all caught up\./);
    assert.doesNotMatch(index, /notif-unavailable/);
    for (const d of designs) {
      const html = read(`${d.relDir}/index.html`);
      assert.ok(!html.includes(DOWNLOADS_NOTE), `${d.name}: an empty release shows no Downloads note`);
      assert.ok(!html.includes(HISTORY_UNAVAILABLE), `${d.name}: an empty history shows no note`);
    }
    assert.ok(existsSync(join(out, "index.html")));
  } finally {
    cleanup();
  }
});
