// The site's catalog grouping (issue #374), held to scripts/catalog.sh.
//
// site/lib/catalog.mjs re-implements scripts/catalog.sh's grouping in JS
// because the deploy cannot run bash+Python (vercel.json pins the build to `npm
// ci` + `node build.mjs`). A re-implementation is a drift risk — two surfaces
// of this repo disagreeing about what a design *is* is exactly issue #55 — so
// the cross-check below runs BOTH the JS grouping and `scripts/catalog.sh
// order` over the same trees and fails on any disagreement about a design's
// group or the order it appears in.
//
// scripts/catalog.sh is invoked with --root against a throwaway tree (and the
// real repo), the way it supports the selftest; it shells out to the Python
// lineage resolver, so this needs bash + python3 the same way lineage.test.mjs
// does.

import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

import { readDesigns } from "../lib/content.mjs";
import { indexPage } from "../lib/templates.mjs";
import { readCategories, groupDesigns, categoryOf, isNuggs } from "../lib/catalog.mjs";

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));

// The same vocabulary the real designs/categories.conf declares, so a fixture
// tree groups by the identical closed set + display order.
const VOCAB = [
  "nuggs                  | NUGGS ecosystem",
  "compliant-mechanisms   | Compliant mechanisms",
  "support-free           | Designing around supports   | Leave slicer supports off.",
  "print-in-place         | Print-in-place kinematics   | Keep auto-supports off.",
  "everyday-functional    | Everyday functional prints",
].join("\n");

/**
 * Build a throwaway designs/ tree.
 *
 * `spec` maps a design name to { category, derives, noCoupling } — category
 * writes a catalog.conf (omit/null for a NUGGS module or to test the no-category
 * case), derives writes a derives.conf. A nuggs-* design gets the coupling
 * include by default (a real NUGGS module is named nuggs-* AND uses the
 * coupling); noCoupling: true withholds it to exercise the name-collision
 * fall-through. Every design gets the entry .scad + README.md readDesigns and
 * the Python discovery both require, and the tree gets the shared
 * categories.conf.
 */
function fixture(spec) {
  const root = mkdtempSync(join(tmpdir(), "print-bench-catalog-"));
  mkdirSync(join(root, "designs"), { recursive: true });
  writeFileSync(join(root, "designs", "categories.conf"), `${VOCAB}\n`);
  for (const [name, opts] of Object.entries(spec)) {
    const dir = join(root, "designs", name);
    mkdirSync(dir, { recursive: true });
    const isNuggsModule =
      (name === "nuggs" || name.startsWith("nuggs-")) && !(opts && opts.noCoupling);
    writeFileSync(
      join(dir, `${name}.scad`),
      isNuggsModule ? "// catalog fixture\ninclude <nuggs-coupling.scad>\n" : "// catalog fixture\n"
    );
    writeFileSync(join(dir, "README.md"), `# ${name}\n\nThe ${name} design.\n`);
    if (opts && opts.category) writeFileSync(join(dir, "catalog.conf"), `category: ${opts.category}\n`);
    if (opts && opts.derives) writeFileSync(join(dir, "derives.conf"), opts.derives);
  }
  return root;
}

/** `scripts/catalog.sh order` as [name, slug] pairs, the authoritative side. */
function catalogPairs(root) {
  const res = spawnSync(
    "bash",
    [join(REPO_ROOT, "scripts", "catalog.sh"), "--root", root, "order"],
    { encoding: "utf8", env: { ...process.env } }
  );
  if (res.error) {
    // Never skip: a cross-check that quietly does not run is indistinguishable
    // from one that passes, and it is the only thing keeping the two
    // implementations honest.
    assert.fail(
      `could not run scripts/catalog.sh (${res.error.message}). ` +
        "bash + python3 are required to cross-check site/lib/catalog.mjs against scripts/catalog.sh."
    );
  }
  assert.equal(res.status, 0, `catalog.sh order failed: ${res.stderr}`);
  return res.stdout
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      const f = line.split("\t");
      return [f[3], f[0]]; // [name, slug]
    });
}

/** The JS grouping as the same [name, slug] pairs. */
function jsPairs(root) {
  const designs = readDesigns(root);
  const groups = groupDesigns(designs, readCategories(root));
  return groups.flatMap((g) => g.designs.map((d) => [d.name, g.slug]));
}

/** `scripts/catalog.sh groups` as [{slug, label, blurb}], the authoritative side. */
function catalogGroups(root) {
  const res = spawnSync(
    "bash",
    [join(REPO_ROOT, "scripts", "catalog.sh"), "--root", root, "groups"],
    { encoding: "utf8", env: { ...process.env } }
  );
  if (res.error) {
    assert.fail(
      `could not run scripts/catalog.sh groups (${res.error.message}). ` +
        "bash is required to cross-check site/lib/catalog.mjs's blurb parsing."
    );
  }
  assert.equal(res.status, 0, `catalog.sh groups failed: ${res.stderr}`);
  return res.stdout
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      const [slug, label, blurb = ""] = line.split("\t");
      return { slug, label, blurb };
    });
}

