"""Drift guard: the reviewer chain walk keys on the ARTIFACT, not the exit code.

Issue #762: claude-code-action exits 0 whenever the agent ends its turn
without an API error, so on PRs #755/#756 every reviewer job reported
'success' and the round stamp called the round complete while neither
reviewer had posted — the walk skipped later links (an exit-0 link reads as
the win) and the stamp trusted the green job results. The #538 lesson
applied to the review pipeline: derive the outcome from what landed.

Both halves of the fix are pinned here:

* every Jane/Drik ship step is followed by an artifact check
  (``scripts/reviewer-posted.sh``) reading the only evidence that counts —
  an Actions-bot MCP-assembled sign-off marker for THIS head sha from this
  run (``--since``) — and link k>=2 plus the two exhaustion gates key on
  ``steps.vN.outputs.served``, never on ``.outcome``;
* the round stamp artifact-confirms BOTH reviewers before advancing the
  reviewed-SHA — green jobs without markers are stamped incomplete.

pm-triage and design-coach keep their exit-code walks on purpose (the PM's
PM_TRIAGE markers are per-design verdicts, not one per-head completion
marker; the coach's COACH-LOCK is a dedupe lock), and that boundary is
pinned too — so a half-migration is caught in either direction.

Every pin has a tamper negative control below, derived from the live
workflow text, proving it can fail. Kept out of test_workflow_drift.py (it
reuses that file's job-block parser, the test_reviewer_backstop_wiring
pattern) so the pin reads on its own.
"""

from __future__ import annotations

import re

import pytest

from test_workflow_drift import (
    REPO_ROOT,
    _job_blocks,
    _job_steps,
    _without_comments,
    _workflow_text,
)

# The two jobs whose reviewers emit one per-head sign-off marker — the only
# ones an artifact check can key on (issue #762 covers Jane/Drik).
ARTIFACT_JOBS = {"jane-review": "jane", "drik-review": "drik"}
# The jobs that deliberately keep the exit-code walk.
EXIT_CODE_JOBS = ("pm-triage", "design-coach")
ARTIFACT_SCRIPT = "scripts/reviewer-posted.sh check"
# The stamp's served guard, verbatim — the reviewed-SHA advances only inside.
STAMP_GUARD = 'if [ "$jane_served" = "true" ] && [ "$drik_served" = "true" ]; then'
STAMP_SHA = "AUTO_REVIEW_STAMP sha=${HEAD_SHA}"
LINKS = 8


def _steps(block: str) -> list[str]:
    """The job's step chunks, comment lines stripped (a comment quoting the
    leg must not satisfy a pin on its behalf)."""
    return [_without_comments(c) for c in _job_steps(block)]


def _ships(steps: list[str]) -> list[str]:
    return [c for c in steps if "uses: anthropics/claude-code-action" in c]


def _if_condition(chunk: str) -> str:
    """The step's `if:` condition folded onto one line: from `if:` to the
    next 8-space key (`continue-on-error:` / `uses:` / `env:` / `run:`),
    whatever the step's shape."""
    m = re.search(r"^        if:(.*?)(?=^        \w[\w-]*:)", chunk,
                  re.DOTALL | re.MULTILINE)
    assert m, "no `if:` on this step — the fixture is stale"
    return " ".join(m.group(1).replace(">-", " ").split())


