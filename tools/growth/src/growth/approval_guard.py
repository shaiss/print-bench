"""Post-approval body-edit + dry-run digest guards for live growth posts.

The ``approved-to-post`` label is the human gate on a queue item. An author
(or anyone with write access) can edit the issue body *after* that label is
applied — and with root-@tag restoration, a post-approval edit of
``## Message`` becomes deterministic brand-account copy. This module is the
pure half of the fix:

* given the latest approval timestamp and the body's ``lastEditedAt``,
  decide whether the body is stale;
* given the issue's comments and the current body, decide whether a
  trusted dry-run comment's ``message-digest`` still matches the
  NFKC-normalized ``## Message`` first paragraph (approved-text binding).

Fetch mechanics (issue events / GraphQL ``lastEditedAt``) live in the
posting tool; this module never touches the network. Fail-closed for
unreadable timestamps / missing digests is the caller's job — this only
compares what it is handed.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from .roottags import message_digest, parse_message_digest

APPROVAL_LABEL = "approved-to-post"
# The workflow posts dry-run comments with GITHUB_TOKEN → REST
# ``github-actions[bot]`` / GraphQL ``github-actions``. Same normalization
# as growth.daycap.
TRUSTED_DRYRUN_AUTHORS = ("github-actions[bot]", "github-actions")
DRYRUN_MARKER = "<!-- growth-twitter:dry-run -->"


class ApprovalGuardError(ValueError):
    """Timeline/edit info missing, body edited after approval, or digest
    binding failed."""


def _norm_login(login: str) -> str:
    login = (login or "").strip()
    return login[:-5] if login.endswith("[bot]") else login


def _parse_iso(ts: str) -> datetime:
    """Parse a GitHub ISO-8601 timestamp into an aware UTC datetime."""
    raw = (ts or "").strip()
    if not raw:
        raise ApprovalGuardError("empty timestamp")
    # GitHub emits ``...Z``; fromisoformat wants ``+00:00``.
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as e:
        raise ApprovalGuardError(f"unparseable timestamp {ts!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def latest_labeled_at(events: list[dict], label: str = APPROVAL_LABEL) -> str | None:
    """The ``created_at`` of the most recent ``labeled`` event for *label*.

    *events* is a list of dicts with at least ``event``, ``label`` (name
    string or ``{"name": ...}``), and ``created_at`` — the shape of GitHub's
    issue-events API (and of the GraphQL LabeledEvent projection the posting
    tool may hand in). ``unlabeled`` events are ignored for the "latest
    approval" question: a re-label after an edit is a fresh approval.
    Returns ``None`` when no matching labeled event exists.
    """
    latest: str | None = None
    latest_dt: datetime | None = None
    for ev in events or []:
        if (ev.get("event") or "").lower() != "labeled":
            continue
        lbl = ev.get("label")
        name = lbl.get("name", "") if isinstance(lbl, dict) else (lbl or "")
        if name != label:
            continue
        created = ev.get("created_at") or ""
        try:
            dt = _parse_iso(created)
        except ApprovalGuardError:
            continue
        if latest_dt is None or dt > latest_dt:
            latest_dt = dt
            latest = created
    return latest


def body_edited_after_approval(
    approved_at: str,
    last_edited_at: str | None,
) -> bool:
    """True iff the body was edited strictly after the approval label event.

    ``last_edited_at is None`` means the body was never edited after creation
    (GraphQL ``lastEditedAt`` is null) — that is not stale. Empty
    ``approved_at`` raises :class:`ApprovalGuardError` (caller must fail
    closed rather than treat a missing approval time as fresh).
    """
    if not (approved_at or "").strip():
        raise ApprovalGuardError(
            "approved-to-post label time is missing — refusing to judge freshness"
        )
    approved = _parse_iso(approved_at)
    if last_edited_at is None or not str(last_edited_at).strip():
        return False
    edited = _parse_iso(str(last_edited_at))
    return edited > approved


def assert_body_fresh_for_live(
    approved_at: str | None,
    last_edited_at: str | None,
) -> None:
    """Raise :class:`ApprovalGuardError` when a LIVE post must not proceed.

    Requires a known approval timestamp. A body edited after that timestamp
    is refused; a never-edited body is allowed.
    """
    if approved_at is None or not str(approved_at).strip():
        raise ApprovalGuardError(
            "could not find an approved-to-post labeled timeline event — "
            "refusing live post (fail closed)"
        )
    if body_edited_after_approval(str(approved_at), last_edited_at):
        raise ApprovalGuardError(
            f"issue body was edited after approved-to-post "
            f"(approved_at={approved_at}, last_edited_at={last_edited_at}) — "
            f"re-apply the approval label on the current body, or refuse"
        )


def _comment_login(comment: dict) -> str:
    user = comment.get("user") or comment.get("author") or {}
    if isinstance(user, dict):
        return user.get("login") or ""
    return str(user or "")


def latest_trusted_dryrun_digest(
    comments: list[dict],
    *,
    trusted_authors: Iterable[str] = TRUSTED_DRYRUN_AUTHORS,
    dryrun_marker: str = DRYRUN_MARKER,
) -> str | None:
    """sha256 from the latest dry-run comment authored by a trusted bot.

    Looks only at comments that carry *dryrun_marker* AND a parseable
    ``message-digest`` line, whose author normalizes to one of
    *trusted_authors* (``[bot]``-suffix collapsed). Look-alike human
    logins cannot match the reserved ``github-actions`` name. Returns
    ``None`` when no such comment exists.
    """
    trusted = {_norm_login(a) for a in trusted_authors if a}
    latest: str | None = None
    for comment in comments or []:
        body = comment.get("body") or ""
        if dryrun_marker not in body:
            continue
        if _norm_login(_comment_login(comment)) not in trusted:
            continue
        digest = parse_message_digest(body)
        if digest:
            latest = digest
    return latest


def assert_digest_binds(
    comments: list[dict],
    body: str | None,
    *,
    trusted_authors: Iterable[str] = TRUSTED_DRYRUN_AUTHORS,
    dryrun_marker: str = DRYRUN_MARKER,
) -> str:
    """Raise if no trusted dry-run digest matches the current Message paragraph.

    Returns the matching digest hex on success.
    """
    recorded = latest_trusted_dryrun_digest(
        comments, trusted_authors=trusted_authors, dryrun_marker=dryrun_marker
    )
    if recorded is None:
        raise ApprovalGuardError(
            "no trusted dry-run comment with a message-digest was found — "
            "re-run a dry-run from the growth-twitter workflow, then approve; "
            "refusing live post (fail closed)"
        )
    expected = message_digest(body)
    if recorded != expected:
        raise ApprovalGuardError(
            f"dry-run message-digest {recorded} does not match current "
            f"## Message first paragraph ({expected}) — body changed since "
            f"the dry-run; re-dry-run and re-approve; refusing live post"
        )
    return expected
