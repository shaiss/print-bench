#!/usr/bin/env bash
# backlog-burn-pid-snap.sh — rematerialize sealed pre-agent PID snapshot + reap.
#
# Sourced by backlog-burn.yml capture/bundle steps after restore from the
# pre-agent START_SHA pin (never trust the worktree copy after Write/Edit).
# The --selftest below executes the same functions (behavioral, not YAML greps).
#
# Contract (identical to the former inline workflow block):
#   - Rematerialize from PID_SNAP_B64 + PID_SNAP_SHA256 into a private mktemp
#     under RUNNER_TEMP (or into $1 when provided — test hook for symlink case).
#   - On missing/mismatched/non-file/symlink integrity failure: emit
#     ::warning::, empty the spare set, continue (never exit 1 here).
#   - reap_agent_orphans kills every PID not in the spare set, except the
#     reaper, its ancestors, and its process group. No comm/name exemptions.
#
# Usage (workflow, after pin-restore + source):
#   backlog_burn_rematerialize_pid_snap
#   reap_agent_orphans
#
# Usage (selftest):
#   scripts/backlog-burn-pid-snap.sh --selftest

backlog_burn_rematerialize_pid_snap() {
  # Optional $1: destination path (selftest symlink case). Workflow omits it.
  if [ -z "${RUNNER_TEMP:-}" ]; then
    echo "::error::RUNNER_TEMP is empty — cannot rematerialize PID snapshot" >&2
    return 1
  fi
  if [ -n "${1:-}" ]; then
    PID_SNAP="$1"
  else
    PID_SNAP="$(mktemp "${RUNNER_TEMP}/backlog-burn-pre-agent-pids.XXXXXX")"
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
