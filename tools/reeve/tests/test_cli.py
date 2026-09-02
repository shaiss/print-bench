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


# greenlight-poll (issue #444): the loop's authority half. run_poll is
# monkeypatched at the module attribute the lazy in-function import resolves —
# the seam's own behaviour is pinned in test_pushthrough.py; this holds the
# glue: one line per issue, the GITHUB_OUTPUT keys, the PAT notice, exit 0
# even when issues failed (per-issue resilience is the driver's contract, not
# a red run).

def test_greenlight_poll_prints_lines_appends_output_and_notices_missing_pat(
    tmp_path, monkeypatch, capsys
):
    gh_out = tmp_path / "gh_output"
    monkeypatch.setattr(
        "reeve.pushthrough.run_poll",
        lambda repo, token, pat, now=None: [
            {"number": 201, "outcome": "approved", "notes": ["ledger skipped"]},
            {"number": 202, "outcome": "overruled", "reason": "👎 overrule"},
            {"number": 203, "outcome": "error", "reason": "could not apply decision-approved"},
            {"number": 204, "outcome": "wait", "reason": "no qualifying reactions yet"},
        ],
    )
    monkeypatch.delenv("REGEN_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "tok")
    rc = main(["greenlight-poll", "--repo", "o/r", "--gh-output", str(gh_out)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "#201: approved [ledger skipped]" in out
    assert "#202: overruled (👎 overrule)" in out
    assert "#203: error (could not apply decision-approved)" in out
    assert "#204: wait (no qualifying reactions yet)" in out
    assert "REGEN_TOKEN is not set" in out
    written = gh_out.read_text(encoding="utf-8")
    assert "resolved=201\n" in written
    assert "overruled=202\n" in written
    assert "failed=203\n" in written


def test_greenlight_poll_passes_both_tokens_and_exits_clean(monkeypatch, capsys):
    seen = {}

    def fake_run_poll(repo, token, pat, now=None):
        seen.update(repo=repo, token=token, pat=pat)
        return []

    monkeypatch.setattr("reeve.pushthrough.run_poll", fake_run_poll)
    monkeypatch.setenv("GH_TOKEN", "workflow-token")
    monkeypatch.setenv("REGEN_TOKEN", "the-pat")
    rc = main(["greenlight-poll", "--repo", "o/r"])
    assert rc == 0
    assert seen == {"repo": "o/r", "token": "workflow-token", "pat": "the-pat"}
    assert capsys.readouterr().out == ""   # an empty poll is a legitimate, quiet run


def test_greenlight_poll_requires_repo():
    import pytest
    with pytest.raises(SystemExit):
        main(["greenlight-poll"])


# greenlight-context / greenlight-append (issue #445): the learning half's two
# verbs. gather_greenlight_rounds is monkeypatched the same way the select
# tests patch their gather — no request leaves the process.

from reeve import greenlights as _gl  # noqa: E402  (kept beside its tests)


def _rounds(*threads):
    return {"threads": list(threads)}


def _thread(number, **overrides):
    base = {
        "number": number, "title": f"t{number}", "state": "open",
        "labels": ["needs-decision"], "greenlight_verdict": "yes",
        "greenlight_reasoning": "GREENLIGHT: YES\nbounded scope",
        "owner_replies": [], "closing_pr": None,
    }
    base.update(overrides)
    return base


def _seed_log(tmp_path):
    log = tmp_path / "reeve-greenlights.ndjson"
    log.write_text(
        _gl.render_line({"issue": 500, "verdict": "yes",
                         "reasoning": "already recorded",
                         "owner_reaction": "/decide approved (x) by o",
                         "outcome": "closed", "recorded_at": "2026-08-16T22:47:03Z"}) + "\n",
        encoding="utf-8",
    )
    return log


def test_greenlight_context_prints_and_appends_the_multiline_digest(
    tmp_path, monkeypatch, capsys
):
    gh_out = tmp_path / "gh_output"
    log = _seed_log(tmp_path)
    monkeypatch.setattr(
        "reeve.github.gather_greenlight_rounds",
        lambda repo, token: _rounds(
            _thread(500, owner_replies=[{"author": "o", "text": "push it through"}])
        ),
    )
    rc = main(["greenlight-context", "--repo", "o/r", "--log", str(log),
               "--gh-output", str(gh_out)])
    assert rc == 0
    digest = capsys.readouterr().out.rstrip("\n")
    assert "#500 · yes" in digest
    assert "o on #500: push it through" in digest
    written = gh_out.read_text(encoding="utf-8")
    assert "digest<<REEVE_GL_DIGEST_EOF\n" + digest + "\nREEVE_GL_DIGEST_EOF\n" in written


def test_greenlight_context_bounds_the_digest_to_the_conf_cap(
    tmp_path, monkeypatch, capsys
):
    conf = tmp_path / "reeve.conf"
    conf.write_text("greenlight_precedent_cap: 1\n", encoding="utf-8")
    log = tmp_path / "reeve-greenlights.ndjson"
    log.write_text(
        _gl.render_line({"issue": 500, "verdict": "yes", "reasoning": "older",
                         "owner_reaction": "none observed", "outcome": "closed",
                         "recorded_at": "2026-08-16T22:47:03Z"}) + "\n"
        + _gl.render_line({"issue": 501, "verdict": "yes", "reasoning": "newer",
                           "owner_reaction": "none observed", "outcome": "closed",
                           "recorded_at": "2026-08-17T22:47:03Z"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("reeve.github.gather_greenlight_rounds",
                        lambda repo, token: _rounds())
    rc = main(["greenlight-context", "--repo", "o/r", "--log", str(log),
               "--conf", str(conf)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "most recent 1, capped at 1" in out
    assert "#501 ·" in out and "#500 ·" not in out


def test_greenlight_context_empty_log_never_touches_the_network(
    tmp_path, monkeypatch, capsys
):
    log = tmp_path / "reeve-greenlights.ndjson"
    log.write_text("", encoding="utf-8")

    def _boom(repo, token):  # pragma: no cover — must not be called
        raise AssertionError("no records means no gather")

    monkeypatch.setattr("reeve.github.gather_greenlight_rounds", _boom)
    rc = main(["greenlight-context", "--repo", "o/r", "--log", str(log)])
    assert rc == 0
    assert "no precedent records yet" in capsys.readouterr().out


def test_greenlight_append_writes_derived_records_and_counts_them(
    tmp_path, monkeypatch, capsys
):
    gh_out = tmp_path / "gh_output"
    log = _seed_log(tmp_path)
    ledger = tmp_path / "ledger.conf"
    ledger.write_text(
        "ship-it | approved | #501 | o | 2026-09-01T07:00:00Z\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        "reeve.github.gather_greenlight_rounds",
        lambda repo, token: _rounds(
            _thread(501, state="closed", closing_pr=512),
            _thread(502),  # still parked — no record
        ),
    )
    rc = main(["greenlight-append", "--repo", "o/r", "--log", str(log),
               "--ledger", str(ledger), "--gh-output", str(gh_out)])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"issue": 501' in out and '"issue": 502' not in out
    assert "/decide approved (ship-it) by o" in out  # the ledger reaction fed the record
    records = _gl.parse_log(log.read_text(encoding="utf-8"))
    assert [r["issue"] for r in records] == [500, 501]  # spliced, not replaced
    assert "appended=1" in gh_out.read_text(encoding="utf-8")


def test_greenlight_append_is_idempotent_against_a_recorded_round(
    tmp_path, monkeypatch, capsys
):
    log = _seed_log(tmp_path)
    ledger = tmp_path / "ledger.conf"
    ledger.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "reeve.github.gather_greenlight_rounds",
        lambda repo, token: _rounds(_thread(500, state="closed")),
    )
    rc = main(["greenlight-append", "--repo", "o/r", "--log", str(log),
               "--ledger", str(ledger)])
    assert rc == 0
    assert capsys.readouterr().out == ""  # already recorded → nothing derived
    assert len(_gl.parse_log(log.read_text(encoding="utf-8"))) == 1  # log untouched


def test_greenlight_append_can_print_to_stdout_instead_of_writing(
    tmp_path, monkeypatch, capsys
):
    log = _seed_log(tmp_path)
    ledger = tmp_path / "ledger.conf"
    ledger.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "reeve.github.gather_greenlight_rounds",
        lambda repo, token: _rounds(_thread(501, state="closed")),
    )
    before = log.read_text(encoding="utf-8")
    rc = main(["greenlight-append", "--repo", "o/r", "--log", str(log),
               "--ledger", str(ledger), "--out", "-"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"issue": 501' in out
    assert log.read_text(encoding="utf-8") == before  # untouched


def test_greenlight_append_refuses_a_malformed_log(tmp_path, monkeypatch, capsys):
    log = tmp_path / "reeve-greenlights.ndjson"
    log.write_text("{oops\n", encoding="utf-8")
    monkeypatch.setattr("reeve.github.gather_greenlight_rounds",
                        lambda repo, token: _rounds())
    rc = main(["greenlight-append", "--repo", "o/r", "--log", str(log),
               "--ledger", str(tmp_path / "ledger.conf")])
    assert rc == 1
    assert "error:" in capsys.readouterr().err
