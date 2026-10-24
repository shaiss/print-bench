// The deploy-time fetch seams' shared status (lib/seam.mjs).
//
// Why this exists: history, releases and decisions used to collapse every
// failure into the empty result a genuinely empty source returns, so a 403
// rate limit built green as "0 commits" and a 401 told visitors the decision
// queue was "all caught up". seam.mjs is the one place the four statuses
// (off / ok / empty / unavailable) and the failure classes are defined, so it
// is pinned here directly — each failure class with the response that
// produces it, and the negative controls: a 2xx is never a failure, a
// disabled seam never calls its loader, a throwing loader never throws.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  SEAM,
  seamResult,
  fetchedResult,
  runSeam,
  fetchJson,
  reasonSummary,
  unavailableWarning,
} from "../lib/seam.mjs";

/** A stub response, optionally with headers (a Map stands in for Headers). */
function res(status, body, headers = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Map(Object.entries(headers)),
    json: async () => {
      if (body instanceof Error) throw body;
      return body;
    },
  };
}
const once = (r) => async () => r;

test("the four statuses are exactly off / ok / empty / unavailable", () => {
  assert.deepEqual(Object.values(SEAM), ["off", "ok", "empty", "unavailable"]);
});

test("fetchJson returns the parsed body of a 2xx", async () => {
  const got = await fetchJson(once(res(200, [1, 2])), "u");
  assert.deepEqual(got, { ok: true, status: 200, body: [1, 2] });
});

test("fetchJson classifies a non-2xx by its HTTP status", async () => {
  assert.deepEqual(await fetchJson(once(res(401, {})), "u"), {
    ok: false,
    status: 401,
    reason: "HTTP 401",
  });
  // a plain 403 (forbidden, quota left) is not a rate limit …
  const forbidden = await fetchJson(once(res(403, {}, { "x-ratelimit-remaining": "12" })), "u");
  assert.equal(forbidden.reason, "HTTP 403");
  // … a 403 with the quota spent, or a 429, is
  const limited = await fetchJson(once(res(403, {}, { "x-ratelimit-remaining": "0" })), "u");
  assert.equal(limited.reason, "HTTP 403, rate limited");
  assert.equal(limited.status, 403);
  assert.equal((await fetchJson(once(res(429, {})), "u")).reason, "HTTP 429, rate limited");
  // a stub with no headers at all still classifies
  assert.equal((await fetchJson(once({ ok: false, status: 500, json: async () => ({}) }), "u")).reason, "HTTP 500");
});

test("fetchJson classifies a thrown fetch as a network error", async () => {
  const err = new TypeError("fetch failed");
  err.cause = { code: "ENOTFOUND" };
  const got = await fetchJson(async () => {
    throw err;
  }, "u");
  assert.deepEqual(got, { ok: false, status: null, reason: "network error: ENOTFOUND" });
  const plain = await fetchJson(async () => {
    throw new Error("socket hang up");
  }, "u");
  assert.equal(plain.reason, "network error: socket hang up");
});

test("fetchJson classifies an unparseable 2xx body", async () => {
  const got = await fetchJson(once(res(200, new SyntaxError("Unexpected token <"))), "u");
  assert.deepEqual(got, { ok: false, status: null, reason: "unparseable JSON body" });
});

test("fetchJson aborts a hung request after the timeout", async () => {
  // never resolves on its own, but honours the abort signal like platform fetch
  const hung = (_url, { signal } = {}) =>
    new Promise((_resolve, reject) => {
      signal?.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
    });
  const got = await fetchJson(hung, "u", { timeoutMs: 20 });
  assert.deepEqual(got, { ok: false, status: null, reason: "timeout after 20 ms" });
});

test("fetchJson sends the caller's headers and a signal", async () => {
  let seen;
  await fetchJson(async (url, init) => {
    seen = { url, init };
    return res(200, {});
  }, "https://x/y", { headers: { Accept: "a" } });
  assert.equal(seen.url, "https://x/y");
  assert.deepEqual(seen.init.headers, { Accept: "a" });
  assert.ok(seen.init.signal, "every request is abortable");
});

test("fetchJson without a fetch implementation is a failure, not a throw", async () => {
  assert.deepEqual(await fetchJson(null, "u"), {
    ok: false,
    status: null,
    reason: "no fetch implementation",
  });
});

test("seamResult carries a reason only for unavailable; fetchedResult picks ok vs empty", () => {
  assert.deepEqual(seamResult(SEAM.OK, [1], "ignored"), { status: "ok", items: [1], reason: null });
  assert.equal(seamResult(SEAM.UNAVAILABLE, []).reason, "unknown failure");
  assert.equal(fetchedResult([1]).status, SEAM.OK);
  assert.equal(fetchedResult([]).status, SEAM.EMPTY);
  assert.equal(fetchedResult(new Map([["a", 1]])).status, SEAM.OK);
  assert.equal(fetchedResult(new Map()).status, SEAM.EMPTY);
});

test("runSeam: a disabled seam is off and never calls its loader", async () => {
  let called = false;
  const got = await runSeam(false, async () => {
    called = true;
    return fetchedResult([1]);
  });
  assert.equal(got.status, SEAM.OFF);
  assert.deepEqual(got.items, []);
  assert.equal(called, false, "off means no network I/O at all");
  const map = await runSeam(false, async () => null, new Map());
  assert.ok(map.items instanceof Map, "the off payload is the caller's empty shape");
});

test("runSeam: an enabled seam reports its loader's result", async () => {
  const got = await runSeam(true, async () => fetchedResult([1, 2]));
  assert.deepEqual(got, { status: "ok", items: [1, 2], reason: null });
});

test("runSeam: a throwing or status-less loader is unavailable, never a throw", async () => {
  const threw = await runSeam(true, async () => {
    throw new Error("boom");
  });
  assert.equal(threw.status, SEAM.UNAVAILABLE);
  assert.equal(threw.reason, "error: boom");
  assert.deepEqual(threw.items, []);
  const bare = await runSeam(true, async () => [1, 2]); // a pre-seam return shape
  assert.equal(bare.status, SEAM.UNAVAILABLE);
});

test("reasonSummary prints one reason as itself, several with counts", () => {
  assert.equal(reasonSummary(["HTTP 403"]), "HTTP 403");
  assert.equal(reasonSummary(["HTTP 403", "HTTP 403"]), "HTTP 403");
  assert.equal(
    reasonSummary(["timeout after 5 ms", "HTTP 403", "HTTP 403", "HTTP 403"]),
    "HTTP 403 ×3; timeout after 5 ms ×1"
  );
  assert.equal(reasonSummary([]), "unknown failure");
});

test("unavailableWarning names the seam, scope and failure class", () => {
  assert.equal(
    unavailableWarning("history", {
      reasons: ["HTTP 403", "HTTP 403", "HTTP 403", "HTTP 403"],
      count: 4,
      noun: "design",
      effect: "History tabs show 'unavailable'",
    }),
    "WARN history: fetch unavailable for 4 design(s) (HTTP 403) — History tabs show 'unavailable'"
  );
  assert.equal(
    unavailableWarning("decisions", { reasons: ["HTTP 401"] }),
    "WARN decisions: fetch unavailable (HTTP 401)"
  );
});
