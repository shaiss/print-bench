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
# DISPOSITION BY ARTIFACT, NOT EXIT CODE (issue #538): the workflow's ship
# links are claude-code-action steps that exit 0 whenever the agent ended its
# turn without an API error — an agent that claimed, produced no branch, no
# PR and no decline, and stopped, still reports outcome 'success'. So this
# script trusts exactly one signal from the workflow: the explicit 'not-run'
# value meaning no ship link ran at all. Every other value — 'success'
# included — gets the full corroboration read below, and the disposition is
# derived from what exists on GitHub:
#   delivered  a claude/issue-<N>-* branch or an open closing PR exists
#   declined   a 🚢 DECLINED / 🚦 DECISION NEEDED comment posted after the
#              latest claim, or that claim already reading SHIP-LOCK
#              WITHDRAWN in the agent's own (non-death) wording
#   dead       anything else — withdrawal posted, death counted, escalation
#              at the threshold — regardless of the exit code passed in,
#              which is carried in the withdrawal body as a diagnostic only
# The workflow gates its red-on-death and provider-triage steps on the
# `delivered`/`declined` outputs, never on the walk's outcome string.
#
# ACCEPTED RACE: the cleanup withdraws the LATEST active lock, so in the rare
# case a hand-run claimed the same issue between our lock and our death, that
# claim gets withdrawn too. The branch/PR corroboration above means real work
# is never orphaned, and a re-claim costs the hand-run one comment. The
# artifact-derived disposition opens a second door to the same race: an
# exit-0 run that never claimed (it found the issue taken and stopped
# silently) is scored dead and withdraws the rival claim it found. Both doors
# end in the same trade — a comment the rival re-posts — and neither can
# orphan real work.
#
# Usage:
#   scripts/routine-lock-cleanup.sh --repo <owner/name> --issue <N> \
#       --agent-outcome <not-run|success|failure|cancelled|skipped> \
#       --run-url <url> --routine <design-run|backlog-burn> \
#       [--escalate-after <n>]                                # default 3
#   scripts/routine-lock-cleanup.sh --selftest
#
# Live mode needs GH_TOKEN (gh api auth) — checked after the not-run no-op,
# so a run with no ship link at all concludes without it. Appends
# `delivered=`, `declined=`, `withdrawn=` and `escalated=` to $GITHUB_OUTPUT
# and one summary line to $GITHUB_STEP_SUMMARY when those are set. Exit
# codes: 0 = decided and acted (including a no-op); 1 = a GitHub API call
# failed (fail loud — a cleanup that can't clean must go red, or the ghost
# locks return silently); 2 = usage.
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
           --agent-outcome <not-run|success|failure|cancelled|skipped>
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

# The comment markers a deliberate terminal stop leads with (the skill's §1
# decline and §8 decision-gate forms). Counted as "declined" only when posted
# AFTER the latest claim, so a previous run's decline never vouches for this
# one.
DECLINE_MARKER_1='🚢 DECLINED'
DECLINE_MARKER_2='🚦 DECISION NEEDED'

# The latest SHIP-LOCK comment (claim or withdrawal form alike), or null.
# First-of-ties on equal created_at, matching Python max() in the selector
# exactly (jq max_by would keep the last of ties).
JQ_LATEST_LOCK='def latest_lock:
  [ .[] | select(fl(.body) | startswith($marker)) ]
  | if length == 0 then null
    else (reduce .[] as $c (.[0]; if $c.created_at > .created_at then $c else . end))
    end;'

# stdin: NDJSON comments {body, created_at}. Prints the latest SHIP-LOCK's
# state, "active", "withdrawn" or "none" — the selector's _ship_lock_state
# split by cause: "withdrawn" distinguishes a claim somebody released from
# "none" (no lock comment at all), because only the former is evidence of a
# deliberate terminal stop by the run that claimed.
lock_state() {
  jq -rs --arg marker "$LOCK_MARKER" "$JQ_FL $JQ_LATEST_LOCK"'
    latest_lock as $l
    | if $l == null then "none"
      elif ($l | fl(.body) | ascii_upcase | contains("WITHDRAWN")) then "withdrawn"
      else "active" end'
}

# stdin: NDJSON comments. Prints true/false: a 🚢 DECLINED or 🚦 DECISION
# NEEDED comment was posted strictly after the latest claim — the skill's own
# terminal-stop markers. A decline posted BEFORE the claim (a previous run's)
# does not count, and neither does the marker mid-line: the skill leads its
# stop comments with the marker.
decline_indicated() {
  jq -rs --arg marker "$LOCK_MARKER" --arg d1 "$DECLINE_MARKER_1" --arg d2 "$DECLINE_MARKER_2" \
    "$JQ_FL $JQ_LATEST_LOCK"'
    latest_lock as $l
    | if $l == null then false
      else [ .[] | select(.created_at > $l.created_at)
             | select(fl(.body) | startswith($d1) or startswith($d2)) ]
           | length > 0
      end'
}

