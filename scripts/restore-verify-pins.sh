#!/usr/bin/env bash
# Hardened START_SHA restore + exec of the Claude / sandbox-runtime pin
# verifiers (Cipher MED-1 follow-up on #876).
#
# Trusted preflight (start_ref) records sha256 digests of
# verify-claude-code-pin.sh and verify-sandbox-runtime-pin.sh into step
# outputs before any agent runs. This script — itself restored from
# START_SHA and digest-checked by the calling workflow step via an
# O_RDONLY fd + unlink (no stable path) — then:
#   1. blanks GIT_* overrides and refuses object alternates
#   2. reaps by ownership: every process of the runner uid that is not an
#      ancestor of this step (and not a protected Runner/infra comm)
#   3. restores both verify scripts into a fresh mktemp dir under the
#      pinned RUNNER_TEMP
#   4. checks digest + regular-file + owner before exec
#   5. invokes each via /usr/bin/bash (never a workspace shebang)
#   6. allocates a fresh mktemp CLAUDE_CONFIG_DIR for the next keyed ship
#      and writes it to GITHUB_OUTPUT (ship must not reuse /home/runner/.claude)
#
# Required env (all set by the calling step's env: block, which wins over
# any GITHUB_ENV plant):
#   START_SHA, RUNNER_TEMP, VERIFY_CLAUDE_SHA256, VERIFY_SRT_SHA256,
#   CLAUDE_BIN, CLAUDE_SHA256, SRT_BIN, GITHUB_OUTPUT
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
if [ -z "${GITHUB_OUTPUT:-}" ]; then
  echo "::error::GITHUB_OUTPUT is empty — cannot publish claude_config_dir" >&2
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

# Close the reap-heuristic class: kill every process owned by the runner
# uid that is not an ancestor of this step. A setsid/nohup daemon with
# cwd=/tmp and an innocuous cmdline still has our uid and is not an
# ancestor, so it dies. Protect only the ancestor chain and known
# runner/infra comm names (never widen by cwd/cmdline signals again).
reap_agent_orphans() {
  local me d pid uid ppid comm v pgid my_pgid
  local -a victims=() ancestors=()
  me="$(id -u)"
  my_pgid="$(ps -o pgid= -p $$ | tr -d '[:space:]')"
  pid=$$
  while [ -n "$pid" ] && [ "$pid" != "0" ]; do
    ancestors+=("$pid")
    [ "$pid" = "1" ] && break
    pid="$(awk '/^PPid:/ { print $2; exit }' "/proc/${pid}/status" 2>/dev/null || true)"
    # Cycle / vanished parent: stop.
    case "$pid" in
      ''|*[!0-9]*) break ;;
    esac
  done

  is_ancestor() {
    local p="$1" a
    for a in "${ancestors[@]}"; do
      [ "$p" = "$a" ] && return 0
    done
    return 1
  }

  shopt -s nullglob
  for d in /proc/[0-9]*; do
    pid="${d#/proc/}"
    case "$pid" in
      *[!0-9]*) continue ;;
    esac
    uid="$(awk '/^Uid:/ { print $2; exit }' "$d/status" 2>/dev/null || true)"
    [ "$uid" = "$me" ] || continue
    if is_ancestor "$pid"; then
      continue
    fi
    comm="$(tr -d '\0' < "$d/comm" 2>/dev/null || true)"
    case "$comm" in
      Runner.*|Agent.*|systemd*|containerd*|dockerd*|dbus*) continue ;;
    esac
    victims+=("$pid")
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

# Reap BEFORE any restore so a prior continue-on-error link cannot rewrite
# RUNNER_TEMP / git objects / Claude config as we materialize trusted bytes.
reap_agent_orphans

git_dir="$(/usr/bin/git --no-replace-objects -c core.hooksPath=/dev/null -c core.fsmonitor=false -c core.sshCommand= rev-parse --git-dir)"
if [ -e "${git_dir}/objects/info/alternates" ] || [ -L "${git_dir}/objects/info/alternates" ]; then
  echo "::error::refusing to restore verify pins: git object alternates are present" >&2
  exit 1
