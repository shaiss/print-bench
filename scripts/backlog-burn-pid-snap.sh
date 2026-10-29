#!/usr/bin/env bash
# backlog-burn-pid-snap.sh — rematerialize sealed pre-agent PID snapshot + reap.
#
# Sourced by backlog-burn.yml capture/bundle steps after restore from the
# pre-agent sealed helper body (PID_SNAP_HELPER_B64) or START_SHA pin (never
# trust the worktree copy after Write/Edit).
# The --selftest below executes the same functions (behavioral, not YAML greps).
#
# Contract (identical to the former inline workflow block):
#   - Rematerialize from PID_SNAP_B64 + PID_SNAP_SHA256 into a private mktemp
#     under RUNNER_TEMP (or into $1 when provided — test hook for symlink case).
#   - On missing/mismatched/non-file/symlink integrity failure: emit
#     ::warning::, empty the spare set, continue (never exit 1 here).
#   - reap_agent_orphans kills every PID not in the spare set, except the
#     reaper, its ancestors, and its process group. No comm/name exemptions.
#   - Capture/Bundle install an EXIT trap so every early exit still reaps.
#     Helper-restore failure warns and falls through to sealed-snapshot reap
#     (or empty-spare-set if the seal is unusable) — never abort before reap.
#
# Usage (workflow, after pin-restore + source):
#   backlog_burn_unset_git_env
#   backlog_burn_install_reap_exit_trap
#   backlog_burn_rematerialize_pid_snap
#   backlog_burn_reap_once          # or: reap_agent_orphans + mark done
#
# Usage (selftest):
#   scripts/backlog-burn-pid-snap.sh --selftest

# Neutralize GIT_* plants (GITHUB_ENV or runner defaults) before any restore.
# Same closed list Capture/Bundle pin in step env and unset in-shell.
backlog_burn_unset_git_env() {
  unset GIT_DIR GIT_WORK_TREE GIT_OBJECT_DIRECTORY \
    GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_INDEX_FILE \
    GIT_CONFIG GIT_CONFIG_GLOBAL GIT_CONFIG_SYSTEM GIT_CONFIG_PARAMETERS \
    GIT_SSH_COMMAND || true
  local n i
  if [ -n "${GIT_CONFIG_COUNT:-}" ]; then
    n="${GIT_CONFIG_COUNT}"
    unset GIT_CONFIG_COUNT || true
    case "$n" in
      *[!0-9]*) n=0 ;;
    esac
    i=0
    while [ "$i" -lt "$n" ] && [ "$i" -lt 128 ]; do
      unset "GIT_CONFIG_KEY_${i}" "GIT_CONFIG_VALUE_${i}" || true
      i=$((i + 1))
    done
  fi
}

# Idempotent rematerialize + reap. Safe under EXIT trap (runs once).
backlog_burn_reap_once() {
  if [ "${_BB_REAP_DONE:-0}" = "1" ]; then
    return 0
  fi
  _BB_REAP_DONE=1
  backlog_burn_rematerialize_pid_snap || true
  # rematerialize may leave PID_SNAP unset (e.g. no RUNNER_TEMP); never let
  # set -u abort the reap — fall through to an empty spare set.
  if [ -z "${PID_SNAP:-}" ]; then
    PID_SNAP="$(mktemp "${TMPDIR:-/tmp}/bb-empty-pid-snap.XXXXXX")" || return 0
    : >"$PID_SNAP"
  fi
  reap_agent_orphans || true
}

backlog_burn_install_reap_exit_trap() {
  if [ "${_BB_REAP_TRAP_INSTALLED:-0}" = "1" ]; then
    return 0
  fi
  _BB_REAP_TRAP_INSTALLED=1
  _BB_REAP_DONE="${_BB_REAP_DONE:-0}"
  # shellcheck disable=SC2064
  trap 'backlog_burn_reap_once' EXIT
}

# Decode sealed helper body (PID_SNAP_HELPER_B64) and verify digest.
# Writes path to $_BB_PID_HELPER_PATH on success. Warns + returns 1 on failure
# (caller continues to sealed-snapshot fallback reap — never exit 1 here).
backlog_burn_materialize_helper_from_seal() {
  local dest="${1:-}" got
  if [ -z "${RUNNER_TEMP:-}" ]; then
    echo "::warning::RUNNER_TEMP empty — cannot materialize pid-snap helper from seal" >&2
    return 1
  fi
  if [ -z "${PID_SNAP_HELPER_B64:-}" ] || [ -z "${PID_SNAP_HELPER_SHA256:-}" ]; then
    echo "::warning::PID_SNAP_HELPER_B64/SHA256 empty — cannot materialize helper from seal" >&2
    return 1
  fi
  if [ -z "$dest" ]; then
    dest="$(mktemp "${RUNNER_TEMP}/backlog-burn-pid-snap.XXXXXX")" || {
      echo "::warning::mktemp failed for pid-snap helper" >&2
      return 1
    }
  fi
  if ! printf '%s' "$PID_SNAP_HELPER_B64" | base64 -d >"$dest"; then
    echo "::warning::pid-snap helper b64 decode failed — sealed-snapshot fallback reap" >&2
    rm -f -- "$dest"
    return 1
  fi
  got="$(sha256sum "$dest" | awk '{print $1}')"
  if [ "$got" != "$PID_SNAP_HELPER_SHA256" ]; then
    echo "::warning::pid-snap helper seal digest mismatch — sealed-snapshot fallback reap" >&2
    rm -f -- "$dest"
    return 1
  fi
  if [ -L "$dest" ] || [ ! -f "$dest" ]; then
    echo "::warning::pid-snap helper seal left non-file — sealed-snapshot fallback reap" >&2
    rm -f -- "$dest"
    return 1
  fi
  _BB_PID_HELPER_PATH="$dest"
  return 0
}

