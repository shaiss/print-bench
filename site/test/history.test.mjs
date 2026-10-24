// Git-history events for the team timeline (the deploy-time source folded into
// issue #126's seam).
//
// Why this exists: these events come from the network — the one part of the
// timeline that is neither committed nor gated by the render pipeline — so its
// two halves are pinned here like releases.mjs. The PURE commit→event mapping
// (dates, summaries, and the honest attribution rule: a login maps to a handle
// only via the committed map, else the event is unattributed), and the
// BEST-EFFORT fetch boundary driven by a stub `fetch` so no test touches the
// network. The negative controls matter most — a fetch that starts throwing on
// a 404 instead of degrading to "no git events" would break every deploy, and
// one that reports a 403 rate limit as `empty` instead of `unavailable` would
// pass a failed fetch off as a design with no git history (the measured
// "history: 0 commit(s)" green build); only these catch either.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  commitsToEvents,
  fetchDesignCommits,
  shouldFetchHistory,
  loginHandleMap,
} from "../lib/history.mjs";
import { SEAM, runSeam } from "../lib/seam.mjs";
import { historySlot, HISTORY_UNAVAILABLE } from "../lib/teams.mjs";

const OWNER = "shaiss";
const REPO = "print-bench";

/** A GitHub commit object, trimmed to the fields commitsToEvents reads. */
function commit({ date, message, login }) {
  return {
    sha: "0".repeat(40),
    commit: { author: { date }, message },
    author: login === undefined ? null : { login },
  };
}

test("commitsToEvents maps commits to timeline events, newest text preserved", () => {
  const events = commitsToEvents([
    commit({ date: "2026-08-06T10:00:00Z", message: "Add design: calibration-cube\n\nbody", login: "shaiss" }),
  ]);
  assert.equal(events.length, 1);
  const e = events[0];
  assert.equal(e.date, "2026-08-06");
  assert.equal(e.source, "git");
  assert.equal(e.sourceTag, "commit · git");
  assert.equal(e.text, "Add design: calibration-cube", "only the first message line");
  assert.equal(e.detail, "");
});

test("commitsToEvents attributes only via the committed login→handle map", () => {
  const loginToHandle = new Map([["shaiss", "shai"]]);
  const events = commitsToEvents(
    [
      commit({ date: "2026-08-06T00:00:00Z", message: "Shai's commit", login: "shaiss" }),
      commit({ date: "2026-08-05T00:00:00Z", message: "a bot's commit", login: "some-bot" }),
      commit({ date: "2026-08-04T00:00:00Z", message: "authorless", login: undefined }),
    ],
    { loginToHandle }
  );
  assert.equal(events[0].handle, "shai", "a mapped login attributes");
  assert.equal(events[1].handle, null, "an unmapped login stays unattributed, not guessed");
  assert.equal(events[2].handle, null, "an authorless commit stays unattributed");
});

test("commitsToEvents attributes case-insensitively (GitHub logins are case-insensitive)", () => {
  // The committed map is canonical-lowercase; the API can return any casing.
  const loginToHandle = new Map([["shaiss", "shai"]]);
  const [e] = commitsToEvents([commit({ date: "2026-08-06T00:00:00Z", message: "x", login: "ShaISS" })], {
    loginToHandle,
  });
  assert.equal(e.handle, "shai");
});

test("loginHandleMap lowercases keys and rejects a login two members claim", () => {
  const { map, problems } = loginHandleMap([
    { handle: "shai", github: "shaiss" },
    { handle: "vera", github: null }, // no login → skipped, not an error
  ]);
  assert.equal(map.get("shaiss"), "shai");
  assert.deepEqual(problems, []);

  const dup = loginHandleMap([
    { handle: "ada", github: "dev" },
    { handle: "bot", github: "dev" }, // same login, different member → a problem
  ]);
  assert.equal(dup.problems.length, 1);
  assert.match(dup.problems[0], /claimed by both 'ada' and 'bot'/);
  assert.equal(dup.map.get("dev"), "ada", "the first mapping stands; the clash is reported, not silently overwritten");
});

