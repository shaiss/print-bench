"""bundle + derived tree + Python↔Node parity (P1d).

Owner: H5. Acceptance criteria from docs/provenance.md (final plan P0/P1a–e,
the critique round's items 5, 6, 14, 27). Unit tests replace H3/H4's
functions with recording stand-ins through ``monkeypatch`` (they run now);
the ``@needs`` tests run the real composition at integration.
"""

from __future__ import annotations

import collections
import copy
import json
import os
import re

import pytest

import _views_helpers as h
from conftest import (FIXTURE_MAIN_SHA, GUARD_DIR, OWNER, OWNER_LOGIN, REPO, REPO_NAME, contract,
                      needs, raw_pr, receipt_paths)
from fakes import FakeCodeBasis, FakeCommit, FakeGitReader, FakeTreeReader

from provenance import (bundle, canonical, contract as contract_mod, episodes, extract,
                        gitstore, serving, trust, views)

GUARD = {
    "vercel.json": ("100644", (GUARD_DIR / "vercel.json").read_bytes()),
    "scripts/vercel-ignore-build.sh": ("100755", (GUARD_DIR / "vercel-ignore-build.sh").read_bytes()),
}


class ModeTreeReader:
    """A ``protocols.TreeReader`` over ``{path: (mode, bytes)}`` that also reports modes."""

    def __init__(self, files):
        self.files = dict(files)

    def paths(self, prefix=""):
        return sorted(p for p in self.files if p.startswith(prefix))

    def read(self, path):
        entry = self.files.get(path)
        return entry[1] if entry else None

    def mode(self, path):
        entry = self.files.get(path)
        return entry[0] if entry else None


@pytest.fixture
def fake_episodes(monkeypatch):
    h.patch_episodes(monkeypatch)


def _tree_files(records=None):
    records = h.synthetic_records() if records is None else records
    views_ = h.fixture_views(records)
    rec_bytes = {bundle.record_path(r): canonical.dumps_bytes(r) for r in records}
    b = bundle.build_bundle(views_, records=rec_bytes, main_sha=FIXTURE_MAIN_SHA,
                            evidence_sha="0" * 40, producer_run=1,
                            extractor=extract.EXTRACTOR_VERSION)
    return bundle.derived_tree_files(records, views_, b, GUARD), b


# ----------------------------------------------------------------------------- the fixture bundle

@needs(episodes.episodes_of, episodes.rounds_from_record, views.build_view)
def test_fixture_bundle_regenerates_byte_for_byte():
    """Rebuilding site/test/fixtures/provenance-bundle.json IN MEMORY from the synthetic records in tests/fixtures/records/ (main_sha 521d0928…, evidence_sha '0'*40, producer_run 1) is byte-identical across two runs and against the committed file; the file is written only when PROVENANCE_UPDATE_FIXTURES=1 (critique 27). Decorate with @needs(episodes.episodes_of, views.build_view): it runs, and the committed file is regenerated, at integration."""
    data = h.fixture_bundle_bytes()
    assert data == h.fixture_bundle_bytes()
    if os.environ.get("PROVENANCE_UPDATE_FIXTURES") == "1":
        h.FIXTURE_BUNDLE.parent.mkdir(parents=True, exist_ok=True)
        h.FIXTURE_BUNDLE.write_bytes(data)
    assert h.FIXTURE_BUNDLE.read_bytes() == data, (
        "site/test/fixtures/provenance-bundle.json is stale: rerun with PROVENANCE_UPDATE_FIXTURES=1")


def test_fixture_bundle_build_is_deterministic(fake_episodes):
    """The builder itself (stand-in episodes): two runs, and reversed record order, agree byte for byte."""
    data = h.fixture_bundle_bytes()
    assert data == h.fixture_bundle_bytes()
    records = list(reversed(h.synthetic_records()))
    rec_bytes = {bundle.record_path(r): canonical.dumps_bytes(r) for r in records}
    flipped = bundle.build_bundle(dict(reversed(list(h.fixture_views(records).items()))),
                                  records=dict(reversed(list(rec_bytes.items()))),
                                  main_sha=FIXTURE_MAIN_SHA, evidence_sha="0" * 40,
                                  producer_run=1, extractor=extract.EXTRACTOR_VERSION)
    assert canonical.dumps_bytes(flipped) == data


def test_committed_fixture_bundle_is_self_consistent():
    """Independent of episodes: the committed file is canonical, carries the fixed meta and its
    digests recompute from its own views and the synthetic records' bytes."""
    raw = h.FIXTURE_BUNDLE.read_bytes()
    b = json.loads(raw)
    assert canonical.dumps_bytes(b) == raw
    assert (b["main_sha"], b["evidence_sha"], b["producer_run"]) == (FIXTURE_MAIN_SHA, "0" * 40, 1)
    assert b["format"] == "bundle@1" and b["contract"] == contract()["version"]
    assert sorted(b["views"]) == sorted(h.synthetic_designs())
    assert b["views_sha256"] == {d: canonical.content_sha256(v) for d, v in b["views"].items()}
    rec_bytes = {bundle.record_path(r): canonical.dumps_bytes(r) for r in h.synthetic_records()}
    again = bundle.build_bundle(b["views"], records=rec_bytes, main_sha=b["main_sha"],
                                evidence_sha=b["evidence_sha"], producer_run=b["producer_run"],
                                extractor=b["extractor"])
    assert again == b
    # negative control: one record byte changed moves content_sha256
    path = sorted(rec_bytes)[0]
    rec_bytes[path] += b" "
    assert bundle.build_bundle(b["views"], records=rec_bytes, main_sha=b["main_sha"],
                               evidence_sha=b["evidence_sha"], producer_run=1,
                               extractor=b["extractor"])["content_sha256"] != b["content_sha256"]


