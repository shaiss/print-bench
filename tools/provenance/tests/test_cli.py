"""cli — argparse, input validation (scaffold-implemented), mode orchestration.

Owner: H1. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e, the critique round's items);
replace the skip with the test.

The orchestration tests drive the workflow's harvest job step by step
(``tests/_gitstore_helpers.Harness``): plan → declare intents → publish →
upload checkpoints, over a temp clone with a LOCAL bare ``origin`` and a
``FakeGitHub``. ``freeze.plan_freezes`` and ``bundle.derive`` /
``same_content`` (H6 / H5) are replaced by small fakes; the real composition
runs at integration.
"""

from __future__ import annotations

import gzip
import json
import re
from urllib.parse import urlsplit

import pytest

from _gitstore_helpers import ALLOW, MINI, NOW_EPOCH, REPO_SLUG, Harness
from conftest import REPO, needs

from provenance import canonical, cli, contract, freeze, github, gitstore
from provenance import conf as conf_mod
from provenance.gitstore import DERIVED_REF as DV
from provenance.gitstore import EVIDENCE_REF as EV

SNAP = ("--snapshot-dir", str(MINI))
SNAP_END = "2026-10-11T17:46:29Z"
#: H6's real freeze pass, captured before any Harness patches it (the integration tests restore it).
REAL_PLAN_FREEZES = freeze.plan_freezes


@pytest.fixture
def h(tmp_path, monkeypatch):
    return Harness(tmp_path, monkeypatch)


def _bootstrap(h):
    r = h.cycle("--bootstrap", *SNAP)
    assert r["plan"] == 0 and r["publish"] == 0, r
    return r["pub_out"]["evidence_tip"], r["pub_out"]["site_tip"]


def _state(h, sha):
    return json.loads(h.sb.files_at(sha)["state.json"])


def _record_pushes(monkeypatch):
    order = []
    ff, lease = gitstore.push_fast_forward, gitstore.push_force_with_lease

    def rec_ff(git, ref, new, old, **kw):
        order.append(("ff", ref))
        return ff(git, ref, new, old, **kw)

    def rec_lease(git, ref, new, old):
        order.append(("lease", ref))
        return lease(git, ref, new, old)
    monkeypatch.setattr(gitstore, "push_fast_forward", rec_ff)
    monkeypatch.setattr(gitstore, "push_force_with_lease", rec_lease)
    return order


def test_harvest_dry_run_writes_plan_not_pushes(h, monkeypatch, capsys):
    """harvest --dry-run over a temp repo + local bare origin + FakeGitHub writes plan.json, intent files and summary.md, sets evidence_changed/site_changed false in --gh-output and calls no push."""
    order = _record_pushes(monkeypatch)
    code, out = h.plan("--bootstrap", "--dry-run", *SNAP)
    assert code == 0, capsys.readouterr().err
    assert out == {"budget_stopped": "false", "derive_error": "false", "derive_skipped": "false", "dry_run": "true",
                   "receipts_error": "false",
                   "evidence_changed": "false", "evidence_sha": "", "foreign_tip": "false", "mode": "harvest",
                   "site_changed": "false", "site_sha": ""}
    plan = h.plan_doc()
    assert plan["format"] == "plan@1" and plan["dry_run"] is True and plan["mode"] == "harvest"
    ev, dv = plan["refs"][EV], plan["refs"][DV]
    assert ev["old"] is None and ev["verdict"] == "bootstrap" and ev["would_change"] and not ev["changed"]
    assert dv["old"] is None and dv["verdict"] == "bootstrap" and dv["would_change"] and not dv["changed"]
    intent = json.loads((h.out / f"intent-{EV}.json").read_text())
    assert intent == {"format": "intent@1", "parent": None, "ref": EV, "run_attempt": 1, "run_id": h.run_id,
                      "sha": ev["new"]}
    assert json.loads((h.out / f"intent-{DV}.json").read_text())["sha"] == dv["new"]
    summary = (h.out / "summary.md").read_text()
    assert "dry run" in summary and "ingest pr843" in summary and "continuity" in summary
    assert plan["derived_from"] == ev["new"] and h.sb.git.has_commit(ev["new"])
    assert h.sb.remote(EV) is None and h.sb.remote(DV) is None              # nothing pushed
    code, pub = h.publish()
    assert code == 0 and pub == {"evidence_tip": "", "foreign_tip": "false", "site_tip": ""}
    assert h.sb.remote(EV) is None and h.sb.remote(DV) is None and order == []
    assert json.loads((h.out / "checkpoints.json").read_text()) == {EV: None, DV: None}


def test_budget_stop_exits_zero(h, capsys):
    """A BudgetExhausted during receipts or freeze exits 0 with a ::notice:: and resumable cursors in the planned state.json."""
    _bootstrap(h)
    h.add_live_run("design-run.yml", 501, "2026-10-13T10:00:00Z")
    h.add_live_run("design-run.yml", 502, "2026-10-13T11:00:00Z")
    jobs_502 = h.jobs.pop(502)

    respond = h.fake.responder

    def stingy(path, params):
        if path == "/actions/runs/502/jobs":
            raise github.BudgetExhausted("request cap 9 reached")
        return respond(path, params)
    h.fake.responder = stingy
    capsys.readouterr()
    r = h.cycle()
    err = capsys.readouterr().err
    assert r["plan"] == 0 and "::notice::capture stopped cleanly" in err
    assert r["plan_out"]["budget_stopped"] == "true" and r["plan_out"]["evidence_changed"] == "true"
    tip = r["pub_out"]["evidence_tip"]
    files = h.sb.files_at(tip)
    assert "receipts/2026/10/13/501.a1.json.gz" in files and "receipts/2026/10/13/502.a1.json.gz" not in files
    assert _state(h, tip)["cursors"]["receipts"]["design-run.yml"] == "2026-10-13T11:00:00Z"  # resumes at 502
    # The next run, with budget, captures exactly what is left.
    h.fake.responder = respond
    h.jobs[502] = jobs_502
    r2 = h.cycle()
    files2 = h.sb.files_at(r2["pub_out"]["evidence_tip"])
    assert "receipts/2026/10/13/502.a1.json.gz" in files2 and r2["plan_out"]["budget_stopped"] == "false"
    # A budget stop inside the freeze pass is clean too.
    h.freeze = lambda gh, **kw: (_ for _ in ()).throw(github.BudgetExhausted("rate-limit floor"))
    code, out = h.plan()
    assert code == 0 and out["budget_stopped"] == "true"
    # And a stopping FreezePlan carries its partial work.
    h.freeze = lambda gh, **kw: freeze.FreezePlan(budget_stopped=True)
    code, out = h.plan()
    assert code == 0 and out["budget_stopped"] == "true"


