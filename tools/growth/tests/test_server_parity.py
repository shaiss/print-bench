"""The posting MCP server re-implements the weighted-length rule and the
root-@tag preservation rule (both must be self-contained — no imports beyond
stdlib in the unattended run), so this test pins the two implementations
together. If either side drifts, this fails — the composing agent and the
posting tool must always measure a tweet identically, and must restore the
same drafted handles the same way, or copy that passed compose gets refused
at post time (or worse, the reverse).
"""

import importlib.util
from pathlib import Path

import pytest

from growth.roottags import (
    RootTagsError,
    ensure_root_tags,
    extract_handles,
    message_root_paragraph,
    required_handles,
)
from growth.tweetlen import tweet_weight

SERVER = (Path(__file__).resolve().parents[3]
          / ".claude" / "skills" / "growth-twitter" / "growth_mcp.py")

VECTORS = [
    "",
    "hello world",
    "https://github.com/shaiss/print-bench",
    "x https://a.io y",
    "https://a.io https://example.com/a/very/long/path",
    "日本語のツイート",
    "🖨️ layer lines",
    "–’ typographic narrow range",
    "x" * 280,
    "A door that must not rattle over a loaded cell — in a hidden-information "
    "game, sound is state. https://github.com/shaiss/print-bench #3dprinting",
]

ROOTTAG_BODIES = [
    "",
    "## Message\n\nNo tags here.\n",
    "## Message\n\nRoot with @Prusa3D and @CNC_Kitchen.\n\nMore intent.\n",
    "## message\n\nCase-insensitive heading @prusament\n\n## Link\n\nhttps://x\n",
    "## Message\n\nuser@host.com and @ok and @this_handle_is_way_too_long_for_x\n",
]


def _load_server():
    spec = importlib.util.spec_from_file_location("growth_mcp", SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_server_file_exists_beside_the_skill():
    assert SERVER.is_file(), f"expected the posting server at {SERVER}"


def test_weighted_length_rules_agree_on_every_vector():
    server = _load_server()
    for text in VECTORS:
        assert server._tweet_weight(text) == tweet_weight(text), (
            f"weighted-length drift between growth.tweetlen and growth_mcp.py "
            f"on {text[:40]!r}"
        )


def test_server_cap_matches_the_package_cap():
    server = _load_server()
    from growth.tweetlen import MAX_WEIGHT
    assert server.MAX_WEIGHT == MAX_WEIGHT


def test_roottags_extraction_agrees_on_every_body():
    server = _load_server()
    for body in ROOTTAG_BODIES:
        assert server._message_root_paragraph(body) == message_root_paragraph(body), (
            f"message_root_paragraph drift on {body[:40]!r}"
        )
        assert server._required_handles(body) == required_handles(body), (
            f"required_handles drift on {body[:40]!r}"
        )
        para = message_root_paragraph(body)
        assert server._extract_handles(para) == extract_handles(para)


def test_roottags_ensure_agrees_on_preserve_append_and_verbatim():
    server = _load_server()
    drafted = "Drafted root ending with tags. @Prusa3D @prusament"
    required = ["@Prusa3D", "@prusament"]
    # already tagged
    assert server._ensure_root_tags(drafted, required, drafted=drafted) == (
        ensure_root_tags(drafted, required, drafted=drafted)
    )
    # append path
    short = "Short composed root."
    assert server._ensure_root_tags(short, required, drafted="") == (
        ensure_root_tags(short, required, drafted="")
    )
    # verbatim drafted path
    bare = "Agent rewrite without tags."
    assert server._ensure_root_tags(bare, required, drafted=drafted) == (
        ensure_root_tags(bare, required, drafted=drafted)
    )


def test_roottags_fail_closed_agrees():
    server = _load_server()
    required = ["@Prusa3D", "@prusament"]
    composed = "y" * 280
    drafted = "z" * 281 + " @Prusa3D @prusament"
    with pytest.raises(RootTagsError):
        ensure_root_tags(composed, required, drafted=drafted)
    with pytest.raises(server._RootTagsError):
        server._ensure_root_tags(composed, required, drafted=drafted)
