// The "How it works" page (behind-the-scenes of the pipeline).
//
// It is generated markup, not markdown routed through the reference checker, so
// nothing else in the build catches a malformed link or a dropped section. These
// tests pin the contract: the page renders whole, carries every section, links
// each mechanism at the passed github base, and shows the real design count — so
// a future edit that breaks one of those fails here rather than shipping quietly.

import { test } from "node:test";
import assert from "node:assert/strict";

import { howItWorksPage } from "../lib/templates.mjs";

const GH = "https://github.example/blob/main";

test("how-it-works: renders a whole page with no unresolved template bits", () => {
  const html = howItWorksPage({ designCount: 7, githubBase: GH });
  assert.match(html, /^<!doctype html>/);
  assert.match(html, /<h1>How the machine works\.<\/h1>/);
  // A dropped interpolation would leave one of these in the output.
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

test("how-it-works: carries every section", () => {
  const html = howItWorksPage({ designCount: 3, githubBase: GH });
  for (const id of [
    "journey",
    "plain",
    "layers",
    "gates",
    "regenerate",
    "selection",
    "autonomy",
    "telemetry",
    "anatomy",
    "provenance",
  ]) {
    assert.ok(html.includes(`id="${id}"`), `missing section #${id}`);
  }
});

test("how-it-works: embeds the four diagrams as inline, labelled SVG", () => {
  const html = howItWorksPage({ designCount: 3, githubBase: GH });
  // Four figures, each an inline SVG with an accessible label — not an <img>.
  const svgs = html.match(/<svg class="diagram-svg/g) || [];
  assert.equal(svgs.length, 4, `expected 4 inline diagrams, found ${svgs.length}`);
  assert.equal((html.match(/role="img"/g) || []).length >= 4, true);
  assert.ok(!html.includes("<img"), "diagrams must be inline SVG, never external images");
  // Anchor phrases from each diagram, so a silently-empty one is caught.
  for (const phrase of ["Scaffold", "Describe it", "gate set", "loop guard"]) {
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
  // And it links the pipeline definition and the classifier seam.
  assert.ok(html.includes(`${GH}/.github/workflows/ci.yml`));
  assert.ok(html.includes(`${GH}/scripts/ci-classify.sh`));
});

test("how-it-works: shows the real design count", () => {
  const html = howItWorksPage({ designCount: 42, githubBase: GH });
  assert.match(html, /<span class="stat-n">42<\/span>/);
});