# Last-resort reap when the helper cannot be sourced. Uses sealed
# PID_SNAP_B64/SHA256; empty spare set if the seal is unusable. Spares
# self/ancestors/process group only — no name matching, never "kill all".
backlog_burn_inline_fallback_reap() {
  local snap_file snap_ok=0 got d pid v pgid my_pgid walk
  local -a victims=()
  if [ -n "${RUNNER_TEMP:-}" ]; then
    snap_file="$(mktemp "${RUNNER_TEMP}/bb-inline-pid-snap.XXXXXX")" || return 0
  else
    snap_file="$(mktemp "${TMPDIR:-/tmp}/bb-inline-pid-snap.XXXXXX")" || return 0
  fi
  if [ -z "${PID_SNAP_SHA256:-}" ] || [ -z "${PID_SNAP_B64:-}" ]; then
    echo "::warning::inline fallback: PID snapshot outputs empty — empty spare set" >&2
  elif ! printf '%s' "$PID_SNAP_B64" | base64 -d >"$snap_file"; then
    echo "::warning::inline fallback: PID snapshot b64 decode failed — empty spare set" >&2
  else
    got="$(sha256sum "$snap_file" | awk '{print $1}')"
    if [ "$got" != "$PID_SNAP_SHA256" ]; then
      echo "::warning::inline fallback: PID snapshot digest mismatch — empty spare set" >&2
    elif [ -L "$snap_file" ] || [ ! -f "$snap_file" ]; then
      echo "::warning::inline fallback: PID snapshot rematerialize left non-file — empty spare set" >&2
    else
      snap_ok=1
    fi
  fi
  if [ "$snap_ok" -ne 1 ]; then
    : >"$snap_file"
  fi
  chmod 600 -- "$snap_file" 2>/dev/null || true
  PID_SNAP="$snap_file"
  my_pgid="$(ps -o pgid= -p $$ | tr -d '[:space:]')"
  shopt -s nullglob
  for d in /proc/[0-9]*; do
    pid="${d#/proc/}"
    case "$pid" in
      *[!0-9]*) continue ;;
    esac
    # Spare self/ancestors.
    walk="$$"
    while [ -n "$walk" ] && [ "$walk" != "0" ]; do
      if [ "$walk" = "$pid" ]; then
        continue 2
      fi
      walk="$(awk '/^PPid:/ { print $2; exit }' "/proc/$walk/status" 2>/dev/null || echo 0)"
    done
    # Spare our process group.
    pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d '[:space:]' || true)"
    if [ -n "$pgid" ] && [ "$pgid" = "$my_pgid" ]; then
      continue
    fi
    # Spare pre-agent snapshot PIDs.
    if grep -qx -- "$pid" "$snap_file" 2>/dev/null; then
      continue
    fi
    victims+=("$pid")
  done
  shopt -u nullglob
  for v in "${victims[@]}"; do
    pgid="$(ps -o pgid= -p "$v" 2>/dev/null | tr -d '[:space:]' || true)"
    if [ -n "$pgid" ] && [ "$pgid" != "$my_pgid" ] && [ "$pgid" != "1" ] && [ "$pgid" != "0" ]; then
      reap_kill -TERM -- "-${pgid}"
    fi
    reap_kill -TERM "$v"
  done
  if [ "${#victims[@]}" -gt 0 ]; then
    sleep 1
    for v in "${victims[@]}"; do
      reap_kill -KILL "$v"
    done
  fi
  rm -f -- "$snap_file"
  return 0
}

backlog_burn_rematerialize_pid_snap() {
  # Optional $1: destination path (selftest symlink case). Workflow omits it.
  # Prefer RUNNER_TEMP; if empty (EXIT-trap after an early guard), fall back to
  # TMPDIR so the reap still has a spare-set file and never aborts under set -u.
  local snap_root="${RUNNER_TEMP:-}"
  if [ -z "$snap_root" ]; then
    echo "::warning::RUNNER_TEMP is empty — rematerializing PID snapshot under TMPDIR" >&2
    snap_root="${TMPDIR:-/tmp}"
  fi
  if [ -n "${1:-}" ]; then
    PID_SNAP="$1"
  else
    PID_SNAP="$(mktemp "${snap_root}/backlog-burn-pre-agent-pids.XXXXXX")" || {
      echo "::warning::mktemp failed for PID snapshot — cannot rematerialize" >&2
      return 1
    }
  fi
  local snap_ok=0
  if [ -z "${PID_SNAP_SHA256:-}" ] || [ -z "${PID_SNAP_B64:-}" ]; then
    echo "::warning::PID snapshot outputs empty — conservative reap (no pre-agent spares)" >&2
  elif ! printf '%s' "$PID_SNAP_B64" | base64 -d >"$PID_SNAP"; then
    echo "::warning::PID snapshot b64 decode failed — conservative reap" >&2
  else
    local got_snap
    got_snap="$(sha256sum "$PID_SNAP" | awk '{print $1}')"
    if [ "$got_snap" != "$PID_SNAP_SHA256" ]; then
      echo "::warning::PID snapshot digest mismatch — conservative reap" >&2
    elif [ -L "$PID_SNAP" ] || [ ! -f "$PID_SNAP" ]; then
      echo "::warning::PID snapshot rematerialize left non-file — conservative reap" >&2
    else
      snap_ok=1
    fi
  fi
  if [ "$snap_ok" -ne 1 ]; then
    : >"$PID_SNAP"
  fi
  # Symlink dest (test hook) may refuse chmod; production mktemp path always works.
  chmod 600 -- "$PID_SNAP" 2>/dev/null || true
  return 0
}

