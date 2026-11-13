"""Post-approval body-edit guard — pure comparison the posting tool enforces."""

from __future__ import annotations

import pytest

from growth.approval_guard import (
    APPROVAL_LABEL,
    ApprovalGuardError,
    DRYRUN_MARKER,
    assert_body_fresh_for_live,
    assert_digest_binds,
    body_edited_after_approval,
    latest_labeled_at,
    latest_trusted_dryrun_digest,
)
from growth.roottags import digest_comment_line, message_digest


def test_latest_labeled_at_picks_most_recent_approval():
    events = [
        {"event": "labeled", "label": {"name": "growth-queue"},
         "created_at": "2026-01-01T00:00:00Z"},
        {"event": "labeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-02T12:00:00Z"},
        {"event": "unlabeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-03T00:00:00Z"},
        {"event": "labeled", "label": APPROVAL_LABEL,  # bare string shape
         "created_at": "2026-01-04T08:00:00Z"},
    ]
    assert latest_labeled_at(events) == "2026-01-04T08:00:00Z"


def test_latest_labeled_at_none_when_missing():
    assert latest_labeled_at([]) is None
    assert latest_labeled_at(
        [{"event": "labeled", "label": {"name": "other"},
          "created_at": "2026-01-01T00:00:00Z"}]
    ) is None


def test_body_never_edited_is_fresh():
    assert body_edited_after_approval("2026-01-02T00:00:00Z", None) is False
    assert body_edited_after_approval("2026-01-02T00:00:00Z", "") is False


def test_body_edited_before_approval_is_fresh():
    assert body_edited_after_approval(
        "2026-01-02T12:00:00Z", "2026-01-02T11:59:59Z"
    ) is False


def test_body_edited_after_approval_is_stale():
    assert body_edited_after_approval(
        "2026-01-02T12:00:00Z", "2026-01-02T12:00:01Z"
    ) is True


def test_assert_body_fresh_for_live_refuses_missing_approval_time():
    with pytest.raises(ApprovalGuardError, match="fail closed"):
        assert_body_fresh_for_live(None, None)
    with pytest.raises(ApprovalGuardError, match="fail closed"):
        assert_body_fresh_for_live("", None)


def test_assert_body_fresh_for_live_refuses_stale_body():
    with pytest.raises(ApprovalGuardError, match="edited after"):
        assert_body_fresh_for_live(
            "2026-01-02T12:00:00Z", "2026-01-03T00:00:00Z"
        )


def test_assert_body_fresh_for_live_allows_fresh_body():
    assert_body_fresh_for_live("2026-01-02T12:00:00Z", None)
    assert_body_fresh_for_live(
        "2026-01-02T12:00:00Z", "2026-01-02T11:00:00Z"
    )


def _bot_dryrun(body: str, login: str = "github-actions[bot]") -> dict:
    return {
        "body": f"{DRYRUN_MARKER}\n{digest_comment_line(body)}\ndry-ran",
        "user": {"login": login},
    }


def test_latest_trusted_dryrun_digest_picks_bot_authored():
    body = "## Message\n\nHello @Prusa3D\n"
    comments = [
        {"body": f"{DRYRUN_MARKER}\nold", "user": {"login": "alice"}},
        _bot_dryrun("## Message\n\nOld draft\n"),
        _bot_dryrun(body),  # latest matching
    ]
    assert latest_trusted_dryrun_digest(comments) == message_digest(body)


def test_latest_trusted_dryrun_digest_ignores_lookalike_authors():
    body = "## Message\n\nHello @Prusa3D\n"
    comments = [
        _bot_dryrun(body, login="github-actions-imposter"),
        _bot_dryrun(body, login="not-github-actions"),
    ]
    assert latest_trusted_dryrun_digest(comments) is None


def test_latest_trusted_dryrun_digest_accepts_github_actions_without_bot_suffix():
    body = "## Message\n\nHello\n"
    comments = [_bot_dryrun(body, login="github-actions")]
    assert latest_trusted_dryrun_digest(comments) == message_digest(body)


def test_assert_digest_binds_refuses_missing():
    with pytest.raises(ApprovalGuardError, match="message-digest"):
        assert_digest_binds([], "## Message\n\nHi\n")


def test_assert_digest_binds_refuses_mismatch():
    body = "## Message\n\nCurrent @Prusa3D\n"
    comments = [_bot_dryrun("## Message\n\nStale @Prusa3D\n")]
    with pytest.raises(ApprovalGuardError, match="does not match"):
        assert_digest_binds(comments, body)


def test_assert_digest_binds_accepts_matching_bot_digest():
    body = "## Message\n\nBound @Prusa3D\n"
    comments = [_bot_dryrun(body)]
    assert assert_digest_binds(comments, body) == message_digest(body)
