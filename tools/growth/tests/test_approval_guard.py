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
    assert_render_binds,
    body_edited_after_approval,
    exactly_one_trusted_preview,
    is_trusted_preview_comment,
    latest_bot_removal_at,
    latest_human_approval_at,
    latest_labeled_at,
    latest_labeled_event,
    parse_approver_allowlist,
    parse_require_direct_human_label,
)
from growth.roottags import (
    DRYRUN_MARKER,
    digest_comment_line,
    message_digest,
    parse_message_digest,
    parse_render_digest,
    preview_digest_header,
    render_digest,
)


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
    assert latest_labeled_event(events)["created_at"] == "2026-01-04T08:00:00Z"


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
             forged_mid=False, old_format=False, root="", thread=None,
             message_digest_only=False) -> dict:
    if updated is None:
        updated = created
    if old_format:
        text = f"{DRYRUN_MARKER}\nold format without digest"
    elif forged_mid:
        text = (
            f"intro\n{DRYRUN_MARKER}\n{digest_comment_line(body)}\n"
            f"{preview_digest_header(body, root, thread).splitlines()[2]}\ntrail"
        )
    elif message_digest_only:
        text = f"{DRYRUN_MARKER}\n{digest_comment_line(body)}\npreview body"
    else:
        text = f"{preview_digest_header(body, root, thread)}preview body"
    return {
        "body": text,
        "user": {"login": login, "type": utype},
        "created_at": created,
        "updated_at": updated,
    }


def _labeled(at, login="shaiss", utype="User", via_app=None):
    ev = {
        "event": "labeled",
        "label": {"name": APPROVAL_LABEL},
        "created_at": at,
        "actor": {"login": login, "type": utype},
    }
    if via_app is not None:
        ev["performed_via_github_app"] = via_app
    return ev


def _unlabeled(at, login=TRUSTED_PREVIEW_LOGIN, utype=TRUSTED_PREVIEW_TYPE):
    return {
        "event": "unlabeled",
        "label": {"name": APPROVAL_LABEL},
        "created_at": at,
        "actor": {"login": login, "type": utype},
    }


def test_parse_message_digest_requires_first_two_lines_exact():
    body = "## Message\n\nHi\n"
    dig = digest_comment_line(body)
    good = f"{DRYRUN_MARKER}\n{dig}\nrest"
    assert parse_message_digest(good) == message_digest(body)
    # Mid-body / quoted / fenced markers never trusted (#1021).
    assert parse_message_digest(
        f"x\n{DRYRUN_MARKER}\n{dig}\n"
    ) is None
    assert parse_message_digest(
        f"> {DRYRUN_MARKER}\n> {dig}\n"
    ) is None
    assert parse_message_digest(
        f"```html\n{DRYRUN_MARKER}\n{dig}\n```\n"
    ) is None
    # Digest present but not immediately after the marker.
    assert parse_message_digest(
        f"{DRYRUN_MARKER}\npreview header\n{dig}\n"
    ) is None
    # Leading whitespace on the marker line is a deliberate reject.
    assert parse_message_digest(f" {DRYRUN_MARKER}\n{dig}\n") is None
    # Old format (no digest line).
    assert parse_message_digest(f"{DRYRUN_MARKER}\nno digest") is None
    # Whitespace on the digest line rejects.
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
        _preview(body, message_digest_only=True)  # pre-#1023 two-line header
    )
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


def test_assert_digest_binds_match_and_mismatch_without_edit():
    body = "## Message\n\nBound @Prusa3D\n"
    comments = [_preview(body)]
    dig, preview = assert_digest_binds(comments, body)
    assert dig == message_digest(body)
    assert preview is comments[0]
    # Digest mismatch on an existing trusted preview → refuse, do NOT migrate.
    with pytest.raises(ApprovalGuardError, match="digest mismatch without edit"):
        assert_digest_binds(
            [_preview("## Message\n\nStale\n")], body
        )


def test_latest_human_approval_allowlist_and_actor_type():
    preview_at = "2026-01-01T10:00:00Z"
    events = [_labeled("2026-01-01T12:00:00Z")]
    assert latest_human_approval_at(
        events, preview_created_at=preview_at, approver_logins=["shaiss"]
    ) == "2026-01-01T12:00:00Z"
    # Empty allowlist fails closed.
    with pytest.raises(ApprovalGuardError, match="empty"):
        latest_human_approval_at(
            events, preview_created_at=preview_at, approver_logins=[]
        )
    # Bot actor as the LATEST labeled → refuse.
    with pytest.raises(ApprovalGuardError, match="not by a User"):
        latest_human_approval_at(
            [_labeled("2026-01-01T12:00:00Z",
                      login="github-actions[bot]", utype="Bot")],
            preview_created_at=preview_at,
            approver_logins=["shaiss", "github-actions[bot]"],
        )
    # Non-allowlisted User as the LATEST labeled → refuse.
    with pytest.raises(ApprovalGuardError, match="not an allowlisted User"):
        latest_human_approval_at(
            [_labeled("2026-01-01T12:00:00Z", login="other", utype="User")],
            preview_created_at=preview_at,
            approver_logins=["shaiss"],
        )
    # Label before preview → refuse.
    with pytest.raises(ApprovalGuardError, match="after the trusted preview"):
        latest_human_approval_at(
            [_labeled("2026-01-01T09:00:00Z")],
            preview_created_at=preview_at,
            approver_logins=["shaiss"],
        )


