"""provenance.py — Reeve's lens on the provenance harvester (docs/provenance.md §Registration).

The continuity port runs EVERY row of the one shared table
(``tools/provenance/tests/fixtures/continuity_cases.json``) — the harvester's
``gitstore.continuity_verdict`` runs the same file, so neither implementation
can drift alone. Each detector has a positive case and a negative control;
the gather is driven through ``github._get`` (monkeypatched — no request
leaves the process), and its read surface is pinned to GETs of the closed set
of endpoints the design names.
"""

from __future__ import annotations

import base64
import copy
import json
import pathlib
import re
from datetime import datetime, timezone

import pytest

from reeve import config, detectors, github, provenance
from reeve.cli import main
from reeve.config import Config

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
TABLE = REPO_ROOT / "tools" / "provenance" / "tests" / "fixtures" / "continuity_cases.json"
CASES = json.loads(TABLE.read_text(encoding="utf-8"))["cases"]
NOW = "2026-08-16T06:00:00Z"
E_C, E_FORGED, S_C = "43" * 20, "46" * 20, "44" * 20


# --- the shared continuity table, row for row ---------------------------------

@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_continuity_port_agrees_with_the_shared_table(case):
    kw = {"max_chain": case["max_chain"]} if "max_chain" in case else {}
    v = provenance.continuity_verdict(ref=case["ref"], tip=case["tip"], marks=case["marks"],
                                      first_parent=lambda s: case["parents"].get(s), **kw)
    assert v["verdict"] == case["expect"], v["reason"]
    if "chain" in case:
        assert v["chain"] == case["chain"]


def test_shared_table_covers_every_verdict_and_both_refs():
    assert {c["expect"] for c in CASES} == set(provenance.VERDICTS)
    assert {c["ref"] for c in CASES} == set(provenance.REFS)
    assert len(CASES) >= 23


def test_port_refuses_an_unknown_ref():
    with pytest.raises(ValueError):
        provenance.continuity_verdict(ref="telemetry", tip=None, marks=[], first_parent=dict().get)


def test_mark_names_parse_and_refuse():
    sha = "a1" * 20
    assert provenance.parse_mark_name(f"tip-provenance-site-{sha}") == ("tip", "provenance-site", sha)
    assert provenance.parse_mark_name(f"intent-provenance-{sha}") == ("intent", "provenance", sha)
    for bad in (f"tip-provenance-{'A1' * 20}", f"tip-provenance-{sha[:39]}", f"tip-other-{sha}",
                f"checkpoint-provenance-{sha}", f"intent-provenance-site-{sha}0", "site", None):
        assert provenance.parse_mark_name(bad) is None


# --- the two detectors (pure) ----------------------------------------------------

def mark(seq, kind, ref, sha, run_id=1000):
    return {"seq": seq, "kind": kind, "ref": ref, "sha": sha, "run_id": run_id}


def block(**over):
    b = {
        "armed": True,
        "conf": {"settle_hours": 6, "max_defer_hours": 24},
        "tips": {"provenance": E_C, "provenance-site": S_C},
        "marks": [mark(12, "tip", "provenance-site", S_C), mark(11, "tip", "provenance", E_C)],
        "parents": {},
        "scan": {"pages": 1, "runs_verified": 1, "marks_rejected": 0},
        "state": {"pending": {"pr": {}, "brief": {}}, "skipped": {"pr": {}}},
        "frozen_prs": [636],
        "closed_prs": [{"number": 636, "closed_at": "2026-08-10T00:00:00Z"}],
    }
    b.update(over)
    return b


def test_foreign_tip_fires_on_a_forged_evidence_tip():
    found = provenance.foreign_tip(block(tips={"provenance": E_FORGED, "provenance-site": S_C}))
    assert [(f["ref"], f["verdict"]) for f in found] == [("provenance", "foreign")]
    assert found[0]["tip"] == E_FORGED[:8] and found[0]["checkpoint"] == E_C[:8]


def test_foreign_tip_silent_when_both_tips_are_their_checkpoints():          # negative control
    assert provenance.foreign_tip(block()) == []