def test_receipts_failure_is_isolated_and_red_after_publish(h, capsys):
    """Integration review round 2 (medium), end to end: one run's jobs GET fails (502 after the
    client's retries) — the plan still exits 0 with receipts_error=true, the healthy run's receipt is
    published and checkpointed, the cursor holds at the failed run, plan.json names it, and the
    workflow's Verdict (receipts) step is what turns the job red. The next run, healthy, captures it."""
    c, _ = _bootstrap(h)
    h.add_live_run("design-run.yml", 901, "2026-10-13T10:00:00Z")
    h.add_live_run("design-run.yml", 902, "2026-10-13T11:00:00Z")
    respond = h.fake.responder

    def flaky(path, params):
        if path == "/actions/runs/901/jobs":
            raise github.APIError("HTTP 502 GET /actions/runs/901/jobs", status=502)
        return respond(path, params)
    h.fake.responder = flaky
    capsys.readouterr()
    r = h.cycle()
    err = capsys.readouterr().err
    assert r["plan"] == 0 and r["publish"] == 0 and r["plan_out"]["receipts_error"] == "true"
    assert "::error::receipts: jobs GET for design-run.yml run 901 failed" in err
    plan = h.plan_doc()
    assert plan["receipts_error"] is True
    assert [f["run_id"] for f in plan["counts"]["receipts"]["failed"]] == [901]
    tip = r["pub_out"]["evidence_tip"]
    assert tip and tip != c and h.sb.remote(EV) == tip
    files = h.sb.files_at(tip)
    assert "receipts/2026/10/13/902.a1.json.gz" in files and "receipts/2026/10/13/901.a1.json.gz" not in files
    assert _state(h, tip)["cursors"]["receipts"]["design-run.yml"] == "2026-10-13T10:00:00Z"
    assert "receipts FAILED: design-run.yml run 901" in (h.out / "summary.md").read_text()
    h.fake.responder = respond
    r2 = h.cycle()
    assert r2["plan_out"]["receipts_error"] == "false"
    assert "receipts/2026/10/13/901.a1.json.gz" in h.sb.files_at(r2["pub_out"]["evidence_tip"])


def test_scan_budget_stop_is_a_clean_noop_through_publish(h, monkeypatch, capsys):
    """A BudgetExhausted DURING the continuity scan (the scheduled floor, the 400 cap, a dispatch's
    max_requests) is a no-op plan whose refs carry old == new == the FETCHED tip with verdict
    unknown: plan exits 0, publish exits 0 pushing and checkpointing nothing (both *_tip outputs
    empty, no phantom 'moved since the plan'), the remotes are unchanged, and the next run with budget
    judges continuity normally. Control: a tip that really moves between that plan and publish is
    still refused (exit 3)."""
    c, d = _bootstrap(h)
    real = h.fake.iter_pages

    def floor(path, params=None, **kw):
        if path == "/actions/artifacts":
            raise github.BudgetExhausted("X-RateLimit-Remaining 12 < floor 500")
        return real(path, params, **kw)
    monkeypatch.setattr(h.fake, "iter_pages", floor)
    order = _record_pushes(monkeypatch)
    capsys.readouterr()
    r = h.cycle("--scheduled")
    err = capsys.readouterr().err
    assert r["plan"] == 0 and r["publish"] == 0, err
    assert "::error::" not in err and "budget stopped before tip continuity" in err
    po = r["plan_out"]
    assert (po["budget_stopped"], po["foreign_tip"], po["evidence_changed"], po["site_changed"],
            po["evidence_sha"], po["site_sha"]) == ("true", "false", "false", "false", "", "")
    assert r["pub_out"] == {"evidence_tip": "", "foreign_tip": "false", "site_tip": ""}
    plan = h.plan_doc()
    for ref, tip in ((EV, c), (DV, d)):
        assert plan["refs"][ref] == {"changed": False, "checkpoint": None, "new": tip, "old": tip,
                                     "verdict": "unknown", "would_change": False}
    assert order == [] and h.sb.remote(EV) == c and h.sb.remote(DV) == d
    assert json.loads((h.out / "checkpoints.json").read_text()) == {EV: None, DV: None}
    assert not (h.out / cli.tip_file(EV)).exists() and not (h.out / cli.tip_file(DV)).exists()
    # The next run, with budget: continuity holds (the bootstrap checkpoint still anchors both tips).
    monkeypatch.setattr(h.fake, "iter_pages", real)
    r = h.cycle()
    assert r["publish"] == 0 and h.plan_doc()["refs"][EV]["verdict"] == "ok"
    assert r["pub_out"] == {"evidence_tip": c, "foreign_tip": "false", "site_tip": d}
    # Control: the remote moves between a scan-stopped plan and its publish → refused, nothing pushed.
    monkeypatch.setattr(h.fake, "iter_pages", floor)
    code, _ = h.plan("--scheduled")
    assert code == 0
    mover = h.sb.commit(dict(h.sb.files_at(c), **{"raw/pr/5.json.gz": b"x"}), c)
    h.sb.push(mover, EV)
    pcode, pub = h.publish()
    assert pcode == 3 and pub["evidence_tip"] == "" and h.sb.remote(EV) == mover and h.sb.remote(DV) == d


def test_capture_deadline_leaves_the_derive_reserve(h, monkeypatch, capsys):
    """A dispatch's Budget.deadline_epoch is job start + dispatch_max_minutes − derive_reserve_minutes (critique 22): with a fake clock past it, capture stops cleanly and derive + plan still run."""
    deadline = NOW_EPOCH + (330 - 30) * 60
    seen = []

    def transport(method, url, headers, body):
        if urlsplit(url).path.endswith("/actions/artifacts"):
            return 200, {"X-RateLimit-Remaining": "4000"}, json.dumps({"artifacts": [], "total_count": 0}).encode()
        raise AssertionError(f"a capture request was sent past the deadline: {url}")

    def make_client(args, conf, *, scheduled, deadline_epoch):
        seen.append((scheduled, deadline_epoch))
        return github.Client(repo=REPO_SLUG, token="", transport=transport, clock=lambda: deadline + 1,
                             sleep=lambda s: None,
                             budget=github.Budget(max_requests=None, floor=500, pace=True, deadline_epoch=deadline_epoch))
    monkeypatch.setattr(cli, "make_client", make_client)
    code, out = h.plan("--bootstrap", *SNAP)
    assert code == 0, capsys.readouterr().err
    assert seen == [(False, float(deadline))]
    assert out["budget_stopped"] == "true" and out["evidence_changed"] == "true" and out["site_changed"] == "true"
    plan = h.plan_doc()
    assert plan["derived_from"] == plan["refs"][EV]["new"] and plan["derive_skipped"] is False
    assert "capture deadline reached" in capsys.readouterr().err
    # A scheduled run has no capture deadline (its cap is the request budget).
    h.client = None
    monkeypatch.setattr(cli, "make_client", h._make_client)
    h.plan("--scheduled", "--bootstrap", *SNAP)
    assert h.deadlines[-1] == (True, None)