def test_synthetic_records_cover_the_contract():
    """Every record kind, every event kind (so every field set), two designs with history plus a
    zero-history one, a maintenance PR and a PR whose linked_issues differ from its briefs."""
    c = contract()
    records = h.synthetic_records()
    rows = [e for evs in h.synthetic_rows().values() for e in evs]
    events = [e for r in records for e in r["events"]] + rows
    assert {r["kind"] for r in records} == {"pr", "brief", "commit", "release"}
    assert {e["kind"] for e in events} == set(c["enums"]["kind"]) == set(c["field_sets"])
    assert {e["trust"] for e in events} == set(c["enums"]["trust"])
    designs = h.synthetic_designs()
    touched = {d for r in records for d in (r.get("designs") or [])}
    assert len(designs) == 3 and set(designs) - touched == {"gamma-stand"}
    memberships = {m["membership"] for r in records if r["kind"] == "pr" for m in r["designs"].values()}
    assert memberships == {"member", "regen-only", "sweep", "stacked-excluded"}
    assert any(r["kind"] == "pr" and r["linked_issues"] != r["briefs"] for r in records)
    for r in records:
        assert canonical.dumps_bytes(r) == (h.RECORDS / bundle.record_path(r)[len("records/"):]).read_bytes()


# ----------------------------------------------------------------------------- validators

def _negatives(b):
    extra_top = copy.deepcopy(b)
    extra_top["extra"] = 1
    extra_deep = copy.deepcopy(b)
    extra_deep["views"]["alpha-clip"]["events"][0]["fields"]["extra"] = True
    bad_enum = copy.deepcopy(b)
    bad_enum["views"]["alpha-clip"]["events"][0]["trust"] = "trusted-by-vibes"
    a_float = copy.deepcopy(b)
    a_float["views"]["alpha-clip"]["counts"]["events"] = 1.5
    return {"extra field (top)": extra_top, "extra field (event fields)": extra_deep,
            "bad enum": bad_enum, "float": a_float}


def test_node_validator_accepts_and_rejects(tmp_path):
    """site/lib/provenance-contract.mjs accepts the committed fixture bundle and every synthetic
    record, and rejects the bundle with one extra field, a bad enum and a float."""
    if h.node() is None:
        pytest.skip("node not on PATH")
    b = json.loads(h.FIXTURE_BUNDLE.read_text(encoding="utf-8"))
    assert h.node_validate("bundle@1", b, tmp_path) == []
    for r in h.synthetic_records():
        assert h.node_validate(f"record@1:{r['kind']}", r, tmp_path) == [], bundle.record_path(r)
    for label, bad in _negatives(b).items():
        assert h.node_validate("bundle@1", bad, tmp_path), label


@needs(contract_mod.validate)
def test_python_and_node_validators_accept_and_reject(tmp_path):
    """Both validators accept the fixture bundle and both reject it with one extra field."""
    b = json.loads(h.FIXTURE_BUNDLE.read_text(encoding="utf-8"))
    assert contract_mod.validate("bundle@1", b) == []
    for r in h.synthetic_records():
        assert contract_mod.validate(f"record@1:{r['kind']}", r) == [], bundle.record_path(r)
    negatives = _negatives(b)
    for label, bad in negatives.items():
        assert contract_mod.validate("bundle@1", bad), label
    if h.node() is None:
        pytest.skip("node not on PATH: the Python half passed")
    assert h.node_validate("bundle@1", b, tmp_path) == []
    for label, bad in negatives.items():
        assert h.node_validate("bundle@1", bad, tmp_path), label


# ----------------------------------------------------------------------------- same_content