def _assert_every_link_is_artifact_checked(text: str) -> None:
    """Each Jane/Drik ship step is followed by its artifact check (id vN,
    the right reviewer, and an `if` that fires exactly when the link ran).
    Factored out so the negative controls can run it against tampered text."""
    blocks = _job_blocks(text)
    for job, reviewer in ARTIFACT_JOBS.items():
        steps = _steps(blocks[job])
        ships = _ships(steps)
        assert len(ships) == LINKS, (
            f"auto-review.yml [{job}]: {len(ships)} ship steps, expected {LINKS}")
        for n in range(1, LINKS + 1):
            at = next(i for i, c in enumerate(steps)
                      if c is ships[n - 1])
            check = steps[at + 1]
            for needle in (f"id: v{n}", ARTIFACT_SCRIPT,
                           f"--reviewer {reviewer}",
                           '--since "$SINCE"',
                           "SINCE: ${{ steps.ready.outputs.started_at }}",
                           f"steps.p{n}.outcome == 'success' || "
                           f"steps.p{n}.outcome == 'failure'"):
                assert needle in check, (
                    f"auto-review.yml [{job}]: the link-{n} ship step is not "
                    f"followed by its artifact check ({needle!r} missing) — an "
                    "exit-0 link that posts nothing would read as the win "
                    "(issue #762)")


def _assert_walk_keys_on_served_outputs(text: str) -> None:
    """Link k>=2 gates on EVERY earlier link's `served` output and on no
    `.outcome` at all; link 1 gates only on its provider key."""
    blocks = _job_blocks(text)
    for job in ARTIFACT_JOBS:
        for n, chunk in enumerate(_ships(_steps(blocks[job])), 1):
            cond = _if_condition(chunk)
            assert ".outcome" not in cond, (
                f"auto-review.yml [{job}] link {n}: the walk still keys on an "
                f"exit code ({cond!r}) — an exit-0 link that posts nothing "
                "reads as success and skips the rest (issue #762)")
            if n == 1:
                continue
            for earlier in range(1, n):
                needle = f"steps.v{earlier}.outputs.served != 'true'"
                assert needle in cond, (
                    f"auto-review.yml [{job}] link {n}: not gated on {needle} — "
                    "it would run even after an earlier link delivered, or "
                    "skip after one that exited 0 without posting (issue #762)")


def _assert_exhaustion_gates_key_on_the_artifact(text: str) -> None:
    """The provider-triage and red-exhaustion steps in Jane/Drik fire when no
    link DELIVERED (all eight `served` legs), and the exit-code needle is gone
    from those job bodies entirely."""
    blocks = _job_blocks(text)
    for job in ARTIFACT_JOBS:
        body = _without_comments(blocks[job])
        assert not re.search(r"steps\.p\d+\.outcome != 'success'", body), (
            f"auto-review.yml [{job}]: the exit-code walk is back — exhaustion "
            "must mean 'no link delivered the review', not 'no link exited 0' "
            "(issue #762)")
        gates = [c for c in _steps(blocks[job])
                 if "uses: ./.github/actions/provider-triage" in c
                 or re.search(r"^          exit 1$", c, re.MULTILINE)]
        assert len(gates) == 2, (
            f"auto-review.yml [{job}]: expected the triage + exhaustion pair, "
            f"found {len(gates)} gate steps")
        for chunk in gates:
            cond = _if_condition(chunk)
            for n in range(1, LINKS + 1):
                needle = f"steps.v{n}.outputs.served != 'true'"
                assert needle in cond, (
                    f"auto-review.yml [{job}] exhaustion gate: missing {needle} "
                    "— a chain where every link exits 0 without posting would "
                    "slip past the red path (issue #762)")
            assert ".outcome" not in cond, (
                f"auto-review.yml [{job}] exhaustion gate keys on an exit code "
                f"({cond!r}) — exit-0-without-posting is not exhaustion under "
                "that rule, and the round would look served (issue #762)")


def _assert_exit_code_jobs_stay_exit_code(text: str) -> None:
    """pm-triage and design-coach keep the exit-code walk Jane/Drik dropped,
    and are not half-wired to the artifact reader."""
    blocks = _job_blocks(text)
    for job in EXIT_CODE_JOBS:
        body = _without_comments(blocks[job])
        assert "steps.p1.outcome != 'success'" in body, (
            f"auto-review.yml [{job}] lost the exit-code walk — migrating it "
            "needs a per-head completion marker defined first (issue #762 "
            "covers Jane/Drik only; update this pin in the same PR)")
        assert "reviewer-posted.sh" not in body, (
            f"auto-review.yml [{job}] half-migrated: it runs the artifact "
            "reader without the walk keyed on it")


