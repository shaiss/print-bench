#!/usr/bin/env python3
"""Read-only snapshot of GitHub Actions/check/status records for shaiss/print-bench
before GitHub's 90-day retention (effective 2026-10-01 for runs, checks, statuses)
evicts them. GET-only. Resumable: every unit is written to its own gz file and
skipped if present."""
import gzip, json, os, sys, time, threading, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

API = "https://api.github.com/repos/shaiss/print-bench"
OUT = os.path.dirname(os.path.abspath(__file__)) + "/data"
START = date(2026, 7, 31)
END = date(2026, 10, 14)
AGENT_WF = {
    "adoption-assessor.yml", "auto-review.yml", "backlog-burn.yml", "chunker.yml", "design-run.yml",
    "growth-twitter.yml", "labeler.yml", "oracle.yml", "product-scout.yml", "reeve-growth.yml",
    "reeve.yml", "spike-converter.yml", "wright.yml", "decide.yml", "ci-gate-approve.yml",
    "lifestyle-shot.yml", "product-still.yml", "lifestyle-clip.yml", "auto-arm.yml",
    "growth-twitter-reply.yml", "lark-oneshot-650-reply.yml", "model-smoke.yml",
    "copilot", "copilot-pull-request-reviewer",
}
lock = threading.Lock()
stats = {"req": 0, "err": 0}


def get(path, params=""):
    url = f"{API}{path}{'?' + params if params else ''}"
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "pb-rescue"})
            with urllib.request.urlopen(req, timeout=60) as r:
                with lock:
                    stats["req"] += 1
                rem = int(r.headers.get("X-RateLimit-Remaining", "1000"))
                if rem < 300:
                    reset = int(r.headers.get("X-RateLimit-Reset", "0"))
                    time.sleep(max(5, reset - time.time() + 5))
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return {"__error__": e.code}
            time.sleep(2 ** attempt)
        except Exception:
            time.sleep(2 ** attempt)
    with lock:
        stats["err"] += 1
    return {"__error__": "failed"}


def save(rel, obj):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with gzip.GzipFile(tmp, "wb", mtime=0) as f:
        f.write(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode())
    os.replace(tmp, p)


def have(rel):
    return os.path.exists(os.path.join(OUT, rel))


def list_runs(wf):
    wid, name = wf["id"], os.path.basename(wf["path"])
    rel = f"runs/{name}.json.gz"
    if have(rel):
        return json.loads(gzip.open(os.path.join(OUT, rel)).read())
    runs, d = [], START
    while d <= END:
        e = d + timedelta(days=2)
        page = 1
        while True:
            body = get(f"/actions/workflows/{wid}/runs", f"per_page=100&page={page}&created={d}..{e}")
            rs = body.get("workflow_runs", []) if isinstance(body, dict) else []
            runs.extend(rs)
            if len(rs) < 100:
                break
            page += 1
        d = e + timedelta(days=1)
    seen, out = set(), []
    for r in runs:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        out.append({k: r.get(k) for k in (
            "id", "name", "path", "event", "status", "conclusion", "head_branch", "head_sha",
            "created_at", "updated_at", "run_started_at", "run_attempt", "run_number", "html_url",
            "display_title")} | {
            "actor": (r.get("actor") or {}).get("login"),
            "triggering_actor": (r.get("triggering_actor") or {}).get("login"),
            "pull_requests": [p.get("number") for p in r.get("pull_requests") or []],
        })
    save(rel, out)
    return out


def fetch_jobs(run):
    rel = f"jobs/{run['id']}.json.gz"
    if have(rel):
        return
    jobs, page = [], 1
    while True:
        body = get(f"/actions/runs/{run['id']}/jobs", f"filter=all&per_page=100&page={page}")
        js = body.get("jobs", []) if isinstance(body, dict) else []
        jobs.extend(js)
        if len(js) < 100:
            break
        page += 1
    save(rel, {"run_id": run["id"], "jobs": jobs})


