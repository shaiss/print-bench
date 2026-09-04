// The site's catalog-grouping port, held to scripts/catalog.sh (issue #374).
//
// The design catalog is grouped — one NUGGS ecosystem collection plus the
// technique domains from docs/advanced-techniques.md — on both surfaces: the
// README gallery (scripts/gallery.sh) and this site index. The authoritative
// derivation is scripts/catalog.sh; the deploy cannot run bash+Python
// (vercel.json pins the build to `npm ci` + `node build.mjs`), so this is a JS
// re-implementation of the same rule. A re-implementation is a drift risk —
// exactly the issue #55 problem the lineage port carries a cross-check for — so
// site/test/catalog.test.mjs runs BOTH this and scripts/catalog.sh over the
// same trees and fails on any disagreement about a design's group or the order.
//
// The grouping signal is minimal committed source, never a hand-grouped table
// (charter N1): a NUGGS module is derived from the nuggs-* name AND reaching
// the lib/nuggs-coupling.scad standard through its include closure (issue #517
// — a derivative inherits the coupling through its parent, and that inheritance
// counts; a nuggs-* name reaching the coupling nowhere is a collision, grouped
// by its declared category); every other design declares
// `category: <slug>` in designs/<name>/catalog.conf; the closed vocabulary and
// display order live in designs/categories.conf.

import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, join, sep } from "node:path";

function read(path) {
  try {
    return readFileSync(path, "utf8");
  } catch {
    return null;
  }
}

/** NUGGS is a group derived from the name, not declared (same rule as catalog.sh). */
export function isNuggs(name) {
  return name === "nuggs" || name.startsWith("nuggs-");
}

/**
 * The live include/use directive targets of a .scad file's text, one per line:
 * comment-stripped first (issue #509 / CodeRabbit), line-oriented always — a
 * directive and its <...> target must sit on one line to count. Mirrors
 * catalog.sh scad_directives (which also documents the comment state machine).
 */
function scadDirectives(scad) {
  // Strip // line comments and /* ... */ block comments before matching, so a
  // commented-out directive is not read as live. The strip is line-oriented and
  // newline-preserving — block-comment state is carried across lines but each
  // line stays a line — the exact state machine catalog.sh strip_scad_comments
  // runs, so the port and the bash authority can never disagree over a wrapped
  // or commented-out directive; catalog.test.mjs pins that parity.
  let inBlock = false;
  const out = [];
  for (const raw of scad.split("\n")) {
    let line = "";
    for (let i = 0; i < raw.length; ) {
      const two = raw.slice(i, i + 2);
      if (inBlock) {
        if (two === "*/") { inBlock = false; i += 2; } else { i += 1; }
        continue;
      }
      if (two === "//") break; // line comment: drop the rest of the line
      if (two === "/*") { inBlock = true; i += 2; continue; }
      line += raw[i]; i += 1;
    }
    for (const m of line.matchAll(/(?:include|use)\s*<([^>]+)>/g)) out.push(m[1]);
  }
  return out;
}

/**
 * Resolve one directive target against the file carrying it, the way the
 * scripts set OPENSCADPATH for OpenSCAD itself: the including file's directory
 * (the `../<parent>/<parent>.scad` derivative form, a coupon's bare
 * `include <entry.scad>`), then lib/, then the repo root
 * (`styles/<name>/style.scad`). Null when no candidate holds the file — an
 * unresolvable directive is a leaf of the walk, never an error. Mirrors
 * catalog.sh resolve_directive.
 */
function resolveDirective(target, from, repoRoot) {
  const candidates = [
    join(dirname(from), target),
    join(repoRoot, "lib", target),
    join(repoRoot, target),
  ];
  for (const c of candidates) {
    if (existsSync(c) && statSync(c).isFile()) return c;
  }
  return null;
}

/**
 * Does the design REACH the NUGGS coupling standard through its include
 * closure (issue #517)? The entry's own directives are level one; every
 * directive resolving to another FIRST-PARTY file (designs/, top-level
 * lib/*.scad, styles/) extends the closure transitively, so a derivative
 * inheriting the coupling through its parent is a NUGGS module. The coupling
 * itself is matched by name wherever the directive sits (the selftest trees
 * carry no lib/), vendored subtrees of lib/ and unresolvable targets are
 * leaves, and a visited set terminates cyclic includes. Mirrors
 * catalog.sh includes_coupling.
 */
function includesCoupling(designDir, name) {
  const entry = join(designDir, `${name}.scad`);
  const scad = read(entry);
  if (scad === null) return false;
  const repoRoot = join(designDir, "..", "..");
  // First-party is the CLAUDE.md set: anything under designs/ or styles/, and
  // a .scad DIRECTLY in lib/ (first-party libs occupy that single level;
  // vendored libraries live in subdirectories of lib/, so anything deeper is a
  // vendored leaf).
  const firstParty = (p) => {
    for (const d of ["designs", "styles"]) {
      if (p.startsWith(join(repoRoot, d) + sep)) return true;
    }
    const lib = join(repoRoot, "lib") + sep;
    if (p.startsWith(lib)) {
      const rel = p.slice(lib.length);
      return rel.endsWith(".scad") && !rel.includes(sep);
    }
    return false;
  };
  const queue = [entry];
  const seen = new Set();
  while (queue.length > 0) {
    const f = queue.shift();
    if (seen.has(f)) continue;
    seen.add(f);
    const text = read(f);
    if (text === null) continue;
    for (const target of scadDirectives(text)) {
      // The directive names the coupling: reached, at whatever depth.
      if (target.endsWith("nuggs-coupling.scad")) return true;
      const resolved = resolveDirective(target, f, repoRoot);
      if (resolved !== null && firstParty(resolved) && !seen.has(resolved)) {
        queue.push(resolved);
      }
    }
  }
  return false;
}

