// The deploy-time fetch seams' shared status — history.mjs (git commits),
// releases.mjs (release manifests) and decisions.mjs (the needs-decision
// queue) all report through this.
//
// Each seam is best-effort: the build never fails because one is down. But
// "best-effort" used to mean every failure collapsed into the same empty result
// a genuinely empty source returns — measured, an anonymous 403 rate limit
// logged "history: 0 commit(s)" in a green build, and a 401 logged "queue
// empty" while the header bell told every visitor "You're all caught up". A
// reader could not tell "nothing there" from "we couldn't look". So every seam
// now says HOW its fetch went, alongside what it fetched:
//
//   off          fetching disabled this build (the local/CI default) — every
//                page renders exactly the committed baseline, as before
//   ok           fetched, and there is something to show
//   empty        fetched fine, and there is genuinely nothing there
//   unavailable  any failure — offline, non-2xx, rate limit, timeout,
//                unparseable or unexpected body. The page says so instead of
//                passing the gap off as "nothing there", and the build log
//                prints a WARN naming the seam and the failure class.
//
// A seam result is { status, items, reason }: `items` is the seam's own payload
// (a commit array, a design→manifest Map, decision rows) and stays the empty
// payload on failure, so a caller that only reads `items` keeps today's
// degrade-to-nothing behaviour; `reason` is the failure class an `unavailable`
// result carries ("HTTP 403, rate limited", "timeout after 10000 ms", ...) and
// null otherwise. Pure except fetchJson, whose `fetch` is injected.

export const SEAM = Object.freeze({
  OFF: "off",
  OK: "ok",
  EMPTY: "empty",
  UNAVAILABLE: "unavailable",
});

const STATUSES = new Set(Object.values(SEAM));

/** One seam's outcome: what it fetched, how the fetch went, and why if not. */
export function seamResult(status, items, reason = null) {
  return { status, items, reason: status === SEAM.UNAVAILABLE ? reason || "unknown failure" : null };
}

/** A fetch that succeeded: `ok` when it found something, `empty` when not. */
export function fetchedResult(items) {
  const n = items instanceof Map ? items.size : Array.isArray(items) ? items.length : 0;
  return seamResult(n ? SEAM.OK : SEAM.EMPTY, items);
}

/**
 * Run one seam: `off` (and `load` never called) when the seam is disabled this
 * build, otherwise whatever `load` reports. The seams' own fetchers never throw,
 * but this is the build's last line of the best-effort contract — an unexpected
 * throw, or a loader that forgets to report a status, becomes `unavailable`
 * rather than a red build. `emptyItems` is the payload an off/failed seam
 * carries ([] for a list, a Map for releases).
 */
export async function runSeam(enabled, load, emptyItems = []) {
  if (!enabled) return seamResult(SEAM.OFF, emptyItems);
  try {
    const r = await load();
    if (r && typeof r === "object" && STATUSES.has(r.status)) return r;
    return seamResult(SEAM.UNAVAILABLE, emptyItems, "seam reported no status");
  } catch (err) {
    return seamResult(SEAM.UNAVAILABLE, emptyItems, `error: ${err?.message ?? err}`);
  }
}

/** The failure class of a non-2xx response; a spent quota is named as such. */
function httpReason(res) {
  const status = Number.isInteger(res.status) ? res.status : "?";
  const remaining =
    res.headers && typeof res.headers.get === "function"
      ? res.headers.get("x-ratelimit-remaining")
      : null;
  // GitHub signals an exhausted quota as a 403 with x-ratelimit-remaining: 0
  // (primary limit) or a 429 (secondary limit); either is "come back later".
  const limited = status === 429 || (status === 403 && remaining === "0");
  return `HTTP ${status}${limited ? ", rate limited" : ""}`;
}

/** The failure class of a thrown fetch (DNS, refused, reset, TLS ...). */
function networkReason(err) {
  const detail = err?.cause?.code || err?.code || err?.message || String(err);
  return `network error: ${detail}`;
}

/**
 * Impure boundary shared by every seam — GET one URL and parse it as JSON,
 * classifying every way that can fail instead of collapsing them:
 *   { ok: true,  status, body }      a 2xx with a parseable JSON body
 *   { ok: false, status, reason }    a non-2xx (`status` is the HTTP code)
 *   { ok: false, status: null, reason }  no response: network error, timeout,
 *                                    unparseable body, no fetch available
 * Never throws. Bounded: the request AND the body read abort after timeoutMs,
 * so a hung connection cannot stall the deploy build. `fetchImpl` is injected
 * so tests drive it with a stub and never touch the network.
 */
export async function fetchJson(fetchImpl, url, { headers = {}, timeoutMs = 10000 } = {}) {
  if (typeof fetchImpl !== "function") {
    return { ok: false, status: null, reason: "no fetch implementation" };
  }
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const timeout = `timeout after ${timeoutMs} ms`;
  try {
    let res;
    try {
      res = await fetchImpl(url, { headers, signal: controller.signal });
    } catch (err) {
      return { ok: false, status: null, reason: timedOut ? timeout : networkReason(err) };
    }
    if (!res || typeof res !== "object") {
      return { ok: false, status: null, reason: "no response" };
    }
    if (!res.ok) return { ok: false, status: res.status ?? null, reason: httpReason(res) };
    try {
      return { ok: true, status: res.status ?? 200, body: await res.json() };
    } catch {
      return { ok: false, status: null, reason: timedOut ? timeout : "unparseable JSON body" };
    }
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Pure: several failure reasons → one short summary for a log line. One
 * distinct reason prints as itself; several print most-frequent first with a
 * count each ("HTTP 403, rate limited ×3; timeout after 10000 ms ×1").
 */
export function reasonSummary(reasons = []) {
  const counts = new Map();
  for (const r of reasons) {
    const key = String(r || "unknown failure");
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  if (counts.size <= 1) return [...counts.keys()][0] || "unknown failure";
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1]) // stable: ties keep first-seen order
    .map(([r, n]) => `${r} ×${n}`)
    .join("; ");
}

/**
 * Pure: the build-log WARN line for an unavailable seam, e.g.
 *   WARN history: fetch unavailable for 4 design(s) (HTTP 403, rate limited) — History tabs show 'unavailable'
 * `count` + `noun` scope it when the seam fetches per item (omit both for a
 * whole-seam failure); `effect` says what a reader of the site will see.
 */
export function unavailableWarning(seam, { reasons = [], count = null, noun = "item", effect = "" } = {}) {
  const scope = count == null ? "" : ` for ${count} ${noun}(s)`;
  return `WARN ${seam}: fetch unavailable${scope} (${reasonSummary(reasons)})${
    effect ? ` — ${effect}` : ""
  }`;
}
