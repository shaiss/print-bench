"""Post-approval body-edit + trusted-preview digest guards for live posts.

The ``approved-to-post`` label is the human gate on a queue item. This
module is the pure half of the LIVE gates (the posting tool fetches
network data and acts):

* **Trusted preview** — a dry-run / self-migrate comment whose *first two
  lines* are exactly the dry-run marker and the ``message-digest`` line,
  authored by ``github-actions[bot]`` with ``type == "Bot"``, never edited
  (``updated_at == created_at``). The old marker-only format is never
  trusted. Markers mid-body are never trusted.

* **Exactly-one rule** — there must be **exactly one** trusted preview
  whose ``created_at`` is **strictly later** than GraphQL ``lastEditedAt``
  (when ``lastEditedAt`` is null, every trusted preview qualifies). Zero
  → missing (caller may self-migrate). More than one → refuse on
  ambiguity (a human deletes extras before re-approving).

* **Human approval** — a ``labeled`` event for ``approved-to-post`` counts
  only when ``actor.login`` is on the allowlist, ``actor.type == "User"``,
  and ``created_at`` is strictly later than the trusted preview's
  ``created_at``. Empty allowlist → fail closed.

* **Body freeze** — ``lastEditedAt`` must not be after that human
  approval timestamp.

Fetch mechanics live in the posting tool; this module never touches the
network.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from .roottags import DRYRUN_MARKER, message_digest, parse_message_digest

APPROVAL_LABEL = "approved-to-post"
# REST GITHUB_TOKEN comments are exactly this login + type. GraphQL's bare
# ``github-actions`` spelling is NOT trusted for preview comments (forge
# surface); only the Bot account that writes issue comments via REST.
TRUSTED_PREVIEW_LOGIN = "github-actions[bot]"
TRUSTED_PREVIEW_TYPE = "Bot"


class ApprovalGuardError(ValueError):
    """Timeline/edit info missing, body edited after approval, or digest
    binding failed."""


class PreviewMigrationNeeded(ApprovalGuardError):
    """No matching trusted preview after the latest body edit — the LIVE
    path should write a preview and remove ``approved-to-post`` rather than
    post."""


def _parse_iso(ts: str) -> datetime:
    """Parse a GitHub ISO-8601 timestamp into an aware UTC datetime."""
    raw = (ts or "").strip()
    if not raw:
        raise ApprovalGuardError("empty timestamp")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as e:
        raise ApprovalGuardError(f"unparseable timestamp {ts!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_approver_allowlist(raw: str | None) -> frozenset[str]:
    """Comma-separated logins from ``GROWTH_APPROVER_LOGINS``. Empty → empty set."""
    if raw is None:
        return frozenset()
    return frozenset(p.strip() for p in raw.split(",") if p.strip())


def latest_labeled_at(events: list[dict], label: str = APPROVAL_LABEL) -> str | None:
    """The ``created_at`` of the most recent ``labeled`` event for *label*.

    Actor is ignored here — use :func:`latest_human_approval_at` for LIVE.
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
    """True iff the body was edited strictly after the approval label event."""
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
    """Raise when a LIVE post must not proceed due to a stale body."""
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


def _comment_user(comment: dict) -> dict:
    user = comment.get("user") or comment.get("author") or {}
    return user if isinstance(user, dict) else {}


def is_trusted_preview_comment(comment: dict) -> bool:
    """True iff *comment* meets every trusted-preview hard requirement."""
    user = _comment_user(comment)
    if user.get("login") != TRUSTED_PREVIEW_LOGIN:
        return False
    if user.get("type") != TRUSTED_PREVIEW_TYPE:
        return False
    created = comment.get("created_at") or ""
    updated = comment.get("updated_at") or ""
    if not created or not updated:
        return False
    if created != updated:
        return False
    return parse_message_digest(comment.get("body") or "") is not None


def trusted_previews_after_edit(
    comments: list[dict],
    last_edited_at: str | None,
) -> list[dict]:
    """Trusted previews with ``created_at`` strictly after *last_edited_at*.

    When *last_edited_at* is null/empty (body never edited after creation),
    every trusted preview qualifies.
    """
    cutoff: datetime | None = None
    if last_edited_at is not None and str(last_edited_at).strip():
        cutoff = _parse_iso(str(last_edited_at))
    out: list[dict] = []
    for comment in comments or []:
        if not is_trusted_preview_comment(comment):
            continue
        try:
            created = _parse_iso(comment.get("created_at") or "")
        except ApprovalGuardError:
            continue
        if cutoff is not None and created <= cutoff:
            continue
        out.append(comment)
    return out


