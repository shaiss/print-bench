"""`smoke` tests — every outcome exercised through the injected post seam.

The smoke command exists because static checks cannot prove a model id is
servable by a key (issue #298); these tests prove the *judgement* — what counts
as served (ok), a proven-unservable id (FAIL, the registry defect it blocks
on), inconclusive (rate limit / account funding / auth / network — external to
the registry, must not red the gate), and skipped — with a positive case and a
negative control per rule, and pin that the package's network I/O stays
confined to the one `_post` seam.
"""

from __future__ import annotations

import pathlib
import textwrap

from model_registry import smoke
from model_registry.cli import main
from model_registry.registry import Registry

# The committed registry (the routine-chain test reads the real chains, not a
# fixture — the deepened tails are the subject).
REGISTRY_PATH = pathlib.Path(__file__).resolve().parents[3] / ".github" / "models" / "registry.conf"

REG = """\
[provider:zai]
secret = ZAI_KEY
base_url = https://api.z.ai/api/anthropic

[provider:anthropic]
secret = ANTHROPIC_API_KEY

[model:glm-5.2]
provider = zai
notes = cheap first

[model:claude-opus-5]
provider = anthropic
notes = frontier backstop

[model:claude-haiku-4-5]
provider = anthropic
notes = last resort

[chain:review]
models = glm-5.2, claude-opus-5, claude-haiku-4-5
"""


def load(tmp_path) -> Registry:
    p = tmp_path / "registry.conf"
    p.write_text(textwrap.dedent(REG), encoding="utf-8")
    return Registry.load(str(p))


def ok_post(calls):
    def post(url, headers, payload):
        calls.append((url, headers, payload))
        return 200, '{"type":"message"}'
    return post


def test_all_configured_links_served_exits_0(tmp_path):
    calls = []
    env = {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}
    lines, code = smoke.smoke_chain(load(tmp_path), "review", env, ok_post(calls))
    assert code == 0
    assert [l.split()[0] for l in lines] == ["ok", "ok", "ok"]
    assert len(calls) == 3


def test_request_wiring_per_provider(tmp_path):
    # Each link must hit its provider's endpoint with its provider's key and a
    # 1-token request for exactly its model id — the wiring the live run relies on.
    calls = []
    env = {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}
    smoke.smoke_chain(load(tmp_path), "review", env, ok_post(calls))
    import json
    (zai_url, zai_hdrs, zai_body), (an_url, an_hdrs, an_body), _ = calls
    assert zai_url == "https://api.z.ai/api/anthropic/v1/messages"
    assert an_url == "https://api.anthropic.com/v1/messages"
    assert zai_hdrs["x-api-key"] == "zk" and an_hdrs["x-api-key"] == "ak"
    assert an_hdrs["anthropic-version"]
    body = json.loads(an_body)
    assert body["model"] == "claude-opus-5" and body["max_tokens"] == 1


def test_non_200_on_a_configured_link_fails(tmp_path):
    # Negative control: the exact #298 signature — the provider answers, but
    # rejects the model id as not found — must fail the run, echoing the reason.
    def post(url, headers, payload):
        if url == "https://api.anthropic.com/v1/messages" and b"claude-opus-5" in payload:
            return 404, '{"error":{"message":"model not found"}}'
        return 200, "{}"
    lines, code = smoke.smoke_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}, post)
    assert code == 1
    assert any(l.startswith("FAIL") and "model not found" in l for l in lines)


def test_permission_denied_is_a_dead_id_fail(tmp_path):
    # A 403 permission denial (the key exists but cannot serve this id) is the
    # #298 access failure — a registry defect — not an account-funding excuse.
    def post(url, headers, payload):
        return 403, '{"error":{"type":"permission_error","message":"no access to model"}}'
    lines, code = smoke.smoke_chain(load(tmp_path), "review", {"ZAI_KEY": "zk"}, post)
    assert code == 1
    assert any(l.startswith("FAIL") for l in lines)