def test_stale_revoked_approval_shaiss_unlabels_then_other_relabels():
    """Shai labels, then unlabels, then someone else re-adds → refuse.

    The latest labeled event overall is the non-allowlisted re-add.
    """
    preview_at = "2026-01-01T10:00:00Z"
    events = [
        _labeled("2026-01-01T11:00:00Z", login="shaiss"),
        _unlabeled("2026-01-01T12:00:00Z", login="shaiss", utype="User"),
        _labeled("2026-01-01T13:00:00Z", login="other", utype="User"),
    ]
    with pytest.raises(ApprovalGuardError, match="not an allowlisted User"):
        latest_human_approval_at(
            events, preview_created_at=preview_at, approver_logins=["shaiss"]
        )


def test_stale_approval_in_gap_before_bot_removal_then_other_relabels():
    """Shai labels between preview and bot removal; bot removes; other re-adds.

    Latest labeled is the non-allowlisted re-add → refuse. Even an allowlisted
    label that sits in the gap before the bot removal would also refuse.
    """
    preview_at = "2026-01-01T10:00:00Z"
    events = [
        _labeled("2026-01-01T11:00:00Z", login="shaiss"),  # in the gap
        _unlabeled("2026-01-01T12:00:00Z"),  # bot self-migrate removal
        _labeled("2026-01-01T13:00:00Z", login="other", utype="User"),
    ]
    assert latest_bot_removal_at(events).isoformat().startswith("2026-01-01T12:00:00")
    with pytest.raises(ApprovalGuardError, match="not an allowlisted User"):
        latest_human_approval_at(
            events, preview_created_at=preview_at, approver_logins=["shaiss"]
        )
    # Same gap label, no later re-add: latest labeled is before bot removal.
    with pytest.raises(ApprovalGuardError, match="after the bot's most recent removal"):
        latest_human_approval_at(
            events[:2], preview_created_at=preview_at, approver_logins=["shaiss"]
        )
    # Allowlisted re-apply AFTER bot removal succeeds.
    ok = events[:2] + [_labeled("2026-01-01T13:00:00Z", login="shaiss")]
    assert latest_human_approval_at(
        ok, preview_created_at=preview_at, approver_logins=["shaiss"]
    ) == "2026-01-01T13:00:00Z"


def test_unlabeled_after_latest_labeled_refuses():
    preview_at = "2026-01-01T10:00:00Z"
    events = [
        _labeled("2026-01-01T12:00:00Z", login="shaiss"),
        _unlabeled("2026-01-01T13:00:00Z", login="shaiss", utype="User"),
    ]
    with pytest.raises(ApprovalGuardError, match="unlabeled after"):
        latest_human_approval_at(
            events, preview_created_at=preview_at, approver_logins=["shaiss"]
        )


def test_require_direct_human_label_true_and_false():
    preview_at = "2026-01-01T10:00:00Z"
    via = {"id": 1, "slug": "some-app"}
    events = [_labeled("2026-01-01T12:00:00Z", via_app=via)]
    assert parse_require_direct_human_label(None) is True
    assert parse_require_direct_human_label("true") is True
    assert parse_require_direct_human_label("TRUE") is True  # not exactly false
    assert parse_require_direct_human_label("false") is False
    with pytest.raises(ApprovalGuardError, match="performed via a GitHub App"):
        latest_human_approval_at(
            events,
            preview_created_at=preview_at,
            approver_logins=["shaiss"],
            require_direct_human_label=True,
        )
    assert latest_human_approval_at(
        events,
        preview_created_at=preview_at,
        approver_logins=["shaiss"],
        require_direct_human_label=False,
    ) == "2026-01-01T12:00:00Z"
    # Explicit null / absent still ok when require=True.
    assert latest_human_approval_at(
        [_labeled("2026-01-01T12:00:00Z", via_app=None)],
        preview_created_at=preview_at,
        approver_logins=["shaiss"],
        require_direct_human_label=True,
    ) == "2026-01-01T12:00:00Z"


def test_assert_live_gates_happy_path():
    body = "## Message\n\nBound @Prusa3D\n"
    preview = _preview(body, created="2026-01-01T10:00:00Z", root="Bound @Prusa3D")
    events = [_labeled("2026-01-01T12:00:00Z")]
    dig, approved, prev = assert_live_gates(
        [preview], body, events, None, ["shaiss"]
    )
    assert dig == message_digest(body)
    assert approved == "2026-01-01T12:00:00Z"
    assert assert_render_binds(prev, "Bound @Prusa3D") == render_digest(
        "Bound @Prusa3D"
    )


def test_assert_render_binds_match_altered_and_bare_domain():
    """Issue #1023: live copy must match the approved preview render-digest."""
    body = (
        "## Message\n\nApproved copy @Prusa3D\n\n"
        "## Link\n\nhttps://github.com/shaiss/print-bench\n"
    )
    approved = "Approved copy @Prusa3D https://github.com/shaiss/print-bench"
    preview = _preview(body, root=approved)
    assert parse_render_digest(preview["body"]) == render_digest(approved)
    assert assert_render_binds(preview, approved) == render_digest(approved)
    with pytest.raises(ApprovalGuardError, match="render-digest mismatch"):
        assert_render_binds(
            preview,
            "Altered prose @Prusa3D https://github.com/shaiss/print-bench",
        )
    with pytest.raises(ApprovalGuardError, match="render-digest mismatch"):
        assert_render_binds(preview, approved + " see example.com/x")
    # Message-digest-only header is not a trusted preview; render parse fails.
    old = _preview(body, root=approved, message_digest_only=True)
    assert parse_render_digest(old["body"]) is None
    with pytest.raises(ApprovalGuardError, match="unreadable render-digest"):
        assert_render_binds(old, approved)


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
