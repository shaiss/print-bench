#!/usr/bin/env bash
# Hardened START_SHA restore + exec of the Claude / sandbox-runtime pin
# verifiers (Cipher MED-1 follow-up on #876).
#
# Trusted preflight (start_ref) records sha256 digests of
# verify-claude-code-pin.sh and verify-sandbox-runtime-pin.sh into step
# outputs before any agent runs. This script — itself restored from
# START_SHA and digest-checked by the calling workflow step — then:
#   1. blanks GIT_* overrides and refuses object alternates
#   2. reaps leftover agent children (continue-on-error prior links)
#   3. restores both verify scripts into a fresh mktemp dir under the
#      pinned RUNNER_TEMP
#   4. checks digest + regular-file + owner before exec
#   5. invokes each via /usr/bin/bash (never a workspace shebang)
#
# Required env (all set by the calling step's env: block, which wins over
# any GITHUB_ENV plant):
#   START_SHA, RUNNER_TEMP, VERIFY_CLAUDE_SHA256, VERIFY_SRT_SHA256,
#   CLAUDE_BIN, CLAUDE_SHA256, SRT_BIN
#
# Cipher MED-2: inherited PATH must already be exactly /usr/bin:/bin —
# this script does not re-export PATH before that check.
set -euo pipefail

unset GIT_DIR GIT_WORK_TREE GIT_CONFIG_PARAMETERS GIT_SSH_COMMAND \
  GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_OBJECT_DIRECTORY || true

if [ -z "${START_SHA:-}" ]; then
  echo "::error::START_SHA is empty — the pin step did not run" >&2
  exit 1
fi
if [ -z "${RUNNER_TEMP:-}" ]; then
  echo "::error::RUNNER_TEMP is empty" >&2
  exit 1
fi
if [ -z "${VERIFY_CLAUDE_SHA256:-}" ] || [ -z "${VERIFY_SRT_SHA256:-}" ]; then
  echo "::error::verify script digests are empty — the pin step did not hash them" >&2
  exit 1
fi
if [ -z "${CLAUDE_BIN:-}" ] || [ -z "${CLAUDE_SHA256:-}" ] || [ -z "${SRT_BIN:-}" ]; then
  echo "::error::CLAUDE_BIN / CLAUDE_SHA256 / SRT_BIN must be set" >&2
  exit 1
fi
if [ "${PATH}" != "/usr/bin:/bin" ]; then
  echo "::error::inherited PATH must be exactly /usr/bin:/bin (got '${PATH}'); GITHUB_PATH may have been planted" >&2
  exit 1
fi

[[ "$VERIFY_CLAUDE_SHA256" =~ ^[a-f0-9]{64}$ ]] || {
  echo "::error::VERIFY_CLAUDE_SHA256 must be 64 lowercase hex chars" >&2
  exit 1
}
[[ "$VERIFY_SRT_SHA256" =~ ^[a-f0-9]{64}$ ]] || {
  echo "::error::VERIFY_SRT_SHA256 must be 64 lowercase hex chars" >&2
  exit 1
}

# A detached child of a continue-on-error agent can rewrite RUNNER_TEMP or
# git objects between restore and exec. Same reap predicate shape as the
# deliver/bundle step; keyed on this script's workdir markers.
reap_should_kill() {
  local pid="$1" ppid="$2" comm="$3" cwd="$4" cmd="$5" sid="$6" cgroup="$7" my_pgid="$8" self_pid="$9"
  [ -n "$pid" ] || return 1
  [ "$pid" = "$self_pid" ] && return 1
  case "$pid" in
    *[!0-9]*) return 1 ;;
  esac
  case "$comm" in
    Runner.*|Agent.*|systemd*|containerd*|dockerd*|dbus*) return 1 ;;
  esac
  local in_tree=0 mentions=0
  case "$cwd" in
    "${GITHUB_WORKSPACE:-/nonexistent}"*|"${RUNNER_TEMP:-/nonexistent}"*) in_tree=1 ;;
  esac
  case "$cmd" in
    *verify-claude-code-pin*|*verify-sandbox-runtime-pin*|*restore-verify-pins*|*model_registry*) mentions=1 ;;
  esac
  if [ "$ppid" = "1" ] && { [ "$in_tree" = 1 ] || [ "$mentions" = 1 ]; }; then
    return 0
  fi
  if [ "$in_tree" = 1 ] && [ -n "$sid" ] && [ "$sid" = "$pid" ] && [ "$sid" != "$my_pgid" ] && [ "$sid" != "1" ] && [ "$sid" != "0" ]; then
    return 0
  fi
  case "$cgroup" in
    *run-*.scope*)
      if [ "$in_tree" = 1 ] || [ "$mentions" = 1 ]; then
        return 0
      fi
      ;;
  esac
  return 1
}

