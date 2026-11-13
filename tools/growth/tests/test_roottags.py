"""Root-tweet @handle preservation — the deterministic backstop for Lark.

The queue item's ``## Message`` first paragraph is the drafted tagged root;
the agent may rewrite it and drop the tags. These cases pin the recovery
contract the posting tool enforces before every dry-run or live post.
"""

from __future__ import annotations

import pytest

from growth.roottags import (
    MAX_REQUIRED_HANDLES,
    RootTagsError,
    allowed_urls,
    assert_only_allowed_urls,
    assert_postable_text,
    assert_thread_mention_cap,
    count_posted_mentions,
    ensure_root_tags,
    extract_handles,
    message_digest,
    message_link_value,
    message_root_paragraph,
    missing_handles,
    parse_message_digest,
    required_handles,
)
from growth.tweetlen import MAX_WEIGHT, tweet_weight


SAMPLE_BODY = """\
## Channel

twitter

## Message

The spool peg's statics came out marginal for a vertical rail: about 11 N of \
friction holding a 10 N Prusament-sized spool. The page publishes the number, \
says prefer a horizontal top rail, and offers a no-reprint fix: an M5 T-nut \
in the same slot, just below. @Prusa3D @prusament

A longer intent paragraph the agent may paraphrase — not the root draft.

## Link

https://github.com/shaiss/print-bench/tree/main/designs/extrusion-spool-holder

## Facts & sources

- Load case cited in NOTES.md
"""


def test_message_root_paragraph_is_the_first_paragraph_under_message():
    para = message_root_paragraph(SAMPLE_BODY)
    assert para.startswith("The spool peg's statics")
    assert para.endswith("@Prusa3D @prusament")
    assert "longer intent" not in para


def test_message_root_paragraph_empty_without_heading_or_body():
    assert message_root_paragraph("") == ""
    assert message_root_paragraph(None) == ""
    assert message_root_paragraph("## Link\n\nhttps://x.example") == ""


def test_extract_handles_validates_strict_pattern_and_dedupes():
    text = (
        "Hello @Prusa3D and @CNC_Kitchen and again @prusa3d — "
        "ignore user@host.com and @this_handle_is_way_too_long_for_x"
    )
    assert extract_handles(text) == ["@Prusa3D", "@CNC_Kitchen"]
    assert extract_handles("no tags here") == []
    assert extract_handles(None) == []


def test_extract_handles_ignores_handles_inside_urls():
    text = "See https://www.youtube.com/@CNC_Kitchen and also @Prusa3D"
    assert extract_handles(text) == ["@Prusa3D"]


def test_message_root_paragraph_accepts_crlf_bodies():
    body = "## Message\r\n\r\nDrafted root with @Prusa3D\r\n\r\nMore intent.\r\n"
    assert message_root_paragraph(body) == "Drafted root with @Prusa3D"
    assert required_handles(body) == ["@Prusa3D"]


def test_message_root_paragraph_accepts_h3_form_headings():
    """GitHub issue forms render field labels as ``### Message``."""
    body = (
        "### Channel\n\ntwitter\n\n"
        "### Message\n\nDrafted root with @Prusa3D\n\nMore intent.\n\n"
        "### Link\n\nhttps://example.com/x\n"
    )
    assert message_root_paragraph(body) == "Drafted root with @Prusa3D"
    assert required_handles(body) == ["@Prusa3D"]
    # Stop at the next h3, not at a later ## elsewhere.
    assert "https://example.com" not in message_root_paragraph(body)


def test_required_handles_come_only_from_message_first_paragraph():
    body = SAMPLE_BODY + "\n\n## Extra\n\nAlso @BambuLab elsewhere\n"
    assert required_handles(body) == ["@Prusa3D", "@prusament"]


