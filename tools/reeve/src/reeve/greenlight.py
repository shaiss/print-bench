"""The greenlight loop's pure decision logic — the approval poll (issue #444).

Everything here is a pure function over shapes the GET seam
(``github.py``) already returns: parsed markers, an aggregated poll
outcome, the decision id a ledger row is keyed by, and the ledger
append that mirrors ``decide.yml`` byte for byte. No module in here
touches the network, so the whole poll semantics — the five cases the
issue's Done-when names, plus the documented tie-breaks — are testable
without a request ever leaving the process.

Three shapes this module owns:

* **The greenlight marker** — the wrapper's invisible first line
  ``<!-- reeve-greenlight v1 issue=<N> verdict=yes|no|route [arm=1] -->``.
  The optional ``arm=1`` attribute (#444) is the drafter's machine-readable
  "arm it for autonomy on approval" bit: stage 1 proved it is per-greenlight
  (#201 asked to be armed, #202 explicitly did not, both ``verdict=yes``),
  and the poll is deterministic code that cannot read prose safely.
* **The resolution marker** — the push-through's reply,
  ``<!-- reeve-greenlight v1 issue=<N> resolution=approved|overruled id=<id> -->``
  (the exact shape the stage-1 session-drafted resolution comments used).
  Its presence — pinned to this thread's ``issue=`` and posted by a trusted
  author, the same two tests a greenlight marker passes — means the
  greenlight was already consumed: the poll never re-reads a resolved or
  overruled greenlight's (stale) reactions.
* **The decision id** — from the thread's ``🚦 DECISION NEEDED — `<id>```
  comment/body (the gate's own capture format, the same string in
  ``decide.yml``, the ship/design skills and the provider-triage raiser),
  so a later human ``/decide <verb> <id>`` replaces the row this loop
  appended rather than growing a duplicate.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional

# The wrapper's greenlight first line. Attributes after `issue=` are
# order-tolerant so a future optional attribute needs no parser change:
# `verdict=` is required (a marker without one is a resolution comment or a
# forgery, never a greenlight), `arm=1` optional (#444).
GREENLIGHT_MARKER_RE = re.compile(
    r"^<!--\s*reeve-greenlight\s+v(\d+)\s+issue=(\d+)"
    r"((?:\s+[a-z_]+=[a-z0-9-]+)*)\s*-->$"
)
_ATTR_RE = re.compile(r"\s+([a-z_]+)=([a-z0-9-]+)")
_VERDICTS = ("yes", "no", "route")

# The push-through's own reply marker (and the stage-1 resolution comments'
# shape): `resolution=` marks a CONSUMED greenlight, `id=` carries the
# decision id the resolution was recorded under.
RESOLUTION_MARKER_RE = re.compile(
    r"^<!--\s*reeve-greenlight\s+v(\d+)\s+issue=(\d+)\s+"
    r"resolution=(approved|overruled)\s+id=([a-z0-9][a-z0-9-]*)\s*-->$"
)

# The gate's capture comment (docs/decision-gate.md §1) — the workflow
# raisers (oracle.yml, provider-triage) put the same line in the issue BODY.
# Kebase-case id per the gate's contract.
DECISION_ID_RE = re.compile(r"🚦\s*DECISION NEEDED\s+—\s+`([a-z0-9][a-z0-9-]*)`")

# decide.yml's OWN anchored command pattern, mirrored exactly (verb, optional
# kebab-case id). Mirroring matters: a bot-posted `/decide` with the comment
# tooling's attribution footer does NOT match this anchor — that is the
# stage-1 lesson this whole piece exists to not repeat — and the poll must
# agree with the workflow about what counts as a command. `status` is
# read-only and outranks nothing.
DECIDE_COMMAND_RE = re.compile(r"^/decide\s+(yes|no|status)(?:\s+([a-z0-9][a-z0-9-]*))?\s*$")

# Reaction content values: 👍 is `+1`, 👎 is `-1`.
APPROVE_REACTION = "+1"
OVERRULE_REACTION = "-1"

# The permission levels decide.yml treats as authorized — the
# `getCollaboratorPermissionLevel` values that may resolve a gate. Kept here
# (not only in the seam) so the aggregation's contract is readable next to
# its tests: the poll's callers filter reactions against this set BEFORE
# aggregating, because permission is a live per-user fact only the seam can
# read.
AUTHORIZED_PERMISSIONS = ("admin", "maintain", "write")

# The login the workflow's OWN token posts as. Both marker kinds the poll
# acts on are written through ``GITHUB_TOKEN`` — the drafter's wrapper (``gh
# issue comment`` under the step's ``GH_TOKEN``) and the push-through's
# resolution reply (``pushthrough.post_comment`` with the workflow token) —
# so a marker under this login is the loop's own, and nobody else can post
# as it. It is trusted by identity rather than by ``permission_of``: the
# collaborator-permission endpoint is defined for users, and an answer of
# ``none``/404 for the Actions bot would dead-letter every legitimate
# greenlight (fail-closed turned into fail-dead). An attended run posts as
# the human who ran it, whose real permission is what vouches for it.
WORKFLOW_BOT_LOGIN = "github-actions[bot]"

# Poll outcomes. `approve` pushes the verdict through; `overrule` parks with
# a reply; `wait` does nothing this run; `yield` steps aside for decide.yml.
OUTCOME_APPROVE = "approve"
OUTCOME_OVERRULE = "overrule"
OUTCOME_WAIT = "wait"
OUTCOME_YIELD = "yield"


def first_line(text: str) -> str:
    """The first non-blank line of ``text``, stripped (``""`` if none)."""
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def parse_greenlight_marker(line: str) -> Optional[dict[str, Any]]:
    """Parse one greenlight marker line, or ``None`` if it is not one.

    Returns ``{"version", "issue", "verdict", "arm"}`` — ``arm`` is the
    optional ``arm=1`` bit (#444). Unknown attributes are tolerated
    (forward-compatible) but a missing/unknown ``verdict`` parses as no
    greenlight: the wrapper always writes one, so a line without it is a
    resolution comment, a truncation or a forgery — never acted on.
    """
    match = GREENLIGHT_MARKER_RE.match((line or "").strip())
    if not match:
        return None
    attrs = dict(_ATTR_RE.findall(match.group(3)))
    verdict = attrs.get("verdict")
    if verdict not in _VERDICTS:
        return None
    return {
        "version": int(match.group(1)),
        "issue": int(match.group(2)),
        "verdict": verdict,
        "arm": attrs.get("arm") == "1",
    }


def parse_resolution_marker(line: str) -> Optional[dict[str, Any]]:
    """Parse one resolution marker line, or ``None`` if it is not one."""
    match = RESOLUTION_MARKER_RE.match((line or "").strip())
    if not match:
        return None
    return {
        "version": int(match.group(1)),
        "issue": int(match.group(2)),
        "resolution": match.group(3),
        "id": match.group(4),
    }


def marker_author_trusted(login: str, authorized: Callable[[str], bool]) -> bool:
    """Whether a marker posted under ``login`` is the loop's own.

    True for the workflow's own bot identity (:data:`WORKFLOW_BOT_LOGIN`,
    tested first so no permission lookup is ever spent on it) or for a
    login ``authorized`` vouches for — the driver's memoized
    :func:`github.permission_of` against :data:`AUTHORIZED_PERMISSIONS`,
    the same test a reaction passes, so an attended run's human-posted
    greenlight counts exactly when that human's 👍 would. An empty login
    is never trusted.
    """
    if not login:
        return False
    if login == WORKFLOW_BOT_LOGIN:
        return True
    return bool(authorized(login))


def find_current_greenlight(
    issue_number: int,
    comments: list[dict[str, Any]],
    trusted: Callable[[str], bool],
) -> dict[str, Any]:
    """The one live greenlight comment on a thread, with its parsed marker.

    A comment *is* a greenlight when its first non-blank line parses as a
    greenlight marker whose ``issue=`` matches the thread — the wrapper
    writes that self-referencing anchor, so a marker copied from another
    thread never reads as this thread's greenlight — **and** its author is
    one ``trusted`` vouches for (:func:`marker_author_trusted`: the
    workflow's own bot login, or a login with a real write-level
    permission). Anyone can comment on a public issue, so without the
    author test an untrusted commenter could paste a second marker and
    force ``ambiguous`` (suppressing the real greenlight for good), or
    paste a resolution marker and spend it as ``consumed``; a marker from
    an untrusted author is simply not a marker here. The trust test is
    injected, never performed, so this stays a pure function over the
    thread — the driver supplies the live permission read.

    Resolution markers are held to the same two tests — a trusted author
    and ``issue=`` pinned to this thread — so a resolution reply copied
    from another thread never spends this one's greenlight.

    Fail-closed on shape anomalies, because the loop's own wrapper
    guarantees at most one marker per thread, ever: zero greenlights →
    ``{"state": "none"}``; more than one → ``{"state": "ambiguous"}``
    (hand-crafted content from a trusted account — never resolved by this
    poll); any resolution marker → ``{"state": "consumed"}`` (already
    approved or overruled; re-polling its stale reactions must not
    re-resolve a re-parked decision). Only the clean single-live-marker
    case carries a verdict.
    """
    greenlights = []
    resolved = False
    for comment in comments:
        line = first_line(comment.get("body", ""))
        marker = parse_greenlight_marker(line)
        resolution = None if marker else parse_resolution_marker(line)
        if marker is None and resolution is None:
            continue  # not a marker at all — no lookup spent on its author
        if (marker or resolution)["issue"] != issue_number:
            continue  # pinned to another thread — never this one's
        if not trusted((comment.get("user") or {}).get("login", "")):
            continue  # an untrusted author's marker is not a marker
        if resolution is not None:
            resolved = True
        else:
            greenlights.append((comment, marker))
    if resolved:
        return {"state": "consumed"}
    if not greenlights:
        return {"state": "none"}
    if len(greenlights) > 1:
        return {"state": "ambiguous"}
    comment, marker = greenlights[0]
    return {
        "state": "live",
        "comment_id": comment.get("id"),
        "author": (comment.get("user") or {}).get("login", ""),
        "created_at": comment.get("created_at", ""),
        **marker,
    }


def decision_id_for(issue_number: int, body: str, comments: list[dict[str, Any]]) -> str:
    """The decision id a resolution on this thread must be recorded under.

    The thread's latest ``🚦 DECISION NEEDED — `<id>``` line (comment or
    issue body — the workflow raisers put it in the body, the skills in a
    comment) is the id the parking run chose; recording under it means a
    later human ``/decide <verb> <id>`` replaces this row rather than
    duplicating it. A thread with no 🚦 line (a hand-parked label) falls
    back to ``greenlight-<n>``: unique per thread, never colliding with a
    human-chosen id, and mechanically identical to the ledger.
    """
    ids = DECISION_ID_RE.findall(body or "")
    for comment in comments:
        ids.extend(DECISION_ID_RE.findall(comment.get("body", "")))
    return ids[-1] if ids else f"greenlight-{issue_number}"


def decide_candidates(comments: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Every ``/decide yes|no <id>`` comment on a thread, oldest first.

    The body is matched against decide.yml's own anchored pattern after a
    trim — a command the workflow would not parse (wrong shape, or a
    bot-posted one carrying the comment tooling's attribution footer, the
    stage-1 neutralization) outranks nothing. Two further gates mirror what
    decide.yml actually honours, because yielding to a command it refuses
    would park the thread against this loop forever: ``status`` is read-only
    and excluded, and **a yes/no without a decision id is excluded too**
    (decide.yml's own refusal: "needs a decision id" — the regex allows the
    omission, the workflow does not). The poll's driver keeps only the
    **newest candidate whose author's real permission is one of
    :data:`AUTHORIZED_PERMISSIONS`** (the same check decide.yml makes before
    honouring a command, so a read-only user's `/decide` — which decide.yml
    itself refuses — cannot park a thread against this loop either): the
    gate's last-writer-wins.
    """
    candidates: list[dict[str, str]] = []
    for comment in comments:
        author = (comment.get("user") or {}).get("login", "")
        match = DECIDE_COMMAND_RE.match((comment.get("body") or "").strip())
        if not match or match.group(1) == "status" or not match.group(2):
            continue
        candidates.append({"verb": match.group(1), "id": match.group(2), "author": author})
    return candidates


