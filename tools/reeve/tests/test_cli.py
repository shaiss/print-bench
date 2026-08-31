"""CLI tests — main([...]) called directly with tmp files / capsys, no
subprocess. Covers report (file + stdin), run (over a temp repo), config --get,
and the armed subcommand's output + $GITHUB_OUTPUT append.
"""

import io
import json
import pathlib

from reeve.cli import main
from reeve.report import MARKER

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def test_report_from_file_writes_marker_led_output(tmp_path, capsys):
    out = tmp_path / "report.md"
    rc = main(["report", "--input", str(FIXTURES / "snapshot.json"), "--out", str(out)])
    assert rc == 0
    body = out.read_text(encoding="utf-8")
    assert body.startswith(MARKER)
    assert capsys.readouterr().out == body   # stdout carries identical bytes


def test_report_reads_stdin(monkeypatch, capsys):
    snapshot = (FIXTURES / "snapshot.json").read_text(encoding="utf-8")
    monkeypatch.setattr("sys.stdin", io.StringIO(snapshot))
    assert main(["report"]) == 0
    assert capsys.readouterr().out.startswith(MARKER)


def test_report_honours_conf_thresholds(tmp_path, capsys):
    # A very low headroom threshold silences the budget section that fires by
    # default — proof --conf reaches the render.
    conf = tmp_path / "reeve.conf"
    conf.write_text("low_headroom_pct: 0\n", encoding="utf-8")
    main(["report", "--input", str(FIXTURES / "snapshot.json"), "--conf", str(conf)])
    body = capsys.readouterr().out
    # The over-budget preview has negative headroom, so even a 0 threshold keeps
    # it; but the 4.6% one is now excluded. Assert the summary count dropped to 1.
    assert "| budget-tightening | 1 |" in body


def test_run_over_a_temp_repo(tmp_path, capsys):
    (tmp_path / "telemetry").mkdir()
    rc = main(["run", "--root", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith(MARKER)
    assert "0 gate-run record(s)" in out   # empty repo → no history


def test_run_without_repo_is_offline_and_not_evaluated(tmp_path, capsys):
    # The offline invariant: no --repo, no network — the run still exits 0 and
    # both run-health signals read "not evaluated", never silently empty.
    (tmp_path / "telemetry").mkdir()
    rc = main(["run", "--root", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "| routine-dead | not evaluated |" in out
    assert "| lock-leak | not evaluated |" in out
    assert "pass --repo to enable" in out


def test_run_with_repo_attaches_run_health(tmp_path, monkeypatch, capsys):
    # --repo wires github.gather_run_health into the snapshot; monkeypatched at
    # the module attribute, which the lazy in-function import resolves at call
    # time — no request leaves the process.
    (tmp_path / "telemetry").mkdir()
    called = {}

    def fake(repo, token, now=None):
        called["repo"], called["token"] = repo, token
        return {"gatheredAt": "2026-08-16T06:00:00Z", "workflows": [],
                "issues": [], "openPRs": [], "branches": []}

    monkeypatch.setattr("reeve.github.gather_run_health", fake)
    monkeypatch.setenv("GH_TOKEN", "tok")
    rc = main(["run", "--root", str(tmp_path), "--repo", "o/r"])
    assert rc == 0
    assert called == {"repo": "o/r", "token": "tok"}
    out = capsys.readouterr().out
    assert "| routine-dead | 0 |" in out
    assert "| lock-leak | 0 |" in out


def test_config_get_prints_value(tmp_path, capsys):
    conf = tmp_path / "reeve.conf"
    conf.write_text("enabled: true\nscore_drop: 5\n", encoding="utf-8")
    main(["config", "--get", "score_drop", "--path", str(conf)])
    assert capsys.readouterr().out.strip() == "5"


def test_armed_prints_verdict_and_appends_output(tmp_path, capsys):
    gh_out = tmp_path / "gh_output"
    rc = main(["armed", "--variable", "true", "--conf-enabled", "true",
               "--gh-output", str(gh_out)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "true"
    assert "armed=true" in gh_out.read_text(encoding="utf-8")


def test_armed_disarmed_still_exits_zero(capsys):
    # The decision is the output; deciding not to run is not a failure.
    assert main(["armed", "--variable", "false", "--conf-enabled", "true"]) == 0
    assert capsys.readouterr().out.strip() == "false"


# greenlight-select (issue #443): the trusted Select step the workflow hands
# the drafter its bounded issue set through. gather_greenlight_queue is
# monkeypatched at the module attribute the lazy in-function import resolves —
# no request leaves the process.

def _queue(*nums):
    return {"parked": [{"number": n, "title": f"t{n}", "url": f"u/{n}"} for n in nums],
            "queue": [{"number": n, "title": f"t{n}", "url": f"u/{n}"} for n in nums]}


def test_greenlight_select_prints_numbers_and_appends_output(tmp_path, monkeypatch, capsys):
    gh_out = tmp_path / "gh_output"
    monkeypatch.setattr("reeve.github.gather_greenlight_queue",
                        lambda repo, token: _queue(230, 265, 267))
    monkeypatch.setenv("GH_TOKEN", "tok")
    rc = main(["greenlight-select", "--repo", "o/r", "--gh-output", str(gh_out)])
    assert rc == 0
    assert capsys.readouterr().out == "230 265 267\n"
    assert "issues=230 265 267" in gh_out.read_text(encoding="utf-8")


def test_greenlight_select_bounds_the_queue_to_the_conf_cap(tmp_path, monkeypatch, capsys):
    # cap 2 → only the two oldest parked issues are handed over, so every
    # issue the drafter sees is postable within the same run's cap.
    conf = tmp_path / "reeve.conf"
    conf.write_text("greenlight_cap: 2\n", encoding="utf-8")
    monkeypatch.setattr("reeve.github.gather_greenlight_queue",
                        lambda repo, token: _queue(230, 265, 267, 269))
    rc = main(["greenlight-select", "--repo", "o/r", "--conf", str(conf)])
    assert rc == 0
    assert capsys.readouterr().out == "230 265\n"


def test_greenlight_select_empty_queue_is_a_clean_empty_line(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("reeve.github.gather_greenlight_queue",
                        lambda repo, token: {"parked": [], "queue": []})
    rc = main(["greenlight-select", "--repo", "o/r"])
    assert rc == 0
    assert capsys.readouterr().out == "\n"


def test_greenlight_select_requires_repo():
    # argparse's own usage error — a selection without a repo is a typo, not a
    # quiet full-repo scan.
    import pytest
    with pytest.raises(SystemExit):
        main(["greenlight-select"])