def test_permission_denial_worded_insufficient_is_still_dead(tmp_path):
    # VADE finding: a 403 permission denial whose body happens to say
    # "insufficient permissions" is the #298 defect (an id the key cannot
    # serve), NOT account funding. A bare "insufficient" marker would misread it
    # as inconclusive and green the gate on an unservable id — so it must FAIL.
    def post(url, headers, payload):
        return 403, ('{"error":{"type":"permission_error","message":'
                     '"insufficient permissions to access this model"}}')
    lines, code = smoke.smoke_chain(load(tmp_path), "review", {"ZAI_KEY": "zk"}, post)
    assert code == 1
    assert any(line.startswith("FAIL") for line in lines)


def test_insufficient_funds_billing_is_still_inconclusive(tmp_path):
    # The other direction: a genuine funding rejection worded "insufficient
    # funds" must stay inconclusive — the specific funding tokens still catch it
    # after the bare "insufficient" marker was dropped.
    def post(url, headers, payload):
        return 400, ('{"error":{"type":"invalid_request_error","message":'
                     '"insufficient funds in your account"}}')
    lines, code = smoke.smoke_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}, post)
    assert code == 0
    assert all(not line.startswith("FAIL") for line in lines)
    assert any(line.startswith("INCONC") for line in lines)


def test_unlisted_5xx_is_inconclusive_not_dead(tmp_path):
    # A non-standard server-side status (Cloudflare 520) is a provider outage,
    # not evidence the id is bad — it must be inconclusive, never fall through
    # to "dead" and red the gate on a transient.
    def post(url, headers, payload):
        return 520, "Web server returned an unknown error"
    lines, code = smoke.smoke_chain(load(tmp_path), "review", {"ZAI_KEY": "zk"}, post)
    assert code == 0
    assert all(not line.startswith("FAIL") for line in lines)
    assert any(line.startswith("INCONC") for line in lines)


def test_rate_limited_is_inconclusive_not_a_fail(tmp_path):
    # 429 says the account is over quota, not that the id is bad — the exact
    # signature that would otherwise red every registry PR on a broke key.
    def post(url, headers, payload):
        return 429, '{"error":{"type":"rate_limit_error","message":"Weekly Limit Exhausted"}}'
    lines, code = smoke.smoke_chain(load(tmp_path), "review", {"ZAI_KEY": "zk"}, post)
    assert code == 0
    assert any(l.startswith("INCONC") for l in lines)
    assert any(l.startswith("WARN") and "NOT PROVEN" in l for l in lines)


def test_credit_balance_too_low_is_inconclusive(tmp_path):
    # A 400 whose body is a billing rejection ("credit balance too low") reached
    # the model — the account, not the id, is the problem. Inconclusive.
    def post(url, headers, payload):
        return 400, ('{"error":{"type":"invalid_request_error","message":'
                     '"Your credit balance is too low to access the Anthropic API."}}')
    lines, code = smoke.smoke_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}, post)
    assert code == 0
    assert all(not l.startswith("FAIL") for l in lines)
    assert any(l.startswith("INCONC") for l in lines)


def test_a_dead_link_fails_even_amid_inconclusive_ones(tmp_path):
    # One genuinely-dead id must fail the run even if other links are only
    # inconclusive — a real defect is not masked by a broke key elsewhere.
    def post(url, headers, payload):
        if b"claude-opus-5" in payload:
            return 404, '{"error":{"message":"model not found"}}'
        return 429, '{"error":{"message":"rate limited"}}'
    lines, code = smoke.smoke_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}, post)
    assert code == 1
    assert any(l.startswith("FAIL") and "model not found" in l for l in lines)


def test_network_error_is_inconclusive_not_a_registry_defect(tmp_path):
    # A network blip proves nothing about a model id, so it is inconclusive, not
    # a failure — the gate must not red on transient connectivity.
    def post(url, headers, payload):
        raise OSError("connection refused")
    lines, code = smoke.smoke_chain(load(tmp_path), "review", {"ZAI_KEY": "zk"}, post)
    assert code == 0
    assert any(l.startswith("INCONC") and "connection refused" in l for l in lines)
    assert any(l.startswith("WARN") and "NOT PROVEN" in l for l in lines)


