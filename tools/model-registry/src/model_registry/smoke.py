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
# the model id is bad: rate limiting and provider-side outages. Transient.
_TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504, 529})

# Substrings marking an account-funding / quota rejection (any status) — the
# request reached the model but the account could not pay for it. External to
# the registry, so inconclusive, not a defect.
#
# Every marker must be UNAMBIGUOUSLY about funding/quota. A bare "insufficient"
# is NOT: a 403 permission denial phrased "insufficient permissions" (or
# "insufficient scope"/"insufficient access") is the exact #298 defect — a
# model id the key cannot serve — and matching it here would silently downgrade
# that FAIL to inconclusive, greening the gate on an unservable id. The funding
# senses ("insufficient credit/balance/quota/funds") are already covered by the
# specific tokens, so the bare word is dropped and "funds" added to keep
# "insufficient funds" caught.
_ACCOUNT_MARKERS = (
    "credit", "billing", "balance", "quota", "payment", "funds",
    "exhausted", "too low", "rate limit", "rate_limit",
)


def _classify(status: int, body: str) -> str:
    """Map an HTTP ``(status, body)`` to ``ok`` / ``dead`` / ``inconc``.

    ``dead`` is reserved for positive evidence the registry named a model id the
    key cannot serve (the #298 defect: 404/not-found, permission denial, an
    invalid-model 400). ``inconc`` covers everything the registry is not to
    blame for — rate limits, account funding, auth, provider outages — so an
    automatic gate does not fail on a transient or a broke key.
    """
    if status == 200:
        return "ok"
    if status in _TRANSIENT_STATUSES:
        return "inconc"
    if status == 401:                       # missing/invalid key: config, not id
        return "inconc"
    low = body.lower()
    if any(marker in low for marker in _ACCOUNT_MARKERS):
        return "inconc"                     # "credit balance too low", quota, …
    # 404 not-found, 403 permission, invalid-model 400, …: the id is the problem.
    return "dead"


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
        url = (link.base_url or NATIVE_BASE_URL).rstrip("/") + "/v1/messages"
        # Both auth header forms: Anthropic's native endpoint reads x-api-key,
        # Anthropic-compatible endpoints (Z.AI) read the Bearer token — each
        # ignores the one it doesn't use, so one request shape serves both.
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
        try:
            status, body = post(url, headers, payload)
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
