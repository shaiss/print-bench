// The read-only "Decisions awaiting a human" queue (the deploy-time surfacing
// layer for the #161 HITL decision gate, issue #181).
//
// Why this exists: the queue comes from the network — the one part of the
// section that is neither committed nor gated by the render pipeline — so its
// two halves are pinned here like releases.mjs and history.mjs. The PURE
// search-API → render-model mapping (number/title/url, honest issue-vs-pull
// kind, length-capped titles, total on junk), and the BEST-EFFORT fetch
// boundary driven by a stub `fetch` so no test touches the network. The
// negative controls matter most — a fetch that starts throwing on a 404
// instead of degrading to "no section" would break every deploy, and only
// these catch it.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  shouldFetchDecisions,
  searchToDecisions,
  fetchOpenDecisions,
} from "../lib/decisions.mjs";
import { indexPage } from "../lib/templates.mjs";

const OWNER = "shaiss";
const REPO = "print-bench";
const LABEL = "needs-decision";

/** A GitHub search-API item, trimmed to the fields searchToDecisions reads. */
function item({ number, title, url, isPull = false }) {
  return {
    number,
    title,
    html_url: url,
    state: "open",
    ...(isPull ? { pull_request: { url: `${url}/pull` } } : {}),
  };
}

// --- the PURE transform, no network ---

test("searchToDecisions maps search items to decision rows", () => {
  const got = searchToDecisions([
    item({ number: 42, title: "Loosen the coupon fit?", url: "https://github.com/o/r/issues/42" }),
  ]);
  assert.equal(got.length, 1);
  assert.deepEqual(got[0], {
    number: 42,
    title: "Loosen the coupon fit?",
    url: "https://github.com/o/r/issues/42",
    kind: "issue",
  });
});

test("searchToDecisions marks a pull request row as 'pull', an issue as 'issue'", () => {
  const got = searchToDecisions([
    item({ number: 7, title: "ship it?", url: "https://github.com/o/r/issues/7" }),
    item({ number: 9, title: "merge it?", url: "https://github.com/o/r/pull/9", isPull: true }),
  ]);
  assert.equal(got[0].kind, "issue");
  assert.equal(got[1].kind, "pull");
});

test("searchToDecisions skips items missing a number, title or url", () => {
  const got = searchToDecisions([
    item({ number: 1, title: "kept", url: "https://github.com/o/r/issues/1" }),
    { number: 2, title: "no url" }, // missing html_url
    { number: 3, url: "https://github.com/o/r/issues/3" }, // missing title
    { title: "no number", url: "https://github.com/o/r/issues/4" }, // missing number
    null,
    "not an object",
  ]);
  assert.equal(got.length, 1);
  assert.equal(got[0].number, 1);
});

test("searchToDecisions trims, takes the first line, and caps a very long title", () => {
  const long = "x".repeat(200);
  const [e] = searchToDecisions([item({ number: 1, title: `  ${long}\nsecond`, url: "u" })]);
  assert.ok(e.title.length <= 140, "title is length-capped for one row");
  assert.ok(e.title.endsWith("…"));
  assert.ok(!e.title.includes("\n"), "only the first line is kept");
});

test("searchToDecisions is total on junk input", () => {
  assert.deepEqual(searchToDecisions(null), [], "non-array → []");
  assert.deepEqual(searchToDecisions(undefined), []);
  assert.deepEqual(searchToDecisions("nope"), []);
  assert.deepEqual(searchToDecisions([]), []);
});

// --- the fetch boundary, driven by a stub `fetch` (never the network) ---

function stubFetch(routes) {
  return async (url) => {
    if (!(url in routes)) return { ok: false, status: 404, json: async () => ({}) };
    const body = routes[url];
    if (body instanceof Error) throw body;
    return { ok: true, status: 200, json: async () => body };
  };
}

const QUEUE_URL = `https://api.github.com/search/issues?q=${encodeURIComponent(
  `repo:${OWNER}/${REPO} is:open label:${LABEL}`
)}&per_page=30&sort=created&order=ascending`;

test("fetchOpenDecisions returns the queue's items as decision rows", async () => {
  const fetchImpl = stubFetch({
    [QUEUE_URL]: {
      total_count: 1,
      incomplete_results: false,
      items: [item({ number: 42, title: "Loosen the coupon fit?", url: "https://github.com/o/r/issues/42" })],
    },
  });
  const got = await fetchOpenDecisions({ fetchImpl, owner: OWNER, repo: REPO });
  assert.equal(got.length, 1);
  assert.equal(got[0].number, 42);
});

test("fetchOpenDecisions degrades to [] on a 404 / non-2xx (empty queue)", async () => {
  const fetchImpl = stubFetch({}); // every URL 404s
  const got = await fetchOpenDecisions({ fetchImpl, owner: OWNER, repo: REPO });
  assert.deepEqual(got, []);
});

