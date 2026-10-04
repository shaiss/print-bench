#!/usr/bin/env bash
# Coach-lock presence check (issue #806).
#
# claude-code-action exits 0 on a denial-only turn (#538 / #764 / #806), so
# a Design-coach job "success" does not mean a COACH-LOCK landed. This
# script is the pin: after a ship step that claimed success, the PR thread
# must carry a comment from the Actions bot whose body contains the exact
# marker the posting tool assembles (`<!-- COACH_LOCK -->`). A substring
# planted by any other author — or the human-visible `🎓 COACH-LOCK` line
# alone — does not count, so a drive-by comment cannot satisfy the check
# and let review-stamp advance.
#
# Live: ./scripts/coach-lock-check.sh <pr-number>
# Offline: ./scripts/coach-lock-check.sh --selftest
set -euo pipefail

# A prior Bash-capable coach step can write PYTHONPATH/LD_PRELOAD via
# GITHUB_ENV. Isolated mode ignores those; also drop them in this shell
# so `gh` is not preloaded either.
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE \
      PYTHONEXECUTABLE LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT \
      DYLD_INSERT_LIBRARIES BASH_ENV ENV || true
export PYTHONNOUSERSITE=1

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Exact server-assembled marker (not the `<!-- COACH_LOCK` prefix, which
# would also match a forged `<!-- COACH_LOCK_FAKE -->`).
MARKER_HTML='<!-- COACH_LOCK -->'
export MARKER_HTML

# Prefer the system interpreter; -I ignores PYTHONPATH/PYTHONHOME/user site.
if [[ -x /usr/bin/python3 ]]; then
  PYTHON3=/usr/bin/python3
else
  PYTHON3=python3
fi

comments_carry_lock() {
  "$PYTHON3" -I -c '
import json, os, sys

MARKER = os.environ["MARKER_HTML"]
BOT = "github-actions"


def is_actions_bot(comment):
    """REST login is github-actions[bot]; GraphQL is github-actions."""
    user = comment.get("user") or {}
    login = (user.get("login") or "").strip().lower()
    if login.endswith("[bot]"):
        login = login[:-5]
    return login == BOT


raw = sys.stdin.read().strip()
if not raw:
    raise SystemExit(1)
data = json.loads(raw)
if not isinstance(data, list):
    data = [data]
for c in data:
    body = c.get("body") or ""
    if MARKER in body and is_actions_bot(c):
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

  expect "Actions bot + the exact HTML marker passes" \
    '[{"body":"round 1\n\n<!-- COACH_LOCK -->\n\nfooter","user":{"login":"github-actions[bot]","type":"Bot"}}]' pass
  expect "GraphQL github-actions login + HTML marker passes" \
    '[{"body":"<!-- COACH_LOCK -->","user":{"login":"github-actions"}}]' pass
  expect "Actions bot + HTML marker and emoji kickoff passes" \
    '[{"body":"🎓 COACH-LOCK\n\nkickoff\n\n<!-- COACH_LOCK -->","user":{"login":"github-actions[bot]"}}]' pass
  expect "a human comment carrying the HTML marker fails" \
    '[{"body":"<!-- COACH_LOCK -->","user":{"login":"attacker"}}]' fail
  expect "cursor[bot] carrying the HTML marker fails" \
    '[{"body":"<!-- COACH_LOCK -->","user":{"login":"cursor[bot]","type":"Bot"}}]' fail
  expect "Actions bot + only the emoji kickoff fails" \
    '[{"body":"🎓 COACH-LOCK\n\nkickoff","user":{"login":"github-actions[bot]"}}]' fail
  expect "a human emoji kickoff fails" \
    '[{"body":"🎓 COACH-LOCK\n\nkickoff","user":{"login":"attacker"}}]' fail
  expect "Actions bot + truncated HTML prefix fails" \
    '[{"body":"<!-- COACH_LOCK","user":{"login":"github-actions[bot]"}}]' fail
  expect "Jane/Drik comments without a coach marker fail" \
    '[{"body":"<!-- JANE_SIGNOFF sha=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa verdict=pass fuse=none -->","user":{"login":"github-actions[bot]"}}]' fail
  expect "an empty thread fails" '[]' fail
  expect "unrelated comments fail" \
    '[{"body":"lgtm","user":{"login":"github-actions[bot]"}}]' fail
  expect "a marker with no author fails" \
    '[{"body":"<!-- COACH_LOCK -->"}]' fail

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
  echo "ok    PR #${pr} carries a trusted COACH-LOCK"
  exit 0
fi

echo "FAIL  PR #${pr} has no Actions-bot comment carrying <!-- COACH_LOCK --> — a denial-only coach turn (or a planted substring) is not a completed round (issue #806)" >&2
exit 1
