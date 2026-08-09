// The team registry: who builds here, and on which design (issue #123).
//
// Two committed sources, both authored — never derived from git or model
// output, because the team pages must invent no content:
//
//   people/<handle>.md          one profile per member, human or agent. A
//                               `---`-fenced header in the house conf style
//                               (NOT YAML: `#` comments including trailing
//                               ones, blank lines ignored, `key: value`,
//                               unknown/duplicate/colonless keys refused
//                               loudly — the same rules parseDerivesConf
//                               applies), then a markdown body.
//   designs/<name>/team.conf    the design's core roster: `core:` lists
//                               member handles, `pm:` says which of them
//                               owns the product charter.
//   people/work.conf            the interim recent-work manifest (issue
//                               #124): one pipe-separated line per recorded
//                               piece of work, each citing a committed
//                               artifact. Interim on purpose — the team
//                               timeline (issue #126) becomes the history
//                               source, and this file retires with it.
//
// The one rule that shapes everything else: **mandate text is never
// re-typed.** An agent's profile carries a `mandate:` path to its charter
// (a skill's SKILL.md, or a PM agent's design PM.md) and the build reads
// that file — the same discipline as model.mjs reading the .scad instead
// of a hand-maintained copy. A human's mandate IS their profile body (the
// bio), so a human profile with a `mandate:` key, or an agent profile with
// body text, is refused rather than tolerated.
//
// mandateExcerpt() is a convention, not a schema: it takes the frontmatter
// `description:` (when the charter has one) plus the first prose paragraph
// after the headings. Every charter in the tree today yields its intro
// mandate paragraph under that rule; only *emptiness* is gated, wrongness
// is not, so a restructured charter can silently excerpt the wrong prose —
// the trade-off accepted over forcing marker headings into every charter.
//
// Deliberately not errors: a design without a team.conf (rosterless is a
// state, not a defect); a pm that resolves to a human (the data model does
// not forbid it, today's data just doesn't do it); display-name or
// initials collisions (plausible for humans — the handle, which is the
// filename and cannot collide, is the identity). A team.conf on an
// ARCHIVED design resolves like any other: whether archived teams render
// is the page layer's call.
//
// Like every structured source here, problems are collected, not thrown —
// one bad line must not hide the rest. The caller (build.mjs) feeds them
// into the same accumulator as broken markdown references, so an
// unresolvable handle or mandate path fails ./scripts/site.sh before a
// single page is written.

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { isAbsolute, join, relative, resolve } from "node:path";

/** The only keys a profile header may carry. */
export const PROFILE_KEYS = ["name", "kind", "role", "initials", "mandate", "shared", "github"];

/** A GitHub login: alphanumerics and single hyphens, 1–39 chars. */
const GITHUB_LOGIN_RE = /^[a-z\d](?:[a-z\d]|-(?=[a-z\d])){0,38}$/i;

/** The only keys a team.conf may carry. */
export const TEAM_KEYS = ["core", "pm"];

const HANDLE_RE = /^[a-z0-9][a-z0-9-]*$/;

/**
 * Resolve a repo-relative source path, or null when it escapes the repo.
 * Containment is checked on the RESOLVED path, not by scanning for '..'
 * segments — a '..\' would slip past a '/'-split on Windows, where
 * backslash is also a separator.
 */
function containedPath(repoRoot, source) {
  const abs = resolve(repoRoot, source);
  const rel = relative(repoRoot, abs);
  if (isAbsolute(source) || rel.startsWith("..") || isAbsolute(rel)) return null;
  return abs;
}

/**
 * House `key: value` line rules over a run of lines, against a key
 * whitelist. Returns Map(key -> {value, lineno}) plus problems; `lineno`
 * is absolute in the source file (`base` is the 0-indexed offset of
 * lines[0]).
 */
function parseKeyValueLines(lines, keys, base) {
  const seen = new Map();
  const problems = [];
  for (let i = 0; i < lines.length; i++) {
    const lineno = base + i + 1;
    const line = lines[i].split("#", 1)[0].trim();
    if (!line) continue;
    if (!line.includes(":")) {
      problems.push(`line ${lineno}: '${line}' has no ':'`);
      continue;
    }
    const at = line.indexOf(":");
    const key = line.slice(0, at).trim();
    const value = line.slice(at + 1).trim();
    if (!keys.includes(key)) {
      problems.push(`line ${lineno}: unknown key '${key}'`);
      continue;
    }
    if (seen.has(key)) {
      problems.push(`line ${lineno}: duplicate key '${key}' (already on line ${seen.get(key).lineno})`);
      continue;
    }
    seen.set(key, { value, lineno });
  }
  return { seen, problems };
}

