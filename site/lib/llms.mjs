// The AI-native serving layer (llms.txt + raw markdown).
//
// Every page this site publishes is generated from a committed markdown
// source. This module makes that source machine-readable on the served site
// itself, following the llms.txt convention (https://llmstxt.org/):
//
//   /llms.txt        — a root index an LLM can read first: what this site is,
//                      and where every markdown source is served
//   /llms-full.txt   — the platform docs (contributing + architecture)
//                      concatenated into one file, for single-fetch consumers
//   /docs/**.md      — the contributor and architecture docs, served verbatim
//   /designs/<n>/README.md, /styles/<n>/STYLE.md — the markdown source of
//                      each rendered product/style page, served beside it
//
// Same rules as the rest of the build: everything served traces to a
// committed file (the docs are copied verbatim, the index is derived from
// their own titles and first paragraphs — nothing here invents content), and
// a local reference that does not resolve fails the build rather than
// shipping a dead link. Docs are served VERBATIM, not rendered, so their
// relative links are checked against the repo tree — the place they really
// point at — not against the served output.

import { readdirSync, readFileSync, existsSync } from "node:fs";
import { dirname, join, normalize, sep } from "node:path";

import { title } from "./content.mjs";

// The doc trees served as raw markdown. Order matters: it is the order the
// llms.txt index presents them in, contributor docs first.
export const DOC_DIRS = ["docs/contributing", "docs/architecture"];

/**
 * The doc's one-line summary for the index: the first sentence of the first
 * prose paragraph after the H1, with markdown link/emphasis syntax reduced to
 * plain text (an index annotation is not a place for relative links).
 */
export function docSummary(markdown) {
  const para = [];
  for (const raw of markdown.split("\n")) {
    const line = raw.trim();
    // Before the paragraph starts, skip anything structural: headings,
    // tables, quotes, lists, standalone images, badge lines ([![...) and
    // reference definitions ([x]: ...) — but a paragraph that OPENS with an
    // inline link is prose. Once inside the paragraph, a line opening with a
    // link or image is a continuation; only genuinely structural lines (or a
    // blank) end it.
    const structural = para.length
      ? /^[#|<>-]/
      : /^([#!|<>-]|\[!\[|\[[^\]]*\]:)/;
    if (!line || structural.test(line)) {
      if (para.length) break;
      continue;
    }
    para.push(line);
  }
  let text = para.join(" ");
  text = text.replace(/!\[[^\]]*\]\([^)]*\)/g, ""); // images: drop
  text = text.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1"); // links: keep label
  text = text.replace(/\*\*?/g, "").replace(/\s+/g, " ").trim();
  const sentence = text.match(/^(.*?[.!?])(?=\s|$)/);
  return sentence ? sentence[1] : text;
}

/**
 * Local markdown references in a doc that do not resolve in the repo tree.
 * External URLs, mailto: and pure #fragment links are out of scope; a
 * root-relative path resolves against the repo root, anything else against
 * the doc's own directory. Scope: inline links/images only (the docs' house
 * style), outside fenced code blocks — a fence may quote link syntax as an
 * example without it being a reference.
 */
export function localRefProblems(relPath, markdown, repoRoot) {
  const problems = [];
  const prose = markdown.replace(/^```[\s\S]*?^```/gm, "");
  const linkRe = /!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g;
  for (const m of prose.matchAll(linkRe)) {
    let target = m[1];
    if (/^[a-z][a-z0-9+.-]*:/i.test(target)) continue; // http:, https:, mailto:
    if (target.startsWith("#")) continue;
    target = target.split("#")[0];
    if (!target) continue;
    const abs = target.startsWith("/")
      ? join(repoRoot, target)
      : join(repoRoot, dirname(relPath), target);
    if (!normalize(abs).startsWith(normalize(repoRoot) + sep)) {
      problems.push(`${relPath}: link escapes the repo: ${m[1]}`);
      continue;
    }
    if (!existsSync(abs)) {
      problems.push(`${relPath}: broken local reference: ${m[1]}`);
    }
  }
  return problems;
}

/**
 * The docs served verbatim: every .md under DOC_DIRS, each dir's README.md
 * first (it is that set's index), then alphabetical. Reports a doc with no
 * H1 or with a broken local reference through onError, the same accumulator
 * discipline as every other structured source in the build.
 */
export function readServableDocs(repoRoot, { onError = () => {} } = {}) {
  const out = [];
  for (const relDir of DOC_DIRS) {
    const dir = join(repoRoot, relDir);
    if (!existsSync(dir)) {
      onError(`${relDir}/ does not exist — the llms.txt index expects it`);
      continue;
    }
    const files = readdirSync(dir)
      .filter((f) => f.endsWith(".md"))
      .sort((a, b) => {
        if (a === "README.md") return -1;
        if (b === "README.md") return 1;
        // Codepoint order, not localeCompare: llms.txt's bytes are part of
        // the deterministic build, and locale collation varies per machine.
        return a < b ? -1 : a > b ? 1 : 0;
      });
    for (const f of files) {
      const relPath = `${relDir}/${f}`;
      const text = readFileSync(join(dir, f), "utf8");
      const docTitle = title(text);
      if (!docTitle) onError(`${relPath}: has no H1 title for the llms.txt index`);
      for (const p of localRefProblems(relPath, text, repoRoot)) onError(p);
      out.push({
        relPath,
        title: docTitle || f,
        summary: docSummary(text),
        text,
      });
    }
  }
  return out;
}

const entry = (href, label, summary) =>
  `- [${label}](${href})${summary ? `: ${summary}` : ""}`;

/**
 * The /llms.txt body (https://llmstxt.org/): H1, blockquote summary, then
 * one linked section per markdown source the site serves. Paths are
 * root-relative so the file is host-agnostic.
 */
export function llmsTxt({ docs, designs, styles, repoUrl }) {
  const section = (relDir) =>
    docs
      .filter((d) => d.relPath.startsWith(`${relDir}/`))
      .map((d) => entry(`/${d.relPath}`, d.title, d.summary));

  const lines = [
    "# print-bench",
    "",
    "> Co-designed, parametric 3D-printable designs in OpenSCAD — plus the",
    "> platform that gates them: render/printability/slice CI, drift-checked",
    "> docs, and a human-gated autonomy loop. Every page on this site is",
    "> generated from a committed markdown source; this file indexes where",
    "> each source is served.",
    "",
    "## Contributing (the platform)",
    "",
    ...section("docs/contributing"),
    "",
    "## Architecture",
    "",
    ...section("docs/architecture"),
    "",
    "## Designs (product pages)",
    "",
    ...designs.map((d) =>
      entry(`/${d.relDir}/README.md`, d.title, d.pitch)
    ),
  ];
  if (styles.length) {
    lines.push("", "## Styles", "");
    for (const s of styles) {
      lines.push(entry(`/${s.relDir}/STYLE.md`, s.title, s.summary));
    }
  }
  lines.push(
    "",
    "## Optional",
    "",
    entry("/llms-full.txt", "llms-full.txt", "the platform docs above, concatenated into one file"),
    entry(repoUrl, "Source repository", "every file this site is generated from"),
    ""
  );
  return lines.join("\n");
}

/** The platform docs concatenated, separated by their served paths. */
export function llmsFullTxt(docs) {
  return docs
    .map((d) => `<!-- source: /${d.relPath} -->\n\n${d.text.trimEnd()}\n`)
    .join("\n---\n\n");
}
