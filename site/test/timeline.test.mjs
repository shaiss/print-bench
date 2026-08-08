// The "History of work together" timeline reader (issue #126).
//
// Why this exists: like the team registry (#123), the timeline is built
// from structured committed content — a PM.md decision-log table — that
// never passes through the markdown reference checker. Its own line-shape
// rules are the only thing standing between a drifted log and a team page
// rendering a hole (or, worse, inventing history). These tests pin the
// shape the reader accepts and — the part that matters most — the shapes it
// must refuse: a gate that stops firing looks identical to one that passes.
//
// The last test runs the reader against the real calibration-cube PM.md, so
// the worked example this issue calibrates on cannot silently rot while the
// fixtures stay green.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

import {
  parseDecisionLog,
  parseFieldTestLog,
  decisionLogSource,
  fieldTestSource,
  SOURCES,
  readTimeline,
  historyTimeline,
} from "../lib/timeline.mjs";

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));

const DECISION_LOG = `# design — product charter

## Decision log

Append-only. Date, decision, reason.

| Date | Decision | Reason |
|---|---|---|
| 2026-08-06 | First choice | Because A |
| 2026-08-08 | Second choice | Because B |

## Out of scope

Something else entirely.
`;

// --- parseDecisionLog: the accepted shape ---------------------------------

test("parseDecisionLog reads a well-formed table, no problems", () => {
  const { entries, problems } = parseDecisionLog(DECISION_LOG);
  assert.deepEqual(problems, []);
  assert.equal(entries.length, 2);
  assert.deepEqual(
    entries.map((e) => [e.date, e.decision, e.reason]),
    [
      ["2026-08-06", "First choice", "Because A"],
      ["2026-08-08", "Second choice", "Because B"],
    ],
  );
});

test("parseDecisionLog stops the table at the next heading, not swallowing prose", () => {
  const { entries } = parseDecisionLog(DECISION_LOG);
  assert.ok(!entries.some((e) => /Out of scope|Something/.test(e.decision)));
});

test("parseDecisionLog unescapes a pipe inside a cell", () => {
  const text = `## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-08 | Support A \\| B modes | Both are needed |
`;
  const { entries, problems } = parseDecisionLog(text);
  assert.deepEqual(problems, []);
  assert.equal(entries[0].decision, "Support A | B modes");
});

test("parseDecisionLog treats an absent section as a quiet zero (no problem)", () => {
  const { entries, problems } = parseDecisionLog("# charter\n\n## Non-negotiables\n\nnope\n");
  assert.deepEqual(entries, []);
  assert.deepEqual(problems, []);
});

// --- parseDecisionLog: negative controls (the gate must fire) --------------

test("NEGATIVE: a malformed row (wrong cell count) is a problem, others kept", () => {
  const text = `## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-06 | Good row | Fine |
| 2026-08-07 | Missing the reason cell |
| 2026-08-08 | Another good row | Also fine |
`;
  const { entries, problems } = parseDecisionLog(text);
  assert.equal(entries.length, 2, "the two well-formed rows survive");
  assert.equal(problems.length, 1);
  assert.match(problems[0], /must have 3 cells/);
});

test("NEGATIVE: a non-calendar date is a problem", () => {
  const text = `## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-02-30 | Impossible date | nope |
`;
  const { entries, problems } = parseDecisionLog(text);
  assert.deepEqual(entries, []);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /real YYYY-MM-DD/);
});

test("NEGATIVE: a drifted header is a problem (the pinned shape moved)", () => {
  const text = `## Decision log

| When | What | Why |
|---|---|---|
| 2026-08-08 | x | y |
`;
  const { entries, problems } = parseDecisionLog(text);
  assert.deepEqual(entries, []);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /header must be \| Date \| Decision \| Reason \|/);
});

test("NEGATIVE: a section with no table at all is a problem", () => {
  const text = "## Decision log\n\nWe never actually added the table.\n";
  const { entries, problems } = parseDecisionLog(text);
  assert.deepEqual(entries, []);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /no table/);
});

test("NEGATIVE: a header with no separator row is a problem", () => {
  const text = `## Decision log

| Date | Decision | Reason |
| 2026-08-08 | x | y |
`;
  const { entries, problems } = parseDecisionLog(text);
  assert.deepEqual(entries, []);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /separator row/);
});

// --- parseFieldTestLog (optional source) ----------------------------------

test("parseFieldTestLog reads ### date — printer subheadings", () => {
  const text = `## Field test log

### 2026-08-08 — Prusa MK4
- **Result:** fit was good

### 2026-08-09 - Bambu A1
- **Result:** also fine
`;
  const { entries, problems } = parseFieldTestLog(text);
  assert.deepEqual(problems, []);
  assert.deepEqual(
    entries.map((e) => [e.date, e.printer]),
    [
      ["2026-08-08", "Prusa MK4"],
      ["2026-08-09", "Bambu A1"],
    ],
  );
});

test("parseFieldTestLog: absent section is a quiet zero", () => {
  const { entries, problems } = parseFieldTestLog("## NOTES\n\nno field tests\n");
  assert.deepEqual(entries, []);
  assert.deepEqual(problems, []);
});

test("NEGATIVE: a field-test heading without a real date is a problem", () => {
  const text = "## Field test log\n\n### someday — a printer\n- nope\n";
  const { entries, problems } = parseFieldTestLog(text);
  assert.deepEqual(entries, []);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /real YYYY-MM-DD/);
});

