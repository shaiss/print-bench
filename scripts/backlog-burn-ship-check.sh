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
# 🚢 DEFERRED), and the ship step prints result subtype + denial tool
# names (sanitized) plus the final message's length and sha256 — never
# the message text (MED-C on #963: shape redaction cannot beat /proc env
# dumps or split/encoded keys).
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
      GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_OBJECT_DIRECTORY \
      GIT_EXEC_PATH || true
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
# Stop markers (DECLINED / DECISION NEEDED / DEFERRED) only from this bot
# login or the repo owner — never any other Bot-type user (MED/LOW on #963).
STOP_MARKER_BOT_LOGIN='github-actions[bot]'
MSG_CAP=1000
# Hard cap before any regex (MED-B on #963): the #953 JWT/AWS patterns are
# quadratic on pathological input (eyJ × 40k took >20s). ~20 KiB is plenty
# for a subtype string or a denial-tool name list.
REDACT_INPUT_CAP=20480

# Shared sanitizer for subtype + denial tool names (diag_redact +
# print_ship_diag must stay in sync). Order: hard-cap → strip Unicode
# space/format/controls → neutralize workflow cmds → key-shape redact →
# optional output cap. Key-shape specs are copied verbatim from PR #953's
# provenance.gitstore._SECRET_PATTERN_SPECS (do not import that package
# from the post-agent path); ship-diag additions follow.
REDACT_PY='
import re
import unicodedata

_INPUT_CAP = 20480
_DROP_CATS = frozenset({"Zs", "Zl", "Zp", "Cf", "Cc"})

