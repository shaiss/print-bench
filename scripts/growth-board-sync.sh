#!/usr/bin/env bash
# growth-board-sync.sh — reflect the growth queue onto the approval board.
#
# The driver half of .github/workflows/growth-board-sync.yml (docs/growth.md):
# the workflow is the trigger and the token holder, this script does the
# reconcile. Moved out of inline workflow YAML (issue #748) so the one behavior
# that matters — a GraphQL rate limit mid-run must DEGRADE, not hard-fail — is
# provable by `--selftest` with a stub `gh` on PATH, which inline YAML cannot
# be. The workflow's scheduled reconciles hard-failed on every fire from
# 2026-09-29 because the then-inline loop re-SET every item's Stage on every
# run (~6 Projects GraphQL calls per item across an 80+ card board), exhausting
# the 5,000/hr budget that ONE Projects-scoped PAT (PROJECT_TOKEN) shares with
# the roadmap board.
#
# The reconcile, in four steps:
#   1. gather — every growth-queue issue (open + closed) plus its concatenated
#        comment bodies, via the ambient GH_TOKEN (REST). A per-issue comment
#        fetch failure skips that issue this run: empty comments would read as
#        "no markers" and drop a Posted/Drafted card back to Queued, so its
#        card keeps the stage a prior run set and self-heals next reconcile.
#   2. derive — `python3 -m growth board-stage` (tools/growth), the committed
#        Stage policy and single source: one url<TAB>stage line per item that
#        belongs on the board.
#   3. read  — the board's current url<TAB>stage state via gh-project.sh's
#        `list-stages` recipe under PROJECT_TOKEN: ONE paginated read for the
#        whole board.
#   4. apply — for each derived stage that DIFFERS from the board's, the
#        idempotent `add-item --stage` recipe re-sets it. The lens semantics
#        are unchanged (the derived truth always wins — a human-dragged Stage
#        that differs IS corrected); only provably-identical writes are
#        skipped.
#
# THE BOARD IS THE CHECKPOINT (issue #748's cursor, statelessly): a run that
# stopped early resumes where it stopped, because already-synced items no
# longer differ — the next run spends its GraphQL budget on the remainder
# instead of re-writing the same head forever. And a steady-state run (nothing
# in the queue changed) costs one read and ZERO writes.
#
# RATE-LIMIT POLICY (issue #748's backoff): a rate-limited write is retried
# GROWTH_SYNC_RETRIES times with a GROWTH_SYNC_BACKOFF_SECS sleep between
# attempts (short on purpose — the job timeout is 10 min and the budget resets
# hourly, so a long wait is futile); still limited → stop the loop, surface a
# ::warning:: naming what was skipped, exit 0. The queue itself is unchanged
# and the next reconcile (an issues event, or the 3-hourly schedule) self-heals
# — the same skip branch the comment fetch already takes. Any OTHER failure
# (bad token, board missing, invalid stage) still exits non-zero: contention
# is expected, breakage must stay red.
#
# Environment:
#   REPO                      owner/name — required in sync mode
#   GH_TOKEN                  the ambient token for queue reads
#   PROJECT_TOKEN             the Projects-scoped PAT for board read + writes
#   GROWTH_SYNC_RETRIES       write retries on a rate limit (default 2)
#   GROWTH_SYNC_BACKOFF_SECS  seconds between retries (default 20)
#
# Usage:
#   scripts/growth-board-sync.sh             # full reconcile (the workflow's call)
#   scripts/growth-board-sync.sh --selftest  # stub-gh failure injection (check.sh)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOARD="growth"
GROWTH_SYNC_RETRIES="${GROWTH_SYNC_RETRIES:-2}"
GROWTH_SYNC_BACKOFF_SECS="${GROWTH_SYNC_BACKOFF_SECS:-20}"

# True when a failed gh call's output is a rate limit (REST secondary limits
# and GraphQL both spell it "rate limit" somewhere in the message).
is_rate_limit() {  # $1 = captured output of the failed call
  grep -qi 'rate limit' <<<"$1"
}

# The graceful stop: surface the miss, stay green, let the next reconcile
# finish. Degradation is a skip, never a silent no-op — the ::warning:: is what
# a scanning human sees when the board is running behind.
degrade() {  # $1 = what we were doing when the limit hit
  echo "::warning::growth-board-sync: rate-limited while $1; skipping the rest this run — the board self-heals on the next reconcile"
  exit 0
}

