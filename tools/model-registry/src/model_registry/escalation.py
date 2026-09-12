"""Reason-keyed, cross-chain dedup for provider-failure escalations (issue #550).

`classify` reduces an exhausted chain to a finer **reason**; this module is what
happens next on the human-fixable ones.  The pre-#550 rule deduped the HITL
escalation **per chain** — marker ``<!-- provider-escalation:<chain> -->``,
decision id ``provider-<chain>`` — which was correct while one routine could be
dark alone, but #544 gave every routine a cross-provider tail, so a chain only
exhausts when *every* provider in it failed.  The case that fans out is then the
dual-provider outage, and it accrued one ``needs-decision`` issue per chain (up
to fifteen) each needing its own ``/decide`` — all restating one fact: fund the
account / rotate the key.  The 2026-09-04 quota day filed seven in seventeen
hours before the andon cord existed to mute them.

The rule here keys the dedup on the **reason** instead: marker
``<!-- provider-escalation:<reason> -->``, decision id ``provider-<reason>``,
one open issue per reason shared by every chain that exhausts with it.  A newly
exhausted chain *joins* the open issue for its reason (a per-chain detail line
accumulates in the body, so a human still sees which routines are affected and
what each walked), and one ``/decide`` resolves the whole set.  When a human
resolves the issue (/decide clears the label, or the issue is closed) the next
exhaustion is free to file a fresh one — same re-escalation semantics as before,
one level up.

Both escalation surfaces call this module (AC: they must not drift apart): the
shared `.github/actions/provider-triage` composite action and `oracle.yml`'s
own exhaustion leg, which had a private ``oracle-provider-escalation:<chain>``
family of its own.  They now share the marker family too, so the Oracle's
escalation joins the same per-reason issue a routine would — and Reeve's
greenlight-select skip, which matches the ``<!-- provider-escalation:`` prefix,
now covers the Oracle's threads as well.

``_request`` is this module's single network seam (the GitHub API — smoke.py
owns the provider-endpoint seam); the tests replace it to exercise every path
without a token.  The token is read from an env var *named* on the command
line, never passed as a value, so it cannot leak into argv or a ps listing.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Sequence

from .registry import Registry

API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"

# The decision-gate label (docs/decision-gate.md) — unspoofable verdict state.
DECISION_LABEL = "needs-decision"

# The marker family: reason-keyed since #550. Mirrored as a *prefix* by
# tools/reeve (PROVIDER_ESCALATION_MARKER) so its greenlight-select skip keeps
# matching; keep the family shaped `<!-- provider-escalation:<token> -->`.
MARKER_PREFIX = "<!-- provider-escalation:"

# The per-chain membership record inside a shared issue's body — NOT a dedup
# key (the reason marker is): it exists so a re-exhaustion of a chain that
# already joined does not append a duplicate detail line every run.
AFFECTED_PREFIX = "<!-- affected:"

# Only these reasons reach the escalation (class `needs-human` is derived from
# exactly this set, so a caller whose `if:` gated on the class cannot name
# anything else — unless the two drifted, which the guard below fires on).
NEEDS_HUMAN_REASONS = ("billing", "quota", "auth", "no-key")

# The reason IS the button a human pushes — say which, and where.
REMEDIES = {
    "billing": "The provider account is **out of credit** (a billing/balance "
               "rejection). **Fund the account**, then confirm.",
    "quota": "The provider account is **out of tokens for the period** (a "
             "quota / spend-cap rejection). **Raise the cap or wait for the "
             "reset**, then confirm.",
    "auth": "The API key is **invalid, expired, or revoked** (an auth "
            "rejection). **Rotate the key**, then confirm.",
    "no-key": "No provider secret is configured for this chain at all. "
              "**Set the key**, then confirm.",
}

# The fixed line the affected-chains block ends on — new detail lines are
# inserted directly before it, keeping the postamble (yes/no, context, resolve
# line) last where a resolver reads it.
_POSTAMBLE_ANCHOR = ("Until it is resolved the affected chains' agentic runs "
                     "cannot produce output.")


def marker_for(reason: str) -> str:
    """The dedup marker for a reason: ``<!-- provider-escalation:<reason> -->``."""
    return f"{MARKER_PREFIX}{reason} -->"


def decision_id_for(reason: str) -> str:
    """The decision-gate id for a reason: one ``/decide`` resolves the set."""
    return f"provider-{reason}"


def affected_marker(chain: str) -> str:
    """The membership marker recording that ``chain`` already joined an issue."""
    return f"{AFFECTED_PREFIX}{chain} -->"


def remediation_for(reason: str) -> str:
    """The reason-tailored remediation, or ``ValueError`` for a non-escalating
    reason — the guard that keeps this leg needs-human-only."""
    if reason not in NEEDS_HUMAN_REASONS:
        raise ValueError(
            f"reason {reason!r} cannot escalate — only the needs-human reasons "
            f"{list(NEEDS_HUMAN_REASONS)} file a decision (the class is derived "
            "from the reason, so a caller gating on `class == 'needs-human` "
            "cannot reach this; if it did, the two drifted)")
    return REMEDIES[reason]


def _walk_of(providers: Sequence[str]) -> str:
    """The deduplicated, in-order provider names a chain walked."""
    ordered: list[str] = []
    for provider in providers:
        if provider not in ordered:
            ordered.append(provider)
    return " -> ".join(ordered)


def detail_line(context_label: str, chain: str, providers: Sequence[str],
                when: str) -> str:
    """One chain's entry in a shared issue's affected-chains block."""
    return (f"- {context_label} — registry chain `{chain}`, walked "
            f"{_walk_of(providers)}, first seen {when} {affected_marker(chain)}")


def render_body(reason: str, details: Sequence[str]) -> str:
    """A fresh shared escalation issue body (the file path)."""
    did = decision_id_for(reason)
    return "\n".join([
        marker_for(reason),
        f"🚦 DECISION NEEDED — `{did}`",
        "",
        "A registry chain failed on **every** link, and the model-registry "
        "classifier read the cause as "
        f"**{reason}** — an account/config problem CI cannot fix, not a "
        "transient outage or a bad model id.",
        "",
        remediation_for(reason),
        "",
        "**Affected chains** — this escalation is shared by every chain that "
        f"exhausts with reason **{reason}**, so one `/decide` resolves the "
        "whole set (issue #550):",
        "",
        *details,
        "",
        _POSTAMBLE_ANCHOR,
        "",
        "**yes** → the account/key is funded / rotated / configured and "
        "working. Confirm by dispatching `model-smoke.yml` for an affected "
        "chain, then resolve.",
        "**no**  → accept these chains staying dark for now; this closes the "
        "escalation without a code change.",
        "",
        "**Context:** classifier reason "
        f"`{reason}`. The registry itself is correct — this is an account/key "
        "problem (issue #347; the shared, reason-keyed escalation is #550).",
        "",
        f"Resolve with `/decide yes {did}` or `/decide no {did}`.",
    ])


def _with_detail(body: str, line: str) -> str:
    """The join path's body update: one more affected-chain line, inserted
    directly before the postamble anchor (or appended at the end when a human
    rearranged the body — the anchor is gone, so line order is theirs)."""
    if _POSTAMBLE_ANCHOR in body:
        head, _, tail = body.partition(_POSTAMBLE_ANCHOR)
        head = head.rstrip("\n") + "\n"
        return head + line + "\n\n" + _POSTAMBLE_ANCHOR + tail
    return body.rstrip("\n") + "\n" + line + "\n"


@dataclass(frozen=True)
class Plan:
    """What the escalation surface should write, decided before any write.

    action   ``file``    no open issue carries the reason's marker — file one
                        (``title`` + ``body`` set, ``number`` None)
              ``join``   an open issue carries the marker but not this chain's
                        membership marker — accumulate the detail line
                        (``number`` + updated ``body`` set)
              ``already``the chain is on the open issue — write nothing
    notice   the ``::warning::`` line the caller prints either way, so the run
             log always names the escalation a human should read
    """

    action: str
    number: Optional[int] = None
    title: Optional[str] = None
    body: Optional[str] = None
    notice: str = ""


def plan_escalation(reason: str, chain: str, context_label: str,
                    providers: Sequence[str], when: str,
                    open_issues: Sequence[Mapping[str, Any]]) -> Plan:
    """Decide file / join / already from a simulated-or-live open-issue list.

    Pure: every caller (the CLI live path, the tests) supplies the same shaped
    list — ``number``, ``html_url`` and ``body`` per open ``needs-decision``
    issue — and gets back exactly the write to perform.
    """
    remediation_for(reason)  # the guard: only needs-human reasons escalate
    marker = marker_for(reason)
    existing = next(
        (i for i in open_issues if marker in (i.get("body") or "")), None)
    line = detail_line(context_label, chain, providers, when)

    if existing is None:
        return Plan(
            action="file",
            title=f"🚦 Provider unusable: {reason}",
            body=render_body(reason, [line]),
            notice=f"chain {chain} exhausted ({reason}) with no open "
                   f"escalation — filing the shared issue",
        )
    url = existing.get("html_url") or f"#{existing.get('number')}"
    if affected_marker(chain) in (existing.get("body") or ""):
        return Plan(
            action="already", number=existing.get("number"),
            notice=f"chain {chain} still unusable ({reason}) — already on the "
                   f"open escalation {url}, not writing again",
        )
    return Plan(
        action="join", number=existing.get("number"),
        body=_with_detail(existing.get("body") or "", line),
        notice=f"chain {chain} exhausted ({reason}) — joining the open "
               f"escalation {url} (one /decide resolves every chain on it)",
    )


# ── the live half ────────────────────────────────────────────────────────────
#
# One urllib seam for every GitHub call (the andon/growth discipline): the
# tests replace `_request` and the planning above stays the only logic.

_Request = Callable[[str, str, str, Optional[Mapping[str, Any]]],
                    tuple[int, Any, Mapping[str, str]]]


def _request(method: str, url: str, token: str,
             payload: Optional[Mapping[str, Any]] = None
             ) -> tuple[int, Any, Mapping[str, str]]:
    """One GitHub API call: ``(status, parsed body, headers)``.

    HTTP error statuses are returned, not raised — the callers branch on them
    (a 404 on the label GET is the create-on-demand path, not an exception).
    Only transport failures raise, which is a red, not a degrade: today's
    octokit step reddened the job on an API error too.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else None), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = body[:300]
        return exc.code, parsed, dict(exc.headers or {})