/**
 * Parse one people/<handle>.md: `---`-fenced header, markdown body.
 * Collects problems instead of throwing; the header/body it does return is
 * only trustworthy when problems is empty.
 */
export function parseProfile(text) {
  const problems = [];
  const lines = text.split("\n");
  const header = { name: null, kind: null, role: null, initials: null, mandate: null, shared: false, github: null };

  if (lines[0]?.trim() !== "---") {
    problems.push("does not open with a '---' header fence");
    return { header, body: "", problems };
  }
  let close = -1;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === "---") { close = i; break; }
  }
  if (close === -1) {
    problems.push("header fence never closes (no second '---')");
    return { header, body: "", problems };
  }

  const { seen, problems: lineProblems } = parseKeyValueLines(lines.slice(1, close), PROFILE_KEYS, 1);
  problems.push(...lineProblems);
  const body = lines.slice(close + 1).join("\n").trim();

  for (const key of ["name", "kind", "role", "initials"]) {
    const got = seen.get(key);
    if (!got || !got.value) problems.push(`missing required key '${key}'`);
    else header[key] = got.value;
  }
  if (header.kind !== null && header.kind !== "human" && header.kind !== "agent") {
    problems.push(`kind must be 'human' or 'agent', not '${header.kind}'`);
    header.kind = null;
  }
  if (header.initials !== null && header.initials.length > 3) {
    problems.push(`initials must be 1-3 characters, not '${header.initials}'`);
  }
  const shared = seen.get("shared");
  if (shared) {
    if (shared.value === "true") header.shared = true;
    else if (shared.value !== "false") problems.push(`shared must be 'true' or 'false', not '${shared.value}'`);
  }
  const mandate = seen.get("mandate");
  if (mandate) header.mandate = mandate.value;
  // Optional: a member's GitHub login, the committed key that lets the team
  // timeline attribute a git commit to them (site/lib/history.mjs). Validated
  // so a typo'd login is a loud problem, not a silently-never-matching value.
  const github = seen.get("github");
  if (github) {
    // GitHub logins are case-insensitive but case-preserving, so store the
    // canonical lowercase form — attribution compares against the API's
    // author.login, which can arrive in any casing.
    if (GITHUB_LOGIN_RE.test(github.value)) header.github = github.value.toLowerCase();
    else problems.push(`github '${github.value}' is not a valid GitHub login`);
  }

  if (header.kind === "human") {
    if (mandate) problems.push("a human's mandate is the profile body — delete the 'mandate:' key");
    if (!body) problems.push("a human profile needs a body: the bio is the mandate text");
  } else if (header.kind === "agent") {
    if (!mandate || !mandate.value) {
      problems.push("an agent profile needs a 'mandate:' path to its charter");
    }
    if (body) {
      problems.push(
        `an agent's mandate lives at '${header.mandate ?? "<mandate path>"}' — do not re-type it in the body`,
      );
    }
  }

  return { header, body, problems };
}

/**
 * Parse people/work.conf, the interim recent-work manifest:
 *
 *   <handle> | <YYYY-MM-DD> | <team or -> | <text> | <artifact path>
 *
 * `team` scopes the entry to one design's roster ('-' = repo-wide work,
 * outside any one team); `artifact` is the committed file the entry cites —
 * an entry that cannot cite one does not belong in the manifest, because
 * the site invents no content. Resolution (handle registered, team
 * published, artifact present) is readTeam's job, like everything else
 * cross-file. Same collect-don't-throw contract as the parsers above.
 */
