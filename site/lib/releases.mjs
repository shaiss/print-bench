// Release download links for product pages (issue #139, the site half of #102).
//
// The build half (scripts/release-bundle.sh + .github/workflows/release.yml)
// publishes, per design, a self-describing manifest and per-part STL assets to a
// tagged GitHub Release. This turns that manifest into the download links a
// product page shows — so a stranger goes view → decide → download in one flow.
//
// Two halves, kept apart on purpose:
//   - manifestToDownloads() is PURE: a manifest → the link model a template
//     renders. Unit-tested exhaustively, no network.
//   - fetchLatestReleaseManifests() is the impure boundary: it reads the latest
//     Release over the GitHub API. It takes an injectable `fetch` so tests never
//     touch the network, and it is BEST-EFFORT — any failure yields no
//     manifests, never a broken build. It reports a seam status (seam.mjs)
//     beside them, so "no release published" (`empty` — no Downloads block)
//     stays distinct from "couldn't read the release" (`unavailable` — the
//     product page says so, designReleaseStatus). The site's no-404 rule for
//     committed references still holds; release links are external and simply
//     absent when the release is.
//
// Determinism: the fetch is Vercel-scoped (shouldFetchReleases). Local and CI
// `site.sh` builds do not fetch and are byte-for-byte reproducible; the Vercel
// deploy, which has network, is where live download links appear. The manifest
// is authored by the CI build that published the release, so its checksums
// match the exact bytes a visitor downloads — a local re-render never forges
// them.

import { SEAM, seamResult, fetchedResult, fetchJson, reasonSummary } from "./seam.mjs";

const GITHUB_API = "https://api.github.com";

/**
 * Whether to fetch release data this build. On (Vercel, or SITE_FETCH_RELEASES=1)
 * the product pages get live download links; off (default, incl. CI and local
 * `site.sh`) the build stays deterministic and offline and shows none.
 */
export function shouldFetchReleases(env = process.env) {
  if (env.SITE_FETCH_RELEASES === "1") return true;
  if (env.SITE_FETCH_RELEASES === "0") return false;
  return Boolean(env.VERCEL); // Vercel sets VERCEL=1 in the build environment
}

/**
 * Pure: a release manifest → the download-link model a product page renders,
 * or null when the manifest is missing or malformed (→ no Downloads block).
 * Every asset URL follows GitHub's stable release-download convention, so no
 * per-asset API lookup is needed:
 *   https://github.com/<owner>/<repo>/releases/download/<version>/<file>
 */
export function manifestToDownloads(manifest, { owner, repo }) {
  if (
    !manifest ||
    typeof manifest.design !== "string" ||
    typeof manifest.version !== "string" ||
    !Array.isArray(manifest.parts)
  ) {
    return null;
  }
  const base = `https://github.com/${owner}/${repo}/releases/download/${manifest.version}`;
  const parts = manifest.parts
    .filter((p) => p && typeof p.file === "string")
    .map((p) => ({
      part: typeof p.part === "string" ? p.part : p.file,
      file: p.file,
      size: Number.isFinite(p.size) ? p.size : null,
      sha256: typeof p.sha256 === "string" ? p.sha256 : null,
      url: `${base}/${p.file}`,
    }));
  if (parts.length === 0) return null;
  const bundleFile = `${manifest.design}-${manifest.version}.zip`;
  return {
    design: manifest.design,
    version: manifest.version,
    parts,
    bundleFile,
    bundleUrl: `${base}/${bundleFile}`,
    releaseUrl: `https://github.com/${owner}/${repo}/releases/tag/${manifest.version}`,
    printSettings:
      manifest.print_settings && typeof manifest.print_settings === "object"
        ? manifest.print_settings
        : {},
  };
}

/**
 * The design a manifest asset belongs to, from its published name —
 * release-bundle.sh writes `<design>-<version>.manifest.json`, and the version
 * is the release tag. null when the name does not follow that convention, so a
 * caller can't narrow a failure to one design and must not pretend to.
 */
function assetDesign(name, tag) {
  const suffix = typeof tag === "string" && tag ? `-${tag}.manifest.json` : null;
  return suffix && name.endsWith(suffix) && name.length > suffix.length
    ? name.slice(0, -suffix.length)
    : null;
}

