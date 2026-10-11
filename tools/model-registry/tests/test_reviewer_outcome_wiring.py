"""Drift guard: the reviewer chain walk keys on the ARTIFACT, not the exit code.

Issue #762: claude-code-action exits 0 whenever the agent ends its turn
without an API error, so on PRs #755/#756 every reviewer job reported
'success' and the round stamp called the round complete while neither
reviewer had posted — the walk skipped later links (an exit-0 link reads as
the win) and the stamp trusted the green job results. The #538 lesson
applied to the review pipeline: derive the outcome from what landed.

Issue #770: the same hole applied to pm-triage and design-coach (they kept
exit-code walks in #762 because no per-head completion marker existed).
Both now emit PM_TRIAGE_DONE / COACH_DONE and walk on ``served`` like
Jane/Drik.

Both halves of the fix are pinned here:

* every Jane/Drik/pm/coach ship step is followed by an artifact check
  (``scripts/reviewer-posted.sh``) reading the only evidence that counts —
  an Actions-bot MCP-assembled per-head marker for THIS head sha from this
  run (``--since``) — and link k>=2 plus the two exhaustion gates key on
  ``steps.vN.outputs.served``, never on ``.outcome``;
* the round stamp artifact-confirms BOTH Jane and Drik reviewers before
  advancing the reviewed-SHA — green jobs without markers are stamped
  incomplete.

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

# Jobs whose reviewers emit one per-head completion marker — the ones an
# artifact check can key on (issue #762 Jane/Drik; issue #770 pm/coach).
ARTIFACT_JOBS = {
    "jane-review": "jane",
    "drik-review": "drik",
    "pm-triage": "pm",
    "design-coach": "coach",
}
ARTIFACT_SCRIPT = "scripts/reviewer-posted.sh check"
# The stamp's served guard, verbatim — the reviewed-SHA advances only inside.
STAMP_GUARD = 'if [ "$jane_served" = "true" ] && [ "$drik_served" = "true" ]; then'
STAMP_SHA = "AUTO_REVIEW_STAMP sha=${HEAD_SHA}"
LINKS = 6


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
    """Each artifact-walk ship step is followed by its artifact check (id vN,
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
                    "(issues #762/#770)")


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
                "reads as success and skips the rest (issues #762/#770)")
            if n == 1:
                continue
            for earlier in range(1, n):
                needle = f"steps.v{earlier}.outputs.served != 'true'"
                assert needle in cond, (
                    f"auto-review.yml [{job}] link {n}: not gated on {needle} — "
                    "it would run even after an earlier link delivered, or "
                    "skip after one that exited 0 without posting "
                    "(issues #762/#770)")


def _assert_exhaustion_gates_key_on_the_artifact(text: str) -> None:
    """The provider-triage and red-exhaustion steps fire when no link
    DELIVERED (all six `served` legs), and the exit-code needle is gone
    from those job bodies entirely."""
    blocks = _job_blocks(text)
    for job in ARTIFACT_JOBS:
        body = _without_comments(blocks[job])
        assert not re.search(r"steps\.p\d+\.outcome != 'success'", body), (
            f"auto-review.yml [{job}]: the exit-code walk is back — exhaustion "
            "must mean 'no link delivered the review', not 'no link exited 0' "
            "(issues #762/#770)")
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
                    "slip past the red path (issues #762/#770)")
            assert ".outcome" not in cond, (
                f"auto-review.yml [{job}] exhaustion gate keys on an exit code "
                f"({cond!r}) — exit-0-without-posting is not exhaustion under "
                "that rule, and the round would look served (issues #762/#770)")


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


def test_every_artifact_walk_link_is_followed_by_its_artifact_check():
    _assert_every_link_is_artifact_checked(_workflow_text())


def test_the_walk_keys_on_served_outputs_not_exit_codes():
    _assert_walk_keys_on_served_outputs(_workflow_text())


def test_exhaustion_gates_key_on_the_artifact():
    _assert_exhaustion_gates_key_on_the_artifact(_workflow_text())