# stdin: NDJSON comments. Prints true/false: the latest lock comment is one
# of THIS script's own death-withdrawal notices (first line starts with
# DEATH_PREFIX). That is a death, not a decline — an agent's own release (the
# skill's §0.6 edit) carries its own wording, never this prefix — and must
# not be read as a deliberate stop by the current run.
death_marked() {
  jq -rs --arg marker "$LOCK_MARKER" --arg prefix "$DEATH_PREFIX" \
    "$JQ_FL $JQ_LATEST_LOCK"'
    latest_lock as $l
    | if $l == null then false
      else ($l | fl(.body) | startswith($prefix))
      end'
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

conclude() {  # delivered declined withdrawn escalated summary — the one exit path
  emit delivered "$1"
  emit declined "$2"
  emit withdrawn "$3"
  emit escalated "$4"
  note "routine-lock-cleanup (${ROUTINE}, #${ISSUE}): $5"
  exit 0
}

# ---- live flow ------------------------------------------------------------

run_live() {
  # 1. The one workflow signal this script trusts: 'not-run' means no ship
  # link ran at all (the walk's all-skipped case — a cancelled-before-agent
  # job, or the agent steps' key/dry-run gates all taking the skip path).
  # Everything else gets the corroboration read below, because a ship link's
  # exit code does not mean what the workflow used to think it means (#538):
  # claude-code-action exits 0 whenever the agent ended its turn without an
  # API error, pushed branch or not. Before the GH_TOKEN check on purpose:
  # this path needs no auth and no network.
  if [ "$OUTCOME" = "not-run" ]; then
    echo "::notice::no ship link ran (outcome '$OUTCOME') — nothing to release on #$ISSUE"
    conclude false false false false "no-op (no ship link ran)"
  fi

  if [ -z "${GH_TOKEN:-}" ]; then
    echo "routine-lock-cleanup: GH_TOKEN is required to derive the disposition for agent outcome '$OUTCOME'" >&2
    exit 1
  fi

  # 2/3. Corroboration before the lock (the selector's own ordering): a
  # claude/issue-<N>-* branch or a closing PR means the claim is backed by
  # real work in flight — delivered, whatever the ship links' exit codes
  # said (a link can time out a minute after pushing).
  local branches prs comments state
  branches="$(gh_api --paginate "/repos/$REPO/branches?per_page=100" --jq '.[].name')"
  if branch_corroborates "$ISSUE" <<<"$branches"; then
    echo "::notice::a claude/issue-$ISSUE-* branch exists — the run delivered; not withdrawing"
    conclude true false false false "delivered (a corroborating branch exists)"
  fi

  prs="$(gh_api --paginate "/repos/$REPO/pulls?state=open&per_page=100" \
    --jq '.[] | {ref: (.head.ref // ""), body: (.body // "")}')"
  if [ "$(pr_corroborates "$ISSUE" <<<"$prs")" = "true" ]; then
    echo "::notice::an open PR already closes #$ISSUE — the run delivered; not withdrawing"
    conclude true false false false "delivered (an open PR closes #$ISSUE)"
  fi

  # 4. A deliberate terminal stop by the run that claimed: the skill's own
  # §1/§8 stop comment posted after its claim, or its §0.6 release (the claim
  # edited to SHIP-LOCK WITHDRAWN in the agent's wording — never this
  # script's DEATH_PREFIX, which marks a death, not a decline).
  comments="$(gh_api --paginate "/repos/$REPO/issues/$ISSUE/comments?per_page=100" \
    --jq '.[] | {body: (.body // ""), created_at: .created_at}')"
  if [ "$(decline_indicated <<<"$comments")" = "true" ]; then
    echo "::notice::a DECLINED/DECISION NEEDED comment follows the claim on #$ISSUE — a deliberate stop, not a death"
    conclude false true false false "declined (a stop comment follows the claim)"
  fi
  state="$(lock_state <<<"$comments")"
  if [ "$state" = "withdrawn" ] && [ "$(death_marked <<<"$comments")" != "true" ]; then
    echo "::notice::the claim on #$ISSUE already reads SHIP-LOCK WITHDRAWN in the agent's own wording — it released its lock"
    conclude false true false false "declined (the claim was self-withdrawn)"
  fi
  if [ "$state" != "active" ]; then
    # No lock this run could have left (never claimed, or the latest lock is
    # one of our own death-withdrawal notices from an earlier firing). No
    # withdrawal, no death to count — but NOT delivered and NOT declined: the
    # workflow's red gate reads those and decides.
    echo "::notice::no active SHIP-LOCK on #$ISSUE — nothing to release"
    conclude false false false false "no-op (no active lock)"
  fi

  # 5. Dead — regardless of the exit code passed in. Withdraw: a new
  # comment, never a deletion: timestamps are the record.
  local body
  body="$(printf '%s\n\n- routine: %s\n- agent outcome (diagnostic only — the disposition is derived from the artifacts above): %s\n- run: %s\n\nThe claim above is released (not deleted — timestamps are the record) so the next firing can select this issue again.' \
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
    conclude false false true false "withdrew a dead run's SHIP-LOCK (death $total of $ESCALATE_AFTER before escalation)"
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
  conclude false false true true "withdrew the lock and escalated ($total dead runs >= $ESCALATE_AFTER) — parked with $DECISION_LABEL"
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
  [ "$(lock_state < "$tmp/withdrawn.ndjson")" = "withdrawn" ] \
    || st_fail "a lowercase-withdrawn latest lock was not classified withdrawn"
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

  # -- decline detection: the skill's §1/§8 stop markers AFTER the claim -----
  # Positive: a DECLINED or DECISION NEEDED comment strictly after the latest
  # claim reads as a deliberate stop. Negative controls: the same marker
  # BEFORE the claim (a previous run's decline never vouches for this one),
  # the marker mid-line, and a thread with no claim at all.
  cat > "$tmp/declined-after.ndjson" <<'EOF'
{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-08-01T00:00:00Z"}
{"body": "🚢 DECLINED — needs a decision\n\nthe issue offers options nobody picked", "created_at": "2026-08-02T00:00:00Z"}
EOF
  [ "$(decline_indicated < "$tmp/declined-after.ndjson")" = "true" ] \
    || st_fail "a DECLINED comment after the claim was not read as a decline"
  cat > "$tmp/decision-after.ndjson" <<'EOF'
{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-08-01T00:00:00Z"}
{"body": "🚦 DECISION NEEDED — `tol-default-loosen`\n\nparked per the gate", "created_at": "2026-08-02T00:00:00Z"}
EOF
  [ "$(decline_indicated < "$tmp/decision-after.ndjson")" = "true" ] \
    || st_fail "a DECISION NEEDED comment after the claim was not read as a decline"
  cat > "$tmp/declined-before.ndjson" <<'EOF'
{"body": "🚢 DECLINED — earlier run gave up here", "created_at": "2026-08-01T00:00:00Z"}
{"body": "🚢 SHIP-LOCK\n\nclaimed afresh", "created_at": "2026-08-02T00:00:00Z"}
EOF
  [ "$(decline_indicated < "$tmp/declined-before.ndjson")" = "false" ] \
    || st_fail "a decline posted BEFORE the claim wrongly vouched for this run"
  cat > "$tmp/declined-midline.ndjson" <<'EOF'
{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-08-01T00:00:00Z"}
{"body": "beware the 🚢 DECLINED marker mid-line", "created_at": "2026-08-02T00:00:00Z"}
EOF
  [ "$(decline_indicated < "$tmp/declined-midline.ndjson")" = "false" ] \
    || st_fail "a mid-line decline marker was counted as a stop comment"
  [ "$(decline_indicated < "$tmp/nolock.ndjson")" = "false" ] \
    || st_fail "a thread with no claim at all read as declined"

  # -- death-marking: our own withdrawal notice is a death, not a decline ---
  cat > "$tmp/our-death.ndjson" <<'EOF'
{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-08-01T00:00:00Z"}
{"body": "🚢 SHIP-LOCK WITHDRAWN — scheduled run died before delivering\n\n- routine: backlog-burn", "created_at": "2026-08-02T00:00:00Z"}
EOF
  [ "$(death_marked < "$tmp/our-death.ndjson")" = "true" ] \
    || st_fail "our own death-withdrawal notice was not death-marked"
  [ "$(death_marked < "$tmp/withdrawn.ndjson")" = "false" ] \
    || st_fail "an agent's own (non-death) withdrawal was wrongly death-marked"
  [ "$(death_marked < "$tmp/nolock.ndjson")" = "false" ] \
    || st_fail "a thread with no lock at all read as death-marked"
  echo "ok    selftest: decline detection (after-claim / before-claim / mid-line / no-claim) + death marking"

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

  # -- the not-run no-op, end to end, plus the tokenless refusals ----------
  # 'not-run' is the one workflow signal that concludes with no GitHub read.
  : > "$tmp/out"
  GITHUB_OUTPUT="$tmp/out" GITHUB_STEP_SUMMARY="$tmp/sum" "$SELF" \
    --repo o/r --issue 1 --agent-outcome not-run --run-url u --routine design-run \
    >/dev/null || st_fail "a not-run outcome did not no-op cleanly"
  for kv in delivered=false declined=false withdrawn=false escalated=false; do
    grep -qx "$kv" "$tmp/out" || st_fail "the not-run no-op did not emit $kv"
  done
  # Negative control — THE #538 assertion: every other outcome, 'success'
  # included, must reach the corroboration read, so with no GH_TOKEN it must
  # refuse loudly (exit 1) before touching the network, never exit 0.
  for outcome in success failure cancelled skipped; do
    rc=0
    env GH_TOKEN= GITHUB_OUTPUT= GITHUB_STEP_SUMMARY= "$SELF" \
      --repo o/r --issue 1 --agent-outcome "$outcome" --run-url u --routine design-run \
      >/dev/null 2>&1 || rc=$?
    [ "$rc" = 1 ] || st_fail "a '$outcome' outcome with no GH_TOKEN exited $rc, not 1 — the exit-code no-op is back"
  done
  echo "ok    selftest: not-run no-op + tokenless refusal for every other outcome"

  # -- disposition end to end over a gh stub -------------------------------
  # The three rows the fix is named for, plus escalation, proven against the
  # REAL CLI: a stub gh serves fixture JSON for the script's GETs (applying
  # the same --jq filter the real gh would) and logs every POST, so the
  # dispositions and the "which comments got posted" side are both asserted.
  mkdir -p "$tmp/bin"
  cat > "$tmp/bin/gh" <<'STUB'
#!/usr/bin/env bash
# selftest double: fixture-backed gh. GETs serve ${GH_STUB_FIXTURES}/<name>.json
# piped through the --jq filter the caller passed; POSTs are logged verbatim.
set -u
filter=''
args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --jq) filter="$2"; shift 2 ;;
    *) args+=("$1"); shift ;;
  esac
done
joined="${args[*]}"
case "$joined" in
  *"--method POST"*) printf '%s\n' "$joined" >> "${GH_STUB_POSTLOG:?}"; exit 0 ;;
  *"/branches?"*) fixture=branches ;;
  *"/pulls?state=open"*) fixture=pulls ;;
  *"/comments?per_page=100"*) fixture=comments ;;
  *"repos/o/r/labels"*) fixture=labels ;;
  *) echo "gh stub: unhandled api call: $joined" >&2; exit 1 ;;