def test_tags_preserved_when_composed_root_already_carries_them():
    drafted = message_root_paragraph(SAMPLE_BODY)
    required = required_handles(SAMPLE_BODY)
    composed = (
        "Spool peg statics: ~11 N friction vs a 10 N spool. Page admits the "
        "margin, prefers a horizontal rail, M5 T-nut stop as the no-reprint "
        "fix. @Prusa3D @prusament"
    )
    assert missing_handles(composed, required) == []
    assert ensure_root_tags(composed, required, drafted=drafted) == composed


def test_missing_tags_restored_via_drafted_verbatim_when_it_fits():
    drafted = message_root_paragraph(SAMPLE_BODY)
    required = required_handles(SAMPLE_BODY)
    assert tweet_weight(drafted) <= MAX_WEIGHT
    composed = (
        "Spool peg statics came out marginal — about 11 N holding a 10 N "
        "spool. Page publishes the number and the M5 T-nut fix."
    )
    assert missing_handles(composed, required) == ["@Prusa3D", "@prusament"]
    out = ensure_root_tags(composed, required, drafted=drafted)
    assert out == drafted
    assert missing_handles(out, required) == []


def test_drafted_fallback_reattaches_only_issue_link():
    drafted = "Measured margin. @Prusa3D"
    required = ["@Prusa3D"]
    link = "https://github.com/shaiss/print-bench/tree/main/designs/x"
    composed = f"Agent rewrite without the tag. {link}"
    out = ensure_root_tags(composed, required, drafted=drafted, link=link)
    assert out == f"{drafted} {link}"
    assert tweet_weight(out) <= MAX_WEIGHT


def test_extra_composed_url_refused():
    """Model text with a URL outside ## Message / ## Link refuses."""
    drafted = "Measured margin. @Prusa3D"
    link = "https://github.com/shaiss/print-bench/tree/main/designs/x"
    evil = "https://evil.example/phish"
    composed = f"Agent rewrite with tag. @Prusa3D {link} {evil}"
    with pytest.raises(RootTagsError, match="not in the approved"):
        ensure_root_tags(composed, required=["@Prusa3D"], drafted=drafted, link=link)
    with pytest.raises(RootTagsError, match="not in the approved"):
        assert_only_allowed_urls(
            f"thread with {evil}",
            allowed_urls(
                f"## Message\n\n{drafted}\n\n## Link\n\n{link}\n"
            ),
        )


def test_drafted_url_overflow_falls_through_to_append():
    """When draft+Link exceeds 280, append handles on the composed root."""
    link = "https://github.com/shaiss/print-bench/tree/main/designs/x"
    # Draft fits alone with the tag, but draft + URL (weight 23) overflows.
    drafted = ("d" * (MAX_WEIGHT - 10)) + " @Prusa3D"
    assert tweet_weight(drafted) <= MAX_WEIGHT
    assert tweet_weight(f"{drafted} {link}") > MAX_WEIGHT
    required = ["@Prusa3D"]
    composed = f"Short rewrite. {link}"
    out = ensure_root_tags(
        composed, required, drafted=drafted, link=link
    )
    assert out == f"Short rewrite. {link} @Prusa3D"
    assert tweet_weight(out) <= MAX_WEIGHT
    assert missing_handles(out, required) == []


def test_missing_tags_appended_when_drafted_does_not_fit_but_append_does():
    # Drafted root is itself over the weighted cap — verbatim path is closed.
    drafted = ("x" * 281) + " @Prusa3D @prusament"
    assert tweet_weight(drafted) > MAX_WEIGHT
    required = ["@Prusa3D", "@prusament"]
    composed = "Short root about the spool peg margin."
    out = ensure_root_tags(composed, required, drafted=drafted)
    assert out == "Short root about the spool peg margin. @Prusa3D @prusament"
    assert missing_handles(out, required) == []
    assert tweet_weight(out) <= MAX_WEIGHT


def test_over_280_fails_closed_rather_than_post_untagged():
    required = ["@Prusa3D", "@prusament"]
    # Composed text fills the budget; appending two handles cannot fit.
    # Drafted also over budget / missing the room.
    composed = "y" * MAX_WEIGHT
    drafted = "z" * (MAX_WEIGHT + 1) + " @Prusa3D @prusament"
    assert tweet_weight(composed) == MAX_WEIGHT
    assert missing_handles(composed, required) == required
    with pytest.raises(RootTagsError, match="refusing untagged"):
        ensure_root_tags(composed, required, drafted=drafted)


