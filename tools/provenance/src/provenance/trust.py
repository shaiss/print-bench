"""Trust tiers — an exact port of ``scripts/reviewer-posted.sh`` and ``scripts/coach-lock-check.sh``.

Computed from the DIGEST (``digest.body_digest``) plus the author login, so
a re-extraction years later reaches the same verdict without the body
(docs/provenance.md §Trust tiers). Tiers, strongest first:

``verified``
    exactly what the repo's own artifact checks accept:

    * a sign-off (``JANE_SIGNOFF``/``DRIK_SIGNOFF``): the author is the
      Actions bot (REST ``github-actions[bot]``, GraphQL ``github-actions``
      — :func:`is_actions_bot`, the reviewer-posted.sh normalisation) AND
      ``digest.suffix_ok`` AND ``suffix_markers[-1]`` is that sign-off
      (family, sha, verdict, fuse exact) — i.e. the body ENDS with
      ``marker + "\\n\\n" + FOOTER``; basis ``actions-bot+suffix``;
    * a PM triage: Actions bot AND ``suffix_markers[-1]`` is
      ``<!-- PM_TRIAGE_DONE sha=S -->`` with ``S`` the triage marker's sha;
    * a coach lock: Actions bot AND ``suffix_markers[-2:] ==
      ["<!-- COACH_LOCK -->", "<!-- COACH_DONE sha=S -->"]`` (coach-lock-check.sh's
      ``SUFFIX_RE``);
    * an Oracle review: Actions bot AND ``head_marker == "<!-- ORACLE_REVIEW -->"``
      AND ``footer_ok``; basis ``actions-bot+head-marker``;
    * a ``reviewer-signoff`` commit status created by the Actions bot whose
      ``target_url`` run id is an ``auto-review.yml`` receipt
      (``actions-status+receipt``); every receipt event (``receipt``).

    Verified inherits that rule's residuals (any session holding
    GITHUB_TOKEN can post as the Actions bot) — documented, not fixed here.
``window`` (assigned by ``serving.py``, not here)
    the rule fails, the author is a posting identity of the role, and
    exactly one agent-step window of that role contains the artifact.
``claimed``
    a marker or trailer is present but the rule fails: owner-token
    sign-offs (``marker:owner-token``), another author (``marker:other-author``,
    e.g. markers quoted by cursor[bot]), an Actions-bot post without the
    MCP suffix (``marker:no-suffix``), or a post EDITED
    ``>= edit_grace_seconds`` after creation (``marker:edited`` — an edit
    demotes even a verified suffix); commit trailers (``trailer``); an issue
    body with a non-null ``lastEditedAt``.
``login``
    only the authoring login is known (basis ``login``).
``ambiguous`` / ``none``
    no single attribution (set by ``serving.py`` / for unattributable rows).

:func:`served` is the parity surface: it runs over RAW comment JSON (the
shape reviewer-posted.sh reads, bodies included), digests each body and
answers exactly like ``reviewer-posted.sh check`` — tests/test_trust.py
replays every ``row`` of ``reviewer-posted.sh --selftest`` and every row of
``coach-lock-check.sh --selftest`` through it, and drift-pins
``digest.FOOTER`` against ``reviewer_mcp.FOOTER`` and both scripts'
``REVIEWER_FOOTER``/``COACH_FOOTER`` literals (a 1-byte change fails).

**As built.**

* :func:`served` / :func:`coach_lock_served` take the comment LIST the
  scripts' ``load_comments`` produces; :func:`load_comments` is the port of
  that decoder (one array, concatenated page arrays, or an outer array of
  page arrays) for callers holding the raw ``gh api --paginate`` text. A
  list whose every element is itself a list is read as pages, as the
  scripts do.
* The served rule is decided on ``digest.body_digest(body)`` alone:
  ``footer_ok`` and ``suffix_markers[-1]`` equal to one of the exact MCP
  marker strings for that family and sha. That is equivalent to the
  scripts' ``body.endswith(marker + "\\n\\n" + FOOTER)`` because a marker
  cannot contain ``<`` — the suffix walk's last capture starts at the last
  ``<!--`` before the footer — and every MCP marker fits the digest's
  marker grammar.
* :func:`comment_tier` judges the four marker-bearing kinds the rules above
  name (``review.signoff``, ``triage.verdict``, ``coach.lock``,
  ``oracle.review``); any other comment kind (a ``coach.round`` note, a
  SHIP-LOCK) carries no verifiable marker and is ``login`` (or ``none``
  without a login). For a judged kind the author decides first (owner →
  ``marker:owner-token``, any other non-bot author or none →
  ``marker:other-author``), then the rule (``marker:no-suffix``), then the
  edit window (``marker:edited``). ``marker_sha`` is the sha of the marker
  the event was built from (the sign-off's, the ``PM_TRIAGE`` marker's, the
  ``COACH_DONE``'s); a triage needs it, a sign-off or coach lock is held to
  it when given.
* :func:`status_tier`: Actions-bot creator + an ``auto-review.yml`` receipt
  for the ``target_url`` run → ``verified``; an Actions-bot status whose run
  has no receipt → ``login`` (nothing vouches for which workflow posted it);
  the owner (optional keyword ``owner_login``) → ``claimed`` /
  ``marker:owner-token``; any other creator → ``claimed`` /
  ``marker:other-author``; no creator → ``none``.
* :func:`is_edited` is the edit-window rule on its own (the ``edited``
  field of the four judged kinds' field sets).

Owner: H2. Pure.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from . import digest as _digest

ACTIONS_BOT = "github-actions"
REVIEWER_FAMILIES = {"jane": "JANE_SIGNOFF", "drik": "DRIK_SIGNOFF",
                     "pm": "PM_TRIAGE_DONE", "coach": "COACH_DONE"}
COACH_LOCK_MARKER = "<!-- COACH_LOCK -->"
ORACLE_MARKER = "<!-- ORACLE_REVIEW -->"

#: The comment kinds whose trust is decided by a marker rule here.
JUDGED_KINDS = frozenset({"review.signoff", "triage.verdict", "coach.lock", "oracle.review"})

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_SINCE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_COACH_DONE_RE = re.compile(r"<!-- COACH_DONE sha=([0-9a-f]{40}) -->")
_SIGNOFF_SUFFIX_RE = re.compile(r"<!-- (JANE|DRIK)_SIGNOFF sha=([0-9a-f]{40}) verdict=(?:pass|block) "
                                r"fuse=(?:none|acknowledged) -->")
_RUN_URL_RE = re.compile(r"https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+/actions/runs/([0-9]+)(?:[/?#].*)?")


def is_actions_bot(login: Optional[str]) -> bool:
    """REST ``github-actions[bot]`` or GraphQL ``github-actions`` (case-insensitive, stripped)."""
    if not isinstance(login, str):
        return False
    name = login.strip().lower()
    if name.endswith("[bot]"):
        name = name[:-5]
    return name == ACTIONS_BOT


def _same_login(a: Optional[str], b: Optional[str]) -> bool:
    """GitHub logins compare case-insensitively."""
    if not (isinstance(a, str) and isinstance(b, str)) or not a.strip() or not b.strip():
        return False
    return a.strip().lower() == b.strip().lower()


def load_comments(raw: str) -> list[Any]:
    """The scripts' ``load_comments``: ``gh api --paginate`` text → one comment list."""
    raw = raw.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        idx, out = 0, []
        while idx < len(raw):
            while idx < len(raw) and raw[idx].isspace():
                idx += 1
            if idx >= len(raw):
                break
            obj, idx = decoder.raw_decode(raw, idx)
            if isinstance(obj, list):
                out.extend(obj)
            else:
                out.append(obj)
        return out
    return _flatten(data if isinstance(data, list) else [data])


