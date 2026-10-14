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
// instead of degrading would break every deploy; one that reports a 401 as
// `empty` tells every visitor "You're all caught up" about a queue nobody
// read; and one that stops after the first page shows 30 of 53 decisions as
// the whole queue (both measured). Only these catch them.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  shouldFetchDecisions,
  searchToDecisions,
  fetchOpenDecisions,
} from "../lib/decisions.mjs";
import { SEAM, runSeam } from "../lib/seam.mjs";
import { decisionsToNotifications } from "../lib/notifications.mjs";
import { indexPage, setNotifications } from "../lib/templates.mjs";

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

// A route's value is the JSON body of a 200, an Error the fetch throws, or a
// function returning the whole response (for a non-2xx or a broken body).
function stubFetch(routes) {
  return async (url) => {
    if (!(url in routes)) return { ok: false, status: 404, json: async () => ({}) };
    const body = routes[url];
    if (body instanceof Error) throw body;
    if (typeof body === "function") return body();
    return { ok: true, status: 200, json: async () => body };
  };
}
const httpError = (status, headers = {}) => () => ({
  ok: false,
  status,
  headers: new Map(Object.entries(headers)),
  json: async () => ({ message: "error" }),
});
const badJson = () => ({
  ok: true,
  status: 200,
  json: async () => {
    throw new SyntaxError("Unexpected token '<'");
  },
});

const pageUrl = (page, perPage = 100) =>
  `https://api.github.com/search/issues?q=${encodeURIComponent(
    `repo:${OWNER}/${REPO} is:open label:${LABEL}`
  )}&per_page=${perPage}&page=${page}&sort=created&order=ascending`;
const QUEUE_URL = pageUrl(1);
const ISSUE_42 = item({ number: 42, title: "Loosen the coupon fit?", url: "https://github.com/o/r/issues/42" });
const OPTS = { owner: OWNER, repo: REPO };

/** n decision items numbered from `from`. */
function items(n, from = 1) {
  return Array.from({ length: n }, (_, i) =>
    item({ number: from + i, title: `decision ${from + i}`, url: `https://github.com/o/r/issues/${from + i}` })
  );
}

test("fetchOpenDecisions returns the queue's items as an ok seam result", async () => {
  const fetchImpl = stubFetch({
    [QUEUE_URL]: { total_count: 1, incomplete_results: false, items: [ISSUE_42] },
  });
  const got = await fetchOpenDecisions({ fetchImpl, ...OPTS });
  assert.equal(got.status, SEAM.OK);
  assert.equal(got.items.length, 1);
  assert.equal(got.items[0].number, 42);
});

test("fetchOpenDecisions asks for the API's maximum page size (100)", async () => {
  const urls = [];
  await fetchOpenDecisions({
    fetchImpl: async (url) => {
      urls.push(url);
      return { ok: true, status: 200, json: async () => ({ total_count: 0, items: [] }) };
    },
    ...OPTS,
  });
  assert.deepEqual(urls, [QUEUE_URL], "one short page → one request");
  assert.match(urls[0], /per_page=100&page=1/);
});

test("fetchOpenDecisions follows pages: a two-page queue of 53 renders and counts 53", async () => {
  // The measured undercount: one 30-row page was all it read, so a 53-decision
  // queue showed 30. At the old page size the queue spans two pages.
  const all = items(53);
  const requested = [];
  const routes = {
    [pageUrl(1, 30)]: { total_count: 53, items: all.slice(0, 30) },
    [pageUrl(2, 30)]: { total_count: 53, items: all.slice(30) }, // 23 — a short page
  };
  const stub = stubFetch(routes);
  const fetchImpl = async (url) => {
    requested.push(url);
    return stub(url);
  };
  const got = await fetchOpenDecisions({ fetchImpl, ...OPTS, perPage: 30 });
  assert.equal(got.status, SEAM.OK);
  assert.equal(got.items.length, 53);
  assert.deepEqual(got.items.map((r) => r.number), all.map((i) => i.number), "order preserved");
  assert.equal(requested.length, 2, "stops at the short page — no third request");

  // …and the bell renders and counts all 53.
  setNotifications(
    decisionsToNotifications({ status: got.status, rows: got.items, searchUrl: "https://github.com/o/r/q" })
  );
  try {
    const html = indexPage([]);
    assert.match(html, /class="notif-badge"[^>]*>53</, "badge counts 53");
    assert.equal((html.match(/class="notif-item"/g) || []).length, 53, "53 rows rendered");
    assert.match(html, /decision 53/);
  } finally {
    setNotifications(null);
  }
});

test("fetchOpenDecisions stops once total_count items have arrived", async () => {
  const all = items(60);
  const requested = [];
  const stub = stubFetch({
    [pageUrl(1, 30)]: { total_count: 60, items: all.slice(0, 30) },
    [pageUrl(2, 30)]: { total_count: 60, items: all.slice(30) }, // full page, but total reached
  });
  const got = await fetchOpenDecisions({
    fetchImpl: async (url) => {
      requested.push(url);
      return stub(url);
    },
    ...OPTS,
    perPage: 30,
  });
  assert.equal(got.items.length, 60);
  assert.equal(requested.length, 2, "no third request past total_count");
});