export function parseWorkConf(text) {
  const problems = [];
  const entries = [];
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].split("#", 1)[0].trim();
    if (!line) continue;
    const fields = line.split("|").map((f) => f.trim());
    if (fields.length !== 5) {
      problems.push(`line ${i + 1}: expected 5 '|'-separated fields (handle | date | team | text | artifact), got ${fields.length}`);
      continue;
    }
    const [handle, date, team, entryText, artifact] = fields;
    if (!HANDLE_RE.test(handle)) {
      problems.push(`line ${i + 1}: handle '${handle}' must match ${HANDLE_RE}`);
      continue;
    }
    // The regex alone would accept 2026-02-30; the UTC round-trip rejects
    // any date the calendar doesn't have.
    const parsed = /^\d{4}-\d{2}-\d{2}$/.test(date) ? new Date(`${date}T00:00:00Z`) : null;
    if (!parsed || Number.isNaN(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== date) {
      problems.push(`line ${i + 1}: date '${date}' must be a real YYYY-MM-DD date`);
      continue;
    }
    if (!entryText || !artifact) {
      problems.push(`line ${i + 1}: text and artifact must both be non-empty`);
      continue;
    }
    entries.push({ handle, date, team: team === "-" ? null : team, text: entryText, artifact, lineno: i + 1 });
  }
  return { entries, problems };
}

/** Parse one designs/<name>/team.conf. Same collect-don't-throw contract. */
export function parseTeamConf(text) {
  const problems = [];
  const { seen, problems: lineProblems } = parseKeyValueLines(text.split("\n"), TEAM_KEYS, 0);
  problems.push(...lineProblems);

  let core = [];
  const coreGot = seen.get("core");
  if (!coreGot || !coreGot.value) {
    problems.push("missing required key 'core' (the roster's member handles)");
  } else {
    core = coreGot.value.split(",").map((v) => v.trim()).filter(Boolean);
    if (core.length === 0) problems.push("'core' names no handles");
    const dup = core.find((h, i) => core.indexOf(h) !== i);
    if (dup) problems.push(`'core' lists '${dup}' twice`);
  }

  let pm = null;
  const pmGot = seen.get("pm");
  if (!pmGot || !pmGot.value) {
    problems.push("missing required key 'pm' (which core member owns the charter)");
  } else {
    const pms = pmGot.value.split(",").map((v) => v.trim()).filter(Boolean);
    if (pms.length !== 1) problems.push(`'pm' must name exactly one handle, not ${pms.length}`);
    else {
      pm = pms[0];
      if (core.length > 0 && !core.includes(pm)) {
        problems.push(`pm '${pm}' is not a member of core`);
      }
    }
  }

  return { core, pm, problems };
}

/**
 * The readable slice of a mandate source: the frontmatter `description:`
 * when the file opens with a `---` fence (a skill's SKILL.md does), plus
 * the first prose paragraph after any headings. See the header comment for
 * what this convention does and does not guarantee.
 */
export function mandateExcerpt(text) {
  let lines = text.split("\n");
  let summary = null;

  if (lines[0]?.trim() === "---") {
    let close = -1;
    for (let i = 1; i < lines.length; i++) {
      if (lines[i].trim() === "---") { close = i; break; }
    }
    if (close !== -1) {
      for (const line of lines.slice(1, close)) {
        const m = line.match(/^description:\s*(.+)$/);
        if (m) { summary = m[1].trim(); break; }
      }
      lines = lines.slice(close + 1);
    }
  }

  const para = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (para.length === 0) {
      if (!line || line.startsWith("#")) continue;
      para.push(line);
    } else {
      if (!line || line.startsWith("#")) break;
      para.push(line);
    }
  }

  return { summary, text: para.join(" ") };
}

/**
 * Read and resolve the whole team layer under repoRoot.
 *
 * Every problem — parse, unresolvable handle, missing mandate source —
 * goes to onError as "<repo-relative file>: <problem>"; a profile or
 * roster with problems is left out of the returned maps so downstream
 * consumers stay total (the build fails on the errors regardless).
 *
 * `designNames`, when given, is the set of design names the site
 * publishes; a team.conf under any other directory is an error rather
 * than a roster for a page that will never exist.
 *
 * A missing people/ directory is quietly empty — fixtures and pre-#123
 * checkouts stay valid — and the real-repo unit test pinning the seeded
 * cast is the backstop against the registry silently vanishing.
 */
