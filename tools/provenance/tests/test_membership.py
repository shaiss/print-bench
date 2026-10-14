"""membership — the refined file-kind rule over fixtures/membership/pr_files.json.gz vs the audit labels.

Owner: H2. Each test's docstring is its acceptance criterion (docs/provenance.md,
final plan P0/P1a–e).

Ground truth: the audit's GAP2 hand labels (the 2026-10-13 provenance audit's
raw notes, "PRECISION/RECALL (PR-level, all states). Hand-labelled ground
truth"), copied below because they were never committed as a file. For the
five tuned designs they equal ``refined_membership.json``; held out, the rule
adds exactly one false positive (#381, the PM-characters roster sweep on
``sweetheart-hamster``) — which is why the rule's held-out precision is 0.94.
"""

from __future__ import annotations

import collections

import pytest

from conftest import golden_full, membership_rows, pr_files, refined_membership
from provenance import membership as M

#: GAP2 hand labels — the tuned set (P = R = 1.00 there by construction).
TUNED = {
    "sbc-case": {371, 397, 802, 805, 810, 815, 817, 818, 821},
    "alcove-rod-socket": {361, 377, 384, 632, 784, 787, 792, 812, 816, 833},
    "constant-force-slider": {209, 216, 221, 240, 254, 261},
    "nuggs-turnaround": {436, 503, 575},
    "snap-clamshell-box": {209, 214, 223, 254, 259, 264, 268, 271, 299},
}
#: GAP2 hand labels — the held-out set.
HELD_OUT = {
    "sweetheart-hamster": {359, 370, 372, 411, 531, 635, 700},
    "preroll-elevator": {476, 477},
    "pip-ratchet": {676},
    "ovodyo": {605, 621, 628, 629, 789},
}

#: membership.csv verdict spelling -> classify_pr's.
CSV_VERDICT = {"member": "member", "member:ai-shot": "member", "regen-only": "regen-only",
               "excluded:catalog-sweep(meta conf)": "sweep", "excluded:stacked-base": "stacked-excluded"}

#: The one row where the audit's script and the documented rule differ: PR #86's only file is a
#: PDF (kind ``other``). The audit's script counted any non-preview file as substantive; the rule
#: of record (docs/provenance.md §Membership, this module) makes an ``other``-only PR regen-only.
CSV_EXCEPTIONS = {("86", "nuggs"): ("member", "regen-only")}


def predicted_members() -> dict[str, set[int]]:
    out: dict[str, set[int]] = collections.defaultdict(set)
    for n, pr in pr_files().items():
        verdicts = M.classify_pr(pr["files"], title=pr["title"], merged=pr["merged_at"] is not None)
        for design, v in verdicts.items():
            if v["membership"] == "member":
                out[design].add(int(n))
    return out


def precision_recall(truth: dict[str, set[int]]) -> tuple[float, float, int, int, int]:
    pred = predicted_members()
    tp = sum(len(pred[d] & truth[d]) for d in truth)
    npred = sum(len(pred[d]) for d in truth)
    ngt = sum(len(truth[d]) for d in truth)
    return tp / npred, tp / ngt, tp, npred, ngt


def test_tuned_sets_precision_and_recall():
    """Over sbc-case, alcove-rod-socket, constant-force-slider, nuggs-turnaround, snap-clamshell-box ground truth (the audit's hand labels, GAP2): P = 1.00 and R = 1.00."""
    p, r, tp, npred, ngt = precision_recall(TUNED)
    assert (tp, npred, ngt) == (37, 37, 37)
    assert p == 1.0 and r == 1.0
    refined = refined_membership()
    assert {d: set(refined[d]) for d in TUNED} == TUNED


def test_held_out_sets():
    """Over sweetheart-hamster, preroll-elevator, pip-ratchet, ovodyo: P >= 0.94 and R = 1.00 (the known FP is #381)."""
    p, r, tp, npred, ngt = precision_recall(HELD_OUT)
    assert (tp, npred, ngt) == (15, 16, 15)
    assert round(p, 2) >= 0.94 and r == 1.0
    pred = predicted_members()
    assert {d: pred[d] - HELD_OUT[d] for d in HELD_OUT} == {
        "sweetheart-hamster": {381}, "preroll-elevator": set(), "pip-ratchet": set(), "ovodyo": set()}


def test_verdicts_match_membership_csv():
    """For every row of audits/.../membership.csv whose PR is in pr_files, classify_pr's verdict maps to the CSV verdict (member / member:ai-shot→member / regen-only / excluded:catalog-sweep→sweep / excluded:stacked-base→stacked-excluded)."""
    files = pr_files()
    rows = membership_rows()
    assert len(rows) == 671
    mismatches = {}
    covered = 0
    for row in rows:
        pr = files.get(row["pr"])
        if pr is None:
            continue
        covered += 1
        got = M.classify_pr(pr["files"], title=pr["title"], merged=pr["merged_at"] is not None)
        verdict = got[row["design_dir"]]["membership"]
        if verdict != CSV_VERDICT[row["verdict"]]:
            mismatches[(row["pr"], row["design_dir"])] = (CSV_VERDICT[row["verdict"]], verdict)
    assert covered == 671
    assert mismatches == CSV_EXCEPTIONS
    # the exception is what it says it is: an other-only PR
    assert M.design_files(files["86"]["files"]) == {"nuggs": ["Positionspapier_DTSchB_Tierschutzwidriges_Zubehoer.PDF"]}
    assert M.classify_pr(files["86"]["files"], title=files["86"]["title"], merged=True)["nuggs"]["kinds"] == ["other"]
    # every PR × design row the rule produces is a row of the CSV, and vice versa
    produced = {(n, d) for n, pr in files.items()
                for d in M.classify_pr(pr["files"], title=pr["title"], merged=pr["merged_at"] is not None)}
    assert produced == {(r["pr"], r["design_dir"]) for r in rows}


