"""Standing approval modes (issue #446) — the pure policy and its conf keys.

``approval.py`` decides, from a parked decision's labels and text, whether
the greenlight loop may resolve it on its own (``auto``), must leave it to a
human (``deny``), or asks as before (``ask``). Every rule below has a positive
case and a negative control, and the security property the module exists for
— *only a trusted signal loosens; untrusted text only tightens* — is pinned
from both directions. The poll/select wiring that consumes this lives in
``test_approval_poll.py``.
"""

from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from reeve import approval, config

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

OWNER_RULES = approval.Rules(auto=frozenset({"docs"}), deny=frozenset({"gates"}))
DOCS_LABEL = approval.CATEGORY_LABELS["docs"]
GATES_LABEL = approval.CATEGORY_LABELS["gates"]


def mode(labels=(), title="", body="", verified=(), rules=OWNER_RULES):
    return approval.mode_for(approval.classify(labels, title, body, verified), rules)[0]


# ---------------------------------------------------------------------------
# Unmatched asks — the default, pinned
# ---------------------------------------------------------------------------

def test_unclassified_decision_asks():
    # Issue #446 Done-when: "unmatched asks (pinned)".
    assert mode(title="Pick a gallery order", body="Which order reads best?") == approval.MODE_ASK


def test_empty_rules_ask_even_for_a_verified_docs_label():
    # The fail-safe default: no conf rules → nothing auto-approves, nothing denies.
    assert mode(labels=[DOCS_LABEL], verified=[DOCS_LABEL], rules=approval.Rules()) == approval.MODE_ASK
    assert mode(body="edit .github/workflows/ci.yml", rules=approval.Rules()) == approval.MODE_ASK


# ---------------------------------------------------------------------------
# Loosening: only a VERIFIED label reaches auto
# ---------------------------------------------------------------------------

def test_verified_docs_label_auto_approves():
    mode_, cats = approval.mode_for(
        approval.classify([DOCS_LABEL], "Fix a typo in docs/growth.md", "", [DOCS_LABEL]),
        OWNER_RULES,
    )
    assert mode_ == approval.MODE_AUTO
    assert cats == {"docs"}


def test_unverified_docs_label_only_asks():
    # NEGATIVE CONTROL for the line above: the same label, its applier not
    # verified (a bot, a read-only account, an unknown history) → ask.
    assert mode(labels=[DOCS_LABEL], title="Fix a typo in docs/growth.md") == approval.MODE_ASK


def test_untrusted_text_cannot_loosen():
    # A body naming only doc paths, with no label, is exactly what an
    # attacker would write — it must never reach auto.
    body = "Only touches docs/decision-gate.md, README.md and tools/reeve/README.md."
    assert mode(title="Docs-only follow-up", body=body) == approval.MODE_ASK
    assert "docs" not in approval.classify([], "Docs-only follow-up", body).categories


def test_text_cannot_loosen_even_a_category_the_conf_auto_approves():
    # A (strange but legal) conf that auto-approves `gates`: a text-only gates
    # hit is untrusted, so it still asks — the asymmetry is in the rule, not
    # in the shipped conf happening to deny gates.
    rules = approval.Rules(auto=frozenset({"gates"}))
    assert mode(body="touches scripts/gate.sh", rules=rules) == approval.MODE_ASK
    # Control: the same category vouched for by a verified label → auto.
    assert mode(labels=[GATES_LABEL], verified=[GATES_LABEL], body="touches scripts/gate.sh",
                rules=rules) == approval.MODE_AUTO


def test_a_verified_label_that_is_not_present_counts_for_nothing():
    assert mode(labels=[], verified=[DOCS_LABEL]) == approval.MODE_ASK


def test_mixed_categories_ask():
    # docs (auto) + gates (neither auto nor deny here) → not ALL auto → ask.
    rules = approval.Rules(auto=frozenset({"docs"}))
    assert mode(labels=[DOCS_LABEL, GATES_LABEL], verified=[DOCS_LABEL, GATES_LABEL],
                rules=rules) == approval.MODE_ASK


# ---------------------------------------------------------------------------
# Tightening: text and labels may always reach deny; deny beats auto
# ---------------------------------------------------------------------------

