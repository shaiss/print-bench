// Git-history events for the "History of work together" timeline — the first
// NON-committed source folded into the timeline, feeding the adapter seam
// timeline.mjs (issue #126) was built to receive.
//
// The timeline's other sources read COMMITTED files (the PM.md decision log,
// the NOTES.md field-test log). This reads the repo's own git history for a
// design over the GitHub API at deploy time, following releases.mjs exactly:
//
//   - commitsToEvents() is PURE: GitHub commit objects → timeline events.
//     Unit-tested, no network. Attribution is derived from a committed
//     login→handle map (a member's `github:` field), honest by construction —
//     a commit author with no committed mapping renders UNATTRIBUTED rather
//     than guessed, the same "attribution only where derivable" contract the
//     committed sources hold.
//   - fetchDesignCommits() is the impure boundary: the design's path-filtered
//     commits over the GitHub API, with an injectable `fetch`. BEST-EFFORT —
//     any failure (offline, rate limit, non-2xx) yields [] and the timeline
//     simply shows no git events, never a broken build.
//
// Determinism (the clarified site rule — build vs. deploy vs. served output):
// the fetch is deploy-scoped (shouldFetchHistory). A plain ./scripts/site.sh
// performs no network I/O and is byte-for-byte reproducible; the Vercel deploy,
// which has network, is where live git events appear. This is provenance, not
// invention — every event is a real commit in this repo's own history, labelled
// `commit · git` so a reader sees exactly where it came from. Product-scoped by
// the `path=designs/<design>` filter: only work on THIS product appears.

const GITHUB_API = "https://api.github.com";

/**
 * Whether to fetch git history this build. On (Vercel, or SITE_FETCH_HISTORY=1)
 * the team timeline gains live commit events; off (default, incl. CI and local
 * `site.sh`) the build stays deterministic and offline and the timeline is
 * committed-only. Mirrors releases.mjs's shouldFetchReleases so the two
 * deploy-time sources arm independently.
 */
export function shouldFetchHistory(env = process.env) {
  if (env.SITE_FETCH_HISTORY === "1") return true;
  if (env.SITE_FETCH_HISTORY === "0") return false;
  return Boolean(env.VERCEL); // Vercel sets VERCEL=1 in the build environment
}

/** First line of a commit message, trimmed and length-capped for one row. */
function commitSummary(message) {
  const first = String(message ?? "").split("\n")[0].trim();
  return first.length > 140 ? `${first.slice(0, 139).trimEnd()}…` : first;
}

/**
 * Pure: GitHub commit objects (as `GET /repos/:o/:r/commits` returns them) →
 * timeline events for one design, in the timeline's event shape
 *   { date, source: "git", sourceTag: "commit · git", text, detail: "", handle }
 * `readTimeline` re-sorts, so the API's newest-first order here is not
 * load-bearing. Skipped: a merge commit (2+ parents — "Merge branch 'main'
 * into …" is branch bookkeeping, not work on the product), and any commit with
 * no usable date or an empty summary. `handle` is loginToHandle.get(author
 * login) or null: attribution only where the committed `github:` map derives it.
 */
export function commitsToEvents(commits, { loginToHandle = new Map() } = {}) {
  if (!Array.isArray(commits)) return [];
  const events = [];
  for (const c of commits) {
    if (!c || typeof c !== "object") continue;
    if (Array.isArray(c.parents) && c.parents.length > 1) continue; // merge → skip
    const commit = c.commit;
    const rawDate = commit?.author?.date ?? commit?.committer?.date ?? null;
    if (!rawDate) continue;
    const date = String(rawDate).slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) continue;
    const text = commitSummary(commit?.message);
    if (!text) continue;
    const login =
      c.author && typeof c.author.login === "string" ? c.author.login : null;
    // Case-insensitive: loginToHandle is keyed by canonical lowercase login
    // (loginHandleMap), and author.login can arrive in any casing.
    const handle = (login && loginToHandle.get(login.toLowerCase())) || null;
    events.push({ date, source: "git", sourceTag: "commit · git", text, detail: "", handle });
  }
  return events;
}

/**
 * Build the canonical login→handle attribution map from resolved team members.
 * Keys are lowercased (GitHub logins are case-insensitive), so a profile's
 * `github: Shaiss` matches an API `author.login` of `shaiss`. Two members
 * claiming the same login is a data error, not a silent last-wins overwrite:
 * it is collected as a problem the caller fails the build on (the resolve-or-
 * fail contract the rest of the team layer holds). Returns { map, problems }.
 */
export function loginHandleMap(members = []) {
  const map = new Map();
  const problems = [];
  for (const m of members) {
    if (!m || !m.github) continue;
    const login = m.github.toLowerCase();
    const existing = map.get(login);
    if (existing && existing !== m.handle) {
      problems.push(`github login '${login}' is claimed by both '${existing}' and '${m.handle}'`);
      continue;
    }
    map.set(login, m.handle);
  }
  return { map, problems };
}

/**
 * Impure boundary — a design's commits over the GitHub API, path-filtered to
 * `designs/<design>` so only work on THIS product appears (the #122 product-
 * scoping principle). Best-effort: returns [] on any failure (no such design,
 * non-2xx, network error, unparseable body), so the caller wraps nothing and
 * the build never breaks. `fetchImpl` is injectable so tests never touch the
 * network; `token` (optional) lifts the unauthenticated rate limit but is
 * never required for a public repo.
 */
export async function fetchDesignCommits({
  fetchImpl = globalThis.fetch,
  owner,
  repo,
  design,
  token,
  perPage = 20,
  timeoutMs = 10000,
} = {}) {
  if (typeof fetchImpl !== "function" || !design) return [];
  const headers = { Accept: "application/vnd.github+json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const path = `designs/${design}`;
  const url = `${GITHUB_API}/repos/${owner}/${repo}/commits?path=${encodeURIComponent(
    path
  )}&per_page=${perPage}`;
  // Bound the request so a hung connection cannot stall the deploy build: abort
  // after timeoutMs, and the AbortError lands in the same best-effort catch as
  // any other failure → [], no git events. The timer is always cleared.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetchImpl(url, { headers, signal: controller.signal });
    if (!res || !res.ok) return []; // no such path / error → no git events
    const body = await res.json();
    return Array.isArray(body) ? body : [];
  } catch {
    return []; // offline / DNS / rate limit / timeout → none
  } finally {
    clearTimeout(timer);
  }
}