def test_same_content_reads_the_tip_not_its_digest(fake_episodes):
    """Critique 5: same_content(tip, files) is True for a tip that differs only in main_sha / evidence_sha / producer_run, and False for a forged tip whose bundle keeps the real content_sha256 field but alters one view (or one records/ blob, or one file mode, or swaps a 1 for true), and False — never an exception — for a tip bundle too deep to parse."""
    files, b = _tree_files()
    assert bundle.same_content(ModeTreeReader(files), files)

    def with_bundle(value, raw=None):
        out = dict(files)
        out[bundle.BUNDLE_PATH] = ("100644", raw if raw is not None else canonical.dumps_bytes(value))
        return out

    # differs only in the three meta fields → same content
    for name, value in (("main_sha", "1" * 40), ("evidence_sha", "2" * 40), ("producer_run", 99)):
        meta = dict(b, **{name: value})
        assert bundle.same_content(ModeTreeReader(with_bundle(meta)), files), name
    # forged: one view altered in views/<d>.json AND in the bundle, real digests kept
    forged_view = copy.deepcopy(b)
    forged_view["views"]["alpha-clip"]["events"][0]["trust"] = "verified"
    forged = with_bundle(forged_view)
    forged["views/alpha-clip.json"] = ("100644",
                                       canonical.dumps_bytes(forged_view["views"]["alpha-clip"]))
    assert forged_view["content_sha256"] == b["content_sha256"]
    assert not bundle.same_content(ModeTreeReader(forged), files)
    # forged in the bundle only, or in the view file only
    assert not bundle.same_content(ModeTreeReader(with_bundle(forged_view)), files)
    only_file = dict(files)
    only_file["views/alpha-clip.json"] = forged["views/alpha-clip.json"]
    assert not bundle.same_content(ModeTreeReader(only_file), files)
    # one records/ blob altered
    rec = dict(files)
    path = next(p for p in files if p.startswith("records/pr/"))
    rec[path] = ("100644", files[path][1].replace(b'"merged"', b'"closed"', 1))
    assert rec[path] != files[path]
    assert not bundle.same_content(ModeTreeReader(rec), files)
    # one file mode
    mode = dict(files)
    mode["scripts/vercel-ignore-build.sh"] = ("100644", files["scripts/vercel-ignore-build.sh"][1])
    assert not bundle.same_content(ModeTreeReader(mode), files)
    # an extra path, a missing path
    assert not bundle.same_content(ModeTreeReader(dict(files, **{"views/zz.json": ("100644", b"{}\n")})), files)
    missing = dict(files)
    del missing["views/gamma-stand.json"]
    assert not bundle.same_content(ModeTreeReader(missing), files)
    # the bundle: same content but non-canonical bytes, a dropped meta field, a duplicated key
    assert not bundle.same_content(ModeTreeReader(with_bundle(b, raw=json.dumps(b).encode())), files)
    no_meta = {k: v for k, v in b.items() if k != "producer_run"}
    assert not bundle.same_content(ModeTreeReader(with_bundle(no_meta)), files)
    text = canonical.dumps(b)
    dup = text.replace('\n "views": {', '\n "views": {},\n "views": {', 1).encode()
    assert dup != text.encode() and json.loads(dup) == b
    assert not bundle.same_content(ModeTreeReader(with_bundle(b, raw=dup)), files)
    bad_meta = dict(b, producer_run=True)
    assert not bundle.same_content(ModeTreeReader(with_bundle(bad_meta)), files)
    # a bool for an int (or an int for a bool) is a forgery Python's == cannot see: the
    # comparison is of canonical bytes
    assert b["contract"] == 1 and b["views"]["alpha-clip"]["counts"]["prs"] == 1
    assert b["views"]["alpha-clip"]["events"][0]["stale_sha"] is False
    for label, path, value in (("contract: true", ("contract",), True),
                               ("counts.prs: true", ("views", "alpha-clip", "counts", "prs"), True),
                               ("stale_sha: 0", ("views", "alpha-clip", "events", 0, "stale_sha"), 0)):
        swapped = copy.deepcopy(b)
        target = swapped
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        assert swapped == b and canonical.dumps_bytes(swapped) != canonical.dumps_bytes(b), label
        assert not bundle.same_content(ModeTreeReader(with_bundle(swapped)), files), label
    # a tip bundle that cannot be read at all is "different", never an exception: not UTF-8,
    # or nested deeper than the parser (100 000) or the canonical encoder (1 500) recurses
    assert not bundle.same_content(ModeTreeReader(with_bundle(b, raw=b"\xff\xfe{}")), files)
    for depth in (1500, 100_000):
        flat = canonical.dumps(dict(b, views={}))
        assert '"views": {}' in flat
        deep = flat.replace('"views": {}', '"views": ' + "[" * depth + "]" * depth, 1).encode()
        with pytest.raises(RecursionError):
            canonical.dumps_bytes(json.loads(deep))
        assert not bundle.same_content(ModeTreeReader(with_bundle(b, raw=deep)), files), depth
    # no tip; a reader that cannot report modes cannot prove sameness
    assert not bundle.same_content(None, files)
    assert not bundle.same_content(FakeTreeReader({p: d for p, (_, d) in files.items()}), files)


# ----------------------------------------------------------------------------- the derived tree

def _layout_patterns():
    subs = {"<n>": "[1-9][0-9]*", "<sha40>": "[0-9a-f]{40}", "<tag>": "[A-Za-z0-9._-]{1,100}",
            "<design>": "[a-z0-9][a-z0-9-]{0,63}"}
    out = {}
    for entry in contract()["trees"]["provenance-site"]:
        pattern = re.escape(entry)
        for k, v in subs.items():
            pattern = pattern.replace(re.escape(k), v)
        out[entry] = re.compile(pattern)
    return out


