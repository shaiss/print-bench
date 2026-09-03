"""``smoke <chain>``: prove each chain link is actually *callable*, live.

Issue #298: the registry declared ``claude-opus-4-8`` as the review chain's
frontier final fallback and every static check passed — ``check`` proves the
file is well-formed, the drift guard proves the workflow matches it — but the
id was unservable by the ``ANTHROPIC_API_KEY``: the first live request was
rejected at $0, so the "never lose a review" backstop was an illusion. No
static validation can prove a model id is servable by a key; only a real
request can.  This module makes that request: for each link in a chain whose
provider secret is present in the environment, POST a minimal 1-token Messages
call and classify the answer.  The exit code is the proof, and it fails ONLY on
positive evidence of a *registry defect* — a model id the key genuinely cannot
serve (404 not-found, an invalid-model 400, a permission denial): the #298
failure.  It deliberately does NOT fail on evidence that the *account* is
temporarily unable to answer — a rate limit (429), a "credit balance too low"
billing rejection, an auth error, a network blip.  Those are external to the
registry: they prove nothing about whether a model id is valid, so a per-PR
smoke gate that went red on them would cry wolf on every registry PR whenever
the key was out of quota.  Three verdicts, then:

  * ``ok``     — HTTP 200: the id is servable, proven.
  * ``FAIL``   — the (key, id) pair genuinely cannot serve this model: a
                 registry defect worth blocking on.
  * ``INCONC`` — the request could not prove servability for a reason external
                 to the registry (rate limit, account funding, auth, network).

Exit code: 1 if any link is ``FAIL`` (a real defect) or no link could be
attempted at all (no secret configured — a misconfiguration, not a transient);
otherwise 0.  A run where every attempted link was ``INCONC`` (nothing proven,
but nothing proved *unservable*) exits 0 with a loud ``WARN`` so it is never
mistaken for "proven".

``_post`` is the package's single HTTP seam — nothing else in model_registry
touches the network, and the tests replace ``_post`` to exercise every outcome
without a key.  The report never contains a secret value: only env-var *names*
(public identifiers, committed in the registry) and response bodies.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Mapping, Optional

from .registry import Registry

# Anthropic's native endpoint, used when a provider declares no base_url.
NATIVE_BASE_URL = "https://api.anthropic.com"

# Bytes of an error response body worth echoing — enough for the API's
# "model not found" / permission message, bounded so a log stays legible.
_BODY_SNIPPET = 500

_TIMEOUT_S = 120

# Statuses that mean the ACCOUNT/provider could not answer right now, not that
# the model id is bad: 429 rate limiting, 408 request timeout, and EVERY 5xx
# server-side outage (including non-standard ones like Cloudflare 520/522).
# Transient — external to the registry, so inconclusive, never a defect. The
# full 5xx range matters: an unlisted 5xx must not fall through to "dead".
def _is_transient(status: int) -> bool:
    return status in (408, 429) or 500 <= status < 600

# Substrings marking an account-funding / quota rejection (any status) — the
# request reached the model but the account could not PAY for it. A human must
# fund or raise the limit, so ``classify_chain`` reads these as ``needs_human``.
#
# Every marker must be UNAMBIGUOUSLY about funding/quota. A bare "insufficient"
# is NOT: a 403 permission denial phrased "insufficient permissions" (or
# "insufficient scope"/"insufficient access") is the exact #298 defect — a
# model id the key cannot serve — and matching it here would silently downgrade
# that FAIL to inconclusive, greening the gate on an unservable id. The funding
# senses ("insufficient credit/balance/quota/funds") are already covered by the
# specific tokens, so the bare word is dropped and "funds" added to keep
# "insufficient funds" caught.
# Split into the two senses the finer cause (`_reason_fine`) must tell apart: a
# spend/period cap the account has hit ("out of tokens" — quota/exhausted) versus
# an unpaid or depleted balance ("billing" — credit/balance/payment/funds/too low).
# Both are ``needs_human`` to the coarse verdict, so the UNION below preserves
# ``_classify_fine``'s behaviour exactly; only the human-facing remediation differs
# (raise the cap / wait for reset, versus fund the account).
# "usage limit" / "regain access" catch the phrasing a provider uses for a spend
# or usage cap that resets on a date — notably Anthropic's "You have reached your
# specified API usage limits. You will regain access on <date>" (an HTTP 400 with
# NO "quota"/"exhausted"/billing word in it). Without these it fell through to
# `bad-model-id` and reddened as a #298 registry defect, when it is really a
# needs_human quota condition (raise the cap / wait for the reset).
_QUOTA_MARKERS = ("quota", "exhausted", "usage limit", "regain access")
_BILLING_MARKERS = ("credit", "billing", "balance", "payment", "funds", "too low")
_FUNDING_MARKERS = _BILLING_MARKERS + _QUOTA_MARKERS

# Rate-limit wording (any status) — the account is momentarily over its rate, a
# TRANSIENT condition a retry clears, so ``classify_chain`` reads these as
# ``transient``, never ``needs_human``. Kept separate from the funding markers
# precisely because the escalation split turns on that difference: funding needs
# a person; a rate limit needs only patience.
_RATE_LIMIT_MARKERS = ("rate limit", "rate_limit")

# The union is what ``_classify`` (the coarse ok/dead/inconc verdict the smoke
# gate exits on) treats as an account/quota rejection — external to the registry,
# so inconclusive either way. The funding/rate-limit split above matters only to
# ``classify_chain``'s finer needs_human-vs-transient escalation decision, and
# ``_classify`` is derived from ``_classify_fine`` below so the two never drift.
_ACCOUNT_MARKERS = _FUNDING_MARKERS + _RATE_LIMIT_MARKERS


# The finest cause labels — the "why" behind the coarse verdict, so a human sees
# billing vs out-of-tokens vs a bad key vs a retryable blip vs an unservable id,
# each with its own remediation. `no-key` is the aggregate-only reason for a chain
# with no secret configured (never a per-request status); every other reason comes
# from one ``(status, body)``. Each maps to exactly one ``_classify_fine`` verdict
# via ``_REASON_TO_FINE`` below, and ``_classify_fine`` is DERIVED from that map —
# so the coarse verdict the smoke gate still exits on can never drift from the
# finer cause the escalation message reads.
_REASON_TO_FINE = {
    "served":       "ok",
    "bad-model-id": "dead",
    "billing":      "needs_human",   # unpaid / depleted balance → fund the account
    "quota":        "needs_human",   # out of tokens for the period → raise cap / wait
    "auth":         "needs_human",   # invalid / missing key → rotate it
    "no-key":       "needs_human",   # no secret configured at all → set it
    "rate-limit":   "transient",     # momentarily over rate → retry
    "outage":       "transient",     # timeout / 5xx / network → retry
}


def _reason_fine(status: int, body: str) -> str:
    """Map an HTTP ``(status, body)`` to the finest cause label.

    The single distinction the HITL escalation turns on stays intact — a
    ``transient`` blip a retry clears versus a ``needs_human`` account/config
    problem — but each side is split into the causes a human acts on differently:
    ``billing`` (fund the account) vs ``quota`` (out of tokens — raise the cap or
    wait) vs ``auth`` (rotate the key) among the human-fixable, and ``rate-limit``
    vs ``outage`` among the retryable. ``bad-model-id`` stays the #298 registry
    defect. The status/marker ORDER is unchanged from the old ``_classify_fine``,
    so ``_REASON_TO_FINE[_reason_fine(...)]`` reproduces its verdict exactly.
    """
    if status == 200:
        return "served"
    if _is_transient(status):               # 408/429/5xx: provider-side, retry
        return "rate-limit" if status == 429 else "outage"
    if status == 401:                       # missing/invalid key: a human rotates
        return "auth"
    low = body.lower()
    if any(marker in low for marker in _RATE_LIMIT_MARKERS):
        return "rate-limit"                 # worded rate limit at a non-429 status
    # Billing BEFORE quota: a depleted balance ("credit balance exhausted") also
    # matches the generic "exhausted" quota marker, but it wants funding
    # remediation, not "raise the cap / wait for reset". Only a message with NO
    # billing marker — a true "quota exceeded" / "weekly limit exhausted" — falls
    # through to quota. Both are needs_human, so the coarse verdict is unchanged
    # either way; the order only decides which remediation the escalation gives.
    if any(marker in low for marker in _BILLING_MARKERS):
        return "billing"                    # "credit balance too low", payment failed
    if any(marker in low for marker in _QUOTA_MARKERS):
        return "quota"                      # "quota exceeded", "weekly limit exhausted",
                                            # "usage limits ... regain access on <date>"
    # 404 not-found, 403 permission, invalid-model 400, …: the id is the problem.
    return "bad-model-id"


def _classify_fine(status: int, body: str) -> str:
    """Coarse ``ok`` / ``dead`` / ``needs_human`` / ``transient`` verdict, DERIVED
    from ``_reason_fine`` so the two can never drift — the four outcomes a
    chain-exhaustion escalation groups causes into (``classify_chain``)."""
    return _REASON_TO_FINE[_reason_fine(status, body)]


def _classify(status: int, body: str) -> str:
    """Coarse ``ok`` / ``dead`` / ``inconc`` verdict the smoke gate exits on.

    Derived from ``_classify_fine`` so the two cannot drift: ``dead`` is positive
    evidence of a #298 registry defect (a model id the key cannot serve), ``ok``
    is a served request, and everything the registry is not to blame for — rate
    limits, account funding, auth, provider outages — collapses to ``inconc`` so
    an automatic gate does not fail on a transient or a broke key.
    """
    fine = _classify_fine(status, body)
    if fine in ("needs_human", "transient"):
        return "inconc"
    return fine                             # "ok" or "dead"


def _post(url: str, headers: dict[str, str], payload: bytes) -> tuple[int, str]:
    """POST ``payload`` to ``url``; return ``(status, body_snippet)``.

    HTTP error statuses are returned, not raised (the status is the signal a
    caller judges); network-level failures raise ``OSError``/``URLError`` for
    the caller to report.  This is the package's only network call.
    """
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            return resp.status, resp.read(_BODY_SNIPPET).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(_BODY_SNIPPET).decode("utf-8", "replace")


def _ping(link, key: str, post) -> tuple[int, str]:
    """Build and send the one 1-token servability request for ``link``.

    The single request shape ``smoke_chain`` and ``classify_chain`` both rely on
    — one place so the two can never send a different probe. Sends both auth
    header forms (native ``x-api-key`` and Bearer) so one request serves the
    native and Anthropic-compatible endpoints alike; ``post`` is the injectable
    seam. Raises ``OSError`` on a network-level failure, like ``_post``.
    """
    url = (link.base_url or NATIVE_BASE_URL).rstrip("/") + "/v1/messages"
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "x-api-key": key,
        "authorization": f"Bearer {key}",
    }
    payload = json.dumps({
        "model": link.model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "ping"}],
    }).encode("utf-8")
    return post(url, headers, payload)


def smoke_chain(
    reg: Registry,
    chain_id: str,
    env: Mapping[str, str],
    post: Optional[Callable[[str, dict[str, str], bytes], tuple[int, str]]] = None,
) -> tuple[list[str], int]:
    """Ping every link of ``chain_id`` whose provider secret is in ``env``.

    Returns ``(report_lines, exit_code)``.  Exit 1 iff a link is proven
    UNSERVABLE (a ``dead`` verdict — the registry defect) or no link could be
    attempted at all (no secret configured). A run whose every attempt was
    inconclusive (rate limit / account funding / network) exits 0 with a WARN:
    nothing proven, but nothing proved unservable, so not a registry defect.
    """
    if post is None:
        post = _post   # resolved at call time so tests can patch the seam
    lines: list[str] = []
    attempted = proven = dead = 0
    for link in reg.resolve(chain_id):
        where = f"link {link.position} {link.model} ({link.provider})"
        key = env.get(link.secret, "")
        if not key:
            lines.append(f"skip  {where}: secret {link.secret} not set")
            continue
        attempted += 1
        try:
            status, body = _ping(link, key, post)
        except OSError as exc:
            # A network-level failure proves nothing about the model id.
            lines.append(f"INCONC  {where}: network error — {exc} (not a registry defect)")
            continue
        verdict = _classify(status, body)
        if verdict == "ok":
            proven += 1
            lines.append(f"ok    {where}: served a 1-token request")
        elif verdict == "inconc":
            lines.append(f"INCONC  {where}: HTTP {status} — {body}")
        else:  # dead — the id is genuinely unservable (#298)
            dead += 1
            lines.append(f"FAIL  {where}: HTTP {status} — {body}")
    if attempted == 0:
        lines.append(
            f"FAIL  chain {chain_id}: no link could be attempted — no provider "
            "secret is set, so this run proves nothing"
        )
        return lines, 1
    if dead:
        return lines, 1
    if proven == 0:
        # Attempted links, but every one was inconclusive (rate limit, account
        # funding, auth, network). Servability was not proven — but nothing
        # proved a model id UNSERVABLE, so this is not a registry defect and
        # must not fail the gate. Say so loudly so it is never read as "proven".
        lines.append(
            f"WARN  chain {chain_id}: servability NOT PROVEN — every attempted "
            "link was inconclusive (rate limit / account funding / network); "
            "none was proven unservable, so this is not a registry defect"
        )
    return lines, 0


# The aggregate classes classify_chain reports, in the precedence a mixed chain
# resolves to (highest first). `servable` wins because a single working link
# means the chain itself is fine — the caller's exhaustion had a non-provider
# cause. `dead` next: a proven-unservable id is an in-repo registry defect worth
# surfacing over a co-occurring broke key. Then `needs-human` (fund/rotate the
# key) over `transient` (retry later): only a person clears the former.
_CLASS_PRECEDENCE = ("servable", "dead", "needs-human", "transient")

# _classify_fine's verdict tokens -> the aggregate class label they contribute.
_FINE_TO_CLASS = {
    "ok": "servable",
    "dead": "dead",
    "needs_human": "needs-human",
    "transient": "transient",
}


def diagnose_chain(
    reg: Registry,
    chain_id: str,
    env: Mapping[str, str],
    post: Optional[Callable[[str, dict[str, str], bytes], tuple[int, str]]] = None,
) -> tuple[list[str], str, str]:
    """Diagnose WHY a chain is unusable, for a caller whose own walk exhausted it.

    Where ``smoke_chain`` answers "is any id a registry defect?" (its exit code),
    this answers "what should a human/CI do about a chain that just failed on
    every link?" — the finer question the HITL escalation turns on. It probes each
    configured link (the same 1-token ``_ping``) and reduces the per-link verdicts
    to two things: an aggregate **class** (the action bucket, by
    ``_CLASS_PRECEDENCE``) and an aggregate **reason** (the finest cause behind it,
    the button a human actually pushes):

      * ``servable``    — a link served: the chain is fine, so the exhaustion had
                          a non-provider cause (agent error, timeout in the real
                          review). Not an escalation.  reason ``served``.
      * ``dead``        — a link is a proven-unservable id (#298): a registry
                          defect to fix in-repo. Red it.  reason ``bad-model-id``.
      * ``needs-human`` — the account/config problem CI cannot fix: reason
                          ``billing`` (fund the account), ``quota`` (out of tokens —
                          raise the cap or wait for reset), ``auth`` (rotate an
                          invalid/expired key), or ``no-key`` (no secret set at
                          all). Escalate via the HITL gate, do not red every run.
      * ``transient``   — every attempt was a retryable blip: reason ``rate-limit``
                          or ``outage`` (timeout / 5xx / network). Retry next run.

    The class stays the proven, precedence-ordered action signal every existing
    caller branches on; the reason is the new sub-signal that lets a message say
    *billing* vs *out-of-tokens* vs *bad key* instead of the undifferentiated
    "needs-human". The aggregate reason is the cause of the FIRST link (report
    order) that produced the aggregate class — deterministic, and the reason a
    reader sees first in the per-link lines. Returns
    ``(report_lines, aggregate_class, aggregate_reason)``; the class IS the signal,
    there is no exit code. A chain with no configured secret reduces to
    ``needs-human`` / ``no-key`` — a human must set the key.
    """
    if post is None:
        post = _post   # resolved at call time so tests can patch the seam
    lines: list[str] = []
    seen: set[str] = set()
    first_reason_by_class: dict[str, str] = {}   # class -> reason of its first link
    attempted = 0

    def record(cls: str, reason: str) -> None:
        seen.add(cls)
        first_reason_by_class.setdefault(cls, reason)

    for link in reg.resolve(chain_id):
        where = f"link {link.position} {link.model} ({link.provider})"
        key = env.get(link.secret, "")
        if not key:
            lines.append(f"skip  {where}: secret {link.secret} not set")
            continue
        attempted += 1
        try:
            status, body = _ping(link, key, post)
        except OSError as exc:
            record("transient", "outage")
            lines.append(f"transient   {where}: [outage] network error — {exc}")
            continue
        reason = _reason_fine(status, body)
        cls = _FINE_TO_CLASS[_REASON_TO_FINE[reason]]
        record(cls, reason)
        if cls == "servable":
            lines.append(f"servable    {where}: [{reason}] served a 1-token request")
        else:
            lines.append(f"{cls:<11} {where}: [{reason}] HTTP {status} — {body}")
    if attempted == 0:
        # No secret set for any link: a human must configure the key. Its own
        # ``no-key`` reason, so an escalation says "set the secret" rather than
        # "fund the account" — a distinct fix from the funding/auth cases.
        record("needs-human", "no-key")
        lines.append(
            f"needs-human chain {chain_id}: [no-key] no provider secret is set — a "
            "human must configure the key before this chain can be used"
        )
    aggregate = next(c for c in _CLASS_PRECEDENCE if c in seen)
    reason = first_reason_by_class[aggregate]
    lines.append(f"REASON {chain_id}: {reason}")
    lines.append(f"CLASS {chain_id}: {aggregate}")
    return lines, aggregate, reason


def classify_chain(
    reg: Registry,
    chain_id: str,
    env: Mapping[str, str],
    post: Optional[Callable[[str, dict[str, str], bytes], tuple[int, str]]] = None,
) -> tuple[list[str], str]:
    """Back-compat 2-tuple facade over ``diagnose_chain`` (aggregate class only).

    Callers that only branch on the action bucket keep this shape; callers wanting
    the finer cause for a human-facing message use ``diagnose_chain`` directly.
    """
    lines, aggregate, _reason = diagnose_chain(reg, chain_id, env, post)
    return lines, aggregate
