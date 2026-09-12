"""Escalation tests — the reason-keyed cross-chain dedup (issue #550).

Same discipline as the rest of the suite: a positive case AND a negative
control per rule.  The dedup rule is the issue's whole point, so its two
directions are pinned at both levels — `plan_escalation` (the pure decision,
over a simulated open-issue list) and `run_escalation` (the live path, over a
recording fake transport that answers like the GitHub API) — proving a
newly-exhausted chain produces ZERO new issues when an open issue for its
reason exists, and exactly one when it does not.  Delete the reuse check from
escalation.py and the join tests fail; weaken it back to per-chain keying and
the marker/id derivation tests fail.
"""

from __future__ import annotations

import textwrap

import pytest

from model_registry import escalation as esc
from model_registry.registry import Chain, Model, Provider, Registry

WHEN = "2026-09-06T17:30:00+00:00"


def reg() -> Registry:
    """A minimal registry: a cross-provider chain to walk (the #544 shape) and
    a single-provider one to tell apart."""
    return Registry(
        providers={"zai": Provider("zai", "ZAI_KEY",
                                   base_url="https://api.z.ai/api/anthropic"),
                   "anthropic": Provider("anthropic", "ANTHROPIC_API_KEY")},
        models={"glm-5.2": Model("glm-5.2", "zai", "head"),
                "claude-sonnet-5": Model("claude-sonnet-5", "anthropic", "tail")},
        chains={"labeler": Chain("labeler", ("glm-5.2", "glm-5.2", "glm-5.2",
                                             "claude-sonnet-5",
                                             "claude-sonnet-5")),
                "oracle-anthropic": Chain("oracle-anthropic",
                                          ("claude-sonnet-5",))})


def _file_plan(reason: str = "billing", chain: str = "labeler") -> esc.Plan:
    """The plan (and body) a first escalation for `reason` is built from."""
    return esc.plan_escalation(reason, chain, f"the {chain} routine",
                               ["zai", "zai", "zai", "anthropic", "anthropic"],
                               WHEN, [])


def _open_with(body: str, number: int = 581) -> list[dict[str, str]]:
    return [{"number": number,
             "html_url": f"https://github.com/o/r/issues/{number}",
             "body": body}]


# ── the derivations: what keys the dedup (AC3) ───────────────────────────────

def test_marker_and_decision_id_derive_from_the_reason_not_the_chain():
    # One shared marker + id per REASON: the dedup key is the reason class, so
    # every chain that exhausts with the same cause lands on one issue and one
    # /decide resolves the set (issue #550). A per-chain key is the old rule.
    for reason in esc.NEEDS_HUMAN_REASONS:
        assert esc.marker_for(reason) == f"<!-- provider-escalation:{reason} -->"
        assert esc.decision_id_for(reason) == f"provider-{reason}"
    assert esc.marker_for("billing") == esc.marker_for("billing")
    assert esc.marker_for("billing") != esc.marker_for("quota")
    # The chain appears only in the per-chain membership record, never in the
    # dedup key.
    assert "labeler" not in esc.marker_for("billing")
    assert esc.affected_marker("labeler") == "<!-- affected:labeler -->"


def test_every_needs_human_reason_has_a_remediation():
    # The body's remediation is tailored to the reason — every reason that can
    # reach the escalation must carry one (a KeyError-shaped hole would file a
    # decision with no button to push).
    for reason in esc.NEEDS_HUMAN_REASONS:
        assert "**" in esc.remediation_for(reason)


def test_non_needs_human_reason_is_refused():
    # NEGATIVE CONTROL (the guard): a reason outside the needs-human set must
    # raise, not escalate — a transient or a dead id filing a HITL decision is
    # exactly the mis-routing the guard exists to stop, and the caller's `if:`
    # (class == 'needs-human') can only produce these reasons by drifting from
    # the classifier.
    with pytest.raises(ValueError, match="cannot escalate"):
        esc.remediation_for("rate-limit")
    with pytest.raises(ValueError, match="cannot escalate"):
        esc.plan_escalation("served", "labeler", "ctx", ["zai"], WHEN, [])


