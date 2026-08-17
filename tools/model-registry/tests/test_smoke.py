"""`smoke` tests — every outcome exercised through the injected post seam.

The smoke command exists because static checks cannot prove a model id is
servable by a key (issue #298); these tests prove the *judgement* — what counts
as served, failed, and skipped, and that a run proving nothing never reports
green — with a positive case and a negative control per rule, and pin that the
package's network I/O stays confined to the one `_post` seam.
"""

from __future__ import annotations

import pathlib
import textwrap

from model_registry import smoke
from model_registry.cli import main
from model_registry.registry import Registry

REG = """\
[provider:zai]
secret = ZAI_KEY
base_url = https://api.z.ai/api/anthropic

[provider:anthropic]
secret = ANTHROPIC_API_KEY

[model:glm-5.2]
provider = zai
notes = cheap first

[model:claude-opus-5]
provider = anthropic
notes = frontier backstop

[model:claude-haiku-4-5]
provider = anthropic
notes = last resort

[chain:review]
models = glm-5.2, claude-opus-5, claude-haiku-4-5
"""


def load(tmp_path) -> Registry:
    p = tmp_path / "registry.conf"
    p.write_text(textwrap.dedent(REG), encoding="utf-8")
    return Registry.load(str(p))


def ok_post(calls):
    def post(url, headers, payload):
        calls.append((url, headers, payload))
        return 200, '{"type":"message"}'
    return post


def test_all_configured_links_served_exits_0(tmp_path):
    calls = []
    env = {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}
    lines, code = smoke.smoke_chain(load(tmp_path), "review", env, ok_post(calls))
    assert code == 0
    assert [l.split()[0] for l in lines] == ["ok", "ok", "ok"]
    assert len(calls) == 3


def test_request_wiring_per_provider(tmp_path):
    # Each link must hit its provider's endpoint with its provider's key and a
    # 1-token request for exactly its model id — the wiring the live run relies on.
    calls = []
    env = {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}
    smoke.smoke_chain(load(tmp_path), "review", env, ok_post(calls))
    import json
    (zai_url, zai_hdrs, zai_body), (an_url, an_hdrs, an_body), _ = calls
    assert zai_url == "https://api.z.ai/api/anthropic/v1/messages"
    assert an_url == "https://api.anthropic.com/v1/messages"
    assert zai_hdrs["x-api-key"] == "zk" and an_hdrs["x-api-key"] == "ak"
    assert an_hdrs["anthropic-version"]
    body = json.loads(an_body)
    assert body["model"] == "claude-opus-5" and body["max_tokens"] == 1


def test_non_200_on_a_configured_link_fails(tmp_path):
    # Negative control: the exact #298 signature — the provider answers, but
    # rejects the model id — must fail the run, echoing the API's reason.
    def post(url, headers, payload):
        if "anthropic.com" in url and b"claude-opus-5" in payload:
            return 404, '{"error":{"message":"model not found"}}'
        return 200, "{}"
    lines, code = smoke.smoke_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}, post)
    assert code == 1
    assert any(l.startswith("FAIL") and "model not found" in l for l in lines)


def test_network_error_on_a_configured_link_fails(tmp_path):
    def post(url, headers, payload):
        raise OSError("connection refused")
    lines, code = smoke.smoke_chain(load(tmp_path), "review", {"ZAI_KEY": "zk"}, post)
    assert code == 1
    assert any("connection refused" in l for l in lines)


def test_missing_secret_skips_the_link_not_the_run(tmp_path):
    calls = []
    lines, code = smoke.smoke_chain(
        load(tmp_path), "review", {"ANTHROPIC_API_KEY": "ak"}, ok_post(calls))
    assert code == 0
    assert lines[0].startswith("skip") and "ZAI_KEY" in lines[0]
    assert len(calls) == 2


def test_no_secret_at_all_fails_never_green_nothing(tmp_path):
    # Negative control for the whole command: zero attempted links must exit 1,
    # or an unconfigured CI run would "prove" the chain with no request made.
    calls = []
    lines, code = smoke.smoke_chain(load(tmp_path), "review", {}, ok_post(calls))
    assert code == 1 and not calls
    assert any("proves nothing" in l for l in lines)


def test_secret_values_never_reach_the_report(tmp_path):
    def post(url, headers, payload):
        return 403, "denied"
    lines, _ = smoke.smoke_chain(
        load(tmp_path), "review",
        {"ZAI_KEY": "sec-zai-value", "ANTHROPIC_API_KEY": "sec-an-value"}, post)
    joined = "\n".join(lines)
    assert "sec-zai-value" not in joined and "sec-an-value" not in joined


def test_cli_smoke_command_wires_env_and_exit_code(tmp_path, capsys, monkeypatch):
    p = tmp_path / "registry.conf"
    p.write_text(textwrap.dedent(REG), encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ak")
    monkeypatch.delenv("ZAI_KEY", raising=False)
    monkeypatch.setattr(smoke, "_post", lambda url, headers, payload: (200, "{}"))
    assert main(["--path", str(p), "smoke", "review"]) == 0
    out = capsys.readouterr().out
    assert "ok    link 2 claude-opus-5 (anthropic)" in out
    assert out.startswith("skip")


def test_post_is_the_packages_only_network_seam():
    # Confinement (the backlog-groomer discipline): network imports live in
    # smoke.py only, so every other module stays statically network-free.
    pkg = pathlib.Path(smoke.__file__).parent
    for src in pkg.glob("*.py"):
        text = src.read_text(encoding="utf-8")
        if src.name == "smoke.py":
            assert "urllib" in text
        else:
            assert "urllib" not in text and "http.client" not in text, (
                f"{src.name} gained network I/O outside the smoke seam")