/**
 * A design's category slug: "nuggs" for a real NUGGS module (a `nuggs`/`nuggs-*`
 * name that ALSO reaches lib/nuggs-coupling.scad through its include closure),
 * else the `category:` key of designs/<name>/catalog.conf. A nuggs-*-named
 * design reaching the coupling nowhere in its closure is a name collision (e.g.
 * nuggs-yard), not a NUGGS module — it falls through to its declared category,
 * matching catalog.sh resolve_groups (both directions of the #374 cross-check).
 * Null when a non-NUGGS design declares none — the build keeps it visible
 * (groupDesigns' Other bucket) rather than dropping it, and the cross-check
 * test flags the divergence.
 *
 * `key: value` parsed the way site/lib/team.mjs parses it: trailing `#`
 * comments stripped, split on the first colon.
 */
export function categoryOf(designDir, name) {
  if (isNuggs(name) && includesCoupling(designDir, name)) return "nuggs";
  const raw = read(join(designDir, "catalog.conf"));
  if (raw === null) return null;
  for (const rawLine of raw.split("\n")) {
    const line = rawLine.split("#", 1)[0].trim();
    if (!line || !line.includes(":")) continue;
    const at = line.indexOf(":");
    if (line.slice(0, at).trim() !== "category") continue;
    return line.slice(at + 1).trim() || null;
  }
  return null;
}

/**
 * The closed vocabulary + display order from designs/categories.conf, as
 * [{slug, label, blurb}] in file order. Each line is "<slug> | <label>" or
 * "<slug> | <label> | <blurb>" (the optional blurb is the promise line shown
 * under a promise-bearing heading); `#` comments and blank lines ignored — the
 * same file scripts/catalog.sh reads. Split on the pipes explicitly so a blurb
 * never glues onto the label (the mirror of catalog.sh's load_vocab).
 */
export function readCategories(repoRoot) {
  const raw = read(join(repoRoot, "designs", "categories.conf"));
  if (raw === null) return [];
  const out = [];
  const seen = new Set();
  for (const rawLine of raw.split("\n")) {
    const line = rawLine.split("#", 1)[0].trim();
    if (!line) continue;
    // Match catalog.sh's load_vocab refusals: a non-blank record must be
    // "<slug> | <label>[ | <blurb>]" with a non-empty slug and label, and no
    // slug may repeat. The bash gate enforces this in CI, but the Vercel deploy
    // runs only `node build.mjs` (no bash), so the port must refuse the same
    // records itself — otherwise a malformed or duplicated categories.conf
    // would silently publish a broken or doubled group. (issue #374 cross-check)
    if (!line.includes("|")) {
      throw new Error(`categories.conf: '${line}' is not '<slug> | <label>[ | <blurb>]'`);
    }
    const parts = line.split("|");
    const slug = parts[0].replace(/\s+/g, ""); // catalog.sh strips all slug whitespace (tr -d)
    const label = (parts[1] || "").trim();
    const blurb = parts.slice(2).join("|").trim(); // keep any | inside a blurb
    if (!slug || !label) {
      throw new Error(`categories.conf: '${line}' has an empty slug or label`);
    }
    if (seen.has(slug)) {
      throw new Error(`categories.conf: duplicate category slug '${slug}'`);
    }
    seen.add(slug);
    out.push({ slug, label, blurb });
  }
  return out;
}

/**
 * Bucket the lineage-ordered designs into their groups, in vocabulary (display)
 * order, preserving within-group order. A derivative takes its ROOT ancestor's
 * group, so a group boundary never splits a parent from a nested child (the
 * designs array is already in lineage order — a root immediately followed by
 * its descendants — so tracking the last depth-0 group is enough). Mirrors
 * scripts/catalog.sh build_order.
 *
 * Returns [{slug, label, designs}] for the non-empty groups, empty groups
 * dropped. A design whose category is missing/unknown lands in a trailing
 * "Other" group rather than vanishing.
 */
export function groupDesigns(ordered, categories) {
  const OTHER = "__other__";
  const bySlug = new Map(
    categories.map((c) => [c.slug, { slug: c.slug, label: c.label, blurb: c.blurb || "", designs: [] }])
  );
  let rootGroup = null;
  for (const d of ordered) {
    if ((d.depth || 0) === 0) rootGroup = d.category || null;
    if (rootGroup && bySlug.has(rootGroup)) {
      bySlug.get(rootGroup).designs.push(d);
    } else {
      if (!bySlug.has(OTHER)) bySlug.set(OTHER, { slug: OTHER, label: "Other", designs: [] });
      bySlug.get(OTHER).designs.push(d);
    }
  }
  const out = categories.map((c) => bySlug.get(c.slug)).filter((g) => g && g.designs.length);
  const other = bySlug.get(OTHER);
  if (other && other.designs.length) out.push(other);
  return out;
}
