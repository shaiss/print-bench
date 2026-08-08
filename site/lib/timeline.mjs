// The "History of work together" timeline (issue #126): a team's shared
// record, rendered on the team page (#125) from COMMITTED files only, with
// attribution — who did each thing.
//
// The one principle behind #122, and the hard boundary of this issue: the
// site invents no content, and v1 reads only what is already committed.
// Non-committed history (git commits/PRs, review threads, telemetry
// gate-runs) is explicitly out of scope — it is a *seam*, not a feature,
// here. So this module is two things:
//
//   1. A tiny **source adapter interface** (see SOURCES below) so a future
//      issue can add a git/PR/review/telemetry source without touching the
//      assembly or the render. Each source is a pure function of committed
//      inputs → events + problems, exactly the collect-don't-throw contract
//      the rest of site/lib uses.
//   2. Two concrete committed-only sources — the design's `PM.md` decision
//      log (the real, already-committed calibration-cube content this issue
//      calibrates on) and, optionally, the `NOTES.md` field-test log (the
//      FIELD-TEST convention, issue #101) — plus the assembly that merges
//      them newest-first and the render that lays them out.
//
// Product-scoping (the #122 principle): a timeline is *one product's*
// history. Every source reads that one design's own committed files; there
// are no cross-team events by construction.
//
// Attribution is best-effort and honest: an event carries a member `handle`
// only where it is *derivable* from committed data. A PM.md decision is the
// charter owner's by definition, so it attributes to the roster's `pm`; a
// field-test entry names a printer, not a member, so it stays unattributed
// rather than guessing. An unresolvable or absent handle renders plain.

import { escapeHtml } from "./markdown.mjs";

/**
 * Real-calendar YYYY-MM-DD check, shared with the rest of site/lib: the
 * regex alone accepts 2026-02-30, the UTC round-trip rejects any date the
 * calendar does not have. (Same rule as team.mjs's parseWorkConf.)
 */
function isRealDate(date) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
  const d = new Date(`${date}T00:00:00Z`);
  return !Number.isNaN(d.valueOf()) && d.toISOString().slice(0, 10) === date;
}

/**
 * Split one GFM table row into trimmed cells. Pipes escaped as `\|` are
 * literal cell content, not delimiters, and are unescaped; the leading and
 * trailing empty cells a `| a | b |` row produces are dropped.
 */
