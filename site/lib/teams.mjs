// The Teams page building blocks (issue #125): the team switcher strip and
// the product-scoped team page. A switcher card per rostered product, and a
// team page that lays out the hero, the level-field core roster (equal peers,
// no hierarchy), a light "reviewed by" reference to the shared specialists,
// and the slot the history timeline (#126) fills.
//
// These are pure functions of committed data — a roster record from team.mjs,
// a design's resolved pitch from content.mjs — so they unit-test on hand-built
// records. The page shell that wraps them lives in templates.mjs, mirroring
// how sharedPage sits beside the profile component it renders. The member
// profile itself (#124) is consumed UNCHANGED: coreRoster calls memberProfile
// with the product's scope, so recent work reads "on <team>" here and the
// same component reads "across teams" on the Shared resources page.

import { escapeHtml, inlineMarkdown } from "./markdown.mjs";
import { memberProfile, memberTeams } from "./profile.mjs";

/**
 * Overlapping kind-coded monograms for a roster's core — the faces on a
 * switcher card. Reuses the profile monogram (initials, no avatars) so a
 * human and an agent read the same colour they do everywhere else.
 */
export function memberFaces(core) {
  return `<span class="switcher-faces" aria-hidden="true">${core
    .map(
      (m) => `<span class="monogram monogram-${m.kind}">${escapeHtml(m.initials)}</span>`
    )
    .join("")}</span>`;
}

/**
 * One switcher card: the product name (linked to its team page), the "ships"
 * pitch (the gallery rule's one-liner, resolved by the caller and passed in),
 * and the overlapping member faces. The current team is marked so the strip
 * reads as a switcher — the reader is already on it, so it is highlighted,
 * not somewhere to click away to.
 */
export function switcherCard(roster, { pitch, href, current }) {
  const cls = current ? "switcher-card is-current" : "switcher-card";
  const aria = current ? ' aria-current="true"' : "";
  return `<article class="${cls}"${aria}>
  <h3 class="switcher-name"><a href="${href}">${escapeHtml(roster.design)}</a></h3>
  <p class="switcher-pitch">${inlineMarkdown(pitch)}</p>
  ${memberFaces(roster.core)}
</article>`;
}

/**
 * The switcher strip: one card per rostered team, current team highlighted.
 * Data-driven off the rosters map, so a product appears here the moment it
 * gets a committed team.conf — the site invents no membership.
 *
 *   pitchFor(design)  the design's one-line "ships" pitch (gallery rule).
 *   teamHref(design)  where a card links (v1 publishes one team page).
 *   currentDesign     the design whose card is highlighted.
 */
export function switcherStrip(rosters, { pitchFor, teamHref, currentDesign }) {
  const cards = [...rosters.values()]
    .map((r) =>
      switcherCard(r, {
        pitch: pitchFor(r.design),
        href: teamHref(r.design),
        current: r.design === currentDesign,
      })
    )
    .join("\n");
  return `<div class="switcher-strip">
${cards}
</div>`;
}

/**
 * The level-field core roster: one equal peer card per core member — the
 * human(s) and the PM agent, no hierarchy — each the full member profile,
 * product-scoped so recent work reads "on <design>". The only difference
 * between two cards is the kind colour on the card edge; nothing marks the PM
 * above a human. Reviewers are never here: team.mjs refuses a shared handle
 * in a core, so iterating the core cannot surface one.
 */
export function coreRoster(roster, { rosters, githubBase }) {
  const cards = roster.core
    .map(
      (m) => `<div class="card profile-card peer-card peer-${m.kind}">
${memberProfile(m, {
        scope: roster.design,
        teams: memberTeams(m, rosters),
        githubBase,
      })}
</div>`
    )
    .join("\n");
  return `<div class="grid level-field">
${cards}
</div>`;
}

/**
 * The light "Reviewed by →" reference: the shared specialists servicing this
 * product (every team can call on them), named and linked to their profile on
 * the Shared resources page. Deliberately not roster cards — a reviewer is a
 * shared resource, not core team (the #122 distinction).
 */
export function reviewedBy(specialists) {
  if (!specialists.length) return "";
  const names = specialists
    .map(
      (m) => `<a href="/shared/#profile-${escapeHtml(m.handle)}">${escapeHtml(m.name)}</a>`
    )
    .join(", ");
  return `<p class="reviewed-by">Reviewed by <span aria-hidden="true">→</span> ${names} <a class="reviewed-all" href="/shared/">Shared resources</a></p>`;
}

/**
 * The "History of work together" slot. Issue #125 lays the section out; its
 * data is #126 (the PM.md-sourced timeline). Until that lands the slot is an
 * honest empty state — no invented history, per #122's first principle.
 */
export function historySlot(design) {
  return `<section class="team-history">
  <p class="eyebrow">History of work together</p>
  <p class="history-empty muted">The shared record of work on <code>${escapeHtml(
    design
  )}</code> — the team's decisions and field tests over time — lands here with the history timeline (issue #126).</p>
</section>`;
}