def test_foreign_tip_silent_on_a_declared_chain_after_the_checkpoint():      # negative control
    died = "58" * 20   # a run pushed and died before checkpointing — accepted
    b = block(tips={"provenance": died, "provenance-site": S_C},
              marks=block()["marks"] + [mark(13, "intent", "provenance", died)],
              parents={died: E_C})
    assert provenance.foreign_tip(b) == []


@pytest.mark.parametrize("tips,marks,expect", [
    ({"provenance": None, "provenance-site": S_C}, None, ("provenance", "deleted")),
    ({"provenance": E_C, "provenance-site": S_C},
     [mark(12, "tip", "provenance-site", S_C)], ("provenance", "unanchored")),
    ({"provenance": None, "provenance-site": S_C},
     [mark(12, "tip", "provenance-site", S_C)], ("provenance", "bootstrap")),
    ({"provenance": E_C, "provenance-site": "45" * 20}, None, ("provenance-site", "foreign")),
])
def test_every_non_ok_verdict_is_a_finding_once_armed(tips, marks, expect):
    b = block(tips=tips) if marks is None else block(tips=tips, marks=marks)
    assert [(f["ref"], f["verdict"]) for f in provenance.foreign_tip(b)] == [expect]


def _pending(due_at):
    return {"pr": {"902": {"closed_at": "2026-08-14T12:00:00Z", "due_at": due_at,
                           "defer_until": "2026-08-15T12:00:00Z", "reasons": []}}, "brief": {}}


def test_lag_fires_on_the_oldest_overdue_unit():
    st = {"pending": _pending("2026-08-14T18:00:00Z"), "skipped": {"pr": {}}}
    st["pending"]["brief"]["901"] = {"closed_at": None, "due_at": "2026-08-15T20:00:00Z",
                                     "defer_until": "2026-08-15T20:00:00Z", "reasons": []}
    found = provenance.lag(block(state=st), NOW, 3)
    assert found == [{"kind": "overdue", "unit": "pr #902", "due_at": "2026-08-14T18:00:00Z",
                      "hours_past": 33.0, "count": 2}]


def test_lag_silent_inside_the_grace():                                      # negative control
    st = {"pending": _pending("2026-08-16T04:00:00Z"), "skipped": {"pr": {}}}   # 2h past, grace 3h
    assert provenance.lag(block(state=st), NOW, 3) == []


def test_lag_stall_check_fires_on_an_unseen_closed_pr():
    closed = [{"number": 700, "closed_at": "2026-08-14T20:00:00Z"},     # 34h ago > 6 + 24 + 3
              {"number": 701, "closed_at": "2026-08-15T12:00:00Z"},     # 18h ago: still inside
              {"number": 636, "closed_at": "2026-08-10T00:00:00Z"}]     # frozen
    found = provenance.lag(block(closed_prs=closed), NOW, 3)
    assert found == [{"kind": "stall", "prs": [700], "count": 1, "window_hours": 33}]


def test_lag_stall_check_silent_when_every_old_pr_is_accounted_for():        # negative control
    closed = [{"number": n, "closed_at": "2026-08-01T00:00:00Z"} for n in (636, 800, 902)]
    st = {"pending": _pending("2026-08-16T05:00:00Z"), "skipped": {"pr": {"800": {"closed_at": "x"}}}}
    assert provenance.lag(block(closed_prs=closed, state=st), NOW, 3) == []
    # … and the window comes from the harvester's conf plus Reeve's grace: a shorter one fires.
    assert provenance.lag(block(closed_prs=[{"number": 1, "closed_at": "2026-08-16T00:00:00Z"}],
                                conf={"settle_hours": 1, "max_defer_hours": 2}), NOW, 1)


def test_lag_reports_an_absent_evidence_ref_once_armed():
    found = provenance.lag(block(tips={"provenance": None, "provenance-site": None}), NOW, 3)
    assert [f["kind"] for f in found] == ["no-evidence"]


# --- evaluate: "not evaluated" only while disarmed or offline ---------------------

def _snapshot(prov):
    rh = {"gatheredAt": NOW, "workflows": [], "issues": [], "openPRs": [], "branches": []}
    if prov is not None:
        rh["provenance"] = prov
    return {"generatedAt": NOW, "records": [], "previews": [], "reportPlaceholder": False,
            "runHealth": rh}