def _flatten(comments: list[Any]) -> list[Any]:
    """An outer array of page arrays (``--slurp``) is read as its pages, as the scripts do."""
    if comments and all(isinstance(page, list) for page in comments):
        return [c for page in comments for c in page]
    return list(comments)


def _author(comment: Any) -> Optional[str]:
    if not isinstance(comment, dict):
        return None
    user = comment.get("user") or {}
    login = user.get("login") if isinstance(user, dict) else None
    return login if isinstance(login, str) else None


def _body(comment: dict[str, Any]) -> str:
    body = comment.get("body") or ""
    return body if isinstance(body, str) else ""


def _check_since(since: Optional[str]) -> Optional[str]:
    if since is None:
        return None
    if not isinstance(since, str) or _SINCE_RE.fullmatch(since) is None:
        raise ValueError(f"since must be UTC ISO8601 to the second (YYYY-MM-DDTHH:MM:SSZ); got {since!r}")
    return since


def _in_window(comment: dict[str, Any], since: Optional[str]) -> bool:
    """``created_at >= since`` by lexical compare (the scripts' rule); no since → always."""
    if since is None:
        return True
    created = comment.get("created_at")
    created = created.strip() if isinstance(created, str) else ""
    return bool(created) and created >= since


def _mcp_markers(family: str, sha: str) -> frozenset[str]:
    """The exact marker strings the reviewer MCP assembles for ``family`` + ``sha``."""
    if family.endswith("_SIGNOFF"):
        return frozenset(f"<!-- {family} sha={sha} verdict={v} fuse={f} -->"
                         for v in ("pass", "block") for f in ("none", "acknowledged"))
    return frozenset({f"<!-- {family} sha={sha} -->"})