def test_missing_secret_skips_the_link_not_the_run(tmp_path):
    calls = []
    lines, code = smoke.smoke_chain(
        load(tmp_path), "review", {"ANTHROPIC_API_KEY": "ak"}, ok_post(calls))
    assert code == 0
    assert lines[0].startswith("skip") and "ZAI_KEY" in lines[0]
    assert len(calls) == 2


def test_no_secret_at_all_fails_never_green_nothing(tmp_path):
    # Negative control for the whole command: zero attempted links must exit 1,
    # or an unconfigured CI run would "prove" the chain with no request made.
    calls = []
    lines, code = smoke.smoke_chain(load(tmp_path), "review", {}, ok_post(calls))
    assert code == 1 and not calls
    assert any("proves nothing" in l for l in lines)


def test_secret_values_never_reach_the_report(tmp_path):
    def post(url, headers, payload):
        return 403, "denied"
    lines, _ = smoke.smoke_chain(
        load(tmp_path), "review",
        {"ZAI_KEY": "sec-zai-value", "ANTHROPIC_API_KEY": "sec-an-value"}, post)
    joined = "\n".join(lines)
    assert "sec-zai-value" not in joined and "sec-an-value" not in joined


def test_cli_smoke_command_wires_env_and_exit_code(tmp_path, capsys, monkeypatch):
    p = tmp_path / "registry.conf"
    p.write_text(textwrap.dedent(REG), encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ak")
    monkeypatch.delenv("ZAI_KEY", raising=False)
    monkeypatch.setattr(smoke, "_post", lambda url, headers, payload: (200, "{}"))
    assert main(["--path", str(p), "smoke", "review"]) == 0
    out = capsys.readouterr().out
    assert "ok    link 2 claude-opus-5 (anthropic)" in out
    assert out.startswith("skip")


def test_invalid_model_400_is_a_dead_id_fail(tmp_path):
    # The third #298 signature: a 400 whose body names the model as invalid is
    # the registry naming an id the provider does not know — a defect, not a
    # funding/billing rejection (which is why _classify checks the account
    # markers BEFORE falling through to dead, and why this body carries none).
    def post(url, headers, payload):
        return 400, ('{"error":{"type":"invalid_request_error","message":'
                     '"invalid model id: glm-9.9-not-a-model"}}')
    lines, code = smoke.smoke_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}, post)
    assert code == 1
    assert any(l.startswith("FAIL") and "invalid model" in l for l in lines)


def test_auth_401_is_inconclusive_not_a_dead_id(tmp_path):
    # A 401 means the KEY is wrong or missing — a configuration problem that
    # says nothing about any model id's validity, so it must not red the gate
    # on a model the registry correctly named.
    def post(url, headers, payload):
        return 401, '{"error":{"type":"authentication_error","message":"invalid x-api-key"}}'
    lines, code = smoke.smoke_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}, post)
    assert code == 0
    assert all(not l.startswith("FAIL") for l in lines)
    assert any(l.startswith("INCONC") for l in lines)
    assert any(l.startswith("WARN") and "NOT PROVEN" in l for l in lines)