# Step 1 — the queue snapshot. Verbatim move of the workflow's old inline
# gather (only new: the initial issue-list failure is classified too, so a
# rate-limited READ degrades the same way a rate-limited write does).
gather_snapshot() {
  # Working set: every growth-queue issue, most-recently-updated first (so a
  # just-closed Posted item is always in the window; old settled cards already
  # sit on the board and never change). `--state all` is REQUIRED: gh keeps its
  # default `--state open` filter even alongside `--search`, so without it
  # every closed growth-queue issue — i.e. every Posted item — is silently
  # omitted and never reaches the board. The stage policy still drops
  # closed-and-never-posted items, so rejected issues don't clutter it.
  local err
  if ! err="$(gh issue list --repo "$REPO" --state all \
        --search 'label:growth-queue sort:updated-desc' --limit 300 \
        --json number,url,state,labels 2>&1 > set.json)"; then
    if is_rate_limit "$err"; then
      degrade "listing the growth queue"
    fi
    echo "growth-board-sync: gh issue list failed (not a rate limit):" >&2
    printf '%s\n' "$err" >&2
    exit 1
  fi

  # Enrich each with its concatenated comment bodies, so the stage policy can
  # read the dry-run / posted markers. growth.board owns the marker strings;
  # this script passes raw comment text and hardcodes no marker itself.
  : > snapshot.ndjson
  local n bodies
  while read -r n; do
    [ -n "$n" ] || continue
    # A FAILED comment fetch must not misclassify the issue: empty comments
    # would read as "no markers" and drop a Posted/Drafted card back to
    # Queued. So on a fetch error skip this issue for this run — its card
    # keeps the stage a prior run set, and self-heals on the next reconcile —
    # and surface the miss. An issue with genuinely no comments succeeds with
    # an empty string, which is the correct Queued input; only a real API
    # failure takes the skip branch.
    if ! bodies="$(gh api "repos/$REPO/issues/$n/comments" --paginate \
        --jq '[.[].body] | join("\n")' 2>/dev/null)"; then
      echo "::warning::growth-board-sync: could not read comments for #${n}; leaving its board card unchanged this run"
      continue
    fi
    jq -c --argjson n "$n" --arg comments "$bodies" \
      '.[] | select(.number==$n)
           | {number, url, state, labels: [.labels[].name], comments: $comments}' \
      set.json >> snapshot.ndjson
  done < <(jq -r '.[].number' set.json)
  jq -s '.' snapshot.ndjson > snapshot.json
}

# Step 2 — derive every item's Stage from the committed policy.
derive_stages() {
  PYTHONPATH="$ROOT/tools/growth/src" python3 -m growth board-stage \
    --snapshot snapshot.json
}

# Step 3 — the board's current state, one read. The recipe needs PROJECT_TOKEN
# (Projects v2 is invisible to the ambient token), so it re-execs bash with
# GH_TOKEN overridden for that one invocation.
read_board() {
  "$ROOT/scripts/gh-project.sh" --board "$BOARD" list-stages \
    | GH_TOKEN="${PROJECT_TOKEN:?PROJECT_TOKEN must be set}" bash
}

# Write one item's stage via the idempotent add-item recipe, backing off a
# rate-limited attempt. Exit codes: 0 = written; 1 = still rate-limited after
# every retry (the caller degrades); 2 = a non-rate-limit failure (the caller
# goes red — this is the boundary where contention and breakage part ways).
write_one() {  # $1 = issue url, $2 = stage
  local url="$1" stage="$2" attempt=1 err
  while :; do
    if err="$("$ROOT/scripts/gh-project.sh" --board "$BOARD" add-item "$url" --stage "$stage" \
          | GH_TOKEN="$PROJECT_TOKEN" bash 2>&1)"; then
      return 0
    fi
    if ! is_rate_limit "$err"; then
      echo "growth-board-sync: board write failed for $url (not a rate limit):" >&2
      printf '%s\n' "$err" >&2
      return 2
    fi
    if [ "$attempt" -gt "$GROWTH_SYNC_RETRIES" ]; then
      echo "growth-board-sync: still rate-limited writing $url after ${GROWTH_SYNC_RETRIES} backoff(s)" >&2
      return 1
    fi
    echo "growth-board-sync: rate-limited writing $url; backing off ${GROWTH_SYNC_BACKOFF_SECS}s (attempt ${attempt} of ${GROWTH_SYNC_RETRIES})" >&2
    sleep "$GROWTH_SYNC_BACKOFF_SECS"
    attempt=$((attempt + 1))
  done
}