def test_evaluate_disarmed_is_not_evaluated_with_the_reason():
    res = detectors.evaluate(_snapshot({"armed": False, "reason": "PROVENANCE_ENABLED is not 'true'"}),
                             Config())
    assert res["not_evaluated"]["provenance-foreign-tip"] == "PROVENANCE_ENABLED is not 'true'"
    assert res["not_evaluated"]["provenance-lag"] == "PROVENANCE_ENABLED is not 'true'"
    assert "provenance-lag" not in res["findings"]


def test_evaluate_offline_and_absent_block_are_not_evaluated():
    offline = {"generatedAt": NOW, "records": [], "previews": [], "reportPlaceholder": False}
    assert "pass --repo" in detectors.evaluate(offline, Config())["not_evaluated"]["provenance-lag"]
    assert "provenance-lag" in detectors.evaluate(_snapshot(None), Config())["not_evaluated"]


def test_evaluate_armed_evaluates_and_an_absent_ref_is_a_finding_not_a_skip():
    res = detectors.evaluate(_snapshot(block(tips={"provenance": None, "provenance-site": None},
                                             marks=[])), Config())
    assert "provenance-foreign-tip" not in res["not_evaluated"]
    assert [f["verdict"] for f in res["findings"]["provenance-foreign-tip"]] == ["bootstrap", "bootstrap"]
    assert [f["kind"] for f in res["findings"]["provenance-lag"]] == ["no-evidence"]
    clean = detectors.evaluate(_snapshot(block()), Config())
    assert clean["findings"]["provenance-foreign-tip"] == [] and clean["findings"]["provenance-lag"] == []


def test_evaluate_uses_reeve_s_own_lag_threshold():
    st = {"pending": _pending("2026-08-15T22:00:00Z"), "skipped": {"pr": {}}}   # 8h past due
    snap = _snapshot(block(state=st))
    assert detectors.evaluate(snap, Config(provenance_lag_hours=3))["findings"]["provenance-lag"]
    assert detectors.evaluate(snap, Config(provenance_lag_hours=9))["findings"]["provenance-lag"] == []


# --- the conf Reeve reads from the harvester, and the arming ------------------------

def test_committed_provenance_conf_is_readable():
    conf = provenance.read_conf((REPO_ROOT / ".github" / "provenance.conf").read_text(encoding="utf-8"))
    assert conf == {"enabled": True, "settle_hours": 6, "max_defer_hours": 24,
                    "continuity_horizon_days": 90}


@pytest.mark.parametrize("text,pattern", [
    ("enabled: true\nsettle_hours: 6\nmax_defer_hours: 24\n", "missing continuity_horizon_days"),
    ("enabled: maybe\nsettle_hours: 6\nmax_defer_hours: 24\ncontinuity_horizon_days: 90\n", "'enabled'"),
    ("enabled: true\nsettle_hours: 6.5\nmax_defer_hours: 24\ncontinuity_horizon_days: 90\n", "settle_hours"),
])
def test_conf_reader_refuses_rather_than_defaulting(text, pattern):
    with pytest.raises(ValueError, match=pattern):
        provenance.read_conf(text)


@pytest.mark.parametrize("enabled,variable,expected", [
    (True, "true", True), (True, "TRUE", True), (True, "True", True),
    (True, " true", False), (True, "1", False), (True, "", False), (True, None, False),
    (False, "true", False),
])
def test_armed_matches_the_harvester_two_key_rule(enabled, variable, expected):
    assert provenance.armed(enabled, variable) is expected


def test_provenance_lag_hours_is_reeve_s_own_key(tmp_path):
    assert Config().provenance_lag_hours == 3
    committed = config.load(str(REPO_ROOT / ".github" / "reeve.conf"))
    assert committed.provenance_lag_hours == 3
    p = tmp_path / "r.conf"
    p.write_text("provenance_lag_hours: 5\n", encoding="utf-8")
    assert config.load(str(p)).provenance_lag_hours == 5
    for bad in ("0", "-1", "1.5", "three"):
        p.write_text(f"provenance_lag_hours: {bad}\n", encoding="utf-8")
        with pytest.raises(ValueError, match="provenance_lag_hours"):
            config.load(str(p))


# --- the GET-only gather ----------------------------------------------------------

class _NotFound(Exception):
    code = 404


def _b64(doc):
    return base64.b64encode(json.dumps(doc).encode()).decode()


