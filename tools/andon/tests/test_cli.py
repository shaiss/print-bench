"""The ``andon`` CLI — the workflow's step, exercised offline."""

from __future__ import annotations

import pathlib

import pytest

from andon import cli, github, policy


def _run(argv):
    return cli.main(argv)


def test_decide_offline_pulled_opens_and_writes_the_body(tmp_path, capsys):
    out = tmp_path / "gh.out"
    rc = _run(["decide", "--offline", "--repo", "o/r", "--cord", "Pulled",
               "--now", "2026-09-01T10:00:00Z", "--gh-output", str(out),
               "--out-dir", str(tmp_path / "andon")])
    assert rc == 0
    assert out.read_text(encoding="utf-8") == (
        "action=open\nissue_number=\npulled=true\nopened_at=\n")
    body = (tmp_path / "andon" / "body.md").read_text(encoding="utf-8")
    assert body.startswith(policy.MARKER + "\n")
    assert "2026-09-01T10:00:00Z" in body
    assert not (tmp_path / "andon" / "comment.md").exists()
    assert "action=open" in capsys.readouterr().out


def test_decide_offline_released_is_a_noop_and_writes_no_files(tmp_path):
    out = tmp_path / "gh.out"
    rc = _run(["decide", "--offline", "--cord", "released", "--gh-output", str(out),
               "--out-dir", str(tmp_path / "andon")])
    assert rc == 0
    assert out.read_text(encoding="utf-8") == (
        "action=none\nissue_number=\npulled=false\nopened_at=\n")
    assert not (tmp_path / "andon").exists()


def test_decide_offline_unset_cord_reads_as_released(tmp_path):
    out = tmp_path / "gh.out"
    assert _run(["decide", "--offline", "--gh-output", str(out)]) == 0
    assert "pulled=false" in out.read_text(encoding="utf-8")


def test_gh_output_is_appended_not_truncated(tmp_path):
    out = tmp_path / "gh.out"
    out.write_text("earlier=1\n", encoding="utf-8")
    _run(["decide", "--offline", "--cord", "x", "--gh-output", str(out)])
    assert out.read_text(encoding="utf-8").startswith("earlier=1\naction=none\n")


def test_decide_with_an_open_issue_closes_via_the_seam(tmp_path, monkeypatch):
    # The live path: the gather seam returns an open issue, the cord is
    # released, so the decision is close and comment.md carries the span.
    monkeypatch.setattr(github, "find_open_status_issue",
                        lambda repo, token: policy.OpenIssue(
                            41, policy.parse_iso("2026-09-01T10:00:00Z")))
    monkeypatch.setenv("GH_TOKEN", "tok")
    out = tmp_path / "gh.out"
    rc = _run(["decide", "--repo", "o/r", "--cord", "", "--now", "2026-09-01T13:30:00Z",
               "--gh-output", str(out), "--out-dir", str(tmp_path / "andon")])
    assert rc == 0
    assert out.read_text(encoding="utf-8") == (
        "action=close\nissue_number=41\npulled=false\nopened_at=2026-09-01T10:00:00Z\n")
    comment = (tmp_path / "andon" / "comment.md").read_text(encoding="utf-8")
    assert "about 3 hours" in comment and "2026-09-01T10:00:00Z" in comment
    assert "https://github.com/o/r/blob/main/docs/andon-cord.md" in comment


def test_decide_still_pulled_is_a_noop_that_names_the_since(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(github, "find_open_status_issue",
                        lambda repo, token: policy.OpenIssue(
                            41, policy.parse_iso("2026-09-01T10:00:00Z")))
    out = tmp_path / "gh.out"
    rc = _run(["decide", "--repo", "o/r", "--cord", "pulled", "--gh-output", str(out),
               "--out-dir", str(tmp_path / "andon")])
    assert rc == 0
    assert out.read_text(encoding="utf-8") == (
        "action=none\nissue_number=41\npulled=true\nopened_at=2026-09-01T10:00:00Z\n")
    assert "still pulled since 2026-09-01T10:00:00Z" in capsys.readouterr().out
    assert not (tmp_path / "andon").exists()


def test_bad_now_exits_1(tmp_path, capsys):
    rc = _run(["decide", "--offline", "--cord", "pulled", "--now", "garbage",
               "--out-dir", str(tmp_path / "andon")])
    assert rc == 1
    assert "ISO-8601" in capsys.readouterr().err
    assert not (tmp_path / "andon").exists()


def test_missing_repo_without_offline_exits_1(capsys):
    assert _run(["decide", "--cord", "pulled"]) == 1
    assert "--repo" in capsys.readouterr().err


def test_render_open_prints_marker_first(capsys):
    assert _run(["render-open", "--now", "2026-09-01T10:00:00Z"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(policy.MARKER + "\n")
    assert "2026-09-01T10:00:00Z" in out


def test_render_close_prints_the_span(capsys):
    assert _run(["render-close", "--since", "2026-09-01T10:00:00Z",
                 "--now", "2026-09-04T14:00:00Z"]) == 0
    assert "about 3 days 4 hours" in capsys.readouterr().out


def test_render_close_bad_since_exits_1(capsys):
    assert _run(["render-close", "--since", "nope"]) == 1
    assert "ISO-8601" in capsys.readouterr().err


def test_argparse_errors_exit_2():
    with pytest.raises(SystemExit) as exc:
        _run(["render-close"])  # --since is required
    assert exc.value.code == 2


def test_module_entrypoint_runs(tmp_path):
    # `python3 -m andon` is what the workflow invokes.
    import os
    import subprocess
    import sys

    src = pathlib.Path(cli.__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "andon", "render-open", "--now", "2026-09-01T10:00:00Z"],
        env={**os.environ, "PYTHONPATH": str(src)}, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.startswith(policy.MARKER)
