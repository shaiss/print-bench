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
      kill -TERM -- "-${pgid}" 2>/dev/null || true
    fi
    kill -TERM "$v" 2>/dev/null || true
  done
  sleep 1
  for v in "${victims[@]}"; do
    kill -KILL "$v" 2>/dev/null || true
  done
}

# --- selftest ---------------------------------------------------------------
# Integrity cases stub reap_agent_orphans so an emptied spare set cannot
# massacre the host; they still assert the call site invokes reap and that
# the bundle path can set pending. The happy-path case uses real processes
# and only asserts about an orphan this test spawned.

_bb_pid_snap_assert_integrity() {
  # Args: name warn_regex [rematerialize_extra_arg]
  local name="$1" warn_re="$2" dest="${3:-}"
  local err pending_out rc=0 reap_called=0
  err="$(mktemp "${RUNNER_TEMP}/err.XXXXXX")"
  pending_out="$(mktemp "${RUNNER_TEMP}/pending.XXXXXX")"

  # Stub: prove invoke without scanning /proc under an empty spare set.
  reap_agent_orphans() { reap_called=1; }

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
  if [ "$reap_called" -ne 1 ]; then
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
  echo "selftest[$name]: ok"
}

_bb_pid_snap_selftest() {
  set -euo pipefail
  local repo_root
  repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  # Global (not local): EXIT trap runs after locals are unset under set -u.
  _BB_PID_SNAP_SELFTEST_RT="$(mktemp -d "${TMPDIR:-/tmp}/bb-pid-snap-selftest.XXXXXX")"
  trap 'rm -rf -- "${_BB_PID_SNAP_SELFTEST_RT:-}"' EXIT
  export RUNNER_TEMP="$_BB_PID_SNAP_SELFTEST_RT"

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

  # Happy path: spare snap PIDs; reap a post-snapshot orphan (spoofed comm).
  (
    # shellcheck disable=SC1091
    source "${repo_root}/scripts/backlog-burn-pid-snap.sh"
    snap="$(mktemp "${RUNNER_TEMP}/happy-snap.XXXXXX")"
    orphan_pid_file="$(mktemp "${RUNNER_TEMP}/happy-orphan-pid.XXXXXX")"
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

    reap_agent_orphans

    if kill -0 "$orphan" 2>/dev/null; then
      echo "selftest[happy]: orphan $orphan still alive after reap" >&2
      kill -KILL "$orphan" 2>/dev/null || true
      exit 1
    fi

    pending_out="$(mktemp "${RUNNER_TEMP}/happy-pending.XXXXXX")"
    echo "pending=true" >"$pending_out"
    grep -qx 'pending=true' "$pending_out"
    echo "selftest[happy]: ok (reaped orphan pid=$orphan)"
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
