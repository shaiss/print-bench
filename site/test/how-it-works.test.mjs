// The "How it works" page (behind-the-scenes of the pipeline).
//
// It is generated markup, not markdown routed through the reference checker, so
// nothing else in the build catches a malformed link or a dropped section. These
// tests pin the contract: the page renders whole, groups content into tabs,
// carries every section, presents the pipeline as an inline-SVG carousel, links
// each mechanism at the passed github base, and shows the real design count.

import { test } from "node:test";
import assert from "node:assert/strict";

import { howItWorksPage } from "../lib/templates.mjs";

const GH = "https://github.example/blob/main";

test("how-it-works: renders a whole page with no unresolved template bits", () => {
  const html = howItWorksPage({ designCount: 7, githubBase: GH });
  assert.match(html, /^<!doctype html>/);
  assert.match(html, /<h1>How the machine works\.<\/h1>/);
  assert.ok(!html.includes("undefined"), "no undefined leaked into the page");
  assert.ok(!html.includes("${"), "no unrendered template placeholder");
  assert.ok(!html.includes("[object Object]"), "no stringified object");
});

test("how-it-works: marks itself current in the shared nav", () => {
  const html = howItWorksPage({ designCount: 3, githubBase: GH });
  assert.match(
    html,
    /<a href="\/how-it-works\/" aria-current="page">How it works<\/a>/
  );
});

test("how-it-works: groups content into three tabs", () => {
  const html = howItWorksPage({ designCount: 3, githubBase: GH });
  assert.ok(html.includes("data-tabs"), "no tab bar");
  for (const id of ["overview", "pipeline", "runs"]) {
    assert.ok(html.includes(`id="${id}"`), `missing tab panel #${id}`);
    assert.ok(html.includes(`aria-controls="${id}"`), `missing tab for #${id}`);
  }
});

test("how-it-works: carries every content section", () => {
  const html = howItWorksPage({ designCount: 3, githubBase: GH });
  for (const id of [
    "layers",
    "plain",
    "journey",
    "flow",
    "gates",
    "regenerate",
    "selection",
    "autonomy",
    "telemetry",
    "provenance",
  ]) {
    assert.ok(html.includes(`id="${id}"`), `missing section #${id}`);
  }
});

test("how-it-works: presents the pipeline as an inline-SVG carousel", () => {
  const html = howItWorksPage({ designCount: 3, githubBase: GH });
  assert.ok(html.includes("data-carousel"), "no carousel");
  assert.ok(html.includes("carousel-slide"), "no carousel slides");
  assert.ok(html.includes("data-carousel-nav"), "no carousel controls");
  // Static figures (2) + carousel slides (6) are all inline SVG, never <img>.
  const svgs = html.match(/<svg class="diagram-svg/g) || [];
  assert.ok(svgs.length >= 6, `expected many inline diagrams, found ${svgs.length}`);
  assert.ok(!html.includes("<img"), "diagrams must be inline SVG, never external images");
  for (const phrase of ["Scaffold", "Describe it", "gate set", "ci-ok"]) {
    assert.ok(html.includes(phrase), `diagram content missing: ${phrase}`);
  }
});

test("how-it-works: links the architecture docs it is drawn from", () => {
  const html = howItWorksPage({ designCount: 3, githubBase: GH });
  for (const doc of [
    "docs/architecture/README.md",
    "docs/architecture/ci-platform.md",
    "docs/architecture/design-workflow.md",
  ]) {
    assert.ok(html.includes(`${GH}/${doc}`), `does not link ${doc}`);
  }
  assert.ok(html.includes(`${GH}/.github/workflows/ci.yml`));
  assert.ok(html.includes(`${GH}/scripts/ci-classify.sh`));
});

test("how-it-works: shows the real design count", () => {
  const html = howItWorksPage({ designCount: 42, githubBase: GH });
  assert.match(html, /<span class="stat-n">42<\/span>/);
});
