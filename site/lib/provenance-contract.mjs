// The Node half of the provenance contract: a hand-rolled validator for the
// closed shapes in site/lib/provenance-contract.json.
//
// One committed contract, two validators — this one and
// tools/provenance/src/provenance/contract.py — and no JSON Schema
// dependency in either stack (docs/provenance.md §Records and events). The
// harvester writes the provenance-site bundle in Python; the site (P3) reads
// it here. A rule implemented differently in the two stacks would let a
// bundle the harvester accepts be refused at deploy, or worse, accepted here
// with a meaning Python never checked — so every rule below is the
// contract's own `typelang` text, held to the Python validator by
// tools/provenance/tests/test_bundle.py (both must accept the fixture bundle
// and both must reject it with one extra field) and pinned rule by rule by
// site/test/provenance-contract.test.mjs.
//
// The rules, and where JS needs care to agree with Python:
//
// * `obj` is CLOSED: every `fields` key required, any `optional_fields` key
//   allowed, any other key an error. `open` requires its `fields` and ignores
//   the rest. Keys are read as OWN properties only (`Object.hasOwn`), so a
//   JSON "__proto__" key is just a key.
// * `null: true` on any type also accepts null; a `ref` accepts null when it
//   or its target says so.
// * `int` = a number with `Number.isInteger` (never a boolean). JSON.parse
//   cannot tell 1.0 from 1, so Python additionally rejects a 1.0 this cannot
//   see; the shared corpus uses 1.5 for its float negative. A consumer that
//   must refuse 1.0 verifies the canonical bytes of the file it read (the
//   contract's typelang `int`; canonical JSON never emits a float).
// * `str` `re` FULL-matches: `new RegExp('^(?:' + p + ')$', 'u')`. The `u`
//   flag makes a quantifier count code points as Python does, and every
//   unescaped `.` outside a class is rewritten to `[^\n]` — Python's `.`
//   (no DOTALL) refuses only "\n", JS's also refuses "\r", U+2028, U+2029.
//   `max` counts Unicode CODE POINTS (`[...s].length`), never `s.length`.
// * `list` `unique`: no two elements with the same canonical JSON — keys
//   sorted (by code point) at every depth — never plain JSON.stringify, whose
//   key order is insertion order. `sorted`: ascending, ints numerically,
//   strings code point by code point (never the default UTF-16 sort or
//   localeCompare, which order an astral character before U+E000–U+FFFF); a
//   sorted list must be homogeneous.
// * `map` keys full-match `key`; `kindfields` is the closed field set
//   `field_sets[<the sibling "kind">]`; `ref` resolves in `types`, then
//   `shapes`; `any` accepts anything.
//
// Errors are collected, never thrown on the first, as "$.path: message"
// strings (`$.a.b[3]`, map entries `$.views["name"]`). No dependency; ESM.

import { readFileSync } from "node:fs";

const CONTRACT_URL = new URL("./provenance-contract.json", import.meta.url);
let cached = null;

/** Parse the contract (default: the provenance-contract.json beside this module). */
export function loadContract(path) {
  if (path === undefined) {
    if (cached === null) cached = JSON.parse(readFileSync(CONTRACT_URL, "utf8"));
    return cached;
  }
  return JSON.parse(readFileSync(path, "utf8"));
}

const hasOwn = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
const isPlainObject = (x) => x !== null && typeof x === "object" && !Array.isArray(x);

/** Compare two strings code point by code point (Python `<` on str). */
export function compareCodePoints(a, b) {
  const ca = [...a];
  const cb = [...b];
  const n = Math.min(ca.length, cb.length);
  for (let i = 0; i < n; i += 1) {
    const x = ca[i].codePointAt(0);
    const y = cb[i].codePointAt(0);
    if (x !== y) return x < y ? -1 : 1;
  }
  return ca.length === cb.length ? 0 : ca.length < cb.length ? -1 : 1;
}

/** Canonical JSON for uniqueness: keys sorted by code point at every depth, no whitespace. */
export function canonicalString(value) {
  if (Array.isArray(value)) return "[" + value.map(canonicalString).join(",") + "]";
  if (isPlainObject(value)) {
    const keys = Object.keys(value).sort(compareCodePoints);
    return "{" + keys.map((k) => JSON.stringify(k) + ":" + canonicalString(value[k])).join(",") + "}";
  }
  return JSON.stringify(value);
}

/** Rewrite every unescaped `.` outside a character class to `[^\n]` (Python's `.`). */
function pythonDots(pattern) {
  let out = "";
  let inClass = false;
  for (let i = 0; i < pattern.length; i += 1) {
    const ch = pattern[i];
    if (ch === "\\") {
      out += ch + (pattern[i + 1] ?? "");
      i += 1;
    } else if (inClass) {
      if (ch === "]") inClass = false;
      out += ch;
    } else if (ch === "[") {
      inClass = true;
      out += ch;
    } else {
      out += ch === "." ? "[^\\n]" : ch;
    }
  }
  return out;
}

const regexCache = new Map();
/** The full-match RegExp for a contract pattern (cached). */
export function fullMatcher(pattern) {
  let re = regexCache.get(pattern);
  if (re === undefined) {
    re = new RegExp("^(?:" + pythonDots(pattern) + ")$", "u");
    regexCache.set(pattern, re);
  }
  return re;
}

function describe(x) {
  if (x === null) return "null";
  if (Array.isArray(x)) return "list";
  if (typeof x === "number") return Number.isInteger(x) ? "int" : "float";
  if (typeof x === "object") return "obj";
  return typeof x;
}

function short(x) {
  const s = JSON.stringify(x);
  return s === undefined ? String(x) : s.length > 80 ? s.slice(0, 77) + "..." : s;
}