def test_foreign_evidence_tip_derives_from_checkpoint(h, capsys):
    """Critique 5: both refs forged (evidence tip F on top of checkpoint C, derived tip a forged tree): plan exits 0 with foreign_tip=true, evidence_changed=false, receipts/freeze not run (no API GET beyond the scan), site_changed=true with the bundle's evidence_sha == C; publish pushes provenance-site only; the workflow's verdict step then fails."""
    c, _ = _bootstrap(h)
    f = h.sb.commit(dict(h.sb.files_at(c), **{"raw/pr/1.json.gz": canonical.dumps_gz({"forged": 1})}), c)
    h.sb.push(f, EV)
    g = h.sb.commit({"FORMAT": b"forged\n"}, None)
    h.sb.push(g, DV, force=True)
    h.add_live_run("design-run.yml", 601, "2026-10-13T10:00:00Z")   # would be captured were the tip ok
    froze = []
    h.freeze = lambda gh, **kw: froze.append(1) or freeze.FreezePlan()
    h.fake.calls.clear()
    capsys.readouterr()
    code, out = h.plan()
    err = capsys.readouterr().err
    assert code == 0
    assert out["foreign_tip"] == "true" and out["evidence_changed"] == "false" and out["site_changed"] == "true"
    assert all(p == "/actions/artifacts" or (p.startswith("/actions/runs/") and not p.endswith("/jobs"))
               for p, _ in h.fake.calls) and froze == []
    assert "::error::evidence tip" in err and "failed continuity (foreign" in err
    plan = h.plan_doc()
    assert plan["derived_from"] == c and plan["refs"][EV]["new"] == f and not plan["refs"][EV]["changed"]
    site = out["site_sha"]
    derived = h.sb.files_at(site)
    assert json.loads(derived["site/bundle.json"])["evidence_sha"] == c
    assert "raw/pr/1.json.gz" not in json.loads(derived["views/demo.json"])["evidence_paths"]
    h.declare(out)
    pcode, pub = h.publish()
    assert pcode == 0 and pub == {"evidence_tip": "", "foreign_tip": "true", "site_tip": site}
    assert h.sb.remote(EV) == f and h.sb.remote(DV) == site
    assert not (h.out / f"tip-{EV}.json").exists() and (h.out / f"tip-{DV}.json").exists()


def _reclone(h, *, prune: bool = False) -> None:
    """Replace the harness checkout with a fresh ``--no-local`` clone of origin — what each production
    run starts from (actions/checkout + fetch_all): only what origin's refs reach is local. The bare
    origin serves an unreachable sha on request (``uploadpack.allowAnySHA1InWant``; the local
    transport's protocol v2 does so anyway), as GitHub does for a commit it still holds; ``prune``
    first expires origin's reflogs and gc's it, so an unreachable sha is GONE (unservable)."""
    import shutil

    from _gitstore_helpers import sh
    sh(h.sb.root, "--git-dir", str(h.sb.origin), "config", "uploadpack.allowAnySHA1InWant", "true")
    if prune:
        sh(h.sb.root, "--git-dir", str(h.sb.origin), "reflog", "expire", "--expire=now", "--all")
        sh(h.sb.root, "--git-dir", str(h.sb.origin), "gc", "-q", "--prune=now")
    h.sb.git.close()                    # its cat-file process and commit memo belong to the old clone
    shutil.rmtree(h.sb.checkout)
    sh(h.sb.root, "clone", "-q", "--no-local", str(h.sb.origin), str(h.sb.checkout))
    h.sb.git = gitstore.Git(str(h.sb.checkout), env=ALLOW)


@pytest.mark.parametrize("how", ["deleted", "orphan"])
def test_foreign_tip_derive_fetches_the_checkpoint_by_sha(h, capsys, how):
    """Panel round 2 (medium): the evidence ref is deleted, or force-pushed to a commit that does not
    descend from the newest checkpoint C, AND a forged provenance-site is planted; every run starts from
    a fresh clone that does not hold C. The plan fetches C by sha, derives from it and replaces the
    forged derived tip on the NEXT run (the docs' promise); a second run leaves the replacement alone.
    Negative control: once origin no longer holds C (pruned), derive is skipped and a re-planted forged
    tip survives with an ::error:: — the residual docs/provenance.md names (C genuinely unservable)."""
    c, _ = _bootstrap(h)
    for _ in range(2):
        assert h.cycle()["pub_out"]["evidence_tip"] == c
    if how == "deleted":
        h.sb.delete(EV)
    else:
        h.sb.push(h.sb.commit({"FORMAT": b"orphan\n"}, None), EV, force=True)
    g = h.sb.commit({"FORMAT": b"forged\n"}, None)
    h.sb.push(g, DV, force=True)

    for i in range(2):
        _reclone(h)
        assert h.sb.git.run_full("cat-file", "-e", c).returncode != 0      # C is not in the fresh clone
        r = h.cycle()
        assert r["plan"] == 0 and r["plan_out"]["foreign_tip"] == "true", r
        assert h.plan_doc()["refs"][EV]["verdict"] == ("deleted" if how == "deleted" else "foreign")
        assert r["plan_out"]["derive_skipped"] == "false" and h.plan_doc()["derived_from"] == c
        site = h.sb.remote(DV)
        assert site != g and json.loads(h.sb.files_at(site)["site/bundle.json"])["evidence_sha"] == c
        assert r["plan_out"]["site_changed"] == ("true" if i == 0 else "false")  # replaced, then left alone

    g2 = h.sb.commit({"FORMAT": b"forged again\n"}, None)                # negative control
    h.sb.push(g2, DV, force=True)
    _reclone(h, prune=True)
    capsys.readouterr()
    r = h.cycle()
    err = capsys.readouterr().err
    assert r["plan"] == 0 and r["plan_out"]["foreign_tip"] == "true" and r["plan_out"]["derive_skipped"] == "true"
    assert r["plan_out"]["site_changed"] == "false" and h.sb.remote(DV) == g2
    assert "could not be rebuilt this run" in err
    assert f"derive skipped: evidence checkpoint {c[:8]} is not fetchable from origin" in (h.out / "summary.md").read_text()


def test_forged_derived_tip_is_replaced(h, capsys):
    """P1d + critique 5: a planted provenance-site tip that is not checkpointed — including one whose bundle copies the real content_sha256 but alters a view — is replaced by the verified tree with ::error:: (moved here from test_gitstore; critique 27)."""
    c, d = _bootstrap(h)
    real = h.sb.files_at(d)
    modes = {"scripts/vercel-ignore-build.sh": "100755"}
    forged = dict(real, **{"views/demo.json": canonical.dumps_bytes({"design": "demo", "evidence_paths": []})})
    x = h.sb.commit(forged, None, modes=modes)                     # bundle bytes (digests) copied verbatim
    h.sb.push(x, DV, force=True)
    capsys.readouterr()
    r = h.cycle()
    err = capsys.readouterr().err
    assert r["plan_out"]["site_changed"] == "true" and r["plan_out"]["evidence_changed"] == "false"
    assert "::error::derived tip" in err and "foreign" in err
    new = r["pub_out"]["site_tip"]
    assert h.sb.remote(DV) == new and new not in (x, d)
    assert h.sb.files_at(new)["views/demo.json"] == real["views/demo.json"]
    # Identical CONTENT on a commit nobody checkpointed is replaced too (continuity, not content).
    y = h.sb.commit(h.sb.files_at(new), None, modes=modes, message="same tree, other commit")
    assert y != new
    h.sb.push(y, DV, force=True)
    r = h.cycle()
    assert r["plan_out"]["site_changed"] == "true" and h.sb.remote(DV) == r["pub_out"]["site_tip"] != y
    # Control: the verified tip is left alone by the next run.
    r = h.cycle()
    assert r["plan_out"]["site_changed"] == "false" and r["pub_out"]["site_tip"] == h.sb.remote(DV)


