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
    ensure_root_tags,
    extract_handles,
    message_root_paragraph,
    missing_handles,
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