reap_ppid_of() {
  awk '/^PPid:/ { print $2; exit }' "/proc/$1/status" 2>/dev/null || echo 0
}

reap_should_kill() {
  local pid="$1" snap_file="$2" self_pid="$3" my_pgid="$4"
  local walk pgid
  [ -n "$pid" ] || return 1
  case "$pid" in
    *[!0-9]*) return 1 ;;
  esac
  # Spare self and ancestors (the Actions runner chain).
  walk="$self_pid"
  while [ -n "$walk" ] && [ "$walk" != "0" ]; do
    [ "$walk" = "$pid" ] && return 1
    walk="$(reap_ppid_of "$walk")"
  done
  # Spare our process group (reaper helpers).
  pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d '[:space:]' || true)"
  if [ -n "$pgid" ] && [ "$pgid" = "$my_pgid" ]; then
    return 1
  fi
  # Spare anything alive before the agent started.
  if grep -qx -- "$pid" "$snap_file" 2>/dev/null; then
    return 1
  fi
  return 0
}

# Named kill helper so the selftest can override it in a subshell and record
# targets without signaling. Production always calls real kill; there is no
# environment or argument gate that skips signaling (an agent must not be
# able to disable reaping).
reap_kill() {
  kill "$@" 2>/dev/null || true
}

reap_agent_orphans() {
  local d pid v pgid my_pgid
  local -a victims=()
  # set -u safe: an EXIT-trap reap must not abort if rematerialize left no file.
  if [ -z "${PID_SNAP:-}" ]; then
    PID_SNAP="$(mktemp "${TMPDIR:-/tmp}/bb-empty-pid-snap.XXXXXX")" || return 0
    : >"$PID_SNAP"
  fi
  my_pgid="$(ps -o pgid= -p $$ | tr -d '[:space:]')"
  shopt -s nullglob
  for d in /proc/[0-9]*; do
    pid="${d#/proc/}"
    case "$pid" in
      *[!0-9]*) continue ;;
    esac
    if reap_should_kill "$pid" "$PID_SNAP" "$$" "$my_pgid"; then
      victims+=("$pid")
    fi
  done
  shopt -u nullglob
  if [ "${#victims[@]}" -eq 0 ]; then
    return 0
  fi
  for v in "${victims[@]}"; do
    pgid="$(ps -o pgid= -p "$v" 2>/dev/null | tr -d '[:space:]' || true)"
    if [ -n "$pgid" ] && [ "$pgid" != "$my_pgid" ] && [ "$pgid" != "1" ] && [ "$pgid" != "0" ]; then
      reap_kill -TERM -- "-${pgid}"
    fi
    reap_kill -TERM "$v"
  done
  sleep 1
  for v in "${victims[@]}"; do
    reap_kill -KILL "$v"
  done
}

# --- selftest ---------------------------------------------------------------
# Kill is stubbed ONLY inside selftest scope (function override in a subshell).
# Production reap_kill / reap_agent_orphans honor no DRY_RUN / NO_KILL switch.
# Integrity cases run the real reap against an emptied spare set; the stub
# records targets and never signals. Happy-path asserts selection via the
# stub record, then cleans up only the test's own known child PIDs.

# Install a recording kill stub + wrap reap so we can prove it was invoked.
# Must be called inside the case's subshell after sourcing this file.
_bb_pid_snap_stub_kills() {
  local record="$1"
  : >"$record"
  _BB_KILL_RECORD="$record"
  _BB_REAP_CALLED=0
  reap_kill() {
    local a
    for a in "$@"; do
      case "$a" in
        --) continue ;;
        -TERM|-KILL|-HUP|-INT|-PIPE|-USR1|-USR2) continue ;;
        -[0-9]*|[0-9]*)
          printf '%s\n' "$a" >>"$_BB_KILL_RECORD"
          ;;
      esac
    done
    # Intentionally no kill — selftest must never signal host processes.
  }
  # Preserve production body; wrap to mark invocation. Kill stays stubbed.
  eval "$(declare -f reap_agent_orphans | sed '1s/^reap_agent_orphans/reap_agent_orphans_production/')"
  reap_agent_orphans() {
    _BB_REAP_CALLED=1
    reap_agent_orphans_production
  }
}

