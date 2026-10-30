#!/usr/bin/env bash
# Post-agent outcome gate + bounded redacted diagnostics for backlog-burn
# (issue #962).
#
# claude-code-action exits 0 with subtype "success" whenever the model ends
# its turn without an API error (#538 / coach-lock #806). For the burn that
# meant a green ship step with HEAD still on main and no decline — settle
# then redded with "neither delivered nor declined". This script is the
# early, clear fail: after the ship walk, HEAD must be on
# claude/issue-<N>-* OR the thread must carry an explicit stop marker the
# settle job already recognizes (🚢 DECLINED / 🚦 DECISION NEEDED /
# 🚢 DEFERRED), and the ship step's result subtype + denial tool names +
# a capped final message are printed with secrets redacted.
#
# Live:
#   ./scripts/backlog-burn-ship-check.sh --issue <N> \
#       [--run-started-at <ISO8601Z>] \
#       [--execution-log <path>] \
#       [--head-ref <name>]   # override git symbolic-ref (tests)
#       [--comments-file <ndjson>]  # offline stop detection
#
# Offline: ./scripts/backlog-burn-ship-check.sh --selftest
set -euo pipefail

unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE \
      PYTHONEXECUTABLE LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT \
      DYLD_INSERT_LIBRARIES BASH_ENV ENV || true
export PYTHONNOUSERSITE=1

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -x /usr/bin/python3 ]]; then
  PYTHON3=/usr/bin/python3
else
  PYTHON3=python3
fi

DECLINE_MARKER_1='🚢 DECLINED'
DECLINE_MARKER_2='🚦 DECISION NEEDED'
DEFER_MARKER='🚢 DEFERRED'
MSG_CAP=1000

