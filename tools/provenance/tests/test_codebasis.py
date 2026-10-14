"""codebasis — GitCodeBasis over a FakeGitReader built from fixtures/codebasis + fixtures/main_history.

Owner: H4. Each test's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e, the critique round's items 9 and
26).
"""

from __future__ import annotations

import pytest

from _serving_helpers import MAIN_REF, REGISTRY, fixture_codebasis, fixture_git
from conftest import codebasis_blob
from fakes import FakeCommit, FakeGitReader
from provenance import codebasis
from provenance.codebasis import GitCodeBasis, basis_kind, main_at, parse_registry_chains
from provenance.protocols import Basis, CodeBasis
from provenance.serving import ts_epoch

A720 = "a720a6bddcd1c2d9ecc6bd5ae2c8b161f3e95e9f"   # main 2026-09-05, the routines' head 09-07..09-12
M0987 = "0987cd19e462779505d8e19c8b7375325fdcd3a5"  # main 2026-10-11T15:48:59Z
M44E3 = "44e33367"                                   # main 2026-10-11T12:49:50Z (first parent of 0987cd19)
F4E3 = "f4e36eb91e2d2c8306a55e262575b417d0a27a20"   # #636 head, run 38161046420
DAE8 = "dae83d67a884afa3d054473640b1299cce640445"   # main 2026-08-10 (pre-#326 design-run.yml)
DESIGN_RUN = (".github/workflows/design-run.yml")

V1 = b"[provider:zai]\nsecret = ZAI_KEY\n\n[model:glm-5.2]\nprovider = zai\nnotes = n\n\n" \
     b"[model:glm-4.6]\nprovider = zai\nnotes = n\n\n[chain:oracle-glm]\nmodels = glm-5.2\n"
V2 = V1.replace(b"models = glm-5.2", b"models = glm-4.6")


def _sha(c: str) -> str:
    return (c * 40)[:40]


def test_is_a_codebasis():
    assert isinstance(GitCodeBasis(FakeGitReader([])), CodeBasis)


def test_head_basis_for_schedule():
    """schedule/workflow_dispatch → Basis('head', run.head_sha)."""
    cb = fixture_codebasis()
    for event in ("schedule", "workflow_dispatch"):
        b = cb.basis_for("design-run.yml", event, A720, "2026-09-12T00:23:08Z")
        assert b == Basis("head", A720, None)
        assert cb.file_at(b, DESIGN_RUN) == codebasis_blob(A720, DESIGN_RUN)
    # Any other workflow/event is the head too — including auto-review/oracle on a non-PR event.
    assert basis_kind("auto-review.yml", "workflow_dispatch") == "head"
    assert basis_kind("labeler.yml", "push") == "head"
    # Negative control: the same run as a pull_request of auto-review is NOT a head basis.
    assert basis_kind("auto-review.yml", "pull_request") == "merge"
    assert cb.basis_for("design-run.yml", "schedule", None, "2026-09-12T00:23:08Z").reason == "no-head-sha"


def test_merge_basis_for_auto_review():
    """auto-review pull_request → Basis('merge', head, main@created_at)."""
    cb = fixture_codebasis(auto_merge=[(M0987, F4E3)])
    b = cb.basis_for("auto-review.yml", "pull_request", F4E3, "2026-10-11T17:46:29Z")
    assert b == Basis("merge", F4E3, M0987)
    assert cb.file_at(b, REGISTRY) == codebasis_blob(F4E3, REGISTRY)
    # main@T is the last first-parent commit at or before T (committer date): one second
    # before 0987cd19 landed, main was its first parent 44e33367.
    early = cb.basis_for("auto-review.yml", "pull_request", F4E3, "2026-10-11T15:48:58Z")
    assert early.kind == "merge" and early.main_sha.startswith(M44E3)
    assert cb.basis_for("auto-review.yml", "pull_request", F4E3, "2026-10-11T15:48:59Z").main_sha == M0987
    # The merge tree, not the head: file_at reads merge_tree_read(main, head).
    git = fixture_git(merges={(M0987, F4E3): ({REGISTRY: b"merged"}, set())})
    assert GitCodeBasis(git).file_at(Basis("merge", F4E3, M0987), REGISTRY) == b"merged"


def _oracle_git() -> FakeGitReader:
    t = ts_epoch("2026-08-22T03:13:28Z")
    m0, m1, m2 = _sha("1"), _sha("2"), _sha("3")
    return FakeGitReader([
        FakeCommit(m0, [], t - 7200, files={REGISTRY: V1}, changed=[REGISTRY]),
        FakeCommit(m1, [m0], t + 20 * 60, files={REGISTRY: V2}, changed=[REGISTRY]),
        FakeCommit(m2, [m1], t + 3 * 3600, files={REGISTRY: V2}, changed=["README.md"]),
    ], refs={MAIN_REF: m2})


