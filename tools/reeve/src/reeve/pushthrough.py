"""The greenlight loop's ONE write seam — the push-through (issue #444).

An approved greenlight is a routing instruction, not code: this module
applies the **same sequence ``decide.yml`` applies** for a human's
``/decide`` — the fail-closed label flip, the ledger append, and (where
the greenlight's marker carried ``arm=1``) the ``autonomy-ok`` arming the
existing backlog burn / design run pick up — never a posted ``/decide``
comment (the stage-1 lesson, observed live on #201/#202: the comment
tooling appends an attribution footer and decide.yml anchors on a bare
command, so a bot-posted command is silently neutralized while the run
reports success).

This is deliberately the **only module in the reeve package that performs
an HTTP write verb** — the confined seam exemption the package's
no-write-verb rule gains for the greenlight loop (the backlog groomer's
``github.py``-shape precedent the parent issue names):
``tests/test_detectors.py`` still asserts no write verb appears anywhere
else, and confines them here. Reads stay in ``github.py`` (the GET seam);
the pure decision logic stays in ``greenlight.py``.

Two tokens, on purpose:

* ``token`` — the workflow's ambient ``GITHUB_TOKEN`` (``issues: write``):
  labels and comments. A token-scoped label flip triggers no CI, which is
  right for the verdict half.
* ``pat`` — ``REGEN_TOKEN``, the fine-grained PAT: the ledger commit to the
  **default branch** authenticates with the PAT, never the workflow token,
  exactly as the ``regen`` job commits its artifacts (the precedent this
  piece inherits). Two reasons, both observed in this repo: the
  default-branch ruleset refuses a push from the Actions bot (the GH013
  lesson that pushed telemetry onto its own data branch — with the
  workflow token, every run's ledger append would be refused, stranding
  the loop's audit half), and a PAT-authored commit re-triggers CI so the
  ledger change lands verified by the same gates everything else is. The
  workflow therefore needs **no permission wider than its present
  ``issues: write``** — the ledger commit is not made with the workflow
  token. When the PAT is absent the append is skipped and reported (the
  label still carries the verdict — decide.yml's documented degradation).
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

from . import greenlight, github

_TIMEOUT_S = 30

LEDGER_PATH = ".github/decisions/ledger.conf"

# The gate's labels, mirrored from decide.yml's own ensure-label calls (and
# the repo's existing autonomy-ok), so this loop's writes are
# indistinguishable from the command's: created on demand, idempotent.
_VERDICT_LABELS = {
    "decision-approved": ("0e8a16", "A /decide human decision resolved yes"),
    "decision-rejected": ("b60205", "A /decide human decision resolved no"),
}
_AUTONOMY_LABEL = "autonomy-ok"
_AUTONOMY_SPEC = ("0e8a16", "Opt-in: eligible for the scheduled backlog-burn /ship-issue routine")


class PushFailed(RuntimeError):
    """The fail-closed label step failed — nothing was recorded."""


def _write(url: str, token: str, method: str, payload: Optional[dict[str, Any]]) -> dict[str, Any]:
    """One HTTP write; returns the parsed body (``{}`` for an empty one)."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "print-bench-reeve",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
        body = resp.read()
    return json.loads(body) if body else {}


def ensure_label(repo: str, token: str, name: str, color: str, description: str) -> None:
    """Create ``name`` if absent (decide.yml's ensureLabel, idempotent)."""
    try:
        github._get(f"{github.API_ROOT}/repos/{repo}/labels/{name}", token)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        _write(
            f"{github.API_ROOT}/repos/{repo}/labels", token, "POST",
            {"name": name, "color": color, "description": description},
        )


def add_labels(repo: str, token: str, issue_number: int, labels: list[str]) -> None:
    _write(
        f"{github.API_ROOT}/repos/{repo}/issues/{issue_number}/labels", token, "POST",
        {"labels": labels},
    )


def remove_label(repo: str, token: str, issue_number: int, name: str) -> None:
    """Best-effort removal — an absent label 404s, which is fine."""
    try:
        _write(
            f"{github.API_ROOT}/repos/{repo}/issues/{issue_number}/labels/{name}",
            token, "DELETE", None,
        )
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise


