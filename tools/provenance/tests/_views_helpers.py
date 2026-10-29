"""Helpers shared by test_views.py and test_bundle.py (H5).

* the SYNTHETIC records under ``fixtures/records/`` — hand-authored, prose-free,
  contract-valid: ``pr/``, ``brief/``, ``commit/``, ``release/`` (record@1, one
  file per record), ``rows/<design>.json`` (the committed-row events of one
  design, a list of event@1) and ``designs.json`` (the designs "on main",
  including the zero-history ``gamma-stand``);
* deterministic stand-ins for ``episodes.episodes_of`` / ``rounds_from_record``
  (H3's), used ONLY inside unit tests through ``monkeypatch`` so the fold logic
  is tested without H3; the fixture-bundle byte test uses the real ones
  (``@needs``);
* the fixture bundle builder (one function, so the byte test and the update
  path cannot drift) and a Node runner for site/lib/provenance-contract.mjs.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
from typing import Any, Optional

from conftest import FIXTURE_MAIN_SHA, FIXTURES, OWNER, REPO, REPO_NAME

from provenance import bundle, canonical, extract, views
from provenance.protocols import Round

RECORDS = FIXTURES / "records"
FIXTURE_BUNDLE = REPO / "site" / "test" / "fixtures" / "provenance-bundle.json"
NODE_VALIDATOR = REPO / "site" / "lib" / "provenance-contract.mjs"
FIXTURE_EVIDENCE_SHA = "0" * 40
FIXTURE_PRODUCER_RUN = 1
RECORD_KINDS = ("pr", "brief", "commit", "release")


def synthetic_records() -> list[dict[str, Any]]:
    out = []
    for kind in RECORD_KINDS:
        for path in sorted((RECORDS / kind).glob("*.json")):
            out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def synthetic_rows() -> dict[str, list[dict[str, Any]]]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((RECORDS / "rows").glob("*.json"))}


def synthetic_designs() -> list[str]:
    return json.loads((RECORDS / "designs.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- episode stand-ins

def fake_rounds_from_record(record: dict[str, Any]) -> list[Round]:
    if record.get("kind") != "pr":
        return []
    return [Round(r["id"], r["head"], tuple(r["heads"]), tuple(r["commits"]), r["pushed_at"],
                  r["start"], r["end"]) for r in record.get("rounds", [])]


_KIND = {"E0": "brief", "R": "round", "M": "merge", "C": "commit", "D": "day"}


def fake_episodes_of(events: list[dict[str, Any]], rounds_: list[Round]) -> list[dict[str, Any]]:
    """Group placed events by episode (episodes.py's documented output shape)."""
    by_id: dict[str, list[dict[str, Any]]] = {}
    for r in rounds_:
        by_id.setdefault(r.id, [])
    for e in sorted(events, key=canonical.event_sort_key):
        by_id.setdefault(e["episode"], []).append(e)
    round_of = {r.id: r for r in rounds_}
    out = []
    for ep, evs in by_id.items():
        prefix = ep.split(":", 1)[0]
        ts = [e["ts"] for e in evs]
        entry = {"id": ep, "kind": _KIND[prefix], "pr": None, "issue": None, "head": None,
                 "start": min(ts) if ts else None, "end": max(ts) if ts else None,
                 "events": [e["id"] for e in evs]}
        if prefix == "R":
            r = round_of.get(ep)
            entry.update(pr=int(ep.split(":")[1]))
            if r is not None:
                entry.update(head=r.head, start=r.start, end=r.end)
        elif prefix == "M":
            entry["pr"] = int(ep.split(":")[1])
        elif prefix == "E0":
            entry["issue"] = int(ep.split(":")[2])
        elif prefix == "C":
            shas = [e["sha"] for e in evs if e.get("sha")]
            entry["head"] = shas[0] if shas else None
        out.append(entry)
    return sorted(out, key=lambda x: (x["start"] is None, x["start"] or "", x["id"]))


def patch_episodes(monkeypatch) -> None:
    from provenance import episodes
    monkeypatch.setattr(episodes, "episodes_of", fake_episodes_of)
    monkeypatch.setattr(episodes, "rounds_from_record", fake_rounds_from_record)


# --------------------------------------------------------------------------- fixture bundle

def fixture_views(records: Optional[list[dict[str, Any]]] = None) -> dict[str, dict[str, Any]]:
    records = synthetic_records() if records is None else records
    rows = synthetic_rows()
    return {d: views.build_view(d, records=records, rows=rows.get(d, []), owner=OWNER,
                                repo=REPO_NAME) for d in synthetic_designs()}


def fixture_bundle() -> dict[str, Any]:
    """The bundle@1 of the synthetic records with the fixed meta (bundle.py docstring)."""
    records = synthetic_records()
    rec_bytes = {bundle.record_path(r): canonical.dumps_bytes(r) for r in records}
    return bundle.build_bundle(fixture_views(records), records=rec_bytes,
                               main_sha=FIXTURE_MAIN_SHA, evidence_sha=FIXTURE_EVIDENCE_SHA,
                               producer_run=FIXTURE_PRODUCER_RUN,
                               extractor=extract.EXTRACTOR_VERSION)


def fixture_bundle_bytes() -> bytes:
    return canonical.dumps_bytes(fixture_bundle())


# --------------------------------------------------------------------------- the Node validator

_NODE_SCRIPT = (
    "const [shape, file] = process.argv.slice(1);"
    "const { validate } = await import(%s);"
    "const { readFileSync } = await import('node:fs');"
    "process.stdout.write(JSON.stringify(validate(shape, JSON.parse(readFileSync(file, 'utf8')))));"
)


def node() -> Optional[str]:
    return shutil.which("node")


def node_validate(shape: str, value: Any, tmp_path: pathlib.Path) -> list[str]:
    """``validate(shape, value)`` of site/lib/provenance-contract.mjs, via ``node``."""
    exe = node()
    if exe is None:
        raise RuntimeError("node is not on PATH")
    target = tmp_path / f"node-input-{len(list(tmp_path.iterdir()))}.json"
    target.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    script = _NODE_SCRIPT % json.dumps(NODE_VALIDATOR.as_uri())
    done = subprocess.run([exe, "--input-type=module", "-e", script, shape, str(target)],
                          capture_output=True, text=True, timeout=60, check=False)
    if done.returncode != 0:
        raise RuntimeError(f"node failed ({done.returncode}): {done.stderr}")
    return json.loads(done.stdout)
