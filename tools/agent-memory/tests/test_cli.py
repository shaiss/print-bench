"""The CLI contract: exit codes and output shapes, plus the live store control."""

from __future__ import annotations

import io
import json
import pathlib

import pytest

from agent_memory import cli, encode
from conftest import make_event

REPO = pathlib.Path(__file__).resolve().parents[3]


def _event_file(tmp_path, **over):
    path = tmp_path / "event.json"
    path.write_text(json.dumps(make_event(**over)), encoding="utf-8")
    return str(path)


def test_record_then_record_again(tmp_path, store, capsys):
    ev = _event_file(tmp_path, status="failed")
    assert cli.main(["record", "--event", ev, "--store", str(store)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("created ") and "importance 40 · rich · model-asserted" in out
    assert cli.main(["record", "--event", ev, "--store", str(store)]) == 0
    assert capsys.readouterr().out.startswith("unchanged ")


def test_record_reads_stdin(monkeypatch, store, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(make_event())))
    assert cli.main(["record", "--event", "-", "--store", str(store)]) == 0
    assert "created" in capsys.readouterr().out


@pytest.mark.parametrize("over", [{"importance": 90}, {"status": "done"}])
def test_negative_control_a_bad_event_exits_2_and_writes_nothing(tmp_path, store, capsys, over):
    assert cli.main(["record", "--event", _event_file(tmp_path, **over), "--store", str(store)]) == 2
    assert "error:" in capsys.readouterr().err
    assert not store.exists()


def test_not_json_exits_2(tmp_path, store, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert cli.main(["record", "--event", str(bad), "--store", str(store)]) == 2
    assert "not valid JSON" in capsys.readouterr().err


def test_overwrite_refusal_exits_2(tmp_path, store, capsys):
    ev = _event_file(tmp_path)
    cli.main(["record", "--event", ev, "--store", str(store)])
    (path,) = (store / "design-run").iterdir()
    path.write_bytes(path.read_bytes().replace(b"gate green", b"gate red"))
    capsys.readouterr()
    assert cli.main(["record", "--event", ev, "--store", str(store)]) == 2
    assert "immutable" in capsys.readouterr().err


def test_score_is_a_dry_run(tmp_path, capsys):
    assert cli.main(["score", "--event", _event_file(tmp_path)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == encode(make_event())
    assert not (tmp_path / "store").exists()


def test_check_exit_codes(tmp_path, store, capsys):
    assert cli.main(["check", "--store", str(store)]) == 0          # absent = empty
    assert "ok 0 note(s)" in capsys.readouterr().out
    cli.main(["record", "--event", _event_file(tmp_path), "--store", str(store)])
    (path,) = (store / "design-run").iterdir()
    path.write_bytes(path.read_bytes() + b"\n")                     # reformatted
    capsys.readouterr()
    assert cli.main(["check", "--store", str(store)]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_selftest_flag(capsys):
    assert cli.main(["--selftest"]) == 0
    assert "all cases passed" in capsys.readouterr().out


def test_no_subcommand_is_a_usage_error(capsys):
    assert cli.main([]) == 2


def test_live_control_the_committed_store_passes_check(capsys):
    # The repo's own store (empty until Slice 1d wires a routine) must always
    # pass — check.sh runs exactly this.
    store = REPO / "tools" / "agent-memory" / "store"
    assert cli.main(["check", "--store", str(store)]) == 0