def test_kind_counts_match_membership_csv():
    """The per-row file-kind counts (source / docs / stamp) the audit recorded are reproduced."""
    files = pr_files()
    for row in membership_rows():
        rels = M.design_files(files[row["pr"]]["files"])[row["design_dir"]]
        counts = collections.Counter(M.file_kind(r) for r in rels)
        assert (counts["source"], counts["docs"], counts["stamp"]) == \
            (int(row["n_source"]), int(row["n_docs"]), int(row["n_stamp"])), (row["pr"], row["design_dir"])


def test_cc1_main_commit_classes():
    """CC-1 from the calibration-cube golden full main.commit events (refs.files, refs.parents): (54, 49, 19, 19, 11)."""
    events = [e for e in golden_full("calibration-cube")["events"] if e["kind"].startswith("main.commit")]
    for e in events:
        assert "main.commit." + M.main_commit_class(e["refs"]["files"]) == e["kind"], e["sha"]
    single = [e for e in events if e["refs"]["parents"] <= 1]
    counts = collections.Counter(M.main_commit_class(e["refs"]["files"]) for e in single)
    assert (len(events), len(single), counts["substantive"], counts["stamp-only"], counts["previews-only"]) == \
        (54, 49, 19, 19, 11)
    with pytest.raises(ValueError):
        M.main_commit_class([])


def test_file_kind_table():
    """cameras.conf → source, CAMERAS.md → docs, lifestyle-x.png → ai, .regen-stamp → stamp, a.png → previews."""
    table = {
        "previews/cameras.conf": "source", "previews/CAMERAS.md": "docs",
        "previews/lifestyle-x.png": "ai", "previews/lifestyle-turntable.gif": "ai",
        "previews/product-still-hero.png": "ai", "previews/.regen-stamp": "stamp", "previews/a.png": "previews",
        "previews/turntable.gif": "previews", "previews/concept-exterior.svg": "previews",
        "README.md": "docs", "NOTES.md": "docs", "docs/deep/x.md": "docs",
        "team.conf": "source", "shots.conf": "source", "x.scad": "source", "lib/part.scad": "source",
        "ci.parts": "source", "ci.fitchecks": "source", "printcheck.args": "source", "ARCHIVED": "source",
        "tumble_stops.py": "other", "paper.PDF": "other",
        # the negative edges of each glob
        "previews/sub/lifestyle-x.png": "previews",   # * never crosses a /
        "previews/lifestyle-x.jpg": "previews", "previews/product-still-x.gif": "previews",
        "lifestyle-x.png": "other",                    # an AI shot lives under previews/
        "previews/x.scad": "previews",                 # previews/* wins over *.scad
        "README.MD": "other", "ARCHIVED.txt": "other", "notci.parts": "other",
        ".regen-stamp": "other",
    }
    assert {p: M.file_kind(p) for p in table} == table
    assert set(table.values()) == set(M.FILE_KINDS)
    for bad in ("", None):
        with pytest.raises(ValueError):
            M.file_kind(bad)


def test_design_files_and_classify_shape():
    paths = ["designs/categories.conf", "designs/a/a.scad", "designs/a/a.scad", "designs/b/previews/x.png",
             "lib/x.scad", "README.md", "designs/c/", "designs//x"]
    assert M.design_files(paths) == {"a": ["a.scad"], "b": ["previews/x.png"]}
    got = M.classify_pr(paths, title="x", merged=True)
    assert got == {"a": {"membership": "member", "kinds": ["source"]},
                   "b": {"membership": "regen-only", "kinds": ["previews"]}}
    assert M.classify_pr([], title="x", merged=True) == {}


def test_exclusion_boundaries():
    """Each exclusion holds exactly at its bound and not one below it."""
    sweep5 = [f"designs/d{i}/catalog.conf" for i in range(5)]
    assert {v["membership"] for v in M.classify_pr(sweep5, title="x", merged=True).values()} == {"sweep"}
    assert {v["membership"] for v in M.classify_pr(sweep5[:4], title="x", merged=True).values()} == {"member"}
    # a design with a doc beside its team.conf is not swept
    docs = sweep5 + ["designs/d0/README.md"]
    assert M.classify_pr(docs, title="x", merged=True)["d0"]["membership"] == "member"
    # a regen-only design does not count toward the sweep's five
    regen = sweep5[:4] + ["designs/d9/previews/.regen-stamp"]
    assert {v["membership"] for v in M.classify_pr(regen, title="x", merged=True).values()} == {"member", "regen-only"}
    # stacked base: unmerged, >= 2 designs, the title names one but not the other (word-bounded, case-folded)
    two = ["designs/nuggs/nuggs.scad", "designs/nuggs-den/nuggs-den.scad"]
    got = M.classify_pr(two, title="NUGGS-DEN: lifestyle shot", merged=False)
    assert (got["nuggs"]["membership"], got["nuggs-den"]["membership"]) == ("stacked-excluded", "member")
    got = M.classify_pr(two, title="lifestyle shots", merged=False)  # names neither: both stay members
    assert {v["membership"] for v in got.values()} == {"member"}
    got = M.classify_pr(two[:1], title="nuggs-den", merged=False)  # one design: never stacked
    assert got["nuggs"]["membership"] == "member"


def test_selftest_cases_hold():
    cases = M.selftest_cases()
    assert len(cases) >= 5
    for label, case in cases:
        assert label.startswith("membership: ")
        assert case() is True, label
