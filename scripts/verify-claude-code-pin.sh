#!/usr/bin/env bash
# Re-verify the root-owned Claude Code pin before a keyed agent link
# (issue #875 / Cipher rulings on #876).
#
# Usage: verify-claude-code-pin.sh <absolute-bin-path> <expected-sha256>
#
# Requires: path under /opt/claude-code/, regular file (not symlink),
# owner 0:0, mode 755, parents not writable by the runner user, sha256 match.
set -euo pipefail
# Pin tooling PATH so a planted ~/.local/bin/{rm,sha256sum,bash} cannot no-op
# the wipe or forge a checksum. Absolute binaries below are belt-and-suspenders.
export PATH="/usr/bin:/bin"
RM_BIN="${RM_BIN:-/usr/bin/rm}"
MKDIR_BIN="${MKDIR_BIN:-/usr/bin/mkdir}"
SHA256SUM_BIN="${SHA256SUM_BIN:-/usr/bin/sha256sum}"
STAT_BIN="${STAT_BIN:-/usr/bin/stat}"

bin="${1:?usage: $0 <bin> <sha256>}"
want="${2:?usage: $0 <bin> <sha256>}"

case "$bin" in
  /opt/claude-code/*) ;;
  *)
    echo "error: refuse to verify a Claude Code binary outside /opt/claude-code/: ${bin}" >&2
    exit 1
    ;;
esac

[[ "$want" =~ ^[a-f0-9]{64}$ ]] || {
  echo "error: expected sha256 must be 64 lowercase hex chars" >&2
  exit 1
}

[ -e "$bin" ] || {
  echo "error: pinned Claude Code binary missing: ${bin}" >&2
  exit 1
}
if [ -L "$bin" ]; then
  echo "error: pinned Claude Code path must not be a symlink: ${bin}" >&2
  exit 1
fi
[ -f "$bin" ] || {
  echo "error: pinned Claude Code path is not a regular file: ${bin}" >&2
  exit 1
}
[ -x "$bin" ] || {
  echo "error: pinned Claude Code binary is not executable: ${bin}" >&2
  exit 1
}

owner_mode="$("${STAT_BIN}" -c '%u:%g %a' "$bin")"
if [ "$owner_mode" != "0:0 755" ]; then
  echo "error: expected owner 0:0 mode 755 for ${bin}, got ${owner_mode}" >&2
  exit 1
fi

parent="$(dirname "$bin")"
grandparent="$(dirname "$parent")"
for d in "$parent" "$grandparent"; do
  case "$d" in
    /opt/claude-code|/opt/claude-code/*|/opt)
      if [ -w "$d" ]; then
        echo "error: ${d} is writable by $(id -un) — expected root-owned parents" >&2
        exit 1
      fi
      ;;
  esac
done
if [ -w "$bin" ]; then
  echo "error: ${bin} is writable by $(id -un)" >&2
  exit 1
fi

got="$("${SHA256SUM_BIN}" "$bin" | cut -d' ' -f1)"
if [ "$got" != "$want" ]; then
  echo "error: Claude Code sha256 mismatch for ${bin} (got ${got} want ${want})" >&2
  exit 1
fi

# Drop any user Claude config a prior continue-on-error agent link may have
# planted. The next secret-bearing claude-code-action parent process loads
# hooks/settings from these paths; SCRUB/AppArmor only wrap sandboxed
# children. Allowlist paths under /home/runner only — never honor a planted
# CLAUDE_CONFIG_DIR / XDG_CONFIG_HOME that could point rm -rf elsewhere.
runner_home="/home/runner"
claude_cfg="${runner_home}/.claude"
xdg_claude="${runner_home}/.config/claude"
claude_json="${runner_home}/.claude.json"
"${RM_BIN}" -rf -- "${claude_cfg}" "${xdg_claude}"
"${RM_BIN}" -f -- "${claude_json}"
"${MKDIR_BIN}" -p -- "${claude_cfg}"
echo "verify-claude-code-pin: ${bin} sha256 ok; wiped ${claude_cfg}, ${xdg_claude}, ${claude_json}"