test("fetchOpenDecisions caps pagination at 10 pages", async () => {
  // A source that never ends (total_count missing, every page full) must not
  // loop forever: 10 × 100 is the search API's own 1000-result ceiling.
  let n = 0;
  const got = await fetchOpenDecisions({
    fetchImpl: async () => {
      const page = items(5, 1 + 5 * n++);
      return { ok: true, status: 200, json: async () => ({ items: page }) };
    },
    ...OPTS,
    perPage: 5,
  });
  assert.equal(n, 10, "exactly maxPages requests");
  assert.equal(got.items.length, 50);
});

test("fetchOpenDecisions de-duplicates a row the ranking repeats across pages", async () => {
  const all = items(4);
  const got = await fetchOpenDecisions({
    fetchImpl: stubFetch({
      [pageUrl(1, 2)]: { total_count: 4, items: all.slice(0, 2) },
      [pageUrl(2, 2)]: { total_count: 4, items: [all[1], all[2]] }, // #2 again
      [pageUrl(3, 2)]: { total_count: 4, items: [all[3]] },
    }),
    ...OPTS,
    perPage: 2,
  });
  assert.deepEqual(got.items.map((r) => r.number), [1, 2, 3, 4]);
});

test("fetchOpenDecisions: a search that finds nothing is empty", async () => {
  const fetchImpl = stubFetch({ [QUEUE_URL]: { total_count: 0, items: [] } });
  const got = await fetchOpenDecisions({ fetchImpl, ...OPTS });
  assert.deepEqual(got, { status: SEAM.EMPTY, items: [], reason: null });
});

test("fetchOpenDecisions: a 401 / 403 / 404 is unavailable, never empty", async () => {
  for (const [route, reason] of [
    [httpError(401), "HTTP 401"],
    [httpError(403, { "x-ratelimit-remaining": "0" }), "HTTP 403, rate limited"],
    [undefined, "HTTP 404"], // absent route → the stub's 404
  ]) {
    const fetchImpl = stubFetch(route ? { [QUEUE_URL]: route } : {});
    const got = await fetchOpenDecisions({ fetchImpl, ...OPTS });
    assert.equal(got.status, SEAM.UNAVAILABLE);
    assert.equal(got.reason, reason);
    assert.deepEqual(got.items, []);
  }
});

test("fetchOpenDecisions: a network error is unavailable", async () => {
  const fetchImpl = stubFetch({ [QUEUE_URL]: new Error("getaddrinfo ENOTFOUND") });
  const got = await fetchOpenDecisions({ fetchImpl, ...OPTS });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.match(got.reason, /^network error: /);
});

test("fetchOpenDecisions: an unparseable body is unavailable", async () => {
  const got = await fetchOpenDecisions({ fetchImpl: stubFetch({ [QUEUE_URL]: badJson }), ...OPTS });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.equal(got.reason, "unparseable JSON body");
});

test("fetchOpenDecisions: a body with no items array is unavailable", async () => {
  // The search API returns a 200 with a message body on a rate limit, or an
  // unexpected shape; neither must sink the build — nor read as an empty queue.
  const fetchImpl = stubFetch({ [QUEUE_URL]: { message: "API rate limit exceeded" } });
  const got = await fetchOpenDecisions({ fetchImpl, ...OPTS });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.equal(got.reason, "unexpected response body");
});

test("fetchOpenDecisions: a failure on page 2 is unavailable — no partial queue", async () => {
  const all = items(53);
  const fetchImpl = stubFetch({
    [pageUrl(1, 30)]: { total_count: 53, items: all.slice(0, 30) },
    [pageUrl(2, 30)]: httpError(403, { "x-ratelimit-remaining": "0" }),
  });
  const got = await fetchOpenDecisions({ fetchImpl, ...OPTS, perPage: 30 });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.equal(got.reason, "HTTP 403, rate limited on page 2");
  assert.deepEqual(got.items, [], "30 of 53 is not shown as the queue");
});

test("fetchOpenDecisions aborts a hung request after the timeout: unavailable", async () => {
  // A fetch that never resolves on its own, but honors the abort signal the
  // way the platform fetch does — the bounded timeout must unstick the build.
  const hung = (_url, { signal } = {}) =>
    new Promise((_resolve, reject) => {
      signal?.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
    });
  const got = await fetchOpenDecisions({ fetchImpl: hung, ...OPTS, timeoutMs: 20 });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.equal(got.reason, "timeout after 20 ms");
});

test("fetchOpenDecisions without a fetch impl is unavailable, not a throw", async () => {
  const got = await fetchOpenDecisions({ fetchImpl: null, ...OPTS });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.deepEqual(got.items, []);
});

test("decisions disabled (the local/CI default) is off, and nothing is fetched", async () => {
  let fetched = false;
  const got = await runSeam(shouldFetchDecisions({}), () =>
    fetchOpenDecisions({
      fetchImpl: async () => {
        fetched = true;
        return { ok: true, status: 200, json: async () => ({ items: [] }) };
      },
      ...OPTS,
    })
  );
  assert.equal(got.status, SEAM.OFF);
  assert.equal(fetched, false);
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

// The decision queue's *rendering* is now the header notification bell, not a
// section on the index page. The mapping from a queue to notifications and the
// bell markup are pinned in notifications.test.mjs; decisions.mjs stays the
// data source and is tested only for that here.