// --- the adapters + assembly ----------------------------------------------

const ROSTER = { pm: { handle: "vera", name: "Vera", kind: "agent", initials: "V" } };

test("decisionLogSource attributes to the roster pm and tags the source", () => {
  const { events, problems } = decisionLogSource.read({ pmText: DECISION_LOG, roster: ROSTER });
  assert.deepEqual(problems, []);
  assert.equal(events.length, 2);
  assert.ok(events.every((e) => e.handle === "vera"));
  assert.ok(events.every((e) => e.sourceTag === "decision · PM.md"));
});

test("decisionLogSource with no roster leaves events unattributed (handle null)", () => {
  const { events } = decisionLogSource.read({ pmText: DECISION_LOG, roster: null });
  assert.ok(events.every((e) => e.handle === null));
});

test("fieldTestSource never attributes (a printer is not a member)", () => {
  const text = "## Field test log\n\n### 2026-08-08 — Prusa MK4\n- ok\n";
  const { events } = fieldTestSource.read({ notesText: text });
  assert.equal(events.length, 1);
  assert.equal(events[0].handle, null);
  assert.equal(events[0].sourceTag, "field test · NOTES.md");
});

test("a source given a null file yields nothing (absent = quiet)", () => {
  assert.deepEqual(decisionLogSource.read({ pmText: null, roster: ROSTER }).events, []);
  assert.deepEqual(fieldTestSource.read({ notesText: null }).events, []);
});

test("readTimeline merges sources newest-first and collects problems", () => {
  const notes = "## Field test log\n\n### 2026-08-07 — Prusa MK4\n- ok\n";
  const { events, problems } = readTimeline({ pmText: DECISION_LOG, notesText: notes, roster: ROSTER });
  assert.deepEqual(problems, []);
  // Two decisions (08-06, 08-08) + one field test (08-07), newest first.
  assert.deepEqual(
    events.map((e) => e.date),
    ["2026-08-08", "2026-08-07", "2026-08-06"],
  );
  assert.equal(events[0].source, "decision-log");
  assert.equal(events[1].source, "field-test");
});

test("readTimeline surfaces a bad row's problem", () => {
  const bad = `## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-02-30 | impossible | x |
`;
  const { problems } = readTimeline({ pmText: bad, notesText: null, roster: ROSTER });
  assert.equal(problems.length, 1);
  assert.match(problems[0], /real YYYY-MM-DD/);
});

test("SOURCES is the committed-only default set, in declaration order", () => {
  assert.deepEqual(SOURCES.map((s) => s.id), ["decision-log", "field-test"]);
});

test("the seam accepts a custom source set without touching assembly", () => {
  const stub = {
    id: "stub",
    label: "stub",
    read: () => ({ events: [{ date: "2030-01-01", source: "stub", sourceTag: "stub", text: "hi", detail: "", handle: null }], problems: [] }),
  };
  const { events } = readTimeline({ pmText: null, notesText: null, roster: null }, [stub]);
  assert.equal(events.length, 1);
  assert.equal(events[0].source, "stub");
});

// --- the render ------------------------------------------------------------

const PEOPLE = new Map([["vera", { handle: "vera", name: "Vera", kind: "agent", initials: "V" }]]);

test("historyTimeline renders events newest-first with source tags and attribution", () => {
  const { events } = readTimeline({ pmText: DECISION_LOG, notesText: null, roster: ROSTER });
  const html = historyTimeline(events, { people: PEOPLE });
  assert.match(html, /History of work together/);
  assert.match(html, /decision · PM\.md/);
  assert.match(html, /2026-08-08/);
  // Attribution monogram + name for the resolvable handle.
  assert.match(html, /monogram-agent/);
  assert.match(html, /Vera/);
  // Newest-first: the 08-08 decision appears before the 08-06 one.
  assert.ok(html.indexOf("Second choice") < html.indexOf("First choice"));
});

test("historyTimeline shows an honest empty state, inventing nothing", () => {
  const html = historyTimeline([], { people: PEOPLE });
  assert.match(html, /No shared history recorded yet/);
  assert.doesNotMatch(html, /<ol class="timeline">/);
});

test("historyTimeline escapes event text (no HTML injection)", () => {
  const events = [{ date: "2026-08-08", source: "x", sourceTag: "x", text: "<script>alert(1)</script>", detail: "a & b", handle: null }];
  const html = historyTimeline(events, {});
  assert.doesNotMatch(html, /<script>alert/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /a &amp; b/);
});

test("historyTimeline renders an unresolvable handle plainly (no crash)", () => {
  const events = [{ date: "2026-08-08", source: "x", sourceTag: "x", text: "t", detail: "", handle: "ghost" }];
  const html = historyTimeline(events, { people: PEOPLE });
  assert.match(html, /timeline-event/);
  assert.doesNotMatch(html, /timeline-who-name/);
});

// --- the real repository (the worked example must not rot) ------------------

test("REAL: calibration-cube PM.md decision log parses clean and non-empty", () => {
  const pm = readFileSync(join(REPO_ROOT, "designs/calibration-cube/PM.md"), "utf8");
  const { entries, problems } = parseDecisionLog(pm);
  assert.deepEqual(problems, [], "the real decision log must match the pinned shape");
  assert.ok(entries.length >= 1, "calibration-cube has committed decisions to show");
  assert.ok(entries.every((e) => /^\d{4}-\d{2}-\d{2}$/.test(e.date)));
});