def test_bootstrap_needs_the_flag(h, capsys):
    """Critique 3: absent evidence ref + no checkpoint: without --bootstrap → ::error::, exit 3, nothing planned; with --bootstrap → a root commit carrying the guard files, README, FORMAT, state.json and the auto-ingest. --bootstrap with an existing ref or a checkpoint → exit 1/3."""
    code, out = h.plan(*SNAP)
    assert code == 3 and "bootstrap=true" in capsys.readouterr().err
    assert not (h.out / "plan.json").exists() and out == {}
    c, _ = _bootstrap(h)
    assert h.sb.git.parents(c) == []
    entries = h.sb.git.tree_entries(c)
    files = h.sb.files_at(c)
    assert entries["scripts/vercel-ignore-build.sh"][0] == "100755" and entries["vercel.json"][0] == "100644"
    guard = gitstore.guard_blobs(str(h.sb.checkout))
    assert files["vercel.json"] == guard["vercel.json"][1]
    assert files["README.md"] == gitstore.EVIDENCE_README and files["FORMAT"] == b"print-bench-provenance 1\n"
    assert _state(h, c)["format"] == "state@1"
    assert sorted(p for p in files if p.startswith(("receipts/", "raw/"))) == sorted([
        "receipts/2026/08/10/31364447108.a1.json.gz", "receipts/2026/09/12/34661448637.a2.json.gz",
        "receipts/2026/10/11/38161046420.a1.json.gz", "raw/snapshot/pr843/runs/ci.yml.json.gz",
        "raw/snapshot/pr843/statuses/77cbb164fc6160a80512f9d59088b00379c2d148.json.gz",
        "raw/snapshot/pr843/statuses/9a751b26e18dac7f9c8c9464fd37a2e4c6c63f2c.json.gz"])
    assert h.sb.remote(EV) == c
    capsys.readouterr()
    code, _ = h.plan("--bootstrap", *SNAP)                        # the ref exists and is checkpointed
    assert code == 1 and "--bootstrap refused" in capsys.readouterr().err
    h.art.items.clear()
    h.art._publish()                                               # 90 days pass: no checkpoint left
    code, _ = h.plan("--bootstrap", *SNAP)                        # unanchored: still refused
    assert code == 1
    code, out = h.plan()
    assert code == 0 and out["foreign_tip"] == "true"              # unanchored is refused, never re-anchored


def test_deleted_ref_is_refused_not_rebootstrapped(h):
    """Critique 3 (the harvest half of test_gitstore's quiet-day test): after quiet no-op runs that
    each checkpoint the same tip, deleting the evidence ref makes the next harvest a refusal
    (foreign_tip — the verdict step exits 3), publish recreates nothing, and --bootstrap is refused."""
    c, _ = _bootstrap(h)
    for _ in range(3):
        r = h.cycle()
        assert r["plan_out"]["evidence_changed"] == "false" and r["pub_out"]["evidence_tip"] == c
    h.sb.delete(EV)
    r = h.cycle()
    assert r["plan"] == 0 and r["plan_out"]["foreign_tip"] == "true" and r["plan_out"]["evidence_changed"] == "false"
    assert h.plan_doc()["refs"][EV]["verdict"] == "deleted" and h.sb.remote(EV) is None
    assert r["pub_out"]["evidence_tip"] == "" and r["pub_out"]["foreign_tip"] == "true"
    code, _ = h.plan("--bootstrap", *SNAP)
    assert code == 1 and h.sb.remote(EV) is None


def test_auto_ingest_runs_once(h):
    """Critique 17: the bootstrap harvest ingests --snapshot-dir fixtures/snapshot-mini (pin = its MANIFEST digest), records state.ingested.pr843 {manifest_sha256, commit, version, snapshot_end, …} and raises each watched receipts cursor to snapshot_end; the next harvest plans no ingest file."""
    c, _ = _bootstrap(h)
    st = _state(h, c)
    assert st["ingested"] == {"pr843": {"commit": h.conf.snapshot_commit,
                                        "manifest_sha256": "0da7f326fb3d57ad8968a56b30e3b3831a1d181b32b3ce0193ea22235ea3d0a0",
                                        "receipts": 3, "runs_listings": 1, "snapshot_end": SNAP_END,
                                        "statuses": 2, "version": 1}}
    assert st["cursors"]["receipts"] == {"auto-review.yml": SNAP_END, "design-run.yml": SNAP_END}
    windows = sorted({p["created"] for path, p in h.fake.calls if "created" in p})
    assert windows[0].startswith("2026-10-09T17:46:29Z..")          # snapshot end − 48 h, not 2026-07-31
    r = h.cycle()
    assert "ingest" not in h.plan_doc()["counts"] and r["plan_out"]["evidence_changed"] == "false"
    # A snapshot that is not the pin aborts the (bootstrap) ingest with nothing planned.
    h2_conf = h.conf
    h.conf = conf_mod.Config(**{**h2_conf.__dict__, "snapshot_manifest_sha256": "0" * 64})
    h.sb.delete(EV)
    h.art.items.clear()
    h.art._publish()
    code, out = h.plan("--bootstrap", *SNAP)
    assert code == 1 and not (h.out / "plan.json").exists()


def test_recover_refused_while_continuity_holds(h, capsys):
    """Critique 4: recover when the evidence tip passes continuity → exit 3, nothing planned."""
    c, _ = _bootstrap(h)
    capsys.readouterr()
    code, out = h.plan("--confirm-sha", c, mode="recover")
    assert code == 3 and "recover refused" in capsys.readouterr().err
    assert not (h.out / "plan.json").exists() and out == {}
    assert h.sb.remote(EV) == c


def test_recover_budget_stop_exits_1_without_a_plan(h, monkeypatch, capsys):
    """recover cannot judge continuity without the scan: a BudgetExhausted there is exit 1 with an
    ::error:: (never a traceback) and no plan for publish to act on."""
    c, _ = _bootstrap(h)

    def floor(path, params=None, **kw):
        raise github.BudgetExhausted("X-RateLimit-Remaining 3 < floor 500")
    monkeypatch.setattr(h.fake, "iter_pages", floor)
    capsys.readouterr()
    code, out = h.plan("--confirm-sha", c, mode="recover")
    assert code == 1 and "::error::BudgetExhausted" in capsys.readouterr().err
    assert not (h.out / "plan.json").exists() and out == {} and h.sb.remote(EV) == c


def test_recover_needs_the_newest_checkpoint(h, monkeypatch, capsys):
    """Critique 4: with a foreign tip, recover --confirm-sha <an older checkpoint or an intent> → exit 3; --confirm-sha <newest checkpoint> → a force-with-lease plan of that sha over the foreign tip."""
    c1, _ = _bootstrap(h)
    h.add_live_run("design-run.yml", 701, "2026-10-13T10:00:00Z")
    c2 = h.cycle()["pub_out"]["evidence_tip"]
    assert c2 != c1 and h.sb.git.parents(c2) == [c1]
    f = h.sb.commit(dict(h.sb.files_at(c2), **{"raw/pr/9.json.gz": b"forged"}), c2)
    h.sb.push(f, EV)
    stray = "5" * 40
    h.art.intent(EV, stray, 9999)
    for bad in (c1, stray, f):
        code, _ = h.plan("--confirm-sha", bad, mode="recover")
        assert code == 3, bad
        assert not (h.out / "plan.json").exists()
    order = _record_pushes(monkeypatch)
    code, out = h.plan("--confirm-sha", c2, mode="recover")
    assert code == 0 and out["mode"] == "recover" and out["evidence_sha"] == c2 and out["site_changed"] == "false"
    plan = h.plan_doc()
    assert plan["refs"][EV] | {"would_change": True} == {"changed": True, "checkpoint": c2, "new": c2, "old": f,
                                                         "verdict": "foreign", "would_change": True}
    h.declare(out)
    pcode, pub = h.publish()
    assert pcode == 0 and pub["evidence_tip"] == c2 and order == [("lease", EV)]
    assert h.sb.remote(EV) == c2
    h.checkpoint(pub)
    r = h.cycle()
    assert r["plan_out"]["foreign_tip"] == "false" and h.plan_doc()["refs"][EV]["verdict"] == "ok"
    # A deleted ref is recovered the same way (the lease: "must not exist").
    h.sb.delete(EV)
    code, out = h.plan("--confirm-sha", c2, mode="recover")
    assert code == 0 and h.plan_doc()["refs"][EV]["old"] is None
    pcode, pub = h.publish()
    assert pcode == 0 and h.sb.remote(EV) == c2


