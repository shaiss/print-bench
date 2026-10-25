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
# Source node must be outside $HOME (a planted ~/.local/bin/node cannot be
# what we copy). We still refuse to BIND the wrapper to /usr/local/bin/node
# itself — that directory is chmod 777 on GHA, so after disable-sudo a
# runner-uid plant would replace the interpreter the root-owned wrapper
# permanently execs. Copy into /opt instead (below).
case "$node_bin" in
  "${HOME}"/*|/home/*)
    echo "error: node at ${node_bin} is under a home directory — refuse to pin a hijackable interpreter" >&2
    exit 1
    ;;
esac
node_src="$(readlink -f "$node_bin")"
[ -x "$node_src" ] || {
  echo "error: resolved node not executable: ${node_src}" >&2
  exit 1
}
case "$node_src" in
  "${HOME}"/*|/home/*)
    echo "error: resolved node at ${node_src} is under a home directory" >&2
    exit 1
    ;;
esac

# Install under /opt as root from the committed lockfile. npm ci verifies
# every tarball against lockfile integrity hashes; --ignore-scripts blocks
# prepare/husky (dist/ is already in the published tarball).
sudo rm -rf "$INSTALL_ROOT"
sudo mkdir -p "${INSTALL_ROOT}/bin"
sudo install -o root -g root -m 0644 \
  "${PKG_DIR}/package.json" "${PKG_DIR}/package-lock.json" "$INSTALL_ROOT/"
sudo env "PATH=$(dirname "$npm_bin"):$(dirname "$node_src"):/usr/local/bin:/usr/bin:/bin" \
  "$npm_bin" ci --ignore-scripts --prefix "$INSTALL_ROOT"

cli_js="${INSTALL_ROOT}/node_modules/@anthropic-ai/sandbox-runtime/dist/cli.js"
[ -f "$cli_js" ] || {
  echo "error: sandbox-runtime cli.js missing after npm ci: ${cli_js}" >&2
  exit 1
}

# Root-owned Node copy under /opt — the wrapper binds THIS path, never the
# world-writable /usr/local/bin/node source. Regular file, not a symlink.
pinned_node="${INSTALL_ROOT}/bin/node"
sudo install -o root -g root -m 0755 "$node_src" "$pinned_node"
if [ -L "$pinned_node" ]; then
  echo "error: pinned node must not be a symlink: ${pinned_node}" >&2
  exit 1
fi
[ -x "$pinned_node" ] || {
  echo "error: pinned node not executable: ${pinned_node}" >&2
  exit 1
}

# Root-owned wrapper with ABSOLUTE /opt node + cli.js — never `#!/usr/bin/env
# node` and never /usr/local/bin/node. Not a symlink.
wrapper_tmp="$(mktemp)"
cat > "$wrapper_tmp" <<EOF
#!/bin/bash
exec ${pinned_node} ${cli_js} "\$@"
EOF
srt_bin="${INSTALL_ROOT}/bin/srt"
sudo install -o root -g root -m 0755 "$wrapper_tmp" "$srt_bin"
rm -f "$wrapper_tmp"
sudo chown root:root "$INSTALL_ROOT" "${INSTALL_ROOT}/bin"
sudo chmod 0755 "$INSTALL_ROOT" "${INSTALL_ROOT}/bin"
sudo chmod go-w "$INSTALL_ROOT" "${INSTALL_ROOT}/bin"

if [ -L "$srt_bin" ]; then
  echo "error: installed srt path must not be a symlink: ${srt_bin}" >&2
  exit 1
fi

# Do NOT install into /usr/local/bin: GHA runner images chmod -R 777 that
# directory, so the runner uid could replace a copy after disable-sudo.
# Agents resolve srt via PATH that puts /opt/sandbox-runtime/bin first.
sudo rm -f /usr/local/bin/srt 2>/dev/null || true
rm -f "${HOME}/.local/bin/srt" 2>/dev/null || true

PATH="/opt/sandbox-runtime/bin:/usr/bin:/bin"
export PATH
resolved="$(command -v srt || true)"
[ "$resolved" = "$srt_bin" ] || {
  echo "error: command -v srt is '${resolved:-empty}', want ${srt_bin}" >&2
  exit 1
}
got_ver="$(srt --version 2>/dev/null | tr -d '[:space:]' || true)"
if [ "$got_ver" != "$srt_ver" ]; then
  echo "error: srt --version is '${got_ver:-empty}', want ${srt_ver}" >&2
  exit 1
fi

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "srt_bin=${srt_bin}" >> "$GITHUB_OUTPUT"
fi

echo "install-sandbox-runtime-pin: ${srt_bin} version=${got_ver} lockfile=ok"
