"""CLI tests — ``main([...])`` called directly with tmp files, no subprocess.

Same convention as ``tools/backlog-burn/tests/test_cli.py``.
"""

from __future__ import annotations

import json
import pathlib

from backlog_groomer.cli import main
from backlog_groomer.report import MARKER

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def test_report_writes_marker_led_file(tmp_path, capsys):
    out = tmp_path / "report.md"
    rc = main(["report", "--input", str(FIXTURES / "snapshot.json"), "--out", str(out)])
    assert rc == 0
    body = out.read_text(encoding="utf-8")
    assert body.splitlines()[0] == MARKER
    assert capsys.readouterr().out == body  # stdout and --out carry the same bytes


def test_report_reads_stdin(tmp_path, capsys, monkeypatch):
    import io
    import sys

    snapshot = (FIXTURES / "snapshot.json").read_text(encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", io.StringIO(snapshot))
    assert main(["report"]) == 0
    assert capsys.readouterr().out.startswith(MARKER)


def test_report_honours_conf_thresholds(tmp_path, capsys):
    conf = tmp_path / "g.conf"
    conf.write_text("enabled: true\nstaleness_days: 5\n", encoding="utf-8")
    rc = main(["report", "--input", str(FIXTURES / "snapshot.json"), "--conf", str(conf)])
    assert rc == 0
    assert "no update in >5 days" in capsys.readouterr().out


def test_config_get(tmp_path, capsys):
    conf = tmp_path / "g.conf"
    conf.write_text("enabled: true\nmax_dup_pairs: 4\n", encoding="utf-8")
    assert main(["config", "--get", "max_dup_pairs", "--path", str(conf)]) == 0
    assert capsys.readouterr().out == "4\n"


def test_armed_prints_verdict_and_writes_output(tmp_path, capsys):
    gh_out = tmp_path / "out.txt"
    rc = main(["armed", "--variable", "true", "--conf-enabled", "true",
               "--gh-output", str(gh_out)])
    assert rc == 0
    assert capsys.readouterr().out == "true\n"
    assert gh_out.read_text(encoding="utf-8") == "armed=true\n"


def test_armed_disarmed_still_exits_zero(tmp_path, capsys):
    # The decision is the output; "don't run" is not a failure.
    rc = main(["armed", "--variable", "", "--conf-enabled", "true"])
    assert rc == 0
    assert capsys.readouterr().out == "false\n"


def test_run_snapshot_seam(monkeypatch, capsys):
    # `run` = gather + report through the same seam the gather tests use.
    from backlog_groomer import github

    snapshot = json.loads((FIXTURES / "snapshot.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(github, "gather_snapshot", lambda repo, token: snapshot)
    assert main(["run", "--repo", "o/r"]) == 0
    assert capsys.readouterr().out.startswith(MARKER)
