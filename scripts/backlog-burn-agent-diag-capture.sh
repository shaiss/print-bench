#!/usr/bin/env bash
# backlog-burn-agent-diag-capture.sh — trusted post-agent bootstrap for backlog-burn.
#
# The workflow restores THIS script from the pre-agent START_SHA pin into
# $RUNNER_TEMP (never the worktree copy — the ship agent has Write/Edit) and
# verifies CAPTURE_SHA256 before exec. This bootstrap then:
#   1. restores scripts/backlog-burn-agent-diag.sh from the same pin
#   2. archives tools/provenance/src from the same pin (the redactor)
#   3. writes secret values to a temp file and strips them from the child env
#   4. runs the pinned diag against the execution log
#
# Usage (env-driven, called from backlog-burn.yml capture steps):
#   START_SHA=… DIAG_SHA256=… PROV_ARCHIVE_SHA256=… RUNNER_TEMP=…
#     scripts/backlog-burn-agent-diag-capture.sh <link>
set -euo pipefail

link="${1:?usage: backlog-burn-agent-diag-capture.sh <link>}"

: "${START_SHA:?START_SHA required}"
: "${DIAG_SHA256:?DIAG_SHA256 required}"
: "${PROV_ARCHIVE_SHA256:?PROV_ARCHIVE_SHA256 required}"
: "${RUNNER_TEMP:?RUNNER_TEMP required}"

git_show() {
  /usr/bin/git --no-replace-objects \
    -c core.hooksPath=/dev/null \
    -c core.fsmonitor=false \
    -c core.sshCommand= \
    show "$1"
}

git_archive() {
  /usr/bin/git --no-replace-objects \
    -c core.hooksPath=/dev/null \
    -c core.fsmonitor=false \
    -c core.sshCommand= \
    archive "$1" "$2"
}

# --- restore pinned diag script ---------------------------------------------
blob="$(mktemp "${RUNNER_TEMP}/backlog-burn-agent-diag-blob.XXXXXX")"
if ! git_show "${START_SHA}:scripts/backlog-burn-agent-diag.sh" > "$blob"; then
  echo "::error::could not restore backlog-burn-agent-diag.sh from ${START_SHA}" >&2
  exit 1
fi
got="$(sha256sum "$blob" | awk '{print $1}')"
if [ "$got" != "$DIAG_SHA256" ]; then
  echo "::error::restored backlog-burn-agent-diag.sh sha256 does not match the pre-agent pin" >&2
  exit 1
fi
diag="${RUNNER_TEMP}/backlog-burn-agent-diag.sh"
mv -f "$blob" "$diag"
chmod +x "$diag"

# --- restore pinned provenance redactor (never worktree tools/provenance) ---
arch="$(mktemp "${RUNNER_TEMP}/provenance-src.tar.XXXXXX")"
if ! git_archive "$START_SHA" tools/provenance/src > "$arch"; then
  echo "::error::could not archive tools/provenance/src from ${START_SHA}" >&2
  rm -f -- "$arch"
  exit 1
fi
got_arch="$(sha256sum "$arch" | awk '{print $1}')"
if [ "$got_arch" != "$PROV_ARCHIVE_SHA256" ]; then
  echo "::error::restored tools/provenance/src archive sha256 does not match the pre-agent pin" >&2
  rm -f -- "$arch"
  exit 1
fi
prov_root="${RUNNER_TEMP}/pinned-provenance-${link}"
rm -rf -- "$prov_root"
mkdir -p -- "$prov_root"
# Archive paths are tools/provenance/src/... — strip to leave the import root
# (a directory that contains the `provenance` package).
tar -x -f "$arch" -C "$prov_root"
rm -f -- "$arch"
prov_src="${prov_root}/tools/provenance/src"
if [ ! -d "$prov_src/provenance" ]; then
  echo "::error::pinned provenance archive missing provenance package at ${prov_src}" >&2
  exit 1
fi

# --- secrets file (trusted shell); child runs without token env vars --------
secrets_file="$(mktemp "${RUNNER_TEMP}/backlog-burn-diag-secrets.XXXXXX")"
cleanup() { rm -f -- "$secrets_file"; }
trap cleanup EXIT
{
  for key in \
    GITHUB_TOKEN GH_TOKEN ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN \
    ZAI_KEY OPENAI_API_KEY OPENROUTER_API_KEY REGEN_TOKEN \
    ACTIONS_RUNTIME_TOKEN ACTIONS_ID_TOKEN_REQUEST_TOKEN
  do
    val="${!key-}"
    if [ -n "$val" ]; then
      printf '%s\n' "$val"
    fi
  done
} >"$secrets_file"

# Wipe the per-link out-dir before writing so a prior ship step cannot leave
# planted files beside diag.json for a recursive artifact upload to pick up.
out_dir="${RUNNER_TEMP}/backlog-burn-agent-diag/link-${link}"
rm -rf -- "$out_dir"
mkdir -p -- "$out_dir"

# Strip credential env from the diag child: secrets reach it only via the
# temp file written above (for redact()), never via environ after this point.
env -u GITHUB_TOKEN -u GH_TOKEN \
    -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN \
    -u ZAI_KEY -u OPENAI_API_KEY -u OPENROUTER_API_KEY -u REGEN_TOKEN \
    -u ACTIONS_RUNTIME_TOKEN -u ACTIONS_ID_TOKEN_REQUEST_TOKEN \
  "$diag" --link "$link" \
    --secrets-file "$secrets_file" \
    --provenance-src "$prov_src" \
    --out-dir "$out_dir"
