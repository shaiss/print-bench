"""The queue server's near-duplicate backstop carries its own copy of the
title-similarity rule (it must stay self-contained — stdlib only, importing
nothing from this tree, like growth_mcp.py's length rule), and parses the
JSON context this package renders. This pins both: the copy to the reference
rule, and the server's reader to the renderer's output — so a rename or a
tokeniser tweak on either side fails here instead of silently disarming the
backstop (an unread context would refuse everything; a misread one, nothing).
"""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

from growth import dedup

SERVER = (Path(__file__).resolve().parents[3]
          / ".claude" / "skills" / "growth-queue" / "queue_mcp.py")

NOW = datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc)

TITLES = [
    "",
    "Growth post:",
    "Growth post: the andon cord — one variable that greys out every AI agent",
    "growth POST: Mixed Case prefix",
    "no prefix at all, with: punctuation & numbers 0.1754 mm³",
    "Growth post: the instrument that isn't in the historical record — one breath",
    "Growth post: 日本語 and ü umlauts — non-ascii is a separator",
    "Growth post: print-in-place × @Prusa3D — OEM CTA",
]


def _load_server():
    spec = importlib.util.spec_from_file_location("queue_mcp", SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_server_file_exists_beside_the_skill():
    assert SERVER.is_file(), f"expected the queue server at {SERVER}"


def test_the_constants_agree():
    server = _load_server()
    assert server.DUP_THRESHOLD == dedup.DUP_THRESHOLD
    assert server._STOPWORDS == dedup.STOPWORDS
    assert server.TITLE_PREFIX == dedup.TITLE_PREFIX
    assert server._DEDUP_SECTIONS == (dedup.SECTION_QUEUED, dedup.SECTION_COVERED)


def test_tokens_and_similarity_agree_on_every_vector():
    server = _load_server()
    for a in TITLES:
        assert server._title_tokens(a) == dedup.title_tokens(a), a
        for b in TITLES:
            assert server._similarity(a, b) == dedup.similarity(a, b), (a, b)


def test_the_server_reads_every_title_the_renderer_writes(tmp_path):
    server = _load_server()
    snapshot = [
        {"number": 753, "title": "Growth post: queued one", "state": "open",
         "labels": ["growth-queue", "channel:twitter"]},
        {"number": 597, "title": "Growth post: declined one", "state": "open",
         "labels": ["channel:twitter", "disposition:declined"]},
    ]
    path = tmp_path / dedup.JSON_NAME
    path.write_text(dedup.render_json(dedup.build(snapshot, NOW)))
    entries = server._dedup_entries(str(path))
    assert sorted((n, t) for n, t, _ in entries) == [
        (597, "Growth post: declined one"), (753, "Growth post: queued one")]
    status = {n: s for n, _, s in entries}
    assert status[597] == "disposition: declined (open)"


def test_the_server_refuses_the_renderers_unavailable_form(tmp_path):
    server = _load_server()
    path = tmp_path / dedup.JSON_NAME
    path.write_text(dedup.render_json(dedup.unavailable("HTTPError: 502", NOW)))
    with pytest.raises(RuntimeError, match="unavailable"):
        server._dedup_entries(str(path))


def test_a_drifted_section_name_would_be_caught(tmp_path):
    # Negative control: a context whose section was renamed is refused, not
    # read as empty — the failure the reader-parity test above exists to keep
    # from ever reaching a run.
    server = _load_server()
    path = tmp_path / dedup.JSON_NAME
    path.write_text('{"version": 1, "complete": true, "queued": [], "declined": []}')
    with pytest.raises(RuntimeError, match="covered"):
        server._dedup_entries(str(path))
