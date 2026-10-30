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
      DYLD_INSERT_LIBRARIES BASH_ENV ENV \
      GIT_DIR GIT_WORK_TREE GIT_CONFIG_PARAMETERS GIT_SSH_COMMAND \
      GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_OBJECT_DIRECTORY || true
export PYTHONNOUSERSITE=1

# Workflow restores this script into $RUNNER_TEMP (issue #962 security: the
# agent may rewrite the worktree copy). Prefer SHIP_CHECK_WORKTREE for the
# checkout; fall back to dirname($0)/.. for local / --selftest runs.
if [[ -n "${SHIP_CHECK_WORKTREE:-}" ]]; then
  case "${SHIP_CHECK_WORKTREE}" in
    /*) ;;
    *)
      echo "backlog-burn-ship-check: SHIP_CHECK_WORKTREE must be an absolute path" >&2
      exit 2
      ;;
  esac
  if [[ ! -d "${SHIP_CHECK_WORKTREE}" ]]; then
    echo "backlog-burn-ship-check: SHIP_CHECK_WORKTREE is not a directory" >&2
    exit 2
  fi
  ROOT="${SHIP_CHECK_WORKTREE}"
else
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi
cd "$ROOT"

if [[ -x /usr/bin/python3 ]]; then
  PYTHON3=/usr/bin/python3
else
  PYTHON3=python3
fi

DECLINE_MARKER_1='🚢 DECLINED'
DECLINE_MARKER_2='🚦 DECISION NEEDED'
DEFER_MARKER='🚢 DEFERRED'
# Same authenticity marker + allowlist as design-run-deliver / settle
# (Cipher #864): HTML marker + named logins only — never a bare SHIP-LOCK
# first line, never an unlisted Bot.
SHIP_LOCK_HTML_MARKER='<!-- design-run-ship-lock:v1 -->'
SHIP_LOCK_AUTHOR_LOGINS='github-actions[bot] shaiss'
MSG_CAP=1000

# Shared redaction patterns (diag_redact + print_ship_diag must stay in sync).
# Cap is applied by the caller after substitution when needed.
REDACT_PY='
import re
def redact_patterns(text, cap=None):
    # Normalize CR before line-anchored escapes: a bare \r before ::error::
    # would otherwise rewind the Actions log line and inject a workflow
    # command (Bugbot on #962).
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    patterns = [
        (re.compile(r"(?i)\b(gh[pousr]_|github_pat_|xox[baprs]-|sk-|AKIA)[A-Za-z0-9_\-]{8,}"), r"\1[REDACTED]"),
        (re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9\-._~+/]+=*"), r"\1[REDACTED]"),
        (re.compile(r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API[_-]?KEY|AUTH)=)(\S+)"), r"\1[REDACTED]"),
        (re.compile(r"(?i)([\"'\'']?[A-Za-z0-9_\-]*(?:token|secret|password|api[_-]?key|auth)[A-Za-z0-9_\-]*[\"'\'']?\s*[:=]\s*[\"'\'']?)[^\s\"'\'',;]+"), r"\1[REDACTED]"),
        (re.compile(r"(?i)\b(Basic\s+)[A-Za-z0-9+/=]{8,}"), r"\1[REDACTED]"),
        (re.compile(r"(?i)(authorization:\s*\S+\s+)\S+"), r"\1[REDACTED]"),
        (re.compile(r"(?i)\b(bundle contents?|git bundle)[:\s].{0,200}"), r"\1 [REDACTED]"),
        # Escape workflow-command prefixes so model output cannot inject ::error:: etc.
        (re.compile(r"(?m)^::"), r"\\::"),
    ]
    for rx, repl in patterns:
        text = rx.sub(repl, text)
    text = text.replace("\x00", "")
    if cap is not None and len(text) > cap:
        text = text[:cap] + "…[truncated]"
    return text
'

usage() {
  echo "usage: $0 --issue <N> [--run-started-at ISO8601Z] [--execution-log path] [--head-ref name] [--comments-file ndjson]" >&2
  echo "       $0 --selftest" >&2
  [[ $# -gt 0 ]] && echo "error: $*" >&2
  exit 2
}

# Env BB_IN or stdin → redacted + length-capped stdout.
diag_redact() {
  BB_CAP="${1:-$MSG_CAP}" "$PYTHON3" -I -c "
${REDACT_PY}
import os, sys
cap = int(os.environ.get('BB_CAP', '1000'))
text = os.environ.get('BB_IN')
if text is None:
    text = sys.stdin.read()
sys.stdout.write(redact_patterns(text, cap))
"
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
  BB_LOG="$log" BB_CAP="$MSG_CAP" "$PYTHON3" -I -c "
${REDACT_PY}
import json, os, re, sys

path = os.environ['BB_LOG']
cap = int(os.environ.get('BB_CAP', '1000'))
try:
    raw = open(path, encoding='utf-8', errors='replace').read()
except OSError as e:
    print('ship-diag: execution-log unreadable (%s)' % e)
    raise SystemExit(0)

def redact(text: str) -> str:
    return redact_patterns(text, cap)

objs = []
raw_s = raw.strip()
if raw_s.startswith('['):
    try:
        objs = json.loads(raw_s)
    except json.JSONDecodeError:
        objs = []
elif raw_s.startswith('{'):
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
final_msg = ''
for obj in objs:
    if not isinstance(obj, dict):
        continue
    if obj.get('type') == 'result':
        subtype = obj.get('subtype')
        dens = obj.get('permission_denials') or obj.get('permissionDenials') or []
        if isinstance(dens, list):
            denials.extend(dens)
        res = obj.get('result') or ''
        if isinstance(res, str) and res.strip():
            final_msg = res.strip()
        elif isinstance(res, list):
            final_msg = '; '.join(str(x) for x in res[:5])
    for key in ('permission_denials', 'permissionDenials'):
        if isinstance(obj.get(key), list):
            denials.extend(obj[key])

names = []
for d in denials:
    if isinstance(d, dict):
        # Tool name ONLY — never input / args / command text.
        n = d.get('tool_name') or d.get('toolName') or d.get('name') or d.get('tool')
        if n:
            names.append(str(n))
    elif isinstance(d, str) and d.strip():
        # Bare string: keep only a Bash(...) / tool-shaped token, drop args.
        m = re.match(r'(Bash\([^):\s]+|Write|Edit|Skill|mcp__\w+|NotebookEdit|Agent)', d.strip())
        names.append(m.group(1) if m else d.strip().split()[0][:80])

# Dedup preserving order
seen = set()
uniq = []
for n in names:
    if n not in seen:
        seen.add(n)
        uniq.append(n)

print('ship-diag: result subtype=%s' % (subtype if subtype is not None else '(missing)'))
if uniq:
    print('ship-diag: permission_denials tools: %s' % redact('; '.join(uniq[:20])))
else:
    print(
        'ship-diag: permission_denials tools: (none listed in execution log; '
        'count may still be >0 when show_full_output is false)'
    )
if final_msg:
    print('ship-diag: final message (redacted, capped ~%d chars):' % cap)
    print(redact(final_msg))
else:
    print('ship-diag: final message: (empty or not present in execution log)')
"
}

# NDJSON comments {body, created_at, login?, type?, id?} on stdin.
# Optional $1 = run-started-at. Prints true/false.
# Mirrors design-run-deliver hard_stop_from_comments / settle:
#   - With an authentic SHIP-LOCK (HTML marker + allowlisted login): any
#     trusted stop after the latest lock inside the run window counts —
#     a later non-stop comment does not invalidate it.
#   - Claimless (no authentic lock): only the latest comment may be a stop.
# Settle still does the authoritative read; this is the early gate.
stop_indicated_from_ndjson() {
  local since="${1:-}"
  local owner="${REPO_OWNER:-}"
  if [[ -z "$owner" && -n "${GITHUB_REPOSITORY:-}" ]]; then
    owner="${GITHUB_REPOSITORY%%/*}"
  fi
  BB_SINCE="$since" BB_OWNER="$owner" \
  BB_D1="$DECLINE_MARKER_1" BB_D2="$DECLINE_MARKER_2" BB_DF="$DEFER_MARKER" \
  BB_LOCK_HTML="$SHIP_LOCK_HTML_MARKER" \
  BB_LOCK_LOGINS="$SHIP_LOCK_AUTHOR_LOGINS" \
  "$PYTHON3" -I -c '
import json, os, sys

since = os.environ.get("BB_SINCE", "").strip()
owner = (os.environ.get("BB_OWNER") or "").strip().lower()
d1 = os.environ["BB_D1"]
d2 = os.environ["BB_D2"]
df = os.environ["BB_DF"]
html_marker = os.environ["BB_LOCK_HTML"]
lock_logins = {
    x.strip().lower()
    for x in os.environ.get("BB_LOCK_LOGINS", "").split()
    if x.strip()
}

def fl(body: str) -> str:
    if not body:
        return ""
    for line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        s = line.strip()
        if s:
            return s
    return ""

def is_stop(body: str) -> bool:
    first = fl(body)
    return first.startswith(d1) or first.startswith(d2) or first.startswith(df)

def stop_trusted(c: dict) -> bool:
    typ = (c.get("type") or "").strip()
    login = (c.get("login") or "").strip().lower()
    if typ == "Bot":
        return True
    if owner and login == owner:
        return True
    return False

def is_lock(c: dict) -> bool:
    login = (c.get("login") or "").strip().lower()
    return html_marker in (c.get("body") or "") and login in lock_logins

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

latest_lock = None
for c in rows:
    if not isinstance(c, dict) or not is_lock(c):
        continue
    if latest_lock is None or sort_key(c) > sort_key(latest_lock):
        latest_lock = c

if latest_lock is None:
    # Claimless: only the latest comment may be a this-run stop.
    if not since:
        print("false")
        raise SystemExit(0)
    latest = rows[-1]
    created = latest.get("created_at") or ""
    ok = (
        is_stop(latest.get("body") or "")
        and stop_trusted(latest)
        and created > since
    )
else:
    lock_created = latest_lock.get("created_at") or ""
    ok = any(
        isinstance(c, dict)
        and (c.get("created_at") or "") > lock_created
        and (not since or (c.get("created_at") or "") > since)
        and is_stop(c.get("body") or "")
        and stop_trusted(c)
        for c in rows
    )
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
    # Live: fetch issue comments as NDJSON {body,created_at,login,type,id}.
    # ALWAYS mktemp a fresh empty GH_CONFIG_DIR immediately before gh —
    # never reuse an incoming GH_CONFIG_DIR (a same-uid leftover can plant
    # http_unix_socket / api_host into a RUNNER_TEMP dir created earlier;
    # Bugbot on #962). --hostname pins the host even if hosts.yml exists.
    # Fail closed on fetch error — never treat attacker NDJSON as "no stop".
    unset GH_ENTERPRISE_TOKEN HTTP_PROXY HTTPS_PROXY ALL_PROXY \
      http_proxy https_proxy all_proxy \
      SSL_CERT_FILE SSL_CERT_DIR CURL_CA_BUNDLE REQUESTS_CA_BUNDLE \
      NODE_EXTRA_CA_CERTS || true
    local gh_cfg
    gh_cfg="$(mktemp -d "${TMPDIR:-/tmp}/bb-gh-config.XXXXXX")"
    if [[ -L "$gh_cfg" || ! -d "$gh_cfg" ]]; then
      echo "ship-check: refusing GH_CONFIG_DIR through a symlink" >&2
      comments=""
    elif [[ -n "$(ls -A -- "$gh_cfg" 2>/dev/null || true)" ]]; then
      echo "ship-check: refusing non-empty GH_CONFIG_DIR (possible poison)" >&2
      rm -rf -- "$gh_cfg"
      comments=""
    else
      chmod 700 "$gh_cfg" || true
      # GH_BIN override is for --selftest only (recording fake); production
      # pins /usr/bin/gh so a PATH plant cannot redirect the job token.
      local gh_bin="${GH_BIN:-/usr/bin/gh}"
      if ! comments="$(
        GH_HOST=github.com GH_CONFIG_DIR="$gh_cfg" \
        GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN}}" \
        "$gh_bin" api --hostname github.com --paginate \
          "repos/${GITHUB_REPOSITORY}/issues/${issue}/comments" \
          --jq '.[] | {body,created_at,login:.user.login,type:.user.type,id}'
      )"; then
        echo "ship-check: gh comment fetch failed — stop-marker path unavailable" >&2
        comments=""
      fi
      rm -rf -- "$gh_cfg"
    fi
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

  out="$(BB_IN='"authToken": "sekritVALUE123" ANTHROPIC_API_KEY: abcdefghijklmnop Basic YWJjZGVmZ2hpams=' diag_redact 1000)"
  printf '%s' "$out" | grep -q '\[REDACTED\]' \
    || { echo "FAIL  selftest: quoted/colon/Basic secrets not redacted (got: $out)"; fails=$((fails + 1)); }
  printf '%s' "$out" | grep -q 'sekritVALUE' \
    && { echo "FAIL  selftest: quoted secret leaked (got: $out)"; fails=$((fails + 1)); } \
    || echo "ok    selftest: quoted/colon/Basic secret shapes are redacted"

  out="$(BB_IN="$(printf '::error::planted\nx%.0s' {1..20})" diag_redact 1000)"
  printf '%s' "$out" | grep -q '^\\::' \
    || { echo "FAIL  selftest: :: workflow-command prefix not escaped (got: $out)"; fails=$((fails + 1)); }
  printf '%s' "$out" | grep -qE '^::' \
    && { echo "FAIL  selftest: bare :: line survived redact"; fails=$((fails + 1)); } \
    || echo "ok    selftest: :: workflow-command prefixes are escaped"

  # CR before :: must not leave a bare workflow command after log rewind.
  out="$(BB_IN="$(printf 'pre\r::error::planted')" diag_redact 1000)"
  printf '%s' "$out" | grep -q $'\r::' \
    && { echo "FAIL  selftest: CR-prefixed :: survived (got: $(printf '%q' "$out"))"; fails=$((fails + 1)); }
  printf '%s' "$out" | grep -qE '(^|[^\\])::error::' \
    && { echo "FAIL  selftest: unescaped ::error after CR normalize (got: $(printf '%q' "$out"))"; fails=$((fails + 1)); } \
    || echo "ok    selftest: CR-prefixed :: workflow commands are escaped"

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

  # --- claimed thread: lock + DECLINED + later non-stop still passes ---
  cat >"$tmp/claimed.ndjson" <<'EOF'
{"body":"🚢 SHIP-LOCK — claim\n\n<!-- design-run-ship-lock:v1 -->\n","created_at":"2026-10-30T12:00:01Z","login":"github-actions[bot]","type":"Bot","id":10}
{"body":"🚢 DECLINED — too big\n","created_at":"2026-10-30T12:00:05Z","login":"github-actions[bot]","type":"Bot","id":11}
{"body":"unrelated follow-up","created_at":"2026-10-30T12:00:09Z","login":"github-actions[bot]","type":"Bot","id":12}
EOF
  if ! "$0" --issue 962 --head-ref main --comments-file "$tmp/claimed.ndjson" \
      --run-started-at 2026-10-30T12:00:00Z --execution-log /nonexistent \
      >"$tmp/pass-claimed.out" 2>&1; then
    echo "FAIL  selftest: claimed-thread stop+later-nonstop did not pass"; fails=$((fails + 1))
    cat "$tmp/pass-claimed.out"
  else
    echo "ok    selftest: claimed-thread stop survives a later non-stop comment"
  fi

  # Bare SHIP-LOCK first line (no HTML marker) must not open claimed mode
  # and a later DECLINED still works as claimless latest.
  cat >"$tmp/fake-lock.ndjson" <<'EOF'
{"body":"🚢 SHIP-LOCK — forged without html\n","created_at":"2026-10-30T12:00:01Z","login":"github-actions[bot]","type":"Bot","id":20}
{"body":"🚢 DECLINED — real stop\n","created_at":"2026-10-30T12:00:05Z","login":"github-actions[bot]","type":"Bot","id":21}
EOF
  if ! "$0" --issue 962 --head-ref main --comments-file "$tmp/fake-lock.ndjson" \
      --run-started-at 2026-10-30T12:00:00Z --execution-log /nonexistent \
      >"$tmp/pass-fake-lock.out" 2>&1; then
    echo "FAIL  selftest: claimless DECLINED after bare SHIP-LOCK did not pass"; fails=$((fails + 1))
    cat "$tmp/pass-fake-lock.out"
  else
    echo "ok    selftest: bare SHIP-LOCK does not forge a claimed lock"
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
  "result": "done; export GITHUB_TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWX and push\n::warning::planted"
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
  if grep -qE '^::warning::' "$tmp/diag.out"; then
    echo "FAIL  selftest: bare :: workflow command in diag final message"; fails=$((fails + 1))
  else
    echo "ok    selftest: diag escapes :: workflow-command lines in the final message"
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

  # Behavioral (not a source grep): a planted lowercase proxy must be
  # cleared before gh runs. actionlint forbids listing http_proxy beside
  # HTTP_PROXY in workflow env (case-insensitive keys), so the script
  # unset is the neutralization that has to hold at the call site.
  cat >"$tmp/fake-gh" <<'EOF'
#!/bin/sh
probe="${PROXY_PROBE:?PROXY_PROBE unset}"
{
  # POSIX parameter expansion: distinguish unset from empty.
  if [ -n "${http_proxy+x}" ]; then printf 'http_proxy=SET\n'; else printf 'http_proxy=UNSET\n'; fi
  if [ -n "${https_proxy+x}" ]; then printf 'https_proxy=SET\n'; else printf 'https_proxy=UNSET\n'; fi
  if [ -n "${all_proxy+x}" ]; then printf 'all_proxy=SET\n'; else printf 'all_proxy=UNSET\n'; fi
  if [ -n "${HTTP_PROXY+x}" ]; then printf 'HTTP_PROXY=SET\n'; else printf 'HTTP_PROXY=UNSET\n'; fi
  if [ -n "${HTTPS_PROXY+x}" ]; then printf 'HTTPS_PROXY=SET\n'; else printf 'HTTPS_PROXY=UNSET\n'; fi
  if [ -n "${ALL_PROXY+x}" ]; then printf 'ALL_PROXY=SET\n'; else printf 'ALL_PROXY=UNSET\n'; fi
} > "$probe"
# Empty comment stream — ship-branch HEAD still passes the hard check.
exit 0
EOF
  chmod +x "$tmp/fake-gh"
  : >"$tmp/proxy-probe.env"
  if ! env \
      GH_BIN="$tmp/fake-gh" \
      PROXY_PROBE="$tmp/proxy-probe.env" \
      GH_TOKEN=test-token \
      GITHUB_REPOSITORY=acme/print-bench \
      http_proxy='http://evil.example:1' \
      https_proxy='http://evil.example:1' \
      all_proxy='socks5://evil.example:1' \
      HTTP_PROXY='http://evil.example:1' \
      HTTPS_PROXY='http://evil.example:1' \
      ALL_PROXY='socks5://evil.example:1' \
      "$0" --issue 962 --head-ref claude/issue-962-proxy-clear \
      --run-started-at 2026-10-30T12:00:00Z --execution-log /nonexistent \
      >"$tmp/proxy.out" 2>&1; then
    echo "FAIL  selftest: planted-proxy live-fetch path did not pass"; fails=$((fails + 1))
    cat "$tmp/proxy.out"
  elif [[ ! -s "$tmp/proxy-probe.env" ]]; then
    echo "FAIL  selftest: fake gh was never invoked (proxy probe empty)"; fails=$((fails + 1))
    cat "$tmp/proxy.out"
  else
    local proxy_leaks=0
    local k
    for k in http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY; do
      if ! grep -qx "${k}=UNSET" "$tmp/proxy-probe.env"; then
        echo "FAIL  selftest: planted ${k} reached gh (probe: $(tr '\n' ' ' <"$tmp/proxy-probe.env"))"
        proxy_leaks=$((proxy_leaks + 1))
      fi
    done
    if [[ "$proxy_leaks" -ne 0 ]]; then
      fails=$((fails + proxy_leaks))
    else
      echo "ok    selftest: planted lowercase/uppercase proxies are cleared before gh"
    fi
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