esac
# -r: gh api --jq prints string results raw (the ensure-label idiom greps
# unquoted names), so the stub must too or branch corroboration never fires.
if [ -n "$filter" ]; then jq -r "$filter" < "${GH_STUB_FIXTURES:?}/$fixture.json"; else cat "$GH_STUB_FIXTURES/$fixture.json"; fi
STUB
  chmod +x "$tmp/bin/gh"

  # run_case <name> <outcome> -- runs the real CLI over $tmp/<name>-fix/
  e2e() {  # name outcome
    local name="$1" outcome="$2"
    : > "$tmp/$name-postlog"
    : > "$tmp/$name-out"
    PATH="$tmp/bin:$PATH" GH_TOKEN=stub GH_STUB_FIXTURES="$tmp/$name-fix" \
      GH_STUB_POSTLOG="$tmp/$name-postlog" GITHUB_OUTPUT="$tmp/$name-out" \
      GITHUB_STEP_SUMMARY='' "$SELF" \
      --repo o/r --issue 1 --agent-outcome "$outcome" --run-url u --routine backlog-burn \
      >/dev/null || st_fail "the '$name' case exited non-zero"
  }
  e2e_fix() {  # case fixture json → writes $tmp/<case>-fix/<fixture>.json
    mkdir -p "$tmp/$1-fix"
    printf '%s\n' "$3" > "$tmp/$1-fix/$2.json"
  }
  no_posts() {  # name
    [ ! -s "$tmp/$1-postlog" ] || st_fail "the '$1' case posted to GitHub: $(cat "$tmp/$1-postlog")"
  }

  # Row 1 (#538's exact shape): exit 0, an active claim, nothing else → dead.
  e2e_fix dead comments '[{"body": "🚢 SHIP-LOCK\n\nclaimed by the run", "created_at": "2026-09-01T15:01:00Z"}]'
  e2e_fix dead branches '[]'
  e2e_fix dead pulls '[]'
  e2e dead success
  grep -qx 'withdrawn=true' "$tmp/dead-out" || st_fail "exit-0 + no branch/PR/decline did not emit withdrawn=true"
  grep -qx 'delivered=false' "$tmp/dead-out" || st_fail "the dead case did not emit delivered=false"
  grep -qx 'declined=false' "$tmp/dead-out" || st_fail "the dead case did not emit declined=false"
  grep -q -- '--method POST /repos/o/r/issues/1/comments' "$tmp/dead-postlog" \
    || st_fail "the dead case did not post the withdrawal comment"

  # Row 2: exit 0 with a corroborating branch → delivered, nothing posted.
  e2e_fix branch comments '[{"body": "🚢 SHIP-LOCK\n\nclaimed by the run", "created_at": "2026-09-01T15:01:00Z"}]'
  e2e_fix branch branches '[{"name": "claude/issue-1-the-fix"}]'
  e2e_fix branch pulls '[]'
  e2e branch success
  grep -qx 'delivered=true' "$tmp/branch-out" || st_fail "exit-0 + branch did not emit delivered=true"
  no_posts branch

  # Row 3: exit 0 with a DECLINED comment after the claim → declined, nothing
  # posted (the lock is left to age out through the selector's staleness, per
  # the fix's design).
  e2e_fix declined comments '[{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-09-01T15:01:00Z"},{"body": "🚢 DECLINED — the issue needs a decision\n\nparked", "created_at": "2026-09-01T16:00:00Z"}]'
  e2e_fix declined branches '[]'
  e2e_fix declined pulls '[]'
  e2e declined success
  grep -qx 'declined=true' "$tmp/declined-out" || st_fail "exit-0 + DECLINED did not emit declined=true"
  no_posts declined

  # Row 3b: exit 0 with the claim self-withdrawn in the agent's own wording →
  # declined (its §0.6 release), nothing posted.
  e2e_fix selfwd comments '[{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-09-01T15:01:00Z"},{"body": "🚢 SHIP-LOCK WITHDRAWN — this run is stopping without shipping", "created_at": "2026-09-01T15:02:00Z"}]'
  e2e_fix selfwd branches '[]'
  e2e_fix selfwd pulls '[]'
  e2e selfwd success
  grep -qx 'declined=true' "$tmp/selfwd-out" || st_fail "a self-withdrawn claim did not emit declined=true"
  no_posts selfwd

  # Escalation still fires at the threshold under the new disposition: two
  # prior death-withdrawals + this death → withdrawal, label add, decision
  # comment, escalated=true.
  e2e_fix esc comments '[{"body": "🚢 SHIP-LOCK WITHDRAWN — scheduled run died before delivering\n\ndetails", "created_at": "2026-09-01T00:00:00Z"},{"body": "🚢 SHIP-LOCK WITHDRAWN — scheduled run died before delivering\n\ndetails", "created_at": "2026-09-02T00:00:00Z"},{"body": "🚢 SHIP-LOCK\n\nclaimed again", "created_at": "2026-09-03T00:00:00Z"}]'
  e2e_fix esc branches '[]'
  e2e_fix esc pulls '[]'
  e2e_fix esc labels '[{"name": "needs-decision"}]'
  e2e esc failure
  grep -qx 'escalated=true' "$tmp/esc-out" || st_fail "the 3rd death did not emit escalated=true"
  grep -q -- '--method POST /repos/o/r/issues/1/labels' "$tmp/esc-postlog" \
    || st_fail "the escalation did not add the needs-decision label"
  grep -q -- '--method POST /repos/o/r/issues/1/comments' "$tmp/esc-postlog" \
    || st_fail "the escalation did not post the decision comment"

  echo "ok    selftest: end-to-end dispositions (dead / delivered / declined / self-withdrawn / escalated)"

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
  [ "$(lock_state < "$tmp/ours.ndjson")" = "withdrawn" ] \
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
case "$OUTCOME" in not-run|success|failure|cancelled|skipped) : ;;
  *) usage "--agent-outcome must be not-run|success|failure|cancelled|skipped, got '$OUTCOME'" ;; esac
case "$ROUTINE" in design-run|backlog-burn) : ;;
  *) usage "--routine must be design-run|backlog-burn, got '$ROUTINE'" ;; esac
case "$ESCALATE_AFTER" in ''|0|*[!0-9]*) usage "--escalate-after must be a positive integer, got '$ESCALATE_AFTER'" ;; esac

run_live