# ── AC1: reuse on match — zero new issues, detail accumulates ────────────────

def test_matching_open_issue_is_joined_not_duplicated():
    # POSITIVE CONTROL (AC1): an open issue carrying the REASON's marker means
    # a newly-exhausted chain joins it — plan says join, the body gains the
    # chain's detail line, and nothing about a second issue is even named.
    first = _file_plan()
    plan = esc.plan_escalation(
        "billing", "scout", "the product scout",
        ["zai", "anthropic", "anthropic"], WHEN, _open_with(first.body))
    assert plan.action == "join"
    assert plan.number == 581
    assert plan.title is None
    # The accumulated body: BOTH chains' detail lines, marker first, and the
    # new line inside the affected block (before the postamble), not after it.
    assert esc.marker_for("billing") in plan.body
    assert "<!-- affected:labeler -->" in plan.body
    assert "<!-- affected:scout -->" in plan.body
    assert "walked zai -> anthropic" in plan.body
    assert plan.body.index("<!-- affected:scout -->") < plan.body.index(
        "Until it is resolved")
    # One decision id serves every chain that joined — no per-chain id appears.
    assert "provider-billing" in plan.body
    assert "provider-scout" not in plan.body


def test_a_different_reason_does_not_reuse_the_open_issue():
    # The reuse is keyed on the reason: an open BILLING issue must not absorb
    # a QUOTA exhaustion (different button to push), so the quota chain files
    # its own issue — the dedup narrows to the same cause, no wider.
    first = _file_plan("billing")
    plan = esc.plan_escalation(
        "quota", "scout", "the product scout", ["zai", "anthropic"], WHEN,
        _open_with(first.body))
    assert plan.action == "file"
    assert esc.marker_for("quota") in plan.body
    assert esc.marker_for("billing") not in plan.body


def test_re_exhaustion_of_a_joined_chain_writes_nothing():
    # The membership marker: the same chain exhausting again next run (the
    # hourly cadence during an outage) must not append a duplicate detail line
    # every firing — the pre-#550 rule's quiet "still unusable" behavior.
    first = _file_plan()
    joined = esc.plan_escalation(
        "billing", "scout", "the product scout", ["zai", "anthropic"], WHEN,
        _open_with(first.body))
    again = esc.plan_escalation(
        "billing", "scout", "the product scout", ["zai", "anthropic"], WHEN,
        _open_with(joined.body))
    assert again.action == "already"
    assert again.body is None
    assert again.notice


def test_join_survives_a_rearranged_body():
    # A human may edit the accumulated body (drop the postamble anchor); the
    # join degrades to appending the detail line at the end rather than
    # failing or silently dropping the chain.
    first = _file_plan()
    trimmed = first.body[:first.body.index("Until it is resolved")]
    plan = esc.plan_escalation(
        "billing", "scout", "the product scout", ["zai", "anthropic"], WHEN,
        _open_with(trimmed))
    assert plan.action == "join"
    assert plan.body.rstrip("\n").endswith("<!-- affected:scout -->")


# ── AC2: file on no match — exactly one issue, unchanged shape ───────────────

def test_no_matching_open_issue_files_exactly_one():
    # NEGATIVE CONTROL (AC2): with no open matching issue the check still
    # fires — one new issue carrying the marker, the decision-gate label, the
    # reason-tailored remediation and both /decide options, so the escalation
    # cannot be weakened into never filing.
    plan = _file_plan()
    assert plan.action == "file"
    assert plan.number is None
    assert plan.title == "🚦 Provider unusable: billing"
    body = plan.body
    assert body.startswith(esc.marker_for("billing") + "\n")
    assert "🚦 DECISION NEEDED — `provider-billing`" in body
    assert "**Fund the account**" in body          # reason-tailored remediation
    assert "/decide yes provider-billing" in body  # the resolve line
    assert "/decide no provider-billing" in body
    assert "**yes** →" in body and "**no**  →" in body  # exactly two options
    assert "<!-- affected:labeler -->" in body     # the first chain's detail
    # The registry-sourced provider walk names what the chain tried.
    assert "walked zai -> anthropic" in body