def test_checkpoint_order_conflict_is_foreign_and_unrecoverable(h, capsys):
    """Panel round 2 (high), the clock-free cross-check end to end: c1 → c2 genuine, then the ref is
    forced back to c1 AND the artifact list's clock misorders c1's checkpoints after c2's (the case
    upload-time ordering alone cannot see). The created rule alone would read the rollback ok; the
    ancestry check finds the newest checkpoint c1 not descending from verified checkpoint c2, so the
    verdict is foreign with that conflict, derive is skipped (never derived from a conflicted C), and
    recover refuses c1. Control: with the clock honest the same rollback is plain foreign, no conflict,
    and recover to c2 plans."""
    c1, _ = _bootstrap(h)
    h.add_live_run("design-run.yml", 711, "2026-10-13T10:00:00Z")
    c2 = h.cycle()["pub_out"]["evidence_tip"]
    assert h.sb.git.parents(c2) == [c1]
    h.sb.push(c1, EV, force=True)                                         # the rollback
    code, _ = h.plan()
    ev = h.plan_doc()["refs"][EV]
    assert code == 0 and ev["verdict"] == "foreign" and ev["checkpoint"] == c2      # control: honest clock
    code, _ = h.plan("--confirm-sha", c1, mode="recover")
    assert code == 3
    code, _ = h.plan("--confirm-sha", c2, mode="recover")
    assert code == 0 and h.plan_doc()["refs"][EV]["new"] == c2
    for a in h.art.items:                                                  # the clock lies: c1 newest
        if a["name"] == gitstore.tip_name(EV, c1):
            a["created_at"] = "2026-10-14T11:30:00Z"
    h.art._publish()
    capsys.readouterr()
    code, out = h.plan()
    err = capsys.readouterr().err
    plan = h.plan_doc()
    assert code == 0 and out["foreign_tip"] == "true" and plan["refs"][EV]["verdict"] == "foreign"
    assert plan["refs"][EV]["checkpoint"] == c1 and out["derive_skipped"] == "true"
    assert "mark-order conflict" in err and c2[:8] in err
    assert "mark-order conflict" in (h.out / "summary.md").read_text()
    capsys.readouterr()
    code, _ = h.plan("--confirm-sha", c1, mode="recover")
    assert code == 3 and "mark-order conflict" in capsys.readouterr().err
    assert not (h.out / "plan.json").exists() and h.sb.remote(EV) == c1


def test_publish_order_and_rejection(h, monkeypatch, capsys):
    """Critique 21: publish pushes provenance first and provenance-site only after it pushed or was unchanged (or the plan derived from the checkpoint); a rejected evidence push → exit 3 and provenance-site is NOT pushed; a moved remote tip since the plan → exit 3; checkpoints.json names only verified tips."""
    order = _record_pushes(monkeypatch)
    c, d = _bootstrap(h)
    assert order == [("ff", EV), ("lease", DV)]
    ck = json.loads((h.out / "checkpoints.json").read_text())
    assert ck == {EV: {"format": "checkpoint@1", "ref": EV, "run_attempt": 1, "run_id": h.run_id, "sha": c},
                  DV: {"format": "checkpoint@1", "ref": DV, "run_attempt": 1, "run_id": h.run_id, "sha": d}}
    # Evidence push rejected (the remote moved since the plan) → exit 3, derived NOT pushed.
    h.add_live_run("design-run.yml", 801, "2026-10-13T10:00:00Z")
    code, out = h.plan()
    assert out["evidence_changed"] == "true" and out["site_changed"] == "true"
    mover = h.sb.commit(dict(h.sb.files_at(c), **{"raw/pr/5.json.gz": b"x"}), c)
    h.sb.push(mover, EV)
    order.clear()
    capsys.readouterr()
    pcode, pub = h.publish()
    assert pcode == 3 and "moved since the plan" in capsys.readouterr().err and order == []
    assert h.sb.remote(EV) == mover and h.sb.remote(DV) == d
    assert pub == {"evidence_tip": "", "foreign_tip": "false", "site_tip": ""}
    assert json.loads((h.out / "checkpoints.json").read_text()) == {EV: None, DV: None}
    # git itself rejects the fast-forward (e.g. a remote-side race the pre-check could not see).
    h.sb.push(c, EV, force=True)
    code, out = h.plan()
    real_tip = gitstore.remote_tip
    monkeypatch.setattr(gitstore, "remote_tip", lambda git, ref: real_tip(git, ref))
    h.sb.push(mover, EV, force=True)
    monkeypatch.setattr(gitstore.Git, "remote_heads", lambda self, refs: {EV: c, DV: d})
    order.clear()
    pcode, pub = h.publish()
    assert pcode == 3 and h.sb.remote(DV) == d and ("lease", DV) not in order
    monkeypatch.undo()
    # The derived ref moved since the plan → exit 3 before ANY push (evidence included).
    h2 = Harness(h.root / "second", monkeypatch)
    order2 = _record_pushes(monkeypatch)
    _bootstrap(h2)
    h2.add_live_run("design-run.yml", 802, "2026-10-13T10:00:00Z")
    code, out = h2.plan()
    ev_before = h2.sb.remote(EV)
    h2.sb.push(h2.sb.commit({"FORMAT": b"other\n"}, None), DV, force=True)
    order2.clear()
    pcode, pub = h2.publish()
    assert pcode == 3 and order2 == [] and h2.sb.remote(EV) == ev_before
    assert pub["evidence_tip"] == "" and pub["site_tip"] == ""


def test_repeat_harvest_pushes_nothing(h, monkeypatch):
    """A repeat dispatch with nothing new plans no change, pushes no commit, and checkpoints both
    unchanged (accepted) tips again."""
    c, d = _bootstrap(h)
    order = _record_pushes(monkeypatch)
    r = h.cycle()
    assert r["plan_out"]["evidence_changed"] == "false" and r["plan_out"]["site_changed"] == "false"
    assert order == [] and r["pub_out"] == {"evidence_tip": c, "foreign_tip": "false", "site_tip": d}
    assert not (h.out / f"intent-{EV}.json").exists() and not (h.out / f"intent-{DV}.json").exists()
    assert h.sb.remote(EV) == c and h.sb.remote(DV) == d