def test_no_tags_issue_is_unchanged():
    body = """\
## Message

A design-decision story with no community tags in the root draft.

Second paragraph of intent.
"""
    required = required_handles(body)
    assert required == []
    composed = "Feel couldn't answer — the vertical rail could."
    assert ensure_root_tags(composed, required, drafted=message_root_paragraph(body)) == composed


def test_ensure_ignores_invalid_required_tokens():
    composed = "plain root"
    assert ensure_root_tags(composed, ["@ok", "@nope!!!", "Prusa3D"]) == "plain root @ok"


def test_required_handles_refuses_above_cap():
    assert MAX_REQUIRED_HANDLES == 5
    tags = " ".join(f"@User{i}" for i in range(MAX_REQUIRED_HANDLES + 1))
    body = f"## Message\n\nDrafted root {tags}\n"
    with pytest.raises(RootTagsError, match=f"cap {MAX_REQUIRED_HANDLES}"):
        required_handles(body)


def test_required_handles_allows_exactly_cap():
    tags = " ".join(f"@User{i}" for i in range(MAX_REQUIRED_HANDLES))
    body = f"## Message\n\nDrafted root {tags}\n"
    assert required_handles(body) == [f"@User{i}" for i in range(MAX_REQUIRED_HANDLES)]


def test_sample_queue_issue_produces_a_tagged_root():
    """Dry-run-shaped example: agent drops tags → tool restores them."""
    required = required_handles(SAMPLE_BODY)
    drafted = message_root_paragraph(SAMPLE_BODY)
    agent_text = (
        "Spool peg: ~11 N of friction holding a 10 N Prusament-sized spool. "
        "Page publishes the margin, prefers a horizontal top rail, offers an "
        "M5 T-nut stop — no reprint."
    )
    restored = ensure_root_tags(agent_text, required, drafted=drafted)
    assert "@Prusa3D" in restored and "@prusament" in restored
    assert tweet_weight(restored) <= MAX_WEIGHT


def test_fullwidth_ff20_refused_on_composed_drafted_and_append():
    """＠ (U+FF20) refuses on every ensure_root_tags return path."""
    fw = "\uff20"  # ＠
    with pytest.raises(RootTagsError, match="full-width"):
        ensure_root_tags(f"composed {fw}Prusa3D", [])
    # Drafted verbatim path
    with pytest.raises(RootTagsError, match="full-width"):
        ensure_root_tags(
            "agent rewrite",
            ["@Prusa3D"],
            drafted=f"Drafted {fw}Prusa3D",
        )
    # Append path: composed already carries a full-width marker
    with pytest.raises(RootTagsError, match="full-width"):
        ensure_root_tags(
            f"short {fw}Sneaky",
            ["@Prusa3D"],
            drafted="z" * 281 + " @Prusa3D",  # over budget → append path
        )


def test_fullwidth_fe6b_refused_on_composed_drafted_and_append():
    """﹫ (U+FE6B) refuses on every ensure_root_tags return path."""
    fw = "\ufe6b"  # ﹫
    with pytest.raises(RootTagsError, match="full-width"):
        ensure_root_tags(f"composed {fw}Prusa3D", [])
    with pytest.raises(RootTagsError, match="full-width"):
        ensure_root_tags(
            "agent rewrite",
            ["@Prusa3D"],
            drafted=f"Drafted {fw}Prusa3D",
        )
    with pytest.raises(RootTagsError, match="full-width"):
        ensure_root_tags(
            f"short {fw}Sneaky",
            ["@Prusa3D"],
            drafted="z" * 281 + " @Prusa3D",
        )