def test_derived_tree_layout(fake_episodes):
    """derived_tree_files has exactly the contract 'trees.provenance-site' layout, the guard files byte-equal .github/data-branch-guard/* (main's CURRENT bytes), FORMAT 'print-bench-provenance-site 1\n'."""
    files, b = _tree_files()
    patterns = _layout_patterns()
    hits = {entry: [] for entry in patterns}
    for path in files:
        matched = [entry for entry, rx in patterns.items() if rx.fullmatch(path)]
        assert len(matched) == 1, (path, matched)
        hits[matched[0]].append(path)
    assert all(hits.values()), {k: v for k, v in hits.items() if not v}
    assert files["vercel.json"] == ("100644", (GUARD_DIR / "vercel.json").read_bytes())
    assert files["scripts/vercel-ignore-build.sh"] == (
        "100755", (GUARD_DIR / "vercel-ignore-build.sh").read_bytes())
    assert files["FORMAT"] == ("100644", b"print-bench-provenance-site 1\n")
    assert bundle.DERIVED_FORMAT_BYTES.decode().rstrip("\n") == contract()["formats"]["derived_FORMAT"]
    assert bundle.EVIDENCE_FORMAT_BYTES.decode().rstrip("\n") == contract()["formats"]["evidence_FORMAT"]
    assert files[bundle.BUNDLE_PATH] == ("100644", canonical.dumps_bytes(b))
    assert sorted(p for p in files if p.startswith("views/")) == [
        f"views/{d}.json" for d in sorted(h.synthetic_designs())]
    for r in h.synthetic_records():
        assert files[bundle.record_path(r)] == ("100644", canonical.dumps_bytes(r))
    assert list(files) == sorted(files)
    # the pure module restates gitstore's guard table; the two must agree
    assert bundle.GUARD_MODES == {p: mode for p, (mode, _src) in gitstore.GUARD_FILES.items()}
    # negative controls
    with pytest.raises(ValueError):
        bundle.derived_tree_files(h.synthetic_records(), {}, b, {"vercel.json": GUARD["vercel.json"]})
    with pytest.raises(ValueError):
        bad = dict(GUARD, **{"scripts/vercel-ignore-build.sh": ("100644", b"x")})
        bundle.derived_tree_files(h.synthetic_records(), {}, b, bad)
    with pytest.raises(ValueError):
        twice = h.synthetic_records()
        bundle.derived_tree_files(twice + twice[:1], {}, b, GUARD)
    with pytest.raises(ValueError):
        bundle.derived_tree_files([], {"alpha-clip": {"design": "beta-hinge"}}, b, GUARD)


@needs(gitstore.guard_blobs)
def test_derived_tree_uses_mains_guard_blobs(fake_episodes):
    files, _ = _tree_files()
    guard = gitstore.guard_blobs(str(REPO))
    assert {p: files[p] for p in guard} == {p: (m, bytes(d)) for p, (m, d) in guard.items()}


def test_record_path():
    assert bundle.record_path({"kind": "pr", "pr": 510}) == "records/pr/510.json"
    assert bundle.record_path({"kind": "brief", "issue": 7}) == "records/brief/7.json"
    assert bundle.record_path({"kind": "commit", "sha": "a" * 40}) == f"records/commit/{'a' * 40}.json"
    assert bundle.record_path({"kind": "release", "tag": "v2.0"}) == "records/release/v2.0.json"
    for bad in ({"kind": "pr", "pr": "../x"}, {"kind": "pr", "pr": 0}, {"kind": "pr"},
                {"kind": "commit", "sha": "a" * 39}, {"kind": "release", "tag": ".."},
                {"kind": "release", "tag": "a/b"}, {"kind": "view", "design": "x"}):
        with pytest.raises(ValueError):
            bundle.record_path(bad)


def test_build_bundle_meta_and_digests(fake_episodes):
    files, b = _tree_files()
    assert set(b) == set(contract()["shapes"]["bundle@1"]["fields"])
    rec = {p: d for p, (_, d) in files.items() if p.startswith("records/")}
    want = canonical.content_sha256({"records": {p: canonical.sha256_hex(d) for p, d in rec.items()},
                                     "views_sha256": b["views_sha256"],
                                     "extractor": extract.EXTRACTOR_VERSION})
    assert b["content_sha256"] == want
    other = bundle.build_bundle(b["views"], records=rec, main_sha="1" * 40, evidence_sha="2" * 40,
                                producer_run=7, extractor=extract.EXTRACTOR_VERSION)
    assert other["content_sha256"] == b["content_sha256"]           # meta is not content
    for kw in ({"main_sha": "x"}, {"evidence_sha": "A" * 40}, {"producer_run": 0},
               {"producer_run": True}):
        args = dict(records=rec, main_sha="1" * 40, evidence_sha="2" * 40, producer_run=7,
                    extractor=extract.EXTRACTOR_VERSION)
        args.update(kw)
        with pytest.raises(ValueError):
            bundle.build_bundle(b["views"], **args)


# ----------------------------------------------------------------------------- derive

M1 = FIXTURE_MAIN_SHA
M2 = "2" * 40           # M1 + one commit touching only scripts/


def _main_git(designs=None):
    designs = h.synthetic_designs() if designs is None else designs
    files = {f"designs/{d}/{d}.scad": b"cube(1);\n" for d in designs}
    return FakeGitReader([
        FakeCommit(sha=M1, files=files, changed=sorted(files), committer_email="noreply@github.com"),
        FakeCommit(sha=M2, parents=[M1], files=dict(files, **{"scripts/x.sh": b"true\n"}),
                   changed=["scripts/x.sh"], committer_email="owner@example.invalid"),
    ], refs={"main": M2})


def _gz(value):
    return canonical.dumps_gz(value)


