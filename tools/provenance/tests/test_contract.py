"""contract — the hand-rolled Python validator (one negative control per typelang rule).

Owner: H2. Each test's docstring is its acceptance criterion (docs/provenance.md,
final plan P0/P1a–e). The typelang rules are proven on a small synthetic
contract (``MINI``) so each one can be isolated; the real contract is proven
on every committed fixture and on whole synthetic data-ref trees.
"""

from __future__ import annotations

import copy
import gzip
import json
import shutil
import subprocess

import pytest

from conftest import CONTRACT, FIXTURES, GUARD_DIR, REPO, contract, raw_pr, receipt_paths
from fakes import FakeTreeReader
from provenance import canonical
from provenance import contract as C

SHA = "a" * 40
TS = "2026-10-11T17:57:29Z"

#: A synthetic contract exercising every typelang rule in isolation.
MINI = {
    "contract": "print-bench-provenance-contract", "version": 1,
    "types": {
        "sha40": {"t": "str", "re": "[0-9a-f]{40}"},
        "who": {"t": "obj", "fields": {"login": {"t": "str"}}, "null": True},
    },
    "field_sets": {
        "a.one": {"x": {"t": "int", "min": 0}},
        "b.two": {"y": {"t": "bool"}},
    },
    "shapes": {
        "closed": {"t": "obj", "fields": {"a": {"t": "int"}, "b": {"t": "str", "null": True}},
                   "optional_fields": {"c": {"t": "bool"}}},
        "open": {"t": "open", "fields": {"id": {"t": "int", "min": 1}}},
        "int": {"t": "int", "min": 1, "max": 9},
        "bool": {"t": "bool"},
        "str": {"t": "str", "re": "[0-9a-f]{40}"},
        "short": {"t": "str", "max": 3},
        "enum": {"t": "enum", "of": ["x", "y"]},
        "list": {"t": "list", "of": {"t": "int"}, "max": 3},
        "unique": {"t": "list", "of": {"t": "any"}, "unique": True},
        "sorted": {"t": "list", "of": {"t": "any"}, "sorted": True},
        "map": {"t": "map", "key": "[a-z]+", "of": {"t": "int"}, "max": 2},
        "ref": {"t": "obj", "fields": {"sha": {"t": "ref", "to": "sha40"}, "who": {"t": "ref", "to": "who"},
                                       "nested": {"t": "ref", "to": "int"}}},
        "dangling": {"t": "ref", "to": "nowhere"},
        "event": {"t": "obj", "fields": {"kind": {"t": "enum", "of": ["a.one", "b.two", "c.three"]},
                                         "fields": {"t": "kindfields", "by": "kind"}}},
        "any": {"t": "any"},
    },
}


def errs(shape, value):
    return C.validate(shape, value, MINI)


def ok(shape, value):
    return errs(shape, value) == []


# ---------------------------------------------------------------------------
# Real fixtures.

def _gz(path):
    return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))


def _raw_docs():
    for path in sorted((FIXTURES / "raw").rglob("*.json.gz")):
        shape = {"pr": "raw-pr@1", "brief": "raw-brief@1", "release": "raw-release@1"}[path.parent.name]
        yield path, shape, _gz(path)


def test_every_fixture_validates():
    """All fixtures/raw/**, fixtures/receipts/** validate against raw-*@1 / receipt@1."""
    seen = 0
    for path, shape, doc in _raw_docs():
        assert C.validate(shape, doc) == [], path
        seen += 1
    assert seen == 11  # 6 PRs, 4 briefs, 1 release
    for path in receipt_paths():
        assert C.validate("receipt@1", _gz(path)) == [], path
        seen += 1
    assert seen == 11 + 166
    # every regenerated raw PR carries linked_issues (critique item 24)
    assert all("linked_issues" in doc for _, shape, doc in _raw_docs() if shape == "raw-pr@1")