def post_comment(repo: str, token: str, issue_number: int, body: str) -> None:
    _write(
        f"{github.API_ROOT}/repos/{repo}/issues/{issue_number}/comments", token, "POST",
        {"body": body},
    )


def _get_ledger(repo: str, token: str, branch: str) -> tuple[str, Optional[str]]:
    """The ledger's current text and blob sha (``("", None)`` when absent)."""
    try:
        body, _ = github._get(
            f"{github.API_ROOT}/repos/{repo}/contents/{LEDGER_PATH}?ref={branch}", token
        )
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        return "", None  # first-ever decision
    return base64.b64decode(body["content"]).decode(), body["sha"]


def commit_ledger(
    repo: str, pat: str, branch: str, decision_id: str, row: str, message: str
) -> None:
    """Append-or-replace ``decision_id``'s row via the Contents API (PAT).

    decide.yml's own commit algorithm: read + sha, keep header and other-id
    rows, append this row, PUT; on a 409 sha race refetch and retry (twice).
    """
    for attempt in range(3):
        existing, sha = _get_ledger(repo, pat, branch)
        content = greenlight.append_ledger_row(existing, decision_id, row)
        try:
            _write(
                f"{github.API_ROOT}/repos/{repo}/contents/{LEDGER_PATH}", pat, "PUT",
                {
                    "path": LEDGER_PATH,
                    "branch": branch,
                    "sha": sha,
                    "message": message,
                    "content": base64.b64encode(content.encode()).decode(),
                },
            )
            return
        except urllib.error.HTTPError as exc:
            if exc.code == 409 and attempt < 2:
                continue
            raise


