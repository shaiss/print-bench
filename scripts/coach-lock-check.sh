#!/usr/bin/env bash
# Coach-lock presence check (issue #806).
#
# claude-code-action exits 0 on a denial-only turn (#538 / #764 / #806), so
# a Design-coach job "success" does not mean a COACH-LOCK landed. This
# script is the pin: after a ship step that claimed success, the PR thread
# must carry the marker the posting tool assembles (`<!-- COACH_LOCK -->`)
# or the human kickoff line (`🎓 COACH-LOCK`). No marker → fail, and the
# workflow must not stamp the round complete.
#
# Live: ./scripts/coach-lock-check.sh <pr-number>
# Offline: ./scripts/coach-lock-check.sh --selftest
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MARKER_HTML='<!-- COACH_LOCK'
MARKER_LINE='🎓 COACH-LOCK'

comments_carry_lock() {
  python3 -c '
import json, sys
raw = sys.stdin.read().strip()
if not raw:
    raise SystemExit(1)
data = json.loads(raw)
if not isinstance(data, list):
    data = [data]
html = "<!-- COACH_LOCK"
line = "🎓 COACH-LOCK"
for c in data:
    body = c.get("body") or ""
    if html in body or line in body:
        raise SystemExit(0)
raise SystemExit(1)
'
}

selftest() {
  local n=0 bad=0
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  expect() {
    local name="$1" json="$2" want="$3"
    n=$((n + 1))
    local rc=0
    comments_carry_lock <<<"$json" && rc=0 || rc=$?
    if [[ "$want" == pass && "$rc" -eq 0 ]]; then
      echo "ok    $name"
    elif [[ "$want" == fail && "$rc" -ne 0 ]]; then
      echo "ok    $name"
    else
      echo "FAIL  $name (want $want, exit $rc)"
      bad=1
    fi
  }

  expect "a COACH-LOCK emoji kickoff passes" \
    '[{"body":"🎓 COACH-LOCK\n\nkickoff"}]' pass
  expect "the HTML marker the posting tool assembles passes" \
    '[{"body":"round 1\n\n<!-- COACH_LOCK -->\n\nfooter"}]' pass
  expect "Jane/Drik comments without a coach marker fail" \
    '[{"body":"<!-- JANE_SIGNOFF sha=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa verdict=pass fuse=none -->"}]' fail
  expect "an empty thread fails" '[]' fail
  expect "unrelated comments fail" '[{"body":"lgtm"}]' fail

  echo "      selftest: $n cases"
  return "$bad"
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    coach-lock-check selftest passed"
  exit 0
fi

pr="${1:-}"
if ! [[ "$pr" =~ ^[1-9][0-9]*$ ]]; then
  echo "usage: $0 <pr-number> | --selftest" >&2
  exit 2
fi

repo="${GITHUB_REPOSITORY:-}"
if [[ -z "$repo" ]]; then
  echo "FAIL  coach-lock-check: GITHUB_REPOSITORY is not set" >&2
  exit 2
fi

json="$(gh api --paginate "repos/${repo}/issues/${pr}/comments")"
if comments_carry_lock <<<"$json"; then
  echo "ok    PR #${pr} carries a COACH-LOCK"
  exit 0
fi

echo "FAIL  PR #${pr} has no COACH-LOCK (no <!-- COACH_LOCK --> / no 🎓 COACH-LOCK) — a denial-only coach turn is not a completed round (issue #806)" >&2
exit 1
