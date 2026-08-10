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
  infographicTechnical,
  regenLoop,
} from "../lib/diagrams.mjs";

const ALL = { journeyMap, infographicNonTechnical, infographicTechnical, regenLoop };

test("every diagram renders a well-formed, accessible SVG", () => {
  for (const [name, fn] of Object.entries(ALL)) {
    const svg = fn();
    assert.ok(svg.startsWith("<svg"), `${name}: not an <svg>`);
    assert.ok(svg.trimEnd().endsWith("</svg>"), `${name}: unclosed <svg>`);
    assert.ok(svg.includes('role="img"'), `${name}: no role=img`);
    assert.ok(/aria-label="[^"]{20,}"/.test(svg), `${name}: missing a real aria-label`);
    // The failure modes of interpolated coordinates/strings.
    for (const bad of ["undefined", "NaN", "${", "[object Object]"]) {
      assert.ok(!svg.includes(bad), `${name}: contains ${bad}`);
    }
    // No hardcoded hex colour — every colour must come from a CSS token so the
    // diagram themes (white text on the accent fill is the one allowed literal).
    const hexes = (svg.match(/#[0-9a-fA-F]{3,6}/g) || []).filter((h) => h.toLowerCase() !== "#fff");
    assert.equal(hexes.length, 0, `${name}: hardcoded colours ${hexes.join(", ")}`);
  }
});

test("diagrams carry their key labels", () => {
  assert.ok(journeyMap().includes("Preflight"));
  assert.ok(journeyMap().includes("/new-design"));
  assert.ok(infographicNonTechnical().includes("Design it together"));
  assert.ok(infographicTechnical().includes("ci-ok"));
  assert.ok(infographicTechnical().includes("PLATFORM — generic (the reusable template)"));
  assert.ok(regenLoop().includes("commit back"));
});