test("commitsToEvents drops merge commits (branch bookkeeping, not product work)", () => {
  const merge = commit({ date: "2026-08-08T00:00:00Z", message: "Merge branch 'main' into feature" });
  merge.parents = [{ sha: "a" }, { sha: "b" }]; // two parents = a merge
  const real = commit({ date: "2026-08-06T00:00:00Z", message: "Add design: calibration-cube" });
  real.parents = [{ sha: "a" }]; // one parent = an ordinary commit
  const events = commitsToEvents([merge, real]);
  assert.equal(events.length, 1);
  assert.equal(events[0].text, "Add design: calibration-cube");
});

test("commitsToEvents skips commits with no usable date or empty summary", () => {
  const events = commitsToEvents([
    commit({ date: undefined, message: "no date" }),
    { commit: { author: { date: "2026-08-06T00:00:00Z" }, message: "   \n more" } }, // blank first line
    commit({ date: "2026-08-06T00:00:00Z", message: "kept" }),
    null,
    "not an object",
  ]);
  assert.equal(events.length, 1);
  assert.equal(events[0].text, "kept");
});

test("commitsToEvents caps a very long summary and is total on junk input", () => {
  const long = "x".repeat(200);
  const [e] = commitsToEvents([commit({ date: "2026-08-06T00:00:00Z", message: long })]);
  assert.ok(e.text.length <= 140, "summary is length-capped for one row");
  assert.ok(e.text.endsWith("…"));
  assert.deepEqual(commitsToEvents(null), [], "non-array → []");
  assert.deepEqual(commitsToEvents(undefined), []);
});

// --- fetch boundary, driven by a stub `fetch` (never the network) ---

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
// GitHub's anonymous rate limit: a 403 with the quota spent.
const rateLimited = () => ({
  ok: false,
  status: 403,
  headers: new Map([["x-ratelimit-remaining", "0"]]),
  json: async () => ({ message: "API rate limit exceeded" }),
});
// A 200 whose body is not JSON (an HTML error page from a proxy, say).
const badJson = () => ({
  ok: true,
  status: 200,
  json: async () => {
    throw new SyntaxError("Unexpected token '<'");
  },
});

const COMMITS_URL = `https://api.github.com/repos/${OWNER}/${REPO}/commits?path=${encodeURIComponent(
  "designs/calibration-cube"
)}&per_page=20`;
const CUBE = { owner: OWNER, repo: REPO, design: "calibration-cube" };

test("fetchDesignCommits returns the API's commit array as an ok seam result", async () => {
  const commits = [commit({ date: "2026-08-06T00:00:00Z", message: "Add design: calibration-cube", login: "shaiss" })];
  const fetchImpl = stubFetch({ [COMMITS_URL]: commits });
  const got = await fetchDesignCommits({ fetchImpl, ...CUBE });
  assert.equal(got.status, SEAM.OK);
  assert.equal(got.reason, null);
  assert.equal(got.items.length, 1);
  assert.equal(got.items[0].commit.message, "Add design: calibration-cube");
});

test("fetchDesignCommits: a path with no commits (200 []) is empty, not unavailable", async () => {
  const got = await fetchDesignCommits({ fetchImpl: stubFetch({ [COMMITS_URL]: [] }), ...CUBE });
  assert.deepEqual(got, { status: SEAM.EMPTY, items: [], reason: null });
});

test("fetchDesignCommits: a 403 rate limit is unavailable, never empty", async () => {
  // The measured failure: an anonymous rate-limited deploy logged
  // "history: 0 commit(s)" and built green. It must be told apart from empty.
  const got = await fetchDesignCommits({ fetchImpl: stubFetch({ [COMMITS_URL]: rateLimited }), ...CUBE });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.equal(got.reason, "HTTP 403, rate limited");
  assert.deepEqual(got.items, [], "still no commits — the best-effort contract holds");
});

test("fetchDesignCommits: a 404 means the repo is missing, so unavailable", async () => {
  const got = await fetchDesignCommits({ fetchImpl: stubFetch({}), ...CUBE }); // every URL 404s
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.equal(got.reason, "HTTP 404");
});

test("fetchDesignCommits: a network error is unavailable", async () => {
  const fetchImpl = stubFetch({ [COMMITS_URL]: new Error("getaddrinfo ENOTFOUND") });
  const got = await fetchDesignCommits({ fetchImpl, ...CUBE });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.match(got.reason, /^network error: /);
  assert.deepEqual(got.items, []);
});

