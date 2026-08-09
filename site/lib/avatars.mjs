// Avatar configuration — the single source of truth for how a member's
// DiceBear avatar is derived, shared by every consumer so they cannot drift:
//
//   * team.mjs validates the optional `avatar-style:` / `avatar-seed:`
//     header keys in people/<handle>.md against the curated sets below;
//   * site/avatars.mjs (the generator) renders the committed SVGs from the
//     same resolution;
//   * test/avatars.test.mjs proves each committed SVG matches its member's
//     declared config (regenerate-and-compare, so a header change with a
//     stale SVG fails the suite);
//   * peoplePage embeds the curated sets as JSON for the browser avatar
//     studio, which offers exactly these styles and no others.
//
// The sets are curated on purpose (a decision from the site-wireframes
// design review): people-like styles for humans, machine-like for agents,
// so the human/agent visual distinction the profiles rely on survives any
// member's choice. Style names are the DiceBear package names (kebab-case);
// styleExport maps one to the export name @dicebear/collection uses.

export const AVATAR_STYLES = {
  human: ["notionists", "adventurer", "avataaars", "lorelei", "open-peeps", "micah"],
  agent: ["bottts", "bottts-neutral", "shapes", "rings", "identicon", "thumbs"],
};

/** Every curated style, either kind, deduplicated. */
export const ALL_AVATAR_STYLES = [...new Set([...AVATAR_STYLES.human, ...AVATAR_STYLES.agent])];

/** The Modernist page ground — avatars sit flush on it. */
export const AVATAR_BACKGROUND = "f3f2f2";

/** The defaults the wireframe fixed: notionists = humans, bottts = agents. */
export function defaultStyle(kind) {
  return kind === "human" ? "notionists" : "bottts";
}

/** Default seed: the member's display first name (the wireframe's seeds). */
export function defaultSeed(name) {
  return String(name || "").split(" ")[0];
}

/**
 * Resolve one member's effective avatar config from their committed header
 * (readTeam sets avatarStyle/avatarSeed from the optional keys; absent keys
 * fall back to the kind/name defaults above).
 */
export function avatarConfig(member) {
  return {
    style: member.avatarStyle || defaultStyle(member.kind),
    seed: member.avatarSeed || defaultSeed(member.name),
  };
}

/** kebab-case style name → the @dicebear/collection export name. */
export function styleExport(style) {
  return style.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
}

/** The DiceBear options every avatar here is generated with. */
export function avatarOptions(seed) {
  return { seed, backgroundColor: [AVATAR_BACKGROUND], radius: 0 };
}

/**
 * Validate a declared style for a member kind. Returns null when fine, a
 * problem string (for the readTeam error accumulator) when not.
 */
export function styleProblem(style, kind) {
  const allowed = AVATAR_STYLES[kind] || [];
  if (allowed.includes(style)) return null;
  return `avatar-style '${style}' is not in the curated ${kind} set (${allowed.join(", ")})`;
}
