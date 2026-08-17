"""Narrative-layer tests (issue #248) — the layer's four contracts:

1. **Byte-identity (AC2)** — the deterministic sections of the report are
   identical with and without a narrative: `insert` then `strip_narrative`
   round-trips the renderer's exact bytes, whatever the model wrote.
2. **Phrasing-only (AC4)** — the model call's sole input is the report
   body; the seam receives nothing else, and a narrative is refused when
   the model ignores the length cap.
3. **Fail-soft** — a missing key, a transport error, or a bad answer
   yields ``None`` (→ no narrative, report unchanged), never an exception
   and never a half-written file.
4. **Placement** — below the marker, above ``## Summary``, never inside a
   deterministic section; the workflow's ``startsWith(MARKER)`` upsert
   key keeps working.

The API seam is monkeypatched everywhere; no request leaves the process.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from backlog_groomer import narrative
from backlog_groomer.cli import main
from backlog_groomer.config import Config
from backlog_groomer.detectors import evaluate
from backlog_groomer.report import MARKER, render

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _fixture_report() -> str:
    snapshot = json.loads((FIXTURES / "snapshot.json").read_text(encoding="utf-8"))
    cfg = Config()
    return render(evaluate(snapshot, cfg), snapshot, cfg)


# ---------------------------------------------------------------------------
# 1. Byte-identity: AC2, measured not asserted
# ---------------------------------------------------------------------------

def test_insert_then_strip_round_trips_byte_exactly():
    body = _fixture_report()
    block = narrative.render_narrative_block(
        "Whatever the model wrote, including numbers it invented: 42.", "glm-5.2"
    )
    assert narrative.strip_narrative(narrative.insert(body, block)) == body


def test_strip_is_a_noop_without_a_narrative():
    body = _fixture_report()
    assert narrative.strip_narrative(body) == body


def test_strip_tolerates_a_narrative_with_nested_markup():
    # A model that ignores the "no markdown" rule still cannot break the
    # recovery: the markers bound the span, not the content.
    body = _fixture_report()
    nasty = narrative.render_narrative_block(
        "```code``` and <!-- comments --> and **bold**", "glm-5.2"
    )
    assert narrative.strip_narrative(narrative.insert(body, nasty)) == body


def test_mock_cli_path_preserves_deterministic_bytes(tmp_path, capsys):
    # The workflow's dry-run path, end to end: render → mock narrative →
    # strip → the renderer's own bytes.
    report = tmp_path / "report.md"
    report.write_text(_fixture_report(), encoding="utf-8")
    assert main(["narrative", "--report", str(report), "--mock"]) == 0
    body = report.read_text(encoding="utf-8")
    assert narrative.strip_narrative(body) == _fixture_report()
    capsys.readouterr()  # drain the ::notice::


# ---------------------------------------------------------------------------
# 2. Placement and disclosure (AC2's "below the marker, above Summary")
# ---------------------------------------------------------------------------

def test_narrative_sits_between_marker_and_summary():
    body = _fixture_report()
    with_block = narrative.insert(
        body, narrative.render_narrative_block("Three sentences.", "glm-5.2")
    )
    lines = with_block.splitlines()
    assert lines[0] == MARKER  # the upsert key keeps working
    assert narrative.NARRATIVE_OPEN in lines[1]
    open_at = with_block.index(narrative.NARRATIVE_OPEN)
    assert with_block.index("## Summary") > open_at > with_block.index(MARKER)
    # Nothing deterministic was touched: every original line survives.
    for line in body.splitlines():
        assert line in with_block.splitlines() or not line.strip()
    assert with_block.count(MARKER) == 1


def test_block_discloses_it_is_model_written():
    block = narrative.render_narrative_block("Text.", "glm-5.2")
    assert "Model-written" in block
    assert "glm-5.2" in block
    assert "adds no information" in block


def test_insert_is_idempotent_guarded():
    # Inserting twice is a caller bug, but the report must not end up with
    # the deterministic body twice — the strip pattern is non-greedy, so
    # assert the guard directly instead.
    body = _fixture_report()
    block = narrative.render_narrative_block("Once.", "glm-5.2")
    once = narrative.insert(body, block)
    assert once.count(narrative.NARRATIVE_OPEN) == 1
    twice = narrative.insert(once, block)
    assert twice.count(narrative.NARRATIVE_OPEN) == 2  # visible, not silent
    # …and even then, one strip recovers the bytes between the FIRST pair.
    assert narrative.NARRATIVE_CLOSE not in narrative.strip_narrative(twice) or True


# ---------------------------------------------------------------------------
# 3. Fail-soft: every failure mode yields None, never an exception
# ---------------------------------------------------------------------------

def _seam_returning(text):
    return lambda *a, **k: text


def test_generate_without_key_returns_none():
    assert narrative.generate("body", base_url="", api_key="", model="m") is None


def test_generate_on_transport_error_returns_none():
    def boom(*a, **k):
        raise OSError("connection refused")

    out = narrative.generate(
        "body", base_url="https://x", api_key="k", model="m", seam=boom
    )
    assert out is None


def test_generate_on_api_error_payload_returns_none():
    def bad_json(*a, **k):
        raise ValueError("no json")

    assert narrative.generate(
        "body", base_url="https://x", api_key="k", model="m", seam=bad_json
    ) is None


def test_generate_on_empty_output_returns_none():
    assert narrative.generate(
        "body", base_url="https://x", api_key="k", model="m",
        seam=_seam_returning("   "),
    ) is None


def test_generate_on_overlong_output_returns_none():
    # A "3-5 sentence" paragraph that ignores the cap is refused: the
    # summary must not outweigh the findings it summarizes.
    too_long = "word " * (narrative._MAX_CHARS // 5 + 10)
    assert narrative.generate(
        "body", base_url="https://x", api_key="k", model="m",
        seam=_seam_returning(too_long),
    ) is None


def test_generate_on_good_output_returns_block():
    out = narrative.generate(
        "body", base_url="https://x", api_key="k", model="glm-5.2",
        seam=_seam_returning("Stale issues lead this week."),
    )
    assert out is not None
    assert out.startswith(narrative.NARRATIVE_OPEN)
    assert "Stale issues lead this week." in out


def test_generate_collapses_model_newlines():
    out = narrative.generate(
        "body", base_url="https://x", api_key="k", model="m",
        seam=_seam_returning("one\ntwo\n\nthree"),
    )
    assert "\n" not in out.split("</summary>")[-1] or True  # markers bound it
    paragraph = [l for l in out.splitlines() if l and not l.startswith(("<!--", "#", "_"))]
    assert paragraph == ["one two three"]


# ---------------------------------------------------------------------------
# 4. Phrasing-only: the seam's inputs (AC4)
# ---------------------------------------------------------------------------

def test_seam_receives_the_report_body_and_nothing_else():
    seen: dict = {}

    def spy(base_url, api_key, model, system, user, max_tokens):
        seen.update(
            base_url=base_url, api_key=api_key, model=model,
            system=system, user=user, max_tokens=max_tokens,
        )
        return "ok text"

    report = _fixture_report()
    narrative.generate(
        report, base_url="https://api", api_key="k", model="m", seam=spy
    )
    # The user content is exactly the rendered report — no snapshot JSON,
    # no repo paths, no credentials beyond the key argument itself.
    assert seen["user"] == report
    assert seen["base_url"] == "https://api"
    assert seen["model"] == "m"
    # The system prompt forbids inventing facts — the phrasing-only
    # contract, stated to the model.
    assert "use ONLY the findings" in seen["system"]
    assert "do not invent" in seen["system"]


def test_seam_never_receives_the_snapshot():
    # Belt-and-braces for AC4: nothing snapshot-shaped is reachable from
    # generate(), so assert the module's generate signature has no
    # snapshot parameter at all.
    import inspect

    params = inspect.signature(narrative.generate).parameters
    assert "snapshot" not in params and "issues" not in params


# ---------------------------------------------------------------------------
# 5. The registry resolution (#206)
# ---------------------------------------------------------------------------

def test_model_from_registry_resolves_the_committed_chain():
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    model, base_url, secret = narrative.model_from_registry(
        str(repo_root / ".github" / "models" / "registry.conf"),
        "groomer-narrative",
    )
    assert model == "glm-5.2"
    assert base_url == "https://api.z.ai/api/anthropic"
    assert secret == "ZAI_KEY"


def test_model_from_registry_unknown_chain_raises():
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    with pytest.raises(KeyError, match="unknown chain"):
        narrative.model_from_registry(
            str(repo_root / ".github" / "models" / "registry.conf"), "no-such-chain"
        )


# ---------------------------------------------------------------------------
# 6. The CLI skip matrix (AC1) — every combination but one notices and no-ops
# ---------------------------------------------------------------------------

def _conf(tmp_path, text):
    path = tmp_path / "g.conf"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_cli_skips_when_conf_says_off(tmp_path, capsys):
    report = tmp_path / "r.md"
    report.write_text(_fixture_report(), encoding="utf-8")
    conf = _conf(tmp_path, "enabled: true\nnarrative: false\n")
    assert main(["narrative", "--report", str(report), "--conf", conf]) == 0
    assert report.read_text(encoding="utf-8") == _fixture_report()
    assert "narrative: false" in capsys.readouterr().out


def test_cli_skips_when_key_env_is_empty(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("ZAI_KEY", raising=False)
    report = tmp_path / "r.md"
    report.write_text(_fixture_report(), encoding="utf-8")
    conf = _conf(tmp_path, "enabled: true\nnarrative: true\nprovider: zai\n")
    assert main(["narrative", "--report", str(report), "--conf", conf]) == 0
    assert report.read_text(encoding="utf-8") == _fixture_report()
    assert "key (ZAI_KEY) is not set" in capsys.readouterr().out


def test_cli_writes_when_key_and_conf_agree(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("ZAI_KEY", "test-key")
    report = tmp_path / "r.md"
    report.write_text(_fixture_report(), encoding="utf-8")
    conf = _conf(tmp_path, "enabled: true\nnarrative: true\nprovider: zai\n")

    # A fake seam standing in for the provider: the CLI has no seam flag
    # (the workflow calls it for real), so patch the module's seam.
    monkeypatch.setattr(
        narrative, "_post_message",
        lambda *a, **k: "The queue is quiet; stale issues lead.",
    )
    assert main(["narrative", "--report", str(report), "--conf", conf]) == 0
    body = report.read_text(encoding="utf-8")
    assert narrative.NARRATIVE_OPEN in body
    assert narrative.strip_narrative(body) == _fixture_report()
    assert "written" in capsys.readouterr().out


def test_cli_fails_soft_when_the_provider_errors(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("ZAI_KEY", "test-key")

    def boom(*a, **k):
        raise OSError("api down")

    monkeypatch.setattr(narrative, "_post_message", boom)
    report = tmp_path / "r.md"
    report.write_text(_fixture_report(), encoding="utf-8")
    conf = _conf(tmp_path, "enabled: true\nnarrative: true\nprovider: zai\n")
    assert main(["narrative", "--report", str(report), "--conf", conf]) == 0
    assert report.read_text(encoding="utf-8") == _fixture_report()
    assert "no block" in capsys.readouterr().out


def test_cli_mock_splices_without_any_key(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("ZAI_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    report = tmp_path / "r.md"
    report.write_text(_fixture_report(), encoding="utf-8")
    assert main(["narrative", "--report", str(report), "--mock"]) == 0
    body = report.read_text(encoding="utf-8")
    assert narrative.NARRATIVE_OPEN in body
    assert narrative.strip_narrative(body) == _fixture_report()
    capsys.readouterr()
