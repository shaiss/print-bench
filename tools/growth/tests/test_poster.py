"""The OAuth 1.0a signing seam — proven offline, never against the network."""

import json

import pytest

from growth import poster


def test_credentials_present_requires_all_four():
    full = {v: "x" for v in poster.ENV_VARS}
    assert poster.credentials_present(full)
    for missing in poster.ENV_VARS:
        env = dict(full)
        env[missing] = ""
        assert not poster.credentials_present(env)
    assert not poster.credentials_present({})


def test_percent_encoding_is_rfc5849():
    # RFC 5849 §3.6: unreserved chars pass, everything else (space, +, ~ kept)
    # is uppercase-hex encoded.
    assert poster._pct("Ladies + Gentlemen") == "Ladies%20%2B%20Gentlemen"
    assert poster._pct("An encoded string!") == "An%20encoded%20string%21"
    assert poster._pct("safe-._~chars") == "safe-._~chars"


def test_oauth1_header_signature_is_deterministic_and_wellformed():
    hdr = poster.oauth1_header(
        "POST", "https://api.x.com/2/tweets",
        "ck", "cs", "tk", "ts",
        nonce="fixednonce", timestamp="1700000000",
    )
    assert hdr.startswith("OAuth ")
    # Same inputs, same signature — the header is a pure function once nonce
    # and timestamp are pinned.
    assert hdr == poster.oauth1_header(
        "POST", "https://api.x.com/2/tweets",
        "ck", "cs", "tk", "ts",
        nonce="fixednonce", timestamp="1700000000",
    )
    for part in ("oauth_consumer_key=\"ck\"", "oauth_token=\"tk\"",
                 "oauth_signature_method=\"HMAC-SHA1\"", "oauth_signature="):
        assert part in hdr


def test_signature_changes_with_the_secret():
    a = poster.oauth1_header("POST", "https://api.x.com/2/tweets",
                             "ck", "cs", "tk", "ts",
                             nonce="n", timestamp="1")
    b = poster.oauth1_header("POST", "https://api.x.com/2/tweets",
                             "ck", "DIFFERENT", "tk", "ts",
                             nonce="n", timestamp="1")
    assert a != b


def test_post_tweet_refuses_without_credentials():
    with pytest.raises(poster.PosterError, match="credentials missing"):
        poster.post_tweet("hello", env={})


def test_post_tweet_signs_and_posts_via_the_seam(monkeypatch):
    captured = {}

    def fake_http(url, headers, body):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json.loads(body)
        return {"data": {"id": "1234567890"}}

    monkeypatch.setattr(poster, "_http", fake_http)
    env = {v: f"v-{v}" for v in poster.ENV_VARS}
    tweet_id = poster.post_tweet("hello world", env=env)
    assert tweet_id == "1234567890"
    assert captured["url"] == "https://api.x.com/2/tweets"
    assert captured["headers"]["Authorization"].startswith("OAuth ")
    assert captured["body"] == {"text": "hello world"}


def test_post_tweet_threads_via_reply(monkeypatch):
    captured = {}
    monkeypatch.setattr(poster, "_http",
                        lambda url, headers, body: (captured.update(body=json.loads(body)),
                                                    {"data": {"id": "2"}})[1])
    env = {v: "x" for v in poster.ENV_VARS}
    poster.post_tweet("part two", reply_to="111", env=env)
    assert captured["body"]["reply"] == {"in_reply_to_tweet_id": "111"}


def test_post_tweet_honors_x_api_base(monkeypatch):
    captured = {}
    monkeypatch.setattr(poster, "_http",
                        lambda url, headers, body: (captured.update(url=url),
                                                    {"data": {"id": "3"}})[1])
    env = {v: "x" for v in poster.ENV_VARS}
    env["X_API_BASE"] = "https://api.example.test/"
    poster.post_tweet("t", env=env)
    assert captured["url"] == "https://api.example.test/2/tweets"


def test_post_tweet_raises_on_idless_response(monkeypatch):
    monkeypatch.setattr(poster, "_http", lambda url, headers, body: {"detail": "nope"})
    env = {v: "x" for v in poster.ENV_VARS}
    with pytest.raises(poster.PosterError, match="no tweet id"):
        poster.post_tweet("t", env=env)


def test_http_surfaces_the_x_error_body(monkeypatch):
    # A real 4xx from X carries its reason in the response BODY; urllib's
    # HTTPError stringifies without it. `_http` must read the body so the reason
    # (e.g. "credits depleted") reaches the caller instead of a bare "HTTP 402".
    import io
    import urllib.error

    def boom(req, timeout=30):
        raise urllib.error.HTTPError(
            req.full_url, 402, "Payment Required", {},
            io.BytesIO(b'{"detail":"credits depleted","status":402}'))

    monkeypatch.setattr(poster.urllib.request, "urlopen", boom)
    env = {v: "x" for v in poster.ENV_VARS}
    with pytest.raises(poster.PosterError, match="credits depleted"):
        poster.post_tweet("t", env=env)