usage() {
  echo "usage: $0 --issue <N> [--run-started-at ISO8601Z] [--execution-log path] [--head-ref name] [--comments-file ndjson]" >&2
  echo "       $0 --selftest" >&2
  [[ $# -gt 0 ]] && echo "error: $*" >&2
  exit 2
}

# Env BB_IN or stdin → redacted + length-capped stdout.
diag_redact() {
  BB_CAP="${1:-$MSG_CAP}" "$PYTHON3" -I -c '
import os, re, sys
cap = int(os.environ.get("BB_CAP", "1000"))
text = os.environ.get("BB_IN")
if text is None:
    text = sys.stdin.read()
patterns = [
    (re.compile(r"(?i)\b(gh[pousr]_|github_pat_|xox[baprs]-|sk-|AKIA)[A-Za-z0-9_\-]{8,}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9\-._~+/]+=*"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API[_-]?KEY|AUTH)=)(\S+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(authorization:\s*\S+\s+)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(bundle contents?|git bundle)[:\s].{0,200}"), r"\1 [REDACTED]"),
]
for rx, repl in patterns:
    text = rx.sub(repl, text)
text = text.replace("\x00", "")
if len(text) > cap:
    text = text[:cap] + "…[truncated]"
sys.stdout.write(text)
'
}

# Extract subtype, denial tool names ONLY, and capped final message from an
# execution log. Never prints inputs/args of denials. Never enables
# show_full_output — reads whatever the action already wrote.
print_ship_diag() {
  local log="$1"
  if [[ -z "$log" || ! -f "$log" ]]; then
    echo "ship-diag: execution-log not found${log:+ at $log}"
    return 0
  fi
  BB_LOG="$log" BB_CAP="$MSG_CAP" "$PYTHON3" -I -c '
import json, os, re, sys

path = os.environ["BB_LOG"]
cap = int(os.environ.get("BB_CAP", "1000"))
try:
    raw = open(path, encoding="utf-8", errors="replace").read()
except OSError as e:
    print("ship-diag: execution-log unreadable (%s)" % e)
    raise SystemExit(0)

def redact(text: str) -> str:
    patterns = [
        (re.compile(r"(?i)\b(gh[pousr]_|github_pat_|xox[baprs]-|sk-|AKIA)[A-Za-z0-9_\-]{8,}"), r"\1[REDACTED]"),
        (re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9\-._~+/]+=*"), r"\1[REDACTED]"),
        (re.compile(r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API[_-]?KEY|AUTH)=)(\S+)"), r"\1[REDACTED]"),
        (re.compile(r"(?i)(authorization:\s*\S+\s+)\S+"), r"\1[REDACTED]"),
        (re.compile(r"(?i)\b(bundle contents?|git bundle)[:\s].{0,200}"), r"\1 [REDACTED]"),
    ]
    for rx, repl in patterns:
        text = rx.sub(repl, text)
    text = text.replace("\x00", "")
    if len(text) > cap:
        text = text[:cap] + "…[truncated]"
    return text

objs = []
raw_s = raw.strip()
if raw_s.startswith("["):
    try:
        objs = json.loads(raw_s)
    except json.JSONDecodeError:
        objs = []
elif raw_s.startswith("{"):
    try:
        objs = [json.loads(raw_s)]
    except json.JSONDecodeError:
        objs = []
if not objs:
    dec = json.JSONDecoder()
    idx = 0
    while idx < len(raw_s):
        while idx < len(raw_s) and raw_s[idx].isspace():
            idx += 1
        if idx >= len(raw_s):
            break
        try:
            obj, end = dec.raw_decode(raw_s, idx)
        except json.JSONDecodeError:
            break
        objs.append(obj)
        idx = end

subtype = None
denials = []
final_msg = ""
for obj in objs:
    if not isinstance(obj, dict):
        continue
    if obj.get("type") == "result":
        subtype = obj.get("subtype")
        dens = obj.get("permission_denials") or obj.get("permissionDenials") or []
        if isinstance(dens, list):
            denials.extend(dens)
        res = obj.get("result") or ""
        if isinstance(res, str) and res.strip():
            final_msg = res.strip()
        elif isinstance(res, list):
            final_msg = "; ".join(str(x) for x in res[:5])
    for key in ("permission_denials", "permissionDenials"):
        if isinstance(obj.get(key), list):
            denials.extend(obj[key])

names = []
for d in denials:
    if isinstance(d, dict):
        # Tool name ONLY — never input / args / command text.
        n = d.get("tool_name") or d.get("toolName") or d.get("name") or d.get("tool")
        if n:
            names.append(str(n))
    elif isinstance(d, str) and d.strip():
        # Bare string: keep only a Bash(...) / tool-shaped token, drop args.
        m = re.match(r"(Bash\([^):\s]+|Write|Edit|Skill|mcp__\w+|NotebookEdit|Agent)", d.strip())
        names.append(m.group(1) if m else d.strip().split()[0][:80])

# Dedup preserving order
seen = set()
uniq = []
for n in names:
    if n not in seen:
        seen.add(n)
        uniq.append(n)

print("ship-diag: result subtype=%s" % (subtype if subtype is not None else "(missing)"))
if uniq:
    print("ship-diag: permission_denials tools: %s" % "; ".join(uniq[:20]))
else:
    print(
        "ship-diag: permission_denials tools: (none listed in execution log; "
        "count may still be >0 when show_full_output is false)"
    )
if final_msg:
    print("ship-diag: final message (redacted, capped ~%d chars):" % cap)
    print(redact(final_msg))
else:
    print("ship-diag: final message: (empty or not present in execution log)")
'
}

# NDJSON comments {body, created_at, login?, type?} on stdin.
# Optional $1 = run-started-at. Prints true/false.
# Claimless shape: latest comment is a stop, trusted author (Bot or matching
# owner login when set), strictly after the window when a window is given —
# mirrors routine-lock-cleanup's claimless stop rule enough for the early
# gate (settle still does the authoritative read).
stop_indicated_from_ndjson() {
  local since="${1:-}"
  local owner="${REPO_OWNER:-}"
  if [[ -z "$owner" && -n "${GITHUB_REPOSITORY:-}" ]]; then
    owner="${GITHUB_REPOSITORY%%/*}"
  fi
  BB_SINCE="$since" BB_OWNER="$owner" \
  BB_D1="$DECLINE_MARKER_1" BB_D2="$DECLINE_MARKER_2" BB_DF="$DEFER_MARKER" \
  "$PYTHON3" -I -c '
import json, os, sys

since = os.environ.get("BB_SINCE", "").strip()
owner = (os.environ.get("BB_OWNER") or "").strip().lower()
d1 = os.environ["BB_D1"]
d2 = os.environ["BB_D2"]
df = os.environ["BB_DF"]

def fl(body: str) -> str:
    if not body:
        return ""
    return body.replace("\r\n", "\n").replace("\r", "\n").split("\n", 1)[0]

def is_stop(body: str) -> bool:
    first = fl(body)
    return first.startswith(d1) or first.startswith(d2) or first.startswith(df)

def trusted(c: dict) -> bool:
    typ = (c.get("type") or "").strip()
    login = (c.get("login") or "").strip().lower()
    if login.endswith("[bot]"):
        login = login[:-5]
    if typ == "Bot" or login in ("github-actions", "shaiss"):
        return True
    if owner and login == owner:
        return True
    return False

rows = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        rows.append(json.loads(line))
    except json.JSONDecodeError:
        continue
if not rows:
    print("false")
    raise SystemExit(0)

def sort_key(c):
    return (c.get("created_at") or "", int(c.get("id") or 0))

rows.sort(key=sort_key)
latest = rows[-1]
body = latest.get("body") or ""
created = latest.get("created_at") or ""
ok = is_stop(body) and trusted(latest)
if since:
    ok = ok and created > since
print("true" if ok else "false")
'
}

head_is_ship_branch() {
  local issue="$1"
  local head="$2"
  [[ "$head" =~ ^claude/issue-${issue}- ]]
}

run_check() {
  local issue="" since="" log="" head_ref="" comments_file=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --issue) issue="${2:?}"; shift 2 ;;
      --run-started-at) since="${2:?}"; shift 2 ;;
      --execution-log) log="${2:?}"; shift 2 ;;
      --head-ref) head_ref="${2:?}"; shift 2 ;;
      --comments-file) comments_file="${2:?}"; shift 2 ;;
      *) usage "unknown option: $1" ;;
    esac
  done
  [[ "$issue" =~ ^[0-9]+$ ]] || usage "--issue must be a number (got: ${issue:-empty})"

  if [[ -z "$log" && -n "${RUNNER_TEMP:-}" && -f "${RUNNER_TEMP}/claude-execution-output.json" ]]; then
    log="${RUNNER_TEMP}/claude-execution-output.json"
  fi

  echo "::group::backlog-burn ship outcome + diag (#${issue})"
  print_ship_diag "${log:-}"

  if [[ -z "$head_ref" ]]; then
    head_ref="$(git symbolic-ref -q --short HEAD 2>/dev/null || git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
  fi
  echo "ship-check: HEAD=${head_ref:-"(unknown)"}"

  local on_branch=0 on_stop=0
  if head_is_ship_branch "$issue" "$head_ref"; then
    on_branch=1
    echo "ship-check: HEAD matches claude/issue-${issue}-*"
  else
    echo "ship-check: HEAD is not claude/issue-${issue}-*"
  fi

  local comments=""
  if [[ -n "$comments_file" ]]; then
    comments="$(cat -- "$comments_file")"
  elif [[ -n "${GH_TOKEN:-${GITHUB_TOKEN:-}}" && -n "${GITHUB_REPOSITORY:-}" ]]; then
    # Live: fetch issue comments as NDJSON {body,created_at,login,type,id}
    comments="$(
      gh api --paginate "repos/${GITHUB_REPOSITORY}/issues/${issue}/comments" \
        --jq '.[] | {body,created_at,login:.user.login,type:.user.type,id}' \
        2>/dev/null || true
    )"
  fi

  if [[ -n "$comments" ]]; then
    if printf '%s\n' "$comments" | stop_indicated_from_ndjson "$since" | grep -qx true; then
      on_stop=1
      echo "ship-check: explicit decline/defer/decision stop marker present"
    else
      echo "ship-check: no trusted stop marker for this firing"
    fi
  else
    echo "ship-check: no comments available to scan for a stop marker"
  fi

  echo "::endgroup::"

  if [[ "$on_branch" -eq 1 || "$on_stop" -eq 1 ]]; then
    echo "ship-check: ok (branch=${on_branch} stop=${on_stop})"
    return 0
  fi

  echo "::error::backlog-burn ship walk ended with HEAD='${head_ref}' (not claude/issue-${issue}-*) and no 🚢 DECLINED / 🚦 DECISION NEEDED / 🚢 DEFERRED stop — refusing to treat subtype=success as an outcome (issue #962)"
  return 1
}

