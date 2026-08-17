#!/usr/bin/env bash
# Withdraw the 🚢 SHIP-LOCK a dead scheduled run left behind (issue #312).
#
# The livelock this closes: design-run/backlog-burn post a "🚢 SHIP-LOCK"
# claim comment on the issue they select, then the job timeout (or a provider
# stall) kills the agent before it delivers or withdraws. The selector
# (tools/backlog-burn/src/backlog_burn/select.py) then reads the orphaned
# claim as "already taken", and every later firing is a green no-op — dead
# runs disguised as health. This script runs as a normal workflow step after
# the agent step and releases such a claim, mirroring the selector's own
# semantics and ordering: corroborating branches and closing PRs are checked
# FIRST, so a claim backed by real work is never orphaned.
#
# ACCEPTED RACE: the cleanup withdraws the LATEST active lock, so in the rare
# case a hand-run claimed the same issue between our lock and our death, that
# claim gets withdrawn too. The branch/PR corroboration above means real work
# is never orphaned, and a re-claim costs the hand-run one comment.
#
# Usage:
#   scripts/routine-lock-cleanup.sh --repo <owner/name> --issue <N> \
#       --agent-outcome <success|failure|cancelled|skipped> \
#       --run-url <url> --routine <design-run|backlog-burn> \
#       [--escalate-after <n>]                                # default 3
#   scripts/routine-lock-cleanup.sh --selftest
#
# Live mode needs GH_TOKEN (gh api auth) — checked after the success/skipped
# no-op, so a delivered run concludes without it. Appends `withdrawn=` and
# `escalated=` to $GITHUB_OUTPUT and one summary line to $GITHUB_STEP_SUMMARY
# when those are set. Exit codes: 0 = decided and acted (including a no-op);
# 1 = a GitHub API call failed (fail loud — a cleanup that can't clean must
# go red, or the ghost locks return silently); 2 = usage.
set -euo pipefail

# Absolute path to this script, captured before the cd so --selftest can
# re-invoke the real CLI end-to-end on its no-op and refusal paths.
SELF="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)/$(basename "$0")"
cd "$(dirname "$0")/.."

# The literal strings the selector classifies on (select.py: the first
# non-blank line must start with SHIP_LOCK_MARKER, and "WITHDRAWN" anywhere
# in that line releases the claim). The withdrawal line must start with the
# marker AND carry WITHDRAWN or the selector keeps reading the claim as
# active — asserted by --selftest against these literals.
LOCK_MARKER='🚢 SHIP-LOCK'
WITHDRAW_LINE='🚢 SHIP-LOCK WITHDRAWN — scheduled run died before delivering'
# Stable prefix the escalation counter keys on; the tail of WITHDRAW_LINE may
# be reworded, this prefix may not (old comments would stop counting).
DEATH_PREFIX='🚢 SHIP-LOCK WITHDRAWN — scheduled run died'
DECISION_LABEL='needs-decision'

