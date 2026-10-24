// The Node provenance-contract validator, held rule by rule to the contract's
// typelang (and so to tools/provenance/src/provenance/contract.py, which
// implements the same text).
//
// The shared corpus is site/test/fixtures/provenance-bundle.json — rebuilt
// byte for byte from the harvester's synthetic records by
// tools/provenance/tests/test_bundle.py — which both validators must accept,
// and must both reject once one field is added. The cases below are the ones
// where a JavaScript validator written the obvious way would silently disagree
// with Python: an astral character in a code-point-sorted list (the default
// UTF-16 sort orders it before U+FF5E), objects that differ only in key order
// in a `unique` list (plain JSON.stringify keeps insertion order), a float
// (JSON.parse cannot tell 1.0 from 1, so the corpus uses 1.5), string `max`
// in code points, and Python's `.` (it refuses only "\n").
//
// No dependency: this file runs with `node --test` even without
// site/node_modules.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  canonicalString,
  compareCodePoints,
  fullMatcher,
  loadContract,
  validate,
} from "../lib/provenance-contract.mjs";

const BUNDLE_URL = new URL("./fixtures/provenance-bundle.json", import.meta.url);
const bundle = () => JSON.parse(readFileSync(BUNDLE_URL, "utf8"));
const contract = loadContract();

/** A minimal contract around one shape, for the rules no bundle field exercises. */
function tiny(shape, extra = {}) {
  return { types: {}, field_sets: {}, shapes: { t: shape }, ...extra };
}

test("the fixture bundle is accepted", () => {
  assert.deepEqual(validate("bundle@1", bundle()), []);
});

test("one extra field anywhere is rejected (closed objects)", () => {
  const top = bundle();
  top.extra = 1;
  assert.ok(validate("bundle@1", top).some((e) => e.startsWith("$: extra keys")));

  const deep = bundle();
  deep.views["alpha-clip"].events[0].fields.extra = true;
  const errs = validate("bundle@1", deep);
  assert.ok(errs.length === 1 && errs[0].includes(".fields: extra keys"), errs.join("\n"));

  const view = bundle();
  view.views["gamma-stand"].main_sha = "0".repeat(40); // critique 6: a view carries no main_sha
  assert.ok(validate("bundle@1", view).length > 0);
});

test("a missing required field is rejected, an optional one is not required", () => {
  const b = bundle();
  delete b.views_sha256;
  assert.ok(validate("bundle@1", b).some((e) => e === "$.views_sha256: missing"));
  const shape = { t: "obj", fields: { a: { t: "int" } }, optional_fields: { b: { t: "int" } } };
  assert.deepEqual(validate("t", { a: 1 }, tiny(shape)), []);
  assert.deepEqual(validate("t", { a: 1, b: 2 }, tiny(shape)), []);
  assert.equal(validate("t", { a: 1, b: "x" }, tiny(shape)).length, 1);
});

test("a bad enum value is rejected", () => {
  const b = bundle();
  b.views["alpha-clip"].events[0].trust = "trusted-by-vibes";
  assert.equal(validate("bundle@1", b).length, 1);
  const kind = bundle();
  kind.views["alpha-clip"].events[0].kind = "pr.reopened"; // also has no field set
  assert.ok(validate("bundle@1", kind).length >= 1);
});

test("a float is rejected where the contract says int; a boolean is not an int", () => {
  const b = bundle();
  b.views["alpha-clip"].counts.events = 1.5;
  assert.equal(validate("bundle@1", b).length, 1);
  const run = bundle();
  run.producer_run = true;
  assert.equal(validate("bundle@1", run).length, 1);
  const shape = { t: "int", min: 1, max: 3 };
  assert.deepEqual(validate("t", 3, tiny(shape)), []);
  assert.equal(validate("t", 0, tiny(shape)).length, 1);
  assert.equal(validate("t", 4, tiny(shape)).length, 1);
  assert.equal(validate("t", "1", tiny(shape)).length, 1);
});

test("null only where the type allows it, including through a ref", () => {
  const b = bundle();
  b.views["alpha-clip"].events[0].pr = null; // event.pr is nullable
  assert.deepEqual(validate("bundle@1", b), []);
  const notNull = bundle();
  notNull.views["alpha-clip"].events[0].ts = null; // event.ts is not
  assert.equal(validate("bundle@1", notNull).length, 1);
  const c = tiny({ t: "ref", to: "u" }, { types: { u: { t: "str", null: true } } });
  assert.deepEqual(validate("t", null, c), []); // the TARGET says null
});

test("patterns full-match: a trailing newline or a 41st character fails", () => {
  const ok = "a".repeat(40);
  for (const bad of [ok + "\n", ok + "a", "A".repeat(40), " " + ok]) {
    const b = bundle();
    b.main_sha = bad;
    assert.equal(validate("bundle@1", b).length, 1, JSON.stringify(bad));
  }
});

