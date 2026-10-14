"""views — fold (P1d).

Owner: H5. The fold logic is tested over the SYNTHETIC records in
``fixtures/records/`` (see ``_views_helpers.py``) with H3's
``episodes.episodes_of`` / ``rounds_from_record`` replaced by deterministic
stand-ins through ``monkeypatch`` — so these run before integration — plus
``@needs`` tests that run the real episodes functions once H3 lands.
"""

from __future__ import annotations

import copy
import inspect

import pytest

import _views_helpers as h
from conftest import FIXTURE_MAIN_SHA, OWNER, REPO_NAME, contract, needs
from fakes import FakeCommit, FakeGitReader

from provenance import canonical, contract as contract_mod, episodes, views


@pytest.fixture
def fake_episodes(monkeypatch):
    h.patch_episodes(monkeypatch)


def _view(design, records=None, rows=None):
    records = h.synthetic_records() if records is None else records
    rows = h.synthetic_rows().get(design, []) if rows is None else rows
    return views.build_view(design, records=records, rows=rows, owner=OWNER, repo=REPO_NAME)


def _main(files: dict[str, bytes], sha: str = FIXTURE_MAIN_SHA) -> FakeGitReader:
    return FakeGitReader([FakeCommit(sha=sha, files=files)], refs={"main": sha})


def _design_tree(*names: str) -> dict[str, bytes]:
    files = {f"designs/{n}/{n}.scad": b"cube(1);\n" for n in names}
    files.update({f"designs/{n}/README.md": b"# x\n" for n in names})
    return files


# ----------------------------------------------------------------------------- design_names

def test_design_names_needs_the_entry_scad():
    files = _design_tree("alpha-clip", "beta-hinge")
    files["designs/no-entry/README.md"] = b"# no scad\n"           # directory without <name>.scad
    files["designs/wrong/other.scad"] = b"cube(1);\n"              # scad not named after the dir
    files["designs/categories.conf"] = b"x | y\n"                  # a file, not a directory
    files["designs/Bad_Name/Bad_Name.scad"] = b"cube(1);\n"        # not a contract design slug
    files["scripts/x.sh"] = b"true\n"
    assert views.design_names(_main(files), FIXTURE_MAIN_SHA) == ["alpha-clip", "beta-hinge"]
    # negative control: the scanner does see a design once its entry exists
    files["designs/no-entry/no-entry.scad"] = b"cube(1);\n"
    assert "no-entry" in views.design_names(_main(files), FIXTURE_MAIN_SHA)


def test_one_view_per_design_including_zero_pr(monkeypatch, fake_episodes):
    """build_views yields one view per designs/<name>/<name>.scad on main, including a design with no PR (empty events, counts all 0)."""
    git = _main(_design_tree(*h.synthetic_designs()))
    rows = h.synthetic_rows()
    calls = []

    def decision_rows(git_, main_sha, design, *, owner, repo, commit_to_pr):
        calls.append((main_sha, design, owner, repo, dict(commit_to_pr)))
        return copy.deepcopy(rows.get(design, []))

    monkeypatch.setattr(episodes, "decision_rows", decision_rows)
    out = views.build_views(h.synthetic_records(), git=git, main_sha=FIXTURE_MAIN_SHA,
                            owner=OWNER, repo=REPO_NAME, commit_to_pr={"a" * 40: 510})
    assert sorted(out) == ["alpha-clip", "beta-hinge", "gamma-stand"]
    assert [c[1] for c in calls] == ["alpha-clip", "beta-hinge", "gamma-stand"]
    assert all(c[0] == FIXTURE_MAIN_SHA and c[4] == {"a" * 40: 510} for c in calls)
    empty = out["gamma-stand"]
    assert empty["design"] == "gamma-stand" and empty["format"] == "view@1"
    assert empty["events"] == [] and empty["episodes"] == [] and empty["prs"] == []
    assert empty["briefs"] == [] and empty["commits"] == [] and empty["maintenance"] == []
    assert empty["releases"] == [] and empty["aliases"] == {"briefs": [], "slugs": []}
    assert empty["counts"] == {"events": 0, "rounds": 0, "prs": 0, "maintenance": 0,
                               "signoffs": {"verified": 0, "window": 0, "claimed": 0},
                               "triage": 0, "jobs_posted_nothing": 0}
    # negative control: the designs with history are NOT empty
    assert out["alpha-clip"]["events"] and out["beta-hinge"]["events"]
    # a design whose directory left main has no view, even though records name it
    git2 = _main(_design_tree("beta-hinge", "gamma-stand"))
    assert "alpha-clip" not in views.build_views(h.synthetic_records(), git=git2,
                                                 main_sha=FIXTURE_MAIN_SHA, owner=OWNER,
                                                 repo=REPO_NAME, commit_to_pr={})


