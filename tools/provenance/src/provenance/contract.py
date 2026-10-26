"""Python validator for the closed contract ``site/lib/provenance-contract.json``.

One committed contract, two hand-rolled validators (this one and
``site/lib/provenance-contract.mjs``), no JSON Schema dependency in either
stack (docs/provenance.md §Contract). The type language is stated in the
contract's own ``typelang`` block; the rules this module must implement
exactly, because the Node validator implements the same ones:

* ``obj`` is CLOSED — a key not in ``fields`` (or ``optional_fields``) is an
  error; every ``fields`` key is required; ``null`` is accepted only where the
  type says ``"null": true``.
* ``open`` requires its ``fields`` and ignores extra keys (complete API job
  objects inside receipts).
* ``int`` rejects ``bool`` and any float (``True`` is not ``1`` here).
* ``str`` ``re`` is a FULL match (``re.fullmatch``); ``max`` bounds the
  length in Unicode code points (``len(s)``; the Node validator must use
  ``[...s].length``, not the UTF-16 ``s.length``, or an emoji-bearing
  title would validate differently in the two stacks).
* ``list`` ``unique`` compares canonical JSON; ``sorted`` means
  ``value == sorted(value)``.
* ``map`` keys full-match ``key``.
* ``ref`` resolves in ``types`` then ``shapes``; ``kindfields`` resolves
  ``field_sets[<the object's own "kind">]`` as a closed ``obj``.
* Errors are collected (never raise on the first) as ``"$.path: message"``
  strings in document order; :func:`check` raises :class:`ContractError`
  carrying all of them.

:func:`validate_tree` checks a whole data-ref tree: ``FORMAT`` bytes; the
guard files equal ``.github/data-branch-guard/*``; every ``receipts/`` path
agrees with its receipt's run id/attempt/date; every ``raw/`` and
``records/`` blob validates against its shape; ``site/bundle.json``'s
``views_sha256`` and ``content_sha256`` recompute.

Owner: H2. tests/test_contract.py must prove each rule with a negative
control, and that the Python and Node validators agree on a shared corpus
(``site/test/fixtures/provenance-bundle.json`` plus one extra-field negative).

**As built** (the details a second implementation needs to agree with):

* **Null.** ``"null": true`` on a node accepts ``None`` before anything else
  is checked. A ``ref`` without its own ``null`` still accepts ``None`` when
  the type it resolves to says ``"null": true`` (``types.user``).
* **Paths.** ``$`` is the value; an object field is ``.name``; a map entry is
  ``[<JSON-quoted key>]``; a list item is ``[<index>]``
  (``$.designs["sbc-case"].kinds[0]``).
* **Order.** Inside an object, errors follow the VALUE's key order (each key's
  own errors, or ``unexpected field``), then one ``missing field`` error per
  absent required field in contract order. Inside a list: ``too long``
  first, then each item, then ``not unique`` / ``not sorted`` /
  ``not homogeneous``. A value of the wrong JSON type gets one error and is
  not descended into.
* **Lists.** ``unique`` compares ``json.dumps(v, sort_keys=True,
  separators=(",", ":"), ensure_ascii=False)``; ``sorted`` is checked only on
  a homogeneous list (all ints — never a bool — or all strings; anything else
  is ``not homogeneous``) and compares ints numerically and strings by code
  point (Python ``<``).
* **enum** values are strings; ``int`` ``min``/``max`` and ``list``/``map``/
  ``str`` ``max`` are inclusive bounds.
* **kindfields** reads the sibling named by the node's ``by`` (default
  ``kind``); a missing or unknown kind is one error at the field's path.

**Trees** (:func:`validate_tree`). Every blob path must match the contract's
``trees.<ref>`` layout (:data:`EVIDENCE_LAYOUT` / :data:`DERIVED_LAYOUT`, a
test pins both tables to the contract); every JSON blob must be canonical
JSON (``canonical.dumps``) — for ``*.json.gz`` the DECOMPRESSED bytes, never
the gzip stream (the contract note); each document must sit at the path it
names (receipts: run id, attempt (``run_attempt or 1``) and the UTC date of
``run.created_at``; raw: number and revision, revision 1 the bare path,
``.r<K>`` only for K ≥ 2; records: ``records/<kind>/<identity>.json``, the
identity being the record's own ``pr``/``issue`` number, ``sha`` or ``tag``; views: ``views/<design>.json``);
raw revisions of each PR and brief are contiguous from 1. Guard files: both
refs must carry them; the DERIVED ref must carry main's current bytes, while
on the evidence ref (written once, at bootstrap) a difference from main is
drift — ``gitstore.guard_drift``'s warning, never an error here (docs
§The add-only guard, critique item 18). The bundle: ``views`` equals the
``views/*.json`` files (same names, same canonical bytes), each
``views_sha256[d] == canonical.content_sha256(views[d])``, ``contract`` is
this contract's version, and ``content_sha256 == canonical.content_sha256(
{"records": {path: sha256(bytes)}, "views_sha256": …, "extractor": …})``
over the tree's actual ``records/**`` blobs (bundle.py's formula).
"""

