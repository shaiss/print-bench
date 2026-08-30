// Canonical / og:url emission is module-level state (setSiteUrl), like the
// asset version and the notification bell. Two controls: with no origin
// configured the head stays origin-free (the state every other lib test runs
// under); with one set, every page carries an absolute canonical + og:url
// built from the configured origin and the page's own canonicalPath.
import { test } from "node:test";
import assert from "node:assert/strict";
import { layout, setSiteUrl } from "../lib/templates.mjs";

test("layout emits no canonical/og:url until an origin is configured", () => {
  setSiteUrl("");
  const html = layout({ title: "T", body: "<p>b</p>", canonicalPath: "/styles/" });
  assert.doesNotMatch(html, /rel="canonical"/, "no canonical without an origin");
  assert.doesNotMatch(html, /og:url/, "no og:url without an origin");
});

test("layout emits absolute canonical + og:url from the configured origin", () => {
  try {
    setSiteUrl("https://printbench.xyz/"); // trailing slash tolerated, not doubled
    const inner = layout({ title: "T", body: "<p>b</p>", canonicalPath: "/styles/" });
    assert.match(
      inner,
      /<link rel="canonical" href="https:\/\/printbench\.xyz\/styles\/">/,
      "canonical is origin + canonicalPath"
    );
    assert.match(
      inner,
      /<meta property="og:url" content="https:\/\/printbench\.xyz\/styles\/">/,
      "og:url mirrors the canonical"
    );
    // Home page → origin + "/", exactly one slash between them.
    const home = layout({ title: "T", body: "", canonicalPath: "/" });
    assert.match(home, /<link rel="canonical" href="https:\/\/printbench\.xyz\/">/);
    assert.doesNotMatch(home, /printbench\.xyz\/\//, "no doubled slash at the origin");
  } finally {
    // Reset the shared module state so later tests stay origin-free.
    setSiteUrl("");
  }
});
