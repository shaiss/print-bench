// Release download links (issue #139, the site half of #102).
//
// Why this exists: the download links a product page shows come from a release
// manifest fetched over the network — the one part of the build that is neither
// committed nor gated by the render pipeline. So its two halves are pinned here:
// the PURE manifest→links mapping (URLs, sizes, checksums, the no-release case),
// and the BEST-EFFORT fetch boundary driven by a stub `fetch` so no test touches
// the network. The negative controls matter most — a fetch that starts throwing
// on a 404 instead of degrading to "no downloads" would break every deploy, and
// only these catch it.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  manifestToDownloads,
  fetchLatestReleaseManifests,
  shouldFetchReleases,
  humanSize,
} from "../lib/releases.mjs";
import { designPage } from "../lib/templates.mjs";

const OWNER = "shaiss";
const REPO = "print-bench";
const REPO_OPTS = { owner: OWNER, repo: REPO };

const MANIFEST = {
  design: "calibration-cube",
  version: "v0.1",
  part_count: 1,
  parts: [
    { part: "calibration-cube", file: "calibration-cube.stl", sha256: "c0ffee".repeat(10) + "abcd", size: 213130 },
  ],
  print_settings: { material: "any", supports: "none needed" },
};

test("manifestToDownloads maps parts to stable release-download URLs", () => {
  const d = manifestToDownloads(MANIFEST, REPO_OPTS);
  assert.equal(d.version, "v0.1");
  assert.equal(d.parts.length, 1);
  const p = d.parts[0];
  assert.equal(p.part, "calibration-cube");
  assert.equal(
    p.url,
    "https://github.com/shaiss/print-bench/releases/download/v0.1/calibration-cube.stl"
  );
  assert.equal(p.size, 213130);
  assert.equal(p.sha256, MANIFEST.parts[0].sha256);
  assert.equal(
    d.bundleUrl,
    "https://github.com/shaiss/print-bench/releases/download/v0.1/calibration-cube-v0.1.zip"
  );
  assert.equal(d.bundleFile, "calibration-cube-v0.1.zip");
  assert.equal(d.releaseUrl, "https://github.com/shaiss/print-bench/releases/tag/v0.1");
  assert.deepEqual(d.printSettings, { material: "any", supports: "none needed" });
});

test("manifestToDownloads handles a multi-part manifest", () => {
  const m = {
    design: "sushi-battleship-tracker",
    version: "v0.2",
    parts: [
      { part: "bottom", file: "sushi-battleship-tracker-bottom.stl", sha256: "aa", size: 10 },
      { part: "coupon", file: "sushi-battleship-tracker-coupon.stl", sha256: "bb", size: 20 },
    ],
  };
  const d = manifestToDownloads(m, REPO_OPTS);
  assert.deepEqual(
    d.parts.map((p) => p.url),
    [
      "https://github.com/shaiss/print-bench/releases/download/v0.2/sushi-battleship-tracker-bottom.stl",
      "https://github.com/shaiss/print-bench/releases/download/v0.2/sushi-battleship-tracker-coupon.stl",
    ]
  );
  // A manifest with no print_settings still maps, with an empty object.
  assert.deepEqual(d.printSettings, {});
});

