#!/usr/bin/env bash
# Trusted-preflight installer for the pinned @anthropic-ai/sandbox-runtime
# (issue #875 / Cipher follow-up on #876).
#
# - No bare `npm install -g @anthropic-ai/sandbox-runtime@…`.
# - Install from the committed `.github/sandbox-runtime/{package.json,
#   package-lock.json}` tree with `npm ci --ignore-scripts`, so the top-level
#   package AND every transitive dep (zod, commander, node-forge,
#   @pondwader/socks5-server, …) are integrity-checked against the lockfile.
# - Cross-checks the pin file's version + dist-integrity against the lockfile.
# - Refuses to run if provider/PAT secrets are present in the environment.
#
# Usage: install-sandbox-runtime-pin.sh [pin-file]
set -euo pipefail

PIN_FILE="${1:-${GITHUB_WORKSPACE:-.}/.github/sandbox-runtime-version}"
REPO_ROOT="${GITHUB_WORKSPACE:-$(cd "$(dirname "$0")/.." && pwd)}"
PKG_DIR="${REPO_ROOT}/.github/sandbox-runtime"
INSTALL_ROOT="/opt/sandbox-runtime"

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
[ -f "${PKG_DIR}/package.json" ] || {
  echo "error: missing ${PKG_DIR}/package.json" >&2
  exit 1
}
[ -f "${PKG_DIR}/package-lock.json" ] || {
  echo "error: missing ${PKG_DIR}/package-lock.json (commit a lockfileVersion-3 lock)" >&2
  exit 1
}

srt_ver="$(awk '/^version:/{print $2; exit}' "$PIN_FILE")"
want_integrity="$(awk '/^dist-integrity:/{print $2; exit}' "$PIN_FILE")"

[[ "$srt_ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "error: bad sandbox-runtime version in ${PIN_FILE}" >&2
  exit 1
}
[[ "$want_integrity" =~ ^sha512-[A-Za-z0-9+/=]+$ ]] || {
  echo "error: bad dist-integrity in ${PIN_FILE}" >&2
  exit 1
}

# Pin file, package.json, and lockfile must agree before npm ci fetches anything.
pkg_ver="$(python3 - "$PKG_DIR/package.json" <<'PY'
import json, sys
deps = json.load(open(sys.argv[1])).get("dependencies") or {}
print(deps.get("@anthropic-ai/sandbox-runtime", ""))
PY
)"
[ "$pkg_ver" = "$srt_ver" ] || {
  echo "error: package.json pins '@anthropic-ai/sandbox-runtime@${pkg_ver:-empty}', pin file wants ${srt_ver}" >&2
  exit 1
}

python3 - "$PKG_DIR/package-lock.json" "$srt_ver" "$want_integrity" <<'PY'
import json, sys
lock_path, want_ver, want_integrity = sys.argv[1], sys.argv[2], sys.argv[3]
lock = json.load(open(lock_path))
if lock.get("lockfileVersion") != 3:
    print(f"error: package-lock.json lockfileVersion must be 3 (got {lock.get('lockfileVersion')})", file=sys.stderr)
    sys.exit(1)
pkgs = lock.get("packages") or {}
entry = pkgs.get("node_modules/@anthropic-ai/sandbox-runtime")
if not isinstance(entry, dict):
    print("error: lockfile missing node_modules/@anthropic-ai/sandbox-runtime", file=sys.stderr)
    sys.exit(1)
got_ver = entry.get("version", "")
got_integrity = entry.get("integrity", "")
if got_ver != want_ver:
    print(f"error: lockfile sandbox-runtime version is '{got_ver}', pin wants {want_ver}", file=sys.stderr)
    sys.exit(1)
if got_integrity != want_integrity:
    print("error: lockfile sandbox-runtime integrity mismatches pin dist-integrity", file=sys.stderr)
    print(f"  lock: {got_integrity}", file=sys.stderr)
    print(f"  pin:  {want_integrity}", file=sys.stderr)
    sys.exit(1)
# Every resolved package (root "" excluded) must carry an integrity hash.
missing = [
    name for name, meta in pkgs.items()
    if name.startswith("node_modules/") and not (meta or {}).get("integrity")
]
if missing:
    print("error: lockfile packages missing integrity:", ", ".join(sorted(missing)), file=sys.stderr)
    sys.exit(1)
print(f"lockfile ok: sandbox-runtime@{got_ver} + {sum(1 for n in pkgs if n.startswith('node_modules/'))} integrity-pinned modules")
PY

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

# Install under /opt as root from the committed lockfile. npm ci verifies
# every tarball against lockfile integrity hashes; --ignore-scripts blocks
# prepare/husky (dist/ is already in the published tarball).
sudo rm -rf "$INSTALL_ROOT"
sudo mkdir -p "$INSTALL_ROOT"
sudo install -o root -g root -m 0644 \
  "${PKG_DIR}/package.json" "${PKG_DIR}/package-lock.json" "$INSTALL_ROOT/"
sudo env "PATH=$(dirname "$npm_bin"):$(dirname "$node_bin"):/usr/local/bin:/usr/bin:/bin" \
  "$npm_bin" ci --ignore-scripts --prefix "$INSTALL_ROOT"

srt_src="${INSTALL_ROOT}/node_modules/.bin/srt"
[ -x "$srt_src" ] || {
  echo "error: srt shim missing after npm ci: ${srt_src}" >&2
  exit 1
}
# Point /usr/local/bin/srt at the lockfile-installed shim (relative requires
# inside that shim resolve against /opt/sandbox-runtime/node_modules).
sudo ln -sfn "$srt_src" /usr/local/bin/srt

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

echo "install-sandbox-runtime-pin: ${srt_bin} version=${got_ver} lockfile=ok"