def test_docs_label_plus_gate_text_asks():
    # Tighten wins: a verified docs-only label cannot launder a body that
    # names gate machinery — the text blocks auto (owner ruling 2026-10-03:
    # text tightens to ask, never to deny on its own).
    mode_, cats = approval.mode_for(
        approval.classify([DOCS_LABEL], "Docs follow-up",
                          "Also tweak .github/workflows/ci.yml", [DOCS_LABEL]),
        OWNER_RULES,
    )
    assert mode_ == approval.MODE_ASK
    assert cats == {"docs", "gates"}
    # NEGATIVE CONTROL: the same verified label without the gate text → auto.
    assert approval.mode_for(
        approval.classify([DOCS_LABEL], "Docs follow-up", "Reword docs/growth.md", [DOCS_LABEL]),
        OWNER_RULES,
    )[0] == approval.MODE_AUTO


def test_gate_label_denies_whoever_applied_it():
    assert mode(labels=[GATES_LABEL]) == approval.MODE_DENY


def test_gate_text_alone_never_denies():
    # Owner ruling 2026-10-03: issue text cannot tell "edits gate.sh" from
    # "names gate.sh as its check", so text alone may only block auto. A
    # full deny takes the gate label (pinned both ways).
    assert mode(body="Done when: gate.sh --slice green") == approval.MODE_ASK
    assert mode(labels=[GATES_LABEL], body="Done when: gate.sh --slice green") == approval.MODE_DENY


@pytest.mark.parametrize("text", [
    "Edit scripts/reeve-perms-check.sh",
    "the wright perms-check needs a new deny",
    "scripts/docs-check.sh should assert it",
    "gate.sh --slice must cover it",
    "bump .github/workflows/ci.yml",
    "widen .claude/reeve-settings.json",
    "the shared .claude/settings.json allow list",
])
def test_each_gate_pattern_blocks_auto(text):
    # Each pattern classifies as gates, so a verified docs-only label can no
    # longer auto-approve — the thread asks. Text alone never denies.
    assert mode(labels=[DOCS_LABEL], verified=[DOCS_LABEL], body=text) == approval.MODE_ASK
    assert mode(body=text) == approval.MODE_ASK
    assert "gates" in approval.classify([], "", text).untrusted


def test_plain_check_sh_is_not_a_gate_pattern():
    # Deliberate (approval.GATE_TEXT_PATTERNS): `./scripts/check.sh green` is
    # near-universal Done-when boilerplate; the owner's list names the
    # *-check.sh family, not the runner — so it does not block auto.
    assert mode(labels=[DOCS_LABEL], verified=[DOCS_LABEL],
                body="Done when: ./scripts/check.sh green") == approval.MODE_AUTO


def test_gate_label_with_no_deny_rule_only_asks():
    # NEGATIVE CONTROL: the deny comes from the rule, not from the label.
    assert mode(labels=[GATES_LABEL],
                rules=approval.Rules(auto=frozenset({"docs"}))) == approval.MODE_ASK


def test_normalization_defeats_case_and_zero_width_smuggling():
    # A smuggled gate path must still block a verified docs label's auto.
    docs = dict(labels=[DOCS_LABEL], verified=[DOCS_LABEL])
    assert mode(body="bump .GITHUB/WORKFLOWS/CI.YML", **docs) == approval.MODE_ASK
    assert mode(body="bump c​i.yml", **docs) == approval.MODE_ASK        # zero-width space
    assert mode(body="bump ｃｉ.yml", **docs) == approval.MODE_ASK              # fullwidth (NFKC)


def test_live_tree_gate_machinery_all_classifies_as_gates():
    # Positive control against the REAL tree: every file the owner named as
    # gate machinery, written as the path an issue would cite, lands in
    # `gates` — so a new *-check.sh or *-settings.json backstop is covered by
    # construction, not by remembering to extend a list.
    paths = [p.relative_to(REPO_ROOT).as_posix() for p in REPO_ROOT.glob("scripts/*-check.sh")]
    paths += [p.relative_to(REPO_ROOT).as_posix() for p in REPO_ROOT.glob(".claude/*-settings.json")]
    paths += ["scripts/gate.sh", ".github/workflows/ci.yml"]
    assert any(p.endswith("-perms-check.sh") for p in paths)  # the fixture is not vacuous
    for path in paths:
        assert (REPO_ROOT / path).is_file(), path
        assert "gates" in approval.text_hits("", f"touches `{path}`"), path


