// AI lifestyle imagery feature flag (issue #302). Z.AI has no true
// image-to-image (seed) model, so the "AI scene pinned to the real mesh"
// premise never held; the tier is disabled behind a committed default-off
// `.github/ai-lifestyle.conf`. These tests pin the two site-side guarantees:
//   1. the flag reader is fail-safe default-off (media.mjs);
//   2. when off, readDesigns drops every AI-styled preview at the single source
//      so it reaches no downstream surface, while tier-1 previews are untouched;
//      when on, the AI previews come back with no other change (reversible).

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { tmpdir } from "node:os";

import { isAiLifestyle, aiLifestyleEnabled } from "../lib/media.mjs";
import { readDesigns } from "../lib/content.mjs";

// --- isAiLifestyle: the single predicate the flag keys on -------------------

test("isAiLifestyle flags exactly the AI tiers, not geometry-true tier-1", () => {
  for (const ai of [
    "lifestyle-scene.png",
    "lifestyle-den-in-use.png",
    "lifestyle-turntable.gif",
    "lifestyle-product-hero.gif",
    "product-still-hero.png",
  ]) {
    assert.equal(isAiLifestyle(ai), true, `${ai} should be AI`);
  }
  for (const real of [
    "product-hero.png",
    "contact-sheet.png",
    "turntable.gif",
    "cutaway.png",
    "shutter-slide.gif",
  ]) {
    assert.equal(isAiLifestyle(real), false, `${real} should not be AI`);
  }
});

// --- aiLifestyleEnabled: fail-safe default-off ------------------------------

function repoWithConf(contents) {
  const root = mkdtempSync(join(tmpdir(), "print-bench-ai-flag-"));
  if (contents !== null) {
    mkdirSync(join(root, ".github"), { recursive: true });
    writeFileSync(join(root, ".github", "ai-lifestyle.conf"), contents);
  }
  return root;
}

test("aiLifestyleEnabled is off unless the conf says exactly enabled: true", () => {
  const cases = [
    [null, false, "missing file"],
    ["", false, "empty file"],
    ["enabled: false\n", false, "explicit false"],
    ["# enabled: true\n", false, "commented out"],
    ["enabled: maybe\n", false, "junk value"],
    ["enabledx: true\n", false, "wrong key"],
    ["enabled: true\n", true, "canonical on"],
    ["  enabled:   true  \n", true, "whitespace tolerant"],
    ["enabled: true # turned on\n", true, "trailing comment"],
    ["# notes\nfoo: bar\nenabled: true\n", true, "among other lines"],
  ];
  for (const [conf, want, why] of cases) {
    const root = repoWithConf(conf);
    try {
      assert.equal(aiLifestyleEnabled(root), want, why);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  }
});

// --- readDesigns: the single-source filter ---------------------------------

/** A minimal one-design repo whose previews mix AI and tier-1 files, plus a
 *  `.github/ai-lifestyle.conf` carrying `flag`. Returns the repo root. */
function designFixture(flag) {
  const root = mkdtempSync(join(tmpdir(), "print-bench-ai-design-"));
  const w = (rel, body) => {
    const abs = join(root, rel);
    mkdirSync(dirname(abs), { recursive: true });
    writeFileSync(abs, body);
  };
  w(".github/ai-lifestyle.conf", `enabled: ${flag}\n`);
  w("designs/widget/widget.scad", "cube(10);\n");
  w("designs/widget/README.md", "# Widget\n\nA thing.\n");
  for (const f of [
    "product-hero.png",
    "contact-sheet.png",
    "turntable.gif",
    "lifestyle-scene.png",
    "lifestyle-turntable.gif",
    "product-still-hero.png",
  ]) {
    w(`designs/widget/previews/${f}`, "");
  }
  return root;
}

test("readDesigns hides AI previews when the flag is off, keeps tier-1", () => {
  const root = designFixture("false");
  try {
    const [d] = readDesigns(root);
    assert.deepEqual(
      d.previews.sort(),
      ["contact-sheet.png", "product-hero.png", "turntable.gif"],
      "AI previews must be dropped, tier-1 kept"
    );
    assert.equal(d.previews.some(isAiLifestyle), false, "no AI preview survives");
    assert.equal(d.hero, "product-hero.png", "hero stays a geometry-true render");
    assert.equal(isAiLifestyle(d.thumb), false, "thumb is never an AI file");
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("readDesigns restores AI previews when the flag is on (reversible)", () => {
  const root = designFixture("true");
  try {
    const [d] = readDesigns(root);
    for (const ai of [
      "lifestyle-scene.png",
      "lifestyle-turntable.gif",
      "product-still-hero.png",
    ]) {
      assert.ok(d.previews.includes(ai), `${ai} should be present when on`);
    }
    // Flipping the flag is the only difference — tier-1 previews are unchanged.
    assert.ok(d.previews.includes("product-hero.png"));
    assert.ok(d.previews.includes("contact-sheet.png"));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