def _at(run: str, needle: str) -> int:
    """`run.index` that fails as an AssertionError, not a ValueError."""
    assert needle in run, f"{needle!r} is gone from the stamp script"
    return run.index(needle)


def _assert_stamp_confirms_both_markers(text: str) -> None:
    """The stamp checks out the reader script, confirms BOTH reviewers'
    markers for this head, and only then posts the sha-carrying stamp; a
    green round with no review is stamped incomplete with a warning."""
    block = _job_blocks(text)["review-stamp"]
    steps = _steps(block)
    assert "uses: actions/checkout" in steps[0], (
        "review-stamp's first step is not the checkout — the artifact "
        "confirmation has no scripts/reviewer-posted.sh to run")
    run = block.split("run: |", 1)[1]
    jane_at = _at(run, "--reviewer jane")
    drik_at = _at(run, "--reviewer drik")
    guard_at = _at(run, STAMP_GUARD)
    sha_at = _at(run, STAMP_SHA)
    assert jane_at < guard_at and drik_at < guard_at, (
        "review-stamp stamps without confirming BOTH reviewers' markers "
        "first — the #755/#762 shape would pass (issue #762)")
    assert guard_at < sha_at and run.count(STAMP_SHA) == 1, (
        "the sha-carrying stamp is not inside the served guard — a green "
        "round with no review would advance the reviewed-SHA and silently "
        "strand the PR from re-review (issue #762)")
    assert '--since "$SINCE"' in run and "SINCE:" in block, (
        "review-stamp no longer scopes the artifact check to this run "
        "(--since) — a planted or stale marker could advance the SHA "
        "(discussion_r4185453576)")
    for needle in ("::warning::auto-review incomplete", "issue #762"):
        assert needle in run, (
            f"the artifact-miss branch no longer surfaces the miss ({needle!r})")


def test_every_jane_and_drik_link_is_followed_by_its_artifact_check():
    _assert_every_link_is_artifact_checked(_workflow_text())


def test_the_walk_keys_on_served_outputs_not_exit_codes():
    _assert_walk_keys_on_served_outputs(_workflow_text())


def test_exhaustion_gates_key_on_the_artifact():
    _assert_exhaustion_gates_key_on_the_artifact(_workflow_text())


def test_pm_and_coach_keep_their_exit_code_walks():
    _assert_exit_code_jobs_stay_exit_code(_workflow_text())


def test_the_stamp_confirms_both_markers_before_advancing_the_sha():
    _assert_stamp_confirms_both_markers(_workflow_text())


def test_the_artifact_reader_exists_and_carries_its_selftest():
    # The workflow half is dead wiring without the reader: presence plus the
    # selftest hook check.sh runs (its decision rows live in the script).
    script = REPO_ROOT / "scripts" / "reviewer-posted.sh"
    assert script.is_file(), "scripts/reviewer-posted.sh is missing"
    body = script.read_text(encoding="utf-8")
    assert "--selftest" in body and "served_from_comments" in body, (
        "scripts/reviewer-posted.sh lost its selftest or its pure core")
    # Trust boundary (discussion_r4185453576): planted markers from other
    # authors must not count — the reader binds to the MCP posting identity.
    for needle in ("github-actions", "REVIEWER_FOOTER", "planted-human",
                   "cursor[bot]", "is_actions_bot"):
        assert needle in body, (
            f"scripts/reviewer-posted.sh lost its author-binding pin "
            f"({needle!r}) — a planted marker would satisfy the walk/stamp")


# ── negative controls ─────────────────────────────────────────────────────────

