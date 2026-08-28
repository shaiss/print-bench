"""AC4: the live negative control — select over THIS tree prints NONE.

The nine #204 catalog demonstrators seeded in docs/advanced-techniques.md
are all `status=briefed` (#385–#393), so the tree itself is the biggest
live fixture the selector has: every rail that can fire, fires.

Two deliberate choices in how the control pins the seed, both about staying
a *control* rather than a freeze:

- Presence, not count: the test asserts the nine seeded slugs are all there
  with their refs, and that every extracted candidate is briefed. Pinning
  `len == 9` would break the first time anyone seeds a TENTH briefed marker
  — the tool's intended workflow — which is not what this control exists to
  catch. What it must catch is a seeded marker that is NOT briefed (the
  seed claim) or a marker that vanished while its brief still points at the
  doc.
- The open-brief list here is the nine real brief titles as committed
  fixture data, so the matcher is exercised against the exact live shape of
  #385–#393's titles. The truly live sweep (`gh issue list` piped to
  `select`) is an operator command — documented in the README — because a
  committed test may not reach the network (AC5).
"""

from __future__ import annotations

from pathlib import Path

from brief_sources import extract, select
from brief_sources.select import parse_briefs

REPO_ROOT = Path(__file__).resolve().parents[3]

#: slug → the brief issue that already files it (#385–#393, catalog order).
SEEDED = {
    "support-free-bracket": 385,
    "snap-cantilever-clip": 386,
    "captive-spinner": 387,
    "let-folding-panel": 388,
    "bistable-toggle": 389,
    "pip-piano-hinge": 390,
    "compliant-gripper": 391,
    "bistable-snap-box": 392,
    "constant-force-slider": 393,
}

#: The nine briefs' real titles, as `gh issue view` reported them at seed
#: time — the live shape the matcher must recognize, committed so the test
#: stays offline.
BRIEF_TITLES = {
    385: "support-free-bracket — Tier 1 reference design (Domain 2, support-free by construction)",
    386: "snap-cantilever-clip — Tier 1 reference design (Domain 1, cantilever snap flexure)",
    387: "captive-spinner — Tier 1 reference design (Domain 3, print-in-place captive ring)",
    388: "let-folding-panel — Tier 2 reference design (Domain 1, LET lamina-emergent joint)",
    389: "bistable-toggle — Tier 2 reference design (Domain 1, buckled-arch bistable switch)",
    390: "pip-piano-hinge — Tier 2 reference design (Domain 3, multi-knuckle print-in-place hinge)",
    391: "compliant-gripper — Tier 3 reference design (fused compliant + print-in-place gripper)",
    392: "bistable-snap-box — Tier 3 reference design (living-hinge box with bistable latch)",
    393: "constant-force-slider — Tier 3 reference design (quasi-zero-stiffness captive slider)",
}


def test_the_nine_seeded_demonstrators_are_all_briefed_with_their_refs():
    candidates = {c.slug: c for c in extract(REPO_ROOT)}
    for slug, ref in SEEDED.items():
        cand = candidates.get(slug)
        assert cand is not None, f"seeded marker {slug} missing from docs/"
        assert cand.status == "briefed", f"{slug}: expected status=briefed, got {cand.status!r}"
        assert cand.ref == ref, f"{slug}: expected ref={ref}, got {cand.ref}"
        assert cand.doc == "docs/advanced-techniques.md", (
            f"{slug}: seeded marker moved out of docs/advanced-techniques.md"
        )


def test_every_marker_in_this_tree_is_briefed():
    # The seed claim as a whole: at this commit the tree carries no un-filed
    # decided marker. A future `status=decided` marker legitimately breaks
    # this and the NONE test below — that is the control doing its job:
    # whoever seeds one updates the live control in the same change.
    for cand in extract(REPO_ROOT):
        assert cand.status == "briefed", (
            f"{cand.slug} ({cand.source}) is status={cand.status!r} — an "
            "un-filed marker over this tree must come with a live-control update"
        )


def test_select_over_this_tree_with_the_live_brief_list_prints_NONE():
    brief_text = "".join(f"{n} {t}\n" for n, t in sorted(BRIEF_TITLES.items()))
    briefs = parse_briefs(brief_text)
    design_names = sorted(p.name for p in (REPO_ROOT / "designs").iterdir() if p.is_dir())
    assert select(extract(REPO_ROOT), briefs, design_names) is None


def test_each_seeded_marker_alone_would_be_caught_by_its_own_brief():
    # The rail-by-rail proof behind the NONE above: for each of the nine,
    # the same marker at status=decided is dropped by its OWN brief title —
    # the matcher, not the status field, is what stops a re-file. This is
    # the negative control that keeps `matches_subject` honest against the
    # real title shapes.
    from brief_sources.select import matches_subject

    for slug, ref in SEEDED.items():
        cand = next(c for c in extract(REPO_ROOT) if c.slug == slug)
        assert matches_subject(cand, BRIEF_TITLES[ref]), (
            f"{slug}: its own brief title no longer matches — the dedup rail has drifted"
        )
