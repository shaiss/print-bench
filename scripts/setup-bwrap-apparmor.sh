#!/usr/bin/env bash
# Load Ubuntu's bwrap-userns-restrict AppArmor profile so bubblewrap can
# create unprivileged user namespaces WITHOUT globally clearing
# kernel.apparmor_restrict_unprivileged_userns (Cipher ruling on #876).
#
# Must run in trusted preflight BEFORE disable-sudo (needs root).
# Expects bubblewrap + apparmor-profiles already apt-installed.
set -euo pipefail

src="/usr/share/apparmor/extra-profiles/bwrap-userns-restrict"
dst="/etc/apparmor.d/bwrap-userns-restrict"

# Ubuntu 24.04 ships bwrap-userns-restrict in apparmor-profiles; 26.04
# (ubuntu-latest as of 2026-10) does not. Ship workflows pin runs-on to
# ubuntu-24.04 for the same reason OpenSCAD-nightly jobs do (PR #920).
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
fi
[ -f "$src" ] || {
  echo "error: missing ${src} (install apparmor-profiles)" >&2
  if [ "${ID:-}" = "ubuntu" ] && [ "${VERSION_ID:-}" != "24.04" ]; then
    echo "error: AppArmor bwrap-userns-restrict is only expected on ubuntu-24.04; this host is ${PRETTY_NAME:-unknown} (VERSION_ID=${VERSION_ID:-unset}). Pin the job to runs-on: ubuntu-24.04." >&2
  fi
  exit 1
}
command -v bwrap >/dev/null || {
  echo "error: bwrap not on PATH" >&2
  exit 1
}
command -v apparmor_parser >/dev/null || {
  echo "error: apparmor_parser not on PATH" >&2
  exit 1
}

# Copy (not symlink): root-owned 0644 as Cipher requires.
sudo install -o root -g root -m 0644 "$src" "$dst"
sudo apparmor_parser -r "$dst"

# securityfs profiles is root-readable on GHA runners — use sudo.
# Pipe through tee (user-owned dump); sudo only for the read.
profiles_file="/sys/kernel/security/apparmor/profiles"
profiles_dump="$(mktemp)"
cleanup_profiles() { rm -f "$profiles_dump"; }
trap cleanup_profiles EXIT
if ! sudo cat "$profiles_file" 2>/dev/null | tee "$profiles_dump" >/dev/null; then
  echo "error: cannot read ${profiles_file} (even with sudo)" >&2
  exit 1
fi
[ -s "$profiles_dump" ] || {
  echo "error: ${profiles_file} dump is empty" >&2
  exit 1
}
# Both profile names must appear in enforce mode.
if ! grep -E '^bwrap \(enforce\)$' "$profiles_dump" >/dev/null; then
  echo "error: AppArmor profile 'bwrap' not in (enforce):" >&2
  grep -E 'bwrap' "$profiles_dump" >&2 || true
  exit 1
fi
if ! grep -E '^unpriv_bwrap \(enforce\)$' "$profiles_dump" >/dev/null; then
  echo "error: AppArmor profile 'unpriv_bwrap' not in (enforce):" >&2
  grep -E 'bwrap' "$profiles_dump" >&2 || true
  exit 1
fi

sysctl_file="/proc/sys/kernel/apparmor_restrict_unprivileged_userns"
[ -r "$sysctl_file" ] || {
  echo "error: missing ${sysctl_file} (expected on ubuntu-24.04 runners)" >&2
  exit 1
}
sysctl_val="$(tr -d '[:space:]' < "$sysctl_file")"
if [ "$sysctl_val" != "1" ]; then
  echo "error: apparmor_restrict_unprivileged_userns must remain 1 (got ${sysctl_val}); do not clear the sysctl" >&2
  exit 1
fi

# dpkg ownership for the profile source and /usr/bin/bwrap.
dpkg -S "$src" >/dev/null
dpkg -S /usr/bin/bwrap >/dev/null

echo "setup-bwrap-apparmor: bwrap+unpriv_bwrap (enforce), sysctl=${sysctl_val}"
