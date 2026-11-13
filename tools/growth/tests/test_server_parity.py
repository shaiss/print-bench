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

from growth.approval_guard import (
    APPROVAL_LABEL,
    ApprovalGuardError,
    PreviewMigrationNeeded,
    TRUSTED_PREVIEW_LOGIN,
    TRUSTED_PREVIEW_TYPE,
    assert_body_fresh_for_live,
    assert_digest_binds,
    assert_live_gates,
    body_edited_after_approval,
    latest_human_approval_at,
    latest_labeled_at,
    latest_trusted_dryrun_digest,
    parse_require_direct_human_label,
)
from growth.roottags import (
    DRYRUN_MARKER,
    MAX_REQUIRED_HANDLES,
    RootTagsError,
    assert_postable_text,
    count_posted_mentions,
    digest_comment_line,
    ensure_root_tags,
    extract_handles,
    extract_urls,
    message_digest,
    message_root_paragraph,
    parse_message_digest,
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
    "## Message\r\n\r\nCRLF draft @Prusa3D\r\n",
    "## Message\n\nURL path https://www.youtube.com/@CNC_Kitchen and @Prusa3D\n",
    "### Message\n\nForm-filed root @Prusa3D\n\n### Link\n\nhttps://x\n",
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
    # drafted + re-attach ONLY the issue ## Link URL
    link = "https://github.com/shaiss/print-bench"
    with_link = f"Agent rewrite. {link}"
    assert server._ensure_root_tags(
        with_link, ["@Prusa3D"], drafted="Measured. @Prusa3D", link=link
    ) == ensure_root_tags(
        with_link, ["@Prusa3D"], drafted="Measured. @Prusa3D", link=link
    )
    # Extra model URL refuses when it would be published (tags already present).
    evil = f"Measured. @Prusa3D {link} https://evil.example/x"
    with pytest.raises(RootTagsError, match="not in the approved"):
        ensure_root_tags(
            evil, ["@Prusa3D"], drafted="Measured. @Prusa3D", link=link
        )
    with pytest.raises(server._RootTagsError, match="not in the approved"):
        server._ensure_root_tags(
            evil, ["@Prusa3D"], drafted="Measured. @Prusa3D", link=link
        )
    # Upper- / mixed-case schemes must not bypass either copy.
    for scheme_evil in (
        f"Measured. @Prusa3D {link} HTTPS://evil.example/x",
        f"Measured. @Prusa3D {link} HtTp://evil.example/x",
    ):
        with pytest.raises(RootTagsError, match="not in the approved"):
            ensure_root_tags(
                scheme_evil,
                ["@Prusa3D"],
                drafted="Measured. @Prusa3D",
                link=link,
            )
        with pytest.raises(server._RootTagsError, match="not in the approved"):
            server._ensure_root_tags(
                scheme_evil,
                ["@Prusa3D"],
                drafted="Measured. @Prusa3D",
                link=link,
            )
        assert server._extract_urls(scheme_evil) == extract_urls(scheme_evil)
    # URL-@ skip + weight agree on uppercase schemes.
    yt = "HTTPS://www.youtube.com/@CNC_Kitchen"
    assert server._count_posted_mentions(yt) == count_posted_mentions(yt) == 0
    assert server._tweet_weight(yt) == tweet_weight(yt) == 23
    assert server._extract_urls(yt) == extract_urls(yt) == [yt]
    # draft+Link overflow → fall through to append (both sides)
    from growth.tweetlen import MAX_WEIGHT
    fat = ("d" * (MAX_WEIGHT - 10)) + " @Prusa3D"
    composed = f"Short. {link}"
    assert server._ensure_root_tags(
        composed, ["@Prusa3D"], drafted=fat, link=link
    ) == ensure_root_tags(composed, ["@Prusa3D"], drafted=fat, link=link)


def test_roottags_fail_closed_agrees():
    server = _load_server()
    required = ["@Prusa3D", "@prusament"]
    composed = "y" * 280
    drafted = "z" * 281 + " @Prusa3D @prusament"
    with pytest.raises(RootTagsError):
        ensure_root_tags(composed, required, drafted=drafted)
    with pytest.raises(server._RootTagsError):
        server._ensure_root_tags(composed, required, drafted=drafted)


def test_roottags_handle_cap_agrees():
    server = _load_server()
    assert server.MAX_REQUIRED_HANDLES == MAX_REQUIRED_HANDLES
    tags = " ".join(f"@User{i}" for i in range(MAX_REQUIRED_HANDLES + 1))
    body = f"## Message\n\nDrafted root {tags}\n"
    with pytest.raises(RootTagsError, match="cap"):
        required_handles(body)
    with pytest.raises(server._RootTagsError, match="cap"):
        server._required_handles(body)


def test_approval_guard_parity_on_stale_and_fresh():
    server = _load_server()
    events = [
        {"event": "labeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-02T12:00:00Z"},
    ]
    assert server._latest_labeled_at(events) == latest_labeled_at(events)
    assert server._body_edited_after_approval(
        "2026-01-02T12:00:00Z", "2026-01-03T00:00:00Z"
    ) == body_edited_after_approval(
        "2026-01-02T12:00:00Z", "2026-01-03T00:00:00Z"
    )
    assert server._body_edited_after_approval(
        "2026-01-02T12:00:00Z", None
    ) == body_edited_after_approval("2026-01-02T12:00:00Z", None)
    with pytest.raises(ApprovalGuardError):
        assert_body_fresh_for_live(None, None)
    with pytest.raises(server._ApprovalGuardError):
        server._assert_body_fresh_for_live(None, None)


def test_posted_mention_and_fullwidth_gates_agree():
    server = _load_server()
    for text in (
        "plain",
        "@a @b @c",
        "x" * 40,
        "@a @b https://www.youtube.com/@CNC_Kitchen @c",
        " ".join(f"@U{i}" for i in range(5))
        + " https://www.youtube.com/@CNC_Kitchen",
    ):
        assert server._count_posted_mentions(text) == count_posted_mentions(text)
        assert server._assert_postable_text(text) == assert_postable_text(text)
    for fw in ("\uff20", "\ufe6b"):
        with pytest.raises(RootTagsError, match="full-width"):
            assert_postable_text(f"hi {fw}X")
        with pytest.raises(server._RootTagsError, match="full-width"):
            server._assert_postable_text(f"hi {fw}X")
    six = " ".join(f"@U{i}" for i in range(6))
    with pytest.raises(RootTagsError, match="cap"):
        ensure_root_tags(six, [])
    with pytest.raises(server._RootTagsError, match="cap"):
        server._ensure_root_tags(six, [])
    # Drafted / append paths refuse full-width identically.
    for fw in ("\uff20", "\ufe6b"):
        drafted = f"Draft {fw}Prusa3D"
        with pytest.raises(RootTagsError):
            ensure_root_tags("rewrite", ["@Prusa3D"], drafted=drafted)
        with pytest.raises(server._RootTagsError):
            server._ensure_root_tags("rewrite", ["@Prusa3D"], drafted=drafted)
        composed = f"short {fw}Sneaky"
        fat_draft = "z" * 281 + " @Prusa3D"
        with pytest.raises(RootTagsError):
            ensure_root_tags(composed, ["@Prusa3D"], drafted=fat_draft)
        with pytest.raises(server._RootTagsError):
            server._ensure_root_tags(composed, ["@Prusa3D"], drafted=fat_draft)


def test_message_digest_parity():
    server = _load_server()
    bodies = [
        "",
        "## Message\n\nHello @Prusa3D\n\nMore.\n",
        "## Message\n\nNFKC \uff20fold @x\n",
        "## Message\r\n\r\nCRLF @y\r\n",
        "## Message\n\nHello @Prusa3D\n\n## Link\n\nhttps://example.com/a\n",
        "## Message\n\nHello @Prusa3D\n\n## Link\n\nhttps://example.com/b\n",
    ]
    for body in bodies:
        assert server._message_digest(body) == message_digest(body)
        assert server._digest_comment_line(body) == digest_comment_line(body)
        comment = f"{DRYRUN_MARKER}\n{digest_comment_line(body)}\nrest"
        assert server._parse_message_digest(comment) == parse_message_digest(comment)
        # Lone digest line (old mid-body search) is never trusted.
        assert server._parse_message_digest(digest_comment_line(body)) is None
        assert parse_message_digest(digest_comment_line(body)) is None
    # Link change flips the digest on both sides.
    a = "## Message\n\nHello @Prusa3D\n\n## Link\n\nhttps://example.com/a\n"
    b = "## Message\n\nHello @Prusa3D\n\n## Link\n\nhttps://example.com/b\n"
    assert message_digest(a) != message_digest(b)
    assert server._message_digest(a) != server._message_digest(b)
    assert server._message_link_value(a) == "https://example.com/a"


def test_digest_bind_parity():
    server = _load_server()
    body = "## Message\n\nBound @Prusa3D\n"
    comments = [{
        "body": f"{DRYRUN_MARKER}\n{digest_comment_line(body)}\n",
        "user": {"login": TRUSTED_PREVIEW_LOGIN, "type": TRUSTED_PREVIEW_TYPE},
        "created_at": "2026-01-01T10:00:00Z",
        "updated_at": "2026-01-01T10:00:00Z",
    }]
    assert latest_trusted_dryrun_digest(comments) == (
        server._latest_trusted_dryrun_digest(comments)
    )
    assert assert_digest_binds(comments, body) == (
        server._assert_digest_binds(comments, body)
    )
    with pytest.raises(PreviewMigrationNeeded):
        assert_digest_binds([], body)
    with pytest.raises(server._PreviewMigrationNeeded):
        server._assert_digest_binds([], body)
    # Digest mismatch on an existing trusted preview → refuse, both sides.
    stale = [{
        "body": f"{DRYRUN_MARKER}\n{digest_comment_line('## Message\\n\\nOld\\n')}\n",
        "user": {"login": TRUSTED_PREVIEW_LOGIN, "type": TRUSTED_PREVIEW_TYPE},
        "created_at": "2026-01-01T10:00:00Z",
        "updated_at": "2026-01-01T10:00:00Z",
    }]
    with pytest.raises(ApprovalGuardError, match="digest mismatch without edit"):
        assert_digest_binds(stale, body)
    with pytest.raises(server._ApprovalGuardError, match="digest mismatch without edit"):
        server._assert_digest_binds(stale, body)


def test_approval_latest_event_and_direct_human_parity():
    server = _load_server()
    preview_at = "2026-01-01T10:00:00Z"
    # Gap approval + bot removal + non-allowlisted re-add.
    events = [
        {"event": "labeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-01T11:00:00Z",
         "actor": {"login": "shaiss", "type": "User"}},
        {"event": "unlabeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-01T12:00:00Z",
         "actor": {"login": TRUSTED_PREVIEW_LOGIN, "type": TRUSTED_PREVIEW_TYPE}},
        {"event": "labeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-01T13:00:00Z",
         "actor": {"login": "other", "type": "User"}},
    ]
    with pytest.raises(ApprovalGuardError, match="not an allowlisted User"):
        latest_human_approval_at(
            events, preview_created_at=preview_at, approver_logins=["shaiss"]
        )
    with pytest.raises(server._ApprovalGuardError, match="not an allowlisted User"):
        server._latest_human_approval_at(events, preview_at, ["shaiss"])
    # Direct-human flag parity.
    assert parse_require_direct_human_label("false") == (
        server._parse_require_direct_human_label("false")
    )
    assert parse_require_direct_human_label("true") == (
        server._parse_require_direct_human_label("true")
    )
    via = [{"event": "labeled", "label": {"name": APPROVAL_LABEL},
            "created_at": "2026-01-01T12:00:00Z",
            "actor": {"login": "shaiss", "type": "User"},
            "performed_via_github_app": {"id": 1, "slug": "x"}}]
    with pytest.raises(ApprovalGuardError, match="GitHub App"):
        latest_human_approval_at(
            via, preview_created_at=preview_at, approver_logins=["shaiss"],
            require_direct_human_label=True,
        )
    with pytest.raises(server._ApprovalGuardError, match="GitHub App"):
        server._latest_human_approval_at(
            via, preview_at, ["shaiss"], require_direct_human_label=True
        )
    assert latest_human_approval_at(
        via, preview_created_at=preview_at, approver_logins=["shaiss"],
        require_direct_human_label=False,
    ) == server._latest_human_approval_at(
        via, preview_at, ["shaiss"], require_direct_human_label=False
    )
    # Happy-path live gates agree.
    body = "## Message\n\nBound @Prusa3D\n"
    comments = [{
        "body": f"{DRYRUN_MARKER}\n{digest_comment_line(body)}\n",
        "user": {"login": TRUSTED_PREVIEW_LOGIN, "type": TRUSTED_PREVIEW_TYPE},
        "created_at": preview_at,
        "updated_at": preview_at,
    }]
    ok_events = [{
        "event": "labeled", "label": {"name": APPROVAL_LABEL},
        "created_at": "2026-01-01T12:00:00Z",
        "actor": {"login": "shaiss", "type": "User"},
    }]
    assert assert_live_gates(
        comments, body, ok_events, None, ["shaiss"]
    ) == server._assert_live_gates(
        comments, body, ok_events, None, ["shaiss"]
    )