def test_posted_mention_cap_after_nfkc_on_all_paths():
    six = " ".join(f"@U{i}" for i in range(6))
    with pytest.raises(RootTagsError, match=f"cap {MAX_REQUIRED_HANDLES}"):
        ensure_root_tags(f"composed {six}", [])
    # Drafted path carries 6 mentions
    with pytest.raises(RootTagsError, match=f"cap {MAX_REQUIRED_HANDLES}"):
        ensure_root_tags("agent", ["@U0"], drafted=f"Draft {six}")
    # Append that would produce 6 mentions
    five = " ".join(f"@U{i}" for i in range(5))
    with pytest.raises(RootTagsError, match=f"cap {MAX_REQUIRED_HANDLES}"):
        ensure_root_tags(
            f"root {five}",
            ["@Extra"],
            drafted="z" * 281 + " @Extra",
        )


def test_count_posted_mentions_nfkc_folds_fullwidth():
    # After NFKC, ＠ and ﹫ become @ — counted as mention tokens.
    assert count_posted_mentions("hi \uff20Ab") == 1
    assert count_posted_mentions("hi \ufe6bAb") == 1
    assert count_posted_mentions("@a @b @c") == 3


def test_thread_mention_cap_is_across_root_and_replies():
    assert_thread_mention_cap("@A @B", ["@C @D"])
    with pytest.raises(RootTagsError, match="across root\\+replies"):
        assert_thread_mention_cap("@A @B @C", ["@D @E @F"])


def test_count_posted_mentions_skips_url_path_ats():
    """YouTube /@user is not a mention — must not inflate the posted cap."""
    five = " ".join(f"@U{i}" for i in range(5))
    text = f"{five} https://www.youtube.com/@CNC_Kitchen"
    assert count_posted_mentions(text) == 5
    # Still postable at the cap (URL @ ignored).
    assert assert_postable_text(text) == text
    # A sixth real mention still refuses.
    with pytest.raises(RootTagsError, match=f"cap {MAX_REQUIRED_HANDLES}"):
        assert_postable_text(f"{text} @Extra")


def test_assert_postable_text_refuses_fullwidth_before_count():
    with pytest.raises(RootTagsError, match="U\\+FF20"):
        assert_postable_text("x \uff20Y")
    with pytest.raises(RootTagsError, match="U\\+FE6B"):
        assert_postable_text("x \ufe6bY")


def test_message_digest_binds_message_paragraph_and_link():
    import hashlib
    import unicodedata

    body = (
        "## Message\n\nHello \uff20world @Prusa3D\n\nMore.\n\n"
        "## Link\n\nhttps://example.com/a\n"
    )
    para = unicodedata.normalize("NFKC", message_root_paragraph(body))
    link = unicodedata.normalize("NFKC", message_link_value(body))
    assert link == "https://example.com/a"
    expected = hashlib.sha256((para + "\n" + link).encode("utf-8")).hexdigest()
    assert message_digest(body) == expected
    # Changing ## Link after the preview changes the digest.
    body2 = (
        "## Message\n\nHello \uff20world @Prusa3D\n\nMore.\n\n"
        "## Link\n\nhttps://example.com/b\n"
    )
    assert message_digest(body2) != message_digest(body)
    # Empty Link still contributes the trailing newline.
    body_nolink = "## Message\n\nHello \uff20world @Prusa3D\n\nMore.\n"
    assert message_link_value(body_nolink) == ""
    assert message_digest(body_nolink) == hashlib.sha256(
        (para + "\n").encode("utf-8")
    ).hexdigest()
    assert allowed_urls(body) == frozenset({"https://example.com/a"})


def test_parse_message_digest_round_trip():
    from growth.roottags import DRYRUN_MARKER, digest_comment_line

    body = "## Message\n\nTagged @Prusa3D\n\n## Link\n\nhttps://x.example\n"
    line = digest_comment_line(body)
    comment = f"{DRYRUN_MARKER}\n{line}\nbody"
    assert parse_message_digest(comment) == message_digest(body)
    assert parse_message_digest("no digest here") is None
    assert parse_message_digest(f"x\n{DRYRUN_MARKER}\n{line}\n") is None
