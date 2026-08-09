// The product page's media stage (the "Product Page Media Rework", PR #159):
// classify a design's committed previews by filename convention, lift the
// README's top-level image embeds — and the italic AI disclaimers that follow
// them — out of the prose, and order the result hero-first for the stage +
// labeled thumbnail rail. The README file itself is untouched: it keeps its
// embeds and disclosures (readme-gate.sh requirement 9 gates them there);
// this only changes how the *site* presents what the README already carries.

const MEDIA_EXT = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp"]);

/** The standard AI disclosures, shown as a stage caption on exactly the
 * media they apply to — same substance as the README's italic paragraphs. */
export const AI_STILL_DISCLOSURE =
  "AI-generated impression for general illustration only — geometry is approximate and may not exactly match the printed part; see the studio render and the STL for the true shape.";
export const AI_MOTION_DISCLOSURE =
  "AI-generated motion impression for general illustration only — geometry is approximate, and the movement shown is illustrative, not a simulation; see the deterministic previews and the STL for the true shape.";

/** "lifestyle-bench-calipers.png" → "Bench Calipers". */
export function mediaLabel(file) {
  return file
    .replace(/\.[a-z0-9]+$/i, "")
    .replace(/^lifestyle-/, "")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * What a preview *is*, from the repo's filename conventions (product-shot.sh,
 * animate.sh, lifestyle-shot.sh/-clip.sh all write these names). `ai` media
 * carry the disclosure caption; `motion` picks the motion wording.
 */
export function classifyMedia(file) {
  const gif = /\.gif$/i.test(file);
  if (/^lifestyle-/.test(file))
    return { kind: gif ? "AI motion clip" : "AI-styled scene", ai: true, motion: gif };
  if (/^product-hero\./.test(file)) return { kind: "Studio render", ai: false, motion: false };
  if (/^turntable\./.test(file)) return { kind: "Turntable", ai: false, motion: true };
  if (/^contact-sheet\./.test(file))
    return { kind: "4-view contact sheet", ai: false, motion: false };
  return { kind: gif ? "Animation" : "Detail", ai: false, motion: gif };
}

/**
 * Lift the README's media embeds out of the prose.
 *
 * Strips exactly two line shapes, both at top level:
 *  - `![alt](previews/<file>)` — the embed moves to the stage, its alt text
 *    kept as the stage caption;
 *  - the single-line italic AI disclaimers that follow lifestyle embeds
 *    (`*AI-generated …*` / an italic line saying "geometry is approximate") —
 *    the stage re-states the disclosure on the media itself.
 * Everything else — headings, the archived blockquote, tables, links — is
 * returned unchanged. That the match is anchored to the whole line is policy,
 * not accident: an embed *inside* prose structure (desiccant-capsule's
 * labeled comparison table) is content placed in context, stays in the body,
 * and keeps flowing through the markdown reference checker; only the
 * standalone image wall moves to the stage.
 */
export function stripReadmeMedia(markdown) {
  const alts = new Map();
  const kept = [];
  // A disclaimer is stripped only when the last lifted embed was AI media —
  // the stage re-states the disclosure there. An italic line that merely
  // resembles one, standing alone in prose, is content and stays.
  let lastLiftedAi = false;
  for (const line of markdown.split("\n")) {
    const t = line.trim();
    const img = /^!\[([^\]]*)\]\(previews\/([^)\s]+)\)$/.exec(t);
    if (img) {
      alts.set(img[2], img[1]);
      lastLiftedAi = /^lifestyle-/.test(img[2]);
      continue;
    }
    if (
      lastLiftedAi &&
      (/^\*(AI-generated|This is an AI)/.test(t) ||
        /^\*.*geometry is approximate.*\*$/.test(t))
    ) {
      lastLiftedAi = false;
      continue;
    }
    if (t !== "") lastLiftedAi = false;
    kept.push(line);
  }
  return { markdown: kept.join("\n"), alts };
}

/**
 * README preview embeds that name a file the design does not ship. The
 * stripper lifts embeds before the markdown reference checker sees them, so
 * without this check a broken embed would vanish silently instead of failing
 * the build (the site's unresolved-local-reference rule).
 */
export function missingMediaRefs(alts, previews) {
  const have = new Set(previews || []);
  return [...alts.keys()].filter((f) => !have.has(f));
}

/**
 * The stage's ordered media list for one design: hero first, then the
 * README's own embed order, then previews the README doesn't embed, the
 * 4-view contact sheet last. Every entry is a committed file in
 * designs/<name>/previews/.
 */
export function designMedia(design, alts = new Map()) {
  const files = (design.previews || []).filter((f) =>
    MEDIA_EXT.has(f.slice(f.lastIndexOf(".")).toLowerCase())
  );
  const bucket = (f) =>
    /^product-hero\./.test(f) ? 0 : /^contact-sheet\./.test(f) ? 2 : 1;
  const embedOrder = [...alts.keys()];
  const embedRank = (f) => {
    const i = embedOrder.indexOf(f);
    return i === -1 ? embedOrder.length : i;
  };
  files.sort((a, b) => bucket(a) - bucket(b) || embedRank(a) - embedRank(b));
  return files.map((file) => {
    const cls = classifyMedia(file);
    return {
      file,
      label: mediaLabel(file),
      alt: alts.get(file) || `${design.title} — ${mediaLabel(file)}`,
      ...cls,
      disclosure: cls.ai ? (cls.motion ? AI_MOTION_DISCLOSURE : AI_STILL_DISCLOSURE) : null,
    };
  });
}