def test_live_tree_docs_paths_never_classify():
    # NEGATIVE CONTROL for the live-tree test: doc paths hit no pattern.
    for path in ["docs/decision-gate.md", "README.md", "tools/reeve/README.md", "PM.md",
                 "CLAUDE.md", "docs/growth.md"]:
        assert approval.text_hits("", f"touches `{path}`") == {}, path


# ---------------------------------------------------------------------------
# Rules — the closed vocabulary, validated at construction
# ---------------------------------------------------------------------------

def test_rules_refuse_an_unknown_category():
    with pytest.raises(ValueError, match="unknown approval categories"):
        approval.Rules(auto=frozenset({"typos"}))


def test_rules_refuse_a_category_in_both_sets():
    with pytest.raises(ValueError, match="both auto-approve and deny"):
        approval.Rules(auto=frozenset({"docs"}), deny=frozenset({"docs"}))


def test_every_category_has_a_label():
    assert set(approval.CATEGORY_LABELS) == set(approval.CATEGORIES)


def test_docs_has_no_text_pattern():
    # Structural: no text signal may ever name the auto-approve category.
    assert "docs" not in approval.TEXT_PATTERNS


def test_label_names_match_case_insensitively_like_github():
    # GitHub label names are case-insensitive: a repo label created as
    # `Gate-Machinery` must still deny, and a verified `Docs-Only` must still
    # reach auto — or the rule silently stops firing.
    assert mode(labels=["Gate-Machinery"]) == approval.MODE_DENY
    assert mode(labels=["DOCS-ONLY"], verified=["docs-only"]) == approval.MODE_AUTO
    assert approval.loosening_labels(["Docs-Only"], OWNER_RULES) == [DOCS_LABEL]
    # Negative control: a different name is still not the label.
    assert mode(labels=["gate-machinery-ish"]) == approval.MODE_ASK
    assert mode(labels=["docs"], verified=["docs"]) == approval.MODE_ASK


def test_label_applier_matches_the_label_case_insensitively():
    events = [_ev("labeled", "Docs-Only", "shaiss", "2026-09-03T00:00:00Z")]
    assert approval.label_applier(events, DOCS_LABEL) == "shaiss"
    # Negative control: another label's event never names the applier.
    assert approval.label_applier([_ev("labeled", "docs", "shaiss", "x")], DOCS_LABEL) == ""


def test_loosening_labels_are_only_the_auto_categories():
    labels = [DOCS_LABEL, GATES_LABEL, "enhancement"]
    assert approval.loosening_labels(labels, OWNER_RULES) == [DOCS_LABEL]
    assert approval.loosening_labels(labels, approval.Rules()) == []   # nothing can loosen


def test_standing_rule_login_names_the_rule_not_a_person():
    assert approval.standing_rule_login({"docs"}) == "standing-rule:docs"


# ---------------------------------------------------------------------------
# Who applied the label — the 👍 bar, bots refused by identity
# ---------------------------------------------------------------------------

def _ev(event, label, actor, at):
    return {"event": event, "label": label, "actor": actor, "created_at": at}


def test_label_applier_is_the_newest_labeled_event():
    events = [
        _ev("labeled", DOCS_LABEL, "driveby", "2026-09-01T00:00:00Z"),
        _ev("unlabeled", DOCS_LABEL, "shaiss", "2026-09-02T00:00:00Z"),
        _ev("labeled", DOCS_LABEL, "shaiss", "2026-09-03T00:00:00Z"),
        _ev("labeled", "enhancement", "bot[bot]", "2026-09-04T00:00:00Z"),
    ]
    assert approval.label_applier(events, DOCS_LABEL) == "shaiss"
    # Order-independent: the history may arrive newest-first.
    assert approval.label_applier(list(reversed(events)), DOCS_LABEL) == "shaiss"


def test_label_applier_unknown_history_is_empty():
    assert approval.label_applier([], DOCS_LABEL) == ""
    assert approval.label_applier([_ev("unlabeled", DOCS_LABEL, "shaiss", "x")], DOCS_LABEL) == ""


def test_label_actor_trusted_holds_the_upvote_bar():
    lookups: list[str] = []

    def authorized(login):
        lookups.append(login)
        return {"shaiss": True, "driveby": False}[login]

    assert approval.label_actor_trusted("shaiss", authorized) is True
    assert approval.label_actor_trusted("driveby", authorized) is False
    # Bots are refused by identity — no lookup is ever spent on them.
    assert approval.label_actor_trusted("github-actions[bot]", authorized) is False
    assert approval.label_actor_trusted("dependabot[bot]", authorized) is False
    assert approval.label_actor_trusted("", authorized) is False
    assert lookups == ["shaiss", "driveby"]


