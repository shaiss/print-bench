"""CLI tests — main([...]) called directly, no subprocess (backlog-burn's style)."""

from __future__ import annotations

import textwrap

import pytest

from model_registry.cli import main

GOOD = """\
[provider:zai]
secret = ZAI_KEY
base_url = https://api.z.ai/api/anthropic

[provider:anthropic]
secret = ANTHROPIC_API_KEY

[model:glm-5.2]
provider = zai
notes = cheap first

[model:claude-opus-4-8]
provider = anthropic
notes = frontier fallback

[chain:review]
models = glm-5.2, claude-opus-4-8
"""


def conf(tmp_path) -> str:
    p = tmp_path / "registry.conf"
    p.write_text(textwrap.dedent(GOOD), encoding="utf-8")
    return str(p)


def test_check_ok(tmp_path, capsys):
    assert main(["--path", conf(tmp_path), "check"]) == 0
    assert "2 providers, 2 models, 1 chains" in capsys.readouterr().out


def test_check_fails_loud_on_bad_registry(tmp_path, capsys):
    p = tmp_path / "registry.conf"
    p.write_text("[chain:review]\nmodels = ghost\n", encoding="utf-8")
    assert main(["--path", str(p), "check"]) == 1
    assert "error:" in capsys.readouterr().err


def test_resolve_writes_gh_output_links(tmp_path):
    gh = tmp_path / "out.txt"
    rc = main(["--path", conf(tmp_path), "resolve", "review", "--gh-output", str(gh)])
    assert rc == 0
    lines = gh.read_text(encoding="utf-8").splitlines()
    assert "link_count=2" in lines
    assert "link1_model=glm-5.2" in lines
    assert "link1_provider=zai" in lines
    assert "link2_model=claude-opus-4-8" in lines
    assert "link2_provider=anthropic" in lines


def test_secret_name_never_reaches_gh_output(tmp_path):
    # The provider's secret *name* is not usable in a step output (secrets are
    # referenced literally) and trips secret-logging scanners — it must not appear.
    gh = tmp_path / "out.txt"
    main(["--path", conf(tmp_path), "resolve", "review", "--gh-output", str(gh)])
    body = gh.read_text(encoding="utf-8")
    assert "ZAI_KEY" not in body and "ANTHROPIC_API_KEY" not in body
    assert "_secret=" not in body and "_base_url=" not in body


def test_resolve_stdout_is_json_without_secret(tmp_path, capsys):
    main(["--path", conf(tmp_path), "resolve", "review", "--gh-output", str(tmp_path / "o")])
    import json
    raw = capsys.readouterr().out
    out = json.loads(raw)
    assert out["chain"] == "review"
    assert [l["model"] for l in out["links"]] == ["glm-5.2", "claude-opus-4-8"]
    # No secret name anywhere in the JSON either.
    assert "secret" not in out["links"][0]
    assert "ZAI_KEY" not in raw and "ANTHROPIC_API_KEY" not in raw


def test_chain_prints_ordered_model_ids(tmp_path, capsys):
    assert main(["--path", conf(tmp_path), "chain", "review"]) == 0
    assert capsys.readouterr().out == "glm-5.2\nclaude-opus-4-8\n"


def test_resolve_unknown_chain_exits_1(tmp_path, capsys):
    assert main(["--path", conf(tmp_path), "resolve", "nope",
                 "--gh-output", str(tmp_path / "o")]) == 1
    assert "unknown chain 'nope'" in capsys.readouterr().err


def test_show_summarizes_without_secret_names(tmp_path, capsys):
    assert main(["--path", conf(tmp_path), "show"]) == 0
    out = capsys.readouterr().out
    assert "provider zai: url=https://api.z.ai/api/anthropic" in out
    assert "chain review: glm-5.2 -> claude-opus-4-8" in out
    assert "ZAI_KEY" not in out and "ANTHROPIC_API_KEY" not in out