def _api_error(what: str, status: int, body: Any) -> str:
    detail = ""
    if isinstance(body, Mapping):
        detail = str(body.get("message") or "")
    elif body:
        detail = str(body)
    return f"{what}: GitHub API {status}" + (f" — {detail}" if detail else "")


def _ensure_label(gh: _Request, repo: str, token: str) -> Optional[str]:
    """docs/decision-gate.md's ensure-label idiom: create on demand, tolerate
    the race with a sibling run. Returns an error string, or None on success."""
    status, body, _ = gh("GET",
                         f"{API_BASE}/repos/{repo}/labels/{DECISION_LABEL}",
                         token)
    if status == 200:
        return None
    if status != 404:
        return _api_error("could not check the needs-decision label", status, body)
    status, body, _ = gh("POST", f"{API_BASE}/repos/{repo}/labels", token,
                         {"name": DECISION_LABEL, "color": "D93F0B",
                          "description": "A human decision is required before "
                                         "an agentic run can proceed"})
    if status not in (201, 422):  # 422 = raced: another run created it first
        return _api_error("could not create the needs-decision label", status, body)
    return None


def _open_issues(gh: _Request, repo: str, token: str
                 ) -> tuple[Optional[list[dict[str, Any]]], Optional[str]]:
    """Every open issue carrying the decision label, paginated."""
    issues: list[dict[str, Any]] = []
    page = 1
    while True:
        status, body, _ = gh(
            "GET",
            f"{API_BASE}/repos/{repo}/issues?state=open&labels={DECISION_LABEL}"
            f"&per_page=100&page={page}",
            token)
        if status != 200:
            return None, _api_error("could not list open needs-decision issues",
                                    status, body)
        batch = body if isinstance(body, list) else []
        issues.extend({"number": i.get("number"),
                       "html_url": i.get("html_url"),
                       "body": i.get("body") or ""}
                      for i in batch if "pull_request" not in i)
        if len(batch) < 100:
            return issues, None
        page += 1