def test_gate_semantics(h, monkeypatch):
    """Critique 20: a dispatch's go = conf enabled; a schedule's go needs conf.armed (casefold) AND no OTHER provenance.yml run in status queued / in_progress / pending / waiting / requested in ONE unfiltered runs-list GET (a pending dispatch → go=false)."""
    monkeypatch.setattr(conf_mod, "armed", lambda enabled, var: bool(enabled) and (var or "").casefold() == "true")
    key = ("/actions/workflows/provenance.yml/runs", frozenset({("per_page", "100")}))

    def gate(*extra):
        h.fake.calls.clear()
        code, out = h.call("gate", *extra)
        assert code == 0
        return out["go"], list(h.fake.calls)

    assert gate() == ("true", [])                                    # a dispatch: conf enabled, no GET
    h.conf = conf_mod.Config(**{**h.conf.__dict__, "enabled": False})
    assert gate()[0] == "false" and gate("--scheduled", "--armed-var", "true")[0] == "false"
    h.conf = conf_mod.Config(**{**h.conf.__dict__, "enabled": True})
    assert gate("--scheduled", "--armed-var", "")[0] == "false"
    assert gate("--scheduled", "--armed-var", "false")[1] == []      # disarmed: no GET either
    h.fake.responses[key] = {"workflow_runs": [{"id": h.run_id, "status": "in_progress"},
                                               {"id": 1, "status": "completed"}]}
    go, calls = gate("--scheduled", "--armed-var", "TRUE")
    assert go == "true" and calls == [("/actions/workflows/provenance.yml/runs", {"per_page": "100"})]
    for status in sorted(cli.WAITING_STATUSES):
        h.fake.responses[key] = {"workflow_runs": [{"id": h.run_id, "status": "in_progress"},
                                                   {"id": 77, "status": status}]}
        assert gate("--scheduled", "--armed-var", "True")[0] == "false", status


def test_guard_drift_warns_not_fails(h, capsys):
    """Critique 18: with .github/data-branch-guard/vercel.json changed by one byte on main, a harvest over an existing evidence ref exits 0, emits ::warning:: naming the path, and its evidence commit leaves the guard files untouched; the derived tree carries main's new bytes."""
    c, _ = _bootstrap(h)
    path = h.sb.checkout / ".github" / "data-branch-guard" / "vercel.json"
    old = path.read_bytes()
    path.write_bytes(old + b" ")
    h.add_live_run("design-run.yml", 901, "2026-10-13T10:00:00Z")
    capsys.readouterr()
    code, out = h.plan()
    err = capsys.readouterr().err
    assert code == 0 and "::warning::guard drift: vercel.json" in err
    assert out["evidence_changed"] == "true"
    new = h.sb.files_at(out["evidence_sha"])
    assert new["vercel.json"] == old and new["receipts/2026/10/13/901.a1.json.gz"]
    assert h.sb.files_at(out["site_sha"])["vercel.json"] == old + b" "
    assert gitstore.guard_diff(h.sb.git, c, out["evidence_sha"])     # the guard accepts the commit


def test_failed_pr_head_fetch_skips_derive(h, monkeypatch, capsys):
    """Critique 9: a failed bulk PR-head fetch still plans evidence but no derived push (derive_skipped)."""
    _bootstrap(h)
    real = gitstore.Git.fetch_all

    def broken(self):
        out = real(self)
        out[gitstore.FETCH_REFSPECS[2]] = False
        return out
    monkeypatch.setattr(gitstore.Git, "fetch_all", broken)
    h.add_live_run("design-run.yml", 951, "2026-10-13T10:00:00Z")
    code, out = h.plan()
    assert code == 0 and out["derive_skipped"] == "true" and out["evidence_changed"] == "true"
    assert out["site_changed"] == "false"


def test_derive_exception_publishes_evidence_and_reports_derive_error(h, monkeypatch, capsys):
    """A derive bug does not block evidence capture (receipts expire) but never stays green: plan
    exits 0 with derive_skipped AND derive_error true (counts.derive_error names the type), publish
    pushes the evidence and checkpoints it, pushes no derived tip, and its summary line says the
    verdict step fails the job. Control: a healthy derive reports derive_error false."""
    from provenance import bundle
    c, d = _bootstrap(h)

    def broken(*a, **kw):
        raise KeyError("a derive-layer bug")
    monkeypatch.setattr(bundle, "derive", broken)
    h.add_live_run("design-run.yml", 961, "2026-10-13T10:00:00Z")
    capsys.readouterr()
    r = h.cycle()
    err = capsys.readouterr().err
    assert r["plan"] == 0 and r["publish"] == 0 and "::error::derive failed (KeyError" in err
    po = r["plan_out"]
    assert po["derive_error"] == "true" and po["derive_skipped"] == "true"
    assert po["evidence_changed"] == "true" and po["site_changed"] == "false"
    plan = h.plan_doc()
    assert plan["derive_error"] is True and plan["counts"]["derive_error"] == "KeyError"
    assert r["pub_out"]["evidence_tip"] == po["evidence_sha"] == h.sb.remote(EV) != c
    assert r["pub_out"]["site_tip"] == d == h.sb.remote(DV)       # the old derived tip, still verified
    assert "derive error: the verdict step fails the job" in (h.out / "summary.md").read_text()
    monkeypatch.undo()
    h2 = Harness(h.root / "healthy", monkeypatch)
    _bootstrap(h2)
    code, out = h2.plan()
    assert code == 0 and out["derive_error"] == "false" and h2.plan_doc()["derive_error"] is False


def test_freeze_calls_carry_run_id_and_since(h, monkeypatch):
    """H6's freeze contract: plan_freezes gets run_id (= --run-id, recorded as captured.run_id) and
    since (a dispatch's since, as RFC3339 — it lowers the PR/brief listing cursors; None without
    it); refreeze gets run_id, each plan is applied before the next PR's refreeze is planned (its
    frozen map sees the previous revision), and a budget-stopped refreeze ends the loop."""
    _bootstrap(h)
    seen = []
    h.freeze = lambda gh, **kw: seen.append(kw) or freeze.FreezePlan()
    code, _ = h.plan("--since", "2026-10-12")
    assert code == 0 and seen[-1]["run_id"] == h.run_id and seen[-1]["since"] == "2026-10-12T00:00:00Z"
    code, _ = h.plan("--since", "2026-10-12T06:30:00Z")
    assert code == 0 and seen[-1]["since"] == "2026-10-12T06:30:00Z"
    code, _ = h.plan()
    assert code == 0 and seen[-1]["since"] is None and seen[-1]["run_id"] == h.run_id
    calls = []

    def refreeze(gh, number, **kw):
        calls.append((number, kw["run_id"], dict(kw["frozen"]["pr"])))
        return freeze.FreezePlan(files={f"raw/pr/{number}.json.gz": canonical.dumps_gz({"pr": number})},
                                 frozen=[("pr", str(number), 1)], budget_stopped=number == 371)
    monkeypatch.setattr(freeze, "refreeze", refreeze)
    code, out = h.plan("--pr", "636,371,5", mode="refreeze")
    assert code == 0 and out["budget_stopped"] == "true"
    assert calls == [(5, h.run_id, {}), (371, h.run_id, {"5": 1})]   # 636 never planned: 371 stopped
    files = h.sb.files_at(out["evidence_sha"])
    assert "raw/pr/5.json.gz" in files and "raw/pr/371.json.gz" in files and "raw/pr/636.json.gz" not in files