def test_main_basis_for_oracle_uses_checkout():
    """oracle pull_request with checkout=(started, completed) → Basis('main', None, main@started); without a checkout interval → main@created_at, ambiguous (reason 'no-checkout-step')."""
    cb = GitCodeBasis(_oracle_git())
    created = "2026-08-22T03:13:28Z"
    b = cb.basis_for("oracle.yml", "pull_request", _sha("f"), created,
                     checkout=("2026-08-22T03:53:28Z", "2026-08-22T03:53:31Z"))
    assert b == Basis("main", None, _sha("2"))
    assert cb.chain_models(b, "oracle-glm") == ("glm-4.6",)
    no_co = cb.basis_for("oracle.yml", "pull_request", _sha("f"), created)
    assert (no_co.main_sha, no_co.ambiguous, no_co.reason) == (_sha("1"), True, "no-checkout-step")
    # A registry change within 15 minutes of the checkout step (here 10 minutes after it ends).
    near = cb.basis_for("oracle.yml", "pull_request", _sha("f"), created,
                        checkout=("2026-08-22T03:20:00Z", "2026-08-22T03:23:28Z"))
    assert (near.main_sha, near.ambiguous, near.reason) == (_sha("1"), True, "main-changed-near-checkout")


def test_registry_change_within_the_window_before_created_is_ambiguous():
    """merge: a main commit touching the registry or the workflow in (created − 15 min, created] → ambiguous; at created − 15 min exactly (open bound) or 16 min before → not."""
    t = ts_epoch("2026-10-01T12:00:00Z")
    main0, main1, head = _sha("a"), _sha("b"), _sha("c")
    git = FakeGitReader([
        FakeCommit(main0, [], t - 86400, files={REGISTRY: V1}, changed=[REGISTRY]),
        FakeCommit(main1, [main0], t - 300, files={REGISTRY: V1}, changed=[".github/workflows/auto-review.yml"]),
        FakeCommit(head, [main0], t - 600),
    ], refs={MAIN_REF: main1}, merges={(main1, head): ({REGISTRY: V1}, set()), (main0, head): ({REGISTRY: V1}, set())})
    cb = GitCodeBasis(git)
    b = cb.basis_for("auto-review.yml", "pull_request", head, "2026-10-01T12:00:00Z")
    assert (b.main_sha, b.ambiguous, b.reason) == (main1, True, "main-changed-before-created")
    later = cb.basis_for("auto-review.yml", "pull_request", head, "2026-10-01T12:10:00Z")   # 15 min after → open bound
    assert later.ambiguous is False
    # Negative control: the same commit touching an unrelated workflow file does not count.
    git.commits[main1].changed = [".github/workflows/oracle.yml"]
    other = GitCodeBasis(git).basis_for("auto-review.yml", "pull_request", head, "2026-10-01T12:00:00Z")
    assert (other.main_sha, other.ambiguous) == (main1, False)


def test_conflict_on_registry_is_ambiguous():
    """merge_tree_read reports registry.conf conflicted → ambiguous."""
    git = fixture_git(merges={(M0987, F4E3): ({".github/workflows/auto-review.yml": b"wf"}, {REGISTRY})})
    cb = GitCodeBasis(git)
    b = cb.basis_for("auto-review.yml", "pull_request", F4E3, "2026-10-11T17:46:29Z")
    assert (b.ambiguous, b.reason) == (True, "merge-conflict")
    assert cb.file_at(b, REGISTRY) is None            # conflict markers are never read as a registry
    # Negative control: a conflict on some OTHER path does not taint the basis.
    clean = GitCodeBasis(fixture_git(merges={(M0987, F4E3): ({REGISTRY: b"r"}, {"designs/x/x.scad"})}))
    assert clean.basis_for("auto-review.yml", "pull_request", F4E3, "2026-10-11T17:46:29Z").ambiguous is False


class CountingReader(FakeGitReader):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.merge_calls = 0

    def merge_tree_read(self, ours, theirs, path):
        self.merge_calls += 1
        return super().merge_tree_read(ours, theirs, path)