/**
 * Impure boundary — read the latest Release and return a seam result (seam.mjs)
 * whose `items` is a Map<design, manifest> built from its `*.manifest.json`
 * assets. Never throws, so the build never breaks:
 *   ok           at least one manifest read
 *   empty        no published release (GitHub answers /releases/latest with
 *                404 when there is none), or a release with no manifests
 *   unavailable  the release itself could not be read (a non-404 error, network
 *                error, timeout, unparseable body) — every design is affected,
 *                `unavailableDesigns: null`; or some manifest assets could not
 *                be read — `items` keeps the ones that were (one bad asset
 *                must not sink the rest) and `unavailableDesigns` names the
 *                designs whose manifest failed (null if a failed asset's name
 *                does not say which design it is). designReleaseStatus turns
 *                this into a per-page answer.
 * `fetchImpl` is injectable so tests drive it with a stub; `token` (optional)
 * lifts the unauthenticated rate limit but is never required for a public repo.
 * Each request is bounded by `timeoutMs` (fetchJson).
 */
export async function fetchLatestReleaseManifests({
  fetchImpl = globalThis.fetch,
  owner,
  repo,
  token,
  timeoutMs = 10000,
} = {}) {
  const result = new Map();
  const headers = { Accept: "application/vnd.github+json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const latest = await fetchJson(
    fetchImpl,
    `${GITHUB_API}/repos/${owner}/${repo}/releases/latest`,
    { headers, timeoutMs }
  );
  if (!latest.ok) {
    if (latest.status === 404) return seamResult(SEAM.EMPTY, result); // nothing published yet
    return { ...seamResult(SEAM.UNAVAILABLE, result, latest.reason), unavailableDesigns: null };
  }
  const release = latest.body;
  if (!release || typeof release !== "object" || Array.isArray(release)) {
    return {
      ...seamResult(SEAM.UNAVAILABLE, result, "unexpected response body"),
      unavailableDesigns: null,
    };
  }
  const assets = Array.isArray(release.assets) ? release.assets : [];
  const failures = [];
  let failedDesigns = new Set();
  for (const asset of assets) {
    if (!asset || typeof asset.name !== "string") continue;
    if (!asset.name.endsWith(".manifest.json")) continue;
    if (typeof asset.browser_download_url !== "string") continue;
    const got = await fetchJson(fetchImpl, asset.browser_download_url, { headers, timeoutMs });
    const manifest = got.ok ? got.body : null;
    if (manifest && typeof manifest.design === "string") {
      result.set(manifest.design, manifest);
      continue;
    }
    // One bad asset must not sink the rest — but it is recorded, not dropped.
    failures.push(got.ok ? "unexpected manifest body" : got.reason);
    const design = assetDesign(asset.name, release.tag_name);
    if (design === null) failedDesigns = null;
    else if (failedDesigns) failedDesigns.add(design);
  }
  if (failures.length) {
    return {
      ...seamResult(SEAM.UNAVAILABLE, result, reasonSummary(failures)),
      unavailableDesigns: failedDesigns,
    };
  }
  return fetchedResult(result);
}

/**
 * Pure: one design's release state from the seam result — what its product
 * page's Downloads block should say. `ok` when its manifest was read, `off`
 * when the seam did not run (the page renders exactly as before), `unavailable`
 * when the release — or this design's own manifest — could not be read (the
 * page says so rather than implying there is no release), and `empty` otherwise:
 * the release was read and simply carries nothing for this design.
 */
export function designReleaseStatus(result, design) {
  if (!result || result.status === SEAM.OFF) return SEAM.OFF;
  if (result.items instanceof Map && result.items.has(design)) return SEAM.OK;
  if (result.status !== SEAM.UNAVAILABLE) return SEAM.EMPTY;
  const scope = result.unavailableDesigns;
  return !(scope instanceof Set) || scope.has(design) ? SEAM.UNAVAILABLE : SEAM.EMPTY;
}

/** Human-readable byte size for a download row (e.g. 213130 → "208 KB"). */
export function humanSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}