def test_refreeze_of_an_unservable_pr_exits_1(h, monkeypatch, capsys):
    """freeze.CaptureError (H6: the operator named a PR GitHub cannot serve) maps to exit 1."""
    _bootstrap(h)

    class CaptureError(Exception):
        pass
    monkeypatch.setattr(freeze, "CaptureError", CaptureError, raising=False)

    def refreeze(gh, number, **kw):
        raise CaptureError(f"/pulls/{number} answered nothing")
    monkeypatch.setattr(freeze, "refreeze", refreeze)
    capsys.readouterr()
    code, out = h.plan("--pr", "999999", mode="refreeze")
    assert code == 1 and "CaptureError: /pulls/999999" in capsys.readouterr().err
    assert not (h.out / "plan.json").exists() and out == {}


@needs(freeze.plan_freezes, freeze.capture_release)
def test_live_freeze_records_the_run_id(h, monkeypatch):
    """At integration (H6's real freeze pass): a raw document a harvest plans carries
    captured.run_id == --run-id (never the fixture sentinel 0), through plan → publish."""
    _bootstrap(h)
    monkeypatch.setattr(freeze, "plan_freezes", REAL_PLAN_FREEZES)
    h.fake.responses[("/releases", frozenset())] = [{
        "assets": [], "author": {"login": "octo", "type": "User"}, "body": "notes",
        "created_at": "2026-10-13T09:00:00Z", "draft": False, "id": 4242, "name": "v9.9",
        "prerelease": False, "published_at": "2026-10-13T10:00:00Z", "tag_name": "v9.9",
        "target_commitish": "main"}]
    r = h.cycle()
    assert r["plan"] == 0 and r["publish"] == 0
    doc = json.loads(gzip.decompress(h.sb.files_at(r["pub_out"]["evidence_tip"])["raw/release/v9.9.json.gz"]))
    assert doc["captured"]["run_id"] == h.run_id != 0


def test_refreeze_adds_one_revision(h, monkeypatch, capsys):
    """refreeze wiring: freeze.refreeze's one new path lands in an add-only evidence commit; a
    foreign evidence tip refuses refreeze (exit 3)."""
    c, _ = _bootstrap(h)
    r2 = canonical.dumps_gz({"format": "raw-pr@1", "pr": 636, "revision": 2})
    calls = []

    def refreeze(gh, number, **kw):
        calls.append(number)
        return freeze.FreezePlan(files={f"raw/pr/{number}.r2.json.gz": r2}, frozen=[("pr", str(number), 2)])
    monkeypatch.setattr(freeze, "refreeze", refreeze)
    r = h.cycle("--pr", "636", mode="refreeze")
    assert r["plan"] == 0 and calls == [636]
    tip = r["pub_out"]["evidence_tip"]
    changes = gitstore.guard_diff(h.sb.git, c, tip)
    assert [(ch.status, ch.path) for ch in changes] == [("A", "raw/pr/636.r2.json.gz")]
    f = h.sb.commit(dict(h.sb.files_at(tip), **{"raw/pr/1.json.gz": b"x"}), tip)
    h.sb.push(f, EV)
    code, _ = h.plan("--pr", "636", mode="refreeze")
    assert code == 3


def test_apply_freeze_updates_state_through_state_py():
    from provenance import state as state_mod
    st = state_mod.empty_state({})
    state_mod.set_pending(st, "pr", "5", closed_at="2026-10-01T00:00:00Z", due_at="2026-10-01T06:00:00Z",
                          defer_until="2026-10-02T00:00:00Z", reasons=[])
    state_mod.set_skipped(st, 6, "2026-10-01T00:00:00Z")
    fp = freeze.FreezePlan(
        pending={"pr": {"7": {"closed_at": "2026-10-03T00:00:00Z", "defer_until": "2026-10-04T00:00:00Z",
                              "due_at": "2026-10-03T06:00:00Z", "reasons": ["settle-deferred"]}}},
        frozen=[("pr", "5", 1), ("pr", "6", 1)], skipped_prs={8: "2026-10-03T00:00:00Z"},
        cursors={"prs_updated": "2026-10-03T00:00:00Z", "briefs_updated": None})
    cli._apply_freeze(st, fp)
    assert sorted(st["pending"]["pr"]) == ["7"] and sorted(st["skipped"]["pr"]) == ["8"]
    assert st["cursors"]["prs_updated"] == "2026-10-03T00:00:00Z" and st["cursors"]["briefs_updated"] is None
    with pytest.raises(ValueError):
        cli._apply_freeze(st, freeze.FreezePlan(pending={"636": {}}))


def test_apply_freeze_replaces_pending_and_honours_cleared():
    """H6's contract: FreezePlan.pending is the COMPLETE new map per kind it names — a stored entry
    it no longer holds leaves (a reopened or unchanged PR/brief cannot stay pending forever, which
    would make Reeve's provenance-lag report it overdue permanently); a kind it does not name keeps
    its entries; every FreezePlan.cleared unit leaves pending; a cleared kind outside pr/brief is
    refused."""
    from provenance import state as state_mod
    entry = {"closed_at": "2026-10-01T00:00:00Z", "defer_until": "2026-10-02T00:00:00Z",
             "due_at": "2026-10-01T06:00:00Z", "reasons": []}
    st = state_mod.empty_state({})
    for kind, key in (("pr", "5"), ("pr", "6"), ("brief", "40"), ("brief", "41")):
        state_mod.set_pending(st, kind, key, **entry)
    # The PR map is replaced: 5 carried over (re-deferred), 6 dropped (reopened), 9 new; briefs untouched.
    fp = freeze.FreezePlan(pending={"pr": {"5": dict(entry, reasons=["settle-deferred"]), "9": entry}})
    cli._apply_freeze(st, fp)
    assert sorted(st["pending"]["pr"]) == ["5", "9"] and st["pending"]["pr"]["5"]["reasons"] == ["settle-deferred"]
    assert sorted(st["pending"]["brief"]) == ["40", "41"]
    # cleared (H6's field; absent from the scaffold's dataclass, so set as an attribute) removes units.
    fp = freeze.FreezePlan()
    fp.cleared = [("brief", "41"), ("pr", "9")]
    cli._apply_freeze(st, fp)
    assert sorted(st["pending"]["pr"]) == ["5"] and sorted(st["pending"]["brief"]) == ["40"]
    # An empty map for a kind is "nothing pending of that kind" — a replacement, not a no-op.
    cli._apply_freeze(st, freeze.FreezePlan(pending={"pr": {}, "brief": {"40": entry}}))
    assert st["pending"] == {"pr": {}, "brief": {"40": entry}}
    bad = freeze.FreezePlan()
    bad.cleared = [("release", "v1")]
    with pytest.raises(ValueError):
        cli._apply_freeze(st, bad)


