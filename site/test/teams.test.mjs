// The Teams page: switcher + product-scoped team page (issue #125).
//
// Why this exists: the team page's contract is behavioural, and two halves of
// it are exactly the kind a presence-only render gate cannot see — that the
// core roster is a LEVEL FIELD (one equal card per core member, the PM never
// elevated above a human, reviewers never in it) and that each profile is
// PRODUCT-SCOPED (recent work reads "on <team>", the #124 component consumed
// unchanged). These tests pin both on hand-built records, and the last test
// builds the page from the real repo so the seeded calibration-cube team
// can't silently rot while fixtures stay green.

import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import { readDesigns } from "../lib/content.mjs";
import { readTeam } from "../lib/team.mjs";
import { teamsPage } from "../lib/templates.mjs";
import {
  memberFaces,
  switcherCard,
  switcherStrip,
  coreRoster,
  reviewedBy,
  historySlot,
} from "../lib/teams.mjs";

const GH = "https://github.example/blob/main";
const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));

const SHAI = {
  handle: "shai",
  kind: "human",
  name: "Shai Perednik",
  role: "Founder / human lead",
  initials: "SP",
  shared: false,
  bio: "Runs the bench.",
  mandate: { source: "people/shai.md", summary: null, text: "Runs the bench." },
  work: [
    { date: "2026-08-08", team: null, text: "Merged the roster reader", artifact: "site/lib/team.mjs" },
  ],
};

const VERA = {
  handle: "vera",
  kind: "agent",
  name: "Vera",
  role: "Product manager, calibration-cube",
  initials: "V",
  shared: false,
  bio: null,
  mandate: { source: "designs/calibration-cube/PM.md", summary: "The charter.", text: "Owns the product charter." },
  work: [
    { date: "2026-08-08", team: "calibration-cube", text: "Charter decision: the engraved marker gets its own shot", artifact: "designs/calibration-cube/PM.md" },
    { date: "2026-08-01", team: "other-thing", text: "Work on another product entirely", artifact: "designs/other-thing/PM.md" },
  ],
};

function specialist(handle, name, initials) {
  return {
    handle,
    kind: "agent",
    name,
    initials,
    shared: true,
    mandate: { source: `.claude/skills/${handle}-review/SKILL.md`, summary: "Reviews.", text: "Re-derives every number." },
    role: "Reviewer",
    work: [],
  };
}
const JANE = specialist("jane", "Jane", "J");
const DRIK = specialist("drik", "Drik", "D");
const COACH = specialist("coach", "Coach", "C");

const CUBE = {
  design: "calibration-cube",
  path: "designs/calibration-cube/team.conf",
  core: [SHAI, VERA],
  pm: VERA,
};
const ROSTERS = new Map([["calibration-cube", CUBE]]);