def test_member_vs_maintenance(fake_episodes):
    """A regen-only or sweep PR becomes a maintenance row, never events."""
    alpha, beta = _view("alpha-clip"), _view("beta-hinge")
    # PR 512 is regen-only for alpha-clip and a sweep for beta-hinge
    assert alpha["maintenance"] == [{"pr": 512, "membership": "regen-only",
                                     "at": "2026-09-07T09:00:00Z",
                                     "url": "https://github.com/shaiss/print-bench/pull/512"}]
    assert beta["maintenance"] == [{"pr": 512, "membership": "sweep",
                                    "at": "2026-09-07T09:00:00Z",
                                    "url": "https://github.com/shaiss/print-bench/pull/512"}]
    for view in (alpha, beta):
        assert 512 not in view["prs"]
        assert not [e for e in view["events"] if e.get("pr") == 512]
        assert view["counts"]["maintenance"] == 1
    # PR 513 is stacked-excluded for alpha-clip: neither events nor a maintenance row
    assert 513 not in alpha["prs"] and not [m for m in alpha["maintenance"] if m["pr"] == 513]
    assert not [e for e in alpha["events"] if e.get("pr") == 513]
    # ... and a member of beta-hinge
    assert beta["prs"] == [511, 513] and alpha["prs"] == [510]
    # negative control: flip 512 to a member of alpha-clip and its events appear
    records = h.synthetic_records()
    for r in records:
        if r["kind"] == "pr" and r["pr"] == 512:
            r["designs"]["alpha-clip"]["membership"] = "member"
    flipped = _view("alpha-clip", records)
    assert 512 in flipped["prs"] and flipped["maintenance"] == []
    assert [e for e in flipped["events"] if e.get("pr") == 512]


def test_brief_aliases(fake_episodes):
    """A brief linked via a member PR's briefs and a different design_name slug lands in aliases."""
    beta = _view("beta-hinge")
    # #520 (design_name "b-hinge") reaches beta-hinge only through member PR 511's briefs;
    # #530 is linked by its design_name alone
    assert beta["briefs"] == [520, 530]
    assert beta["aliases"] == {"briefs": [520, 530], "slugs": ["b-hinge"]}
    ids = {e["id"] for e in beta["events"]}
    assert {"issue:520:filed", "issue:530:filed", "timeline:4201"} <= ids
    # the matching slug is not an alias; alpha-clip's brief carries its own name
    assert _view("alpha-clip")["aliases"] == {"briefs": [501], "slugs": []}
    # negative control: drop 520 from PR 511's briefs and it leaves the view
    records = h.synthetic_records()
    for r in records:
        if r["kind"] == "pr" and r["pr"] == 511:
            r["briefs"] = []
    cut = _view("beta-hinge", records)
    assert cut["briefs"] == [530] and cut["aliases"] == {"briefs": [530], "slugs": []}
    assert "issue:520:filed" not in {e["id"] for e in cut["events"]}
    # a non-member PR's briefs link nothing (PR 512's membership is maintenance)
    for r in records:
        if r["kind"] == "pr" and r["pr"] == 512:
            r["briefs"] = [520]
    assert 520 not in _view("beta-hinge", records)["briefs"]


