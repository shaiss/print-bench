"""CLI surface: --json must be parseable JSON with no trailing VERDICT line."""

import json
from pathlib import Path

from cogcheck.cli import main
from conftest import write_box


def test_json_mode_stdout_is_parseable(tmp_path: Path, capsys):
    write_box(tmp_path / "base.stl", -10, -10, 0, 10, 10, 10)
    manifest = tmp_path / "ci.cog"
    manifest.write_text(
        "margin: 2\npart: base.stl | density: 1.24\n", encoding="utf-8"
    )
    rc = main([str(manifest), "--stl-dir", str(tmp_path), "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["verdict"] == "STABLE"
    assert "VERDICT:" not in out


def test_human_mode_prints_verdict_line(tmp_path: Path, capsys):
    write_box(tmp_path / "base.stl", -10, -10, 0, 10, 10, 10)
    manifest = tmp_path / "ci.cog"
    manifest.write_text(
        "margin: 2\npart: base.stl | density: 1.24\n", encoding="utf-8"
    )
    rc = main([str(manifest), "--stl-dir", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.rstrip().splitlines()[-1].startswith("VERDICT: STABLE —")
