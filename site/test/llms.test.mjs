// The AI-native serving layer (lib/llms.mjs): /llms.txt, /llms-full.txt and
// the docs served as raw markdown.
//
// Two kinds of pinning here. The pure functions get fixture tests with a
// negative control per rule — a broken local reference must FAIL, a doc
// without an H1 must FAIL — because a checker that cannot fail checks
// nothing. And the real repo gets a census: the contributor docs and the
// architecture docs must exist and read clean, so deleting one (or breaking
// a link inside one) fails `npm --prefix site test` before it 404s for an
// LLM in production.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import {
  DOC_DIRS,
  docSummary,
  localRefProblems,
  readServableDocs,
  llmsTxt,
  llmsFullTxt,
} from "../lib/llms.mjs";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

function fixtureRepo(files) {
  const root = mkdtempSync(join(tmpdir(), "llms-test-"));
  for (const [rel, text] of Object.entries(files)) {
    mkdirSync(join(root, dirname(rel)), { recursive: true });
    writeFileSync(join(root, rel), text);
  }
  return root;
}

test("docSummary: first sentence of the first prose paragraph, as plain text", () => {
  const md = [
    "# Title",
    "",
    "![shot](previews/x.png)",
    "> a quote is not the summary",
    "| a | b |",
    "",
    "The actual summary line.",
    "More prose in the same paragraph.",
  ].join("\n");
  assert.equal(docSummary(md), "The actual summary line.");
  assert.equal(docSummary("# Only a title\n"), "");
});

test("docSummary: a paragraph opening with an inline link is prose, a badge is not", () => {
  const linkFirst = "# T\n\n[gate.sh](../gate.sh) is the bar. More.\n";
  assert.equal(docSummary(linkFirst), "gate.sh is the bar.");
  const badgeFirst = "# T\n\n[![ci](badge.svg)](https://x)\n\nReal summary.\n";
  assert.equal(docSummary(badgeFirst), "Real summary.");
});

