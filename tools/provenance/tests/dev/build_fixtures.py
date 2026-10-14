#!/usr/bin/env python3
"""Regenerate the committed provenance fixtures from an UNCOMMITTED raw capture.

Dev-only (never run in CI): the inputs carry comment bodies, which must never
be committed. This script reads them, projects + digests them through the
package's own ``rawdoc`` / ``digest`` / ``canonical`` modules (so the
fixtures are byte-for-byte what the harvester itself would store), and writes
only digested, prose-free files under ``tools/provenance/tests/fixtures/``:

=================================  ===============================================
fixtures/raw/pr/<n>.json.gz        raw-pr@1 for PRs 636, 371, 397, 634, 343, 316
fixtures/raw/brief/<n>.json.gz     raw-brief@1 for the briefs those PRs close
fixtures/raw/release/<tag>.json.gz raw-release@1 for every release
fixtures/receipts/Y/M/D/<id>.a<k>  receipt@1 for the fixture runs (snapshot jobs)
fixtures/codebasis/index.json      {sha40: {path: blob sha256}} + blobs/<sha256>.gz
fixtures/main_history.json.gz      main's commits since 2026-07-31 (sha, parents,
                                   committer date) + path-touch sets
fixtures/membership/pr_files.json.gz  {pr: {state, merged_at, title, files}} for
                                   every PR in the audit's membership.csv
fixtures/snapshot-mini/            a miniature #843-format snapshot (real rows,
                                   check-run output nulled) for ingest tests
=================================  ===============================================

Usage (from the repo root)::

    PYTHONPATH=tools/provenance/src python3 tools/provenance/tests/dev/build_fixtures.py \\
        --raw <scratch>/harvester/raw --snapshot <scratch>/harvester/snap \\
        --out tools/provenance/tests/fixtures [--check]

``--check`` regenerates into a temp dir and exits 1 if any committed fixture
differs (the H2/H3 parity check after a digest or projection change).
The raw capture is produced by the GET-only scratch script
``<scratch>/harvester/bin/capture_raw.py`` (+ ``capture_main.py``); the
snapshot dir is the extracted ``runs.tar``/``jobs.tar``/``sha.tar`` of the
#843 evidence branch (``ccr-d0be94c3-o4sati-rescue``).
"""

from __future__ import annotations

import argparse
import csv
import filecmp
import glob
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone

from provenance import canonical, rawdoc
from provenance.steps import jobs_have_agent_step, suspicious_step_names, STEP_GRAMMAR_VERSION

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
FIXTURE_PRS = (636, 371, 397, 634, 343, 316)
NAMED_RUNS = (34661448637, 31364447108, 34112970240, 38161046420, 38161125269, 38177985892, 38178322662)
WATCHED = ("auto-review.yml", "design-run.yml", "backlog-burn.yml", "product-scout.yml",
           "spike-converter.yml", "oracle.yml", "chunker.yml", "labeler.yml", "wright.yml")
ROUTINES = ("design-run.yml", "backlog-burn.yml", "product-scout.yml", "spike-converter.yml",
            "chunker.yml", "labeler.yml")
CAPTURED = {"digest": "body-digest@1", "harvester": "fixture", "run_id": 0}


def _rel(path, params=None):
    rel = path.strip("/").replace("/", "__")
    if params:
        rel += "__" + "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
    return re.sub(r"[^A-Za-z0-9_.=-]", "-", rel) + ".json"


class Raw:
    def __init__(self, root):
        self.root = root

    def get(self, path, params=None):
        p = os.path.join(self.root, _rel(path, params))
        if not os.path.exists(p):
            return None
        doc = json.load(open(p, encoding="utf-8"))
        if any(s != 200 for s in doc["status"]):
            return None
        return doc["data"]