def poll_outcome(
    greenlight: dict[str, Any],
    approvers: list[str],
    overrulers: list[str],
    decide: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Aggregate one live greenlight's permission-checked signals.

    ``approvers``/``overrulers`` are the logins whose 👍/👎 counted — the
    seam has already filtered both by :data:`AUTHORIZED_PERMISSIONS`;
    this function never sees a read-only reaction. ``decide`` is the
    newest authorized :func:`decide_candidates` entry when a human command
    exists, else ``None``.

    Precedence, in order (each documented, each testable):

    1. **An explicit ``/decide`` always outranks a reaction** — yield to
       decide.yml. If its label flip already landed the thread is not
       parked and this poll never sees it; if it did not (the workflow
       failed, or the command was neutralized by a footer) a re-run heals
       it. This loop never re-applies a human's typed command — parsing it
       twice is a second place to get authorization wrong.
    2. **A route sets no gate verdict** — the wrapper's own footer says a
       reaction on a routing note approves nothing, so reactions on it are
       ignored entirely.
    3. **An authorized 👎 overrules, even against a 👍** — a contested
       greenlight stays parked (fail-closed: not resolving is the
       recoverable direction; a human ``/decide`` breaks the tie).
    4. **An authorized 👍 approves** — the greenlight's own verdict is what
       resolves: ``yes`` → approved, ``no`` → rejected.
    5. Otherwise keep waiting — and never a duplicate greenlight while one
       is live (the wrapper already refuses; this poll adds nothing).
    """
    if decide is not None:
        return {
            "outcome": OUTCOME_YIELD,
            "reason": (
                f"explicit /decide {decide['verb']} by {decide['author']} "
                "outranks reactions — left to decide.yml"
            ),
        }
    if greenlight["verdict"] == "route":
        return {
            "outcome": OUTCOME_WAIT,
            "reason": "a routing note sets no gate verdict; a reaction approves nothing",
        }
    if overrulers:
        return {"outcome": OUTCOME_OVERRULE, "overrulers": overrulers, "reason": "👎 overrule"}
    if approvers:
        return {
            "outcome": OUTCOME_APPROVE,
            "verdict": greenlight["verdict"],
            "arm": bool(greenlight.get("arm")),
            "approvers": approvers,
            "reason": "👍 approval",
        }
    return {"outcome": OUTCOME_WAIT, "reason": "no qualifying reactions yet"}


# ---------------------------------------------------------------------------
# The ledger append — decide.yml's own algorithm, mirrored line for line.
# ---------------------------------------------------------------------------

LEDGER_HEADER_PREFIX = "#"


def ledger_row(decision_id: str, verdict: str, issue_number: int, login: str, when: str) -> str:
    """One ledger row: ``<id> | approved|rejected | #<issue> | <login> | <iso8601>``.

    The exact shape ``decide.yml`` writes (its ``row`` join), so a row from
    this loop is indistinguishable from a row from the command — including
    to ``/decide status`` and to a later append-or-replace.
    """
    return " | ".join([decision_id, verdict, f"#{issue_number}", login, when])


def append_ledger_row(existing: str, decision_id: str, row: str) -> str:
    """Append-or-replace ``decision_id``'s row in the ledger's text.

    Mirrors decide.yml's ``Resolve the decision`` step exactly: keep the
    ``#`` header lines, keep the rows whose id differs, append the new row,
    trailing newline. Idempotent by id — re-deciding replaces, never
    duplicates — which is what makes the round-trip through decide.yml's
    parser a property of the bytes, not of the caller's good behaviour.
    """
    lines = (existing or "").split("\n")
    header = [line for line in lines if line.startswith(LEDGER_HEADER_PREFIX)]
    kept = [
        line
        for line in lines
        if line.strip()
        and not line.startswith(LEDGER_HEADER_PREFIX)
        and line.split("|")[0].strip() != decision_id
    ]
    return "\n".join(header + kept + [row]) + "\n"


def parse_ledger(text: str) -> list[dict[str, str]]:
    """Read ledger rows the way decide.yml does — the round-trip proof.

    decide.yml's reader (its ``status`` dump and its append-or-replace
    filter) splits on newlines, keeps non-``#`` non-blank lines, and takes
    a row's id as everything before the first ``|``, trimmed. This is that
    parser in Python: a row this loop appended must come back out as the
    same five fields, and a row decide.yml appends for the same id must
    replace it — one source of shape, two writers.
    """
    rows = []
    for line in (text or "").split("\n"):
        line = line.strip()
        if not line or line.startswith(LEDGER_HEADER_PREFIX):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) == 5:
            rows.append(
                {"id": parts[0], "verdict": parts[1], "issue": parts[2],
                 "login": parts[3], "when": parts[4]}
            )
    return rows
