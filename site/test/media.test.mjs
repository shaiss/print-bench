import { test } from "node:test";
import assert from "node:assert/strict";

import {
  missingMediaRefs,
  classifyMedia,
  designMedia,
  mediaLabel,
  stripReadmeMedia,
  AI_MOTION_DISCLOSURE,
  AI_STILL_DISCLOSURE,
} from "../lib/media.mjs";

test("classifyMedia knows the repo's filename conventions", () => {
  assert.deepEqual(classifyMedia("product-hero.png"), {
    kind: "Studio render",
    ai: false,
    motion: false,
  });
  assert.deepEqual(classifyMedia("turntable.gif"), {
    kind: "Turntable",
    ai: false,
    motion: true,
  });
  assert.deepEqual(classifyMedia("lifestyle-bench-calipers.png"), {
    kind: "AI-styled scene",
    ai: true,
    motion: false,
  });
  assert.deepEqual(classifyMedia("lifestyle-turntable.gif"), {
    kind: "AI motion clip",
    ai: true,
    motion: true,
  });
  assert.deepEqual(classifyMedia("product-still-hero.png"), {
    kind: "AI-styled scene",
    ai: true,
    motion: false,
  });
  assert.deepEqual(classifyMedia("contact-sheet.png"), {
    kind: "4-view contact sheet",
    ai: false,
    motion: false,
  });
  assert.equal(classifyMedia("cutaway.png").kind, "Detail");
  assert.equal(classifyMedia("shutter-slide.gif").kind, "Animation");
});

test("mediaLabel prettifies filenames and drops the lifestyle prefix", () => {
  assert.equal(mediaLabel("product-hero.png"), "Product Hero");
  assert.equal(mediaLabel("lifestyle-bench-calipers.png"), "Bench Calipers");
  assert.equal(mediaLabel("product-still-hero.png"), "Hero");
});

test("stripReadmeMedia lifts embeds and disclaimers, keeps everything else", () => {
  const md = [
    "# calibration-cube",
    "",
    "The pitch paragraph.",
    "",
    "![Product shot: the cube](previews/product-hero.png)",
    "",
    "![AI scene](previews/lifestyle-x.png)",
    "",
    "*AI-generated impression for general illustration only — geometry is approximate; see the STL.*",
    "",
    "## What you get",
    "",
    "- a cube",
  ].join("\n");
  const { markdown, alts } = stripReadmeMedia(md);
  assert.equal(alts.get("product-hero.png"), "Product shot: the cube");
  assert.equal(alts.get("lifestyle-x.png"), "AI scene");
  assert.ok(!markdown.includes("!["), "image embeds removed");
  assert.ok(!markdown.includes("AI-generated"), "disclaimer removed");
  assert.ok(markdown.includes("# calibration-cube"), "H1 kept");
  assert.ok(markdown.includes("The pitch paragraph."), "prose kept");
  assert.ok(markdown.includes("## What you get"), "sections kept");
});

test("stripReadmeMedia negative control: ordinary italics survive", () => {
  const md = "*This part is deliberately ugly.*\n\nBody.";
  const { markdown } = stripReadmeMedia(md);
  assert.ok(markdown.includes("deliberately ugly"));
});

test("designMedia orders hero first, contact sheet last, embeds in between", () => {
  const design = {
    title: "calibration-cube",
    previews: [
      "contact-sheet.png",
      "lifestyle-bench-calipers.png",
      "product-hero.png",
      "size-marker.png",
      "turntable.gif",
      "cameras.conf", // not media — must be filtered
    ],
  };
  const alts = new Map([
    ["product-hero.png", "hero alt"],
    ["lifestyle-bench-calipers.png", "scene alt"],
    ["size-marker.png", "marker alt"],
    ["turntable.gif", "turn alt"],
  ]);
  const media = designMedia(design, alts);
  assert.deepEqual(
    media.map((m) => m.file),
    [
      "product-hero.png",
      "lifestyle-bench-calipers.png",
      "size-marker.png",
      "turntable.gif",
      "contact-sheet.png",
    ]
  );
  assert.equal(media[0].alt, "hero alt");
});

test("designMedia carries the right disclosure per AI media", () => {
  const media = designMedia({
    title: "x",
    previews: ["lifestyle-a.png", "lifestyle-b.gif", "product-hero.png"],
  });
  const byFile = new Map(media.map((m) => [m.file, m]));
  assert.equal(byFile.get("lifestyle-a.png").disclosure, AI_STILL_DISCLOSURE);
  assert.equal(byFile.get("lifestyle-b.gif").disclosure, AI_MOTION_DISCLOSURE);
  assert.equal(byFile.get("product-hero.png").disclosure, null);
});

test("designMedia carries the AI still disclosure for a product still", () => {
  const media = designMedia({
    title: "x",
    previews: ["product-still-hero.png"],
  });
  assert.equal(media[0].ai, true);
  assert.equal(media[0].motion, false);
  assert.equal(media[0].disclosure, AI_STILL_DISCLOSURE);
});

test("designMedia falls back to a title-derived alt for unembedded previews", () => {
  const media = designMedia({ title: "Widget", previews: ["cutaway.png"] });
  assert.equal(media[0].alt, "Widget — Cutaway");
});

test("stripReadmeMedia keeps a disclaimer not preceded by an AI embed", () => {
  const md = [
    "![Studio shot](previews/product-hero.png)",
    "",
    "*AI-generated impression for general illustration only — geometry is approximate.*",
    "",
    "Body.",
  ].join("\n");
  const { markdown } = stripReadmeMedia(md);
  assert.ok(
    markdown.includes("AI-generated"),
    "a disclaimer after non-AI media is content, not a lifted disclosure"
  );
});

test("stripReadmeMedia strips the disclaimer only when an AI embed precedes it", () => {
  const md = [
    "![AI scene](previews/lifestyle-x.png)",
    "",
    "*AI-generated impression for general illustration only — geometry is approximate.*",
  ].join("\n");
  const { markdown, alts } = stripReadmeMedia(md);
  assert.ok(alts.has("lifestyle-x.png"));
  assert.ok(!markdown.includes("AI-generated"));
});

test("stripReadmeMedia strips the disclaimer after a product-still embed too", () => {
  const md = [
    "![AI product still](previews/product-still-hero.png)",
    "",
    "*AI-generated impression for general illustration only — geometry is approximate.*",
  ].join("\n");
  const { markdown, alts } = stripReadmeMedia(md);
  assert.ok(alts.has("product-still-hero.png"));
  assert.ok(!markdown.includes("AI-generated"));
});

test("stripReadmeMedia policy: an embed inside a table row stays in the prose", () => {
  const md = [
    "| Closed assembly | Cutaway |",
    "|---|---|",
    "| ![Assembly](previews/assembly.png) | ![Cutaway](previews/cutaway.png) |",
  ].join("\n");
  const { markdown, alts } = stripReadmeMedia(md);
  assert.equal(alts.size, 0, "in-context embeds are not lifted");
  assert.ok(markdown.includes("previews/assembly.png"), "table structure survives intact");
});

test("missingMediaRefs flags lifted embeds naming absent previews", () => {
  const { alts } = stripReadmeMedia("![x](previews/gone.png)\n\n![y](previews/here.png)");
  assert.deepEqual(missingMediaRefs(alts, ["here.png"]), ["gone.png"]);
  assert.deepEqual(missingMediaRefs(alts, ["here.png", "gone.png"]), []);
});
