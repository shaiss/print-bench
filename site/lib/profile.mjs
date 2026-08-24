// The reusable member profile (issue #124): one member record from
// team.mjs rendered as a self-contained block — identity, role, the
// readable mandate with its source cited, team chips, recent work.
//
// Rendered on the People page in the cross-team scope (issue #122's revised
// IA): the caller passes a `scope` (a design name, or null) and the component
// both filters the recent-work list to that scope and words the heading
// accordingly — "on <team>" for a product-scoped view, "across teams"
// otherwise. That is the product-scoping principle from #122 as it shows up
// in a member view. (The product page shows only light *identity* that links
// here — see teams.mjs; the full profile lives on the People page.)
//
// Everything rendered is committed data resolved by readTeam: the mandate
// text was read from the member's charter at build time, and every work
// entry cites an artifact the reader proved exists. Team chips link to the
// team's product page. No avatars: initials monograms only (#122 non-goal).

import { avatarConfig } from "./avatars.mjs";
import { escapeHtml, inlineExcerpt } from "./markdown.mjs";

/**
 * The member's identity mark: the committed DiceBear avatar where one
 * exists (readTeam sets `avatar` only after proving the file is there),
 * the kind-coded initials monogram otherwise. Both live in the same
 * .monogram box, so every caller (profile, contributor card, timeline
 * attribution) renders either without caring which.
 */
export function identityMark(member) {
  if (member.avatar) {
    return `<img class="monogram monogram-${member.kind}" src="${escapeHtml(member.avatar)}" alt="" width="46" height="46">`;
  }
  return `<span class="monogram monogram-${member.kind}" aria-hidden="true">${escapeHtml(member.initials)}</span>`;
}

/** The design names whose roster lists this member, in roster order. */
export function memberTeams(member, rosters) {
  const teams = [];
  for (const roster of rosters.values()) {
    if (roster.core.some((m) => m.handle === member.handle)) teams.push(roster.design);
  }
  return teams;
}

/**
 * A mandate source is cited the way a reader names it — the skill
 * directory, not the SKILL.md inside it — while the link still targets the
 * real file.
 */
function citeSource(source) {
  return source.endsWith("/SKILL.md") ? source.slice(0, -"/SKILL.md".length) : source;
}

/**
 * A repo path dropped into an href, each segment URL-encoded — the same
 * treatment templates.mjs gives design names, so a quote or fragment
 * character in a committed filename can never break out of the attribute.
 */
function sourceHref(githubBase, source) {
  return `${githubBase}/${source.split("/").map(encodeURIComponent).join("/")}`;
}

function workItem(entry, { scoped, githubBase }) {
  // In the across-teams view each entry says which team it happened on; in
  // a team-scoped view that would repeat the heading.
  const teamTag =
    !scoped && entry.team
      ? ` <a class="tag tag-plain" href="/designs/${encodeURIComponent(entry.team)}/">${escapeHtml(entry.team)}</a>`
      : "";
  return `<li>
      <span class="work-date">${escapeHtml(entry.date)}</span>
      <span class="work-text">${escapeHtml(entry.text)}${teamTag}
        <a class="work-artifact" href="${sourceHref(githubBase, entry.artifact)}" rel="noopener noreferrer"><code>${escapeHtml(entry.artifact)}</code></a></span>
    </li>`;
}

/**
 * Render one member profile.
 *
 *   scope       a design name to scope "recent work" to, or null for the
 *               cross-team view. Also picks the heading's wording.
 *   teams       design names whose roster lists this member (memberTeams).
 *   githubBase  where non-served sources (charters, artifacts) link to.
 */
export function memberProfile(member, { scope = null, teams = [], githubBase }) {
  const pills = [
    `<span class="pill pill-${member.kind}">${member.kind}</span>`,
    member.shared ? '<span class="pill pill-shared">shared across print-bench</span>' : "",
  ]
    .filter(Boolean)
    .join("\n      ");

  const mandateSummary = member.mandate.summary
    ? `<p class="mandate-summary">${inlineExcerpt(member.mandate.summary)}</p>`
    : "";

  const teamChips = teams.length
    ? `<section class="profile-teams">
    <h4>Teams</h4>
    <p>${teams
      .map(
        (t) => `<a class="tag" href="/designs/${encodeURIComponent(t)}/">${escapeHtml(t)}</a>`
      )
      .join("\n      ")}</p>
  </section>`
    : "";

  const scoped = scope !== null;
  const scopeLabel = scoped
    ? `on <code>${escapeHtml(scope)}</code>`
    : "across teams";
  const work = scoped ? member.work.filter((w) => w.team === scope) : member.work;
  const workList = work.length
    ? `<ul class="work-list">
${work.map((w) => workItem(w, { scoped, githubBase })).join("\n")}
    </ul>`
    : `<p class="work-empty muted">Nothing recorded yet.</p>`;

  // The avatar studio's hook (People page only): the identity mark wrapped in
  // a slot carrying the member's effective committed config, plus the re-roll
  // glyph. The studio is browser-local — a re-roll changes this visitor's
  // view (localStorage), and the panel shows the header lines whose commit
  // makes it everyone's. Progressive enhancement: site.js reveals the button.
  const { style, seed } = avatarConfig(member);
  const avatarSlot = `<span class="avatar-slot" data-avatar-slot data-handle="${escapeHtml(member.handle)}" data-kind="${escapeHtml(member.kind)}" data-style="${escapeHtml(style)}" data-seed="${escapeHtml(seed)}">
      ${identityMark(member)}
      <button class="avatar-reroll" type="button" data-avatar-reroll hidden
        title="Re-roll this avatar — changes your view only"
        aria-label="Re-roll ${escapeHtml(member.name)}'s avatar (your view only)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg></button>
    </span>`;

  return `<article class="profile" id="profile-${escapeHtml(member.handle)}">
  <header class="profile-head">
    ${avatarSlot}
    <div class="profile-id">
      <h3 class="profile-name">${escapeHtml(member.name)} <code class="profile-handle">${escapeHtml(member.handle)}</code></h3>
      <p class="profile-role">${escapeHtml(member.role)}</p>
    </div>
    <div class="profile-pills">
      ${pills}
    </div>
  </header>
  <section class="profile-mandate">
    <h4>Mandate &amp; instructions</h4>
    ${mandateSummary}
    <p>${inlineExcerpt(member.mandate.text)}</p>
    <p class="mandate-source muted">From <a href="${sourceHref(githubBase, member.mandate.source)}" rel="noopener noreferrer"><code>${escapeHtml(citeSource(member.mandate.source))}</code></a></p>
  </section>
  ${teamChips}
  <section class="profile-work">
    <h4>Recent work <span class="work-scope">· ${scopeLabel}</span></h4>
    ${workList}
  </section>
</article>`;
}