def _suffix_last(d: dict[str, Any]) -> Optional[str]:
    suffix = d.get("suffix_markers") or []
    return suffix[-1] if d.get("footer_ok") and suffix else None


def served(comments: list[dict[str, Any]], *, reviewer: str, sha: str,
           since: Optional[str] = None) -> bool:
    """reviewer-posted.sh ``check`` over raw comments (``jane|drik|pm|coach``); ValueError on a
    bad reviewer or sha, exactly like the script's refusals."""
    if reviewer not in REVIEWER_FAMILIES:
        raise ValueError(f"reviewer must be jane, drik, pm or coach (got: {reviewer or 'empty'})")
    if not isinstance(sha, str) or _SHA_RE.fullmatch(sha) is None:
        raise ValueError(f"sha must be 40 hex chars (got: {sha or 'empty'})")
    since = _check_since(since)
    wanted = _mcp_markers(REVIEWER_FAMILIES[reviewer], sha)
    for comment in _flatten(list(comments)):
        if not isinstance(comment, dict) or not is_actions_bot(_author(comment)):
            continue
        if _suffix_last(_digest.body_digest(_body(comment))) not in wanted:
            continue
        if not _in_window(comment, since):
            continue
        return True
    return False


def _coach_pair(d: dict[str, Any]) -> Optional[str]:
    """The COACH_DONE sha when the digest's suffix ends ``[COACH_LOCK, COACH_DONE sha=S]``."""
    suffix = d.get("suffix_markers") or []
    if not d.get("footer_ok") or len(suffix) < 2 or suffix[-2] != COACH_LOCK_MARKER:
        return None
    m = _COACH_DONE_RE.fullmatch(suffix[-1])
    return m.group(1) if m else None


def coach_lock_served(comments: list[dict[str, Any]], *, since: Optional[str] = None) -> bool:
    """coach-lock-check.sh over raw comments."""
    since = _check_since(since)
    for comment in _flatten(list(comments)):
        if not isinstance(comment, dict) or not is_actions_bot(_author(comment)):
            continue
        if _coach_pair(_digest.body_digest(_body(comment))) is None:
            continue
        if not _in_window(comment, since):
            continue
        return True
    return False


def _epoch(ts: str) -> int:
    """Epoch seconds of a contract ``ts`` (``YYYY-MM-DDTHH:MM:SSZ``); ValueError otherwise."""
    if not isinstance(ts, str) or _SINCE_RE.fullmatch(ts) is None:
        raise ValueError(f"not a UTC timestamp to the second: {ts!r}")
    moment = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return int(moment.timestamp())