def _synthetic_evidence():
    """A tiny evidence tree whose raw docs NAME the synthetic records (the stand-in extractors
    map them back), with a revision 2, a re-run receipt attempt, a snapshot path to skip and
    the files derive must not read."""
    recs = h.synthetic_records()
    files = {"FORMAT": bundle.EVIDENCE_FORMAT_BYTES, "state.json": b"{}\n",
             "raw/snapshot/pr843/runs/ci.yml.json.gz": _gz({"rows": []})}
    for r in recs:
        if r["kind"] == "pr":
            doc = {"format": "raw-pr@1", "pr": r["pr"], "revision": 1,
                   "pull": {"merged": r["merged_at"] is not None, "merged_at": r["merged_at"],
                            "merge_commit_sha": r["merge_commit_sha"] or ("9" * 40)},
                   "commits": [{"sha": s} for rd in r["rounds"] for s in rd["commits"]]}
            files[f"raw/pr/{r['pr']}.json.gz"] = _gz(dict(doc, revision=1, stale=True))
            files[f"raw/pr/{r['pr']}.r2.json.gz"] = _gz(dict(doc, revision=2))
        elif r["kind"] == "brief":
            files[f"raw/brief/{r['issue']}.json.gz"] = _gz({"format": "raw-brief@1",
                                                            "number": r["issue"], "revision": 1})
        elif r["kind"] == "release":
            files[f"raw/release/{r['tag']}.json.gz"] = _gz({"format": "raw-release@1",
                                                            "tag": r["tag"], "revision": 1})
    files["receipts/2026/09/01/3001.a1.json.gz"] = _gz({"workflow": "auto-review.yml",
                                                        "run": {"id": 3001, "run_attempt": 1}})
    files["receipts/2026/09/01/3002.a1.json.gz"] = _gz({"workflow": "oracle.yml",
                                                        "run": {"id": 3002, "run_attempt": 1}})
    files["receipts/2026/09/01/3002.a2.json.gz"] = _gz({"workflow": "oracle.yml",
                                                        "run": {"id": 3002, "run_attempt": 2}})
    return FakeTreeReader(files)


def _context_with_receipt_run_ids(monkeypatch):
    """H3's ``ExtractContext`` carries ``auto_review_run_ids`` (wip/h3); the scaffold's does not
    yet. Until H3 is merged, give the scaffold's class that one field (default empty, as H3's)
    so the unit tests exercise derive's real call; at integration this is a no-op, and the
    @needs real-pipeline test below proves the field reaches ``trust.status_tier``."""
    import dataclasses
    if "auto_review_run_ids" in {f.name for f in dataclasses.fields(extract.ExtractContext)}:
        return
    shim = dataclasses.make_dataclass(
        "ExtractContext",
        [("auto_review_run_ids", frozenset, dataclasses.field(default=frozenset()))],
        bases=(extract.ExtractContext,), frozen=True)
    monkeypatch.setattr(extract, "ExtractContext", shim)


class _Calls:
    def __init__(self):
        self.log = []

    def add(self, *item):
        self.log.append(item)

    def names(self):
        return [c[0] for c in self.log]


def _stub_pipeline(monkeypatch, *, lazy_place=False):
    """Recording stand-ins for H3/H4. extract_* map the raw docs back to the synthetic records
    and read main ONLY through ctx.git (the direct-commit stand-in walks main's first-parent log
    for designs/ commits the way the real one does), receipt_events returns one UNPLACED job
    event for PR 510, place fills unplaced episodes from the record's first round."""
    calls = _Calls()
    def _rid(r):
        if r["kind"] == "pr":
            return str(r["pr"])
        if r["kind"] == "brief":
            return str(r["issue"])
        if r["kind"] == "commit":
            return r["sha"]
        if r["kind"] == "release":
            return r["tag"]
        raise AssertionError(r["kind"])
    by_key = {(r["kind"], _rid(r)): r for r in h.synthetic_records()}
    rows = h.synthetic_rows()
    h.patch_episodes(monkeypatch)
    _context_with_receipt_run_ids(monkeypatch)

    def extract_pr(doc, ctx):
        calls.add("extract_pr", doc["pr"], doc["revision"], ctx)
        return copy.deepcopy(by_key[("pr", str(doc["pr"]))])

    def extract_brief(doc, ctx):
        calls.add("extract_brief", doc["number"], ctx)
        return copy.deepcopy(by_key[("brief", str(doc["number"]))])

    def extract_release(doc, ctx):
        calls.add("extract_release", doc["tag"], ctx)
        return copy.deepcopy(by_key[("release", doc["tag"])])

    def extract_direct_commits(ctx, frozen):
        calls.add("extract_direct_commits", ctx, frozen)
        out = []
        for sha, _epoch in ctx.git.first_parent_log(ctx.main_sha):
            if any(p.startswith("designs/") for p in ctx.git.changed_paths(sha)) \
                    and ctx.git.committer_email(sha) != extract.GITHUB_COMMITTER and sha not in frozen:
                out.append({"kind": "commit", "sha": sha})          # never reached on this history
        return out + [copy.deepcopy(r) for (k, _), r in sorted(by_key.items()) if k == "commit"]

    class Index:
        def __init__(self, receipts):
            calls.add("ReceiptIndex", [r["run"]["id"] for r in receipts],
                      [r["run"]["run_attempt"] for r in receipts])

    def run_claims(briefs, index, *, owner_login):
        calls.add("run_claims", sorted(r["issue"] for r in briefs), owner_login)
        return {3001: 501}

    def annotate_record(record, index, codebasis, *, owner_login, claims):
        calls.add("annotate_record", record["kind"], _rid(record), claims)
        return copy.deepcopy(record)

    def receipt_events(record, index, codebasis, *, owner, repo):
        calls.add("receipt_events", _rid(record))
        if record.get("pr") != 510:
            return []
        ev = copy.deepcopy(next(e for e in record["events"] if e["id"] == "job:7001"))
        ev.update(id="job:7999", episode=None, head_sha=None)
        return [ev]

    def place(record):
        calls.add("place", _rid(record), [e["id"] for e in record["events"] if e["episode"] is None])
        out = copy.deepcopy(record)
        for e in out["events"]:
            if e["episode"] is None and not lazy_place:
                e["episode"] = record["rounds"][0]["id"]
        out["events"].sort(key=canonical.event_sort_key)
        return out

    real_build_views = views.build_views

    def build_views(records, **kw):
        calls.add("build_views", [(r["kind"], _rid(r)) for r in records])
        return real_build_views(records, **kw)

    monkeypatch.setattr(extract, "extract_pr", extract_pr)
    monkeypatch.setattr(extract, "extract_brief", extract_brief)
    monkeypatch.setattr(extract, "extract_release", extract_release)
    monkeypatch.setattr(extract, "extract_direct_commits", extract_direct_commits)
    monkeypatch.setattr(serving, "ReceiptIndex", Index)
    monkeypatch.setattr(serving, "run_claims", run_claims)
    monkeypatch.setattr(serving, "annotate_record", annotate_record)
    monkeypatch.setattr(serving, "receipt_events", receipt_events)
    monkeypatch.setattr(episodes, "place", place)
    monkeypatch.setattr(episodes, "decision_rows",
                        lambda git, main_sha, design, **kw: copy.deepcopy(rows.get(design, [])))
    monkeypatch.setattr(views, "build_views", build_views)
    return calls


