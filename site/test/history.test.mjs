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
// only these catch it.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  commitsToEvents,
  fetchDesignCommits,
  shouldFetchHistory,
} from "../lib/history.mjs";

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

function stubFetch(routes) {
  return async (url) => {
    if (!(url in routes)) return { ok: false, status: 404, json: async () => ({}) };
    const body = routes[url];
    if (body instanceof Error) throw body;
    return { ok: true, status: 200, json: async () => body };
  };
}

const COMMITS_URL = `https://api.github.com/repos/${OWNER}/${REPO}/commits?path=${encodeURIComponent(
  "designs/calibration-cube"
)}&per_page=20`;

test("fetchDesignCommits returns the API's commit array", async () => {
  const commits = [commit({ date: "2026-08-06T00:00:00Z", message: "Add design: calibration-cube", login: "shaiss" })];
  const fetchImpl = stubFetch({ [COMMITS_URL]: commits });
  const got = await fetchDesignCommits({ fetchImpl, owner: OWNER, repo: REPO, design: "calibration-cube" });
  assert.equal(got.length, 1);
  assert.equal(got[0].commit.message, "Add design: calibration-cube");
});

test("fetchDesignCommits degrades to [] on a 404 (unknown design path)", async () => {
  const fetchImpl = stubFetch({}); // every URL 404s
  const got = await fetchDesignCommits({ fetchImpl, owner: OWNER, repo: REPO, design: "nope" });
  assert.deepEqual(got, []);
});

test("fetchDesignCommits degrades to [] on a network error", async () => {
  const fetchImpl = stubFetch({ [COMMITS_URL]: new Error("getaddrinfo ENOTFOUND") });
  const got = await fetchDesignCommits({ fetchImpl, owner: OWNER, repo: REPO, design: "calibration-cube" });
  assert.deepEqual(got, []);
});

test("fetchDesignCommits degrades to [] when the body is not an array", async () => {
  const fetchImpl = stubFetch({ [COMMITS_URL]: { message: "API rate limit exceeded" } });
  const got = await fetchDesignCommits({ fetchImpl, owner: OWNER, repo: REPO, design: "calibration-cube" });
  assert.deepEqual(got, []);
});

test("fetchDesignCommits returns [] without a design or a fetch impl", async () => {
  assert.deepEqual(await fetchDesignCommits({ fetchImpl: stubFetch({}), owner: OWNER, repo: REPO }), []);
  assert.deepEqual(await fetchDesignCommits({ fetchImpl: null, owner: OWNER, repo: REPO, design: "x" }), []);
});

test("shouldFetchHistory: on for Vercel or explicit opt-in, off otherwise", () => {
  assert.equal(shouldFetchHistory({}), false); // local / CI default: deterministic, no network
  assert.equal(shouldFetchHistory({ VERCEL: "1" }), true); // the deploy has network
  assert.equal(shouldFetchHistory({ SITE_FETCH_HISTORY: "1" }), true);
  assert.equal(shouldFetchHistory({ VERCEL: "1", SITE_FETCH_HISTORY: "0" }), false); // explicit off wins
});
