// The inline-SVG diagrams (site/lib/diagrams.mjs).
//
// They are authored markup interpolated from data, so a dropped coordinate or a
// bad template shows up as "undefined"/"NaN" in an attribute — invalid SVG the
// build won't catch (it doesn't parse the generated HTML). These tests render
// each diagram and assert it is well-formed enough to draw, carries an
// accessible label, and contains the labels it's supposed to.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  journeyMap,
  infographicNonTechnical,
  pipelineSlides,
} from "../lib/diagrams.mjs";

function assertWellFormedSvg(name, svg) {
  assert.ok(svg.startsWith("<svg"), `${name}: not an <svg>`);
  assert.ok(svg.trimEnd().endsWith("</svg>"), `${name}: unclosed <svg>`);
  assert.ok(svg.includes('role="img"'), `${name}: no role=img`);
  assert.ok(/aria-label="[^"]{20,}"/.test(svg), `${name}: missing a real aria-label`);
  for (const bad of ["undefined", "NaN", "${", "[object Object]"]) {
    assert.ok(!svg.includes(bad), `${name}: contains ${bad}`);
  }
  // No hardcoded hex colour — every colour must come from a CSS token so the
  // diagram themes (white text on the accent fill is the one allowed literal).
  const hexes = (svg.match(/#[0-9a-fA-F]{3,6}/g) || []).filter((h) => h.toLowerCase() !== "#fff");
  assert.equal(hexes.length, 0, `${name}: hardcoded colours ${hexes.join(", ")}`);
}

test("static diagrams render well-formed, accessible SVG", () => {
  assertWellFormedSvg("journeyMap", journeyMap());
  assertWellFormedSvg("infographicNonTechnical", infographicNonTechnical());
});

test("pipelineSlides is a stepped set of well-formed slides", () => {
  const slides = pipelineSlides();
  assert.ok(Array.isArray(slides) && slides.length >= 4, "expected several slides");
  const ids = new Set();
  for (const s of slides) {
    assert.ok(s.id && s.title && s.note, `slide missing id/title/note: ${JSON.stringify(s)}`);
    assert.ok(!ids.has(s.id), `duplicate slide id ${s.id}`);
    ids.add(s.id);
    assertWellFormedSvg(`slide:${s.id}`, s.svg);
    // The number lives in the carousel's "Step N of M" chrome, not the title.
    assert.ok(!/^\d/.test(s.title), `slide title should not lead with a number: ${s.title}`);
  }
});

test("diagrams carry their key labels", () => {
  assert.ok(journeyMap().includes("Preflight"));
  assert.ok(journeyMap().includes("/new-design"));
  assert.ok(infographicNonTechnical().includes("Design it together"));
  const flow = pipelineSlides().map((s) => s.svg).join("");
  assert.ok(flow.includes("gate set"));
  assert.ok(flow.includes("ci-ok"));
  assert.ok(flow.includes("PLATFORM — generic (the reusable template)"));
});
