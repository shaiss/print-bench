"""The CLI surface the workflow's policy step and the dry run consume."""

import io
import json

from growth.board import POSTED_MARKER
from growth.cli import main

CONF = """\
enabled: true
provider: zai
cadence: 0 9 * * *
max_posts_per_run: 1
require_approval: true
"""


def test_config_get(tmp_path, capsys):
    p = tmp_path / "g.conf"
    p.write_text(CONF)
    assert main(["config", "--get", "provider", "--path", str(p)]) == 0
    assert capsys.readouterr().out.strip() == "zai"


def test_config_get_unknown_key_fails(tmp_path, capsys):
    p = tmp_path / "g.conf"
    p.write_text(CONF)
    assert main(["config", "--get", "nope", "--path", str(p)]) == 1
    assert "unknown key" in capsys.readouterr().err


def test_config_get_missing_file_fails(tmp_path, capsys):
    assert main(["config", "--get", "enabled", "--path", str(tmp_path / "no.conf")]) == 1


def test_length(capsys):
    assert main(["length", "hello https://a.io"]) == 0
    assert capsys.readouterr().out.strip() == str(6 + 23)


def _daycap(monkeypatch, capsys, comments_json, args):
    monkeypatch.setattr("sys.stdin", io.StringIO(comments_json))
    rc = main(["daycap", *args])
    return rc, capsys.readouterr().out.strip()


def test_daycap_counts_and_holds_at_the_cap(monkeypatch, capsys):
    # Authors carry the gh GraphQL spelling ("github-actions", no "[bot]") — the
    # exact string the Select step feeds — while the caller trusts the REST
    # spelling. The guard must still count them, then hold at the cap.
    marker = f"{POSTED_MARKER}\nlive"
    one = json.dumps([{"body": marker, "createdAt": "2026-09-01T13:00:00Z",
                       "author": "github-actions"}])
    two = json.dumps([{"body": marker, "createdAt": "2026-09-01T13:00:00Z",
                       "author": "github-actions"},
                      {"body": marker, "createdAt": "2026-09-01T15:00:00Z",
                       "author": "github-actions"}])
    common = ["--today", "2026-09-01", "--author", "github-actions[bot]"]

    assert _daycap(monkeypatch, capsys, one, [*common, "--cap", "2"]) == (0, "clear")
    assert _daycap(monkeypatch, capsys, two, [*common, "--cap", "2"]) == (0, "hold")
    # default cap of 1: the first post already holds
    assert _daycap(monkeypatch, capsys, one, common) == (0, "hold")


def test_daycap_bad_stdin_json_fails(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert main(["daycap", "--author", "github-actions[bot]"]) == 1
    assert "bad comments JSON" in capsys.readouterr().err


def test_simulate_end_to_end(tmp_path, capsys):
    conf = tmp_path / "g.conf"
    conf.write_text(CONF)
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps([{"number": 1, "title": "Growth post: t", "labels": []}]))
    posts = tmp_path / "posts.json"
    posts.write_text(json.dumps({"1": {"text": "hi"}}))
    out_md = tmp_path / "out.md"
    out_nd = tmp_path / "out.ndjson"
    rc = main(["simulate", "--conf", str(conf), "--snapshot", str(snap),
               "--posts", str(posts), "--start", "2026-08-29T00:00:00Z",
               "--days", "2", "--out-md", str(out_md), "--out-ndjson", str(out_nd)])
    assert rc == 0
    assert "queue item #1" in out_md.read_text()
    assert '"mode": "dry-run"' in out_nd.read_text()
    assert "1 slot(s)" in capsys.readouterr().out


def test_simulate_refuses_overlong_copy(tmp_path, capsys):
    conf = tmp_path / "g.conf"
    conf.write_text(CONF)
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps([{"number": 1, "title": "t", "labels": []}]))
    posts = tmp_path / "posts.json"
    posts.write_text(json.dumps({"1": {"text": "x" * 300}}))
    rc = main(["simulate", "--conf", str(conf), "--snapshot", str(snap),
               "--posts", str(posts), "--start", "2026-08-29T00:00:00Z",
               "--days", "1", "--out-md", str(tmp_path / "o.md")])
    assert rc == 1
    assert "over the weighted" in capsys.readouterr().err