# jq prelude: first non-blank line of a body, stripped — the line
# backlog_burn.select._first_line classifies on.
JQ_FL='def fl($b): ($b // "") | split("\n")
  | map(gsub("^[[:space:]]+|[[:space:]]+$"; ""))
  | map(select(length > 0)) | (.[0] // "");'

usage() {  # [message]
  [ $# -eq 0 ] || echo "routine-lock-cleanup: $*" >&2
  cat >&2 <<'EOF'
usage: scripts/routine-lock-cleanup.sh --repo <owner/name> --issue <N>
           --agent-outcome <success|failure|cancelled|skipped>
           --run-url <url> --routine <design-run|backlog-burn>
           [--escalate-after <n>]
       scripts/routine-lock-cleanup.sh --selftest
EOF
  exit 2
}

# jq is this script's one JSON tool (its stream filters are what the decision
# functions are built from), a departure from the no-standalone-jq convention
# product-page.sh documents — accepted for this script because the selftest
# and live mode share the same jq predicates. It is preinstalled on the CI
# runners and installed by .claude/hooks/session-start.sh; fail with a clear
# name here rather than a mid-run command-not-found.
command -v jq >/dev/null 2>&1 || {
  echo "routine-lock-cleanup: jq is required (apt-get install -y jq, or re-run .claude/hooks/session-start.sh --force)" >&2
  exit 1
}

# ---- pure decision functions (JSON/text on stdin, no network) -------------

# stdin: NDJSON comments {body, created_at}. Prints the latest SHIP-LOCK's
# state, "active" or "none" — the selector's _ship_lock_state without the
# staleness branch (this cleanup acts on its own run's death, not on age).
lock_state() {
  jq -rs --arg marker "$LOCK_MARKER" "$JQ_FL"'
    [ .[] | select(fl(.body) | startswith($marker)) ]
    | if length == 0 then "none"
      # First-of-ties on equal created_at, matching Python max() in the
      # selector exactly (jq max_by would keep the last of ties).
      elif ((reduce .[] as $c (.[0]; if $c.created_at > .created_at then $c else . end))
            | fl(.body) | ascii_upcase | contains("WITHDRAWN"))
        then "none"
      else "active" end'
}

# stdin: branch names, one per line. $1: the issue number (validated as an
# integer up front, so it needs no regex escaping). Exit 0 when a
# claude/issue-<N>-* branch exists — the trailing "-" keeps issue 281 from
# being corroborated by claude/issue-2811-*.
branch_corroborates() {
  grep -q "^claude/issue-$1-"
}

# stdin: NDJSON PRs {ref, body}. $1: the issue number. Prints true/false: an
# open PR corroborates when its head branch is claude/issue-<N>-* or its body
# carries one of GitHub's nine closing keywords for #<N> (select.py's
# _closes_issue pattern: keyword, optional colon, whitespace, #N, trailing
# boundary — so "#9" never matches "#95").
pr_corroborates() {
  jq -rs --arg n "$1" '
    def closes($b):
      ["close","closes","closed","fix","fixes","fixed",
       "resolve","resolves","resolved"]
      | any(. as $kw
            | ($b // "") | test("\\b" + $kw + ":?\\s+#" + $n + "\\b"; "i"));
    any(.[]; ((.ref // "") | test("^claude/issue-" + $n + "-")) or closes(.body))'
}

# stdin: NDJSON comments. Prints how many dead-run withdrawal notices this
# issue already carries — the "before this run's POST" side of the counter.
count_dead_withdrawals() {
  jq -rs --arg prefix "$DEATH_PREFIX" "$JQ_FL"'
    [ .[] | select(fl(.body) | startswith($prefix)) ] | length'
}

# $1: prior dead-run withdrawals, $2: escalate-after threshold. Counts this
# run's own withdrawal (+1) so the Nth death escalates in the same run that
# posts it, not one firing later.
should_escalate() {
  [ $(( $1 + 1 )) -ge "$2" ]
}

# ---- the one network seam -------------------------------------------------

# ALL network access happens here. Any API failure exits 1 (a cleanup that
# cannot clean must go red, never quietly no-op); TOLERATE_422=1 excuses
# exactly the label-creation race where another run created the label first.
gh_api() {
  local out
  if out="$(gh api "$@" 2>&1)"; then
    printf '%s\n' "$out"
    return 0
  fi
  if [ "${TOLERATE_422:-}" = "1" ] && grep -q 'HTTP 422' <<<"$out"; then
    return 0
  fi
  echo "routine-lock-cleanup: gh api $* failed: $out" >&2
  exit 1
}

# ---- Actions plumbing -----------------------------------------------------

emit() {  # key value → $GITHUB_OUTPUT when running under Actions
  if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "$1=$2" >> "$GITHUB_OUTPUT"; fi
}

note() {  # one line → $GITHUB_STEP_SUMMARY when running under Actions
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then echo "$1" >> "$GITHUB_STEP_SUMMARY"; fi
}

conclude() {  # withdrawn escalated summary — the single successful exit path
  emit withdrawn "$1"
  emit escalated "$2"
  note "routine-lock-cleanup (${ROUTINE}, #${ISSUE}): $3"
  exit 0
}

# ---- live flow ------------------------------------------------------------

run_live() {
  # 1. A run that delivered — or never started — left nothing to release.
  # Before the GH_TOKEN check on purpose: the common healthy path needs no
  # auth and no network.
  case "$OUTCOME" in
    success|skipped)
      echo "::notice::agent outcome '$OUTCOME' — no orphaned lock to release on #$ISSUE"
      conclude false false "no-op (agent outcome: $OUTCOME)"
      ;;
  esac

  if [ -z "${GH_TOKEN:-}" ]; then
    echo "routine-lock-cleanup: GH_TOKEN is required to clean up after agent outcome '$OUTCOME'" >&2
    exit 1
  fi

  # 2/3. Corroboration before the lock (the selector's own ordering): a
  # claude/issue-<N>-* branch or a closing PR means the claim is backed by
  # real work in flight — leave it alone.
  local branches prs comments state
  branches="$(gh_api --paginate "/repos/$REPO/branches?per_page=100" --jq '.[].name')"
  if branch_corroborates "$ISSUE" <<<"$branches"; then
    echo "::notice::a claude/issue-$ISSUE-* branch exists — the claim is backed by real work; not withdrawing"
    conclude false false "no-op (a corroborating branch exists)"
  fi

  prs="$(gh_api --paginate "/repos/$REPO/pulls?state=open&per_page=100" \
    --jq '.[] | {ref: (.head.ref // ""), body: (.body // "")}')"
  if [ "$(pr_corroborates "$ISSUE" <<<"$prs")" = "true" ]; then
    echo "::notice::an open PR already closes #$ISSUE — the claim is backed by real work; not withdrawing"
    conclude false false "no-op (an open PR closes #$ISSUE)"
  fi

  # 4. The latest lock's state, per the selector's first-non-blank-line rule.
  comments="$(gh_api --paginate "/repos/$REPO/issues/$ISSUE/comments?per_page=100" \
    --jq '.[] | {body: (.body // ""), created_at: .created_at}')"
  state="$(lock_state <<<"$comments")"
  if [ "$state" != "active" ]; then
    echo "::notice::no active SHIP-LOCK on #$ISSUE — nothing to release"
    conclude false false "no-op (no active lock)"
  fi

  # 5. Withdraw — a new comment, never a deletion: timestamps are the record.
  local body
  body="$(printf '%s\n\n- routine: %s\n- agent outcome: %s\n- run: %s\n\nThe claim above is released (not deleted — timestamps are the record) so the next firing can select this issue again.' \
    "$WITHDRAW_LINE" "$ROUTINE" "$OUTCOME" "$RUN_URL")"
  gh_api --method POST "/repos/$REPO/issues/$ISSUE/comments" -f body="$body" >/dev/null
  echo "::notice::withdrew a dead $ROUTINE run's SHIP-LOCK on #$ISSUE (agent outcome: $OUTCOME)"

  # 6. Escalate a repeat offender to a human (docs/decision-gate.md). Counted
  # from the pre-POST snapshot plus this run's own withdrawal, so the Nth
  # death parks the issue in the same run that notices it.
  local deaths total
  deaths="$(count_dead_withdrawals <<<"$comments")"
  total=$(( deaths + 1 ))
  if ! should_escalate "$deaths" "$ESCALATE_AFTER"; then
    conclude true false "withdrew a dead run's SHIP-LOCK (death $total of $ESCALATE_AFTER before escalation)"
  fi

  # Ensure the label exists — the ensure-label idiom from the decision gate:
  # a --paginate list (gh label list defaults to 30 and would fall through to
  # a 422), POST only when absent, 422 tolerated as a race with a parallel
  # creator. Label before comment, the gate's fail-closed ordering.
  local labels id
  labels="$(gh_api --paginate "repos/$REPO/labels" --jq '.[].name')"
  if ! grep -qxF "$DECISION_LABEL" <<<"$labels"; then
    TOLERATE_422=1 gh_api --method POST "repos/$REPO/labels" \
      -f name="$DECISION_LABEL" \
      -f color='d93f0b' \
      -f description='Parked for a human /decide (issue #161)' >/dev/null
  fi
  gh_api --method POST "/repos/$REPO/issues/$ISSUE/labels" \
    -f "labels[]=$DECISION_LABEL" >/dev/null

  id="${ROUTINE}-run-death-${ISSUE}"
  body="$(printf '🚦 DECISION NEEDED — `%s`\n\n**Question:** %s scheduled %s runs have died after claiming this issue (latest: %s). Keep it armed?\n\n**yes** → the run budget/provider has been fixed; clear the `needs-decision` label to re-arm this issue.\n**no**  → shelve this issue for now.\n\nResolve with `/decide yes %s` or `/decide no %s`.' \
    "$id" "$total" "$ROUTINE" "$RUN_URL" "$id" "$id")"
  gh_api --method POST "/repos/$REPO/issues/$ISSUE/comments" -f body="$body" >/dev/null
  echo "::notice::escalated #$ISSUE to a human decision ($id) after $total dead runs"
  conclude true true "withdrew the lock and escalated ($total dead runs >= $ESCALATE_AFTER) — parked with $DECISION_LABEL"
}

# ---- selftest (fully offline: fixtures + the no-op/refusal CLI paths) -----

selftest() {
  local tmp deaths rc
  tmp="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap "rm -rf '$tmp'" EXIT

  st_fail() { echo "FAIL  selftest: $*"; exit 1; }

  # -- lock classification, each case with its negative control ------------
  cat > "$tmp/active.ndjson" <<'EOF'
{"body": "🚢 SHIP-LOCK\n\nclaimed by run 1", "created_at": "2026-08-01T00:00:00Z"}
{"body": "just a comment", "created_at": "2026-08-02T00:00:00Z"}
EOF
  [ "$(lock_state < "$tmp/active.ndjson")" = "active" ] \
    || st_fail "an active latest lock was not classified active"
  cat > "$tmp/nolock.ndjson" <<'EOF'
{"body": "just a comment", "created_at": "2026-08-02T00:00:00Z"}
EOF
  [ "$(lock_state < "$tmp/nolock.ndjson")" = "none" ] \
    || st_fail "a thread with no lock comment was not classified none"

  # WITHDRAWN latest releases, case-insensitively; the same pair with the
  # timestamps swapped (withdrawal older than the claim) must stay active.
  cat > "$tmp/withdrawn.ndjson" <<'EOF'
{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-08-01T00:00:00Z"}
{"body": "🚢 SHIP-LOCK withdrawn — taking it back", "created_at": "2026-08-03T00:00:00Z"}
EOF
  [ "$(lock_state < "$tmp/withdrawn.ndjson")" = "none" ] \
    || st_fail "a lowercase-withdrawn latest lock was not classified none"
  cat > "$tmp/reclaimed.ndjson" <<'EOF'
{"body": "🚢 SHIP-LOCK withdrawn — taking it back", "created_at": "2026-08-01T00:00:00Z"}
{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-08-03T00:00:00Z"}
EOF
  [ "$(lock_state < "$tmp/reclaimed.ndjson")" = "active" ] \
    || st_fail "a re-claim after a withdrawal was not classified active"

  # The marker mid-line is body text, not a claim; at line start it is one.
  cat > "$tmp/midline.ndjson" <<'EOF'
{"body": "beware the 🚢 SHIP-LOCK marker mid-line", "created_at": "2026-08-01T00:00:00Z"}
EOF
  [ "$(lock_state < "$tmp/midline.ndjson")" = "none" ] \
    || st_fail "a mid-line marker was counted as a lock"
  cat > "$tmp/linestart.ndjson" <<'EOF'
{"body": "🚢 SHIP-LOCK marker at line start", "created_at": "2026-08-01T00:00:00Z"}
EOF
  [ "$(lock_state < "$tmp/linestart.ndjson")" = "active" ] \
    || st_fail "a line-start marker was not counted as a lock"

  # First-NON-blank-line rule: leading blank lines and indentation are
  # stripped before classifying; a marker on a later line does not count.
  cat > "$tmp/blankfirst.ndjson" <<'EOF'
{"body": "\n   🚢 SHIP-LOCK\nclaimed", "created_at": "2026-08-01T00:00:00Z"}
EOF
  [ "$(lock_state < "$tmp/blankfirst.ndjson")" = "active" ] \
    || st_fail "a body starting with a blank line was not classified by its first non-blank line"
  cat > "$tmp/laterline.ndjson" <<'EOF'
{"body": "preamble\n🚢 SHIP-LOCK", "created_at": "2026-08-01T00:00:00Z"}
EOF
  [ "$(lock_state < "$tmp/laterline.ndjson")" = "none" ] \
    || st_fail "a marker below a non-blank first line was counted as a lock"
  echo "ok    selftest: lock classification (active / withdrawn / none / mid-line / first-non-blank)"

  # -- branch corroboration + the near-miss --------------------------------
  printf 'main\nclaude/issue-281-fix-thing\n' | branch_corroborates 281 \
    || st_fail "claude/issue-281-* did not corroborate issue 281"
  if printf 'main\nclaude/issue-2811-x\n' | branch_corroborates 281; then
    st_fail "claude/issue-2811-* wrongly corroborated issue 281"
  fi
  echo "ok    selftest: branch corroboration + near-miss (issue-2811 vs 281)"

  # -- closing keywords + the #9-vs-#95 boundary ---------------------------
  [ "$(printf '{"ref": "feature-x", "body": "Closes #38"}\n' | pr_corroborates 38)" = "true" ] \
    || st_fail "'Closes #38' did not corroborate issue 38"
  [ "$(printf '{"ref": "", "body": "Resolved: #38 at last"}\n' | pr_corroborates 38)" = "true" ] \
    || st_fail "'Resolved: #38' did not corroborate issue 38"
  [ "$(printf '{"ref": "", "body": "Fixes #95"}\n' | pr_corroborates 9)" = "false" ] \
    || st_fail "'Fixes #95' wrongly corroborated issue 9"
  [ "$(printf '{"ref": "", "body": "Fixes #9"}\n' | pr_corroborates 9)" = "true" ] \
    || st_fail "'Fixes #9' did not corroborate issue 9"
  [ "$(printf '{"ref": "feature", "body": "mentions #38 in passing"}\n' | pr_corroborates 38)" = "false" ] \
    || st_fail "a keyword-free mention wrongly corroborated issue 38"
  [ "$(printf '{"ref": "claude/issue-38-x", "body": ""}\n' | pr_corroborates 38)" = "true" ] \
    || st_fail "a claude/issue-38-* head branch did not corroborate issue 38"
  echo "ok    selftest: closing keywords + #9-vs-#95 boundary"

  # -- success/skipped no-op, end to end, plus the tokenless refusal -------
  : > "$tmp/out"
  GITHUB_OUTPUT="$tmp/out" GITHUB_STEP_SUMMARY="$tmp/sum" "$SELF" \
    --repo o/r --issue 1 --agent-outcome success --run-url u --routine design-run \
    >/dev/null || st_fail "a success outcome did not no-op cleanly"
  grep -qx 'withdrawn=false' "$tmp/out" || st_fail "the success no-op did not emit withdrawn=false"
  grep -qx 'escalated=false' "$tmp/out" || st_fail "the success no-op did not emit escalated=false"
  GITHUB_OUTPUT='' GITHUB_STEP_SUMMARY='' "$SELF" \
    --repo o/r --issue 1 --agent-outcome skipped --run-url u --routine backlog-burn \
    >/dev/null || st_fail "a skipped outcome did not no-op cleanly"
  # Negative control: a dead outcome must NOT no-op — with no GH_TOKEN it must
  # refuse loudly (exit 1) before touching the network, never exit 0.
  rc=0
  env GH_TOKEN= GITHUB_OUTPUT= GITHUB_STEP_SUMMARY= "$SELF" \
    --repo o/r --issue 1 --agent-outcome cancelled --run-url u --routine design-run \
    >/dev/null 2>&1 || rc=$?
  [ "$rc" = 1 ] || st_fail "a cancelled outcome with no GH_TOKEN exited $rc, not 1"
  echo "ok    selftest: success/skipped no-op + tokenless negative control"

  # -- escalation fires at the threshold, not below it ---------------------
  cat > "$tmp/two-deaths.ndjson" <<'EOF'
{"body": "🚢 SHIP-LOCK WITHDRAWN — scheduled run died before delivering\n\ndetails", "created_at": "2026-08-01T00:00:00Z"}
{"body": "🚢 SHIP-LOCK WITHDRAWN — scheduled run died before delivering\n\ndetails", "created_at": "2026-08-02T00:00:00Z"}
{"body": "🚢 SHIP-LOCK\n\nclaimed again", "created_at": "2026-08-03T00:00:00Z"}
EOF
  deaths="$(count_dead_withdrawals < "$tmp/two-deaths.ndjson")"
  [ "$deaths" = 2 ] || st_fail "expected 2 prior dead-run withdrawals, got $deaths"
  should_escalate "$deaths" 3 \
    || st_fail "the 3rd death (2 prior + this run) did not escalate at threshold 3"
  cat > "$tmp/one-death.ndjson" <<'EOF'
{"body": "🚢 SHIP-LOCK WITHDRAWN — scheduled run died before delivering\n\ndetails", "created_at": "2026-08-01T00:00:00Z"}
{"body": "🚢 SHIP-LOCK\n\nclaimed again", "created_at": "2026-08-02T00:00:00Z"}
EOF
  deaths="$(count_dead_withdrawals < "$tmp/one-death.ndjson")"
  [ "$deaths" = 1 ] || st_fail "expected 1 prior dead-run withdrawal, got $deaths"
  if should_escalate "$deaths" 3; then
    st_fail "the 2nd death (1 prior + this run) escalated below threshold 3"
  fi
  echo "ok    selftest: escalation fires at 3 and not at 2"

  # -- selector compatibility of the withdrawal line -----------------------
  # The literal strings, asserted directly: the first line must start with
  # the SHIP-LOCK marker AND contain WITHDRAWN (uppercase) or select.py keeps
  # reading the claim as active; and it must keep the DEATH_PREFIX or old
  # withdrawals stop counting toward escalation.
  case "$WITHDRAW_LINE" in
    "$LOCK_MARKER"*) : ;;
    *) st_fail "WITHDRAW_LINE does not start with the SHIP-LOCK marker" ;;
  esac
  case "$WITHDRAW_LINE" in
    *WITHDRAWN*) : ;;
    *) st_fail "WITHDRAW_LINE does not contain WITHDRAWN (uppercase)" ;;
  esac
  case "$WITHDRAW_LINE" in
    "$DEATH_PREFIX"*) : ;;
    *) st_fail "WITHDRAW_LINE drifted off the DEATH_PREFIX the escalation counter keys on" ;;
  esac
  # And the behavioral proof: a comment built from our own withdrawal line
  # must release a prior claim in the classifier itself.
  jq -cn --arg lock "$LOCK_MARKER" --arg wd "$WITHDRAW_LINE" '
    {body: ($lock + "\n\nclaimed"), created_at: "2026-08-01T00:00:00Z"},
    {body: ($wd + "\n\n- routine: design-run"), created_at: "2026-08-02T00:00:00Z"}' \
    > "$tmp/ours.ndjson"
  [ "$(lock_state < "$tmp/ours.ndjson")" = "none" ] \
    || st_fail "our own withdrawal line does not release the lock for the selector"
  echo "ok    selftest: withdrawal first line stays selector-compatible"

  # -- usage errors exit 2 -------------------------------------------------
  rc=0
  "$SELF" --repo o/r --issue not-a-number --agent-outcome cancelled \
    --run-url u --routine design-run >/dev/null 2>&1 || rc=$?
  [ "$rc" = 2 ] || st_fail "a non-integer --issue exited $rc, not 2"
  rc=0
  "$SELF" --repo o/r --issue 1 --agent-outcome exploded \
    --run-url u --routine design-run >/dev/null 2>&1 || rc=$?
  [ "$rc" = 2 ] || st_fail "an unknown --agent-outcome exited $rc, not 2"
  echo "ok    selftest: usage errors exit 2"
}

if [ "${1:-}" = "--selftest" ]; then
  selftest
  echo "ok    routine-lock-cleanup selftest passed"
  exit 0
fi

# ---- argument parsing -----------------------------------------------------

REPO='' ISSUE='' OUTCOME='' RUN_URL='' ROUTINE='' ESCALATE_AFTER=3

need_val() { [ "$#" -ge 2 ] || usage "$1 requires a value"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --repo)           need_val "$@"; REPO="$2"; shift 2 ;;
    --issue)          need_val "$@"; ISSUE="$2"; shift 2 ;;
    --agent-outcome)  need_val "$@"; OUTCOME="$2"; shift 2 ;;
    --run-url)        need_val "$@"; RUN_URL="$2"; shift 2 ;;
    --routine)        need_val "$@"; ROUTINE="$2"; shift 2 ;;
    --escalate-after) need_val "$@"; ESCALATE_AFTER="$2"; shift 2 ;;
    *) usage "unknown argument: $1" ;;
  esac
done

[ -n "$REPO" ] && [ -n "$ISSUE" ] && [ -n "$OUTCOME" ] && [ -n "$RUN_URL" ] && [ -n "$ROUTINE" ] \
  || usage "--repo, --issue, --agent-outcome, --run-url and --routine are all required"
# The issue number reaches grep/jq patterns and API paths — integers only.
case "$ISSUE" in ''|*[!0-9]*) usage "--issue must be an integer, got '$ISSUE'" ;; esac
case "$OUTCOME" in success|failure|cancelled|skipped) : ;;
  *) usage "--agent-outcome must be success|failure|cancelled|skipped, got '$OUTCOME'" ;; esac
case "$ROUTINE" in design-run|backlog-burn) : ;;
  *) usage "--routine must be design-run|backlog-burn, got '$ROUTINE'" ;; esac
case "$ESCALATE_AFTER" in ''|0|*[!0-9]*) usage "--escalate-after must be a positive integer, got '$ESCALATE_AFTER'" ;; esac

run_live
