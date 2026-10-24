"""ingest — the #843 snapshot (tests use fixtures/snapshot-mini, same formats; the real one is on main).

Owner: H1 (the placeholders). Each placeholder's docstring is its
acceptance criterion (docs/provenance.md §INGEST, the critique round's items
1, 2, 8, 17, 19); replace the skip with the test. The pin test below is live.
"""

from __future__ import annotations

import ast
import gzip
import hashlib
import io
import json
import re
import shutil
import tarfile

import pytest

from conftest import REPO, TOOL, needs

from provenance import canonical, contract, ingest, receipts


def _conf_value(key: str) -> str:
    text = (REPO / ".github" / "provenance.conf").read_text(encoding="utf-8")
    m = re.search(rf"^{key}: (\S+)$", text, re.M)
    assert m, key
    return m.group(1)


def test_conf_pins_the_snapshot_on_main():
    """Critique 1: the committed snapshot directory's MANIFEST.sha256 hashes to the conf's pin (a
    textual read — conf.py is H6's). If this fails, someone changed the snapshot or the pin."""
    d = REPO / _conf_value("snapshot_dir")
    assert hashlib.sha256((d / "MANIFEST.sha256").read_bytes()).hexdigest() == _conf_value("snapshot_manifest_sha256")
    assert re.fullmatch(r"[0-9a-f]{40}", _conf_value("snapshot_commit"))
    for name in ("runs.tar", "jobs.tar", "sha.tar"):
        assert (d / name).is_file(), name


# ---------------------------------------------------------------------------

MINI = TOOL / "tests" / "fixtures" / "snapshot-mini"
MINI_PIN = "0da7f326fb3d57ad8968a56b30e3b3831a1d181b32b3ce0193ea22235ea3d0a0"
WATCHED = ("auto-review.yml", "backlog-burn.yml", "design-run.yml")
SID = "pr843"


def _copy(tmp_path):
    d = tmp_path / "snap"
    shutil.copytree(MINI, d)
    return d