def test_routine_chains_are_smokeable_and_within_their_provider():
    """#327 AC: the four routine chains resolve to >1 link, all on the routine's
    conf provider, so a model-smoke run (the model-smoke.yml workflow smokes
    EVERY chain on any registry edit, and dispatch accepts any chain name)
    actually exercises the deepened tails.

    This is the smoke-side half of the drift guard's chain checks: not that
    the workflows walk (test_workflow_drift proves that), but that what they
    walk can be PROVEN callable — every link resolvable and skippable by
    secret presence, none dangling.
    """
    reg = Registry.load(REGISTRY_PATH)
    routines = {
        "design-run": "zai",
        "backlog-burn": "zai",
        "chunker": "zai",
        "labeler": "zai",
    }
    for chain_id, provider in routines.items():
        links = reg.resolve(chain_id)
        assert len(links) > 1, (
            f"the `{chain_id}` chain has {len(links)} link(s) — #327 requires "
            "a multi-model tail so one unservable id cannot kill the routine")
        for link in links:
            assert link.provider == provider, (
                f"the `{chain_id}` chain's link {link.position} ({link.model}) "
                f"is on provider {link.provider!r} but .github/{chain_id}.conf "
                f"declares {provider!r} — the run holds only that provider's "
                "secret, so the walk cannot reach this link")
    # And the smoke itself runs end-to-end over a routine chain with all its
    # provider's secrets absent: exit 1 "proves nothing" (the documented
    # misconfiguration verdict), not a crash on the deepened tail.
    lines, code = smoke.smoke_chain(reg, "chunker", {}, post=None)
    assert code == 1
    assert any("proves nothing" in l for l in lines)


def test_post_is_the_packages_only_network_seam():
    # Confinement (the backlog-groomer discipline): network imports live in
    # smoke.py only, so every other module stays statically network-free.
    pkg = pathlib.Path(smoke.__file__).parent
    for src in pkg.glob("*.py"):
        text = src.read_text(encoding="utf-8")
        if src.name == "smoke.py":
            assert "urllib" in text
        else:
            assert "urllib" not in text and "http.client" not in text, (
                f"{src.name} gained network I/O outside the smoke seam")


# ── classify_chain: the escalation-facing diagnosis (issue #347) ──────────────
#
# Where smoke_chain answers "is any id a registry defect?" (its exit code),
# classify_chain answers "what should a human/CI do about a chain that failed on
# EVERY link?" — servable / dead / needs-human / transient. The Oracle's HITL
# escalation branches on it: needs-human raises a decision, dead reds, transient
# retries. A positive case and a negative control per class, plus the precedence
# a mixed chain resolves to, and the property that the finer verdict never drifts
# from the coarse one the smoke gate still exits on.

def _post_status(status, body):
    def post(url, headers, payload):
        return status, body
    return post


def test_classify_credit_too_low_is_needs_human(tmp_path):
    # The live signature that surfaced #347: every anthropic link 400s with
    # "credit balance too low". Funding is a HUMAN problem (fund/rotate the key),
    # so it must classify needs-human — not transient (no retry clears it) and
    # not a dead id (the model is fine).
    post = _post_status(400, '{"error":{"message":"Your credit balance is too low"}}')
    lines, klass = smoke.classify_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}, post)
    assert klass == "needs-human"
    assert lines[-1] == "CLASS review: needs-human"


def test_classify_401_is_needs_human_not_transient(tmp_path):
    # An invalid/revoked key is the other needs-human case: a person must rotate
    # it. Negative control against transient — a retry never fixes a bad key.
    post = _post_status(401, '{"error":{"message":"invalid x-api-key"}}')
    _, klass = smoke.classify_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}, post)
    assert klass == "needs-human"


def test_classify_rate_limit_is_transient_not_needs_human(tmp_path):
    # 429 is retryable — nobody needs to act, the next run clears it. The
    # negative control for needs-human: a rate limit must NOT be read as funding.
    post = _post_status(429, '{"error":{"type":"rate_limit_error","message":"slow down"}}')
    _, klass = smoke.classify_chain(load(tmp_path), "review", {"ZAI_KEY": "zk"}, post)
    assert klass == "transient"


def test_classify_5xx_is_transient(tmp_path):
    # A provider outage (Cloudflare 520) is retryable, not a human problem.
    _, klass = smoke.classify_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk"}, _post_status(520, "outage"))
    assert klass == "transient"


def test_classify_network_error_is_transient(tmp_path):
    def post(url, headers, payload):
        raise OSError("connection refused")
    lines, klass = smoke.classify_chain(load(tmp_path), "review", {"ZAI_KEY": "zk"}, post)
    assert klass == "transient"
    assert any("connection refused" in l for l in lines)