test("fetchOpenDecisions degrades to [] on a network error", async () => {
  const fetchImpl = stubFetch({ [QUEUE_URL]: new Error("getaddrinfo ENOTFOUND") });
  const got = await fetchOpenDecisions({ fetchImpl, owner: OWNER, repo: REPO });
  assert.deepEqual(got, []);
});

test("fetchOpenDecisions degrades to [] when the body has no items array", async () => {
  // The search API returns a 200 with a message body on a rate limit, or an
  // unexpected shape; neither must sink the build.
  const fetchImpl = stubFetch({ [QUEUE_URL]: { message: "API rate limit exceeded" } });
  const got = await fetchOpenDecisions({ fetchImpl, owner: OWNER, repo: REPO });
  assert.deepEqual(got, []);
});

test("fetchOpenDecisions aborts a hung request after the timeout and returns []", async () => {
  // A fetch that never resolves on its own, but honors the abort signal the
  // way the platform fetch does — the bounded timeout must unstick the build.
  const hung = (_url, { signal } = {}) =>
    new Promise((_resolve, reject) => {
      signal?.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
    });
  const got = await fetchOpenDecisions({
    fetchImpl: hung,
    owner: OWNER,
    repo: REPO,
    timeoutMs: 20,
  });
  assert.deepEqual(got, []);
});

test("fetchOpenDecisions returns [] without a fetch impl", async () => {
  assert.deepEqual(await fetchOpenDecisions({ fetchImpl: null, owner: OWNER, repo: REPO }), []);
});

test("fetchOpenDecisions scopes the query to the repo and label", async () => {
  let called;
  const fetchImpl = async (url) => {
    called = url;
    return { ok: true, status: 200, json: async () => ({ items: [] }) };
  };
  await fetchOpenDecisions({ fetchImpl, owner: OWNER, repo: REPO });
  // The query is URL-encoded on the wire, so decode before asserting on the
  // human-readable qualifiers.
  const q = decodeURIComponent(called);
  assert.ok(q.includes(`repo:${OWNER}/${REPO}`), "scoped to this repo");
  assert.ok(q.includes(`label:${LABEL}`), "filtered to the needs-decision label");
  assert.ok(q.includes("is:open"), "open decisions only");
});

test("shouldFetchDecisions: on for Vercel or explicit opt-in, off otherwise", () => {
  assert.equal(shouldFetchDecisions({}), false); // local / CI default: deterministic, no network
  assert.equal(shouldFetchDecisions({ VERCEL: "1" }), true); // the deploy has network
  assert.equal(shouldFetchDecisions({ SITE_FETCH_DECISIONS: "1" }), true);
  assert.equal(shouldFetchDecisions({ VERCEL: "1", SITE_FETCH_DECISIONS: "0" }), false); // explicit off wins
});

// --- the rendered section, driven through the index page (no network) ---
//
// The positive render path is deploy-only — the gate is off for a local/CI
// build and the queue may be empty even on the deploy — so the build cannot
// prove a non-empty queue renders. These hold that path against regression by
// feeding indexPage a non-empty decision bundle directly, the same way
// how-it-works.test.mjs drives howItWorksPage.

test("indexPage renders a Decisions section from a non-empty queue", () => {
  const html = indexPage([], {
    decisions: {
      rows: [
        { number: 42, title: "Loosen the coupon fit?", url: "https://github.com/o/r/issues/42", kind: "issue" },
        { number: 9, title: "ship it?", url: "https://github.com/o/r/pull/9", kind: "pull" },
      ],
      searchUrl: "https://github.com/o/r/issues?q=needs-decision",
    },
  });
  assert.match(html, /Decisions awaiting a human/);
  assert.match(html, /class="decisions"/);
  assert.match(html, /#42/, "issue number rendered");
  assert.match(html, /Loosen the coupon fit\?/, "issue title rendered");
  assert.match(html, /href="https:\/\/github\.com\/o\/r\/issues\/42"/, "row links to the issue");
  assert.match(html, /Every open decision/, "search link rendered");
  // each row carries an honest kind label
  const kinds = html.match(/<span class="dec-kind">/g) || [];
  assert.equal(kinds.length, 2, "one kind label per row");
  // the how-it-works sanity checks: no leaks into the page
  assert.ok(!html.includes("undefined"), "no undefined leaked into the page");
  assert.ok(!html.includes("${"), "no unrendered template placeholder");
});

test("indexPage renders no Decisions section when the queue is null or empty", () => {
  // null (fetch skipped, local/CI) — the determinism case
  assert.ok(!indexPage([], { decisions: null }).includes("Decisions awaiting a human"));
  assert.ok(!indexPage([], { decisions: null }).includes('class="decisions"'));
  // empty rows (queue legitimately empty on the deploy)
  assert.ok(
    !indexPage([], { decisions: { rows: [], searchUrl: "x" } }).includes("Decisions awaiting a human"),
    "an empty queue renders nothing, not an empty heading"
  );
});
