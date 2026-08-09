// The team/org building blocks. Two surfaces render from this committed data
// (a roster from team.mjs, the design's timeline from timeline.mjs):
//
//   * the **product page** carries the team as two tab-panels (the site
//     wireframes' 1d IA): Team — who built this product (identity only, not
//     their profile: contributorRow + reviewedBy) — and History, the build
//     history (historySlot). The team as seen *from the product*,
//     product-scoped; templates.mjs designPage composes them.
//   * the **People page** (templates.mjs peoplePage) is the directory of
//     everyone — humans, PM agents, shared specialists — each rendered as the
//     full member profile with the product teams they've been part of.
//
// The split is deliberate (the #122 IA, revised): a product page answers "who
// made this and what did they do to it"; a person's profile and their whole
// story live on the People page. So the product page shows light identity
// cards that *link* to the profile — never the profile itself.
//
// Pure functions of committed data, so they unit-test on hand-built records.

import { escapeHtml } from "./markdown.mjs";
import { identityMark } from "./profile.mjs";
import { timelineEvents } from "./timeline.mjs";

/**
 * One light identity card for the product-page contributions row: the
 * kind-coded initials monogram, the member's name and handle, and their role
 * — linking to their full profile on the People page. Identity, not profile
 * (the #122 distinction as it shows up on the product page).
 */
export function contributorCard(member) {
  return `<a class="contributor" href="/people/#profile-${escapeHtml(member.handle)}">
  ${identityMark(member)}
  <span class="contributor-id">
    <span class="contributor-name">${escapeHtml(member.name)} <code>${escapeHtml(member.handle)}</code></span>
    <span class="contributor-role muted">${escapeHtml(member.role)}</span>
  </span>
</a>`;
}

/** The core team's identity cards, in roster order (no hierarchy). */
export function contributorRow(core) {
  return `<div class="contributor-row">
${core.map(contributorCard).join("\n")}
</div>`;
}

/**
 * The light "Reviewed by →" reference: the shared specialists servicing this
 * product (every team can call on them), named and linked to their profile on
 * the People page. Deliberately not roster cards — a reviewer is a shared
 * resource, not core team (the #122 distinction).
 */
export function reviewedBy(specialists) {
  if (!specialists.length) return "";
  const names = specialists
    .map(
      (m) => `<a href="/people/#profile-${escapeHtml(m.handle)}">${escapeHtml(m.name)}</a>`
    )
    .join(", ");
  return `<p class="reviewed-by">Reviewed by <span aria-hidden="true">→</span> ${names} <a class="reviewed-all" href="/people/">People</a></p>`;
}

/**
 * The "History of work together" block: the product's shared record, built
 * from committed sources only (issue #126). The events are assembled in
 * build.mjs (which has filesystem access to the design's PM.md / NOTES.md) by
 * readTimeline and passed in already newest-first, attributed where derivable;
 * timelineEvents renders them. A design with no committed history yet keeps the
 * honest empty state — no invented history, per #122's first principle.
 *
 *   events   the design's timeline events (readTimeline), or [].
 *   people   the team.mjs people Map, for attribution monograms.
 */
export function historySlot(design, { events = [], people = new Map() } = {}) {
  const list = timelineEvents(events, { people });
  const body =
    list ||
    `<p class="history-empty muted">The shared record of work on <code>${escapeHtml(
      design
    )}</code> — the team's decisions and field tests over time — lands here as it accumulates.</p>`;
  return `<section class="team-history">
  <p class="eyebrow">History of work together</p>
  ${body}
</section>`;
}