reap_agent_orphans() {
  local d pid ppid comm cwd cmd v pgid my_pgid sid cgroup
  local -a victims=()
  my_pgid="$(ps -o pgid= -p $$ | tr -d '[:space:]')"
  shopt -s nullglob
  for d in /proc/[0-9]*; do
    pid="${d#/proc/}"
    case "$pid" in
      *[!0-9]*) continue ;;
    esac
    ppid="$(awk '/^PPid:/ { print $2; exit }' "$d/status" 2>/dev/null || true)"
    comm="$(tr -d '\0' < "$d/comm" 2>/dev/null || true)"
    cwd="$(readlink "$d/cwd" 2>/dev/null || true)"
    cmd="$(tr '\0' ' ' < "$d/cmdline" 2>/dev/null || true)"
    sid="$(ps -o sid= -p "$pid" 2>/dev/null | tr -d '[:space:]' || true)"
    cgroup="$(tr '\0' ' ' < "$d/cgroup" 2>/dev/null || true)"
    if reap_should_kill "$pid" "$ppid" "$comm" "$cwd" "$cmd" "$sid" "$cgroup" "$my_pgid" "$$"; then
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

git_dir="$(/usr/bin/git --no-replace-objects -c core.hooksPath=/dev/null -c core.fsmonitor=false -c core.sshCommand= rev-parse --git-dir)"
if [ -e "${git_dir}/objects/info/alternates" ] || [ -L "${git_dir}/objects/info/alternates" ]; then
  echo "::error::refusing to restore verify pins: git object alternates are present" >&2
  exit 1
fi
if [ -L scripts ] || [ -L scripts/verify-claude-code-pin.sh ] || [ -L scripts/verify-sandbox-runtime-pin.sh ]; then
  echo "::error::refusing to restore verify pins: scripts/ or a verify script is a symlink" >&2
  exit 1
fi

# Reap BEFORE restore so a prior continue-on-error link cannot overwrite
# the fresh workdir as we materialize it.
reap_agent_orphans

workdir="$(mktemp -d "${RUNNER_TEMP}/verify-pins.XXXXXX")"
if [ -L "$workdir" ] || [ ! -d "$workdir" ]; then
  echo "::error::mktemp did not leave a regular directory under RUNNER_TEMP" >&2
  exit 1
fi
me="$(id -u)"
dir_owner="$(/usr/bin/stat -c '%u' "$workdir")"
if [ "$dir_owner" != "$me" ]; then
  echo "::error::verify-pins workdir not owned by the runner uid (${dir_owner} != ${me})" >&2
  exit 1
fi

restore_one() {
  local name="$1"
  local want="$2"
  local dest="${workdir}/${name}"
  local blob_tmp got owner
  blob_tmp="$(mktemp "${workdir}/${name}.XXXXXX")"
  if [ -L "$blob_tmp" ] || [ ! -f "$blob_tmp" ]; then
    echo "::error::refusing to restore ${name} through a symlink" >&2
    exit 1
  fi
  if ! /usr/bin/git --no-replace-objects -c core.hooksPath=/dev/null -c core.fsmonitor=false -c core.sshCommand= show "$START_SHA:scripts/${name}" > "$blob_tmp"; then
    /usr/bin/rm -f "$blob_tmp"
    echo "::error::could not restore ${name} from ${START_SHA}" >&2
    exit 1
  fi
  if [ -L "$dest" ]; then
    /usr/bin/rm -f "$dest"
  fi
  /usr/bin/mv -f "$blob_tmp" "$dest"
  if [ -L "$dest" ] || [ ! -f "$dest" ]; then
    echo "::error::${name} restore did not leave a regular file" >&2
    exit 1
  fi
  owner="$(/usr/bin/stat -c '%u' "$dest")"
  if [ "$owner" != "$me" ]; then
    echo "::error::${name} restore not owned by the runner uid (${owner} != ${me})" >&2
    exit 1
  fi
  got="$(/usr/bin/sha256sum "$dest" | awk '{print $1}')"
  if [ "$got" != "$want" ]; then
    echo "::error::restored ${name} sha256 does not match the pre-agent pin" >&2
    exit 1
  fi
}

restore_one verify-claude-code-pin.sh "$VERIFY_CLAUDE_SHA256"
restore_one verify-sandbox-runtime-pin.sh "$VERIFY_SRT_SHA256"

# Reap again, then re-check digests so a survivor cannot swap the bytes
# between the first check and exec.
reap_agent_orphans
got="$(/usr/bin/sha256sum "${workdir}/verify-claude-code-pin.sh" | awk '{print $1}')"
if [ "$got" != "$VERIFY_CLAUDE_SHA256" ]; then
  echo "::error::verify-claude-code-pin.sh sha256 changed after reap" >&2
  exit 1
fi
got="$(/usr/bin/sha256sum "${workdir}/verify-sandbox-runtime-pin.sh" | awk '{print $1}')"
if [ "$got" != "$VERIFY_SRT_SHA256" ]; then
  echo "::error::verify-sandbox-runtime-pin.sh sha256 changed after reap" >&2
  exit 1
fi
if [ -L "${workdir}/verify-claude-code-pin.sh" ] || [ ! -f "${workdir}/verify-claude-code-pin.sh" ] \
  || [ -L "${workdir}/verify-sandbox-runtime-pin.sh" ] || [ ! -f "${workdir}/verify-sandbox-runtime-pin.sh" ]; then
  echo "::error::verify pin restore did not leave regular files after reap" >&2
  exit 1
fi

/usr/bin/bash "${workdir}/verify-claude-code-pin.sh" "$CLAUDE_BIN" "$CLAUDE_SHA256"
/usr/bin/bash "${workdir}/verify-sandbox-runtime-pin.sh" "$SRT_BIN"