def test_pm_and_coach_are_on_the_artifact_walk():
    """Issue #770: the exit-code boundary pin is gone — both jobs walk on
    served outputs and run the artifact reader."""
    text = _workflow_text()
    blocks = _job_blocks(text)
    for job, reviewer in (("pm-triage", "pm"), ("design-coach", "coach")):
        body = _without_comments(blocks[job])
        assert "steps.p1.outcome != 'success'" not in body, (
            f"auto-review.yml [{job}] still keys on exit codes — issue #770 "
            "migrated it to the artifact walk")
        assert "reviewer-posted.sh" in body, (
            f"auto-review.yml [{job}] lost the artifact reader")
        assert f"--reviewer {reviewer}" in body, (
            f"auto-review.yml [{job}] does not check --reviewer {reviewer}")
        assert "steps.v1.outputs.served != 'true'" in body, (
            f"auto-review.yml [{job}] walk does not key on served outputs")


def test_pm_and_coach_tolerate_a_pre_770_base_checker():
    """CodeRabbit on #820: base.ref / base.sha may still carry a jane|drik-only
    checker. Exit 2 for hardcoded pm/coach must become served=false (walk
    continues), never a step failure and never a pass — and never the
    PR-head checker."""
    text = _workflow_text()
    blocks = _job_blocks(text)
    needle = r"must be jane or drik \(got: (pm|coach)\)"
    for job, who in (("pm-triage", "pm"), ("design-coach", "coach")):
        body = _without_comments(blocks[job])
        assert needle in body, (
            f"auto-review.yml [{job}] lost the pre-#770 exit-2 compat match "
            f"— an older base checker would abort the walk under set -e")
        assert f"base checker predates #770 ({who})" in body, (
            f"auto-review.yml [{job}] lost the pre-#770 notice"
            f" ({who})")
        # served=false is written explicitly — old checker never reaches
        # its GITHUB_OUTPUT write when usage() exits 2.
        assert 'echo "served=false" >> "$GITHUB_OUTPUT"' in body, (
            f"auto-review.yml [{job}] does not write served=false on the "
            "older-checker path — the walk would see an empty served")
        # Trust boundary: coach still extracts the checker from base.sha;
        # neither job may point the check at the PR-head tree as a "fix".
        assert "head.sha}}:scripts/reviewer-posted.sh" not in body, (
            f"auto-review.yml [{job}] switched the checker to the PR head "
            "— that weakens the trust boundary CodeRabbit called out")
    coach = _without_comments(blocks["design-coach"])
    assert 'git show "${BASE_SHA}:scripts/reviewer-posted.sh"' in coach, (
        "design-coach no longer restores reviewer-posted.sh from base.sha")


def _coach_lock_check_step(text: str) -> str:
    """The design-coach completeness pin (not an artifact-check vN step)."""
    steps = _steps(_job_blocks(text)["design-coach"])
    for chunk in steps:
        if "Coach posted a COACH-LOCK" in chunk:
            return chunk
    raise AssertionError(
        "auto-review.yml [design-coach] lost the Coach posted a COACH-LOCK "
        "step — the #806 completeness pin is gone")


def _assert_coach_lock_check_is_success_only(text: str) -> None:
    """Lock check runs after a claimed success, never on provider failure.

    Bugbot Medium on #820: #770 widened the if to success|failure. The step
    has no continue-on-error, so a fully-exhausted provider chain (every
    ship link failed, no COACH-LOCK posted) failed as a missing lock and
    skipped Diagnose / Every configured provider failed. Missing-lock is
    only meaningful after a ship link claimed success (#806); exhaustion
    must reach the provider-triage path.
    """
    chunk = _coach_lock_check_step(text)
    cond = _if_condition(chunk)
    for n in range(1, LINKS + 1):
        success = f"steps.p{n}.outcome == 'success'"
        failure = f"steps.p{n}.outcome == 'failure'"
        assert success in cond, (
            f"auto-review.yml [design-coach] COACH-LOCK check lost "
            f"{success} — a denial-only exit-0 turn would skip the pin "
            "(issue #806)")
        assert failure not in cond, (
            f"auto-review.yml [design-coach] COACH-LOCK check still keys on "
            f"{failure} — provider exhaustion would fail as a missing lock "
            "and skip the exhaustion diagnosis (Bugbot on #820)")
    assert "continue-on-error" not in chunk.split("run:", 1)[0], (
        "auto-review.yml [design-coach] COACH-LOCK check gained "
        "continue-on-error — a success-without-lock round would stamp "
        "green (issue #806)")
    # Exhaustion gates must still be reachable when no link succeeded:
    # they key on served, not on the lock-check outcome.
    _assert_exhaustion_gates_key_on_the_artifact(text)