def test_load_contract_refuses_a_foreign_file(tmp_path):
    assert C.load_contract()["version"] == C.CONTRACT_VERSION
    assert C.load_contract(str(CONTRACT)) is C.load_contract(str(CONTRACT))
    bad = tmp_path / "c.json"
    bad.write_text(json.dumps(dict(contract(), version=2)), encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        C.load_contract(str(bad))
    bad.write_text(json.dumps({"contract": "something-else", "version": 1}), encoding="utf-8")
    with pytest.raises(ValueError):
        C.load_contract(str(bad))


def test_unknown_shape_is_a_programming_error():
    with pytest.raises(ValueError, match="unknown contract shape"):
        C.validate("record@9", {})


# ---------------------------------------------------------------------------
# One rule, one negative control.

def test_closed_object_refuses_an_extra_field():
    """Negative: one extra key anywhere → an error naming the path (P1d: 'both reject a fixture with an extra field')."""
    assert ok("closed", {"a": 1, "b": None})
    assert ok("closed", {"a": 1, "b": "x", "c": True})  # optional field
    assert errs("closed", {"a": 1, "b": None, "z": 0}) == ["$: unexpected field 'z'"]
    assert errs("closed", {"b": None}) == ["$: missing field 'a'"]
    # on the real contract, deep inside a fixture: the error names the full path
    doc = raw_pr(636)
    doc["issue_comments"][3]["body"]["extra"] = 1
    assert C.validate("raw-pr@1", doc) == ["$.issue_comments[3].body: unexpected field 'extra'"]
    doc = raw_pr(636)
    doc["pull"]["head"]["label"] = "x"
    assert C.validate("raw-pr@1", doc) == ["$.pull.head: unexpected field 'label'"]
    with pytest.raises(C.ContractError) as exc:
        C.check("raw-pr@1", doc)
    assert exc.value.errors == ["$.pull.head: unexpected field 'label'"] and exc.value.shape == "raw-pr@1"


def test_open_object_requires_fields_and_ignores_extras():
    assert ok("open", {"id": 3, "anything": {"goes": [1.5]}})
    assert errs("open", {"anything": 1}) == ["$: missing field 'id'"]
    assert errs("open", {"id": 0}) == ["$.id: 0 < min 1"]


def test_null_only_where_the_type_says_so():
    assert ok("closed", {"a": 1, "b": None})
    assert errs("closed", {"a": None, "b": None}) == ["$.a: want int, got null"]
    # a ref without its own null accepts None when the referenced type says "null": true
    assert ok("ref", {"sha": SHA, "who": None, "nested": 5})
    assert errs("ref", {"sha": None, "who": None, "nested": 5}) == ["$.sha: want str, got null"]


def test_int_refuses_bool_and_float():
    """Negative: True and 1.0 are not ints."""
    assert ok("int", 1) and ok("int", 9)
    assert errs("int", True) == ["$: want int, got bool"]
    assert errs("int", 1.0) == ["$: want int, got float"]
    assert errs("int", 1.5) == ["$: want int, got float"]
    assert errs("int", 0) == ["$: 0 < min 1"]
    assert errs("int", 10) == ["$: 10 > max 9"]
    assert errs("bool", 1) == ["$: want bool, got int"] and ok("bool", False)
    doc = raw_pr(636)
    doc["pull"]["commits"] = True
    assert C.validate("raw-pr@1", doc) == ["$.pull.commits: want int, got bool"]


def test_patterns_fullmatch():
    """Negative: a sha with a trailing newline or a 41st char fails."""
    assert ok("str", SHA)
    assert errs("str", SHA + "\n") and errs("str", SHA + "0") and errs("str", SHA[:-1])
    assert errs("str", " " + SHA)
    assert errs("str", 7) == ["$: want str, got int"]
    doc = raw_pr(636)
    doc["pull"]["merge_commit_sha"] += "\n"
    assert [e.split(":")[0] for e in C.validate("raw-pr@1", doc)] == ["$.pull.merge_commit_sha"]


def test_string_max_counts_code_points():
    """``max`` bounds Unicode code points (Python len), never UTF-16 units: three emoji fit max 3."""
    emoji = "\U0001F600" * 3
    assert len(emoji.encode("utf-16-le")) // 2 == 6  # what JS s.length would say
    assert ok("short", emoji)
    assert errs("short", emoji + "x") == ["$: longer than 3 code points (4)"]


def test_enum_and_list_max_and_map_rules():
    assert ok("enum", "x") and errs("enum", "z") and errs("enum", 1) and errs("enum", None)
    assert ok("list", [1, 2, 3])
    assert errs("list", [1, 2, 3, 4]) == ["$: more than 3 items (4)"]
    assert errs("list", [1, "2"]) == ["$[1]: want int, got str"]
    assert errs("list", {"0": 1}) == ["$: want list, got obj"]
    assert ok("map", {"ab": 1, "c": 2})
    assert errs("map", {"AB": 1}) == ['$["AB"]: key does not match [a-z]+']
    # a key whose PREFIX matches but whose tail does not: the key must full-match, not prefix-match
    assert errs("map", {"aB": 1}) == ['$["aB"]: key does not match [a-z]+']
    assert errs("map", {"ab1": 1}) == ['$["ab1"]: key does not match [a-z]+']
    assert errs("map", {"ab\n": 1}) == ['$["ab\\n"]: key does not match [a-z]+']
    assert errs("map", {"a": 1, "b": 2, "c": 3}) == ["$: more than 2 entries (3)"]
    assert errs("map", {"a": "1"}) == ['$["a"]: want int, got str']


def test_real_map_keys_fullmatch():
    """On the real contract a map key with a valid prefix and an invalid tail is refused: a status
    sha key with a trailing newline or a 41st hex char, a record's design key "demo/x" / "demo\\n"."""
    pr = raw_pr(636)
    sha = next(iter(pr["statuses"]))
    for bad in (sha + "\n", sha + "0", sha + "/x"):
        doc = copy.deepcopy(pr)
        doc["statuses"][bad] = doc["statuses"].pop(sha)
        got = C.validate("raw-pr@1", doc)
        assert got == [f"$.statuses[{json.dumps(bad)}]: key does not match [0-9a-f]{{40}}"], (bad, got)
    commit = _records()[f"records/commit/{SHA}.json"]
    assert C.validate("record@1:commit", commit) == []
    for bad in ("demo/x", "demo\n", "demo "):
        rec = copy.deepcopy(commit)
        rec["designs"][bad] = rec["designs"].pop("demo")
        assert C.validate("record@1:commit", rec) == [
            f"$.designs[{json.dumps(bad)}]: key does not match [a-z0-9][a-z0-9-]{{0,63}}"], bad


def test_unique_is_canonical_json_with_sorted_keys():
    """A list of objects that differ only in key order is NOT unique (canonical JSON, sorted keys at every depth)."""
    assert ok("unique", [{"a": 1, "b": {"c": 1, "d": 2}}, {"a": 1, "b": {"c": 2, "d": 1}}])
    assert errs("unique", [{"a": 1, "b": {"c": 1, "d": 2}}, {"b": {"d": 2, "c": 1}, "a": 1}])
    assert errs("unique", [1, 1]) and ok("unique", [1, True, "1"])  # 1, true and "1" differ
    # the real contract: a duplicated label
    doc = raw_pr(636)
    doc["pull"]["labels"] = ["a", "a"]
    assert any("not unique" in e for e in C.validate("raw-pr@1", doc))


def test_sorted_compares_ints_numerically_and_strings_by_code_point():
    """A code-point-sorted list with an astral character validates; its UTF-16 order does not."""
    assert ok("sorted", [2, 10]) and errs("sorted", [10, 2])  # numeric, not lexical
    assert ok("sorted", ["￿", "\U0001F600"])  # U+FFFF < U+1F600 by code point …
    assert sorted(["￿", "\U0001F600"], key=lambda s: s.encode("utf-16-be")) == ["\U0001F600", "￿"]
    assert errs("sorted", ["\U0001F600", "￿"]) == ["$: not sorted"]  # … though UTF-16 sorts the emoji first
    assert errs("sorted", [1, "a"]) == ["$: not homogeneous (a sorted list holds only ints or only strings)"]
    assert errs("sorted", [True, 2]) == ["$: not homogeneous (a sorted list holds only ints or only strings)"]
    doc = raw_pr(636)
    doc["pull"]["labels"] = ["￿", "\U0001F600"]
    assert C.validate("raw-pr@1", doc) == []
    doc["pull"]["labels"] = ["\U0001F600", "￿"]
    assert C.validate("raw-pr@1", doc) == ["$.pull.labels: not sorted"]


def test_refs_resolve_types_then_shapes():
    assert ok("ref", {"sha": SHA, "who": {"login": "x"}, "nested": 3})
    assert errs("ref", {"sha": SHA, "who": {"login": "x"}, "nested": 0}) == ["$.nested: 0 < min 1"]
    assert errs("ref", {"sha": SHA, "who": {"login": 1}, "nested": 3}) == ["$.who.login: want str, got int"]
    assert errs("dangling", 1) == ["$: contract names an unknown type 'nowhere'"]


def test_errors_are_collected_in_document_order():
    value = {"z": 1, "a": "x", "b": 3}
    assert errs("closed", value) == ["$: unexpected field 'z'", "$.a: want int, got str", "$.b: want str, got int"]
    assert errs("list", ["a", 1, "b", 2, 3]) == ["$: more than 3 items (5)", "$[0]: want int, got str",
                                                 "$[2]: want int, got str"]


def test_kindfields_closed_per_kind():
    """Negative: review.signoff fields with a triage key fail; every contract kind has a field set."""
    assert ok("event", {"kind": "a.one", "fields": {"x": 1}})
    assert errs("event", {"kind": "a.one", "fields": {"y": True}}) == ["$.fields: unexpected field 'y'",
                                                                       "$.fields: missing field 'x'"]
    assert errs("event", {"kind": "c.three", "fields": {}}) == ["$.fields: no field set for kind 'c.three'"]
    # the real contract
    c = contract()
    assert set(c["field_sets"]) == set(c["enums"]["kind"]) == set(c["shapes"]["event@1"]["fields"]["kind"]["of"])
    event = _event()
    assert C.validate("event@1", event) == []
    bad = copy.deepcopy(event)
    bad["fields"]["act_now"] = 1
    assert C.validate("event@1", bad) == ["$.fields: unexpected field 'act_now'"]
    bad = copy.deepcopy(event)
    bad["kind"] = "triage.verdict"
    got = C.validate("event@1", bad)
    assert "$.fields: unexpected field 'family'" in got and "$.fields: missing field 'act_now'" in got


def test_every_contract_pattern_is_ascii_and_compiles():
    """The typelang says patterns are ASCII-only (both stacks compile them); every one compiles here."""
    import re
    found = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("re", "key") and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    c = contract()
    walk({k: c[k] for k in ("types", "field_sets", "shapes")})
    assert len(found) > 50
    for pattern in found:
        assert pattern.isascii(), pattern
        re.compile(pattern)


def test_layout_tables_are_the_contracts_trees():
    c = contract()
    assert list(C.EVIDENCE_LAYOUT) == c["trees"]["provenance"]
    assert list(C.DERIVED_LAYOUT) == c["trees"]["provenance-site"]


# ---------------------------------------------------------------------------
# Prose: no key the contract does not name.

#: The GitHub Actions job / step API keys a receipt keeps inside its two opaque regions
#: (``jobs[]`` is ``open`` and ``steps`` is ``any``): complete API objects, none of them prose.
JOB_API_KEYS = frozenset({
    "check_run_url", "completed_at", "conclusion", "created_at", "head_branch", "head_sha",
    "html_url", "id", "labels", "name", "node_id", "run_attempt", "run_id", "run_url",
    "runner_group_id", "runner_group_name", "runner_id", "runner_name", "started_at", "status",
    "steps", "url", "workflow_name"})
STEP_API_KEYS = frozenset({"completed_at", "conclusion", "name", "number", "started_at", "status"})


def _foreign_keys(c, shape, doc):
    """Every key of ``doc`` the contract does not name, walking the contract alongside the value.

    A closed ``obj`` names its keys (``validate`` refuses any other); a map's
    keys are data (validated by its ``key`` pattern), not field names; the two
    opaque regions — an ``open`` object's extra keys and the inside of an
    ``any`` — must stay within the GitHub job / step API key sets.
    """
    out = []

    def resolve(node):
        while node.get("t") == "ref":
            node = c["types"].get(node["to"]) or c["shapes"][node["to"]]
        return node

    def walk(node, value, path, parent):
        node = resolve(node)
        t = node.get("t")
        if value is None:
            return
        if t == "list" and isinstance(value, list):
            for i, item in enumerate(value):
                walk(node["of"], item, f"{path}[{i}]", None)
        elif t == "map" and isinstance(value, dict):
            for key, item in value.items():
                walk(node["of"], item, f"{path}[{key!r}]", None)
        elif t in ("obj", "open", "kindfields") and isinstance(value, dict):
            fields = (c["field_sets"].get(parent.get(node.get("by", "kind")), {}) if t == "kindfields"
                      else {**node.get("fields", {}), **node.get("optional_fields", {})})
            for key, item in value.items():
                if key in fields:
                    walk(fields[key], item, f"{path}.{key}", value)
                elif t != "open" or key not in JOB_API_KEYS:
                    out.append(f"{path}.{key}")
        elif t == "any":
            for step in value if isinstance(value, list) else [value]:
                keys = step.keys() if isinstance(step, dict) else ()
                out.extend(f"{path}.{k}" for k in keys if k not in STEP_API_KEYS)

    walk(c["shapes"][shape], doc, "$", None)
    return out


def test_no_fixture_field_outside_the_contract():
    """P1a: a walk of every committed fixture finds no key the contract does not name, so no prose is present."""
    c = contract()
    for path, shape, doc in _raw_docs():
        assert _foreign_keys(c, shape, doc) == [], path
    for path in receipt_paths():
        assert _foreign_keys(c, "receipt@1", _gz(path)) == [], path
    # negative controls: the walk and the closed shapes both catch a planted prose key
    doc = raw_pr(636)
    doc["issue_comments"][0]["comment_text"] = "a pasted secret"
    assert _foreign_keys(c, "raw-pr@1", doc) == ["$.issue_comments[0].comment_text"]
    assert C.validate("raw-pr@1", doc) == ["$.issue_comments[0]: unexpected field 'comment_text'"]
    doc = raw_pr(636)
    doc["pull"]["body"] = "prose instead of a digest"
    assert C.validate("raw-pr@1", doc) == ["$.pull.body: want obj, got str"]
    rec = _gz(receipt_paths()[0])
    assert rec["kind"] == "full"
    rec["jobs"][0]["steps"][0]["log_text"] = "x"
    rec["jobs"][0]["runner_log"] = "x"
    assert _foreign_keys(c, "receipt@1", rec) == ["$.jobs[0].steps[0].log_text", "$.jobs[0].runner_log"]
    assert C.validate("receipt@1", rec) == []  # the opaque regions are exactly what this walk adds


# ---------------------------------------------------------------------------
# Whole trees.

def _state():
    return {"format": "state@1",
            "versions": {"harvester": "provenance 0.1.0", "digest": "body-digest@1", "step_grammar": 1,
                         "contract": 1},
            "cursors": {"receipts": {}, "prs_updated": None, "briefs_updated": None, "releases_published": None},
            "pending": {"pr": {}, "brief": {}}, "skipped": {"pr": {}}, "ingested": {}}


def _guard():
    return {"vercel.json": (GUARD_DIR / "vercel.json").read_bytes(),
            "scripts/vercel-ignore-build.sh": (GUARD_DIR / "vercel-ignore-build.sh").read_bytes()}


def _evidence_files():
    files = dict(_guard())
    files["FORMAT"] = b"print-bench-provenance 1\n"
    files["README.md"] = b"# provenance - evidence data branch\n"
    files["state.json"] = canonical.dumps_bytes(_state())
    for path in sorted((FIXTURES / "raw").rglob("*.json.gz")) + receipt_paths():
        files[path.relative_to(FIXTURES).as_posix()] = path.read_bytes()
    return files


def _tree_errors(files, kind):
    return C.validate_tree(FakeTreeReader(files), kind)


def test_evidence_tree_of_the_fixtures_validates():
    files = _evidence_files()
    assert len(files) == 5 + 11 + 166
    assert _tree_errors(files, "evidence") == []


def test_evidence_tree_negatives():
    base = _evidence_files()

    def with_(**edits):
        files = dict(base)
        for path, data in edits.items():
            if data is None:
                files.pop(path)
            else:
                files[path] = data
        return _tree_errors(files, "evidence")

    def put(path, doc):
        return {path: canonical.dumps_gz(doc)}

    assert with_(FORMAT=b"print-bench-provenance 2\n") == [
        "FORMAT: b'print-bench-provenance 2\\n' is not b'print-bench-provenance 1\\n'"]
    assert with_(**{"README.md": None}) == ["README.md: missing (the evidence tree must carry it)"]
    assert with_(**{"notes.txt": b"x"}) == ["notes.txt: not a path of the contract's trees.provenance layout"]
    # a receipt filed under the wrong day / attempt
    rec_path = receipt_paths()[0].relative_to(FIXTURES).as_posix()
    moved = rec_path.replace("/10/", "/11/", 1)
    got = with_(**{rec_path: None, moved: base[rec_path]})
    assert got == [f"{moved}: the document belongs at {rec_path}"]
    wrong_attempt = rec_path.replace(".a1.", ".a2.")
    assert with_(**{rec_path: None, wrong_attempt: base[rec_path]}) == [
        f"{wrong_attempt}: the document belongs at {rec_path}"]
    # raw revisions: .r1 is not a path, K >= 2 must be contiguous from 1
    doc = raw_pr(636)
    assert with_(**{"raw/pr/636.json.gz": None, "raw/pr/636.r1.json.gz": base["raw/pr/636.json.gz"]}) == [
        "raw/pr/636.r1.json.gz: the document belongs at raw/pr/636.json.gz"]
    assert with_(**put("raw/pr/636.r3.json.gz", dict(doc, revision=3))) == [
        "raw/pr/636: revisions [1, 3] are not contiguous from 1"]
    assert with_(**put("raw/pr/636.r2.json.gz", dict(doc, revision=2))) == []  # the positive control
    # a document that is not canonical JSON (indent 2) or does not validate
    loose = gzip.compress(json.dumps(doc, indent=2).encode())
    assert with_(**{"raw/pr/636.json.gz": loose}) == ["raw/pr/636.json.gz: not canonical JSON (canonical.dumps)"]
    bad = dict(doc, surprise=1)
    assert with_(**put("raw/pr/636.json.gz", bad)) == ["raw/pr/636.json.gz: $: unexpected field 'surprise'"]
    assert with_(**{"state.json": b'{"format": "state@1"}'}) != []
    # content identity is the decompressed bytes: a different gzip stream of the same JSON is fine
    regz = gzip.compress(gzip.decompress(base["raw/pr/636.json.gz"]), compresslevel=1, mtime=12345)
    assert regz != base["raw/pr/636.json.gz"]
    assert with_(**{"raw/pr/636.json.gz": regz}) == []
    # guard drift on the evidence ref is gitstore.guard_drift's warning, never an error here
    assert with_(**{"vercel.json": b'{"drifted": true}\n'}) == []
    assert with_(**{"vercel.json": b""}) == ["vercel.json: empty guard file"]


def _view(design):
    return {"format": "view@1", "design": design, "extractor": "provenance-extract 1",
            "aliases": {"briefs": [], "slugs": []}, "prs": [], "briefs": [], "commits": [], "episodes": [],
            "events": [], "maintenance": [], "releases": [],
            "counts": {"events": 0, "rounds": 0, "prs": 0, "maintenance": 0,
                       "signoffs": {"verified": 0, "window": 0, "claimed": 0}, "triage": 0,
                       "jobs_posted_nothing": 0}}


def _records():
    commit = {"format": "record@1", "extractor": "provenance-extract 1", "incomplete": [], "events": [],
              "kind": "commit", "key": SHA, "sha": SHA, "committed_at": TS,
              "designs": {"demo": {"membership": "member", "kinds": ["docs", "source"]}},
              "evidence": {"raw": None, "raw_sha256": None, "revision": None, "receipts": [], "source": "git"}}
    release = {"format": "record@1", "extractor": "provenance-extract 1", "incomplete": [], "events": [],
               "kind": "release", "key": "v2.0", "tag": "v2.0", "published_at": TS, "designs": ["demo"],
               "evidence": {"raw": "raw/release/v2.0.json.gz", "raw_sha256": "0" * 64, "revision": 1,
                            "receipts": [], "source": "evidence"}}
    return {f"records/commit/{SHA}.json": commit, "records/release/v2.0.json": release}


def _derived_files(views=("demo", "empty-design"), records=None, bundle_edit=None):
    recs = _records() if records is None else records
    vs = {d: _view(d) for d in views}
    files = dict(_guard())
    files["FORMAT"] = b"print-bench-provenance-site 1\n"
    for path, rec in recs.items():
        files[path] = canonical.dumps_bytes(rec)
    for d, v in vs.items():
        files[f"views/{d}.json"] = canonical.dumps_bytes(v)
    views_sha = {d: canonical.content_sha256(v) for d, v in vs.items()}
    record_sha = {p: canonical.sha256_hex(files[p]) for p in sorted(files) if p.startswith("records/")}
    bundle = {"format": "bundle@1", "contract": 1, "extractor": "provenance-extract 1",
              "main_sha": "521d092813b78a88bd9a74b1052cfef1f230d86b", "evidence_sha": "0" * 40,
              "producer_run": 1, "views": vs, "views_sha256": views_sha,
              "content_sha256": canonical.content_sha256({"records": record_sha, "views_sha256": views_sha,
                                                          "extractor": "provenance-extract 1"})}
    if bundle_edit:
        bundle_edit(bundle)
    files["site/bundle.json"] = canonical.dumps_bytes(bundle)
    return files


def test_derived_tree_validates_and_recomputes():
    files = _derived_files()
    assert _tree_errors(files, "derived") == []
    # a derived tree is not an evidence tree
    assert _tree_errors(files, "evidence") != []
    with pytest.raises(ValueError):
        C.validate_tree(FakeTreeReader(files), "site")


def test_derived_tree_negatives():
    def forge(fn):
        return _derived_files(bundle_edit=fn)

    # a forged content digest, a forged view digest, a contract version the validator is not
    assert _tree_errors(forge(lambda b: b.update(content_sha256="f" * 64)), "derived") == [
        "site/bundle.json: content_sha256 does not recompute from the tree"]
    got = _tree_errors(forge(lambda b: b["views_sha256"].update(demo="f" * 64)), "derived")
    assert 'site/bundle.json: views_sha256["demo"] does not recompute' in got
    assert _tree_errors(forge(lambda b: b.update(contract=2)), "derived") == [
        "site/bundle.json: contract 2 is not the contract's version 1"]
    # the bundle's view differs from views/<d>.json (a forged view under a copied digest)
    files = _derived_files()
    files["views/demo.json"] = canonical.dumps_bytes(dict(_view("demo"), prs=[636]))
    assert _tree_errors(files, "derived") == ["views/demo.json: differs from the bundle's view"]
    # a view file the bundle does not carry
    files = _derived_files()
    files["views/ghost.json"] = canonical.dumps_bytes(_view("ghost"))
    assert any("are not the tree's views/ files" in e for e in _tree_errors(files, "derived"))
    # a record edited after the bundle was built changes content_sha256
    files = _derived_files()
    rec = _records()[f"records/commit/{SHA}.json"]
    files[f"records/commit/{SHA}.json"] = canonical.dumps_bytes(dict(rec, committed_at="2026-10-12T00:00:00Z"))
    assert _tree_errors(files, "derived") == ["site/bundle.json: content_sha256 does not recompute from the tree"]
    # a record at the wrong path, or whose key is not its own sha
    other = "b" * 40
    recs = {f"records/commit/{other}.json": _records()[f"records/commit/{SHA}.json"]}
    assert _tree_errors(_derived_files(records=recs), "derived") == [
        f"records/commit/{other}.json: the document belongs at records/commit/{SHA}.json"]
    bad_key = dict(_records()[f"records/commit/{SHA}.json"], key=other)
    got = _tree_errors(_derived_files(records={f"records/commit/{other}.json": bad_key}), "derived")
    assert got == [f"records/commit/{other}.json: cannot derive the document's own path "
                   f"(key '{other}' is not the record's sha)"]
    # an extra field in a record, a guard file that is not main's, a wrong FORMAT
    recs = {f"records/commit/{SHA}.json": dict(_records()[f"records/commit/{SHA}.json"], note="x")}
    assert _tree_errors(_derived_files(records=recs), "derived") == [
        f"records/commit/{SHA}.json: $: unexpected field 'note'"]
    files = _derived_files()
    files["vercel.json"] = b'{"drifted": true}\n'
    assert _tree_errors(files, "derived") == ["vercel.json: differs from main's .github/data-branch-guard/vercel.json"]
    files = _derived_files()
    files["FORMAT"] = b"print-bench-provenance 1\n"
    assert _tree_errors(files, "derived") == [
        "FORMAT: b'print-bench-provenance 1\\n' is not b'print-bench-provenance-site 1\\n'"]
    files = _derived_files()
    del files["site/bundle.json"]
    assert "site/bundle.json: missing (the derived tree must carry it)" in _tree_errors(files, "derived")


# ---------------------------------------------------------------------------
# Python ↔ Node.

def _event():
    return {
        "id": "issuecomment:6111970233", "ts": TS, "ts_precision": "second", "tz": "UTC",
        "kind": "review.signoff", "episode": "R:636:f4e36eb9", "pr": 636, "issue": None, "sha": SHA,
        "head_sha": None, "stale_sha": False, "after_merge": False,
        "url": "https://github.com/shaiss/print-bench/pull/636#issuecomment-6111970233",
        "signals": {"login": "github-actions[bot]", "login_type": "Bot", "app": "github-actions",
                    "marker": "JANE_SIGNOFF", "commit_author_name": None, "commit_author_email": None,
                    "committer_login": None, "status_context": None, "regen_identity": False,
                    "trailer_coauthors": [], "trailer_session": None},
        "trust": "verified", "trust_basis": "actions-bot+suffix",
        "runtime": {"platform": "github-actions", "harness": None, "role": None, "workflow": None, "job": None,
                    "job_id": None, "run_id": None, "attempt": None, "chain": None, "chain_link": None,
                    "links_not_served": None, "provider": None, "model": None, "model_basis": "none"},
        "fields": {"family": "JANE_SIGNOFF", "verdict": "pass", "fuse": "none", "edited": False},
        "edges": {"verifies": []},
    }


NODE_MJS = REPO / "site" / "lib" / "provenance-contract.mjs"
NODE_BUNDLE = REPO / "site" / "test" / "fixtures" / "provenance-bundle.json"

#: The one corpus case the two stacks CANNOT agree on through ``validate(shape, value)``: Python's
#: ``json.loads("1.0")`` keeps a float (``want int, got float``) while Node's ``JSON.parse("1.0")``
#: is the integer ``1`` — the distinction is gone before a JS validator sees the value. What refuses
#: an integral float on the Node side is the canonical-bytes check of the file it read
#: (:func:`test_integral_float_is_refused_by_the_canonical_bytes_check` pins the Python half: a
#: tree blob carrying ``1.0`` is never canonical). Pinned both ways so a change on either side is seen.
INTEGRAL_FLOAT = "an integral float (N.0) where an int belongs"
NODE_DIVERGES = {INTEGRAL_FLOAT: (False, True)}  # label -> (python accepts, node accepts)


def _corpus():
    """``[(label, shape, value)]`` over the real contract: accepts and the matching rejects."""
    out = []
    if NODE_BUNDLE.exists():
        bundle = json.loads(NODE_BUNDLE.read_text(encoding="utf-8"))
        out.append(("fixture bundle", "bundle@1", bundle))
        out.append(("fixture bundle + extra field", "bundle@1", dict(bundle, extra=1)))
        out.append(("fixture bundle, bad enum", "bundle@1", dict(bundle, format="bundle@2")))
    pr = raw_pr(636)
    out.append(("raw pr 636", "raw-pr@1", pr))
    out.append(("raw pr 636 + extra field", "raw-pr@1", dict(pr, extra=1)))
    labels = copy.deepcopy(pr)
    labels["pull"]["labels"] = ["￿", "\U0001F600"]
    out.append(("astral labels, code-point order", "raw-pr@1", labels))
    labels = copy.deepcopy(pr)
    labels["pull"]["labels"] = ["\U0001F600", "￿"]
    out.append(("astral labels, UTF-16 order", "raw-pr@1", labels))
    flt = copy.deepcopy(pr)
    flt["pull"]["commits"] = 1.5
    out.append(("a float where an int belongs", "raw-pr@1", flt))
    flt = copy.deepcopy(pr)
    flt["pull"]["commits"] = float(flt["pull"]["commits"])  # serialised as "N.0"
    out.append((INTEGRAL_FLOAT, "raw-pr@1", flt))
    long_title = copy.deepcopy(pr)
    long_title["pull"]["title"] = "\U0001F600" * 1000  # 1000 code points = max, 2000 UTF-16 units
    out.append(("1000 emoji title (max 1000 code points)", "raw-pr@1", long_title))
    out.append(("event@1", "event@1", _event()))
    ev = _event()
    ev["fields"]["act_now"] = 0
    out.append(("event@1 with a foreign kind field", "event@1", ev))
    out.append(("evidence state", "state@1", _state()))
    return out


def test_integral_float_is_refused_by_the_canonical_bytes_check():
    """The Python half of the NODE_DIVERGES closure: a stored blob spelling an int as ``1.0`` (which
    a JS ``JSON.parse`` reads back as ``1``) is refused by ``validate_tree`` — canonical bytes never
    carry a float — on a derived tree (site/bundle.json) and on an evidence raw blob."""
    files = _derived_files()
    blob = files["site/bundle.json"]
    assert blob.count(b'"producer_run": 1,') == 1
    files["site/bundle.json"] = blob.replace(b'"producer_run": 1,', b'"producer_run": 1.0,')
    got = _tree_errors(files, "derived")
    assert "site/bundle.json: not storable canonical JSON ($.producer_run: float 1.0 — the provenance " \
           "contract stores integers only)" in got, got
    ev = _evidence_files()
    doc = json.loads(gzip.decompress(ev["raw/pr/636.json.gz"]))
    doc["pull"]["commits"] = float(doc["pull"]["commits"])
    ev["raw/pr/636.json.gz"] = gzip.compress(json.dumps(doc, indent=1, sort_keys=True,
                                                        ensure_ascii=False).encode() + b"\n", mtime=0)
    assert any(e.startswith("raw/pr/636.json.gz: not storable canonical JSON ($.pull.commits: float")
               for e in _tree_errors(ev, "evidence"))


@pytest.mark.skipif(shutil.which("node") is None or not NODE_MJS.exists(),
                    reason="needs node and site/lib/provenance-contract.mjs (H5)")
def test_python_and_node_agree(tmp_path):
    """When node is on PATH: site/lib/provenance-contract.mjs gives the same accept/reject verdicts as contract.validate on a shared corpus (the fixture bundle, the extra-field negative, a bad-enum negative)."""
    corpus = _corpus()
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps([[shape, value] for _, shape, value in corpus], ensure_ascii=False),
                    encoding="utf-8")
    script = ("import { pathToFileURL } from 'node:url'; import { readFileSync } from 'node:fs';"
              "const m = await import(pathToFileURL(process.argv[1]).href);"
              "const corpus = JSON.parse(readFileSync(process.argv[2], 'utf8'));"
              "console.log(JSON.stringify(corpus.map(([s, v]) => m.validate(s, v).length === 0)));")
    proc = subprocess.run(["node", "--input-type=module", "-e", script, str(NODE_MJS), str(path)],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    labels = [c[0] for c in corpus]
    node = dict(zip(labels, json.loads(proc.stdout.strip().splitlines()[-1])))
    python = dict(zip(labels, (C.validate(shape, value) == [] for _, shape, value in corpus)))
    # the known divergence, pinned exactly (python rejects, node accepts) …
    assert {label: (python[label], node[label]) for label in NODE_DIVERGES} == NODE_DIVERGES
    # … and every other case agrees
    assert {k: v for k, v in node.items() if k not in NODE_DIVERGES} == {
        k: v for k, v in python.items() if k not in NODE_DIVERGES}
    expected_reject = {label for label, _, _ in corpus if any(w in label for w in (
        "extra field", "bad enum", "UTF-16 order", "float", "foreign kind"))}
    assert {label for label, good in python.items() if not good} == expected_reject


def test_python_corpus_verdicts():
    """The Python half of the parity corpus, runnable without node: accepts and rejects as labelled."""
    for label, shape, value in _corpus():
        rejected = any(w in label for w in ("extra field", "bad enum", "UTF-16 order", "float", "foreign kind"))
        assert (C.validate(shape, value) != []) == rejected, label
