// Discovery: what the site is made of, read straight out of the repo.
//
// Nothing here is hand-maintained. A new design directory appears on the
// site because it exists on disk, with the same entry-point rule the rest
// of the toolchain uses (designs/<name>/<name>.scad), and the same one-line
// pitch scripts/gallery.sh puts in the README gallery — so the site and the
// README cannot drift into disagreeing about what a design is.

import { readdirSync, readFileSync, existsSync, statSync } from "node:fs";
import { join } from "node:path";

import { declaredParents, parseDerivesConf, resolveLineage } from "./lineage.mjs";
import { aiLifestyleEnabled, isAiLifestyle } from "./media.mjs";
import { categoryOf } from "./catalog.mjs";

export const IMAGE_EXT = new Set([".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]);

function read(path) {
  try {
    return readFileSync(path, "utf8");
  } catch {
    return null;
  }
}

function dirs(path) {
  if (!existsSync(path)) return [];
  return readdirSync(path, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort();
}

/**
 * The design's one-line pitch.
 *
 * Deliberately a port of the `pitch()` shell function in scripts/gallery.sh,
 * rule for rule: NOTES.md's "## Goal" paragraph, falling back to the first
 * prose line of the product page. Keep the two in step — if that script's
 * rule changes, this changes with it, or the gallery in README.md and the
 * gallery on the site start describing the same design differently.
 */
export function pitch(repoRoot, name) {
  let line = "";

  const notes = read(join(repoRoot, "designs", name, "NOTES.md"));
  if (notes) {
    const out = [];
    let hit = false;
    let got = false;
    for (const raw of notes.split("\n")) {
      if (/^##\s+Goal/.test(raw)) {
        hit = true;
        continue;
      }
      if (!hit) continue;
      if (/^\s*$/.test(raw)) {
        if (got) break;
        continue;
      }
      if (/^#/.test(raw)) break;
      out.push(raw);
      got = true;
    }
    line = out.join(" ");
  }

  if (!line) {
    const readme = read(join(repoRoot, "designs", name, "README.md"));
    if (readme) {
      const lines = readme.split("\n");
      for (let i = 0; i < lines.length; i++) {
        const raw = lines[i];
        if (i === 0 && /^#/.test(raw)) continue;
        if (/^\s*$/.test(raw)) continue;
        if (/^[#![|<]/.test(raw)) continue;
        line = raw;
        break;
      }
    }
  }

  line = line.replace(/\s+$/, "").trim();

  // A Goal paragraph that leads into a list ends with "...:" — drop the
  // dangling fragment, keep the complete sentences before it. (Same guard
  // as gallery.sh.)
  if (line.endsWith(":") && line.includes(".")) {
    line = line.slice(0, line.lastIndexOf(".") + 1);
  }
  return line;
}

/** First H1 text of a markdown document, or null. */
export function title(markdown) {
  const m = markdown.match(/^#\s+(.+?)\s*$/m);
  return m ? m[1].trim() : null;
}

/**
 * A prominent warning the product page opens with, if any.
 *
 * nuggs currently carries a "Work in progress — do not print yet" blockquote.
 * A gallery card that quietly dropped that would be actively harmful, so it
 * is lifted out as structured data and shown on the card too.
 */
export function warningBanner(markdown) {
  const bq = markdown.match(/^>\s*\*\*(.+?)\*\*/m);
  if (!bq) return null;
  const text = bq[1].replace(/\s+/g, " ").trim();
  return text.length > 90 ? `${text.slice(0, 88)}…` : text;
}

function lines(path) {
  const raw = read(path);
  if (!raw) return [];
  return raw
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("#"));
}

/**
 * Every design, in gallery order, with its lineage resolved.
 *
 * Order and nesting come from the lineage record, not from the designs/*&#47;
 * glob — a derivative listed as a peer of the design whose geometry it reuses
 * reads as an independent design, and the reader has no way to tell otherwise.
 * That is the rule scripts/gallery.sh follows for the README; issue #55 was
 * this surface disagreeing with it.
 *
 * Each design gains two fields: `depth` (0 for a root) and `parents` (real
 * parent designs, in include order — empty for a root).
 */
export function readDesigns(repoRoot) {
  const out = [];
  const declared = new Map();
  // AI lifestyle imagery feature flag (issue #302). When off (the committed
  // default), every AI-styled preview is dropped at this single source, so it
  // reaches no downstream surface — the media stage, the gallery hero/thumb/
  // count, and the copied asset set all read from `previews`. Geometry-true
  // tier-1 previews are untouched.
  const aiOn = aiLifestyleEnabled(repoRoot);
  for (const name of dirs(join(repoRoot, "designs"))) {
    const dir = join(repoRoot, "designs", name);
    const entry = join(dir, `${name}.scad`);
    const readmePath = join(dir, "README.md");
    // Same entry-point rule as gate.sh/gallery.sh: a directory without
    // designs/<name>/<name>.scad is not a design.
    if (!existsSync(entry) || !existsSync(readmePath)) continue;

    const readme = read(readmePath);
    const parts = lines(join(dir, "ci.parts"));
    const styleConf = lines(join(dir, "style.conf"));

    // Read like ci.parts and style.conf above, but parsed by the lineage
    // port rather than lines(): derives.conf is `key: value`, strips trailing
    // comments, and its parent order is load-bearing.
    // Explicitly against null, not truthiness: read() returns "" for a
    // present-but-empty derives.conf, and that is a file that exists. Parsing
    // it yields no parents, which is what skipping it yields too — so the two
    // agree today — but keeping one test for "the file is there" stops that
    // equivalence from being load-bearing. site/test/lineage.test.mjs pins it.
    const derives = read(join(dir, "derives.conf"));
    declared.set(
      name,
      derives !== null ? declaredParents(parseDerivesConf(derives)) : []
    );

    const previewsDir = join(dir, "previews");
    const previews = (
      existsSync(previewsDir)
        ? readdirSync(previewsDir)
            .filter((f) => IMAGE_EXT.has(f.slice(f.lastIndexOf(".")).toLowerCase()))
            .sort()
        : []
    ).filter((f) => aiOn || !isAiLifestyle(f));

    const scads = readdirSync(dir)
      .filter((f) => f.endsWith(".scad"))
      .sort();

    out.push({
      name,
      dir,
      relDir: `designs/${name}`,
      readme,
      readmePath,
      title: title(readme) || name,
      pitch: pitch(repoRoot, name),
      // The catalog group (issue #374): "nuggs" for a real NUGGS module (a
      // nuggs/nuggs-* name that ALSO reaches lib/nuggs-coupling.scad through
      // its include closure — issue #517), else designs/<name>/catalog.conf's
      // category. build.mjs buckets the index by it; scripts/catalog.sh is the
      // authority both surfaces agree with.
      category: categoryOf(dir, name),
      warning: warningBanner(readme),
      parts,
      style: styleConf[0] || null,
      previews,
      scads,
      hero: previews.includes("product-hero.png")
        ? "product-hero.png"
        : previews.includes("contact-sheet.png")
          ? "contact-sheet.png"
          : previews[0] || null,
      thumb: previews.includes("contact-sheet.png")
        ? "contact-sheet.png"
        : previews[0] || null,
      hasCoupon: existsSync(join(dir, `${name}-coupon.scad`)),
      hasDerivesConf: derives !== null,
    });
  }

  const { parents, order, unreachable } = resolveLineage(
    out.map((d) => d.name),
    declared
  );
  const byName = new Map(out.map((d) => [d.name, d]));

  const ordered = [];
  for (const row of order) {
    const design = byName.get(row.name);
    design.depth = row.depth;
    design.parents = parents.get(row.name);
    ordered.push(design);
  }
  // A design on a lineage cycle has no place in the tree. Still list it —
  // dropping a design from the index silently is worse than showing it
  // unnested — and flag it so build.mjs can fail the build, which is what the
  // Python `order` does (exit 1) rather than answering.
  for (const name of unreachable) {
    const design = byName.get(name);
    design.depth = 0;
    design.parents = parents.get(name);
    design.lineageCycle = true;
    ordered.push(design);
  }
  return ordered;
}

export function readStyles(repoRoot) {
  const out = [];
  for (const name of dirs(join(repoRoot, "styles"))) {
    const dir = join(repoRoot, "styles", name);
    const specPath = join(dir, "STYLE.md");
    if (!existsSync(specPath)) continue;
    const spec = read(specPath);

    let summary = "";
    try {
      const json = JSON.parse(read(join(dir, "style.json")) || "{}");
      summary = json.description || json.summary || "";
    } catch {
      summary = "";
    }
    if (!summary) {
      for (const raw of spec.split("\n")) {
        if (/^\s*$/.test(raw)) continue;
        if (/^[#![|<>]/.test(raw)) continue;
        summary = raw.trim();
        break;
      }
    }

    const swatch = join(dir, "previews", "swatch.png");
    out.push({
      name,
      dir,
      relDir: `styles/${name}`,
      spec,
      specPath,
      title: title(spec) || name,
      summary,
      swatch: existsSync(swatch) ? "previews/swatch.png" : null,
    });
  }
  return out;
}

/** Designs that declare a given style, for cross-linking. */
export function designsUsingStyle(designs, styleName) {
  return designs.filter((d) => d.style === styleName);
}

export function fileExists(path) {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}
