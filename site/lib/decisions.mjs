// The read-only "Decisions awaiting a human" queue for the product site — the
// second buildable follow-up to the HITL decision gate (#161; see
// `docs/decision-gate.md` §Follow-ups), tracked as #181.
//
// The decision gate's surface half is the `needs-decision` label + the saved
// search `is:open label:needs-decision`. This turns that search into a
// read-only section on the index page so a maintainer can see, at a glance,
// what the autonomy pipeline has parked for them. It adds NO deciding power:
// the section links out to the issues, and resolving a decision still goes
// through `/decide`. Cloning site/lib/releases.mjs (and its evolved form
// site/lib/history.mjs) exactly:
//   - searchToDecisions() is PURE: GitHub search-API issue objects → the
//     render model a template section consumes. Unit-tested, no network.
//   - fetchOpenDecisions() is the impure boundary: the open needs-decision
//     queue over the GitHub search API, every page of it, with an injectable
//     `fetch`. BEST-EFFORT — any failure (offline, rate limit, non-2xx,
//     unparseable body) yields no rows, never a broken build — but it reports
//     a seam status (seam.mjs) beside them, so an `unavailable` queue puts the
//     bell in a "couldn't load" state instead of "You're all caught up".
//
// Determinism (the clarified site rule — build vs. deploy vs. served output):
// the fetch is deploy-scoped (shouldFetchDecisions). A plain ./scripts/site.sh
// performs no network I/O and is byte-for-byte reproducible; the Vercel deploy,
// which has network, is where the live queue appears. This is surfacing of real
// repository state (open, labelled issues/PRs), not invention — every row links
// to a real issue the label already keys on.

import { SEAM, seamResult, fetchedResult, fetchJson } from "./seam.mjs";

const GITHUB_API = "https://api.github.com";

/**
 * Whether to fetch the decision queue this build. On (Vercel, or
 * SITE_FETCH_DECISIONS=1) the index page gains a live "Decisions awaiting a
 * human" section; off (default, incl. CI and local `site.sh`) the build stays
 * deterministic and offline and shows no section. Mirrors releases.mjs's
 * shouldFetchReleases and history.mjs's shouldFetchHistory so the three
 * deploy-time sources arm independently.
 */
export function shouldFetchDecisions(env = process.env) {
  if (env.SITE_FETCH_DECISIONS === "1") return true;
  if (env.SITE_FETCH_DECISIONS === "0") return false;
  return Boolean(env.VERCEL); // Vercel sets VERCEL=1 in the build environment
}

/** First line of a title, trimmed and length-capped for one row. */
function trimTitle(title) {
  const first = String(title ?? "").trim();
  if (!first) return "";
  const one = first.split("\n")[0].trim();
  return one.length > 140 ? `${one.slice(0, 139).trimEnd()}…` : one;
}

/**
 * Pure: GitHub search-API issue objects (as `GET /search/issues` returns them
 * in `items`) → the render model for one decision row
 *   { number, title, url, kind }
 * `kind` is "pull" when the item carries a `pull_request` object, else
 * "issue", so a row can be labelled honestly (the queue may hold either — a
 * PR can be parked for a decision just as an issue can). Skipped: any item
 * missing a usable number, title or html_url, and any non-array/junk input.
 */
export function searchToDecisions(items) {
  if (!Array.isArray(items)) return [];
  const out = [];
  for (const it of items) {
    if (!it || typeof it !== "object") continue;
    const number = typeof it.number === "number" ? it.number : null;
    const title = trimTitle(it.title);
    const url = typeof it.html_url === "string" ? it.html_url : null;
    if (number === null || !title || !url) continue;
    const kind =
      it.pull_request && typeof it.pull_request === "object" ? "pull" : "issue";
    out.push({ number, title, url, kind });
  }
  return out;
}

