// The avatar layer (site-wireframes avatar studio): the curated style sets,
// the header→config resolution, and — the load-bearing one — the drift gate:
// every committed site/assets/avatars/<handle>.svg must be exactly what the
// member's people/<handle>.md header derives. DiceBear generates
// deterministically from pinned packages, so regenerate-and-compare is a
// byte-equality check; a header change with a stale SVG fails here with the
// one command that fixes it.

import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { createAvatar } from "@dicebear/core";

import {
  AVATAR_STYLES,
  avatarConfig,
  avatarOptions,
  styleExport,
  styleProblem,
  defaultStyle,
} from "../lib/avatars.mjs";
import { parseProfile } from "../lib/team.mjs";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

test("avatarConfig falls back to the wireframe defaults by kind and first name", () => {
  assert.deepEqual(
    avatarConfig({ kind: "human", name: "Shai Perednik", avatarStyle: null, avatarSeed: null }),
    { style: "notionists", seed: "Shai" }
  );
  assert.deepEqual(
    avatarConfig({ kind: "agent", name: "Vera", avatarStyle: null, avatarSeed: null }),
    { style: "bottts", seed: "Vera" }
  );
});

test("avatarConfig honours a declared style and seed over the defaults", () => {
  assert.deepEqual(
    avatarConfig({ kind: "human", name: "Shai P", avatarStyle: "adventurer", avatarSeed: "x1" }),
    { style: "adventurer", seed: "x1" }
  );
});

test("styleProblem accepts curated styles for the right kind", () => {
  for (const kind of ["human", "agent"]) {
    for (const style of AVATAR_STYLES[kind]) {
      assert.equal(styleProblem(style, kind), null, `${style} is curated for ${kind}`);
    }
  }
});

test("NEGATIVE: styleProblem refuses an off-list style and a cross-kind style", () => {
  assert.match(styleProblem("pixel-art", "human"), /not in the curated human set/);
  assert.match(styleProblem("bottts", "human"), /not in the curated human set/);
  assert.match(styleProblem("notionists", "agent"), /not in the curated agent set/);
});

test("styleExport maps kebab-case names to collection export names", () => {
  assert.equal(styleExport("open-peeps"), "openPeeps");
  assert.equal(styleExport("bottts-neutral"), "botttsNeutral");
  assert.equal(styleExport("notionists"), "notionists");
});

test("parseProfile reads avatar-style and avatar-seed, validated by kind", () => {
  const { header, problems } = parseProfile(
    "---\nname: A B\nkind: human\nrole: r\ninitials: A\navatar-style: adventurer\navatar-seed: 7f3a\n---\n\nbio\n"
  );
  assert.deepEqual(problems, []);
  assert.equal(header.avatarStyle, "adventurer");
  assert.equal(header.avatarSeed, "7f3a");
});

test("NEGATIVE: parseProfile rejects an avatar style outside the member kind's set", () => {
  const { problems } = parseProfile(
    "---\nname: A B\nkind: human\nrole: r\ninitials: A\navatar-style: bottts\n---\n\nbio\n"
  );
  assert.equal(problems.length, 1);
  assert.match(problems[0], /not in the curated human set/);
});

// --- the drift gate (real repo) --------------------------------------------

test("REAL: every committed avatar SVG matches its member's declared config", async () => {
  const peopleDir = join(REPO_ROOT, "people");
  const files = readdirSync(peopleDir).filter((f) => f.endsWith(".md")).sort();
  assert.ok(files.length > 0, "the people registry is populated");

  for (const file of files) {
    const handle = file.slice(0, -3);
    const { header, problems } = parseProfile(readFileSync(join(peopleDir, file), "utf8"));
    assert.deepEqual(problems, [], `people/${file} parses clean`);

    const committed = join(REPO_ROOT, "site", "assets", "avatars", `${handle}.svg`);
    if (!existsSync(committed)) continue; // avatars are opt-in per member

    const { style, seed } = avatarConfig({
      kind: header.kind,
      name: header.name,
      avatarStyle: header.avatarStyle,
      avatarSeed: header.avatarSeed,
    });
    const mod = await import(`@dicebear/${style}`);
    const fresh = createAvatar(mod, avatarOptions(seed)).toString();
    assert.equal(
      readFileSync(committed, "utf8"),
      fresh,
      `site/assets/avatars/${handle}.svg is stale for its header — run: npm --prefix site run avatars`
    );
  }
});

test("REAL: default styles keep the human/agent distinction", () => {
  assert.notEqual(defaultStyle("human"), defaultStyle("agent"));
});
