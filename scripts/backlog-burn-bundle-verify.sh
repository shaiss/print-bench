#!/usr/bin/env bash
# backlog-burn-bundle-verify.sh — digest recheck before ship-bundle upload.
#
# Mirrors the inline ``bundle_verify`` step in .github/workflows/backlog-burn.yml
# so match/mismatch can be exercised offline. Writes match=true only on
# equality; match=false otherwise (Cipher on #953).
#
# Usage:
#   EXPECT_SHA=… BUNDLE_PATH=… ./scripts/backlog-burn-bundle-verify.sh
#   ./scripts/backlog-burn-bundle-verify.sh --selftest
set -euo pipefail

selftest() {
  local tmp fails=0
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/bb-bundle-verify.XXXXXX")"
  # shellcheck disable=SC2064
  trap "rm -rf -- $(printf '%q' "$tmp")" RETURN

  printf 'bundle-body\n' >"$tmp/ok.bundle"
  local ok_sha
  ok_sha="$(sha256sum "$tmp/ok.bundle" | awk '{print $1}')"

  if EXPECT_SHA="$ok_sha" BUNDLE_PATH="$tmp/ok.bundle" GITHUB_OUTPUT="$tmp/ok.out" \
      bash -- "$0"; then
    if grep -qx 'match=true' "$tmp/ok.out"; then
      echo "ok    selftest: matching digest → match=true"
    else
      echo "FAIL  selftest: matching digest missing match=true"; fails=$((fails + 1))
    fi
  else
    echo "FAIL  selftest: matching digest exited non-zero"; fails=$((fails + 1))
  fi

  printf 'other\n' >"$tmp/bad.bundle"
  if EXPECT_SHA="$ok_sha" BUNDLE_PATH="$tmp/bad.bundle" GITHUB_OUTPUT="$tmp/bad.out" \
      bash -- "$0"; then
    echo "FAIL  selftest: mismatch exited 0"; fails=$((fails + 1))
  else
    if grep -qx 'match=false' "$tmp/bad.out"; then
      echo "ok    selftest: mismatch → match=false + nonzero"
    else
      echo "FAIL  selftest: mismatch missing match=false"; fails=$((fails + 1))
    fi
  fi

  if EXPECT_SHA="" BUNDLE_PATH="$tmp/ok.bundle" GITHUB_OUTPUT="$tmp/empty.out" \
      bash -- "$0"; then
    echo "FAIL  selftest: empty expect exited 0"; fails=$((fails + 1))
  else
    if grep -qx 'match=false' "$tmp/empty.out"; then
      echo "ok    selftest: empty expect → match=false"
    else
      echo "FAIL  selftest: empty expect missing match=false"; fails=$((fails + 1))
    fi
  fi

  if [ "$fails" -ne 0 ]; then
    echo "backlog-burn-bundle-verify --selftest: $fails failure(s)" >&2
    return 1
  fi
  echo "selftest: ok"
  return 0
}

if [ "${1:-}" = "--selftest" ]; then
  selftest
  exit $?
fi

: "${BUNDLE_PATH:?BUNDLE_PATH required}"
# EXPECT_SHA may be empty (missing pin) — that is a mismatch, not a usage error.
EXPECT_SHA="${EXPECT_SHA-}"

if [ -z "${EXPECT_SHA}" ] || [ ! -f "$BUNDLE_PATH" ]; then
  echo "::error::bundle missing before upload" >&2
  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    echo "match=false" >> "$GITHUB_OUTPUT"
  fi
  exit 1
fi
got="$(sha256sum "$BUNDLE_PATH" | awk '{print $1}')"
if [ "$got" != "$EXPECT_SHA" ]; then
  echo "::error::bundle digest changed before upload (${got} != ${EXPECT_SHA})" >&2
  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    echo "match=false" >> "$GITHUB_OUTPUT"
  fi
  exit 1
fi
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "match=true" >> "$GITHUB_OUTPUT"
fi