test("manifestToDownloads returns null for a missing or malformed manifest", () => {
  assert.equal(manifestToDownloads(null, REPO_OPTS), null);
  assert.equal(manifestToDownloads(undefined, REPO_OPTS), null);
  assert.equal(manifestToDownloads({ design: "x", version: "v1" }, REPO_OPTS), null); // no parts[]
  assert.equal(manifestToDownloads({ design: "x", parts: [] }, REPO_OPTS), null); // no version
  assert.equal(manifestToDownloads({ version: "v1", parts: [{ file: "a.stl" }] }, REPO_OPTS), null); // no design
  assert.equal(manifestToDownloads({ design: "x", version: "v1", parts: [] }, REPO_OPTS), null); // empty parts
  assert.equal(
    manifestToDownloads({ design: "x", version: "v1", parts: [{ sha256: "z" }] }, REPO_OPTS),
    null
  ); // no usable file
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

const LATEST = "https://api.github.com/repos/shaiss/print-bench/releases/latest";

test("fetchLatestReleaseManifests reads *.manifest.json assets into a map", async () => {
  const mfUrl =
    "https://github.com/shaiss/print-bench/releases/download/v0.1/calibration-cube-v0.1.manifest.json";
  const fetchImpl = stubFetch({
    [LATEST]: {
      tag_name: "v0.1",
      assets: [
        { name: "calibration-cube.stl", browser_download_url: "https://x/stl" }, // ignored (not a manifest)
        { name: "calibration-cube-v0.1.manifest.json", browser_download_url: mfUrl },
      ],
    },
    [mfUrl]: MANIFEST,
  });
  const map = await fetchLatestReleaseManifests({ fetchImpl, owner: OWNER, repo: REPO });
  assert.equal(map.size, 1);
  assert.equal(map.get("calibration-cube").version, "v0.1");
});

test("fetchLatestReleaseManifests returns empty when there is no release (404)", async () => {
  const fetchImpl = stubFetch({}); // every URL 404s
  const map = await fetchLatestReleaseManifests({ fetchImpl, owner: OWNER, repo: REPO });
  assert.equal(map.size, 0);
});

test("fetchLatestReleaseManifests degrades to empty on a network error", async () => {
  const fetchImpl = stubFetch({ [LATEST]: new Error("getaddrinfo ENOTFOUND") });
  const map = await fetchLatestReleaseManifests({ fetchImpl, owner: OWNER, repo: REPO });
  assert.equal(map.size, 0); // best-effort: a thrown fetch is "no downloads", not a crash
});

test("fetchLatestReleaseManifests skips one bad asset but keeps the rest", async () => {
  const goodUrl = "https://github.com/shaiss/print-bench/releases/download/v0.1/good-v0.1.manifest.json";
  const badUrl = "https://github.com/shaiss/print-bench/releases/download/v0.1/bad-v0.1.manifest.json";
  const fetchImpl = stubFetch({
    [LATEST]: {
      assets: [
        { name: "bad-v0.1.manifest.json", browser_download_url: badUrl }, // 404 on fetch
        { name: "good-v0.1.manifest.json", browser_download_url: goodUrl },
      ],
    },
    [goodUrl]: { design: "good", version: "v0.1", parts: [{ part: "a", file: "good.stl" }] },
    // badUrl intentionally absent → 404
  });
  const map = await fetchLatestReleaseManifests({ fetchImpl, owner: OWNER, repo: REPO });
  assert.deepEqual([...map.keys()], ["good"]);
});

test("shouldFetchReleases: on for Vercel or explicit opt-in, off otherwise", () => {
  assert.equal(shouldFetchReleases({}), false); // local / CI default: deterministic, no network
  assert.equal(shouldFetchReleases({ VERCEL: "1" }), true); // the deploy has network
  assert.equal(shouldFetchReleases({ SITE_FETCH_RELEASES: "1" }), true);
  assert.equal(shouldFetchReleases({ VERCEL: "1", SITE_FETCH_RELEASES: "0" }), false); // explicit off wins
});

// --- the block as it lands on a product page (AC-S1 / AC-S2) ---

const DESIGN_FIXTURE = {
  name: "calibration-cube",
  title: "Calibration Cube",
  pitch: "A dimensional-accuracy test cube.",
  relDir: "designs/calibration-cube",
  scads: ["calibration-cube.scad"],
  parts: [],
  parents: [],
  style: null,
  thumb: null,
};
const PAGE_OPTS = {
  html: "<p>body</p>",
  toc: "",
  githubBase: "https://github.com/shaiss/print-bench/blob/main",
  model: {},
};

test("designPage renders a Downloads block from a manifest", () => {
  const downloads = manifestToDownloads(MANIFEST, REPO_OPTS);
  const page = designPage(DESIGN_FIXTURE, { ...PAGE_OPTS, downloads });
  assert.match(page, /<h3>Downloads<\/h3>/);
  assert.ok(
    page.includes(
      "https://github.com/shaiss/print-bench/releases/download/v0.1/calibration-cube.stl"
    ),
    "links the per-part STL asset"
  );
  assert.ok(page.includes("calibration-cube-v0.1.zip"), "links the bundle zip");
  assert.ok(page.includes("208 KB"), "shows the human-readable size");
  assert.ok(page.includes(MANIFEST.parts[0].sha256.slice(0, 12)), "shows a short checksum");
});

test("designPage shows no Downloads block when there is no release", () => {
  const page = designPage(DESIGN_FIXTURE, { ...PAGE_OPTS, downloads: null });
  assert.ok(!page.includes("<h3>Downloads</h3>"));
});

test("humanSize renders B / KB / MB", () => {
  assert.equal(humanSize(512), "512 B");
  assert.equal(humanSize(213130), "208 KB");
  assert.equal(humanSize(6291174), "6.0 MB");
  assert.equal(humanSize(-1), "");
});