test("sorted compares strings by code point, not UTF-16 (an astral character)", () => {
  // U+FF5E < U+1F600 by code point; by UTF-16 code unit 0xD83D < 0xFF5E.
  const high = "～";
  const astral = "\u{1F600}";
  assert.ok(compareCodePoints(high, astral) < 0);
  assert.ok([high, astral].sort()[0] === astral, "the default sort disagrees — the trap");
  const brief = {
    format: "record@1", extractor: "provenance-extract 1", incomplete: [], events: [],
    kind: "brief", key: "1", issue: 1, state: "open", state_reason: null,
    created_at: "2026-01-01T00:00:00Z", closed_at: null, labels: [high, astral],
    design_name: null, prs: [],
    evidence: { raw: null, raw_sha256: null, revision: null, receipts: [], source: "git" },
  };
  assert.deepEqual(validate("record@1:brief", brief), []);
  assert.equal(validate("record@1:brief", { ...brief, labels: [astral, high] }).length, 1);
  // ints sort numerically, not as strings
  assert.deepEqual(validate("record@1:brief", { ...brief, prs: [9, 10] }), []);
  assert.equal(validate("record@1:brief", { ...brief, prs: [10, 9] }).length, 1);
  // a sorted list is homogeneous
  const mixed = tiny({ t: "list", of: { t: "any" }, sorted: true });
  assert.equal(validate("t", [1, "a"], mixed).length, 1);
});

test("unique compares canonical JSON: key order does not make two objects different", () => {
  const shape = {
    t: "list", unique: true,
    of: { t: "obj", fields: { a: { t: "int" }, b: { t: "list", of: { t: "any" } } } },
  };
  const c = tiny(shape);
  const one = { a: 1, b: [{ x: 1, y: 2 }] };
  const reordered = { b: [{ y: 2, x: 1 }], a: 1 };
  assert.notEqual(JSON.stringify(one), JSON.stringify(reordered), "plain stringify differs — the trap");
  assert.equal(canonicalString(one), canonicalString(reordered));
  assert.equal(validate("t", [one, reordered], c).length, 1);
  assert.deepEqual(validate("t", [one, { a: 2, b: [] }], c), []);
  // the contract's own unique lists: a duplicated PR in a view
  const b = bundle();
  b.views["beta-hinge"].prs = [511, 511];
  assert.ok(validate("bundle@1", b).some((e) => e.includes("duplicate")));
});

test("string max counts code points, never UTF-16 code units", () => {
  const shape = tiny({ t: "str", max: 3 });
  assert.deepEqual(validate("t", "\u{1F600}\u{1F600}\u{1F600}", shape), []); // 6 code units
  assert.equal(validate("t", "abcd", shape).length, 1);
  const pattern = tiny({ t: "map", key: ".{1,3}", of: { t: "int" } });
  assert.deepEqual(validate("t", { "\u{1F600}\u{1F600}\u{1F600}": 1 }, pattern), []);
  assert.equal(validate("t", { "\u{1F600}\u{1F600}\u{1F600}\u{1F600}": 1 }, pattern).length, 1);
});

test("`.` is Python's: everything but a newline", () => {
  const dot = fullMatcher(".{1,5}");
  assert.ok(dot.test("a\rb"));
  assert.ok(dot.test("a b"));
  assert.ok(!dot.test("a\nb"));
  assert.ok(fullMatcher("[.]").test("."));
  assert.ok(!fullMatcher("[.]").test("x")); // a dot in a class stays literal
  assert.ok(fullMatcher("a\\.b").test("a.b"));
  assert.ok(!fullMatcher("a\\.b").test("axb")); // an escaped dot stays literal
});

test("maps: keys full-match, values typed; kindfields follows the sibling kind", () => {
  const b = bundle();
  b.views["Not A Design"] = b.views["gamma-stand"];
  assert.ok(validate("bundle@1", b).some((e) => e.includes("key does not match")));
  const swapped = bundle();
  const ev = swapped.views["alpha-clip"].events.find((e) => e.kind === "review.signoff");
  ev.fields = { designs: [], act_now: 0, queue: 0, decline: 0, no_action: 0, rows: 0,
    completion_marker: false, edited: false }; // triage fields on a sign-off
  assert.ok(validate("bundle@1", swapped).length > 0);
  for (const kind of contract.enums.kind) assert.ok(Object.hasOwn(contract.field_sets, kind), kind);
});

test("an unknown shape is an error, not a pass", () => {
  assert.deepEqual(validate("nope@1", {}), ['$: unknown shape "nope@1"']);
});

test("every contract pattern compiles", () => {
  const seen = [];
  (function walk(x) {
    if (Array.isArray(x)) x.forEach(walk);
    else if (x && typeof x === "object") {
      for (const [k, v] of Object.entries(x)) {
        if ((k === "re" || k === "key") && typeof v === "string") seen.push(v);
        walk(v);
      }
    }
  })(contract);
  assert.ok(seen.length > 20);
  for (const p of seen) assert.doesNotThrow(() => fullMatcher(p), p);
});