def pr_commits(n):
    rel = f"prcommits/{n}.json.gz"
    if have(rel):
        return json.loads(gzip.open(os.path.join(OUT, rel)).read())
    out, page = [], 1
    while True:
        body = get(f"/pulls/{n}/commits", f"per_page=100&page={page}")
        if not isinstance(body, list):
            break
        out.extend({"sha": c["sha"], "author": (c.get("author") or {}).get("login"),
                    "committer": (c.get("committer") or {}).get("login"),
                    "commit": {"author": c["commit"]["author"], "committer": c["commit"]["committer"],
                               "message": c["commit"]["message"]}} for c in body)
        if len(body) < 100:
            break
        page += 1
    save(rel, out)
    return out


def sha_records(sha):
    rel = f"sha/{sha}.json.gz"
    if have(rel):
        return
    st, page = [], 1
    while True:
        body = get(f"/commits/{sha}/statuses", f"per_page=100&page={page}")
        if not isinstance(body, list):
            break
        st.extend({k: s.get(k) for k in ("id", "context", "state", "description", "target_url", "created_at", "updated_at")}
                  | {"creator": (s.get("creator") or {}).get("login")} for s in body)
        if len(body) < 100:
            break
        page += 1
    cr, page = [], 1
    while True:
        body = get(f"/commits/{sha}/check-runs", f"filter=all&per_page=100&page={page}")
        rs = body.get("check_runs", []) if isinstance(body, dict) else []
        cr.extend({k: c.get(k) for k in ("id", "name", "status", "conclusion", "started_at", "completed_at", "details_url", "html_url")}
                  | {"app": (c.get("app") or {}).get("slug"),
                     "output": {k: (c.get("output") or {}).get(k) for k in ("title", "summary", "annotations_count")},
                     "check_suite": (c.get("check_suite") or {}).get("id")} for c in rs)
        if len(rs) < 100:
            break
        page += 1
    save(rel, {"sha": sha, "statuses": st, "check_runs": cr})


def main():
    os.makedirs(OUT, exist_ok=True)
    wfs = get("/actions/workflows", "per_page=100")["workflows"]
    save("workflows.json.gz", wfs)
    with ThreadPoolExecutor(8) as ex:
        all_runs = list(ex.map(list_runs, wfs))
    runs = [r for rs in all_runs for r in rs]
    print(f"runs listed: {len(runs)}  req={stats['req']}", flush=True)
    agent = [r for r in runs if os.path.basename(r["path"] or "") in AGENT_WF
             and r.get("conclusion") not in ("skipped",)]
    print(f"agent runs to fetch jobs: {len(agent)}", flush=True)
    with ThreadPoolExecutor(10) as ex:
        for i, _ in enumerate(ex.map(fetch_jobs, agent)):
            if i % 250 == 0:
                print(f"  jobs {i}/{len(agent)} req={stats['req']} err={stats['err']}", flush=True)
    # PRs: every PR number
    prs, page = [], 1
    while True:
        body = get("/pulls", f"state=all&per_page=100&page={page}")
        if not isinstance(body, list) or not body:
            break
        prs.extend({"number": p["number"], "title": p["title"], "state": p["state"], "merged_at": p.get("merged_at"),
                    "created_at": p["created_at"], "closed_at": p.get("closed_at"), "user": p["user"]["login"],
                    "head_ref": p["head"]["ref"], "head_sha": p["head"]["sha"], "base": p["base"]["ref"],
                    "merge_commit_sha": p.get("merge_commit_sha")} for p in body)
        page += 1
    save("pulls.json.gz", prs)
    print(f"PRs: {len(prs)}", flush=True)
    with ThreadPoolExecutor(10) as ex:
        commits = list(ex.map(lambda p: pr_commits(p["number"]), prs))
    shas = sorted({c["sha"] for cs in commits for c in cs} | {p["head_sha"] for p in prs})
    print(f"PR SHAs: {len(shas)}  req={stats['req']}", flush=True)
    with ThreadPoolExecutor(10) as ex:
        for i, _ in enumerate(ex.map(sha_records, shas)):
            if i % 250 == 0:
                print(f"  sha {i}/{len(shas)} req={stats['req']} err={stats['err']}", flush=True)
    print(f"DONE req={stats['req']} err={stats['err']}", flush=True)


if __name__ == "__main__":
    main()