def test_missing_head_is_unavailable():
    """A head sha the GitReader does not have → Basis.unavailable == that sha (never a fetch); memoized per (workflow, kind, main8, head8)."""
    gone = _sha("e")
    cb = fixture_codebasis()
    b = cb.basis_for("auto-review.yml", "pull_request", gone, "2026-10-11T17:46:29Z")
    assert b.unavailable == gone and b.kind == "merge"
    assert cb.file_at(b, REGISTRY) is None and cb.chain_models(b, "review") is None
    assert cb.basis_for("design-run.yml", "schedule", gone, "2026-09-12T00:23:08Z").unavailable == gone
    assert not hasattr(cb.git, "fetch") and not hasattr(cb.git, "ensure_commit")
    # Memo: two reviews of one head at one main cost one merge-tree read per file...
    reader = CountingReader([
        FakeCommit(_sha("1"), [], ts_epoch("2026-10-01T10:00:00Z"), changed=[REGISTRY]),
        FakeCommit(_sha("2"), [_sha("1")], ts_epoch("2026-10-01T11:55:00Z"), changed=[REGISTRY]),
        FakeCommit(_sha("9"), [_sha("1")], 0),
    ], refs={MAIN_REF: _sha("2")})
    mc = GitCodeBasis(reader)
    first = mc.basis_for("auto-review.yml", "pull_request", _sha("9"), "2026-10-01T12:00:00Z")
    second = mc.basis_for("auto-review.yml", "pull_request", _sha("9"), "2026-10-01T13:00:00Z")
    assert reader.merge_calls == 2                       # registry + workflow, once
    mc.file_at(second, REGISTRY)
    assert reader.merge_calls == 2
    # ...but the time-window ambiguity is per run: same (workflow, kind, main, head), the first
    # run created 5 min after a registry commit, the second an hour after it.
    assert (first.main_sha, second.main_sha) == (_sha("2"), _sha("2"))
    assert (first.ambiguous, second.ambiguous) == (True, False)


def test_registry_parsed_with_model_registry(monkeypatch):
    """chain_models reads the fixture registry@a720a6bd: design-run = (glm-5.2, glm-5.1, glm-4.6, claude-sonnet-5, claude-haiku-4-5)."""
    from model_registry import registry as mr

    calls = []
    real = mr.Registry.load.__func__

    def spy(cls, path=mr.DEFAULT_PATH):
        calls.append(path)
        return real(cls, path)

    monkeypatch.setattr(mr.Registry, "load", classmethod(spy))
    cb = fixture_codebasis()
    b = Basis("head", A720, None)
    assert cb.chain_models(b, "design-run") == ("glm-5.2", "glm-5.1", "glm-4.6", "claude-sonnet-5", "claude-haiku-4-5")
    assert cb.chain_models(b, "scout") == ("glm-5.2", "claude-sonnet-5", "claude-haiku-4-5")
    assert cb.chain_models(b, "no-such-chain") is None
    assert len(calls) == 1                     # the model-registry parser ran, once per blob
    # Negative control: no registry at the basis (it did not exist at dae83d67) → None.
    assert cb.chain_models(Basis("head", DAE8, None), "design-run") is None


@pytest.mark.parametrize("text", [
    b"[chain:design-run]\nmodels = glm-5.2\n",                 # a chain naming an undeclared model
    b"models = glm-5.2\n",                                      # no section header
    b"[model:glm-5.2]\nprovider = zai\n",                       # missing required notes / provider
    b"[chain:x]\nmodels = a\n[chain:x]\nmodels = b\n",          # duplicate stanza
    b"[provider:zai]\nsecret = K\nbase_url = http://x\n",       # non-https base_url
    b"\xff\xfe[chain:x]\n",                                     # not UTF-8
])
def test_unparseable_registry_is_none(text):
    """A registry the strict parser refuses → None (never a lenient re-parse)."""
    assert parse_registry_chains(text) is None
    git = FakeGitReader([FakeCommit(_sha("7"), files={REGISTRY: text})])
    assert GitCodeBasis(git).chain_models(Basis("head", _sha("7"), None), "design-run") is None


def test_parseable_registry_positive_control():
    assert parse_registry_chains(codebasis_blob(A720, REGISTRY))["design-run"][2] == "glm-4.6"
    assert parse_registry_chains(V1) == {"oracle-glm": ("glm-5.2",)}


def test_main_at():
    git = fixture_git()
    assert main_at(git, MAIN_REF, ts_epoch("2026-10-11T17:46:29Z")) == M0987
    assert main_at(git, MAIN_REF, ts_epoch("2026-09-12T00:23:08Z")) == A720
    assert main_at(git, MAIN_REF, ts_epoch("2026-07-01T00:00:00Z")) is None
    assert codebasis.MAIN_REF == MAIN_REF