def run_escalation(reg: Registry, chain: str, reason: str, context_label: str,
                   repo: str, token: str, when: Optional[str] = None,
                   gh: Optional[_Request] = None) -> int:
    """The live path: list, plan, perform. Prints the notices; returns the
    process exit code (0 on every decided outcome — advisory; 1 only on a
    transport/API error or a guard firing, which are defects, not outages)."""
    if gh is None:
        gh = _request
    when = when or datetime.now(timezone.utc).isoformat(timespec="seconds")

    providers = [link.provider for link in reg.resolve(chain)]

    # The old github-script order, kept: ensure the label, then read the open
    # set, then decide. Each step's failure is a red, not a degrade.
    err = _ensure_label(gh, repo, token)
    if err is not None:
        print(f"::error::provider escalation for {chain} ({reason}) failed: {err}")
        return 1
    issues, err = _open_issues(gh, repo, token)
    if err is not None:
        print(f"::error::provider escalation for {chain} ({reason}) failed: {err}")
        return 1
    plan = plan_escalation(reason, chain, context_label, providers, when, issues)

    if plan.action == "file":
        status, body, _ = gh("POST", f"{API_BASE}/repos/{repo}/issues", token,
                             {"title": plan.title, "body": plan.body,
                              "labels": [DECISION_LABEL]})
        if status != 201:
            print(f"::error::{_api_error('could not file the escalation', status, body)}")
            return 1
        url = body.get("html_url") if isinstance(body, Mapping) else None
        print(f"::warning::provider-triage: {plan.notice}: {url or '(url unavailable)'}")
        return 0

    if plan.action == "join":
        status, body, _ = gh("PATCH",
                             f"{API_BASE}/repos/{repo}/issues/{plan.number}",
                             token, {"body": plan.body})
        if status != 200:
            print(f"::error::{_api_error('could not update the escalation', status, body)}")
            return 1
        print(f"::warning::provider-triage: {plan.notice}")
        return 0

    print(f"::warning::provider-triage: {plan.notice}")
    return 0