def test_coach_lock_check_runs_only_after_a_ship_success():
    _assert_coach_lock_check_is_success_only(_workflow_text())


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
    # Issue #770 vocabulary: pm and coach completion markers.
    for needle in ("PM_TRIAGE_DONE", "COACH_DONE", "jane|drik|pm|coach"):
        assert needle in body, (
            f"scripts/reviewer-posted.sh lost its #770 vocabulary pin "
            f"({needle!r})")


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


def test_check_guard_rejects_a_dropped_pm_artifact_check():
    # NEGATIVE CONTROL: drop PM's link-1 artifact check — the #770 hole.
    tampered = _drop_step(_workflow_text(), "pm-triage", "id: v1")
    with pytest.raises(AssertionError, match="artifact check"):
        _assert_every_link_is_artifact_checked(tampered)


def test_check_guard_rejects_a_dropped_coach_artifact_check():
    # NEGATIVE CONTROL: drop coach's link-2 artifact check.
    tampered = _drop_step(_workflow_text(), "design-coach", "id: v2")
    with pytest.raises(AssertionError, match="artifact check"):
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


def test_walk_guard_rejects_a_pm_link_reverted_to_exit_codes():
    # NEGATIVE CONTROL: PM link 2 back on exit codes (issue #770 regression).
    tampered = _job_replace(
        _workflow_text(), "pm-triage",
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
        f"          && steps.v{n}.outputs.served != 'true'" for n in range(1, 7))
    outcomes = "\n".join(
        f"          && steps.p{n}.outcome != 'success'" for n in range(1, 7))
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


def test_pm_coach_guard_rejects_an_exit_code_regression():
    # NEGATIVE CONTROL: PM walk silently reverted to exit codes after #770.
    tampered = _job_replace(
        _workflow_text(), "pm-triage",
        "steps.v1.outputs.served != 'true'",
        "steps.p1.outcome != 'success'", count=-1)
    blocks = _job_blocks(tampered)
    body = _without_comments(blocks["pm-triage"])
    with pytest.raises(AssertionError, match="still keys on exit codes"):
        assert "steps.p1.outcome != 'success'" not in body, (
            "auto-review.yml [pm-triage] still keys on exit codes — issue #770 "
            "migrated it to the artifact walk")


def test_lock_check_guard_rejects_widening_to_failure():
    # NEGATIVE CONTROL: Bugbot on #820 — success|failure on the lock check
    # makes provider exhaustion look like a missing COACH-LOCK.
    success_only = (
        "          && (steps.p1.outcome == 'success'\n"
        "              || steps.p2.outcome == 'success'\n"
        "              || steps.p3.outcome == 'success'\n"
        "              || steps.p4.outcome == 'success'\n"
        "              || steps.p5.outcome == 'success'\n"
        "              || steps.p6.outcome == 'success')")
    success_or_failure = (
        "          && (steps.p1.outcome == 'success' || steps.p1.outcome == 'failure'\n"
        "              || steps.p2.outcome == 'success' || steps.p2.outcome == 'failure'\n"
        "              || steps.p3.outcome == 'success' || steps.p3.outcome == 'failure'\n"
        "              || steps.p4.outcome == 'success' || steps.p4.outcome == 'failure'\n"
        "              || steps.p5.outcome == 'success' || steps.p5.outcome == 'failure'\n"
        "              || steps.p6.outcome == 'success' || steps.p6.outcome == 'failure')")
    tampered = _job_replace(
        _workflow_text(), "design-coach", success_only, success_or_failure)
    with pytest.raises(AssertionError, match="outcome == 'failure'"):
        _assert_coach_lock_check_is_success_only(tampered)


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