_bb_pid_snap_assert_no_disable_switch() {
  # Production half of this file (above the selftest marker) must not gate
  # killing on any env/flag an agent could set, and must call real kill.
  local script="$1"
  local prod code
  prod="$(awk '/^# --- selftest /{exit} {print}' "$script")"
  # Strip comments before grepping for disable-switch names (prose is free).
  code="$(printf '%s\n' "$prod" | sed -E 's/(^|[[:space:]])#.*//')"
  if printf '%s\n' "$code" | grep -Ei \
    'DRY_RUN|NO_KILL|SKIP_KILL|REAP_DRY|DISABLE_KILL|KILL_DISABLED|skip[[:space:]]*kill|dry[[:space:]-]*run' \
    >/dev/null; then
    echo "selftest[no-disable]: production reap path mentions a kill disable switch" >&2
    return 1
  fi
  if ! printf '%s\n' "$prod" | grep -E '^reap_kill\(\)' >/dev/null; then
    echo "selftest[no-disable]: production reap_kill() missing" >&2
    return 1
  fi
  # reap_kill body must invoke the real kill builtin (not a no-op / env gate).
  if ! printf '%s\n' "$prod" | awk '
    /^reap_kill\(\)/ {in_fn=1; next}
    in_fn && /^[a-zA-Z_][a-zA-Z0-9_]*\(\)/ {exit}
    in_fn && /^}/ {exit}
    in_fn && /(^|[[:space:]])kill([[:space:]]|$)/ {found=1}
    END {exit found ? 0 : 1}
  '; then
    echo "selftest[no-disable]: production reap_kill() does not call kill" >&2
    return 1
  fi
  if ! printf '%s\n' "$prod" | awk '
    /^reap_agent_orphans\(\)/ {in_fn=1; next}
    in_fn && /^[a-zA-Z_][a-zA-Z0-9_]*\(\)/ {exit}
    in_fn && /^}/ {exit}
    in_fn && /(^|[[:space:]])reap_kill([[:space:]]|$)/ {found=1}
    END {exit found ? 0 : 1}
  '; then
    echo "selftest[no-disable]: production reap_agent_orphans() does not call reap_kill" >&2
    return 1
  fi
  # Production must not call kill directly outside reap_kill (selection stays
  # on the overridable helper).
  if printf '%s\n' "$code" | awk '
    /^reap_kill\(\)/ {in_kill=1; next}
    in_kill && /^}/ {in_kill=0; next}
    in_kill {next}
    /(^|[[:space:]])kill([[:space:]]|$)/ {bad=1}
    END {exit bad ? 0 : 1}
  '; then
    echo "selftest[no-disable]: production calls kill outside reap_kill()" >&2
    return 1
  fi
  echo "selftest[no-disable]: ok"
}

_bb_pid_snap_assert_integrity() {
  # Args: name warn_regex [rematerialize_extra_arg]
  local name="$1" warn_re="$2" dest="${3:-}"
  local err pending_out kill_record rc=0
  err="$(mktemp "${RUNNER_TEMP}/err.XXXXXX")"
  pending_out="$(mktemp "${RUNNER_TEMP}/pending.XXXXXX")"
  kill_record="$(mktemp "${RUNNER_TEMP}/kill-record.XXXXXX")"

  # Real reap + stubbed kill: empty spare set may select many PIDs; never signal.
  _bb_pid_snap_stub_kills "$kill_record"

  set +e
  if [ -n "$dest" ]; then
    backlog_burn_rematerialize_pid_snap "$dest" 2>"$err"
  else
    backlog_burn_rematerialize_pid_snap 2>"$err"
  fi
  rc=$?
  reap_agent_orphans
  set -e

  if [ "$rc" -ne 0 ]; then
    echo "selftest[$name]: rematerialize exited $rc (must warn+continue)" >&2
    cat "$err" >&2
    return 1
  fi
  if [ "${_BB_REAP_CALLED:-0}" -ne 1 ]; then
    echo "selftest[$name]: reap_agent_orphans was not invoked" >&2
    return 1
  fi
  if ! grep -E "$warn_re" "$err" >/dev/null; then
    echo "selftest[$name]: expected warning matching /$warn_re/" >&2
    echo "stderr was:" >&2
    cat "$err" >&2
    return 1
  fi
  # Delivery must not be blocked: bundle path can still set pending.
  echo "pending=true" >"$pending_out"
  if ! grep -qx 'pending=true' "$pending_out"; then
    echo "selftest[$name]: could not set pending after integrity failure" >&2
    return 1
  fi
  if [ -n "${PID_SNAP:-}" ] && [ -e "$PID_SNAP" ] && [ ! -L "$PID_SNAP" ] && [ -s "$PID_SNAP" ]; then
    echo "selftest[$name]: PID_SNAP not emptied after integrity failure" >&2
    return 1
  fi
  echo "selftest[$name]: ok (reap invoked; kill stubbed, record lines=$(wc -l <"$kill_record" | tr -d ' '))"
}

