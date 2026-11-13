"""Trusted-preview + human-approval gates — pure comparisons the posting tool enforces."""

from __future__ import annotations

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
    exactly_one_trusted_preview,
    is_trusted_preview_comment,
    latest_human_approval_at,
    latest_labeled_at,
    parse_approver_allowlist,
)
from growth.roottags import DRYRUN_MARKER, digest_comment_line, message_digest, parse_message_digest


def test_latest_labeled_at_picks_most_recent_approval():
    events = [
        {"event": "labeled", "label": {"name": "growth-queue"},
         "created_at": "2026-01-01T00:00:00Z"},
        {"event": "labeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-02T12:00:00Z"},
        {"event": "unlabeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-03T00:00:00Z"},
        {"event": "labeled", "label": APPROVAL_LABEL,
         "created_at": "2026-01-04T08:00:00Z"},
    ]
    assert latest_labeled_at(events) == "2026-01-04T08:00:00Z"


def test_body_edited_after_approval_is_stale():
    assert body_edited_after_approval(
        "2026-01-02T12:00:00Z", "2026-01-02T12:00:01Z"
    ) is True
    assert body_edited_after_approval(
        "2026-01-02T12:00:00Z", "2026-01-02T11:59:59Z"
    ) is False


def test_assert_body_fresh_for_live_refuses_missing_and_stale():
    with pytest.raises(ApprovalGuardError, match="fail closed"):
        assert_body_fresh_for_live(None, None)
    with pytest.raises(ApprovalGuardError, match="edited after"):
        assert_body_fresh_for_live(
            "2026-01-02T12:00:00Z", "2026-01-03T00:00:00Z"
        )


def _preview(body: str, *, created="2026-01-01T10:00:00Z", updated=None,
             login=TRUSTED_PREVIEW_LOGIN, utype=TRUSTED_PREVIEW_TYPE,
             forged_mid=False, old_format=False) -> dict:
    if updated is None:
        updated = created
    if old_format:
        text = f"{DRYRUN_MARKER}\nold format without digest"
    elif forged_mid:
        text = f"intro\n{DRYRUN_MARKER}\n{digest_comment_line(body)}\ntrail"
    else:
        text = f"{DRYRUN_MARKER}\n{digest_comment_line(body)}\npreview body"
    return {
        "body": text,
        "user": {"login": login, "type": utype},
        "created_at": created,
        "updated_at": updated,
    }


def test_parse_message_digest_requires_first_two_lines_exact():
    body = "## Message\n\nHi\n"
    good = f"{DRYRUN_MARKER}\n{digest_comment_line(body)}\nrest"
    assert parse_message_digest(good) == message_digest(body)
    # Mid-body markers never trusted.
    assert parse_message_digest(
        f"x\n{DRYRUN_MARKER}\n{digest_comment_line(body)}\n"
    ) is None
    # Old format (no digest line).
    assert parse_message_digest(f"{DRYRUN_MARKER}\nno digest") is None
    # Whitespace on the digest line rejects.
    dig = digest_comment_line(body)
    assert parse_message_digest(f"{DRYRUN_MARKER}\n {dig}\n") is None


def test_is_trusted_preview_rejects_lookalike_edited_old_format():
    body = "## Message\n\nHi\n"
    assert is_trusted_preview_comment(_preview(body))
    assert not is_trusted_preview_comment(
        _preview(body, login="github-actions-imposter")
    )
    assert not is_trusted_preview_comment(
        _preview(body, login="github-actions", utype="Bot")
    )
    assert not is_trusted_preview_comment(
        _preview(body, updated="2026-01-01T11:00:00Z")
    )
    assert not is_trusted_preview_comment(_preview(body, old_format=True))
    assert not is_trusted_preview_comment(_preview(body, forged_mid=True))
    assert not is_trusted_preview_comment(
        _preview(body, utype="User")  # wrong type even with bot login
    )


