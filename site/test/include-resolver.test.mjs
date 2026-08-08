// The site's OpenSCAD include resolver (buildModel's `resolve`, driving
// includeClosure) reads each `include <…>` / `use <…>` ref off the source and
// embeds the file's bytes verbatim into the publicly served model.json. Issue
// #120: it must never read a file outside the repo. These tests pin both
// directions the fix has to hold at once — a legitimate nested include still
// resolves, and a traversal or absolute ref is refused — exactly as the issue
// asks ("ship it with a test that pins both").
//
// The tests exercise the real public path (buildModel → includeClosure), so the
// negative cases plant an actual readable secret *outside* the repo root and
// assert its bytes never reach model.files: if the containment check is removed,
// the first candidate root resolves that secret and the test fails.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, symlinkSync, rmSync } from "node:fs";
import { dirname, join, isAbsolute } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

import { readDesigns } from "../lib/content.mjs";
import { buildModel } from "../lib/model.mjs";

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));

const SECRET = "SUPER_SECRET_TOKEN_c0ffee";

/**
 * A throwaway two-level tree: a `repo/` root written from `files`, and a
 * `secret.scad` planted one directory *above* it (still readable, outside the
 * repo). Returns { parent, repoRoot, secretAbs }.
 */
function fixture(files) {
  const parent = mkdtempSync(join(tmpdir(), "print-bench-resolver-"));
  const repoRoot = join(parent, "repo");
  const secretAbs = join(parent, "secret.scad");
  writeFileSync(secretAbs, `// ${SECRET}\ncube(1);\n`);
  for (const [rel, contents] of Object.entries(files)) {
    const abs = join(repoRoot, rel);
    mkdirSync(dirname(abs), { recursive: true });
    writeFileSync(abs, contents);
  }
  return { parent, repoRoot, secretAbs };
}

/** buildModel for a design placed at designs/<name>/<name>.scad in the fixture. */
function model(repoRoot, name) {
  return buildModel(repoRoot, { name, relDir: `designs/${name}`, title: name });
}

// AC1 — a ref whose `../` segments normalize outside the repo is refused, and
// the secret it points at is never embedded. `join("lib", "../../secret.scad")`
// resolves to `<parent>/secret.scad`; without the containment check that first
// candidate would be read.
test("a traversal ref that escapes the repo root is refused", () => {
  const { parent, repoRoot } = fixture({
    "designs/evil/evil.scad": "include <../../secret.scad>\ncube(10);\n",
    "designs/evil/README.md": "# Evil\n",
  });
  try {
    const m = model(repoRoot, "evil");
    assert.doesNotMatch(
      JSON.stringify(m.files),
      new RegExp(SECRET),
      "traversal ref must not embed a file from outside the repo"
    );
    for (const key of Object.keys(m.files)) {
      assert.ok(!key.startsWith(".."), `resolved path escaped the repo: ${key}`);
    }
  } finally {
    rmSync(parent, { recursive: true, force: true });
  }
});

// AC2 — an absolute ref is refused even when it points at a file that exists.
test("an absolute ref is refused", () => {
  const { parent, repoRoot, secretAbs } = fixture({ "designs/abs/README.md": "# Abs\n" });
  assert.ok(isAbsolute(secretAbs), "test precondition: secret path is absolute");
  writeFileSync(join(repoRoot, "designs/abs/abs.scad"), `include <${secretAbs}>\ncube(10);\n`);
  try {
    const m = model(repoRoot, "abs");
    assert.doesNotMatch(
      JSON.stringify(m.files),
      new RegExp(SECRET),
      "absolute ref must not embed a file"
    );
  } finally {
    rmSync(parent, { recursive: true, force: true });
  }
});

// AC1 (symlink vector) — a ref that resolves to a symlink *inside* the repo
// whose real target is *outside* it is refused. Only the real-path
// (symlink-resolved) containment check catches this: a check on the
// pre-resolution path would see an in-repo path and let it through. Without
// this case, swapping the resolver's realpath for a plain path-normalize would
// keep the traversal/absolute tests green while reopening the escape.
test("an in-repo symlink whose target escapes the repo root is refused", () => {
  const { parent, repoRoot, secretAbs } = fixture({
    "designs/link/link.scad": "include <leak.scad>\ncube(10);\n",
    "designs/link/README.md": "# Link\n",
  });
  symlinkSync(secretAbs, join(repoRoot, "designs/link/leak.scad"));
  try {
    const m = model(repoRoot, "link");
    assert.doesNotMatch(
      JSON.stringify(m.files),
      new RegExp(SECRET),
      "a symlink resolving outside the repo must not embed its target"
    );
    for (const key of Object.keys(m.files)) {
      assert.ok(!key.startsWith(".."), `resolved path escaped the repo: ${key}`);
    }
  } finally {
    rmSync(parent, { recursive: true, force: true });
  }
});

// AC3 — the legitimate roots still resolve: a lib ref, the design's own-dir
// sibling, and a nested repo-root ref (the `styles/<n>/style.scad` shape the
// issue's "Care" note calls out).
test("legitimate lib, own-dir, and nested includes still resolve", () => {
  const { parent, repoRoot } = fixture({
    "lib/helper-lib.scad": "// lib helper\n",
    "designs/good/good.scad":
      "include <helper-lib.scad>\ninclude <sibling.scad>\ninclude <styles/s/style.scad>\ncube(10);\n",
    "designs/good/sibling.scad": "// design sibling\n",
    "designs/good/README.md": "# Good\n",
    "styles/s/style.scad": "// nested style token\n",
  });
  try {
    const m = model(repoRoot, "good");
    assert.ok(m.files["lib/helper-lib.scad"] !== undefined, "lib include did not resolve");
    assert.ok(m.files["designs/good/sibling.scad"] !== undefined, "own-dir sibling did not resolve");
    assert.ok(m.files["styles/s/style.scad"] !== undefined, "nested repo-root include did not resolve");
  } finally {
    rmSync(parent, { recursive: true, force: true });
  }
});

// AC4 — every resolved path is repo-relative: never absolute, never begins with
// "..". Checked on the fixture above and across every real design.
test("every resolved include path is repo-relative, on fixtures and the real repo", () => {
  const { parent, repoRoot } = fixture({
    "lib/helper-lib.scad": "// lib helper\n",
    "designs/good/good.scad": "include <helper-lib.scad>\ninclude <styles/s/style.scad>\ncube(1);\n",
    "designs/good/README.md": "# Good\n",
    "styles/s/style.scad": "// nested\n",
  });
  try {
    const m = model(repoRoot, "good");
    assert.ok(Object.keys(m.files).length > 0, "fixture produced no include closure");
    for (const key of Object.keys(m.files)) {
      assert.ok(!isAbsolute(key), `resolved path is absolute: ${key}`);
      assert.ok(!key.startsWith(".."), `resolved path begins with "..": ${key}`);
    }
  } finally {
    rmSync(parent, { recursive: true, force: true });
  }

  for (const design of readDesigns(REPO_ROOT)) {
    const m = buildModel(REPO_ROOT, design);
    for (const key of Object.keys(m.files)) {
      assert.ok(!isAbsolute(key), `${design.name}: resolved path is absolute: ${key}`);
      assert.ok(!key.startsWith(".."), `${design.name}: resolved path begins with "..": ${key}`);
    }
  }
});
