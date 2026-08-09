// The team/org layer's revised IA (issue #122, revised):
//
//   * the PRODUCT page carries a "team contributions" section — who built the
//     product (identity, not profile) + its build history — so a visitor on
//     the product page sees the team that made it.
//   * the PEOPLE page is the directory of everyone (core members + shared
//     specialists) as full profiles, with the product teams each has been on.
//
// Why these tests: two halves of the contract a presence-only render gate
// can't see — that the product page shows IDENTITY that links out to the
// profile (not the profile inline), and that the People page lists EVERYONE
// including the shared specialists (the old Shared resources page, folded in).
// The last tests build from the real repo so the seeded cast can't rot.

import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { readDesigns } from "../lib/content.mjs";
import { readTeam } from "../lib/team.mjs";
import { readTimeline } from "../lib/timeline.mjs";
import { buildModel } from "../lib/model.mjs";
import { designPage, peoplePage, redirectPage } from "../lib/templates.mjs";
import {
  contributorCard,
  contributorRow,
  reviewedBy,
  historySlot,
} from "../lib/teams.mjs";

const GH = "https://github.example/blob/main";
const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));

const SHAI = { handle: "shai", name: "Shai Perednik", kind: "human", initials: "SP", role: "Maker" };
const VERA = { handle: "vera", name: "Vera", kind: "agent", initials: "V", role: "PM agent" };
const JANE = { handle: "jane", name: "Jane", kind: "agent", initials: "J", role: "Reviewer" };

// --- contributor identity cards (product page) -----------------------------

test("contributorCard renders identity linking to the People profile, not the profile itself", () => {
  const html = contributorCard(VERA);
  assert.match(html, /href="\/people\/#profile-vera"/);
  assert.match(html, /monogram-agent/);
  assert.match(html, /Vera/);
  assert.match(html, /PM agent/);
  // Identity only — no mandate/charter prose (that's the full profile).
  assert.doesNotMatch(html, /Mandate/);
});

test("contributorRow emits one card per core member, in order", () => {
  const html = contributorRow([SHAI, VERA]);
  assert.match(html, /profile-shai/);
  assert.match(html, /profile-vera/);
  assert.ok(html.indexOf("profile-shai") < html.indexOf("profile-vera"));
});

// --- reviewed-by (now points at People) ------------------------------------