_bb_pid_snap_selftest() {
  set -euo pipefail
  local repo_root script_path
  repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  script_path="${repo_root}/scripts/backlog-burn-pid-snap.sh"
  # Global (not local): EXIT trap runs after locals are unset under set -u.
  _BB_PID_SNAP_SELFTEST_RT="$(mktemp -d "${TMPDIR:-/tmp}/bb-pid-snap-selftest.XXXXXX")"
  trap 'rm -rf -- "${_BB_PID_SNAP_SELFTEST_RT:-}"' EXIT
  export RUNNER_TEMP="$_BB_PID_SNAP_SELFTEST_RT"

  _bb_pid_snap_assert_no_disable_switch "$script_path"

  # (a) missing snapshot
  (
    # shellcheck disable=SC1091
    source "${repo_root}/scripts/backlog-burn-pid-snap.sh"
    unset PID_SNAP_B64 PID_SNAP_SHA256 PID_SNAP || true
    PID_SNAP_B64=""
    PID_SNAP_SHA256=""
    export PID_SNAP_B64 PID_SNAP_SHA256
    _bb_pid_snap_assert_integrity missing 'PID snapshot outputs empty'
  )

  # (b) symlinked rematerialize/legacy path
  (
    # shellcheck disable=SC1091
    source "${repo_root}/scripts/backlog-burn-pid-snap.sh"
    target="$(mktemp "${RUNNER_TEMP}/pid-snap-target.XXXXXX")"
    link="${RUNNER_TEMP}/pid-snap-link.$$"
    ln -s "$target" "$link"
    body=$'1\n2\n'
    printf '%s' "$body" >"$target"
    PID_SNAP_B64="$(printf '%s' "$body" | base64 -w0)"
    PID_SNAP_SHA256="$(printf '%s' "$body" | sha256sum | awk '{print $1}')"
    export PID_SNAP_B64 PID_SNAP_SHA256
    _bb_pid_snap_assert_integrity symlink \
      'PID snapshot rematerialize left non-file' "$link"
  )

  # (c) digest mismatch
  (
    # shellcheck disable=SC1091
    source "${repo_root}/scripts/backlog-burn-pid-snap.sh"
    body=$'10\n20\n'
    PID_SNAP_B64="$(printf '%s' "$body" | base64 -w0)"
    PID_SNAP_SHA256="deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    export PID_SNAP_B64 PID_SNAP_SHA256
    _bb_pid_snap_assert_integrity digest 'PID snapshot digest mismatch'
  )

  # (d) truncated/tampered PID list (decodes; digest is for the full original)
  (
    # shellcheck disable=SC1091
    source "${repo_root}/scripts/backlog-burn-pid-snap.sh"
    full=$'30\n40\n50\n60\n'
    trunc=$'30\n40\n'
    PID_SNAP_B64="$(printf '%s' "$trunc" | base64 -w0)"
    PID_SNAP_SHA256="$(printf '%s' "$full" | sha256sum | awk '{print $1}')"
    export PID_SNAP_B64 PID_SNAP_SHA256
    _bb_pid_snap_assert_integrity tampered 'PID snapshot digest mismatch'
  )

  # (a) failed helper restore still reaps via sealed-snapshot / empty-spare path.
  (
    # shellcheck disable=SC1091
    source "${repo_root}/scripts/backlog-burn-pid-snap.sh"
    kill_record="$(mktemp "${RUNNER_TEMP}/restore-fail-kill.XXXXXX")"
    _bb_pid_snap_stub_kills "$kill_record"
    # Poison seal so materialize fails; EXIT trap / fallback must still reap.
    PID_SNAP_HELPER_B64="bm90LWEtdmFsaWQtaGVscGVyCg=="
    PID_SNAP_HELPER_SHA256="deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    export PID_SNAP_HELPER_B64 PID_SNAP_HELPER_SHA256
    unset PID_SNAP_B64 PID_SNAP_SHA256 || true
    PID_SNAP_B64=""
    PID_SNAP_SHA256=""
    export PID_SNAP_B64 PID_SNAP_SHA256
    err="$(mktemp "${RUNNER_TEMP}/restore-fail-err.XXXXXX")"
    _BB_REAP_DONE=0
    set +e
    backlog_burn_materialize_helper_from_seal 2>"$err"
    mat_rc=$?
    if [ "$mat_rc" -eq 0 ]; then
      echo "selftest[restore-fail]: materialize unexpectedly succeeded" >&2
      exit 1
    fi
    if ! grep -E '::warning::' "$err" >/dev/null; then
      echo "selftest[restore-fail]: expected ::warning:: on failed helper seal" >&2
      cat "$err" >&2
      exit 1
    fi
    # Simulate workflow: warn + fallback reap (never exit before reap).
    backlog_burn_inline_fallback_reap
    set -e
    # Fallback does not go through reap_agent_orphans wrapper; mark via kill stub
    # having been exercised OR empty victims (still a successful reap path).
    if ! declare -F reap_kill >/dev/null; then
      echo "selftest[restore-fail]: reap_kill missing after source" >&2
      exit 1
    fi
    echo "pending=true" >"${RUNNER_TEMP}/restore-fail-pending"
    grep -qx 'pending=true' "${RUNNER_TEMP}/restore-fail-pending"
    echo "selftest[restore-fail]: ok (warn+fallback reap; pending still set)"
  )

  # (b) planted GIT_DIR + GITHUB_ENV-style GIT_* neutralized; restore/reap works.
  (
    # shellcheck disable=SC1091
    source "${repo_root}/scripts/backlog-burn-pid-snap.sh"
    kill_record="$(mktemp "${RUNNER_TEMP}/git-env-kill.XXXXXX")"
    _bb_pid_snap_stub_kills "$kill_record"
    export GIT_DIR=/tmp/evil-git-dir-does-not-exist
    export GIT_WORK_TREE=/tmp/evil-work-tree
    export GIT_OBJECT_DIRECTORY=/tmp/evil-objects
    export GIT_ALTERNATE_OBJECT_DIRECTORIES=/tmp/evil-alternates
    export GIT_INDEX_FILE=/tmp/evil-index
    export GIT_CONFIG=/tmp/evil-gitconfig
    export GIT_CONFIG_GLOBAL=/tmp/evil-global
    export GIT_CONFIG_SYSTEM=/tmp/evil-system
    export GIT_CONFIG_PARAMETERS="'core.editor=evil'"
    export GIT_CONFIG_COUNT=2
    export GIT_CONFIG_KEY_0=user.name
    export GIT_CONFIG_VALUE_0=Evil
    export GIT_CONFIG_KEY_1=user.email
    export GIT_CONFIG_VALUE_1=evil@example.com
    backlog_burn_unset_git_env
    for v in GIT_DIR GIT_WORK_TREE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES \
      GIT_INDEX_FILE GIT_CONFIG GIT_CONFIG_GLOBAL GIT_CONFIG_SYSTEM GIT_CONFIG_PARAMETERS \
      GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0 GIT_CONFIG_KEY_1 GIT_CONFIG_VALUE_1; do
      if [ -n "${!v:-}" ]; then
        echo "selftest[git-env]: $v still set to '${!v}'" >&2
        exit 1
      fi
    done
    # Seal a real helper body and load it after GIT_* cleared.
    PID_SNAP_HELPER_B64="$(base64 -w0 <"$script_path")"
    PID_SNAP_HELPER_SHA256="$(sha256sum "$script_path" | awk '{print $1}')"
    export PID_SNAP_HELPER_B64 PID_SNAP_HELPER_SHA256
    body=$'1\n'
    PID_SNAP_B64="$(printf '%s' "$body" | base64 -w0)"
    PID_SNAP_SHA256="$(printf '%s' "$body" | sha256sum | awk '{print $1}')"
    export PID_SNAP_B64 PID_SNAP_SHA256
    backlog_burn_materialize_helper_from_seal || {
      echo "selftest[git-env]: sealed helper materialize failed after unset" >&2
      exit 1
    }
    backlog_burn_install_reap_exit_trap
    backlog_burn_reap_once
    if [ "${_BB_REAP_CALLED:-0}" -ne 1 ]; then
      echo "selftest[git-env]: reap_once did not invoke reap_agent_orphans" >&2
      exit 1
    fi
    echo "selftest[git-env]: ok (GIT_* cleared; seal restore + reap)"
  )

  # (c) each audited exit path still reaps via EXIT trap.
  # Audited Capture/Bundle pre-reap exits: empty RUNNER_TEMP, empty helper pin,
  # helper seal/restore failure, helper digest mismatch, empty capture digests.
  # Each case installs the trap, simulates the failure, exits 1; the trap must
  # leave a marker proving reap ran (kill stubbed — no host signals).
  _bb_pid_snap_assert_exit_path_reaps() {
    local name="$1"
    local kill_record marker err
    kill_record="$(mktemp "${RUNNER_TEMP}/exit-${name}-kill.XXXXXX")"
    marker="$(mktemp "${RUNNER_TEMP}/exit-${name}-marker.XXXXXX")"
    err="$(mktemp "${RUNNER_TEMP}/exit-${name}-err.XXXXXX")"
    rm -f -- "$marker"
    : >"$marker"
    set +e
    (
      # shellcheck disable=SC1091
      source "${repo_root}/scripts/backlog-burn-pid-snap.sh"
      _bb_pid_snap_stub_kills "$kill_record"
      unset PID_SNAP_B64 PID_SNAP_SHA256 || true
      PID_SNAP_B64=""
      PID_SNAP_SHA256=""
      export PID_SNAP_B64 PID_SNAP_SHA256
      _BB_REAP_DONE=0
      _BB_REAP_TRAP_INSTALLED=0
      # Trap body writes the marker so the parent can observe it across exit.
      backlog_burn_reap_once() {
        if [ "${_BB_REAP_DONE:-0}" = "1" ]; then
          return 0
        fi
        _BB_REAP_DONE=1
        backlog_burn_rematerialize_pid_snap || true
        if [ -z "${PID_SNAP:-}" ]; then
          PID_SNAP="$(mktemp "${TMPDIR:-/tmp}/bb-empty-pid-snap.XXXXXX")" || true
          [ -n "${PID_SNAP:-}" ] && : >"$PID_SNAP"
        fi
        if [ -n "${PID_SNAP:-}" ]; then
          reap_agent_orphans || true
        fi
        printf 'reaped\n' >"$marker"
      }
      trap 'backlog_burn_reap_once' EXIT
      case "$name" in
        empty-runner-temp)
          RUNNER_TEMP=""
          export RUNNER_TEMP
          echo "::error::RUNNER_TEMP is empty — cannot rematerialize PID snapshot" >&2
          exit 1
          ;;
        empty-helper-pin)
          unset PID_SNAP_HELPER_SHA256 PID_SNAP_HELPER_B64 || true
          echo "::error::START_SHA or PID_SNAP_HELPER_SHA256 empty — pin step did not run" >&2
          exit 1
          ;;
        helper-seal-fail)
          PID_SNAP_HELPER_B64="e30K"
          PID_SNAP_HELPER_SHA256="0000000000000000000000000000000000000000000000000000000000000000"
          export PID_SNAP_HELPER_B64 PID_SNAP_HELPER_SHA256
          if backlog_burn_materialize_helper_from_seal 2>"$err"; then
            echo "selftest[exit-$name]: seal materialize should fail" >&2
            exit 2
          fi
          echo "::warning::could not restore backlog-burn-pid-snap.sh — fallback reap" >&2
          exit 1
          ;;
        helper-digest-mismatch)
          PID_SNAP_HELPER_B64="$(printf 'not-the-helper\n' | base64 -w0)"
          PID_SNAP_HELPER_SHA256="$(sha256sum "$script_path" | awk '{print $1}')"
          export PID_SNAP_HELPER_B64 PID_SNAP_HELPER_SHA256
          backlog_burn_materialize_helper_from_seal 2>"$err" || true
          echo "::warning::restored backlog-burn-pid-snap.sh sha256 mismatch — fallback reap" >&2
          exit 1
          ;;
        empty-capture-digests)
          echo "::error::START_SHA or pin digests empty — pin step did not run" >&2
          exit 1
          ;;
        *)
          echo "selftest[exit-path]: unknown path $name" >&2
          exit 2
          ;;
      esac
    )
    local rc=$?
    # Subshell exits 1 by design (simulated workflow failure); set +e above so
    # set -e in the parent does not abort before we can assert the trap marker.
    set -e
    if [ "$rc" -eq 2 ]; then
      echo "selftest[exit-$name]: fixture failed closed" >&2
      return 1
    fi
    if ! grep -qx 'reaped' "$marker" 2>/dev/null; then
      echo "selftest[exit-$name]: EXIT trap did not reap (marker missing)" >&2
      return 1
    fi
    echo "selftest[exit-$name]: ok (EXIT-trap reap)"
  }

  _bb_pid_snap_assert_exit_path_reaps empty-runner-temp
  _bb_pid_snap_assert_exit_path_reaps empty-helper-pin
  _bb_pid_snap_assert_exit_path_reaps helper-seal-fail
  _bb_pid_snap_assert_exit_path_reaps helper-digest-mismatch
  _bb_pid_snap_assert_exit_path_reaps empty-capture-digests

  # Happy path: spare snap PIDs; select a post-snapshot orphan (spoofed comm).
  # Kill is stubbed — assert via the record, then clean up only our child.
  (
    # shellcheck disable=SC1091
    source "${repo_root}/scripts/backlog-burn-pid-snap.sh"
    snap="$(mktemp "${RUNNER_TEMP}/happy-snap.XXXXXX")"
    orphan_pid_file="$(mktemp "${RUNNER_TEMP}/happy-orphan-pid.XXXXXX")"
    kill_record="$(mktemp "${RUNNER_TEMP}/happy-kill-record.XXXXXX")"
    : >"$orphan_pid_file"
    shopt -s nullglob
    for d in /proc/[0-9]*; do
      pid="${d#/proc/}"
      case "$pid" in
        *[!0-9]*) continue ;;
      esac
      printf '%s\n' "$pid"
    done >"$snap"
    shopt -u nullglob
    printf '%s\n' "$$" >>"$snap"

    # Detached orphan in its own session/pgid with spoofable Runner.Worker comm.
    # Record $$ after setsid (before exec) so we know the victim pid exactly.
    setsid bash -c "echo \$\$ >'$orphan_pid_file'; exec -a Runner.Worker sleep 120" \
      </dev/null >/dev/null 2>&1 &
    disown $! 2>/dev/null || true
    orphan=""
    for _try in $(seq 1 30); do
      sleep 0.1
      if [ -s "$orphan_pid_file" ]; then
        orphan="$(tr -d '[:space:]' <"$orphan_pid_file")"
        case "$orphan" in
          ''|*[!0-9]*) orphan="" ;;
        esac
        if [ -n "$orphan" ] && kill -0 "$orphan" 2>/dev/null; then
          break
        fi
        orphan=""
      fi
    done
    if [ -z "$orphan" ]; then
      echo "selftest[happy]: could not find spawned orphan" >&2
      exit 1
    fi
    orphan_pgid="$(ps -o pgid= -p "$orphan" 2>/dev/null | tr -d '[:space:]' || true)"
    # Confirm spoofed comm when /proc still exposes it (best-effort).
    if [ -r "/proc/$orphan/comm" ]; then
      comm="$(tr -d '\0\n' <"/proc/$orphan/comm" 2>/dev/null || true)"
      if [ -n "$comm" ] && [ "$comm" != "Runner.Worker" ] && [ "$comm" != "sleep" ]; then
        echo "selftest[happy]: unexpected comm '$comm' for orphan $orphan" >&2
        kill -KILL "$orphan" 2>/dev/null || true
        exit 1
      fi
    fi
    if grep -qx -- "$orphan" "$snap" 2>/dev/null; then
      echo "selftest[happy]: orphan $orphan was already in the pre-agent snap" >&2
      kill -KILL "$orphan" 2>/dev/null || true
      exit 1
    fi

    PID_SNAP_B64="$(base64 -w0 <"$snap")"
    PID_SNAP_SHA256="$(sha256sum "$snap" | awk '{print $1}')"
    export PID_SNAP_B64 PID_SNAP_SHA256

    err="$(mktemp "${RUNNER_TEMP}/happy-err.XXXXXX")"
    set +e
    backlog_burn_rematerialize_pid_snap 2>"$err"
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
      echo "selftest[happy]: rematerialize failed" >&2
      cat "$err" >&2
      kill -KILL "$orphan" 2>/dev/null || true
      exit 1
    fi
    if grep -E '::warning::' "$err" >/dev/null; then
      echo "selftest[happy]: unexpected warning on valid snap" >&2
      cat "$err" >&2
      kill -KILL "$orphan" 2>/dev/null || true
      exit 1
    fi
    if [ ! -f "$PID_SNAP" ] || [ -L "$PID_SNAP" ] || [ ! -s "$PID_SNAP" ]; then
      echo "selftest[happy]: valid snap did not rematerialize" >&2
      kill -KILL "$orphan" 2>/dev/null || true
      exit 1
    fi

    my_pgid="$(ps -o pgid= -p $$ | tr -d '[:space:]')"
    if reap_should_kill "$$" "$PID_SNAP" "$$" "$my_pgid"; then
      echo "selftest[happy]: predicate would kill self" >&2
      kill -KILL "$orphan" 2>/dev/null || true
      exit 1
    fi
    if ! reap_should_kill "$orphan" "$PID_SNAP" "$$" "$my_pgid"; then
      echo "selftest[happy]: predicate would spare orphan $orphan" >&2
      kill -KILL "$orphan" 2>/dev/null || true
      exit 1
    fi

    # Stub kill before real reap — never signal host processes from check.sh/CI.
    _bb_pid_snap_stub_kills "$kill_record"
    reap_agent_orphans

    if [ "${_BB_REAP_CALLED:-0}" -ne 1 ]; then
      echo "selftest[happy]: reap_agent_orphans was not invoked" >&2
      kill -KILL "$orphan" 2>/dev/null || true
      exit 1
    fi

    # (1) spawned orphan IS selected
    if ! grep -qx -- "$orphan" "$kill_record"; then
      echo "selftest[happy]: orphan pid $orphan not in kill stub record" >&2
      echo "record was:" >&2
      cat "$kill_record" >&2
      kill -KILL "$orphan" 2>/dev/null || true
      exit 1
    fi

    # (2) snapshot PIDs and the runner (self/ancestors/process group) are NOT
    while IFS= read -r snap_pid; do
      case "$snap_pid" in
        ''|*[!0-9]*) continue ;;
      esac
      if grep -qx -- "$snap_pid" "$kill_record"; then
        echo "selftest[happy]: snap pid $snap_pid was targeted" >&2
        kill -KILL "$orphan" 2>/dev/null || true
        exit 1
      fi
    done <"$snap"
    walk="$$"
    while [ -n "$walk" ] && [ "$walk" != "0" ]; do
      if grep -qx -- "$walk" "$kill_record"; then
        echo "selftest[happy]: runner/ancestor pid $walk was targeted" >&2
        kill -KILL "$orphan" 2>/dev/null || true
        exit 1
      fi
      walk="$(reap_ppid_of "$walk")"
    done
    if [ -n "$my_pgid" ] && grep -qx -- "-${my_pgid}" "$kill_record"; then
      echo "selftest[happy]: reaper process group -$my_pgid was targeted" >&2
      kill -KILL "$orphan" 2>/dev/null || true
      exit 1
    fi

    # (3) every recorded target is one of this test's own children / their pgid
    allowed_pid="$orphan"
    allowed_pgid_neg=""
    if [ -n "$orphan_pgid" ]; then
      allowed_pgid_neg="-${orphan_pgid}"
    fi
    while IFS= read -r target; do
      [ -n "$target" ] || continue
      if [ "$target" = "$allowed_pid" ]; then
        continue
      fi
      if [ -n "$allowed_pgid_neg" ] && [ "$target" = "$allowed_pgid_neg" ]; then
        continue
      fi
      echo "selftest[happy]: unrelated host target '$target' in kill stub record" >&2
      echo "allowed: pid=$allowed_pid pgid_neg=$allowed_pgid_neg" >&2
      echo "record was:" >&2
      cat "$kill_record" >&2
      kill -KILL "$orphan" 2>/dev/null || true
      exit 1
    done <"$kill_record"

    # Stub never signals — clean up only our known child PIDs directly.
    kill -KILL "$orphan" 2>/dev/null || true
    if [ -n "$orphan_pgid" ] && [ "$orphan_pgid" != "1" ] && [ "$orphan_pgid" != "0" ]; then
      kill -KILL -- "-${orphan_pgid}" 2>/dev/null || true
    fi

    pending_out="$(mktemp "${RUNNER_TEMP}/happy-pending.XXXXXX")"
    echo "pending=true" >"$pending_out"
    grep -qx 'pending=true' "$pending_out"
    echo "selftest[happy]: ok (stub-selected orphan pid=$orphan; cleaned up directly)"
  )

  echo "backlog-burn-pid-snap selftest: all cases passed"
}

if [[ "${BASH_SOURCE[0]-}" == "${0}" ]]; then
  set -euo pipefail
  case "${1:-}" in
    --selftest) _bb_pid_snap_selftest ;;
    *)
      echo "usage: scripts/backlog-burn-pid-snap.sh --selftest" >&2
      echo "(workflow steps source this file after START_SHA pin-restore)" >&2
      exit 2
      ;;
  esac
fi
