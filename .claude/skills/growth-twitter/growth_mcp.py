#!/usr/bin/env python3
"""growth_mcp.py — Lark's posting surface (Twitter/X), as a stdio MCP tool.

WHY AN MCP TOOL (the same dead end the scout hit)
-------------------------------------------------
Lark's only write is "post ONE queued item to the channel" — and even the
dry-run form of that is rich multi-line markdown (the rendered tweet, a
thread, a table of weights) landing as an issue comment. Under
`--permission-mode dontAsk` the Bash matcher denies any command whose
argument reads as shell structure — an embedded newline is enough, no
quoting fixes it (scout_mcp.py's header has the proof). A JSON tool argument
never touches a command line. Same pattern, the channel-facing consumer.

SECURITY (this tool can reach OUTSIDE the repo — the most-guarded write here)
-----------------------------------------------------------------------------
A live call publishes text to the public internet under the bench's name,
composed by a model that just read UNTRUSTED queue-issue text. So this
server trusts nothing and layers every gate the desk has:

  * DRY-RUN IS THE DEFAULT. A live post happens only when the human live key
    (`GROWTH_TWITTER_LIVE` == 'true', a repo variable no agent can set) AND
    all four X credentials are present. Anything less → the would-be tweet
    lands as a comment on the queue issue, which is the designed deliverable
    for review, not a degraded failure.
  * HUMAN APPROVAL PER ITEM. In live mode (unless the committed policy says
    `require_approval: false`, surfaced as GROWTH_REQUIRE_APPROVAL) the
    queue issue must carry the `approved-to-post` label — a label only a
    human applies; this tool applies NO labels at all.
  * WRITE-TIME TARGET RE-READ. The tool refuses unless the issue is open,
    not a PR, labeled `growth-queue` AND `channel:twitter`, and not parked
    `needs-decision` — a prompt-injected number cannot reach anything else.
  * CANDIDATE BINDING. When the trusted workflow Select step exports
    `GROWTH_SELECTED_ISSUES`, any number outside that set is refused.
  * ONE POST PER QUEUE ITEM, EVER. A hidden marker comment records each
    outcome; a `posted` marker refuses forever, a `dry-run` marker refuses
    further dry-runs (the daily sweep is idempotent) while still allowing
    the eventual approved live post.
  * WEIGHTED LENGTH. Copy is metered with the same rule tools/growth ships
    (URLs = 23, wide code points = 2, hard cap 280 — the parity test pins
    the two implementations together); an over-weight tweet is refused, so
    an unpostable draft can never burn the approval.
  * ROOT @-TAGS. The first paragraph of the queue item's ``## Message`` is
    the drafted root tweet and may end with brand/community ``@handles``.
    Issue body stays UNTRUSTED — this tool extracts handles matching
    ``^@[A-Za-z0-9_]{1,15}$`` only, never obeys instructions in it. At most
    5 required handles (over the cap → refuse). If the composed root
    dropped any required handle, the tool restores them deterministically
    (drafted paragraph verbatim when it fits 280, else append the missing
    handles) or refuses rather than post untagged. Tags go in the root
    tweet only, never a thread reply. `growth.roottags` is the reference;
    the copy below is parity-pinned.
  * POST-APPROVAL BODY FREEZE (LIVE). On a live post, the issue body must
    not have been edited after the latest ``approved-to-post`` labeled
    timeline event (compare that event's time with GraphQL
    ``lastEditedAt``). Unreadable timeline/edit info fails closed. A dry
    run still proceeds but reports the stale-body condition on the comment.
    `growth.approval_guard` is the pure comparison reference.
  * PER-RUN CAP. `GROWTH_MAX_POSTS` (default 1) bounds an unattended run —
    counted in a state file every link step of the chain walk shares
    (`GROWTH_CAP_STATE`, the reeve.yml `REEVE_GREENLIGHT_STATE` pattern; issue
    #570), so the bound spans the whole walk and not one server process. The
    agent can neither set env vars nor write files, so it cannot reach or
    reset the count.
  * The GitHub writes are: the outcome comment, and — after a LIVE post
    only — closing the drained queue issue (queue semantics: the message
    was delivered). Never a label, never another repo, never code.

The OAuth 1.0a mechanics live in the tested tools/growth package
(growth.poster) — imported lazily, ONLY on the live path, from this same
checkout (a committed repo path added to sys.path; not a pip install, so the
stdlib-only rule for the unattended run holds: dry-run touches none of it).
Logs go to stderr so stdout carries nothing but JSON-RPC.

To reply under an *existing* parent tweet (not a thread this tool composed),
use the human-triggered ``growth-twitter-reply.yml`` workflow_dispatch
(``.github/workflows/growth-twitter-reply.yml``) — it calls the same
``growth.poster.post_tweet`` seam with ``reply_to`` set.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

QUEUE_LABEL = "growth-queue"
CHANNEL_LABEL = "channel:twitter"
APPROVAL_LABEL = "approved-to-post"
PARKED_LABEL = "needs-decision"
POSTED_MARKER = "<!-- growth-twitter:posted -->"
DRYRUN_MARKER = "<!-- growth-twitter:dry-run -->"
DIGEST_PREFIX = "<!-- growth-twitter:message-digest:sha256="
DIGEST_LINE_RE = re.compile(
    r"^<!-- growth-twitter:message-digest:sha256=([0-9a-f]{64}) -->$"
)
RENDER_DIGEST_PREFIX = "<!-- growth-twitter:render-digest:sha256="
RENDER_DIGEST_LINE_RE = re.compile(
    r"^<!-- growth-twitter:render-digest:sha256=([0-9a-f]{64}) -->$"
)
# REST GITHUB_TOKEN issue comments are exactly this login + Bot type.
TRUSTED_PREVIEW_LOGIN = "github-actions[bot]"
TRUSTED_PREVIEW_TYPE = "Bot"
APPROVER_LOGINS_ENV = "GROWTH_APPROVER_LOGINS"
DIRECT_HUMAN_LABEL_ENV = "GROWTH_REQUIRE_DIRECT_HUMAN_LABEL"
# Cap-state outcomes that do NOT consume the run's post slot.
_CAP_NON_CONSUMING_OUTCOMES = frozenset({"preview-migrate"})
# LIVE self-migrate may preview many approved items per run; posts still
# honor GROWTH_MAX_POSTS / max_posts_per_run.
MAX_PREVIEWS_PER_RUN = 60
# Hard bound on REST list walks (comments, events). Matching tools/growth's
# ``_MAX_PAGES``: hit the cap → RAISE (fail closed), never return a truncated
# prefix — GitHub events are oldest-first, so a silent prefix drops the
# newest label/unlabel and can miss a revocation.
MAX_LIST_PAGES = 50
LIST_PER_PAGE = 100
DRYRUN_HEADER = "## \U0001F426 Growth dry run — what Lark would have posted"
PREVIEW_HEADER = "## \U0001F426 Growth preview — re-apply approved-to-post to post"
POSTED_HEADER = "## \U0001F426 Posted to Twitter/X"
FAILURE_HEADER = "## ⚠️ Growth post failed"
FOOTER = "---\n_Generated by [Claude Code](https://claude.ai/code)_"
GITHUB_API = "https://api.github.com"
SERVER_NAME = "growth_twitter"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
MAX_THREAD_PARTS = 4

# --- the weighted length rule (self-contained copy) --------------------------
# tools/growth/src/growth/tweetlen.py is the reference implementation; this
# copy exists because the unattended server imports nothing beyond stdlib on
# the dry-run path. tools/growth/tests/test_server_parity.py pins the two
# together on a vector set, so a drift here fails CI.

MAX_WEIGHT = 280
# Case-insensitive so HTTPS:// / HtTp:// cannot bypass the allowlist,
# URL-@ skip, or the weighted-length URL meter.
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_WEIGHT_ONE_RANGES = (
    (0x0000, 0x10FF),
    (0x2000, 0x200D),
    (0x2010, 0x201F),
    (0x2032, 0x2037),
)


def _char_weight(cp):
    for lo, hi in _WEIGHT_ONE_RANGES:
        if lo <= cp <= hi:
            return 1
    return 2


def _tweet_weight(text):
    total = 0
    last = 0
    for m in _URL_RE.finditer(text):
        for ch in text[last:m.start()]:
            total += _char_weight(ord(ch))
        total += 23
        last = m.end()
    for ch in text[last:]:
        total += _char_weight(ord(ch))
    return total


# --- root @-tag preservation (self-contained copy of growth.roottags) --------
# tools/growth/src/growth/roottags.py is the reference; this copy exists for
# the same stdlib-only dry-run reason as the weighted-length copy above.
# tools/growth/tests/test_server_parity.py pins the two together.

MAX_REQUIRED_HANDLES = 5
FULLWIDTH_AT = ("\uff20", "\ufe6b")  # ＠  ﹫
_HANDLE_RE = re.compile(r"^@[A-Za-z0-9_]{1,15}$")
_HANDLE_SCAN_RE = re.compile(
    r"(?<![A-Za-z0-9_])@[A-Za-z0-9_]{1,15}(?![A-Za-z0-9_])")
_POSTED_MENTION_RE = re.compile(
    r"(?<![A-Za-z0-9_])[@\uff20\ufe6b][A-Za-z0-9_]+")
# Optional CR so GitHub CRLF bodies still match the heading.
# h2 (##, MCP/template) and h3 (###, GitHub issue-form field labels).
_MESSAGE_HEADING_RE = re.compile(
    r"^#{2,3}[ \t]+Message[ \t]*\r?$", re.IGNORECASE | re.MULTILINE)
_LINK_HEADING_RE = re.compile(
    r"^#{2,3}[ \t]+Link[ \t]*\r?$", re.IGNORECASE | re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^#{2,3}[ \t]+\S", re.MULTILINE)


class _RootTagsError(ValueError):
    pass


class _ApprovalGuardError(ValueError):
    pass


def _section_first_paragraph(body, heading_re):
    if not body:
        return ""
    m = heading_re.search(body)
    if not m:
        return ""
    rest = body[m.end():]
    next_h = _NEXT_HEADING_RE.search(rest)
    if next_h:
        rest = rest[:next_h.start()]
    chunks = []
    buf = []
    for line in rest.splitlines():
        if line.strip() == "":
            if buf:
                chunks.append(" ".join(p.strip() for p in buf if p.strip()))
                buf = []
                if chunks and chunks[-1]:
                    break
            continue
        buf.append(line)
    if buf and not chunks:
        chunks.append(" ".join(p.strip() for p in buf if p.strip()))
    for para in chunks:
        if para:
            return para
    return ""


def _message_root_paragraph(body):
    return _section_first_paragraph(body, _MESSAGE_HEADING_RE)


def _message_link_value(body):
    return _section_first_paragraph(body, _LINK_HEADING_RE)


def _message_digest(body):
    para = unicodedata.normalize("NFKC", _message_root_paragraph(body))
    link = unicodedata.normalize("NFKC", _message_link_value(body))
    return hashlib.sha256((para + "\n" + link).encode("utf-8")).hexdigest()


def _render_digest(root, thread=None):
    # Raw parts as a deterministic JSON array — no NFKC (would equate e.g.
    # 10⁵ with 105) and no NUL join (would equate root "a\0b" with root
    # "a" + reply "b"). Parity with growth.roottags.render_digest.
    parts = [root or ""]
    parts.extend(thread or [])
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _digest_comment_line(body):
    return f"{DIGEST_PREFIX}{_message_digest(body)} -->"


def _render_digest_comment_line(root, thread=None):
    return f"{RENDER_DIGEST_PREFIX}{_render_digest(root, thread)} -->"


def _preview_digest_header(body, root, thread=None):
    return (
        f"{DRYRUN_MARKER}\n"
        f"{_digest_comment_line(body)}\n"
        f"{_render_digest_comment_line(root, thread)}\n"
    )


def _parse_message_digest(comment_body):
    """sha256 when body *begins* with marker + digest (parity with roottags).

    Writer emits ``{DRYRUN_MARKER}\\n{message-digest}\\n{render-digest}\\n...``
    at column 0. Trust for the message binding is
    ``startswith(DRYRUN_MARKER + \"\\n\")`` then an exact digest line — no
    strip (leading whitespace is a deliberate reject, #1021). Mid-body /
    quoted / fenced markers and a digest not right after the marker return
    None. A missing render-digest still yields the message digest here;
    trusted-preview checks require :func:`_parse_render_digest` too.
    """
    if not comment_body:
        return None
    text = comment_body.replace("\r\n", "\n").replace("\r", "\n")
    prefix = DRYRUN_MARKER + "\n"
    if not text.startswith(prefix):
        return None
    line2, _sep, _tail = text[len(prefix):].partition("\n")
    m = DIGEST_LINE_RE.fullmatch(line2)
    return m.group(1) if m else None


def _parse_render_digest(comment_body):
    """sha256 of approved root+thread from a three-line preview header."""
    if not comment_body:
        return None
    text = comment_body.replace("\r\n", "\n").replace("\r", "\n")
    prefix = DRYRUN_MARKER + "\n"
    if not text.startswith(prefix):
        return None
    rest = text[len(prefix):]
    line2, sep2, after2 = rest.partition("\n")
    if not sep2 or not DIGEST_LINE_RE.fullmatch(line2):
        return None
    line3, _sep3, _tail = after2.partition("\n")
    m = RENDER_DIGEST_LINE_RE.fullmatch(line3)
    return m.group(1) if m else None


def _count_posted_mentions(text):
    nfkc = unicodedata.normalize("NFKC", text or "")
    url_spans = [(m.start(), m.end()) for m in _URL_RE.finditer(nfkc)]

    def in_url(pos):
        for lo, hi in url_spans:
            if lo <= pos < hi:
                return True
        return False

    return sum(
        1 for m in _POSTED_MENTION_RE.finditer(nfkc) if not in_url(m.start())
    )


def _assert_thread_mention_cap(root, thread):
    total = _count_posted_mentions(root) + sum(
        _count_posted_mentions(p) for p in (thread or [])
    )
    if total > MAX_REQUIRED_HANDLES:
        raise _RootTagsError(
            f"thread carries {total} mention(s) across root+replies "
            f"(cap {MAX_REQUIRED_HANDLES}); refusing"
        )


def _assert_postable_text(text):
    raw = text if text is not None else ""
    for ch in FULLWIDTH_AT:
        if ch in raw:
            raise _RootTagsError(
                f"full-width at-sign (U+{ord(ch):04X}) in postable text — "
                f"refusing (never emit full-width mentions)"
            )
    n = _count_posted_mentions(raw)
    if n > MAX_REQUIRED_HANDLES:
        raise _RootTagsError(
            f"postable text carries {n} mention(s) "
            f"(cap {MAX_REQUIRED_HANDLES}); refusing"
        )
    return raw


def _extract_handles(text):
    if not text:
        return []
    url_spans = [(m.start(), m.end()) for m in _URL_RE.finditer(text)]

    def in_url(pos):
        for lo, hi in url_spans:
            if lo <= pos < hi:
                return True
        return False

    out = []
    seen = set()
    for m in _HANDLE_SCAN_RE.finditer(text):
        if in_url(m.start()):
            continue
        tok = m.group(0)
        if not _HANDLE_RE.match(tok):
            continue
        key = tok.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tok)
    return out


def _extract_urls(text):
    if not text:
        return []
    out = []
    seen = set()
    for m in _URL_RE.finditer(text):
        u = m.group(0)
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _allowed_urls(body):
    return frozenset(
        _extract_urls(_message_root_paragraph(body))
        + _extract_urls(_message_link_value(body))
    )


def _assert_only_allowed_urls(text, allowed):
    raw = text if text is not None else ""
    allow = frozenset(allowed)
    bad = [u for u in _extract_urls(raw) if u not in allow]
    if bad:
        raise _RootTagsError(
            f"postable text carries URL(s) not in the approved ## Message "
            f"first paragraph or ## Link: {bad} — refusing"
        )
    return raw


def _required_handles(body):
    para = _message_root_paragraph(body)
    _assert_postable_text(para)
    handles = _extract_handles(para)
    if len(handles) > MAX_REQUIRED_HANDLES:
        raise _RootTagsError(
            f"## Message root declares {len(handles)} @handles "
            f"(cap {MAX_REQUIRED_HANDLES}); refusing"
        )
    return handles


def _missing_handles(text, required):
    present = {h.lower() for h in _extract_handles(text)}
    return [h for h in required if h.lower() not in present]


class _PreviewMigrationNeeded(_ApprovalGuardError):
    """LIVE should write a preview and remove approved-to-post, not post."""


def _parse_approver_allowlist(raw):
    if raw is None:
        return frozenset()
    return frozenset(p.strip() for p in raw.split(",") if p.strip())


def _parse_require_direct_human_label(raw):
    return (raw or "").strip() != "false"


def _approver_logins():
    return _parse_approver_allowlist(os.environ.get(APPROVER_LOGINS_ENV))


def _require_direct_human_label():
    return _parse_require_direct_human_label(
        os.environ.get(DIRECT_HUMAN_LABEL_ENV)
    )


def _event_label_name(ev):
    lbl = ev.get("label")
    return lbl.get("name", "") if isinstance(lbl, dict) else (lbl or "")


def _comment_user(comment):
    user = comment.get("user") or comment.get("author") or {}
    return user if isinstance(user, dict) else {}


def _is_trusted_preview_comment(comment):
    user = _comment_user(comment)
    if user.get("login") != TRUSTED_PREVIEW_LOGIN:
        return False
    if user.get("type") != TRUSTED_PREVIEW_TYPE:
        return False
    created = comment.get("created_at") or ""
    updated = comment.get("updated_at") or ""
    if not created or not updated or created != updated:
        return False
    body = comment.get("body") or ""
    return (
        _parse_message_digest(body) is not None
        and _parse_render_digest(body) is not None
    )


def _trusted_previews_after_edit(comments, last_edited_at):
    cutoff = None
    if last_edited_at is not None and str(last_edited_at).strip():
        cutoff = _parse_iso_ts(str(last_edited_at))
    out = []
    for comment in comments or []:
        if not _is_trusted_preview_comment(comment):
            continue
        try:
            created = _parse_iso_ts(comment.get("created_at") or "")
        except _ApprovalGuardError:
            continue
        if cutoff is not None and created <= cutoff:
            continue
        out.append(comment)
    return out


def _exactly_one_trusted_preview(comments, last_edited_at):
    found = _trusted_previews_after_edit(comments, last_edited_at)
    if len(found) == 0:
        raise _PreviewMigrationNeeded(
            "no trusted preview comment after the latest body edit — "
            "write a preview and remove approved-to-post (self-migrate)"
        )
    if len(found) > 1:
        raise _ApprovalGuardError(
            f"ambiguous: {len(found)} trusted preview comments after the "
            f"latest body edit — delete extras so exactly one remains; "
            f"refusing live post (fail closed)"
        )
    return found[0]


def _latest_labeled_event(events, label=APPROVAL_LABEL):
    latest = None
    latest_dt = None
    for ev in events or []:
        if (ev.get("event") or "").lower() != "labeled":
            continue
        if _event_label_name(ev) != label:
            continue
        created = ev.get("created_at") or ""
        try:
            dt = _parse_iso_ts(created)
        except _ApprovalGuardError:
            continue
        if latest_dt is None or dt > latest_dt:
            latest_dt = dt
            latest = ev
    return latest


def _latest_bot_removal_at(events, label=APPROVAL_LABEL):
    latest_dt = None
    for ev in events or []:
        if (ev.get("event") or "").lower() != "unlabeled":
            continue
        if _event_label_name(ev) != label:
            continue
        actor = ev.get("actor") or {}
        if not isinstance(actor, dict):
            continue
        if actor.get("login") != TRUSTED_PREVIEW_LOGIN:
            continue
        if actor.get("type") != TRUSTED_PREVIEW_TYPE:
            continue
        created = ev.get("created_at") or ""
        try:
            dt = _parse_iso_ts(created)
        except _ApprovalGuardError:
            continue
        if latest_dt is None or dt > latest_dt:
            latest_dt = dt
    return latest_dt


def _has_unlabeled_after(events, after, label=APPROVAL_LABEL):
    for ev in events or []:
        if (ev.get("event") or "").lower() != "unlabeled":
            continue
        if _event_label_name(ev) != label:
            continue
        created = ev.get("created_at") or ""
        try:
            dt = _parse_iso_ts(created)
        except _ApprovalGuardError:
            continue
        if dt > after:
            return True
    return False


def _latest_human_approval_at(events, preview_created_at, approver_logins,
                              require_direct_human_label=True):
    allow = frozenset(a for a in approver_logins if a)
    if not allow:
        raise _ApprovalGuardError(
            "GROWTH_APPROVER_LOGINS is empty — refusing live post (fail closed)"
        )
    preview_dt = _parse_iso_ts(preview_created_at)
    latest = _latest_labeled_event(events, APPROVAL_LABEL)
    if latest is None:
        raise _ApprovalGuardError(
            "no approved-to-post labeled timeline event — refusing live post "
            "(fail closed)"
        )
    created = latest.get("created_at") or ""
    try:
        labeled_dt = _parse_iso_ts(created)
    except _ApprovalGuardError as e:
        raise _ApprovalGuardError(
            "latest approved-to-post labeled event has an unreadable "
            "created_at — refusing live post (fail closed)"
        ) from e
    actor = latest.get("actor") or {}
    if not isinstance(actor, dict) or actor.get("type") != "User":
        raise _ApprovalGuardError(
            "latest approved-to-post label event is not by a User actor — "
            "refusing live post (fail closed)"
        )
    login = actor.get("login") or ""
    if login not in allow:
        raise _ApprovalGuardError(
            f"latest approved-to-post label event is by {login!r}, not an "
            f"allowlisted User — refusing live post (fail closed)"
        )
    if labeled_dt <= preview_dt:
        raise _ApprovalGuardError(
            "latest approved-to-post label event is not strictly after the "
            "trusted preview — a human must re-apply the label after the "
            "preview; refusing live post (fail closed)"
        )
    bot_removal = _latest_bot_removal_at(events, APPROVAL_LABEL)
    if bot_removal is not None and labeled_dt <= bot_removal:
        raise _ApprovalGuardError(
            "latest approved-to-post label event is not strictly after the "
            "bot's most recent removal of the label — a human must re-apply "
            "after the preview self-migrate; refusing live post (fail closed)"
        )
    if _has_unlabeled_after(events, labeled_dt, APPROVAL_LABEL):
        raise _ApprovalGuardError(
            "approved-to-post was unlabeled after the latest labeled event "
            "(stale or revoked approval) — refusing live post (fail closed)"
        )
    if require_direct_human_label:
        via_app = latest.get("performed_via_github_app")
        if via_app is not None:
            raise _ApprovalGuardError(
                "latest approved-to-post label was performed via a GitHub "
                "App (GROWTH_REQUIRE_DIRECT_HUMAN_LABEL) — refusing live "
                "post (fail closed)"
            )
    return created


def _assert_digest_binds(comments, body, last_edited_at=None):
    preview = _exactly_one_trusted_preview(comments, last_edited_at)
    digest = _parse_message_digest(preview.get("body") or "")
    if digest is None:
        raise _ApprovalGuardError(
            "trusted preview comment has an unreadable message-digest — "
            "refusing live post (fail closed)"
        )
    expected = _message_digest(body)
    if digest != expected:
        raise _ApprovalGuardError(
            f"digest mismatch without edit: trusted preview message-digest "
            f"{digest} does not match current ## Message + ## Link binding "
            f"({expected}) — refusing (fail closed); do not create a second "
            f"preview"
        )
    return digest, preview


def _assert_render_binds(preview, root, thread=None):
    dig = _parse_render_digest(preview.get("body") or "")
    if dig is None:
        raise _ApprovalGuardError(
            "trusted preview comment has an unreadable render-digest — "
            "refusing live post (fail closed)"
        )
    expected = _render_digest(root, thread)
    if dig != expected:
        raise _ApprovalGuardError(
            f"render-digest mismatch: live copy does not match the approved "
            f"preview (preview={dig}, live={expected}) — refusing (fail "
            f"closed); post the approved preview copy or re-preview"
        )
    return dig


def _assert_live_gates(comments, body, events, last_edited_at, approver_logins,
                       require_direct_human_label=True):
    digest, preview = _assert_digest_binds(
        comments, body, last_edited_at=last_edited_at
    )
    preview_created = preview.get("created_at") or ""
    if not preview_created:
        raise _ApprovalGuardError(
            "trusted preview is missing created_at — refusing (fail closed)"
        )
    approved_at = _latest_human_approval_at(
        events, preview_created, approver_logins,
        require_direct_human_label=require_direct_human_label,
    )
    _assert_body_fresh_for_live(approved_at, last_edited_at)
    return digest, approved_at, preview

def _latest_trusted_dryrun_digest(comments, last_edited_at=None):
    found = _trusted_previews_after_edit(comments, last_edited_at)
    if len(found) > 1:
        raise _ApprovalGuardError(
            f"ambiguous: {len(found)} trusted preview comments after the "
            f"latest body edit"
        )
    if not found:
        return None
    return _parse_message_digest(found[0].get("body") or "")


def _parse_iso_ts(ts):
    from datetime import datetime, timezone  # noqa: PLC0415 — local to keep top lean
    raw = (ts or "").strip()
    if not raw:
        raise _ApprovalGuardError("empty timestamp")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as e:
        raise _ApprovalGuardError(f"unparseable timestamp {ts!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _latest_labeled_at(events, label=APPROVAL_LABEL):
    latest = None
    latest_dt = None
    for ev in events or []:
        if (ev.get("event") or "").lower() != "labeled":
            continue
        lbl = ev.get("label")
        name = lbl.get("name", "") if isinstance(lbl, dict) else (lbl or "")
        if name != label:
            continue
        created = ev.get("created_at") or ""
        try:
            dt = _parse_iso_ts(created)
        except _ApprovalGuardError:
            continue
        if latest_dt is None or dt > latest_dt:
            latest_dt = dt
            latest = created
    return latest


def _body_edited_after_approval(approved_at, last_edited_at):
    if not (approved_at or "").strip():
        raise _ApprovalGuardError(
            "approved-to-post label time is missing — refusing to judge freshness"
        )
    approved = _parse_iso_ts(approved_at)
    if last_edited_at is None or not str(last_edited_at).strip():
        return False
    edited = _parse_iso_ts(str(last_edited_at))
    return edited > approved


def _assert_body_fresh_for_live(approved_at, last_edited_at):
    if approved_at is None or not str(approved_at).strip():
        raise _ApprovalGuardError(
            "could not find an approved-to-post labeled timeline event — "
            "refusing live post (fail closed)"
        )
    if _body_edited_after_approval(str(approved_at), last_edited_at):
        raise _ApprovalGuardError(
            f"issue body was edited after approved-to-post "
            f"(approved_at={approved_at}, last_edited_at={last_edited_at}) — "
            f"re-apply the approval label on the current body, or refuse"
        )


def _ensure_root_tags(text, required, drafted="", link=""):
    required = [h for h in required if _HANDLE_RE.match(h)] if required else []
    allow = frozenset(_extract_urls(drafted) + _extract_urls(link))

    def _finish(candidate):
        return _assert_only_allowed_urls(_assert_postable_text(candidate), allow)

    if not required:
        return _finish(text)
    if not _missing_handles(text, required):
        return _finish(text)
    drafted = (drafted or "").strip()
    if drafted and _tweet_weight(drafted) <= MAX_WEIGHT:
        _assert_postable_text(drafted)
        if not _missing_handles(drafted, required):
            # Re-attach ONLY the issue ## Link URL(s) — never model URLs.
            draft_urls = set(_extract_urls(drafted))
            missing_link_urls = [
                u for u in _extract_urls(link) if u not in draft_urls
            ]
            candidate = drafted
            use_drafted = True
            if missing_link_urls:
                url_suffix = " ".join(missing_link_urls)
                if candidate and not candidate[-1].isspace():
                    with_urls = f"{candidate.rstrip()} {url_suffix}"
                else:
                    with_urls = f"{candidate}{url_suffix}"
                if _tweet_weight(with_urls) <= MAX_WEIGHT:
                    candidate = with_urls
                else:
                    use_drafted = False
            if use_drafted:
                return _finish(candidate)
    missing = _missing_handles(text, required)
    if not missing:
        return _finish(text)
    suffix = " ".join(missing)
    if text and not text[-1].isspace():
        candidate = f"{text.rstrip()} {suffix}"
    else:
        candidate = f"{text}{suffix}" if text else suffix
    if _tweet_weight(candidate) <= MAX_WEIGHT:
        return _finish(candidate)
    raise _RootTagsError(
        f"root tweet is missing required handle(s) {missing} and neither the "
        f"drafted ## Message paragraph nor appending them fits within "
        f"{MAX_WEIGHT} weighted characters — refusing untagged post"
    )


# --- the walk-spanning post cap (issue #570) ---------------------------------
#
# Every link of a chain walk is its own claude-code-action step, so this
# server process — and anything in-process — restarts at link N+1. An
# in-process counter therefore caps ONE LINK, not the run: a link that posts
# up to the cap and then dies (agent error, step timeout) hands the next link
# a fresh counter with the same prompt, so a 3-link walk could post up to 3x
# the cap — and this is the one server whose writes can eventually publish
# OUTSIDE the repo, so a cap that lies about its own scope matters more here
# even with the one-post-per-item marker guards in place (#549 split 6). The
# count must live where every link can see it: a state file the workflow
# names via GROWTH_CAP_STATE, one path shared by every link step of the job
# (the reeve.yml REEVE_GREENLIGHT_STATE precedent). runner.temp is fresh per
# job, so the file is run-scoped and never persists across runs.
#
# SIBLING ADOPTION (scout_mcp.py's #565 note): the three functions below are
# lifted verbatim from its mechanism — deliberately self-contained, stdlib
# only — so adoption is a copy plus the CAP_STATE_ENV constant, not a
# re-derivation of the mechanism.
CAP_STATE_ENV = "GROWTH_CAP_STATE"


def _cap_state_path():
    """The shared state-file path for this run, or None attended.

    Attended (no GITHUB_RUN_ID) the cap is skipped entirely — a human is the
    trust boundary — so no state file is required. Unattended the path comes
    from the env var the workflow sets; an empty value is returned as-is so the
    caller can refuse: posting on without it would silently fall back to
    per-process counting, which is exactly the per-link reset this mechanism
    exists to kill.
    """
    if not os.environ.get("GITHUB_RUN_ID", "").strip():
        return None
    return os.environ.get(CAP_STATE_ENV, "").strip()


def _cap_state_iter(path):
    """Yield parsed records from the shared state file (empty if absent)."""
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except json.JSONDecodeError:
                    yield {"outcome": "__unparseable__", "issue": None}
                    continue
                if isinstance(rec, dict):
                    yield rec
                else:
                    yield {"outcome": "__unparseable__", "issue": None}
    except FileNotFoundError:
        return
    except OSError as e:
        raise RuntimeError(f"cannot read {CAP_STATE_ENV} file {path}: {e}") from e


def _cap_state_count(path):
    """How many post slots this run has already consumed.

    Counts JSON records whose ``outcome`` is a consuming one (live post,
    live attempt, dry-run). ``preview-migrate`` is audit-only and does
    **not** consume a slot — LIVE may preview-migrate many items, then
    still post up to ``GROWTH_MAX_POSTS``. An absent file is zero; any
    other read failure raises (fail closed).
    """
    n = 0
    for rec in _cap_state_iter(path):
        outcome = rec.get("outcome") or ""
        if outcome in _CAP_NON_CONSUMING_OUTCOMES:
            continue
        n += 1
    return n


def _cap_state_preview_count(path):
    """How many ``preview-migrate`` records this run has written."""
    return sum(
        1 for rec in _cap_state_iter(path)
        if (rec.get("outcome") or "") == "preview-migrate"
    )


def _cap_state_has_preview_migrate(path, number):
    """True iff this run already preview-migrated *number*."""
    for rec in _cap_state_iter(path):
        if (rec.get("outcome") or "") != "preview-migrate":
            continue
        if rec.get("issue") == number:
            return True
    return False


def _cap_state_record(path, number, url, outcome):
    """Append ONE record — audit trail + slot accounting."""
    rec = {"issue": number, "url": url, "outcome": outcome,
           "posted_at": datetime.now(timezone.utc).isoformat()}
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def _cap_state_note(state, number, url, outcome):
    """Record one outcome when a state file is in play (attended runs
    have none — the cap is skipped). A record that cannot be appended is a
    WARNING, never a refusal: the action already happened and refusing after
    the fact would strand the outcome."""
    if not state:
        return
    try:
        _cap_state_record(state, number, url, outcome)
    except OSError as e:
        log(f"WARNING: could not append {CAP_STATE_ENV} record for #{number} "
            f"outcome={outcome!r} ({e})")

# Captured by the selftest so it can assert exact payloads without a network
# call. `None`/empty in normal operation.
_last_comment = None
_last_close = None
_last_tweets = None
_last_deleted = None
_last_label_removed = None

# Fake state for the offline selftest (GROWTH_MCP_FAKE).
_FAKE_ISSUES = {}
_FAKE_COMMENTS = {}
_FAKE_EVENTS = {}          # issue number -> list of issue-event dicts
_FAKE_LAST_EDITED = {}     # issue number -> ISO timestamp or None
_fake_comment_seq = 0


def log(msg):
    """Diagnostics go to stderr — stdout is reserved for JSON-RPC frames."""
    print(f"growth_mcp: {msg}", file=sys.stderr, flush=True)


def _repo():
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY is not set")
    return repo


def _token():
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        tok = os.environ.get(var, "").strip()
        if tok:
            return tok
    raise RuntimeError("no GitHub token (set GITHUB_TOKEN)")


def _api(method, path, payload=None):
    """One authenticated GitHub REST call. Returns the decoded JSON body."""
    url = f"{GITHUB_API}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {_token()}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "print-bench-growth-twitter")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw else {}


def _get_issue(number):
    if os.environ.get("GROWTH_MCP_FAKE"):
        return _FAKE_ISSUES.get(number)
    return _api("GET", f"/repos/{_repo()}/issues/{number}")


def _paginate_rest_pages(fetch_page, *, what):
    """Walk ``fetch_page(page) -> list`` until a short page.

    Raises (fail closed) when a full page would require walking past
    :data:`MAX_LIST_PAGES`, or when a page body is not a list — never return
    a silently truncated prefix. Same contract as ``growth.github._paged``.
    """
    out = []
    page = 1
    while True:
        batch = fetch_page(page)
        if not isinstance(batch, list):
            raise RuntimeError(
                f"unexpected non-list response paging {what} "
                f"(got {type(batch).__name__}) — refusing truncated {what}"
            )
        if not batch:
            break
        out.extend(batch)
        if len(batch) < LIST_PER_PAGE:
            break
        page += 1
        if page > MAX_LIST_PAGES:
            raise RuntimeError(
                f"more than {MAX_LIST_PAGES} pages of {what} — refusing "
                f"truncated {what} (fail closed)"
            )
    return out


def _get_comments(number):
    if os.environ.get("GROWTH_MCP_FAKE"):
        if os.environ.get("GROWTH_MCP_FAKE_COMMENTS_PAGE_CAP"):
            # Exercise the real pager: endless full pages → raise.
            return _paginate_rest_pages(
                lambda _p: [{"id": i} for i in range(LIST_PER_PAGE)],
                what="issue comments",
            )
        return list(_FAKE_COMMENTS.get(number, []))
    # Walk EVERY page — the marker guard must see an early comment on a long
    # thread, or a duplicate slips through (the assessor's lesson). Cap hit
    # raises (fail closed); never return a truncated prefix.
    return _paginate_rest_pages(
        lambda page: _api(
            "GET",
            f"/repos/{_repo()}/issues/{number}/comments"
            f"?per_page={LIST_PER_PAGE}&page={page}",
        ),
        what="issue comments",
    )


def _get_issue_events(number):
    """Issue timeline events (labeled/unlabeled/…). Failures raise — the
    live post-approval body freeze must fail closed, not invent freshness.
    Page-cap / non-list responses raise rather than returning a truncated
    oldest-first prefix (newest revocations live in the dropped tail)."""
    if os.environ.get("GROWTH_MCP_FAKE"):
        if os.environ.get("GROWTH_MCP_FAKE_EVENTS_FAIL"):
            raise RuntimeError("selftest: simulated events failure")
        if os.environ.get("GROWTH_MCP_FAKE_EVENTS_PAGE_CAP"):
            return _paginate_rest_pages(
                lambda _p: [{"id": i} for i in range(LIST_PER_PAGE)],
                what="issue events",
            )
        return list(_FAKE_EVENTS.get(number, []))
    return _paginate_rest_pages(
        lambda page: _api(
            "GET",
            f"/repos/{_repo()}/issues/{number}/events"
            f"?per_page={LIST_PER_PAGE}&page={page}",
        ),
        what="issue events",
    )


def _get_body_last_edited_at(number):
    """GraphQL ``Issue.lastEditedAt`` (null when the body was never edited
    after creation). Raises on transport/shape failure — fail closed on live."""
    if os.environ.get("GROWTH_MCP_FAKE"):
        if os.environ.get("GROWTH_MCP_FAKE_EDITED_FAIL"):
            raise RuntimeError("selftest: simulated lastEditedAt failure")
        # Key missing → treat as "never edited" (None). Explicit None is fine.
        if number not in _FAKE_LAST_EDITED:
            return None
        return _FAKE_LAST_EDITED[number]
    owner, _, name = _repo().partition("/")
    if not owner or not name:
        raise RuntimeError(f"GITHUB_REPOSITORY is not owner/name: {_repo()!r}")
    query = (
        "query($owner:String!,$name:String!,$number:Int!){"
        "repository(owner:$owner,name:$name){"
        "issue(number:$number){ lastEditedAt }"
        "}}"
    )
    payload = json.dumps({
        "query": query,
        "variables": {"owner": owner, "name": name, "number": int(number)},
    }).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=payload,
                                 method="POST")
    req.add_header("Authorization", f"Bearer {_token()}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "print-bench-growth-twitter")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
    data = json.loads(raw) if raw else {}
    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors reading lastEditedAt: {data['errors']!r}")
    issue = (((data.get("data") or {}).get("repository") or {}).get("issue"))
    if issue is None:
        raise RuntimeError(f"GraphQL returned no issue #{number} for lastEditedAt")
    return issue.get("lastEditedAt")  # may be null


def _post_comment(number, body):
    global _last_comment, _fake_comment_seq
    if os.environ.get("GROWTH_MCP_FAKE"):
        if os.environ.get("GROWTH_MCP_FAKE_COMMENT_FAIL"):
            raise RuntimeError("selftest: simulated comment failure")
        _fake_comment_seq += 1
        cid = _fake_comment_seq
        _last_comment = {"number": number, "body": body}
        # Workflow GITHUB_TOKEN comments land as github-actions[bot] — the
        # LIVE digest gate trusts only that identity (not look-alikes).
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _FAKE_COMMENTS.setdefault(number, []).append({
            "id": cid,
            "body": body,
            "user": {"login": TRUSTED_PREVIEW_LOGIN, "type": TRUSTED_PREVIEW_TYPE},
            "created_at": now,
            "updated_at": now,
        })
        return {"html_url": f"https://example.invalid/{number}#comment", "id": cid}
    _last_comment = {"number": number, "body": body}
    return _api("POST", f"/repos/{_repo()}/issues/{number}/comments", {"body": body})


def _delete_comment(comment_id):
    """Withdraw a comment we posted. Used to remove a claim marker when a live
    post never reached the channel, so the item is retryable without a human
    hand-deleting the marker. The one destructive GitHub write — reached ONLY
    for our own claim comment, ONLY when nothing was published (a first-tweet
    failure), so it can never erase the record of a tweet that did go out."""
    global _last_deleted
    _last_deleted = comment_id
    if os.environ.get("GROWTH_MCP_FAKE"):
        for lst in _FAKE_COMMENTS.values():
            lst[:] = [c for c in lst if c.get("id") != comment_id]
        return {}
    return _api("DELETE", f"/repos/{_repo()}/issues/comments/{comment_id}")


def _remove_approval_label(number):
    """REMOVE ``approved-to-post`` only — never adds any label, never touches
    any other label. Used by the LIVE self-migrate path after writing a
    preview so a human must re-apply approval on the current body."""
    global _last_label_removed
    _last_label_removed = {"number": number, "label": APPROVAL_LABEL}
    if os.environ.get("GROWTH_MCP_FAKE"):
        if os.environ.get("GROWTH_MCP_FAKE_LABEL_REMOVE_FAIL"):
            raise RuntimeError("selftest: simulated label-removal failure")
        issue = _FAKE_ISSUES.get(number) or {}
        labels = issue.get("labels") or []
        issue["labels"] = [
            lbl for lbl in labels
            if (lbl.get("name") if isinstance(lbl, dict) else lbl) != APPROVAL_LABEL
        ]
        return {}
    # DELETE .../labels/{name} — URL-encode the label name.
    from urllib.parse import quote
    return _api(
        "DELETE",
        f"/repos/{_repo()}/issues/{number}/labels/{quote(APPROVAL_LABEL, safe='')}",
    )


def _close_issue(number):
    """Close a DRAINED queue item (live post delivered). The one non-comment
    GitHub write, hardcoded to close-as-completed — never a label."""
    global _last_close
    _last_close = number
    if os.environ.get("GROWTH_MCP_FAKE"):
        return {}
    return _api("PATCH", f"/repos/{_repo()}/issues/{number}",
                {"state": "closed", "state_reason": "completed"})


def _x_post(text, reply_to=None):
    """One live tweet, via the tested OAuth seam in tools/growth (this same
    checkout — see the header). Reached ONLY in live mode."""
    global _last_tweets
    if _last_tweets is None:
        _last_tweets = []
    if os.environ.get("GROWTH_MCP_FAKE"):
        if os.environ.get("GROWTH_MCP_FAKE_X_FAIL"):
            raise RuntimeError("selftest: simulated X API failure")
        # Fail on a THREAD PART (after the first tweet is already live) to
        # exercise the mid-thread branch, which must keep the claim marker.
        if os.environ.get("GROWTH_MCP_FAKE_X_FAIL_PART") and reply_to is not None:
            raise RuntimeError("selftest: simulated X API failure on a thread part")
        _last_tweets.append({"text": text, "reply_to": reply_to})
        return f"fake-tweet-{len(_last_tweets)}"
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root / "tools" / "growth" / "src"))
    from growth.poster import post_tweet as poster_post_tweet  # noqa: PLC0415
    return poster_post_tweet(text, reply_to=reply_to)


def _selected_issues():
    """The trusted workflow Select step exports GROWTH_SELECTED_ISSUES (space-
    or comma-separated digits) — the run's candidate set. Returns a set, or
    None when unset (attended: a human is the trust boundary, no binding)."""
    raw = os.environ.get("GROWTH_SELECTED_ISSUES", "").strip()
    if not raw:
        return None
    nums = set()
    for tok in raw.replace(",", " ").split():
        if tok.isdigit():
            nums.add(int(tok))
    return nums


def _label_names(issue):
    out = []
    for lbl in (issue.get("labels") or []):
        out.append(lbl.get("name", "") if isinstance(lbl, dict) else str(lbl))
    return out


def _x_credentials_present():
    return all(
        (os.environ.get(v) or "").strip()
        for v in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
    )


def _live_mode():
    """Live iff the human live key says so AND the channel credentials exist.
    Everything else — including 'keys arrived but nobody flipped the
    variable' — is a dry run. The variable is a repo variable exported by the
    workflow; no agent can set it."""
    return (
        os.environ.get("GROWTH_TWITTER_LIVE", "").strip() == "true"
        and _x_credentials_present()
    )


def _require_approval():
    """The committed policy's require_approval, surfaced by the workflow as
    GROWTH_REQUIRE_APPROVAL. Fail-safe: anything but the literal 'false'
    means approval is required."""
    return os.environ.get("GROWTH_REQUIRE_APPROVAL", "true").strip() != "false"


def _render_parts(text, thread):
    parts = [text] + list(thread)
    lines = []
    for i, part in enumerate(parts, start=1):
        prefix = f"**{i}/{len(parts)}**\n" if len(parts) > 1 else ""
        quoted = "> " + part.replace("\n", "\n> ")
        lines.append(f"{prefix}{quoted}\n({_tweet_weight(part)}/{MAX_WEIGHT} weighted)")
    return "\n\n".join(lines)


def _post_tweet(arguments):
    """Drain ONE queue item to the channel — dry-run comment by default, a
    live tweet only behind the live key + approval label. Lark's entire
    write taxonomy."""
    args = arguments or {}
    number = args.get("number")
    text = args.get("text")
    thread = args.get("thread") or []

    # --- input shape -------------------------------------------------------
    if isinstance(number, bool):
        return _tool_error("post_tweet: 'number' must be an integer issue number")
    if isinstance(number, str):
        if not number.strip().isdigit():
            return _tool_error(
                f"post_tweet: 'number' must be a positive integer (got {number!r})")
        number = int(number.strip())
    if not isinstance(number, int) or number <= 0:
        return _tool_error("post_tweet: 'number' is required (positive integer)")
    if not isinstance(text, str) or not text.strip():
        return _tool_error("post_tweet: 'text' is required (non-empty string)")
    if not isinstance(thread, list) or any(
            not isinstance(p, str) or not p.strip() for p in thread):
        return _tool_error("post_tweet: 'thread' must be a list of non-empty strings")
    if len(thread) > MAX_THREAD_PARTS:
        return _tool_error(
            f"post_tweet: a thread carries at most {MAX_THREAD_PARTS} follow-ups "
            f"(got {len(thread)}) — one idea per post; condense")

    # --- weighted length, every part ---------------------------------------
    for i, part in enumerate([text, *thread]):
        w = _tweet_weight(part)
        if w > MAX_WEIGHT:
            where = "text" if i == 0 else f"thread[{i - 1}]"
            return _tool_error(
                f"post_tweet: {where} is {w} weighted (cap {MAX_WEIGHT}; URLs "
                f"count 23, wide code points 2) — shorten it")

    # --- candidate-set binding (trusted Select step) -----------------------
    selected = _selected_issues()
    if selected is not None and number not in selected:
        return _tool_error(
            f"issue #{number} is not in this run's candidate set {sorted(selected)}; refusing")

    # Cap-state path is resolved early so self-migrate can audit without
    # consuming a slot; the consuming check itself runs AFTER live gates
    # (so preview-migrate never hits the post cap).
    state = _cap_state_path()
    if state is not None and not state:
        return _tool_error(
            f"post_tweet: {CAP_STATE_ENV} is not set but this is an "
            "unattended run (GITHUB_RUN_ID is set) — the workflow must "
            "give every link step the same state-file path (the reeve.yml "
            "REEVE_GREENLIGHT_STATE pattern) or the post cap cannot span "
            "the chain walk; refusing to post"
        )

    # --- re-read the target and enforce state at WRITE time ----------------
    try:
        issue = _get_issue(number)
    except urllib.error.HTTPError as e:
        return _tool_error(f"GitHub API error {e.code} reading issue #{number}")
    except Exception as e:  # noqa: BLE001 — surface any failure to the agent
        return _tool_error(f"failed to read issue #{number}: {type(e).__name__}: {e}")
    if not issue:
        return _tool_error(f"issue #{number} not found")
    if "pull_request" in issue:
        return _tool_error(f"#{number} is a pull request, not a queue item; refusing")
    if issue.get("state") != "open":
        return _tool_error(f"issue #{number} is not open (state={issue.get('state')!r}); refusing")
    labels = _label_names(issue)
    if QUEUE_LABEL not in labels:
        return _tool_error(f"issue #{number} does not carry the '{QUEUE_LABEL}' label; refusing")
    if CHANNEL_LABEL not in labels:
        return _tool_error(
            f"issue #{number} is not this channel's ('{CHANNEL_LABEL}' label missing); refusing")
    if PARKED_LABEL in labels:
        return _tool_error(
            f"issue #{number} is parked for a human ('{PARKED_LABEL}'); refusing")

    live = _live_mode()

    # --- approval gate (live only) -----------------------------------------
    if live and _require_approval() and APPROVAL_LABEL not in labels:
        return _tool_error(
            f"issue #{number} lacks the '{APPROVAL_LABEL}' label — a human "
            f"approves each live post (the dry-run comment is there to "
            f"review); refusing the live post")

    # --- marker guards — one post per queue item, ever ---------------------
    try:
        comments = _get_comments(number)
    except Exception as e:  # noqa: BLE001
        return _tool_error(f"failed to read comments on #{number}: {type(e).__name__}: {e}")
    bodies = [(c.get("body") or "") for c in comments]
    if any(POSTED_MARKER in b for b in bodies):
        return _tool_error(f"issue #{number} was already posted live; refusing a duplicate")
    if not live and any(DRYRUN_MARKER in b for b in bodies):
        return _tool_error(
            f"issue #{number} already carries a dry-run comment; refusing a "
            f"duplicate (a later approved LIVE post is still allowed)")

    # --- root @-tags + allowed URLs (deterministic; body is UNTRUSTED) ----
    # Extract handles only — never treat issue text as instructions. Restore
    # any the agent dropped into the ROOT tweet (never a thread reply), or
    # refuse rather than post untagged. Drafted-restore re-attaches ONLY the
    # issue ## Link URL. Any other URL in root/thread that is not in the
    # ## Message first paragraph or ## Link is refused. Mention cap is
    # across the WHOLE thread (root + replies).
    issue_body = issue.get("body") or ""
    drafted_root = _message_root_paragraph(issue_body)
    issue_link = _message_link_value(issue_body)
    allow_urls = _allowed_urls(issue_body)
    try:
        required = _required_handles(issue_body)
        text = _ensure_root_tags(
            text, required, drafted=drafted_root, link=issue_link
        )
        for part in thread:
            _assert_postable_text(part)
            _assert_only_allowed_urls(part, allow_urls)
        _assert_thread_mention_cap(text, thread)
    except _RootTagsError as e:
        return _tool_error(f"post_tweet: {e}")
    root_w = _tweet_weight(text)
    if root_w > MAX_WEIGHT:
        return _tool_error(
            f"post_tweet: text is {root_w} weighted after root-tag restoration "
            f"(cap {MAX_WEIGHT}) — shorten the root or the drafted ## Message "
            f"paragraph")

    # --- LIVE gates / self-migrate / dry-run freeze notes -------------------
    # LIVE posts only when: exactly one trusted preview after lastEditedAt
    # (marker + message-digest + render-digest), message-digest matches,
    # render-digest matches the postable root+thread, the latest
    # approved-to-post labeled event overall is an allowlisted User
    # (optionally direct, not via GitHub App) strictly after that preview
    # AND after the bot's most recent label removal, with no unlabeled
    # after it, and the body freeze passes. Missing preview → write
    # preview (both digests + the exact copy) + REMOVE approved-to-post
    # only + do not post; does not consume the run's post slot or the
    # daycap. Digest mismatch on an existing trusted preview → refuse
    # (do not write a second preview).
    approval_notes = []
    events = None
    last_edited = None
    need_live_gates = live and (_require_approval() or APPROVAL_LABEL in labels)
    report_freeze = (not live) and APPROVAL_LABEL in labels
    if need_live_gates or report_freeze:
        try:
            events = _get_issue_events(number)
            last_edited = _get_body_last_edited_at(number)
        except Exception as e:  # noqa: BLE001
            if live:
                return _tool_error(
                    f"post_tweet: could not read approval timeline / body "
                    f"lastEditedAt for #{number} ({type(e).__name__}: {e}) — "
                    f"refusing live post (fail closed)"
                )
            approval_notes.append(
                f"could not read approval timeline / body lastEditedAt "
                f"({type(e).__name__}: {e}); a LIVE post would refuse"
            )
            events = None
            last_edited = None
        if (not live) and events is not None:
            approved_at = _latest_labeled_at(events, APPROVAL_LABEL)
            try:
                if approved_at is None:
                    approval_notes.append(
                        "approved-to-post is present but no labeled "
                        "timeline event was found; a LIVE post would refuse"
                    )
                elif _body_edited_after_approval(approved_at, last_edited):
                    approval_notes.append(
                        f"issue body was edited after approved-to-post "
                        f"(approved_at={approved_at}, "
                        f"last_edited_at={last_edited}); re-apply the "
                        f"label before a LIVE post"
                    )
            except _ApprovalGuardError as e:
                approval_notes.append(f"{e}; a LIVE post would refuse")

    rendered = _render_parts(text, thread)
    digest_header = _preview_digest_header(issue_body, text, thread)

    if need_live_gates:
        try:
            _digest, _approved_at, preview_comment = _assert_live_gates(
                comments,
                issue.get("body") or "",
                events or [],
                last_edited,
                _approver_logins(),
                require_direct_human_label=_require_direct_human_label(),
            )
            _assert_render_binds(preview_comment, text, thread)
        except _PreviewMigrationNeeded as e:
            # Self-migrate: write preview (marker + message-digest +
            # render-digest of the exact copy under the gates), REMOVE
            # approved-to-post only, do not post, no post-slot / daycap
            # burn. Bounded by MAX_PREVIEWS_PER_RUN.
            if state is not None:
                try:
                    n_previews = _cap_state_preview_count(state)
                except RuntimeError as err:
                    return _tool_error(f"post_tweet: {err}")
                if n_previews >= MAX_PREVIEWS_PER_RUN:
                    return _tool_error(
                        f"post_tweet: per-run preview-migrate cap reached "
                        f"({n_previews}/{MAX_PREVIEWS_PER_RUN}); refusing "
                        f"further self-migrates this run"
                    )
            preview = (
                f"{digest_header}{PREVIEW_HEADER}\n\n"
                f"{rendered}\n\n"
                f"**Preview (self-migrate)** — nothing was published. "
                f"The message-digest binds the `## Message` first paragraph "
                f"and `## Link`; the render-digest binds this exact root + "
                f"thread — a later LIVE post must match it (issue #1023). "
                f"Re-apply `{APPROVAL_LABEL}` after reviewing. ({e})\n\n"
                f"{FOOTER}"
            )
            try:
                posted = _post_comment(number, preview)
            except Exception as err:  # noqa: BLE001
                return _tool_error(
                    f"post_tweet: could not write preview on #{number} "
                    f"({type(err).__name__}: {err}) — refusing (fail closed); "
                    f"nothing was published"
                )
            try:
                _remove_approval_label(number)
            except Exception as err:  # noqa: BLE001
                log(f"label removal failed on #{number}: {type(err).__name__}: {err}")
                return _tool_error(
                    f"post_tweet: preview written on #{number} but removing "
                    f"'{APPROVAL_LABEL}' failed ({type(err).__name__}: {err}) — "
                    f"refusing to post (fail closed); remove the label by hand"
                )
            url = (posted or {}).get("html_url", "(unknown url)")
            _cap_state_note(state, number, url, "preview-migrate")
            log(f"self-migrated preview on #{number} {url} (label removed)")
            return _tool_text(
                f"PREVIEW self-migrated on #{number} {url} — "
                f"re-apply {APPROVAL_LABEL} to post"
            )
        except _ApprovalGuardError as e:
            return _tool_error(f"post_tweet: {e}")

    # --- per-run post cap (after gates; preview-migrate never reaches here) -
    # Enforced only inside an Actions run; attended, a human is the trust
    # boundary. The count spans the chain walk via GROWTH_CAP_STATE.
    # Never preview-migrate and post the same item in one run.
    if state is not None:
        try:
            if _cap_state_has_preview_migrate(state, number):
                return _tool_error(
                    f"post_tweet: issue #{number} was preview-migrated earlier "
                    f"in this run — refusing to post it in the same run; "
                    f"re-apply {APPROVAL_LABEL} and wait for a later firing"
                )
            posted = _cap_state_count(state)
        except RuntimeError as e:
            return _tool_error(f"post_tweet: {e}")
        try:
            cap = int(os.environ.get("GROWTH_MAX_POSTS", "1"))
        except ValueError:
            cap = 1
        if posted >= cap:
            return _tool_error(
                f"per-run post cap reached ({posted}/{cap} posted across the "
                "chain walk so far); refusing to post more")

    # --- act ----------------------------------------------------------------
    if live:
        # CLAIM FIRST, POST SECOND. The posted marker is the only cross-run
        # dedup signal, so it must exist even if this run dies mid-post: a
        # claim written before the first tweet turns every partial failure
        # into at-worst a LOST post a human retries deliberately — never a
        # DUPLICATE on a public channel. (If the claim itself cannot be
        # written, nothing has been published yet, so refusing is free.)
        claim = (
            f"{POSTED_MARKER}\n{POSTED_HEADER}\n\n_Live posting in flight — if no"
            f" tweet URL follows in a later comment, verify on the channel"
            f" before re-queuing; this item will not be posted again._\n\n"
            f"{rendered}\n\n{FOOTER}"
        )
        try:
            claim_resp = _post_comment(number, claim)
        except Exception as e:  # noqa: BLE001
            return _tool_error(
                f"could not claim #{number} before posting "
                f"({type(e).__name__}: {e}) — nothing was published; retry next run")
        claim_id = (claim_resp or {}).get("id")
        posted_any = False
        try:
            first_id = _x_post(text)
            posted_any = True
            last_id = first_id
            for part in thread:
                last_id = _x_post(part, reply_to=last_id)
        except Exception as e:  # noqa: BLE001
            _cap_state_note(state, number, None, "live-attempt-failed")
            reason = f"{type(e).__name__}: {e}"
            if not posted_any:
                # The FIRST tweet never went out, so NOTHING was published — the
                # claim is a false alarm. Withdraw it so the item is retryable
                # once the cause is fixed (e.g. X API credits), and record the
                # real reason on the item instead of a silent "verify by hand".
                # (A later thread-part failure is the opposite case below: a
                # tweet IS live, so the claim must stand.)
                withdrawn = False
                if claim_id:
                    try:
                        _delete_comment(claim_id)
                        withdrawn = True
                    except Exception:  # noqa: BLE001
                        pass
                retry = ("The claim was withdrawn, so re-running the routine will "
                         "retry this item." if withdrawn else
                         "Delete the claim comment above to retry.")
                try:
                    _post_comment(
                        number,
                        f"{FAILURE_HEADER}\n\nThe live post to Twitter/X was rejected "
                        f"before anything was published:\n\n> {reason}\n\n"
                        f"Nothing reached the channel. {retry}\n\n{FOOTER}")
                except Exception:  # noqa: BLE001
                    pass
                return _tool_error(
                    f"live post for #{number} was rejected before publishing ({reason}); "
                    + ("claim withdrawn — the item is retryable" if withdrawn
                       else "claim left in place — clear it to retry"))
            # A tweet DID go out but a later thread part failed: the item is live
            # and must stay claim-marked so no run double-posts it.
            try:
                _post_comment(
                    number,
                    f"{FAILURE_HEADER}\n\nThe first tweet posted but a later part of "
                    f"the thread failed:\n\n> {reason}\n\nVerify the thread on the "
                    f"channel; this item stays claimed and will not be reposted.\n\n{FOOTER}")
            except Exception:  # noqa: BLE001
                pass
            return _tool_error(
                f"live post for #{number} failed mid-thread ({reason}) — the item is "
                f"claim-marked and will not be retried automatically; verify by hand")
        tweet_url = f"https://x.com/i/web/status/{first_id}"
        comment = f"{POSTED_HEADER}\n\n{tweet_url}\n\nQueue item drained — closing.\n\n{FOOTER}"
        try:
            _post_comment(number, comment)
            _close_issue(number)
        except Exception as e:  # noqa: BLE001
            # The tweet is out and the claim marker already guards against a
            # re-post; surface the bookkeeping failure loudly.
            _cap_state_note(state, number, tweet_url, "posted-recording-failed")
            return _tool_error(
                f"tweet posted ({tweet_url}) but recording it on #{number} "
                f"failed: {type(e).__name__}: {e} — close the item by hand")
        _cap_state_note(state, number, tweet_url, "posted-live")
        log(f"posted live for #{number}: {tweet_url}")
        return _tool_text(f"POSTED live for #{number} {tweet_url} (queue item closed)")

    reasons = []
    if os.environ.get("GROWTH_TWITTER_LIVE", "").strip() != "true":
        reasons.append("the `GROWTH_TWITTER_LIVE` repo variable is not 'true'")
    if not _x_credentials_present():
        reasons.append("the X credentials are not configured")
    if _require_approval() and APPROVAL_LABEL not in labels:
        reasons.append(f"the `{APPROVAL_LABEL}` label is not applied")
    note_block = ""
    if approval_notes:
        note_block = (
            "\n\n**Approval freshness:** "
            + "; ".join(approval_notes)
            + "."
        )
    comment = (
        f"{digest_header}{DRYRUN_HEADER}\n\n{rendered}\n\n"
        f"**Dry run** — nothing was published. Going live needs: "
        f"{'; '.join(reasons) if reasons else 'nothing further'}. "
        f"The render-digest binds this exact copy; a LIVE post must match "
        f"it (issue #1023). See docs/growth.md."
        f"{note_block}\n\n{FOOTER}"
    )
    try:
        posted = _post_comment(number, comment)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500] if hasattr(e, "read") else ""
        return _tool_error(f"GitHub API error {e.code} commenting on #{number}: {detail}")
    except Exception as e:  # noqa: BLE001
        return _tool_error(f"failed to comment on #{number}: {type(e).__name__}: {e}")
    url = posted.get("html_url", "(unknown url)")
    _cap_state_note(state, number, url, "dry-run")
    log(f"dry-ran #{number} {url}")
    return _tool_text(f"DRY-RUN recorded on #{number} {url}")


# --- MCP tool registry ------------------------------------------------------

TOOLS = [
    {
        "name": "post_tweet",
        "description": (
            "Drain ONE growth-queue item to Twitter/X. Pass the queue issue "
            "'number', the tweet 'text', and optionally 'thread' (up to 4 "
            "follow-up tweets). Copy is metered with the weighted rule (URLs "
            "= 23, cap 280). By default this is a DRY RUN: the would-be tweet "
            "is recorded as a comment on the queue issue for a human to "
            "review — that comment is the deliverable. A LIVE post happens "
            "only when the human live key and X credentials are configured "
            "AND (per policy) the issue carries the approved-to-post label; "
            "after a live post the drained issue is closed. The tool re-reads "
            "the target and refuses anything that is not an open, "
            "twitter-channel queue item; one post per item, ever. A refusal "
            "is final — fix what it names or move on, never retry unchanged."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "number": {
                    "type": "integer",
                    "description": "The growth-queue issue number being drained.",
                },
                "text": {
                    "type": "string",
                    "description": "The tweet (weighted length ≤ 280; compose to ≤ 270).",
                },
                "thread": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional follow-up tweets (max 4), posted as replies.",
                },
            },
            "required": ["number", "text"],
            "additionalProperties": False,
        },
    }
]

_DISPATCH = {"post_tweet": _post_tweet}


def _tool_text(text):
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _tool_error(text):
    log(text)
    return {"content": [{"type": "text", "text": f"Error: {text}"}], "isError": True}


# --- JSON-RPC over stdio (newline-delimited) --------------------------------

def _result(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def handle(msg):
    """Map one JSON-RPC request to a response dict, or None for notifications."""
    method = msg.get("method")
    msg_id = msg.get("id")

    if msg_id is None and "id" not in msg:
        # Notifications (no id) get no response.
        return None

    if method == "initialize":
        params = msg.get("params") or {}
        version = params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION
        return _result(
            msg_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": "1.0.0"},
            },
        )

    if method == "ping":
        return _result(msg_id, {})

    if method == "tools/list":
        return _result(msg_id, {"tools": TOOLS})

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        fn = _DISPATCH.get(name)
        if fn is None:
            return _result(msg_id, _tool_error(f"unknown tool: {name!r}"))
        return _result(msg_id, fn(params.get("arguments") or {}))

    return _error(msg_id, -32601, f"method not found: {method}")


def selftest():
    """Prove the write surface's security invariants fire, offline. A guard
    that is never exercised can be weakened and every other check stays green
    (the repo's standing rule) — and THIS surface can reach outside the repo,
    so these are the cases that must never regress."""
    global _last_comment, _last_close, _last_tweets, _last_deleted
    global _last_label_removed
    global _FAKE_ISSUES, _FAKE_COMMENTS
    os.environ["GROWTH_MCP_FAKE"] = "1"
    # Pin the environment: each case below decides attended/unattended
    # itself, so an ambient Actions GITHUB_RUN_ID / GROWTH_CAP_STATE (this
    # selftest runs inside CI) must not leak into the attended cases.
    for var in ("GROWTH_SELECTED_ISSUES", "GITHUB_RUN_ID", "GROWTH_TWITTER_LIVE",
                "GROWTH_REQUIRE_APPROVAL", "GROWTH_MAX_POSTS", CAP_STATE_ENV,
                APPROVER_LOGINS_ENV, DIRECT_HUMAN_LABEL_ENV,
                "X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        os.environ.pop(var, None)
    os.environ[APPROVER_LOGINS_ENV] = "shaiss"
    fails = []

    def check(name, cond):
        print(f"{'ok  ' if cond else 'FAIL'}  {name}")
        if not cond:
            fails.append(name)

    def err(res):
        return res.get("isError") is True

    def q(number, labels, state="open", pr=False):
        issue = {"number": number, "state": state,
                 "labels": [{"name": n} for n in labels]}
        if pr:
            issue["pull_request"] = {"url": "x"}
        return issue

    OK = [QUEUE_LABEL, CHANNEL_LABEL]
    PREVIEW_AT = "2026-01-01T10:00:00Z"
    APPROVE_AT = "2026-01-01T12:00:00Z"  # strictly after preview

    def _seed_trusted_preview(number, body="", root="", thread=None,
                              created_at=PREVIEW_AT, updated_at=None,
                              login=TRUSTED_PREVIEW_LOGIN,
                              utype=TRUSTED_PREVIEW_TYPE):
        """A workflow-bot preview whose digests match *body* and *root*+*thread*."""
        header = _preview_digest_header(body, root, thread)
        if updated_at is None:
            updated_at = created_at
        _FAKE_COMMENTS[number] = [{
            "body": f"{header}dry-ran earlier",
            "user": {"login": login, "type": utype},
            "created_at": created_at,
            "updated_at": updated_at,
        }]

    def _approve(number, at=APPROVE_AT, login="shaiss", utype="User",
                 via_app=None, events=None):
        if events is not None:
            _FAKE_EVENTS[number] = list(events)
        else:
            ev = {
                "event": "labeled",
                "label": {"name": APPROVAL_LABEL},
                "created_at": at,
                "actor": {"login": login, "type": utype},
            }
            if via_app is not None:
                ev["performed_via_github_app"] = via_app
            _FAKE_EVENTS[number] = [ev]
        _FAKE_LAST_EDITED.pop(number, None)

    def _ready_live(number, body="", root="", thread=None):
        """Trusted preview + allowlisted human approval after it."""
        _seed_trusted_preview(number, body=body, root=root, thread=thread)
        _approve(number)

    _FAKE_ISSUES = {
        1: q(1, OK),
        2: q(2, OK, state="closed"),
        3: q(3, [CHANNEL_LABEL]),
        4: q(4, [QUEUE_LABEL]),
        5: q(5, OK + [PARKED_LABEL]),
        6: q(6, OK, pr=True),
        7: q(7, OK),
        8: q(8, OK),
        9: q(9, OK),
        10: q(10, OK + [APPROVAL_LABEL]),
        11: q(11, OK),
        12: q(12, OK + [APPROVAL_LABEL]),
    }
    _FAKE_COMMENTS = {
        7: [{"body": f"{POSTED_MARKER}\nposted earlier"}],
        8: [{"body": f"{DRYRUN_MARKER}\ndry-ran earlier"}],
    }
    _FAKE_EVENTS.clear()
    _FAKE_LAST_EDITED.clear()
    for n in (10, 12):
        _approve(n)
    _ready_live(12, root="approved and live", thread=["part two"])

    # Input guards.
    check("missing number is rejected", err(_post_tweet({"text": "x"})))
    check("a boolean number is rejected (bool is an int subclass)",
          err(_post_tweet({"number": True, "text": "x"})))
    check("a non-numeric number is rejected",
          err(_post_tweet({"number": "abc", "text": "x"})))
    check("missing text is rejected", err(_post_tweet({"number": 1})))
    check("a non-list thread is rejected",
          err(_post_tweet({"number": 1, "text": "x", "thread": "y"})))
    check("an empty thread part is rejected",
          err(_post_tweet({"number": 1, "text": "x", "thread": ["ok", "  "]})))
    check("a thread over 4 parts is rejected",
          err(_post_tweet({"number": 1, "text": "x", "thread": list("abcde")})))

    # Weighted length — URLs count 23, so a 2000-char URL passes and 281
    # plain chars fail; the guard covers thread parts too.
    check("281 plain chars are rejected",
          err(_post_tweet({"number": 1, "text": "x" * 281})))
    long_url = "https://example.com/" + "p" * 2000
    _FAKE_ISSUES[1]["body"] = f"## Message\n\nok\n\n## Link\n\n{long_url}\n"
    r = _post_tweet({"number": 1, "text": f"ok {long_url}"})
    check("a long URL weighs 23 and passes", r.get("isError") is False)
    _FAKE_COMMENTS.pop(1, None)  # reset the dry-run marker that call left
    _FAKE_ISSUES[1]["body"] = ""
    check("an over-weight thread part is rejected",
          err(_post_tweet({"number": 1, "text": "ok", "thread": ["y" * 281]})))

    # Dry-run is the default: no live key, no creds → the comment carries the
    # dry-run marker, the header, the footer, and the issue is NOT closed.
    _last_comment, _last_close = None, None
    r = _post_tweet({"number": 9, "text": "hello bench",
                     "thread": ["second part"]})
    check("default mode is dry-run", r.get("isError") is False
          and "DRY-RUN" in r["content"][0]["text"])
    check("the dry-run comment carries the marker",
          _last_comment and _last_comment["body"].startswith(DRYRUN_MARKER))
    check("the dry-run comment carries a message-digest of ## Message",
          _last_comment and _parse_message_digest(_last_comment["body"])
          == _message_digest(""))
    check("the dry-run comment carries a render-digest of root+thread",
          _last_comment and _parse_render_digest(_last_comment["body"])
          == _render_digest("hello bench", ["second part"]))
    check("the dry-run comment carries the attribution footer",
          _last_comment and _last_comment["body"].endswith(FOOTER))
    check("the dry-run comment renders the thread part",
          _last_comment and "second part" in _last_comment["body"])
    check("a dry run never closes the queue item", _last_close is None)

    # State guards at write time.
    check("a closed issue is rejected", err(_post_tweet({"number": 2, "text": "x"})))
    check("a missing growth-queue label is rejected",
          err(_post_tweet({"number": 3, "text": "x"})))
    check("a missing channel:twitter label is rejected",
          err(_post_tweet({"number": 4, "text": "x"})))
    check("a needs-decision item is rejected", err(_post_tweet({"number": 5, "text": "x"})))
    check("a pull request is rejected", err(_post_tweet({"number": 6, "text": "x"})))

    # Marker guards.
    check("an already-posted item is refused",
          err(_post_tweet({"number": 7, "text": "x"})))
    check("a second dry-run on the same item is refused",
          err(_post_tweet({"number": 8, "text": "x"})))

    # Candidate binding.
    os.environ["GROWTH_SELECTED_ISSUES"] = "1"
    check("a number outside the run's candidate set is rejected",
          err(_post_tweet({"number": 9, "text": "x"})))
    os.environ.pop("GROWTH_SELECTED_ISSUES", None)

    # Live mode needs BOTH the human key and the credentials.
    for v in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        os.environ[v] = "cred"
    _last_comment = None
    r = _post_tweet({"number": 11, "text": "creds but no key"})
    check("credentials without the live key still dry-run",
          r.get("isError") is False and DRYRUN_MARKER in _last_comment["body"])

    os.environ["GROWTH_TWITTER_LIVE"] = "true"
    # Live + approval required + label absent → refused.
    check("live mode without the approval label is refused",
          err(_post_tweet({"number": 9, "text": "x"})))
    # Live + approved → claims, posts, records, closes; an earlier dry-run
    # marker does not block the approved live post.
    _last_tweets, _last_close, _last_comment = None, None, None
    r = _post_tweet({"number": 12, "text": "approved and live",
                     "thread": ["part two"]})
    check("an approved item posts live over its old dry-run marker",
          r.get("isError") is False and "POSTED live" in r["content"][0]["text"])
    check("the thread posts as replies in order",
          _last_tweets == [{"text": "approved and live", "reply_to": None},
                           {"text": "part two", "reply_to": "fake-tweet-1"}])
    check("the CLAIM comment carries the posted marker and lands BEFORE the tweets",
          any(c["body"].startswith(POSTED_MARKER) for c in _FAKE_COMMENTS[12]))
    check("the outcome comment carries the tweet URL",
          _last_comment and "https://x.com/i/web/status/" in _last_comment["body"])
    check("a live post closes the drained queue item", _last_close == 12)
    # And a posted item never posts again, in any mode.
    check("a live-posted item is refused forever",
          err(_post_tweet({"number": 12, "text": "again"})))

    # A FIRST-tweet failure publishes NOTHING, so the claim is a false alarm:
    # it is withdrawn, the real reason is recorded, and the item stays retryable
    # (the X-credits-depleted lesson — a rejected post must not strand a queued
    # message behind a claim marker a human has to hand-delete).
    _FAKE_ISSUES[13] = q(13, OK + [APPROVAL_LABEL])
    _ready_live(13, root="fails on the first tweet")
    _last_deleted = None
    os.environ["GROWTH_MCP_FAKE_X_FAIL"] = "1"
    r = _post_tweet({"number": 13, "text": "fails on the first tweet"})
    check("a first-tweet failure errors loudly and reports it retryable",
          err(r) and "rejected before publishing" in r["content"][0]["text"]
          and "retryable" in r["content"][0]["text"])
    check("nothing-published WITHDRAWS the claim marker",
          not any(POSTED_MARKER in c["body"] for c in _FAKE_COMMENTS.get(13, [])))
    check("the withdrawn claim id is recorded", _last_deleted is not None)
    check("the failure reason lands on the item as a comment",
          any(FAILURE_HEADER in c["body"] for c in _FAKE_COMMENTS.get(13, [])))
    os.environ.pop("GROWTH_MCP_FAKE_X_FAIL", None)
    check("a withdrawn item is postable again (not refused as a duplicate)",
          _post_tweet({"number": 13, "text": "fails on the first tweet"}
                      ).get("isError") is False)

    # A MID-THREAD failure is the OPPOSITE: the first tweet IS live, so the
    # claim must STAND (withdrawing it would risk a public double-post) and the
    # item stays refused on retry.
    _FAKE_ISSUES[15] = q(15, OK + [APPROVAL_LABEL])
    _ready_live(15, root="first is fine", thread=["this part fails"])
    _last_deleted = None
    os.environ["GROWTH_MCP_FAKE_X_FAIL_PART"] = "1"
    r = _post_tweet({"number": 15, "text": "first is fine", "thread": ["this part fails"]})
    check("a mid-thread failure errors loudly",
          err(r) and "mid-thread" in r["content"][0]["text"])
    check("a mid-thread failure KEEPS the claim marker",
          any(POSTED_MARKER in c["body"] for c in _FAKE_COMMENTS.get(15, [])))
    check("a mid-thread failure withdraws nothing", _last_deleted is None)
    os.environ.pop("GROWTH_MCP_FAKE_X_FAIL_PART", None)
    check("a mid-thread-failed item is refused on the next attempt (no duplicate)",
          err(_post_tweet({"number": 15, "text": "retry"})))

    # If the claim itself cannot be written, nothing is published.
    _FAKE_ISSUES[14] = q(14, OK + [APPROVAL_LABEL])
    _ready_live(14, root="cannot claim")
    _last_tweets = None
    os.environ["GROWTH_MCP_FAKE_COMMENT_FAIL"] = "1"
    r = _post_tweet({"number": 14, "text": "cannot claim"})
    check("an unclaimable item publishes nothing",
          err(r) and "nothing was published" in r["content"][0]["text"]
          and not _last_tweets)
    os.environ.pop("GROWTH_MCP_FAKE_COMMENT_FAIL", None)

    # The live key without credentials is still a dry run.
    for v in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        os.environ.pop(v, None)
    _last_comment = None
    r = _post_tweet({"number": 10, "text": "key but no creds"})
    check("the live key without credentials still dry-runs",
          r.get("isError") is False and DRYRUN_MARKER in _last_comment["body"])
    os.environ.pop("GROWTH_TWITTER_LIVE", None)

    # The walk-spanning per-run cap (issue #570), inside an Actions run
    # (GITHUB_RUN_ID set). Default cap is 1.
    os.environ["GITHUB_RUN_ID"] = "selftest-run"
    _FAKE_ISSUES[20] = q(20, OK)
    _FAKE_ISSUES[21] = q(21, OK)

    # Unwired: run id set but no state path. Fail closed — per-process
    # counting is exactly the per-link reset the state file replaces.
    r = _post_tweet({"number": 20, "text": "unwired"})
    check("an unattended run without GROWTH_CAP_STATE refuses (fail closed)",
          err(r) and CAP_STATE_ENV in r["content"][0]["text"])

    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "growth-posts")
        os.environ[CAP_STATE_ENV] = state

        # In-process: one post consumes the default cap of 1 (a DRY-RUN
        # counts — the same semantics the in-process counter had), and the
        # refusal the next call reads counts from the state file.
        r1 = _post_tweet({"number": 20, "text": "one"})
        r2 = _post_tweet({"number": 21, "text": "two"})
        check("the cap lets through GROWTH_MAX_POSTS (default 1)",
              r1.get("isError") is False)
        check("the cap refuses past the limit",
              err(r2) and "cap reached" in r2["content"][0]["text"])
        check("the consumed slot appended one state record",
              _cap_state_count(state) == 1)

        # THE cross-process property (#570): link N posts its fill and then
        # dies; link N+1 is a FRESH process whose only memory of the run is
        # the state file. A real subprocess against the pre-populated file is
        # the exact situation an in-process counter got wrong.
        probe = [sys.executable, os.path.abspath(__file__), "--selftest-cap-child"]

        proc = subprocess.run(probe + [state], env=dict(os.environ),
                              capture_output=True, text=True)
        check("a fresh process counting from a state file at the cap refuses "
              "(the cross-process property)",
              proc.returncode == 0 and proc.stdout.startswith("REFUSED"))

        # An EMPTY state file (nothing posted yet) → the fresh process posts
        # (a dry-run, in this env), and the shared file advances — so the
        # link after IT sees the incremented count too.
        state2 = os.path.join(tmp, "growth-posts-2")
        os.environ[CAP_STATE_ENV] = state2
        proc = subprocess.run(probe + [state2], env=dict(os.environ),
                              capture_output=True, text=True)
        check("a fresh process with an empty state file posts (cross-process)",
              proc.returncode == 0 and proc.stdout.startswith("POSTED"))
        check("the fresh process's post advanced the shared state file",
              _cap_state_count(state2) == 1)

    os.environ.pop(CAP_STATE_ENV, None)
    os.environ.pop("GITHUB_RUN_ID", None)

    # Attended behavior is unchanged: no GITHUB_RUN_ID means the cap is
    # skipped — no state file needed or required.
    _FAKE_ISSUES[22] = q(22, OK)
    _FAKE_ISSUES[23] = q(23, OK)
    a1 = _post_tweet({"number": 22, "text": "attended one"})
    a2 = _post_tweet({"number": 23, "text": "attended two"})
    check("attended (no GITHUB_RUN_ID) skips the cap — no state file required",
          a1.get("isError") is False and a2.get("isError") is False)

    # Root @-tag preservation: ## Message first paragraph's handles must land
    # in the root tweet (never only a reply). Missing tags are restored or
    # the post is refused.
    tagged_body = (
        "## Message\n\n"
        "Drafted root about the spool peg margin. @Prusa3D @prusament\n\n"
        "Longer intent the agent may paraphrase.\n"
    )
    _FAKE_ISSUES[30] = q(30, OK)
    _FAKE_ISSUES[30]["body"] = tagged_body
    _FAKE_COMMENTS.pop(30, None)
    _last_comment = None
    r = _post_tweet({
        "number": 30,
        "text": "Spool peg statics came out marginal — page publishes the number.",
    })
    check("a composed root missing drafted @handles is restored before dry-run",
          r.get("isError") is False
          and _last_comment
          and "@Prusa3D" in _last_comment["body"]
          and "@prusament" in _last_comment["body"])
    _FAKE_ISSUES[31] = q(31, OK)
    _FAKE_ISSUES[31]["body"] = tagged_body
    _FAKE_COMMENTS.pop(31, None)
    _last_comment = None
    kept = ("Spool peg statics came out marginal — page publishes the number. "
            "@Prusa3D @prusament")
    r = _post_tweet({"number": 31, "text": kept})
    check("a composed root that already carries the tags is left unchanged",
          r.get("isError") is False
          and _last_comment
          and kept in _last_comment["body"])
    _FAKE_ISSUES[32] = q(32, OK)
    _FAKE_ISSUES[32]["body"] = (
        "## Message\n\nA design-decision story with no community tags.\n"
    )
    _FAKE_COMMENTS.pop(32, None)
    _last_comment = None
    bare = "Feel couldn't answer — the vertical rail could."
    r = _post_tweet({"number": 32, "text": bare})
    check("a no-tags ## Message leaves the composed root unchanged",
          r.get("isError") is False
          and _last_comment
          and bare in _last_comment["body"])
    _FAKE_ISSUES[33] = q(33, OK)
    _FAKE_ISSUES[33]["body"] = tagged_body
    # Fill the weighted budget so appending two handles cannot fit, and make
    # the drafted paragraph itself over-weight so the verbatim path is closed.
    _FAKE_ISSUES[33]["body"] = (
        "## Message\n\n" + ("z" * 281) + " @Prusa3D @prusament\n"
    )
    r = _post_tweet({"number": 33, "text": "y" * 280})
    check("over-budget missing tags fail closed (no untagged post)",
          err(r) and "refusing untagged" in r["content"][0]["text"])

    # Handle cap: more than MAX_REQUIRED_HANDLES in ## Message → refuse.
    over = " ".join(f"@U{i}" for i in range(MAX_REQUIRED_HANDLES + 1))
    _FAKE_ISSUES[34] = q(34, OK)
    _FAKE_ISSUES[34]["body"] = f"## Message\n\nRoot {over}\n"
    r = _post_tweet({"number": 34, "text": "agent rewrite"})
    check("over-cap @handles in ## Message are refused",
          err(r) and f"cap {MAX_REQUIRED_HANDLES}" in r["content"][0]["text"])

    # Full-width at-signs (＠ U+FF20 / ﹫ U+FE6B) refuse on every path.
    _FAKE_ISSUES[38] = q(38, OK)
    _FAKE_ISSUES[38]["body"] = "## Message\n\nDrafted with ＠Prusa3D\n"
    r = _post_tweet({"number": 38, "text": "agent rewrite"})
    check("full-width ＠ in ## Message is refused",
          err(r) and "full-width at-sign" in r["content"][0]["text"])
    _FAKE_ISSUES[39] = q(39, OK)
    _FAKE_ISSUES[39]["body"] = "## Message\n\nNo tags.\n"
    _FAKE_COMMENTS.pop(39, None)
    r = _post_tweet({"number": 39, "text": "composed with ＠Sneaky"})
    check("full-width ＠ in composed root is refused",
          err(r) and "full-width at-sign" in r["content"][0]["text"])
    _FAKE_ISSUES[41] = q(41, OK)
    _FAKE_ISSUES[41]["body"] = "## Message\n\nNo tags.\n"
    _FAKE_COMMENTS.pop(41, None)
    r = _post_tweet({"number": 41, "text": "root ok", "thread": ["reply ﹫Sneaky"]})
    check("full-width ﹫ in a thread part is refused",
          err(r) and "full-width at-sign" in r["content"][0]["text"])
    six = " ".join(f"@U{i}" for i in range(6))
    _FAKE_ISSUES[42] = q(42, OK)
    _FAKE_ISSUES[42]["body"] = "## Message\n\nNo tags.\n"
    _FAKE_COMMENTS.pop(42, None)
    r = _post_tweet({"number": 42, "text": f"composed {six}"})
    check("composed root with >5 mention tokens is refused",
          err(r) and f"cap {MAX_REQUIRED_HANDLES}" in r["content"][0]["text"])

    # Thread-wide mention cap (root + replies combined).
    _FAKE_ISSUES[47] = q(47, OK)
    _FAKE_ISSUES[47]["body"] = "## Message\n\nNo tags.\n"
    _FAKE_COMMENTS.pop(47, None)
    r = _post_tweet({
        "number": 47,
        "text": "@A @B @C",
        "thread": ["@D @E @F"],
    })
    check("thread-wide mention cap refuses root+replies over 5",
          err(r) and "across root+replies" in r["content"][0]["text"])

    # --- LIVE gates (preview → human re-label → post) -----------------------
    os.environ["GROWTH_TWITTER_LIVE"] = "true"
    for v in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        os.environ[v] = "cred"

    # Body edited after approval: preview is no longer after lastEditedAt →
    # self-migrate (no post). Freeze still applies on the happy path.
    _FAKE_ISSUES[35] = q(35, OK + [APPROVAL_LABEL])
    _seed_trusted_preview(35, created_at="2026-01-02T10:00:00Z")
    _approve(35, at="2026-01-02T12:00:00Z")
    _FAKE_LAST_EDITED[35] = "2026-01-03T00:00:00Z"
    _last_tweets = None
    r = _post_tweet({"number": 35, "text": "should not go live"})
    check("LIVE does not post when body was edited after approved-to-post",
          not _last_tweets
          and (err(r) or "PREVIEW self-migrated" in r["content"][0]["text"]))

    # Unreadable timeline → fail closed on LIVE.
    _FAKE_ISSUES[36] = q(36, OK + [APPROVAL_LABEL])
    _ready_live(36)
    os.environ["GROWTH_MCP_FAKE_EVENTS_FAIL"] = "1"
    r = _post_tweet({"number": 36, "text": "no timeline"})
    check("LIVE refuses when approval timeline cannot be read",
          err(r) and "fail closed" in r["content"][0]["text"])
    os.environ.pop("GROWTH_MCP_FAKE_EVENTS_FAIL", None)

    # Events page-cap → raise inside the pager → LIVE refuses (fail closed).
    # Must not return a truncated oldest-first prefix and still post.
    _FAKE_ISSUES[67] = q(67, OK + [APPROVAL_LABEL])
    _ready_live(67)
    _last_tweets = None
    os.environ["GROWTH_MCP_FAKE_EVENTS_PAGE_CAP"] = "1"
    r = _post_tweet({"number": 67, "text": "page cap must refuse"})
    check("LIVE refuses when issue-events page cap is hit",
          err(r)
          and "fail closed" in r["content"][0]["text"]
          and "pages of issue events" in r["content"][0]["text"]
          and not _last_tweets)
    os.environ.pop("GROWTH_MCP_FAKE_EVENTS_PAGE_CAP", None)

    # Comments page-cap → refuse before LIVE gates (marker walk fail closed).
    _FAKE_ISSUES[68] = q(68, OK + [APPROVAL_LABEL])
    _ready_live(68)
    _last_tweets = None
    os.environ["GROWTH_MCP_FAKE_COMMENTS_PAGE_CAP"] = "1"
    r = _post_tweet({"number": 68, "text": "comments page cap"})
    check("LIVE refuses when issue-comments page cap is hit",
          err(r)
          and "pages of issue comments" in r["content"][0]["text"]
          and not _last_tweets)
    os.environ.pop("GROWTH_MCP_FAKE_COMMENTS_PAGE_CAP", None)

    # Missing preview → self-migrate (write preview, remove label, no post).
    _FAKE_ISSUES[43] = q(43, OK + [APPROVAL_LABEL])
    _approve(43)
    _FAKE_COMMENTS.pop(43, None)
    _last_comment = None
    _last_label_removed = None
    _last_tweets = None
    r = _post_tweet({"number": 43, "text": "needs preview"})
    check("LIVE self-migrates when no trusted preview exists",
          r.get("isError") is False
          and "PREVIEW self-migrated" in r["content"][0]["text"]
          and _last_comment and _parse_message_digest(_last_comment["body"])
          and _parse_render_digest(_last_comment["body"])
          == _render_digest("needs preview")
          and _last_label_removed == {"number": 43, "label": APPROVAL_LABEL}
          and not _last_tweets
          and APPROVAL_LABEL not in _label_names(_FAKE_ISSUES[43]))

    # Look-alike login → treated as missing → self-migrate.
    _FAKE_ISSUES[44] = q(44, OK + [APPROVAL_LABEL])
    _FAKE_ISSUES[44]["body"] = "## Message\n\nTagged root @Prusa3D\n"
    _approve(44)
    dig = _digest_comment_line(_FAKE_ISSUES[44]["body"])
    _FAKE_COMMENTS[44] = [{
        "body": f"{DRYRUN_MARKER}\n{dig}\nspoofed",
        "user": {"login": "github-actions-imposter", "type": "User"},
        "created_at": PREVIEW_AT,
        "updated_at": PREVIEW_AT,
    }]
    _last_label_removed = None
    r = _post_tweet({"number": 44, "text": "lookalike author @Prusa3D"})
    check("LIVE self-migrates when only a look-alike author preview exists",
          r.get("isError") is False
          and "PREVIEW self-migrated" in r["content"][0]["text"]
          and _last_label_removed is not None)

    # Markers mid-body (forged) → not trusted → self-migrate.
    _FAKE_ISSUES[48] = q(48, OK + [APPROVAL_LABEL])
    _approve(48)
    dig = _digest_comment_line("")
    _FAKE_COMMENTS[48] = [{
        "body": f"intro\n{DRYRUN_MARKER}\n{dig}\ntrailing",
        "user": {"login": TRUSTED_PREVIEW_LOGIN, "type": TRUSTED_PREVIEW_TYPE},
        "created_at": PREVIEW_AT,
        "updated_at": PREVIEW_AT,
    }]
    r = _post_tweet({"number": 48, "text": "forged mid-body"})
    check("LIVE rejects mid-body marker forgeries (self-migrates)",
          r.get("isError") is False
          and "PREVIEW self-migrated" in r["content"][0]["text"])

    # Old format (marker, no digest line) → not trusted → self-migrate.
    _FAKE_ISSUES[49] = q(49, OK + [APPROVAL_LABEL])
    _approve(49)
    _FAKE_COMMENTS[49] = [{
        "body": f"{DRYRUN_MARKER}\nold format without digest",
        "user": {"login": TRUSTED_PREVIEW_LOGIN, "type": TRUSTED_PREVIEW_TYPE},
        "created_at": PREVIEW_AT,
        "updated_at": PREVIEW_AT,
    }]
    r = _post_tweet({"number": 49, "text": "old format"})
    check("LIVE rejects old marker-only format (self-migrates)",
          r.get("isError") is False
          and "PREVIEW self-migrated" in r["content"][0]["text"])

    # Edited preview (updated_at != created_at) → not trusted → self-migrate.
    _FAKE_ISSUES[50] = q(50, OK + [APPROVAL_LABEL])
    _approve(50)
    _seed_trusted_preview(
        50, created_at=PREVIEW_AT, updated_at="2026-01-01T11:00:00Z"
    )
    r = _post_tweet({"number": 50, "text": "edited preview"})
    check("LIVE rejects an edited preview comment (self-migrates)",
          r.get("isError") is False
          and "PREVIEW self-migrated" in r["content"][0]["text"])

    # Digest mismatch on an existing trusted preview → refuse (no 2nd preview).
    _FAKE_ISSUES[45] = q(45, OK + [APPROVAL_LABEL])
    _FAKE_ISSUES[45]["body"] = "## Message\n\nCurrent body @Prusa3D\n"
    _approve(45)
    _seed_trusted_preview(
        45, body="## Message\n\nOld draft @Prusa3D\n",
        root="Current body @Prusa3D",
    )
    _last_tweets = None
    _last_comment = None
    r = _post_tweet({"number": 45, "text": "Current body @Prusa3D"})
    check("LIVE refuses digest mismatch without edit (no second preview)",
          err(r) and "digest mismatch without edit" in r["content"][0]["text"]
          and not _last_tweets and _last_comment is None)

    # Two trusted previews after last edit → refuse (ambiguity, no migrate).
    _FAKE_ISSUES[51] = q(51, OK + [APPROVAL_LABEL])
    body_prev = f"{_preview_digest_header('', 'two previews')}one"
    _FAKE_COMMENTS[51] = [
        {"body": body_prev,
         "user": {"login": TRUSTED_PREVIEW_LOGIN, "type": TRUSTED_PREVIEW_TYPE},
         "created_at": "2026-01-01T09:00:00Z", "updated_at": "2026-01-01T09:00:00Z"},
        {"body": body_prev,
         "user": {"login": TRUSTED_PREVIEW_LOGIN, "type": TRUSTED_PREVIEW_TYPE},
         "created_at": "2026-01-01T10:00:00Z", "updated_at": "2026-01-01T10:00:00Z"},
    ]
    _approve(51)
    r = _post_tweet({"number": 51, "text": "two previews"})
    check("LIVE refuses when two trusted previews exist after last edit",
          err(r) and "ambiguous" in r["content"][0]["text"])

    # Message-digest-only preview (pre-#1023) → not trusted → self-migrate.
    _FAKE_ISSUES[69] = q(69, OK + [APPROVAL_LABEL])
    _approve(69)
    dig_only = _digest_comment_line("")
    _FAKE_COMMENTS[69] = [{
        "body": f"{DRYRUN_MARKER}\n{dig_only}\nold two-line header",
        "user": {"login": TRUSTED_PREVIEW_LOGIN, "type": TRUSTED_PREVIEW_TYPE},
        "created_at": PREVIEW_AT,
        "updated_at": PREVIEW_AT,
    }]
    r = _post_tweet({"number": 69, "text": "needs render digest"})
    check("LIVE self-migrates when preview lacks render-digest (#1023)",
          r.get("isError") is False
          and "PREVIEW self-migrated" in r["content"][0]["text"])

    # Bot-actor label as the LATEST labeled → refuse (not a User approval).
    _FAKE_ISSUES[52] = q(52, OK + [APPROVAL_LABEL])
    _seed_trusted_preview(52)
    _approve(52, login="github-actions[bot]", utype="Bot")
    r = _post_tweet({"number": 52, "text": "bot labeled"})
    check("LIVE refuses a Bot-actor approved-to-post label",
          err(r) and "not by a User" in r["content"][0]["text"])

    # Non-allowlisted User label as the LATEST → refuse.
    _FAKE_ISSUES[53] = q(53, OK + [APPROVAL_LABEL])
    _seed_trusted_preview(53)
    _approve(53, login="random-user", utype="User")
    r = _post_tweet({"number": 53, "text": "not allowlisted"})
    check("LIVE refuses a non-allowlisted approver",
          err(r) and "not an allowlisted User" in r["content"][0]["text"])

    # Label before preview → refuse.
    _FAKE_ISSUES[54] = q(54, OK + [APPROVAL_LABEL])
    _seed_trusted_preview(54, created_at="2026-01-01T12:00:00Z")
    _approve(54, at="2026-01-01T10:00:00Z")  # before preview
    r = _post_tweet({"number": 54, "text": "label too early"})
    check("LIVE refuses when approval is not after the preview",
          err(r) and "after the trusted preview" in r["content"][0]["text"])

    # Label-removal failure after writing preview → refuse, don't post.
    _FAKE_ISSUES[55] = q(55, OK + [APPROVAL_LABEL])
    _approve(55)
    _FAKE_COMMENTS.pop(55, None)
    _last_tweets = None
    os.environ["GROWTH_MCP_FAKE_LABEL_REMOVE_FAIL"] = "1"
    r = _post_tweet({"number": 55, "text": "removal fails"})
    check("LIVE refuses when removing approved-to-post fails",
          err(r) and "removing" in r["content"][0]["text"]
          and not _last_tweets)
    os.environ.pop("GROWTH_MCP_FAKE_LABEL_REMOVE_FAIL", None)

    # Shai labels, unlabels, someone else re-adds → refuse (latest = other).
    _FAKE_ISSUES[56] = q(56, OK + [APPROVAL_LABEL])
    _seed_trusted_preview(56)
    _approve(56, events=[
        {"event": "labeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-01T11:00:00Z",
         "actor": {"login": "shaiss", "type": "User"}},
        {"event": "unlabeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-01T12:00:00Z",
         "actor": {"login": "shaiss", "type": "User"}},
        {"event": "labeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-01T13:00:00Z",
         "actor": {"login": "other", "type": "User"}},
    ])
    r = _post_tweet({"number": 56, "text": "revoked then other"})
    check("LIVE refuses when Shai unlabels and someone else re-adds",
          err(r) and "not an allowlisted User" in r["content"][0]["text"])

    # Shai labels in the gap before bot removal; bot removes; other re-adds.
    _FAKE_ISSUES[57] = q(57, OK + [APPROVAL_LABEL])
    _seed_trusted_preview(57)
    _approve(57, events=[
        {"event": "labeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-01T11:00:00Z",
         "actor": {"login": "shaiss", "type": "User"}},
        {"event": "unlabeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-01T12:00:00Z",
         "actor": {"login": TRUSTED_PREVIEW_LOGIN, "type": TRUSTED_PREVIEW_TYPE}},
        {"event": "labeled", "label": {"name": APPROVAL_LABEL},
         "created_at": "2026-01-01T13:00:00Z",
         "actor": {"login": "other", "type": "User"}},
    ])
    r = _post_tweet({"number": 57, "text": "gap then other"})
    check("LIVE refuses gap-approval then bot removal then non-allowlisted re-add",
          err(r) and "not an allowlisted User" in r["content"][0]["text"])

    # App-performed label refused when GROWTH_REQUIRE_DIRECT_HUMAN_LABEL=true.
    os.environ[DIRECT_HUMAN_LABEL_ENV] = "true"
    _FAKE_ISSUES[58] = q(58, OK + [APPROVAL_LABEL])
    _seed_trusted_preview(58, root="via app allowed")
    _approve(58, via_app={"id": 1, "slug": "cursor"})
    r = _post_tweet({"number": 58, "text": "via app"})
    check("LIVE refuses app-performed label when direct-human required",
          err(r) and "performed via a GitHub App" in r["content"][0]["text"])
    # Same label allowed when the env is exactly 'false'.
    os.environ[DIRECT_HUMAN_LABEL_ENV] = "false"
    _last_tweets, _last_close = None, None
    r = _post_tweet({"number": 58, "text": "via app allowed"})
    check("LIVE allows app-performed label when direct-human is false",
          r.get("isError") is False and "POSTED live" in r["content"][0]["text"])
    os.environ.pop(DIRECT_HUMAN_LABEL_ENV, None)

    # Preview-migrate does not consume the run's post slot.
    os.environ["GITHUB_RUN_ID"] = "selftest-preview-cap"
    os.environ["GROWTH_MAX_POSTS"] = "1"
    preview_cap_dir = tempfile.mkdtemp(prefix="growth-preview-cap-")
    preview_cap_state = os.path.join(preview_cap_dir, "growth-posts")
    os.environ[CAP_STATE_ENV] = preview_cap_state
    for n, body in ((59, ""), (60, "")):
        _FAKE_ISSUES[n] = q(n, OK + [APPROVAL_LABEL])
        _approve(n)
        _FAKE_COMMENTS.pop(n, None)
    r1 = _post_tweet({"number": 59, "text": "preview one"})
    r2 = _post_tweet({"number": 60, "text": "preview two"})
    check("LIVE preview-migrates two items under a post cap of 1",
          r1.get("isError") is False
          and r2.get("isError") is False
          and "PREVIEW self-migrated" in r1["content"][0]["text"]
          and "PREVIEW self-migrated" in r2["content"][0]["text"]
          and _cap_state_count(preview_cap_state) == 0)
    # A ready item can still post after those previews.
    _FAKE_ISSUES[61] = q(61, OK + [APPROVAL_LABEL])
    _FAKE_ISSUES[61]["body"] = "## Message\n\nAfter previews @Prusa3D\n"
    _ready_live(
        61, body=_FAKE_ISSUES[61]["body"], root="After previews @Prusa3D"
    )
    _last_tweets = None
    r3 = _post_tweet({"number": 61, "text": "After previews @Prusa3D"})
    check("LIVE still posts one item after non-consuming preview-migrates",
          r3.get("isError") is False
          and "POSTED live" in r3["content"][0]["text"]
          and _cap_state_count(preview_cap_state) == 1)
    # Same-run preview then post of the SAME issue is refused.
    _FAKE_ISSUES[62] = q(62, OK + [APPROVAL_LABEL])
    _FAKE_ISSUES[62]["body"] = "## Message\n\nSame-run @Prusa3D\n"
    _approve(62)
    _FAKE_COMMENTS.pop(62, None)
    r_prev = _post_tweet({"number": 62, "text": "Same-run @Prusa3D"})
    # Re-add approval + matching preview as if a human re-labeled immediately,
    # but the cap-state still has preview-migrate for 62.
    _FAKE_ISSUES[62]["labels"] = [
        {"name": n} for n in OK + [APPROVAL_LABEL]
    ]
    _ready_live(
        62, body=_FAKE_ISSUES[62]["body"], root="Same-run @Prusa3D"
    )
    # Keep the preview-migrate record; overlay a trusted preview + approval.
    r_same = _post_tweet({"number": 62, "text": "Same-run @Prusa3D"})
    check("LIVE refuses to post an issue preview-migrated earlier this run",
          r_prev.get("isError") is False
          and "PREVIEW self-migrated" in r_prev["content"][0]["text"]
          and err(r_same)
          and "preview-migrated earlier" in r_same["content"][0]["text"])
    # Extra model URL outside ## Link refuses (dry-run path; same gate).
    # Drop the run-cap / live env so these are plain attended dry-runs.
    os.environ.pop("GROWTH_TWITTER_LIVE", None)
    os.environ.pop("GITHUB_RUN_ID", None)
    os.environ.pop("GROWTH_MAX_POSTS", None)
    os.environ.pop(CAP_STATE_ENV, None)
    for v in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        os.environ.pop(v, None)
    try:
        import shutil
        shutil.rmtree(preview_cap_dir, ignore_errors=True)
    except OSError:
        pass
    _FAKE_ISSUES[63] = q(63, OK)
    _FAKE_ISSUES[63]["body"] = (
        "## Message\n\nLink only @Prusa3D\n\n"
        "## Link\n\nhttps://github.com/shaiss/print-bench\n"
    )
    _FAKE_COMMENTS.pop(63, None)
    r_evil = _post_tweet({
        "number": 63,
        "text": "Link only @Prusa3D https://github.com/shaiss/print-bench "
                "https://evil.example/phish",
    })
    check("extra URL outside ## Message/## Link is refused",
          err(r_evil) and "not in the approved" in r_evil["content"][0]["text"])
    # Upper- / mixed-case schemes must not bypass the allowlist.
    _FAKE_ISSUES[65] = q(65, OK)
    _FAKE_ISSUES[65]["body"] = (
        "## Message\n\nLink only @Prusa3D\n\n"
        "## Link\n\nhttps://github.com/shaiss/print-bench\n"
    )
    _FAKE_COMMENTS.pop(65, None)
    r_https = _post_tweet({
        "number": 65,
        "text": "Hi @Prusa3D HTTPS://evil.example/x",
    })
    check("HTTPS:// scheme URL outside allowlist is refused",
          err(r_https) and "not in the approved" in r_https["content"][0]["text"])
    _FAKE_ISSUES[66] = q(66, OK)
    _FAKE_ISSUES[66]["body"] = _FAKE_ISSUES[65]["body"]
    _FAKE_COMMENTS.pop(66, None)
    r_http_mix = _post_tweet({
        "number": 66,
        "text": "Hi @Prusa3D HtTp://evil.example/x",
    })
    check("HtTp:// scheme URL outside allowlist is refused",
          err(r_http_mix)
          and "not in the approved" in r_http_mix["content"][0]["text"])
    # Link-only re-attach on dry-run succeeds.
    _FAKE_ISSUES[64] = q(64, OK)
    _FAKE_ISSUES[64]["body"] = (
        "## Message\n\nLink only @Prusa3D\n\n"
        "## Link\n\nhttps://github.com/shaiss/print-bench\n"
    )
    _FAKE_COMMENTS.pop(64, None)
    _last_comment = None
    r_ok_link = _post_tweet({
        "number": 64,
        "text": "Agent rewrite without the tag.",
    })
    check("Link-only re-attach on drafted restore passes",
          r_ok_link.get("isError") is False
          and _last_comment
          and "https://github.com/shaiss/print-bench" in _last_comment["body"]
          and "@Prusa3D" in _last_comment["body"])

    # Happy path: matching digest + human approval after preview + freeze.
    os.environ["GROWTH_TWITTER_LIVE"] = "true"
    for v in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        os.environ[v] = "cred"
    _FAKE_ISSUES[46] = q(46, OK + [APPROVAL_LABEL])
    _FAKE_ISSUES[46]["body"] = "## Message\n\nBound draft @Prusa3D\n"
    _ready_live(
        46, body=_FAKE_ISSUES[46]["body"], root="Bound draft @Prusa3D"
    )
    _last_tweets, _last_close = None, None
    r = _post_tweet({"number": 46, "text": "Bound draft @Prusa3D"})
    check("LIVE proceeds when trusted digest matches and freeze is fresh",
          r.get("isError") is False and "POSTED live" in r["content"][0]["text"])

    # #1023: matching render-digest posts; altered copy / bare-domain refuse.
    _FAKE_ISSUES[70] = q(70, OK + [APPROVAL_LABEL])
    _FAKE_ISSUES[70]["body"] = (
        "## Message\n\nApproved copy @Prusa3D\n\n"
        "## Link\n\nhttps://github.com/shaiss/print-bench\n"
    )
    approved_copy = (
        "Approved copy @Prusa3D https://github.com/shaiss/print-bench"
    )
    _ready_live(70, body=_FAKE_ISSUES[70]["body"], root=approved_copy)
    _last_tweets = None
    r = _post_tweet({"number": 70, "text": approved_copy})
    check("LIVE posts when render-digest matches approved preview (#1023)",
          r.get("isError") is False and "POSTED live" in r["content"][0]["text"]
          and _last_tweets == [{"text": approved_copy, "reply_to": None}])

    _FAKE_ISSUES[71] = q(71, OK + [APPROVAL_LABEL])
    _FAKE_ISSUES[71]["body"] = _FAKE_ISSUES[70]["body"]
    _ready_live(71, body=_FAKE_ISSUES[71]["body"], root=approved_copy)
    _last_tweets = None
    r = _post_tweet({
        "number": 71,
        "text": "Altered prose @Prusa3D https://github.com/shaiss/print-bench",
    })
    check("LIVE refuses altered copy vs approved preview (#1023)",
          err(r) and "render-digest mismatch" in r["content"][0]["text"]
          and not _last_tweets)

    _FAKE_ISSUES[72] = q(72, OK + [APPROVAL_LABEL])
    _FAKE_ISSUES[72]["body"] = _FAKE_ISSUES[70]["body"]
    _ready_live(72, body=_FAKE_ISSUES[72]["body"], root=approved_copy)
    _last_tweets = None
    r = _post_tweet({
        "number": 72,
        "text": approved_copy + " see example.com/x",
    })
    check("LIVE refuses bare-domain injection via recomposed copy (#1023)",
          err(r) and "render-digest mismatch" in r["content"][0]["text"]
          and not _last_tweets)

    # Dry-run with a stale body still proceeds but reports the condition.
    os.environ.pop("GROWTH_TWITTER_LIVE", None)
    for v in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        os.environ.pop(v, None)
    _FAKE_ISSUES[37] = q(37, OK + [APPROVAL_LABEL])
    _approve(37, at="2026-01-02T12:00:00Z")
    _FAKE_LAST_EDITED[37] = "2026-01-03T00:00:00Z"
    _FAKE_COMMENTS.pop(37, None)
    _last_comment = None
    r = _post_tweet({"number": 37, "text": "dry-run with stale body"})
    check("dry-run proceeds on a stale body but reports approval freshness",
          r.get("isError") is False
          and _last_comment
          and "Approval freshness" in _last_comment["body"]
          and "edited after approved-to-post" in _last_comment["body"])
    check("dry-run on a stale body still records a message-digest",
          _last_comment and _parse_message_digest(_last_comment["body"])
          == _message_digest(""))
    check("dry-run on a stale body still records a render-digest",
          _last_comment and _parse_render_digest(_last_comment["body"])
          == _render_digest("dry-run with stale body"))

    # The JSON-RPC surface exposes exactly the one tool.
    check("tools/list exposes exactly post_tweet",
          [t["name"] for t in TOOLS] == ["post_tweet"])

    if fails:
        print(f"\ngrowth_mcp selftest FAILED: {', '.join(fails)}")
        return 1
    print("\ngrowth_mcp selftest passed")
    return 0


def selftest_cap_child(state_path):
    """One post attempt in THIS fresh process — the parent selftest's
    cross-process case. The parent's module state died with its process; the
    only thing this process knows about the run's posts is the state file it
    is handed, which is exactly link N+1's view after link N posted and died
    (issue #570). Prints POSTED/REFUSED for the parent to assert on."""
    os.environ["GROWTH_MCP_FAKE"] = "1"
    os.environ["GITHUB_RUN_ID"] = "selftest-link-n+1"
    os.environ[CAP_STATE_ENV] = state_path
    _FAKE_ISSUES[40] = {"number": 40, "state": "open",
                        "labels": [{"name": n} for n in (QUEUE_LABEL, CHANNEL_LABEL)]}
    r = _post_tweet({"number": 40, "text": "cross-process probe"})
    outcome = "REFUSED" if r.get("isError") else "POSTED"
    print(f"{outcome}: {r['content'][0]['text']}")
    return 0


def main():
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    if "--selftest-cap-child" in sys.argv:
        i = sys.argv.index("--selftest-cap-child")
        if i + 1 >= len(sys.argv):
            log("--selftest-cap-child needs the state-file path argument")
            raise SystemExit(2)
        raise SystemExit(selftest_cap_child(sys.argv[i + 1]))
    log(f"starting (repo={os.environ.get('GITHUB_REPOSITORY', '?')}, "
        f"run={os.environ.get('GITHUB_RUN_ID', 'attended')}, "
        f"mode={'LIVE' if _live_mode() else 'dry-run'})")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            log(f"skipping unparseable line: {e}")
            continue
        try:
            response = handle(msg)
        except Exception as e:  # noqa: BLE001 — never let one message kill the loop
            log(f"handler error: {type(e).__name__}: {e}")
            response = _error(msg.get("id"), -32603, f"internal error: {e}")
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    log("stdin closed, exiting")


if __name__ == "__main__":
    main()
