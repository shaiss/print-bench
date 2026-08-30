"""The posting MCP server re-implements the weighted-length rule (it must be
self-contained — no imports beyond stdlib in the unattended run), so this
test pins the two implementations together. If either side's rule drifts,
this fails — the composing agent and the posting tool must always measure a
tweet identically, or copy that passed compose gets refused at post time (or
worse, the reverse).
"""

import importlib.util
from pathlib import Path

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