test("reviewedBy links specialists and the directory to /people/", () => {
  const html = reviewedBy([JANE]);
  assert.match(html, /href="\/people\/#profile-jane"/);
  assert.match(html, /href="\/people\/"/);
  assert.doesNotMatch(html, /\/shared\//);
});

test("reviewedBy with no specialists renders nothing", () => {
  assert.equal(reviewedBy([]), "");
});

test("historySlot renders the timeline with events and an empty state without", () => {
  const withEvents = historySlot("x", {
    events: [{ date: "2026-08-08", source: "s", sourceTag: "s", text: "t", detail: "", handle: null }],
    people: new Map(),
  });
  assert.match(withEvents, /<ol class="timeline">/);
  const without = historySlot("x", { events: [], people: new Map() });
  assert.match(without, /class="history-empty/);
});

// --- the product page carries the contributions section (real repo) --------

test("REAL: the calibration-cube product page shows its team + build history", () => {
  const designs = readDesigns(REPO_ROOT);
  const designNames = new Set(designs.map((d) => d.name));
  const team = readTeam(REPO_ROOT, {
    onError: (m) => assert.fail(`real repo roster did not resolve: ${m}`),
    designNames,
  });
  const cube = designs.find((d) => d.name === "calibration-cube");
  assert.ok(cube, "calibration-cube is published");
  const roster = team.rosters.get("calibration-cube");
  assert.ok(roster, "calibration-cube has a committed roster");

  const pmText = readFileSync(join(REPO_ROOT, "designs/calibration-cube/PM.md"), "utf8");
  const { events, problems } = readTimeline({ pmText, notesText: null, roster });
  assert.deepEqual(problems, [], "real decision log parses clean");

  const html = designPage(cube, {
    html: "<h1>calibration-cube</h1>",
    toc: "",
    githubBase: GH,
    model: buildModel(REPO_ROOT, cube),
    roster,
    specialists: team.specialists,
    events,
    people: team.people,
  });

  // The revised product-page IA (site wireframes, 1d + preview feedback):
  // the roster renders as the header's Built-by block — below the
  // description, above the action row — and the build history as the
  // History tab-panel.
  assert.match(html, /id="tab-history"/);
  assert.doesNotMatch(html, /id="tab-team"/);
  assert.match(html, /class="contributions-team"/);
  assert.match(html, /Built by/);
  assert.match(
    html,
    /contributions-team[\s\S]*btn-row/,
    "the team block precedes the action row in the header"
  );
  assert.match(html, /href="\/people\/#profile-vera"/, "core PM linked to their profile");
  assert.match(html, /Reviewed by/);
  assert.match(html, /<ol class="timeline">/);
  assert.match(html, /size-marker/, "a real PM.md decision-log entry renders");
});

test("REAL: a rosterless design's product page carries no contributions section", () => {
  const designs = readDesigns(REPO_ROOT);
  const designNames = new Set(designs.map((d) => d.name));
  const team = readTeam(REPO_ROOT, { onError: () => {}, designNames });
  const rosterless = designs.find((d) => !team.rosters.has(d.name));
  assert.ok(rosterless, "there is a design without a roster to test the absence");

  const html = designPage(rosterless, {
    html: "<h1>x</h1>",
    toc: "",
    githubBase: GH,
    model: buildModel(REPO_ROOT, rosterless),
    roster: null,
  });
  assert.doesNotMatch(html, /class="contributions-team"/);
  assert.doesNotMatch(html, /Built by/);
  // No roster → no header team block and no History tab; Overview and
  // Workbench remain.
  assert.doesNotMatch(html, /id="tab-history"/);
  assert.match(html, /id="tab-overview"/);
  assert.match(html, /id="tab-workbench"/);
});

// --- the People page lists everyone, incl. shared specialists (real repo) --

test("REAL: the People page lists everyone with profiles, shared specialists folded in", () => {
  const designs = readDesigns(REPO_ROOT);
  const designNames = new Set(designs.map((d) => d.name));
  const team = readTeam(REPO_ROOT, {
    onError: (m) => assert.fail(`real repo roster did not resolve: ${m}`),
    designNames,
  });
  const html = peoplePage(team, { githubBase: GH });

  assert.match(html, /<h1>People<\/h1>/);
  // Everyone in the seeded cast — core members and the shared specialists.
  for (const handle of ["shai", "vera", "jane", "drik", "coach"]) {
    assert.match(html, new RegExp(`profile-${handle}`), `${handle} has a profile on the People page`);
  }
  // The shared specialists are folded in, still marked as shared.
  assert.match(html, /shared across print-bench/);
  // Full profiles, not just identity — the mandate section is present.
  assert.match(html, /Mandate/);
  // High-level product involvement: profiles carry team chips to product pages.
  assert.match(html, /href="\/designs\/calibration-cube\/"/);
});

test("redirectPage forwards a retired route to /people/ (both /shared/ and /teams/)", () => {
  const html = redirectPage("/people/", "People");
  assert.match(html, /http-equiv="refresh" content="0; url=\/people\/"/);
  assert.match(html, /<link rel="canonical" href="\/people\/">/);
  assert.match(html, /has moved to <a href="\/people\/">People<\/a>/);
});

test("REAL: nav says People and no longer Teams or Shared resources", () => {
  const designs = readDesigns(REPO_ROOT);
  const team = readTeam(REPO_ROOT, { onError: () => {}, designNames: new Set(designs.map((d) => d.name)) });
  const html = peoplePage(team, { githubBase: GH });
  assert.match(html, /href="\/people\/"[^>]*>People</);
  // The old routes are gone from the nav (route-based, since "Teams" also
  // appears as a profile's team-chips heading).
  assert.doesNotMatch(html, /href="\/teams\/"/);
  assert.doesNotMatch(html, /href="\/shared\/"/);
  assert.doesNotMatch(html, />Shared resources</);
});