def test_classify_404_is_dead(tmp_path):
    # A proven-unservable id (#298) is an in-repo registry defect, not a human
    # account problem — it must red, so it classifies dead.
    _, klass = smoke.classify_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk"},
        _post_status(404, '{"error":{"message":"model not found"}}'))
    assert klass == "dead"


def test_classify_invalid_model_400_is_dead(tmp_path):
    _, klass = smoke.classify_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk"},
        _post_status(400, '{"error":{"message":"invalid model id: nope"}}'))
    assert klass == "dead"


def test_classify_a_servable_link_makes_the_chain_servable(tmp_path):
    # Precedence, positive: one link serves, so the chain is fine — the caller's
    # exhaustion had a non-provider cause. servable wins over the broke anthropic
    # links, so no HITL escalation fires for a working provider.
    def post(url, headers, payload):
        if b"glm-5.2" in payload:
            return 200, "{}"
        return 400, '{"error":{"message":"credit balance too low"}}'
    _, klass = smoke.classify_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}, post)
    assert klass == "servable"


def test_classify_dead_id_beats_a_broke_key(tmp_path):
    # Precedence, negative control: a proven-dead id outranks a co-occurring
    # funding failure — the registry defect is the more actionable signal, so it
    # reds rather than escalating a key nobody needs to touch to see the defect.
    def post(url, headers, payload):
        if b"claude-opus-5" in payload:
            return 404, '{"error":{"message":"model not found"}}'
        return 400, '{"error":{"message":"credit balance too low"}}'
    _, klass = smoke.classify_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}, post)
    assert klass == "dead"


def test_classify_no_secret_is_needs_human(tmp_path):
    # No key configured for any link is a human problem too (set the key) — the
    # same class as an invalid one, so the Oracle escalates rather than silently
    # doing nothing.
    lines, klass = smoke.classify_chain(load(tmp_path), "review", {}, _post_status(200, "{}"))
    assert klass == "needs-human"
    assert any("no provider secret is set" in l for l in lines)


def test_classify_fine_never_drifts_from_the_coarse_verdict():
    # The refactor's load-bearing invariant: _classify is DERIVED from
    # _classify_fine, so every needs_human/transient is exactly a coarse
    # "inconc", every dead stays dead, every ok stays ok. If a future edit splits
    # them, this fails before the smoke gate can green an unservable id.
    cases = [
        (200, "{}"), (429, "slow"), (408, "timeout"), (503, "down"), (520, "cf"),
        (401, "invalid x-api-key"), (400, "credit balance too low"),
        (400, "quota exceeded"), (400, "rate limit exceeded"),
        (404, "model not found"),
        (403, "insufficient permissions to access this model"),
        (400, "invalid model id: nope"),
    ]
    for status, body in cases:
        fine = smoke._classify_fine(status, body)
        coarse = smoke._classify(status, body)
        if fine in ("needs_human", "transient"):
            assert coarse == "inconc", (status, body, fine, coarse)
        else:
            assert coarse == fine, (status, body, fine, coarse)


def test_classify_secret_values_never_reach_the_report(tmp_path):
    lines, _ = smoke.classify_chain(
        load(tmp_path), "review",
        {"ZAI_KEY": "sec-zai-value", "ANTHROPIC_API_KEY": "sec-an-value"},
        _post_status(400, "credit balance too low"))
    joined = "\n".join(lines)
    assert "sec-zai-value" not in joined and "sec-an-value" not in joined


def test_cli_classify_writes_class_to_gh_output(tmp_path, capsys, monkeypatch):
    # The workflow contract: `classify <chain> --gh-output` appends
    # `class=<token>` (the resolve shape) and prints the CLASS line, exit 0.
    p = tmp_path / "registry.conf"
    p.write_text(textwrap.dedent(REG), encoding="utf-8")
    gh = tmp_path / "gh_output"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ak")
    monkeypatch.delenv("ZAI_KEY", raising=False)
    monkeypatch.setattr(
        smoke, "_post",
        lambda url, headers, payload: (400, '{"error":{"message":"credit balance too low"}}'))
    assert main(["--path", str(p), "classify", "review", "--gh-output", str(gh)]) == 0
    assert "class=needs-human\n" in gh.read_text(encoding="utf-8")
    assert "CLASS review: needs-human" in capsys.readouterr().out