# Step 4 — write only what differs.
apply_stages() {  # $1 = derived stages.tsv, $2 = board.tsv
  local stages="$1" board="$2"
  local tab; tab="$(printf '\t')"
  local total written=0 pos=0 url stage
  total="$(grep -c . "$stages" || true)"
  while IFS="$tab" read -r url stage; do
    [ -n "$url" ] || continue
    pos=$((pos + 1))
    # The checkpoint: the board already shows exactly this stage — a prior run
    # synced it (or it never changed) — so spend no GraphQL budget on it. An
    # exact whole-line match, never a substring: -x anchors both ends.
    if grep -qFx -- "${url}${tab}${stage}" "$board"; then
      continue
    fi
    if write_one "$url" "$stage"; then
      written=$((written + 1))
    else
      rc=$?
      if [ "$rc" -ne 1 ]; then
        exit 1  # not contention — breakage. Stay red.
      fi
      degrade "writing the board (${url} and ${pos} of ${total} derived items onward are skipped this run)"
    fi
  done < "$stages"
  echo "::notice::growth-board sync: ${written} of ${total} derived item(s) written; the rest were already current."
}

main_sync() {
  : "${REPO:?REPO (owner/name) must be set}"
  : "${PROJECT_TOKEN:?PROJECT_TOKEN must be set}"
  local board_out
  # A named global, not a local: the EXIT trap fires after this frame has
  # returned, when a `local` would be popped and (under `set -u`) the trap
  # would resolve the name up the dynamic chain into an unrelated caller's
  # variable — the selftest learned this the hard way.
  GROWTH_SYNC_WORK="$(mktemp -d)"
  trap 'rm -rf "$GROWTH_SYNC_WORK"' EXIT
  (
    cd "$GROWTH_SYNC_WORK"
    gather_snapshot
    derive_stages > stages.tsv
    # The board read is the one step that can be rate-limited before any write
    # happens. Degraded → this run is a no-op (the board keeps its state);
    # anything else (board missing, token bad) is a defect and stays red.
    if ! board_out="$(read_board 2>&1)"; then
      if is_rate_limit "$board_out"; then
        degrade "reading the board's current stages"
      fi
      echo "growth-board-sync: could not read the board (not a rate limit):" >&2
      printf '%s\n' "$board_out" >&2
      exit 1
    fi
    printf '%s\n' "$board_out" > board.tsv
    apply_stages stages.tsv board.tsv
  )
}