# ---------------------------------------------------------------------------
# The 👎 grace window
# ---------------------------------------------------------------------------

POSTED = "2026-09-01T06:00:00Z"
POSTED_DT = datetime(2026, 9, 1, 6, 0, tzinfo=timezone.utc)


def test_grace_elapses_after_the_window():
    assert approval.grace_elapsed(POSTED, POSTED_DT + approval.AUTO_APPROVE_GRACE) is True
    assert approval.grace_elapsed(POSTED, POSTED_DT + timedelta(hours=24)) is True


def test_grace_not_elapsed_inside_the_window():
    # A same-day workflow_dispatch must not auto-approve.
    assert approval.grace_elapsed(POSTED, POSTED_DT + timedelta(minutes=5)) is False
    assert approval.grace_elapsed(
        POSTED, POSTED_DT + approval.AUTO_APPROVE_GRACE - timedelta(seconds=1)) is False


def test_grace_unparseable_stamp_never_elapses():
    assert approval.grace_elapsed("", POSTED_DT + timedelta(days=30)) is False
    assert approval.grace_elapsed("yesterday", POSTED_DT + timedelta(days=30)) is False


def test_grace_reads_a_naive_clock_as_utc():
    assert approval.grace_elapsed(POSTED, datetime(2026, 9, 2, 6, 0)) is True


def test_grace_window_is_under_the_daily_cadence():
    # An on-time next scheduled run (~24h later) must qualify.
    assert approval.AUTO_APPROVE_GRACE < timedelta(hours=24)
    assert approval.grace_ends(POSTED) == "2026-09-02T02:00:00Z"


# ---------------------------------------------------------------------------
# The conf keys (config.py) — strict parse, fail-safe defaults
# ---------------------------------------------------------------------------

def _conf(tmp_path, text):
    p = tmp_path / "reeve.conf"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_approval_keys_default_empty():
    cfg = config.Config()
    assert cfg.approve_auto == () and cfg.approve_deny == ()
    assert cfg.approval_rules() == approval.Rules()


def test_approval_keys_absent_from_a_file_default_empty(tmp_path):
    cfg = config.load(_conf(tmp_path, "enabled: true\n"))
    assert cfg.approval_rules() == approval.Rules()


def test_approval_keys_parse(tmp_path):
    cfg = config.load(_conf(tmp_path, "approve_auto: docs\napprove_deny:  gates \n"))
    assert cfg.approve_auto == ("docs",)
    assert cfg.approve_deny == ("gates",)
    assert cfg.approval_rules() == OWNER_RULES


def test_approval_key_may_list_several_or_none(tmp_path):
    cfg = config.load(_conf(tmp_path, "approve_auto: docs, gates\napprove_deny:\n"))
    assert cfg.approve_auto == ("docs", "gates")
    assert cfg.approve_deny == ()


@pytest.mark.parametrize("line,match", [
    ("approve_auto: typos", "unknown category 'typos'"),
    ("approve_deny: gate", "unknown category 'gate'"),
    ("approve_auto: Docs", "unknown category 'Docs'"),        # case is not folded
    ("approve_auto: docs,", "empty item"),
    ("approve_auto: docs,,gates", "empty item"),
    ("approve_auto: docs, docs", "names a category twice"),
])
def test_bad_approval_list_raises(tmp_path, line, match):
    with pytest.raises(ValueError, match=match):
        config.load(_conf(tmp_path, line + "\n"))


def test_a_category_in_both_lists_raises(tmp_path):
    with pytest.raises(ValueError, match=r"\['docs'\] are in both"):
        config.load(_conf(tmp_path, "approve_auto: docs\napprove_deny: docs, gates\n"))


def test_duplicate_approval_key_raises(tmp_path):
    with pytest.raises(ValueError, match="duplicate key 'approve_auto'"):
        config.load(_conf(tmp_path, "approve_auto: docs\napprove_auto: docs\n"))


def test_get_renders_a_category_list_as_the_conf_writes_it(tmp_path):
    path = _conf(tmp_path, "approve_auto: docs, gates\n")
    assert config.get("approve_auto", path=path) == "docs, gates"
    assert config.get("approve_deny", path=path) == ""


