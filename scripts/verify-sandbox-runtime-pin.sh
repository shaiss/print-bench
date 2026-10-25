#!/usr/bin/env bash
# Re-verify the root-owned sandbox-runtime (srt) pin before a keyed agent
# link or SCRUB smoke (issue #875 / Cipher follow-up on #876).
#
# Mirrors verify-claude-code-pin.sh for the PATH-resolved `srt` binary that
# Claude's SCRUB wrap invokes by name: strip a runner-writable ~/.local/bin
# shadow, require the absolute /opt wrapper (root-owned, not a symlink, no
# `env node`), and require `command -v srt` to resolve to that same file.
#
# Usage: verify-sandbox-runtime-pin.sh [srt-bin]
# Default bin: /opt/sandbox-runtime/bin/srt
set -euo pipefail

bin="${1:-/opt/sandbox-runtime/bin/srt}"

case "$bin" in
  /opt/sandbox-runtime/*) ;;
  *)
    echo "error: refuse to verify srt outside /opt/sandbox-runtime/: ${bin}" >&2
    exit 1
    ;;
esac

# Runner-writable PATH prefix can shadow /usr/local/bin and /opt. Drop any
# planted srt (and only srt — do not touch unrelated ~/.local tools).
rm -f "${HOME}/.local/bin/srt" 2>/dev/null || true

[ -e "$bin" ] || {
  echo "error: pinned srt missing: ${bin}" >&2
  exit 1
}
if [ -L "$bin" ]; then
  echo "error: pinned srt path must not be a symlink: ${bin}" >&2
  exit 1
fi
[ -f "$bin" ] || {
  echo "error: pinned srt path is not a regular file: ${bin}" >&2
  exit 1
}
[ -x "$bin" ] || {
  echo "error: pinned srt is not executable: ${bin}" >&2
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
    /opt/sandbox-runtime|/opt/sandbox-runtime/*|/opt)
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

# Wrapper must exec an absolute node + absolute cli.js — never `env node`,
# which a planted ~/.local/bin/node would intercept.
if grep -Eiq 'env[[:space:]]+node|/usr/bin/env[[:space:]]+node' "$bin"; then
  echo "error: pinned srt wrapper must not use env node: ${bin}" >&2
  exit 1
fi
cli_js="/opt/sandbox-runtime/node_modules/@anthropic-ai/sandbox-runtime/dist/cli.js"
[ -f "$cli_js" ] || {
  echo "error: sandbox-runtime cli.js missing: ${cli_js}" >&2
  exit 1
}
grep -Fq "$cli_js" "$bin" || {
  echo "error: pinned srt wrapper does not exec ${cli_js}" >&2
  exit 1
}

# Publish the same bytes at /usr/local/bin/srt (root-owned copy, not a
# symlink into a PATH-hijackable name) so a bare `srt` lookup still hits
# the pin after ~/.local/bin/srt is removed.
usr_bin="/usr/local/bin/srt"
if [ -L "$usr_bin" ]; then
  echo "error: ${usr_bin} must not be a symlink" >&2
  exit 1
fi
[ -f "$usr_bin" ] || {
  echo "error: ${usr_bin} missing — re-run install-sandbox-runtime-pin.sh" >&2
  exit 1
}
usr_owner="$(stat -c '%u:%g %a' "$usr_bin")"
if [ "$usr_owner" != "0:0 755" ]; then
  echo "error: expected owner 0:0 mode 755 for ${usr_bin}, got ${usr_owner}" >&2
  exit 1
fi
if ! cmp -s "$bin" "$usr_bin"; then
  echo "error: ${usr_bin} bytes differ from ${bin}" >&2
  exit 1
fi

# Prefer a clean PATH for the resolution check: no ~/.local/bin.
PATH="/usr/local/bin:/usr/bin:/bin"
export PATH
resolved="$(command -v srt || true)"
if [ "$resolved" != "$usr_bin" ]; then
  echo "error: command -v srt resolved to '${resolved:-empty}', want ${usr_bin}" >&2
  exit 1
fi

got_ver="$(srt --version 2>/dev/null | tr -d '[:space:]' || true)"
[[ "$got_ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "error: srt --version is '${got_ver:-empty}'" >&2
  exit 1
}

echo "verify-sandbox-runtime-pin: ${bin} (=${usr_bin}) version=${got_ver} ok"