# ── diagnose_chain: the finer CAUSE behind the action bucket (billing / quota /
# auth / rate-limit / outage / bad id) — so a message can route the right fix
# instead of the undifferentiated "needs-human". A positive case per reason, the
# reason↔class consistency, and that the split preserves the coarse verdict.

def test_reason_fine_reproduces_the_coarse_verdict_exactly():
    # The load-bearing invariant of the split: _classify_fine is DERIVED from
    # _reason_fine via _REASON_TO_FINE, so every reason maps to the same coarse
    # verdict the smoke gate always exited on. If a reason is ever mapped to the
    # wrong bucket, this fails before any workflow can act on a wrong route.
    cases = [
        (200, "{}", "served", "ok"),
        (429, "slow down", "rate-limit", "transient"),
        (408, "timeout", "outage", "transient"),
        (503, "down", "outage", "transient"),
        (520, "cf", "outage", "transient"),
        (401, "invalid x-api-key", "auth", "needs_human"),
        (400, "Your credit balance is too low", "billing", "needs_human"),
        (400, "insufficient funds in your account", "billing", "needs_human"),
        (400, "monthly quota exceeded", "quota", "needs_human"),
        (400, "rate limit exceeded", "rate-limit", "transient"),
        (404, "model not found", "bad-model-id", "dead"),
        (403, "insufficient permissions to access this model", "bad-model-id", "dead"),
        (400, "invalid model id: nope", "bad-model-id", "dead"),
    ]
    for status, body, want_reason, want_fine in cases:
        assert smoke._reason_fine(status, body) == want_reason, (status, body)
        assert smoke._REASON_TO_FINE[want_reason] == want_fine
        assert smoke._classify_fine(status, body) == want_fine, (status, body)


def test_every_reason_maps_to_a_class():
    # No reason may dangle: each must resolve through _REASON_TO_FINE and
    # _FINE_TO_CLASS to one of the four aggregate classes the callers branch on.
    for reason, fine in smoke._REASON_TO_FINE.items():
        assert fine in smoke._FINE_TO_CLASS, reason
        assert smoke._FINE_TO_CLASS[fine] in smoke._CLASS_PRECEDENCE, reason


def test_diagnose_billing_vs_quota_are_distinct_reasons(tmp_path):
    # The whole point: both are needs-human, but a depleted balance ("fund it")
    # and an exhausted quota ("out of tokens — raise the cap / wait") route to
    # different remediation, so they must surface as DIFFERENT reasons.
    _, klass_b, reason_b = smoke.diagnose_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk"},
        _post_status(400, '{"error":{"message":"credit balance too low"}}'))
    _, klass_q, reason_q = smoke.diagnose_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk"},
        _post_status(400, '{"error":{"message":"monthly quota exceeded"}}'))
    assert klass_b == klass_q == "needs-human"   # same action bucket …
    assert reason_b == "billing" and reason_q == "quota"   # … different cause


def test_diagnose_auth_reason_is_distinct_from_billing(tmp_path):
    _, klass, reason = smoke.diagnose_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk"},
        _post_status(401, '{"error":{"message":"invalid x-api-key"}}'))
    assert klass == "needs-human" and reason == "auth"


def test_diagnose_rate_limit_and_outage_split_the_transient_bucket(tmp_path):
    _, k_rl, r_rl = smoke.diagnose_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk"},
        _post_status(429, '{"error":{"message":"slow down"}}'))
    _, k_out, r_out = smoke.diagnose_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk"}, _post_status(520, "outage"))
    assert k_rl == k_out == "transient"
    assert r_rl == "rate-limit" and r_out == "outage"