test("fetchDesignCommits: an unparseable body is unavailable", async () => {
  const got = await fetchDesignCommits({ fetchImpl: stubFetch({ [COMMITS_URL]: badJson }), ...CUBE });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.equal(got.reason, "unparseable JSON body");
});

test("fetchDesignCommits: a 200 that is not a commit list is unavailable", async () => {
  const fetchImpl = stubFetch({ [COMMITS_URL]: { message: "API rate limit exceeded" } });
  const got = await fetchDesignCommits({ fetchImpl, ...CUBE });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.equal(got.reason, "unexpected response body");
});

test("fetchDesignCommits aborts a hung request after the timeout: unavailable", async () => {
  // A fetch that never resolves on its own, but honors the abort signal the
  // way the platform fetch does — the bounded timeout must unstick the build.
  const hung = (_url, { signal } = {}) =>
    new Promise((_resolve, reject) => {
      signal?.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
    });
  const got = await fetchDesignCommits({ fetchImpl: hung, ...CUBE, timeoutMs: 20 });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.equal(got.reason, "timeout after 20 ms");
});

test("fetchDesignCommits without a design or a fetch impl is unavailable, not a throw", async () => {
  const noDesign = await fetchDesignCommits({ fetchImpl: stubFetch({}), owner: OWNER, repo: REPO });
  assert.equal(noDesign.status, SEAM.UNAVAILABLE);
  assert.deepEqual(noDesign.items, []);
  const noFetch = await fetchDesignCommits({ fetchImpl: null, owner: OWNER, repo: REPO, design: "x" });
  assert.equal(noFetch.status, SEAM.UNAVAILABLE);
  assert.deepEqual(noFetch.items, []);
});

test("history disabled (the local/CI default) is off, and nothing is fetched", async () => {
  let fetched = false;
  const fetchImpl = async () => {
    fetched = true;
    return { ok: true, status: 200, json: async () => [] };
  };
  const got = await runSeam(shouldFetchHistory({}), () => fetchDesignCommits({ fetchImpl, ...CUBE }));
  assert.equal(got.status, SEAM.OFF);
  assert.equal(fetched, false);
});

// --- the History tab as it renders each status ---

const EVENT = { date: "2026-08-08", source: "decision-log", sourceTag: "decision · PM.md", text: "a committed decision", detail: "", handle: null };

test("historySlot: an unavailable git fetch shows the note, and committed events still render", () => {
  const html = historySlot("calibration-cube", { events: [EVENT], gitStatus: SEAM.UNAVAILABLE });
  assert.ok(html.includes(HISTORY_UNAVAILABLE), "the couldn't-load note is shown");
  assert.equal(
    HISTORY_UNAVAILABLE,
    "Git history couldn't be loaded for this deploy; the next deploy retries."
  );
  assert.match(html, /<ol class="timeline">/, "the committed timeline is still there");
  assert.match(html, /a committed decision/);
  // and with nothing committed either, the note sits beside the empty state
  const bare = historySlot("calibration-cube", { events: [], gitStatus: SEAM.UNAVAILABLE });
  assert.ok(bare.includes(HISTORY_UNAVAILABLE));
  assert.match(bare, /class="history-empty/);
});

test("historySlot: off / ok / empty render exactly as before — no note", () => {
  const before = historySlot("calibration-cube", { events: [EVENT] }); // pre-seam call shape
  for (const gitStatus of [SEAM.OFF, SEAM.OK, SEAM.EMPTY]) {
    const html = historySlot("calibration-cube", { events: [EVENT], gitStatus });
    assert.equal(html, before, `${gitStatus} is byte-identical to the default render`);
    assert.ok(!html.includes(HISTORY_UNAVAILABLE));
  }
});

test("shouldFetchHistory: on for Vercel or explicit opt-in, off otherwise", () => {
  assert.equal(shouldFetchHistory({}), false); // local / CI default: deterministic, no network
  assert.equal(shouldFetchHistory({ VERCEL: "1" }), true); // the deploy has network
  assert.equal(shouldFetchHistory({ SITE_FETCH_HISTORY: "1" }), true);
  assert.equal(shouldFetchHistory({ VERCEL: "1", SITE_FETCH_HISTORY: "0" }), false); // explicit off wins
});
