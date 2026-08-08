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
//     touch the network, and it is BEST-EFFORT — any failure (offline, rate
//     limit, no release yet) yields an empty result and the caller renders no
//     downloads, never a broken build. The site's no-404 rule for committed
//     references still holds; release links are external and simply absent when
//     the release is.
//
// Determinism: the fetch is Vercel-scoped (shouldFetchReleases). Local and CI
// `site.sh` builds do not fetch and are byte-for-byte reproducible; the Vercel
// deploy, which has network, is where live download links appear. The manifest
// is authored by the CI build that published the release, so its checksums
// match the exact bytes a visitor downloads — a local re-render never forges
// them.

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
 * Impure boundary — read the latest Release and return a Map<design, manifest>
 * built from its `*.manifest.json` assets. Best-effort: returns an EMPTY map on
 * any failure (no release, non-2xx, network error, unparseable asset), so the
 * caller wraps nothing and the build never breaks. `fetchImpl` is injectable so
 * tests drive it with a stub; `token` (optional) lifts the unauthenticated rate
 * limit but is never required for a public repo.
 */
export async function fetchLatestReleaseManifests({
  fetchImpl = globalThis.fetch,
  owner,
  repo,
  token,
} = {}) {
  const result = new Map();
  if (typeof fetchImpl !== "function") return result;
  const headers = { Accept: "application/vnd.github+json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  let release;
  try {
    const res = await fetchImpl(
      `${GITHUB_API}/repos/${owner}/${repo}/releases/latest`,
      { headers }
    );
    if (!res || !res.ok) return result; // no release yet (404) or an error → none
    release = await res.json();
  } catch {
    return result; // offline / DNS / rate limit → none
  }
  const assets = Array.isArray(release?.assets) ? release.assets : [];
  for (const asset of assets) {
    if (!asset || typeof asset.name !== "string") continue;
    if (!asset.name.endsWith(".manifest.json")) continue;
    if (typeof asset.browser_download_url !== "string") continue;
    try {
      const res = await fetchImpl(asset.browser_download_url, { headers });
      if (!res || !res.ok) continue;
      const manifest = await res.json();
      if (manifest && typeof manifest.design === "string") {
        result.set(manifest.design, manifest);
      }
    } catch {
      // one bad asset must not sink the rest
    }
  }
  return result;
}

/** Human-readable byte size for a download row (e.g. 213130 → "208 KB"). */
export function humanSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}