def _derive(evidence, main_sha=M1, git=None, **kw):
    args = dict(git=git or _main_git(), codebasis=FakeCodeBasis(), main_sha=main_sha, owner=OWNER,
                repo=REPO_NAME, owner_login=OWNER_LOGIN, evidence_sha="e" * 40, producer_run=5,
                edit_grace_seconds=60, guard=GUARD)
    args.update(kw)
    return bundle.derive(evidence, **args)


def test_derive_order(monkeypatch):
    """Critique 14: with monkeypatched extract/serving/episodes/views recording calls, derive calls extract_* → run_claims → annotate_record(claims=…) → receipt_events → place → build_views, in that order, and stores no unplaced event."""
    calls = _stub_pipeline(monkeypatch)
    tree = _derive(_synthetic_evidence())
    names = calls.names()
    phases = ["extract", "ReceiptIndex", "run_claims", "annotate_record", "receipt_events",
              "place", "build_views"]
    rank = [phases.index("extract" if n.startswith("extract_") else n) for n in names]
    assert rank == sorted(rank), names
    assert set(names) == {"extract_pr", "extract_brief", "extract_release", "extract_direct_commits",
                          "ReceiptIndex", "run_claims", "annotate_record", "receipt_events",
                          "place", "build_views"}
    log = calls.log
    # the highest revision per raw key, highest attempt per receipt run
    assert sorted((c[1], c[2]) for c in log if c[0] == "extract_pr") == [
        (510, 2), (511, 2), (512, 2), (513, 2)]
    assert [c for c in log if c[0] == "ReceiptIndex"][0][1:] == ([3001, 3002], [1, 2])
    # the context comes from the raw documents: merged PRs only, brief numbers from raw/brief/
    ctx = next(c for c in log if c[0] == "extract_pr")[3]
    assert ctx.brief_numbers == frozenset({501, 520, 530})
    merged = {r["merge_commit_sha"]: r["pr"] for r in h.synthetic_records()
              if r["kind"] == "pr" and r["merged_at"]}
    assert ctx.merge_shas == merged and "9" * 40 not in ctx.merge_shas
    assert ctx.design_names == frozenset(h.synthetic_designs()) and ctx.main_sha == M1
    assert ctx.owner_login == OWNER_LOGIN and ctx.edit_grace_seconds == 60
    # status_tier's receipt half: the auto-review.yml receipts' run ids, nothing else
    assert ctx.auto_review_run_ids == frozenset({3001})
    ctx_at = {"extract_pr": 3, "extract_brief": 2, "extract_release": 2, "extract_direct_commits": 1}
    assert all(c[ctx_at[c[0]]] is ctx for c in log if c[0] in ctx_at)     # one context for all
    frozen = next(c for c in log if c[0] == "extract_direct_commits")[2]
    assert frozen == {s for r in h.synthetic_records() if r["kind"] == "pr"
                      for rd in r["rounds"] for s in rd["commits"]}
    # claims flow into every annotate_record; receipt_events only for PR records
    assert {c[3] == {3001: 501} for c in log if c[0] == "annotate_record"} == {True}
    assert len([c for c in log if c[0] == "annotate_record"]) == 9
    assert sorted(c[1] for c in log if c[0] == "receipt_events") == ["510", "511", "512", "513"]
    # place saw the unplaced receipt event; nothing unplaced is stored
    assert [c[2] for c in log if c[0] == "place" and c[1] == "510"] == [["job:7999"]]
    for r in tree.records:
        assert all(e["episode"] is not None for e in r["events"])
    stored = [json.loads(d) for p, (_, d) in tree.files.items() if p.startswith("records/")]
    assert all(e["episode"] is not None for r in stored for e in r["events"])
    job = next(e for r in stored if r["kind"] == "pr" and r["pr"] == 510 for e in r["events"]
               if e["id"] == "job:7999")
    assert job["episode"] == next(r for r in stored if r.get("pr") == 510)["rounds"][0]["id"]
    assert tree.counts["records"] == 9 and tree.counts["receipts"] == 2
    assert tree.counts["views"] == 3 and tree.bundle == json.loads(tree.files[bundle.BUNDLE_PATH][1])
    assert (tree.bundle["main_sha"], tree.bundle["evidence_sha"], tree.bundle["producer_run"]) == (
        M1, "e" * 40, 5)


