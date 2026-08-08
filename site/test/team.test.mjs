// The team registry reader and its resolve-or-fail gate (issue #123).
//
// Why this exists: the roster data (people/<handle>.md, designs/<name>/
// team.conf) is structured — it never passes through the markdown
// reference checker that guards every product-page link — so its own
// resolution rules are the only thing standing between a typo'd handle and
// a team page rendering a hole in production. These tests pin both halves:
// the strict house parsing (a malformed profile refuses loudly, exactly
// like derives.conf), and the gate (an unresolvable handle or mandate
// source is an error, not a skip). The negative controls matter most — a
// gate that stops firing looks identical to one that passes.
//
// The last test runs the reader against the real repository, so the seeded
// cast (issue #123's shai/frieda/vera/jane/drik/coach) cannot silently rot
// or vanish while the fixtures stay green.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { readDesigns } from "../lib/content.mjs";

import {
  PROFILE_KEYS,
  TEAM_KEYS,
  parseProfile,
  parseTeamConf,
  parseWorkConf,
  mandateExcerpt,
  readTeam,
} from "../lib/team.mjs";

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));

/** Build a throwaway repo tree from relPath -> content. */
function fixture(spec) {
  const root = mkdtempSync(join(tmpdir(), "print-bench-team-"));
  for (const [rel, content] of Object.entries(spec)) {
    mkdirSync(join(root, dirname(rel)), { recursive: true });
    writeFileSync(join(root, rel), content);
  }
  return root;
}

/** Run readTeam collecting errors. */
function collect(root, designNames) {
  const errors = [];
  const team = readTeam(root, { onError: (m) => errors.push(m), designNames });
  return { team, errors };
}

const HUMAN = `---
name: Ada
kind: human
role: Founder
initials: A
---

Builds the things and signs off on the shapes.
`;

const AGENT = `---
name: Bot
kind: agent
role: Product manager
initials: B
mandate: charter.md
---
`;

const CHARTER = `# Charter

Owns what we build and why, and says no to the rest.

## 0. First section
Procedure text the excerpt must not include.
`;

test("a profile header parses into a member record, and a human's body becomes the bio", () => {
  const { header, body, problems } = parseProfile(HUMAN);
  assert.deepEqual(problems, []);
  assert.equal(header.name, "Ada");
  assert.equal(header.kind, "human");
  assert.equal(header.role, "Founder");
  assert.equal(header.initials, "A");
  assert.equal(header.shared, false);
  assert.equal(header.mandate, null);
  assert.match(body, /signs off on the shapes/);
});

test("an agent profile points at its charter, and re-typed mandate text is refused", () => {
  assert.deepEqual(parseProfile(AGENT).problems, []);

  const agentWithBody = parseProfile(AGENT + "\nSome re-typed mandate prose.\n");
  assert.equal(agentWithBody.problems.length, 1);
  assert.match(agentWithBody.problems[0], /do not re-type/);

  const agentNoMandate = parseProfile(AGENT.replace(/^mandate:.*\n/m, ""));
  assert.equal(agentNoMandate.problems.length, 1);
  assert.match(agentNoMandate.problems[0], /needs a 'mandate:' path/);

  const humanWithMandate = parseProfile(HUMAN.replace("---\n\nBuilds", "mandate: charter.md\n---\n\nBuilds"));
  assert.equal(humanWithMandate.problems.length, 1);
  assert.match(humanWithMandate.problems[0], /delete the 'mandate:' key/);

  const humanNoBody = parseProfile(HUMAN.slice(0, HUMAN.lastIndexOf("---") + 4));
  assert.equal(humanNoBody.problems.length, 1);
  assert.match(humanNoBody.problems[0], /bio is the mandate text/);
});