test("categoryOf: NUGGS by name, catalog.conf otherwise, null when absent", () => {
  const root = fixture({
    "nuggs-den": {}, // NUGGS by prefix, no catalog.conf
    widget: { category: "everyday-functional" },
    orphan: {}, // non-NUGGS, no catalog.conf
  });
  try {
    assert.equal(isNuggs("nuggs-den"), true);
    assert.equal(isNuggs("widget"), false);
    assert.equal(categoryOf(join(root, "designs", "nuggs-den"), "nuggs-den"), "nuggs");
    assert.equal(categoryOf(join(root, "designs", "widget"), "widget"), "everyday-functional");
    assert.equal(categoryOf(join(root, "designs", "orphan"), "orphan"), null);

    const byName = new Map(readDesigns(root).map((d) => [d.name, d]));
    assert.equal(byName.get("nuggs-den").category, "nuggs");
    assert.equal(byName.get("widget").category, "everyday-functional");
    assert.equal(byName.get("orphan").category, null);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("groupDesigns buckets in vocabulary order, dropping empty groups", () => {
  const root = fixture({
    "nuggs-elbow": {},
    zeta: { category: "everyday-functional" },
    alpha: { category: "compliant-mechanisms" },
  });
  try {
    const groups = groupDesigns(readDesigns(root), readCategories(root));
    // nuggs, compliant, everyday — in vocab order, support-free/print-in-place
    // dropped as empty. Not alphabetical (which would be alpha, nuggs, zeta).
    assert.deepEqual(
      groups.map((g) => g.slug),
      ["nuggs", "compliant-mechanisms", "everyday-functional"]
    );
    assert.deepEqual(groups[0].designs.map((d) => d.name), ["nuggs-elbow"]);
    assert.deepEqual(groups[1].designs.map((d) => d.name), ["alpha"]);
    assert.deepEqual(groups[2].designs.map((d) => d.name), ["zeta"]);
    // and it agrees with the authoritative script on this tree.
    assert.deepEqual(jsPairs(root), catalogPairs(root));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("a derivative shares its parent's group, nested, never split across a boundary", () => {
  // The parent is print-in-place; the derivative declares the same. It must
  // land right after its parent inside the print-in-place group, even though a
  // group ordered purely by category could otherwise separate them.
  const root = fixture({
    base: { category: "print-in-place" },
    child: { category: "print-in-place", derives: "variant-of: base\n" },
    other: { category: "compliant-mechanisms" },
  });
  try {
    const groups = groupDesigns(readDesigns(root), readCategories(root));
    const pip = groups.find((g) => g.slug === "print-in-place");
    assert.deepEqual(
      pip.designs.map((d) => [d.depth, d.name]),
      [
        [0, "base"],
        [1, "child"],
      ]
    );
    assert.deepEqual(jsPairs(root), catalogPairs(root));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("indexPage renders one labelled section per group, in order, with the cards", () => {
  const root = fixture({
    "nuggs-open": {},
    widget: { category: "everyday-functional" },
  });
  try {
    const designs = readDesigns(root);
    const groups = groupDesigns(designs, readCategories(root));
    const html = indexPage(designs, { groups });

    // A labelled section per group, in vocab order (NUGGS ecosystem before
    // Everyday functional prints).
    assert.match(html, /class="design-group"[^>]*aria-label="NUGGS ecosystem"/);
    assert.match(html, /<p class="group-label">NUGGS ecosystem<\/p>/);
    assert.match(html, /<p class="group-label">Everyday functional prints<\/p>/);
    assert.ok(
      html.indexOf("NUGGS ecosystem") < html.indexOf("Everyday functional prints"),
      "NUGGS group should render before the Everyday group"
    );
    // The cards still render inside the groups.
    assert.match(html, /href="\/designs\/nuggs-open\/"/);
    assert.match(html, /href="\/designs\/widget\/"/);

    // Without groups it falls back to one flat grid (the lineage tests' path).
    const flat = indexPage(designs);
    assert.doesNotMatch(flat, /design-group/);
    assert.match(flat, /<section class="grid">/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("the optional promise blurb parses without gluing onto the label, and the port agrees with catalog.sh", () => {
  const root = fixture({ "nuggs-open": {}, box: { category: "support-free" } });
  try {
    const cats = readCategories(root);
    const bySlug = new Map(cats.map((c) => [c.slug, c]));
    // The promise headings carry a blurb; the label must NOT have absorbed it.
    assert.equal(bySlug.get("support-free").label, "Designing around supports");
    assert.equal(bySlug.get("support-free").blurb, "Leave slicer supports off.");
    assert.equal(bySlug.get("print-in-place").blurb, "Keep auto-supports off.");
    // Navigational headings have no blurb.
    assert.equal(bySlug.get("nuggs").blurb, "");
    assert.equal(bySlug.get("everyday-functional").blurb, "");

    // The port agrees with the authoritative catalog.sh on slug/label/blurb.
    assert.deepEqual(
      cats.map((c) => [c.slug, c.label, c.blurb]),
      catalogGroups(root).map((g) => [g.slug, g.label, g.blurb])
    );

    // The blurb reaches the rendered index, under its group; a blurb-less group
    // renders none.
    const designs = readDesigns(root);
    const groups = groupDesigns(designs, cats);
    const html = indexPage(designs, { groups });
    assert.match(html, /<p class="group-blurb">Leave slicer supports off\.<\/p>/);
    const nuggsSection = html.slice(
      html.indexOf("NUGGS ecosystem"),
      html.indexOf("Designing around supports")
    );
    assert.doesNotMatch(nuggsSection, /group-blurb/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("readCategories refuses a malformed record, a duplicate slug or an empty label — and catalog.sh agrees (issue #374 parity)", () => {
  const write = (body) => {
    const root = mkdtempSync(join(tmpdir(), "print-bench-catalog-vocab-"));
    mkdirSync(join(root, "designs"), { recursive: true });
    writeFileSync(join(root, "designs", "categories.conf"), body);
    return root;
  };
  // catalog.sh `groups` only loads the vocabulary (no designs needed), so it is
  // the authority to cross-check the port's refusals against — both surfaces
  // must reject the same records, or a Node-only deploy could publish what the
  // bash gate would have blocked.
  const catalogGroupsExit = (root) =>
    spawnSync("bash", [join(REPO_ROOT, "scripts", "catalog.sh"), "--root", root, "groups"], {
      encoding: "utf8",
      env: { ...process.env },
    }).status;

  const cases = [
    ["a non-blank record with no |", "nuggs | NUGGS ecosystem\nnot-a-record\n", /not '<slug>/],
    ["a duplicate slug", "nuggs | NUGGS ecosystem\nnuggs | NUGGS again\n", /duplicate category slug 'nuggs'/],
    ["an empty label", "nuggs | NUGGS ecosystem\nempty-label |\n", /empty slug or label/],
  ];
  for (const [why, body, rx] of cases) {
    const root = write(body);
    try {
      assert.throws(() => readCategories(root), rx, `the port should refuse ${why}`);
      assert.notEqual(catalogGroupsExit(root), 0, `catalog.sh should also refuse ${why}`);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  }

  // Positive control: a well-formed vocabulary still parses on both sides (the
  // refusal isn't a blanket throw), and they agree on slug/label/blurb.
  const ok = write(
    "nuggs | NUGGS ecosystem\nsupport-free | Designing around supports | Leave supports off.\n"
  );
  try {
    const cats = readCategories(ok);
    assert.deepEqual(
      cats.map((c) => c.slug),
      ["nuggs", "support-free"]
    );
    assert.equal(cats[1].blurb, "Leave supports off.");
    assert.deepEqual(
      cats.map((c) => [c.slug, c.label, c.blurb]),
      catalogGroups(ok).map((g) => [g.slug, g.label, g.blurb])
    );
  } finally {
    rmSync(ok, { recursive: true, force: true });
  }
});

test("a coupling-less nuggs-* name is a collision, grouped by its category on both surfaces (issue #374)", () => {
  // nuggs-yard's shape: a nuggs-* NAME with no coupling include is NOT a NUGGS
  // module — it groups by its declared category, and the port must agree with
  // catalog.sh, or the collision would land in a different aisle on each surface.
  const root = fixture({
    "nuggs-real": {}, // real NUGGS module (coupling via the fixture default)
    "nuggs-yardish": { category: "everyday-functional", noCoupling: true }, // the collision
    widget: { category: "compliant-mechanisms" },
  });
  try {
    assert.equal(categoryOf(join(root, "designs", "nuggs-real"), "nuggs-real"), "nuggs");
    assert.equal(
      categoryOf(join(root, "designs", "nuggs-yardish"), "nuggs-yardish"),
      "everyday-functional"
    );
    const groups = groupDesigns(readDesigns(root), readCategories(root));
    const bySlug = new Map(groups.map((g) => [g.slug, g.designs.map((d) => d.name)]));
    assert.deepEqual(bySlug.get("nuggs"), ["nuggs-real"]);
    assert.ok(
      bySlug.get("everyday-functional").includes("nuggs-yardish"),
      "the coupling-less nuggs-* name groups by its declared category"
    );
    // And the port agrees with the authoritative script — membership and order.
    assert.deepEqual(jsPairs(root), catalogPairs(root));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("the real repo's site grouping agrees with scripts/catalog.sh", () => {
  // The regression that pins the port to the authority on the live catalog:
  // same designs, same groups, same order — membership, group order and
  // within-group nesting all at once, as [name, slug] pairs.
  assert.deepEqual(jsPairs(REPO_ROOT), catalogPairs(REPO_ROOT));

  // And the same for the group headings + promise blurbs.
  assert.deepEqual(
    readCategories(REPO_ROOT).map((c) => [c.slug, c.label, c.blurb]),
    catalogGroups(REPO_ROOT).map((g) => [g.slug, g.label, g.blurb])
  );

  // Sanity: every real design is grouped (nothing lands in the Other bucket),
  // so the catalog signal covers the whole tree.
  const groups = groupDesigns(readDesigns(REPO_ROOT), readCategories(REPO_ROOT));
  assert.equal(
    groups.some((g) => g.slug === "__other__"),
    false,
    "some design has no category — every design must be in a real group"
  );
});