def test_open_issues_without_the_marker_do_not_count():
    # The marker is the reuse key, not the label alone: other open
    # needs-decision issues (parked human decisions) must not absorb a
    # provider escalation.
    plan = esc.plan_escalation(
        "billing", "labeler", "the labeler routine", ["zai"], WHEN,
        [{"number": 7, "html_url": "u", "body": "an unrelated parked decision"}])
    assert plan.action == "file"


# ── the live half: run_escalation over a recording fake transport ────────────

class FakeGH:
    """Answers like the GitHub API for the calls run_escalation makes, and
    records every write so the tests can assert what shipped."""

    def __init__(self, open_bodies: list[str], label_exists: bool = True,
                 fail_on: tuple[str, ...] = ()) -> None:
        self.issues = [{"number": 100 + n,
                        "html_url": f"https://github.com/o/r/issues/{100 + n}",
                        "body": body}
                       for n, body in enumerate(open_bodies)]
        self.label_exists = label_exists
        self.fail_on = fail_on
        self.created: list[dict] = []
        self.updated: list[dict] = []
        self.label_created = False
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, url: str, token: str, payload=None):
        self.calls.append((method, url))
        if any(flag in url for flag in self.fail_on):
            return 500, {"message": "boom"}, {}
        if method == "GET" and f"/labels/{esc.DECISION_LABEL}" in url:
            return (200, {}, {}) if self.label_exists else (404, {}, {})
        if method == "POST" and url.endswith("/labels"):
            self.label_created = True
            return 201, {}, {}
        if method == "GET" and "/issues?" in url:
            return 200, self.issues, {}
        if method == "POST" and url.endswith("/issues"):
            self.created.append(dict(payload))
            return 201, {"number": 999,
                         "html_url": "https://github.com/o/r/issues/999"}, {}
        if method == "PATCH" and "/issues/" in url:
            self.updated.append(dict(payload))
            return 200, {}, {}
        raise AssertionError(f"unexpected call {method} {url}")


def test_live_reuse_performs_no_issue_create(capfd):
    # AC1 at the transport level: an open billing issue (filed by `labeler`)
    # + a newly-exhausted chain — here the Oracle's own, proving the two
    # surfaces share one issue — -> ZERO POSTs to /issues, exactly one body
    # PATCH, exit 0.
    first = _file_plan()
    gh = FakeGH(open_bodies=[first.body])
    code = esc.run_escalation(reg(), "oracle-anthropic", "billing",
                              "the Oracle's opposite-vendor review chain",
                              "o/r", "tok", when=WHEN, gh=gh)
    assert code == 0
    assert gh.created == []
    assert len(gh.updated) == 1
    assert "<!-- affected:labeler -->" in gh.updated[0]["body"]
    assert "<!-- affected:oracle-anthropic -->" in gh.updated[0]["body"]
    out = capfd.readouterr().out
    assert "::warning::" in out and "joining" in out


def test_live_no_match_creates_exactly_one_issue(capfd):
    # AC2 at the transport level: no open issue -> ONE create, carrying the
    # marker body and the decision label; no PATCH.
    gh = FakeGH(open_bodies=[])
    code = esc.run_escalation(reg(), "labeler", "quota", "the labeler routine",
                              "o/r", "tok", when=WHEN, gh=gh)
    assert code == 0
    assert len(gh.created) == 1
    assert gh.created[0]["labels"] == [esc.DECISION_LABEL]
    assert esc.marker_for("quota") in gh.created[0]["body"]
    assert "**Raise the cap or wait for the reset**" in gh.created[0]["body"]
    assert gh.updated == []
    out = capfd.readouterr().out
    assert "filing the shared issue" in out