def _iso(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def write_gz(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(canonical.dumps_gz(value))


def load_snapshot(snap):
    runs = {}
    for f in sorted(glob.glob(os.path.join(snap, "runs", "*.json.gz"))):
        wf = os.path.basename(f)[: -len(".json.gz")]
        for r in json.load(gzip.open(f)):
            runs[r["id"]] = (wf, r)
    return runs


def snapshot_jobs(snap, run_id):
    p = os.path.join(snap, "jobs", f"{run_id}.json.gz")
    return json.load(gzip.open(p))["jobs"] if os.path.exists(p) else None


def snapshot_statuses(snap, sha):
    p = os.path.join(snap, "sha", f"{sha}.json.gz")
    return json.load(gzip.open(p))["statuses"] if os.path.exists(p) else None


def build_receipt(workflow, run, jobs, source):
    """receipt@1 — must stay byte-identical to receipts.build_receipt (tests pin it)."""
    jobs = sorted(jobs or [], key=lambda j: (j.get("run_attempt") or 0, j.get("id") or 0))
    full = jobs_have_agent_step(jobs) or bool(suspicious_step_names(jobs))
    doc = {
        "format": "receipt@1",
        "jobs": jobs if full else None,
        "jobs_sha256": canonical.content_sha256(jobs),
        "kind": "full" if full else "stub",
        "run": rawdoc.project_run(run),
        "source": source,
        "step_grammar": STEP_GRAMMAR_VERSION,
        "stub": None if full else {
            "jobs": [{"conclusion": j.get("conclusion"), "name": j.get("name"),
                      "run_attempt": j.get("run_attempt")} for j in jobs],
        },
        "suspicious_steps": suspicious_step_names(jobs),
        "workflow": workflow,
    }
    return doc


def receipt_path(run):
    day = run["created_at"][:10].split("-")
    return os.path.join("receipts", day[0], day[1], day[2], f"{run['id']}.a{run.get('run_attempt') or 1}.json.gz")


def build_pr(raw, snap, n):
    pull = raw.get(f"/pulls/{n}")
    if pull is None:
        raise SystemExit(f"PR {n}: not captured")
    head_ref = pull["head"]["ref"]
    commits_raw = raw.get(f"/pulls/{n}/commits") or []
    commit_shas = {c["sha"] for c in commits_raw}
    ci = raw.get("/actions/workflows/ci.yml/runs", {"branch": head_ref}) or {}
    ci_runs = [r for r in ci.get("workflow_runs", [])
               if n in [p.get("number") for p in r.get("pull_requests") or []] or r["head_sha"] in commit_shas]
    # Statuses for EVERY PR commit and every CI head: a commit carrying any
    # status (Vercel/CodeRabbit post one per pushed head) is a pushed head even
    # when ci.yml did not run on it (docs/provenance.md §Episodes, push evidence).
    shas = sorted({r["head_sha"] for r in ci_runs} | commit_shas | {pull["head"]["sha"]})
    statuses, incomplete = {}, []
    for h in shas:
        st = snapshot_statuses(snap, h)
        if st is None:
            incomplete.append(f"statuses-unavailable:{h[:8]}")
            continue
        if st:
            statuses[h] = rawdoc.project_statuses(st)
    deployments = []
    if pull.get("merged_at") and pull.get("merge_commit_sha"):
        for d in raw.get("/deployments", {"environment": "Production", "sha": pull["merge_commit_sha"]}) or []:
            deployments.append(rawdoc.project_deployment(d, raw.get(f"/deployments/{d['id']}/statuses") or []))
    ccr = raw.get(f"/pulls/{n}/ccr/review_threads")
    if ccr is None:
        threads = rawdoc.project_threads([], "ccr-fixture", None)
        incomplete.append("threads-unavailable")
    else:
        threads = rawdoc.project_threads(
            [{"first_comment_id": (t.get("comment_ids") or [None])[0], "outdated": t.get("outdated"),
              "resolved": t.get("resolved")} for t in ccr], "ccr-fixture", None)
    body = rawdoc.project_pull(pull)
    briefs = list(body["body"]["refs_closes"])
    m = re.match(r"^claude/issue-([0-9]+)-", head_ref or "")
    if m:
        briefs.append(int(m.group(1)))
    return rawdoc.raw_pr_doc(
        number=n, revision=1, captured=CAPTURED, incomplete=incomplete, pull=body,
        files=rawdoc.project_files(raw.get(f"/pulls/{n}/files") or []),
        commits=rawdoc.project_commits(commits_raw),
        reviews=rawdoc.project_reviews(raw.get(f"/pulls/{n}/reviews") or []),
        review_comments=rawdoc.project_review_comments(raw.get(f"/pulls/{n}/comments") or []),
        issue_comments=rawdoc.project_issue_comments(raw.get(f"/issues/{n}/comments") or []),
        timeline=rawdoc.project_timeline(raw.get(f"/issues/{n}/timeline") or []),
        threads=threads, ci_runs=rawdoc.project_runs(ci_runs), statuses=statuses,
        deployments=deployments, briefs=briefs,
    ), head_ref


def build_brief(raw, n):
    issue = raw.get(f"/issues/{n}")
    if issue is None or issue.get("pull_request"):
        return None
    return rawdoc.raw_brief_doc(
        number=n, revision=1, captured=CAPTURED,
        incomplete=["graphql-unavailable"] + ([] if issue.get("state") == "closed" else ["brief-open"]),
        issue=rawdoc.project_issue(issue, None),
        comments=rawdoc.project_issue_comments(raw.get(f"/issues/{n}/comments") or []),
        timeline=rawdoc.project_timeline(raw.get(f"/issues/{n}/timeline") or []),
    )


def fixture_runs(snapruns, head_refs, anchors):
    keep = set(NAMED_RUNS)
    for rid, (wf, r) in snapruns.items():
        if wf not in WATCHED or r.get("conclusion") == "skipped":
            continue
        if wf in ("auto-review.yml", "oracle.yml") and r.get("head_branch") in head_refs:
            keep.add(rid)
        if wf in ROUTINES:
            t = _iso(r["created_at"])
            if any(a - timedelta(hours=2) <= t <= a + timedelta(minutes=30) for a in anchors):
                keep.add(rid)
    return sorted(keep)


def build_codebasis(raw_root, out):
    index, blobs = {}, {}
    for f in sorted(glob.glob(os.path.join(raw_root, "contents__*"))):
        name = os.path.basename(f)[len("contents__"):]
        sha, enc_path = name.split("__", 1)
        path = {".github-models-registry.conf": ".github/models/registry.conf"}.get(enc_path)
        if path is None and enc_path.startswith(".github-workflows-"):
            path = ".github/workflows/" + enc_path[len(".github-workflows-"):]
        if path is None:
            raise SystemExit(f"unrecognised contents capture {name}")
        data = open(f, "rb").read()
        if data.startswith(b'{"documentation_url"') or data.startswith(b'{"message"'):
            continue  # 404 at that sha (registry.conf did not exist yet)
        h = hashlib.sha256(data).hexdigest()
        blobs[h] = data
        index.setdefault(sha, {})[path] = h
    for h, data in blobs.items():
        p = os.path.join(out, "codebasis", "blobs", f"{h}.gz")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(canonical.gzip_bytes(data))
    p = os.path.join(out, "codebasis", "index.json")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(canonical.dumps(index))


def build_main_history(raw, out):
    commits = raw.get("/commits", {"sha": "main", "since": "2026-07-31T00:00:00Z"}) or []
    rows = [{"committed_at": c["commit"]["committer"]["date"], "parents": [p["sha"] for p in c["parents"]],
             "sha": c["sha"], "subject_pr": None} for c in commits]
    for c, row in zip(commits, rows):
        m = re.search(r"\(#([0-9]+)\)$|^Merge pull request #([0-9]+)", c["commit"]["message"].split("\n", 1)[0])
        row["subject_pr"] = int(m.group(1) or m.group(2)) if m else None
    touches = {}
    for path in (".github/models/registry.conf", ".github/workflows/auto-review.yml", ".github/workflows/oracle.yml",
                 ".github/workflows/design-run.yml", ".github/workflows/product-scout.yml",
                 ".github/workflows/backlog-burn.yml"):
        lst = raw.get("/commits", {"path": path, "sha": "main", "since": "2026-07-31T00:00:00Z"}) or []
        touches[path] = sorted(c["sha"] for c in lst)
    write_gz(os.path.join(out, "main_history.json.gz"),
             {"commits": rows, "note": "GET /commits?sha=main since 2026-07-31, API order (newest first)",
              "touches": touches})


def build_pr_files(raw, out):
    csv_path = os.path.join(REPO_ROOT, "audits", "provenance-2026-10", "fixtures", "membership", "membership.csv")
    prs = sorted({int(r["pr"]) for r in csv.DictReader(open(csv_path, encoding="utf-8"))})
    table = {}
    for n in prs:
        pull = raw.get(f"/pulls/{n}")
        files = raw.get(f"/pulls/{n}/files")
        if pull is None or files is None:
            table[str(n)] = None
            continue
        table[str(n)] = {"files": sorted(f["filename"] for f in files), "merged_at": pull.get("merged_at"),
                         "state": pull.get("state"), "title": pull.get("title")}
    write_gz(os.path.join(out, "membership", "pr_files.json.gz"), table)


def _tar_bytes(members):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        for name in sorted(members):
            data = members[name]
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.uid, info.gid, info.mode = len(data), 1791849600, 0, 0, 0o644
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _snap_gz(obj):
    return canonical.gzip_bytes(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode())


def build_snapshot_mini(snap, snapruns, out):
    """A miniature #843 snapshot: same file formats, a handful of real rows."""
    pick = {"design-run.yml": [31364447108, 34661448637], "auto-review.yml": [38161046420]}
    runs_tar = {}
    for wf, ids in pick.items():
        rows = [snapruns[i][1] for i in ids if i in snapruns]
        extra = [r for (w, r) in snapruns.values() if w == wf and r.get("conclusion") == "skipped"][:1]
        runs_tar[f"{wf}.json.gz"] = _snap_gz(rows + extra)
    ci_rows = [r for (w, r) in snapruns.values() if w == "ci.yml" and r.get("head_branch") == "claude/issue-592-nuggs-vent-cap"][:6]
    runs_tar["ci.yml.json.gz"] = _snap_gz(ci_rows)
    jobs_tar = {}
    for ids in pick.values():
        for i in ids:
            jobs = snapshot_jobs(snap, i)
            if jobs is not None:
                jobs_tar[f"{i}.json.gz"] = _snap_gz({"jobs": jobs, "run_id": i})
    sha_tar = {}
    for r in ci_rows[:2]:
        p = os.path.join(snap, "sha", f"{r['head_sha']}.json.gz")
        if os.path.exists(p):
            d = json.load(gzip.open(p))
            for c in d["check_runs"]:
                c["output"] = {"annotations_count": 0, "summary": None, "title": None}
            sha_tar[f"{r['head_sha']}.json.gz"] = _snap_gz(d)
    files = {
        "runs.tar": _tar_bytes(runs_tar),
        "jobs.tar": _tar_bytes(jobs_tar),
        "sha.tar": _tar_bytes(sha_tar),
        "prcommits.tar": _tar_bytes({}),
        "pulls.json.gz": _snap_gz([]),
        "workflows.json.gz": _snap_gz([{"id": 1, "path": ".github/workflows/design-run.yml"}]),
    }
    d = os.path.join(out, "snapshot-mini")
    os.makedirs(d, exist_ok=True)
    lines = []
    for name in sorted(files):
        with open(os.path.join(d, name), "wb") as fh:
            fh.write(files[name])
        lines.append(f"{hashlib.sha256(files[name]).hexdigest()}  {name}")
    with open(os.path.join(d, "MANIFEST.sha256"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def build(raw_root, snap, out):
    raw = Raw(raw_root)
    snapruns = load_snapshot(snap)
    head_refs, briefs, anchors = set(), set(), []
    for n in FIXTURE_PRS:
        doc, head_ref = build_pr(raw, snap, n)
        head_refs.add(head_ref)
        briefs |= set(doc["briefs"])
        anchors.append(_iso(doc["pull"]["created_at"]))
        write_gz(os.path.join(out, "raw", "pr", f"{n}.json.gz"), doc)
    for b in sorted(briefs):
        doc = build_brief(raw, b)
        if doc is None:
            continue
        anchors.append(_iso(doc["issue"]["created_at"]))
        anchors.extend(_iso(c["created_at"]) for c in doc["comments"] if c["body"]["lead"] == "ship_lock")
        write_gz(os.path.join(out, "raw", "brief", f"{b}.json.gz"), doc)
    for rel in raw.get("/releases") or []:
        tag = rel["tag_name"]
        if re.fullmatch(r"[A-Za-z0-9._-]{1,100}", tag):
            write_gz(os.path.join(out, "raw", "release", f"{tag}.json.gz"),
                     rawdoc.raw_release_doc(tag=tag, revision=1, captured=CAPTURED,
                                            release=rawdoc.project_release(rel)))
    for rid in fixture_runs(snapruns, head_refs, anchors):
        if rid not in snapruns:
            continue
        wf, run = snapruns[rid]
        jobs = snapshot_jobs(snap, rid)
        write_gz(os.path.join(out, receipt_path(run)), build_receipt(wf, run, jobs, "snapshot:pr843"))
    build_codebasis(raw_root, out)
    build_main_history(raw, out)
    build_pr_files(raw, out)
    build_snapshot_mini(snap, snapruns, out)


GENERATED = ("raw", "receipts", "codebasis", "main_history.json.gz", "membership", "snapshot-mini")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--raw", required=True)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if not args.check:
        for g in GENERATED:
            p = os.path.join(args.out, g)
            if os.path.isdir(p):
                shutil.rmtree(p)
            elif os.path.exists(p):
                os.remove(p)
        build(args.raw, args.snapshot, args.out)
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        build(args.raw, args.snapshot, tmp)
        bad = []
        for g in GENERATED:
            a, b = os.path.join(tmp, g), os.path.join(args.out, g)
            if os.path.isdir(a):
                cmp = filecmp.dircmp(a, b)
                stack = [cmp]
                while stack:
                    c = stack.pop()
                    bad += [os.path.join(c.left, x) for x in c.left_only + c.right_only + c.diff_files]
                    stack.extend(c.subdirs.values())
            elif not os.path.exists(b) or open(a, "rb").read() != open(b, "rb").read():
                bad.append(b)
        for p in bad:
            print(f"differs: {p}", file=sys.stderr)
        return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