def _remanifest(d) -> str:
    """Recompute MANIFEST.sha256 so the directory is internally consistent; return its digest."""
    lines = []
    for p in sorted(d.iterdir()):
        if p.name == "MANIFEST.sha256" or not p.is_file():
            continue
        lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    (d / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")
    return hashlib.sha256((d / "MANIFEST.sha256").read_bytes()).hexdigest()


def _tar(members: list[tarfile.TarInfo | tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        for m in members:
            if isinstance(m, tarfile.TarInfo):
                tf.addfile(m)
            else:
                info = tarfile.TarInfo(m[0])
                info.size = len(m[1])
                tf.addfile(info, io.BytesIO(m[1]))
    return buf.getvalue()


def _gzjson(value) -> bytes:
    return gzip.compress(json.dumps(value).encode(), mtime=0)


def _read(d=MINI, pin=MINI_PIN):
    return ingest.read_snapshot(str(d), SID, pin)


def test_manifest_mismatch_refuses(tmp_path):
    """One flipped byte in runs.tar → IngestError, nothing planned."""
    d = _copy(tmp_path)
    data = bytearray((d / "runs.tar").read_bytes())
    data[600] ^= 0x01
    (d / "runs.tar").write_bytes(bytes(data))
    assert ingest.verify_manifest(str(MINI), MINI_PIN) == MINI_PIN           # control: the original passes
    with pytest.raises(ingest.IngestError, match="runs.tar sha256"):
        _read(d)
    (d / "runs.tar").unlink()
    with pytest.raises(ingest.IngestError, match="runs.tar is missing"):
        _read(d)


def test_consistent_but_unpinned_snapshot_refuses(tmp_path):
    """Critique 2: a copy of snapshot-mini with a modified runs.tar AND a recomputed, internally consistent MANIFEST.sha256 → IngestError (its manifest digest is not the pin)."""
    d = _copy(tmp_path)
    forged_row = {"conclusion": "success", "created_at": "2026-10-12T00:00:00Z", "event": "schedule", "id": 1,
                  "run_attempt": 1, "status": "completed"}
    (d / "runs.tar").write_bytes(_tar([("design-run.yml.json.gz", _gzjson([forged_row]))]))
    digest = _remanifest(d)
    assert digest != MINI_PIN
    with pytest.raises(ingest.IngestError, match="not the pinned"):
        _read(d)
    assert ingest.verify_manifest(str(d), digest) == digest   # control: internally consistent
    # A required tar the manifest does not list is refused even when the pin matches.
    lines = [ln for ln in (d / "MANIFEST.sha256").read_text().splitlines() if not ln.endswith("  sha.tar")]
    (d / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")
    pin = hashlib.sha256((d / "MANIFEST.sha256").read_bytes()).hexdigest()
    with pytest.raises(ingest.IngestError, match="sha.tar is not covered"):
        ingest.verify_manifest(str(d), pin)


def _member_dir(tmp_path, member) -> tuple[str, str]:
    d = tmp_path / "bad"
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(MINI, d)
    (d / "sha.tar").write_bytes(_tar([member]))
    return str(d), _remanifest(d)


def test_tar_members_are_regular_and_named(tmp_path):
    """Critique 2: a tar holding a symlink, a directory, '../x.json.gz', 'a/b.json.gz' or 'x.json' → IngestError; members are read with extractfile only (no extract/extractall call in ingest.py — an AST check)."""
    sym = tarfile.TarInfo("link.json.gz")
    sym.type, sym.linkname = tarfile.SYMTYPE, "/etc/passwd"
    dirm = tarfile.TarInfo("d.json.gz")
    dirm.type = tarfile.DIRTYPE
    payload = _gzjson({"check_runs": [], "sha": "a" * 40, "statuses": []})
    bad = [sym, dirm, ("../x.json.gz", payload), ("a/b.json.gz", payload), ("x.json", payload)]
    for member in bad:
        d, pin = _member_dir(tmp_path, member)
        with pytest.raises(ingest.IngestError):
            ingest.read_snapshot(d, SID, pin)
    # Control: a well-named regular member passes the same path.
    d, pin = _member_dir(tmp_path, (f"{'a' * 40}.json.gz", payload))
    assert ingest.read_snapshot(d, SID, pin).statuses == {"a" * 40: []}
    # A member whose content names another sha is refused too.
    d, pin = _member_dir(tmp_path, (f"{'b' * 40}.json.gz", payload))
    with pytest.raises(ingest.IngestError, match="names sha"):
        ingest.read_snapshot(d, SID, pin)
    tree = ast.parse((TOOL / "src" / "provenance" / "ingest.py").read_text(encoding="utf-8"))
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "extractfile" in calls and not ({"extract", "extractall", "makefile", "_extract_member"} & calls)


def _plan(data, existing=lambda p: None, cursors=None):
    return ingest.plan_ingest(data, watched=WATCHED, commit="4" * 40, cursors=cursors or {}, existing=existing)


def test_mapping_writes_receipts_runs_and_statuses():
    """snapshot-mini plans receipts for its watched runs (31364447108 full, 34661448637 full, the skipped row none), raw/snapshot/pr843/runs/ci.yml.json.gz and raw/snapshot/pr843/statuses/<sha>.json.gz for each sha with statuses; prcommits/pulls/workflows are not ingested."""
    data = _read()
    plan = _plan(data)
    shas = sorted(sha for sha, st in data.statuses.items() if st)
    assert sorted(plan.files) == sorted([
        "receipts/2026/08/10/31364447108.a1.json.gz", "receipts/2026/09/12/34661448637.a2.json.gz",
        "receipts/2026/10/11/38161046420.a1.json.gz", "raw/snapshot/pr843/runs/ci.yml.json.gz",
        *(f"raw/snapshot/pr843/statuses/{sha}.json.gz" for sha in shas)])
    kinds = {p: receipts.load_receipt(b)["kind"] for p, b in plan.files.items() if p.startswith("receipts/")}
    assert kinds["receipts/2026/08/10/31364447108.a1.json.gz"] == "full"
    assert kinds["receipts/2026/09/12/34661448637.a2.json.gz"] == "full"
    assert plan.skipped_runs == 1 and plan.missing_jobs == 0 and plan.conflicts == 0
    assert plan.receipts_full + plan.receipts_stub == 3 and plan.statuses == len(shas) == 2 and plan.runs_listings == 1
    runs_doc = canonical.loads_gz(plan.files["raw/snapshot/pr843/runs/ci.yml.json.gz"])
    assert runs_doc["format"] == "raw-snapshot-runs@1" and runs_doc["workflow"] == "ci.yml"
    assert len(runs_doc["runs"]) == len(data.runs["ci.yml"]) == 6
    assert not any(p.startswith(("raw/snapshot/pr843/runs/design-run", "prcommits", "pulls")) for p in plan.files)
    # A watched run whose jobs.tar member is missing is counted and skipped.
    data.jobs.pop(31364447108)
    assert _plan(data).missing_jobs == 1
    # An unwatched workflow plans nothing.
    assert not [p for p in ingest.plan_ingest(data, watched=("oracle.yml",), commit="4" * 40, cursors={},
                                              existing=lambda p: None).files if p.startswith("receipts/")]


def test_snapshot_receipt_equals_live_shape():
    """A receipt built from a snapshot row validates against receipt@1 and differs from a live one only in 'source'."""
    data = _read()
    row = next(r for r in data.runs["design-run.yml"] if r["id"] == 34661448637)
    snap = receipts.build_receipt("design-run.yml", row, data.jobs[row["id"]], f"snapshot:{SID}")
    live_row = json.loads(json.dumps(row))
    live_row["actor"] = {"login": live_row["actor"], "type": "User"} if isinstance(live_row.get("actor"), str) else live_row.get("actor")
    live_row["extra_api_field"] = {"ignored": True}
    live = receipts.build_receipt("design-run.yml", live_row, list(reversed(data.jobs[row["id"]])), "live")
    diff = {k for k in snap if snap[k] != live[k]}
    assert diff == {"source"} and snap["source"] == "snapshot:pr843" and live["source"] == "live"
    assert canonical.loads_gz(_plan(data).files[receipts.receipt_path(row)]) == snap


@needs(contract.validate)
def test_ingested_documents_validate():
    data = _read()
    for path, blob in _plan(data).files.items():
        doc = canonical.loads_gz(blob)
        shape = doc["format"]
        assert contract.validate(shape, doc) == [], path


def test_cursors_rise_to_snapshot_end():
    """Critique 8: plan_ingest raises every watched workflow's receipts cursor to snapshot_end (the latest row created_at — 2026-10-13T06:13:35Z for the real snapshot) and never lowers a later one."""
    data = _read()
    every = [r["created_at"] for rows in data.runs.values() for r in rows]
    assert data.snapshot_end == max(every) == "2026-10-11T17:46:29Z"
    plan = _plan(data, cursors={"auto-review.yml": "2026-10-12T00:00:00Z", "design-run.yml": "2026-09-01T00:00:00Z"})
    assert plan.cursors == {"backlog-burn.yml": data.snapshot_end, "design-run.yml": data.snapshot_end}
    assert plan.state_entry["snapshot_end"] == data.snapshot_end


def test_real_snapshot_end_and_counts():
    """The committed snapshot on main (read through the conf's pin): its end is 2026-10-13T06:13:35Z
    and the nine watched workflows map to the documented 1,635 full / 2,103 stub receipts and
    1,689 status files (docs/provenance.md §Sizes)."""
    d = REPO / _conf_value("snapshot_dir")
    data = ingest.read_snapshot(str(d), SID, _conf_value("snapshot_manifest_sha256"))
    assert data.snapshot_end == "2026-10-13T06:13:35Z"
    watched = tuple(w.strip() for w in re.search(r"^watched_workflows: (.+)$", (REPO / ".github" / "provenance.conf")
                                                  .read_text(encoding="utf-8"), re.M).group(1).split(","))
    plan = ingest.plan_ingest(data, watched=watched, commit=_conf_value("snapshot_commit"), cursors={},
                              existing=lambda p: None)
    assert (plan.receipts_full, plan.receipts_stub, plan.statuses, plan.runs_listings) == (1635, 2103, 1689, 1)
    assert plan.missing_jobs == 0 and plan.skipped_runs == 351


def test_ingest_is_idempotent_on_content():
    """A second ingest over an evidence tree that already holds the first plans zero files — including when the existing .gz blobs were written at another gzip level (identity is the decompressed bytes, critique 19); a path present with different CONTENT is counted as a conflict and never modified; needs_ingest is false for the recorded version and true for INGEST_VERSION + 1."""
    data = _read()
    first = _plan(data)
    regz = {p: gzip.compress(gzip.decompress(b), compresslevel=1, mtime=7) for p, b in first.files.items()}
    assert all(regz[p] != first.files[p] for p in regz)
    again = _plan(data, existing=regz.get)
    assert again.files == {} and again.receipts_existing == 3 and again.conflicts == 0
    assert again.state_entry == first.state_entry                    # same counts: it holds them all
    live = dict(regz)
    p = "receipts/2026/08/10/31364447108.a1.json.gz"
    doc = canonical.loads_gz(first.files[p])
    live[p] = canonical.dumps_gz(dict(doc, source="live"))           # a live receipt captured first
    third = _plan(data, existing=live.get)
    assert third.files == {} and third.conflicts == 1 and third.state_entry["receipts"] == 2
    state = {"ingested": {SID: first.state_entry}}
    assert not ingest.needs_ingest(state, SID)
    assert ingest.needs_ingest({"ingested": {}}, SID)
    assert ingest.needs_ingest({"ingested": {SID: dict(first.state_entry, version=ingest.INGEST_VERSION - 1)}}, SID)
    bumped = dict(first.state_entry, version=ingest.INGEST_VERSION)
    orig = ingest.INGEST_VERSION
    try:
        ingest.INGEST_VERSION = orig + 1
        assert ingest.needs_ingest({"ingested": {SID: bumped}}, SID)
    finally:
        ingest.INGEST_VERSION = orig


def test_check_runs_are_dropped_and_counted():
    """raw-snapshot-statuses@1 carries check_runs_dropped = the member's check-run count; no check-run output reaches a stored byte."""
    data = _read()
    plan = _plan(data)
    with tarfile.open(MINI / "sha.tar") as tf:
        members = {m.name[:40]: json.loads(gzip.decompress(tf.extractfile(m).read())) for m in tf.getmembers()}
    for sha, member in members.items():
        doc = canonical.loads_gz(plan.files[f"raw/snapshot/{SID}/statuses/{sha}.json.gz"])
        assert doc["check_runs_dropped"] == len(member["check_runs"]) > 0
        assert set(doc) == {"check_runs_dropped", "format", "sha", "snapshot", "statuses"}
        assert len(doc["statuses"]) == len(member["statuses"])
        blob = gzip.decompress(plan.files[f"raw/snapshot/{SID}/statuses/{sha}.json.gz"])
        assert b"check_runs\"" not in blob.replace(b"check_runs_dropped\"", b"")
        for cr in member["check_runs"]:
            assert f'"id": {cr["id"]}'.encode() not in blob          # no check-run object survives
        for st in doc["statuses"]:
            if st["context"] != "reviewer-signoff":
                assert st["description"] is None
