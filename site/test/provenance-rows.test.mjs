// The provenance harvester's committed-row parsers, held to the site parsers
// they were ported from (docs/provenance.md §Episodes, critique item 25).
//
// tools/provenance/src/provenance/episodes.py re-implements three readers of
// site/lib/timeline.mjs — parseDecisionLog (PM.md "## Decision log"),
// parseFieldTestLog and parseChangelog (NOTES.md) — so the harvester can
// turn committed rows into day-precision events with the commit that added
// each line. Two readers of one file disagreeing about which lines are rows
// is exactly the drift this file exists to catch: the site would render a
// row the provenance bundle has no event for, or the bundle would carry a
// row the site never shows. So every case below runs BOTH implementations
// over the same text and fails on any difference in the selected lines.
//
// It lives in the site's suite, not in tools/provenance's pytest, because
// timeline.mjs imports `marked` (through markdown.mjs) and so needs
// site/node_modules; the site-build job runs `npm --prefix site test` on
// every PR, so a change on either side is caught by a required check (the
// site/lib/lineage.mjs ↔ tools/lineage precedent). The Python side gets the
// very strings this file read, on stdin, so both stacks parse identical
// input — line endings and all.

import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { parseDecisionLog, parseFieldTestLog, parseChangelog } from "../lib/timeline.mjs";

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));

/** The rows timeline.mjs selects from one file, in the shape episodes.rows_json emits. */
function jsRows(name, text) {
  const out = [];
  if (name === "PM.md") {
    for (const e of parseDecisionLog(text).entries) out.push({ date: e.date, kind: "decision.pm_log", line: e.lineno });
  } else if (name === "NOTES.md") {
    for (const e of parseFieldTestLog(text).entries) out.push({ date: e.date, kind: "field_test", line: e.lineno });
    for (const e of parseChangelog(text).entries) out.push({ date: e.date, kind: "changelog", line: e.lineno });
  }
  return out.sort((a, b) => a.line - b.line);
}

/** Run the Python ports over {path: text}; NOTES.md bullets (no JS counterpart) are dropped. */
function pythonRows(texts) {
  const res = spawnSync(
    "python3",
    ["-c", "import json, sys\nfrom provenance import episodes\nprint(episodes.rows_json(json.load(sys.stdin)))"],
    {
      encoding: "utf8",
      input: JSON.stringify(texts),
      env: { ...process.env, PYTHONPATH: join(REPO_ROOT, "tools", "provenance", "src") },
      maxBuffer: 64 * 1024 * 1024,
    },
  );
  if (res.error) {
    // Never skip: a cross-check that quietly does not run is indistinguishable
    // from one that passes, and this is the only thing keeping the ports honest.
    assert.fail(`could not run the Python ports (${res.error.message}); python3 is required to cross-check episodes.py against timeline.mjs`);
  }
  assert.equal(res.status, 0, `episodes.rows_json failed: ${res.stderr}`);
  const parsed = JSON.parse(res.stdout);
  for (const path of Object.keys(parsed)) parsed[path] = parsed[path].filter((r) => r.kind !== "decision.notes_log");
  return parsed;
}

function compare(texts) {
  const py = pythonRows(texts);
  const js = {};
  for (const [path, text] of Object.entries(texts)) js[path] = jsRows(path.split("/").pop(), text);
  assert.deepEqual(py, js);
  return js;
}

/** Every designs/<d>/PM.md and NOTES.md in the checkout. */
function committedFiles() {
  const texts = {};
  const root = join(REPO_ROOT, "designs");
  for (const d of readdirSync(root, { withFileTypes: true })) {
    if (!d.isDirectory()) continue;
    for (const name of ["PM.md", "NOTES.md"]) {
      const p = join(root, d.name, name);
      if (existsSync(p)) texts[`designs/${d.name}/${name}`] = readFileSync(p, "utf8");
    }
  }
  return texts;
}

test("episodes.py selects the same PM.md / NOTES.md rows as timeline.mjs over every committed design", () => {
  const texts = committedFiles();
  assert.ok(Object.keys(texts).length > 20, "expected the committed designs' PM.md / NOTES.md files");
  const rows = compare(texts);
  // Not vacuous: the corpus really carries rows of every ported kind.
  const kinds = new Set(Object.values(rows).flat().map((r) => r.kind));
  for (const kind of ["decision.pm_log", "field_test", "changelog"]) assert.ok(kinds.has(kind), `no ${kind} row in the corpus`);
});

test("the ports agree on the edge shapes (escaped pipes, CRLF, JS whitespace, bad dates, headings)", () => {
  const pm = [
    "﻿# PM",
    "",
    "## Decision log",
    "",
    "A note | with a pipe in prose.",
    "",
    "| Date | Decision | Reason |",
    "|:---|:---:|---:|",
    "| 2026-08-01 | Keep it | because |",
    "| 2026-02-29 | not a leap year | x |",
    "| 2024-02-29 | a leap year | x |",
    "| 0000-02-29 | year zero | x |",
    "| 2026-08-02 | nbsp-padded | x |",
    "| 2026-08-03 | Escaped \\| pipe | ok |",
    "| 2026-08-04 | Too | many | cells |",
    "| 2026-08-05 |  | empty |",
    "| ２０２６-08-06 | full-width digits | x |",
    "",
    "| 2026-08-07 | after the blank | not read |",
  ].join("\n");
  const notes = [
    "# Notes",
    "## Field test log",
    "### 2026-09-01 — Prusa MK4",
    "### 2026-09-02 - Bambu",
    "### 2026-09-03 — nbsp after the hashes",
    "### 2026-09-04  — a line separator",
    "#### 2026-09-05 — level four",
    "### 2026-09-31 — no such day",
    "## Changelog",
    "### v0.2 — 2026-09-06 — field-driven",
    "### v0.3 - 2026-09-07 - hyphens",
    "### v0.4 — 2026-09-08 — X",
    "### v0.5 —2026-09-09 — tight",
    "# Top",
    "### v0.6 — 2026-09-10 — after the section",
  ].join("\n");
  const rows = compare({
    "designs/x/PM.md": pm,
    "designs/x/NOTES.md": notes,
    "designs/y/PM.md": pm.replace(/\n/g, "\r\n"),
    "designs/y/NOTES.md": notes.replace(/\n/g, "\r\n"),
  });
  assert.ok(rows["designs/x/PM.md"].length >= 3 && rows["designs/x/NOTES.md"].length >= 3);
});

test("a drifted port would be caught (negative control)", () => {
  const text = "## Decision log\n\n| Date | Decision | Reason |\n|---|---|---|\n| 2026-08-01 | A | b |\n";
  const py = pythonRows({ "designs/z/PM.md": text });
  assert.equal(py["designs/z/PM.md"].length, 1);
  assert.notDeepEqual(py, { "designs/z/PM.md": [] });
  assert.notDeepEqual(py, { "designs/z/PM.md": [{ date: "2026-08-01", kind: "decision.pm_log", line: 4 }] });
});