def is_edited(created_at: str, updated_at: Optional[str], edit_grace_seconds: int) -> bool:
    """``updated_at - created_at >= edit_grace_seconds`` (no ``updated_at`` → never edited)."""
    if not isinstance(edit_grace_seconds, int) or isinstance(edit_grace_seconds, bool) or edit_grace_seconds < 0:
        raise ValueError(f"edit_grace_seconds must be a non-negative int, got {edit_grace_seconds!r}")
    if updated_at is None:
        return False
    return _epoch(updated_at) - _epoch(created_at) >= edit_grace_seconds


def _rule_holds(kind: str, d: dict[str, Any], marker_sha: Optional[str]) -> bool:
    """The verified rule of one judged kind over the digest (author already checked)."""
    if kind == "review.signoff":
        last = _suffix_last(d)
        m = _SIGNOFF_SUFFIX_RE.fullmatch(last) if last is not None and d.get("suffix_ok") else None
        return m is not None and (marker_sha is None or m.group(2) == marker_sha)
    if kind == "triage.verdict":
        return (marker_sha is not None and _SHA_RE.fullmatch(marker_sha) is not None
                and _suffix_last(d) == f"<!-- PM_TRIAGE_DONE sha={marker_sha} -->")
    if kind == "coach.lock":
        done = _coach_pair(d)
        return done is not None and (marker_sha is None or done == marker_sha)
    if kind == "oracle.review":
        return d.get("head_marker") == ORACLE_MARKER and bool(d.get("footer_ok"))
    return False


def comment_tier(*, kind: str, login: Optional[str], owner_login: str, digest: dict[str, Any],
                 created_at: str, updated_at: Optional[str], edit_grace_seconds: int,
                 marker_sha: Optional[str] = None) -> tuple[str, str]:
    """``(tier, trust_basis)`` for a marker-bearing comment event — ``verified``/``claimed``/
    ``login``/``none`` (window is serving's)."""
    if kind not in JUDGED_KINDS:
        return ("login", "login") if login else ("none", "none")
    if not is_actions_bot(login):
        if _same_login(login, owner_login):
            return "claimed", "marker:owner-token"
        return "claimed", "marker:other-author"
    if not _rule_holds(kind, digest, marker_sha):
        return "claimed", "marker:no-suffix"
    if is_edited(created_at, updated_at, edit_grace_seconds):
        return "claimed", "marker:edited"
    return "verified", ("actions-bot+head-marker" if kind == "oracle.review" else "actions-bot+suffix")


def run_id_of(target_url: Optional[str]) -> Optional[int]:
    """The run id of an ``…/actions/runs/<id>[/…]`` URL, else ``None``."""
    if not isinstance(target_url, str):
        return None
    m = _RUN_URL_RE.fullmatch(target_url)
    return int(m.group(1)) if m else None


def status_tier(status: dict[str, Any], auto_review_run_ids: set[int], *,
                owner_login: Optional[str] = None) -> tuple[str, str]:
    """``(tier, basis)`` for a ``reviewer-signoff`` status (raw-pr@1 status shape).

    ``owner_login`` (optional) names the owner's own statuses ``marker:owner-token``;
    without it every non-bot creator is ``marker:other-author``.
    """
    creator = status.get("creator")
    creator = creator if isinstance(creator, str) and creator else None
    if creator is None:
        return "none", "none"
    if is_actions_bot(creator):
        run = run_id_of(status.get("target_url"))
        if run is not None and run in auto_review_run_ids:
            return "verified", "actions-status+receipt"
        return "login", "login"
    if _same_login(creator, owner_login):
        return "claimed", "marker:owner-token"
    return "claimed", "marker:other-author"