def test_exactly_one_trusted_preview_after_edit():
    body = "## Message\n\nHi\n"
    a = _preview(body, created="2026-01-01T10:00:00Z")
    b = _preview(body, created="2026-01-01T11:00:00Z")
    assert exactly_one_trusted_preview([a], None) is a
    with pytest.raises(PreviewMigrationNeeded):
        exactly_one_trusted_preview([], None)
    with pytest.raises(ApprovalGuardError, match="ambiguous"):
        exactly_one_trusted_preview([a, b], None)
    # Preview before last edit does not count.
    with pytest.raises(PreviewMigrationNeeded):
        exactly_one_trusted_preview(
            [a], "2026-01-01T10:30:00Z"
        )
    assert exactly_one_trusted_preview(
        [a, b], "2026-01-01T10:30:00Z"
    ) is b


def test_assert_digest_binds_match_and_mismatch():
    body = "## Message\n\nBound @Prusa3D\n"
    comments = [_preview(body)]
    dig, preview = assert_digest_binds(comments, body)
    assert dig == message_digest(body)
    assert preview is comments[0]
    with pytest.raises(PreviewMigrationNeeded, match="does not match"):
        assert_digest_binds(
            [_preview("## Message\n\nStale\n")], body
        )


def test_latest_human_approval_allowlist_and_actor_type():
    preview_at = "2026-01-01T10:00:00Z"
    events = [
        {"event": "labeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-01T12:00:00Z",
         "actor": {"login": "shaiss", "type": "User"}},
    ]
    assert latest_human_approval_at(
        events, preview_created_at=preview_at, approver_logins=["shaiss"]
    ) == "2026-01-01T12:00:00Z"
    # Empty allowlist fails closed.
    with pytest.raises(ApprovalGuardError, match="empty"):
        latest_human_approval_at(
            events, preview_created_at=preview_at, approver_logins=[]
        )
    # Bot actor ignored.
    with pytest.raises(ApprovalGuardError, match="allowlisted User"):
        latest_human_approval_at(
            [{"event": "labeled", "label": {"name": APPROVAL_LABEL},
              "created_at": "2026-01-01T12:00:00Z",
              "actor": {"login": "github-actions[bot]", "type": "Bot"}}],
            preview_created_at=preview_at,
            approver_logins=["shaiss", "github-actions[bot]"],
        )
    # Non-allowlisted User ignored.
    with pytest.raises(ApprovalGuardError, match="allowlisted User"):
        latest_human_approval_at(
            [{"event": "labeled", "label": {"name": APPROVAL_LABEL},
              "created_at": "2026-01-01T12:00:00Z",
              "actor": {"login": "other", "type": "User"}}],
            preview_created_at=preview_at,
            approver_logins=["shaiss"],
        )
    # Label before preview ignored.
    with pytest.raises(ApprovalGuardError, match="after the trusted preview"):
        latest_human_approval_at(
            [{"event": "labeled", "label": {"name": APPROVAL_LABEL},
              "created_at": "2026-01-01T09:00:00Z",
              "actor": {"login": "shaiss", "type": "User"}}],
            preview_created_at=preview_at,
            approver_logins=["shaiss"],
        )


def test_assert_live_gates_happy_path():
    body = "## Message\n\nBound @Prusa3D\n"
    preview = _preview(body, created="2026-01-01T10:00:00Z")
    events = [{
        "event": "labeled", "label": {"name": APPROVAL_LABEL},
        "created_at": "2026-01-01T12:00:00Z",
        "actor": {"login": "shaiss", "type": "User"},
    }]
    dig, approved, _ = assert_live_gates(
        [preview], body, events, None, ["shaiss"]
    )
    assert dig == message_digest(body)
    assert approved == "2026-01-01T12:00:00Z"


def test_assert_live_gates_migration_needed():
    with pytest.raises(PreviewMigrationNeeded):
        assert_live_gates(
            [], "## Message\n\nHi\n", [], None, ["shaiss"]
        )


def test_parse_approver_allowlist():
    assert parse_approver_allowlist("shaiss, alice") == frozenset(
        {"shaiss", "alice"}
    )
    assert parse_approver_allowlist("") == frozenset()
    assert parse_approver_allowlist(None) == frozenset()