test("profile parsing is strict: bad fence, no colon, unknown key, duplicate key, bad kind, bad shared each refuse loudly", () => {
  assert.match(parseProfile("name: Ada\n").problems[0], /does not open with a '---'/);
  assert.match(parseProfile("---\nname: Ada\n").problems[0], /fence never closes/);

  const perLine = (line) =>
    parseProfile(`---\nname: Ada\nkind: human\nrole: F\ninitials: A\n${line}\n---\n\nBio.\n`).problems;
  assert.match(perLine("colonless").join("\n"), /has no ':'/);
  assert.match(perLine("nickname: Lady A").join("\n"), /unknown key 'nickname'/);
  assert.match(perLine("name: Twice").join("\n"), /duplicate key 'name'/);
  assert.match(perLine("shared: yes").join("\n"), /shared must be 'true' or 'false'/);

  const badKind = parseProfile("---\nname: A\nkind: robot\nrole: F\ninitials: A\n---\n\nBio.\n");
  assert.match(badKind.problems.join("\n"), /kind must be 'human' or 'agent'/);

  // Trailing comments are stripped, same as derives.conf — a value can
  // never legally contain '#'.
  const commented = parseProfile("---\nname: Ada # the founder\nkind: human\nrole: F\ninitials: A\n---\n\nBio.\n");
  assert.deepEqual(commented.problems, []);
  assert.equal(commented.header.name, "Ada");

  assert.deepEqual(PROFILE_KEYS, ["name", "kind", "role", "initials", "mandate", "shared"]);
});

test("team.conf parses core and pm with the same strictness as derives.conf", () => {
  const ok = parseTeamConf("# who\ncore: ada, bot # the pair\npm: bot\n");
  assert.deepEqual(ok.problems, []);
  assert.deepEqual(ok.core, ["ada", "bot"]);
  assert.equal(ok.pm, "bot");

  assert.match(parseTeamConf("core ada\npm: ada\n").problems.join("\n"), /has no ':'/);
  assert.match(parseTeamConf("core: ada\npm: ada\nlead: ada\n").problems.join("\n"), /unknown key 'lead'/);
  assert.match(parseTeamConf("core: ada\ncore: bot\npm: ada\n").problems.join("\n"), /duplicate key 'core'/);
  assert.match(parseTeamConf("core: ada, ada\npm: ada\n").problems.join("\n"), /lists 'ada' twice/);
  assert.match(parseTeamConf("core: ada, bot\npm: ada, bot\n").problems.join("\n"), /exactly one handle/);
  assert.match(parseTeamConf("core:\npm: ada\n").problems.join("\n"), /missing required key 'core'/);
  assert.match(parseTeamConf("core: ada\npm: bot\n").problems.join("\n"), /pm 'bot' is not a member of core/);
  assert.match(parseTeamConf("core: ada\n").problems.join("\n"), /missing required key 'pm'/);

  assert.deepEqual(TEAM_KEYS, ["core", "pm"]);
});

test("the mandate excerpt is the charter's description plus its intro paragraph, and plain markdown falls back to its first prose paragraph", () => {
  const skill = `---
name: rev
description: Reviews everything twice.
---

# Reviewer

You are the reviewer. You re-derive
every number before trusting it.

## 0. Procedure
Steps the excerpt must not include.
`;
  const s = mandateExcerpt(skill);
  assert.equal(s.summary, "Reviews everything twice.");
  assert.equal(s.text, "You are the reviewer. You re-derive every number before trusting it.");

  const pmdoc = `# widget — product charter

## The product, in one paragraph

A widget that does one thing well.

## Non-negotiables
`;
  const p = mandateExcerpt(pmdoc);
  assert.equal(p.summary, null);
  assert.equal(p.text, "A widget that does one thing well.");
});