def test_derive_passes_the_auto_review_receipts_run_ids(monkeypatch):
    """ExtractContext.auto_review_run_ids = run.id of every auto-review.yml receipt (a stub too,
    at its highest attempt) and of nothing else; negative control: the same evidence with no
    auto-review.yml receipt hands extraction an empty set (no status can be receipt-verified)."""
    calls = _stub_pipeline(monkeypatch)
    evidence = _synthetic_evidence()
    evidence.files["receipts/2026/09/02/3003.a1.json.gz"] = _gz(
        {"workflow": "auto-review.yml", "kind": "stub", "run": {"id": 3003, "run_attempt": 1}})
    evidence.files["receipts/2026/09/02/3003.a2.json.gz"] = _gz(
        {"workflow": "auto-review.yml", "kind": "stub", "run": {"id": 3003, "run_attempt": 2}})
    _derive(evidence)
    ctxs = {c[-1].auto_review_run_ids for c in calls.log if c[0] in ("extract_pr", "extract_brief",
                                                                      "extract_release")}
    assert ctxs == {frozenset({3001, 3003})}
    # negative control: every auto-review.yml receipt relabelled as another workflow
    calls.log.clear()
    for path in [p for p in evidence.files if p.startswith("receipts/")]:
        doc = canonical.loads_gz(evidence.files[path])
        if doc["workflow"] == "auto-review.yml":
            evidence.files[path] = _gz(dict(doc, workflow="design-run.yml"))
    _derive(evidence)
    ctx = next(c for c in calls.log if c[0] == "extract_pr")[3]
    assert ctx.auto_review_run_ids == frozenset()


def test_derive_refuses_an_unplaced_event(monkeypatch):
    _stub_pipeline(monkeypatch, lazy_place=True)
    with pytest.raises(ValueError, match="unplaced"):
        _derive(_synthetic_evidence())


def test_derive_refuses_a_corrupt_evidence_path(monkeypatch):
    _stub_pipeline(monkeypatch)
    for bad in ("raw/pr/510.r1.json.gz", "raw/pr/abc.json.gz", "raw/notes.txt",
                "receipts/2026/09/01/3001.json.gz"):
        evidence = _synthetic_evidence()
        evidence.files[bad] = _gz({})
        with pytest.raises(ValueError):
            _derive(evidence)


def test_rerun_with_unchanged_inputs_pushes_nothing(monkeypatch):
    """A second derive over the same evidence + main gives an identical tree (P1d)."""
    _stub_pipeline(monkeypatch)
    first = _derive(_synthetic_evidence())
    second = _derive(_synthetic_evidence())
    assert first.files == second.files and first.bundle == second.bundle
    assert bundle.same_content(ModeTreeReader(first.files), second.files)
    # negative control: one changed input record is a different tree
    evidence = _synthetic_evidence()
    del evidence.files["raw/brief/530.json.gz"]
    third = _derive(evidence)
    assert not bundle.same_content(ModeTreeReader(first.files), third.files)


def test_main_commit_outside_designs_changes_nothing(monkeypatch):
    """Critique 6: derive over the same evidence against main M and against M' = M + one commit touching only scripts/ gives the same tree except the bundle's main_sha, same_content True, content_sha256 equal — so no derived push."""
    _stub_pipeline(monkeypatch)
    git = _main_git()
    on_m = _derive(_synthetic_evidence(), main_sha=M1, git=git)
    on_m2 = _derive(_synthetic_evidence(), main_sha=M2, git=git)
    assert on_m.bundle["main_sha"] == M1 and on_m2.bundle["main_sha"] == M2
    assert on_m.bundle["content_sha256"] == on_m2.bundle["content_sha256"]
    differing = sorted(p for p in on_m.files if on_m.files[p] != on_m2.files.get(p))
    assert differing == [bundle.BUNDLE_PATH] and set(on_m.files) == set(on_m2.files)
    assert bundle.same_content(ModeTreeReader(on_m.files), on_m2.files)
    # negative control: a main commit that adds a design DOES change the tree
    files = {f"designs/{d}/{d}.scad": b"cube(1);\n" for d in h.synthetic_designs()}
    grown = FakeGitReader([FakeCommit(sha=M1, files=files),
                           FakeCommit(sha=M2, parents=[M1],
                                      files=dict(files, **{"designs/delta-new/delta-new.scad": b"x"}),
                                      changed=["designs/delta-new/delta-new.scad"])])
    on_grown = _derive(_synthetic_evidence(), main_sha=M2, git=grown)
    assert "views/delta-new.json" in on_grown.files
    assert not bundle.same_content(ModeTreeReader(on_m.files), on_grown.files)


def _fixture_evidence(drop_workflow=None):
    """The committed raw + receipt fixtures as an evidence tree (``drop_workflow``: leave out
    every receipt of that workflow — a negative control's input)."""
    files = {}
    for kind in ("pr", "brief", "release"):
        for p in sorted((h.FIXTURES / "raw" / kind).glob("*.json.gz")):
            files[f"raw/{kind}/{p.name}"] = p.read_bytes()
    for p in receipt_paths():
        data = p.read_bytes()
        if drop_workflow is not None and canonical.loads_gz(data).get("workflow") == drop_workflow:
            continue
        files[str(p.relative_to(h.FIXTURES)).replace(os.sep, "/")] = data
    return FakeTreeReader(files)


