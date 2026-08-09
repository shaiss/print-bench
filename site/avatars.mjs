#!/usr/bin/env node
// Regenerate the committed member avatars (site/assets/avatars/<handle>.svg)
// from each member's people/<handle>.md header — the authoritative config
// (`avatar-style:` / `avatar-seed:`, falling back to the kind/name defaults
// in lib/avatars.mjs). DiceBear generates deterministically, so same header
// + same pinned packages = same bytes; test/avatars.test.mjs holds the
// committed SVGs to exactly this resolution.
//
//   node site/avatars.mjs                        regenerate every member
//   node site/avatars.mjs --set <handle> [--style <style>] [--seed <seed>]
//                                                update that member's header
//                                                (omitted seed → a fresh
//                                                random one), then regenerate
//
// The --set mode is what the "Regenerate avatar" Action runs; it edits only
// the two avatar keys, never the rest of the profile.

import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { randomBytes } from "node:crypto";
import { fileURLToPath } from "node:url";

import { createAvatar } from "@dicebear/core";

import { avatarConfig, avatarOptions, styleProblem } from "./lib/avatars.mjs";
import { parseProfile } from "./lib/team.mjs";

const SITE_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(SITE_DIR, "..");
const PEOPLE_DIR = join(REPO_ROOT, "people");
const OUT_DIR = join(SITE_DIR, "assets", "avatars");

function fail(msg) {
  console.error(`error: ${msg}`);
  process.exit(2);
}

function parseArgs(argv) {
  const args = { set: null, style: null, seed: null };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--set") args.set = argv[++i] || fail("--set needs a handle");
    else if (argv[i] === "--style") args.style = argv[++i] || fail("--style needs a value");
    else if (argv[i] === "--seed") args.seed = argv[++i] || fail("--seed needs a value");
    else fail(`unknown argument: ${argv[i]}`);
  }
  if ((args.style || args.seed) && !args.set) fail("--style/--seed only make sense with --set");
  return args;
}

function member(handle) {
  const path = join(PEOPLE_DIR, `${handle}.md`);
  let text;
  try {
    text = readFileSync(path, "utf8");
  } catch {
    fail(`no profile at people/${handle}.md`);
  }
  const { header, problems } = parseProfile(text);
  if (problems.length) fail(`people/${handle}.md: ${problems.join("; ")}`);
  return { path, text, header };
}

/**
 * Replace (or insert, just before the closing fence) the avatar keys inside
 * the profile's `---` header. Only these two lines move; comments and every
 * other key stay byte-identical.
 */
function setAvatarKeys(text, { style, seed }) {
  const lines = text.split("\n");
  const close = lines.indexOf("---", 1);
  if (lines[0].trim() !== "---" || close === -1) fail("profile has no '---' header fence");
  const keep = lines
    .slice(1, close)
    .filter((l) => !/^\s*avatar-(style|seed)\s*:/.test(l));
  const inserted = [];
  if (style) inserted.push(`avatar-style: ${style}`);
  if (seed) inserted.push(`avatar-seed: ${seed}`);
  return ["---", ...keep, ...inserted, "---", ...lines.slice(close + 1)].join("\n");
}

async function render(handle, header) {
  const { style, seed } = avatarConfig({
    kind: header.kind,
    name: header.name,
    avatarStyle: header.avatarStyle,
    avatarSeed: header.avatarSeed,
  });
  const mod = await import(`@dicebear/${style}`);
  const svg = createAvatar(mod, avatarOptions(seed)).toString();
  writeFileSync(join(OUT_DIR, `${handle}.svg`), svg);
  console.log(`avatars: ${handle} ← ${style} / '${seed}' (${svg.length} bytes)`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  if (args.set) {
    const m = member(args.set);
    const style = args.style || m.header.avatarStyle;
    if (style) {
      const problem = styleProblem(style, m.header.kind);
      if (problem) fail(`people/${args.set}.md: ${problem}`);
    }
    // No seed given → a fresh random one: --set exists to re-roll.
    const seed = args.seed || randomBytes(4).toString("hex");
    writeFileSync(m.path, setAvatarKeys(m.text, { style, seed }));
    const updated = member(args.set);
    await render(args.set, updated.header);
    return;
  }

  const files = readdirSync(PEOPLE_DIR).filter((f) => f.endsWith(".md")).sort();
  for (const file of files) {
    const handle = file.slice(0, -3);
    const m = member(handle);
    await render(handle, m.header);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