def test_live_already_joined_is_a_pure_no_write(capfd):
    first = _file_plan()
    gh = FakeGH(open_bodies=[first.body])
    code = esc.run_escalation(reg(), "labeler", "billing", "the labeler routine",
                              "o/r", "tok", when=WHEN, gh=gh)
    assert code == 0
    assert gh.created == [] and gh.updated == []
    assert "::warning::" in capfd.readouterr().out


def test_live_creates_the_label_on_demand():
    # The ensure-label idiom: a 404 on the label GET creates it; a 422 race
    # with a sibling run is tolerated (FakeGH's 201 stands in for both).
    gh = FakeGH(open_bodies=[], label_exists=False)
    code = esc.run_escalation(reg(), "labeler", "billing", "ctx", "o/r", "tok",
                              when=WHEN, gh=gh)
    assert code == 0
    assert gh.label_created


def test_live_api_failure_is_red_not_silent(capfd):
    # An API error must fail loudly (exit 1) — a silently-missing escalation
    # is the exact hole a dedup rewrite must not open.
    gh = FakeGH(open_bodies=[], fail_on=("/issues?",))
    code = esc.run_escalation(reg(), "labeler", "billing", "ctx", "o/r", "tok",
                              when=WHEN, gh=gh)
    assert code == 1
    assert "::error::" in capfd.readouterr().out


def test_live_pull_requests_are_not_open_issues():
    # The list endpoint returns PRs too; one carrying the marker text in its
    # body must not absorb the escalation (PRs are not decision threads).
    first = _file_plan()
    gh = FakeGH(open_bodies=[])
    gh.issues = [{"number": 42, "html_url": "u", "body": first.body,
                  "pull_request": {}}]
    code = esc.run_escalation(reg(), "labeler", "billing", "ctx", "o/r", "tok",
                              when=WHEN, gh=gh)
    assert code == 0
    assert len(gh.created) == 1


def test_both_surfaces_marker_family_is_shared_with_reeve():
    # The marker prefix tools/reeve mirrors (PROVIDER_ESCALATION_MARKER) so its
    # greenlight-select skips these threads: every marker this module writes
    # must start with it, and the Oracle's old private family must be gone.
    for reason in esc.NEEDS_HUMAN_REASONS:
        assert esc.marker_for(reason).startswith("<!-- provider-escalation:")


def test_cli_escalate_arg_plumbing_and_missing_token_guard(monkeypatch,
                                                            capfd, tmp_path):
    # The workflows call `python3 -m model_registry escalate <chain> --reason
    # … --context … --repo … --token-env …`; the drift guard pins the workflow
    # side of that line, this pins the CLI side — a renamed flag would pass
    # every other test and redden both escalation surfaces at runtime. Drives
    # main() end to end with the named env var UNSET, so it also proves the
    # fail-loud guard: no token is a red `::error::`, never a silent skip.
    conf = tmp_path / "registry.conf"
    conf.write_text(
        "[provider:zai]\nsecret = ZAI_KEY\n"
        "base_url = https://api.z.ai/api/anthropic\n\n"
        "[model:glm-5.2]\nprovider = zai\nnotes = head\n\n"
        "[chain:labeler]\nmodels = glm-5.2\n")
    monkeypatch.delenv("ESCALATION_TOKEN", raising=False)
    from model_registry import cli
    code = cli.main(["--path", str(conf), "escalate", "labeler",
                     "--reason", "billing", "--context", "the labeler routine",
                     "--repo", "o/r", "--token-env", "ESCALATION_TOKEN"])
    assert code == 1
    out = capfd.readouterr().out
    assert "::error::no token in $ESCALATION_TOKEN" in out
    assert "labeler" in out
