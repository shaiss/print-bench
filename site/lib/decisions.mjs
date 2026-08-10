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
//     queue over the GitHub search API, with an injectable `fetch`. BEST-EFFORT
//     — any failure (offline, rate limit, non-2xx, unparseable body) yields []
//     and the section simply doesn't render, never a broken build.
//
// Determinism (the clarified site rule — build vs. deploy vs. served output):
// the fetch is deploy-scoped (shouldFetchDecisions). A plain ./scripts/site.sh
// performs no network I/O and is byte-for-byte reproducible; the Vercel deploy,
// which has network, is where the live queue appears. This is surfacing of real
// repository state (open, labelled issues/PRs), not invention — every row links
// to a real issue the label already keys on.

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
 * Best-effort: returns [] on any failure (no match, non-2xx, network error,
 * unparseable body), so the caller renders no section and the build never
 * breaks. `fetchImpl` is injectable so tests never touch the network; `token`
 * (optional) lifts the unauthenticated rate limit but is never required for a
 * public repo.
 *
 * The search API ranks issues and PRs together; `repo:` scopes it, `is:open`
 * keeps only unresolved ones, and `label:` is the unspoofable state the
 * pipeline keys on (`docs/decision-gate.md`). Created-ascending so the oldest
 * parked decision leads the queue — the one waiting longest for a human.
 *
 * A bounded timeout keeps a hung connection from stalling the deploy build
 * (the same bound history.mjs added): abort after timeoutMs, and the
 * AbortError lands in the same best-effort catch as any other failure → [].
 */
export async function fetchOpenDecisions({
  fetchImpl = globalThis.fetch,
  owner,
  repo,
  label = "needs-decision",
  token,
  perPage = 30,
  timeoutMs = 10000,
} = {}) {
  if (typeof fetchImpl !== "function") return [];
  const headers = { Accept: "application/vnd.github+json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const q = `repo:${owner}/${repo} is:open label:${label}`;
  const url = `${GITHUB_API}/search/issues?q=${encodeURIComponent(
    q
  )}&per_page=${perPage}&sort=created&order=ascending`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetchImpl(url, { headers, signal: controller.signal });
    if (!res || !res.ok) return []; // no match / rate limit / error → no section
    const body = await res.json();
    const items = body && Array.isArray(body.items) ? body.items : [];
    return searchToDecisions(items);
  } catch {
    return []; // offline / DNS / rate limit / timeout → no section
  } finally {
    clearTimeout(timer);
  }
}
