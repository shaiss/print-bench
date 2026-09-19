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
#              latest claim, that claim already reading SHIP-LOCK
#              WITHDRAWN in the agent's own (non-death) wording, or a
#              🚢 DEFERRED (re-check-later) stop (#690) — the walk found
#              the issue's dependencies unlanded and deferred, which it
#              often does without ever claiming, so that marker is
#              detected on its own anchor (see deferred_indicated)
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
# The marker a deferring walk leads with (#690): dependencies not landed,
# re-check later — a deliberate non-delivery, so decline-class for the
# red-on-death gate. Kept OUT of decline_indicated() because the deferring
# walk usually never claims (the #641 shape: a DEFERRED per firing, not one
# SHIP-LOCK on the thread), leaving that function's "strictly after the
# latest claim" anchor with nothing to anchor to.
DEFER_MARKER='🚢 DEFERRED'

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

# stdin: NDJSON comments. Prints true/false: a first-line 🚢 DEFERRED comment
# posted strictly after the latest lock comment (the claimed shape), or — when
# the thread carries no lock comment at all, the observed claimless shape —
# the DEFERRED being the thread's LATEST comment, the freshest artifact,
# which is what a cleanup running moments after the walk sees. That
# latest-comment bound is what keeps an old DEFERRED from vouching for a
# dead run: a defer anything newer followed (a human reply, a triage note)
# is history, not this run's stop.
deferred_indicated() {
  jq -rs --arg marker "$LOCK_MARKER" --arg d "$DEFER_MARKER" \
    "$JQ_FL $JQ_LATEST_LOCK"'
    latest_lock as $l
    | if $l == null then
        if length == 0 then false
        else (reduce .[] as $c (.[0]; if $c.created_at > .created_at then $c else . end)) as $last
             | ($last | fl(.body) | startswith($d))
        end
      else
        [ .[] | select(.created_at > $l.created_at)
               | select(fl(.body) | startswith($d)) ] | length > 0
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
  if [ "$(deferred_indicated <<<"$comments")" = "true" ]; then
    echo "::notice::a DEFERRED (re-check when dependencies land) comment is the latest stop on #$ISSUE — a deliberate defer, not a death"
    conclude false true false false "declined (a DEFERRED comment defers to unlanded dependencies)"
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

  # -- deferred detection (#690): the re-check-later stop marker -----------
  # Positive: the walk's DEFERRED after the claim, and — the #641 shape — a
  # claimless thread whose LATEST comment is the DEFERRED. Negative controls:
  # the defer before a later claim (a previous run's defer never vouches for
  # this one), the marker mid-line, a stale defer that a newer comment
  # followed, and a claimless thread whose latest comment is not a defer.
  cat > "$tmp/defer-after.ndjson" <<'EOF'
{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-09-01T15:01:00Z"}
{"body": "🚢 DEFERRED (re-check) — dependencies still not landed.", "created_at": "2026-09-01T15:02:00Z"}
EOF
  [ "$(deferred_indicated < "$tmp/defer-after.ndjson")" = "true" ] \
    || st_fail "a DEFERRED comment after the claim was not read as a defer"
  cat > "$tmp/defer-before.ndjson" <<'EOF'
{"body": "🚢 DEFERRED — dependency not landed yet.", "created_at": "2026-09-01T15:00:00Z"}
{"body": "🚢 SHIP-LOCK\n\nclaimed afresh", "created_at": "2026-09-01T15:01:00Z"}
EOF
  [ "$(deferred_indicated < "$tmp/defer-before.ndjson")" = "false" ] \
    || st_fail "a defer posted BEFORE the claim wrongly vouched for this run"
  cat > "$tmp/defer-midline.ndjson" <<'EOF'
{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-09-01T15:01:00Z"}
{"body": "beware the 🚢 DEFERRED marker mid-line", "created_at": "2026-09-01T15:02:00Z"}
EOF
  [ "$(deferred_indicated < "$tmp/defer-midline.ndjson")" = "false" ] \
    || st_fail "a mid-line defer marker was counted as a stop comment"
  # The #641 shape exactly (read off the live thread): no lock comment
  # anywhere, the walk's DEFERRED as the thread's latest artifact.
  cat > "$tmp/defer-claimless.ndjson" <<'EOF'
{"body": "🏷️ Triaged: `autonomy-ok` — still blocked on the dependency.", "created_at": "2026-09-01T05:53:00Z"}
{"body": "🚢 DEFERRED (re-check) — dependencies still not landed.", "created_at": "2026-09-01T06:01:00Z"}
EOF
  [ "$(deferred_indicated < "$tmp/defer-claimless.ndjson")" = "true" ] \
    || st_fail "a claimless thread whose latest comment is a DEFERRED was not read as a defer"
  cat > "$tmp/defer-stale.ndjson" <<'EOF'
{"body": "🚢 DEFERRED (re-check) — dependencies still not landed.", "created_at": "2026-09-01T06:01:00Z"}
{"body": "**Ops stopgap** — parking until deps land.", "created_at": "2026-09-01T06:36:00Z"}
EOF
  [ "$(deferred_indicated < "$tmp/defer-stale.ndjson")" = "false" ] \
    || st_fail "a DEFERRED that a newer comment followed was still read as this run's stop"
  [ "$(deferred_indicated < "$tmp/nolock.ndjson")" = "false" ] \
    || st_fail "a claimless thread whose latest comment is not a defer read as deferred"
  [ "$(deferred_indicated < /dev/null)" = "false" ] \
    || st_fail "an empty comment thread read as deferred"
  echo "ok    selftest: deferred detection (after-claim / before-claim / mid-line / claimless-latest / stale / none)"

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

  # Row 4 (#690's exact shape): exit 0, the walk's DEFERRED as the latest
  # comment on a claimless thread, no branch/PR → declined (a deliberate
  # defer), nothing posted — so the red gate's delivered/declined condition
  # reads declined=true and the job stays green instead of false-redding.
  e2e_fix deferred comments '[{"body": "🏷️ Triaged: `autonomy-ok` — still blocked on the dependency.", "created_at": "2026-09-18T22:39:00Z"},{"body": "🚢 DEFERRED (re-check) — dependencies still not landed.", "created_at": "2026-09-19T06:01:00Z"}]'
  e2e_fix deferred branches '[]'
  e2e_fix deferred pulls '[]'
  e2e deferred success
  grep -qx 'declined=true' "$tmp/deferred-out" || st_fail "exit-0 + claimless DEFERRED did not emit declined=true"
  grep -qx 'delivered=false' "$tmp/deferred-out" || st_fail "the deferred case did not emit delivered=false"
  grep -qx 'withdrawn=false' "$tmp/deferred-out" || st_fail "the deferred case did not emit withdrawn=false"
  no_posts deferred

  # Row 4's negative control (AC1's other direction): the same claimless
  # fixture WITHOUT the DEFERRED comment stays the all-false no-op — no
  # branch, no PR, no stop marker of any kind — so delivered=false AND
  # declined=false reach the red gate and the job fails. A claimless walk
  # that posted nothing is still a death.
  e2e_fix nodefer comments '[{"body": "🏷️ Triaged: `autonomy-ok` — still blocked on the dependency.", "created_at": "2026-09-18T22:39:00Z"}]'
  e2e_fix nodefer branches '[]'
  e2e_fix nodefer pulls '[]'
  e2e nodefer success
  grep -qx 'declined=false' "$tmp/nodefer-out" || st_fail "a claimless walk with no stop marker wrongly emitted declined=true"
  grep -qx 'delivered=false' "$tmp/nodefer-out" || st_fail "the no-defer control did not emit delivered=false"
  grep -qx 'withdrawn=false' "$tmp/nodefer-out" || st_fail "the no-defer control did not emit withdrawn=false"
  no_posts nodefer

  # Row 4b: the claimed shape — the walk claimed, deferred, and left the
  # lock standing → declined, nothing posted (the lock ages out through the
  # selector's staleness, the DECLINED row's design).
  e2e_fix deferlock comments '[{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-09-01T15:01:00Z"},{"body": "🚢 DEFERRED (re-check) — dependencies still not landed.", "created_at": "2026-09-01T15:02:00Z"}]'
  e2e_fix deferlock branches '[]'
  e2e_fix deferlock pulls '[]'
  e2e deferlock success
  grep -qx 'declined=true' "$tmp/deferlock-out" || st_fail "exit-0 + DEFERRED after the claim did not emit declined=true"
  no_posts deferlock

  # Row 4c: corroboration outranks the defer — a branch exists even though
  # the thread's latest stop is a DEFERRED → delivered, nothing posted (a
  # walk that deferred and then landed anyway is a delivery, not a defer).
  e2e_fix deferbranch comments '[{"body": "🚢 SHIP-LOCK\n\nclaimed", "created_at": "2026-09-01T15:01:00Z"},{"body": "🚢 DEFERRED (re-check) — dependencies still not landed.", "created_at": "2026-09-01T15:02:00Z"}]'
  e2e_fix deferbranch branches '[{"name": "claude/issue-1-the-fix"}]'
  e2e_fix deferbranch pulls '[]'
  e2e deferbranch success
  grep -qx 'delivered=true' "$tmp/deferbranch-out" || st_fail "exit-0 + branch + DEFERRED did not emit delivered=true"
  grep -qx 'declined=false' "$tmp/deferbranch-out" || st_fail "the branch-plus-DEFERRED case wrongly emitted declined=true"
  no_posts deferbranch

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

  echo "ok    selftest: end-to-end dispositions (dead / delivered / declined / self-withdrawn / deferred / escalated)"

  # -- #670: cleanup runs the start commit's script, not the tree's copy -----
  # The scheduled workflows pin the cleanup script to the commit the job
  # started on (git checkout <sha> -- <script>, with a symlink-safe git-show
  # fallback) because the agent's walk may stack its branch on an older
  # feature branch whose pre-#538 copy turns a dead 'success' into a silent
  # no-op (#627). This fixture reproduces that incident end to end: the
  # tree's own old copy no-ops; the same tree after the workflow's restore
  # withdraws.
  #
  # Mirrors the restore inlined in backlog-burn.yml and design-run.yml. A
  # redirect onto the script path is not used: the agent can leave that path
  # as a symlink, and the shell would follow it. The drift guard below pins
  # the same markers in both workflow files.
  restore_lock_cleanup() { # <repo> <sha>
    local repo sha
    repo="$1"
    sha="$2"
    (
      cd "$repo"
      if [ -L scripts ]; then
        echo "refusing to restore lock-cleanup: scripts/ is a symlink" >&2
        exit 1
      fi
      if [ -L scripts/routine-lock-cleanup.sh ]; then
        rm -f scripts/routine-lock-cleanup.sh
      fi
      if ! git checkout "$sha" -- scripts/routine-lock-cleanup.sh; then
        restore_tmp="$(mktemp)"
        if ! git show "$sha:scripts/routine-lock-cleanup.sh" > "$restore_tmp"; then
          rm -f "$restore_tmp"
          exit 1
        fi
        if [ -L scripts/routine-lock-cleanup.sh ]; then
          rm -f scripts/routine-lock-cleanup.sh
        fi
        mv -f "$restore_tmp" scripts/routine-lock-cleanup.sh
      fi
      if [ -L scripts/routine-lock-cleanup.sh ] || [ ! -f scripts/routine-lock-cleanup.sh ]; then
        echo "lock-cleanup restore did not leave a regular file" >&2
        exit 1
      fi
      chmod +x scripts/routine-lock-cleanup.sh
    )
  }
  local repo start_sha wf
  repo="$tmp/stacked"
  mkdir -p "$repo/scripts"
  git -C "$repo" init -q
  git -C "$repo" config user.email selftest@invalid
  git -C "$repo" config user.name selftest
  cp "$SELF" "$repo/scripts/routine-lock-cleanup.sh"
  git -C "$repo" add scripts
  git -C "$repo" commit -qm "start (the default-branch copy)"
  start_sha="$(git -C "$repo" rev-parse HEAD)"
  # The stacked branch's pre-#538 copy: exit-code semantics — 'success' meant
  # delivered, so cleanup printed a notice and no-oped. That is the exact
  # behavior that stranded #627.
  cat > "$repo/scripts/routine-lock-cleanup.sh" <<'DECOY'
#!/usr/bin/env bash
# pre-#538 shape: exit-code semantics — 'success' meant delivered, so cleanup
# no-oped (the exact behavior that stranded #627).
echo "::notice::agent outcome 'success' — no orphaned lock to release on #1"
exit 0
DECOY
  git -C "$repo" commit -qam "stacked branch carries the pre-#538 copy"

  # Control — the tree's own (decoy) copy no-ops: the incident reproduces.
  "$repo/scripts/routine-lock-cleanup.sh" --repo o/r --issue 1 \
    --agent-outcome success --run-url u --routine backlog-burn \
    > "$tmp/stacked-decoy-log" 2>&1 \
    || st_fail "the decoy (pre-#538) copy exited non-zero — the fixture is wrong"
  grep -q "no orphaned lock to release" "$tmp/stacked-decoy-log" \
    || st_fail "the decoy (pre-#538) copy did not print its no-op notice — the fixture is wrong"

  # Dead-success fixtures: an active claim, nothing corroborating or stopping.
  e2e_fix stacked comments '[{"body": "🚢 SHIP-LOCK\n\nclaimed by the run", "created_at": "2026-09-01T15:01:00Z"}]'
  e2e_fix stacked branches '[]'
  e2e_fix stacked pulls '[]'

  # The workflow's restore, then the restored copy must withdraw.
  restore_lock_cleanup "$repo" "$start_sha" \
    || st_fail "the restore failed on the stacked tree"
  cmp -s "$repo/scripts/routine-lock-cleanup.sh" "$SELF" \
    || st_fail "the restore did not recover the start commit's copy of the script"
  : > "$tmp/stacked-postlog"; : > "$tmp/stacked-out"; : > "$tmp/stacked-log"
  PATH="$tmp/bin:$PATH" GH_TOKEN=stub GH_STUB_FIXTURES="$tmp/stacked-fix" \
    GH_STUB_POSTLOG="$tmp/stacked-postlog" GITHUB_OUTPUT="$tmp/stacked-out" \
    GITHUB_STEP_SUMMARY='' "$repo/scripts/routine-lock-cleanup.sh" \
    --repo o/r --issue 1 --agent-outcome success --run-url u --routine backlog-burn \
    > "$tmp/stacked-log" 2>&1 \
    || st_fail "the restored copy exited non-zero on the dead-success case"
  grep -qx 'withdrawn=true' "$tmp/stacked-out" \
    || st_fail "the restored copy did not emit withdrawn=true on a dead success (outcome 'success', no branch/PR/decline)"
  grep -q -- '--method POST /repos/o/r/issues/1/comments' "$tmp/stacked-postlog" \
    || st_fail "the restored copy did not post the withdrawal comment"
  grep -qF -- "$DEATH_PREFIX" "$tmp/stacked-postlog" \
    || st_fail "the restored copy's withdrawal did not carry the death-withdrawal first line"
  if grep -q "no orphaned lock to release" "$tmp/stacked-log" "$tmp/stacked-out"; then
    st_fail "the pre-#538 no-op notice appeared under the restored copy — the tree's stacked script ran anyway"
  fi
  echo "ok    selftest: #670 — a stacked tree's pre-#538 copy no-ops, the restored start-commit copy withdraws"

  # The agent can leave the script path as a symlink. A redirect onto that
  # path follows the link (negative control, below). The locked index is the
  # documented reason checkout fails and the git-show fallback runs — that
  # fallback must not clobber the link target, and must leave a regular file.
  victim="$tmp/outside-victim"
  printf 'do-not-clobber\n' > "$tmp/victim-safe"
  cp "$tmp/victim-safe" "$victim"
  rm -f "$repo/scripts/routine-lock-cleanup.sh"
  ln -s "$victim" "$repo/scripts/routine-lock-cleanup.sh"
  git -C "$repo" show "$start_sha:scripts/routine-lock-cleanup.sh" \
    > "$repo/scripts/routine-lock-cleanup.sh"
  if cmp -s "$victim" "$tmp/victim-safe"; then
    st_fail "the unsafe redirect did not follow the symlink — the negative control is wrong"
  fi
  cp "$tmp/victim-safe" "$victim"
  rm -f "$repo/scripts/routine-lock-cleanup.sh"
  ln -s "$victim" "$repo/scripts/routine-lock-cleanup.sh"
  : > "$repo/.git/index.lock"
  restore_lock_cleanup "$repo" "$start_sha" \
    >"$tmp/symlink-restore-out" 2>"$tmp/symlink-restore-err" \
    || st_fail "symlink-safe restore failed when the index was locked"
  grep -q 'index.lock' "$tmp/symlink-restore-err" \
    || st_fail "locked-index fixture did not make checkout fail — the git-show fallback was not exercised"
  rm -f "$repo/.git/index.lock"
  [ ! -L "$repo/scripts/routine-lock-cleanup.sh" ] \
    || st_fail "restore left scripts/routine-lock-cleanup.sh as a symlink"
  [ -f "$repo/scripts/routine-lock-cleanup.sh" ] \
    || st_fail "restore did not leave a regular file at scripts/routine-lock-cleanup.sh"
  cmp -s "$repo/scripts/routine-lock-cleanup.sh" "$SELF" \
    || st_fail "symlink-safe fallback did not recover the start commit's copy"
  cmp -s "$victim" "$tmp/victim-safe" \
    || st_fail "symlink-safe fallback wrote through the symlink and clobbered its target"
  # Checkout path too: a symlink with an unlocked index is unlinked before
  # checkout, not followed.
  printf 'do-not-clobber\n' > "$victim"
  rm -f "$repo/scripts/routine-lock-cleanup.sh"
  ln -s "$victim" "$repo/scripts/routine-lock-cleanup.sh"
  restore_lock_cleanup "$repo" "$start_sha" \
    || st_fail "symlink-safe restore failed on the checkout path"
  [ ! -L "$repo/scripts/routine-lock-cleanup.sh" ] \
    || st_fail "checkout-path restore left scripts/routine-lock-cleanup.sh as a symlink"
  cmp -s "$victim" "$tmp/victim-safe" \
    || st_fail "checkout-path restore wrote through the symlink"
  # A symlink at scripts/ itself must fail closed without writing outside.
  outside_dir="$tmp/outside-scripts"
  mkdir -p "$outside_dir"
  printf 'outside-script\n' > "$outside_dir/routine-lock-cleanup.sh"
  cp "$outside_dir/routine-lock-cleanup.sh" "$tmp/outside-script-safe"
  rm -rf "$repo/scripts"
  ln -s "$outside_dir" "$repo/scripts"
  if restore_lock_cleanup "$repo" "$start_sha" \
      >"$tmp/scripts-link-out" 2>"$tmp/scripts-link-err"; then
    st_fail "restore followed a symlink at scripts/ instead of refusing"
  fi
  grep -q 'scripts/ is a symlink' "$tmp/scripts-link-err" \
    || st_fail "a symlinked scripts/ was refused without the refusal message"
  cmp -s "$outside_dir/routine-lock-cleanup.sh" "$tmp/outside-script-safe" \
    || st_fail "refusing a symlinked scripts/ still modified the outside tree"
  echo "ok    selftest: #670 — restore does not follow a symlink the agent left behind"

  # -- #670 drift guard: both workflows restore before they run -------------
  # A workflow whose cleanup step runs the tree's copy would regress #670
  # silently, so pin the mechanism: the lock-cleanup step must restore the
  # script from the job's start commit (START_SHA, bound to
  # steps.start_ref.outputs.sha) BEFORE invoking it, the start_ref capture
  # must precede every agent step (else the walk moves HEAD first), and the
  # restore must unlink a symlink at the script path before checkout and
  # install the git-show fallback with mv rather than a redirect onto the
  # path (that redirect follows a symlink).
  restore_in_block() {  # step-block text on stdin → 0 when the restore pins the script
    local block restore_ln invoke_ln unlink_ln
    block="$(cat)"
    restore_ln="$(printf '%s\n' "$block" \
      | grep -n 'git checkout "\$START_SHA" -- scripts/routine-lock-cleanup.sh' \
      | head -1 | cut -d: -f1)"
    invoke_ln="$(printf '%s\n' "$block" \
      | grep -n '\./scripts/routine-lock-cleanup.sh --repo' \
      | head -1 | cut -d: -f1)"
    unlink_ln="$(printf '%s\n' "$block" \
      | grep -n '\[ -L scripts/routine-lock-cleanup.sh \]' \
      | head -1 | cut -d: -f1)"
    [ -n "$restore_ln" ] && [ -n "$invoke_ln" ] && [ -n "$unlink_ln" ] \
      && [ "$unlink_ln" -lt "$restore_ln" ] && [ "$restore_ln" -lt "$invoke_ln" ] \
      && printf '%s\n' "$block" \
        | grep -q 'START_SHA: \${{ steps\.start_ref\.outputs\.sha }}' \
      && printf '%s\n' "$block" \
        | grep -q '\[ -L scripts \]' \
      && printf '%s\n' "$block" \
        | grep -q 'mv -f "\$restore_tmp" scripts/routine-lock-cleanup.sh' \
      && ! printf '%s\n' "$block" \
        | grep -q '> scripts/routine-lock-cleanup.sh'
  }
  capture_precedes_agent() {  # workflow file → 0 when start_sha is captured before the first agent step
    local cap_ln agent_ln
    cap_ln="$(grep -n 'id: start_ref' "$1" | head -1 | cut -d: -f1)"
    agent_ln="$(grep -n 'uses: anthropics/claude-code-action' "$1" | head -1 | cut -d: -f1)"
    [ -n "$cap_ln" ] && [ -n "$agent_ln" ] && [ "$cap_ln" -lt "$agent_ln" ] \
      && grep -q 'git rev-parse HEAD' "$1"
  }
  for wf in .github/workflows/backlog-burn.yml .github/workflows/design-run.yml; do
    [ -f "$wf" ] || st_fail "drift: $wf is missing — the cleanup workflows moved"
    sed -n "/Withdraw a dead run's SHIP-LOCK/,/^      - name:/p" "$wf" | sed '$d' \
      | restore_in_block \
      || st_fail "drift: $wf's lock-cleanup step does not restore scripts/routine-lock-cleanup.sh from \$START_SHA before running it (#670)"
    capture_precedes_agent "$wf" \
      || st_fail "drift: $wf does not capture the start commit (id: start_ref, git rev-parse HEAD) before its first agent step (#670)"
  done
  # Negative controls — each guard must fire on the pre-#670 shape: the step
  # exactly as it was (run the tree's copy, no restore, no START_SHA), and a
  # workflow with no capture step at all.
  cat > "$tmp/old-step.yml" <<'OLDSTEP'
      - name: Withdraw a dead run's SHIP-LOCK
        id: lock_cleanup
        run: |
          ./scripts/routine-lock-cleanup.sh --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" \
            --agent-outcome "$AGENT_OUTCOME" --run-url "$RUN_URL" --routine backlog-burn
OLDSTEP
  if sed -n "/Withdraw a dead run's SHIP-LOCK/,/^      - name:/p" "$tmp/old-step.yml" \
      | sed '$d' | restore_in_block; then
    st_fail "drift: the restore guard accepted the pre-#670 step shape — it can never fire"
  fi
  if capture_precedes_agent "$tmp/old-step.yml"; then
    st_fail "drift: the start_ref guard accepted a workflow with no capture step — it can never fire"
  fi
  # The pre-symlink-fix shape: checkout plus a redirect onto the script path.
  # That redirect follows a symlink the agent left behind, so the guard must
  # reject it even though the restore still precedes the invocation.
  cat > "$tmp/unsafe-restore.yml" <<'UNSAFE'
      - name: Withdraw a dead run's SHIP-LOCK
        id: lock_cleanup
        env:
          START_SHA: ${{ steps.start_ref.outputs.sha }}
        run: |
          git checkout "$START_SHA" -- scripts/routine-lock-cleanup.sh \
            || git show "$START_SHA":scripts/routine-lock-cleanup.sh \
                 > scripts/routine-lock-cleanup.sh
          chmod +x scripts/routine-lock-cleanup.sh
          ./scripts/routine-lock-cleanup.sh --repo "$GITHUB_REPOSITORY" --issue "$ISSUE" \
            --agent-outcome "$AGENT_OUTCOME" --run-url "$RUN_URL" --routine backlog-burn
UNSAFE
  if sed -n "/Withdraw a dead run's SHIP-LOCK/,/^      - name:/p" "$tmp/unsafe-restore.yml" \
      | sed '$d' | restore_in_block; then
    st_fail "drift: the restore guard accepted a redirect onto the script path — the symlink hole can never fire"
  fi
  echo "ok    selftest: workflow drift guard (restore-before-run in both ship workflows + capture before the agent)"

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
