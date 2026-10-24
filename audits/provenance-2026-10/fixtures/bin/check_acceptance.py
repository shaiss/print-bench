#!/usr/bin/env python3
"""Self-check: recompute each mechanically checkable acceptance assertion from
the golden events (gzipped, prose stripped). This is also the shape of the CD job's acceptance test —
swap the golden events for the job's output and the same checks must hold."""
import gzip, json, os, collections, sys
G = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "golden")
fails = 0

def check(name, got, want):
    global fails
    ok = got == want
    fails += (not ok)
    print(f"{'PASS' if ok else 'FAIL'} {name}: got={got} want={want}")

g = json.load(gzip.open(f"{G}/nuggs-vent-cap.golden.json.gz"))
full = json.load(gzip.open(f"{G}/nuggs-vent-cap.full.json.gz"))
ev = g["events"]
check("NVC-1 rounds", sum(1 for e in g["episodes"] if e["id"].startswith("R:")), 15)
bf = [e for e in ev if e["kind"] == "brief.filed"][0]
check("NVC-2 brief filer", (bf["actor"]["handle"], bf["runtime"]["run_url"].rsplit("/", 1)[1], bf["runtime"]["model"].split()[0]), ("remy", "34112970240", "glm-5.2"))
dc = [e for e in ev if e["kind"] == "commit.design"][0]
check("NVC-3 design commit model", (dc["sha"][:8], dc["runtime"]["model"], dc["runtime"]["chain_link"]), ("9a751b26", "glm-4.6", 3))
so = [e for e in ev if e["kind"] == "review.signoff"]
gha = [e for e in so if e["actor"]["login"] == "github-actions[bot]"]
check("NVC-5 GHA sign-offs", (len(gha), sorted({e["runtime"]["model"] for e in gha})), (12, ["glm-5.3"]))
own = [e for e in so if e["actor"]["login"] == "shaiss"]
check("NVC-6 owner-token sign-offs", (len(own), all(not e["actor"]["verified"] for e in own)), (13, True))
check("NVC-7 distinct owner (reviewer,sha)", len({(e["actor"]["handle"], e["sha"]) for e in own}), 9)
st = [e for e in so if e["url"].endswith("6111973609")][0]
check("NVC-8 stale sign-off", (st["sha"][:8], st["episode"]), ("9a751b26", "R:636:f4e36eb9"))
tri = [e for e in ev if e["kind"] == "triage.verdict"]
check("NVC-9 triage count / handle", (len(tri), {e["actor"]["handle"] for e in tri}), (6, {None}))
kinds = collections.Counter(e["kind"] for e in full["events"])
check("NVC-12 noise", (kinds["noise.bugbot_limit"], kinds["noise.qodo_paused"], kinds["deploy.preview"], kinds["noise.coderabbit_status"]), (21, 1, 46, 33))
check("NVC-12b noise absent from curated", sum(1 for e in ev if e["kind"].startswith("noise.") or e["kind"] == "deploy.preview"), 0)
last_fix = max(e["ts"] for e in ev if e["kind"] == "commit.fix")
an = sum(sum(1 for r in e["refs"]["rows"] if "act-now" in r["verdict"].lower()) for e in tri if e["ts"] > last_fix)
check("NVC-13 act-now after last fix", an, 21)
check("NVC-14 every displayed (non-thread) event has url", all(e["url"] for e in ev), True)
dep = [e for e in ev if e["kind"] == "deploy.production"]
check("NVC-11 deploy", (len(dep), dep[0]["ts"]), (1, "2026-10-11T22:57:47Z"))

g = json.load(gzip.open(f"{G}/sbc-case.golden.json.gz"))
ev = g["events"]
r = collections.Counter(e["id"].split(":")[1] for e in g["episodes"] if e["id"].startswith("R:"))
check("SBC-1 rounds per PR", dict(r), {"371": 2, "397": 14})
e3 = g["edges"]["fix_to_thread_resolved"]
check("SBC-7 threads", (e3["threads"], e3["resolved"], e3["resolved_with_reply_citing_fix_sha"], e3["unresolved_but_reply_claims_fixed"]), (26, 6, 0, 10))
rows = [e for e in ev if e["kind"] == "decision.pm_log"]
check("SBC-8 rows / naming Vera", (len(rows), sum(1 for x in rows if "Vera" in x["refs"]["names"])), (22, 12))
check("SBC-6 coach round notes", sum(1 for e in ev if e["kind"] == "coach.round"), 13)

g = json.load(gzip.open(f"{G}/calibration-cube.golden.json.gz"))
full = json.load(gzip.open(f"{G}/calibration-cube.full.json.gz"))
mc = [e for e in full["events"] if e["kind"].startswith("main.commit")]
nm = [e for e in mc if e["refs"]["parents"] <= 1]
c = collections.Counter(e["kind"].split(".")[-1] for e in nm)
check("CC-1 main commits", (len(mc), len(nm), c["substantive"], c["stamp-only"], c["previews-only"]), (54, 49, 19, 19, 11))
check("CC-5 #634 rounds", sum(1 for e in g["episodes"] if e["id"].startswith("R:634")), 13)
own = [e for e in g["events"] if e["kind"] == "review.signoff" and e["actor"]["login"] == "shaiss"]
check("CC-6 owner-token Drik", len(own), 11)
check("CC-7 #634 triage comments", sum(1 for e in g["events"] if e["kind"] == "triage.verdict"), 0)
sys.exit(1 if fails else 0)