def test_events_deduped_and_sorted(fake_episodes):
    """Events are unique by id and sorted by canonical.event_sort_key."""
    beta = _view("beta-hinge")
    ids = [e["id"] for e in beta["events"]]
    assert len(ids) == len(set(ids))
    assert beta["events"] == sorted(beta["events"], key=canonical.event_sort_key)
    # commit d1 is in BOTH stacked member PRs 511 and 513 (different bytes: url, episode, head):
    # exactly one copy survives — the one with the smallest canonical JSON — whatever the order
    records = h.synthetic_records()
    d1 = [e for r in records if r["kind"] == "pr" for e in r["events"]
          if e["kind"] == "commit.design" and r["pr"] in (511, 513)]
    assert len(d1) == 2 and d1[0]["id"] == d1[1]["id"] and d1[0] != d1[1]
    kept = [e for e in beta["events"] if e["id"] == d1[0]["id"]]
    assert kept == [min(d1, key=canonical.dumps_bytes)]
    reversed_view = _view("beta-hinge", list(reversed(records)))
    assert canonical.dumps_bytes(reversed_view) == canonical.dumps_bytes(beta)
    # a brief event reached twice (design_name AND a member PR's briefs) is one event
    for r in records:
        if r["kind"] == "brief" and r["issue"] == 520:
            r["design_name"] = "beta-hinge"
    twice = _view("beta-hinge", records)
    assert [e["id"] for e in twice["events"]].count("issue:520:filed") == 1
    # negative control: the dedup is by id — two distinct ids both survive
    extra = copy.deepcopy(d1[0])
    extra["id"] = "commit:" + "f" * 40
    member = next(r for r in records if r["kind"] == "pr" and r["pr"] == 511)
    member["events"].append(extra)
    more = _view("beta-hinge", records)
    assert len(more["events"]) == len(twice["events"]) + 1


def test_view_has_no_main_sha(fake_episodes):
    """Critique 6: view@1 carries no main_sha; build_view takes none."""
    assert "main_sha" not in inspect.signature(views.build_view).parameters
    assert "main_sha" not in contract()["shapes"]["view@1"]["fields"]
    for design in h.synthetic_designs():
        view = _view(design)
        assert "main_sha" not in view
        assert FIXTURE_MAIN_SHA not in canonical.dumps(view)


def test_build_views_is_independent_of_main_sha(monkeypatch, fake_episodes):
    """Critique 6: the same records and rows against two main shas give byte-identical views."""
    rows = h.synthetic_rows()
    monkeypatch.setattr(episodes, "decision_rows",
                        lambda git, main_sha, design, **kw: copy.deepcopy(rows.get(design, [])))
    files = _design_tree(*h.synthetic_designs())
    m1, m2 = FIXTURE_MAIN_SHA, "1" * 40
    git = FakeGitReader([FakeCommit(sha=m1, files=files),
                         FakeCommit(sha=m2, parents=[m1], files=dict(files, **{"scripts/x.sh": b"x"}),
                                    changed=["scripts/x.sh"])])
    a = views.build_views(h.synthetic_records(), git=git, main_sha=m1, owner=OWNER,
                          repo=REPO_NAME, commit_to_pr={})
    b = views.build_views(h.synthetic_records(), git=git, main_sha=m2, owner=OWNER,
                          repo=REPO_NAME, commit_to_pr={})
    assert canonical.dumps_bytes(a) == canonical.dumps_bytes(b)


def test_counts(fake_episodes):
    """counts.signoffs by tier and jobs_posted_nothing match the events."""
    alpha = _view("alpha-clip")
    signoffs = [e for e in alpha["events"] if e["kind"] == "review.signoff"]
    assert sorted(e["trust"] for e in signoffs) == ["claimed", "claimed", "verified", "window"]
    assert alpha["counts"]["signoffs"] == {"verified": 1, "window": 1, "claimed": 2}
    assert alpha["counts"]["triage"] == 1
    assert alpha["counts"]["jobs_posted_nothing"] == 1        # Drik's job 7002: 6 links, posted nothing
    assert alpha["counts"]["events"] == len(alpha["events"])
    assert alpha["counts"]["rounds"] == 2 and alpha["counts"]["prs"] == 1
    assert alpha["counts"]["maintenance"] == 1
    # negative controls: re-tier a sign-off, flip the job to posted
    records = h.synthetic_records()
    pr510 = next(r for r in records if r["kind"] == "pr" and r["pr"] == 510)
    for e in pr510["events"]:
        if e["id"] == "issuecomment:6002":
            e["trust"], e["trust_basis"] = "verified", "actions-bot+suffix"
        if e["id"] == "job:7002":
            e["fields"]["posted"] = True
    changed = _view("alpha-clip", records)
    assert changed["counts"]["signoffs"] == {"verified": 2, "window": 0, "claimed": 2}
    assert changed["counts"]["jobs_posted_nothing"] == 0
    # a login/ambiguous/none sign-off is not counted in any tier
    for e in pr510["events"]:
        if e["id"] == "issuecomment:6002":
            e["trust"], e["trust_basis"] = "login", "login"
    assert _view("alpha-clip", records)["counts"]["signoffs"] == {"verified": 1, "window": 0,
                                                                   "claimed": 2}