# --- verbatim from PR #953 provenance.gitstore (key-shape redactor) ---
_SECRET_PATTERN_SPECS = (
    # GitHub fine-grained / classic / app installation / user-to-server /
    # refresh tokens (ghp_/gho_/ghs_/ghu_/ghr_). Allow . and - — some
    # server-to-server forms are not pure [A-Za-z0-9_].
    (r"gh[pousr]_[A-Za-z0-9._\-]{20,}", "***"),
    (r"github_pat_[A-Za-z0-9._\-]{20,}", "***"),
    # Actions / OIDC JWTs (ACTIONS_RUNTIME_TOKEN and friends).
    (r"eyJ[A-Za-z0-9_\-]+=*\.eyJ[A-Za-z0-9_\-]+=*\.[A-Za-z0-9_\-+/=]+", "***"),
    # OpenRouter / Anthropic API keys.
    (r"sk-or-[A-Za-z0-9_\-]{20,}", "***"),
    (r"sk-ant-[A-Za-z0-9_\-]{20,}", "***"),
    # Documented Z.AI API keys (32 hex + "." + 16 alnum), including when
    # echoed as ANTHROPIC_AUTH_TOKEN=… from a ship-link env dump. Do NOT use
    # a blanket 48+ url-safe class — that redacts SHA-256 digests (64 hex).
    # Leading lookbehind is hex-only so a non-hex letter prefix still redacts;
    # trailing lookahead omits "." so ``key.`` (key then a dot) still redacts.
    (r"(?i)(?:ANTHROPIC_AUTH_TOKEN|ZAI_KEY)\s*[=:]\s*[0-9a-f]{32}\.[A-Za-z0-9]{16}", "***"),
    (r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{32}\.[A-Za-z0-9]{16}(?![A-Za-z0-9])", "***"),
    # AWS secret access key sitting near an access-key id (40 chars of
    # base64-ish, within ~80 chars of AKIA/ASIA — catch both orders).
    # These MUST run before the standalone AKIA/ASIA patterns or the id
    # is replaced first and the nearby secret is left behind. No
    # lookbehind on [A-Za-z0-9/+=] — that class includes ``=``, which is
    # the usual ``secret=…`` separator and would skip the value.
    (
        r"(?:AKIA|ASIA)[0-9A-Z]{16}"
        r"(?:[\s\S]{0,80}?)"
        r"[A-Za-z0-9/+]{40}",
        "***",
    ),
    (
        r"[A-Za-z0-9/+]{40}"
        r"(?:[\s\S]{0,80}?)"
        r"(?:AKIA|ASIA)[0-9A-Z]{16}",
        "***",
    ),
    # AWS access key ids (after the nearby-secret pairs above).
    (r"(?:AKIA|ASIA)[0-9A-Z]{16}", "***"),
    # Authorization Bearer values (header form before bare Bearer).
    (r"(?i)Authorization\s*:\s*Bearer\s+\S+", "Authorization: Bearer ***"),
    (r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]{20,}", "Bearer ***"),
    # Credentials in URLs (user:pass@ before x-access-token form).
    (r"(?i)https?://[^\s/@:]+:[^\s/@]+@", "https://***:***@"),
    (r"(?i)x-access-token:[^\s/@]+@", "x-access-token:***@"),
    # Base64-encoded x-access-token basic-auth strings (Actions masks the
    # raw token but not this form — see credential_env / Git.secrets).
    (r"(?i)(?:AUTHORIZATION:\s*)?basic\s+[A-Za-z0-9+/]{20,}={0,2}", "basic ***"),
)

# Ship-diag additions on top of the #953 key-shape set (MED-1 on #963).
_SHIP_DIAG_EXTRA_SPECS = (
    # Any *_KEY= assignment (covers ZAI_KEY= when the value shape drifts,
    # plus ANTHROPIC_API_KEY= / OPENROUTER_API_KEY= without relying on
    # TOKEN/SECRET/API_KEY word classes alone).
    (r"(?i)\b([A-Za-z0-9_]*_KEY)\s*[=:]\s*\S+", r"\1=***"),
    # Google API keys.
    (r"AIza[0-9A-Za-z_\-]{35}", "***"),
    # URL userinfo for any scheme (postgres://user:pw@ → scheme://[REDACTED]@).
    (r"(?i)([a-z][a-z0-9+.\-]*://)[^\s/@:]+:[^\s/@]+@", r"\1[REDACTED]@"),
    # Long bare hex (>=40 chars) — diag excerpts must not leak digests/tokens.
    (r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{40,}(?![0-9A-Fa-f])", "***"),
)

_SECRET_PATTERNS = tuple(
    (re.compile(pat), repl) for pat, repl in _SECRET_PATTERN_SPECS
) + tuple(
    (re.compile(pat), repl) for pat, repl in _SHIP_DIAG_EXTRA_SPECS
)

# After Zs/Zl/Zp/Cf/Cc (except LF) are stripped, only ASCII space/tab remain
# as line-leading indent before a workflow-command ::.
_WF_LINE_RE = re.compile(r"(?m)^([ \t]*)::")
_LIVE_WF_RE = re.compile(r"(?m)^[ \t]*::")


def _strip_space_format_controls(text: str) -> str:
    """Drop Unicode Zs/Zl/Zp/Cf and Cc. Keep LF + ASCII space/tab only."""
    out = []
    for ch in text:
        # Keep line structure and ordinary indent; drop NBSP/U+2000/…/Cf.
        # Use real LF/TAB code points (not the two-char sequences \\n / \\t).
        if ch == "\n" or ch == "\t" or ch == " ":
            out.append(ch)
            continue
        if unicodedata.category(ch) in _DROP_CATS:
            continue
        out.append(ch)
    return "".join(out)


def redact_patterns(text, cap=None):
    text = text or ""
    # 0) Hard-cap BEFORE any regex (MED-B ReDoS bound).
    if len(text) > _INPUT_CAP:
        text = text[:_INPUT_CAP]
    # 1) Strip Unicode space/format + controls so NBSP/U+2000/…/U+3000
    #    cannot hide a line-leading :: (MED-A).
    text = _strip_space_format_controls(text)
    # 2) Neutralize workflow commands: line-leading :: (optional indent) and
    #    legacy ##[ anywhere (including ##[add-mask]).
    text = _WF_LINE_RE.sub(r"\1\\::", text)
    text = text.replace("##[", "# #[")
    # 3) Key-shape redaction (#953 verbatim + ship-diag extras).
    for pat, repl in _SECRET_PATTERNS:
        text = pat.sub(repl, text)
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

# Extract subtype + denial tool names (sanitized) and final-message
# length/sha256 from an execution log. Never prints message text, never
# prints denial inputs/args. Never enables show_full_output.
print_ship_diag() {
  local log="$1"
  if [[ -z "$log" || ! -f "$log" ]]; then
    echo "ship-diag: execution-log not found${log:+ at $log}"
    return 0
  fi
  BB_LOG="$log" BB_CAP="$MSG_CAP" "$PYTHON3" -I -c "
${REDACT_PY}
import hashlib, json, os, re, sys

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

sub_s = str(subtype) if subtype is not None else '(missing)'
print('ship-diag: result subtype=%s' % redact(sub_s))
if uniq:
    print('ship-diag: permission_denials tools: %s' % redact('; '.join(uniq[:20])))
else:
    print(
        'ship-diag: permission_denials tools: (none listed in execution log; '
        'count may still be >0 when show_full_output is false)'
    )
# MED-C: never emit message text — length + sha256 of the raw body only.
msg_len = len(final_msg)
msg_sha = hashlib.sha256(final_msg.encode('utf-8')).hexdigest()
if final_msg:
    print('ship-diag: final message: len=%d sha256=%s' % (msg_len, msg_sha))
else:
    print(
        'ship-diag: final message: (empty or not present; len=%d sha256=%s)'
        % (msg_len, msg_sha)
    )
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
  BB_STOP_BOT="$STOP_MARKER_BOT_LOGIN" \
  "$PYTHON3" -I -c '
import json, os, sys

since = os.environ.get("BB_SINCE", "").strip()
owner = (os.environ.get("BB_OWNER") or "").strip().lower()
d1 = os.environ["BB_D1"]
d2 = os.environ["BB_D2"]
df = os.environ["BB_DF"]
html_marker = os.environ["BB_LOCK_HTML"]
stop_bot = (os.environ.get("BB_STOP_BOT") or "github-actions[bot]").strip().lower()
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
    # Only github-actions[bot] (by login) or the repo owner — never any
    # other Bot-type user (a dependabot/renovate DECLINED must not pass).
    login = (c.get("login") or "").strip().lower()
    if login == stop_bot:
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

  # Behavioral selftest hook: record whether a planted GIT_EXEC_PATH survived
  # the startup unset to the git call site. symbolic-ref/rev-parse are often
  # builtins (so a helper plant would never run); the probe is the falsifiable
  # check (Bugbot on #963).
  if [[ -n "${BB_SHIP_CHECK_GIT_ENV_PROBE:-}" ]]; then
    {
      if [ -n "${GIT_EXEC_PATH+x}" ]; then printf 'GIT_EXEC_PATH=SET\n'; else printf 'GIT_EXEC_PATH=UNSET\n'; fi
    } >"${BB_SHIP_CHECK_GIT_ENV_PROBE}" || true
  fi

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
    unset GH_ENTERPRISE_TOKEN GH_FORCE_TTY HTTP_PROXY HTTPS_PROXY ALL_PROXY \
      http_proxy https_proxy all_proxy \
      SSL_CERT_FILE SSL_CERT_DIR CURL_CA_BUNDLE REQUESTS_CA_BUNDLE \
      NODE_EXTRA_CA_CERTS || true
    # Planted GH_PAGER/PAGER + GH_FORCE_TTY make gh exec the pager with
    # GH_TOKEN (Security Reviewer on #963). Force cat; never inherit a plant.
    export GH_PAGER=cat PAGER=cat
    unset GH_FORCE_TTY || true
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
      # Always /usr/bin/gh — never honor GH_BIN. A GITHUB_ENV plant of
      # GH_BIN must not receive GH_TOKEN or forge a Bot DECLINED (Bugbot /
      # Agentic Security Review on #962 / #963). The ship-outcome step also
      # pins GH_BIN=/usr/bin/gh; this is defense in depth if a caller omits
      # the pin. Selftests that need the pre-gh env use BB_SHIP_CHECK_PROXY_PROBE.
      local gh_bin=/usr/bin/gh
      if [[ -n "${BB_SHIP_CHECK_PROXY_PROBE:-}" ]]; then
        # Behavioral selftest hook: record whether planted proxies survived
        # to the call site. Does not substitute gh_bin.
        {
          if [ -n "${http_proxy+x}" ]; then printf 'http_proxy=SET\n'; else printf 'http_proxy=UNSET\n'; fi
          if [ -n "${https_proxy+x}" ]; then printf 'https_proxy=SET\n'; else printf 'https_proxy=UNSET\n'; fi
          if [ -n "${all_proxy+x}" ]; then printf 'all_proxy=SET\n'; else printf 'all_proxy=UNSET\n'; fi
          if [ -n "${HTTP_PROXY+x}" ]; then printf 'HTTP_PROXY=SET\n'; else printf 'HTTP_PROXY=UNSET\n'; fi
          if [ -n "${HTTPS_PROXY+x}" ]; then printf 'HTTPS_PROXY=SET\n'; else printf 'HTTPS_PROXY=UNSET\n'; fi
          if [ -n "${ALL_PROXY+x}" ]; then printf 'ALL_PROXY=SET\n'; else printf 'ALL_PROXY=UNSET\n'; fi
          printf 'gh_bin=%s\n' "$gh_bin"
          printf 'GH_PAGER=%s\n' "${GH_PAGER-}"
          if [ -n "${GH_FORCE_TTY+x}" ]; then printf 'GH_FORCE_TTY=SET\n'; else printf 'GH_FORCE_TTY=UNSET\n'; fi
        } >"${BB_SHIP_CHECK_PROXY_PROBE}" || true
      fi
      if ! comments="$(
        GH_HOST=github.com GH_CONFIG_DIR="$gh_cfg" \
        GH_PAGER=cat PAGER=cat \
        GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN}}" \
        env -u GH_FORCE_TTY \
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
  # Synthetic fixtures are built at runtime (concat) so the repo never holds
  # a literal secret-shaped string for gitleaks to trip on.
  local out
  local ghp_tok="gh"'p_'"ABCDEFGHIJKLMNOPQRSTUVWX"
  out="$(BB_IN="see ${ghp_tok} and ok" diag_redact 1000)"
  printf '%s' "$out" | grep -q '\*\*\*' \
    || { echo "FAIL  selftest: token-like string was not redacted (got: $out)"; fails=$((fails + 1)); }
  printf '%s' "$out" | grep -q 'ghp_ABCDEF' \
    && { echo "FAIL  selftest: raw token leaked after redact"; fails=$((fails + 1)); } \
    || echo "ok    selftest: token-like string is redacted"

  # Basic pattern from #953 needs >=20 b64 chars; KEY= covers the assignment.
  local key_val='abcdefghijklmnop'
  local basic_b64='YWJjZGVm'"Z2hpamtsbXFxcnN0dXZ3eHl6"'='
  out="$(BB_IN="ANTHROPIC_API_KEY=${key_val} Basic ${basic_b64}" diag_redact 1000)"
  printf '%s' "$out" | grep -q '\*\*\*' \
    || { echo "FAIL  selftest: KEY=/Basic secrets not redacted (got: $out)"; fails=$((fails + 1)); }
  printf '%s' "$out" | grep -q 'abcdefghijklmnop' \
    && { echo "FAIL  selftest: API key value leaked (got: $out)"; fails=$((fails + 1)); } \
    || echo "ok    selftest: KEY=/Basic secret shapes are redacted"
  printf '%s' "$out" | grep -qi 'YWJjZGVmZ2hpamtsbXFxcnN0dXZ3eHl6' \
    && { echo "FAIL  selftest: Basic credential leaked (got: $out)"; fails=$((fails + 1)); }

  out="$(BB_IN="$(printf '::error::planted\nx%.0s' {1..20})" diag_redact 1000)"
  printf '%s' "$out" | grep -q '^\\::' \
    || { echo "FAIL  selftest: :: workflow-command prefix not escaped (got: $out)"; fails=$((fails + 1)); }
  printf '%s' "$out" | grep -qE '^::' \
    && { echo "FAIL  selftest: bare :: line survived redact"; fails=$((fails + 1)); } \
    || echo "ok    selftest: :: workflow-command prefixes are escaped"

  # CR before :: is stripped as a C0 control so it cannot rewind the Actions
  # log line; after strip the remnant is mid-line and not a workflow cmd.
  out="$(BB_IN="$(printf 'pre\r::error::planted')" diag_redact 1000)"
  printf '%s' "$out" | grep -q $'\r' \
    && { echo "FAIL  selftest: CR survived control strip (got: $(printf '%q' "$out"))"; fails=$((fails + 1)); }
  if printf '%s' "$out" | "$PYTHON3" -I -c 'import re,sys; sys.exit(0 if re.search(r"(?m)^[ \t]*::", sys.stdin.read()) else 1)'; then
    echo "FAIL  selftest: line-leading :: after CR strip (got: $(printf '%q' "$out"))"; fails=$((fails + 1))
  else
    echo "ok    selftest: CR-prefixed :: cannot inject a workflow command"
  fi

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

  # --- MED-1: every redact_probe.out row (secret AND injected command gone) ---
  # Inputs mirror the probe; assert secret material and live workflow cmds
  # cannot appear (neutralized \:: still contains the letters — check the
  # line-anchored form / ##[ instead).
  BB_CAP=1000 "$PYTHON3" -I -c "
${REDACT_PY}
import re, sys

def check_secret(name, raw, forbidden):
    out = redact_patterns(raw, 1000)
    bad = [f for f in forbidden if f in out]
    if bad:
        print('FAIL  selftest: probe %s leaked %r in %r' % (name, bad, out))
        return 1
    print('ok    selftest: probe %s redacts secret' % name)
    return 0

def check_cmd(name, raw):
    out = redact_patterns(raw, 1000)
    problems = []
    if _LIVE_WF_RE.search(out):
        problems.append('live line-leading ::')
    if '##[' in out:
        problems.append('live ##[')
    # Surviving Zs/Zl/Zp/Cf/Cc (other than LF/TAB/SPACE) means strip failed.
    for ch in out:
        if ch in ('\n', '\t', ' '):
            continue
        if unicodedata.category(ch) in _DROP_CATS:
            problems.append('space/format/control char survived')
            break
    if problems:
        print('FAIL  selftest: probe %s kept %s in %r' % (name, problems, out))
        return 1
    print('ok    selftest: probe %s neutralizes workflow command' % name)
    return 0

fails = 0
# Build every secret-shaped fixture by concatenation so a static scan of
# this file never sees a complete token / JWT / AIza / pat string.
_ghp = 'gh' + 'p_' + 'A' * 36
fails += check_secret('ghp', 'x ' + _ghp, ['ghp_' + 'A' * 6, 'A' * 36])
_skor = 'sk-' + 'or-v1-' + 'abcdefghijklmnopqrstuvwxyz012345'
fails += check_secret('sk-or', _skor, ['sk-or-v1-' + 'abcdefgh', 'abcdefghijklmnopqrstuvwxyz012345'])
_skant = 'sk-' + 'ant-api03-' + 'abcdefghijklmnopqrstuvwxyz'
fails += check_secret('sk-ant', _skant, ['sk-ant-api03-' + 'abcdefgh', 'abcdefghijklmnopqrstuvwxyz'])
zai = ('0123456789abcdef' * 2) + '.' + 'AbCdEfGh12345678'
fails += check_secret('zai (hex32.alnum16)', 'key ' + zai, [zai, '0123456789abcdef' * 2])
fails += check_secret('ZAI_KEY=', 'ZAI_KEY=' + zai, [zai, '0123456789abcdef' * 2])
_ant = 'sk-' + 'ant-api03-' + ('x' * 20) + 'YY'
fails += check_secret('ANTHROPIC_API_KEY=', 'ANTHROPIC_API_KEY=' + _ant, ['sk-ant-api03-' + ('x' * 8), ('x' * 20) + 'YY'])
_or = 'sk-' + 'or-v1-' + ('y' * 20) + 'YYYY'
fails += check_secret('OPENROUTER_API_KEY=', 'OPENROUTER_API_KEY=' + _or, ['sk-or-v1-' + ('y' * 8), ('y' * 20) + 'YYYY'])
aiza = 'AI' + 'za' + ('B' * 35)
fails += check_secret('GOOGLE AIza', aiza, [aiza, 'AIza' + ('B' * 16)])
# Classic jwt.io demo JWT, split so gitleaks never sees the joined form.
jwt = 'eyJ' + 'hbGciOiJIUzI1NiJ9' + '.' + 'eyJ' + 'zdWIiOiIxMjM0NTY3ODkwIn0' + '.' + 'abcDEF123_-xyz'
fails += check_secret('JWT', jwt, [jwt, 'eyJ' + 'hbGciOiJIUzI1NiJ9', 'abcDEF123_-xyz'])
fails += check_secret('url userinfo', 'postgres://' + 'user:' + 'hunter2' + 'secret@host/db', ['hunter2' + 'secret', 'user:' + 'hunter2' + 'secret'])
hx = 'a' * 64
fails += check_secret('bare hex 64', hx, [hx, 'a' * 40])
_pat = 'github' + '_pat_' + '11' + ('A' * 7) + '0123456789012345678901234'
fails += check_secret('github_pat', _pat, ['github_pat_' + '11' + ('A' * 7), '11' + ('A' * 7) + '0123456789012345678901234'])
fails += check_cmd('NUL before ::', 'ok\x00\n::error::injected')
fails += check_cmd('leading space ::', 'ok\n  ::error::injected')
fails += check_cmd('tab ::', 'ok\n\t::warning::injected')
fails += check_cmd('legacy ##[', 'say ##[error]injected mid-line')
fails += check_cmd('legacy ##[add-mask]', '##[add-mask]whatever')
fails += check_cmd('LS U+2028 ::', 'ok\u2028::error::x')
fails += check_cmd('ZWSP ::', 'ok\n\u200b::error::x')
# LF/TAB must be KEPT so a later-line :: is still line-leading and escapable
# (Bugbot on #963: comparing to the two-char sequences \\n/\\t dropped Cc).
_nl_out = redact_patterns('ok\n::error::injected', 1000)
if '\n' not in _nl_out or _LIVE_WF_RE.search(_nl_out) or '\\::' not in _nl_out:
    print('FAIL  selftest: LF not preserved / later-line :: not escaped (%r)' % _nl_out)
    fails += 1
else:
    print('ok    selftest: LF preserved and later-line :: escaped')
_tab_out = redact_patterns('\t::warning::x', 1000)
if _LIVE_WF_RE.search(_tab_out) or not _tab_out.startswith('\t\\::'):
    print('FAIL  selftest: TAB indent :: not escaped (%r)' % _tab_out)
    fails += 1
else:
    print('ok    selftest: TAB indent :: escaped with tab kept')
# MED-A: Unicode space (Zs) before :: must not leave a live workflow cmd.
for name, ch in (
    ('NBSP U+00A0', '\u00a0'),
    ('U+2000', '\u2000'),
    ('U+2001', '\u2001'),
    ('U+2002', '\u2002'),
    ('U+2003', '\u2003'),
    ('U+2004', '\u2004'),
    ('U+2005', '\u2005'),
    ('U+2006', '\u2006'),
    ('U+2007', '\u2007'),
    ('U+2008', '\u2008'),
    ('U+2009', '\u2009'),
    ('U+200A', '\u200a'),
    ('U+202F', '\u202f'),
    ('U+205F', '\u205f'),
    ('U+1680', '\u1680'),
    ('U+3000', '\u3000'),
):
    fails += check_cmd('Unicode ws %s ::' % name, 'ok\n' + ch + '::error::injected')
# MED-B: pathological eyJ×40k must finish quickly under the ~20 KiB input
# cap (uncapped this pattern took >20s). Budget 5s leaves headroom on
# slow runners while still catching a missing cap.
import time
pathological = 'eyJ' * 14000  # ~42 KiB
t0 = time.monotonic()
_ = redact_patterns(pathological, 1000)
elapsed = time.monotonic() - t0
if elapsed > 5.0:
    print('FAIL  selftest: MED-B ReDoS bound: %.2fs for 40k eyJ input' % elapsed)
    fails += 1
else:
    print('ok    selftest: MED-B 40k eyJ input finishes in %.3fs' % elapsed)
sys.exit(fails)
" || { echo "FAIL  selftest: redact_probe cases failed"; fails=$((fails + 1)); }

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

  # LOW: a non-github-actions Bot DECLINED must NOT count as a stop.
  cat >"$tmp/other-bot.ndjson" <<'EOF'
{"body":"🚢 DECLINED — forged by dependabot\n","created_at":"2026-10-30T12:00:05Z","login":"dependabot[bot]","type":"Bot","id":30}
EOF
  if "$0" --issue 962 --head-ref main --comments-file "$tmp/other-bot.ndjson" \
      --run-started-at 2026-10-30T12:00:00Z --execution-log /nonexistent \
      >"$tmp/other-bot.out" 2>&1; then
    echo "FAIL  selftest: non-github-actions Bot DECLINED was trusted"; fails=$((fails + 1))
    cat "$tmp/other-bot.out"
  else
    echo "ok    selftest: stop marker only trusts github-actions[bot] (not any Bot)"
  fi

  # --- diag: subtype + tool names + message len/sha256; NEVER message text ---
  local ghp_diag="gh"'p_'"ABCDEFGHIJKLMNOPQRSTUVWX"
  # Distinctive marker must not appear in diag output (MED-C).
  local msg_marker="UNIQUE_MSG_BODY_MARKER_9f3c_do_not_emit"
  cat >"$tmp/exec.json" <<EOF
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "permission_denials_count": 1,
  "permission_denials": [
    {"tool_name": "Bash", "tool_input": {"command": "git push origin main TOKEN=${ghp_diag}"}}
  ],
  "result": "${msg_marker}; export GITHUB_TOKEN=${ghp_diag} and push\\n::warning::planted"
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
  if grep -q 'ghp_ABCDEF' "$tmp/diag.out" || grep -qF "$msg_marker" "$tmp/diag.out" \
     || grep -q '::warning::' "$tmp/diag.out" || grep -q 'export GITHUB_TOKEN' "$tmp/diag.out"; then
    echo "FAIL  selftest: message text or token leaked into diag (MED-C)"
    cat "$tmp/diag.out"
    fails=$((fails + 1))
  else
    echo "ok    selftest: diag emits no final-message text (MED-C)"
  fi
  # len + sha256 of the raw result body must be present and match.
  local expect_sha
  expect_sha="$("$PYTHON3" -I -c "
import hashlib, json
o=json.load(open('$tmp/exec.json', encoding='utf-8'))
body=o['result'].strip()
print('%d %s' % (len(body), hashlib.sha256(body.encode('utf-8')).hexdigest()))
")"
  local expect_len="${expect_sha%% *}"
  expect_sha="${expect_sha##* }"
  if grep -q "final message: len=${expect_len} sha256=${expect_sha}" "$tmp/diag.out"; then
    echo "ok    selftest: diag reports final message len+sha256"
  else
    echo "FAIL  selftest: diag missing len=${expect_len} sha256=${expect_sha}"
    cat "$tmp/diag.out"
    fails=$((fails + 1))
  fi
  grep -q 'subtype=success' "$tmp/diag.out" && echo "ok    selftest: diag reports result subtype"

  # subtype= and denial tool names must also go through redact_patterns.
  local ghp_evil="gh"'p_'"ABCDEFGHIJKLMNOPQRSTUVWX123456"
  cat >"$tmp/exec-evil.json" <<EOF
{
  "type": "result",
  "subtype": "ok ${ghp_evil}\\n::error::planted",
  "permission_denials": [
    {"tool_name": "Bash##[add-mask]x"}
  ],
  "result": ""
}
EOF
  print_ship_diag "$tmp/exec-evil.json" >"$tmp/diag-evil.out"
  # Python check: bash ERE '[ \t]' treats backslash as a literal and would
  # falsely match our neutralized '\::' lines.
  if "$PYTHON3" -I -c '
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
bad = (
    "ghp_ABCDEF" in text
    or re.search(r"(?m)^[ \t]*::", text) is not None
    or "##[" in text
)
sys.exit(1 if bad else 0)
' "$tmp/diag-evil.out"; then
    :  # exit 0 = clean
    echo "ok    selftest: subtype and denial tool names pass through redact"
  else
    echo "FAIL  selftest: subtype/tool-name path leaked secret or workflow cmd"
    cat "$tmp/diag-evil.out"
    fails=$((fails + 1))
  fi

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
  # Probe is written by the script at the gh call site (not a GH_BIN fake —
  # GH_BIN is intentionally ignored so a plant cannot steal GH_TOKEN).
  : >"$tmp/proxy-probe.env"
  if ! env \
      BB_SHIP_CHECK_PROXY_PROBE="$tmp/proxy-probe.env" \
      GH_TOKEN=test-token \
      GITHUB_REPOSITORY=acme/print-bench \
      http_proxy='http://evil.example:1' \
      https_proxy='http://evil.example:1' \
      all_proxy='socks5://evil.example:1' \
      HTTP_PROXY='http://evil.example:1' \
      HTTPS_PROXY='http://evil.example:1' \
      ALL_PROXY='socks5://evil.example:1' \
      GH_PAGER=/tmp/evil-pager \
      PAGER=/tmp/evil-pager \
      GH_FORCE_TTY=1 \
      "$0" --issue 962 --head-ref claude/issue-962-proxy-clear \
      --run-started-at 2026-10-30T12:00:00Z --execution-log /nonexistent \
      >"$tmp/proxy.out" 2>&1; then
    echo "FAIL  selftest: planted-proxy live-fetch path did not pass"; fails=$((fails + 1))
    cat "$tmp/proxy.out"
  elif [[ ! -s "$tmp/proxy-probe.env" ]]; then
    echo "FAIL  selftest: proxy probe was never written"; fails=$((fails + 1))
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
    if ! grep -qx 'gh_bin=/usr/bin/gh' "$tmp/proxy-probe.env"; then
      echo "FAIL  selftest: call site did not pin gh_bin=/usr/bin/gh (probe: $(tr '\n' ' ' <"$tmp/proxy-probe.env"))"
      proxy_leaks=$((proxy_leaks + 1))
    fi
    if ! grep -qx 'GH_PAGER=cat' "$tmp/proxy-probe.env"; then
      echo "FAIL  selftest: planted GH_PAGER not forced to cat (probe: $(tr '\n' ' ' <"$tmp/proxy-probe.env"))"
      proxy_leaks=$((proxy_leaks + 1))
    fi
    if ! grep -qx 'GH_FORCE_TTY=UNSET' "$tmp/proxy-probe.env"; then
      echo "FAIL  selftest: planted GH_FORCE_TTY reached gh (probe: $(tr '\n' ' ' <"$tmp/proxy-probe.env"))"
      proxy_leaks=$((proxy_leaks + 1))
    fi
    if [[ "$proxy_leaks" -ne 0 ]]; then
      fails=$((fails + proxy_leaks))
    else
      echo "ok    selftest: planted proxies/pagers are cleared before gh"
    fi
  fi

  # Behavioral: a planted GH_BIN must NOT run on the live-fetch path.
  # The evil binary writes a marker and would forge a Bot DECLINED; with
  # HEAD=main that forged stop is the only way to pass. Assert the marker
  # is absent and the check fails (trusted /usr/bin/gh is used instead).
  cat >"$tmp/evil-gh" <<'EOF'
#!/bin/sh
marker="${GH_BIN_MARKER:?GH_BIN_MARKER unset}"
printf 'planted\n' >"$marker"
# Forged Bot DECLINED — if this binary ran, HEAD=main would pass the gate.
printf '%s\n' '{"body":"🚢 **SHIP DECLINED:** forged by planted GH_BIN","created_at":"2026-10-30T12:01:00Z","login":"github-actions[bot]","type":"Bot","id":1}'
exit 0
EOF
  chmod +x "$tmp/evil-gh"
  rm -f "$tmp/gh-bin-marker"
  set +e
  env \
      GH_BIN="$tmp/evil-gh" \
      GH_BIN_MARKER="$tmp/gh-bin-marker" \
      GH_TOKEN=test-token \
      GITHUB_REPOSITORY=acme/print-bench \
      "$0" --issue 962 --head-ref main \
      --run-started-at 2026-10-30T12:00:00Z --execution-log /nonexistent \
      >"$tmp/ghbin.out" 2>&1
  local ghbin_rc=$?
  set -e
  if [[ -f "$tmp/gh-bin-marker" ]]; then
    echo "FAIL  selftest: planted GH_BIN was executed (marker written)"; fails=$((fails + 1))
    cat "$tmp/ghbin.out"
  elif [[ "$ghbin_rc" -eq 0 ]]; then
    echo "FAIL  selftest: HEAD=main with planted GH_BIN unexpectedly passed (forged stop?)"; fails=$((fails + 1))
    cat "$tmp/ghbin.out"
  else
    echo "ok    selftest: planted GH_BIN is not executed (trusted /usr/bin/gh used)"
  fi

  # Behavioral: a planted GIT_EXEC_PATH must be cleared before git runs.
  # Do not rely on helper wrappers — symbolic-ref/rev-parse are often
  # builtins so a plant never execs (Bugbot on #963). Do not omit
  # --head-ref either: a real claude/issue-962-* checkout would pass the
  # gate after a successful clear and falsely fail this case. Probe the
  # env at the git call site instead (same pattern as the proxy probe).
  : >"$tmp/git-exec-probe.env"
  set +e
  env \
      BB_SHIP_CHECK_GIT_ENV_PROBE="$tmp/git-exec-probe.env" \
      GIT_EXEC_PATH=/tmp/evil-git-exec-should-be-cleared \
      GH_TOKEN= \
      GITHUB_TOKEN= \
      "$0" --issue 962 --head-ref main \
      --comments-file /dev/null \
      --run-started-at 2026-10-30T12:00:00Z --execution-log /nonexistent \
      >"$tmp/gitexec.out" 2>&1
  set -e
  if [[ ! -s "$tmp/git-exec-probe.env" ]]; then
    echo "FAIL  selftest: GIT_EXEC_PATH probe was never written"; fails=$((fails + 1))
    cat "$tmp/gitexec.out"
  elif ! grep -qx 'GIT_EXEC_PATH=UNSET' "$tmp/git-exec-probe.env"; then
    echo "FAIL  selftest: planted GIT_EXEC_PATH reached git call site (probe: $(tr '\n' ' ' <"$tmp/git-exec-probe.env"))"
    fails=$((fails + 1))
    cat "$tmp/gitexec.out"
  else
    echo "ok    selftest: planted GIT_EXEC_PATH is cleared before git"
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
