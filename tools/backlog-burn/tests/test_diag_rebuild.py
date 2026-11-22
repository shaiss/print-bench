"""upload-diag REBUILD_PY: per-link validate/rebuild (CodeRabbit eSqv / eSq1)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
WORKFLOW = REPO / ".github" / "workflows" / "backlog-burn.yml"


def _rebuild_py() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    # REBUILD_PY: | … until a line that is only spaces + a non-indented-or-less key
    m = re.search(
        r"^          REBUILD_PY: \|\n((?:          .*\n)+)",
        text,
        re.M,
    )
    assert m, "REBUILD_PY not found in upload-diag"
    raw = m.group(1)
    # Block scalar content is indented 12 spaces under `REBUILD_PY: |`.
    indent = "            "
    lines = []
    for line in raw.splitlines(True):
        if line.startswith(indent):
            lines.append(line[len(indent) :])
        elif line.strip() == "":
            lines.append("\n" if line.endswith("\n") else "")
        else:
            break
    body = "".join(lines)
    assert body.lstrip().startswith("import json"), repr(body[:80])
    return body


@pytest.fixture()
def rebuild_script(tmp_path: Path) -> Path:
    script = tmp_path / "rebuild.py"
    script.write_text(_rebuild_py(), encoding="utf-8")
    return script


def _valid_payload(**overrides):
    base = {
        "label": "agent planted label",
        "log_note": "",
        "denied_tools": [{"tool": "Read"}],
        "denied_tools_extra": 0,
        "final_assistant_message_len": 2,
        "final_assistant_message_sha256": "a" * 64,
    }
    base.update(overrides)
    return base


def test_rebuild_keeps_valid_link_and_derives_label(rebuild_script: Path, tmp_path: Path):
    raw = tmp_path / "diag.raw"
    out = tmp_path / "diag.json"
    raw.write_text(json.dumps(_valid_payload()), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-I", str(rebuild_script), "3", str(raw), str(out)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    obj = json.loads(out.read_text(encoding="utf-8"))
    assert obj["label"] == "backlog-burn agent diag (link 3)"
    assert obj["denied_tools"] == [{"tool": "Read"}]


def test_rebuild_skips_invalid_link_while_sibling_ok(rebuild_script: Path, tmp_path: Path):
    """Invalid link exits 2; caller continues — sibling still rebuilds."""
    bad_raw = tmp_path / "bad.raw"
    bad_out = tmp_path / "bad.json"
    bad_raw.write_text(json.dumps({"nope": 1}), encoding="utf-8")
    bad = subprocess.run(
        [sys.executable, "-I", str(rebuild_script), "1", str(bad_raw), str(bad_out)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert bad.returncode == 2
    assert not bad_out.exists()
    assert "keys schema" in bad.stderr

    good_raw = tmp_path / "good.raw"
    good_out = tmp_path / "good.json"
    good_raw.write_text(json.dumps(_valid_payload()), encoding="utf-8")
    good = subprocess.run(
        [sys.executable, "-I", str(rebuild_script), "2", str(good_raw), str(good_out)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert good.returncode == 0, good.stderr
    obj = json.loads(good_out.read_text(encoding="utf-8"))
    assert obj["label"] == "backlog-burn agent diag (link 2)"