def test_commits_releases_and_rows(fake_episodes):
    beta, alpha = _view("beta-hinge"), _view("alpha-clip")
    direct = next(r for r in h.synthetic_records() if r["kind"] == "commit")
    assert beta["commits"] == [direct["sha"]] and alpha["commits"] == []
    assert f"commit:{direct['sha']}" in {e["id"] for e in beta["events"]}
    assert alpha["releases"] == [{"tag": "v1.0", "published_at": "2026-09-03T15:00:00Z",
                                  "url": "https://github.com/shaiss/print-bench/releases/tag/v1.0"}]
    assert "release:9501" in {e["id"] for e in alpha["events"]} and beta["releases"] == []
    row_kinds = {e["kind"] for e in alpha["events"] if e["id"].startswith("row:")}
    assert row_kinds == {"decision.pm_log", "decision.notes_log", "field_test", "changelog"}
    # rows are taken as given: none passed, none in the view
    bare = _view("alpha-clip", rows=[])
    assert not [e for e in bare["events"] if e["id"].startswith("row:")]


def test_rejects_unknown_kind_and_bad_names(fake_episodes):
    with pytest.raises(ValueError):
        _view("Bad_Name")
    with pytest.raises(ValueError):
        views.build_view("alpha-clip", records=[{"kind": "mystery"}], rows=[], owner=OWNER,
                         repo=REPO_NAME)
    with pytest.raises(ValueError):
        views.build_view("alpha-clip", records=h.synthetic_records(), rows=[], owner="bad/owner",
                         repo=REPO_NAME)


def test_views_validate_against_the_contract_node(fake_episodes, tmp_path):
    """Every synthetic view validates as view@1 under site/lib/provenance-contract.mjs."""
    if h.node() is None:
        pytest.skip("node not on PATH")
    for design in h.synthetic_designs():
        assert h.node_validate("view@1", _view(design), tmp_path) == []
    broken = _view("alpha-clip")
    broken["counts"]["extra"] = 1
    assert h.node_validate("view@1", broken, tmp_path)


@needs(contract_mod.validate)
def test_views_validate_against_the_contract_python(fake_episodes):
    for design in h.synthetic_designs():
        assert contract_mod.validate("view@1", _view(design)) == []
    broken = _view("alpha-clip")
    broken["counts"]["extra"] = 1
    assert contract_mod.validate("view@1", broken)


@needs(episodes.episodes_of, episodes.rounds_from_record)
def test_real_episodes_fold_the_synthetic_records():
    """With H3's real episodes functions: every view is deterministic, its episodes cover every
    event exactly once, and the round episodes are the member PRs' rounds."""
    for design in h.synthetic_designs():
        a, b = _view(design), _view(design, list(reversed(h.synthetic_records())))
        assert canonical.dumps_bytes(a) == canonical.dumps_bytes(b)
        listed = [i for ep in a["episodes"] for i in ep["events"]]
        assert sorted(listed) == sorted(e["id"] for e in a["events"])
        rounds = {ep["id"] for ep in a["episodes"] if ep["id"].startswith("R:")}
        member = {rd["id"] for r in h.synthetic_records() if r["kind"] == "pr"
                  and r["pr"] in a["prs"] for rd in r["rounds"]}
        assert rounds <= member and a["counts"]["rounds"] == len(rounds)