/**
 * Impure boundary — the open `needs-decision` queue over the GitHub search
 * API, scoped to one repo so only THIS repository's parked decisions appear.
 * Returns a seam result (seam.mjs) and never throws, so the build never breaks:
 *   ok           items: every open decision row, across all pages
 *   empty        the search ran and nothing is parked — "all caught up" is true
 *   unavailable  items: [], with the failure class in `reason` — a non-2xx on
 *                any page, network error, timeout, unparseable body, a body
 *                with no `items` array, or an answer that is not the whole
 *                queue (below). A page-2 failure is unavailable too: showing
 *                the first page's rows as the whole queue is the undercount
 *                this replaces, so no partial queue is returned.
 * `fetchImpl` is injectable so tests never touch the network; `token`
 * (optional) lifts the unauthenticated rate limit but is never required for a
 * public repo.
 *
 * The search API ranks issues and PRs together; `repo:` scopes it, `is:open`
 * keeps only unresolved ones, and `label:` is the unspoofable state the
 * pipeline keys on (`docs/decision-gate.md`). Created-ascending so the oldest
 * parked decision leads the queue — the one waiting longest for a human. The
 * API spells that `order=asc` (its only values are asc/desc) and silently
 * ignores anything else: this once sent `order=ascending`, and the live queue
 * came back newest-first with no error to say so.
 *
 * Paginated: it requests `perPage` (the API's maximum, 100) per page and
 * follows pages until a short page or `total_count` rows have arrived, capped
 * at `maxPages` — 10 × 100 is the search API's own 1000-result ceiling. One
 * page used to be all it read (30 rows), so a 53-decision queue showed 30.
 * Rows are de-duplicated by number in case the ranking shifts between pages.
 * Each page is bounded by `timeoutMs` (fetchJson), so a hung connection cannot
 * stall the deploy build.
 *
 * A 200 is not proof the queue arrived whole, and a short count shown as the
 * queue is the same lie as "all caught up" — so these are `unavailable` too:
 * GitHub flagging the search `incomplete_results` (it timed out server-side and
 * answered with what it had); a page whose items yield no usable row (the shape
 * drifted under searchToDecisions); fewer distinct rows than the latest
 * `total_count` when the pages ran out; and hitting `maxPages` with the queue
 * still going. Measured against the latest page's `total_count` because a
 * decision resolved between two page reads lowers both sides by one, so a race
 * keeps the count honest rather than reading as a failure.
 */
export async function fetchOpenDecisions({
  fetchImpl = globalThis.fetch,
  owner,
  repo,
  label = "needs-decision",
  token,
  perPage = 100,
  maxPages = 10,
  timeoutMs = 10000,
} = {}) {
  const headers = { Accept: "application/vnd.github+json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const q = encodeURIComponent(`repo:${owner}/${repo} is:open label:${label}`);
  const rows = [];
  const seen = new Set();
  let total = null; // the latest page's total_count, when the API sent one
  let complete = false;
  for (let page = 1; page <= maxPages; page++) {
    const url = `${GITHUB_API}/search/issues?q=${q}&per_page=${perPage}&page=${page}&sort=created&order=asc`;
    const got = await fetchJson(fetchImpl, url, { headers, timeoutMs });
    const where = page > 1 ? ` on page ${page}` : "";
    if (!got.ok) return seamResult(SEAM.UNAVAILABLE, [], `${got.reason}${where}`);
    const body = got.body;
    if (!body || !Array.isArray(body.items)) {
      return seamResult(SEAM.UNAVAILABLE, [], `unexpected response body${where}`);
    }
    if (body.incomplete_results === true) {
      return seamResult(SEAM.UNAVAILABLE, [], `incomplete search results${where}`);
    }
    const parsed = searchToDecisions(body.items);
    if (body.items.length && !parsed.length) {
      return seamResult(SEAM.UNAVAILABLE, [], `unexpected response body${where}`);
    }
    for (const row of parsed) {
      if (seen.has(row.number)) continue;
      seen.add(row.number);
      rows.push(row);
    }
    if (Number.isInteger(body.total_count)) total = body.total_count;
    // Done on a short page (the last one), or once every distinct decision the
    // search counted has arrived. (A repeated row doesn't count toward it, so a
    // ranking shift costs one more page, not a row.)
    if (body.items.length < perPage || (total !== null && rows.length >= total)) {
      complete = true;
      break;
    }
  }
  if (!complete) {
    return seamResult(SEAM.UNAVAILABLE, [], `queue longer than ${maxPages} pages`);
  }
  if (total !== null && rows.length < total) {
    return seamResult(SEAM.UNAVAILABLE, [], `partial results: ${rows.length} of ${total}`);
  }
  return fetchedResult(rows);
}