def _export(h, sha, dest):
    for path, data in h.sb.files_at(sha).items():
        p = dest.joinpath(*path.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        if h.sb.git.tree_entries(sha)[path][0] == "100755":
            p.chmod(0o755)
    return dest


def test_check_dir_wires_validate_tree(h, tmp_path, monkeypatch, capsys):
    """check --dir --kind: contract.validate_tree's errors → exit 1 (each an ::error::), none → 0;
    guard drift from main's .github/data-branch-guard/* is a ::warning::, never an error."""
    c, _ = _bootstrap(h)
    tree = _export(h, c, tmp_path / "tree")
    seen = []
    monkeypatch.setattr(contract, "validate_tree",
                        lambda reader, kind: seen.append((kind, len(reader.paths()))) or
                        ([] if kind == "evidence" else ["$.site/bundle.json: missing"]))
    argv = ["check", "--dir", str(tree), "--repo-dir", str(h.sb.checkout)]
    assert cli.main(argv + ["--kind", "evidence"]) == 0
    assert cli.main(argv + ["--kind", "derived"]) == 1
    assert seen == [("evidence", 11), ("derived", 11)]
    err = capsys.readouterr().err
    assert "::error::$.site/bundle.json: missing" in err and "guard drift" not in err
    (tree / "vercel.json").write_bytes(b"{}\n")
    assert cli.main(argv + ["--kind", "evidence"]) == 0
    assert "::warning::guard drift: vercel.json" in capsys.readouterr().err
    assert cli.main(["check", "--dir", str(tmp_path / "nope"), "--kind", "evidence"]) == 1


@needs(contract.validate_tree)
def test_bootstrapped_evidence_tree_passes_check(h, tmp_path):
    """At integration: the evidence root a bootstrap harvest writes (guard files, README, FORMAT,
    state.json, the ingest) passes the real contract.validate_tree through check --dir."""
    c, _ = _bootstrap(h)
    tree = _export(h, c, tmp_path / "tree")
    assert cli.main(["check", "--dir", str(tree), "--kind", "evidence", "--repo-dir", str(h.sb.checkout)]) == 0


def _upload_steps(text):
    """``(artifact name, path, if)`` of every actions/upload-artifact step in a workflow's text."""
    steps = re.split(r"\n\s*- name: ", text)
    out = []
    for step in steps:
        if "uses: actions/upload-artifact" not in step:
            continue
        name = re.search(r"\n\s+name: (\S+)", step)
        path = re.search(r"\n\s+path: (\S+)", step)
        cond = re.search(r"\n\s+if: (.+)", step)
        out.append((name.group(1) if name else "", path.group(1) if path else "",
                    cond.group(1).strip() if cond else ""))
    return out


def test_workflow_uploads_the_files_publish_writes():
    """The plan/publish file contract seen from the workflow (H6's provenance.yml; skipped until it
    exists): each intent upload's path is ``<out-dir>/`` + cli.intent_file(ref) and each checkpoint
    upload's path ``<out-dir>/`` + cli.tip_file(ref) — a mismatch with ``if-no-files-found: error``
    fails every non-dry run and no checkpoint is ever uploaded; and each checkpoint step runs even
    when publish failed after a verified push (``!cancelled()`` or ``always()``), or the evidence
    tip pushed before a derived rejection is never checkpointed and the next run refuses it."""
    wf = REPO / ".github" / "workflows" / "provenance.yml"
    if not wf.exists():
        pytest.skip("waits for H6's .github/workflows/provenance.yml")
    text = wf.read_text(encoding="utf-8")
    out_dir = re.search(r"publish --out-dir (\S+)", text)
    assert out_dir, "the publish step names its --out-dir"
    uploads = _upload_steps(text)
    for kind, fname in (("intent", cli.intent_file), ("tip", cli.tip_file)):
        for ref in (EV, DV):
            prefix = f"{kind}-{ref}-${{{{"
            hits = [(p, c) for n, p, c in uploads if n.startswith(prefix)]
            assert len(hits) == 1, (kind, ref, uploads)
            path, cond = hits[0]
            assert path == f"{out_dir.group(1)}/{fname(ref)}", (kind, ref, path)
            if kind == "tip":
                assert "!cancelled()" in cond or "always()" in cond, (ref, cond)


def test_upload_step_parser_can_fail():
    """Negative control for the workflow pin's parser: a wrong path and a bare if are seen as such."""
    text = ("steps:\n      - name: Checkpoint the evidence tip\n        if: steps.publish.outputs.evidence_tip != ''\n"
            "        uses: actions/upload-artifact@v7\n        with:\n          name: tip-provenance-${{ x }}\n"
            "          path: .provenance/checkpoint-provenance.json\n")
    [(name, path, cond)] = _upload_steps(text)
    assert name.startswith("tip-provenance-${{") and path != f".provenance/{cli.tip_file(EV)}"
    assert "!cancelled()" not in cond and "always()" not in cond


def test_outputs_validate_shas(tmp_path):
    out = tmp_path / "o"
    cli.write_outputs(str(out), {"evidence_tip": "a" * 40, "site_tip": "", "go": True, "mode": "harvest"})
    assert out.read_text() == f"evidence_tip={'a' * 40}\nsite_tip=\ngo=true\nmode=harvest\n"
    for bad in ({"evidence_sha": "A" * 40}, {"site_tip": "x"}, {"mode": "a\nb=c"}):
        with pytest.raises(ValueError):
            cli.write_outputs(str(out), bad)


def test_input_floor_and_repo_validation(h, capsys):
    code, _ = h.plan("--since", "2026-07-01")
    assert code == 1 and "backfill_since" in capsys.readouterr().err
    code, _ = h.plan("--since", "2026-10-12", "--until", "2026-10-11")
    assert code == 1
    assert cli.main(["gate", "--repo", "not a repo", "--conf", "x"]) == 1


def test_validate_inputs_accepts_the_documented_shapes():
    from provenance.cli import validate_inputs
    v = validate_inputs(since="2026-07-31", until="2026-10-13T00:00:00Z", pr="636,371,636",
                        max_requests="400", confirm_sha="a" * 40)
    assert v.prs == (371, 636) and v.max_requests == 400 and v.confirm_sha == "a" * 40
    assert validate_inputs(since="", pr="").prs == ()


@pytest.mark.parametrize("kw", [
    {"since": "2026-07-31; rm -rf /"}, {"since": "2026-7-31"}, {"pr": "636,"}, {"pr": "6 36"},
    {"max_requests": "123456"}, {"confirm_sha": "A" * 40}, {"until": "2026-10-13T00:00:00"},
])
def test_validate_inputs_refuses(kw):
    from provenance.cli import InputError, validate_inputs
    with pytest.raises(InputError):
        validate_inputs(**kw)


def test_no_snapshot_or_ref_inputs():
    """Critique 2/17: no input, option or subcommand can point the ingest at a ref or a path."""
    import inspect

    from provenance.cli import COMMANDS, build_parser, validate_inputs
    assert set(COMMANDS) == {"harvest", "refreeze", "publish", "recover", "gate", "check", "selftest"}
    assert not {"snapshot_ref", "snapshot_path", "snapshot_id"} & set(inspect.signature(validate_inputs).parameters)
    ap = build_parser()
    for bad in (["ingest", "--ref", "x"], ["harvest", "--ref", "x"], ["harvest", "--path", "x"],
                ["config", "--get", "enabled"], ["check", "--ref", "provenance"]):
        with pytest.raises(SystemExit):
            ap.parse_args(bad)


def test_parser_knows_every_mode():
    from provenance.cli import COMMANDS, build_parser
    ap = build_parser()
    for cmd in COMMANDS:
        assert ap.parse_args([cmd] + {"refreeze": ["--pr", "1"],
                                      "recover": ["--confirm-sha", "a" * 40],
                                      "check": ["--dir", ".", "--kind", "evidence"]}.get(cmd, [])).cmd == cmd
    assert ap.parse_args(["harvest", "--bootstrap", "--snapshot-dir", "d"]).bootstrap is True