fi
if [ -L scripts ] || [ -L scripts/verify-claude-code-pin.sh ] || [ -L scripts/verify-sandbox-runtime-pin.sh ]; then
  echo "::error::refusing to restore verify pins: scripts/ or a verify script is a symlink" >&2
  exit 1
fi

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

# Restore one verify script to a unique path, open an O_RDONLY fd, unlink the
# path, then re-check the digest via the fd so a survivor cannot swap the
# file between hash and exec (TOCTOU).
restore_one() {
  local name="$1"
  local want="$2"
  local blob_tmp got owner fd
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
  owner="$(/usr/bin/stat -c '%u' "$blob_tmp")"
  if [ "$owner" != "$me" ]; then
    echo "::error::${name} restore not owned by the runner uid (${owner} != ${me})" >&2
    exit 1
  fi
  got="$(/usr/bin/sha256sum "$blob_tmp" | awk '{print $1}')"
  if [ "$got" != "$want" ]; then
    echo "::error::restored ${name} sha256 does not match the pre-agent pin" >&2
    exit 1
  fi
  # Hold the inode, drop the directory entry, re-hash via the fd.
  exec {fd}<"$blob_tmp"
  /usr/bin/rm -f "$blob_tmp"
  got="$(/usr/bin/sha256sum "/dev/fd/${fd}" | awk '{print $1}')"
  if [ "$got" != "$want" ]; then
    echo "::error::${name} sha256 changed after unlink (TOCTOU)" >&2
    exit 1
  fi
  # Stash the fd number for the caller via nameref-ish globals.
  case "$name" in
    verify-claude-code-pin.sh) VERIFY_CLAUDE_FD="$fd" ;;
    verify-sandbox-runtime-pin.sh) VERIFY_SRT_FD="$fd" ;;
    *)
      echo "::error::unknown verify script ${name}" >&2
      exit 1
      ;;
  esac
}

VERIFY_CLAUDE_FD=""
VERIFY_SRT_FD=""
restore_one verify-claude-code-pin.sh "$VERIFY_CLAUDE_SHA256"
restore_one verify-sandbox-runtime-pin.sh "$VERIFY_SRT_SHA256"

# Reap again before exec; fds still hold the trusted inodes.
reap_agent_orphans

/usr/bin/bash "/dev/fd/${VERIFY_CLAUDE_FD}" "$CLAUDE_BIN" "$CLAUDE_SHA256"
/usr/bin/bash "/dev/fd/${VERIFY_SRT_FD}" "$SRT_BIN"

# Fresh per-link Claude config dir for the next keyed ship. The shared
# /home/runner/.claude was wiped by verify-claude-code-pin.sh; a survivor
# that replants there must not be what the next ship reads.
cfg_dir="$(mktemp -d "${RUNNER_TEMP}/claude-cfg.XXXXXX")"
if [ -L "$cfg_dir" ] || [ ! -d "$cfg_dir" ]; then
  echo "::error::mktemp did not leave a regular claude-cfg directory" >&2
  exit 1
fi
cfg_owner="$(/usr/bin/stat -c '%u' "$cfg_dir")"
if [ "$cfg_owner" != "$me" ]; then
  echo "::error::claude-cfg dir not owned by the runner uid (${cfg_owner} != ${me})" >&2
  exit 1
fi
# Refuse path characters that would break GITHUB_OUTPUT / step-env wiring.
case "$cfg_dir" in
  *$'\n'*|*$'\r'*)
    echo "::error::claude-cfg path contains a newline" >&2
    exit 1
    ;;
esac
echo "claude_config_dir=${cfg_dir}" >> "$GITHUB_OUTPUT"
echo "restore-verify-pins: pins ok; claude_config_dir=${cfg_dir}"