function tableCells(row) {
  const cells = [];
  let cur = "";
  for (let i = 0; i < row.length; i++) {
    const ch = row[i];
    if (ch === "\\" && row[i + 1] === "|") {
      cur += "|";
      i++;
    } else if (ch === "|") {
      cells.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  cells.push(cur);
  const trimmed = cells.map((c) => c.trim());
  if (trimmed.length && trimmed[0] === "") trimmed.shift();
  if (trimmed.length && trimmed[trimmed.length - 1] === "") trimmed.pop();
  return trimmed;
}

/** A `|---|:--:|` GFM table separator row (dashes, optional colons, pipes). */
function isSeparatorRow(row) {
  const cells = tableCells(row);
  return cells.length > 0 && cells.every((c) => /^:?-+:?$/.test(c));
}

/**
 * Return the lines of the section introduced by a `## <title>` (level-2)
 * heading, up to the next heading of the same-or-higher level or EOF, each
 * paired with its absolute (1-indexed) line number. Returns null when no
 * such section exists — an absent section is a quiet zero, not a problem
 * (a design need not keep a decision log).
 */
function sectionLines(text, title) {
  const lines = text.split("\n");
  const want = title.trim().toLowerCase();
  let start = -1;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^(#{1,6})\s+(.*?)\s*$/);
    if (m && m[1].length === 2 && m[2].trim().toLowerCase() === want) {
      start = i + 1;
      break;
    }
  }
  if (start === -1) return null;
  const out = [];
  for (let i = start; i < lines.length; i++) {
    if (/^#{1,2}\s+/.test(lines[i])) break; // next # or ## ends the section
    out.push({ text: lines[i], lineno: i + 1 });
  }
  return out;
}

/**
 * Parse a `## Decision log` table into entries.
 *
 * The pinned line shape (templates/PM.md): a level-2 "Decision log"
 * heading, then a GFM table whose header is `| Date | Decision | Reason |`,
 * a separator row, then one row per decision. Every data row must be three
 * non-empty cells with a real date; anything else is a collected problem,
 * not a thrown error, so one bad row cannot hide the rest.
 *
 * Contract:
 *   - no section            -> { entries: [], problems: [] }   (quiet)
 *   - section, no table     -> a problem (the log drifted out of shape)
 *   - wrong header columns  -> a problem (the shape this reader pins moved)
 *   - a malformed data row  -> a problem, that row skipped, others kept
 */
export function parseDecisionLog(text) {
  const problems = [];
  const entries = [];
  const section = sectionLines(text, "Decision log");
  if (section === null) return { entries, problems };

  // Find the header row: the first line that is a *table row*, i.e. begins
  // with a pipe (the pinned template shape, `| Date | Decision | Reason |`).
  // Prose before the table — the append-only note — is skipped, and an
  // incidental pipe *inside* that prose can no longer be mistaken for the
  // header, since prose does not start with one.
  let h = -1;
  for (let i = 0; i < section.length; i++) {
    const t = section[i].text.trim();
    if (!t) continue;
    if (t.startsWith("|")) { h = i; break; }
    // Prose (the append-only note) before the table is fine; keep scanning.
  }
  if (h === -1) {
    problems.push("has a '## Decision log' section but no table");
    return { entries, problems };
  }

  const header = tableCells(section[h].text);
  const expected = ["date", "decision", "reason"];
  const got = header.map((c) => c.toLowerCase());
  if (got.length !== 3 || !expected.every((c, i) => got[i] === c)) {
    problems.push(
      `line ${section[h].lineno}: decision-log header must be | Date | Decision | Reason |, got | ${header.join(" | ")} |`,
    );
    return { entries, problems };
  }
  // The separator row must match the header's three columns — a one-cell
  // `|---|` under a three-column header is itself drift.
  const sep = h + 1 < section.length ? section[h + 1] : null;
  if (!sep || !isSeparatorRow(sep.text) || tableCells(sep.text).length !== 3) {
    problems.push(`line ${section[h].lineno + 1}: decision-log header must be followed by a 3-column |---|---|---| separator row`);
    return { entries, problems };
  }

  for (let i = h + 2; i < section.length; i++) {
    const raw = section[i].text;
    const t = raw.trim();
    if (!t) break; // a blank line ends the table
    if (!t.includes("|")) break; // table ended, prose resumed
    const lineno = section[i].lineno;
    const cells = tableCells(raw);
    if (cells.length !== 3) {
      problems.push(`line ${lineno}: decision-log row must have 3 cells (date | decision | reason), got ${cells.length}`);
      continue;
    }
    const [date, decision, reason] = cells;
    if (!isRealDate(date)) {
      problems.push(`line ${lineno}: decision-log date '${date}' must be a real YYYY-MM-DD date`);
      continue;
    }
    if (!decision || !reason) {
      problems.push(`line ${lineno}: decision-log decision and reason must both be non-empty`);
      continue;
    }
    entries.push({ date, decision, reason, lineno });
  }
  return { entries, problems };
}

/**
 * Parse a `## Field test log` section into entries (issue #101 convention).
 *
 * Each real print is a `### YYYY-MM-DD — <printer>` subheading (an em-dash
 * or a hyphen separates the date from the printer). Only the date is
 * validated and pinned; the printer label is free text. Optional source —
 * a design without the section yields nothing, quietly.
 */
export function parseFieldTestLog(text) {
  const problems = [];
  const entries = [];
  const section = sectionLines(text, "Field test log");
  if (section === null) return { entries, problems };

  for (const { text: raw, lineno } of section) {
    const m = raw.match(/^###\s+(.*\S)\s*$/);
    if (!m) continue;
    const heading = m[1].trim();
    const sep = heading.match(/^(\S+)\s*(?:—|-)\s*(.*)$/);
    const date = sep ? sep[1] : heading;
    const printer = sep ? sep[2].trim() : "";
    if (!isRealDate(date)) {
      problems.push(`line ${lineno}: field-test heading must start with a real YYYY-MM-DD date, got '${heading}'`);
      continue;
    }
    entries.push({ date, printer, lineno });
  }
  return { entries, problems };
}

// ---------------------------------------------------------------------------
// The source adapter interface (the seam).
//
// A source is: { id, label, read(ctx) -> { events, problems } }
//   ctx    = { pmText, notesText, roster }
//            pmText/notesText are the committed file contents (or null when
//            the file is absent); roster is the design's team.mjs roster
//            (or null when rosterless) — used only for attribution.
//   event  = { date, source, sourceTag, text, detail, handle }
//            handle is a member handle or null (attribution where derivable).
//
// Every seeded source reads only committed inputs. Adding a git/PR/review/
// telemetry source later means adding an entry here whose read() draws on
// that source — the assembly (readTimeline) and the render (historyTimeline)
// do not change. Non-committed sources are deliberately unimplemented: v1
// is committed-only (#122 non-goal), and the interface is the whole point of
// laying the seam now.
// ---------------------------------------------------------------------------

/** The design's PM.md decision log — the charter owner's recorded choices. */
export const decisionLogSource = {
  id: "decision-log",
  label: "decision · PM.md",
  read({ pmText, roster }) {
    if (pmText == null) return { events: [], problems: [] };
    const { entries, problems } = parseDecisionLog(pmText);
    const handle = roster && roster.pm ? roster.pm.handle : null;
    const events = entries.map((e) => ({
      date: e.date,
      source: "decision-log",
      sourceTag: "decision · PM.md",
      text: e.decision,
      detail: e.reason,
      handle,
    }));
    return { events, problems };
  },
};

/** The design's NOTES.md field-test log — real prints (issue #101). */
export const fieldTestSource = {
  id: "field-test",
  label: "field test · NOTES.md",
  read({ notesText }) {
    if (notesText == null) return { events: [], problems: [] };
    const { entries, problems } = parseFieldTestLog(notesText);
    // A field-test names a printer, not a member — attribution is not
    // derivable, so it stays null rather than guessing.
    const events = entries.map((e) => ({
      date: e.date,
      source: "field-test",
      sourceTag: "field test · NOTES.md",
      text: e.printer ? `Field test — ${e.printer}` : "Field test",
      detail: "",
      handle: null,
    }));
    return { events, problems };
  },
};

/** The committed-only sources v1 reads, in declaration order. */
export const SOURCES = [decisionLogSource, fieldTestSource];

/**
 * Assemble one product's timeline from its committed inputs.
 *
 *   ctx      { pmText, notesText, roster } — see the interface above.
 *   sources  the adapters to run (defaults to SOURCES); the seam that lets
 *            a caller or a future issue swap the source set without
 *            touching assembly or render.
 *
 * Returns { events, problems }: events newest-first (stable — same-day
 * events keep source-declaration then in-file order), problems collected
 * across every source. Same collect-don't-throw contract as readTeam, so
 * build.mjs can fail the deploy on any problem without a page rendering a
 * hole.
 */
export function readTimeline(ctx, sources = SOURCES) {
  const events = [];
  const problems = [];
  for (const source of sources) {
    const res = source.read(ctx);
    events.push(...res.events);
    problems.push(...res.problems);
  }
  // Newest first; stable so the push order above breaks ties deterministically.
  events.sort((a, b) => b.date.localeCompare(a.date));
  return { events, problems };
}

/**
 * Render the timeline's events as an ordered list — the inner content of the
 * team page's "History of work together" section (teams.mjs's historySlot
 * owns the section wrapper and heading, so the history block reads in the
 * team page's own section-label style rather than introducing a heading of
 * its own).
 *
 *   events      from readTimeline (already newest-first).
 *   people      the team.mjs people Map (handle -> member), for attribution
 *               monograms; a handle absent from it renders plain.
 *
 * Returns "" for an empty timeline, leaving the caller to word the honest
 * empty state in its own context (a design with no committed history yet).
 * Self-contained and theme-aware: every class draws on existing site.css
 * tokens (see the .timeline rules), no external reference, no avatars —
 * initials monograms only, the same convention as the member profile.
 */
export function timelineEvents(events, { people = new Map() } = {}) {
  if (!events.length) return "";
  const items = events
    .map((e) => {
      const member = e.handle ? people.get(e.handle) : null;
      const who = member
        ? `<span class="timeline-who">
        <span class="monogram monogram-${member.kind}" aria-hidden="true">${escapeHtml(member.initials)}</span>
        <span class="timeline-who-name">${escapeHtml(member.name)} <code>${escapeHtml(member.handle)}</code></span>
      </span>`
        : "";
      const detail = e.detail
        ? `\n      <p class="timeline-detail muted">${escapeHtml(e.detail)}</p>`
        : "";
      return `    <li class="timeline-event">
      <div class="timeline-meta">
        <span class="timeline-date">${escapeHtml(e.date)}</span>
        <span class="tag tag-plain timeline-source">${escapeHtml(e.sourceTag)}</span>
      </div>
      <p class="timeline-text">${escapeHtml(e.text)}</p>${detail}
      ${who}
    </li>`;
    })
    .join("\n");

  return `<ol class="timeline">
${items}
  </ol>`;
}