def _api(path):
    return f"{github.API_ROOT}/repos/o/r{path}"


def _art(aid, name, run_id, branch="main", created="2026-08-16T05:30:00Z"):
    return {"id": aid, "name": name, "created_at": created,
            "workflow_run": {"id": run_id, "head_branch": branch, "head_sha": "ff" * 20}}


def _world():
    root_tree, raw_tree, pr_tree = "a0" * 20, "a1" * 20, "a2" * 20
    state = {"format": "state@1", "pending": {"pr": {"902": {"closed_at": "2026-08-15T00:00:00Z",
                                                            "due_at": "2026-08-15T06:00:00Z",
                                                            "defer_until": "2026-08-16T00:00:00Z",
                                                            "reasons": []}}, "brief": {}},
             "skipped": {"pr": {"800": {"closed_at": "2026-08-01T00:00:00Z"}}}, "cursors": {}}
    return {
        _api("/git/ref/heads/provenance"): {"object": {"sha": E_FORGED}},
        _api("/git/ref/heads/provenance-site"): {"object": {"sha": S_C}},
        _api("/actions/artifacts?per_page=100"): {"artifacts": [
            _art(20, f"intent-provenance-{'99' * 20}", 77, branch="evil"),       # off-branch: rejected
            _art(19, f"tip-provenance-{'98' * 20}", 78),                          # wrong workflow: rejected
            _art(18, "telemetry-record", 79),                                     # not a mark
            _art(17, f"tip-provenance-site-{S_C}", 80),
            _art(16, f"tip-provenance-{E_C}", 80),
            _art(5, f"tip-provenance-{'97' * 20}", 80, created="2026-01-01T00:00:00Z"),  # past horizon
        ]},
        _api("/actions/runs/80"): {"path": ".github/workflows/provenance.yml", "event": "schedule",
                                   "head_branch": "main"},
        _api("/actions/runs/78"): {"path": ".github/workflows/ci.yml", "event": "schedule",
                                   "head_branch": "main"},
        _api(f"/git/commits/{E_FORGED}"): {"parents": [{"sha": E_C}], "tree": {"sha": root_tree}},
        _api(f"/git/trees/{root_tree}"): {"tree": [{"path": "raw", "type": "tree", "sha": raw_tree},
                                                   {"path": "state.json", "type": "blob", "sha": "b" * 40}]},
        _api(f"/git/trees/{raw_tree}"): {"tree": [{"path": "pr", "type": "tree", "sha": pr_tree}]},
        _api(f"/git/trees/{pr_tree}"): {"tree": [{"path": "636.json.gz", "type": "blob"},
                                                 {"path": "636.r2.json.gz", "type": "blob"},
                                                 {"path": "371.json.gz", "type": "blob"},
                                                 {"path": "README", "type": "blob"}]},
        _api(f"/contents/state.json?ref={E_FORGED}"): {"encoding": "base64", "content": _b64(state),
                                                       "sha": "b" * 40},
        _api("/pulls?state=closed&sort=updated&direction=desc&per_page=100"): [
            {"number": 636, "closed_at": "2026-08-10T00:00:00Z"},
            {"number": 700, "closed_at": "2026-08-14T00:00:00Z"}],
    }


def _patch(monkeypatch, world, seen):
    def fake(url, token):
        seen.append(url)
        if url not in world:
            raise _NotFound(url)
        return copy.deepcopy(world[url]), ""

    monkeypatch.setattr(github, "_get", fake)


def test_gather_disarmed_sends_nothing(monkeypatch, tmp_path):
    def boom(url, token):
        raise AssertionError(f"a disarmed gather sent {url}")

    monkeypatch.setattr(github, "_get", boom)
    for variable in (None, "", "false", " true", "1"):
        out = provenance.gather("o/r", "tok", root=str(tmp_path), variable=variable)
        assert out["armed"] is False and "PROVENANCE_ENABLED" in out["reason"]
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "provenance.conf").write_text(
        "enabled: false\nsettle_hours: 6\nmax_defer_hours: 24\ncontinuity_horizon_days: 90\n",
        encoding="utf-8")
    paused = provenance.gather("o/r", "tok", root=str(tmp_path), variable="true")
    assert paused["armed"] is False and "enabled: false" in paused["reason"]