selftest() {
  local tmp fails=0
  tmp="$(mktemp -d)"
  # Cleanup must not trip `set -u` if tmp is already gone.
  cleanup_st() { rm -rf -- "${tmp:-}"; }
  trap cleanup_st EXIT

  # --- redact + cap ---
  local out
  out="$(BB_IN='see ghp_ABCDEFGHIJKLMNOPQRSTUVWX and ok' diag_redact 1000)"
  printf '%s' "$out" | grep -q 'ghp_\[REDACTED\]' \
    || { echo "FAIL  selftest: token-like string was not redacted (got: $out)"; fails=$((fails + 1)); }
  printf '%s' "$out" | grep -q 'ghp_ABCDEF' \
    && { echo "FAIL  selftest: raw token leaked after redact"; fails=$((fails + 1)); } \
    || echo "ok    selftest: token-like string is redacted"

  out="$(BB_IN="$(printf 'x%.0s' {1..1500})" diag_redact 1000)"
  local len=${#out}
  # 1000 + len("…[truncated]") = 1012
  if [[ "$len" -gt 1020 ]]; then
    echo "FAIL  selftest: capped message longer than expected ($len)"; fails=$((fails + 1))
  else
    echo "ok    selftest: final message is length-capped ($len chars)"
  fi
  printf '%s' "$out" | grep -q '\[truncated\]' \
    || { echo "FAIL  selftest: truncation marker missing"; fails=$((fails + 1)); }

  # --- hard check: HEAD main + no decline → fail ---
  cat >"$tmp/empty-comments.ndjson" <<'EOF'
{"body":"unrelated note","created_at":"2026-10-30T12:00:01Z","login":"github-actions[bot]","type":"Bot","id":1}
EOF
  if "$0" --issue 962 --head-ref main --comments-file "$tmp/empty-comments.ndjson" \
      --run-started-at 2026-10-30T12:00:00Z --execution-log /nonexistent \
      >"$tmp/fail.out" 2>&1; then
    echo "FAIL  selftest: HEAD main with no decline did not fail"; fails=$((fails + 1))
    cat "$tmp/fail.out"
  else
    echo "ok    selftest: HEAD main with no decline fails the hard check"
  fi

  # --- hard check: claude/issue-N branch → pass ---
  if ! "$0" --issue 962 --head-ref claude/issue-962-ship-outcome \
      --comments-file "$tmp/empty-comments.ndjson" \
      --run-started-at 2026-10-30T12:00:00Z --execution-log /nonexistent \
      >"$tmp/pass-branch.out" 2>&1; then
    echo "FAIL  selftest: claude/issue-962-* HEAD did not pass"; fails=$((fails + 1))
    cat "$tmp/pass-branch.out"
  else
    echo "ok    selftest: claude/issue-N branch passes the hard check"
  fi

  # --- hard check: decline on main → pass ---
  cat >"$tmp/decline.ndjson" <<'EOF'
{"body":"🚢 DECLINED — needs a decision\n\nparked","created_at":"2026-10-30T12:00:05Z","login":"github-actions[bot]","type":"Bot","id":2}
EOF
  if ! "$0" --issue 962 --head-ref main --comments-file "$tmp/decline.ndjson" \
      --run-started-at 2026-10-30T12:00:00Z --execution-log /nonexistent \
      >"$tmp/pass-decline.out" 2>&1; then
    echo "FAIL  selftest: DECLINED stop on main did not pass"; fails=$((fails + 1))
    cat "$tmp/pass-decline.out"
  else
    echo "ok    selftest: explicit DECLINED stop passes the hard check"
  fi

  # --- diag extracts subtype + tool names only; redacts message ---
  cat >"$tmp/exec.json" <<'EOF'
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "permission_denials_count": 1,
  "permission_denials": [
    {"tool_name": "Bash", "tool_input": {"command": "git push origin main TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWX"}}
  ],
  "result": "done; export GITHUB_TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWX and push"
}
EOF
  print_ship_diag "$tmp/exec.json" >"$tmp/diag.out"
  grep -q 'subtype=success' "$tmp/diag.out" \
    || { echo "FAIL  selftest: subtype missing from diag"; fails=$((fails + 1)); }
  grep -q 'permission_denials tools: Bash' "$tmp/diag.out" \
    || { echo "FAIL  selftest: denial tool name missing"; fails=$((fails + 1)); }
  # Must NOT echo the tool_input command
  if grep -q 'git push origin main' "$tmp/diag.out"; then
    echo "FAIL  selftest: denial tool_input leaked into diag"; fails=$((fails + 1))
  else
    echo "ok    selftest: diag prints denial tool names only (no inputs)"
  fi
  if grep -q 'ghp_ABCDEF' "$tmp/diag.out"; then
    echo "FAIL  selftest: token leaked in diag final message"; fails=$((fails + 1))
  else
    echo "ok    selftest: diag redacts token-like strings in the final message"
  fi
  grep -q 'subtype=success' "$tmp/diag.out" && echo "ok    selftest: diag reports result subtype"

  # Wrong-issue branch must not pass
  if "$0" --issue 962 --head-ref claude/issue-961-other \
      --comments-file "$tmp/empty-comments.ndjson" \
      --run-started-at 2026-10-30T12:00:00Z --execution-log /nonexistent \
      >"$tmp/wrong.out" 2>&1; then
    echo "FAIL  selftest: wrong-issue branch passed"; fails=$((fails + 1))
  else
    echo "ok    selftest: wrong-issue claude/issue-* branch is refused"
  fi

  if [[ "$fails" -ne 0 ]]; then
    echo "FAIL  backlog-burn-ship-check selftest: $fails failure(s)" >&2
    exit 1
  fi
  echo "ok    backlog-burn-ship-check selftest passed"
  trap - EXIT
  rm -rf -- "$tmp"
}

main() {
  if [[ "${1:-}" == "--selftest" ]]; then
    selftest
    return 0
  fi
  run_check "$@"
}

main "$@"