def _job_replace(text: str, job: str, old: str, new: str,
                 count: int = 1) -> str:
    """Rewrite `old` → `new` inside ONE job's block (count=-1 for every
    occurrence), anchored on the live block text."""
    block = _job_blocks(text)[job]
    assert old in block, "tamper target not found — the fixture is stale"
    tampered = text.replace(block, block.replace(old, new, count), 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    return tampered


def _drop_step(text: str, job: str, needle: str) -> str:
    chunk = next(c for c in _job_steps(_job_blocks(text)[job]) if needle in c)
    tampered = text.replace("\n      - " + chunk, "", 1)
    assert tampered != text, "tamper did not land — the fixture is stale"
    return tampered


def test_check_guard_rejects_a_dropped_artifact_check():
    # NEGATIVE CONTROL: delete Drik's link-3 artifact check — the silent
    # exit-0 case it exists to catch comes straight back.
    tampered = _drop_step(_workflow_text(), "drik-review", "id: v3")
    with pytest.raises(AssertionError, match="artifact check"):
        _assert_every_link_is_artifact_checked(tampered)


def test_check_guard_rejects_a_check_reading_the_other_reviewer():
    # NEGATIVE CONTROL: Jane's link-2 check reads Drik's marker — it would
    # answer 'served' off the wrong reviewer's comment.
    tampered = _job_replace(
        _workflow_text(), "jane-review",
        '--sha "$HEAD_SHA" --reviewer jane --since "$SINCE")"\n'
        '          echo "link 2 artifact',
        '--sha "$HEAD_SHA" --reviewer drik --since "$SINCE")"\n'
        '          echo "link 2 artifact')
    with pytest.raises(AssertionError, match="--reviewer jane"):
        _assert_every_link_is_artifact_checked(tampered)


def test_check_guard_rejects_a_check_without_since():
    # NEGATIVE CONTROL: drop --since from Jane's link-1 check — a stale
    # marker from an earlier run could short-circuit the walk.
    tampered = _job_replace(
        _workflow_text(), "jane-review",
        '--sha "$HEAD_SHA" --reviewer jane --since "$SINCE")"\n'
        '          echo "link 1 artifact',
        '--sha "$HEAD_SHA" --reviewer jane)"\n'
        '          echo "link 1 artifact')
    with pytest.raises(AssertionError, match="--since"):
        _assert_every_link_is_artifact_checked(tampered)


def test_walk_guard_rejects_a_link_reverted_to_exit_codes():
    # NEGATIVE CONTROL: link 2 back on the exit code — exactly the #755/#756
    # defect (an exit-0 silent link stops the walk).
    tampered = _job_replace(
        _workflow_text(), "drik-review",
        "if: steps.ready.outputs.ready == 'true' && env.HAS_ZAI == 'true' "
        "&& steps.v1.outputs.served != 'true'",
        "if: steps.ready.outputs.ready == 'true' && env.HAS_ZAI == 'true' "
        "&& steps.p1.outcome != 'success'")
    with pytest.raises(AssertionError, match="still keys on an exit code"):
        _assert_walk_keys_on_served_outputs(tampered)


def test_walk_guard_rejects_a_tail_link_missing_an_earlier_gate():
    # NEGATIVE CONTROL: link 4 loses its link-2 gate — it would run after
    # link 2 delivered.
    tampered = _job_replace(_workflow_text(), "jane-review",
                            "          && steps.v2.outputs.served != 'true'\n", "")
    with pytest.raises(AssertionError, match="steps.v2.outputs.served"):
        _assert_walk_keys_on_served_outputs(tampered)


def test_exhaustion_guard_rejects_an_exit_code_gate():
    # NEGATIVE CONTROL: the triage leg back on exit codes — a chain where
    # every link exits 0 without posting never reaches the red path.
    served = "\n".join(
        f"          && steps.v{n}.outputs.served != 'true'" for n in range(1, 9))
    outcomes = "\n".join(
        f"          && steps.p{n}.outcome != 'success'" for n in range(1, 9))
    tampered = _job_replace(_workflow_text(), "jane-review",
                            served, outcomes)
    with pytest.raises(AssertionError, match="exit-code walk is back"):
        _assert_exhaustion_gates_key_on_the_artifact(tampered)


def test_exhaustion_guard_rejects_the_needle_surviving_anywhere():
    # NEGATIVE CONTROL: one outcome leg smuggled back into a link condition —
    # the whole-body ban is what catches it, not the gate-list check alone.
    tampered = _job_replace(
        _workflow_text(), "drik-review",
        "if: steps.ready.outputs.ready == 'true' && env.HAS_ZAI == 'true' "
        "&& steps.v1.outputs.served != 'true' "
        "&& steps.v2.outputs.served != 'true'",
        "if: steps.ready.outputs.ready == 'true' && env.HAS_ZAI == 'true' "
        "&& steps.p1.outcome != 'success' "
        "&& steps.p2.outcome != 'success'")
    with pytest.raises(AssertionError, match="exit-code walk is back"):
        _assert_exhaustion_gates_key_on_the_artifact(tampered)


def test_exit_code_guard_rejects_a_migrated_pm_walk():
    # NEGATIVE CONTROL: the PM's walk silently switched to served outputs —
    # the boundary pin must notice (a marker contract has to land with it).
    # Every occurrence, or the needle survives in a later link's condition.
    tampered = _job_replace(
        _workflow_text(), "pm-triage",
        "steps.p1.outcome != 'success'",
        "steps.v1.outputs.served != 'true'", count=-1)
    with pytest.raises(AssertionError, match="lost the exit-code walk"):
        _assert_exit_code_jobs_stay_exit_code(tampered)


def test_exit_code_guard_rejects_a_half_migrated_pm_job():
    # NEGATIVE CONTROL: the PM job runs the artifact reader while its walk
    # still keys on exit codes — half a migration is worse than none.
    tampered = _job_replace(
        _workflow_text(), "pm-triage",
        "    steps:\n      - uses: actions/checkout@v7",
        "    steps:\n      - run: scripts/reviewer-posted.sh check\n"
        "      - uses: actions/checkout@v7")
    with pytest.raises(AssertionError, match="half-migrated"):
        _assert_exit_code_jobs_stay_exit_code(tampered)


def test_stamp_guard_rejects_a_one_reviewer_confirmation():
    # NEGATIVE CONTROL: the stamp confirms only Jane — Drik's silent exit-0
    # round would be stamped complete (the #755 shape).
    tampered = _job_replace(
        _workflow_text(), "review-stamp", STAMP_GUARD,
        'if [ "$jane_served" = "true" ]; then')
    with pytest.raises(AssertionError, match="is gone from the stamp script"):
        _assert_stamp_confirms_both_markers(tampered)


def test_stamp_guard_rejects_a_dropped_reviewer_read():
    # NEGATIVE CONTROL: the Drik read re-targeted — the guard would pass on
    # Jane's marker alone.
    tampered = _job_replace(_workflow_text(), "review-stamp",
                            "--reviewer drik", "--reviewer pm")
    with pytest.raises(AssertionError, match="--reviewer drik"):
        _assert_stamp_confirms_both_markers(tampered)


def test_stamp_guard_rejects_a_lost_checkout():
    # NEGATIVE CONTROL: the checkout dropped — the confirmation step has no
    # script to run and fails at run time instead of at review time.
    tampered = _job_replace(
        _workflow_text(), "review-stamp",
        "      - uses: actions/checkout@v7\n"
        "        with:\n"
        "          persist-credentials: false\n\n"
        "      - name: Post / update stamp comment",
        "      - name: Post / update stamp comment")
    with pytest.raises(AssertionError, match="checkout"):
        _assert_stamp_confirms_both_markers(tampered)
