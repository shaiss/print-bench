#!/usr/bin/env bash
# Trusted-preflight installer for the pinned Claude Code CLI
# (issue #875 / Cipher rulings on #876).
#
# - No install.sh / bootstrap.sh / curl|bash.
# - Import the Anthropic Claude Code signing key, require the committed
#   fingerprint, gpg --verify manifest.json.sig.
# - Download linux-x64 `claude`, check sha256 against BOTH the signed
#   manifest AND the committed pin.
# - install -o root -g root -m 0755 to /opt/claude-code/<ver>/claude with
#   root-owned 0755 parents (no symlinks, no ~/.local copy).
#
# Usage: install-claude-code-pin.sh [pin-file]
# Writes claude_bin= and claude_sha256= lines to GITHUB_OUTPUT when set.
# Refuses to run if provider/PAT secrets are present in the environment.
set -euo pipefail

PIN_FILE="${1:-${GITHUB_WORKSPACE:-.}/.github/claude-code-version}"

for v in ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_KEY ZAI_KEY \
         OPENROUTER_API_KEY GH_TOKEN REGEN_TOKEN; do
  if [ -n "${!v:-}" ]; then
    echo "error: ${v} must not be set during Claude Code pin install" >&2
    exit 1
  fi
done

[ -f "$PIN_FILE" ] || {
  echo "error: pin file missing: ${PIN_FILE}" >&2
  exit 1
}

claude_ver="$(awk '/^version:/{print $2; exit}' "$PIN_FILE")"
expected_sha="$(awk '/^linux-x64-sha256:/{print $2; exit}' "$PIN_FILE")"
want_fpr="$(awk '/^gpg-fingerprint:/{print $2; exit}' "$PIN_FILE")"
key_url="$(awk '/^signing-key-url:/{print $2; exit}' "$PIN_FILE")"

[[ "$claude_ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "error: bad version in ${PIN_FILE}" >&2
  exit 1
}
[[ "$expected_sha" =~ ^[a-f0-9]{64}$ ]] || {
  echo "error: bad linux-x64-sha256 in ${PIN_FILE}" >&2
  exit 1
}
[[ "$want_fpr" =~ ^[0-9A-F]{40}$ ]] || {
  echo "error: bad gpg-fingerprint in ${PIN_FILE}" >&2
  exit 1
}
[ -n "$key_url" ] || {
  echo "error: signing-key-url missing in ${PIN_FILE}" >&2
  exit 1
}

case "$(uname -m)" in
  x86_64|amd64) ;;
  *)
    echo "error: pinned checksum is linux-x64 only (got $(uname -m))" >&2
    exit 1
    ;;
esac

work="$(mktemp -d)"
cleanup() { rm -rf "$work"; }
trap cleanup EXIT

GNUPGHOME="${work}/gnupg"
mkdir -m 700 "$GNUPGHOME"
export GNUPGHOME

curl -fsSL "$key_url" -o "${work}/signing-key.asc"
gpg --batch --import "${work}/signing-key.asc"
got_fpr="$(gpg --batch --with-colons --fingerprint "$want_fpr" \
  | awk -F: '/^fpr:/{print $10; exit}')"
if [ "$got_fpr" != "$want_fpr" ]; then
  echo "error: imported key fingerprint mismatch (got ${got_fpr:-empty} want ${want_fpr})" >&2
  exit 1
fi

base="https://downloads.claude.ai/claude-code-releases/${claude_ver}"
curl -fsSL "${base}/manifest.json" -o "${work}/manifest.json"
curl -fsSL "${base}/manifest.json.sig" -o "${work}/manifest.json.sig"
gpg --batch --verify "${work}/manifest.json.sig" "${work}/manifest.json"

manifest_sha="$(python3 - "$work/manifest.json" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
print(m["platforms"]["linux-x64"]["checksum"])
PY
)"
[[ "$manifest_sha" =~ ^[a-f0-9]{64}$ ]] || {
  echo "error: signed manifest missing linux-x64 checksum" >&2
  exit 1
}
if [ "$manifest_sha" != "$expected_sha" ]; then
  echo "error: signed manifest sha256 ${manifest_sha} != committed pin ${expected_sha}" >&2
  exit 1
fi

curl -fsSL "${base}/linux-x64/claude" -o "${work}/claude"
got_sha="$(sha256sum "${work}/claude" | cut -d' ' -f1)"
if [ "$got_sha" != "$expected_sha" ] || [ "$got_sha" != "$manifest_sha" ]; then
  echo "error: binary sha256 mismatch (got ${got_sha}, pin ${expected_sha}, manifest ${manifest_sha})" >&2
  exit 1
fi

claude_root="/opt/claude-code"
claude_dir="${claude_root}/${claude_ver}"
claude_bin="${claude_dir}/claude"

sudo mkdir -p "$claude_dir"
# Replace any prior install; refuse to leave a symlink behind.
if [ -L "$claude_bin" ] || [ -e "$claude_bin" ]; then
  sudo rm -f "$claude_bin"
fi
sudo install -o root -g root -m 0755 "${work}/claude" "$claude_bin"
sudo chown root:root "$claude_root" "$claude_dir"
sudo chmod 0755 "$claude_root" "$claude_dir"
sudo chmod go-w "$claude_root" "$claude_dir"

if [ -L "$claude_bin" ]; then
  echo "error: installed path must not be a symlink: ${claude_bin}" >&2
  exit 1
fi
# No ~/.local copy — the agent-owned launcher is the tamper surface.
rm -f "${HOME}/.local/bin/claude" 2>/dev/null || true

test -x "$claude_bin"
[ ! -w "$claude_bin" ]
[ ! -w "$claude_dir" ]
owner_mode="$(stat -c '%u:%g %a' "$claude_bin")"
[ "$owner_mode" = "0:0 755" ] || {
  echo "error: expected owner 0:0 mode 755, got ${owner_mode}" >&2
  exit 1
}

"$claude_bin" --version | grep -F "$claude_ver"
claude_sha="$(sha256sum "$claude_bin" | cut -d' ' -f1)"
[ "$claude_sha" = "$expected_sha" ]

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "claude_bin=${claude_bin}" >> "$GITHUB_OUTPUT"
  echo "claude_sha256=${claude_sha}" >> "$GITHUB_OUTPUT"
fi

echo "install-claude-code-pin: ${claude_bin} sha256=${claude_sha}"
