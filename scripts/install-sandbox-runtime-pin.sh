#!/usr/bin/env bash
# Trusted-preflight installer for the pinned @anthropic-ai/sandbox-runtime
# (issue #875 / Cipher follow-up on #876).
#
# - No unhashed `npm install -g @anthropic-ai/sandbox-runtime@…`.
# - Fetch the exact version's tarball (`npm pack` or the committed registry
#   URL), verify sha512 dist.integrity against the committed pin, then
#   `npm install -g --ignore-scripts` that verified tarball.
# - Refuses to run if provider/PAT secrets are present in the environment.
#
# Usage: install-sandbox-runtime-pin.sh [pin-file]
set -euo pipefail

PIN_FILE="${1:-${GITHUB_WORKSPACE:-.}/.github/sandbox-runtime-version}"

for v in ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_KEY ZAI_KEY \
         OPENROUTER_API_KEY GH_TOKEN REGEN_TOKEN; do
  if [ -n "${!v:-}" ]; then
    echo "error: ${v} must not be set during sandbox-runtime pin install" >&2
    exit 1
  fi
done

[ -f "$PIN_FILE" ] || {
  echo "error: pin file missing: ${PIN_FILE}" >&2
  exit 1
}

srt_ver="$(awk '/^version:/{print $2; exit}' "$PIN_FILE")"
want_integrity="$(awk '/^dist-integrity:/{print $2; exit}' "$PIN_FILE")"
tarball_url="$(awk '/^tarball-url:/{print $2; exit}' "$PIN_FILE")"

[[ "$srt_ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "error: bad sandbox-runtime version in ${PIN_FILE}" >&2
  exit 1
}
[[ "$want_integrity" =~ ^sha512-[A-Za-z0-9+/=]+$ ]] || {
  echo "error: bad dist-integrity in ${PIN_FILE}" >&2
  exit 1
}

work="$(mktemp -d)"
cleanup() { rm -rf "$work"; }
trap cleanup EXIT

# Prefer npm pack (exact version); fall back to the committed registry URL.
(
  cd "$work"
  if command -v npm >/dev/null 2>&1; then
    npm pack "@anthropic-ai/sandbox-runtime@${srt_ver}" --silent
  elif [ -n "$tarball_url" ]; then
    curl -fsSL "$tarball_url" -o "anthropic-ai-sandbox-runtime-${srt_ver}.tgz"
  else
    echo "error: npm not on PATH and no tarball-url in pin file" >&2
    exit 1
  fi
)

tgz="$(find "$work" -maxdepth 1 -type f -name 'anthropic-ai-sandbox-runtime-*.tgz' | head -1)"
[ -n "$tgz" ] && [ -f "$tgz" ] || {
  echo "error: sandbox-runtime tarball missing after fetch" >&2
  exit 1
}

got_integrity="$(python3 - "$tgz" <<'PY'
import base64, hashlib, sys
data = open(sys.argv[1], "rb").read()
print("sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode())
PY
)"
if [ "$got_integrity" != "$want_integrity" ]; then
  echo "error: sandbox-runtime tarball integrity mismatch" >&2
  echo "  got:  ${got_integrity}" >&2
  echo "  want: ${want_integrity}" >&2
  exit 1
fi

# Install the verified local tarball only. --ignore-scripts skips prepare/
# husky (dist/ is already in the published tarball). Pass PATH explicitly so
# sudo's secure_path still finds node next to npm (nvm / user-local installs).
npm_bin="$(command -v npm)"
node_bin="$(command -v node)"
[ -x "$npm_bin" ] || {
  echo "error: npm not executable at ${npm_bin:-empty}" >&2
  exit 1
}
[ -x "$node_bin" ] || {
  echo "error: node not executable at ${node_bin:-empty}" >&2
  exit 1
}
sudo env "PATH=$(dirname "$npm_bin"):$(dirname "$node_bin"):/usr/local/bin:/usr/bin:/bin" \
  "$npm_bin" install -g --ignore-scripts --silent "$tgz"

# Global bin dir may be /usr/local/bin (system node) or a prefix next to npm.
PATH="/usr/local/bin:$(dirname "$npm_bin"):${PATH}"
export PATH
srt_bin="$(command -v srt || true)"
[ -n "$srt_bin" ] || {
  echo "error: srt not on PATH after verified sandbox-runtime install" >&2
  exit 1
}
got_ver="$(srt --version 2>/dev/null | tr -d '[:space:]' || true)"
if [ "$got_ver" != "$srt_ver" ]; then
  echo "error: srt --version is '${got_ver:-empty}', want ${srt_ver}" >&2
  exit 1
fi

echo "install-sandbox-runtime-pin: ${srt_bin} version=${got_ver} integrity=ok"