test("member faces are the core's kind-coded initials monograms", () => {
  const html = memberFaces(CUBE.core);
  assert.match(html, /class="switcher-faces"/);
  assert.match(html, /monogram monogram-human">SP</);
  assert.match(html, /monogram monogram-agent">V</);
});

test("a switcher card shows the product name, its ships pitch, and member faces, marked when current", () => {
  const html = switcherCard(CUBE, { pitch: "A dimensional-accuracy test print.", href: "/teams/", current: true });
  assert.match(html, /class="switcher-card is-current"/);
  assert.match(html, /aria-current="true"/);
  assert.match(html, /<a href="\/teams\/">calibration-cube<\/a>/);
  assert.match(html, /A dimensional-accuracy test print\./);
  assert.match(html, /monogram-human">SP</);
  assert.match(html, /monogram-agent">V</);
});

test("a non-current switcher card carries no current marker", () => {
  const html = switcherCard(CUBE, { pitch: "x", href: "/teams/", current: false });
  assert.doesNotMatch(html, /is-current/);
  assert.doesNotMatch(html, /aria-current/);
});

test("a switcher card escapes its href at the HTML boundary, like every other href in site/lib", () => {
  const html = switcherCard(CUBE, { pitch: "x", href: '/teams/"><script>', current: false });
  assert.doesNotMatch(html, /href="\/teams\/"><script>/, "raw metacharacters must not reach the attribute");
  assert.match(html, /href="\/teams\/&quot;&gt;&lt;script&gt;"/, "href is HTML-escaped, unsafe-by-default avoided");
});

test("the switcher strip renders one card per rostered team, using the passed-in pitch, and highlights the current one", () => {
  const html = switcherStrip(ROSTERS, {
    pitchFor: (n) => `pitch-of-${n}`,
    teamHref: () => "/teams/",
    currentDesign: "calibration-cube",
  });
  assert.match(html, /class="switcher-strip"/);
  assert.match(html, /pitch-of-calibration-cube/);
  assert.match(html, /is-current/);
  assert.equal((html.match(/class="switcher-card/g) || []).length, 1);
});

test("the core roster is one equal peer card per core member, kind-coded, with no PM hierarchy", () => {
  const html = coreRoster(CUBE, { rosters: ROSTERS, githubBase: GH });
  // Exactly one card per core member — no more (a reviewer leaking in), no fewer.
  assert.equal((html.match(/class="card profile-card peer-card/g) || []).length, 2);
  // Both are the full profile component.
  assert.equal((html.match(/class="profile"/g) || []).length, 2);
  // Kind is colour-coded at the card edge...
  assert.match(html, /peer-card peer-human/);
  assert.match(html, /peer-card peer-agent/);
  // ...but nothing elevates the PM (vera) above the human: no rank markup.
  assert.doesNotMatch(html, /peer-(lead|pm|owner|primary|core-lead)/);
});

test("the core roster scopes each profile to the product, so recent work reads on that team and off-team work is filtered out", () => {
  const html = coreRoster(CUBE, { rosters: ROSTERS, githubBase: GH });
  assert.match(html, /Recent work <span class="work-scope">· on <code>calibration-cube<\/code><\/span>/);
  assert.match(html, /engraved marker gets its own shot/, "vera's calibration-cube work shows");
  assert.doesNotMatch(html, /another product entirely/, "her other-team work stays off this team page");
});

test("reviewers never appear as core roster cards", () => {
  const html = coreRoster(CUBE, { rosters: ROSTERS, githubBase: GH });
  for (const h of ["jane", "drik", "coach"]) {
    assert.doesNotMatch(html, new RegExp(`profile-${h}`), `${h} is a reviewer, not core roster`);
  }
});

test("reviewed-by names the shared specialists and links the Shared resources page, not as roster cards", () => {
  const html = reviewedBy([JANE, DRIK, COACH]);
  assert.match(html, /class="reviewed-by"/);
  for (const [h, n] of [["jane", "Jane"], ["drik", "Drik"], ["coach", "Coach"]]) {
    assert.match(html, new RegExp(`href="/shared/#profile-${h}"`));
    assert.match(html, new RegExp(n));
  }
  assert.match(html, /href="\/shared\/"/, "links the Shared resources page");
  assert.doesNotMatch(html, /profile-card/, "reviewers are a light reference, not roster cards");
});

test("reviewed-by with no specialists renders nothing", () => {
  assert.equal(reviewedBy([]), "");
});

test("the history slot is laid out as an honest empty state deferring to the timeline issue", () => {
  const html = historySlot("calibration-cube");
  assert.match(html, /class="team-history"/);
  assert.match(html, /History of work together/);
  assert.match(html, /class="history-empty/);
  assert.match(html, /issue #126/, "the section is laid out; its data is #126");
});

test("the Teams page builds from the real repo: switcher, product-scoped calibration-cube team, reviewed-by, history — and no front-door hero", () => {
  const designs = readDesigns(REPO_ROOT);
  const designNames = new Set(designs.map((d) => d.name));
  const team = readTeam(REPO_ROOT, {
    onError: (m) => assert.fail(`real repo roster did not resolve: ${m}`),
    designNames,
  });
  const html = teamsPage(team, designs, { githubBase: GH });

  // AC3 — a page in the site, not the front door: no landing hero.
  assert.doesNotMatch(html, /<section class="hero">/, "the Teams page must not use the front-door hero");
  assert.match(html, /class="team-switcher"/);

  // AC1 — the page carries the Teams nav item marked current (from layout()).
  assert.match(html, /<a href="\/teams\/" aria-current="page">Teams<\/a>/);

  // AC2 — switcher lists calibration-cube with the gallery-rule pitch, current.
  assert.match(html, /<a href="\/teams\/">calibration-cube<\/a>/);
  assert.match(html, /dimensional-accuracy test print/, "the ships pitch is the gallery rule's one-liner");
  assert.match(html, /class="switcher-card is-current"/);

  // AC4 — team hero: product name, pitch, member count.
  assert.match(html, /class="team-name">calibration-cube</);
  assert.match(html, /2 people/);

  // AC5 — level-field core roster: shai + vera, exactly two peer cards.
  assert.equal((html.match(/class="card profile-card peer-card/g) || []).length, 2);
  assert.match(html, /peer-card peer-human/);
  assert.match(html, /peer-card peer-agent/);
  assert.match(html, /class="profile-name">Shai Perednik /);
  assert.match(html, /class="profile-name">Vera /);

  // AC6 — product-scoped profiles.
  assert.match(html, /· on <code>calibration-cube<\/code>/);

  // AC7 — reviewed-by → the three shared specialists, linking /shared/.
  assert.match(html, /class="reviewed-by"/);
  assert.match(html, /href="\/shared\/#profile-jane"/);
  assert.match(html, /href="\/shared\/#profile-drik"/);
  assert.match(html, /href="\/shared\/#profile-coach"/);

  // AC8 — history slot laid out, data deferred to #126.
  assert.match(html, /History of work together/);
  assert.match(html, /issue #126/);
});