def test_gather_armed_reads_the_closed_set_of_endpoints(monkeypatch):
    seen: list[str] = []
    _patch(monkeypatch, _world(), seen)
    out = provenance.gather("o/r", "tok", root=str(REPO_ROOT), variable="TRUE",
                            now=datetime(2026, 8, 16, 6, 0, tzinfo=timezone.utc))
    assert out["armed"] is True
    assert out["tips"] == {"provenance": E_FORGED, "provenance-site": S_C}
    assert out["marks"] == [mark(17, "tip", "provenance-site", S_C, 80),
                            mark(16, "tip", "provenance", E_C, 80)]
    assert out["scan"] == {"pages": 1, "runs_verified": 1, "marks_rejected": 2}
    assert out["parents"] == {}                     # the forged tip is not a declared intent
    assert out["frozen_prs"] == [371, 636]
    assert out["state"]["pending"]["pr"]["902"]["due_at"] == "2026-08-15T06:00:00Z"
    assert out["state"]["skipped"]["pr"] == {"800": {"closed_at": "2026-08-01T00:00:00Z"}}
    assert out["closed_prs"] == [{"number": 636, "closed_at": "2026-08-10T00:00:00Z"},
                                 {"number": 700, "closed_at": "2026-08-14T00:00:00Z"}]
    assert out["conf"] == {"settle_hours": 6, "max_defer_hours": 24}
    # Every request is one of the design's reads, under this repo, through the GET seam.
    allowed = re.compile(
        r"https://api\.github\.com/repos/o/r/(git/ref/heads/(provenance|provenance-site)"
        r"|actions/artifacts\?per_page=100|actions/runs/[0-9]+|git/commits/[0-9a-f]{40}"
        r"|git/trees/[0-9a-f]{40}|git/blobs/[0-9a-f]{40}|contents/state\.json\?ref=[0-9a-f]{40}"
        r"|pulls\?state=closed&sort=updated&direction=desc&per_page=100)")
    assert seen and all(allowed.fullmatch(u) for u in seen), seen
    assert _api("/actions/runs/77") not in seen     # an off-branch mark costs no run GET
    # … and the detectors over that block find the forged tip and the stall.
    res = detectors.evaluate(_snapshot(out), Config())
    assert [f["verdict"] for f in res["findings"]["provenance-foreign-tip"]] == ["foreign"]
    assert {f["kind"] for f in res["findings"]["provenance-lag"]} == {"overdue", "stall"}


def test_gather_walks_first_parents_for_a_declared_chain(monkeypatch):
    world = _world()
    died = "58" * 20
    world[_api("/git/ref/heads/provenance")] = {"object": {"sha": died}}
    world[_api("/actions/artifacts?per_page=100")]["artifacts"].insert(
        0, _art(21, f"intent-provenance-{died}", 80))
    world[_api(f"/git/commits/{died}")] = {"parents": [{"sha": E_C}], "tree": {"sha": "a0" * 20}}
    world[_api(f"/contents/state.json?ref={died}")] = world.pop(_api(f"/contents/state.json?ref={E_FORGED}"))
    seen: list[str] = []
    _patch(monkeypatch, world, seen)
    out = provenance.gather("o/r", "tok", root=str(REPO_ROOT), variable="true",
                            now=datetime(2026, 8, 16, 6, 0, tzinfo=timezone.utc))
    assert out["parents"] == {died: E_C}
    assert provenance.foreign_tip(out) == []
    assert seen.count(_api(f"/git/commits/{died}")) == 1        # memoised: walk + tree share it


def test_gather_absent_refs_are_none_not_errors(monkeypatch):
    world = _world()
    del world[_api("/git/ref/heads/provenance")]
    del world[_api("/git/ref/heads/provenance-site")]
    _patch(monkeypatch, world, [])
    out = provenance.gather("o/r", "tok", root=str(REPO_ROOT), variable="true",
                            now=datetime(2026, 8, 16, 6, 0, tzinfo=timezone.utc))
    assert out["tips"] == {"provenance": None, "provenance-site": None}
    assert out["state"] == {} and out["frozen_prs"] == []
    assert [f["verdict"] for f in provenance.foreign_tip(out)] == ["deleted", "deleted"]


