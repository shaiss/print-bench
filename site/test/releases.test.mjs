// Release download links (issue #139, the site half of #102).
//
// Why this exists: the download links a product page shows come from a release
// manifest fetched over the network — the one part of the build that is neither
// committed nor gated by the render pipeline. So its two halves are pinned here:
// the PURE manifest→links mapping (URLs, sizes, checksums, the no-release case),
// and the BEST-EFFORT fetch boundary driven by a stub `fetch` so no test touches
// the network. The negative controls matter most — a fetch that starts throwing
// on a 404 instead of degrading to "no downloads" would break every deploy, and
// one that reports a 401/403 as `empty` would pass a failed fetch off as "this
// design has no release"; only these catch either.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  manifestToDownloads,
  fetchLatestReleaseManifests,
  designReleaseStatus,
  shouldFetchReleases,
  humanSize,
} from "../lib/releases.mjs";
import { SEAM, runSeam } from "../lib/seam.mjs";
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
const httpError = (status, headers = {}) => () => ({
  ok: false,
  status,
  headers: new Map(Object.entries(headers)),
  json: async () => ({ message: "error" }),
});
const badJson = () => ({
  ok: true,
  status: 200,
  json: async () => {
    throw new SyntaxError("Unexpected token '<'");
  },
});

const LATEST = "https://api.github.com/repos/shaiss/print-bench/releases/latest";
const MF_URL =
  "https://github.com/shaiss/print-bench/releases/download/v0.1/calibration-cube-v0.1.manifest.json";
const RELEASE = {
  tag_name: "v0.1",
  assets: [
    { name: "calibration-cube.stl", browser_download_url: "https://x/stl" }, // ignored (not a manifest)
    { name: "calibration-cube-v0.1.manifest.json", browser_download_url: MF_URL },
  ],
};

test("fetchLatestReleaseManifests reads *.manifest.json assets into an ok map", async () => {
  const fetchImpl = stubFetch({ [LATEST]: RELEASE, [MF_URL]: MANIFEST });
  const got = await fetchLatestReleaseManifests({ fetchImpl, owner: OWNER, repo: REPO });
  assert.equal(got.status, SEAM.OK);
  assert.equal(got.items.size, 1);
  assert.equal(got.items.get("calibration-cube").version, "v0.1");
  assert.equal(designReleaseStatus(got, "calibration-cube"), SEAM.OK);
  assert.equal(designReleaseStatus(got, "nuggs"), SEAM.EMPTY, "a design the release doesn't carry");
});

test("fetchLatestReleaseManifests: no published release (404) is empty, not unavailable", async () => {
  const got = await fetchLatestReleaseManifests({ fetchImpl: stubFetch({}), owner: OWNER, repo: REPO });
  assert.equal(got.status, SEAM.EMPTY);
  assert.equal(got.items.size, 0);
  assert.equal(designReleaseStatus(got, "calibration-cube"), SEAM.EMPTY);
});

test("fetchLatestReleaseManifests: a release with no manifests is empty", async () => {
  const fetchImpl = stubFetch({ [LATEST]: { tag_name: "v0.1", assets: [] } });
  const got = await fetchLatestReleaseManifests({ fetchImpl, owner: OWNER, repo: REPO });
  assert.equal(got.status, SEAM.EMPTY);
});

test("fetchLatestReleaseManifests: a 403 / 401 on the release is unavailable for every design", async () => {
  for (const [route, reason] of [
    [httpError(403, { "x-ratelimit-remaining": "0" }), "HTTP 403, rate limited"],
    [httpError(401), "HTTP 401"],
  ]) {
    const got = await fetchLatestReleaseManifests({
      fetchImpl: stubFetch({ [LATEST]: route }),
      owner: OWNER,
      repo: REPO,
    });
    assert.equal(got.status, SEAM.UNAVAILABLE);
    assert.equal(got.reason, reason);
    assert.equal(got.items.size, 0);
    assert.equal(designReleaseStatus(got, "calibration-cube"), SEAM.UNAVAILABLE);
    assert.equal(designReleaseStatus(got, "anything-else"), SEAM.UNAVAILABLE, "can't say any design has no release");
  }
});

test("fetchLatestReleaseManifests: a network error is unavailable, not a crash", async () => {
  const fetchImpl = stubFetch({ [LATEST]: new Error("getaddrinfo ENOTFOUND") });
  const got = await fetchLatestReleaseManifests({ fetchImpl, owner: OWNER, repo: REPO });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.match(got.reason, /^network error: /);
  assert.equal(got.items.size, 0);
});

test("fetchLatestReleaseManifests: an unparseable release body is unavailable", async () => {
  const fetchImpl = stubFetch({ [LATEST]: badJson });
  const got = await fetchLatestReleaseManifests({ fetchImpl, owner: OWNER, repo: REPO });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.equal(got.reason, "unparseable JSON body");
});

