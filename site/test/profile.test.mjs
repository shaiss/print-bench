// The member profile component (issue #124).
//
// Why this exists: the profile is the one block both the Shared resources
// page and the coming team page (#125) render, and its contract is
// behavioural, not visual — every field of the member record must appear,
// the scope parameter must both FILTER the recent-work list and word its
// heading, and a member with nothing recorded must get an honest empty
// state rather than a hole. These tests pin that contract on hand-built
// records, so #125 can consume the component unchanged and know what it
// gets.

import { test } from "node:test";
import assert from "node:assert/strict";

import { memberProfile, memberTeams } from "../lib/profile.mjs";

const GH = "https://github.example/blob/main";

const SPECIALIST = {
  handle: "rev",
  profilePath: "people/rev.md",
  name: "Rev",
  kind: "agent",
  role: "Printability reviewer",
  initials: "R",
  shared: true,
  bio: null,
  mandate: {
    source: ".claude/skills/rev-review/SKILL.md",
    summary: "Reviews everything twice.",
    text: "You are the reviewer. You re-derive every number before trusting it.",
  },
  work: [
    { date: "2026-08-08", team: "widget", text: "Re-derived the widget margins", artifact: "designs/widget/NOTES.md" },
    { date: "2026-08-02", team: "gadget", text: "Audited the gadget overhangs", artifact: "audits/g/pair.png" },
  ],
};

const HUMAN = {
  handle: "ada",
  profilePath: "people/ada.md",
  name: "Ada",
  kind: "human",
  role: "Founder",
  initials: "A",
  shared: false,
  bio: "Builds the things and signs off on the shapes.",
  mandate: { source: "people/ada.md", summary: null, text: "Builds the things and signs off on the shapes." },
  work: [],
};

test("an agent specialist's profile carries every field the issue names: identity, pills, role, cited mandate, work", () => {
  const html = memberProfile(SPECIALIST, { scope: null, teams: [], githubBase: GH });

  assert.match(html, /Rev/);
  assert.match(html, /<code class="profile-handle">rev<\/code>/, "the handle is set in mono");
  assert.match(html, /monogram-agent[^>]*>R</, "the monogram is the initials, kind-coded");
  assert.match(html, /class="pill pill-agent">agent</, "the kind pill");
  assert.match(html, /class="pill pill-shared">shared across print-bench</, "the shared pill");
  assert.match(html, /Printability reviewer/);

  assert.match(html, /Mandate &amp; instructions/);
  assert.match(html, /Reviews everything twice\./, "the charter's description is the summary");
  assert.match(html, /re-derive every number/, "the charter excerpt is the mandate text");
  // Cited the way a reader names it — the skill directory — while the link
  // still targets the real file.
  assert.match(html, /<code>\.claude\/skills\/rev-review<\/code>/);
  assert.match(html, new RegExp(`href="${GH}/\\.claude/skills/rev-review/SKILL\\.md"`));

  assert.match(html, /Re-derived the widget/);
  assert.match(html, /Audited the gadget/);
});

test("the scope parameter filters the work list to one team and words the heading for that context", () => {
  const scoped = memberProfile(SPECIALIST, { scope: "widget", teams: [], githubBase: GH });
  assert.match(scoped, /Recent work <span class="work-scope">· on <code>widget<\/code><\/span>/);
  assert.match(scoped, /Re-derived the widget/);
  assert.doesNotMatch(scoped, /Audited the gadget/, "other teams' work stays off a team-scoped profile");

  const all = memberProfile(SPECIALIST, { scope: null, teams: [], githubBase: GH });
  assert.match(all, /Recent work <span class="work-scope">· across teams<\/span>/);
  // Cross-team entries say where they happened; a scoped list would only
  // repeat its own heading.
  assert.match(all, /href="\/designs\/gadget\/"/);
  assert.doesNotMatch(scoped, /href="\/designs\/widget\/"[^>]*>widget/);
});

test("a human's profile renders the bio as the mandate, cites their own profile, and carries no shared pill", () => {
  const html = memberProfile(HUMAN, { scope: null, teams: ["widget"], githubBase: GH });

  assert.match(html, /monogram-human[^>]*>A</);
  assert.match(html, /class="pill pill-human">human</);
  assert.doesNotMatch(html, /pill-shared/);
  assert.match(html, /signs off on the shapes/);
  assert.match(html, /<code>people\/ada\.md<\/code>/, "a human's mandate source is their own profile");

  assert.match(html, /class="profile-teams"/);
  assert.match(html, /href="\/designs\/widget\/"/, "team chips link to the team's product page");
});

test("a member with nothing recorded gets an honest empty state, and no teams means no Teams section", () => {
  const html = memberProfile({ ...SPECIALIST, work: [] }, { scope: null, teams: [], githubBase: GH });
  assert.match(html, /Nothing recorded yet\./);
  assert.doesNotMatch(html, /class="profile-teams"/);
});

test("memberTeams reads a member's teams off the rosters, in roster order", () => {
  const rosters = new Map([
    ["widget", { design: "widget", core: [HUMAN, SPECIALIST] }],
    ["gadget", { design: "gadget", core: [SPECIALIST] }],
    ["gizmo", { design: "gizmo", core: [HUMAN] }],
  ]);
  assert.deepEqual(memberTeams(SPECIALIST, rosters), ["widget", "gadget"]);
  assert.deepEqual(memberTeams(HUMAN, rosters), ["widget", "gizmo"]);
  assert.deepEqual(memberTeams({ ...HUMAN, handle: "ghost" }, rosters), []);
});
