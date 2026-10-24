#!/usr/bin/env bash
# Re-verify the root-owned Claude Code pin before a keyed agent link
# (issue #875 / Cipher rulings on #876).
#
# Usage: verify-claude-code-pin.sh <absolute-bin-path> <expected-sha256>
#
# Requires: path under /opt/claude-code/, regular file (not symlink),
# owner 0:0, mode 755, parents not writable by the runner user, sha256 match.
set -euo pipefail

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

owner_mode="$(stat -c '%u:%g %a' "$bin")"
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

got="$(sha256sum "$bin" | cut -d' ' -f1)"
if [ "$got" != "$want" ]; then
  echo "error: Claude Code sha256 mismatch for ${bin} (got ${got} want ${want})" >&2
  exit 1
fi
