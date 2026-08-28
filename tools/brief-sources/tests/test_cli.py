"""The CLI — `extract` and `select` end to end (the shape a caller runs).

Exit codes and output shapes are the contract: 0 for success *including the
NONE verdict*, 2 for a wrong invocation, a bad marker, or a malformed
open-brief list. `select` without `--open-briefs` is exit 2 on purpose —
dedup is the reason this tool exists, and silently assuming an empty
backlog would re-file everything the rail was meant to catch.
"""

from __future__ import annotations

import pytest

from brief_sources.cli import main

from conftest import marker, write_doc


def test_extract_prints_one_line_per_candidate_in_scan_order(root, capsys):
    write_doc(root, "research.md",
              marker("bistable-toggle", "bistable-toggle — Tier 2 reference design",
                     status="briefed", ref=389)
              + "\n" + marker("next-thing"))
    assert main(["extract", "--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert out.splitlines() == [
        "bistable-toggle | bistable-toggle — Tier 2 reference design"
        " | docs/research.md#the-section | status=briefed ref=389",
        "next-thing | next-thing — a decided demonstrator"
        " | docs/research.md#the-section | status=decided",
    ]


def test_extract_json_is_machine_readable(root, capsys):
    import json

    write_doc(root, "research.md", marker("next-thing"))
    assert main(["extract", "--root", str(root), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == [
        {
            "slug": "next-thing",
            "title": "next-thing — a decided demonstrator",
            "source": "docs/research.md#the-section",
            "status": "decided",
        }
    ]


def test_select_prints_one_candidate_with_provenance(root, capsys):
    write_doc(root, "research.md", marker("next-thing"))
    briefs = root / "briefs.txt"
    briefs.write_text("385 support-free-bracket — Tier 1 reference design\n", encoding="utf-8")
    assert main(["select", "--root", str(root), "--open-briefs", str(briefs)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "slug: next-thing",
        "title: next-thing — a decided demonstrator",
        "source: docs/research.md#the-section",
        "status: decided",
    ]


def test_select_prints_NONE_and_exits_zero_when_nothing_selects(root, capsys):
    write_doc(root, "research.md", marker("filed-thing", status="briefed", ref=1))
    briefs = root / "briefs.txt"
    briefs.write_text("1 filed-thing — already open\n", encoding="utf-8")
    assert main(["select", "--root", str(root), "--open-briefs", str(briefs)]) == 0
    assert capsys.readouterr().out.strip() == "NONE"


def test_select_reads_the_brief_list_from_stdin(root, capsys, monkeypatch):
    import io

    write_doc(root, "research.md", marker("next-thing"))
    monkeypatch.setattr("sys.stdin", io.StringIO("385 something else entirely\n"))
    assert main(["select", "--root", str(root), "--open-briefs", "-"]) == 0
    assert "slug: next-thing" in capsys.readouterr().out


def test_select_json_emits_null_for_none(root, capsys):
    import json

    write_doc(root, "research.md", marker("filed-thing", status="briefed", ref=1))
    briefs = root / "briefs.txt"
    briefs.write_text("", encoding="utf-8")
    assert main(["select", "--root", str(root), "--open-briefs", str(briefs), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) is None


def test_select_without_open_briefs_is_exit_2(root, capsys):
    # argparse rejects the missing required flag with its own usage error —
    # exit code 2 either way, which is the contract callers read.
    write_doc(root, "research.md", marker("next-thing"))
    with pytest.raises(SystemExit) as exc:
        main(["select", "--root", str(root)])
    assert exc.value.code == 2
    assert "--open-briefs" in capsys.readouterr().err


def test_a_malformed_marker_is_exit_2(root, capsys):
    write_doc(root, "research.md", "<!-- brief-candidate: no-pipes-here -->")
    assert main(["extract", "--root", str(root)]) == 2
    assert "docs/research.md:1" in capsys.readouterr().err


def test_a_malformed_brief_list_is_exit_2(root, capsys):
    write_doc(root, "research.md", marker("next-thing"))
    briefs = root / "briefs.txt"
    briefs.write_text("not-a-number some title\n", encoding="utf-8")
    assert main(["select", "--root", str(root), "--open-briefs", str(briefs)]) == 2
    assert "open-brief line" in capsys.readouterr().err


def test_a_missing_brief_list_file_is_exit_2(root, capsys):
    write_doc(root, "research.md", marker("next-thing"))
    assert main(["select", "--root", str(root), "--open-briefs", str(root / "nope.txt")]) == 2
