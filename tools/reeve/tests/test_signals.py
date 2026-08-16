"""Signals (the file-reading I/O seam) tests — parse the log fail-loud, scan
previews with the budget formula, and gather from a temp repo tree. No network
anywhere; the seam only reads committed files.
"""

import json
import pathlib
import re

import pytest

from reeve import signals


def _rec(designs="ALL"):
    return {"schema": 1, "kind": "gate-run", "meta": {"designs": designs}, "gate": {}}


# --- parse_log ---------------------------------------------------------------

def test_parse_log_reads_gate_runs_oldest_first():
    text = "\n".join(json.dumps(_rec("ALL")) for _ in range(2)) + "\n"
    assert len(signals.parse_log(text)) == 2


def test_parse_log_skips_blank_lines():
    text = "\n\n" + json.dumps(_rec()) + "\n\n"
    assert len(signals.parse_log(text)) == 1


def test_parse_log_filters_non_gate_run_kinds():
    other = {"schema": 1, "kind": "something-else"}
    text = json.dumps(other) + "\n" + json.dumps(_rec()) + "\n"
    records = signals.parse_log(text)
    assert len(records) == 1 and records[0]["kind"] == "gate-run"


def test_parse_log_empty_is_no_history():
    assert signals.parse_log("") == []


def test_parse_log_malformed_line_raises_with_lineno():
    with pytest.raises(ValueError, match=r"log\.ndjson:2: not valid JSON"):
        signals.parse_log(json.dumps(_rec()) + "\n{ broken\n")


def test_parse_log_missing_schema_or_kind_raises():
    with pytest.raises(ValueError, match="must be an object with 'schema' and 'kind'"):
        signals.parse_log(json.dumps({"kind": "gate-run"}) + "\n")


# --- scan_previews -----------------------------------------------------------

def _make_preview(root, design, name, size):
    d = root / "designs" / design / "previews"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(b"x" * size)


def test_scan_previews_computes_headroom_and_budget(tmp_path):
    _make_preview(tmp_path, "alpha", "turntable.gif", 100)
    _make_preview(tmp_path, "beta", "hero.png", 200)
    found = {p["file"]: p for p in signals.scan_previews(str(tmp_path))}
    gif = found["designs/alpha/previews/turntable.gif"]
    assert gif["budget"] == signals.MAX_GIF_BYTES
    assert gif["headroom_pct"] == round((signals.MAX_GIF_BYTES - 100) * 100.0 / signals.MAX_GIF_BYTES, 1)
    png = found["designs/beta/previews/hero.png"]
    assert png["budget"] == signals.MAX_SHOT_BYTES


def test_scan_previews_sorted_worst_first(tmp_path):
    # A near-full GIF (low headroom) sorts ahead of a tiny PNG (high headroom).
    _make_preview(tmp_path, "alpha", "big.gif", signals.MAX_GIF_BYTES - 1)
    _make_preview(tmp_path, "beta", "small.png", 1)
    files = [p["file"] for p in signals.scan_previews(str(tmp_path))]
    assert files[0] == "designs/alpha/previews/big.gif"


def test_scan_previews_ignores_non_preview_files(tmp_path):
    d = tmp_path / "designs" / "alpha" / "previews"
    d.mkdir(parents=True)
    (d / "CAMERAS.md").write_text("notes", encoding="utf-8")
    (d / ".regen-stamp").write_text("abc", encoding="utf-8")
    assert signals.scan_previews(str(tmp_path)) == []


# --- gather_snapshot ---------------------------------------------------------

def test_gather_snapshot_empty_repo_is_no_history(tmp_path):
    (tmp_path / "telemetry").mkdir()
    snap = signals.gather_snapshot(str(tmp_path))
    assert snap["records"] == []
    assert snap["previews"] == []
    assert snap["reportPlaceholder"] is True
    assert snap["generatedAt"].endswith("Z")


def test_gather_snapshot_reads_log_and_report_state(tmp_path):
    tel = tmp_path / "telemetry"
    tel.mkdir()
    (tel / "log.ndjson").write_text(json.dumps(_rec()) + "\n", encoding="utf-8")
    (tel / "REPORT.md").write_text("# Telemetry report\n\n| When | ... |\n", encoding="utf-8")
    _make_preview(tmp_path, "alpha", "t.gif", 10)
    snap = signals.gather_snapshot(str(tmp_path))
    assert len(snap["records"]) == 1
    assert snap["reportPlaceholder"] is False   # non-placeholder REPORT.md
    assert len(snap["previews"]) == 1


def test_gather_snapshot_detects_placeholder_report(tmp_path):
    tel = tmp_path / "telemetry"
    tel.mkdir()
    (tel / "REPORT.md").write_text(
        "# Telemetry report\n\n_No gate runs recorded yet. CI appends..._\n", encoding="utf-8")
    assert signals.gather_snapshot(str(tmp_path))["reportPlaceholder"] is True


# --- drift guard: budgets must match scripts/preview-budget.sh ---------------

def _sh_budget(text, name):
    # Extract e.g. `MAX_GIF_BYTES=$((6 * 1024 * 1024))` and evaluate the
    # arithmetic. The expression is restricted to digits/spaces/`*` before eval,
    # so this can only ever multiply integers from a repo-controlled file.
    m = re.search(rf"^{name}=\$\(\((.+?)\)\)", text, re.MULTILINE)
    assert m, f"{name} not found in scripts/preview-budget.sh"
    expr = m.group(1).strip()
    assert re.fullmatch(r"[\d\s*]+", expr), f"unexpected arithmetic for {name}: {expr!r}"
    return eval(expr)  # noqa: S307 — digits/spaces/* only, from a committed file


def test_budgets_match_preview_budget_sh():
    # scripts/preview-budget.sh is the single source of truth for the caps, and
    # Reeve duplicates them (it reads live file sizes, not a sourced shell var).
    # Pin the two together so a budget change there without a matching Reeve edit
    # is a test failure — the same idiom as the cadence↔cron drift guard.
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    text = (repo_root / "scripts/preview-budget.sh").read_text(encoding="utf-8")
    assert signals.MAX_GIF_BYTES == _sh_budget(text, "MAX_GIF_BYTES")
    assert signals.MAX_SHOT_BYTES == _sh_budget(text, "MAX_SHOT_BYTES")