def test_diagnose_network_error_reason_is_outage(tmp_path):
    def post(url, headers, payload):
        raise OSError("connection refused")
    lines, klass, reason = smoke.diagnose_chain(load(tmp_path), "review", {"ZAI_KEY": "zk"}, post)
    assert klass == "transient" and reason == "outage"
    assert any("connection refused" in l for l in lines)


def test_diagnose_dead_id_reason_is_bad_model_id(tmp_path):
    _, klass, reason = smoke.diagnose_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk"},
        _post_status(404, '{"error":{"message":"model not found"}}'))
    assert klass == "dead" and reason == "bad-model-id"


def test_diagnose_no_secret_reason_is_no_key(tmp_path):
    # Distinct from billing/auth: nothing to fund or rotate — the secret is just
    # not set. An escalation keys off this to say "set the key", not "fund it".
    lines, klass, reason = smoke.diagnose_chain(load(tmp_path), "review", {}, _post_status(200, "{}"))
    assert klass == "needs-human" and reason == "no-key"
    assert any("[no-key]" in l for l in lines)


def test_diagnose_aggregate_reason_follows_the_winning_class(tmp_path):
    # Precedence: a dead id outranks a co-occurring billing failure, so BOTH the
    # class and the reason come from the dead link — the reason must track the
    # class that won, never a louder-but-lower one.
    def post(url, headers, payload):
        if b"claude-opus-5" in payload:
            return 404, '{"error":{"message":"model not found"}}'
        return 400, '{"error":{"message":"credit balance too low"}}'
    _, klass, reason = smoke.diagnose_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}, post)
    assert klass == "dead" and reason == "bad-model-id"


def test_diagnose_servable_reason_is_served(tmp_path):
    def post(url, headers, payload):
        if b"glm-5.2" in payload:
            return 200, "{}"
        return 400, '{"error":{"message":"credit balance too low"}}'
    _, klass, reason = smoke.diagnose_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk", "ANTHROPIC_API_KEY": "ak"}, post)
    assert klass == "servable" and reason == "served"


def test_classify_chain_facade_still_returns_the_2_tuple(tmp_path):
    # Back-compat: the old 2-tuple shape every existing caller/test relies on is
    # unchanged; only diagnose_chain carries the third (reason) element.
    result = smoke.classify_chain(
        load(tmp_path), "review", {"ZAI_KEY": "zk"},
        _post_status(400, "credit balance too low"))
    assert len(result) == 2
    lines, klass = result
    assert klass == "needs-human"
    assert lines[-1] == "CLASS review: needs-human"


def test_diagnose_secret_values_never_reach_the_report(tmp_path):
    lines, _, _ = smoke.diagnose_chain(
        load(tmp_path), "review",
        {"ZAI_KEY": "sec-zai-value", "ANTHROPIC_API_KEY": "sec-an-value"},
        _post_status(400, "credit balance too low"))
    joined = "\n".join(lines)
    assert "sec-zai-value" not in joined and "sec-an-value" not in joined


def test_cli_classify_writes_reason_alongside_class(tmp_path, capsys, monkeypatch):
    # The workflow contract's new half: `classify --gh-output` appends
    # `reason=<token>` next to `class=<token>`, and prints the REASON line, so a
    # step routes billing vs out-of-tokens vs technical without a JSON parse.
    p = tmp_path / "registry.conf"
    p.write_text(textwrap.dedent(REG), encoding="utf-8")
    gh = tmp_path / "gh_output"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ak")
    monkeypatch.delenv("ZAI_KEY", raising=False)
    monkeypatch.setattr(
        smoke, "_post",
        lambda url, headers, payload: (400, '{"error":{"message":"credit balance too low"}}'))
    assert main(["--path", str(p), "classify", "review", "--gh-output", str(gh)]) == 0
    written = gh.read_text(encoding="utf-8")
    assert "class=needs-human\n" in written and "reason=billing\n" in written
    assert "REASON review: billing" in capsys.readouterr().out