test("fetchLatestReleaseManifests keeps the good assets and marks only the bad one's design", async () => {
  const goodUrl = "https://github.com/shaiss/print-bench/releases/download/v0.1/good-v0.1.manifest.json";
  const badUrl = "https://github.com/shaiss/print-bench/releases/download/v0.1/bad-v0.1.manifest.json";
  const fetchImpl = stubFetch({
    [LATEST]: {
      tag_name: "v0.1",
      assets: [
        { name: "bad-v0.1.manifest.json", browser_download_url: badUrl }, // 404 on fetch
        { name: "good-v0.1.manifest.json", browser_download_url: goodUrl },
      ],
    },
    [goodUrl]: { design: "good", version: "v0.1", parts: [{ part: "a", file: "good.stl" }] },
    // badUrl intentionally absent → 404
  });
  const got = await fetchLatestReleaseManifests({ fetchImpl, owner: OWNER, repo: REPO });
  assert.deepEqual([...got.items.keys()], ["good"], "one bad asset does not sink the rest");
  assert.equal(got.status, SEAM.UNAVAILABLE, "but the failure is reported, not dropped");
  assert.equal(got.reason, "HTTP 404");
  assert.equal(designReleaseStatus(got, "good"), SEAM.OK);
  assert.equal(designReleaseStatus(got, "bad"), SEAM.UNAVAILABLE);
  assert.equal(designReleaseStatus(got, "other"), SEAM.EMPTY, "a design not in the release is unaffected");
});

test("fetchLatestReleaseManifests: a failed asset whose name names no design affects every design", async () => {
  const oddUrl = "https://github.com/shaiss/print-bench/releases/download/v0.1/odd.manifest.json";
  const fetchImpl = stubFetch({
    [LATEST]: { tag_name: "v0.1", assets: [{ name: "odd.manifest.json", browser_download_url: oddUrl }] },
    [oddUrl]: badJson,
  });
  const got = await fetchLatestReleaseManifests({ fetchImpl, owner: OWNER, repo: REPO });
  assert.equal(got.status, SEAM.UNAVAILABLE);
  assert.equal(designReleaseStatus(got, "anything"), SEAM.UNAVAILABLE);
});

test("releases disabled (the local/CI default) is off, and nothing is fetched", async () => {
  let fetched = false;
  const fetchImpl = async () => {
    fetched = true;
    return { ok: true, status: 200, json: async () => RELEASE };
  };
  const got = await runSeam(
    shouldFetchReleases({}),
    () => fetchLatestReleaseManifests({ fetchImpl, owner: OWNER, repo: REPO }),
    new Map()
  );
  assert.equal(got.status, SEAM.OFF);
  assert.equal(fetched, false);
  assert.equal(designReleaseStatus(got, "calibration-cube"), SEAM.OFF);
  assert.equal(designReleaseStatus(null, "calibration-cube"), SEAM.OFF);
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
  // off (the default) and empty render exactly that same page
  for (const releaseStatus of [SEAM.OFF, SEAM.EMPTY]) {
    assert.equal(designPage(DESIGN_FIXTURE, { ...PAGE_OPTS, downloads: null, releaseStatus }), page);
  }
});

test("designPage says the downloads couldn't be loaded when the release was unavailable", () => {
  const page = designPage(DESIGN_FIXTURE, {
    ...PAGE_OPTS,
    downloads: null,
    releaseStatus: SEAM.UNAVAILABLE,
  });
  assert.match(page, /<h3>Downloads<\/h3>/, "the block is not silently absent");
  assert.match(page, /Release downloads couldn(&#39;|')t be loaded for this deploy/);
  assert.ok(
    page.includes('href="https://github.com/shaiss/print-bench/releases"'),
    "points the reader at the releases list"
  );
  assert.ok(!page.includes("Download STLs"), "no download action for a release we couldn't read");
});

test("designPage: a design whose manifest DID load shows its downloads even if another's failed", () => {
  const downloads = manifestToDownloads(MANIFEST, REPO_OPTS);
  const page = designPage(DESIGN_FIXTURE, { ...PAGE_OPTS, downloads, releaseStatus: SEAM.OK });
  assert.ok(page.includes("calibration-cube-v0.1.zip"));
  assert.ok(!/couldn(&#39;|')t be loaded/.test(page));
});

test("humanSize renders B / KB / MB", () => {
  assert.equal(humanSize(512), "512 B");
  assert.equal(humanSize(213130), "208 KB");
  assert.equal(humanSize(6291174), "6.0 MB");
  assert.equal(humanSize(-1), "");
});
