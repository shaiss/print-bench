"""gitstore — add-only writer, diff-tree guard, pushes, tip continuity (P0 acceptance). Real temp repos (git init), no network.

Owner: H1 (the placeholders). The continuity-table and mark-name tests are
LIVE: ``continuity_verdict`` and the name helpers are architect-implemented
and frozen, and ``fixtures/continuity_cases.json`` is the table Reeve's
``provenance-foreign-tip`` port must also pass (critique item 16).
"""

from __future__ import annotations

import json

import pytest

from conftest import FIXTURES

CASES = json.loads((FIXTURES / "continuity_cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_continuity_table(case):
    from provenance.gitstore import Mark, continuity_verdict
    kw = {"max_chain": case["max_chain"]} if "max_chain" in case else {}
    v = continuity_verdict(ref=case["ref"], tip=case["tip"], marks=[Mark(**m) for m in case["marks"]],
                           first_parent=lambda s: case["parents"].get(s), **kw)
    assert v.verdict == case["expect"], v.reason
    if "chain" in case:
        assert list(v.chain) == case["chain"]
    assert v.accepted == (case["expect"] == "ok")


def test_continuity_table_covers_every_verdict_and_both_refs():
    from provenance.gitstore import VERDICTS
    assert {c["expect"] for c in CASES} == set(VERDICTS)
    assert {c["ref"] for c in CASES} == {"provenance", "provenance-site"}


def test_mark_names_round_trip_and_refuse():
    from provenance.gitstore import intent_name, parse_mark_name, tip_name
    sha = "a1" * 20
    assert parse_mark_name(tip_name("provenance-site", sha)) == ("tip", "provenance-site", sha)
    assert parse_mark_name(intent_name("provenance", sha)) == ("intent", "provenance", sha)
    for bad in ("tip-provenance-" + "A1" * 20, "tip-provenance-" + sha[:39], "tip-other-" + sha,
                "checkpoint-provenance-" + sha, "intent-provenance-site-" + sha + "0", "site"):
        assert parse_mark_name(bad) is None
    with pytest.raises(ValueError):
        tip_name("telemetry", sha)


@pytest.mark.skip(reason="builder: implement")
def test_treebuilder_adds_new_blobs_without_touching_existing():
    """Seeded from a tip, add() of a new path writes it; add() of an existing path with identical CONTENT is a no-op (False) — for *.json.gz compared decompressed, so a re-gzipped identical document (other zlib, other level) is a no-op too (critique 19); with different content raises GuardViolation; no existing blob ever passes through the working tree."""


@pytest.mark.skip(reason="builder: implement")
def test_guard_refuses_delete():
    """Negative: a new commit missing any old path → GuardViolation('D …')."""


@pytest.mark.skip(reason="builder: implement")
def test_guard_refuses_modify_outside_state_json():
    """Negative: M under receipts/ or raw/ → GuardViolation; M of state.json passes."""


@pytest.mark.skip(reason="builder: implement")
def test_guard_refuses_zero_byte_blob():
    """Negative: 'a raw file becomes 0 B' → GuardViolation (the telemetry #D2 class)."""


@pytest.mark.skip(reason="builder: implement")
def test_guard_refuses_guard_file_change():
    """Negative: changing vercel.json or scripts/vercel-ignore-build.sh after bootstrap → GuardViolation (the writer never re-adds them, so this fires only on a forged tree)."""


@pytest.mark.skip(reason="builder: implement")
def test_identical_tree_pushes_nothing():
    """guard_diff returns [] for an identical tree and the orchestrator skips the push (a repeat dispatch pushes no commit)."""


@pytest.mark.skip(reason="builder: implement")
def test_scan_marks_reads_the_artifact_list():
    """scan_marks over a FakeGitHub /actions/artifacts with 150 unrelated artifacts (site, stls…) before the checkpoint: pages until a VERIFIED tip mark per ref, then stops; a mark from a run on another branch, with event pull_request, path other than provenance.yml, or head_sha off main's first-parent history is rejected (counted); the horizon stops paging."""


@pytest.mark.skip(reason="builder: implement")
def test_quiet_day_then_deleted_ref():
    """Critique 3, end to end over a temp repo: 25 no-op runs (each re-uploading tip-provenance-C) keep the tip ok; deleting the ref then makes the next harvest refuse (deleted, exit 3) — never a silent re-bootstrap."""


@pytest.mark.skip(reason="builder: implement")
def test_rollback_to_an_older_declared_sha_is_refused():
    """Critique 4, over a temp repo: force-pushing provenance back to an older checkpointed sha → foreign, exit 3."""


@pytest.mark.skip(reason="builder: implement")
def test_push_ff_retries_transport_not_rejections():
    """A transport failure retries the SAME commit up to 3x then raises GitError; ANY non-ff rejection raises ForeignTip and never rebuilds (critique 21)."""


@pytest.mark.skip(reason="builder: implement")
def test_derived_push_uses_force_with_lease():
    """provenance-site is pushed with --force-with-lease on the planned old tip; a lease failure raises ForeignTip."""


@pytest.mark.skip(reason="builder: implement")
def test_push_error_never_carries_the_token():
    """Critique 12: a push to a local remote that fails with token 'ghs_TESTTOKEN' set raises GitError whose message contains neither the token nor base64('x-access-token:ghs_TESTTOKEN'); the credential reached git through GIT_CONFIG_COUNT/KEY_0/VALUE_0 (env), not argv; '::add-mask::<b64>' was printed once; fetches ran with no credential."""


@pytest.mark.skip(reason="builder: implement")
def test_guard_blobs_come_from_data_branch_guard():
    """guard_blobs: vercel.json and scripts/vercel-ignore-build.sh (mode 100755) equal .github/data-branch-guard/* byte-for-byte; guard_drift names a path whose evidence bytes differ from main's."""