# Prove the reconcile's behavior with a stub `gh` on PATH serving fixture
# queue + board state from $STUB_DIR — no network, no real board. Every case
# runs the REAL main_sync (gather → derive → read → apply) end to end; the stub
# is the only fake. Failure injection is file-driven so a case can arm exactly
# one failure mode:
#   state.tsv               the board's live url<TAB>stage rows (mutated by
#                           item-add/item-edit, so a second run sees what the
#                           first wrote — the board state IS the checkpoint)
#   calls.log               every write call, one line each (failed
#                           rate-limited attempts included, as item-edit-fail)
#   fail_queue_rate_limit   the queue listing fails with a rate limit
#   fail_read_rate_limit    board reads fail with a GraphQL rate limit
#   fail_hard               board reads fail with a non-rate-limit error
#   fail_write_rate_limit   file body = one url; writes for it always fail
#                           with a rate limit (persistent contention)
#   fail_write_once         file body = one url; its FIRST write attempt fails
#                           with a rate limit, the retry must succeed
#   fail_write_auth         file body = one url; writes for it fail with HTTP
#                           401 (a non-rate-limit breakage that must stay red)
selftest() {
  local bin stub failures=0 out rc
  # Named global for the same reason main_sync uses GROWTH_SYNC_WORK: the EXIT
  # trap outlives this frame, where a `local` would be popped.
  GROWTH_SYNC_TEST_WORK="$(mktemp -d)"
  bin="$GROWTH_SYNC_TEST_WORK/bin"; stub="$GROWTH_SYNC_TEST_WORK/stub"
  mkdir -p "$bin" "$stub"
  trap 'rm -rf "$GROWTH_SYNC_TEST_WORK"' EXIT

  cat > "$bin/gh" <<STUB
#!/usr/bin/env bash
# Stub gh for growth-board-sync.sh --selftest: serves the queue/board surface
# from \$STUB_DIR fixtures, applies --jq via real jq, records writes, and
# mutates state.tsv so a later run sees what an earlier one wrote.
set -u
DIR="\${STUB_DIR:?STUB_DIR must be set}"

jq_apply() {  # \$1 = json; the rest may carry --jq <expr>
  local json="\$1"; shift
  local expr="" a prev=""
  for a in "\$@"; do
    if [ "\$prev" = "--jq" ]; then expr="\$a"; break; fi
    prev="\$a"
  done
  if [ -n "\$expr" ]; then printf '%s' "\$json" | jq -r "\$expr"
  else printf '%s\n' "\$json"; fi
}
flagval() {  # flagval <flag> <default> <args...> — value after <flag>
  local f="\$1" d="\$2"; shift 2
  local a prev=""
  for a in "\$@"; do
    if [ "\$prev" = "\$f" ]; then printf '%s' "\$a"; return 0; fi
    prev="\$a"
  done
  printf '%s' "\$d"
}
# exit, not return: the stub runs without set -e, so a `return 1` would fall
# through the case to the success path (the failure would fire AND the write
# would land) — exactly the bug that hid T5/T8 until now.
rate_limited() { echo "GraphQL: API rate limit exceeded for user ID 113060." >&2; exit 1; }
state_url() { awk -F'\t' -v row="\$1" 'NR==row {print \$1}' "\$DIR/state.tsv"; }
state_count() { grep -c . "\$DIR/state.tsv" || true; }

cmd="\$1 \$2"
case "\$cmd" in
  'issue list')
    if [ -e "\$DIR/fail_queue_rate_limit" ]; then rate_limited; fi
    jq_apply "\$(cat "\$DIR/issues.json")" "\$@"
    ;;
  'api 'repos*)
    # gh api repos/<o>/<r>/issues/<n>/comments [--paginate] [--jq e]
    n="\$(printf '%s' "\$2" | sed -n 's#.*/issues/\\([0-9]*\\)/comments#\\1#p')"
    jq_apply "\$(cat "\$DIR/comments-\${n}.json")" "\$@"
    ;;
  'project list')
    if [ -e "\$DIR/fail_hard" ]; then
      echo "GraphQL: Could not resolve to a ProjectV2 with the number 3. (user.projectV2)" >&2
      exit 1
    fi
    [ -e "\$DIR/fail_read_rate_limit" ] && rate_limited
    jq_apply '{"projects":[{"number":3,"title":"print-bench growth","id":"PVT_STUB"}]}' "\$@"
    ;;
  'project item-list')
    [ -e "\$DIR/fail_read_rate_limit" ] && rate_limited
    # Serve the board's items from state.tsv; ids are positional so item-edit
    # can map an --id back to its url and update the row.
    printf '{"items":[' > "\$DIR/items.json"
    first=1; n=0
    while IFS=\$'\\t' read -r url stage; do
      [ -n "\$url" ] || continue
      n=\$((n + 1))
      [ \$first -eq 1 ] || printf ',' >> "\$DIR/items.json"
      first=0
      printf '{"content":{"url":"%s"},"id":"PVTI_%d","stage":"%s"}' "\$url" "\$n" "\$stage" >> "\$DIR/items.json"
    done < "\$DIR/state.tsv"
    printf ']}' >> "\$DIR/items.json"
    jq_apply "\$(cat "\$DIR/items.json")" "\$@"
    ;;
  'project field-list')
    jq_apply '{"fields":[{"name":"Stage","id":"STAGE_F","options":[
      {"id":"Queued","name":"Queued"},{"id":"Drafted","name":"Drafted"},
      {"id":"Approved","name":"Approved"},{"id":"Posted","name":"Posted"},
      {"id":"Parked","name":"Parked"},{"id":"Attention","name":"Attention"}]}]}' "\$@"
    ;;
  'project item-add')
    url="\$(flagval --url "" "\$@")"
    printf '%s\\n' "item-add \${url}" >> "\$DIR/calls.log"
    printf '%s\\t\\n' "\$url" >> "\$DIR/state.tsv"
    newid="PVTI_\$(state_count)"
    jq_apply "{\\"id\\":\"\${newid}\\"}" "\$@"
    ;;
  'project item-edit')
    id="\$(flagval --id "" "\$@")"
    opt="\$(flagval --single-select-option-id "" "\$@")"
    row="\${id#PVTI_}"
    url="\$(state_url "\$row")"
    if [ -e "\$DIR/fail_write_rate_limit" ] && grep -qFx "\$url" "\$DIR/fail_write_rate_limit"; then
      printf '%s\\n' "item-edit-fail \${url} \${opt} rate-limit" >> "\$DIR/calls.log"
      rate_limited
    fi
    if [ -e "\$DIR/fail_write_once" ] && grep -qFx "\$url" "\$DIR/fail_write_once"; then
      rm -f "\$DIR/fail_write_once"  # exactly one failure; the retry succeeds
      printf '%s\\n' "item-edit-fail \${url} \${opt} rate-limit" >> "\$DIR/calls.log"
      rate_limited
    fi
    if [ -e "\$DIR/fail_write_auth" ] && grep -qFx "\$url" "\$DIR/fail_write_auth"; then
      printf '%s\\n' "item-edit-fail \${url} \${opt} auth" >> "\$DIR/calls.log"
      echo "gh: HTTP 401: Bad credentials ()" >&2
      exit 1
    fi
    printf '%s\\n' "item-edit \${url} \${opt}" >> "\$DIR/calls.log"
    awk -F'\t' -v OFS='\t' -v row="\$row" -v st="\$opt" 'NR==row {\$2=st} {print}' \
      "\$DIR/state.tsv" > "\$DIR/state.tmp" && mv "\$DIR/state.tmp" "\$DIR/state.tsv"
    ;;
  *)
    echo "stub gh: unhandled command: \$*" >&2
    exit 1
    ;;
