#!/usr/bin/env bash
# Re-verify the root-owned sandbox-runtime (srt) pin AND the SCRUB toolchain
# PATH surface before a keyed agent link or SCRUB smoke (issue #875 / Cipher
# follow-up on #876).
#
# Claude's SCRUB wrap PATH-resolves `srt`, `bwrap`, `socat`, and `rg` by name.
# AppArmor only confines `/usr/bin/bwrap`. Two PATH traps on GHA runners:
#   • ~/.local/bin is ahead of /usr/bin by default
#   • /usr/local/bin is chmod 777 (no sticky bit) on the hosted image, so the
#     runner uid can plant bwrap/srt there without sudo
# This script strips those shadows, requires the absolute /opt srt wrapper
# (root-owned, not a symlink, no `env node`), and requires `command -v` to
# resolve bwrap/socat/rg/srt to the expected non-writable pins.
#
# Agent steps set PATH=/opt/sandbox-runtime/bin:/usr/bin:/bin:/home/runner/.local/bin
# (no /usr/local/bin) so a mid-link plant cannot shadow SCRUB tools while pip
# user scripts under ~/.local/bin remain reachable after system pins.
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

local_bin="${HOME}/.local/bin"
# Drop planted SCRUB-toolchain shadows under runner-writable prefixes.
# ~/.local/bin: strip SCRUB names + node (a planted node would hijack
# `#!/usr/bin/env node`; the pin wrapper binds an absolute node instead).
for name in srt bwrap socat rg node; do
  rm -f "${local_bin}/${name}" 2>/dev/null || true
done
# /usr/local/bin is world-writable on GHA — remove SCRUB names there too
# (no sudo needed). Never strip `node`: hosted images keep the real Node
# at /usr/local/bin/node, and the pin installer binds the root-owned srt
# wrapper to that absolute interpreter. Deleting it after disable-sudo
# breaks srt and every later SCRUB smoke that re-runs this verify.
for name in srt bwrap socat rg; do
  rm -f "/usr/local/bin/${name}" 2>/dev/null || true
done

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

# Resolve on a PATH shaped like the hardened agent PATH (system + /opt first,
# ~/.local/bin last for pip scripts, no /usr/local/bin).
resolve_path="/opt/sandbox-runtime/bin:/usr/bin:/bin:${local_bin}"
assert_resolved() {
  local name="$1" want="$2" got
  got="$(PATH="$resolve_path" command -v "$name" || true)"
  if [ "$got" != "$want" ]; then
    echo "error: command -v ${name} resolved to '${got:-empty}', want ${want}" >&2
    exit 1
  fi
  case "$got" in
    "${HOME}"/*|/usr/local/*)
      echo "error: ${name} resolved under a writable prefix: ${got}" >&2
      exit 1
      ;;
  esac
  if [ -w "$got" ]; then
    echo "error: ${got} is writable by $(id -un)" >&2
    exit 1
  fi
}

assert_resolved srt "$bin"
assert_resolved bwrap /usr/bin/bwrap
assert_resolved socat /usr/bin/socat
assert_resolved rg /usr/bin/rg

got_ver="$(PATH="$resolve_path" srt --version 2>/dev/null | tr -d '[:space:]' || true)"
[[ "$got_ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "error: srt --version is '${got_ver:-empty}'" >&2
  exit 1
}

echo "verify-sandbox-runtime-pin: ${bin} version=${got_ver}; bwrap/socat/rg pins ok"