def exactly_one_trusted_preview(
    comments: list[dict],
    last_edited_at: str | None,
) -> dict:
    """Return the sole trusted preview after the latest body edit.

    Raises :class:`PreviewMigrationNeeded` when there are zero (caller may
    write a preview and remove the approval label). Raises
    :class:`ApprovalGuardError` when there are two or more (ambiguity —
    refuse; a human deletes extras before re-approving).
    """
    found = trusted_previews_after_edit(comments, last_edited_at)
    if len(found) == 0:
        raise PreviewMigrationNeeded(
            "no trusted preview comment after the latest body edit — "
            "write a preview and remove approved-to-post (self-migrate)"
        )
    if len(found) > 1:
        raise ApprovalGuardError(
            f"ambiguous: {len(found)} trusted preview comments after the "
            f"latest body edit — delete extras so exactly one remains; "
            f"refusing live post (fail closed)"
        )
    return found[0]


def latest_human_approval_at(
    events: list[dict],
    *,
    preview_created_at: str,
    approver_logins: Iterable[str],
    label: str = APPROVAL_LABEL,
) -> str:
    """``created_at`` of the latest allowlisted User ``labeled`` event after the preview.

    Empty *approver_logins* fails closed. Bot actors and non-allowlisted
    logins are ignored. Events at or before the preview are ignored.
    """
    allow = frozenset(a for a in approver_logins if a)
    if not allow:
        raise ApprovalGuardError(
            "GROWTH_APPROVER_LOGINS is empty — refusing live post (fail closed)"
        )
    preview_dt = _parse_iso(preview_created_at)
    latest: str | None = None
    latest_dt: datetime | None = None
    for ev in events or []:
        if (ev.get("event") or "").lower() != "labeled":
            continue
        lbl = ev.get("label")
        name = lbl.get("name", "") if isinstance(lbl, dict) else (lbl or "")
        if name != label:
            continue
        actor = ev.get("actor") or {}
        if not isinstance(actor, dict):
            continue
        if actor.get("type") != "User":
            continue
        login = actor.get("login") or ""
        if login not in allow:
            continue
        created = ev.get("created_at") or ""
        try:
            dt = _parse_iso(created)
        except ApprovalGuardError:
            continue
        if dt <= preview_dt:
            continue
        if latest_dt is None or dt > latest_dt:
            latest_dt = dt
            latest = created
    if latest is None:
        raise ApprovalGuardError(
            "no allowlisted User approved-to-post label event after the "
            "trusted preview — a human must re-apply the label after the "
            "preview; refusing live post (fail closed)"
        )
    return latest


def assert_digest_binds(
    comments: list[dict],
    body: str | None,
    *,
    last_edited_at: str | None = None,
) -> tuple[str, dict]:
    """Exactly one trusted preview after last edit, digest matches *body*.

    Returns ``(digest_hex, preview_comment)``. Raises
    :class:`PreviewMigrationNeeded` when zero trusted previews (or the one
    present has a mismatched digest — treated as migration). Raises
    :class:`ApprovalGuardError` on ambiguity or unreadable timestamps.
    """
    try:
        preview = exactly_one_trusted_preview(comments, last_edited_at)
    except PreviewMigrationNeeded:
        raise
    digest = parse_message_digest(preview.get("body") or "")
    if digest is None:
        # is_trusted_preview_comment should have filtered this; fail closed.
        raise ApprovalGuardError(
            "trusted preview comment has an unreadable message-digest — "
            "refusing live post (fail closed)"
        )
    expected = message_digest(body)
    if digest != expected:
        raise PreviewMigrationNeeded(
            f"trusted preview message-digest {digest} does not match current "
            f"## Message first paragraph ({expected}) — write a fresh preview "
            f"and remove approved-to-post (self-migrate)"
        )
    return digest, preview


def assert_live_gates(
    comments: list[dict],
    body: str | None,
    events: list[dict],
    last_edited_at: str | None,
    approver_logins: Iterable[str],
) -> tuple[str, str, dict]:
    """Full LIVE gate: preview bind + human approval after preview + freeze.

    Returns ``(digest, approved_at, preview_comment)``. Propagates
    :class:`PreviewMigrationNeeded` for the self-migrate path.
    """
    digest, preview = assert_digest_binds(
        comments, body, last_edited_at=last_edited_at
    )
    preview_created = preview.get("created_at") or ""
    if not preview_created:
        raise ApprovalGuardError(
            "trusted preview is missing created_at — refusing (fail closed)"
        )
    approved_at = latest_human_approval_at(
        events,
        preview_created_at=preview_created,
        approver_logins=approver_logins,
    )
    assert_body_fresh_for_live(approved_at, last_edited_at)
    return digest, approved_at, preview


# Back-compat alias used by older tests / docs pointers.
def latest_trusted_dryrun_digest(
    comments: list[dict],
    *,
    last_edited_at: str | None = None,
) -> str | None:
    """Digest of the sole trusted preview after *last_edited_at*, or None.

    Ambiguity (2+) raises :class:`ApprovalGuardError`. Zero returns None.
    """
    found = trusted_previews_after_edit(comments, last_edited_at)
    if len(found) > 1:
        raise ApprovalGuardError(
            f"ambiguous: {len(found)} trusted preview comments after the "
            f"latest body edit"
        )
    if not found:
        return None
    return parse_message_digest(found[0].get("body") or "")