function resolve(contract, name) {
  if (hasOwn(contract.types ?? {}, name)) return contract.types[name];
  if (hasOwn(contract.shapes ?? {}, name)) return contract.shapes[name];
  return null;
}

function check(contract, t, x, path, errs) {
  if (x === null && t.null === true) return;
  switch (t.t) {
    case "ref": {
      const target = resolve(contract, t.to);
      if (target === null) {
        errs.push(`${path}: unknown type ${short(t.to)}`);
        return;
      }
      check(contract, target, x, path, errs);
      return;
    }
    case "any":
      return;
    case "str": {
      if (typeof x !== "string") {
        errs.push(`${path}: want str, got ${describe(x)}`);
        return;
      }
      if (t.re !== undefined && !fullMatcher(t.re).test(x)) {
        errs.push(`${path}: ${short(x)} does not match the pattern`);
      }
      if (t.max !== undefined && [...x].length > t.max) {
        errs.push(`${path}: longer than ${t.max} code points`);
      }
      return;
    }
    case "int": {
      if (typeof x !== "number" || !Number.isInteger(x)) {
        errs.push(`${path}: want int, got ${describe(x)}`);
        return;
      }
      if (t.min !== undefined && x < t.min) errs.push(`${path}: ${x} < min ${t.min}`);
      if (t.max !== undefined && x > t.max) errs.push(`${path}: ${x} > max ${t.max}`);
      return;
    }
    case "bool":
      if (typeof x !== "boolean") errs.push(`${path}: want bool, got ${describe(x)}`);
      return;
    case "enum":
      if (typeof x !== "string" || !t.of.includes(x)) errs.push(`${path}: ${short(x)} not in enum`);
      return;
    case "list":
      checkList(contract, t, x, path, errs);
      return;
    case "obj":
    case "open":
      checkObject(contract, t, x, path, errs);
      return;
    case "map": {
      if (!isPlainObject(x)) {
        errs.push(`${path}: want map, got ${describe(x)}`);
        return;
      }
      const keys = Object.keys(x);
      if (t.max !== undefined && keys.length > t.max) errs.push(`${path}: more than ${t.max} entries`);
      for (const key of keys) {
        const sub = `${path}[${JSON.stringify(key)}]`;
        if (!fullMatcher(t.key).test(key)) errs.push(`${sub}: key does not match the pattern`);
        check(contract, t.of, x[key], sub, errs);
      }
      return;
    }
    default:
      errs.push(`${path}: unknown contract type ${short(t.t)}`);
  }
}

function checkList(contract, t, x, path, errs) {
  if (!Array.isArray(x)) {
    errs.push(`${path}: want list, got ${describe(x)}`);
    return;
  }
  if (t.max !== undefined && x.length > t.max) errs.push(`${path}: more than ${t.max} items`);
  x.forEach((item, i) => check(contract, t.of, item, `${path}[${i}]`, errs));
  if (t.unique === true) {
    const seen = new Set();
    for (const item of x) {
      const key = canonicalString(item);
      if (seen.has(key)) {
        errs.push(`${path}: duplicate element ${short(item)}`);
        break;
      }
      seen.add(key);
    }
  }
  if (t.sorted === true && x.length > 1) {
    const allInts = x.every((v) => typeof v === "number" && Number.isInteger(v));
    const allStrings = x.every((v) => typeof v === "string");
    if (!allInts && !allStrings) {
      errs.push(`${path}: a sorted list must hold only ints or only strings`);
      return;
    }
    for (let i = 1; i < x.length; i += 1) {
      const order = allInts ? Math.sign(x[i - 1] - x[i]) : compareCodePoints(x[i - 1], x[i]);
      if (order > 0) {
        errs.push(`${path}: not sorted at [${i}]`);
        break;
      }
    }
  }
}

function checkObject(contract, t, x, path, errs) {
  if (!isPlainObject(x)) {
    errs.push(`${path}: want obj, got ${describe(x)}`);
    return;
  }
  const fields = t.fields ?? {};
  const optional = t.optional_fields ?? {};
  for (const [name, ft] of Object.entries(fields)) {
    const sub = `${path}.${name}`;
    if (!hasOwn(x, name)) {
      errs.push(`${sub}: missing`);
      continue;
    }
    checkField(contract, ft, x, name, sub, errs);
  }
  for (const [name, ft] of Object.entries(optional)) {
    if (hasOwn(x, name)) checkField(contract, ft, x, name, `${path}.${name}`, errs);
  }
  if (t.t === "obj") {
    const extra = Object.keys(x).filter((k) => !hasOwn(fields, k) && !hasOwn(optional, k));
    if (extra.length) errs.push(`${path}: extra keys ${short(extra.sort(compareCodePoints))}`);
  }
}

function checkField(contract, ft, parent, name, path, errs) {
  if (ft.t !== "kindfields") {
    check(contract, ft, parent[name], path, errs);
    return;
  }
  const kind = parent[ft.by ?? "kind"];
  const sets = contract.field_sets ?? {};
  if (typeof kind !== "string" || !hasOwn(sets, kind)) {
    errs.push(`${path}: no field set for kind ${short(kind)}`);
    return;
  }
  check(contract, { t: "obj", fields: sets[kind] }, parent[name], path, errs);
}

/**
 * Every error of `value` against `shapes[shape]` ([] = valid). `contract`
 * defaults to the committed provenance-contract.json (loadContract()).
 */
export function validate(shape, value, contract = loadContract()) {
  if (!hasOwn(contract.shapes ?? {}, shape)) return [`$: unknown shape ${short(shape)}`];
  const errs = [];
  check(contract, contract.shapes[shape], value, "$", errs);
  return errs;
}