esac
STUB
  chmod +x "$bin/gh"
  export PATH="$bin:$PATH"
  export STUB_DIR="$stub"
  export REPO="shaiss/print-bench"
  export GH_TOKEN="stub-ambient"
  export PROJECT_TOKEN="stub-project"
  export GROWTH_SYNC_BACKOFF_SECS=0   # retry instantly; the sleep is not under test
  export GROWTH_SYNC_RETRIES=2

  # Four queue issues covering four different derived stages (the real
  # board-stage policy decides them — the fixtures only supply the inputs):
  #   #10 open, nothing special                -> Queued
  #   #11 open + approved-to-post              -> Approved
  #   #12 closed + a posted marker comment     -> Posted
  #   #13 open + needs-decision                -> Parked
  local U1="https://github.com/shaiss/print-bench/issues/10"
  local U2="https://github.com/shaiss/print-bench/issues/11"
  local U3="https://github.com/shaiss/print-bench/issues/12"
  local U4="https://github.com/shaiss/print-bench/issues/13"
  cat > "$stub/issues.json" <<EOF
[
 {"number":10,"url":"$U1","state":"open","labels":[{"name":"growth-queue"}]},
 {"number":11,"url":"$U2","state":"open","labels":[{"name":"growth-queue"},{"name":"approved-to-post"}]},
 {"number":12,"url":"$U3","state":"closed","labels":[{"name":"growth-queue"}]},
 {"number":13,"url":"$U4","state":"open","labels":[{"name":"growth-queue"},{"name":"needs-decision"}]}
]
EOF
  printf '[]\n' > "$stub/comments-10.json"
  printf '[]\n' > "$stub/comments-11.json"
  printf '[{"body":"shipped\\n<!-- growth-twitter:posted -->"}]\n' > "$stub/comments-12.json"
  printf '[]\n' > "$stub/comments-13.json"
  # The board already reflecting all four derived stages = steady state.
  steady_state() {
    printf '%s\tQueued\n%s\tApproved\n%s\tPosted\n%s\tParked\n' "$U1" "$U2" "$U3" "$U4" > "$stub/state.tsv"
  }
  reset() {  # empty call log + no failure modes armed (a case sets state.tsv
    : > "$stub/calls.log"          # itself, so the board's starting point is
    rm -f "$stub"/fail_* "$stub"/items.json  # always visible in the case)
  }
  run_sync() {  # runs the real reconcile; sets out/rc without tripping set -e
    if out="$( ( main_sync ) 2>&1 )"; then rc=0; else rc=$?; fi
  }
  # Assertion helpers: grep reads stdin, so pass a file with `< file` or a
  # captured run's output with `<<<"$out"`.
  check() {  # check <description> <grep-args...>
    local desc="$1"; shift
    if grep -q "$@"; then
      echo "ok    $desc"
    else
      echo "FAIL  $desc"
      failures=$((failures + 1))
    fi
  }
  check_not() {  # check_not <description> <grep-args...> — the negation
    local desc="$1"; shift
    if grep -q "$@"; then
      echo "FAIL  $desc"
      failures=$((failures + 1))
    else
      echo "ok    $desc"
    fi
  }
  check_rc() {  # check_rc <description> <wanted-rc> — against the last run
    if [ "$rc" -eq "$2" ]; then
      echo "ok    $1"
    else
      echo "FAIL  $1 (rc=$rc, wanted $2)"
      failures=$((failures + 1))
    fi
  }
  check_rc_ne() {  # check_rc_ne <description> — rc must be non-zero (stays red)
    if [ "$rc" -ne 0 ]; then
      echo "ok    $1"
    else
      echo "FAIL  $1 (rc=0, wanted non-zero)"
      failures=$((failures + 1))
    fi
  }
  check_count() {  # check_count <description> <wanted> <grep-args...>
    local desc="$1" wanted="$2"; shift 2
    local got; got="$(grep -c "$@" || true)"
    if [ "$got" -eq "$wanted" ]; then
      echo "ok    $desc"
    else
      echo "FAIL  $desc (got $got, wanted $wanted)"
      failures=$((failures + 1))
    fi
  }

  # T1 — steady state: the board already matches every derived stage, so the
  # reconcile performs ZERO writes (the GraphQL-budget collapse of issue #748
  # is impossible when unchanged items cost nothing).
  reset
  steady_state > "$stub/state.tsv"
  run_sync
  check_rc "T1 steady state exits 0" 0
  check_not "T1 steady state writes nothing" -E 'item-(edit|add)' < "$stub/calls.log"
  check "T1 notice reports zero writes" -qF '0 of 4 derived item(s) written' <<<"$out"

  # T2 — lens correction: a human dragged #10's card to Parked; the derived
  # truth (Queued) must win — "skip unchanged" may never become "never set".
  reset
  printf '%s\tParked\n%s\tApproved\n%s\tPosted\n%s\tParked\n' "$U1" "$U2" "$U3" "$U4" > "$stub/state.tsv"
  run_sync
  check_rc "T2 lens correction exits 0" 0
  check "T2 corrects the dragged card back to Queued" -qF "item-edit $U1 Queued" < "$stub/calls.log"
  check_count "T2 writes exactly one item" 1 -F 'item-edit ' < "$stub/calls.log"
  check "T2 notice reports one write" -qF '1 of 4 derived item(s) written' <<<"$out"

  # T3 — a queue item missing from the board entirely: add + set it.
  reset
  printf '%s\tQueued\n%s\tApproved\n%s\tPosted\n' "$U1" "$U2" "$U3" > "$stub/state.tsv"
  run_sync
  check_rc "T3 new item exits 0" 0
  check "T3 adds the missing card" -qF "item-add $U4" < "$stub/calls.log"
  check "T3 sets the new card's stage" -qF "item-edit $U4 Parked" < "$stub/calls.log"

  # T4 — backoff: the first write attempt is rate-limited, the retry (after
  # GROWTH_SYNC_BACKOFF_SECS) succeeds — the item is still written this run
  # and no degradation warning fires. (#11 is the first DIFFERING item on this
  # board, so the injected failure is armed on it.)
  reset
  printf '%s\n' "$U2" > "$stub/fail_write_once"
  printf '%s\tQueued\n%s\tParked\n%s\tQueued\n%s\tQueued\n' "$U1" "$U2" "$U3" "$U4" > "$stub/state.tsv"
  run_sync
  check_rc "T4 backoff exits 0" 0
  check "T4 the rate-limited attempt is logged" -qF "item-edit-fail $U2 Approved rate-limit" < "$stub/calls.log"
  check "T4 the retry writes the item" -qF "item-edit $U2 Approved" < "$stub/calls.log"
  check "T4 backs off before retrying" -qF 'backing off' <<<"$out"
  check_not "T4 no degradation warning" -qF '::warning::growth-board-sync: rate-limited while writing' <<<"$out"

  # T5 — graceful stop mid-loop: #10 already matches (no write), #11's write is
  # persistently rate-limited, so the run degrades — warning, exit 0, and #12 /
  # #13 are NOT attempted this run. This is the exact shape of the #748
  # failure, now green instead of red.
  reset
  printf '%s\n' "$U2" > "$stub/fail_write_rate_limit"
  printf '%s\tQueued\n%s\tParked\n%s\tQueued\n%s\tQueued\n' "$U1" "$U2" "$U3" "$U4" > "$stub/state.tsv"
  run_sync
  check_rc "T5 rate-limited run stays green (exit 0)" 0
  check "T5 surfaces the skipped remainder" -qF '::warning::growth-board-sync: rate-limited while writing' <<<"$out"
  check_count "T5 tried the write 1 + 2 retries times" 3 -F 'item-edit-fail' < "$stub/calls.log"
  check_not "T5 later items untouched this run" -E "item-edit(-fail)? ($U3|$U4)" < "$stub/calls.log"
  check_not "T5 no successful writes before the stop" -F 'item-edit ' < "$stub/calls.log"

  # T6 — resume (the checkpoint): the board state T5 left (only #10 current).
  # A fresh run with contention gone writes exactly the remainder — #11, #12,
  # #13 — and spends nothing on #10, which no longer differs.
  reset
  printf '%s\tQueued\n%s\tParked\n%s\tQueued\n%s\tQueued\n' "$U1" "$U2" "$U3" "$U4" > "$stub/state.tsv"
  run_sync
  check_rc "T6 resume exits 0" 0
  check_not "T6 already-synced item is not rewritten" -qF "item-edit $U1" < "$stub/calls.log"
  check "T6 writes the remainder (#11)" -qF "item-edit $U2 Approved" < "$stub/calls.log"
  check "T6 writes the remainder (#12)" -qF "item-edit $U3 Posted" < "$stub/calls.log"
  check "T6 writes the remainder (#13)" -qF "item-edit $U4 Parked" < "$stub/calls.log"
  check "T6 notice reports three writes" -qF '3 of 4 derived item(s) written' <<<"$out"

  # T7 — a non-rate-limit failure stays RED: contention degrades, breakage
  # must not. (a) the board read fails hard; (b) a write fails auth.
  reset
  : > "$stub/fail_hard"
  run_sync
  check_rc_ne "T7a hard read failure stays red"
  check "T7a reports the real error" -qF 'Could not resolve to a ProjectV2' <<<"$out"
  check_not "T7a does not claim a rate limit" -qF 'rate-limited while' <<<"$out"
  reset
  printf '%s\n' "$U2" > "$stub/fail_write_auth"
  printf '%s\tQueued\n%s\tParked\n%s\tQueued\n%s\tQueued\n' "$U1" "$U2" "$U3" "$U4" > "$stub/state.tsv"
  run_sync
  check_rc_ne "T7b auth-failed write stays red"
  check "T7b names the failing url" -qF "board write failed for $U2" <<<"$out"
  check "T7b reports the real error" -qF 'HTTP 401' <<<"$out"

  # T8 — the board read itself rate-limited: nothing can be diffed, so the
  # run is a graceful no-op (the board keeps its state; next run heals).
  reset
  steady_state > "$stub/state.tsv"
  : > "$stub/fail_read_rate_limit"
  run_sync
  check_rc "T8 rate-limited board read stays green" 0
  check "T8 surfaces the degraded read" -qF 'rate-limited while reading' <<<"$out"
  check_not "T8 writes nothing without a diff base" -E 'item-(edit|add)' < "$stub/calls.log"

  # T9 — the queue listing itself rate-limited (the REST side): same policy.
  reset
  steady_state > "$stub/state.tsv"
  : > "$stub/fail_queue_rate_limit"
  run_sync
  check_rc "T9 rate-limited queue read stays green" 0
  check "T9 surfaces the degraded listing" -qF 'rate-limited while listing' <<<"$out"

  if [ "$failures" -ne 0 ]; then
    echo "growth-board-sync selftest: ${failures} FAILURE(S)"
    return 1
  fi
  echo "ok    growth-board-sync.sh selftest passed"
}

case "${1:-}" in
  --selftest) selftest ;;
  -h|--help)  grep '^#' "$0" | sed 's/^# \{0,1\}//' ;;
  *)          main_sync ;;
esac