test("localRefProblems: link syntax quoted in a code fence is not a reference", () => {
  const root = fixtureRepo({ "docs/contributing/a.md": "x" });
  try {
    const md = "```md\n[example](does-not-exist.md)\n```\nprose\n";
    assert.deepEqual(localRefProblems("docs/contributing/a.md", md, root), []);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("docSummary: joins wrapped lines and strips markdown syntax", () => {
  const md = [
    "# T",
    "",
    "A summary that wraps across **two lines** and links",
    "[the guide](../guide.md) before ending here. A second sentence.",
  ].join("\n");
  assert.equal(
    docSummary(md),
    "A summary that wraps across two lines and links the guide before ending here."
  );
});

test("localRefProblems: resolves relative and root-relative, ignores external", () => {
  const root = fixtureRepo({
    "docs/contributing/a.md": "x",
    "docs/contributing/b.md": "x",
    "scripts/check.sh": "x",
  });
  try {
    const md = [
      "[sibling](b.md)",
      "[root](/scripts/check.sh)",
      "[updir](../../scripts/check.sh)",
      "[ext](https://example.com/x)",
      "[mail](mailto:x@example.com)",
      "[frag](#section)",
      "[anchored](b.md#part)",
    ].join("\n");
    assert.deepEqual(localRefProblems("docs/contributing/a.md", md, root), []);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("localRefProblems: a broken reference fails (negative control)", () => {
  const root = fixtureRepo({ "docs/contributing/a.md": "x" });
  try {
    const problems = localRefProblems(
      "docs/contributing/a.md",
      "[gone](missing.md) [escape](../../../etc/passwd)",
      root
    );
    assert.equal(problems.length, 2);
    assert.match(problems[0], /broken local reference: missing\.md/);
    assert.match(problems[1], /escapes the repo/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("readServableDocs: README.md leads each dir, rest alphabetical", () => {
  const root = fixtureRepo({
    "docs/contributing/zebra.md": "# Z\n\nZ doc.\n",
    "docs/contributing/README.md": "# Index\n\nThe index.\n",
    "docs/contributing/alpha.md": "# A\n\nA doc.\n",
    "docs/architecture/README.md": "# Arch\n\nArch index.\n",
  });
  try {
    const errors = [];
    const docs = readServableDocs(root, { onError: (m) => errors.push(m) });
    assert.deepEqual(errors, []);
    assert.deepEqual(
      docs.map((d) => d.relPath),
      [
        "docs/contributing/README.md",
        "docs/contributing/alpha.md",
        "docs/contributing/zebra.md",
        "docs/architecture/README.md",
      ]
    );
    assert.equal(docs[0].title, "Index");
    assert.equal(docs[0].summary, "The index.");
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("readServableDocs: missing H1 and missing dir both report (negative controls)", () => {
  const root = fixtureRepo({
    "docs/contributing/bare.md": "no heading here\n",
  });
  try {
    const errors = [];
    readServableDocs(root, { onError: (m) => errors.push(m) });
    assert.ok(
      errors.some((m) => m.includes("bare.md") && m.includes("no H1")),
      `expected a no-H1 report, got: ${errors}`
    );
    assert.ok(
      errors.some((m) => m.includes("docs/architecture")),
      `expected a missing-dir report, got: ${errors}`
    );
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("llms.txt: indexes every served source with root-relative paths", () => {
  const docs = [
    { relPath: "docs/contributing/README.md", title: "Contributing", summary: "How." },
    { relPath: "docs/architecture/README.md", title: "Architecture", summary: "What." },
  ];
  const designs = [
    { relDir: "designs/foo", title: "Foo", pitch: "A foo." },
  ];
  const styles = [{ relDir: "styles/bar", title: "Bar", summary: "A bar." }];
  const txt = llmsTxt({ docs, designs, styles, repoUrl: "https://github.example/r" });

  assert.match(txt, /^# print-bench\n/);
  assert.match(txt, /\n> /);
  assert.ok(txt.includes("- [Contributing](/docs/contributing/README.md): How."));
  assert.ok(txt.includes("- [Architecture](/docs/architecture/README.md): What."));
  assert.ok(txt.includes("- [Foo](/designs/foo/README.md): A foo."));
  assert.ok(txt.includes("- [Bar](/styles/bar/STYLE.md): A bar."));
  // Exact-line membership, not substring matching: stronger assertions, and
  // a URL substring check is the shape CodeQL rightly flags elsewhere.
  const txtLines = txt.split("\n");
  assert.ok(
    txtLines.includes(
      "- [llms-full.txt](/llms-full.txt): the platform docs above, concatenated into one file"
    )
  );
  assert.ok(
    txtLines.includes(
      "- [Source repository](https://github.example/r): every file this site is generated from"
    )
  );
  assert.ok(!txt.includes("undefined"), "no undefined leaked into the index");
});

test("llms-full.txt: concatenates the docs with their served paths", () => {
  const full = llmsFullTxt([
    { relPath: "docs/contributing/README.md", text: "# A\n\nbody A\n" },
    { relPath: "docs/architecture/README.md", text: "# B\n\nbody B\n" },
  ]);
  assert.ok(full.includes("<!-- source: /docs/contributing/README.md -->"));
  assert.ok(full.includes("<!-- source: /docs/architecture/README.md -->"));
  assert.ok(full.includes("body A"));
  assert.ok(full.includes("body B"));
});

test("census: the real repo's served docs exist and read clean", () => {
  const errors = [];
  const docs = readServableDocs(REPO_ROOT, { onError: (m) => errors.push(m) });
  assert.deepEqual(errors, [], "served docs must have H1s and resolving links");

  const paths = docs.map((d) => d.relPath);
  for (const required of [
    "docs/contributing/README.md",
    "docs/architecture/README.md",
    "docs/architecture/ci-platform.md",
    "docs/architecture/design-workflow.md",
  ]) {
    assert.ok(paths.includes(required), `missing served doc: ${required}`);
  }
  for (const d of docs) {
    assert.ok(d.title, `${d.relPath} has no title`);
    assert.ok(d.summary, `${d.relPath} has no summary line for the index`);
  }
  // Both DOC_DIRS contributed — the index never silently loses a section.
  for (const dir of DOC_DIRS) {
    assert.ok(
      paths.some((p) => p.startsWith(`${dir}/`)),
      `no docs served from ${dir}/`
    );
  }

  // The contributor guide's own map table must name every sibling page:
  // the serving layer picks a new page up automatically, but the index is
  // hand-written prose — this is the mechanical completeness check that
  // keeps the two from drifting apart.
  const guideIndex = docs.find((d) => d.relPath === "docs/contributing/README.md");
  for (const d of docs) {
    if (!d.relPath.startsWith("docs/contributing/")) continue;
    if (d.relPath === "docs/contributing/README.md") continue;
    const name = d.relPath.split("/").pop();
    assert.ok(
      guideIndex.text.includes(`(${name})`),
      `docs/contributing/README.md's map does not link ${name}`
    );
  }
});