from __future__ import annotations

import gzip
import json
import os
import re
from typing import Any, Optional

from . import canonical
from .protocols import TreeReader

#: The contract file, relative to the repository root.
CONTRACT_RELPATH = os.path.join("site", "lib", "provenance-contract.json")
CONTRACT_VERSION = 1
CONTRACT_NAME = "print-bench-provenance-contract"

#: Recursion bound — the contract has no recursive type; a cycle is a contract defect.
_MAX_DEPTH = 64

_CACHE: dict[str, dict[str, Any]] = {}


class ContractError(ValueError):
    """A value failed validation; ``errors`` lists every failure."""

    def __init__(self, shape: str, errors: list[str]) -> None:
        super().__init__(f"{shape}: {len(errors)} contract error(s): " + "; ".join(errors[:5]))
        self.shape = shape
        self.errors = errors


def repo_root() -> str:
    """The repository root, from this file's location (tools/provenance/src/provenance/)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def load_contract(path: Optional[str] = None) -> dict[str, Any]:
    """Parse the contract JSON (default: :data:`CONTRACT_RELPATH` under :func:`repo_root`)."""
    full = os.path.abspath(path or os.path.join(repo_root(), CONTRACT_RELPATH))
    if full in _CACHE:
        return _CACHE[full]
    with open(full, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or data.get("contract") != CONTRACT_NAME:
        raise ValueError(f"{full}: not the {CONTRACT_NAME}")
    if data.get("version") != CONTRACT_VERSION:
        raise ValueError(f"{full}: contract version {data.get('version')!r}, this validator is "
                         f"version {CONTRACT_VERSION}")
    for section in ("types", "shapes", "field_sets"):
        if not isinstance(data.get(section), dict):
            raise ValueError(f"{full}: missing section {section!r}")
    _CACHE[full] = data
    return data


def _canonical_compact(value: Any) -> str:
    """The canonical JSON the ``unique`` rule compares (sorted keys at every depth, no whitespace)."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(value)


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "obj"
    return type(value).__name__


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _short(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= 80 else text[:77] + "..."


class _Validator:
    """One walk of one value against one contract (errors accumulate in ``self.errors``)."""

    def __init__(self, contract: dict[str, Any]) -> None:
        self.types = contract.get("types", {})
        self.shapes = contract.get("shapes", {})
        self.field_sets = contract.get("field_sets", {})
        self.errors: list[str] = []
        self._rx: dict[str, re.Pattern[str]] = {}

    def err(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def rx(self, pattern: str) -> re.Pattern[str]:
        compiled = self._rx.get(pattern)
        if compiled is None:
            compiled = self._rx[pattern] = re.compile(pattern)
        return compiled

    def resolve(self, name: str) -> Optional[dict[str, Any]]:
        if name in self.types:
            return self.types[name]
        return self.shapes.get(name)

    def node(self, t: dict[str, Any], x: Any, path: str, parent: Optional[dict[str, Any]] = None,
             depth: int = 0) -> None:
        if depth > _MAX_DEPTH:
            self.err(path, "contract recursion too deep")
            return
        if x is None and t.get("null") is True:
            return
        kind = t.get("t")
        if kind == "ref":
            target = self.resolve(t.get("to", ""))
            if target is None:
                self.err(path, f"contract names an unknown type {t.get('to')!r}")
                return
            self.node(target, x, path, parent, depth + 1)
        elif kind == "any":
            return
        elif kind == "str":
            self.string(t, x, path)
        elif kind == "int":
            self.integer(t, x, path)
        elif kind == "bool":
            if not isinstance(x, bool):
                self.err(path, f"want bool, got {_type_name(x)}")
        elif kind == "enum":
            allowed = t.get("of", ())
            if not isinstance(x, str) or x not in allowed:
                shown = allowed if len(allowed) <= 6 else f"the {len(allowed)} allowed values"
                self.err(path, f"{_short(x)} is not one of {shown}")
        elif kind == "list":
            self.listing(t, x, path, depth)
        elif kind in ("obj", "open"):
            self.obj(t.get("fields", {}), t.get("optional_fields", {}), x, path, depth,
                     closed=(kind == "obj"))
        elif kind == "map":
            self.mapping(t, x, path, depth)
        elif kind == "kindfields":
            by = t.get("by", "kind")
            sel = parent.get(by) if isinstance(parent, dict) else None
            fields = self.field_sets.get(sel) if isinstance(sel, str) else None
            if fields is None:
                self.err(path, f"no field set for {by} {_short(sel)}")
                return
            self.obj(fields, {}, x, path, depth, closed=True)
        else:
            self.err(path, f"contract uses an unknown type {kind!r}")

    def string(self, t: dict[str, Any], x: Any, path: str) -> None:
        if not isinstance(x, str):
            self.err(path, f"want str, got {_type_name(x)}")
            return
        if "max" in t and len(x) > t["max"]:
            self.err(path, f"longer than {t['max']} code points ({len(x)})")
        if "re" in t and self.rx(t["re"]).fullmatch(x) is None:
            self.err(path, f"{_short(x)} does not match {t['re'][:80]}")

    def integer(self, t: dict[str, Any], x: Any, path: str) -> None:
        if not _is_int(x):
            self.err(path, f"want int, got {_type_name(x)}")
            return
        if "min" in t and x < t["min"]:
            self.err(path, f"{x} < min {t['min']}")
        if "max" in t and x > t["max"]:
            self.err(path, f"{x} > max {t['max']}")

    def listing(self, t: dict[str, Any], x: Any, path: str, depth: int) -> None:
        if not isinstance(x, list):
            self.err(path, f"want list, got {_type_name(x)}")
            return
        if "max" in t and len(x) > t["max"]:
            self.err(path, f"more than {t['max']} items ({len(x)})")
        item = t.get("of", {"t": "any"})
        for i, value in enumerate(x):
            self.node(item, value, f"{path}[{i}]", None, depth + 1)
        if t.get("unique"):
            seen: set[str] = set()
            for value in x:
                key = _canonical_compact(value)
                if key in seen:
                    self.err(path, f"not unique (duplicate {_short(value)})")
                    break
                seen.add(key)
        if t.get("sorted") and x:
            if all(_is_int(v) for v in x) or all(isinstance(v, str) for v in x):
                if any(x[i + 1] < x[i] for i in range(len(x) - 1)):
                    self.err(path, "not sorted")
            else:
                self.err(path, "not homogeneous (a sorted list holds only ints or only strings)")

    def obj(self, fields: dict[str, Any], optional: dict[str, Any], x: Any, path: str, depth: int,
            *, closed: bool) -> None:
        if not isinstance(x, dict):
            self.err(path, f"want obj, got {_type_name(x)}")
            return
        for key, value in x.items():
            spec = fields.get(key, optional.get(key)) if isinstance(key, str) else None
            if spec is None:
                if closed:
                    self.err(path, f"unexpected field {_short(key)}")
                continue
            self.node(spec, value, f"{path}.{key}", x, depth + 1)
        for key in fields:
            if key not in x:
                self.err(path, f"missing field {key!r}")

    def mapping(self, t: dict[str, Any], x: Any, path: str, depth: int) -> None:
        if not isinstance(x, dict):
            self.err(path, f"want map, got {_type_name(x)}")
            return
        if "max" in t and len(x) > t["max"]:
            self.err(path, f"more than {t['max']} entries ({len(x)})")
        key_rx = self.rx(t.get("key", ".*"))
        item = t.get("of", {"t": "any"})
        for key, value in x.items():
            sub = f"{path}[{json.dumps(key, ensure_ascii=False)}]" if isinstance(key, str) else f"{path}[?]"
            if not isinstance(key, str) or key_rx.fullmatch(key) is None:
                self.err(sub, f"key does not match {t.get('key')}")
            self.node(item, value, sub, None, depth + 1)


def validate(shape: str, value: Any, contract: Optional[dict[str, Any]] = None) -> list[str]:
    """Every error of ``value`` against ``shapes[shape]`` (``[]`` = valid)."""
    c = contract if contract is not None else load_contract()
    spec = c.get("shapes", {}).get(shape)
    if spec is None:
        raise ValueError(f"unknown contract shape {shape!r}")
    v = _Validator(c)
    v.node(spec, value, "$")
    return v.errors


def check(shape: str, value: Any, contract: Optional[dict[str, Any]] = None) -> None:
    """:func:`validate`, raising :class:`ContractError` when anything fails."""
    errors = validate(shape, value, contract)
    if errors:
        raise ContractError(shape, errors)


# ---------------------------------------------------------------------------
# Whole-tree validation.

GUARD_SOURCES = {
    "vercel.json": os.path.join(".github", "data-branch-guard", "vercel.json"),
    "scripts/vercel-ignore-build.sh": os.path.join(".github", "data-branch-guard", "vercel-ignore-build.sh"),
}

_N = r"([1-9][0-9]*)"

#: ``trees.provenance`` (the contract's own spelling) -> (path regex, shape or None for a fixed file).
EVIDENCE_LAYOUT: dict[str, tuple[re.Pattern[str], Optional[str]]] = {
    "vercel.json": (re.compile(r"vercel\.json"), None),
    "scripts/vercel-ignore-build.sh": (re.compile(r"scripts/vercel-ignore-build\.sh"), None),
    "README.md": (re.compile(r"README\.md"), None),
    "FORMAT": (re.compile(r"FORMAT"), None),
    "state.json": (re.compile(r"state\.json"), "state@1"),
    "receipts/YYYY/MM/DD/<run_id>.a<attempt>.json.gz":
        (re.compile(r"receipts/[0-9]{4}/[0-9]{2}/[0-9]{2}/" + _N + r"\.a" + _N + r"\.json\.gz"), "receipt@1"),
    "raw/pr/<n>.json.gz": (re.compile(r"raw/pr/" + _N + r"\.json\.gz"), "raw-pr@1"),
    "raw/pr/<n>.r<K>.json.gz": (re.compile(r"raw/pr/" + _N + r"\.r" + _N + r"\.json\.gz"), "raw-pr@1"),
    "raw/brief/<n>.json.gz": (re.compile(r"raw/brief/" + _N + r"\.json\.gz"), "raw-brief@1"),
    "raw/brief/<n>.r<K>.json.gz": (re.compile(r"raw/brief/" + _N + r"\.r" + _N + r"\.json\.gz"), "raw-brief@1"),
    "raw/release/<tag>.json.gz": (re.compile(r"raw/release/([A-Za-z0-9._-]{1,100})\.json\.gz"), "raw-release@1"),
    "raw/snapshot/pr<N>/runs/<workflow>.json.gz":
        (re.compile(r"raw/snapshot/(pr[0-9]+)/runs/([a-z0-9][a-z0-9-]{0,63}\.yml)\.json\.gz"),
         "raw-snapshot-runs@1"),
    "raw/snapshot/pr<N>/statuses/<sha40>.json.gz":
        (re.compile(r"raw/snapshot/(pr[0-9]+)/statuses/([0-9a-f]{40})\.json\.gz"), "raw-snapshot-statuses@1"),
}

#: ``trees.provenance-site`` -> (path regex, shape or None for a fixed file).
DERIVED_LAYOUT: dict[str, tuple[re.Pattern[str], Optional[str]]] = {
    "vercel.json": (re.compile(r"vercel\.json"), None),
    "scripts/vercel-ignore-build.sh": (re.compile(r"scripts/vercel-ignore-build\.sh"), None),
    "FORMAT": (re.compile(r"FORMAT"), None),
    "records/pr/<n>.json": (re.compile(r"records/pr/" + _N + r"\.json"), "record@1:pr"),
    "records/brief/<n>.json": (re.compile(r"records/brief/" + _N + r"\.json"), "record@1:brief"),
    "records/commit/<sha40>.json": (re.compile(r"records/commit/([0-9a-f]{40})\.json"), "record@1:commit"),
    "records/release/<tag>.json": (re.compile(r"records/release/([A-Za-z0-9._-]{1,100})\.json"),
                                   "record@1:release"),
    "views/<design>.json": (re.compile(r"views/([a-z0-9][a-z0-9-]{0,63})\.json"), "view@1"),
    "site/bundle.json": (re.compile(r"site/bundle\.json"), "bundle@1"),
}

_REQUIRED = {
    "evidence": ("FORMAT", "README.md", "state.json", "vercel.json", "scripts/vercel-ignore-build.sh"),
    "derived": ("FORMAT", "site/bundle.json", "vercel.json", "scripts/vercel-ignore-build.sh"),
}


def _layout_entry(layout: dict[str, tuple[re.Pattern[str], Optional[str]]], path: str) -> Optional[str]:
    for template, (rx, _shape) in layout.items():
        if rx.fullmatch(path):
            return template
    return None


def _format_bytes(contract: dict[str, Any], kind: str) -> bytes:
    key = "evidence_FORMAT" if kind == "evidence" else "derived_FORMAT"
    return (contract.get("formats", {}).get(key, "") + "\n").encode("utf-8")


def _guard_bytes(name: str) -> Optional[bytes]:
    try:
        with open(os.path.join(repo_root(), GUARD_SOURCES[name]), "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _parse_json_blob(path: str, data: bytes, errors: list[str]) -> Any:
    """Decode one stored JSON blob (decompressing ``*.json.gz``); the decoded bytes must be canonical."""
    raw = data
    if path.endswith(".gz"):
        try:
            raw = gzip.decompress(data)
        except (OSError, EOFError, ValueError) as exc:
            errors.append(f"{path}: not a gzip stream ({exc})")
            return None
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        errors.append(f"{path}: not UTF-8 JSON ({exc})")
        return None
    try:
        canonical_bytes = canonical.dumps_bytes(doc)
    except (TypeError, ValueError) as exc:
        errors.append(f"{path}: not storable canonical JSON ({exc})")
        return doc
    if canonical_bytes != raw:
        errors.append(f"{path}: not canonical JSON (canonical.dumps)")
    return doc


def _expected_evidence_path(shape: str, doc: dict[str, Any]) -> str:
    """The path a valid evidence document must be stored at (KeyError/TypeError on a malformed one)."""
    if shape == "receipt@1":
        run = doc["run"]
        y, m, d = run["created_at"][:10].split("-")
        return f"receipts/{y}/{m}/{d}/{run['id']}.a{run.get('run_attempt') or 1}.json.gz"
    if shape in ("raw-pr@1", "raw-brief@1"):
        number = doc["pr"] if shape == "raw-pr@1" else doc["number"]
        unit = "pr" if shape == "raw-pr@1" else "brief"
        rev = doc["revision"]
        return f"raw/{unit}/{number}.json.gz" if rev == 1 else f"raw/{unit}/{number}.r{rev}.json.gz"
    if shape == "raw-release@1":
        return f"raw/release/{doc['tag']}.json.gz"
    if shape == "raw-snapshot-runs@1":
        return f"raw/snapshot/{doc['snapshot']}/runs/{doc['workflow']}.json.gz"
    if shape == "raw-snapshot-statuses@1":
        return f"raw/snapshot/{doc['snapshot']}/statuses/{doc['sha']}.json.gz"
    if shape == "state@1":
        return "state.json"
    raise KeyError(shape)


_RECORD_IDENTITY = {"pr": "pr", "brief": "issue", "commit": "sha", "release": "tag"}


def _expected_derived_path(shape: str, doc: dict[str, Any]) -> str:
    if shape.startswith("record@1:"):
        kind = doc["kind"]
        identity = _RECORD_IDENTITY[kind]
        key = str(doc[identity])
        return f"records/{kind}/{key}.json"
    if shape == "view@1":
        return f"views/{doc['design']}.json"
    if shape == "bundle@1":
        return "site/bundle.json"
    raise KeyError(shape)


def validate_tree(reader: TreeReader, kind: str, contract: Optional[dict[str, Any]] = None) -> list[str]:
    """Every error of one data-ref tree (``kind`` = ``evidence`` | ``derived``)."""
    if kind not in ("evidence", "derived"):
        raise ValueError(f"validate_tree: kind must be evidence or derived, got {kind!r}")
    c = contract if contract is not None else load_contract()
    layout = EVIDENCE_LAYOUT if kind == "evidence" else DERIVED_LAYOUT
    errors: list[str] = []
    paths = list(reader.paths(""))
    present = set(paths)
    for required in _REQUIRED[kind]:
        if required not in present:
            errors.append(f"{required}: missing (the {kind} tree must carry it)")
    revisions: dict[tuple[str, str], set[int]] = {}
    docs: dict[str, Any] = {}  # path -> document, only for documents that validated
    blobs: dict[str, bytes] = {}
    for path in paths:
        template = _layout_entry(layout, path)
        if template is None:
            errors.append(f"{path}: not a path of the contract's trees.{_ref_name(kind)} layout")
            continue
        data = reader.read(path)
        if data is None:
            errors.append(f"{path}: listed but unreadable")
            continue
        blobs[path] = data
        shape = layout[template][1]
        if shape is None:
            _check_fixed_file(path, data, kind, c, errors)
            continue
        doc = _parse_json_blob(path, data, errors)
        if doc is None:
            continue
        shape_errors = validate(shape, doc, c)
        errors.extend(f"{path}: {e}" for e in shape_errors)
        if shape_errors:
            continue
        docs[path] = doc
        try:
            want = (_expected_evidence_path if kind == "evidence" else _expected_derived_path)(shape, doc)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            errors.append(f"{path}: cannot derive the document's own path ({exc})")
            continue
        if want != path:
            errors.append(f"{path}: the document belongs at {want}")
        if shape in ("raw-pr@1", "raw-brief@1"):
            unit = "pr" if shape == "raw-pr@1" else "brief"
            number = str(doc["pr"] if unit == "pr" else doc["number"])
            revisions.setdefault((unit, number), set()).add(doc["revision"])
    for (unit, number), revs in sorted(revisions.items()):
        if revs != set(range(1, max(revs) + 1)):
            errors.append(f"raw/{unit}/{number}: revisions {sorted(revs)} are not contiguous from 1")
    if kind == "derived" and "site/bundle.json" in docs:
        _check_bundle(docs, blobs, c, errors)
    return errors


def _ref_name(kind: str) -> str:
    return "provenance" if kind == "evidence" else "provenance-site"


def _check_fixed_file(path: str, data: bytes, kind: str, contract: dict[str, Any], errors: list[str]) -> None:
    if path == "FORMAT":
        want = _format_bytes(contract, kind)
        if data != want:
            errors.append(f"FORMAT: {data[:60]!r} is not {want!r}")
    elif path in GUARD_SOURCES:
        if not data:
            errors.append(f"{path}: empty guard file")
        elif kind == "derived":
            main = _guard_bytes(path)
            if main is None:
                errors.append(f"{path}: main's {GUARD_SOURCES[path]} is unreadable")
            elif data != main:
                errors.append(f"{path}: differs from main's {GUARD_SOURCES[path]}")
    elif path == "README.md" and not data:
        errors.append("README.md: empty")


def _check_bundle(docs: dict[str, Any], blobs: dict[str, bytes], contract: dict[str, Any],
                  errors: list[str]) -> None:
    bundle = docs["site/bundle.json"]  # validated against bundle@1 by the caller
    if bundle["contract"] != contract.get("version"):
        errors.append(f"site/bundle.json: contract {bundle['contract']} is not the contract's version "
                      f"{contract.get('version')}")
    views = bundle["views"]
    if set(views) != set(bundle["views_sha256"]):
        errors.append("site/bundle.json: views_sha256 does not name exactly the bundle's views")
    for design, view in sorted(views.items()):
        digest = bundle["views_sha256"].get(design)
        if digest is not None and digest != canonical.content_sha256(view):
            errors.append(f"site/bundle.json: views_sha256[{json.dumps(design)}] does not recompute")
    files = {p[len("views/"):-len(".json")]: p for p in blobs if p.startswith("views/")}
    if set(files) != set(views):
        errors.append(f"site/bundle.json: views {sorted(views)} are not the tree's views/ files {sorted(files)}")
    for design in sorted(set(files) & set(views)):
        try:
            if blobs[files[design]] != canonical.dumps_bytes(views[design]):
                errors.append(f"{files[design]}: differs from the bundle's view")
        except (TypeError, ValueError):
            errors.append(f"site/bundle.json: view {design!r} is not storable canonical JSON")
    records = {p: canonical.sha256_hex(blobs[p]) for p in sorted(blobs) if p.startswith("records/")}
    want = canonical.content_sha256({"records": records, "views_sha256": bundle["views_sha256"],
                                     "extractor": bundle["extractor"]})
    if bundle["content_sha256"] != want:
        errors.append("site/bundle.json: content_sha256 does not recompute from the tree")