export function readTeam(repoRoot, { onError = () => {}, designNames } = {}) {
  const people = new Map();
  const rosters = new Map();

  const peopleDir = join(repoRoot, "people");
  let entries = [];
  try {
    entries = readdirSync(peopleDir).filter((f) => f.endsWith(".md")).sort();
  } catch {
    entries = [];
  }

  for (const file of entries) {
    const profilePath = `people/${file}`;
    const handle = file.slice(0, -3);
    if (!HANDLE_RE.test(handle)) {
      onError(`${profilePath}: handle '${handle}' must match ${HANDLE_RE} — rename the file`);
      continue;
    }
    const { header, body, problems } = parseProfile(readFileSync(join(peopleDir, file), "utf8"));
    for (const p of problems) onError(`${profilePath}: ${p}`);
    if (problems.length > 0) continue;

    let mandate;
    if (header.kind === "human") {
      mandate = { source: profilePath, summary: null, text: body };
    } else {
      const source = header.mandate;
      const abs = containedPath(repoRoot, source);
      if (abs === null) {
        onError(`${profilePath}: mandate path '${source}' must be repo-relative with no '..'`);
        continue;
      }
      if (!existsSync(abs) || !statSync(abs).isFile()) {
        onError(`${profilePath}: mandate points at '${source}', which does not exist — fix the path or commit the charter`);
        continue;
      }
      const excerpt = mandateExcerpt(readFileSync(abs, "utf8"));
      if (!excerpt.text) {
        onError(`${profilePath}: mandate source '${source}' has no leading prose paragraph to excerpt`);
        continue;
      }
      mandate = { source, ...excerpt };
    }

    people.set(handle, {
      handle,
      profilePath,
      name: header.name,
      kind: header.kind,
      role: header.role,
      initials: header.initials,
      shared: header.shared,
      github: header.github,
      bio: header.kind === "human" ? body : null,
      mandate,
    });
  }

  let designDirs = [];
  try {
    designDirs = readdirSync(join(repoRoot, "designs"))
      .filter((d) => existsSync(join(repoRoot, "designs", d, "team.conf")))
      .sort();
  } catch {
    designDirs = [];
  }

  for (const design of designDirs) {
    const path = `designs/${design}/team.conf`;
    const { core, pm, problems } = parseTeamConf(readFileSync(join(repoRoot, path), "utf8"));
    if (designNames && !designNames.has(design)) {
      problems.push("names a team for a directory the site does not publish as a design");
    }
    for (const handle of core) {
      const member = people.get(handle);
      if (!member) {
        problems.push(`names '${handle}', which people/ does not register — add people/${handle}.md or fix the handle`);
      } else if (member.shared) {
        problems.push(`'${handle}' is a shared specialist and sits outside per-design cores`);
      }
    }
    for (const p of problems) onError(`${path}: ${p}`);
    if (problems.length > 0) continue;

    rosters.set(design, {
      design,
      path,
      core: core.map((h) => people.get(h)),
      pm: people.get(pm),
    });
  }

  // The interim recent-work manifest. Missing is quiet (same reasoning as a
  // missing people/): pre-#124 checkouts and fixtures stay valid, and the
  // real-repo test is the backstop. Every cross-file reference an entry
  // makes is resolved here — handle registered, team published, cited
  // artifact present in the tree — so a stale citation fails the build
  // instead of shipping a profile whose evidence link 404s.
  for (const member of people.values()) member.work = [];
  const workPath = "people/work.conf";
  let workText = null;
  try {
    workText = readFileSync(join(repoRoot, workPath), "utf8");
  } catch {
    workText = null;
  }
  if (workText !== null) {
    const { entries, problems } = parseWorkConf(workText);
    for (const p of problems) onError(`${workPath}: ${p}`);
    for (const e of entries) {
      const member = people.get(e.handle);
      if (!member) {
        onError(`${workPath}: line ${e.lineno}: names '${e.handle}', which people/ does not register — add people/${e.handle}.md or fix the handle`);
        continue;
      }
      if (e.team !== null && designNames && !designNames.has(e.team)) {
        onError(`${workPath}: line ${e.lineno}: team '${e.team}' is not a design the site publishes — use '-' for repo-wide work`);
        continue;
      }
      const abs = containedPath(repoRoot, e.artifact);
      if (abs === null) {
        onError(`${workPath}: line ${e.lineno}: artifact path '${e.artifact}' must be repo-relative with no '..'`);
        continue;
      }
      if (!existsSync(abs) || !statSync(abs).isFile()) {
        onError(`${workPath}: line ${e.lineno}: cites '${e.artifact}', which does not exist — an entry must cite a committed artifact`);
        continue;
      }
      member.work.push({ date: e.date, team: e.team, text: e.text, artifact: e.artifact });
    }
    // Newest first; the sort is stable, so same-day entries keep file order.
    for (const member of people.values()) {
      member.work.sort((a, b) => b.date.localeCompare(a.date));
    }
  }

  const members = [...people.values()];
  return {
    people,
    members,
    rosters,
    specialists: members.filter((m) => m.shared),
  };
}
