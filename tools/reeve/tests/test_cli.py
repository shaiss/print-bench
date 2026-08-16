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
