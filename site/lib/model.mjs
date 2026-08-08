// The design's browser-side model bundle: its source and the complete include
// closure the WASM runtime needs to render it, plus its Customizer parameters.
//
// One bundle serves two consumers. The configurator (site/assets/configurator.js)
// reads its `sections`/`asserts` to build controls; the 3D viewer
// (site/assets/viewer.js, issue #100) renders `entry`/`source`/`files` at
// default parameters and draws the result. Every design gets a bundle — a
// design with no tunable parameters still has geometry to view — so the builder
// never returns null the way the old configurator-only path did.
//
// Files are keyed by their repo-relative path; the browser recreates that layout
// under one root with OPENSCADPATH set to `lib:root` — the same search path
// every script in this repo exports. Mirroring rather than flattening keeps a
// nested reference (`BOSL2/std.scad`, `styles/<n>/style.scad`) resolvable if a
// design ever takes one.

import { readFileSync, realpathSync, statSync } from "node:fs";
import { isAbsolute, join, resolve as resolvePath, sep } from "node:path";

import { parseParameters, includeClosure } from "./scadparams.mjs";

export function buildModel(repoRoot, design) {
  const entry = `${design.relDir}/${design.name}.scad`;
  const source = readFileSync(join(repoRoot, entry), "utf8");
  const { sections, asserts } = parseParameters(source);

  // Same roots the scripts search: OPENSCADPATH="lib:repo-root", plus the
  // design's own directory for a sibling include.
  //
  // A resolved file's bytes are embedded verbatim into the publicly served
  // model.json, so the resolver must never read outside the repo (issue #120):
  // an absolute ref, or one whose `../` segments normalize past the root
  // (`include <../../../../etc/passwd>`), is refused rather than resolved.
  // Containment is checked against the *real* (symlink-resolved) path so a
  // symlink cannot smuggle the escape past the string check either. Legitimate
  // nested includes — `BOSL2/std.scad`, `styles/<n>/style.scad` — stay inside
  // the root and keep resolving.
  const root = realpathSync(repoRoot);
  const resolve = (ref) => {
    if (isAbsolute(ref)) return null;
    for (const rel of [join("lib", ref), join(design.relDir, ref), ref]) {
      const candidate = resolvePath(root, rel);
      let real;
      try {
        real = realpathSync(candidate);
        if (!statSync(real).isFile()) continue;
      } catch {
        continue; // does not exist — try the next root
      }
      if (real !== root && !real.startsWith(root + sep)) continue; // escapes the repo
      return {
        path: rel.split(sep).join("/"),
        contents: readFileSync(real, "utf8"),
      };
    }
    return null;
  };

  return {
    name: design.name,
    title: design.title,
    entry,
    source,
    files: includeClosure(source, resolve),
    sections,
    asserts,
  };
}

/** Whether this model exposes tunable parameters — i.e. gets a configurator. */
export function hasConfigurator(model) {
  return !!(model && model.sections && model.sections.length);
}