test("readTeam resolves every core handle to a member record and marks the pm", () => {
  const root = fixture({
    "people/ada.md": HUMAN,
    "people/bot.md": AGENT.replace("mandate: charter.md", "mandate: docs/charter.md"),
    "people/rev.md": AGENT.replace("name: Bot", "name: Rev")
      .replace("initials: B", "initials: R\nshared: true")
      .replace("mandate: charter.md", "mandate: docs/charter.md"),
    "docs/charter.md": CHARTER,
    "designs/widget/team.conf": "core: ada, bot\npm: bot\n",
  });
  try {
    const { team, errors } = collect(root, new Set(["widget"]));
    assert.deepEqual(errors, []);
    const roster = team.rosters.get("widget");
    assert.deepEqual(roster.core.map((m) => m.handle), ["ada", "bot"]);
    assert.equal(roster.pm.handle, "bot");
    assert.equal(team.people.get("ada").mandate.text, team.people.get("ada").bio);
    assert.match(team.people.get("bot").mandate.text, /says no to the rest/);
    assert.equal(team.people.get("bot").mandate.source, "docs/charter.md");
    assert.deepEqual(team.specialists.map((m) => m.handle), ["rev"]);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("an unresolvable roster handle fails the build, not the render", () => {
  const root = fixture({
    "people/ada.md": HUMAN,
    "designs/widget/team.conf": "core: ada, ghost\npm: ada\n",
  });
  try {
    const { team, errors } = collect(root, new Set(["widget"]));
    assert.equal(errors.length, 1);
    assert.match(errors[0], /designs\/widget\/team\.conf/);
    assert.match(errors[0], /'ghost', which people\/ does not register/);
    assert.equal(team.rosters.size, 0);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("a missing mandate source is an error naming the profile that points at it", () => {
  const root = fixture({
    "people/bot.md": AGENT.replace("mandate: charter.md", "mandate: docs/gone.md"),
    "people/esc.md": AGENT.replace("name: Bot", "name: Esc")
      .replace("mandate: charter.md", "mandate: ../outside.md"),
    // Backslash traversal: on Windows this resolves outside the repo (the
    // containment check rejects it); on POSIX it is a literal filename
    // that does not exist. Rejected either way — the build must fail.
    "people/esc2.md": AGENT.replace("name: Bot", "name: Esc Two")
      .replace("mandate: charter.md", "mandate: ..\\outside.md"),
  });
  try {
    const { errors } = collect(root);
    assert.equal(errors.length, 3);
    assert.match(errors.find((e) => e.includes("bot.md")), /'docs\/gone\.md', which does not exist/);
    assert.match(errors.find((e) => e.includes("esc.md")), /no '\.\.'/);
    assert.match(errors.find((e) => e.includes("esc2.md")), /no '\.\.'|does not exist/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("a shared specialist inside a core is refused", () => {
  const root = fixture({
    "people/ada.md": HUMAN,
    "people/rev.md": AGENT.replace("name: Bot", "name: Rev")
      .replace("initials: B", "initials: R\nshared: true"),
    "charter.md": CHARTER,
    "designs/widget/team.conf": "core: ada, rev\npm: ada\n",
  });
  try {
    const { errors } = collect(root, new Set(["widget"]));
    assert.equal(errors.length, 1);
    assert.match(errors[0], /'rev' is a shared specialist/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("a design without a team.conf is not an error, and a team.conf for an unpublished directory is", () => {
  const root = fixture({
    "people/ada.md": HUMAN,
    "designs/bare/bare.scad": "cube(1);\n",
    "designs/retired/team.conf": "core: ada\npm: ada\n",
  });
  try {
    const { team, errors } = collect(root, new Set(["bare"]));
    assert.equal(errors.length, 1);
    assert.match(errors[0], /designs\/retired\/team\.conf/);
    assert.match(errors[0], /does not publish as a design/);
    assert.equal(team.rosters.size, 0);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("a missing people directory is quiet until a roster needs it", () => {
  const empty = fixture({ "designs/widget/widget.scad": "cube(1);\n" });
  try {
    const { team, errors } = collect(empty, new Set(["widget"]));
    assert.deepEqual(errors, []);
    assert.equal(team.members.length, 0);
    assert.equal(team.rosters.size, 0);
  } finally {
    rmSync(empty, { recursive: true, force: true });
  }

  const orphan = fixture({ "designs/widget/team.conf": "core: ada\npm: ada\n" });
  try {
    const { errors } = collect(orphan, new Set(["widget"]));
    assert.equal(errors.length, 1);
    assert.match(errors[0], /'ada', which people\/ does not register/);
  } finally {
    rmSync(orphan, { recursive: true, force: true });
  }
});

test("work.conf parses its pipe manifest with the house strictness", () => {
  const ok = parseWorkConf(
    "# what was done\nada | 2026-08-08 | widget | Shipped the widget | designs/widget/NOTES.md # good day\n" +
      "ada | 2026-08-07 | - | Repo-wide chore | scripts/check.sh\n"
  );
  assert.deepEqual(ok.problems, []);
  assert.equal(ok.entries.length, 2);
  assert.equal(ok.entries[0].team, "widget");
  assert.equal(ok.entries[0].artifact, "designs/widget/NOTES.md");
  assert.equal(ok.entries[1].team, null, "'-' means repo-wide, outside any one team");

  const bad = (line) => parseWorkConf(line).problems.join("\n");
  assert.match(bad("ada | 2026-08-08 | widget | Missing artifact\n"), /expected 5 '\|'-separated fields/);
  assert.match(bad("Ada | 2026-08-08 | widget | Text | a.md\n"), /handle 'Ada' must match/);
  assert.match(bad("ada | last tuesday | widget | Text | a.md\n"), /must be YYYY-MM-DD/);
  assert.match(bad("ada | 2026-08-08 | widget |  | a.md\n"), /text and artifact must both be non-empty/);
});

test("a work entry resolves or fails the build: unknown handle, unpublished team, and a missing or escaping artifact are each errors", () => {
  const base = {
    "people/ada.md": HUMAN,
    "designs/widget/widget.scad": "cube(1);\n",
    "designs/widget/NOTES.md": "notes\n",
  };
  const good = fixture({
    ...base,
    "people/work.conf":
      "ada | 2026-08-08 | widget | Shipped the widget | designs/widget/NOTES.md\n" +
      "ada | 2026-08-09 | - | Repo-wide chore | people/ada.md\n",
  });
  try {
    const { team, errors } = collect(good, new Set(["widget"]));
    assert.deepEqual(errors, []);
    const work = team.people.get("ada").work;
    assert.deepEqual(work.map((w) => w.date), ["2026-08-09", "2026-08-08"], "entries come newest first");
    assert.equal(work[1].team, "widget");
  } finally {
    rmSync(good, { recursive: true, force: true });
  }

  const cases = [
    ["ghost | 2026-08-08 | widget | Who did this | designs/widget/NOTES.md", /'ghost', which people\/ does not register/],
    ["ada | 2026-08-08 | retired | On a page that never renders | designs/widget/NOTES.md", /team 'retired' is not a design the site publishes/],
    ["ada | 2026-08-08 | widget | Cites nothing real | designs/widget/gone.md", /'designs\/widget\/gone\.md', which does not exist/],
    ["ada | 2026-08-08 | widget | Escapes the repo | ../outside.md", /must be repo-relative with no '\.\.'/],
  ];
  for (const [line, want] of cases) {
    const root = fixture({ ...base, "people/work.conf": line + "\n" });
    try {
      const { team, errors } = collect(root, new Set(["widget"]));
      assert.equal(errors.length, 1, `one error for: ${line}`);
      assert.match(errors[0], /people\/work\.conf: line 1/);
      assert.match(errors[0], want);
      assert.deepEqual(team.people.get("ada").work, [], "a rejected entry never reaches the member");
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  }
});

test("the real repo agrees with the team resolver", () => {
  // The same discovery build.mjs uses — not a re-derived predicate, so the
  // test cannot disagree with production about which directories are
  // published designs.
  const designNames = new Set(readDesigns(REPO_ROOT).map((d) => d.name));
  const { team, errors } = collect(REPO_ROOT, designNames);
  assert.deepEqual(errors, []);

  // The issue-#123 seeded cast. Assert facts, not prose — mandate wording
  // belongs to the charters, and coupling tests to it would make every
  // charter edit a test failure.
  const shai = team.people.get("shai");
  assert.equal(shai.kind, "human");
  assert.ok(shai.bio.length > 40, "shai's bio is the mandate text and must not be empty");

  const frieda = team.people.get("frieda");
  assert.equal(frieda.kind, "human");

  const vera = team.people.get("vera");
  assert.equal(vera.kind, "agent");
  assert.equal(vera.mandate.source, "designs/calibration-cube/PM.md");
  assert.ok(vera.mandate.text.length > 40, "vera's mandate excerpt must be non-trivial");

  for (const handle of ["jane", "drik", "coach"]) {
    const m = team.people.get(handle);
    assert.equal(m.kind, "agent", `${handle} is an agent`);
    assert.equal(m.shared, true, `${handle} is a shared specialist`);
    assert.ok(m.mandate.text.length > 40, `${handle}'s mandate excerpt must be non-trivial`);
  }
  assert.deepEqual(team.specialists.map((m) => m.handle).sort(), ["coach", "drik", "jane"]);

  const cube = team.rosters.get("calibration-cube");
  assert.deepEqual(cube.core.map((m) => m.handle), ["shai", "vera"]);
  assert.equal(cube.pm.handle, "vera");

  for (const roster of team.rosters.values()) {
    for (const m of roster.core) assert.equal(m.shared, false, "no shared member sits in a core");
  }

  // The interim recent-work manifest (issue #124) resolves in full — every
  // handle registered, every cited artifact present. Assert shape, not
  // wording: the entries are authored data that will grow and eventually be
  // superseded by the team timeline (#126).
  for (const m of team.members) assert.ok(Array.isArray(m.work), `${m.handle} carries a work list`);
  const recorded = team.members.reduce((n, m) => n + m.work.length, 0);
  assert.ok(recorded >= 1, "the committed people/work.conf seeds at least one entry");
});
