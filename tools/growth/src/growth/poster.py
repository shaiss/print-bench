"""The X API v2 posting seam — OAuth 1.0a user-context signing, stdlib-only.

Posting a tweet needs a *user-context* credential set (the four values the X
developer portal calls consumer key/secret + access token/secret). This
module signs ``POST /2/tweets`` with OAuth 1.0a (HMAC-SHA1) by hand —
stdlib-only like every tool here, so the unattended run needs no pip step.

The seam is deliberately narrow and inert-by-default:

* :func:`credentials_present` is the ONE mode decision input — all four env
  vars set, or this module refuses to sign anything;
* :func:`post_tweet` performs exactly one call, ``POST {X_API_BASE}/2/tweets``
  (optionally as a reply, which is how a thread is built), and returns the
  created tweet's id;
* the HTTP transport is a module function (:func:`_http`) so tests exercise
  the full signing path against a captured request, never the network — and
  the signature itself is pinned against RFC 5849's percent-encoding rules by
  the test suite.

The MCP posting tool (.claude/skills/growth-twitter/growth_mcp.py) holds the
policy (approval label, marker dedupe, caps); this module holds only the
mechanics, so the policy layer stays testable without a single crypto line.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_API_BASE = "https://api.x.com"

ENV_VARS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")


class PosterError(RuntimeError):
    pass


def credentials_present(env: dict | None = None) -> bool:
    env = os.environ if env is None else env
    return all((env.get(v) or "").strip() for v in ENV_VARS)


def _pct(s: str) -> str:
    # RFC 5849 §3.6: percent-encode everything but unreserved characters.
    return urllib.parse.quote(s, safe="-._~")


def oauth1_header(
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    token: str,
    token_secret: str,
    *,
    nonce: str | None = None,
    timestamp: str | None = None,
) -> str:
    """The ``Authorization: OAuth ...`` header for a request with NO query or
    form parameters (the v2 tweet endpoint takes a JSON body, which OAuth 1.0a
    excludes from the signature base string)."""
    params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp or str(int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    param_str = "&".join(
        f"{_pct(k)}={_pct(v)}" for k, v in sorted(params.items())
    )
    base = "&".join((method.upper(), _pct(url), _pct(param_str)))
    key = f"{_pct(consumer_secret)}&{_pct(token_secret)}".encode()
    sig = base64.b64encode(
        hmac.new(key, base.encode(), hashlib.sha1).digest()
    ).decode()
    params["oauth_signature"] = sig
    header_params = ", ".join(
        f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(params.items())
    )
    return f"OAuth {header_params}"


def _http(url: str, headers: dict, body: bytes) -> dict:
    """POST and decode JSON. Module-level so tests monkeypatch it.

    On an HTTP error, READ the response body and raise a PosterError carrying
    the status and X's actual message — urllib's HTTPError otherwise stringifies
    to a bare "HTTP Error 402: Payment Required" with the reason (e.g. "credits
    depleted") stranded in the unread body, which is exactly what turned a
    one-line X-side problem into a blind debugging hunt (issue: the swallowed
    error body)."""
    req = urllib.request.Request(url, data=body, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode(errors="replace")
        except Exception:  # noqa: BLE001 — a body we can't read is still an error
            pass
        raise PosterError(f"X API HTTP {e.code}: {detail[:500]}".rstrip(": ")) from e
    return json.loads(raw) if raw else {}


def post_tweet(text: str, reply_to: str | None = None, env: dict | None = None) -> str:
    """Create one tweet (optionally replying to ``reply_to`` — a thread is a
    chain of these). Returns the new tweet id. Raises :class:`PosterError`
    when credentials are missing or the API answers without an id."""
    env = os.environ if env is None else env
    if not credentials_present(env):
        raise PosterError(
            "X credentials missing (need X_API_KEY, X_API_SECRET, "
            "X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET) — refusing to post"
        )
    base = (env.get("X_API_BASE") or DEFAULT_API_BASE).rstrip("/")
    url = f"{base}/2/tweets"
    payload: dict = {"text": text}
    if reply_to:
        payload["reply"] = {"in_reply_to_tweet_id": str(reply_to)}
    header = oauth1_header(
        "POST", url,
        env["X_API_KEY"], env["X_API_SECRET"],
        env["X_ACCESS_TOKEN"], env["X_ACCESS_TOKEN_SECRET"],
    )
    resp = _http(
        url,
        {"Authorization": header, "Content-Type": "application/json",
         "User-Agent": "print-bench-growth-twitter"},
        json.dumps(payload).encode(),
    )
    tweet_id = ((resp or {}).get("data") or {}).get("id")
    if not tweet_id:
        raise PosterError(f"X API returned no tweet id: {resp!r}")
    return str(tweet_id)
