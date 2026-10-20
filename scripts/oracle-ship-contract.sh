#!/usr/bin/env bash
# Pick the frozen §2 acceptance contract from an issue's comments for the
# Oracle reviewer context (Cipher / Bugbot MED on #864).
#
# Settle's authentic lock is a constant stub ("🚢 SHIP-LOCK — settle claim"
# + HTML marker) — NOT the contract. The real contract is either:
#   - an attended claim that embeds Gate contract / Acceptance criteria in
#     the same SHIP-LOCK body, or
#   - a later intent comment carrying those section headings (unattended).
# This script selects the latest comment whose body looks like a contract
# and is not the settle stub alone.
#
# Usage:
#   scripts/oracle-ship-contract.sh <comments.json>
#   scripts/oracle-ship-contract.sh --selftest
# stdin or file: JSON array of {body, user:{login}, created_at} (gh api shape).
# stdout: the contract comment body, or empty when none found.
set -euo pipefail

SETTLE_STUB='🚢 SHIP-LOCK — settle claim'
LOCK_HTML='<!-- design-run-ship-lock:v1 -->'

select_contract() {  # file or -
  jq -r --arg stub "$SETTLE_STUB" '
    def fl($b): ($b // "") | split("\n")
      | map(gsub("^[[:space:]]+|[[:space:]]+$"; ""))
      | map(select(length > 0)) | (.[0] // "");
    def looks_like_contract:
      (.body // "")
      | test("\\*\\*Gate contract\\*\\*|\\*\\*Acceptance criteria\\*\\*|\\*\\*Design name:\\*\\*|\\*\\*Chosen approach:\\*\\*");
    # Settle stub is the constant claim body with no contract sections.
    def is_settle_stub:
      ((.body // "") | contains($stub)) and (looks_like_contract | not);
    [ .[]
      | select(is_settle_stub | not)
      | select(fl(.body) | test("^🚢 SHIP-LOCK WITHDRAWN") | not)
      | select(looks_like_contract) ]
    | sort_by(.created_at // "")
    | last
    | if . == null then "" else (.body // "") end
  ' "$1"
}

selftest() {
  local tmp rc
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # Settle stub alone → no contract
  jq -n --arg stub "$SETTLE_STUB" --arg html "$LOCK_HTML" \
    '[{body:($stub + "\n\n" + $html + "\n"), created_at:"2026-10-20T00:00:00Z",
       user:{login:"github-actions[bot]",type:"Bot"}}]' > "$tmp/stub.json"
  [ -z "$(select_contract "$tmp/stub.json")" ] || {
    echo "selftest: settle stub was treated as the contract" >&2
    return 1
  }

  # Settle stub + later contract comment → contract body
  jq -n --arg stub "$SETTLE_STUB" --arg html "$LOCK_HTML" \
    '[{body:($stub + "\n\n" + $html + "\n"), created_at:"2026-10-20T00:00:00Z",
       user:{login:"github-actions[bot]",type:"Bot"}},
      {body:"**Design name:** nuggs-ladder\n\n**Gate contract** (done = every box)\n- [ ] G1\n",
       created_at:"2026-10-20T00:01:00Z",
       user:{login:"github-actions[bot]",type:"Bot"}}]' > "$tmp/pair.json"
  out="$(select_contract "$tmp/pair.json")"
  printf '%s' "$out" | grep -q 'Gate contract' || {
    echo "selftest: did not pick the later Gate contract comment" >&2
    return 1
  }
  printf '%s' "$out" | grep -qF -- "$SETTLE_STUB" && {
    echo "selftest: settle stub leaked into the selected contract" >&2
    return 1
  }

  # Attended claim embeds the contract in the lock body → that body wins
  jq -n --arg html "$LOCK_HTML" \
    '[{body:("🚢 SHIP-LOCK — running this design to a gated draft PR.\n\n"
             + $html + "\n\n**Design name:** widget\n\n**Gate contract**\n- [ ] G1\n"),
       created_at:"2026-10-20T00:00:00Z",
       user:{login:"shaiss",type:"User"}}]' > "$tmp/attended.json"
  out="$(select_contract "$tmp/attended.json")"
  printf '%s' "$out" | grep -qF '**Design name:** widget' || {
    echo "selftest: attended embedded contract was not selected" >&2
    printf 'got: %s\n' "$out" >&2
    return 1
  }

  # WITHDRAWN lock with contract text in an old body is ignored when withdrawn
  # is the only match? A withdrawn comment that still has Gate contract —
  # we filter WITHDRAWN first lines, so it should not win over a later real one.
  jq -n --arg html "$LOCK_HTML" \
    '[{body:("🚢 SHIP-LOCK WITHDRAWN — yielding\n\n" + $html + "\n\n**Gate contract**\nold\n"),
       created_at:"2026-10-20T00:00:00Z",
       user:{login:"github-actions[bot]",type:"Bot"}},
      {body:"**Chosen approach:** the one option\n\n**Acceptance criteria**\n- [ ] AC1\n",
       created_at:"2026-10-20T00:02:00Z",
       user:{login:"shaiss",type:"User"}}]' > "$tmp/wd.json"
  out="$(select_contract "$tmp/wd.json")"
  printf '%s' "$out" | grep -q 'Acceptance criteria' || {
    echo "selftest: Acceptance criteria comment was not selected after WITHDRAWN" >&2
    return 1
  }

  echo "ok    oracle-ship-contract selftest passed"
  return 0
}

if [ "${1:-}" = "--selftest" ]; then
  selftest
  exit $?
fi

if [ $# -eq 0 ] || [ "$1" = "-" ]; then
  select_contract /dev/stdin
else
  select_contract "$1"
fi