def _iso_now(now: Optional[datetime]) -> str:
    """``now`` as decide.yml's ``new Date().toISOString()`` shape."""
    stamp = now or datetime.now(timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.") + f"{stamp.microsecond // 1000:03d}Z"


def _default_branch(repo: str, token: str) -> str:
    body, _ = github._get(f"{github.API_ROOT}/repos/{repo}", token)
    return body["default_branch"]


# ---------------------------------------------------------------------------
# The push-through itself — decide.yml's sequence, label-first.
# ---------------------------------------------------------------------------

def push_approval(
    repo: str,
    token: str,
    pat: str,
    issue_number: int,
    greenlight_info: dict[str, Any],
    decision_id: str,
    approvers: list[str],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Apply an approved greenlight: labels first (fail closed), then the rest.

    Order, mirroring decide.yml's ``Resolve the decision``:

    1. ensure both verdict labels exist (idempotent);
    2. add the verdict label — **the authoritative state, and the step that
       may fail the whole push**: on failure nothing else is recorded and
       ``needs-decision`` stays in place, so the issue remains parked and
       the next run retries (never un-paused with no verdict, never a
       ledger row claiming a decision the label never received);
    3. best-effort remove the opposite verdict label and ``needs-decision``
       (an absent label 404s; a failed removal just leaves the pause on —
       the recoverable direction);
    4. where the greenlight's marker carried ``arm=1`` and the verdict is
       ``yes``: apply ``autonomy-ok`` so the existing backlog burn / design
       run picks the work up (pull-based resume, no new executor). Never
       armed without an approved greenlight — structurally: this is the
       only code path that can add it. A failure here is reported, not
       fatal: the verdict stands and arming is routing, not authority;
    5. append the ledger row via the PAT (skipped + reported when the PAT
       is absent);
    6. the resolution reply — the human-visible record, posted last so it
       can report what actually landed.
    """
    verdict = greenlight_info["verdict"]
    want = "decision-approved" if verdict == "yes" else "decision-rejected"
    other = "decision-rejected" if verdict == "yes" else "decision-approved"
    # The ledger row carries the WORD decide.yml writes (`approved`/
    # `rejected` — its VERDICT), never the label name: the row must be
    # indistinguishable from one the command appended, which is the whole
    # point of /decide status and of append-or-replace by id.
    verdict_word = "approved" if verdict == "yes" else "rejected"
    when = _iso_now(now)
    notes: list[str] = []

    # Steps 1-2 — the fail-closed core, one try: creating the labels and
    # applying the verdict are the steps whose failure must leave NOTHING
    # recorded (no removals, no arming, no ledger row, no reply).
    try:
        for name, (color, description) in _VERDICT_LABELS.items():
            ensure_label(repo, token, name, color, description)
        add_labels(repo, token, issue_number, [want])
    except (urllib.error.HTTPError, OSError) as exc:
        raise PushFailed(f"could not apply {want} on #{issue_number}: {exc}") from exc
    # Step 3 — best-effort removals: an absent label 404s (tolerated), and a
    # failed removal only leaves the pause on — the recoverable direction,
    # reported as a note on the reply rather than fatal.
    for name in (other, github.NEEDS_DECISION_LABEL):
        try:
            remove_label(repo, token, issue_number, name)
        except (urllib.error.HTTPError, OSError) as exc:
            notes.append(f"could not remove `{name}` ({exc}) — the `{want}` label carries the verdict; lift `{name}` by hand")

    armed = False
    if greenlight_info.get("arm") and verdict == "yes":
        try:
            ensure_label(repo, token, _AUTONOMY_LABEL, *_AUTONOMY_SPEC)
            add_labels(repo, token, issue_number, [_AUTONOMY_LABEL])
            armed = True
        except (urllib.error.HTTPError, OSError) as exc:
            notes.append(f"arming failed ({exc}) — apply `{_AUTONOMY_LABEL}` by hand to route it to the backlog burn")

    ledger = None
    if pat:
        row = greenlight.ledger_row(decision_id, verdict_word, issue_number, approvers[0], when)
        try:
            commit_ledger(
                repo, pat, _default_branch(repo, token), decision_id, row,
                f"greenlight: {decision_id} -> {verdict_word} (#{issue_number})",
            )
            ledger = True
        except (urllib.error.HTTPError, OSError) as exc:
            ledger = False
            notes.append(f"ledger append failed ({exc}) — the `{want}` label carries the verdict; add the row to `{LEDGER_PATH}` by hand if you want the audit trail")
    else:
        ledger = False
        notes.append("REGEN_TOKEN is not set — ledger append skipped; the label carries the verdict")

    arming_text = (
        " and `autonomy-ok` applied — the backlog burn picks this up on its next firing"
        if armed else
        " (not armed: the greenlight did not recommend arming)"
    )
    ledger_text = (
        f", ledger row appended under `{decision_id}`."
        if ledger else
        ". The ledger append did not complete — the label is the authoritative verdict."
    )
    reply = [
        f"<!-- reeve-greenlight v1 issue={issue_number} resolution=approved id={decision_id} -->",
        "",
        f"✅ **Approved by 👍 ({approvers[0]}) — recorded {want}**",
        "",
        "Applied the `/decide` sequence via the API (never a posted command): "
        f"`{want}` added first, `needs-decision` lifted{arming_text}{ledger_text}",
    ]
    for note in notes:
        reply.append(f"- {note}")
    reply.append("")
    reply.append("— the reeve greenlight loop (#444), from the `greenlight` job in `.github/workflows/reeve.yml`")
    try:
        post_comment(repo, token, issue_number, "\n".join(reply))
    except (urllib.error.HTTPError, OSError) as exc:
        notes.append(f"resolution reply failed ({exc})")

    return {
        "outcome": "approved", "label": want, "armed": armed,
        "ledger": ledger, "notes": notes,
    }


def push_overrule(
    repo: str,
    token: str,
    issue_number: int,
    decision_id: str,
    overrulers: list[str],
) -> dict[str, Any]:
    """Record an overrule: one reply, and the gate stays parked.

    Nothing else is written — no label changes, no ledger row (the decision
    is still pending; the ledger records decisions, and an overruled
    recommendation is not one). ``needs-decision`` stays, and the thread's
    marker means no new greenlight is drafted on it, so the next move is a
    human's: ``/decide``, or handing a taste call to its design PM.
    """
    body = "\n".join([
        f"<!-- reeve-greenlight v1 issue={issue_number} resolution=overruled id={decision_id} -->",
        "",
        f"👎 **Overruled by {overrulers[0]}** — this greenlight's recommendation is rejected by the owner's reaction.",
        "",
        "The gate stays parked (`needs-decision` remains). Resolve it with a",
        f"`/decide yes {decision_id}` or `/decide no {decision_id}` comment, or hand it to the",
        "design PM if it is a taste call. No new greenlight will be drafted on this thread.",
        "",
        "— the reeve greenlight loop (#444), from the `greenlight` job in `.github/workflows/reeve.yml`",
    ])
    post_comment(repo, token, issue_number, body)
    return {"outcome": "overruled", "overrulers": overrulers, "notes": []}


# ---------------------------------------------------------------------------
# The poll driver — the NEXT run reading its own prior greenlights.
# ---------------------------------------------------------------------------

def run_poll(
    repo: str, token: str, pat: str, now: Optional[datetime] = None
) -> list[dict[str, Any]]:
    """Poll every open parked decision's greenlight; push what is approved.

    Per issue: classify the thread's greenlight (live / none / consumed /
    ambiguous — ``greenlight.find_current_greenlight``), read the live one's
    reactions through the GET seam, keep only reactions whose author's real
    permission is one of ``greenlight.AUTHORIZED_PERMISSIONS``, let an
    explicit authorized ``/decide`` comment outrank everything, then apply
    the outcome. One issue failing never stops the rest — each result
    carries its own error, and the fail-closed order means a partial
    failure leaves the gate parked for the next run to retry. That is also
    why a mid-read failure (a bad permission payload, a network blip) is
    reported rather than raised: the issue simply waits this run, which is
    the fail-closed direction for a gate.
    """
    results: list[dict[str, Any]] = []
    permissions: dict[str, str] = {}

    def _authorized(login: str) -> bool:
        if login not in permissions:
            permissions[login] = github.permission_of(repo, token, login)
        return permissions[login] in greenlight.AUTHORIZED_PERMISSIONS

    for thread in github.gather_greenlight_poll(repo, token):
        number = thread["number"]
        try:
            info = greenlight.find_current_greenlight(number, thread["comments"])
            if info["state"] != "live":
                results.append({"number": number, "outcome": "wait",
                                "reason": f"greenlight state: {info['state']}"})
                continue

            decision_id = greenlight.decision_id_for(number, thread["body"], thread["comments"])

            # An explicit /decide by an authorized human outranks any reaction:
            # newest authorized command wins (the gate's last-writer-wins).
            decide = None
            for candidate in reversed(greenlight.decide_candidates(thread["comments"])):
                if _authorized(candidate["author"]):
                    decide = candidate
                    break

            approvers: list[str] = []
            overrulers: list[str] = []
            reactions = (
                github.list_reactions(repo, token, info["comment_id"])
                if info.get("comment_id") is not None
                else []
            )
            for reaction in reactions:
                content = reaction.get("content", "")
                if content not in (greenlight.APPROVE_REACTION, greenlight.OVERRULE_REACTION):
                    continue
                login = (reaction.get("user") or {}).get("login", "")
                if _authorized(login):
                    (approvers if content == greenlight.APPROVE_REACTION else overrulers).append(login)

            polled = greenlight.poll_outcome(info, approvers, overrulers, decide)
            if polled["outcome"] == greenlight.OUTCOME_APPROVE:
                results.append({
                    "number": number,
                    **push_approval(
                        repo, token, pat, number, info, decision_id, polled["approvers"], now
                    ),
                })
            elif polled["outcome"] == greenlight.OUTCOME_OVERRULE:
                results.append({
                    "number": number,
                    **push_overrule(repo, token, number, decision_id, polled["overrulers"]),
                })
            else:  # wait or yield — nothing this run, by design
                results.append({"number": number, **polled})
        except PushFailed as exc:
            results.append({"number": number, "outcome": "error", "reason": str(exc)})
        except Exception as exc:  # noqa: BLE001 — per-issue isolation is the driver's contract
            results.append({"number": number, "outcome": "error",
                            "reason": f"{type(exc).__name__}: {exc}"})
    return results