def test_gather_fails_loud_on_anything_but_a_404(monkeypatch):
    class Forbidden(Exception):
        code = 403

    def fake(url, token):
        raise Forbidden(url)

    monkeypatch.setattr(github, "_get", fake)
    with pytest.raises(Forbidden):
        provenance.gather("o/r", "tok", root=str(REPO_ROOT), variable="true")


def test_gather_refuses_a_runaway_artifact_scan(monkeypatch):
    world = _world()
    page = {"artifacts": [_art(1, "telemetry-record", 1)]}

    nxt = _api("/actions/artifacts?per_page=100&page=2")

    def fake(url, token):
        if "/actions/artifacts" in url:
            return copy.deepcopy(page), f'<{nxt}>; rel="next"'
        if url in world:
            return copy.deepcopy(world[url]), ""
        raise _NotFound(url)

    monkeypatch.setattr(github, "_get", fake)
    monkeypatch.setattr(provenance, "MAX_ARTIFACT_PAGES", 3)
    with pytest.raises(RuntimeError, match="more than 3 artifact pages"):
        provenance.gather("o/r", "tok", root=str(REPO_ROOT), variable="true")


def test_gather_never_follows_a_next_link_off_the_api(monkeypatch):
    world = _world()
    page = {"artifacts": [_art(1, "telemetry-record", 1)]}

    def fake(url, token):
        if "/actions/artifacts" in url:
            return copy.deepcopy(page), '<https://evil.example/steal>; rel="next"'
        if url in world:
            return copy.deepcopy(world[url]), ""
        raise AssertionError(f"followed {url}")

    monkeypatch.setattr(github, "_get", fake)
    with pytest.raises(RuntimeError, match="off api.github.com"):
        provenance.gather("o/r", "tok", root=str(REPO_ROOT), variable="true")


def test_cli_run_with_repo_hands_the_variable_to_the_gather(tmp_path, monkeypatch, capsys):
    (tmp_path / "telemetry").mkdir()
    monkeypatch.setattr("reeve.github.gather_run_health",
                        lambda repo, token, now=None: {"gatheredAt": NOW, "workflows": [],
                                                       "issues": [], "openPRs": [], "branches": []})
    got = {}

    def fake_gather(repo, token, *, root, variable):
        got["variable"] = variable
        return {"armed": False, "reason": "PROVENANCE_ENABLED is not 'true' (test)"}

    monkeypatch.setattr("reeve.provenance.gather", fake_gather)
    monkeypatch.setenv("PROVENANCE_ENABLED", "True")
    assert main(["run", "--root", str(tmp_path), "--repo", "o/r"]) == 0
    assert got["variable"] == "True"                               # the env default
    out = capsys.readouterr().out
    assert "| provenance-foreign-tip | not evaluated |" in out
    assert main(["run", "--root", str(tmp_path), "--repo", "o/r", "--provenance-enabled="]) == 0
    assert got["variable"] == ""                                   # the flag wins


# --- the lens stays in this module, and the workflow hands it the variable ---------

def test_only_this_module_names_the_data_refs():
    src = REPO_ROOT / "tools" / "reeve" / "src" / "reeve"
    pattern = re.compile(r"provenance-site|git/ref/heads|state\.json\?ref=")
    holders = sorted(p.name for p in src.glob("*.py") if pattern.search(p.read_text(encoding="utf-8")))
    assert holders == ["provenance.py"]


def test_reeve_yml_hands_the_report_job_the_raw_variable():
    text = (REPO_ROOT / ".github" / "workflows" / "reeve.yml").read_text(encoding="utf-8")
    report = re.search(r"^  report:\n(.*?)^  [a-z][a-z0-9-]*:\n", text, re.MULTILINE | re.DOTALL).group(1)
    assert "PROVENANCE_ENABLED: ${{ vars.PROVENANCE_ENABLED }}" in report
    assert '--provenance-enabled="$PROVENANCE_ENABLED"' in report
    perms = re.search(r"^    permissions:\n((?:      .*\n)+)", report, re.MULTILINE).group(1)
    for scope in ("contents: read", "actions: read", "pull-requests: read"):
        assert scope in perms, scope
    assert "${{ vars.PROVENANCE_ENABLED }}" not in "".join(
        ln for ln in report.splitlines(True) if "reeve run" in ln)    # env-indirected, never inline
