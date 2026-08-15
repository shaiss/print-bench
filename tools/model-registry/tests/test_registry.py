"""Parser + resolver tests — a positive case AND a negative control per rule.

Same discipline as tools/ci-gates / tools/backlog-burn: every validation rule is
proved two ways — a registry that satisfies it loads, and the same registry with
that one rule broken raises ValueError naming the offending stanza. Delete a
guard from registry.py and one half of its pair fails.
"""

from __future__ import annotations

import textwrap

import pytest

from model_registry.registry import Registry

# A minimal well-formed registry: two providers, three models, one chain.
GOOD = """\
[provider:zai]
secret = ZAI_KEY
base_url = https://api.z.ai/api/anthropic

[provider:anthropic]
secret = ANTHROPIC_API_KEY

[model:glm-5.2]
provider = zai
notes = cheap first choice

[model:glm-4.6]
provider = zai
notes = older glm fallback

[model:claude-opus-4-8]
provider = anthropic
notes = frontier final fallback

[chain:review]
models = glm-5.2, glm-4.6, claude-opus-4-8
"""


def write(tmp_path, text: str) -> str:
    path = tmp_path / "registry.conf"
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return str(path)


def load(tmp_path, text: str) -> Registry:
    return Registry.load(write(tmp_path, text))


# ---------------------------------------------------------------------------
# Positive: a well-formed registry parses and resolves
# ---------------------------------------------------------------------------

def test_good_registry_loads(tmp_path):
    reg = load(tmp_path, GOOD)
    assert set(reg.providers) == {"zai", "anthropic"}
    assert set(reg.models) == {"glm-5.2", "glm-4.6", "claude-opus-4-8"}
    assert reg.chains["review"].models == ("glm-5.2", "glm-4.6", "claude-opus-4-8")


def test_provider_fields_parse(tmp_path):
    reg = load(tmp_path, GOOD)
    assert reg.providers["zai"].secret == "ZAI_KEY"
    assert reg.providers["zai"].base_url == "https://api.z.ai/api/anthropic"
    assert reg.providers["anthropic"].base_url == ""  # native endpoint


def test_resolve_pairs_models_with_provider_wiring(tmp_path):
    reg = load(tmp_path, GOOD)
    links = reg.resolve("review")
    assert [(l.position, l.model, l.provider) for l in links] == [
        (1, "glm-5.2", "zai"),
        (2, "glm-4.6", "zai"),
        (3, "claude-opus-4-8", "anthropic"),
    ]
    # Each link carries its provider's literal secret + endpoint.
    assert links[0].secret == "ZAI_KEY"
    assert links[0].base_url == "https://api.z.ai/api/anthropic"
    assert links[2].secret == "ANTHROPIC_API_KEY"
    assert links[2].base_url == ""


def test_chain_order_is_the_declared_order(tmp_path):
    # Reordering the `models =` line reorders resolution — the whole point.
    reg = load(tmp_path, GOOD.replace(
        "models = glm-5.2, glm-4.6, claude-opus-4-8",
        "models = glm-4.6, glm-5.2, claude-opus-4-8",
    ))
    assert [l.model for l in reg.resolve("review")] == [
        "glm-4.6", "glm-5.2", "claude-opus-4-8"]


# ---------------------------------------------------------------------------
# Negative controls — each raises ValueError naming the offending stanza
# ---------------------------------------------------------------------------

def test_unknown_kind_raises(tmp_path):
    with pytest.raises(ValueError, match=r"\[widget:foo\]: unknown kind 'widget'"):
        load(tmp_path, GOOD + "\n[widget:foo]\nx = 1\n")


def test_section_without_colon_raises(tmp_path):
    with pytest.raises(ValueError, match="must be '<kind>:<id>'"):
        load(tmp_path, GOOD + "\n[bareword]\nx = 1\n")


def test_provider_unknown_field_raises(tmp_path):
    with pytest.raises(ValueError, match=r"\[provider:zai\]: unknown field\(s\) \['secrt'\]"):
        load(tmp_path, GOOD.replace("secret = ZAI_KEY", "secrt = ZAI_KEY"))


def test_provider_missing_secret_raises(tmp_path):
    bad = GOOD.replace("[provider:anthropic]\nsecret = ANTHROPIC_API_KEY",
                       "[provider:anthropic]\nnotes = no secret here")
    with pytest.raises(ValueError, match=r"\[provider:anthropic\]: 'secret' is required"):
        load(tmp_path, bad)


def test_model_missing_provider_raises(tmp_path):
    bad = GOOD.replace("[model:glm-4.6]\nprovider = zai\nnotes = older glm fallback",
                       "[model:glm-4.6]\nnotes = older glm fallback")
    with pytest.raises(ValueError, match=r"\[model:glm-4.6\]: 'provider' is required"):
        load(tmp_path, bad)


def test_model_missing_notes_raises(tmp_path):
    # notes is required: the registry must SAY why a model is where it is.
    bad = GOOD.replace("[model:glm-4.6]\nprovider = zai\nnotes = older glm fallback",
                       "[model:glm-4.6]\nprovider = zai")
    with pytest.raises(ValueError, match=r"\[model:glm-4.6\]: 'notes' is required"):
        load(tmp_path, bad)


def test_model_dangling_provider_raises(tmp_path):
    bad = GOOD.replace("[model:glm-4.6]\nprovider = zai",
                       "[model:glm-4.6]\nprovider = nope")
    with pytest.raises(ValueError, match=r"\[model:glm-4.6\]: provider 'nope' is not declared"):
        load(tmp_path, bad)


def test_chain_dangling_model_raises(tmp_path):
    bad = GOOD.replace("models = glm-5.2, glm-4.6, claude-opus-4-8",
                       "models = glm-5.2, glm-9.9, claude-opus-4-8")
    with pytest.raises(ValueError, match=r"\[chain:review\]: model 'glm-9.9' is not declared"):
        load(tmp_path, bad)


def test_chain_empty_models_raises(tmp_path):
    bad = GOOD.replace("models = glm-5.2, glm-4.6, claude-opus-4-8", "models =")
    with pytest.raises(ValueError, match=r"\[chain:review\]: 'models' is required"):
        load(tmp_path, bad)


def test_duplicate_stanza_raises(tmp_path):
    # configparser rejects a duplicate section — surfaced as a ValueError.
    with pytest.raises(ValueError, match="malformed registry"):
        load(tmp_path, GOOD + "\n[provider:zai]\nsecret = AGAIN\n")


def test_duplicate_normalized_id_raises(tmp_path):
    # configparser only rejects BYTE-identical section names, but the id is
    # stripped: `[model:glm-5.2]` and `[model: glm-5.2]` are distinct raw
    # sections that normalize to the same (kind, id). Without the guard the
    # second silently overwrites the first — a model misrouted to the wrong
    # provider/secret with no diagnostic. The guard turns it into a hard error.
    bad = GOOD + "\n[model: glm-5.2]\nprovider = anthropic\nnotes = shadow\n"
    with pytest.raises(ValueError, match=r"duplicate model id 'glm-5.2'"):
        load(tmp_path, bad)


def test_resolve_unknown_chain_raises(tmp_path):
    reg = load(tmp_path, GOOD)
    with pytest.raises(KeyError, match="unknown chain 'nope'"):
        reg.resolve("nope")