def test_committed_conf_rules_parse_into_the_closed_vocabulary():
    # Values are not pinned (a reviewed flip must stay green, the
    # test_config.py convention); what may never regress is that the
    # committed rules parse and name only categories the code can classify.
    rules = config.load(str(REPO_ROOT / config.DEFAULT_PATH)).approval_rules()
    assert set(rules.auto) | set(rules.deny) <= set(approval.CATEGORIES)


# ---------------------------------------------------------------------------
# The #760 bindings: the label vouches only for the greenlit text
# ---------------------------------------------------------------------------

def test_label_applied_returns_the_newest_event_and_its_time():
    events = [
        _ev("labeled", DOCS_LABEL, "early", "2026-08-01T00:00:00Z"),
        _ev("labeled", DOCS_LABEL, "shaiss", "2026-08-20T07:00:00Z"),
    ]
    assert approval.label_applied(events, DOCS_LABEL) == ("shaiss", "2026-08-20T07:00:00Z")
    assert approval.label_applied([], DOCS_LABEL) == ("", "")


def test_label_vouches_only_at_or_after_the_greenlight():
    gl = "2026-08-20T06:00:00Z"
    assert approval.label_vouches("2026-08-20T07:00:00Z", gl)
    assert approval.label_vouches(gl, gl)                        # same second counts
    # NEGATIVE CONTROLS: before the greenlight, or an unknowable stamp.
    assert not approval.label_vouches("2026-08-19T00:00:00Z", gl)
    assert not approval.label_vouches("", gl)
    assert not approval.label_vouches("2026-08-20T07:00:00Z", "")


def test_text_digest_is_the_documented_canonical_form():
    import hashlib
    want = hashlib.sha256("T\nB\n".encode("utf-8")).hexdigest()[:16]
    assert approval.text_digest("T", "B") == want
    # A null body hashes as "" — the same as jq's `.body // ""`.
    assert approval.text_digest("T", None) == approval.text_digest("T", "")
    assert len(want) == 16 and all(c in "0123456789abcdef" for c in want)


def test_text_digest_changes_on_any_edit():
    base = approval.text_digest("Fix docs", "Reword it.")
    assert approval.text_digest("Fix docs", "Reword it. ") != base   # trailing space
    assert approval.text_digest("Fix docs", "Reword it.\r\n") != base
    assert approval.text_digest("Fix Docs", "Reword it.") != base


def test_text_binding_blocker():
    digest = approval.text_digest("T", "B")
    assert approval.text_binding_blocker(digest, "T", "B") == ""
    # NEGATIVE CONTROLS: a mismatch, and a marker without a digest.
    assert "changed since the greenlight" in approval.text_binding_blocker(digest, "T", "B2")
    assert "does not record" in approval.text_binding_blocker("", "T", "B")
    assert "does not record" in approval.text_binding_blocker(None, "T", "B")


PARITY_CASES = [
    ("Fix the docs", "Reword the paragraph."),
    ("Trailing newlines", "body ends in newlines\n\n\n"),
    ("CRLF", "line one\r\nline two\r\n"),
    ("Unicode — ünïcödé ✓ 🚦", "zero\u200bwidth and emoji 🚀\n"),
    ("Null body", None),
    ("", ""),
]


@pytest.mark.parametrize("title,body", PARITY_CASES)
def test_text_digest_matches_the_wrappers_shell_pipeline(tmp_path, title, body):
    # The wrapper computes the digest as `gh api … --jq '<filter>' | sha256sum`
    # (bytes piped, never through $(...)); jq -r with the same filter is that
    # pipeline offline. Python and the shell must agree byte for byte.
    import json
    import shutil
    import subprocess
    if not (shutil.which("jq") and shutil.which("sha256sum")):
        pytest.skip("jq/sha256sum not installed")
    issue = tmp_path / "issue.json"
    issue.write_text(json.dumps({"title": title, "body": body}), encoding="utf-8")
    out = subprocess.run(
        ["bash", "-c", "jq -r '.title + \"\\n\" + (.body // \"\")' \"$1\" | sha256sum", "_", str(issue)],
        check=True, capture_output=True, text=True,
    ).stdout
    assert out[:16] == approval.text_digest(title, body)


def test_text_digest_cross_pin_with_the_wrapper_selftest():
    # greenlight-helper.sh --selftest pins the same value for the same text:
    # change the definition on either side and one of the two fails.
    assert approval.text_digest("Docs — ünïcödé ✓", "line one\r\nline two\n\n\n") == "12e3e433b82bf3ce"
