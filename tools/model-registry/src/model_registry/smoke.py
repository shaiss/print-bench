"""``smoke <chain>``: prove each chain link is actually *callable*, live.

Issue #298: the registry declared ``claude-opus-4-8`` as the review chain's
frontier final fallback and every static check passed — ``check`` proves the
file is well-formed, the drift guard proves the workflow matches it — but the
id was unservable by the ``ANTHROPIC_API_KEY``: the first live request was
rejected at $0, so the "never lose a review" backstop was an illusion. No
static validation can prove a model id is servable by a key; only a real
request can.  This module makes that request: for each link in a chain whose
provider secret is present in the environment, POST a minimal 1-token Messages
call and report ``ok`` / ``FAIL`` / ``skip`` (no key).  The exit code is the
proof: 0 only when every *attempted* link answered, and attempting nothing is
a failure too (a smoke run that proves nothing must not report green).

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

    Returns ``(report_lines, exit_code)``.  Exit 0 only when at least one link
    was attempted and every attempted link succeeded; a failed attempt, or a
    run where no secret was configured at all, exits 1.
    """
    if post is None:
        post = _post   # resolved at call time so tests can patch the seam
    lines: list[str] = []
    attempted = failed = 0
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
            failed += 1
            lines.append(f"FAIL  {where}: {exc}")
            continue
        if status == 200:
            lines.append(f"ok    {where}: served a 1-token request")
        else:
            failed += 1
            lines.append(f"FAIL  {where}: HTTP {status} — {body}")
    if attempted == 0:
        lines.append(
            f"FAIL  chain {chain_id}: no link could be attempted — no provider "
            "secret is set, so this run proves nothing"
        )
        return lines, 1
    return lines, 1 if failed else 0
