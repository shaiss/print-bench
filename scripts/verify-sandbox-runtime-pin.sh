#!/usr/bin/env bash
# Re-verify the root-owned sandbox-runtime (srt) pin AND the SCRUB toolchain
# PATH surface before a keyed agent link or SCRUB smoke (issue #875 / Cipher
# follow-up on #876).
#
# Claude's SCRUB wrap PATH-resolves `srt`, `bwrap`, `socat`, and `rg` by name.
# AppArmor only confines `/usr/bin/bwrap`, so a planted `~/.local/bin/bwrap`
# (ahead of /usr/bin on the GHA PATH) would defeat clearenv. This script:
#   1. Strips runner-writable ~/.local/bin shadows for the SCRUB toolchain
#   2. Requires the absolute /opt srt wrapper (root-owned, not a symlink, no
#      `env node`) and a matching /usr/local/bin/srt copy
#   3. Requires `command -v` (on a PATH that still prefers ~/.local/bin if
#      present) to resolve bwrap/socat/rg/srt to the expected system pins
#
# Agent steps should ALSO set PATH=/usr/local/bin:/usr/bin:/bin so a plant
# mid-link cannot shadow the next subprocess inside the same job.
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

# Drop planted SCRUB-toolchain shadows under the runner-writable PATH prefix.
# Keep the strip list tight to tools Claude SCRUB / srt actually resolve.
local_bin="${HOME}/.local/bin"
for name in srt bwrap socat rg node; do
  rm -f "${local_bin}/${name}" 2>/dev/null || true
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

# Resolve on a PATH that still puts ~/.local/bin first when it exists — after
# the strip above, these must land on the system / root-owned pins. This is
# what the agent job's inherited PATH looks like before we also harden PATH
# on the keyed ship/run steps themselves.
resolve_path="${local_bin}:/usr/local/bin:/usr/bin:/bin"
assert_resolved() {
  local name="$1" want="$2" got
  got="$(PATH="$resolve_path" command -v "$name" || true)"
  if [ "$got" != "$want" ]; then
    echo "error: command -v ${name} resolved to '${got:-empty}', want ${want}" >&2
    exit 1
  fi
  case "$got" in
    "${HOME}"/*)
      echo "error: ${name} resolved under \$HOME: ${got}" >&2
      exit 1
      ;;
  esac
  if [ -w "$got" ]; then
    echo "error: ${got} is writable by $(id -un)" >&2
    exit 1
  fi
}

assert_resolved srt "$usr_bin"
assert_resolved bwrap /usr/bin/bwrap
assert_resolved socat /usr/bin/socat
assert_resolved rg /usr/bin/rg

got_ver="$(PATH="$resolve_path" srt --version 2>/dev/null | tr -d '[:space:]' || true)"
[[ "$got_ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "error: srt --version is '${got_ver:-empty}'" >&2
  exit 1
}

echo "verify-sandbox-runtime-pin: ${bin} (=${usr_bin}) version=${got_ver}; bwrap/socat/rg pins ok"