def selftest_cases() -> list:
    """Offline negatives for ``selftest.run``: planted human/cursor markers, no footer, sibling
    plant, case-folded marker, stale sha, edited post, coach pair order."""
    footer = _digest.FOOTER
    head, old = "0123456789abcdef0123456789abcdef01234567", "fedcba9876543210fedcba9876543210fedcba98"
    bot = {"login": "github-actions[bot]", "type": "Bot"}
    jane = f"<!-- JANE_SIGNOFF sha={head} verdict=pass fuse=none -->"
    drik = f"<!-- DRIK_SIGNOFF sha={head} verdict=block fuse=none -->"
    lock = f"x\n\n{COACH_LOCK_MARKER}\n\n<!-- COACH_DONE sha={head} -->\n\n{footer}"

    def post(body: str, user: Optional[dict[str, Any]] = None, created: str = "2026-10-05T12:00:01Z"):
        return {"body": body, "user": bot if user is None else user, "created_at": created}

    def mcp(marker: str, user: Optional[dict[str, Any]] = None):
        return post(f"Jane here.\n\n{marker}\n\n{footer}", user)

    def tier(body: str, *, login: str = "github-actions[bot]", updated: str = "2026-10-05T12:00:01Z"):
        return comment_tier(kind="review.signoff", login=login, owner_login="owner",
                            digest=_digest.body_digest(body), created_at="2026-10-05T12:00:01Z",
                            updated_at=updated, edit_grace_seconds=60, marker_sha=head)

    def refuses(fn) -> bool:
        try:
            fn()
        except ValueError:
            return True
        return False

    return [
        ("trust: a genuine MCP sign-off is served (positive control)",
         lambda: served([mcp(jane)], reviewer="jane", sha=head)),
        ("trust: a human-planted marker+footer is not served",
         lambda: not served([mcp(jane, {"login": "attacker"})], reviewer="jane", sha=head)),
        ("trust: a cursor[bot]-planted marker+footer is not served",
         lambda: not served([mcp(jane, {"login": "cursor[bot]", "type": "Bot"})], reviewer="jane", sha=head)),
        ("trust: an Actions-bot marker without the MCP footer is not served",
         lambda: not served([post(f"Jane.\n\n{jane}")], reviewer="jane", sha=head)),
        ("trust: a sibling plant (Drik suffix, Jane in the body) does not serve jane",
         lambda: not served([post(f"x\n\n{jane}\n\n{drik}\n\n{footer}")], reviewer="jane", sha=head)),
        ("trust: a case-folded marker is not an MCP post",
         lambda: not served([mcp(jane.lower())], reviewer="jane", sha=head)),
        ("trust: a sign-off for an older head is stale",
         lambda: not served([mcp(jane.replace(head, old))], reviewer="jane", sha=head)),
        ("trust: a lock from before --since is not served",
         lambda: not served([mcp(jane)], reviewer="jane", sha=head, since="2026-10-05T12:00:02Z")),
        ("trust: a typo'd reviewer and a short sha are refused",
         lambda: refuses(lambda: served([], reviewer="jan", sha=head))
         and refuses(lambda: served([], reviewer="jane", sha="abc123"))),
        ("trust: a verified sign-off tiers verified (positive control)",
         lambda: tier(f"Jane.\n\n{jane}\n\n{footer}") == ("verified", "actions-bot+suffix")),
        ("trust: an edited post drops to claimed (marker:edited)",
         lambda: tier(f"Jane.\n\n{jane}\n\n{footer}", updated="2026-10-05T12:01:01Z")
         == ("claimed", "marker:edited")),
        ("trust: an owner-token sign-off is claimed (marker:owner-token)",
         lambda: tier(f"Jane.\n\n{jane}\n\n{footer}", login="owner") == ("claimed", "marker:owner-token")),
        ("trust: the coach pair passes in order (positive control)",
         lambda: coach_lock_served([post(lock)])),
        ("trust: the coach pair in the wrong order is not a lock",
         lambda: not coach_lock_served([post(
             f"x\n\n<!-- COACH_DONE sha={head} -->\n\n{COACH_LOCK_MARKER}\n\n{footer}")])),
        ("trust: a Jane post that planted COACH_LOCK before its own sign-off is not a lock",
         lambda: not coach_lock_served([post(f"x\n\n{COACH_LOCK_MARKER}\n\n{jane}\n\n{footer}")])),
    ]