def _fixture_designs():
    return sorted({f["filename"].split("/")[1] for n in (636, 371, 397, 634, 343, 316)
                   for f in raw_pr(n)["files"] if f["filename"].startswith("designs/")
                   and f["filename"].count("/") >= 2})


M3 = "3" * 40           # M2 + one commit appending a decision row to one design's PM.md
_PM = ("# PM\n\n## Decision log\n\n| Date | Decision | Reason |\n| --- | --- | --- |\n"
       "| 2026-09-01 | Keep the snap fit | The field test held |\n").encode()
_PM_ROW = b"| 2026-09-20 | Thicken the wall | The drop test cracked it |\n"


def _main_git_with_rows(designs):
    """``_main_git``'s M1 -> M2 (scripts/ only) with a committed decision row in the first
    design's PM.md, added in M1 (blame names M1 at every main), plus M3 = M2 + a commit
    appending a second row (blame: M1's lines, then M3's)."""
    files = {f"designs/{d}/{d}.scad": b"cube(1);\n" for d in designs}
    pm = f"designs/{designs[0]}/PM.md"
    files[pm] = _PM
    old = [(M1, i + 1) for i in range(_PM.count(b"\n"))]
    m2_files = dict(files, **{"scripts/x.sh": b"true\n"})
    return FakeGitReader([
        FakeCommit(sha=M1, files=files, changed=sorted(files), committer_email="noreply@github.com",
                   blame={pm: old}),
        FakeCommit(sha=M2, parents=[M1], files=m2_files, changed=["scripts/x.sh"],
                   committer_email="owner@example.invalid", blame={pm: old}),
        FakeCommit(sha=M3, parents=[M2], subject="Log a decision (#640)",
                   files=dict(m2_files, **{pm: _PM + _PM_ROW}), changed=[pm],
                   blame={pm: old + [(M3, len(old) + 1)]}),
    ], refs={"main": M3})


_REAL_PIPELINE = (extract.extract_pr, extract.extract_brief, extract.extract_release,
                  extract.extract_direct_commits, serving.ReceiptIndex, serving.run_claims,
                  serving.annotate_record, serving.receipt_events, episodes.place,
                  episodes.decision_rows, episodes.episodes_of, episodes.rounds_from_record)


@needs(*_REAL_PIPELINE)
def test_main_commit_outside_designs_changes_nothing_real():
    """The same property through the REAL extract/serving/episodes over the committed raw and
    receipt fixtures plus a committed decision row on main: M' = M + a scripts/-only commit
    leaves every record and view byte-identical (the row included — it names the commit that
    added it, never main). Negative control: a main commit that ADDS a decision row changes that
    design's view (and only it), so the identity above is not vacuous."""
    designs = _fixture_designs()
    git = _main_git_with_rows(designs)
    a = _derive(_fixture_evidence(), main_sha=M1, git=git)
    b = _derive(_fixture_evidence(), main_sha=M2, git=git)
    assert sorted(p for p in a.files if a.files[p] != b.files.get(p)) == [bundle.BUNDLE_PATH]
    assert a.bundle["content_sha256"] == b.bundle["content_sha256"]
    assert bundle.same_content(ModeTreeReader(a.files), b.files)
    assert all(e["episode"] is not None for r in a.records for e in r["events"])
    view = f"views/{designs[0]}.json"

    def pm_rows(tree):
        return [e for e in json.loads(tree.files[view][1])["events"] if e["kind"] == "decision.pm_log"]

    assert [r["fields"]["added_in_sha"] for r in pm_rows(b)] == [M1]
    # negative control: M3 appends a row
    c = _derive(_fixture_evidence(), main_sha=M3, git=git)
    assert sorted(p for p in b.files if b.files[p] != c.files.get(p)) == [bundle.BUNDLE_PATH, view]
    assert sorted(r["fields"]["added_in_sha"] for r in pm_rows(c)) == sorted([M1, M3])
    assert b.bundle["content_sha256"] != c.bundle["content_sha256"]
    assert not bundle.same_content(ModeTreeReader(b.files), c.files)


def _signoff_status_tiers(tree):
    return collections.Counter((e["trust"], e["trust_basis"]) for r in tree.records
                               for e in r["events"] if e["kind"] == "status.reviewer_signoff")


@needs(*_REAL_PIPELINE, trust.status_tier)
def test_derive_receipt_verifies_reviewer_signoff_statuses_real():
    """Through the REAL pipeline over the committed fixtures, every status.reviewer_signoff is
    verified/actions-status+receipt: derive hands extraction the auto-review.yml receipts' run
    ids (ExtractContext.auto_review_run_ids), the receipt half of trust.status_tier. Negative
    control: the same evidence without its auto-review.yml receipts verifies none of them."""
    git = _main_git(_fixture_designs())
    tiers = _signoff_status_tiers(_derive(_fixture_evidence(), git=git))
    assert sum(tiers.values()) > 0
    assert set(tiers) == {("verified", "actions-status+receipt")}, tiers
    without = _signoff_status_tiers(_derive(_fixture_evidence(drop_workflow="auto-review.yml"),
                                            git=git))
    assert sum(without.values()) == sum(tiers.values())
    assert ("verified", "actions-status+receipt") not in without, without
